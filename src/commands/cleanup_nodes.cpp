// 아무도 참조하지 않는 절점을 찾아 보고하고(기본) 지운다 — 숫자를 긁지 않고 **키워드별로** 읽는다
//
// 왜 이 op 이 KooRemapper 안에 있어야 하나 (요청서 2026-10-10 §1).
// 요청자는 밖에서 한 번 시도했고 **실패했다** — "비-`*NODE`/`*ELEMENT_` 줄에서 8칸·10칸·공백
// 분리로 숫자를 전부 긁었더니 118,568개 전부가 참조됨으로 나왔다."
//
// ★그 실패의 원인은 '숫자를 긁은 것' 자체가 아니다. **`*SET_NODE_*` 블록까지 긁은 것**이다.
// 덱에는 보통 '전체 절점' 세트가 있고, 그 블록은 **모든 절점 ID 를 글자 그대로 담는다.**
// 그것을 참조로 세면 고아가 사라진다. 그래서 여기서는
//   · `*SET_NODE_*` 의 멤버십은 **참조로 세지 않고** 대신 세트를 **정리(prune)** 한다.
//   · 다만 **그 세트를 이름하는 키워드**(CNRB·SPC·하중…)가 있으면 멤버를 전이로 **남긴다**
//     — 요청서의 CNRB 71건이 정확히 이 경로다(CNRB 는 절점을 NSID 로 가리킨다).
//
// **"안전" 의 뜻** — '내가 이해한 것만 지운다'. 우리가 모르는 키워드가 삭제 후보와 같은 정수를
// 칸에 갖고 있으면 **남기고 `unknown_keyword_kept` 에 적는다**(거절이 아니라 보고).
// 그러므로 안전을 만드는 것은 `keep_referenced_by` 목록이 아니라 **모르는 키워드 전수 훑기**다.
// 목록은 "이건 추측이 아니다" 를 말하고 `mode: force` 에서 갈라진다.
//
// **`*INCLUDE` 를 읽는다.** 안 읽으면 인클루드가 쓰는 절점을 고아로 보고 지운다 — 조용하고
// 치명적이다. `safe` 는 못 읽은 인클루드가 하나라도 있으면 **쓰지 않는다**(rc=1).
//
// 패스 구성(2.32GB 덱 전제 — 문자열로 모으지 않는다):
//   0) *SECTION_SOLID ELFORM + *PART → PID 별 고차 절점 수(카드 줄 수 판정에 필요)
//   1) 정의·요소 참조·키워드 정수·세트 멤버십 + bbox(전)
//   2) bbox(후)
//   3) 덱 재작성(쓰기 모드만)
//   4) 되읽기 검증 — 산출 덱의 '참조하는데 없는 절점' 이 0 인지 **스스로** 찍는다
//
// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cleanup-nodes]]

#include "cleanup_nodes.h"

#include "cli/ConsoleOutput.h"
#include "parser/CardFields.h"
#include "parser/DeckScan.h"
#include "parser/DeckWriter.h"
#include "parser/ElementCardLayout.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using KooRemapper::ConsoleOutput;
using namespace KooRemapper::cards;      // NOLINT(google-build-using-namespace)
// 덱을 **블록으로 걸어가는** 규칙은 `parser/DeckScan.h` 한 곳이다 —
// `extract-parts` 가 같은 것을 전부 필요로 해서 여기 사본을 거기로 옮겼다.
using namespace KooRemapper::deckscan;   // NOLINT(google-build-using-namespace)

