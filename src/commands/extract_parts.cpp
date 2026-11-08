// 고른 파트만 뽑아 **그대로 돌아가는** 덱으로 쓴다 — 어려운 부분은 '뽑기' 가 아니라 '남은 것이
// 멀쩡한가' 다
//
// 요청서(CAE그룹 v1.0, 2026-10-10) ①. 61파트 Q8 Close 덱(2.32GB)에서 몇 파트만 떼어
// `unfold` → `prestress` → `relax` 로 보내려는데, 그 떼어내기를 매번 손으로 했다.
//
// ★설계 판단은 둘이다.
//   1) **잘라낸 쪽이 아니라 남긴 쪽을 검증한다.** 산출 덱을 **되읽어** '요소가 가리키는 절점·
//      파트·섹션·재질이 전부 그 덱 안에 있다' 를 op 이 스스로 찍는다(요청서 §2 의 3번).
//      수를 세는 것은 전제 위에 있지만 되읽기는 전제가 없다.
//   2) **모르는 것을 조용히 버리지 않는다.** 뽑은 파트의 요소를 담은 `*ELEMENT_*` 변형을
//      우리가 못 읽으면 **거절한다**(rc=1). 조용히 빠뜨린 덱은 그럴듯하게 돌면서 틀린다.
//      그 밖에 버린 키워드는 전부 `dropped_keywords` 로 센다 — 안 보이는 손실을 만들지 않는다.
//
// ID·바이트 보존: 줄을 **다시 쓰지 않고** 고른 줄을 그대로 흘린다. `renumber: true` 일 때만
// 칸을 **제자리에서** 갈아 끼운다(좌표 글자를 다시 포맷하지 않으므로 실수 왕복 오차가 없다).
//
// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/extract-parts]]

#include "extract_parts.h"

#include "cli/ConsoleOutput.h"
#include "parser/CardFields.h"
#include "parser/DeckScan.h"
#include "parser/DeckWriter.h"
#include "parser/ElementCardLayout.h"
#include "parser/IncludeClosure.h"   // 쓸 파일이 입력 덱을 덮는지(sameFile · clobberPair)
#include "util/StagedWrite.h"       // 임시 파일 + 바꿔 넣기(apply_carryover_plan 과 같은 도우미)
#include "util/Utf8.h"              // 보고 글자를 바른 UTF-8 로(apply_carryover_plan 보고와 같은 함수)
#include "util/YamlComment.h"

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <system_error>
#include <vector>

using KooRemapper::ConsoleOutput;
using namespace KooRemapper::cards;      // NOLINT(google-build-using-namespace)
using namespace KooRemapper::deckscan;   // NOLINT(google-build-using-namespace)

namespace {

std::string stripQuotes(const std::string& s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}

// `batt*` · `*case` · `cell_?` — 쉘 글롭 중 `*` 와 `?` 만. 대소문자를 무시한다.
bool globMatch(const std::string& pat, const std::string& txt) {
    size_t p = 0, t = 0, star = std::string::npos, mark = 0;
    while (t < txt.size()) {
        if (p < pat.size() && (pat[p] == '?' || pat[p] == txt[t])) { ++p; ++t; }
        else if (p < pat.size() && pat[p] == '*') { star = p++; mark = t; }
        else if (star != std::string::npos) { p = star + 1; t = ++mark; }
        else return false;
    }
    while (p < pat.size() && pat[p] == '*') ++p;
    return p == pat.size();
}

// ─────────────────────────────────────────────────────────────────────────────
// 설정
// ─────────────────────────────────────────────────────────────────────────────

struct Opts {
    std::string model, output, reportPath;
    std::vector<int> parts;
    std::vector<std::string> partTitles;
    bool incNodes = true;
    bool incSets = true;             // sets: referenced(기본) / none
    bool incMaterials = true;
    bool incSections = true;
    bool renumber = false;
    bool verify = true;
};

// ─────────────────────────────────────────────────────────────────────────────
// `*PART` 표
// ─────────────────────────────────────────────────────────────────────────────

struct PartDef {
    int pid = 0, secid = 0, mid = 0, eosid = 0, hgid = 0, tmid = 0;
    std::string title;
};

struct DeckIndex {
    std::map<int, PartDef> parts;              // `*PART`/`*PART_TITLE` 로 정의된 것
    std::map<int, int> secElform;              // SECID → ELFORM
    std::vector<std::string> partVariants;     // `*PART_INERTIA` 등
    int fieldWidth = 8;
    // `*SET_PART`(목록 · 열 꼴)의 SID → PID — `*ELEMENT_MASS_PART_SET` 의 세트를 풀 때만 쓴다(2026-11-07 검토 #5)
    std::map<int, std::vector<int>> partSets;
    std::set<int> partSetsOpaque;              // 멤버를 ID 로 못 읽는 꼴(`_ADD` · `_GENERAL` · `_GENERATE` …) · 두 번 정의된 SID
};

// ── 인클루드 — 정본 닫힘(include_closure::readPaths)을 따른다 ──────────────────────────────────
// 주 덱 폴더 먼저 · 그다음 `*INCLUDE_PATH` 폴더(Vol_I 181591) · `␣+` 이음 · 인클루드 안 `*END` 는 그 파일만 끝낸다 · 깊이 16 · 같은 파일은
// 한 번. 예전엔 패스마다 포함하는 파일의 폴더로 풀고 `*INCLUDE_PATH` 를 몰랐으며 깊이 8 에서 말없이 멈췄다 — 9단째 인클루드의 고른 파트
// 셸이 rc 0 · 되읽기 0 으로 빠졌다(재검토 N3 · D1). 패스는 `*INCLUDE` 블록의 이름 줄(그 이름의 마지막 줄)에서 이 표를 묻는다.
class IncludeMap {
public:
    explicit IncludeMap(const std::string& model) : clo_(KooRemapper::include_closure::readPaths(model)) {
        for (const auto& r : clo_.refs) byLast_[{r.file, r.lastLine}] = &r;
    }
    IncludeMap(const IncludeMap&) = delete;
    IncludeMap& operator=(const IncludeMap&) = delete;
    const KooRemapper::include_closure::Closure& closure() const { return clo_; }
    // 그 파일 그 줄에서 끝나는 이름 — 없으면 nullptr(이름의 앞줄 · 주석 · 닫힘이 보지 않은 줄)
    const KooRemapper::include_closure::NameRef* at(const std::string& file, size_t line) const {
        const auto it = byLast_.find({file, line});
        return it == byLast_.end() ? nullptr : it->second;
    }
    // 따라갈 경로(Followed 일 때만) — 아니면 빈 글자
    std::string follow(const std::string& file, size_t line) const {
        const auto* r = at(file, line);
        return r && r->what == KooRemapper::include_closure::NameRef::What::Followed ? r->path : std::string();
    }

private:
    KooRemapper::include_closure::Closure clo_;
    std::map<std::pair<std::string, size_t>, const KooRemapper::include_closure::NameRef*> byLast_;
};

// `*PART` 블록은 '제목 줄 + 카드 2' 가 **쌍으로 반복**된다(제목은 비워 둘 수 있으나 생략 못 한다).
// ⚠ 그래서 **빈 줄도 카드 줄로 센다** — 건너뛰면 다음 파트의 제목 자리가 한 칸 밀려 PID 가
// 통째로 어긋난다. 주석(`$`)만 뺀다.
//
// ⚠ 덱 전문을 메모리에 들지 않는다(2.32GB 전제) — **블록 하나만** 버퍼한다.
// `im` — 인클루드를 따라갈 표(되읽기는 홀로 선 산출을 보니 nullptr)
void indexDeck(const std::string& path, DeckIndex& idx, std::set<std::string>& visited, const IncludeMap* im) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    size_t lineNo = 0;
    const int sfw = 10;                        // `*PART` 카드 2 와 `*SECTION_*` 은 8I10 이다
    std::string line, kw;
    std::vector<std::string> buf;              // 지금 블록의 카드 줄
    int setW = 10;                             // `*SET_PART` 카드 폭(8I10 · long 이면 20)

    auto flush = [&]() {
        if (kw == "*PART" || kw == "*PART_TITLE") {
            for (size_t k = 0; k + 1 < buf.size(); k += 2) {
                auto f = cardFields(buf[k + 1], sfw);
                PartDef pd;
                pd.pid = fieldInt(f, 0);
                if (pd.pid <= 0) continue;
                pd.secid = fieldInt(f, 1);
                pd.mid   = fieldInt(f, 2);
                pd.eosid = fieldInt(f, 3);
                pd.hgid  = fieldInt(f, 4);
                pd.tmid  = fieldInt(f, 7);
                pd.title = trim(buf[k]);
                if (!idx.parts.count(pd.pid)) idx.parts[pd.pid] = pd;
            }
        } else if (starts(kw, "*SECTION_SOLID")) {
            int want = titleLines(kw), di = 0;
            for (const auto& l : buf) {
                if (!isDataLine(l)) continue;
                if (di == want) {
                    auto f = cardFields(l, sfw);
                    int sid = fieldInt(f, 0);
                    if (sid > 0 && !idx.secElform.count(sid)) idx.secElform[sid] = fieldInt(f, 1);
                }
                ++di;
            }
        } else if (starts(kw, "*SET_PART")) {
            // 목록 꼴 · 열 꼴만 멤버를 읽는다(열 꼴은 줄마다 칸 0 이 PID — 속성 A1-A4 는 멤버가 아니다)
            const auto kind = KooRemapper::deckscan::classifySetNode(kw);
            const bool list = kind != KooRemapper::deckscan::SetKind::OPAQUE;
            const bool column = kind == KooRemapper::deckscan::SetKind::COLUMN;
            const int tn = titleLines(kw);
            int di = 0, sid = 0;
            std::vector<int> mem;
            for (const auto& l : buf) {
                if (!isDataLine(l)) continue;
                if (di < tn) { ++di; continue; }
                const auto f = cardFields(l, setW);
                if (di++ == tn) { sid = fieldInt(f, 0); continue; }
                for (size_t q = 0; q < (column ? std::min<size_t>(1, f.size()) : f.size()); ++q) {
                    const int v = fieldInt(f, q);
                    if (v > 0) mem.push_back(v);
                }
            }
            if (sid > 0) {
                if (!list || idx.partSets.count(sid) || idx.partSetsOpaque.count(sid)) {
                    idx.partSets.erase(sid);
                    idx.partSetsOpaque.insert(sid);
                } else {
                    idx.partSets[sid] = mem;
                }
            }
        }
        buf.clear();
    };

    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        ++lineNo;
        size_t g = line.find_first_not_of(" \t");
        if (isKeywordLine(line)) {   // 1열 규칙(리더와 같다) — 들여쓴 `*` 줄은 데이터다
            flush();
            kw = kwBare(keywordToken(line));
            if (kw == "*END") break;                       // 그 파일은 여기서 끝난다(Vol_I 179654 — 닫힘과 같다)
            if (kw == "*KEYWORD") {
                int w = KooRemapper::keywordCardDeckWidth(line);
                if (w > 0) idx.fieldWidth = w;
            }
            setW = KooRemapper::keywordFieldWidth(line, idx.fieldWidth) >= 20 ? 20 : 10;
            if (starts(kw, "*PART") && kw != "*PART" && kw != "*PART_TITLE" &&
                std::find(idx.partVariants.begin(), idx.partVariants.end(), kw) ==
                    idx.partVariants.end())
                idx.partVariants.push_back(kw);
            continue;
        }
        if (kw == "*INCLUDE") {
            if (im) {
                const std::string next = im->follow(path, lineNo);
                if (!next.empty()) indexDeck(next, idx, visited, im);
            }
            continue;
        }
        if (kw != "*PART" && kw != "*PART_TITLE" && !starts(kw, "*SECTION_SOLID") && !starts(kw, "*SET_PART")) continue;
        if (g != std::string::npos && line[g] == '$') continue;
        buf.push_back(line);
    }
    flush();
}

std::map<int, int> pidNodeCounts(const DeckIndex& idx) {
    std::map<int, int> out;
    for (const auto& kv : idx.parts) {
        auto it = idx.secElform.find(kv.second.secid);
        if (it == idx.secElform.end()) continue;
        int n = KooRemapper::solidNodesFromElform(it->second);
        if (n > 0) out[kv.first] = n;
    }
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// 패스 1 — 고른 파트의 요소가 쓰는 절점·요소 ID
// ─────────────────────────────────────────────────────────────────────────────

struct Picked {
    std::vector<int> nodes;                 // 정렬·유일
    std::vector<int> solids, shells, tshells;
    std::vector<int> allElems;              // 세 가지 합집합(전역 번호 다시 매길 때)
    bool elemIdCollision = false;           // 종류가 달라도 EID 가 겹친다
    long long cards = 0;
    long long auxCards = 0;                               // 보·질량·이산 족에서 고른 카드
    std::vector<std::string> auxKws;                      // 그 중 **칸 자리를 아는** 키워드
    std::map<std::string, long long> opaqueElemTouched;   // 못 읽는 변형이 고른 파트를 담았다
    std::map<std::string, long long> opaqueElemOther;     // 담지 않았다(그냥 버린다)
    long long seatbeltCards = 0;                          // 고른 파트의 `*ELEMENT_SEATBELT` 카드
    std::vector<std::string> seatbeltDevices;             // 덱의 안전띠 장치 키워드 블록 — 「파일:줄 키워드」
    // ── 보 장치 · 질량 얹기(2026-11-07 검토 #5) ──
    std::vector<int> beamEids;                            // 고른 파트의 보(`*ELEMENT_BEAM*`) 요소 번호
    struct BeamDevice { std::string where; std::vector<int> refs; };
    std::vector<BeamDevice> beamDevices;                  // `*ELEMENT_BEAM_PULLEY` · `_SOURCE` 줄 — 가리키는 보 요소 번호
    long long massPartCards = 0;                          // 고른 파트(세트)의 `*ELEMENT_MASS_PART(_SET)` 줄(요소가 아니다 — auxCards 와 따로)
    long long massSetCards = 0;                           // 그 가운데 `_SET`(세트가 실려야 한다)
    std::vector<std::string> massSetRefused;              // 세트를 일부만 고르거나 풀 수 없는 `*ELEMENT_MASS_PART_SET` 줄
    // ── 보 족 줄이 두 가지로 읽힐 때(넓은 칸 뒤 칸 — 2026-11-07 사용자 결정 「둘 다 남기고 번호 매기기는 거절」) ──
    std::vector<int> altNodes;                            // 고른 줄을 다른 읽기로만 읽을 때 나오는 절점 — 덱에 있으면 싣는다
    struct AuxLine { std::string where; std::vector<int> altVsManual; bool placeable = true; };
    std::vector<AuxLine> renumberRisk;                    // 고른 보 족 줄 가운데 번호를 제자리에 못 바꿔 쓸 수 있는 것
    std::vector<std::string> unreadableAux;               // 칸으로 읽지 못한 보 족 줄(쓰는 칸에 빈칸 — `auxLineUnreadable`) 「파일:줄」
    std::vector<std::string> unreadablePicked;            // 그 가운데 고른 파트에 있을 수 있는 줄 「파일:줄 키워드 — 까닭」(거절한다)
    std::vector<std::string> ambiguousPid;                // 읽기마다 PID 가 갈리고 그 하나가 고른 PID 인 줄
};

// 그 번호들(정렬) 가운데 덱(닫힘)의 `*NODE` 가 정의한 것을 `found` 에 — 보 족 줄의 다른 읽기가 말하는 절점이 덱에 있나를 잴 때만
// 부른다(드물다 · 덱 전체의 절점 표를 들지 않는다). 인클루드는 scanElements 와 같이 맨 `*INCLUDE` 를 따라간다.
void definedNodesAmong(const std::string& path, const DeckIndex& idx, const std::vector<int>& want,
                       std::vector<int>& found, std::set<std::string>& visited, const IncludeMap& im) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    std::string line, kw;
    int fw = idx.fieldWidth;
    size_t lineNo = 0;
    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        ++lineNo;
        if (isKeywordLine(line)) {   // 1열 규칙(리더와 같다)
            kw = kwBare(keywordToken(line));
            if (kw == "*END") break;
            fw = KooRemapper::keywordFieldWidth(line, idx.fieldWidth);
            continue;
        }
        if (!isDataLine(line)) continue;
        if (kw == "*INCLUDE") {
            const std::string next = im.follow(path, lineNo);
            if (!next.empty()) definedNodesAmong(next, idx, want, found, visited, im);
            continue;
        }
        if (kw != "*NODE") continue;
        int nid = 0;
        double xyz[3];
        if (readNodeLine(line, fw, nid, xyz) && inSorted(want, nid)) found.push_back(nid);
    }
}

