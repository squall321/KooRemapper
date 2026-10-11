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
#include "util/YamlComment.h"

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
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
};

// `*PART` 블록은 '제목 줄 + 카드 2' 가 **쌍으로 반복**된다(제목은 비워 둘 수 있으나 생략 못 한다).
// ⚠ 그래서 **빈 줄도 카드 줄로 센다** — 건너뛰면 다음 파트의 제목 자리가 한 칸 밀려 PID 가
// 통째로 어긋난다. 주석(`$`)만 뺀다.
//
// ⚠ 덱 전문을 메모리에 들지 않는다(2.32GB 전제) — **블록 하나만** 버퍼한다.
void indexDeck(const std::string& path, DeckIndex& idx, std::set<std::string>& visited,
               int depth = 0) {
    if (depth > 8 || visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    const std::string baseDir = dirOf(path);
    const int sfw = 10;                        // `*PART` 카드 2 와 `*SECTION_*` 은 8I10 이다
    std::string line, kw;
    std::vector<std::string> buf;              // 지금 블록의 카드 줄

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
        }
        buf.clear();
    };

    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        size_t g = line.find_first_not_of(" \t");
        if (g != std::string::npos && line[g] == '*') {
            flush();
            kw = kwBare(keywordToken(line));
            if (kw == "*KEYWORD") {
                int w = KooRemapper::keywordCardDeckWidth(line);
                if (w > 0) idx.fieldWidth = w;
            }
            if (starts(kw, "*PART") && kw != "*PART" && kw != "*PART_TITLE" &&
                std::find(idx.partVariants.begin(), idx.partVariants.end(), kw) ==
                    idx.partVariants.end())
                idx.partVariants.push_back(kw);
            continue;
        }
        if (kw == "*INCLUDE") {
            std::string rel = trim(line);
            if (!rel.empty()) indexDeck(joinPath(baseDir, rel), idx, visited, depth + 1);
            continue;
        }
        if (kw != "*PART" && kw != "*PART_TITLE" && !starts(kw, "*SECTION_SOLID")) continue;
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
};