namespace {

// ─────────────────────────────────────────────────────────────────────────────
// 작은 보조
// ─────────────────────────────────────────────────────────────────────────────

std::string stripQuotes(const std::string& s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}

// ─────────────────────────────────────────────────────────────────────────────
// `*SET_NODE_*` 변종 분류
// ─────────────────────────────────────────────────────────────────────────────
//
// ─────────────────────────────────────────────────────────────────────────────
// 설정
// ─────────────────────────────────────────────────────────────────────────────

struct Opts {
    std::string model, output, reportPath;
    std::string mode = "report";            // report(기본) | safe | force
    std::vector<std::string> keepKeywords;
    bool pruneSets = true;
    bool verify = true;
};

// 요청서의 다섯. `*` 를 뺀 접두사로 맞춘다 — `BOUNDARY_SPC_NODE` 는 `_ID` 변종도 잡는다.
const char* kDefaultKeep[] = {
    "CONSTRAINED_NODAL_RIGID_BODY",
    "BOUNDARY_SPC_NODE",
    "DATABASE_HISTORY_NODE",
    "CONSTRAINED_EXTRA_NODES",
    "INITIAL_VELOCITY_NODE",
};

// ─────────────────────────────────────────────────────────────────────────────
// 훑기 결과
// ─────────────────────────────────────────────────────────────────────────────

struct Scan {
    std::vector<int> definedMain;      // **주 덱**이 정의한 절점(지울 수 있는 것은 이것뿐)
    std::vector<int> definedAll;       // 인클루드까지 합친 정의
    std::vector<int> byElement;        // 요소가 쓰는 절점
    std::map<std::string, std::vector<int>> keepInts;      // keep 키워드 → 그 블록의 정수
    std::map<std::string, std::vector<int>> unknownInts;   // 그 밖 키워드 → 정수
    std::map<int, std::vector<int>> setMembers;            // SID → 멤버(LIST·COLUMN 만)
    std::vector<int> opaqueSetInts;                        // 못 읽는 세트 변종이 이름하는 절점
    std::vector<std::string> opaqueSetKws;
    std::vector<std::string> elemOpaqueKws;                // 줄 수를 모르는 `*ELEMENT_*` 변종
    // bbox(전)
    double bmin[3] = {1e300, 1e300, 1e300};
    double bmax[3] = {-1e300, -1e300, -1e300};
    bool anyNode = false;
    // 인클루드
    std::vector<std::string> includeRead, includeMissing, includeVariant;
    // 덱
    int fieldWidth = 8;
};

// ─────────────────────────────────────────────────────────────────────────────
// 패스 0 — PID 별 고차 절점 수
// ─────────────────────────────────────────────────────────────────────────────
//
// *ELEMENT_SOLID 카드 **줄 수**가 이것으로 갈린다(고차 정식은 절점 카드가 여러 줄이다).
// 틀리면 연결 줄을 Card 1 로 읽어 **절점 참조를 놓치고 쓰이는 절점을 지운다.**

struct SectionMap {
    std::map<int, int> secElform;   // SECID → ELFORM
    std::map<int, int> partSec;     // PID → SECID
};

void scanSections(const std::string& path, int fw, SectionMap& sm,
                  std::set<std::string>& visited, int depth);

void scanSectionsStream(std::istream& in, const std::string& baseDir, int fw, SectionMap& sm,
                        std::set<std::string>& visited, int depth) {
    std::string line, kw;
    int dataIdx = 0;
    bool pendingInclude = false;
    while (std::getline(in, line)) {
        size_t g = line.find_first_not_of(" \t\r\n");
        if (g != std::string::npos && line[g] == '*') {
            kw = keywordToken(line);
            dataIdx = 0;
            pendingInclude = (kw == "*INCLUDE");
            continue;
        }
        if (!isDataLine(line)) continue;
        if (pendingInclude) {
            std::string rel = trim(line);
            while (!rel.empty() && rel.back() == '\r') rel.pop_back();
            if (!rel.empty() && depth < 8)
                scanSections(joinPath(baseDir, rel), fw, sm, visited, depth + 1);
            continue;   // *INCLUDE 는 줄마다 파일 하나다
        }
        if (starts(kw, "*SECTION_SOLID")) {
            // 제목줄(_TITLE) 뒤에 Card 1 = SECID, ELFORM …
            int want = titleLines(kw);
            if (dataIdx == want) {
                auto f = fields10(line);
                int secid = fieldInt(f, 0), elform = fieldInt(f, 1);
                if (secid > 0 && !sm.secElform.count(secid)) sm.secElform[secid] = elform;
            }
            ++dataIdx;
        } else if (kw == "*PART" || kw == "*PART_TITLE") {
            // 제목줄 + 카드 2 가 반복된다 — PID·SECID 가 모두 양수인 줄만 카드 2 로 본다.
            auto f = fields10(line);
            int pid = fieldInt(f, 0), sec = fieldInt(f, 1);
            if (pid > 0 && sec > 0 && !sm.partSec.count(pid)) sm.partSec[pid] = sec;
        }
    }
    (void)fw;
}

void scanSections(const std::string& path, int fw, SectionMap& sm,
                  std::set<std::string>& visited, int depth) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    scanSectionsStream(in, dirOf(path), fw, sm, visited, depth);
}