// 보 족 Card 1 의 PID 후보 — 하나로 읽은 PID(`auxPrimaryFields` — 설명서 칸 · 0 이면 PID 없음)가 먼저, 다른 읽기(정수 폭)가
// 다른 PID 를 말하면 그것이 덱의 파트(`*PART` 표)일 때만 더한다 — 정수꼴 질량값(「1000」)이나 빈 칸을 PID 로 세어 멀쩡한 줄을
// 모호하다 하지 않는다. 후보가 둘 이상이고 그 하나라도 고른 PID 면 실을지 버릴지 정할 수 없다(2026-11-07 「둘 다 남기고 …」 — 질량 PID).
// 패스 1(scanElements)과 패스 2(Writer)가 같이 쓴다 — 고르는 판정이 갈리면 싣는 줄과 센 절점이 어긋난다.
std::vector<int> auxPidCandidates(const KooRemapper::AuxElementCard& a, const KooRemapper::AuxCardReadings& rd,
                                  const DeckIndex& idx) {
    std::vector<int> out;
    if (!a.hasPart || a.partField < 0) return out;
    const int prim = fieldInt(KooRemapper::auxPrimaryFields(rd), (size_t)a.partField);
    out.push_back(prim);
    for (int p : KooRemapper::auxPidsOf(a, rd))
        if (p != prim && idx.parts.count(p)) out.push_back(p);
    return out;
}

// 칸으로 읽지 못한 보 족 줄(`auxLineUnreadable`)이 고른 파트에 있을 수 있나 — 있으면 까닭(비었으면 없다). 그 줄의 정수(`auxLineInts` ·
// PID 칸의 값도) 가운데 고른 PID 가 있으면 있을 수 있다 — 넘치게 센다. PID 칸이 깨끗해도 그것만 믿지 않는다: 짧은 공백 줄은 PID 칸에
// 다른 번호의 조각이 든다(`45 2 103 105` 의 9-16열 「105」 · 2026-11-08 여섯째 검토 S1 · 「지키는 쪽은 잃지 않는다」)
std::string unreadablePickedWhy(const KooRemapper::AuxElementCard& a, const std::vector<std::string>& card1, const std::string& line,
                                const std::vector<int>& sel) {
    std::vector<int> cand = KooRemapper::auxLineInts(line);
    const std::string pf =
        a.partField >= 0 && static_cast<size_t>(a.partField) < card1.size() ? card1[static_cast<size_t>(a.partField)] : std::string();
    int p = 0;
    if (!pf.empty() && pf.find_first_of(" \t") == std::string::npos && toInt(pf, p) && p > 0) cand.push_back(p);
    sortUnique(cand);
    std::string hit;
    for (int v : cand)
        if (inSorted(sel, v)) hit += (hit.empty() ? "" : ", ") + std::to_string(v);
    return hit.empty() ? std::string() : "그 줄의 PID 를 칸으로 단정하지 못했고(쓰는 칸에 빈칸) 그 줄의 정수 가운데 고른 PID " + hit + " 가 있다";
}

// `*ELEMENT_MASS_PART_SET` 의 파트 세트를 고른 파트와 견준다 — 0 = 세트에 고른 파트가 없다(버린다) · 1 = 세트가 다 고른 파트다
// (싣는다) · -1 = 실을지 버릴지 정할 수 없다(`why`). 질량은 세트 전체에 나눠 얹히니 일부만 실으면 남은 파트에 얹히는 질량이 바뀐다.
// 세트를 못 풀면(목록 꼴이 아니다 · 덱에서 못 찾았다) 고른 파트에 닿는지 모른다 — 정할 수 없다로 친다.
int massSetVerdict(int sid, const DeckIndex& idx, const std::vector<int>& sel, std::string& why) {
    const auto it = idx.partSets.find(sid);
    if (sid <= 0 || it == idx.partSets.end() || idx.partSetsOpaque.count(sid)) {
        why = "파트 세트 " + std::to_string(sid) + " 을 풀 수 없다(목록 · 열 꼴 *SET_PART 가 아니거나 덱 · 맨 *INCLUDE 에서 못 찾았다)";
        return -1;
    }
    std::string all, mine;
    size_t in = 0;
    for (int p : it->second) {
        all += (all.empty() ? "" : ", ") + std::to_string(p);
        if (inSorted(sel, p)) { ++in; mine += (mine.empty() ? "" : ", ") + std::to_string(p); }
    }
    if (in == 0) return 0;
    if (in == it->second.size()) return 1;
    why = "파트 세트 " + std::to_string(sid) + "(" + all + ") 가운데 " + mine + " 만 고른다 — 나눠 얹는 질량이 남은 파트에 다르게 간다";
    return -1;
}

void scanElements(const std::string& path, const std::vector<int>& sel, const DeckIndex& idx,
                  const std::map<int, int>& pidNodes, Picked& pk,
                  std::set<std::string>& visited, const IncludeMap& im, bool top = true) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    std::string line, kw;
    int fw = idx.fieldWidth;
    KooRemapper::ElementKeywordInfo info;
    KooRemapper::ElementCardSpan span;
    int remaining = 0, lineIdx = 0;
    std::vector<std::string> card1;
    bool inElem = false, opaque = false, picked = false, inInclude = false;
    std::string deviceAt;   // 데이터 줄을 기다리는 안전띠 장치 블록 「파일:줄 키워드」 — 첫 데이터 줄에서 센다(빈 블록은 장치가 없다)
    // 보·질량·이산 족 — 공용 판정기의 별도 축이 칸 자리를 안다(ElementCardLayout.h 의 인용).
    KooRemapper::AuxElementCard aux;
    int auxRemaining = 0, auxLineIdx = 0;
    bool auxPicked = false;
    std::vector<std::string> auxCard1;
    size_t lineNo = 0;

    while (std::getline(in, line)) {
        ++lineNo;
        size_t g = line.find_first_not_of(" \t\r\n");
        if (isKeywordLine(line)) {   // 1열 규칙(리더와 같다)
            remaining = 0;
            kw = kwBare(keywordToken(line));
            if (kw == "*END") break;                       // 그 파일은 여기서 끝난다(닫힘과 같다)
            fw = KooRemapper::keywordFieldWidth(line, idx.fieldWidth);
            deviceAt.clear();
            if (kw == "*INCLUDE") { inElem = false; inInclude = true; continue; }
            inInclude = false;
            inElem = starts(kw, "*ELEMENT");
            if (inElem) {
                info = KooRemapper::parseElementKeyword(line);
                opaque = (info.family == KooRemapper::ElemFamily::NONE || !info.supported);
                aux = opaque ? KooRemapper::auxElementCard(line) : KooRemapper::AuxElementCard();
                auxRemaining = 0;
                if (aux.supported &&
                    std::find(pk.auxKws.begin(), pk.auxKws.end(), kw) == pk.auxKws.end())
                    pk.auxKws.push_back(kw);
                // 안전띠 **장치** 키워드(`_PRETENSIONER` · `_RETRACTOR` · `_SENSOR` · `_SLIPRING` · 모르는 `_*`)는 PID 칸이 없다 —
                // 어느 띠에 붙었는지 증명할 수 없어 자리를 적어 둔다(아래 runExtractParts 의 거절). 데이터 줄이 있어야 장치다 —
                // 키워드 줄만 있는 블록은 세지 않는다. `_ACCELEROMETER` 는 띠가 아니라 절점의 가속도를 재는 장치라(Vol_I) 띠와
                // 무관할 수 있다 — 거절하지 않고 다른 모르는 카드처럼 버려 `dropped_keywords` 에 센다(사용자 결정 2026-11-07)
                if (aux.family == KooRemapper::AuxFamily::SEATBELT && !aux.supported &&
                    kw.rfind("*ELEMENT_SEATBELT_ACCELEROMETER", 0) != 0)
                    deviceAt = path + ":" + std::to_string(lineNo) + " " + kw;
            }
            continue;
        }
        if (inInclude) {
            if (!isDataLine(line)) continue;
            const std::string next = im.follow(path, lineNo);
            if (!next.empty()) scanElements(next, sel, idx, pidNodes, pk, visited, im, false);
            continue;
        }
        if (!inElem) continue;
        if (g != std::string::npos && line[g] == '$') continue;
        // 카드 밖의 빈 줄만 건너뛴다 — 보 족 카드(auxRemaining)도 셈에 든다. 비워 둔 옵션 카드도 카드다(LS-PrePost 도 그렇게
        // 읽는다). 예전엔 격자 셈만 보아 다음 요소의 Card 1 을 그 카드로 삼켜 절점을 놓쳤다(되읽기 실패 · 2026-11-07 검토).
        if (g == std::string::npos && remaining == 0 && auxRemaining == 0) continue;

        if (opaque && aux.supported) {
            // ★칸 자리를 **안다** — PID 칸도 족마다 다르다(`*ELEMENT_MASS` 는 칸 차례 3 = 33-40열 —
            //   MASS 가 E16 이라 칸은 공용 판정기 `auxCardReadings` 가 자른다).
            //   `*ELEMENT_PLOTEL` 은 PID 가 없어 여기서 고르지 않고, 쓰기 쪽이 '두 절점이 다
            //   남았나' 로 판정한다(그 줄은 표시용이고 파트에 속하지 않는다).
            if (auxRemaining == 0) {
                const auto rd = KooRemapper::auxCardReadings(aux, line, fw);
                auxCard1 = KooRemapper::auxPrimaryFields(rd);
                auxLineIdx = 0;
                auxRemaining = aux.lines;
                // PID 는 후보 전부를 본다 — 넓은 칸 뒤 PID(질량)는 설명서 칸 · 정수 폭으로 갈릴 수 있다. 갈리는데 그 하나가 고른 PID 면
                // 실을지 버릴지 정할 수 없다 — 줄을 적어 두고 runExtractParts 가 거절한다(조용히 싣거나 버리지 않는다)
                const std::string where = path + ":" + std::to_string(lineNo) + " " + kw;
                if (KooRemapper::auxLineUnreadable(rd)) pk.unreadableAux.push_back(where);   // [WARN] — runExtractParts 가 댄다
                // ★칸으로 읽지 못한 줄이 고른 파트에 있을 수 있으면 거절한다 — 실으면 절점이, 버리면 요소가 빠진다(2026-11-08 여섯째 검토 S1 —
                //   예전엔 조용히 버렸다 · rc 0). 질량 얹기 세트(`_PART_SET`)는 세트를 못 풀어 아래 massSetVerdict 가 따로 거절한다
                if (KooRemapper::auxLineUnreadable(rd) && aux.hasPart && !aux.partIsSet) {
                    const std::string why = unreadablePickedWhy(aux, auxCard1, line, sel);
                    if (!why.empty()) pk.unreadablePicked.push_back(where + " — " + why);
                }
                std::vector<int> pids;
                bool hit = false;
                if (aux.partIsSet) {
                    // `*ELEMENT_MASS_PART_SET` — 칸 0 이 파트 세트 ID 다. 세트를 풀어 견준다(일부만 · 못 풀면 거절할 줄로 적는다)
                    std::string why;
                    const int v = massSetVerdict(fieldInt(auxCard1, 0), idx, sel, why);
                    if (v < 0) pk.massSetRefused.push_back(where + " — " + why);
                    hit = v == 1;
                } else {
                    pids = auxPidCandidates(aux, rd, idx);
                    for (int p : pids) hit = hit || inSorted(sel, p);
                }
                auxPicked = aux.hasPart && hit;
                if (auxPicked && pids.size() > 1) {
                    std::string ps;
                    for (int p : pids) ps += (ps.empty() ? "" : " / ") + (p > 0 ? std::to_string(p) : std::string("0(없음)"));
                    pk.ambiguousPid.push_back(where + " — PID " + ps);
                }
                if (auxPicked && !aux.hasEid) {
                    // 질량 얹기(`*ELEMENT_MASS_PART(_SET)`)는 요소가 아니다 — 요소 수에 넣지 않는다(EID · 절점 칸이 없다)
                    ++pk.massPartCards;
                    if (aux.partIsSet) ++pk.massSetCards;
                } else if (auxPicked) {
                    ++pk.auxCards;
                    if (aux.family == KooRemapper::AuxFamily::SEATBELT) ++pk.seatbeltCards;
                    if (aux.family == KooRemapper::AuxFamily::BEAM) pk.beamEids.push_back(fieldInt(auxCard1, 0));
                    // 절점 — 든 읽기가 다 말하는 절점은 싣고, 한 읽기만 말하는 절점은 덱에 있으면 싣는다(둘 다 남긴다 — 갈리는 줄의
                    // 설명서 칸은 덱에 없는 번호를 말할 수 있다 · 11-08)
                    for (int v : KooRemapper::auxNodesSure(aux, rd)) pk.nodes.push_back(v);
                    for (int v : KooRemapper::auxNodesUnsure(aux, rd)) pk.altNodes.push_back(v);
                    // 번호 매기기는 설명서 칸(LS-DYNA 가 읽는 칸)에 쓴다. 제자리에 못 쓰거나(콤마 · 절점 칸에 공백) 그 줄을 그렇게
                    // 썼을 수 있는 다른 읽기가 설명서 칸에 없는 절점을 말하면 적어 둔다 — 그 절점이 덱에 있으면 모호하다(runExtractParts 가
                    // 덱에서 잰다). 설명서 꼴 줄(N4 가 65-72열에 있다)은 정수 폭 읽기가 갈림을 말하지 않는다(`auxNodesDisputed`)
                    const auto altM = KooRemapper::auxNodesDisputed(aux, rd);
                    const bool placeable = KooRemapper::auxManualNodesPlaceable(aux, rd);
                    if (!placeable || !altM.empty()) pk.renumberRisk.push_back({where, altM, placeable});
                }
            } else if (auxPicked && KooRemapper::auxOptNodeFields(aux, auxLineIdx)) {
                // 옵션 카드의 절점 — 보 `_WARPAGE` 의 SN1 · SN2(스칼라 절점 — `*NODE_SCALAR` 줄을 싣는다) · `_ELBOW` 의 가운데 절점
                // MN(8칸 표). 콤마 줄 · 칸 안에 빈칸 · 번호 칸 안에서 시작하는 `$` 주석이면 번호를 제자리에 못 바꾼다(재검토 D2 — 주석이
                // 겹친 MN 에 새 번호를 쓰면 `$` 를 덮어 주석 글자가 칸 2 의 값이 됐다). 예전엔 SN 을 아무도 안 읽었다(셋째 묶음)
                for (int v : KooRemapper::auxOptNodesOf(aux, auxLineIdx, line, fw)) pk.nodes.push_back(v);
                if (!KooRemapper::auxOptNodesPlaceable(aux, auxLineIdx, line, fw))
                    pk.renumberRisk.push_back({path + ":" + std::to_string(lineNo) + " " + kw, {}, false});
            }
            ++auxLineIdx;
            if (--auxRemaining <= 0) auxRemaining = 0;
            continue;
        }
        if (opaque) {
            // 아직도 줄 수를 모르는 변형. **고른 파트를 담았는지**만 판정한다 — 담았으면
            // 거절해야 한다(조용히 빠뜨린 덱이 더 나쁘다).
            //
            // ⚠ PID 칸을 1 로 **가정하면 안 된다.** 족은 알고 줄 수만 모르는 경우가 있고
            //   (`*ELEMENT_MASS_NODE_SET` 은 PID 가 칸 차례 **3** — 33-40열이다), 1 로 가정하면 그 카드가
            //   '안 고른 파트' 로 분류돼 **조용히 버려진다**(실측으로 회귀 L-14 가 잡았다).
            //   족은 아는데 **PID 칸이 없다**고 표가 말하면(`*ELEMENT_SEATBELT_ACCELEROMETER` 같은 별개 키워드 · 플롯 요소)
            //   PID 를 짐작하지 않는다 — 예전엔 칸 1(가속도계의 절점 · 리트랙터의 절점)을 PID 로 읽어, 그 번호가 고른 PID 와
            //   우연히 같으면 「고른 파트를 담았다」 고 거절했다. 여기서는 싣지 않는 카드로 센다 — 안전띠 장치(가속도계 · 데이터 줄
            //   없는 블록은 빼고)는 고른 파트에 안전띠 요소가 있으면 runExtractParts 가 통째로 거절한다(띠에 붙었는지 증명할 수 없다).
            if (aux.family != KooRemapper::AuxFamily::NONE && !aux.hasPart) {
                if (!deviceAt.empty()) { pk.seatbeltDevices.push_back(deviceAt); deviceAt.clear(); }
                // 보 장치(`*ELEMENT_BEAM_PULLEY` · `_SOURCE` — 8칸 표)는 가리키는 보 요소 번호를 적어 둔다(runExtractParts 가 고른 보와 견준다)
                if (!aux.elemRefFields.empty()) {
                    const auto f = cardFields(line, fw >= 20 ? 20 : 10);
                    Picked::BeamDevice bd{path + ":" + std::to_string(lineNo) + " " + kw, {}};
                    for (int q : aux.elemRefFields) bd.refs.push_back(fieldInt(f, (size_t)q));
                    pk.beamDevices.push_back(std::move(bd));
                }
                ++pk.opaqueElemOther[kw];
                continue;
            }
            // 족을 알면 그 PID 칸의 후보 전부(넓은 칸 뒤 PID 는 읽기마다 갈린다 — `auxPidCandidates`), 모르면 칸 1
            const auto rd = KooRemapper::auxCardReadings(aux, line, fw);
            bool touched = false;
            if (aux.family != KooRemapper::AuxFamily::NONE && aux.partField >= 0) {
                for (int p : auxPidCandidates(aux, rd, idx)) touched = touched || inSorted(sel, p);
            } else {
                const int pid = fieldInt(KooRemapper::auxPrimaryFields(rd), 1);
                touched = pid > 0 && inSorted(sel, pid);
            }
            if (touched) ++pk.opaqueElemTouched[kw];
            else         ++pk.opaqueElemOther[kw];
            continue;
        }
        if (remaining == 0) {
            card1 = cardFields(line, fw);
            int pid = fieldInt(card1, 1);
            int pidN = 0;
            auto pit = pidNodes.find(pid);
            if (pit != pidNodes.end()) pidN = pit->second;
            span = KooRemapper::elementCardSpan(info, card1, pidN);
            lineIdx = 0;
            remaining = span.lines;
            picked = (pid > 0 && inSorted(sel, pid));
            if (picked) {
                ++pk.cards;
                int eid = fieldInt(card1, 0);
                if (eid > 0) {
                    if (info.family == KooRemapper::ElemFamily::SOLID)       pk.solids.push_back(eid);
                    else if (info.family == KooRemapper::ElemFamily::SHELL)  pk.shells.push_back(eid);
                    else                                                     pk.tshells.push_back(eid);
                }
            }
        }
        if (picked && lineIdx >= span.nodeFirst && lineIdx < span.nodeFirst + span.nodeLines) {
            const std::vector<std::string> f = (lineIdx == 0) ? card1 : cardFields(line, fw);
            size_t from = (lineIdx == span.nodeFirst) ? (size_t)span.nodeFieldSkip : 0u;
            for (size_t q = from; q < f.size(); ++q) {
                int v = fieldInt(f, q);
                if (v > 0) pk.nodes.push_back(v);
            }
        }
        ++lineIdx;
        if (--remaining <= 0) remaining = 0;
    }
    if (!top) return;
    sortUnique(pk.nodes);
    sortUnique(pk.solids);
    sortUnique(pk.shells);
    sortUnique(pk.tshells);
    pk.allElems.reserve(pk.solids.size() + pk.shells.size() + pk.tshells.size());
    pk.allElems.insert(pk.allElems.end(), pk.solids.begin(), pk.solids.end());
    pk.allElems.insert(pk.allElems.end(), pk.shells.begin(), pk.shells.end());
    pk.allElems.insert(pk.allElems.end(), pk.tshells.begin(), pk.tshells.end());
    const size_t before = pk.allElems.size();
    sortUnique(pk.allElems);
    pk.elemIdCollision = (pk.allElems.size() != before);
}