void scanElements(const std::string& path, const std::vector<int>& sel, const DeckIndex& idx,
                  const std::map<int, int>& pidNodes, Picked& pk,
                  std::set<std::string>& visited, int depth = 0, bool top = true) {
    if (depth > 8 || visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    const std::string baseDir = dirOf(path);
    std::string line, kw;
    int fw = idx.fieldWidth;
    KooRemapper::ElementKeywordInfo info;
    KooRemapper::ElementCardSpan span;
    int remaining = 0, lineIdx = 0;
    std::vector<std::string> card1;
    bool inElem = false, opaque = false, picked = false, inInclude = false;
    // 보·질량·이산 족 — 공용 판정기의 별도 축이 칸 자리를 안다(ElementCardLayout.h 의 인용).
    KooRemapper::AuxElementCard aux;
    int auxRemaining = 0, auxLineIdx = 0;
    bool auxPicked = false;
    std::vector<std::string> auxCard1;

    while (std::getline(in, line)) {
        size_t g = line.find_first_not_of(" \t\r\n");
        if (g != std::string::npos && line[g] == '*') {
            remaining = 0;
            kw = kwBare(keywordToken(line));
            fw = KooRemapper::keywordFieldWidth(line, idx.fieldWidth);
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
            }
            continue;
        }
        if (inInclude) {
            if (!isDataLine(line)) continue;
            std::string rel = trim(line);
            if (!rel.empty())
                scanElements(joinPath(baseDir, rel), sel, idx, pidNodes, pk, visited,
                             depth + 1, false);
            continue;
        }
        if (!inElem) continue;
        if (g != std::string::npos && line[g] == '$') continue;
        if (g == std::string::npos && remaining == 0) continue;     // 카드 밖의 빈 줄

        if (opaque && aux.supported) {
            // ★칸 자리를 **안다** — PID 칸도 족마다 다르다(`*ELEMENT_MASS` 는 칸 3).
            //   `*ELEMENT_PLOTEL` 은 PID 가 없어 여기서 고르지 않고, 쓰기 쪽이 '두 절점이 다
            //   남았나' 로 판정한다(그 줄은 표시용이고 파트에 속하지 않는다).
            if (auxRemaining == 0) {
                auxCard1 = cardFields(line, fw);
                auxLineIdx = 0;
                auxRemaining = aux.lines;
                const int pid = (aux.partField >= 0) ? fieldInt(auxCard1, (size_t)aux.partField) : 0;
                auxPicked = aux.hasPart && pid > 0 && inSorted(sel, pid);
                if (auxPicked) ++pk.auxCards;
            }
            if (auxLineIdx == 0 && auxPicked) {
                auto take = [&](int from, int cnt) {
                    if (from < 0) return;
                    for (int q = 0; q < cnt; ++q) {
                        int v = fieldInt(auxCard1, (size_t)(from + q));
                        if (v > 0) pk.nodes.push_back(v);
                    }
                };
                take(aux.nodeSkip, aux.nodeCount);
                take(aux.nodeSkip2, aux.nodeCount2);
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
            //   (`*ELEMENT_MASS_NODE_SET` 은 PID 가 칸 **3** 이다), 1 로 가정하면 그 카드가
            //   '안 고른 파트' 로 분류돼 **조용히 버려진다**(실측으로 회귀 L-14 가 잡았다).
            auto f = cardFields(line, fw);
            const int pf = (aux.family != KooRemapper::AuxFamily::NONE && aux.partField >= 0)
                               ? aux.partField : 1;
            int pid = fieldInt(f, (size_t)pf);
            if (pid > 0 && inSorted(sel, pid)) ++pk.opaqueElemTouched[kw];
            else                               ++pk.opaqueElemOther[kw];
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
bool putField(std::string& line, int fw, size_t idx, int value) {
    const size_t off = idx * (size_t)fw;
    if (fw <= 0) return false;
    char buf[32];
    int n = std::snprintf(buf, sizeof(buf), "%*d", fw, value);
    if (n != fw) return false;
    if (line.size() < off + (size_t)fw) line.resize(off + (size_t)fw, ' ');
    line.replace(off, (size_t)fw, buf, (size_t)fw);
    return true;
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
    std::map<std::string, long long> setsTrimmed;   // 키워드 → 자른 블록 수
    std::vector<int> setsDropped;                   // 못 자르는 변형의 SID
    std::map<std::string, long long> carriedWhole;  // 통째로 실은 ID 블록(과포함)
    long long includesInlined = 0;                  // 펼친 `*INCLUDE` 파일 수
    long long auxCards = 0;                         // 보·질량·이산 족에서 실은 카드
};

enum class Act { VERBATIM, NODE, ELEM, ELEM_AUX, PART, PART_VARIANT, IDBLOCK, SETS, DROP };

Act classify(const std::string& kw, const Opts& o, bool elemSupported, bool auxSupported) {
    if (kw == "*KEYWORD" || kw == "*TITLE" || kw == "*END" || starts(kw, "*PARAMETER") ||
        starts(kw, "*COMMENT") || starts(kw, "*CONTROL"))
        return Act::VERBATIM;
    // `*DATABASE_HISTORY_*` 는 절점·요소 ID 를 담는다 — 통째로 실으면 산출 덱에 없는 것을
    // 가리킨다. 그 밖의 `*DATABASE_` 는 순수 설정이라 그대로 싣는다.
    if (starts(kw, "*DATABASE")) return has(kw, "_HISTORY") ? Act::DROP : Act::VERBATIM;
    if (kw == "*NODE") return o.incNodes ? Act::NODE : Act::DROP;
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
        else if (act == Act::NODE || act == Act::ELEM || act == Act::ELEM_AUX)
            pendingKw = line;                                 // 첫 줄이 실릴 때 낸다
        else if (act == Act::DROP) st.dropped[kw] += 1;
    }

    void onData(const std::string& line, size_t g, const std::string& baseDir, int depth) {
        switch (act) {
            case Act::VERBATIM: *out << line << "\n"; break;
            case Act::DROP: {
                // `*INCLUDE` 는 버리지 않고 **펼친다** — 그 안에 고른 파트의 요소가 있다.
                if (kw == "*INCLUDE" && isDataLine(line)) {
                    std::string rel = trim(line);
                    if (rel.empty()) break;
                    processFile(joinPath(baseDir, rel), depth + 1);
                    break;
                }
                st.dropped[kw] += 1;
                break;
            }
            case Act::NODE: {
                if (!isDataLine(line)) break;             // `*NODE` 안의 주석은 싣지 않는다
                int nid = 0;
                double xyz[3];
                if (!readNodeLine(line, fw, nid, xyz)) break;
                if (!inSorted(pk.nodes, nid)) break;
                std::string o2 = line;
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
                    if (rm.on) {
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
                    card1 = cardFields(line, fw);
                    lineIdx = 0;
                    remaining = aux.lines;
                    if (aux.hasPart) {
                        const int pid = (aux.partField >= 0)
                                            ? fieldInt(card1, (size_t)aux.partField) : 0;
                        picked = (pid > 0 && inSorted(sel, pid));
                    } else {
                        // PID 칸이 없다(`*ELEMENT_PLOTEL`) — 표시용이고 파트에 속하지 않는다.
                        // **두 절점이 다 남았을 때만** 싣는다(한쪽만 남은 선은 선이 아니다).
                        picked = (aux.nodeCount > 0);
                        for (int q = 0; q < aux.nodeCount; ++q) {
                            const int v = fieldInt(card1, (size_t)(aux.nodeSkip + q));
                            if (v <= 0 || !inSorted(pk.nodes, v)) { picked = false; break; }
                        }
                    }
                    if (picked) ++st.auxCards;
                }
                if (picked) {
                    std::string o2 = line;
                    // ⚠ 번호를 다시 매길 때 **절점 칸만** 고친다. 보의 RT1·RR1·LOCAL 이나
                    //   안전벨트의 SBRID·SLEN 을 같이 고치면 카드가 깨진다. 요소 ID 는
                    //   건드리지 않는다 — 번호 표는 격자 요소만 담는다(족별로 번호가 따로다).
                    if (rm.on && lineIdx == 0) {
                        auto put = [&](int from, int cnt) {
                            if (from < 0) return;
                            for (int q = 0; q < cnt; ++q) {
                                const int v = fieldInt(card1, (size_t)(from + q));
                                if (v > 0) putField(o2, fw, (size_t)(from + q), rm.node(v));
                            }
                        };
                        put(aux.nodeSkip, aux.nodeCount);
                        put(aux.nodeSkip2, aux.nodeCount2);
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
                    if (rm.on)
                        for (size_t q = 0; q < 4; ++q) {
                            int v = fieldInt(f, q);
                            if (v > 0) putField(o2, sfw, q, rm.node(v));
                        }
                    *out << o2 << "\n";
                    break;
                }
                if (stream) {                    // `_COLUMN` — 한 줄에 하나
                    int v = fieldInt(f, 0);
                    if (v <= 0 || !inSorted(pk.nodes, v)) break;
                    std::string o2 = line;
                    if (rm.on) putField(o2, sfw, 0, rm.node(v));
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
        if (failed || depth > 8) return;
        if (visited.count(path)) return;
        visited.insert(path);
        std::ifstream in(path);
        if (!in.is_open()) { missingIncludes.push_back(path); return; }
        if (depth > 0) ++st.includesInlined;
        const std::string baseDir = dirOf(path);
        // 블록 상태는 파일 경계에서 닫는다 — 인클루드 안의 키워드가 바깥 블록을 잇지 않는다.
        const std::string savedKw = kw, savedKwLine = kwLine;
        const Act savedAct = act;
        flushBlock();
        act = Act::VERBATIM;
        kw.clear();
        std::string line;
        while (std::getline(in, line)) {
            while (!line.empty() && line.back() == '\r') line.pop_back();
            size_t g = line.find_first_not_of(" \t");
            if (g != std::string::npos && line[g] == '*') {
                // 인클루드 안의 `*KEYWORD`·`*END` 는 펼친 덱에 두 번 나오면 안 된다.
                std::string k2 = kwBare(keywordToken(line));
                if (depth > 0 && (k2 == "*KEYWORD" || k2 == "*END")) {
                    flushBlock();
                    act = Act::DROP;
                    kw = k2;
                    continue;
                }
                onKeyword(line);
                continue;
            }
            onData(line, g, baseDir, depth);
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

struct Verify {
    long long undefNodes = 0, undefParts = 0, undefSections = 0, undefMaterials = 0;
    int firstBadNode = 0, firstBadPart = 0;
};

Verify verifyOutput(const std::string& path) {
    Verify v;
    DeckIndex idx;
    { std::set<std::string> vis; indexDeck(path, idx, vis); }
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
    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        size_t g = line.find_first_not_of(" \t");
        if (g != std::string::npos && line[g] == '*') {
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
                auto f = cardFields(line, fw);
                if (vaux.partField >= 0) {
                    const int pid = fieldInt(f, (size_t)vaux.partField);
                    if (pid > 0) elemPids.push_back(pid);
                }
                auto take = [&](int from, int cnt) {
                    if (from < 0) return;
                    for (int q = 0; q < cnt; ++q) {
                        const int v = fieldInt(f, (size_t)(from + q));
                        if (v > 0) elemNodes.push_back(v);
                    }
                };
                take(vaux.nodeSkip, vaux.nodeCount);
                take(vaux.nodeSkip2, vaux.nodeCount2);
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
            int nid = 0;
            double xyz[3];
            if (readNodeLine(line, fw, nid, xyz)) nodes.push_back(nid);
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

std::string jsonStr(const std::string& s) {
    std::string o = "\"";
    for (char c : s) {
        if (c == '"' || c == '\\') { o += '\\'; o += c; }
        else if (c == '\n') o += "\\n";
        else if (c == '\t') o += "\\t";
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

}  // namespace

// ─────────────────────────────────────────────────────────────────────────────
// runExtractParts
// ─────────────────────────────────────────────────────────────────────────────

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
    }
    yf.close();

    const std::string cfgDir = dirOf(yamlFile);
    auto rp = [&](const std::string& p) {
        return p.empty() ? p : KooRemapper::yamlResolvePath(cfgDir, p);
    };
    o.model = rp(o.model);
    o.output = rp(o.output);
    o.reportPath = rp(o.reportPath);

    if (o.model.empty()) { console.error("'model' is required in YAML config"); return 1; }
    { std::ifstream probe(o.model);
      if (!probe.is_open()) { console.error("Cannot open model: " + o.model); return 1; } }
    if (o.parts.empty() && o.partTitles.empty()) {
        console.error("'parts' (PID list) 또는 'part_titles' (와일드카드) 가 하나는 필요하다 — "
                      "무엇을 뽑을지 고르지 않으면 할 일이 없다");
        return 1;
    }
    if (o.output.empty()) {
        size_t dot = o.model.rfind('.');
        o.output = (dot == std::string::npos) ? o.model + "_extracted"
                   : o.model.substr(0, dot) + "_extracted" + o.model.substr(dot);
    }

    console.info("extract-parts: " + o.model);

    // ── 패스 0 — `*PART` 표 ──────────────────────────────────────────────────
    DeckIndex idx;
    { std::set<std::string> vis; indexDeck(o.model, idx, vis); }
    if (idx.parts.empty()) {
        console.error("No *PART definitions found (or only *PART_* variants we cannot chunk)");
        return 1;
    }
    const std::map<int, int> pidNodes = pidNodeCounts(idx);

    // 고를 PID 를 확정한다 — 제목 와일드카드는 여기서 PID 로 바뀐다.
    std::vector<int> sel = o.parts, missing;
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
        console.error("덱에 없는 PID: " + s + " — 오타면 조용히 빈 덱이 나온다");
        return 1;
    }
    std::vector<int> selDefined;
    for (int p : sel) if (idx.parts.count(p)) selDefined.push_back(p);
    sel = selDefined;
    if (sel.empty()) { console.error("고를 파트가 없다"); return 1; }
    console.info("  parts: " + std::to_string(sel.size()) + " / " +
                 std::to_string(idx.parts.size()) + " (덱 전체)");
    for (const auto& h : titleHits) console.info("    title match: " + h);

    // ── 패스 1 — 요소·절점 ──────────────────────────────────────────────────
    Picked pk;
    { std::set<std::string> vis; scanElements(o.model, sel, idx, pidNodes, pk, vis); }
    if (idx.fieldWidth != 8)
        console.info("  deck field width: " + std::to_string(idx.fieldWidth));
    // ⚠ 보·질량·이산 족도 센다. 격자 카드만 세면 **보만으로 된 파트**(볼트·용접점 묶음)가
    //   "요소가 없다" 로 거절된다 — 회귀 L-0 이 그 자리를 지킨다.
    if (pk.cards == 0 && pk.auxCards == 0) {
        console.error("고른 파트에 요소가 없다 — PID 는 맞는데 그 파트의 요소를 못 읽었다는 뜻이다");
        return 1;
    }
    // ★모르는 `*ELEMENT_*` 변형이 고른 파트의 요소를 담고 있으면 **거절한다.**
    //   조용히 빠뜨린 덱은 그럴듯하게 돌면서 틀린다.
    if (!pk.opaqueElemTouched.empty()) {
        for (const auto& kv : pk.opaqueElemTouched)
            console.error(kv.first + " 가 고른 파트의 요소 " + std::to_string(kv.second) +
                          " 줄을 담고 있는데 이 op 은 그 카드의 줄 수를 모른다 — "
                          "조용히 빠뜨리지 않기 위해 거절한다");
        console.info("읽을 수 있는 것은 격자 3족(*ELEMENT_SOLID·SHELL·TSHELL)과 "
                     "보 족 5종(*ELEMENT_BEAM·DISCRETE·MASS·SEATBELT·PLOTEL)이다");
        return 1;
    }
    console.info("  element cards: " + std::to_string(pk.cards) +
                 (pk.auxCards > 0 ? " (+보·질량·이산 " + std::to_string(pk.auxCards) + ")" : "") +
                 "  nodes: " + std::to_string(pk.nodes.size()));
    for (const auto& k : pk.auxKws)
        console.info("    " + k + " — 칸 자리를 알고 읽었다(추측이 아니다)");

    Needed nd;
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
    Remap rm;
    if (o.renumber) {
        if (pk.elemIdCollision) {
            console.error("renumber: 종류가 다른 요소가 같은 EID 를 쓴다 — 전역으로 1부터 다시 "
                          "매기면 어느 쪽인지 알 수 없게 된다. renumber: false 로 돌려라");
            return 1;
        }
        rm.on = true;
        rm.nodes = &pk.nodes;
        rm.elems = &pk.allElems;
        console.info("  renumber: 절점 1.." + std::to_string(pk.nodes.size()) +
                     " · 요소 1.." + std::to_string(pk.allElems.size()));
    }

    // ── 패스 2 — 쓰기 ───────────────────────────────────────────────────────
    WriteStats st;
    {
        KooRemapper::DeckWriter w(o.output, KooRemapper::deck_newline::detect(o.model));
        if (!w.ok()) { console.error("Cannot open output: " + o.output); return 1; }
        Writer wr{o, idx, sel, pidNodes, pk, nd, rm, console, st};
        wr.out = &w.stream();
        wr.processFile(o.model, 0);
        w.close();
        if (wr.failed) return 1;
        if (!wr.missingIncludes.empty()) {
            for (const auto& m : wr.missingIncludes)
                console.error("*INCLUDE 를 열 수 없다: " + m);
            console.error("인클루드를 못 읽으면 그 안의 파트가 조용히 빠진다 — 거절한다");
            return 1;
        }
    }
    console.success("wrote: " + o.output + "  (*NODE " + std::to_string(st.nodeLines) +
                    " · 요소 카드 " + std::to_string(st.elemCards) +
                    " · *PART " + std::to_string(st.partsEmitted) + ")");
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
    if (!st.dropped.empty()) {
        long long total = 0;
        for (const auto& kv : st.dropped) total += kv.second;
        console.info("  dropped: " + std::to_string(st.dropped.size()) + " 키워드 · " +
                     std::to_string(total) + " 줄 (리포트의 dropped_keywords 에 전부 적는다)");
    }

    // ── 번호 표 ─────────────────────────────────────────────────────────────
    std::string mapPath;
    if (rm.on) {
        {   // `out.k` → `out_renumber_map.json` (확장자 앞에 붙인다)
            size_t dot = o.output.rfind('.');
            size_t sep = o.output.find_last_of("/\\");
            if (dot != std::string::npos && (sep == std::string::npos || dot > sep))
                mapPath = o.output.substr(0, dot) + "_renumber_map.json";
            else
                mapPath = o.output + "_renumber_map.json";
        }
        std::ofstream mf(mapPath);
        if (!mf.is_open()) { console.error("Cannot write renumber map: " + mapPath); return 1; }
        mf << "{\n  \"note\": \"old -> new. 이것이 없으면 되돌릴 수 없다\",\n  \"nodes\": [";
        for (size_t i = 0; i < pk.nodes.size(); ++i)
            mf << (i ? "," : "") << "[" << pk.nodes[i] << "," << (i + 1) << "]";
        mf << "],\n  \"elements\": [";
        for (size_t i = 0; i < pk.allElems.size(); ++i)
            mf << (i ? "," : "") << "[" << pk.allElems[i] << "," << (i + 1) << "]";
        mf << "]\n}\n";
        mf.close();
        console.info("  renumber map: " + mapPath);
        if (pk.nodes.size() > 1000000)
            console.warning("번호 표가 " + std::to_string(pk.nodes.size()) +
                            " 항이다 — 파일이 크다. 되돌리려면 필요하므로 지우지 말라");
    }

    // ── 패스 3 — 되읽기 검증 ────────────────────────────────────────────────
    Verify vf;
    if (o.verify) {
        vf = verifyOutput(o.output);
        const bool ok = (vf.undefNodes == 0 && vf.undefParts == 0 &&
                         vf.undefSections == 0 && vf.undefMaterials == 0);
        if (ok)
            console.success("verify: 산출 덱의 미정의 참조 0 (절점·파트·섹션·재질 전수)");
        else {
            console.error("verify: 미정의 절점 " + std::to_string(vf.undefNodes) +
                          " · 파트 " + std::to_string(vf.undefParts) +
                          " · 섹션 " + std::to_string(vf.undefSections) +
                          " · 재질 " + std::to_string(vf.undefMaterials));
            if (vf.firstBadNode) console.error("  첫 미정의 절점 NID " + std::to_string(vf.firstBadNode));
            if (vf.firstBadPart) console.error("  첫 미정의 파트 PID " + std::to_string(vf.firstBadPart));
        }
    }

    // ── 리포트 ──────────────────────────────────────────────────────────────
    if (!o.reportPath.empty()) {
        std::ofstream jf(o.reportPath);
        if (!jf.is_open()) { console.error("Cannot write report: " + o.reportPath); return 1; }
        jf << "{\n  \"op\": \"extract-parts\",\n";
        jf << "  \"model\": " << jsonStr(o.model) << ",\n";
        jf << "  \"output\": " << jsonStr(o.output) << ",\n";
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
        jf << "  \"renumber\": {\"on\": " << (rm.on ? "true" : "false") << ", \"map\": "
           << (mapPath.empty() ? std::string("null") : jsonStr(mapPath)) << "},\n";
        jf << "  \"verify\": "
           << (o.verify ? "{\"undefined_nodes\": " + std::to_string(vf.undefNodes) +
                          ", \"undefined_parts\": " + std::to_string(vf.undefParts) +
                          ", \"undefined_sections\": " + std::to_string(vf.undefSections) +
                          ", \"undefined_materials\": " + std::to_string(vf.undefMaterials) + "}"
                        : "null")
           << "\n}\n";
        jf.close();
        console.info("report: " + o.reportPath);
    }

    if (o.verify && (vf.undefNodes || vf.undefParts || vf.undefSections || vf.undefMaterials))
        return 1;
    return 0;
}