std::map<int, int> buildPidNodes(const SectionMap& sm) {
    std::map<int, int> out;
    for (const auto& ps : sm.partSec) {
        auto it = sm.secElform.find(ps.second);
        if (it == sm.secElform.end()) continue;
        int n = KooRemapper::solidNodesFromElform(it->second);
        if (n > 0) out[ps.first] = n;
    }
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// 패스 1 — 정의·참조·세트 멤버십
// ─────────────────────────────────────────────────────────────────────────────

bool matchesKeepList(const std::string& kw, const std::vector<std::string>& keep) {
    for (const auto& k : keep) {
        std::string want = "*" + upper(k);
        if (want.size() > 1 && want[1] == '*') want = want.substr(1);
        if (starts(kw, want.c_str())) return true;
    }
    return false;
}

void scanRefs(const std::string& path, bool isMain, const Opts& o,
              const std::map<int, int>& pidNodes, Scan& sc,
              std::set<std::string>& visited, int depth, long long& paramRefLines);

void scanRefsStream(std::istream& in, const std::string& baseDir, bool isMain, const Opts& o,
                    const std::map<int, int>& pidNodes, Scan& sc,
                    std::set<std::string>& visited, int depth, long long& paramRefLines) {
    enum class Mode { OTHER, NODE, ELEM, SETNODE, KEEP, TEXT, INCLUDE };
    Mode mode = Mode::OTHER;
    std::string kw;
    int fw = sc.fieldWidth;
    KooRemapper::ElementKeywordInfo info;
    KooRemapper::ElementCardSpan span;
    int cardRemaining = 0, cardLineIdx = 0;
    std::vector<std::string> card1;
    bool elemOpaque = false;
    // 보·질량·이산 족 — 공용 판정기의 **별도 축**이 칸 자리를 안다(헤더의 인용 참조).
    KooRemapper::AuxElementCard aux;
    int auxRemaining = 0, auxLineIdx = 0;
    SetKind setKind = SetKind::LIST;
    int setSid = 0, setDataIdx = 0, setTitleN = 0;
    bool setIncrement = false;
    std::string line;

    auto endElementCard = [&]() { cardRemaining = 0; cardLineIdx = 0; };

    while (std::getline(in, line)) {
        size_t g = line.find_first_not_of(" \t\r\n");
        const bool isKw = (g != std::string::npos && line[g] == '*');

        if (isKw) {
            endElementCard();
            kw = kwBare(keywordToken(line));
            fw = KooRemapper::keywordFieldWidth(line, sc.fieldWidth);
            if (kw == "*KEYWORD") {
                int w = KooRemapper::keywordCardDeckWidth(line);
                if (w > 0) sc.fieldWidth = w;
                fw = sc.fieldWidth;
                mode = Mode::TEXT;
                continue;
            }
            if (kw == "*NODE") { mode = Mode::NODE; continue; }
            if (kw == "*INCLUDE") { mode = Mode::INCLUDE; continue; }
            if (starts(kw, "*INCLUDE")) {
                sc.includeVariant.push_back(kw);
                mode = Mode::TEXT;                 // 변종 본문은 경로·변환값이라 정수로 읽지 않는다
                continue;
            }
            if (starts(kw, "*PARAMETER") || starts(kw, "*COMMENT") || kw == "*TITLE" ||
                kw == "*END") { mode = Mode::TEXT; continue; }
            if (starts(kw, "*SET_NODE")) {
                mode = Mode::SETNODE;
                setKind = classifySetNode(kw);
                setIncrement = has(kw, "_INCREMENT");
                setTitleN = titleLines(kw);
                setDataIdx = 0;
                setSid = 0;
                if (setKind == SetKind::OPAQUE) sc.opaqueSetKws.push_back(kw);
                continue;
            }
            if (starts(kw, "*ELEMENT")) {
                info = KooRemapper::parseElementKeyword(line);
                elemOpaque = (info.family == KooRemapper::ElemFamily::NONE || !info.supported);
                aux = elemOpaque ? KooRemapper::auxElementCard(line) : KooRemapper::AuxElementCard();
                auxRemaining = 0;
                mode = Mode::ELEM;
                continue;
            }
            mode = matchesKeepList(kw, o.keepKeywords) ? Mode::KEEP : Mode::OTHER;
            continue;
        }

        if (mode == Mode::TEXT) continue;

        if (mode == Mode::INCLUDE) {
            if (!isDataLine(line)) continue;
            std::string rel = trim(line);
            if (rel.empty()) continue;
            std::string full = joinPath(baseDir, rel);
            std::ifstream probe(full);
            if (probe.is_open()) {
                probe.close();
                sc.includeRead.push_back(full);
                if (depth < 8) {
                    // 인클루드가 선언한 칸 폭이 부모로 새지 않게 복원한다(그 파일 안에서만 유효).
                    const int savedFw = sc.fieldWidth;
                    scanRefs(full, false, o, pidNodes, sc, visited, depth + 1, paramRefLines);
                    sc.fieldWidth = savedFw;
                }
            } else {
                sc.includeMissing.push_back(full);
            }
            continue;
        }

        if (mode == Mode::ELEM) {
            // ⚠ 빈 줄도 카드 한 장으로 센다(셸 두께 Card 는 비워 둘 수 있으나 생략은 못 한다).
            //   건너뛰면 다음 요소의 Card 1 을 이 카드의 연결 줄로 삼켜 절점이 통째로 사라진다.
            const bool comment = (g != std::string::npos && line[g] == '$');
            if (comment) continue;
            if (g == std::string::npos && cardRemaining == 0) continue;   // 카드 밖의 빈 줄
            if (elemOpaque && aux.supported) {
                // ★보·질량·이산 족은 **칸 자리를 안다** — 추측하지 않는다.
                //   그래서 `*ELEMENT_BEAM` 의 RT1·RR1·LOCAL 이나 `*ELEMENT_SEATBELT` 의
                //   SBRID·SLEN 을 절점으로 세지 않는다(그것들을 절점으로 세면 엉뚱한 낮은
                //   번호 절점이 영구히 남는다).
                if (auxRemaining == 0) { auxLineIdx = 0; auxRemaining = aux.lines; }
                if (auxLineIdx == 0) {
                    auto f = cardFields(line, fw);
                    auto take = [&](int from, int cnt) {
                        if (from < 0) return;
                        for (int q = 0; q < cnt; ++q) {
                            int v = fieldInt(f, (size_t)(from + q));
                            if (v > 0) sc.byElement.push_back(v);
                        }
                    };
                    take(aux.nodeSkip, aux.nodeCount);
                    take(aux.nodeSkip2, aux.nodeCount2);
                }
                ++auxLineIdx;
                if (--auxRemaining <= 0) auxRemaining = 0;
                continue;
            }
            if (elemOpaque) {
                // 아직도 모르는 `*ELEMENT_*` 변형 — **칸 0(EID) 만** 빼고 전부 절점으로 본다.
                // (`*ELEMENT_MASS_NODE_SET` 처럼 칸 뜻이 갈리는 변형이 여기 온다.)
                std::vector<int> v;
                harvestInts(line, v);
                auto f = cardFields(line, fw);
                int eid = fieldInt(f, 0);
                for (int x : v) if (x != eid) sc.byElement.push_back(x);
                if (std::find(sc.elemOpaqueKws.begin(), sc.elemOpaqueKws.end(), kw) ==
                    sc.elemOpaqueKws.end())
                    sc.elemOpaqueKws.push_back(kw);
                continue;
            }
            if (cardRemaining == 0) {
                card1 = cardFields(line, fw);
                int pid = fieldInt(card1, 1);
                int pidN = 0;
                auto pit = pidNodes.find(pid);
                if (pit != pidNodes.end()) pidN = pit->second;
                span = KooRemapper::elementCardSpan(info, card1, pidN);
                cardLineIdx = 0;
                cardRemaining = span.lines;
            }
            if (cardLineIdx >= span.nodeFirst && cardLineIdx < span.nodeFirst + span.nodeLines) {
                const std::vector<std::string> f =
                    (cardLineIdx == 0) ? card1 : cardFields(line, fw);
                size_t from = (cardLineIdx == span.nodeFirst) ? (size_t)span.nodeFieldSkip : 0u;
                for (size_t q = from; q < f.size(); ++q) {
                    int v = fieldInt(f, q);
                    if (v > 0) sc.byElement.push_back(v);
                }
            }
            ++cardLineIdx;
            if (--cardRemaining <= 0) endElementCard();
            continue;
        }

        if (!isDataLine(line)) continue;

        if (mode == Mode::NODE) {
            int nid = 0;
            double xyz[3];
            if (!readNodeLine(line, fw, nid, xyz)) continue;
            sc.definedAll.push_back(nid);
            if (isMain) sc.definedMain.push_back(nid);
            sc.anyNode = true;
            for (int k = 0; k < 3; ++k) {
                if (xyz[k] < sc.bmin[k]) sc.bmin[k] = xyz[k];
                if (xyz[k] > sc.bmax[k]) sc.bmax[k] = xyz[k];
            }
            continue;
        }

        if (mode == Mode::SETNODE) {
            const int sfw = (fw >= 20) ? 20 : 10;      // 세트 카드는 I10(long 이면 I20)
            if (setDataIdx < setTitleN) { ++setDataIdx; continue; }
            if (setDataIdx == setTitleN) {
                setSid = fieldInt(cardFields(line, sfw), 0);
                ++setDataIdx;
                continue;
            }
            ++setDataIdx;
            auto f = cardFields(line, sfw);
            if (setKind == SetKind::LIST) {
                for (size_t q = 0; q < f.size(); ++q) {
                    int v = fieldInt(f, q);
                    if (v > 0 && setSid > 0) sc.setMembers[setSid].push_back(v);
                }
            } else if (setKind == SetKind::COLUMN) {
                int v = fieldInt(f, 0);
                if (v > 0 && setSid > 0) sc.setMembers[setSid].push_back(v);
            } else {
                // 못 읽는 변종 — **범위는 펼쳐서** 전부 남긴다. 끝점만 남기면 범위 안쪽
                // 절점이 지워지고 세트가 조용히 비어 LS-DYNA 가 다른 자리에서 죽는다.
                const size_t stepN = setIncrement ? 3u : 2u;
                bool pairsOk = true;
                for (size_t q = 0; q + 1 < f.size(); q += stepN) {
                    int b = fieldInt(f, q), e = fieldInt(f, q + 1);
                    if (b <= 0) continue;
                    if (e < b) { pairsOk = false; break; }
                    if ((long long)e - b > 50000000LL) { pairsOk = false; break; }
                    for (int v = b; v <= e; ++v) sc.opaqueSetInts.push_back(v);
                }
                if (!pairsOk || !has(kw, "_GENERATE")) harvestInts(line, sc.opaqueSetInts);
            }
            continue;
        }

        if (hasParameterRef(line)) ++paramRefLines;

        if (mode == Mode::KEEP) harvestInts(line, sc.keepInts[kw]);
        else                    harvestInts(line, sc.unknownInts[kw]);
    }
}

void scanRefs(const std::string& path, bool isMain, const Opts& o,
              const std::map<int, int>& pidNodes, Scan& sc,
              std::set<std::string>& visited, int depth, long long& paramRefLines) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    scanRefsStream(in, dirOf(path), isMain, o, pidNodes, sc, visited, depth, paramRefLines);
}