// ─────────────────────────────────────────────────────────────────────────────
// 번호 다시 매기기 — 정렬 벡터의 **자리**가 새 번호다(별도 맵을 들지 않는다)
// ─────────────────────────────────────────────────────────────────────────────

struct Remap {
    bool on = false;
    const std::vector<int>* nodes = nullptr;
    const std::vector<int>* elems = nullptr;
    int node(int old) const {
        if (!on || !nodes) return old;
        auto it = std::lower_bound(nodes->begin(), nodes->end(), old);
        if (it == nodes->end() || *it != old) return old;
        return (int)(it - nodes->begin()) + 1;
    }
    int elem(int old) const {
        if (!on || !elems) return old;
        auto it = std::lower_bound(elems->begin(), elems->end(), old);
        if (it == elems->end() || *it != old) return old;
        return (int)(it - elems->begin()) + 1;
    }
};

// 고정폭 칸 하나를 **제자리에서** 갈아 끼운다. 다른 칸의 글자는 손대지 않는다 —
// 그래서 좌표 실수를 다시 포맷하지 않고(왕복 오차 0) 주석·꼬리 공백도 그대로 간다.
// 새 값이 칸보다 길면 false 를 돌려준다(번호를 1부터 다시 매기면 일어날 수 없다).
bool putAt(std::string& line, size_t col, size_t width, int value) {
    if (width == 0 || width > 30) return false;
    char buf[32];
    int n = std::snprintf(buf, sizeof(buf), "%*d", (int)width, value);
    if (n != (int)width) return false;
    if (line.size() < col + width) line.resize(col + width, ' ');
    line.replace(col, width, buf, width);
    return true;
}

bool putField(std::string& line, int fw, size_t idx, int value) {
    if (fw <= 0) return false;
    return putAt(line, idx * (size_t)fw, (size_t)fw, value);
}

// ─────────────────────────────────────────────────────────────────────────────
// 패스 2 — 쓰기
// ─────────────────────────────────────────────────────────────────────────────

struct Needed {
    std::vector<int> secids, mids, eosids, hgids, tmids;
};

struct WriteStats {
    long long nodeLines = 0, elemCards = 0, partsEmitted = 0, partVariantBlocks = 0;
    std::map<std::string, long long> dropped;       // 버린 키워드 → 버린 줄 수
    // ★버린 것 중 **조용하면 치명적인** 것 — 초기상태·이력이다. `dropped_keywords` 안에
    //   섞어 두면 수십 개 중 한 줄이 되어 아무도 안 본다. 따로 세어 **크게** 말한다.
    std::map<std::string, long long> droppedState;
    std::map<std::string, long long> setsTrimmed;   // 키워드 → 자른 블록 수
    std::vector<int> setsDropped;                   // 못 자르는 변형의 SID
    std::map<std::string, long long> carriedWhole;  // 통째로 실은 ID 블록(과포함)
    long long includesInlined = 0;                  // 펼친 `*INCLUDE` 파일 수
    long long auxCards = 0;                         // 보·질량·이산 족에서 실은 카드
};

enum class Act { VERBATIM, NODE, SCALAR_NODE, ELEM, ELEM_AUX, PART, PART_VARIANT, IDBLOCK, SETS, DROP };

// 버리면 **조용하면 치명적인** 키워드 — 초기상태·이력. 자르려면 카드 수를 알아야 하고
// `*INITIAL_STRESS_SOLID` 는 그것이 **데이터로** 정해진다(Vol_I 190149-: NINT·NHISV·LARGE·
// NTHINT·NTHHSV 가 한 요소당 줄 수를 정하고 "LARGE=1 이면 수십 장" 이다). 틀리면 응력이
// 요소끼리 **섞인다** — 조용한 오답이 손실보다 나쁘다. 그래서 자르지 않고 버렸다고 말한다.
bool isStateKeyword(const std::string& kw) {
    return starts(kw, "*INITIAL_") || starts(kw, "*STRESS_") ||
           starts(kw, "*INTERFACE_SPRINGBACK");
}

Act classify(const std::string& kw, const Opts& o, bool elemSupported, bool auxSupported) {
    if (kw == "*KEYWORD" || kw == "*TITLE" || kw == "*END" || starts(kw, "*PARAMETER") ||
        starts(kw, "*COMMENT") || starts(kw, "*CONTROL"))
        return Act::VERBATIM;
    // `*DATABASE_HISTORY_*` 는 절점·요소 ID 를 담는다 — 통째로 실으면 산출 덱에 없는 것을
    // 가리킨다. 그 밖의 `*DATABASE_` 는 순수 설정이라 그대로 싣는다.
    if (starts(kw, "*DATABASE")) return has(kw, "_HISTORY") ? Act::DROP : Act::VERBATIM;
    if (kw == "*NODE") return o.incNodes ? Act::NODE : Act::DROP;
    // 스칼라 절점 — 보 `_WARPAGE` 의 SN1 · SN2 가 가리킨다. 고른 요소가 쓰는 줄만 싣는다(예전엔 통째로 버려 뽑은 보가 없는 스칼라
    // 절점을 가리켰다 — 셋째 묶음)
    if (KooRemapper::isScalarNodeKeyword(kw)) return o.incNodes ? Act::SCALAR_NODE : Act::DROP;
    if (starts(kw, "*ELEMENT"))
        return elemSupported ? Act::ELEM : (auxSupported ? Act::ELEM_AUX : Act::DROP);
    if (kw == "*PART" || kw == "*PART_TITLE") return Act::PART;
    if (starts(kw, "*PART")) return Act::PART_VARIANT;
    if (starts(kw, "*SECTION")) return o.incSections ? Act::IDBLOCK : Act::DROP;
    if (starts(kw, "*MAT") || starts(kw, "*EOS") || starts(kw, "*HOURGLASS"))
        return o.incMaterials ? Act::IDBLOCK : Act::DROP;
    // 곡선·표는 순수 수치다(절점·요소를 가리키지 않는다) — 통째로 싣는다. 그래야 재질이 돈다.
    if (starts(kw, "*DEFINE_CURVE") || starts(kw, "*DEFINE_TABLE"))
        return o.incMaterials ? Act::VERBATIM : Act::DROP;
    if (starts(kw, "*SET")) return o.incSets ? Act::SETS : Act::DROP;
    return Act::DROP;
}

// 그 `*SET_*` 가 무엇의 집합인가 — 자를 대상이 다르다.
enum class SetOf { NODE, PART, SOLID, SHELL, TSHELL, SEGMENT, UNKNOWN };

SetOf setSubject(const std::string& kw) {
    if (starts(kw, "*SET_NODE")) return SetOf::NODE;
    if (starts(kw, "*SET_PART")) return SetOf::PART;
    if (starts(kw, "*SET_SOLID")) return SetOf::SOLID;
    if (starts(kw, "*SET_SHELL")) return SetOf::SHELL;
    if (starts(kw, "*SET_TSHELL")) return SetOf::TSHELL;
    if (starts(kw, "*SET_SEGMENT")) return SetOf::SEGMENT;
    return SetOf::UNKNOWN;
}

// 쓰기 — 상태가 많고 `*INCLUDE` 를 **인라인**해야 하므로 구조체로 둔다.
//
// ★왜 인라인하나: 2.32GB 급 덱은 거의 늘 `*INCLUDE` 로 쪼개져 있고, 고른 파트의 요소가
// 인클루드 안에 있으면 그것을 안 읽는 순간 **요소가 하나도 없는 덱**이 조용히 나온다.
// 그래서 읽어서 제자리에 펼친다 — 산출 덱은 **홀로 서는** 한 파일이 된다(하류 체인이 원하는 꼴).
// 못 읽는 인클루드가 하나라도 있으면 **거절한다**(rc=1) — 파트가 조용히 빠지는 쪽이 더 나쁘다.
struct Writer {
    const Opts& o;
    const IncludeMap& im;
    const DeckIndex& idx;
    const std::vector<int>& sel;
    const std::map<int, int>& pidNodes;
    const Picked& pk;
    const Needed& nd;
    const Remap& rm;
    ConsoleOutput& console;
    WriteStats& st;
    std::ostream* out = nullptr;
    std::set<std::string> visited;
    std::vector<std::string> missingIncludes;
    bool failed = false;
    // 번호를 다시 매길 줄이 콤마 자유형식이면 제자리에 쓸 열이 없다 — 「파일:줄 키워드」 를 적고 쓰지 않는다(패스 2 뒤 거절 · 산출을
    // 지운다). 예전엔 칸 차례 × 폭 자리에 덮어써 「       1102,103,       1 …」 같은 깨진 줄을 냈고 되읽기도 통과했다(2026-11-07 검토 #7)
    std::vector<std::string> commaLines;
    long long commaCount = 0;
    const std::string* curPath = nullptr;
    size_t curLine = 0;

    bool commaRefuse(const std::string& line) {
        if (!rm.on || line.find(',') == std::string::npos) return false;
        if (commaLines.size() < 50) commaLines.push_back((curPath ? *curPath : std::string()) + ":" + std::to_string(curLine) + " " + kw);
        ++commaCount;
        return true;
    }

    // 현재 블록 상태
    std::string kw, kwLine;
    int fw = 8;
    Act act = Act::VERBATIM;
    KooRemapper::ElementKeywordInfo info;
    KooRemapper::ElementCardSpan span;
    KooRemapper::AuxElementCard aux;
    int remaining = 0, lineIdx = 0;
    bool picked = false;
    std::vector<std::string> card1;
    KooRemapper::AuxCardReadings auxRd;   // 보 족 Card 1 의 읽기들(설명서 칸의 열 자리에 번호를 쓴다)
    std::vector<std::string> auxBuf;      // 보 족 카드 한 장(줄 수가 2 이상일 수 있다)
    std::vector<std::string> buf;
    std::vector<size_t> cardIdx;
    // 하나도 안 실은 `*NODE`·`*ELEMENT_*` 블록은 키워드 줄도 내지 않는다 — 빈 블록은 소음이고,
    // 그것을 보고 "뽑혔다" 고 읽는 사람이 생긴다.
    std::string pendingKw;
    // 세트
    enum class SetMode { DROP, REPACK, STREAM };
    SetOf subj = SetOf::UNKNOWN;
    SetMode smode = SetMode::DROP;
    int setSid = 0, setDataIdx = 0, setTitleN = 0, sfw = 10;
    std::vector<int> survivors;

    const std::vector<int>* subjectList(SetOf s) const {
        switch (s) {
            case SetOf::NODE:   return &pk.nodes;
            case SetOf::PART:   return &sel;
            case SetOf::SOLID:  return &pk.solids;
            case SetOf::SHELL:  return &pk.shells;
            case SetOf::TSHELL: return &pk.tshells;
            default:            return nullptr;
        }
    }
    int remapSubject(SetOf s, int v) const {
        if (s == SetOf::NODE) return rm.node(v);
        if (s == SetOf::SOLID || s == SetOf::SHELL || s == SetOf::TSHELL) return rm.elem(v);
        return v;                                     // PID 는 다시 매기지 않는다
    }

    void emitLine(const std::string& l) {
        if (!pendingKw.empty()) { *out << pendingKw << "\n"; pendingKw.clear(); }
        *out << l << "\n";
    }

    void flushBlock() {
        if (act == Act::PART) {
            const size_t firstCard = cardIdx.empty() ? buf.size() : cardIdx.front();
            std::vector<std::string> emit;
            for (size_t k = 0; k + 1 < cardIdx.size(); k += 2) {
                int pid = fieldInt(cardFields(buf[cardIdx[k + 1]], 10), 0);
                if (pid <= 0 || !inSorted(sel, pid)) continue;
                emit.push_back(buf[cardIdx[k]]);
                emit.push_back(buf[cardIdx[k + 1]]);
            }
            if (!emit.empty()) {
                *out << kwLine << "\n";
                for (size_t i = 0; i < firstCard; ++i) *out << buf[i] << "\n";  // 머리 주석
                for (const auto& l : emit) *out << l << "\n";
                st.partsEmitted += (long long)emit.size() / 2;
            } else if (!buf.empty()) {
                st.dropped[kw] += (long long)buf.size();
            }
        } else if (act == Act::PART_VARIANT) {
            // 변형은 카드 묶음을 믿고 쪼갤 수 없다. 고른 PID 가 어느 카드의 칸 0 으로 나오면
            // 블록을 **통째로** 싣는다 — 안 고른 파트가 같이 와도 LS-DYNA 는 돌지만(요소 없는
            // 파트는 경고다), 조용히 빠뜨리는 쪽이 훨씬 나쁘다. 수로 적는다.
            bool hit = false;
            for (size_t i : cardIdx) {
                int pid = fieldInt(cardFields(buf[i], 10), 0);
                if (pid > 0 && inSorted(sel, pid)) { hit = true; break; }
            }
            if (hit) {
                *out << kwLine << "\n";
                for (const auto& l : buf) *out << l << "\n";
                ++st.partVariantBlocks;
            } else {
                st.dropped[kw] += (long long)buf.size();
            }
        } else if (act == Act::IDBLOCK) {
            const std::vector<int>* want = starts(kw, "*SECTION") ? &nd.secids
                                         : starts(kw, "*MAT")     ? &nd.mids
                                         : starts(kw, "*EOS")     ? &nd.eosids
                                                                  : &nd.hgids;
            bool hit = false;
            for (size_t i : cardIdx) {
                int id = fieldInt(cardFields(buf[i], 10), 0);
                if (id <= 0) continue;
                if (inSorted(*want, id)) { hit = true; break; }
                if (starts(kw, "*MAT") && inSorted(nd.tmids, id)) { hit = true; break; }
            }
            if (hit) {
                *out << kwLine << "\n";
                for (const auto& l : buf) *out << l << "\n";
                // 한 블록에 정의가 여럿이면 안 고른 것도 같이 온다 — 무해하지만 적는다.
                if (cardIdx.size() > 1) ++st.carriedWhole[kw];
            } else {
                st.dropped[kw] += (long long)buf.size();
            }
        } else if (act == Act::SETS) {
            if (smode == SetMode::DROP) {
                if (setSid > 0) st.setsDropped.push_back(setSid);
                st.dropped[kw] += (long long)buf.size();
            } else if (smode == SetMode::REPACK) {
                for (const auto& l : buf) *out << l << "\n";        // 키워드·제목·SID 줄
                for (size_t i = 0; i < survivors.size(); ++i) {
                    char b[32];
                    std::snprintf(b, sizeof(b), "%*d", sfw, survivors[i]);
                    *out << b;
                    if ((i + 1) % 8 == 0 || i + 1 == survivors.size()) *out << "\n";
                }
                if (survivors.empty()) *out << "\n";                // 빈 세트도 문법은 맞다
                ++st.setsTrimmed[kw];
            } else {
                ++st.setsTrimmed[kw];                               // STREAM 은 이미 흘렸다
            }
        }
        if (!pendingKw.empty()) {        // 한 줄도 안 실렸다 — 키워드 줄도 내지 않는다
            st.dropped[kw] += 1;
            pendingKw.clear();
        }
        buf.clear();
        cardIdx.clear();
        survivors.clear();
    }

    void onKeyword(const std::string& line) {
        flushBlock();
        remaining = 0;
        auxBuf.clear();
        kwLine = line;
        kw = kwBare(keywordToken(line));
        fw = KooRemapper::keywordFieldWidth(line, idx.fieldWidth);
        bool supported = false, auxOk = false;
        if (starts(kw, "*ELEMENT")) {
            info = KooRemapper::parseElementKeyword(line);
            supported = (info.family != KooRemapper::ElemFamily::NONE && info.supported);
            if (!supported) {
                aux = KooRemapper::auxElementCard(line);
                auxOk = aux.supported;
            }
        }
        act = classify(kw, o, supported, auxOk);
        if (act == Act::SETS) {
            subj = setSubject(kw);
            const auto sk = KooRemapper::deckscan::classifySetNode(kw);   // 변형 규칙은 같다
            setTitleN = titleLines(kw);
            setDataIdx = 0;
            setSid = 0;
            sfw = (fw >= 20) ? 20 : 10;
            if (subj == SetOf::UNKNOWN || sk == KooRemapper::deckscan::SetKind::OPAQUE)
                smode = SetMode::DROP;          // 멤버를 ID 로 못 읽거나 무엇의 집합인지 모른다
            else if (subj == SetOf::SEGMENT || sk == KooRemapper::deckscan::SetKind::COLUMN)
                smode = SetMode::STREAM;        // 줄 단위로 걸러 흘린다(다시 포장할 것이 없다)
            else
                smode = SetMode::REPACK;
            if (smode != SetMode::STREAM) buf.push_back(kwLine);
            else *out << kwLine << "\n";
            return;
        }
        if (act == Act::VERBATIM) *out << line << "\n";
        else if (act == Act::NODE || act == Act::SCALAR_NODE || act == Act::ELEM || act == Act::ELEM_AUX)
            pendingKw = line;                                 // 첫 줄이 실릴 때 낸다
        else if (act == Act::DROP) {
            st.dropped[kw] += 1;
            if (isStateKeyword(kw)) st.droppedState[kw] += 1;
        }
    }

    void onData(const std::string& line, size_t g, int depth) {
        switch (act) {
            case Act::VERBATIM: *out << line << "\n"; break;
            case Act::DROP: {
                // `*INCLUDE` 는 버리지 않고 **펼친다** — 그 안에 고른 파트의 요소가 있다.
                if (kw == "*INCLUDE" && isDataLine(line)) {
                    // 정본 닫힘이 정한 대로 — 따라가거나(Followed) · 이미 실었거나(Cycle) · 못 찾았거나 깊이를 넘었다(미리 거절했다)
                    const auto* r = im.at(curPath ? *curPath : std::string(), curLine);
                    using W = KooRemapper::include_closure::NameRef::What;
                    if (r && r->what == W::Followed) processFile(r->path, depth + 1);
                    else if (r && (r->what == W::Unresolved || r->what == W::DepthCut)) missingIncludes.push_back(r->name);
                    break;
                }
                st.dropped[kw] += 1;
                if (isStateKeyword(kw)) st.droppedState[kw] += 1;
                break;
            }
            case Act::NODE: {
                if (!isDataLine(line)) break;             // `*NODE` 안의 주석은 싣지 않는다
                int nid = 0;
                double xyz[3];
                if (!readNodeLine(line, fw, nid, xyz)) break;
                if (!inSorted(pk.nodes, nid)) break;
                std::string o2 = line;
                if (commaRefuse(line)) break;
                if (rm.on && !putField(o2, fw, 0, rm.node(nid))) {
                    console.error("renumber: 새 절점 번호가 칸 폭 " + std::to_string(fw) +
                                  " 를 넘는다 (NID " + std::to_string(nid) + ")");
                    failed = true;
                    break;
                }
                emitLine(o2);
                ++st.nodeLines;
                break;
            }
            case Act::SCALAR_NODE: {
                // 스칼라 절점(`*NODE_SCALAR` · `_VALUE` — 칸 0 이 NID) — 고른 요소가 쓰는 줄만 · 번호를 매기면 NID 를 바꾼다
                if (!isDataLine(line)) break;
                const int nid = fieldInt(cardFields(line, fw), 0);
                if (nid <= 0 || !inSorted(pk.nodes, nid)) break;
                std::string o2 = line;
                if (commaRefuse(line)) break;
                if (rm.on && !putField(o2, fw, 0, rm.node(nid))) {
                    console.error("renumber: 새 절점 번호가 칸 폭 " + std::to_string(fw) + " 를 넘는다 (스칼라 NID " +
                                  std::to_string(nid) + ")");
                    failed = true;
                    break;
                }
                emitLine(o2);
                ++st.nodeLines;
                break;
            }
            case Act::ELEM: {
                if (g != std::string::npos && line[g] == '$') break;
                if (g == std::string::npos && remaining == 0) break;
                if (remaining == 0) {
                    card1 = cardFields(line, fw);
                    int pid = fieldInt(card1, 1);
                    int pidN = 0;
                    auto pit = pidNodes.find(pid);
                    if (pit != pidNodes.end()) pidN = pit->second;
                    span = KooRemapper::elementCardSpan(info, card1, pidN);
                    lineIdx = 0;
                    remaining = span.lines;
                    picked = (pid > 0 && inSorted(sel, pid));
                    if (picked) ++st.elemCards;
                }
                if (picked) {
                    std::string o2 = line;
                    const bool renumLine = lineIdx == 0 || (lineIdx >= span.nodeFirst && lineIdx < span.nodeFirst + span.nodeLines);
                    if (renumLine && commaRefuse(line)) {
                        // 적었다 — 번호를 바꾸지 않고 둔다(패스 2 뒤 거절 · 산출을 지운다)
                    } else if (rm.on) {
                        if (lineIdx == 0) {
                            int eid = fieldInt(card1, 0);
                            if (eid > 0 && !putField(o2, fw, 0, rm.elem(eid))) {
                                console.error("renumber: 새 요소 번호가 칸 폭을 넘는다");
                                failed = true;
                            }
                        }
                        if (lineIdx >= span.nodeFirst &&
                            lineIdx < span.nodeFirst + span.nodeLines) {
                            const std::vector<std::string> f =
                                (lineIdx == 0) ? card1 : cardFields(line, fw);
                            size_t from =
                                (lineIdx == span.nodeFirst) ? (size_t)span.nodeFieldSkip : 0u;
                            for (size_t q = from; q < f.size(); ++q) {
                                int v = fieldInt(f, q);
                                if (v > 0 && !putField(o2, fw, q, rm.node(v))) {
                                    console.error("renumber: 새 절점 번호가 칸 폭을 넘는다");
                                    failed = true;
                                }
                            }
                        }
                    }
                    emitLine(o2);
                }
                ++lineIdx;
                if (--remaining <= 0) remaining = 0;
                break;
            }
            case Act::ELEM_AUX: {
                // 보·질량·이산 족. 칸 자리는 공용 판정기가 알고, **PID 칸도 족마다 다르다**.
                if (g != std::string::npos && line[g] == '$') break;
                if (g == std::string::npos && remaining == 0) break;
                if (remaining == 0) {
                    auxRd = KooRemapper::auxCardReadings(aux, line, fw);
                    card1 = KooRemapper::auxPrimaryFields(auxRd);
                    lineIdx = 0;
                    remaining = aux.lines;
                    if (aux.hasPart && aux.partIsSet) {
                        // 패스 1 과 같은 판정 — 세트가 다 고른 파트일 때만 싣는다(일부 · 못 푼 세트는 이미 거절했다)
                        std::string why;
                        picked = massSetVerdict(fieldInt(card1, 0), idx, sel, why) == 1;
                    } else if (aux.hasPart) {
                        // 패스 1 과 같은 판정 — PID 후보 가운데 고른 것이 있으면 싣는다(갈리는 줄은 이미 거절했다)
                        bool hit = false;
                        for (int p : auxPidCandidates(aux, auxRd, idx)) hit = hit || inSorted(sel, p);
                        picked = hit;
                    } else {
                        // PID 칸이 없다(`*ELEMENT_PLOTEL`) — 표시용이고 파트에 속하지 않는다.
                        // **두 절점이 다 남았을 때만** 싣는다(한쪽만 남은 선은 선이 아니다).
                        picked = (aux.nodeCount > 0);
                        for (int q = 0; q < aux.nodeCount; ++q) {
                            const int v = fieldInt(card1, (size_t)(aux.nodeSkip + q));
                            if (v <= 0 || !inSorted(pk.nodes, v)) { picked = false; break; }
                        }
                    }
                    if (picked && aux.hasEid) ++st.auxCards;
                }
                if (picked) {
                    std::string o2 = line;
                    // ⚠ 번호를 다시 매길 때 **절점 칸만** 고친다. 보의 RT1·RR1·LOCAL 이나
                    //   안전벨트의 SBRID·SLEN 을 같이 고치면 카드가 깨진다. 요소 ID 는
                    //   건드리지 않는다 — 번호 표는 격자 요소만 담는다(족별로 번호가 따로다).
                    // ★설명서 칸(LS-DYNA 가 읽는 칸 — `auxCardReadings` 의 manual)의 열 자리에 쓴다. 칸 차례 × 폭으로 잡으면 안전띠
                    //   N3 · N4(SLEN 이 E16 이라 57-72열)를 SLEN 위에 썼다(2026-11-07). 제자리에 못 쓰는 줄 · 두 가지로 읽혀 갈리는 줄은
                    //   패스 1 뒤에 줄마다 적고 이미 거절했다 — 여기 걸리면 이 op 의 결함이다(줄마다 한 번 말한다).
                    if (rm.on && lineIdx == 0) {
                        bool told = false;
                        auto put = [&](int from, int cnt) {
                            for (int q = 0; from >= 0 && q < cnt; ++q) {
                                const size_t k = (size_t)(from + q);
                                const int v = fieldInt(auxRd.manual.f, k);
                                if (v <= 0) continue;
                                if (k < auxRd.manual.col.size() && !auxRd.comma &&
                                    putAt(o2, auxRd.manual.col[k], auxRd.manual.width[k], rm.node(v)))
                                    continue;
                                if (!told) console.error("renumber: " + kw + " 줄 「" + line + "」 의 절점 번호를 제자리에 못 바꾼다");
                                told = true;
                                failed = true;
                            }
                        };
                        put(aux.nodeSkip, aux.nodeCount);
                        put(aux.nodeSkip2, aux.nodeCount2);
                    }
                    const std::vector<int>* optF = KooRemapper::auxOptNodeFields(aux, lineIdx);
                    if (rm.on && optF) {
                        // 옵션 카드의 절점(보 `_WARPAGE` 의 SN1 · SN2 · `_ELBOW` 의 MN — 8칸 표 칸 폭 10 · long 20). 제자리에 못 쓰는
                        // 줄(콤마 · 칸 안 빈칸 · 번호 칸의 주석)은 패스 1 이 이미 거절했다
                        const int w = KooRemapper::auxOptTableWidth(fw);
                        std::string body = line;
                        const size_t cmt = body.find('$');
                        if (cmt != std::string::npos) body.erase(cmt);
                        const auto f = cardFields(body, w);
                        for (int q : *optF) {
                            const int v = fieldInt(f, (size_t)q);
                            if (v > 0 && !putField(o2, w, (size_t)q, rm.node(v))) {
                                console.error("renumber: " + kw + " 줄 「" + line + "」 의 옵션 카드 절점 번호를 제자리에 못 바꾼다");
                                failed = true;
                            }
                        }
                    }
                    emitLine(o2);
                }
                ++lineIdx;
                if (--remaining <= 0) remaining = 0;
                break;
            }
            case Act::PART:
                if (g != std::string::npos && line[g] == '$') { buf.push_back(line); break; }
                cardIdx.push_back(buf.size());       // ⚠ 빈 줄도 카드다(제목을 비워 둘 수 있다)
                buf.push_back(line);
                break;
            case Act::PART_VARIANT:
            case Act::IDBLOCK:
                if (isDataLine(line)) cardIdx.push_back(buf.size());
                buf.push_back(line);
                break;
            case Act::SETS: {
                if (smode == SetMode::DROP) {
                    // 버려도 **SID 는 읽는다** — 무엇을 버렸는지 말하지 못하면 손실이 안 보인다
                    if (isDataLine(line)) {
                        if (setDataIdx == setTitleN) setSid = fieldInt(cardFields(line, sfw), 0);
                        ++setDataIdx;
                    }
                    buf.push_back(line);
                    break;
                }
                const bool stream = (smode == SetMode::STREAM);
                if (!isDataLine(line)) { stream ? (void)(*out << line << "\n") : buf.push_back(line); break; }
                if (setDataIdx < setTitleN) {
                    ++setDataIdx;
                    stream ? (void)(*out << line << "\n") : buf.push_back(line);
                    break;
                }
                if (setDataIdx == setTitleN) {
                    setSid = fieldInt(cardFields(line, sfw), 0);
                    ++setDataIdx;
                    stream ? (void)(*out << line << "\n") : buf.push_back(line);
                    break;
                }
                ++setDataIdx;
                auto f = cardFields(line, sfw);
                if (subj == SetOf::SEGMENT) {
                    // 네 칸이 절점이다 — **네 절점이 다 남은** 면만 싣는다(일부만 남은 면은
                    // 면이 아니다. 감김·접촉 방향이 거기서 거짓이 된다).
                    bool all = true;
                    for (size_t q = 0; q < 4; ++q) {
                        int v = fieldInt(f, q);
                        if (v <= 0 || !inSorted(pk.nodes, v)) { all = false; break; }
                    }
                    if (!all) break;
                    std::string o2 = line;
                    if (commaRefuse(line)) break;
                    if (rm.on)
                        for (size_t q = 0; q < 4; ++q) {
                            int v = fieldInt(f, q);
                            if (v > 0) putField(o2, sfw, q, rm.node(v));
                        }
                    *out << o2 << "\n";
                    break;
                }
                if (stream) {                    // `_COLUMN` — 한 줄에 멤버 하나(+ 속성 A1-A4)
                    // ★세트가 무엇의 집합인가로 거르고 그 대상으로 번호를 바꾼다 — 절점 · 파트(번호를 바꾸지 않는다) · 셸 · 솔리드 · 티쉘.
                    //   예전엔 늘 절점 번호로 걸러 `*SET_PART_COLUMN` · `*SET_SHELL_COLUMN` 을 비우거나 절점 번호로 바꿨다(재검토 N1)
                    const std::vector<int>* keep = subjectList(subj);
                    const int v = fieldInt(f, 0);
                    if (v <= 0 || !keep || !inSorted(*keep, v)) break;
                    std::string o2 = line;
                    if (rm.on && subj != SetOf::PART) {
                        if (commaRefuse(line)) break;
                        putField(o2, sfw, 0, remapSubject(subj, v));
                    }
                    *out << o2 << "\n";
                    break;
                }
                const std::vector<int>* keep = subjectList(subj);
                for (size_t q = 0; q < f.size(); ++q) {
                    int v = fieldInt(f, q);
                    if (v <= 0 || !keep || !inSorted(*keep, v)) continue;
                    survivors.push_back(remapSubject(subj, v));
                }
                break;
            }
        }
    }