// ─────────────────────────────────────────────────────────────────────────────
// 판정 — 후보에서 '남길 이유' 를 하나씩 빼낸다
// ─────────────────────────────────────────────────────────────────────────────

struct KeptRow {
    std::string keyword;
    long long nodes = 0;
};

struct Resolution {
    std::vector<int> candidates;        // definedMain − 요소 참조
    std::vector<int> deletable;
    std::vector<KeptRow> keptByKeyword;         // keep 목록이 살린 것
    std::vector<KeptRow> keptByUnknown;         // 모르는 키워드가 살린 것
    long long keptByOpaqueSets = 0;
    long long forceDeletedDespiteUnknown = 0;
};

// `ints` 가 이름하는 것을 절점으로도, **절점 세트 ID 로도** 본다.
// CNRB 가 절점을 NSID 로 가리키므로 세트 전이가 없으면 요청서의 71건을 놓친다.
long long markKept(const std::vector<int>& ints, const std::vector<int>& cand,
                   const std::map<int, std::vector<int>>& setMembers, std::vector<char>& mark) {
    long long newly = 0;
    auto markOne = [&](int v) {
        auto it = std::lower_bound(cand.begin(), cand.end(), v);
        if (it == cand.end() || *it != v) return;
        size_t idx = (size_t)(it - cand.begin());
        if (!mark[idx]) { mark[idx] = 1; ++newly; }
    };
    for (int v : ints) {
        markOne(v);
        auto sit = setMembers.find(v);
        if (sit != setMembers.end())
            for (int m : sit->second) markOne(m);
    }
    return newly;
}

Resolution resolve(const Opts& o, Scan& sc) {
    Resolution r;
    sortUnique(sc.definedMain);
    sortUnique(sc.definedAll);
    sortUnique(sc.byElement);
    sortUnique(sc.opaqueSetInts);

    // 후보 = 주 덱이 정의했고 어떤 요소도 쓰지 않는 절점
    r.candidates.reserve(sc.definedMain.size());
    std::set_difference(sc.definedMain.begin(), sc.definedMain.end(),
                        sc.byElement.begin(), sc.byElement.end(),
                        std::back_inserter(r.candidates));

    std::vector<char> mark(r.candidates.size(), 0);

    // 1) keep 목록 — 추측이 아닌 것부터(귀속은 **먼저 걸린 키워드**가 가져간다)
    for (auto& kv : sc.keepInts) {
        sortUnique(kv.second);
        long long n = markKept(kv.second, r.candidates, sc.setMembers, mark);
        if (n > 0) r.keptByKeyword.push_back({kv.first, n});
    }
    // 2) 멤버를 못 읽는 세트 변종
    r.keptByOpaqueSets = markKept(sc.opaqueSetInts, r.candidates, sc.setMembers, mark);
    // 3) 모르는 키워드 — `force` 는 이것을 **존중하지 않는다**
    for (auto& kv : sc.unknownInts) {
        sortUnique(kv.second);
        if (o.mode == "force") {
            std::vector<char> probe(r.candidates.size(), 0);
            markKept(kv.second, r.candidates, sc.setMembers, probe);
            long long fresh = 0;
            for (size_t i = 0; i < probe.size(); ++i) if (probe[i] && !mark[i]) ++fresh;
            if (fresh > 0) {
                r.keptByUnknown.push_back({kv.first, fresh});
                r.forceDeletedDespiteUnknown += fresh;
            }
            continue;
        }
        long long n = markKept(kv.second, r.candidates, sc.setMembers, mark);
        if (n > 0) r.keptByUnknown.push_back({kv.first, n});
    }

    for (size_t i = 0; i < r.candidates.size(); ++i)
        if (!mark[i]) r.deletable.push_back(r.candidates[i]);
    return r;
}