    void processFile(const std::string& path, int depth) {
        if (failed) return;
        if (visited.count(path)) return;
        visited.insert(path);
        std::ifstream in(path);
        if (!in.is_open()) { missingIncludes.push_back(path); return; }
        if (depth > 0) ++st.includesInlined;
        // 블록 상태는 파일 경계에서 닫는다 — 인클루드 안의 키워드가 바깥 블록을 잇지 않는다.
        const std::string savedKw = kw, savedKwLine = kwLine;
        const Act savedAct = act;
        flushBlock();
        act = Act::VERBATIM;
        kw.clear();
        std::string line;
        size_t ln = 0;
        while (std::getline(in, line)) {
            while (!line.empty() && line.back() == '\r') line.pop_back();
            curPath = &path;       // 인클루드를 펼치고 돌아오면 다음 줄에서 다시 맞춘다
            curLine = ++ln;
            size_t g = line.find_first_not_of(" \t");
            if (isKeywordLine(line)) {   // 1열 규칙(리더와 같다) — 패스 1 훑기와 같은 키워드 줄
                // 인클루드 안의 `*KEYWORD`·`*END` 는 펼친 덱에 두 번 나오면 안 된다.
                std::string k2 = kwBare(keywordToken(line));
                if (depth > 0 && (k2 == "*KEYWORD" || k2 == "*END")) {
                    flushBlock();
                    act = Act::DROP;
                    kw = k2;
                    if (k2 == "*END") break;               // 그 파일은 여기서 끝난다(닫힘과 같다)
                    continue;
                }
                onKeyword(line);
                if (k2 == "*END") break;                   // 주 덱의 `*END` 는 싣고 멈춘다
                continue;
            }
            onData(line, g, depth);
            if (failed) return;
        }
        flushBlock();
        kw = savedKw;
        kwLine = savedKwLine;
        act = savedAct;
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// 패스 3 — 되읽기 검증: **남긴 쪽**이 멀쩡한가
// ─────────────────────────────────────────────────────────────────────────────
//
// 수를 세는 것은 전제 위에 있다. 산출 덱을 다시 읽어 '요소가 가리키는 절점·파트, 파트가
// 가리키는 섹션·재질이 전부 그 덱 안에 있다' 를 확인하는 것은 전제가 없다.
//
// ⚠ 정의 집합(섹션 ID·재질 ID)은 **과포함**으로 모은다 — `*MAT_*` 다중 카드의 둘째 줄 칸 0 이
// 정수로 보이면 ID 로 섞인다. 과포함은 '없다고 거짓 경보' 를 줄이는 쪽이고, ID 블록을 통째로
// 싣는 이 op 에서는 정말 빠진 ID 가 숨지 않는다(그 블록 자체가 안 실린다).

// 칸이 깨진 콤마 줄 — 콤마로 가른 칸 안에 공백이 낀다(번호를 콤마 줄의 칸 차례 × 폭 자리에 덮어쓴 꼴 「       1102,103,       1 …」).
// 되읽기가 절점 · 요소 · 세트 멤버로 읽는 줄만 본다(제목 · 곡선 줄은 보지 않는다)
bool malformedCommaLine(const std::string& line) {
    if (line.find(',') == std::string::npos) return false;
    std::string tok;
    auto bad = [](const std::string& t) { return trim(t).find_first_of(" \t") != std::string::npos; };
    for (char c : line) {
        if (c == ',') { if (bad(tok)) return true; tok.clear(); }
        else tok += c;
    }
    return bad(tok);
}

struct Verify {
    long long undefNodes = 0, undefParts = 0, undefSections = 0, undefMaterials = 0;
    int firstBadNode = 0, firstBadPart = 0;
    long long malformed = 0;          // 칸이 깨진 콤마 줄(`malformedCommaLine`)
    std::string firstMalformed;       // 그 첫 줄 「줄 번호: 내용」
};

// `altExisting` — 보 족 줄의 다른 읽기만 말하는 절점 가운데 입력 덱에 있던 것(정렬). 그것은 산출에도 있어야 한다(둘 다 남겼다).
Verify verifyOutput(const std::string& path, const std::vector<int>& altExisting) {
    Verify v;
    DeckIndex idx;
    { std::set<std::string> vis; indexDeck(path, idx, vis, nullptr); }
    const std::map<int, int> pidN = pidNodeCounts(idx);

    std::vector<int> nodes, secIds, matIds, elemPids, elemNodes, setMembers;
    std::ifstream in(path);
    if (!in.is_open()) return v;
    std::string line, kw;
    int fw = idx.fieldWidth;
    KooRemapper::ElementKeywordInfo info;
    KooRemapper::ElementCardSpan span;
    int remaining = 0, lineIdx = 0, dataIdx = 0;
    bool inElem = false, opaque = false;
    std::vector<std::string> card1;
    // ★보·질량·이산 족도 검증한다. 안 하면 실은 보가 **없는 절점**을 가리켜도 통과하고,
    //   "되읽어 증명한다" 가 거짓이 된다.
    KooRemapper::AuxElementCard vaux;
    int vAuxRemaining = 0, vAuxLineIdx = 0;
    size_t vln = 0;
    auto malformed = [&](const std::string& l) {
        if (!malformedCommaLine(l)) return;
        if (v.malformed++ == 0) v.firstMalformed = std::to_string(vln) + ": " + l;
    };
    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        ++vln;
        size_t g = line.find_first_not_of(" \t");
        if (isKeywordLine(line)) {   // 1열 규칙(리더와 같다) — 들여쓴 `*` 줄은 데이터다
            kw = kwBare(keywordToken(line));
            fw = KooRemapper::keywordFieldWidth(line, idx.fieldWidth);
            remaining = 0;
            dataIdx = 0;
            inElem = starts(kw, "*ELEMENT");
            if (inElem) {
                info = KooRemapper::parseElementKeyword(line);
                opaque = (info.family == KooRemapper::ElemFamily::NONE || !info.supported);
                vaux = opaque ? KooRemapper::auxElementCard(line) : KooRemapper::AuxElementCard();
                vAuxRemaining = 0;
            }
            continue;
        }
        if (inElem && opaque && vaux.supported) {
            if (g != std::string::npos && line[g] == '$') continue;
            if (g == std::string::npos && vAuxRemaining == 0) continue;
            if (vAuxRemaining == 0) { vAuxLineIdx = 0; vAuxRemaining = vaux.lines; }
            if (vAuxLineIdx == 0) {
                malformed(line);
                const auto rd = KooRemapper::auxCardReadings(vaux, line, fw);
                const auto& f = KooRemapper::auxPrimaryFields(rd);
                if (vaux.partField >= 0 && !vaux.partIsSet) {   // `_MASS_PART_SET` 의 칸 0 은 파트 세트 ID 다
                    const int pid = fieldInt(f, (size_t)vaux.partField);
                    if (pid > 0) elemPids.push_back(pid);
                }
                for (int x : KooRemapper::auxNodesSure(vaux, rd)) elemNodes.push_back(x);
                for (int x : KooRemapper::auxNodesUnsure(vaux, rd))
                    if (inSorted(altExisting, x)) elemNodes.push_back(x);
            } else {
                for (int x : KooRemapper::auxOptNodesOf(vaux, vAuxLineIdx, line, fw)) elemNodes.push_back(x);   // 보 `_WARPAGE` 의 SN · `_ELBOW` 의 MN
            }
            ++vAuxLineIdx;
            if (--vAuxRemaining <= 0) vAuxRemaining = 0;
            continue;
        }
        if (inElem) {
            if (g != std::string::npos && line[g] == '$') continue;
            if (g == std::string::npos && remaining == 0) continue;
            if (opaque) continue;
            if (remaining == 0) {
                card1 = cardFields(line, fw);
                int pid = fieldInt(card1, 1);
                if (pid > 0) elemPids.push_back(pid);
                int pn = 0;
                auto it = pidN.find(pid);
                if (it != pidN.end()) pn = it->second;
                span = KooRemapper::elementCardSpan(info, card1, pn);
                lineIdx = 0;
                remaining = span.lines;
            }
            if (lineIdx == 0 || (lineIdx >= span.nodeFirst && lineIdx < span.nodeFirst + span.nodeLines)) malformed(line);
            if (lineIdx >= span.nodeFirst && lineIdx < span.nodeFirst + span.nodeLines) {
                const std::vector<std::string> f = (lineIdx == 0) ? card1 : cardFields(line, fw);
                size_t from = (lineIdx == span.nodeFirst) ? (size_t)span.nodeFieldSkip : 0u;
                for (size_t q = from; q < f.size(); ++q) {
                    int x = fieldInt(f, q);
                    if (x > 0) elemNodes.push_back(x);
                }
            }
            ++lineIdx;
            if (--remaining <= 0) remaining = 0;
            continue;
        }
        if (!isDataLine(line)) continue;
        if (kw == "*NODE") {
            malformed(line);
            int nid = 0;
            double xyz[3];
            if (readNodeLine(line, fw, nid, xyz)) nodes.push_back(nid);
        } else if (KooRemapper::isScalarNodeKeyword(kw)) {   // 스칼라 절점 — 보 `_WARPAGE` 의 SN 이 가리킨다
            malformed(line);
            const int nid = fieldInt(cardFields(line, fw), 0);
            if (nid > 0) nodes.push_back(nid);
        } else if (starts(kw, "*SECTION")) {
            int id = fieldInt(cardFields(line, 10), 0);
            if (id > 0) secIds.push_back(id);
        } else if (starts(kw, "*MAT")) {
            int id = fieldInt(cardFields(line, 10), 0);
            if (id > 0) matIds.push_back(id);
        } else if (starts(kw, "*SET_NODE")) {
            const int sfw = (fw >= 20) ? 20 : 10;
            const int tn = titleLines(kw);
            if (dataIdx > tn) {
                malformed(line);
                auto f = cardFields(line, sfw);
                size_t lim = (KooRemapper::deckscan::classifySetNode(kw) ==
                              KooRemapper::deckscan::SetKind::COLUMN) ? 1u : f.size();
                for (size_t q = 0; q < lim && q < f.size(); ++q) {
                    int x = fieldInt(f, q);
                    if (x > 0) setMembers.push_back(x);
                }
            }
            ++dataIdx;
            continue;
        } else if (starts(kw, "*SET_SEGMENT")) {
            const int sfw = (fw >= 20) ? 20 : 10;
            const int tn = titleLines(kw);
            if (dataIdx > tn) {
                malformed(line);
                auto f = cardFields(line, sfw);
                for (size_t q = 0; q < 4 && q < f.size(); ++q) {
                    int x = fieldInt(f, q);
                    if (x > 0) setMembers.push_back(x);
                }
            }
            ++dataIdx;
            continue;
        }
        ++dataIdx;
    }
    sortUnique(nodes);
    sortUnique(secIds);
    sortUnique(matIds);
    for (int x : elemNodes)
        if (!inSorted(nodes, x)) { ++v.undefNodes; if (!v.firstBadNode) v.firstBadNode = x; }
    for (int x : setMembers)
        if (!inSorted(nodes, x)) ++v.undefNodes;
    sortUnique(elemPids);
    for (int p : elemPids)
        if (!idx.parts.count(p)) { ++v.undefParts; if (!v.firstBadPart) v.firstBadPart = p; }
    for (const auto& kv : idx.parts) {
        if (kv.second.secid > 0 && !inSorted(secIds, kv.second.secid)) ++v.undefSections;
        if (kv.second.mid > 0 && !inSorted(matIds, kv.second.mid)) ++v.undefMaterials;
    }
    return v;
}

// ─────────────────────────────────────────────────────────────────────────────
// 리포트
// ─────────────────────────────────────────────────────────────────────────────

// 보고에 싣는 글은 늘 바른 UTF-8 이다 — 덱 줄 · 경로(CP949 로 쓴 `*INCLUDE` 이름 등)의 깨진 바이트는 U+FFFD 로 바꾸고(공용
// `util::validUtf8` — 이월 적용 보고와 같은 규칙) 따옴표 · 역슬래시 · 제어 글자를 이스케이프한다. 예전엔 깨진 바이트를 그대로 실어
// 보고가 엄격한 UTF-8 리더에서 읽히지 않았다(3차 검토 TJ_euckr)
std::string jsonStr(const std::string& raw) {
    const std::string s = KooRemapper::util::validUtf8(raw);
    std::string o = "\"";
    for (char c : s) {
        if (c == '"' || c == '\\') { o += '\\'; o += c; }
        else if (c == '\n') o += "\\n";
        else if (c == '\t') o += "\\t";
        else if (c == '\r') o += "\\r";
        else if ((unsigned char)c < 0x20) {
            char b[8];
            std::snprintf(b, sizeof b, "\\u%04x", (unsigned)(unsigned char)c);
            o += b;
        }
        else o += c;
    }
    return o + "\"";
}

std::string intList(const std::vector<int>& v, size_t cap = 400) {
    std::ostringstream os;
    os << "[";
    for (size_t i = 0; i < v.size() && i < cap; ++i) os << (i ? ", " : "") << v[i];
    if (v.size() > cap) os << ", \"...(+" << (v.size() - cap) << ")\"";
    os << "]";
    return os.str();
}

std::string kwMap(const std::map<std::string, long long>& m) {
    std::ostringstream os;
    os << "{";
    bool first = true;
    for (const auto& kv : m) {
        os << (first ? "" : ", ") << jsonStr(kv.first) << ": " << kv.second;
        first = false;
    }
    os << "}";
    return os.str();
}

// ─────────────────────────────────────────────────────────────────────────────
// 쓸 파일 — 같은 폴더의 임시 파일에 쓰고 성공하면 제 이름으로 바꿔 넣는다(재검토 R3 · R5 — 공용 도우미 `staged_write::StagedFiles`)
// ─────────────────────────────────────────────────────────────────────────────
// 실패하면 이번 실행이 만든 임시 파일만 지운다 — 앞 실행이 같은 이름으로 남긴 파일 · 남의 파일 · 폴더는 건드리지 않는다
// (예전엔 rc≠0 이면 산출 · 번호 지도 · 보고 이름을 지워 설정 YAML · 따라가지 않는 인클루드 · 빈 폴더 · 앞 잡의 산출까지 지웠다).

bool isDirectory(const std::string& p) {
    std::error_code ec;
    return !p.empty() && std::filesystem::is_directory(p, ec);
}

bool fileExists(const std::string& p) {
    std::error_code ec;
    return !p.empty() && std::filesystem::exists(p, ec);
}

// 이 op 이 쓴 번호 지도인가 — 첫 키로 알아본다(`kind`, 2026-11-07 전 판은 `note` 다음 `nodes`). 아니면 지우지도 덮지도 않는다
bool isRenumberMap(const std::string& p) {
    std::ifstream in(p, std::ios::binary);
    if (!in.is_open()) return false;
    std::string head(512, '\0');
    in.read(&head[0], (std::streamsize)head.size());
    head.resize((size_t)in.gcount());
    head.erase(std::remove(head.begin(), head.end(), '\r'), head.end());
    static const std::string kNow = "{\n  \"kind\": \"extract-parts renumber map\",";
    static const std::string kOld = "{\n  \"note\": \"old -> new. 이것이 없으면 되돌릴 수 없다\",\n  \"nodes\": [";
    return head.rfind(kNow, 0) == 0 || head.rfind(kOld, 0) == 0;
}

// 글자 수 상한(바이트) — UTF-8 글자 가운데서 자르지 않는다
std::string utf8Cut(const std::string& s, size_t cap) {
    if (s.size() <= cap) return s;
    size_t n = cap;
    while (n > 0 && ((unsigned char)s[n] & 0xC0) == 0x80) --n;
    return s.substr(0, n) + "…";
}

}  // namespace