// ─────────────────────────────────────────────────────────────────────────────
// bbox(후) — 삭제 뒤 남는 절점만
// ─────────────────────────────────────────────────────────────────────────────

struct Box {
    double mn[3] = {1e300, 1e300, 1e300};
    double mx[3] = {-1e300, -1e300, -1e300};
    bool any = false;
    void add(const double p[3]) {
        any = true;
        for (int k = 0; k < 3; ++k) { if (p[k] < mn[k]) mn[k] = p[k]; if (p[k] > mx[k]) mx[k] = p[k]; }
    }
};

void bboxAfterFile(const std::string& path, int deckFw, const std::vector<int>& del, Box& box,
                   std::set<std::string>& visited, int depth) {
    if (visited.count(path)) return;
    visited.insert(path);
    std::ifstream in(path);
    if (!in.is_open()) return;
    const std::string baseDir = dirOf(path);
    std::string line, kw;
    int fw = deckFw;
    bool node = false, incl = false;
    while (std::getline(in, line)) {
        size_t g = line.find_first_not_of(" \t\r\n");
        if (g != std::string::npos && line[g] == '*') {
            kw = kwBare(keywordToken(line));
            if (kw == "*KEYWORD") {
                int w = KooRemapper::keywordCardDeckWidth(line);
                if (w > 0) deckFw = w;
            }
            fw = KooRemapper::keywordFieldWidth(line, deckFw);
            node = (kw == "*NODE");
            incl = (kw == "*INCLUDE");
            continue;
        }
        if (!isDataLine(line)) continue;
        if (incl) {
            std::string rel = trim(line);
            if (!rel.empty() && depth < 8)
                bboxAfterFile(joinPath(baseDir, rel), deckFw, del, box, visited, depth + 1);
            continue;
        }
        if (!node) continue;
        int nid = 0;
        double xyz[3];
        if (!readNodeLine(line, fw, nid, xyz)) continue;
        if (inSorted(del, nid)) continue;
        box.add(xyz);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 덱 재작성 — 주 덱만 고친다(인클루드는 건드리지 않는다. 그래서 삭제 후보도 주 덱 정의뿐이다)
// ─────────────────────────────────────────────────────────────────────────────

struct PrunedSet {
    int sid = 0;
    long long removed = 0, kept = 0;
};

bool rewriteDeck(const Opts& o, const Scan& sc, const std::vector<int>& del,
                 const std::map<int, bool>& setDirty, ConsoleOutput& console,
                 long long& deletedNodeLines, std::vector<PrunedSet>& pruned,
                 long long& setsEmptied) {
    std::ifstream in(o.model);
    if (!in.is_open()) { console.error("Cannot reopen model: " + o.model); return false; }
    KooRemapper::DeckWriter w(o.output, KooRemapper::deck_newline::detect(o.model));
    if (!w.ok()) { console.error("Cannot open output: " + o.output); return false; }
    std::ostream& out = w.stream();

    int deckFw = sc.fieldWidth, fw = deckFw;
    std::string line, kw;
    bool inNode = false;
    // 세트 정리 상태
    bool inSet = false, setDirtyNow = false, setRepack = false, setFilter = false;
    int setSid = 0, setDataIdx = 0, setTitleN = 0, sfw = 10;
    std::vector<int> survivors;
    std::vector<std::string> setComments;
    PrunedSet cur;

    auto flushSet = [&]() {
        if (!inSet) return;
        inSet = false;
        if (!setDirtyNow) return;
        if (setFilter) {                       // COLUMN — 줄 단위로 이미 걸러 썼다
            if (cur.removed > 0) pruned.push_back(cur);
            if (cur.kept == 0) ++setsEmptied;
            return;
        }
        if (!setRepack) return;
        for (const auto& c : setComments) out << c << "\n";
        for (size_t i = 0; i < survivors.size(); ++i) {
            char buf[32];
            std::snprintf(buf, sizeof(buf), "%*d", sfw, survivors[i]);
            out << buf;
            if ((i + 1) % 8 == 0 || i + 1 == survivors.size()) out << "\n";
        }
        cur.kept = (long long)survivors.size();
        if (cur.removed > 0) pruned.push_back(cur);
        if (survivors.empty()) ++setsEmptied;
    };

    while (std::getline(in, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();   // DeckWriter 가 되붙인다
        size_t g = line.find_first_not_of(" \t");
        if (g != std::string::npos && line[g] == '*') {
            flushSet();
            kw = kwBare(keywordToken(line));
            if (kw == "*KEYWORD") {
                int wd = KooRemapper::keywordCardDeckWidth(line);
                if (wd > 0) deckFw = wd;
            }
            fw = KooRemapper::keywordFieldWidth(line, deckFw);
            inNode = (kw == "*NODE");
            if (starts(kw, "*SET_NODE")) {
                SetKind k = classifySetNode(kw);
                inSet = true;
                setRepack = (k == SetKind::LIST);
                setFilter = (k == SetKind::COLUMN);
                setTitleN = titleLines(kw);
                setDataIdx = 0;
                setSid = 0;
                setDirtyNow = false;
                survivors.clear();
                setComments.clear();
                cur = PrunedSet();
                sfw = (fw >= 20) ? 20 : 10;
            }
            out << line << "\n";
            continue;
        }

        if (inNode && isDataLine(line)) {
            int nid = 0;
            double xyz[3];
            if (readNodeLine(line, fw, nid, xyz) && inSorted(del, nid)) {
                ++deletedNodeLines;
                continue;                       // 이 절점 줄을 뺀다
            }
            out << line << "\n";
            continue;
        }

        if (inSet) {
            const bool data = isDataLine(line);
            if (!data) {
                if (setDirtyNow && setRepack) setComments.push_back(line);
                else out << line << "\n";
                continue;
            }
            if (setDataIdx < setTitleN) { ++setDataIdx; out << line << "\n"; continue; }
            if (setDataIdx == setTitleN) {
                setSid = fieldInt(cardFields(line, sfw), 0);
                auto it = setDirty.find(setSid);
                setDirtyNow = o.pruneSets && (setRepack || setFilter) &&
                              it != setDirty.end() && it->second;
                cur.sid = setSid;
                ++setDataIdx;
                out << line << "\n";
                continue;
            }
            ++setDataIdx;
            if (!setDirtyNow) { out << line << "\n"; continue; }
            if (setFilter) {
                int v = fieldInt(cardFields(line, sfw), 0);
                if (v > 0 && inSorted(del, v)) { ++cur.removed; continue; }
                ++cur.kept;
                out << line << "\n";
                continue;
            }
            auto f = cardFields(line, sfw);
            for (size_t q = 0; q < f.size(); ++q) {
                int v = fieldInt(f, q);
                if (v <= 0) continue;
                if (inSorted(del, v)) ++cur.removed;
                else survivors.push_back(v);
            }
            continue;
        }

        out << line << "\n";
    }
    flushSet();
    w.close();
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// 되읽기 검증 — 산출 덱이 **참조하는데 없는** 절점을 스스로 찍는다
// ─────────────────────────────────────────────────────────────────────────────
//
// 이것이 이 op 의 유일한 강한 증거다. 숫자를 세는 것은 전제 위에 있지만, 산출 덱을 다시 읽어
// '요소가 쓰는 절점이 전부 있다 · 세트 멤버가 전부 있다' 를 확인하는 것은 전제가 없다.

struct VerifyResult {
    long long undefByElement = 0;
    long long undefSetMembers = 0;
    int firstUndefined = 0;
};

VerifyResult verifyDeck(const std::string& path, const Opts& o) {
    VerifyResult vr;
    SectionMap sm;
    {
        std::set<std::string> vis;
        scanSections(path, 8, sm, vis, 0);
    }
    const std::map<int, int> pidNodes = buildPidNodes(sm);
    Scan sc;
    Opts probe = o;
    probe.model = path;
    long long paramRefs = 0;
    {
        std::set<std::string> vis;
        scanRefs(path, true, probe, pidNodes, sc, vis, 0, paramRefs);
    }
    sortUnique(sc.definedAll);
    sortUnique(sc.byElement);
    for (int v : sc.byElement)
        if (!inSorted(sc.definedAll, v)) {
            ++vr.undefByElement;
            if (!vr.firstUndefined) vr.firstUndefined = v;
        }
    for (const auto& kv : sc.setMembers)
        for (int v : kv.second)
            if (!inSorted(sc.definedAll, v)) {
                ++vr.undefSetMembers;
                if (!vr.firstUndefined) vr.firstUndefined = v;
            }
    return vr;
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

std::string num(double v) {
    std::ostringstream os;
    os << std::setprecision(10) << v;
    return os.str();
}

std::string boxJson(const Box& b) {
    if (!b.any) return "null";
    std::ostringstream os;
    os << "{\"min\": [" << num(b.mn[0]) << ", " << num(b.mn[1]) << ", " << num(b.mn[2])
       << "], \"max\": [" << num(b.mx[0]) << ", " << num(b.mx[1]) << ", " << num(b.mx[2])
       << "], \"size\": [" << num(b.mx[0] - b.mn[0]) << ", " << num(b.mx[1] - b.mn[1]) << ", "
       << num(b.mx[2] - b.mn[2]) << "]}";
    return os.str();
}

std::string boxLine(const Box& b) {
    if (!b.any) return "(절점 없음)";
    std::ostringstream os;
    os << std::setprecision(10)
       << "[" << b.mn[0] << ", " << b.mn[1] << ", " << b.mn[2] << "] .. ["
       << b.mx[0] << ", " << b.mx[1] << ", " << b.mx[2] << "]  size ["
       << (b.mx[0] - b.mn[0]) << ", " << (b.mx[1] - b.mn[1]) << ", " << (b.mx[2] - b.mn[2]) << "]";
    return os.str();
}

}  // namespace

// ─────────────────────────────────────────────────────────────────────────────
// runCleanupNodes
// ─────────────────────────────────────────────────────────────────────────────

int runCleanupNodes(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭 들여쓰기는 블록을 통째로 무너뜨려 조용히 아무 일도 안 한다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("cleanup-nodes", tabLine));
            return 1;
        }
    }
    std::ifstream yf(yamlFile);
    if (!yf.is_open()) { console.error("Cannot open config: " + yamlFile); return 1; }

    Opts o;
    bool keepGiven = false;
    bool inKeepList = false;
    std::string raw;
    while (std::getline(yf, raw)) {
        std::string l = KooRemapper::yamlStripComment(raw);
        std::string tr = trim(l);
        if (tr.empty()) continue;
        if (inKeepList && tr.substr(0, 2) == "- ") {
            o.keepKeywords.push_back(stripQuotes(trim(tr.substr(2))));
            continue;
        }
        inKeepList = false;
        size_t c = tr.find(':');
        if (c == std::string::npos) continue;
        std::string key = trim(tr.substr(0, c));
        std::string val = stripQuotes(trim(tr.substr(c + 1)));
        if (key == "model" || key == "input") o.model = val;
        else if (key == "output") o.output = val;
        else if (key == "report") o.reportPath = val;
        else if (key == "mode") o.mode = upper(val) == "SAFE" ? "safe"
                                       : upper(val) == "FORCE" ? "force" : "report";
        else if (key == "prune_sets") o.pruneSets = (upper(val) != "FALSE" && val != "0");
        else if (key == "verify") o.verify = (upper(val) != "FALSE" && val != "0");
        else if (key == "keep_referenced_by") {
            keepGiven = true;
            if (!val.empty() && val[0] == '[') {
                std::string inner = val.substr(1);
                size_t rb = inner.rfind(']');
                if (rb != std::string::npos) inner = inner.substr(0, rb);
                std::istringstream ss(inner);
                std::string tok;
                while (std::getline(ss, tok, ',')) {
                    tok = stripQuotes(trim(tok));
                    if (!tok.empty()) o.keepKeywords.push_back(tok);
                }
            } else {
                inKeepList = true;
            }
        }
    }
    yf.close();

    const std::string cfgDir = dirOf(yamlFile);
    auto rp = [&](const std::string& p) { return p.empty() ? p : KooRemapper::yamlResolvePath(cfgDir, p); };
    o.model = rp(o.model);
    o.output = rp(o.output);
    o.reportPath = rp(o.reportPath);

    if (o.model.empty()) { console.error("'model' is required in YAML config"); return 1; }
    { std::ifstream probe(o.model);
      if (!probe.is_open()) { console.error("Cannot open model: " + o.model); return 1; } }
    if (!keepGiven || o.keepKeywords.empty()) {
        o.keepKeywords.clear();
        for (const char* k : kDefaultKeep) o.keepKeywords.push_back(k);
    }
    if (o.mode != "report" && o.output.empty()) {
        size_t dot = o.model.rfind('.');
        o.output = (dot == std::string::npos) ? o.model + "_clean"
                                              : o.model.substr(0, dot) + "_clean" + o.model.substr(dot);
    }

    console.info("cleanup-nodes: " + o.model);
    console.info("  mode: " + o.mode + (o.mode == "report" ? "  (덱을 쓰지 않는다)" : ""));

    // ── 패스 0·1 ─────────────────────────────────────────────────────────────
    SectionMap sm;
    { std::set<std::string> vis; scanSections(o.model, 8, sm, vis, 0); }
    const std::map<int, int> pidNodes = buildPidNodes(sm);

    Scan sc;
    long long paramRefLines = 0;
    { std::set<std::string> vis; scanRefs(o.model, true, o, pidNodes, sc, vis, 0, paramRefLines); }

    if (!sc.anyNode) { console.error("No *NODE definitions found in: " + o.model); return 1; }

    Resolution res = resolve(o, sc);

    Box before;
    if (sc.anyNode) { before.any = true;
        for (int k = 0; k < 3; ++k) { before.mn[k] = sc.bmin[k]; before.mx[k] = sc.bmax[k]; } }

    // ── 인클루드 판정 ────────────────────────────────────────────────────────
    std::vector<std::string> warnings;
    const bool includeProblem = !sc.includeMissing.empty() || !sc.includeVariant.empty();
    if (!sc.includeRead.empty())
        console.info("  *INCLUDE read: " + std::to_string(sc.includeRead.size()) +
                     " (참조를 함께 세었다 — 안 읽으면 인클루드가 쓰는 절점을 고아로 본다)");
    for (const auto& m : sc.includeMissing)
        warnings.push_back("*INCLUDE 를 열 수 없다: " + m);
    for (const auto& v : sc.includeVariant)
        warnings.push_back(v + " 는 본문을 읽지 않았다 — 그 안의 절점 참조를 모른다");
    if (paramRefLines > 0)
        warnings.push_back("*PARAMETER 참조(&)가 있는 줄 " + std::to_string(paramRefLines) +
                           " — 기호로 적힌 절점 ID 는 읽을 수 없다");

    // ── bbox(후) ─────────────────────────────────────────────────────────────
    Box after;
    { std::set<std::string> vis; bboxAfterFile(o.model, sc.fieldWidth, res.deletable, after, vis, 0); }

    // ── 보고 ─────────────────────────────────────────────────────────────────
    console.info("  nodes defined (main deck): " + std::to_string(sc.definedMain.size()));
    if (sc.definedAll.size() != sc.definedMain.size())
        console.info("  nodes defined (incl. *INCLUDE): " + std::to_string(sc.definedAll.size()) +
                     "  — 인클루드 정의는 지우지 않는다");
    console.info("  used by elements:          " + std::to_string(sc.byElement.size()));
    console.info("  unreferenced candidates:   " + std::to_string(res.candidates.size()));
    for (const auto& r : res.keptByKeyword)
        console.info("    kept by " + r.keyword + ": " + std::to_string(r.nodes));
    if (res.keptByOpaqueSets > 0)
        console.info("    kept by unreadable *SET_NODE_* variants: " +
                     std::to_string(res.keptByOpaqueSets));
    for (const auto& r : res.keptByUnknown)
        console.info("    " + std::string(o.mode == "force" ? "FORCE-DELETED despite " : "kept by ") +
                     r.keyword + ": " + std::to_string(r.nodes));
    console.info("  deletable:                 " + std::to_string(res.deletable.size()));
    console.info("  bbox before: " + boxLine(before));
    console.info("  bbox after:  " + boxLine(after));
    if (before.any && after.any) {
        double worst = 0.0;
        int worstAxis = -1;
        for (int k = 0; k < 3; ++k) {
            double d = std::max(std::fabs(after.mn[k] - before.mn[k]),
                                std::fabs(after.mx[k] - before.mx[k]));
            if (d > worst) { worst = d; worstAxis = k; }
        }
        if (worstAxis >= 0 && worst > 0.0) {
            const char* ax = (worstAxis == 0) ? "x" : (worstAxis == 1) ? "y" : "z";
            console.info(std::string("  ★bbox 가 ") + ax + " 축에서 " + num(worst) +
                         " 줄어든다 — 고아 절점이 모델 범위를 그만큼 넓히고 있었다"
                         " (낙하판·접촉면을 이 bbox 로 놓았다면 그만큼 어긋나 있다)");
        }
    }
    for (const auto& w : warnings) console.warning(w);
    for (const auto& k : sc.elemOpaqueKws)
        console.warning(k + " 는 카드 줄 수를 모른다 — 그 블록의 정수를 모두 절점으로 보고 남겼다");

    // ── 쓰기 ─────────────────────────────────────────────────────────────────
    long long deletedNodeLines = 0, setsEmptied = 0;
    std::vector<PrunedSet> pruned;
    VerifyResult vr;
    bool wrote = false;

    if (o.mode == "safe" && includeProblem) {
        console.error("mode: safe — 읽지 못한 *INCLUDE 가 있어 덱을 쓰지 않는다. "
                      "그 안의 절점 참조를 모르는 채로 지우면 조용히 깨진다. "
                      "평탄화한 덱으로 돌리거나 mode: force 로 책임을 지고 돌려라.");
        return 1;
    }
    if (o.mode != "report") {
        std::map<int, bool> setDirty;
        for (const auto& kv : sc.setMembers) {
            bool dirty = false;
            for (int v : kv.second) if (inSorted(res.deletable, v)) { dirty = true; break; }
            setDirty[kv.first] = dirty;
        }
        if (!rewriteDeck(o, sc, res.deletable, setDirty, console,
                         deletedNodeLines, pruned, setsEmptied))
            return 1;
        wrote = true;
        console.success("wrote: " + o.output + "  (*NODE 줄 " + std::to_string(deletedNodeLines) +
                        " 삭제, *SET_NODE 정리 " + std::to_string(pruned.size()) + " 건)");
        if (setsEmptied > 0)
            console.warning("정리 후 멤버가 0 이 된 *SET_NODE 가 " + std::to_string(setsEmptied) +
                            " 개다 — 그 세트를 가리키는 카드가 있으면 LS-DYNA 가 거기서 죽는다");
        if (o.verify) {
            vr = verifyDeck(o.output, o);
            if (vr.undefByElement == 0 && vr.undefSetMembers == 0)
                console.success("verify: 산출 덱에 '참조하는데 없는 절점' 0 (요소·세트 멤버 전수)");
            else
                console.error("verify: 요소 참조 미정의 " + std::to_string(vr.undefByElement) +
                              " · 세트 멤버 미정의 " + std::to_string(vr.undefSetMembers) +
                              " (첫 건 NID " + std::to_string(vr.firstUndefined) + ")");
        }
    }

    // ── 리포트 JSON ──────────────────────────────────────────────────────────
    if (!o.reportPath.empty()) {
        std::ofstream jf(o.reportPath);
        if (!jf.is_open()) {
            console.error("Cannot write report: " + o.reportPath);
            return 1;
        }
        jf << "{\n";
        jf << "  \"op\": \"cleanup-nodes\",\n";
        jf << "  \"model\": " << jsonStr(o.model) << ",\n";
        jf << "  \"output\": " << (wrote ? jsonStr(o.output) : std::string("null")) << ",\n";
        jf << "  \"mode\": " << jsonStr(o.mode) << ",\n";
        jf << "  \"prune_sets\": " << (o.pruneSets ? "true" : "false") << ",\n";
        jf << "  \"deck\": {\"field_width\": " << sc.fieldWidth
           << ", \"includes_read\": " << sc.includeRead.size()
           << ", \"includes_unreadable\": " << sc.includeMissing.size()
           << ", \"include_variants_unread\": " << sc.includeVariant.size() << "},\n";
        jf << "  \"nodes\": {\n";
        jf << "    \"defined_main\": " << sc.definedMain.size() << ",\n";
        jf << "    \"defined_all\": " << sc.definedAll.size() << ",\n";
        jf << "    \"used_by_elements\": " << sc.byElement.size() << ",\n";
        jf << "    \"unreferenced_candidates\": " << res.candidates.size() << ",\n";
        jf << "    \"deletable\": " << res.deletable.size() << ",\n";
        jf << "    \"deleted\": " << deletedNodeLines << "\n";
        jf << "  },\n";
        jf << "  \"kept_by\": {";
        {
            bool first = true;
            for (const auto& r : res.keptByKeyword) {
                jf << (first ? "" : ", ") << jsonStr(r.keyword) << ": " << r.nodes;
                first = false;
            }
            if (res.keptByOpaqueSets > 0)
                jf << (first ? "" : ", ") << "\"(unreadable *SET_NODE_* variants)\": "
                   << res.keptByOpaqueSets;
        }
        jf << "},\n";
        jf << "  \"unknown_keyword_kept\": [";
        for (size_t i = 0; i < res.keptByUnknown.size(); ++i)
            jf << (i ? ", " : "") << "{\"keyword\": " << jsonStr(res.keptByUnknown[i].keyword)
               << ", \"nodes\": " << res.keptByUnknown[i].nodes << "}";
        jf << "],\n";
        jf << "  \"force_deleted_despite_unknown\": " << res.forceDeletedDespiteUnknown << ",\n";
        jf << "  \"element_keywords_opaque\": [";
        for (size_t i = 0; i < sc.elemOpaqueKws.size(); ++i)
            jf << (i ? ", " : "") << jsonStr(sc.elemOpaqueKws[i]);
        jf << "],\n";
        jf << "  \"bbox_before\": " << boxJson(before) << ",\n";
        jf << "  \"bbox_after\": " << boxJson(after) << ",\n";
        jf << "  \"sets_pruned\": [";
        for (size_t i = 0; i < pruned.size(); ++i)
            jf << (i ? ", " : "") << "{\"sid\": " << pruned[i].sid
               << ", \"removed\": " << pruned[i].removed
               << ", \"kept\": " << pruned[i].kept << "}";
        jf << "],\n";
        jf << "  \"sets_emptied\": " << setsEmptied << ",\n";
        jf << "  \"verify\": "
           << (wrote && o.verify
                   ? "{\"undefined_by_elements\": " + std::to_string(vr.undefByElement) +
                     ", \"undefined_set_members\": " + std::to_string(vr.undefSetMembers) + "}"
                   : "null")
           << ",\n";
        jf << "  \"warnings\": [";
        for (size_t i = 0; i < warnings.size(); ++i)
            jf << (i ? ", " : "") << jsonStr(warnings[i]);
        jf << "]\n}\n";
        jf.close();
        console.info("report: " + o.reportPath);
    }

    if (wrote && o.verify && (vr.undefByElement > 0 || vr.undefSetMembers > 0)) return 1;
    return 0;
}