// ─────────────────────────────────────────────────────────────────────────────
// runExtractParts
// ─────────────────────────────────────────────────────────────────────────────

// 번호 지도 경로 — `out.k` → `out_renumber_map.json`(확장자 앞에 붙인다)
std::string renumberMapPath(const std::string& output) {
    const size_t dot = output.rfind('.');
    const size_t sep = output.find_last_of("/\\");
    if (dot != std::string::npos && (sep == std::string::npos || dot > sep)) return output.substr(0, dot) + "_renumber_map.json";
    return output + "_renumber_map.json";
}

int runExtractParts(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭 들여쓰기는 블록을 통째로 무너뜨려 조용히 아무 일도 안 한다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("extract-parts", tabLine));
            return 1;
        }
    }
    std::ifstream yf(yamlFile);
    if (!yf.is_open()) { console.error("Cannot open config: " + yamlFile); return 1; }

    Opts o;
    enum class List { NONE, PARTS, TITLES };
    List inList = List::NONE;
    bool inInclude = false;
    std::string raw;
    auto boolOf = [](const std::string& v) { return upper(v) != "FALSE" && v != "0" && upper(v) != "NO"; };
    while (std::getline(yf, raw)) {
        std::string l = KooRemapper::yamlStripComment(raw);
        if (trim(l).empty()) continue;
        const size_t indent = l.find_first_not_of(' ');
        std::string tr = trim(l);
        if (inList != List::NONE && tr.substr(0, 2) == "- ") {
            std::string item = stripQuotes(trim(tr.substr(2)));
            if (inList == List::PARTS) { int v = 0; if (toInt(item, v)) o.parts.push_back(v); }
            else o.partTitles.push_back(item);
            continue;
        }
        inList = List::NONE;
        size_t c = tr.find(':');
        if (c == std::string::npos) continue;
        std::string key = trim(tr.substr(0, c));
        std::string val = stripQuotes(trim(tr.substr(c + 1)));
        if (inInclude && indent > 0) {
            if (key == "nodes") o.incNodes = boolOf(val);
            else if (key == "materials") o.incMaterials = boolOf(val);
            else if (key == "sections") o.incSections = boolOf(val);
            else if (key == "sets") o.incSets = (upper(val) != "NONE" && upper(val) != "FALSE");
            else console.warning("[extract-parts] include 아래 모르는 키는 무시한다: " + key);
            continue;
        }
        inInclude = false;
        if (key == "model" || key == "input") o.model = val;
        else if (key == "output") o.output = val;
        else if (key == "report") o.reportPath = val;
        else if (key == "renumber") o.renumber = boolOf(val);
        else if (key == "verify") o.verify = boolOf(val);
        else if (key == "include") { if (val.empty()) inInclude = true; }
        else if (key == "parts" || key == "part_titles") {
            const bool isParts = (key == "parts");
            if (!val.empty() && val[0] == '[') {
                std::string inner = val.substr(1);
                size_t rb = inner.rfind(']');
                if (rb != std::string::npos) inner = inner.substr(0, rb);
                std::istringstream ss(inner);
                std::string tok;
                while (std::getline(ss, tok, ',')) {
                    tok = stripQuotes(trim(tok));
                    if (tok.empty()) continue;
                    if (isParts) { int v = 0; if (toInt(tok, v)) o.parts.push_back(v); }
                    else o.partTitles.push_back(tok);
                }
            } else if (val.empty()) {
                inList = isParts ? List::PARTS : List::TITLES;
            }
        }
        else console.warning("[extract-parts] 모르는 키는 무시한다: " + key);   // 조용히 넘어가지 않는다(오타면 기본값으로 돈다)
    }
    yf.close();

    const std::string cfgDir = dirOf(yamlFile);
    auto rp = [&](const std::string& p) {
        return p.empty() ? p : KooRemapper::yamlResolvePath(cfgDir, p);
    };
    o.model = rp(o.model);
    o.output = rp(o.output);
    o.reportPath = rp(o.reportPath);
    if (o.output.empty() && !o.model.empty()) {
        size_t dot = o.model.rfind('.');
        o.output = (dot == std::string::npos) ? o.model + "_extracted"
                   : o.model.substr(0, dot) + "_extracted" + o.model.substr(dot);
    }
    const std::string mapPathOf = o.output.empty() ? std::string() : renumberMapPath(o.output);
    const std::string mapWrite = o.renumber ? mapPathOf : std::string();   // 번호를 매길 때만 번호 지도를 쓴다

    // ── 실행의 결과 — 보고는 성공 · 실패 모두 쓴다(재검토 R3 · R4 · R5 뒤 사용자 결정 2026-11-07) ─────────────────────
    // ★이번 실행이 만들지 않은 파일은 지우지 않고 폴더는 지우지 않는다. 산출 · 번호 지도 · 보고는 같은 폴더의 임시 파일에 쓰고 다 되면
    //   바꿔 넣는다 — 실패하면 앞 실행의 파일이 그대로다. 보고에는 ok · output_written · 거절 목록 전부(`refusals`)를 적고 쓰지 않은
    //   파일은 대지 않는다. 거절 목록은 [ERROR] 요약 줄로도 낸다 — 플랫폼 잡 요약(error_summary)이 [ERROR] 줄만 모은다
    DeckIndex idx;
    std::vector<int> sel;
    Picked pk;
    Needed nd;
    Remap rm;
    WriteStats st;
    Verify vf;
    bool verified = false;
    struct Refusal { std::string kind, message; std::vector<std::string> lines; };
    std::vector<Refusal> refusals;
    // 덮으면 안 되는 파일 — 설정 YAML · 주 덱 · 닫힘의 인클루드(주 덱 폴더 · *INCLUDE_PATH 로 찾은 것) · 따라가지 않는 변형 인클루드의 파일
    std::vector<std::string> reads{yamlFile};
    if (!o.model.empty()) reads.push_back(o.model);
    KooRemapper::staged_write::StagedFiles staged;
    // 도우미가 남긴 말(읽기 전용 폴더의 제자리 쓰기 · 이름 바꾸기 대신 제자리로 쓴 것 — 원자적이 아니다)을 찍는다
    auto stagedNotes = [&]() {
        for (const auto& n : staged.takeNotes()) n.warn ? console.warning(n.text) : console.info(n.text);
    };
    auto reportWritable = [&]() {
        if (o.reportPath.empty() || isDirectory(o.reportPath)) return false;
        for (const auto& r : reads)
            if (KooRemapper::include_closure::sameFile(o.reportPath, r)) return false;
        return !KooRemapper::include_closure::sameFile(o.reportPath, o.output) &&
               !KooRemapper::include_closure::sameFile(o.reportPath, mapWrite);
    };
    // 보고 — 실제로 바꿔 넣은 것만 댄다(산출 · 번호 지도). ok 는 셋 다 바꿔 넣었을 때만 참이다
    auto reportJson = [&](bool ok, bool written, bool mapWritten) {
        std::ostringstream jf;
        jf << "{\n  \"op\": \"extract-parts\",\n";
        jf << "  \"model\": " << jsonStr(o.model) << ",\n";
        jf << "  \"output\": " << (written ? jsonStr(o.output) : std::string("null")) << ",\n";   // 쓰지 않은 파일은 대지 않는다
        jf << "  \"ok\": " << (ok ? "true" : "false") << ",\n";
        jf << "  \"output_written\": " << (written ? "true" : "false") << ",\n";
        jf << "  \"refusals\": [";
        for (size_t i = 0; i < refusals.size(); ++i) {
            jf << (i ? "," : "") << "\n    {\"kind\": " << jsonStr(refusals[i].kind)
               << ", \"message\": " << jsonStr(refusals[i].message) << ", \"lines\": [";
            for (size_t k = 0; k < refusals[i].lines.size(); ++k) jf << (k ? ", " : "") << jsonStr(refusals[i].lines[k]);
            jf << "]}";
        }
        jf << (refusals.empty() ? "" : "\n  ") << "],\n";
        jf << "  \"deck\": {\"field_width\": " << idx.fieldWidth
           << ", \"includes_inlined\": " << st.includesInlined
           << ", \"parts_in_deck\": " << idx.parts.size() << "},\n";
        jf << "  \"parts_selected\": " << intList(sel) << ",\n";
        jf << "  \"include\": {\"nodes\": " << (o.incNodes ? "true" : "false")
           << ", \"sets\": " << (o.incSets ? "\"referenced\"" : "\"none\"")
           << ", \"materials\": " << (o.incMaterials ? "true" : "false")
           << ", \"sections\": " << (o.incSections ? "true" : "false") << "},\n";
        jf << "  \"picked\": {\"element_cards\": " << pk.cards
           << ", \"aux_element_cards\": " << st.auxCards
           << ", \"nodes\": " << pk.nodes.size()
           << ", \"node_lines_written\": " << st.nodeLines
           << ", \"parts_emitted\": " << st.partsEmitted << "},\n";
        jf << "  \"needed\": {\"sections\": " << intList(nd.secids)
           << ", \"materials\": " << intList(nd.mids)
           << ", \"eos\": " << intList(nd.eosids)
           << ", \"hourglass\": " << intList(nd.hgids) << "},\n";
        jf << "  \"sets_trimmed\": " << kwMap(st.setsTrimmed) << ",\n";
        jf << "  \"sets_dropped_sids\": " << intList(st.setsDropped) << ",\n";
        jf << "  \"aux_keywords_read\": [";
        for (size_t i = 0; i < pk.auxKws.size(); ++i)
            jf << (i ? ", " : "") << jsonStr(pk.auxKws[i]);
        jf << "],\n";
        jf << "  \"carried_whole\": " << kwMap(st.carriedWhole) << ",\n";
        jf << "  \"part_variant_blocks_carried_whole\": " << st.partVariantBlocks << ",\n";
        jf << "  \"dropped_keywords\": " << kwMap(st.dropped) << ",\n";
        jf << "  \"dropped_initial_state\": " << kwMap(st.droppedState) << ",\n";
        if (!st.droppedState.empty())
            jf << "  \"dropped_initial_state_note\": "
               << jsonStr("뽑은 덱에는 초기응력·이력이 없다. 카드 수가 데이터로 정해지는 꼴이라"
                          "(NINT·NHISV·LARGE) 자르면 응력이 요소끼리 섞일 수 있어 자르지 않았다. "
                          "전체 모델의 dynain 을 update/prestress 로 다시 적용하라 — "
                          "ID 가 보존되므로 ID 로 맞는다")
               << ",\n";
        jf << "  \"renumber\": {\"on\": " << (rm.on ? "true" : "false") << ", \"map\": "
           << (mapWritten ? jsonStr(mapWrite) : std::string("null")) << "},\n";
        jf << "  \"verify\": "
           << (verified ? "{\"undefined_nodes\": " + std::to_string(vf.undefNodes) +
                          ", \"undefined_parts\": " + std::to_string(vf.undefParts) +
                          ", \"undefined_sections\": " + std::to_string(vf.undefSections) +
                          ", \"undefined_materials\": " + std::to_string(vf.undefMaterials) +
                          ", \"malformed_comma_lines\": " + std::to_string(vf.malformed) + "}"
                        : "null")
           << "\n}\n";
        return jf.str();
    };
    // 거절 — [ERROR] 머리 줄 · 목록(줄마다) · 목록을 담은 [ERROR] 요약 줄 하나 · 힌트. 그리고 실패 보고(쓸 수 있을 때 — 임시 파일로)
    auto fail = [&](const std::string& kind, const std::string& rawMessage, const std::vector<std::string>& rawLines = {},
                    const std::string& hint = std::string()) {
        // 말 · 목록의 임시 이름은 제 이름으로(콘솔 · 보고 어디에도 `.kr_tmp_` 가 새지 않게 — 3차 검토)
        const std::string message = staged.unstage(rawMessage);
        std::vector<std::string> lines;
        for (const auto& l : rawLines) lines.push_back(staged.unstage(l));
        console.error(message);
        const size_t cap = 50;
        for (size_t i = 0; i < lines.size() && i < cap; ++i) console.println("  " + lines[i]);
        if (lines.size() > cap) console.println("  … 외 " + std::to_string(lines.size() - cap) + " 줄(보고의 refusals 에 전부)");
        if (!lines.empty()) {
            std::string first;
            for (size_t i = 0; i < lines.size() && i < 3; ++i) first += (i ? " · " : "") + lines[i];
            console.error("  거절 목록 " + std::to_string(lines.size()) + " 줄 — " + utf8Cut(first, 600));
        }
        if (!hint.empty()) console.info(hint);
        refusals.push_back({kind, message, lines});
        staged.discardAll();
        if (reportWritable()) {
            std::string why;
            if (staged.writeText(o.reportPath, reportJson(false, false, false), why) && staged.commit(o.reportPath, why))
                console.info("report: " + o.reportPath);
            else
                console.error("Cannot write report: " + o.reportPath + " (" + why + ")");
            staged.discardAll();
            stagedNotes();
        }
        return 1;
    };

    if (o.model.empty()) return fail("config", "'model' is required in YAML config");
    { std::ifstream probe(o.model);
      if (!probe.is_open()) return fail("config", "Cannot open model: " + o.model); }

    // 인클루드 닫힘 — 정본 규칙(주 덱 폴더 · *INCLUDE_PATH · 깊이 16). 읽는 파일을 다 알아야 보고 · 산출을 그 위에 쓰지 않는다
    const IncludeMap im(o.model);
    for (const auto& f : im.closure().files) reads.push_back(f.path);
    for (const auto& r : im.closure().refs)
        if (!r.path.empty()) reads.push_back(r.path);
    for (const auto& n : im.closure().notFollowed)
        if (!n.path.empty()) reads.push_back(n.path);

    if (o.parts.empty() && o.partTitles.empty())
        return fail("config", "'parts' (PID list) 또는 'part_titles' (와일드카드) 가 하나는 필요하다 — "
                              "무엇을 뽑을지 고르지 않으면 할 일이 없다");

    // ★쓸 파일이 읽는 파일과 같으면 거절한다 — 바꿔 넣는 순간 입력(설정 · 주 덱 · 인클루드 · 변형 인클루드의 파일)이 사라진다. 쓸 자리가
    //   폴더면 거절한다(지우지 않는다). 번호를 매길 때 번호 지도 자리에 이 op 의 번호 지도가 아닌 파일이 있으면 덮지 않는다
    {
        const std::vector<std::string> writes{o.output, o.reportPath, mapWrite};
        std::string w, r;
        if (KooRemapper::include_closure::clobberPair(writes, reads, w, r)) {
            const bool both = std::find(writes.begin(), writes.end(), r) != writes.end() &&
                              std::find(reads.begin(), reads.end(), r) == reads.end();
            return fail("clobber", both ? "쓸 파일 「" + w + "」 과 「" + r + "」 이 같은 파일이다 — 하나가 다른 하나를 덮는다"
                                        : "쓸 파일 「" + w + "」 이 읽는 파일 「" + r + "」 과 같은 파일이다 — 입력(설정 · 주 덱 · 인클루드)에 "
                                          "쓰지 않는다",
                        {}, "output · report 를 입력과 다른 이름으로 주라");
        }
        for (const auto& p : writes)
            if (isDirectory(p))
                return fail("clobber", "쓸 자리 「" + p + "」 가 폴더다 — 폴더에 쓰지 않고 지우지도 않는다", {},
                            "output · report 에 파일 이름을 주라");
        if (!mapWrite.empty() && fileExists(mapWrite) && !isRenumberMap(mapWrite))
            return fail("clobber", "번호 지도 자리 「" + mapWrite + "」 에 이 op 의 번호 지도가 아닌 파일이 있다 — 덮지 않는다", {},
                        "그 파일을 옮기거나 output 이름을 바꿔라");
    }
    // 앞 실행이 끝나지 못하고(SIGKILL · 시간 초과) 남긴 이 산출 · 번호 지도 · 보고의 임시 파일 — 주인 프로세스가 없는 것만 지운다
    {
        std::vector<KooRemapper::staged_write::Note> notes;
        for (const std::string& p : {o.output, mapPathOf, o.reportPath}) KooRemapper::staged_write::sweepStale(p, &notes);
        for (const auto& n : notes) n.warn ? console.warning(n.text) : console.info(n.text);
    }

    console.info("extract-parts: " + o.model);

    // ── 패스 0 — `*PART` 표 ──────────────────────────────────────────────────
    std::set<std::string> inputs;   // 이 op 이 연 파일(주 덱 · 따라간 맨 *INCLUDE) — 닫힘의 파일과 같다
    indexDeck(o.model, idx, inputs, &im);
    // ★인클루드 닫힘을 다 못 읽으면 미리 거절한다 — 그 안의 고른 파트 요소 · 안전띠 장치를 못 본다(재검토 D1 · N2 · N3)
    //   · 못 찾았거나 열 수 없는 맨 *INCLUDE(주 덱 폴더 · *INCLUDE_PATH 폴더에서 찾는다)
    //   · 깊이 16 을 넘은 인클루드(예전엔 8 에서 말없이 멈춰 9단째의 고른 파트가 rc 0 으로 빠졌다)
    //   · 따라가지 않는 파일 인클루드(*INCLUDE_TRANSFORM · _AUTO_OFFSET · _BINARY · _NASTRAN · _STAMPED_* …) — 안을 모르니 고른 파트가
    //     거기 있는지 증명할 수 없다(예전엔 안전띠를 골랐을 때만 거절했다). *INCLUDE_PATH · _PATH_RELATIVE 는 탐색 경로라 세지 않는다
    {
        const auto& clo = im.closure();
        std::vector<std::string> bad;
        for (const auto& u : clo.unresolved)
            bad.push_back(u.file + ":" + std::to_string(u.line) + " *INCLUDE 「" + u.name + "」 — " + u.why);
        using W = KooRemapper::include_closure::NameRef::What;
        for (const auto& r : clo.refs)
            if (r.what == W::DepthCut)
                bad.push_back(r.file + ":" + std::to_string(r.firstLine) + " *INCLUDE 「" + r.name + "」 — 인클루드 깊이 상한(16)을 넘었다");
        for (const auto& n : clo.notFollowed)
            bad.push_back(n.file + ":" + std::to_string(n.line) + " " + n.keyword + (n.name.empty() ? "" : " 「" + n.name + "」") +
                          " — 이 op 이 따라가지 않는 파일 인클루드다(안을 모른다)");
        if (!bad.empty())
            return fail("include", "인클루드 닫힘을 다 읽지 못했다 — " + std::to_string(bad.size()) + " 곳. 그 안의 고른 파트 요소 · 장치가 "
                                   "조용히 빠질 수 있어 거절한다", bad,
                        "따라가는 것은 맨 *INCLUDE 다(주 덱 폴더 먼저 · 그다음 *INCLUDE_PATH 폴더 · 깊이 16) — 변형 인클루드는 펼친 덱으로 돌려라");
    }
    if (idx.parts.empty()) return fail("parts", "No *PART definitions found (or only *PART_* variants we cannot chunk)");
    const std::map<int, int> pidNodes = pidNodeCounts(idx);

    // 고를 PID 를 확정한다 — 제목 와일드카드는 여기서 PID 로 바뀐다.
    std::vector<int> missing;
    sel = o.parts;
    std::vector<std::string> titleHits;
    for (const auto& pat : o.partTitles) {
        bool any = false;
        for (const auto& kv : idx.parts)
            if (globMatch(upper(pat), upper(kv.second.title))) {
                sel.push_back(kv.first);
                titleHits.push_back(std::to_string(kv.first) + " " + kv.second.title);
                any = true;
            }
        if (!any) console.warning("part_titles '" + pat + "' 와 맞는 파트가 없다");
    }
    sortUnique(sel);
    for (int p : o.parts) if (!idx.parts.count(p)) missing.push_back(p);
    if (!missing.empty()) {
        std::string s;
        for (size_t i = 0; i < missing.size() && i < 20; ++i)
            s += (i ? ", " : "") + std::to_string(missing[i]);
        return fail("parts", "덱에 없는 PID: " + s + " — 오타면 조용히 빈 덱이 나온다");
    }
    std::vector<int> selDefined;
    for (int p : sel) if (idx.parts.count(p)) selDefined.push_back(p);
    sel = selDefined;
    if (sel.empty()) return fail("parts", "고를 파트가 없다");
    console.info("  parts: " + std::to_string(sel.size()) + " / " +
                 std::to_string(idx.parts.size()) + " (덱 전체)");
    for (const auto& h : titleHits) console.info("    title match: " + h);

    // ── 패스 1 — 요소·절점 ──────────────────────────────────────────────────
    { std::set<std::string> vis; scanElements(o.model, sel, idx, pidNodes, pk, vis, im); }
    if (idx.fieldWidth != 8)
        console.info("  deck field width: " + std::to_string(idx.fieldWidth));
    // ★칸으로 읽지 못한 보 족 줄(쓰는 칸 EID · PID · 절점에 빈칸 — 공백으로 가른 줄 등) — 그 칸은 값이 없어 이 op 이 그 줄의 PID · 절점을
    //   모른다(공백 토큰은 읽기가 아니다 · 2026-11-08). 조용히 넘기지 않고 줄마다 댄다 — 고른 파트의 요소인데 빠졌을 수 있다
    for (const auto& w : pk.unreadableAux)
        console.warning("[extract-parts] " + w + " — 보 족 줄의 쓰는 칸(EID · PID · 절점)에 빈칸이 끼어 칸으로 읽지 못했다 — 고른 파트에 "
                        "있을 수 있으면(PID 칸 · 그 줄의 정수로 본다) 거절하고, 아니면 싣지 않는다. 고정폭 칸이나 콤마로 고쳐 써라");
    // ★그 줄이 고른 파트에 있을 수 있으면 거절한다 — 그 줄의 PID · 절점을 칸으로 몰라 실으면 절점이, 버리면 요소가 조용히 빠진다
    //   (2026-11-08 여섯째 검토 S1 · 사용자 원칙 「지키는 쪽은 잃지 않는다 — 거절이 안전한 실패다」)
    if (!pk.unreadablePicked.empty())
        return fail("unreadable_aux", "칸으로 읽지 못한 보 족 줄 " + std::to_string(pk.unreadablePicked.size()) + " 장이 고른 파트에 있을 수 "
                                      "있다 — 그 줄의 PID · 절점을 칸으로 몰라 싣지도 버리지도 못해 거절한다", pk.unreadablePicked,
                    "그 줄을 고정폭 칸(정수 8 · 실수 16 — i10 은 정수 10, long 은 모두 20)이나 콤마로 고쳐 쓰라");
    // ⚠ 보·질량·이산 족도 센다. 격자 카드만 세면 **보만으로 된 파트**(볼트·용접점 묶음)가
    //   "요소가 없다" 로 거절된다 — 회귀 L-0 이 그 자리를 지킨다.
    if (pk.cards == 0 && pk.auxCards == 0)
        return fail("parts", "고른 파트에 요소가 없다 — PID 는 맞는데 그 파트의 요소를 못 읽었다는 뜻이다");
    // ★모르는 `*ELEMENT_*` 변형이 고른 파트의 요소를 담고 있으면 **거절한다.**
    //   조용히 빠뜨린 덱은 그럴듯하게 돌면서 틀린다.
    if (!pk.opaqueElemTouched.empty()) {
        std::vector<std::string> lines;
        for (const auto& kv : pk.opaqueElemTouched)
            lines.push_back(kv.first + " — 고른 파트의 요소 " + std::to_string(kv.second) + " 줄");
        return fail("opaque_elements", "이 op 이 카드의 줄 수를 모르는 *ELEMENT_* 변형이 고른 파트의 요소를 담고 있다 — 조용히 빠뜨리지 "
                                       "않기 위해 거절한다", lines,
                    "읽을 수 있는 것은 격자 3족(*ELEMENT_SOLID·SHELL·TSHELL)과 보 족 5종(*ELEMENT_BEAM·DISCRETE·MASS·SEATBELT·PLOTEL)이다");
    }
    // ★안전띠 장치 키워드는 PID 칸이 없어 고른 띠에 붙었는지 **증명할 수 없다** — 위 규칙(「모르는 변형이 고른 파트를 담으면
    //   거절」)을 보수적으로 댄다: 고른 파트에 `*ELEMENT_SEATBELT` 가 있으면 거절하고, 없으면 다른 모르는 카드처럼 버리고
    //   `dropped_keywords` 에 센다(2026-11-07). 장치를 빼고 띠만 실은 덱은 그럴듯하게 돌면서 리트랙터 · 프리텐셔너가 없다.
    //   가속도계(`_ACCELEROMETER`)와 데이터 줄 없는 장치 블록은 세지 않는다(scanElements — 사용자 결정 2026-11-07).
    if (pk.seatbeltCards > 0 && !pk.seatbeltDevices.empty())
        return fail("seatbelt_device", "고른 파트에 *ELEMENT_SEATBELT 카드 " + std::to_string(pk.seatbeltCards) + " 장이 있는데 덱에 안전띠 "
                                       "장치 키워드가 " + std::to_string(pk.seatbeltDevices.size()) + " 블록 있다 — 장치는 PID 칸이 없어 고른 "
                                       "띠에 붙었는지 증명할 수 없으므로 거절한다(빼면 띠가 그럴듯하게 돌면서 장치가 없다)",
                    pk.seatbeltDevices, "안전띠를 고르지 않으면 장치는 싣지 않고 dropped_keywords 에 센다");
    // ★보 장치(`*ELEMENT_BEAM_PULLEY` · `_SOURCE`)는 PID 칸이 없다 — 고른 보 요소(BID1 · BID2 · BSEID)를 가리키면 장치를 빼고 보만 실을
    //   수 없다 → 거절. 번호가 0 이면(PULLEY — LS-DYNA 가 이웃 보를 스스로 찾는다) 고른 파트에 보가 있을 때 거절. 그 밖은 버리고
    //   dropped_keywords 에 센다(2026-11-07 검토 #5 — 예전엔 보의 옵션으로 읽어 칸 1(BID1 · BSNID)을 PID 로 셌다)
    {
        sortUnique(pk.beamEids);
        std::vector<std::string> bad;
        for (const auto& bd : pk.beamDevices) {
            std::string hit;
            bool zero = true;
            for (int r : bd.refs) {
                if (r > 0) zero = false;
                if (r > 0 && inSorted(pk.beamEids, r)) hit += (hit.empty() ? "" : ", ") + std::to_string(r);
            }
            if (!hit.empty()) bad.push_back(bd.where + " — 고른 보 요소 " + hit + " 를 가리킨다");
            else if (zero && !pk.beamEids.empty()) bad.push_back(bd.where + " — 보 요소 번호가 0(이웃 보를 스스로 찾는다)이고 고른 파트에 보가 있다");
        }
        if (!bad.empty())
            return fail("beam_device", "보 장치(*ELEMENT_BEAM_PULLEY · _SOURCE) " + std::to_string(bad.size()) + " 줄이 고른 보에 붙었을 수 "
                                       "있다 — 장치는 PID 칸이 없어 따로 싣지 못하고, 빼면 보가 그럴듯하게 돌면서 도르래 · 공급원이 없다. "
                                       "거절한다", bad);
    }
    // ★질량 얹기 세트(`*ELEMENT_MASS_PART_SET`) — 세트를 일부만 고르거나 풀 수 없으면 실을지 버릴지 정할 수 없다. 세트를 싣지 않으면
    //   (`include.sets: none`) 실은 줄이 없는 세트를 가리킨다(2026-11-07 검토 #5)
    if (!pk.massSetRefused.empty() || (pk.massSetCards > 0 && !o.incSets)) {
        std::vector<std::string> lines = pk.massSetRefused;
        if (pk.massSetCards > 0 && !o.incSets)
            lines.push_back("include.sets: none — 실을 질량 얹기 " + std::to_string(pk.massSetCards) + " 줄이 가리키는 *SET_PART 를 싣지 않는다");
        return fail("mass_part_set", "*ELEMENT_MASS_PART_SET " + std::to_string(pk.massSetRefused.size() + (o.incSets ? 0 : pk.massSetCards)) +
                                     " 줄 — 파트 세트에 나눠 얹는 질량을 고른 파트에 맞게 실을 수 없어 거절한다", lines);
    }
    // ★넓은 칸 뒤 PID 가 읽기마다 갈리는데 그 하나를 골랐다 — 실을지 버릴지 정할 수 없다(질량의 MASS 를 정수 폭으로 쓴 줄 · 2026-11-07)
    if (!pk.ambiguousPid.empty())
        return fail("ambiguous_pid", "보 족 줄 " + std::to_string(pk.ambiguousPid.size()) + " 장이 설명서 칸과 정수 폭으로 읽혀 PID 가 갈리고 "
                                     "그 하나가 고른 파트다 — 실을지 버릴지 정할 수 없어 거절한다", pk.ambiguousPid,
                    "그 줄을 설명서 칸(정수 8 · 실수 16 — i10 은 정수 10, long 은 모두 20)으로 고쳐 쓰라");
    // 다른 읽기만 말하는 절점 — 덱(닫힘)에 정의된 것만 남긴다(둘 다 남긴다 · 지어낸 번호는 싣지 않는다). 드물게만 덱을 한 번 더 훑는다
    std::vector<int> altExisting;
    {
        std::vector<int> want = pk.altNodes;
        for (const auto& r : pk.renumberRisk) want.insert(want.end(), r.altVsManual.begin(), r.altVsManual.end());
        sortUnique(want);
        if (!want.empty()) {
            std::set<std::string> vis;
            definedNodesAmong(o.model, idx, want, altExisting, vis, im);
            sortUnique(altExisting);
        }
        sortUnique(pk.altNodes);
        std::vector<int> carry;
        std::set_intersection(pk.altNodes.begin(), pk.altNodes.end(), altExisting.begin(), altExisting.end(),
                              std::back_inserter(carry));
        if (!carry.empty()) {
            pk.nodes.insert(pk.nodes.end(), carry.begin(), carry.end());
            sortUnique(pk.nodes);
            console.info("  보 족 줄의 다른 읽기만 말하는 절점 " + std::to_string(carry.size()) +
                         " 개도 싣는다 — 넓은 칸 뒤 칸이 설명서 칸 · 정수 폭으로 갈린다(둘 다 남긴다)");
        }
    }
    console.info("  element cards: " + std::to_string(pk.cards) +
                 (pk.auxCards > 0 ? " (+보·질량·이산 " + std::to_string(pk.auxCards) + ")" : "") +
                 "  nodes: " + std::to_string(pk.nodes.size()));
    for (const auto& k : pk.auxKws)
        console.info("    " + k + " — 칸 자리를 알고 읽었다(추측이 아니다)");
    if (pk.massPartCards > 0)
        console.info("  *ELEMENT_MASS_PART(_SET) " + std::to_string(pk.massPartCards) + " 줄 — 고른 파트(세트)에 얹는 질량을 싣는다");

    for (int p : sel) {
        const PartDef& d = idx.parts.at(p);
        if (d.secid > 0) nd.secids.push_back(d.secid);
        if (d.mid > 0) nd.mids.push_back(d.mid);
        if (d.eosid > 0) nd.eosids.push_back(d.eosid);
        if (d.hgid > 0) nd.hgids.push_back(d.hgid);
        if (d.tmid > 0) nd.tmids.push_back(d.tmid);
    }
    sortUnique(nd.secids); sortUnique(nd.mids); sortUnique(nd.eosids);
    sortUnique(nd.hgids);  sortUnique(nd.tmids);

    // ── 번호 다시 매기기 판정 ────────────────────────────────────────────────
    if (o.renumber) {
        if (pk.elemIdCollision)
            return fail("renumber", "renumber: 종류가 다른 요소가 같은 EID 를 쓴다 — 전역으로 1부터 다시 매기면 어느 쪽인지 알 수 없게 "
                                    "된다. renumber: false 로 돌려라");
        // ★번호를 제자리에 바꿔 쓸 수 없는 보 족 줄 — 줄마다 한 번 적고 쓰기 전에 거절한다(2026-11-07 「번호 매기기는 거절」)
        //   · 칸 자리가 없다 — 콤마 자유형식 · 설명서 칸 안에 빈칸이 낀 줄(정수 폭으로 쓴 줄 — LS-DYNA 가 읽는 칸이 쓴 꼴과 다르다) ·
        //     번호를 쓸 칸에 겹친 `$` 주석
        //   · 모호하다 — 그 줄을 그렇게 썼을 수 있는 다른 읽기(규칙 (a)-(d)를 지킨 정수 폭 읽기)가 설명서 칸에 없는 절점을 말하고 그
        //     절점이 덱에 있다. 설명서대로 쓴 줄(빈 SLEN · 빈 SBRID · 소수점 · 지수 표기 · 왼쪽 맞춤 · 꼬리 주석 · 정수꼴 SLEN)은 다른
        //     읽기가 없다
        std::vector<std::string> bad;
        for (const auto& r : pk.renumberRisk) {
            if (!r.placeable) {
                bad.push_back(r.where + " — 칸 자리가 없다(콤마 자유형식 · 설명서 칸 안에 빈칸 · 번호 칸에 겹친 $ 주석)");
                continue;
            }
            std::string hit;
            for (int v : r.altVsManual)
                if (inSorted(altExisting, v)) hit += (hit.empty() ? "" : ", ") + std::to_string(v);
            if (!hit.empty())
                bad.push_back(r.where + " — 설명서 칸과 정수 폭으로 읽혀 갈린다(다른 읽기의 절점 " + hit + " 이 덱에 있다)");
        }
        if (!bad.empty())
            return fail("renumber", "renumber: 보 족 줄 " + std::to_string(bad.size()) + " 장은 절점 번호를 제자리에 바꿔 쓸 수 없다 — "
                                    "거절한다", bad, "renumber: false 면 그 줄은 그대로 싣고 두 읽기의 절점을 다 싣는다");
        rm.on = true;
        rm.nodes = &pk.nodes;
        rm.elems = &pk.allElems;
        console.info("  renumber: 절점 1.." + std::to_string(pk.nodes.size()) +
                     " · 요소 1.." + std::to_string(pk.allElems.size()));
    }

    // ── 패스 2 — 쓰기(임시 파일 — 다 되기 전엔 산출 자리를 건드리지 않는다) ─────────────────────────────
    //    링크면 따라간 파일 옆 · 읽기 전용 폴더의 쓸 수 있는 파일이면 시스템 임시 폴더에(바꿔 넣을 때 제자리로) · 장치 · FIFO(`/dev/null`)면
    //    그 자리에 바로 쓴다(공용 staged_write — 배포 판이 제자리로 쓰던 꼴들)
    std::string tmpOut, stageWhy;
    if (!staged.reserve(o.output, "", tmpOut, stageWhy)) return fail("write", "Cannot open output: " + o.output + " (" + stageWhy + ")");
    stagedNotes();
    {
        KooRemapper::DeckWriter w(tmpOut, KooRemapper::deck_newline::detect(o.model));
        if (!w.ok()) return fail("write", "Cannot open output: " + o.output);
        Writer wr{o, im, idx, sel, pidNodes, pk, nd, rm, console, st};
        wr.out = &w.stream();
        wr.processFile(o.model, 0);
        w.close();
        if (!wr.commaLines.empty()) {
            std::vector<std::string> lines = wr.commaLines;
            if (wr.commaCount > (long long)wr.commaLines.size())
                lines.push_back("… 외 " + std::to_string(wr.commaCount - (long long)wr.commaLines.size()) + " 장");
            return fail("renumber", "renumber: 콤마 자유형식 줄 " + std::to_string(wr.commaCount) + " 장은 칸 자리가 없어 번호를 제자리에 "
                                    "바꿔 쓸 수 없다 — 거절한다", lines,
                        "renumber: false 면 그 줄을 그대로 싣는다 · 고정폭으로 고쳐 쓰면 번호를 매길 수 있다");
        }
        // 쓰다 멈춘 덱(번호를 다 못 바꾼 줄이 남는다)은 바꿔 넣지 않는다 — 그럴듯하게 읽히는 틀린 덱이다
        if (wr.failed) return fail("write", "쓰기가 멈췄다(위 [ERROR]) — 산출을 쓰지 않았다");
        if (!wr.missingIncludes.empty())
            return fail("include", "*INCLUDE 를 열 수 없다 — 인클루드를 못 읽으면 그 안의 파트가 조용히 빠진다. 거절한다", wr.missingIncludes);
    }
    if (st.includesInlined > 0)
        console.info("  *INCLUDE " + std::to_string(st.includesInlined) +
                     " 개를 펼쳐 넣었다 — 산출 덱은 홀로 선다");
    for (const auto& kv : st.setsTrimmed)
        console.info("  trimmed " + kv.first + ": " + std::to_string(kv.second) + " 블록");
    if (!st.setsDropped.empty())
        console.warning("멤버를 ID 로 못 읽는 세트 " + std::to_string(st.setsDropped.size()) +
                        " 개를 버렸다(`_GENERATE`·`_GENERAL`·`_ADD` 등) — "
                        "그 세트를 쓰는 카드가 있으면 손으로 다시 적어야 한다");
    for (const auto& kv : st.carriedWhole)
        console.info("  " + kv.first + " 블록 " + std::to_string(kv.second) +
                     " 개를 통째로 실었다(안 고른 정의가 같이 온다 — 무해하다)");
    if (st.partVariantBlocks > 0)
        console.warning("*PART_* 변형 블록 " + std::to_string(st.partVariantBlocks) +
                        " 개를 통째로 실었다 — 안 고른 파트가 같이 왔을 수 있다(요소 없는 파트는 경고다)");
    // ★초기상태를 버렸으면 **크게** 말한다. 조용히 빠지면 프리스트레스된 모델에서 파트를
    //   뽑아 그대로 돌리고 "응력이 왜 0 인가" 를 한참 뒤에 묻는다.
    if (!st.droppedState.empty()) {
        long long n = 0;
        std::string kws;
        for (const auto& kv : st.droppedState) {
            n += kv.second;
            kws += (kws.empty() ? "" : ", ") + kv.first;
        }
        console.warning("★초기상태·이력을 버렸다 — " + kws + " (" + std::to_string(n) +
                        " 줄). 뽑은 덱은 **초기응력이 없다.**");
        console.info("  카드 수가 데이터로 정해지는 꼴이라(NINT·NHISV·LARGE) 자르면 응력이 "
                     "요소끼리 섞일 수 있어 **자르지 않았다**.");
        console.info("  상태를 이어가려면 전체 모델 해석의 dynain 을 `update`(좌표)·"
                     "`prestress`(초기응력)로 **뽑은 덱에 다시** 적용하라 — `renumber: false` 가 "
                     "기본이라 절점·요소 ID 가 그대로여서 ID 로 맞는다.");
    }
    if (!st.dropped.empty()) {
        long long total = 0;
        for (const auto& kv : st.dropped) total += kv.second;
        console.info("  dropped: " + std::to_string(st.dropped.size()) + " 키워드 · " +
                     std::to_string(total) + " 줄 (리포트의 dropped_keywords 에 전부 적는다)");
    }

    // ── 번호 표(임시 파일) ──────────────────────────────────────────────────
    if (rm.on) {
        std::ostringstream mf;
        mf << "{\n  \"kind\": \"extract-parts renumber map\",\n  \"note\": \"old -> new. 이것이 없으면 되돌릴 수 없다\",\n  \"nodes\": [";
        for (size_t i = 0; i < pk.nodes.size(); ++i)
            mf << (i ? "," : "") << "[" << pk.nodes[i] << "," << (i + 1) << "]";
        mf << "],\n  \"elements\": [";
        for (size_t i = 0; i < pk.allElems.size(); ++i)
            mf << (i ? "," : "") << "[" << pk.allElems[i] << "," << (i + 1) << "]";
        mf << "]\n}\n";
        if (!staged.writeText(mapWrite, mf.str(), stageWhy))
            return fail("write", "Cannot write renumber map: " + mapWrite + " (" + stageWhy + ")");
        stagedNotes();
        if (pk.nodes.size() > 1000000)
            console.warning("번호 표가 " + std::to_string(pk.nodes.size()) +
                            " 항이다 — 파일이 크다. 되돌리려면 필요하므로 지우지 말라");
    }

    // ── 패스 3 — 되읽기 검증(임시 산출을 읽는다) ─────────────────────────────
    if (o.verify) {
        // 번호를 다시 매겼으면 산출의 번호는 새 번호다 — 다른 읽기만 말하는 절점(옛 번호)은 대지 않는다(갈림이 덱에 있는 줄은 이미
        // 거절했고, 남은 것은 설명서 꼴 줄을 정수 폭으로 읽은 넘친 몫이다)
        vf = verifyOutput(tmpOut, rm.on ? std::vector<int>() : altExisting);
        verified = true;
        if (vf.undefNodes == 0 && vf.undefParts == 0 && vf.undefSections == 0 && vf.undefMaterials == 0 && vf.malformed == 0) {
            console.success("verify: 산출 덱의 미정의 참조 0 (절점·파트·섹션·재질 전수)");
        } else {
            std::vector<std::string> lines;
            if (vf.firstBadNode) lines.push_back("첫 미정의 절점 NID " + std::to_string(vf.firstBadNode));
            if (vf.firstBadPart) lines.push_back("첫 미정의 파트 PID " + std::to_string(vf.firstBadPart));
            if (vf.malformed) lines.push_back("첫 깨진 콤마 줄 — " + vf.firstMalformed);
            return fail("verify", "verify: 미정의 절점 " + std::to_string(vf.undefNodes) +
                                  " · 파트 " + std::to_string(vf.undefParts) +
                                  " · 섹션 " + std::to_string(vf.undefSections) +
                                  " · 재질 " + std::to_string(vf.undefMaterials) +
                                  (vf.malformed ? " · 칸이 깨진 콤마 줄 " + std::to_string(vf.malformed) : std::string()) +
                                  " — 산출 · 번호 지도를 쓰지 않았다(이번 실행의 임시 파일만 지웠다 · 같은 이름의 앞 파일은 그대로다)",
                        lines, "산출을 보려면 verify: false 로 다시 돌려라(되읽지 않고 쓴다)");
        }
    }

    // ── 바꿔 넣기 — 보고를 임시로 먼저 써 두고(못 쓰면 아무것도 바꾸지 않는다) 잠금을 쥐고 산출 · 번호 지도 · 보고 차례로 ─────────
    //    ★보고는 늘 마지막이고 실제로 바꿔 넣은 것을 말한다 — 산출을 바꿔 넣은 뒤 번호 지도가 실패하면 보고를 그 상태(ok false ·
    //    output_written true · 번호 지도 null)로 다시 쓴다. 예전엔 rc 1 · 새 산출 · 앞 번호 지도 · 앞 보고(앞 실행을 말한다)가 남았다.
    //    잠금(.kr_tmp_lock_<이름 해시> · flock)은 같은 산출을 쓰는 동시 실행이 셋을 서로 섞지 못하게 한다(3차 검토 — 한 실행의 산출이
    //    다른 실행의 번호 지도와 짝을 이뤘다). 바꿔 넣는 사이에 읽는 쪽이 반쯤 바뀐 묶음을 볼 수는 있다(파일마다만 원자적이다)
    const bool writeReport = reportWritable();
    if (writeReport) {
        if (!staged.writeText(o.reportPath, reportJson(true, true, rm.on), stageWhy))
            return fail("write", "Cannot write report: " + o.reportPath + " (" + stageWhy + ")");
        stagedNotes();
    }
    KooRemapper::staged_write::CommitLock commitLock(o.output);
    for (const auto& n : commitLock.takeNotes()) n.warn ? console.warning(n.text) : console.info(n.text);
    if (!staged.commit(o.output, stageWhy))
        return fail("commit", "산출을 제 이름으로 바꿔 넣지 못했다: " + o.output + " (" + stageWhy + ") — 같은 이름의 앞 파일은 그대로다");
    stagedNotes();
    console.success("wrote: " + o.output + "  (*NODE " + std::to_string(st.nodeLines) +
                    " · 요소 카드 " + std::to_string(st.elemCards) +
                    " · *PART " + std::to_string(st.partsEmitted) + ")");
    // 산출은 이번 것이다 — 뒤의 것이 실패하면 보고를 이 상태로 다시 쓴다(앞 실행을 말하는 보고를 남기지 않는다)
    auto afterOutput = [&](const std::string& message) {
        console.error(message);
        refusals.push_back({"commit", message, {}});
        staged.discardAll();
        if (reportWritable()) {
            std::string why;
            if (staged.writeText(o.reportPath, reportJson(false, true, false), why) && staged.commit(o.reportPath, why))
                console.info("report: " + o.reportPath + " (ok false — 산출은 바꿔 넣었다)");
            else
                console.error("Cannot write report: " + o.reportPath + " (" + why + ") — 그 자리의 보고(있으면)는 이번 실행의 것이 아니다");
            staged.discardAll();
            stagedNotes();
        }
        return 1;
    };
    if (rm.on) {
        if (!staged.commit(mapWrite, stageWhy)) {
            // 앞 실행의 번호 지도가 남으면 새 산출과 짝이 틀린다 — 이 op 의 지도로 알아볼 때만 지운다
            std::string gone;
            if (fileExists(mapWrite) && isRenumberMap(mapWrite)) {
                std::error_code ec;
                if (std::filesystem::remove(mapWrite, ec)) gone = " · 앞 실행의 번호 지도는 지웠다(새 산출과 짝이 아니다)";
            }
            return afterOutput("번호 지도를 제 이름으로 바꿔 넣지 못했다: " + mapWrite + " (" + stageWhy + ") — 산출은 바꿔 넣었는데 "
                               "되돌릴 표가 없다" + gone);
        }
        stagedNotes();
        console.info("  renumber map: " + mapWrite);
    } else if (fileExists(mapPathOf) && !KooRemapper::include_closure::sameFile(mapPathOf, o.reportPath)) {
        // 지난 실행이 남긴 번호 지도는 번호를 매기지 않은 이 산출과 짝이 아니다 — 이 op 의 번호 지도로 알아볼 때만 지운다
        if (isRenumberMap(mapPathOf)) {
            std::error_code ec;
            std::filesystem::remove(mapPathOf, ec);
            console.info("  지난 실행의 번호 지도를 지웠다(번호를 매기지 않은 이 산출과 짝이 아니다): " + mapPathOf);
        } else {
            console.warning("번호 지도 자리 「" + mapPathOf + "」 에 이 op 의 번호 지도가 아닌 파일이 있다 — 그대로 둔다");
        }
    }
    if (writeReport) {
        // 이름 바꾸기를 폴더 권한이 막으면 도우미가 그 파일에 제자리로 쓴다([WARN]). 그것도 못 하면 그 자리의 보고는 앞 실행의 것이다
        if (!staged.commit(o.reportPath, stageWhy)) {
            console.error("Cannot write report: " + o.reportPath + " (" + stageWhy + ") — 산출 · 번호 지도는 바꿔 넣었다 · 그 자리의 "
                          "보고(있으면)는 이번 실행의 것이 아니다");
            return 1;
        }
        stagedNotes();
        console.info("report: " + o.reportPath);
    }
    return 0;
}
