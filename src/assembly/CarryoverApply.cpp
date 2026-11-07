// StepForge 이월 계획을 이 덱에 적용한다 — 사전 검사(전부 아니면 전무) · 처리마다 편집 상태 · 쓴 덱 되읽기 대조 · 품질 관문
#include "assembly/ModelAssembler.h"

#include "commands/contact_helpers.h"
#include "core/Mesh.h"
#include "parser/CardCut.h"
#include "parser/CardFields.h"
#include "parser/CarryoverPlan.h"
#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"
#include "parser/IdRefs.h"
#include "parser/IncludeClosure.h"
#include "parser/KFileReader.h"
#include "parser/NodeRefs.h"
#include "util/Sha256.h"
#include "util/Validator.h"
#include "validation/ElementQualityChecker.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

// 왜 이 op 이 있나 (2026-11-07). StepForge 가 CAD 개정을 해석 덱으로 이월하는 재료(계획 · 변위장 · 조각)를 내고
// (`REQUEST-2026-11-06-carryover.md`), 덱을 고치는 일은 우리 몫이다(경계 합의 §1). 처리 꼴은 답신
// (`docs/requests/stepforge-carryover-reply-2026-11-07.md` Q1~Q8)과 사용자 결정(11-07)이 정했다.
//
// 지키는 것.
//   · **사전 검사는 전부 아니면 전무** — 걸린 것을 전부 모아 한 번에 거절하고 덱을 쓰지 않는다(덱이 반쯤 고쳐진 채 남지 않게)
//   · 계획은 **그 덱의 것**이어야 한다(deck.sha256) · 동반 파일은 지문(sha256 · 바이트)으로 대조한다. 조각(.k)만은 바이트가
//     달라도(개행 · 공백) **값 대조**가 지나면 받고 경고한다
//   · 나눠 쓰는 절점(보 · 이산 · 질량 · 안전띠 · 플롯 요소 포함)이 있는 PID 는 옮기지도 바꾸지도 지우지도 않는다(결정)
//   · 바꿔 넣거나 지우는 PID 를 절점 · 세그먼트 · 요소로 가리키는 세트 · 접촉이 있으면 거절한다(결정 — PID 로 건 참조는
//     바꿔 넣기에서 살고 지우기는 막는다). 정본(`NodeRefs` · `IdRefs`)이 칸 뜻을 단정하지 못한 자리, 정본이 보지도 세지도 않고
//     참조 없는 키워드 표(`refCover`)에도 없는 키워드, 풀 수 없는 방언 세트가 덱에 있으면 그것도 거절한다 — 그 PID 를 가리키지
//     않는다고 증명할 수 없다(리뷰 11-07)
//   · 절점 칸을 다 읽지 못하는 요소 블록(리더가 담지 않는 솔리드 · 티쉘 변형 · 셸 `_DOF` · 칸 자리를 모르는 변형 …)이나 EID 가 겹친 덱은
//     덱을 고치는 줄을 하나도 적용하지 않는다(리뷰 11-07)
//   · 조각 번호는 덱 바닥(`idMaxima` — 보 · 이산 · 질량 요소까지) 위여야 한다. 아래에 걸치면 조각 전부를 **한 이동량**으로 옮긴다
//   · 쓴 뒤 **다시 읽어** 대조하고 품질 관문(새로 뒤집힌 솔리드 · 모프가 법선을 뒤집은 셸)을 건다 — 걸리면 부르는 쪽이 산출을 지운다
//
// 판 2(2026-11-07 — StepForge 요청서 §10 · 사용자 결정 둘).
//   · 인클루드가 있는 덱 — `deck.includes` 가 우리 닫힘(`include_closure::read` — §10.3 ① 과 같은 규칙)과 **글자 그대로** 같아야 받는다.
//     사전 검사는 닫힘 전체를 **읽기만** 하고(참조 · 나눠 쓴 절점 · 세트 · 접촉 · 번호 바닥 · SECID) **주 덱만 고친다** — 고칠 자리
//     (바꿀 PID 의 요소 · 그 절점 · `*PART` · 새 섹션이 옮길 옛 섹션 카드)가 인클루드 파일에 있으면 거절하고 목록을 낸다(「주 덱만 고침 ·
//     인클루드면 거절」). 산출은 `*INCLUDE` 줄을 그대로 두고 덱과 같은 폴더에 써야 한다 — 그래야 같은 파일을 가리킨다
//   · 줄마다 실린 덱 자리(그쪽 `KDeck.part_ranges()` · `*PART`)를 우리 셈과 견준다 — 손대는 줄은 거절, keep · review 는 경고
//     (「손대는 줄은 거절 · keep/review 는 경고」)
//   · 셸 두께가 바뀐 모프의 새 섹션(`section_<PID>.k`) — 옛 카드를 그대로 옮겨 SECID · T1~T4 만 바꾼 카드인지 줄마다 견주고,
//     넣은 뒤 그 PID 의 `*PART` SECID 만 잇는다(답신 Q8)

namespace KooRemapper {
namespace {

using carryover::Action;
using carryover::Problem;

bool readBytes(const std::string& path, std::string& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    out = ss.str();
    return true;
}

std::vector<std::string> splitLines(const std::string& text) {
    std::vector<std::string> lines;
    std::string cur;
    for (char c : text) {
        if (c != '\n') { cur += c; continue; }
        if (!cur.empty() && cur.back() == '\r') cur.pop_back();
        lines.push_back(cur);
        cur.clear();
    }
    if (!cur.empty()) {
        if (cur.back() == '\r') cur.pop_back();
        lines.push_back(cur);
    }
    return lines;
}

bool geometryAction(Action a) {
    return a == Action::Transform || a == Action::Morph || a == Action::Remesh || a == Action::Delete;
}

// 번호 목록을 사람이 읽게 — 앞 몇 개와 총수(보고 문장이 수천 개 번호로 덮이지 않게)
template <class C>
std::string idList(const C& c, size_t cap = 20) {
    std::string s;
    size_t k = 0;
    for (const auto& v : c) {
        if (k == cap) { s += " …"; break; }
        s += (k++ ? ", " : "") + std::to_string(v);
    }
    if (c.size() > cap) s += "(총 " + std::to_string(c.size()) + " 개)";
    return s;
}

std::string join(const std::set<std::string>& v) {
    std::string s;
    for (const auto& x : v) s += (s.empty() ? "" : ", ") + x;
    return s;
}

std::string num(double v) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.6g", v);
    return buf;
}

// 맨 `*PART`(· `_TITLE`) 의 제목 · 카드 짝. 빈 줄도 카드다(제목은 비워 둘 수 있다) — `extract_parts` indexDeck 과 같은 규칙.
struct PartLoc {
    size_t kwLine = 0, blockEnd = 0;        // 블록 [kwLine, blockEnd)
    size_t titleLine = 0, cardLine = 0;
    size_t pairs = 0;                       // 그 블록의 짝 수
    long long secid = 0, mid = 0;
    bool fixedCard = true;                  // 카드가 고정폭이다(SECID 칸을 제자리에서 고칠 수 있다)
    int fieldW = 10;                        // 그 블록의 칸 폭 — 표준 · i10 은 10, long(덱 · 키워드 `+`)은 20
};
struct PartIndex {
    std::map<long long, PartLoc> plain;
    std::set<long long> duplicate;
    std::vector<size_t> oddBlocks;          // 데이터 줄이 짝으로 안 떨어지는 블록의 키워드 줄
};

PartIndex indexParts(const std::vector<std::string>& L) {
    PartIndex idx;
    const auto blocks = cardcut::blocks(L);
    const int deckFw = deckFieldWidth(L);
    for (size_t b = 0; b < blocks.size(); ++b) {
        const auto& blk = blocks[b];
        if (blk.kw != "*PART" && blk.kw != "*PART_TITLE") continue;
        const size_t end = (b + 1 < blocks.size()) ? blocks[b + 1].kwLine : L.size();
        if (blk.data.size() % 2 != 0) idx.oddBlocks.push_back(blk.kwLine);
        // `*PART` 칸은 표준 · i10 에서 10, long 에서 20 이다(i10 은 8칸만 넓힌다 — Vol_I 19353) — SECID 를 제자리에서 고칠 칸 폭
        const int w = keywordFieldWidth(L[blk.kwLine], deckFw) == 20 ? 20 : 10;
        for (size_t k = 0; k + 1 < blk.data.size(); k += 2) {
            const std::string& card = L[blk.data[k + 1]];
            const auto c = cardcut::cut(card, w);
            int pid = 0, sec = 0, mid = 0;
            if (c.f.empty() || !cards::toInt(c.f[0], pid) || pid <= 0) continue;
            if (c.f.size() > 1) cards::toInt(c.f[1], sec);
            if (c.f.size() > 2) cards::toInt(c.f[2], mid);
            PartLoc loc;
            loc.kwLine = blk.kwLine;
            loc.blockEnd = end;
            loc.titleLine = blk.data[k];
            loc.cardLine = blk.data[k + 1];
            loc.pairs = blk.data.size() / 2;
            loc.secid = sec;
            loc.mid = mid;
            loc.fixedCard = c.fixed && card.find(',') == std::string::npos;
            loc.fieldW = w;
            if (!idx.plain.emplace(pid, loc).second) idx.duplicate.insert(pid);
        }
    }
    return idx;
}

// 정규화한 키워드(`*ELEMENT_BEAM_WARPAGE_TITLE`)의 옵션 토큰에 `opt` 가 있나
bool hasOption(const std::string& kw, const std::string& base, const char* opt) {
    if (kw.rfind(base, 0) != 0) return false;
    std::istringstream rest(kw.substr(base.size()));
    for (std::string t; std::getline(rest, t, '_');)
        if (t == opt) return true;
    return false;
}

// ★이 `*ELEMENT_*` 블록의 절점 칸을 이월 적용이 **전부** 읽는가(리뷰 11-07 — 리더가 담지 않는 솔리드 변형을 아무도 보지 않아
// 지운 절점을 가리키는 카드 · 겹친 EID 가 rc 0 으로 나갔다). 읽으면 빈 글자, 아니면 까닭. 읽는 것은 둘뿐이다 —
//   · 리더가 메시에 그대로 담는 격자 블록(셸 `_DOF` 는 빼고 — Card 5 의 NS1-NS4 스칼라 절점은 아무도 읽지 않는다, Vol_I 162243-162261)
//   · 칸 자리를 아는 격자 밖 블록(`auxElementCard`) — 보의 옵션 카드 절점(`_WARPAGE` Card 9 의 SN1 · SN2 · `_ELBOW` Card 10 의 MN)도
//     공용 걸음(`forEachNonGridElementCard`)이 읽어 카드의 절점에 싣는다(92f50fe · 6341aac — 11-07 밤에 그 두 거절을 뺐다 · Vol_I
//     156529-156638). Card 1 의 N3(방향 절점)은 읽는다
std::string elementBlockGap(const std::string& line) {
    const ElementKeywordInfo info = parseElementKeyword(line);
    if (info.family != ElemFamily::NONE) {
        if (!gridReaderReadsKeyword(line)) return info.supported ? "리더가 메시에 담지 않는 변형" : "카드 줄 수를 확정할 수 없는 변형";
        if (info.family == ElemFamily::SHELL && hasOption(info.keyword, "*ELEMENT_SHELL", "DOF"))
            return "DOF 카드의 스칼라 절점(NS1-NS4)을 읽지 않는다";
        return std::string();
    }
    // `*ELEMENT_MASS_PART(_SET)` 은 파트(세트)에 질량을 나눠 얹는 카드다 — 칸은 ID ADDMASS FINMASS LCID MWD 뿐, 절점 칸이 없다(Vol_I 160154)
    if (hasOption(info.keyword, "*ELEMENT_MASS", "PART")) return std::string();
    const AuxElementCard a = auxElementCard(line);
    if (a.family == AuxFamily::NONE) return "칸 자리를 모르는 요소 키워드";
    if (!a.supported) return "칸 자리를 확정할 수 없는 변형";
    return std::string();
}

// ★리더가 메시에 담는 격자 블록 가운데 TITLE 옵션이 붙은 것(`*ELEMENT_SOLID_TITLE` · `*ELEMENT_SHELL_TITLE`(셸 변형 포함) ·
// `*ELEMENT_TSHELL_TITLE`) — StepForge 권고(그쪽 591d5b5 · D-681, 사용자 결정 11-07 밤). TITLE 은 이 키워드들의 설명서 옵션이 아니어서
// 블록 첫 줄이 제목 카드인지 LS-DYNA 가 어떻게 읽는지 근거가 없다. 우리 리더도 짐작한다(11-07 밤 실측) — 솔리드 · 티쉘은 제목 카드가
// 없다고 읽어 글자 제목은 칸이 안 읽혀 버려질 뿐이고 숫자꼴 제목(「10 20」)은 두 줄 카드 머리가 되어 다음 요소 카드를 절점 줄로 삼킨다
// (EID 10 · PID 20 이 생기고 요소 1 이 사라졌다). 셸은 첫 줄의 첫 토큰이 정수가 아닐 때만 제목으로 버려 숫자꼴 제목이 요소 하나가 된다.
bool gridTitleBlock(const std::string& line) {
    if (!gridReaderReadsKeyword(line)) return false;
    const ElementKeywordInfo info = parseElementKeyword(line);
    if (info.family == ElemFamily::NONE || info.keyword.size() <= 9) return false;
    std::istringstream rest(info.keyword.substr(9));   // `*ELEMENT_` 뒤의 토큰
    for (std::string t; std::getline(rest, t, '_');)
        if (t == "TITLE") return true;
    return false;
}

// 리더가 담는 격자 요소 카드를 카드마다 한 번 — Card 1 줄과 그 칸. 카드 경계는 정본(`elementCardSpan`)이 정하고, 2차 솔리드의 절점
// 수는 리더가 담은 PID → ELFORM(`Mesh::partSolidElform`)에서 온다. 주석은 건너뛰고 빈 줄은 카드 안에서만 카드다.
struct GridCard {
    size_t line = 0;
    ElemFamily family = ElemFamily::NONE;
    const std::string* keyword = nullptr;
    std::vector<std::string> f;
    int fw = 8;                     // 그 블록의 정수 칸 폭(키워드 접미사까지)
    bool thicknessCard = false;     // 셸 THICKNESS · BETA · MCID — Card 2(중간절점이면 Card 3 도)가 두께다
};
void forEachGridCard(const std::vector<std::string>& L, const Mesh& m, const std::function<void(const GridCard&)>& fn) {
    const int deckFw = deckFieldWidth(L);
    ElementKeywordInfo info;
    bool in = false;
    int fw = deckFw, remaining = 0;
    GridCard c;
    for (size_t i = 0; i < L.size(); ++i) {
        const std::string& l = L[i];
        const size_t g = l.find_first_not_of(" \t");
        if (g != std::string::npos && l[g] == '*') {
            in = gridReaderReadsKeyword(l);
            if (in) info = parseElementKeyword(l);
            fw = keywordFieldWidth(l, deckFw);
            remaining = 0;
            continue;
        }
        if (!in) continue;
        if (g != std::string::npos && l[g] == '$') continue;
        if (g == std::string::npos && remaining == 0) continue;
        if (remaining == 0) {
            c.line = i;
            c.family = info.family;
            c.keyword = &info.keyword;
            c.f = deckscan::cardFields(l, fw);
            c.fw = fw;
            c.thicknessCard = info.thicknessCard;
            int pidN = 0;
            if (info.family == ElemFamily::SOLID)
                if (auto it = m.partSolidElform.find(deckscan::fieldInt(c.f, 1)); it != m.partSolidElform.end())
                    pidN = solidNodesFromElform(it->second);
            remaining = elementCardSpan(info, c.f, pidN).lines;
            fn(c);
        }
        --remaining;
    }
}

// 8절점 셸의 중간절점(N5-N8) — 리더(`KFileReader`)는 셸 코너 넷만 담는다. 옮기면 중간절점도 옮겨야 하고, 나눠 쓴 절점을 셀 때도
// 세야 한다. EID → 중간절점.
std::unordered_map<int, std::vector<int>> shellMidsideNodes(const std::vector<std::string>& L, const Mesh& m) {
    std::unordered_map<int, std::vector<int>> out;
    forEachGridCard(L, m, [&](const GridCard& c) {
        if (c.family != ElemFamily::SHELL) return;
        std::vector<int> mid;
        for (size_t q = 6; q < 10; ++q) {
            const int v = deckscan::fieldInt(c.f, q);
            if (v > 0) mid.push_back(v);
        }
        if (!mid.empty()) out[deckscan::fieldInt(c.f, 0)] = mid;
    });
    return out;
}

// 계획이 준 글자를 덱 줄에 넣을 때 — 줄을 끊거나 이을 수 있는 제어 문자(CR · LF · 그 밖)를 빈칸으로(리뷰 11-07 — 이름의 개행이 살아 있는
// `*BOUNDARY_SPC_NODE` 카드를 심었다)
std::string oneLine(const std::string& s) {
    std::string out = s;
    for (char& c : out) {
        const unsigned char u = static_cast<unsigned char>(c);
        if (u < 0x20 || u == 0x7F) c = ' ';
    }
    return out;
}

// ★바꿔 넣기 · 지우기의 참조 덮음 — 이 키워드(대문자 · 칸폭 접미사 뗌)가 고치는 PID 의 절점 · 요소 · 파트를 가리키지 않는다고
// **증명할 수 있나**(리뷰 11-07 — 정본 밖 키워드 열 가지가 지운 절점 · 요소 · 파트를 가리킨 채 rc 0 으로 나갔다).
//   Free      — 매뉴얼(Vol_I · Vol_II) 칸에 절점 · 요소 · 파트 ID 가 없다. 세트 ID 는 된다(세트 멤버는 정본 · 세트 해석기가 본다)
//   Scanned   — 정본(NodeRefs · IdRefs · 접촉 면 풀기)이 그 칸을 읽거나, 못 읽으면 notChecked 로 센다(`not_checked` 가 거절한다)
//   PartOnly  — 절점 · 요소 칸은 없거나 정본이 읽지만 **파트 ID 칸**을 아무도 읽지 않는다 — 지우기만 막는다(PID 참조는 바꿔 넣기에서 산다)
//   Unscanned — 그 밖 전부. 모르면 Free 가 아니다
// `*SET_*` 는 세트 표(`ct_parseSets`)가 · `*ELEMENT_*` 는 요소 블록 판정(`elementBlockGap`)이 · `*INCLUDE` 는 앞 검사가 다룬다.
// 표의 근거(매뉴얼 칸)는 계획 노트 `stepforge-carryover-apply.plan.md` 「참조 덮음 표」.
enum class Cover { Free, Scanned, PartOnly, Unscanned };
Cover refCover(const std::string& kw) {
    using cards::has;
    using cards::starts;
    const std::string base = kw.size() > 6 && kw.compare(kw.size() - 6, 6, "_TITLE") == 0 ? kw.substr(0, kw.size() - 6) : kw;
    auto oneOf = [](const std::string& k, std::initializer_list<const char*> names) {
        return std::any_of(names.begin(), names.end(), [&](const char* n) { return k == n; });
    };
    // ── 정본이 읽거나 세는 갈래 — NodeRefs(한 칸 카드 · 이력 · CNRB · 좌표계 절점 · 세는 갈래) · IdRefs(접촉 · 강체 묶음 · 감쇠 ·
    //    초기응력 · 세는 갈래). `*LOAD_NODE_POINT` 의 M1-M3 는 부르는 쪽이 따로 본다
    if (starts(kw, "*BOUNDARY_SPC_NODE") || starts(kw, "*INITIAL_VELOCITY_NODE") || starts(kw, "*BOUNDARY_PRESCRIBED_MOTION_NODE") ||
        starts(kw, "*LOAD_NODE_POINT") || kw == "*CONSTRAINED_NODAL_RIGID_BODY" || kw == "*DEFINE_COORDINATE_NODES" ||
        starts(kw, "*CONSTRAINED_JOINT_") || starts(kw, "*CONSTRAINED_SPOTWELD") || kw == "*CONSTRAINED_RIGID_BODIES" ||
        starts(kw, "*DAMPING_PART_MASS") || starts(kw, "*DAMPING_PART_STIFFNESS") || starts(kw, "*INITIAL_STRESS_SOLID") ||
        starts(kw, "*INITIAL_STRESS_SHELL") || starts(kw, "*PART_MOVE") || starts(kw, "*BOUNDARY_PRESCRIBED_MOTION_RIGID") ||
        starts(kw, "*INITIAL_VELOCITY_GENERATION") || starts(kw, "*MAT_ADD_THERMAL_EXPANSION") || starts(kw, "*DEFORMABLE_TO_RIGID") ||
        starts(kw, "*INITIAL_STRAIN_SOLID") || starts(kw, "*INITIAL_STRAIN_SHELL"))
        return Cover::Scanned;
    if (starts(kw, "*DATABASE_HISTORY_")) {
        if (kw.size() > 4 && kw.compare(kw.size() - 4, 4, "_SET") == 0) return Cover::Free;   // 세트 ID 다
        for (const char* t : {"*DATABASE_HISTORY_NODE", "*DATABASE_HISTORY_SOLID", "*DATABASE_HISTORY_SHELL", "*DATABASE_HISTORY_BEAM",
                              "*DATABASE_HISTORY_TSHELL"})
            if (starts(kw, t)) return Cover::Scanned;   // 맨 키워드는 읽고 `_ID` · `_LOCAL` 은 센다
        return Cover::Unscanned;
    }
    if (starts(kw, "*CONTACT_")) {
        // 카드 1 이 SURFA SURFB SURFATYP SURFBTYP 꼴이 아닌 접촉 — 정본은 같은 자리로 읽어 뜻을 틀린다(Vol_I 접촉 장의 따로 선 키워드)
        for (const char* t : {"*CONTACT_ENTITY", "*CONTACT_GEBOD", "*CONTACT_1D", "*CONTACT_2D", "*CONTACT_RIGID_SURFACE",
                              "*CONTACT_AUTO_MOVE", "*CONTACT_COUPLING", "*CONTACT_ADD_WEAR", "*CONTACT_EXCLUDE_INTERACTION",
                              "*CONTACT_INTERIOR", "*CONTACT_SPG", "*CONTACT_GUIDED_CABLE"})
            if (starts(kw, t)) return Cover::Unscanned;
        return Cover::Scanned;
    }
    // ── 파트 칸만 아무도 읽지 않는 갈래(절점 · 요소 ID 칸이 없거나 그 칸은 정본이 읽는다)
    if (starts(kw, "*CONSTRAINED_EXTRA_NODES_NODE") || starts(kw, "*CONSTRAINED_EXTRA_NODES_SET") ||
        starts(kw, "*INITIAL_VELOCITY_RIGID_BODY") || starts(kw, "*CONSTRAINED_RIGID_BODY_STOPPERS") || starts(kw, "*DAMPING_RELATIVE") ||
        starts(kw, "*DEFINE_FRICTION") || starts(kw, "*MAT_ADD_") || base == "*MAT_NONLOCAL" ||
        oneOf(base, {"*MAT_ELASTIC_6DOF_SPRING_DISCRETE_BEAM", "*MAT_093", "*MAT_INELASTIC_6DOF_SPRING_DISCRETE_BEAM", "*MAT_095"}) ||
        starts(kw, "*CONTROL_REFINE_") || starts(kw, "*CONTROL_ADAPTIVE_CURVE") || starts(kw, "*CONTROL_SUBCYCLE") ||
        (starts(kw, "*CONTROL_MPP_DECOMPOSITION_") && has(kw, "PART")))
        return Cover::PartOnly;
    // ── 참조 없는 키워드(매뉴얼 칸을 본 것만 — 모르면 넣지 않는다)
    if (oneOf(base, {"*KEYWORD", "*TITLE", "*END", "*COMMENT", "*NODE", "*PART", "*PART_CONTACT", "*HOURGLASS", "*DAMPING_GLOBAL", "*SECTION_SOLID",
                     "*SECTION_SHELL", "*SECTION_TSHELL", "*SECTION_BEAM", "*SECTION_DISCRETE", "*SECTION_SEATBELT", "*DEFINE_CURVE",
                     "*DEFINE_CURVE_SMOOTH", "*DEFINE_TABLE", "*DEFINE_TABLE_2D", "*DEFINE_TABLE_3D", "*DEFINE_BOX", "*DEFINE_VECTOR",
                     "*DEFINE_COORDINATE_SYSTEM", "*INITIAL_VELOCITY", "*LOAD_BODY_X", "*LOAD_BODY_Y", "*LOAD_BODY_Z", "*LOAD_BODY_RX",
                     "*LOAD_BODY_RY", "*LOAD_BODY_RZ", "*LOAD_BODY_VECTOR", "*LOAD_BODY_PARTS", "*LOAD_SEGMENT_SET", "*LOAD_SHELL_SET",
                     "*DATABASE_FORMAT", "*DATABASE_NODAL_FORCE_GROUP", "*DATABASE_ABSTAT", "*DATABASE_ATDOUT", "*DATABASE_BNDOUT",
                     "*DATABASE_CURVOUT", "*DATABASE_DCFAIL", "*DATABASE_DEFGEO", "*DATABASE_DEFORC", "*DATABASE_DISBOUT",
                     "*DATABASE_ELOUT", "*DATABASE_GCEOUT", "*DATABASE_GLSTAT", "*DATABASE_H3OUT", "*DATABASE_JNTFORC",
                     "*DATABASE_MATSUM", "*DATABASE_NCFORC", "*DATABASE_NODFOR", "*DATABASE_NODOUT", "*DATABASE_PLLYOUT",
                     "*DATABASE_PRTUBE", "*DATABASE_RBDOUT", "*DATABASE_RCFORC", "*DATABASE_RWFORC", "*DATABASE_SBTOUT",
                     "*DATABASE_SECFORC", "*DATABASE_SLEOUT", "*DATABASE_SPCFORC", "*DATABASE_SPHOUT", "*DATABASE_SSSTAT",
                     "*DATABASE_SWFORC", "*DATABASE_TPRINT", "*DATABASE_TRHIST"}))
        return Cover::Free;
    if (starts(kw, "*BOUNDARY_SPC_SET") || starts(kw, "*PARAMETER") || starts(kw, "*EOS_") || starts(kw, "*DATABASE_BINARY_") ||
        starts(kw, "*DATABASE_EXTENT_"))
        return Cover::Free;
    if (starts(kw, "*RIGIDWALL_PLANAR")) {   // `_ORTHO` · `_FORCES` 는 절점 칸(NODE1 …)이 있다
        std::istringstream rest(kw.substr(std::string("*RIGIDWALL_PLANAR").size()));
        for (std::string t; std::getline(rest, t, '_');)
            if (!t.empty() && t != "ID" && t != "FINITE" && t != "MOVING") return Cover::Unscanned;
        return Cover::Free;
    }
    if (starts(kw, "*MAT_"))   // 재질 카드 — 위 PartOnly 밖에서 요소 칸(EID1 · EID2)이 있는 것은 철근 카드 하나다(Vol_II)
        return starts(kw, "*MAT_WINFRITH_CONCRETE_REINFORCEMENT") ? Cover::Unscanned : Cover::Free;
    if (starts(kw, "*CONTROL_")) {   // 풀이 제어 — 절점 · 요소 칸이 있는 카드만 뺀다(Vol_I 제어 장의 칸)
        for (const char* t : {"*CONTROL_FORMING", "*CONTROL_IMPLICIT_SOLUTION", "*CONTROL_COARSEN", "*CONTROL_2D_REMESHING_REGION",
                              "*CONTROL_SPOTWELD_BEAM", "*CONTROL_STAGED_CONSTRUCTION", "*CONTROL_SEGMENTS_IN_ALE_COUPLING"})
            if (starts(kw, t)) return Cover::Unscanned;
        return Cover::Free;
    }
    return Cover::Unscanned;
}

// 고정폭 칸(w 칸) 하나를 제자리에서 바꾼다 — 다른 칸의 글자는 그대로(`extract_parts` putField 와 같은 꼴)
bool putField(std::string& line, size_t idx, int w, long long v) {
    char buf[40];
    if (std::snprintf(buf, sizeof(buf), "%*lld", w, v) != w) return false;
    const size_t off = idx * static_cast<size_t>(w);
    if (line.size() < off + static_cast<size_t>(w)) line.resize(off + static_cast<size_t>(w), ' ');
    line.replace(off, static_cast<size_t>(w), buf, static_cast<size_t>(w));
    return true;
}

// 키워드 줄 kw 부터 다음 키워드 줄 앞까지(주석 · 빈 줄 포함) — StepForge `section_card` 가 옮기는 「옛 카드 원문」 의 자리
std::vector<std::string> blockAt(const std::vector<std::string>& L, size_t kw) {
    size_t j = kw + 1;
    while (j < L.size() && !cardcut::isKeywordLine(L[j])) ++j;
    return std::vector<std::string>(L.begin() + static_cast<long>(kw), L.begin() + static_cast<long>(j));
}

// 첫 카드의 SECID 가 secid 인 셸 섹션 블록(`*SECTION_SHELL` · `_TITLE`)의 키워드 줄들 — 첫 데이터 줄(제목 다음)의 앞 10칸으로 가린다
// (StepForge `section_card` 와 같은 읽기). 한 키워드 아래 쌓인 둘째 카드는 보지 않는다(그 블록은 카드 하나가 아니라 거절된다).
std::vector<size_t> shellSectionBlocks(const std::vector<std::string>& L, long long secid) {
    std::vector<size_t> out;
    for (size_t i = 0; i < L.size(); ++i) {
        if (!cardcut::isKeywordLine(L[i])) continue;
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(L[i]));
        if (kw != "*SECTION_SHELL" && kw != "*SECTION_SHELL_TITLE") continue;
        size_t skip = kw == "*SECTION_SHELL_TITLE" ? 1 : 0;
        for (size_t j = i + 1; j < L.size() && !cardcut::isKeywordLine(L[j]); ++j) {
            if (cardcut::isCommentLine(L[j])) continue;
            if (skip) { --skip; continue; }
            int v = 0;
            const auto f = cardcut::cut(L[j], 10).f;
            if (!f.empty() && cards::toInt(f[0], v) && v == secid) out.push_back(i);
            break;
        }
    }
    return out;
}

// 그 PID 의 셸 요소 가운데 요소마다 두께(`*ELEMENT_SHELL_THICKNESS` · `_BETA` · `_MCID` 의 THIC1-4 · 중간절점이면 THIC5-8)에 0 이 아닌 값을
// 적은 수 — 그 값은 섹션 두께를 덮는다(Vol_I *ELEMENT_SHELL 주석 6) · 새 섹션 두께가 그 요소에 먹지 않는다(답신 Q8 — 거절)
long long perElementThickness(const std::vector<std::string>& L, const Mesh& m, long long pid) {
    long long n = 0;
    forEachGridCard(L, m, [&](const GridCard& c) {
        if (c.family != ElemFamily::SHELL || !c.thicknessCard || deckscan::fieldInt(c.f, 1) != pid) return;
        const int rw = realFieldWidth(c.fw);
        bool mid = false;
        for (size_t q = 6; q < 10; ++q) mid = mid || deckscan::fieldInt(c.f, q) > 0;
        bool thick = false;
        size_t j = c.line;
        for (int card = 0; card < (mid ? 2 : 1); ++card) {
            ++j;
            while (j < L.size() && cardcut::isCommentLine(L[j])) ++j;
            if (j >= L.size() || cardcut::isKeywordLine(L[j])) break;
            const auto f = cards::fieldsFixed(L[j], rw);
            for (size_t q = 0; q < 4 && q < f.size(); ++q) {
                char* end = nullptr;
                const double t = f[q].empty() ? 0.0 : std::strtod(f[q].c_str(), &end);
                if (!f[q].empty() && (end != f[q].c_str() + f[q].size() || t != 0.0)) thick = true;   // 못 읽는 칸도 0 이라 단정하지 않는다
            }
        }
        n += thick ? 1 : 0;
    });
    return n;
}

// 주 덱 폴더 기준 상대 경로 — `/` · `.` · `..` 를 정규화한다(StepForge `os.path.relpath(p, main_dir)` 와 같은 꼴 · 링크는 풀지 않는다)
std::string relpathOf(const std::string& path, const std::string& mainDir) {
    namespace fs = std::filesystem;
    std::error_code ec;
    const fs::path a = fs::absolute(path, ec).lexically_normal();
    const fs::path b = fs::absolute(mainDir.empty() ? std::string(".") : mainDir, ec).lexically_normal();
    const fs::path r = a.lexically_relative(b);
    return r.empty() ? a.generic_string() : r.generic_string();
}

// 덱의 인클루드 닫힘 — LS-DYNA 가 읽는 차례로 파일마다 {주 덱 폴더 기준 상대 경로, 바이트 전부의 sha256}(판 2 `deck.includes` 와 같은 꼴).
// changed 를 주면 잰 바이트가 닫힘이 담은 줄(`files[].lines`)을 내지 않는 파일(닫힘을 읽은 뒤 바뀌었다)의 상대 경로를 담는다
std::vector<carryover::IncludeEntry> closureEntries(const include_closure::Closure& c, const std::string& mainPath,
                                                    std::vector<std::string>* changed = nullptr) {
    std::vector<carryover::IncludeEntry> out;
    const std::string dir = deckscan::dirOf(mainPath);
    for (const auto& f : c.files) {
        carryover::IncludeEntry e;
        e.relpath = relpathOf(f.path, dir);
        std::string bytes;
        if (!readBytes(f.path, bytes)) {
            e.sha256 = "(읽지 못했다)";
        } else {
            e.sha256 = util::sha256Hex(bytes);
            if (changed && !carryover::bytesGiveLines(bytes, f.lines, true)) changed->push_back(e.relpath);
        }
        out.push_back(e);
    }
    return out;
}

// 솔리드가 뒤집혔나(야코비안 ≤ 0) — 사면체는 6V(`Validator`), 육면체 · 쐐기는 2×2×2 가우스점의 최소(`ElementQualityChecker`)
bool solidInverted(const Mesh& m, const Element& e) {
    if (e.type == ElementType::TET4 || e.type == ElementType::TET10) return !(Validator::calculateJacobian(m, e) > 0);
    std::array<Vector3D, 8> c;
    for (int i = 0; i < 8; ++i) {
        const Node* n = m.getNode(e.nodeIds[static_cast<size_t>(i)]);
        if (!n) return true;
        c[static_cast<size_t>(i)] = n->position;
    }
    ElementQualityChecker q;
    return !(q.checkHex8(c).minJacobian > 0);
}

// 셸 법선 — 두 대각선의 외적(삼각형 n4 = n3 이면 (p3-p1)×(p3-p2) 가 되어 같은 쪽이다). 길이가 0 이면 false.
bool shellNormal(const Mesh& m, const Element& e, Vector3D& n) {
    const Node* p[4];
    for (int i = 0; i < 4; ++i) {
        p[i] = m.getNode(e.nodeIds[static_cast<size_t>(i)]);
        if (!p[i]) return false;
    }
    n = (p[2]->position - p[0]->position).cross(p[3]->position - p[1]->position);
    return n.magnitude() > 0;
}

}  // namespace

bool ModelAssembler::applyCarryoverPlan(const std::string& planPath, const std::string& outputPath, carryover::Report& rep) {
    namespace fs = std::filesystem;
    carry_ = CarryExpect{};
    carry_.base = &baseMesh_;
    std::vector<Problem>& P = rep.problems;
    auto problem = [&](long long pid, const char* kind, const std::string& detail) { P.push_back({pid, kind, detail}); };
    auto warn = [&](long long pid, const char* kind, const std::string& detail) { rep.warnings.push_back({pid, kind, detail}); };
    const std::string tag = "[apply_carryover_plan] ";

    // ── ① 덱 — 지문 · 폭 ────────────────────────────────────────────────────
    {
        std::string bytes;
        if (!readBytes(baseModelPath_, bytes)) { problem(0, "deck_read", "덱을 다시 열지 못했다: " + baseModelPath_); return false; }
        rep.deckShaIn = util::sha256Hex(bytes);
        // 지문은 **고칠 줄을 낸 바이트**의 것이어야 한다 — 줄(rawLines_)은 덱을 담을 때 읽고 지문은 여기서 파일을 다시 열어 잰다. 그 사이에
        // 파일이 바뀌면 지금 바이트의 지문을 계획과 견주고 처음 읽은 줄을 고쳐 썼다(계획이 지금 덱의 것이면 옛 덱에 적용된다 · 적대적 검토 11-07)
        if (!carryover::bytesGiveLines(bytes, rawLines_, false))
            problem(0, "deck_changed", "덱 파일이 읽은 뒤 바뀌었다(" + baseModelPath_ + ") — 잰 지문은 지금 바이트의 것이고 고칠 줄은 처음 읽은 "
                                       "것이라 계획과 견줄 수 없다 · 파일을 그대로 두고 다시 돌린다");
    }
    const int fw = deckFieldWidth(rawLines_);
    if (fw == 20)
        problem(0, "deck_width", "long 폭 덱(*KEYWORD long=y)은 받지 않는다 — 조각의 좌표 글자를 그대로 둘 수 없고 쓰기 길이 20칸 꼴을 확정하지 않았다");

    // ── ② 계획 — 엄격히 읽는다(칸 표 하나 · 판마다 · 걸린 것 전부) ─────────────────
    std::string planText;
    if (!readBytes(planPath, planText)) { problem(0, "plan_read", "계획을 열지 못했다: " + planPath); return false; }
    rep.planRead = true;
    rep.planSha256 = util::sha256Hex(planText);
    carryover::Plan plan;
    carryover::parsePlan(planText, plan, P);
    if (std::any_of(P.begin(), P.end(), [](const Problem& p) { return p.kind == "plan_json"; })) return false;
    rep.planParsed = true;
    rep.planVersion = plan.version;
    rep.reportKey = plan.reportKey;
    const bool v2 = plan.version == 2;
    if (v2) rep.deckFrom = plan.deckFrom;   // 덱을 relpath 로 찾지 않는다 — 부르는 쪽이 준 model 이 그 덱이다(sha256 이 지킨다)
    if (!plan.deckSha256.empty() && plan.deckSha256 != rep.deckShaIn)
        problem(0, "deck_sha", "이 덱의 sha256 " + rep.deckShaIn + " 이 계획의 deck.sha256 " + plan.deckSha256 + " 와 다르다 — 계획은 다른 덱(" +
                                   plan.deckRelpath + ")을 전제했다");
    if (!plan.unreadCards.empty()) {
        std::set<std::string> u(plan.unreadCards.begin(), plan.unreadCards.end());
        warn(0, "unread_cards", "계획을 지은 리더가 모르는 카드 — " + join(u) + " · 그 번호는 계획의 deck.max 에 없다(우리 바닥으로 다시 센다)");
    }
    std::set<long long> planPids;
    for (const auto& row : plan.parts) {
        carryover::PartResult pr;
        pr.pid = row.pid;
        pr.action = row.actionText;
        if (row.valid && row.action == Action::Keep) pr.absorbed = row.absorbed;
        if (row.valid && row.hasRefusedTransform) {   // 판 2 — 계획이 사람 확인으로 돌린 옮김(그대로 되돌려 준다)
            pr.hasRefusedTransform = true;
            pr.refusedM = row.refusedM;
            pr.refusedDet = row.refusedDet;
            pr.refusedScale = row.refusedScale;
            pr.refusedOrth = row.refusedOrth;
        }
        rep.parts.push_back(pr);
        if (row.pid > 0) planPids.insert(row.pid);
        if (row.valid && row.action == Action::Keep && !row.touchesChanged.empty()) rep.touches.push_back({row.pid, row.touchesChanged});
    }

    // ── ②b 인클루드 닫힘 — 판 1 은 거절 · 판 2 는 deck.includes 와 글자 그대로 대조(사용자 결정 11-07 「주 덱만 고침」) ──────────
    // 판 2 에서 닫힘을 다 읽었으면 아래 검사는 **펼친 닫힘 전체**(S · M)를 읽기만 한다. 고치는 것은 주 덱(rawLines_)뿐이다.
    std::vector<std::string> closureLines;
    std::vector<include_closure::LineOrigin> origins;
    std::vector<carryover::IncludeEntry> entries;
    bool closureActive = false;
    {
        size_t first = 0, n = 0;
        for (size_t i = 0; i < rawLines_.size(); ++i) {
            if (deckscan::isDataLine(rawLines_[i])) continue;
            if (deckscan::kwBare(deckscan::keywordToken(rawLines_[i])).rfind("*INCLUDE", 0) == 0 && n++ == 0) first = i;
        }
        if (!v2) {
            if (n)
                problem(0, "deck_include", "덱에 *INCLUDE 카드가 " + std::to_string(n) + " 장 있다(첫 줄 " + std::to_string(first + 1) +
                                               ") — 계획 v1 에는 deck.includes 가 없어 인클루드 닫힘을 지문으로 지킬 수 없다(답신 Q3)");
        } else {
            // 닫힘을 다 못 읽으면(없는 · 못 연 이름 · 맨 *INCLUDE 가 아닌 카드 · 깊이 · 순환 · 폭을 바꾸는 카드 · 폭이 다른 인클루드) 거절 —
            // 그쪽도 그런 덱의 계획은 내지 않는다(§10.3 ①)
            std::string why;
            const bool readable = n == 0 || include_closure::inlined(rawLines_, baseModelPath_, incl_, closureLines, why, &origins);
            if (!readable) {
                problem(0, "include_closure", "덱의 *INCLUDE 닫힘을 다 읽지 못했다 — " + why + " · 닫힘 전체를 읽어야 고치는 PID 를 가리키는 카드가 없다고 "
                                                  "단정할 수 있다");
                closureLines.clear();
                origins.clear();
            } else {
                std::vector<std::string> changed;
                entries = closureEntries(incl_, baseModelPath_, &changed);
                for (const auto& r : changed)   // 지문은 훑은 줄을 낸 바이트의 것이어야 한다 — 주 덱과 같은 까닭(①)
                    problem(0, "deck_changed", "인클루드 파일 " + r + " 이 읽은 뒤 바뀌었다 — 잰 지문은 지금 바이트의 것이고 훑은 줄은 처음 읽은 "
                                               "것이라 deck.includes 와 견줄 수 없다 · 파일을 그대로 두고 다시 돌린다");
                bool same = entries.size() == plan.includes.size();
                for (size_t k = 0; same && k < entries.size(); ++k)
                    same = entries[k].relpath == plan.includes[k].relpath && entries[k].sha256 == plan.includes[k].sha256;
                if (!same) {
                    auto show = [](const std::vector<carryover::IncludeEntry>& v) {
                        std::string s;
                        for (const auto& e : v) s += (s.empty() ? "" : ", ") + e.relpath + "(" + e.sha256.substr(0, 12) + "…)";
                        return "[" + s + "]";
                    };
                    problem(0, "include_mismatch", "deck.includes " + show(plan.includes) + " 가 이 덱의 *INCLUDE 닫힘 " + show(entries) +
                                                       "(주 덱 폴더 기준 상대 경로 · 파일 바이트의 sha256 · LS-DYNA 가 읽는 차례 · 파일마다 한 번)과 다르다");
                } else {
                    rep.includesChecked = true;
                    rep.includes = entries;
                }
                closureActive = !incl_.files.empty();
            }
            if (closureActive) {
                // 산출은 `*INCLUDE` 줄을 그대로 둔다 — LS-DYNA 와 우리 리더는 그 이름을 **산출 덱의 폴더**에서 찾는다(Vol_I 181591).
                // 다른 폴더에 쓰면 그 산출이 다른 파일(또는 없는 파일)을 끌어온다 — 덱과 같은 폴더에만 쓴다
                // 견주는 폴더는 **준 경로 그대로의 폴더**다 — 덱 파일이 심볼릭 링크여도 그 링크가 놓인 자리(LS-DYNA 와 닫힘이 상대 이름을
                // 푸는 자리). 파일 경로를 정규화하면 링크를 따라가 다른 폴더가 나와 맞는 산출을 거절했다(적대적 검토 #5). 폴더 자체의
                // 별칭(폴더 링크)은 정규화로 풀어도 같은 파일을 찾는다
                auto dirOfGiven = [](const std::string& p) {
                    std::error_code e;
                    const fs::path d = fs::absolute(fs::path(p), e).parent_path();
                    const fs::path c = fs::weakly_canonical(d, e);
                    return e ? d.lexically_normal() : c;
                };
                const fs::path od = dirOfGiven(outputPath), md = dirOfGiven(baseModelPath_);
                if (outputPath.empty() || od != md)
                    problem(0, "include_output", "인클루드가 있는 덱의 산출(" + outputPath + ")은 덱과 같은 폴더(" + md.string() + ")에 써야 한다 — 산출은 "
                                                     "*INCLUDE 줄을 그대로 두고 그 이름은 산출 덱의 폴더에서 찾는다(다른 폴더면 다른 파일을 끌어온다)");
                // 닫힘째 읽은 메시 — 나눠 쓴 절점 · 덱 자리 · 품질 · 되읽기 대조의 「앞」(인클루드 안의 요소 · 절점까지)
                std::string note;
                bool complete = true;
                try {
                    KFileReader reader;
                    carry_.closure = std::make_shared<const Mesh>(reader.readFileWithIncludes(baseModelPath_, &note, &complete));
                } catch (const std::exception& e) {
                    complete = false;
                    note = e.what();
                }
                if (!complete || !carry_.closure) {
                    problem(0, "include_closure", "인클루드 닫힘을 메시로 다 읽지 못했다 — " + note);
                    closureActive = false;
                    carry_.closure.reset();
                } else {
                    carry_.base = carry_.closure.get();
                    carry_.includes = true;
                    carry_.includeList = entries;
                }
            }
            if (!closureActive) {   // 끌어온 파일이 없다(`*INCLUDE_PATH` 뿐) · 못 읽었다 — 펼친 사본을 들고 있지 않는다
                closureLines.clear();
                origins.clear();
            }
        }
    }
    // 읽기 전용으로 훑을 줄과 메시 — 인클루드가 있는 판 2 덱은 펼친 닫힘, 아니면 주 덱 그대로(사본을 짓지 않는다)
    const std::vector<std::string>& S = closureActive ? closureLines : rawLines_;
    const Mesh& M = *carry_.base;
    // 훑은 줄의 자리 — 주 덱이면 「줄 N」, 인클루드면 「<상대 경로> 줄 N」(인클루드가 없으면 예전 문구 그대로)
    auto at = [&](size_t i) -> std::string {
        if (!closureActive || i >= origins.size()) return "줄 " + std::to_string(i + 1);
        const auto& o = origins[i];
        if (o.file == include_closure::LineOrigin::kMain || o.file >= entries.size()) return "줄 " + std::to_string(o.line + 1);
        return entries[o.file].relpath + " 줄 " + std::to_string(o.line + 1);
    };
    auto relOfPath = [&](const std::string& path) { return relpathOf(path, deckscan::dirOf(baseModelPath_)); };
    for (const auto& a : plan.added) {
        carryover::AddedResult ar;
        ar.name = a.name;
        ar.hasPid = a.hasPid || (a.fragment.present && a.fragment.ok && a.fragment.pid > 0);
        ar.pid = a.hasPid ? a.pid : a.fragment.pid;
        rep.added.push_back(ar);
    }

    // ── ③ 동반 파일 — 계획 폴더 바로 아래 · 지문 ───────────────────────────────
    // 파일의 몫은 **줄이 정한다**(morph 의 field.file · 판 2 field.new_section.file · remesh · 새 파트의 fragment.file) — 확장자로 가르면
    // `.k` 로 이름 지은 변위장이 조각으로 읽혀 아무 문제도 남기지 않고 적용 단계에서 터졌다(리뷰 11-07). 변위장 · 새 셸 섹션은 지문이
    // 다르면 거절(바이트가 곧 값이다), 조각은 값으로 대조(⑧), 어느 줄도 안 쓰는 파일은 경고만 한다(덱에 닿지 않는다).
    std::set<std::string> fieldFiles, fragmentFiles, sectionFiles;
    for (const auto& row : plan.parts) {
        if (row.action == Action::Morph && row.field.built && !row.field.file.empty()) fieldFiles.insert(row.field.file);
        if (v2 && row.action == Action::Morph && row.field.newSection.built) sectionFiles.insert(row.field.newSection.file);
        if (row.action == Action::Remesh && row.fragment.present && row.fragment.ok && !row.fragment.file.empty())
            fragmentFiles.insert(row.fragment.file);
    }
    for (const auto& a : plan.added)
        if (a.fragment.present && a.fragment.ok && !a.fragment.file.empty()) fragmentFiles.insert(a.fragment.file);
    for (const auto& n : fieldFiles)
        if (fragmentFiles.count(n)) problem(0, "plan_inconsistent", n + " 을 변위장과 조각이 함께 가리킨다 — 한 파일의 몫은 하나다");
    for (const auto& n : sectionFiles)
        if (fieldFiles.count(n) || fragmentFiles.count(n))
            problem(0, "plan_inconsistent", n + " 을 새 셸 섹션과 " + (fieldFiles.count(n) ? "변위장" : "조각") + "이 함께 가리킨다 — 한 파일의 몫은 하나다");
    const fs::path planDir = fs::path(planPath).parent_path();
    struct Companion { bool exists = false, exact = false; std::string text, mismatch; long long claimBytes = 0; };
    std::map<std::string, Companion> comp;
    for (const auto& fe : plan.files) {
        Companion& c = comp[fe.name];
        c.claimBytes = fe.bytes;
        if (fe.name.find_first_of("/\\:") != std::string::npos || fe.name == "." || fe.name == ".." || fe.name.empty()) continue;   // 이미 말했다
        const fs::path p = planDir / fe.name;
        if (!readBytes(p.string(), c.text)) {
            problem(0, "file_missing", fe.name + " 이 계획 폴더(" + planDir.string() + ")에 없다");
            continue;
        }
        c.exists = true;
        const std::string sha = util::sha256Hex(c.text);
        c.exact = (sha == fe.sha256 && static_cast<long long>(c.text.size()) == fe.bytes);
        if (c.exact) continue;
        const std::string detail = fe.name + " — 실물 sha256 " + sha.substr(0, 16) + "… · " + std::to_string(c.text.size()) +
                                   " 바이트가 계획의 " + fe.sha256.substr(0, 16) + "… · " + std::to_string(fe.bytes) + " 바이트와 다르다";
        if (fieldFiles.count(fe.name) || sectionFiles.count(fe.name)) problem(0, "file_mismatch", detail);   // 변위장 · 새 섹션 — 바이트가 곧 값이다
        else c.mismatch = detail;   // 조각은 값으로 대조한다(⑧) · 안 쓰는 파일은 경고(⑧ 끝)
    }
    // 줄이 가리키는 파일 — files 에 있어야 하고 머리의 bytes 가 files 의 bytes 와 같아야 한다(계획 안의 두 주장 · 새 섹션 머리는 bytes 가 없다 — -1)
    std::set<std::string> usedFiles;   // 줄이 가리킨 동반 파일 — 바이트가 달랐는데 아무 줄도 안 쓴 조각은 값으로 못 대조했다고 말한다
    auto companion = [&](long long pid, const std::string& name, long long bytes, const char* what) -> const Companion* {
        usedFiles.insert(name);
        auto it = comp.find(name);
        if (it == comp.end()) {
            problem(pid, "file_unlisted", std::string(what) + " " + name + " 이 계획의 files 에 없다 — 지문으로 대조할 수 없다");
            return nullptr;
        }
        if (bytes >= 0 && it->second.claimBytes != bytes)
            problem(pid, "plan_inconsistent", std::string(what) + " " + name + " 의 bytes " + std::to_string(bytes) + " 가 files 의 " +
                                                  std::to_string(it->second.claimBytes) + " 와 다르다");
        return it->second.exists ? &it->second : nullptr;
    };

    // ── ④ 덱 표 — *PART · 섹션 · 재질 · 격자 밖 요소 · 셸 중간절점(닫힘 전체 — 고칠 자리는 주 덱의 표 `partsMain`) ─────────
    const PartIndex partsMain = indexParts(rawLines_);
    const PartIndex partsAll = closureActive ? indexParts(S) : PartIndex{};
    const PartIndex& parts = closureActive ? partsAll : partsMain;
    const auto variants = definedPartVariantIds(S);
    const auto sections = definedSectionIds(S);
    // 새 SECID 의 겹침 · 차례는 쌓인 카드까지 넉넉히 센 집합으로 본다(위 `sections` 는 키워드마다 첫 카드 — 있나 · 종류를 가리는 데만 쓴다)
    // (번호 커서와 같은 공용 훑기 `ModelAssembler::sectionIdsAnyCard` — 리뷰 11-07 #1 에 이 파일에 두었던 것을 11-07 밤 커서에도 쓰려고 옮겼다)
    const auto secidsAll = sectionIdsAnyCard(S);
    const long long secidTop = secidsAll.empty() ? 0 : *secidsAll.rbegin();
    const auto mids = definedMaterialIds(S);
    // 번호마다 정의한 블록 — 손대는 PID 의 SECID · MID 를 두 블록이 정의하면 그 줄을 거절한다(StepForge 권고 D-681 · 아래 ⑤)
    const auto secDefs = sectionDefinitionLines(S);
    const auto midDefs = materialDefinitionLines(S);
    for (size_t kwl : parts.oddBlocks)
        problem(0, "deck_part_block", at(kwl) + " 의 *PART 블록 — 데이터 줄이 제목 · 카드 짝으로 떨어지지 않는다");
    std::vector<NonGridElementCard> auxCards;   // 칸 자리를 아는 격자 밖 요소(보 · 이산 · 질량 · 안전띠 · 플롯) — 나눠 쓴 절점 · EID 겹침이 본다
    forEachNonGridElementCard(S, [&](const NonGridElementCard& c) {
        if (c.known) auxCards.push_back(c);
    });
    // 절점 칸을 다 읽지 못하는 요소 블록 — 키워드마다 첫 줄 · 블록 수 · 까닭(`elementBlockGap`)
    struct Gap { size_t first = 0, blocks = 0; std::string why; };
    std::map<std::string, Gap> elemGaps;
    bool hasEnd = false;   // 넣을 블록은 쓰기가 주 덱의 *END 자리에 낸다(writeOutput — 대문자 머리 「*END」)
    for (size_t i = 0; i < rawLines_.size(); ++i)
        if (cardcut::isKeywordLine(rawLines_[i]) && deckscan::kwBare(deckscan::keywordToken(rawLines_[i])).rfind("*END", 0) == 0) hasEnd = true;
    for (size_t i = 0; i < S.size(); ++i) {
        if (!cardcut::isKeywordLine(S[i])) continue;
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(S[i]));
        if (kw.rfind("*ELEMENT_", 0) != 0) continue;
        std::string why = elementBlockGap(S[i]);
        if (why.empty()) continue;
        Gap& g = elemGaps[kw];
        if (g.blocks++ == 0) { g.first = i; g.why = std::move(why); }
    }
    // 요소 `_TITLE` 블록(`gridTitleBlock`)은 다 읽은 블록이 아니다 — 그 블록에 요소가 있을 수 있는 PID 를 고치면 거절하고 keep · review 는
    // 둔다(StepForge 권고 D-681). PID 는 데이터 줄마다 둘째 칸의 정수 — 첫 줄이 제목이든 아니든 두 읽기를 다 덮게 넉넉히 센다(두 줄 카드의
    // 절점 줄 · 제목 줄의 정수도 들어 거짓 거절이 날 수 있다 — 안전한 쪽). 키워드 줄은 `forEachGridCard` 와 같은 규칙(첫 글자 `*`)
    std::map<long long, size_t> titleBlockOf;   // PID → 그 PID 가 있을 수 있는 첫 블록의 키워드 줄
    {
        const int deckFw = deckFieldWidth(S);
        bool in = false;
        int fw = deckFw;
        size_t kwl = 0;
        for (size_t i = 0; i < S.size(); ++i) {
            const std::string& l = S[i];
            const size_t g = l.find_first_not_of(" \t");
            if (g != std::string::npos && l[g] == '*') {
                in = gridTitleBlock(l);
                fw = keywordFieldWidth(l, deckFw);
                kwl = i;
                continue;
            }
            if (!in || !deckscan::isDataLine(l)) continue;
            const int v = deckscan::fieldInt(deckscan::cardFields(l, fw), 1);
            if (v > 0) titleBlockOf.emplace(v, kwl);
        }
    }
    const auto midside = shellMidsideNodes(S, M);
    {
        std::vector<long long> unplanned;
        for (const auto& [pid, loc] : parts.plain) {
            (void)loc;
            if (!planPids.count(pid)) unplanned.push_back(pid);
        }
        if (!unplanned.empty()) warn(0, "unplanned_parts", "계획에 줄이 없는 덱 PID — " + idList(unplanned) + " · 그대로 둔다");
    }

    // 고칠 PID(옮기기 · 모프 · 바꿔 넣기 · 지우기)의 요소와 절점 — 2차 솔리드는 중간절점까지(`forEachElementNode`), 셸은 N5-N8 까지
    std::set<long long> geometryPids;
    bool anyRefRows = false;
    for (const auto& row : plan.parts)
        if (row.valid && geometryAction(row.action)) {
            geometryPids.insert(row.pid);
            anyRefRows = anyRefRows || row.action == Action::Remesh || row.action == Action::Delete;
        }
    auto elementNodes = [&](const Element& e, const std::function<void(int)>& f) {
        M.forEachElementNode(e, f);
        if (e.type != ElementType::QUAD4) return;
        auto it = midside.find(e.id);
        if (it != midside.end()) for (int n : it->second) f(n);
    };
    std::map<long long, std::vector<int>> elemsOf, nodesOf;
    {
        std::map<long long, std::set<int>> ns;
        for (const auto& [eid, e] : M.elements) {
            if (!geometryPids.count(e.partId)) continue;
            elemsOf[e.partId].push_back(eid);
            auto& s = ns[e.partId];
            elementNodes(e, [&](int n) { s.insert(n); });
        }
        for (auto& [pid, s] : ns) nodesOf[pid].assign(s.begin(), s.end());
    }
    // 덱을 고치는 줄 — 옮기기 · 모프 · 바꿔 넣기 · 지우기 · 조각이 있는 새 파트
    const bool anyGeometry = !geometryPids.empty() || std::any_of(plan.added.begin(), plan.added.end(), [](const carryover::AddedRow& a) {
                                 return a.valid && a.fragment.present && a.fragment.ok;
                             });
    if (anyGeometry && !elemGaps.empty()) {
        std::string list;
        for (const auto& [kw, g] : elemGaps)
            list += (list.empty() ? "" : ", ") + kw + "(" + at(g.first) + " · 블록 " + std::to_string(g.blocks) + " · " + g.why + ")";
        problem(0, "opaque_elements", "덱에 절점 칸을 다 읽지 못하는 요소 블록이 있다 — " + list +
                                          " · 그 요소가 고치는 PID 의 절점 · 요소를 쓰는지 단정할 수 없고 번호 바닥도 그 EID 를 모른다");
    }
    // 요소 번호 겹침 — 리더는 요소를 번호 하나로 들고(한쪽을 잃는다) 쓰기는 지울 번호를 모든 요소 블록에서 지운다(리뷰 11-07 — 셸과
    // 솔리드가 EID 하나를 나눠 써 지우지 않을 솔리드가 사라졌다). 날 줄을 직접 훑어 격자 · 격자 밖 요소 카드를 다 센다.
    // 먼저 싸게 본다 — 격자 카드 수가 메시의 서로 다른 EID 수와 같고 격자 밖 EID 가 메시 · 서로와 안 겹치면 겹침이 없다(큰 덱에서 EID
    // 표를 통째로 짓지 않는다). 수가 다르면(리더가 건너뛴 카드일 수도 있다) 표를 지어 실제로 겹친 번호를 찾는다
    bool eidSuspect = false;
    if (anyGeometry) {
        size_t gridCards = 0;
        forEachGridCard(S, M, [&](const GridCard& c) { gridCards += deckscan::fieldInt(c.f, 0) > 0 ? 1 : 0; });
        eidSuspect = gridCards != M.elements.size();
        std::unordered_set<int> auxSeen;
        for (const auto& c : auxCards)
            if (c.eid > 0 && (M.elements.count(c.eid) || !auxSeen.insert(c.eid).second)) eidSuspect = true;
    }
    if (eidSuspect) {
        std::vector<std::string> kwNames;
        std::map<std::string, uint32_t> kwIndex;
        std::unordered_map<int, std::pair<uint32_t, size_t>> first;     // EID → (키워드 · 줄)
        std::map<int, std::vector<std::pair<uint32_t, size_t>>> dup;     // 겹친 EID → 나온 자리 전부
        auto note = [&](int eid, const std::string& kw, size_t line) {
            if (eid <= 0) return;
            auto ki = kwIndex.emplace(kw, static_cast<uint32_t>(kwNames.size()));
            if (ki.second) kwNames.push_back(kw);
            const auto here = std::make_pair(ki.first->second, line);
            auto f = first.emplace(eid, here);
            if (f.second) return;
            auto& d = dup[eid];
            if (d.empty()) d.push_back(f.first->second);
            d.push_back(here);
        };
        forEachGridCard(S, M, [&](const GridCard& c) { note(deckscan::fieldInt(c.f, 0), *c.keyword, c.line); });
        for (const auto& c : auxCards) note(c.eid, c.keyword, c.line);
        if (!dup.empty()) {
            std::string list;
            std::set<std::string> kws;
            size_t k = 0;
            for (const auto& [eid, occ] : dup) {
                for (const auto& o : occ) kws.insert(kwNames[o.first]);
                if (k++ == 10) list += " …";
                if (k > 10) continue;
                std::string where;
                for (const auto& o : occ) where += (where.empty() ? "" : " · ") + kwNames[o.first] + " " + at(o.second);
                list += (list.empty() ? "" : ", ") + ("EID " + std::to_string(eid) + "(" + where + ")");
            }
            problem(0, "eid_collision", "요소 번호가 겹친다 " + std::to_string(dup.size()) + " 개 — " + list + " · 키워드 " + join(kws) +
                                            " · 이 덱은 요소를 번호로 가를 수 없다(리더는 한쪽만 들고 쓰기는 지울 번호를 모든 요소 블록에서 지운다)");
        }
    }

    // ── ④b 판 2 — 줄마다의 덱 자리(그쪽 `KDeck.part_ranges()` 와 같은 셈) · 인클루드 파일이 정의한 고칠 절점 ─────────────
    // 덱 자리: 그 PID 의 솔리드 · 셸 · 두꺼운 셸 요소(닫힘 전체 · 리더가 담은 격자 요소)가 가리킨 서로 다른 절점(2차 중간절점 · 8절점 셸의
    // N5-N8 포함 · 0 제외)의 최소 · 최대 · 수, 요소 번호의 최소 · 최대 · 수, 둘 다 빈 데가 없나(contiguous — 요소가 없으면 null),
    // `*PART` 의 SECID · MID(없으면 null). 번호 목록(지우기 · 바꿔 넣기)은 늘 그 PID 의 요소에서 다시 구한다 — 범위로 고르지 않는다(§10.3 ⑤)
    struct Place {
        bool hasNode = false, hasElem = false, hasSecid = false, hasMid = false;
        long long nodeLo = 0, nodeHi = 0, nodeCount = 0, elemLo = 0, elemHi = 0, elemCount = 0, secid = 0, mid = 0;
        int contiguous = -1;
    };
    std::map<long long, Place> places;
    if (v2) {
        std::map<long long, std::vector<const Element*>> byPid;   // 계획에 줄이 있는 PID 만(EID 오름차순 — 메시가 그 차례다)
        for (const auto& [eid, e] : M.elements) {
            (void)eid;
            if (planPids.count(e.partId)) byPid[e.partId].push_back(&e);
        }
        std::vector<int> buf;
        for (const auto& [pid, es] : byPid) {
            Place pl;
            pl.hasElem = true;
            pl.elemLo = es.front()->id;
            pl.elemHi = es.back()->id;
            pl.elemCount = static_cast<long long>(es.size());
            buf.clear();
            for (const Element* e : es) elementNodes(*e, [&](int n) { if (n > 0) buf.push_back(n); });
            std::sort(buf.begin(), buf.end());
            buf.erase(std::unique(buf.begin(), buf.end()), buf.end());
            pl.nodeCount = static_cast<long long>(buf.size());
            if (!buf.empty()) { pl.hasNode = true; pl.nodeLo = buf.front(); pl.nodeHi = buf.back(); }
            pl.contiguous = pl.hasNode && pl.nodeHi - pl.nodeLo + 1 == pl.nodeCount && pl.elemHi - pl.elemLo + 1 == pl.elemCount ? 1 : 0;
            places[pid] = pl;
        }
        for (long long pid : planPids) {
            Place& pl = places[pid];
            if (auto it = parts.plain.find(pid); it != parts.plain.end()) {
                pl.hasSecid = pl.hasMid = true;
                pl.secid = it->second.secid;
                pl.mid = it->second.mid;
            }
        }
    }
    // 그 줄의 덱 자리를 우리 셈과 견준 차이(칸마다 「계획 · 우리」) — 비면 같다
    auto placeDiff = [&](const carryover::PartDeck& d, const Place& o) {
        auto rng = [](bool has, long long lo, long long hi) { return has ? "[" + std::to_string(lo) + ", " + std::to_string(hi) + "]" : std::string("null"); };
        auto opt = [](bool has, long long v) { return has ? std::to_string(v) : std::string("null"); };
        auto tri = [](int c) { return c < 0 ? std::string("null") : (c ? std::string("true") : std::string("false")); };
        std::vector<std::string> out;
        auto cmp = [&](const char* name, const std::string& a, const std::string& b) {
            if (a != b) out.push_back(std::string(name) + " 계획 " + a + " · 우리 " + b);
        };
        cmp("node", rng(d.hasNode, d.nodeLo, d.nodeHi), rng(o.hasNode, o.nodeLo, o.nodeHi));
        cmp("node_count", std::to_string(d.nodeCount), std::to_string(o.nodeCount));
        cmp("elem", rng(d.hasElem, d.elemLo, d.elemHi), rng(o.hasElem, o.elemLo, o.elemHi));
        cmp("elem_count", std::to_string(d.elemCount), std::to_string(o.elemCount));
        cmp("contiguous", tri(d.contiguous), tri(o.contiguous));
        cmp("secid", opt(d.hasSecid, d.secid), opt(o.hasSecid, o.secid));
        cmp("mid", opt(d.hasMid, d.mid), opt(o.hasMid, o.mid));
        std::string s;
        for (const auto& x : out) s += (s.empty() ? "" : " · ") + x;
        return s;
    };
    // 인클루드 파일의 `*NODE` 가 정의한 고칠 절점 → 그 파일(닫힘 색인) — 주 덱만 고치므로 그런 절점은 옮기지도 지우지도 못한다
    std::unordered_map<int, size_t> includeNodeFile;
    if (closureActive) {
        std::unordered_set<int> U;
        for (const auto& [pid, ns] : nodesOf) {
            (void)pid;
            U.insert(ns.begin(), ns.end());
        }
        for (size_t fi = 0; fi < incl_.files.size() && !U.empty(); ++fi) {
            const auto& L = incl_.files[fi].lines;
            bool inNode = false;
            int nfw = fw;
            for (const auto& l : L) {
                if (cardcut::isKeywordLine(l)) {
                    inNode = deckscan::kwBare(deckscan::keywordToken(l)) == "*NODE";
                    nfw = keywordFieldWidth(l, fw);
                    continue;
                }
                if (!inNode || !deckscan::isDataLine(l)) continue;
                int nid = 0;
                double xyz[3];
                if (deckscan::readNodeLine(l, nfw, nid, xyz) && U.count(nid)) includeNodeFile.emplace(nid, fi);
            }
        }
    }

    // ── ⑤ 줄마다 — 덱에 있나 · 덱 자리 · 고칠 자리가 주 덱인가 · 처리별 검사 ─────────────────────────
    std::map<long long, carryover::Field> fields;
    std::set<long long> ready;   // 덱에서 찾았고 요소가 있는 고칠 PID(고칠 자리가 전부 주 덱에 있다)
    for (const auto& row : plan.parts) {
        if (!row.valid) continue;
        const long long pid = row.pid;
        const bool plain = parts.plain.count(pid) != 0;
        const bool variant = variants.count(static_cast<int>(pid)) != 0;
        if (!plain && !variant) { problem(pid, "part_missing", "PID " + std::to_string(pid) + " 가 덱의 *PART 에 없다"); continue; }
        // 판 2 — 줄의 덱 자리가 우리 셈과 다르면 손대는 줄은 거절, keep · review 는 경고(사용자 결정 11-07)
        if (v2 && row.deck.present) {
            const std::string diff = placeDiff(row.deck, places[pid]);
            if (!diff.empty()) {
                if (geometryAction(row.action))
                    problem(pid, "deck_range", "PID 의 덱 자리가 계획과 다르다 — " + diff + " · 계획이 본 덱과 다른 PID 를 고치지 않는다");
                else
                    warn(pid, "deck_range", "PID 의 덱 자리가 계획과 다르다 — " + diff + " · " + row.actionText + " 줄이라 손대지 않는다");
            }
        }
        if (!geometryAction(row.action)) continue;
        if (!plain) {
            problem(pid, "part_variant", "PID 가 맨 *PART 가 아니라 " + variants.at(static_cast<int>(pid)) +
                                             " 로 정의됐다 — 그 카드의 값(무게중심 · 관성 · 접촉 두께 …)을 함께 고치는 규칙이 없다");
            continue;
        }
        if (parts.duplicate.count(pid) || variant) {
            problem(pid, "part_duplicate", std::string("PID 의 *PART 카드가 둘 이상이다") +
                                               (variant ? "(맨 *PART 와 " + variants.at(static_cast<int>(pid)) + ")" : std::string()));
            continue;
        }
        if (auto t = titleBlockOf.find(pid); t != titleBlockOf.end()) {
            problem(pid, "opaque_elements", "PID 의 요소가 " + deckscan::kwBare(deckscan::keywordToken(S[t->second])) + " 블록(" + at(t->second) +
                                                ")에 있을 수 있다 — 요소 키워드의 TITLE 은 설명서 옵션이 아니어서 첫 줄이 제목 카드인지 근거가 없고 "
                                                "우리 리더는 숫자꼴 제목을 요소로 읽는다 · 그 PID 는 고치지 않는다(StepForge 권고 D-681)");
            continue;
        }
        // 그 PID 의 SECID · MID 를 두 블록 이상이 정의하면 LS-DYNA 는 둘째 정의에서 멈춘다 — StepForge 도 그 줄에서 멈춘다(권고 D-681 ·
        // 사용자 결정 11-07 밤). `*PART` 가 둘인 것과 같은 갈래(part_duplicate)로 거절한다. 정의는 블록마다 첫 카드다(번호 훑기와 같다)
        {
            const PartLoc& loc = parts.plain.at(pid);
            std::string dup;
            auto twice = [&](const char* what, long long id, const std::map<int, std::vector<size_t>>& defs) {
                auto it = id > 0 ? defs.find(static_cast<int>(id)) : defs.end();
                if (it == defs.end() || it->second.size() < 2) return;
                std::string where;
                for (size_t k = 0; k < it->second.size() && k < 4; ++k) where += (k ? " · " : "") + at(it->second[k]);
                dup += (dup.empty() ? "" : " / ") + std::string(what) + " " + std::to_string(id) + " 의 정의가 " + std::to_string(it->second.size()) +
                       " 개(" + where + ")";
            };
            twice("SECID", loc.secid, secDefs);
            twice("MID", loc.mid, midDefs);
            if (!dup.empty()) {
                problem(pid, "part_duplicate", "PID 의 " + dup + " — LS-DYNA 는 같은 번호의 둘째 정의에서 멈춘다(StepForge 도 그 줄에서 멈춘다 · 권고 D-681)");
                continue;
            }
        }
        // 판 2 · 인클루드 덱 — 고칠 자리(그 PID 의 `*PART` · 요소 · 그 요소의 절점)가 전부 주 덱에 있어야 한다(사용자 결정 11-07 「주 덱만
        // 고침 · 인클루드면 거절」 — 인클루드 파일은 쓰지 않는다). 새 섹션이 옮길 옛 섹션 카드는 아래 ⑧b 가 본다
        if (closureActive) {
            std::map<std::string, std::vector<std::string>> where;   // 파일 → 무엇
            if (!partsMain.plain.count(pid)) {
                const std::string f = include_closure::partFile(incl_, static_cast<int>(pid));
                where[f.empty() ? std::string("(인클루드)") : relOfPath(f)].push_back("*PART 카드");
            }
            long long inInclude = 0;
            for (int eid : elemsOf[pid]) {
                auto it = baseMesh_.elements.find(eid);
                if (it == baseMesh_.elements.end() || it->second.partId != pid) ++inInclude;
            }
            if (inInclude) {
                auto f = includeElemPidFile_.find(static_cast<int>(pid));
                where[f == includeElemPidFile_.end() ? std::string("(인클루드)") : relOfPath(f->second)].push_back(
                    "요소 " + std::to_string(inInclude) + " 개");
            }
            std::map<size_t, std::vector<int>> nodeFiles;
            for (int n : nodesOf[pid])
                if (auto it = includeNodeFile.find(n); it != includeNodeFile.end()) nodeFiles[it->second].push_back(n);
            for (const auto& [fi, ns] : nodeFiles)
                where[entries[fi].relpath].push_back("절점 " + std::to_string(ns.size()) + " 개(" + idList(ns, 8) + ")");
            if (!where.empty()) {
                std::string list;
                for (const auto& [f, what] : where) {
                    std::string w;
                    for (const auto& x : what) w += (w.empty() ? "" : " · ") + x;
                    list += (list.empty() ? "" : " / ") + f + ": " + w;
                }
                problem(pid, "include_edit", "PID " + std::to_string(pid) + "(" + row.actionText + ")를 고칠 자리가 인클루드 파일에 있다 — " + list +
                                                 " · 주 덱만 고친다(인클루드 파일은 쓰지 않는다 — 사용자 결정 11-07)");
                continue;
            }
        }
        if (elemsOf[pid].empty()) {
            problem(pid, "part_empty", "PID 의 요소가 메시에 없다 — 리더가 읽지 못한 블록에 있을 수 있다");
            continue;
        }
        {
            std::vector<int> undefinedNodes;
            for (int n : nodesOf[pid])
                if (!M.getNode(n)) undefinedNodes.push_back(n);
            if (!undefinedNodes.empty()) {
                problem(pid, "node_undefined", "PID 의 요소가 정의되지 않은 절점을 가리킨다 — " + idList(undefinedNodes));
                continue;
            }
        }
        {
            std::set<std::string> kinds;
            // PID 후보 전부를 본다 — 질량 줄을 정수 폭으로 쓰면 PID 가 읽기마다 갈린다(2026-11-07 — 어느 읽기로든 이 PID 면 적는다)
            for (const auto& c : auxCards)
                if (std::find(c.pids.begin(), c.pids.end(), pid) != c.pids.end()) kinds.insert(c.keyword);
            if (!kinds.empty())
                problem(pid, "aux_in_part", "PID 에 " + join(kinds) + " 요소가 있다 — 옮기기 · 바꿔 넣기 · 지우기가 그 요소를 다루지 않는다");
        }
        ready.insert(pid);
        switch (row.action) {
            case Action::Transform: {
                const auto& m = row.m;
                if (m[12] != 0 || m[13] != 0 || m[14] != 0 || m[15] != 1)
                    problem(pid, "transform_not_rigid", "4×4 의 마지막 행이 0 0 0 1 이 아니다");
                const double R[3][3] = {{m[0], m[1], m[2]}, {m[4], m[5], m[6]}, {m[8], m[9], m[10]}};
                double orth = 0;
                for (int i = 0; i < 3; ++i)
                    for (int j = 0; j < 3; ++j) {
                        double s = 0;
                        for (int k = 0; k < 3; ++k) s += R[k][i] * R[k][j];
                        orth = std::max(orth, std::fabs(s - (i == j ? 1.0 : 0.0)));
                    }
                const double det = R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0]) +
                                   R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]);
                // 허용 1e-6 — StepForge 는 4×4 칸을 round(x, 9) 로 싣는다. 칸마다 5e-10 이 RᵀR 에 ~2e-9 까지 쌓여 1e-9 로는 돌린
                // 강체의 다섯에 하나를 거절했다(리뷰 11-07 — z 축 23° 가 1.2e-9). 늘림 · 기울임 · 거울은 그보다 몇 자리 크다
                if (!(orth <= 1e-6) || !(std::fabs(det - 1.0) <= 1e-6)) {
                    char buf[128];
                    std::snprintf(buf, sizeof(buf), "max|RᵀR − I| = %.12g · det(R) = %.12g", orth, det);
                    problem(pid, "transform_not_rigid", std::string("회전부가 강체가 아니다 — ") + buf + " (허용 1e-6 — 늘림 · 기울임 · 거울을 받지 않는다)");
                }
                double offIdentity = 0;
                for (int i = 0; i < 3; ++i)
                    for (int j = 0; j < 3; ++j) offIdentity = std::max(offIdentity, std::fabs(R[i][j] - (i == j ? 1.0 : 0.0)));
                if (offIdentity > 1e-12)
                    warn(pid, "orientation_not_rotated", "PID " + std::to_string(pid) + " 를 돌린다 — 절점 자리만 돌리고 재질 축(AOPT 벡터) · " +
                                                             "좌표계(*DEFINE_COORDINATE_*) · 셸 MCID · 초기 응력 · 변형률은 돌리지 않는다(사람이 확인한다)");
                for (int k = 0; k < 3; ++k)
                    if (std::fabs(row.translation[static_cast<size_t>(k)] - m[static_cast<size_t>(4 * k + 3)]) >
                        1e-9 * std::max(1.0, std::fabs(m[static_cast<size_t>(4 * k + 3)]))) {
                        problem(pid, "plan_inconsistent", "translation 이 4×4 의 이동 칸과 다르다");
                        break;
                    }
                break;
            }
            case Action::Morph: {
                if (row.hasInstead)
                    problem(pid, "morph_instead", "morph 줄에 instead(조각)가 있다 — 우리는 변위장만 쓴다(답신 Q1). 그 줄은 적용하지 않는다");
                if (!row.field.built) { problem(pid, "field_missing", "변위장을 못 지었다 — " + row.field.why); break; }
                // 판 1 은 셸 두께가 바뀐 모프를 받지 않는다. 판 2 는 new_section 이 정한다 — null 이면 섹션을 그대로 두고(§10.2) 지은 카드면
                // ⑧b 가 넣는다
                if (!v2 && row.field.hasThickness)
                    problem(pid, "field_thickness", "셸 두께가 바뀐 모프 — v1 에는 field.new_section 이 없어 섹션을 잇지 못한다(답신 Q8 · v2)");
                const Companion* c = companion(pid, row.field.file, row.field.bytes, "변위장");
                if (!c || !c->exact) break;   // 없거나 지문이 다르면 읽지 않는다(이미 말했다)
                carryover::Field fld;
                std::string err;
                if (!carryover::readField(c->text, row.field, fld, err)) { problem(pid, "field_values", row.field.file + " — " + err); break; }
                const auto& want = nodesOf[pid];
                std::vector<int> missing, extra;
                {
                    std::set<int> have(fld.node.begin(), fld.node.end());
                    for (int n : want)
                        if (!have.count(n)) missing.push_back(n);
                    std::set<int> w(want.begin(), want.end());
                    for (uint32_t n : fld.node)
                        if (!w.count(static_cast<int>(n))) extra.push_back(static_cast<int>(n));
                }
                if (!missing.empty() || !extra.empty())
                    problem(pid, "field_nodes", "변위장의 절점이 PID 요소가 쓰는 절점 전부와 같지 않다 — 빠짐 " + std::to_string(missing.size()) +
                                                    (missing.empty() ? "" : "(" + idList(missing, 10) + ")") + " · 남음 " +
                                                    std::to_string(extra.size()) + (extra.empty() ? "" : "(" + idList(extra, 10) + ")"));
                std::vector<int> sharedBit;
                for (size_t i = 0; i < fld.node.size(); ++i)
                    if (fld.kind[i] & static_cast<uint8_t>(row.field.kind.sharedBit)) sharedBit.push_back(static_cast<int>(fld.node[i]));
                if (!sharedBit.empty())
                    problem(pid, "shared_bit", "변위장의 꼴 바이트가 다른 PID 와 나눠 쓴 절점으로 적었다 — " + idList(sharedBit));
                fields[pid] = std::move(fld);
                break;
            }
            case Action::Remesh:
                if (!row.fragment.ok)
                    problem(pid, "fragment_failed", "조각을 못 지었다 — " + (row.fragment.why.empty() ? std::string("StepForge 가 까닭을 적지 않았다")
                                                                                                     : row.fragment.why));
                break;
            default:
                break;
        }
    }
    // 새 파트 — PID 는 덱에 없어야 하고 서로 겹치지 않는다
    {
        std::set<long long> addedPids;
        for (const auto& a : plan.added) {
            if (!a.valid || !a.fragment.present) continue;
            if (!a.fragment.ok) {
                problem(a.pid, "fragment_failed", "새 파트 " + a.name + " 의 조각을 못 지었다 — " +
                                                      (a.fragment.why.empty() ? std::string("StepForge 가 까닭을 적지 않았다") : a.fragment.why));
                continue;
            }
            const long long pid = a.fragment.pid;
            if (parts.plain.count(pid) || variants.count(static_cast<int>(pid)))
                problem(pid, "added_pid_exists", "새 파트 " + a.name + " 의 PID " + std::to_string(pid) + " 가 덱에 이미 있다");
            if (!addedPids.insert(pid).second)
                problem(pid, "added_pid_duplicate", "새 파트 PID " + std::to_string(pid) + " 를 두 줄이 쓴다");
        }
    }

    // ── ⑥ 나눠 쓰는 절점 — 격자 요소(다른 PID) · 보 · 이산 · 질량 · 안전띠 · 플롯 요소 ───────────
    {
        std::unordered_set<int> U;
        for (long long pid : ready)
            for (int n : nodesOf[pid]) U.insert(n);
        std::unordered_map<int, std::set<long long>> gridUsers;
        std::unordered_map<int, std::set<std::string>> auxUsers;
        if (!U.empty()) {
            for (const auto& [eid, e] : M.elements) {
                (void)eid;
                elementNodes(e, [&](int n) {
                    if (U.count(n)) gridUsers[n].insert(e.partId);
                });
            }
            for (const auto& c : auxCards)
                for (int n : c.nodes)
                    if (U.count(n)) auxUsers[n].insert(c.keyword + (c.pid > 0 ? "(PID " + std::to_string(c.pid) + ")" : ""));
        }
        for (const auto& row : plan.parts) {
            if (!row.valid || !ready.count(row.pid)) continue;
            const long long pid = row.pid;
            std::vector<long long> shared;
            std::set<std::string> with;
            for (int n : nodesOf[pid]) {
                bool s = false;
                if (auto g = gridUsers.find(n); g != gridUsers.end())
                    for (long long q : g->second)
                        if (q != pid) { with.insert("PID " + std::to_string(q)); s = true; }
                if (auto a = auxUsers.find(n); a != auxUsers.end() && !a->second.empty()) {
                    with.insert(a->second.begin(), a->second.end());
                    s = true;
                }
                if (s) shared.push_back(n);
            }
            const std::set<long long> ours(shared.begin(), shared.end());
            const std::set<long long> theirs(row.shared.nodes.begin(), row.shared.nodes.end());
            if (!shared.empty())
                problem(pid, "shared_nodes", "PID 의 절점 " + std::to_string(shared.size()) + " 개를 다른 요소와 나눠 쓴다 — 절점 " +
                                                 idList(shared) + " · 상대 " + join(with) +
                                                 " · 나눠 쓰는 절점이 있는 PID 는 적용하지 않는다(사용자 결정 11-07 — `disconnect` 로 먼저 뗀다)" +
                                                 (row.shared.present && theirs != ours ? " · 계획의 shared_nodes 와 다르다" : ""));
            if (row.shared.present && !row.shared.nodes.empty())
                problem(pid, "shared_nodes_plan", "계획이 나눠 쓰는 절점 " + std::to_string(row.shared.nodes.size()) + " 개(" +
                                                      idList(row.shared.nodes) + " · 상대 PID " + idList(row.shared.with) +
                                                      ")를 적었다 — 그런 PID 는 적용하지 않는다" +
                                                      (shared.empty() ? " · 우리 덱 리더로 다시 세면 0 개다" : ""));
        }
    }

    // ── ⑦ 참조 — 바꿔 넣기 · 지우기 PID 를 절점 · 세그먼트 · 요소(지우기는 PID 도)로 가리키는 카드 ──────────
    if (anyRefRows) {
        std::unordered_map<int, long long> nodeOwner, elemOwner;
        std::set<long long> deletePids;
        for (const auto& row : plan.parts) {
            if (!row.valid || !ready.count(row.pid) || (row.action != Action::Remesh && row.action != Action::Delete)) continue;
            for (int n : nodesOf[row.pid]) nodeOwner.emplace(n, row.pid);
            for (int e : elemsOf[row.pid]) elemOwner.emplace(e, row.pid);
            if (row.action == Action::Delete) deletePids.insert(row.pid);
        }
        // 블록마다 한 문장으로 모은다 — 절점 세트 한 블록이 수천 줄이다
        struct Hit { long long count = 0; size_t firstLine = 0; std::set<int> values; std::string kw; };
        std::map<std::pair<long long, size_t>, Hit> nodeHits;
        const auto nr = noderefs::find(S, fw, [&](int v) { return nodeOwner.count(v) != 0; });
        for (const auto& r : nr.refs) {
            auto& h = nodeHits[{nodeOwner.at(r.value), r.kwLine}];
            if (h.count++ == 0) { h.firstLine = r.line; h.kw = noderefs::keywordOf(S, r); }
            if (h.values.size() < 12) h.values.insert(r.value);
        }
        for (const auto& [key, h] : nodeHits)
            problem(key.first, "node_ref", h.kw + "(" + at(key.second) + ")이 이 PID 의 절점을 " + std::to_string(h.count) +
                                               " 곳 가리킨다(첫 " + at(h.firstLine) + " · 절점 " + idList(h.values, 10) +
                                               ") — 바꿔 넣거나 지우면 그 참조를 옮길 수 없다");
        std::map<std::tuple<long long, size_t, int>, Hit> idHits;
        const auto ir = idrefs::find(S, fw, [&](idrefs::Axis ax, int v) {
            return ax == idrefs::Axis::Elem ? elemOwner.count(v) != 0 : deletePids.count(v) != 0;
        });
        for (const auto& r : ir.refs) {
            const long long owner = r.axis == idrefs::Axis::Elem ? elemOwner.at(r.value) : r.value;
            auto& h = idHits[{owner, r.kwLine, r.axis == idrefs::Axis::Elem ? 0 : 1}];
            if (h.count++ == 0) { h.firstLine = r.line; h.kw = idrefs::keywordOf(S, r); }
            if (h.values.size() < 12) h.values.insert(r.value);
        }
        for (const auto& [key, h] : idHits) {
            const bool elem = std::get<2>(key) == 0;
            problem(std::get<0>(key), elem ? "elem_ref" : "part_ref",
                    h.kw + "(" + at(std::get<1>(key)) + ")이 이 PID 의 " + (elem ? "요소" : "PID") + "를 " +
                        std::to_string(h.count) + " 곳 가리킨다(첫 " + at(h.firstLine) +
                        (elem ? " · 요소 " + idList(h.values, 10) : std::string()) + ") — " +
                        (elem ? "바꿔 넣거나 지우면 그 참조를 옮길 수 없다" : "지우면 그 참조가 매달린다(PID 로 건 참조는 지우기를 막는다)"));
        }
        // 정본이 칸 뜻을 단정하지 못한 자리 — 칸 자리를 아는 격자 밖 요소 블록(⑥이 절점을 셌다)은 뺀다
        {
            std::vector<std::string> auxOnly;
            bool inAux = false;
            for (const auto& l : S) {
                const size_t g = l.find_first_not_of(" \t");
                if (g != std::string::npos && l[g] == '*') {
                    const AuxElementCard a = auxElementCard(l);
                    // 질량 얹기(`*ELEMENT_MASS_PART(_SET)` — 요소가 아니다 · 걸음이 넘긴다)는 ⑥이 세지 않으니 빼지 않는다(그 PID 는 아래 표가 본다)
                    inAux = a.family != AuxFamily::NONE && a.supported && a.hasEid;
                }
                if (inAux) auxOnly.push_back(l);
            }
            const auto cn = noderefs::find(auxOnly, fw);
            const auto ci = idrefs::find(auxOnly, fw);
            const long long uncovered = static_cast<long long>(nr.notChecked) + ir.notChecked - cn.notChecked - ci.notChecked;
            if (uncovered > 0) {
                std::set<std::string> kws(nr.notCheckedKeywords.begin(), nr.notCheckedKeywords.end());
                kws.insert(ir.notCheckedKeywords.begin(), ir.notCheckedKeywords.end());
                for (const auto& k : cn.notCheckedKeywords) kws.erase(k);
                for (const auto& k : ci.notCheckedKeywords) kws.erase(k);
                problem(0, "not_checked", "절점 · 요소 · 파트를 가리키는 줄 알지만 칸 뜻을 단정하지 못한 자리 " + std::to_string(uncovered) + " 곳 — " +
                                              (kws.empty() ? std::string("(키워드 목록 밖)") : join(kws)) +
                                              " · 바꿔 넣거나 지우는 PID 를 가리키지 않는다고 증명할 수 없다");
            }
        }
        // ★정본이 보지도 세지도 않는 키워드 — 참조 없는 표(`refCover`)에 없으면 거절한다(리뷰 11-07 — *CONSTRAINED_SHELL_TO_SOLID ·
        // *LOAD_SEGMENT · *DEFINE_VECTOR_NODES … 가 지운 절점을 가리킨 채 rc 0 으로 나갔다). 키워드마다 한 번 · 첫 줄과 블록 수
        {
            struct Uncov { size_t first = 0, blocks = 0; bool partOnly = false; };
            std::map<std::string, Uncov> unscanned;
            const bool deleting = !deletePids.empty();
            for (size_t i = 0; i < S.size(); ++i) {   // 키워드 줄만 본다(큰 *NODE 블록의 줄 표를 짓지 않는다)
                if (!cardcut::isKeywordLine(S[i])) continue;
                const std::string kw = deckscan::kwBare(deckscan::keywordToken(S[i]));
                if (kw.rfind("*SET_", 0) == 0 || kw.rfind("*INCLUDE", 0) == 0) continue;   // 세트 표(아래) · 인클루드(①)가 본다
                Cover cv;
                if (kw.rfind("*ELEMENT_", 0) == 0) {
                    // 절점 칸은 요소 블록 판정(④)이 · 격자 밖 요소의 PID 는 aux_in_part 가 본다. 보 `_PID` 옵션 카드의 PID1 · PID2 와
                    // `*ELEMENT_MASS_PART` 의 ID(파트)는 아무도 읽지 않는다(Vol_I 155771 · 160154) — `_SET` 은 파트 세트 ID 다
                    const bool massPart = hasOption(kw, "*ELEMENT_MASS", "PART");
                    cv = (hasOption(kw, "*ELEMENT_BEAM", "PID") || (massPart && !hasOption(kw, "*ELEMENT_MASS", "SET"))) ? Cover::PartOnly
                                                                                                                            : Cover::Scanned;
                } else {
                    cv = refCover(kw);
                    // *LOAD_NODE_POINT 의 M1-M3(칸 6-8)는 따름 힘의 절점이다(Vol_I *LOAD_NODE — DOF 4 · 8). 정본은 칸 1 만 읽는다
                    if (cv == Cover::Scanned && kw.rfind("*LOAD_NODE_POINT", 0) == 0)
                        for (size_t d = i + 1; d < S.size() && !cardcut::isKeywordLine(S[d]); ++d) {
                            if (cardcut::isCommentLine(S[d])) continue;
                            const auto c = cardcut::cut(S[d], fw >= 20 ? 20 : 10);
                            for (size_t q = 5; q < 8 && q < c.f.size(); ++q) {
                                int v = 0;
                                if (!deckscan::trim(c.f[q]).empty() && (!cards::toInt(c.f[q], v) || v != 0)) cv = Cover::Unscanned;
                            }
                        }
                }
                if (cv == Cover::Free || cv == Cover::Scanned || (cv == Cover::PartOnly && !deleting)) continue;
                Uncov& u = unscanned[kw];
                if (u.blocks++ == 0) { u.first = i; u.partOnly = cv == Cover::PartOnly; }
            }
            for (const auto& [kw, u] : unscanned)
                problem(0, "ref_unscanned", kw + "(" + at(u.first) + " · 블록 " + std::to_string(u.blocks) + ") — " +
                                                (u.partOnly ? std::string("파트 ID 칸을 정본이 읽지 않는다 · 지우는 PID 를 가리키지 않는다고 증명할 수 없다")
                                                            : std::string("절점 · 요소 · 파트 칸을 정본(NodeRefs · IdRefs)이 읽지 않고 참조 없는 키워드 표에도 없다 · "
                                                                          "바꿔 넣거나 지우는 PID 를 가리키지 않는다고 증명할 수 없다")));
        }
        // 접촉 면 — 세트로 건 면은 정본(`ct_setMembers`)으로 풀어 본다(방언 `_ADD` · `_GENERATE` … 까지)
        auto sets = ct_parseSets(S);
        ct_resolveSetRanges(sets, M);
        for (const auto& c : ct_parseContacts(S)) {
            if (c.cardLine[0] < 0) continue;   // Card 1 이 없으면 정본이 단정하지 않았다고 이미 셌다
            const std::string where = c.fullKeyword + "(" + at(static_cast<size_t>(c.startLine)) + ")";
            const std::pair<const char*, std::pair<int, int>> sides[] = {{"SURFA", {c.ssid, c.sstyp}}, {"SURFB", {c.msid, c.mstyp}}};
            for (const auto& [side, s] : sides) {
                const int id = s.first, st = s.second;
                if (id == 0 || st == 3 || st == 5) continue;   // 3 은 위 정본(PID 칸)이 · 5 는 전부라 PID 를 가리키지 않는다
                const char* type = st == 0 ? "SEGMENT" : st == 1 ? "SHELL" : (st == 2 || st == 6) ? "PART" : st == 4 ? "NODE" : nullptr;
                if (!type) { problem(0, "contact_side", where + " 의 " + side + " — STYP " + std::to_string(st) + " 은 풀 수 없다"); continue; }
                if (std::string(type) == "PART" && deletePids.empty()) continue;   // 파트 세트는 바꿔 넣기에서 산다
                const auto m = ct_setMembers(sets, id, type);
                if (!m.found || !m.resolved) {
                    problem(0, "contact_side", where + " 의 " + side + " — " + type + " 세트 " + std::to_string(id) + " 를 풀 수 없다(" +
                                                   (m.found ? m.why : std::string("덱에 없다")) + ") · 고치는 PID 를 담는지 단정할 수 없다");
                    continue;
                }
                std::map<long long, long long> hits;
                if (std::string(type) == "SEGMENT") {
                    for (const auto& seg : m.segments)
                        for (int n : seg)
                            if (auto it = nodeOwner.find(n); it != nodeOwner.end()) ++hits[it->second];
                } else {
                    for (int v : m.ids) {
                        if (st == 1) { if (auto it = elemOwner.find(v); it != elemOwner.end()) ++hits[it->second]; }
                        else if (st == 4) { if (auto it = nodeOwner.find(v); it != nodeOwner.end()) ++hits[it->second]; }
                        else if (deletePids.count(v)) ++hits[v];
                    }
                }
                for (const auto& [owner, cnt] : hits)
                    problem(owner, "contact_side", where + " 의 " + side + "(STYP " + std::to_string(st) + " · " + type + " 세트 " +
                                                       std::to_string(id) + ")가 이 PID 를 " + std::to_string(cnt) +
                                                       " 곳 담는다 — 바꿔 넣거나 지우면 그 면이 조용히 비거나 깨진다");
            }
        }
        // 세트 — 평범한 목록 · `_COLUMN` 은 위 정본이 읽었다. 방언(_GENERATE · _ADD · _INTERSECT)은 정본 해석기로 풀어 보고, 풀 수 없으면
        // (`_GENERAL` 의 옵션 줄 · `_ADVANCED` · 없는 멤버 세트 · 순환) 거절한다(리뷰 11-07 — `*SET_NODE_GENERAL` 의 PART 줄이 지운 PID 를
        // 담은 채 rc 0 으로 나갔다). 종류를 모르는 세트(*SET_DISCRETE · *SET_NODE_INTERVAL …)는 정본도 해석기도 보지 않는다 — 거절한다
        for (const auto& s : sets) {
            const std::string type = s.type == "NODE_SMOOTH" ? "NODE" : s.type;   // *SET_NODE_LIST_SMOOTH — 정본은 목록으로 읽는다
            const bool elemSet = type == "SHELL" || type == "SOLID" || type == "TSHELL" || type == "BEAM";
            const bool nodeSet = type == "NODE" || type == "SEGMENT";
            const bool partSet = type == "PART";
            const std::string where = deckscan::kwBare(deckscan::keywordToken(S[static_cast<size_t>(s.startLine)])) + " " +
                                      std::to_string(s.id) + "(" + at(static_cast<size_t>(s.startLine)) + ")";
            if (!elemSet && !nodeSet && !partSet) {
                problem(0, "ref_unscanned", where + " — 세트 종류 " + s.type +
                                                " 의 멤버를 정본도 세트 해석기도 읽지 않는다 · 바꿔 넣거나 지우는 PID 를 담지 않는다고 증명할 수 없다");
                continue;
            }
            if (partSet && deletePids.empty()) continue;   // 파트 세트는 바꿔 넣기에서 산다
            if (s.dialect.empty() || s.dialect == "COLLECT" || s.dialect == "COLUMN") continue;   // 정본 칸 표가 읽었다
            const auto m = ct_setMembers(sets, s.id, type);
            if (!m.found || !m.resolved) {
                problem(0, "set_unresolved", where + " — 멤버를 풀 수 없다(" + (m.found ? m.why : std::string("덱에 없다")) +
                                                 ") · 바꿔 넣거나 지우는 PID 를 담지 않는다고 증명할 수 없다");
                continue;
            }
            std::map<long long, long long> hits;
            for (const auto& seg : m.segments)
                for (int n : seg)
                    if (auto it = nodeOwner.find(n); it != nodeOwner.end()) ++hits[it->second];
            for (int v : m.ids) {
                if (elemSet) { if (auto it = elemOwner.find(v); it != elemOwner.end()) ++hits[it->second]; }
                else if (type == "NODE") { if (auto it = nodeOwner.find(v); it != nodeOwner.end()) ++hits[it->second]; }
                else if (partSet && deletePids.count(v)) ++hits[v];
            }
            for (const auto& [owner, cnt] : hits)
                problem(owner, "set_member", where + "이 이 PID 를 " + std::to_string(cnt) + " 곳 담는다 — 바꿔 넣거나 지우면 그 세트가 조용히 바뀐다");
        }
    }

    // ── ⑧ 조각 — 값 대조 · 덱과 견주기(섹션 · 재질) ─────────────────────────────
    struct Job {
        long long pid = 0;
        bool added = false;
        size_t row = 0;
        const carryover::FragmentHead* h = nullptr;
        std::vector<std::string> lines;
        carryover::FragmentScan scan;
    };
    std::vector<Job> jobs;
    for (size_t k = 0; k < plan.parts.size(); ++k) {
        const auto& row = plan.parts[k];
        if (row.valid && row.action == Action::Remesh && row.fragment.ok && ready.count(row.pid)) jobs.push_back({row.pid, false, k, &row.fragment, {}, {}});
    }
    for (size_t k = 0; k < plan.added.size(); ++k) {
        const auto& a = plan.added[k];
        if (a.valid && a.fragment.present && a.fragment.ok) jobs.push_back({a.fragment.pid, true, k, &a.fragment, {}, {}});
    }
    // 넣을 조각은 쓰기가 *END 자리에 낸다 — *END 가 없는 덱이면 블록이 조용히 빠지고 되읽기 대조가 엉뚱한 까닭으로 멈췄다(리뷰 11-07)
    if (!jobs.empty() && !hasEnd)
        problem(0, "deck_no_end", "덱에 *END 가 없다 — 조각(바꿔 넣기 · 새 파트)은 *END 앞에 넣는다 · 잘린 덱일 수 있다(끝에 *END 를 두고 계획을 다시 짓는다)");
    std::set<long long> newSecids;
    for (auto& j : jobs) {
        const auto& h = *j.h;
        const Companion* c = companion(j.pid, h.file, h.bytes, "조각");
        if (!c) continue;
        j.lines = splitLines(c->text);
        std::vector<std::string> fp;
        if (carryover::scanFragment(j.lines, j.scan, fp)) carryover::checkFragment(j.scan, h, j.pid, fp);
        size_t shells = 0;
        for (const auto& e : j.scan.elems) shells += e.shell ? 1 : 0;
        const bool shellPart = !j.scan.elems.empty() && shells == j.scan.elems.size();
        if (!mids.count(static_cast<int>(h.mid))) fp.push_back("MID " + std::to_string(h.mid) + " 이 덱에 없다");
        if (!j.added) {
            const PartLoc& loc = partsMain.plain.at(j.pid);   // 바꿔 넣는 PID 의 `*PART` 는 주 덱에 있다(⑤ — 아니면 ready 가 아니다)
            if (h.mid != loc.mid)
                fp.push_back("fragment.mid " + std::to_string(h.mid) + " 가 덱 *PART 의 MID " + std::to_string(loc.mid) + " 와 다르다 — 바꿔 넣기는 덱의 MID 를 그대로 쓴다");
            if (!h.newSection.present && h.secid != loc.secid)
                fp.push_back("fragment.secid " + std::to_string(h.secid) + " 가 덱 *PART 의 SECID " + std::to_string(loc.secid) +
                             " 와 다르다 — 섹션을 바꾸는 조각은 new_section 을 싣는다");
            if (h.newSection.present && !loc.fixedCard)
                fp.push_back("덱 *PART 카드(줄 " + std::to_string(loc.cardLine + 1) + ")가 고정폭이 아니다 — SECID 칸을 제자리에서 고칠 수 없다");
        }
        if (h.newSection.present) {
            const int ns = static_cast<int>(h.newSection.secid);
            if (sections.count(ns)) fp.push_back("new_section.secid " + std::to_string(ns) + " 가 덱에 이미 있다(" + sections.at(ns) + ")");
            else if (secidsAll.count(ns))
                fp.push_back("new_section.secid " + std::to_string(ns) + " 가 덱에 이미 있다(*SECTION_* 블록 안의 쌓인 카드 — 데이터 줄 첫 칸)");
            if (!newSecids.insert(ns).second) fp.push_back("new_section.secid " + std::to_string(ns) + " 를 다른 조각도 쓴다");
            // 판 2 — 새 SECID 는 덱(닫힘 전체 · 쌓인 카드까지)의 가장 큰 SECID 위로 매긴다(§10.3 ③)
            if (v2 && (ns <= plan.maxSecid || ns <= secidTop))
                problem(j.pid, "secid_order", h.file + " — new_section.secid " + std::to_string(ns) + " 가 deck.max.secid " +
                                                  std::to_string(plan.maxSecid) + " · 이 덱(닫힘 · 쌓인 카드까지)의 가장 큰 SECID " +
                                                  std::to_string(secidTop) + " 위가 아니다(§10.3 ③)");
        } else if (!j.scan.elems.empty()) {
            auto it = sections.find(static_cast<int>(h.secid));
            if (it == sections.end()) fp.push_back("SECID " + std::to_string(h.secid) + " 가 덱에 없다");
            else if (it->second.rfind(shellPart ? "*SECTION_SHELL" : "*SECTION_SOLID", 0) != 0)
                fp.push_back("SECID " + std::to_string(h.secid) + " 는 " + it->second + " 인데 조각 요소는 " + (shellPart ? "셸" : "솔리드") + " 다");
        }
        for (const auto& s : fp) problem(j.pid, "fragment", h.file + " — " + s);
        if (!c->mismatch.empty()) {
            if (fp.empty())
                warn(j.pid, "fragment_bytes", c->mismatch + " — 값 대조(번호 구간 · 수 · PID · SECID · MID · 요소 꼴 · 섹션 카드)는 지났다(개행 · 공백이 바뀐 사본일 수 있다)");
            else
                problem(j.pid, "file_mismatch", c->mismatch);
        }
    }

    // ── ⑧b 판 2 — 셸 두께가 바뀐 모프의 새 섹션(요청서 §10.2 · §10.3 ② ③ · 답신 Q8) ─────────────────────────
    // 카드는 덱의 옛 카드(그 PID `*PART` 의 SECID — 주 덱)를 그대로 옮겨 SECID(Card 1 앞 10칸) · T1~T4(Card 2 앞 40칸)만 바꾼 것이어야
    // 한다. SECID 는 계획과 같고 · 닫힘에 없고 · deck.max.secid 위이며 · 조각의 새 섹션 뒤에 모프 줄 차례로 잇는다. 요소마다 두께를
    // 싣는 PID 면 새 섹션 두께가 먹지 않아 거절한다. 못 지은 꼴(secid · file null)은 그 줄이 조각으로 물러섰다는 뜻이다 — 우리는 변위장만
    // 쓴다(답신 Q1 · instead 는 morph_instead 가 따로 말한다).
    struct SecJob {
        long long pid = 0, secid = 0;
        double thickness = 0;
        std::string file;
        carryover::SectionFileScan scan;
    };
    std::map<size_t, SecJob> secJobs;   // 계획 줄 → 넣을 새 섹션
    if (v2) {
        long long fragMax = 0;   // 조각의 새 섹션(줄 차례로 먼저 매긴다 — §10.3 ③)
        for (const auto& row : plan.parts)
            if (row.valid && row.action == Action::Remesh && row.fragment.ok && row.fragment.newSection.present)
                fragMax = std::max(fragMax, row.fragment.newSection.secid);
        for (const auto& a : plan.added)
            if (a.valid && a.fragment.present && a.fragment.ok && a.fragment.newSection.present)
                fragMax = std::max(fragMax, a.fragment.newSection.secid);
        std::set<long long> morphSecids;
        long long prev = 0;
        for (size_t k = 0; k < plan.parts.size(); ++k) {
            const auto& row = plan.parts[k];
            if (!row.valid || row.action != Action::Morph || !row.field.newSection.present) continue;   // null — 섹션은 그대로(§10.2)
            const long long pid = row.pid;
            const auto& ns = row.field.newSection;
            const std::string sid = std::to_string(ns.secid);
            if (!ns.built) {
                problem(pid, "new_section", "셸 두께가 바뀌었는데 StepForge 가 새 섹션을 못 지었다 — " +
                                                (ns.why.empty() ? std::string("까닭을 적지 않았다") : ns.why) +
                                                " · 그 줄은 조각(instead)으로 물러섰다 — 우리는 변위장만 쓴다(답신 Q1)");
                continue;
            }
            if (auto it = sections.find(static_cast<int>(ns.secid)); it != sections.end())
                problem(pid, "secid_collision", "new_section.secid " + sid + " 가 덱(닫힘)에 이미 있다(" + it->second + ")");
            else if (secidsAll.count(ns.secid))
                problem(pid, "secid_collision", "new_section.secid " + sid + " 가 덱(닫힘)에 이미 있다(*SECTION_* 블록 안의 쌓인 카드 — 데이터 줄 첫 칸)");
            if (newSecids.count(ns.secid)) problem(pid, "secid_collision", "new_section.secid " + sid + " 가 조각의 새 섹션과 겹친다");
            if (!morphSecids.insert(ns.secid).second) problem(pid, "secid_collision", "new_section.secid " + sid + " 를 다른 모프 줄도 쓴다");
            if (ns.secid <= plan.maxSecid || ns.secid <= secidTop)
                problem(pid, "secid_order", "new_section.secid " + sid + " 가 deck.max.secid " + std::to_string(plan.maxSecid) +
                                                " · 이 덱(닫힘 · 쌓인 카드까지)의 가장 큰 SECID " + std::to_string(secidTop) + " 위가 아니다(§10.3 ③)");
            if (ns.secid <= fragMax)
                problem(pid, "secid_order", "new_section.secid " + sid + " — 조각의 새 섹션(가장 큰 SECID " + std::to_string(fragMax) +
                                                ")을 먼저 매기고 모프 줄은 그 뒤에 잇는다(§10.3 ③)");
            if (ns.secid <= prev)
                problem(pid, "secid_order", "new_section.secid " + sid + " — 모프 줄의 새 섹션은 줄 차례로 잇는다(앞 줄 " + std::to_string(prev) + ")");
            prev = std::max(prev, ns.secid);
            if (row.field.hasElementThickness)
                problem(pid, "element_thickness", "계획이 이 PID 의 셸 요소 " + std::to_string(row.field.elementThicknessCount) +
                                                      " 개가 요소마다 두께를 싣는다고 했다(field.element_thickness) — 그 두께가 섹션 두께를 덮어 새 섹션이 먹지 않는다(답신 Q8 — 거절)");
            SecJob sj;
            sj.pid = pid;
            sj.secid = ns.secid;
            sj.thickness = ns.thickness;
            sj.file = ns.file;
            std::vector<std::string> fp;
            bool scanned = false;
            const Companion* c = companion(pid, ns.file, -1, "새 셸 섹션");
            if (c && c->exact) {   // 없거나 지문이 다르면 읽지 않는다(이미 말했다)
                scanned = carryover::scanSectionFile(splitLines(c->text), sj.scan, fp);
                if (scanned && sj.scan.secid != ns.secid)
                    fp.push_back("카드의 SECID " + std::to_string(sj.scan.secid) + " 가 new_section.secid " + sid + " 와 다르다");
                if (scanned)
                    for (int t = 0; t < 4; ++t)
                        if (!(std::fabs(sj.scan.t[t] - ns.thickness) <= 1e-9 * std::max(1.0, std::fabs(ns.thickness)))) {
                            fp.push_back("카드의 T" + std::to_string(t + 1) + " " + num(sj.scan.t[t]) + " 가 new_section.thickness " + num(ns.thickness) +
                                         " 와 다르다(T1~T4 넷 다 그 값이어야 한다)");
                            break;
                        }
            }
            // 덱의 옛 카드 — 그 PID `*PART`(주 덱 — ⑤ 를 지났으면 ready)의 SECID 로 찾는다. 주 덱에 하나뿐이어야 하고 인클루드에 있으면 거절
            if (ready.count(pid)) {
                const PartLoc& loc = partsMain.plain.at(pid);
                if (!loc.fixedCard)
                    fp.push_back("덱 *PART 카드(줄 " + std::to_string(loc.cardLine + 1) + ")가 고정폭이 아니다 — SECID 칸을 제자리에서 고칠 수 없다");
                std::vector<std::string> incFiles;
                if (closureActive)
                    for (size_t fi = 0; fi < incl_.files.size(); ++fi)
                        if (definedSectionIds(incl_.files[fi].lines).count(static_cast<int>(loc.secid))) incFiles.push_back(entries[fi].relpath);
                const auto blocks = shellSectionBlocks(rawLines_, loc.secid);
                if (!incFiles.empty()) {
                    std::set<std::string> u(incFiles.begin(), incFiles.end());
                    problem(pid, "include_edit", "PID " + std::to_string(pid) + "(morph)의 옛 섹션 SECID " + std::to_string(loc.secid) + " 카드가 인클루드 파일에 있다 — " +
                                                     join(u) + " · 새 섹션은 그 카드를 옮긴다 — 주 덱만 고친다(사용자 결정 11-07)");
                } else if (blocks.size() != 1) {
                    fp.push_back(blocks.empty() ? "덱 *PART 의 옛 SECID " + std::to_string(loc.secid) +
                                                      " 이 주 덱의 *SECTION_SHELL(_TITLE) 블록 첫 카드가 아니다(다른 섹션 꼴 · 쌓인 둘째 카드) — 옮긴 카드를 견줄 수 없다"
                                                : "옛 SECID " + std::to_string(loc.secid) + " 의 셸 섹션 블록이 둘 이상이다(줄 " + std::to_string(blocks[0] + 1) +
                                                      " · " + std::to_string(blocks[1] + 1) + ")");
                } else {
                    if (keywordFieldWidth(rawLines_[blocks[0]], fw) == 20) fp.push_back("옛 셸 섹션 카드(줄 " + std::to_string(blocks[0] + 1) + ")가 long 폭이다");
                    if (scanned) carryover::compareSectionCards(blockAt(rawLines_, blocks[0]), sj.scan, fp);
                }
                if (const long long et = perElementThickness(S, M, pid); et > 0)
                    problem(pid, "element_thickness", "PID 셸 요소 " + std::to_string(et) + " 개가 요소마다 두께(*ELEMENT_SHELL_THICKNESS · _BETA · _MCID 의 "
                                                          "THIC)를 싣는다 — 그 두께가 섹션 두께를 덮어 새 섹션이 먹지 않는다(답신 Q8 — 거절)");
            }
            for (const auto& s : fp) problem(pid, "new_section", ns.file + " — " + s);
            if (fp.empty() && scanned) secJobs.emplace(k, std::move(sj));
        }
        if (!secJobs.empty() && jobs.empty() && !hasEnd)   // 새 섹션 카드도 쓰기가 주 덱의 *END 자리에 낸다(조각과 같은 까닭)
            problem(0, "deck_no_end", "덱에 *END 가 없다 — 새 셸 섹션 카드는 *END 앞에 넣는다 · 잘린 덱일 수 있다");
    }

    for (const auto& [name, c] : comp)
        if (!c.mismatch.empty() && !usedFiles.count(name))
            warn(0, "file_mismatch_unused", c.mismatch + " — 계획의 어느 줄도 이 파일을 쓰지 않아 값으로 대조하지 않았다");

    // ── ⑨ 번호 — 바닥(모든 요소 족) 위 · 조각끼리 겹치지 않음 · 칸 폭 ──────────────────
    long long shiftNode = 0, shiftElem = 0;
    if (!jobs.empty()) {
        const auto mx = idMaxima();
        long long minN = std::numeric_limits<long long>::max(), minE = minN, maxN = 0, maxE = 0;
        for (const auto& j : jobs) {
            minN = std::min(minN, j.h->nodeLo);
            minE = std::min(minE, j.h->elemLo);
            maxN = std::max(maxN, j.h->nodeHi);
            maxE = std::max(maxE, j.h->elemHi);
        }
        if (minN <= mx.node) shiftNode = mx.node + 1 - minN;
        if (minE <= mx.elem) shiftElem = mx.elem + 1 - minE;
        const long long cap = fw == 10 ? static_cast<long long>(std::numeric_limits<int>::max()) : 99999999LL;
        if (maxN + shiftNode > cap || maxE + shiftElem > cap)
            problem(0, "id_width", "조각 번호(옮긴 뒤 절점 ~" + std::to_string(maxN + shiftNode) + " · 요소 ~" + std::to_string(maxE + shiftElem) +
                                       ")가 이 덱의 칸 폭(" + std::to_string(fw) + ")을 넘는다");
        auto overlap = [&](bool node) {
            std::vector<std::pair<long long, long long>> rs;
            for (const auto& j : jobs) rs.push_back(node ? std::make_pair(j.h->nodeLo, j.h->nodeHi) : std::make_pair(j.h->elemLo, j.h->elemHi));
            std::sort(rs.begin(), rs.end());
            for (size_t k = 1; k < rs.size(); ++k)
                if (rs[k].first <= rs[k - 1].second)
                    problem(0, "fragment_overlap", std::string("조각 ") + (node ? "절점" : "요소") + " 구간 " + std::to_string(rs[k - 1].first) + "~" +
                                                       std::to_string(rs[k - 1].second) + " 와 " + std::to_string(rs[k].first) + "~" +
                                                       std::to_string(rs[k].second) + " 가 겹친다");
        };
        overlap(true);
        overlap(false);
        rep.shifted = shiftNode != 0 || shiftElem != 0;
        rep.shiftNode = shiftNode;
        rep.shiftElem = shiftElem;
        if (rep.shifted)
            warn(0, "shift", "조각 번호가 이 덱의 바닥(절점 " + std::to_string(mx.node) + " · 요소 " + std::to_string(mx.elem) +
                                 " — 보 · 이산 · 질량 요소까지 센 최대값) 이하에 걸쳐 옮겼다 — 절점 +" + std::to_string(shiftNode) + " · 요소 +" +
                                 std::to_string(shiftElem) + "(조각끼리는 그대로 잇는다)");
    }

    // ── 거절 — 걸린 것이 하나라도 있으면 덱을 건드리지 않는다 ─────────────────────
    if (!P.empty()) {
        for (auto& pr : rep.parts) {
            const bool own = std::any_of(P.begin(), P.end(), [&](const Problem& p) { return p.pid == pr.pid && pr.pid > 0; });
            pr.result = own ? "refused" : "skipped";
        }
        for (size_t k = 0; k < rep.added.size(); ++k) {
            auto& ar = rep.added[k];
            auto own = std::find_if(P.begin(), P.end(), [&](const Problem& p) { return ar.pid > 0 && p.pid == ar.pid; });
            ar.result = own != P.end() ? "refused" : "skipped";
            ar.why = own != P.end() ? own->detail : plan.added[k].why;
        }
        return false;
    }

    // ── ⑩ 적용 — 편집 상태(쓰기는 writeOutput) ───────────────────────────────
    std::map<size_t, const Job*> jobOfRow, jobOfAdded;
    for (const auto& j : jobs) (j.added ? jobOfAdded : jobOfRow)[j.row] = &j;
    auto insertFragment = [&](const Job& j, const std::string& title) {
        const auto& h = *j.h;
        std::ostringstream head;   // 계획이 준 글자(이름 · 파일 이름)는 한 줄로 — 주석 줄을 끊고 카드를 심지 못하게
        head << "$\n$ === apply_carryover_plan — " << oneLine(title) << " · StepForge 조각 " << oneLine(h.file) << " ===\n"
             << "$ 번호 — 절점 " << h.nodeLo + shiftNode << "~" << h.nodeHi + shiftNode << " · 요소 " << h.elemLo + shiftElem << "~"
             << h.elemHi + shiftElem;
        if (shiftNode || shiftElem) head << " (조각 번호에서 절점 +" << shiftNode << " · 요소 +" << shiftElem << " 옮김)";
        head << "\n";
        addedKeywordBlocks_.push_back(head.str() + carryover::renderFragment(j.lines, j.scan, shiftNode, shiftElem, fw, j.added));
        for (const auto& n : j.scan.nodes) carry_.insertedNodes[n.id + shiftNode] = n.xyz;
        for (const auto& e : j.scan.elems) {
            CarryExpect::Inserted ins;
            ins.pid = e.pid;
            for (size_t k = 0; k < (e.shell ? 4u : 8u); ++k)
                if (e.n[k] > 0) ins.nodes.push_back(e.n[k] + shiftNode);
            std::sort(ins.nodes.begin(), ins.nodes.end());
            ins.nodes.erase(std::unique(ins.nodes.begin(), ins.nodes.end()), ins.nodes.end());
            carry_.insertedElems[e.id + shiftElem] = ins;
        }
        maxNodeId_ = std::max<long long>(maxNodeId_, h.nodeHi + shiftNode);
        maxElementId_ = std::max<long long>(maxElementId_, h.elemHi + shiftElem);
    };
    auto removePart = [&](long long pid, carryover::PartResult& pr) {
        const auto& es = elemsOf[pid];
        const auto& ns = nodesOf[pid];
        removedElementIds_.insert(es.begin(), es.end());
        removedNodeIds_.insert(ns.begin(), ns.end());   // 나눠 쓴 절점이 없음을 ⑥이 보였다 — 전부 이 PID 만 쓴다
        carry_.removedElems.insert(es.begin(), es.end());
        carry_.removedNodes.insert(ns.begin(), ns.end());
        pr.hasRemoved = true;
        pr.removedNodes = static_cast<long long>(ns.size());
        pr.removedElements = static_cast<long long>(es.size());
    };
    std::map<size_t, size_t> deletedPairs;   // *PART 블록 키워드 줄 → 지운 짝 수
    std::set<size_t> dropLines;
    for (size_t k = 0; k < plan.parts.size(); ++k) {
        const auto& row = plan.parts[k];
        auto& pr = rep.parts[k];
        const long long pid = row.pid;
        switch (row.action) {
            case Action::Transform:
            case Action::Morph: {
                double maxd = 0;
                long long moved = 0;
                auto put = [&](int n, const Vector3D& y) {
                    const Vector3D x = M.getNode(n)->position;
                    modifiedNodePositions_[n] = y;
                    carry_.moved[n] = y;
                    carry_.movedPid[n] = pid;
                    maxd = std::max(maxd, (y - x).magnitude());
                    ++moved;
                };
                if (row.action == Action::Transform) {
                    const auto& m = row.m;
                    for (int n : nodesOf[pid]) {
                        const Vector3D x = M.getNode(n)->position;
                        put(n, Vector3D(m[0] * x.x + m[1] * x.y + m[2] * x.z + m[3], m[4] * x.x + m[5] * x.y + m[6] * x.z + m[7],
                                        m[8] * x.x + m[9] * x.y + m[10] * x.z + m[11]));
                    }
                } else {
                    const auto& f = fields.at(pid);
                    for (size_t i = 0; i < f.node.size(); ++i) {
                        const int n = static_cast<int>(f.node[i]);
                        const Vector3D x = M.getNode(n)->position;
                        put(n, Vector3D(x.x + f.disp[3 * i], x.y + f.disp[3 * i + 1], x.z + f.disp[3 * i + 2]));
                    }
                }
                pr.hasMove = true;
                pr.nodesMoved = moved;
                pr.maxDisp = maxd;
                pr.result = "applied";
                carry_.gates.push_back({pid, row.action, false, k});
                std::string secNote;
                if (auto sj = secJobs.find(k); sj != secJobs.end()) {
                    // 판 2 새 셸 섹션 — 그쪽 카드(옛 카드를 옮긴 것)를 *END 앞에 넣고 이 PID `*PART` 의 SECID 만 잇는다(답신 Q8 —
                    // 같은 섹션을 쓰는 다른 파트는 옛 섹션 그대로). 계획이 준 파일 이름은 한 줄로(주석 줄을 끊지 못하게)
                    const SecJob& j = sj->second;
                    const PartLoc& loc = partsMain.plain.at(pid);
                    std::ostringstream blk;
                    blk << "$\n$ === apply_carryover_plan — PID " << pid << " morph 새 셸 섹션 SECID " << j.secid << "(옛 SECID " << loc.secid
                        << ") · StepForge " << oneLine(j.file) << " ===\n";
                    for (const auto& l : j.scan.head) blk << l << "\n";
                    for (const auto& l : j.scan.block) blk << l << "\n";
                    addedKeywordBlocks_.push_back(blk.str());
                    putField(rawLines_[loc.cardLine], 1, loc.fieldW, j.secid);
                    carry_.newSecid[pid] = j.secid;
                    carry_.newShellT[j.secid] = j.thickness;
                    maxSectionId_ = std::max<long long>(maxSectionId_, j.secid);
                    pr.hasNewSection = pr.newSectionShell = true;
                    pr.newSecid = j.secid;
                    pr.newThickness = j.thickness;
                    secNote = " · 새 셸 섹션 SECID " + std::to_string(j.secid) + "(두께 " + num(j.thickness) + " · 옛 SECID " + std::to_string(loc.secid) + ")";
                }
                infoMessages.push_back(tag + "PID " + std::to_string(pid) + " " + row.actionText + " — 절점 " + std::to_string(moved) +
                                       " 개 · 최대 변위 " + num(maxd) + secNote);
                break;
            }
            case Action::Remesh: {
                const Job& j = *jobOfRow.at(k);
                const auto& h = *j.h;
                removePart(pid, pr);
                insertFragment(j, "PID " + std::to_string(pid) + " remesh(" + row.name + ")");
                pr.hasInserted = true;
                pr.insNodeLo = h.nodeLo + shiftNode;
                pr.insNodeHi = h.nodeHi + shiftNode;
                pr.insElemLo = h.elemLo + shiftElem;
                pr.insElemHi = h.elemHi + shiftElem;
                if (h.newSection.present) {
                    const PartLoc& loc = partsMain.plain.at(pid);
                    putField(rawLines_[loc.cardLine], 1, loc.fieldW, h.newSection.secid);   // *PART 의 SECID 만 잇는다(같은 섹션을 쓰는 다른 파트는 그대로)
                    carry_.newSecid[pid] = h.newSection.secid;
                    maxSectionId_ = std::max<long long>(maxSectionId_, h.newSection.secid);
                    pr.hasNewSection = true;
                    pr.newSecid = h.newSection.secid;
                    pr.newElform = h.newSection.elform;
                }
                pr.result = "applied";
                carry_.gates.push_back({pid, row.action, false, k});
                infoMessages.push_back(tag + "PID " + std::to_string(pid) + " remesh — 지움 요소 " + std::to_string(pr.removedElements) +
                                       " · 절점 " + std::to_string(pr.removedNodes) + " / 넣음 절점 " + std::to_string(pr.insNodeLo) + "~" +
                                       std::to_string(pr.insNodeHi) + " · 요소 " + std::to_string(pr.insElemLo) + "~" + std::to_string(pr.insElemHi) +
                                       (h.newSection.present ? " · 새 섹션 SECID " + std::to_string(h.newSection.secid) + "(ELFORM " +
                                                                   std::to_string(h.newSection.elform) + ")" : std::string()));
                break;
            }
            case Action::Delete: {
                removePart(pid, pr);
                const PartLoc& loc = partsMain.plain.at(pid);
                ++deletedPairs[loc.kwLine];
                carry_.deletedPids.insert(pid);
                pr.result = "applied";
                infoMessages.push_back(tag + "PID " + std::to_string(pid) + " delete — 요소 " + std::to_string(pr.removedElements) + " · 절점 " +
                                       std::to_string(pr.removedNodes) + " · *PART 카드(섹션 · 재질 카드는 남긴다)");
                break;
            }
            case Action::Keep:
            case Action::Review:
                pr.result = "skipped";
                break;
        }
    }
    // *PART 짝 지우기 — 블록의 짝을 다 지우면 블록째(키워드 · 주석까지), 아니면 그 짝(제목 · 사이 주석 · 카드)만
    for (const auto& row : plan.parts) {
        if (row.action != Action::Delete) continue;
        const PartLoc& loc = partsMain.plain.at(row.pid);
        const bool whole = deletedPairs[loc.kwLine] == loc.pairs;
        const size_t from = whole ? loc.kwLine : loc.titleLine, to = whole ? loc.blockEnd : loc.cardLine + 1;
        for (size_t i = from; i < to; ++i) dropLines.insert(i);
    }
    for (size_t k = 0; k < plan.added.size(); ++k) {
        const auto& a = plan.added[k];
        auto& ar = rep.added[k];
        auto it = jobOfAdded.find(k);
        if (it == jobOfAdded.end()) { ar.result = "skipped"; ar.why = a.why; continue; }
        const Job& j = *it->second;
        insertFragment(j, "새 파트 PID " + std::to_string(j.pid) + "(" + a.name + ")");
        carry_.addedParts[j.pid] = {j.h->secid, j.h->mid};
        if (j.h->newSection.present) maxSectionId_ = std::max<long long>(maxSectionId_, j.h->newSection.secid);
        maxPartId_ = std::max<long long>(maxPartId_, j.pid);
        carry_.gates.push_back({j.pid, Action::Remesh, true, k});
        ar.result = "applied";
        ar.why.clear();
        warn(j.pid, "new_part_material", "새 파트 " + a.name + "(PID " + std::to_string(j.pid) + ") — SECID " + std::to_string(j.h->secid) +
                                             " · MID " + std::to_string(j.h->mid) + " 를 가리킨다. 물성은 사람이 맞춘다(답신 Q7 — matswap · matdb)");
        infoMessages.push_back(tag + "새 파트 PID " + std::to_string(j.pid) + "(" + a.name + ") — 절점 " + std::to_string(j.h->nodeLo + shiftNode) + "~" +
                               std::to_string(j.h->nodeHi + shiftNode) + " · 요소 " + std::to_string(j.h->elemLo + shiftElem) + "~" +
                               std::to_string(j.h->elemHi + shiftElem));
    }
    if (!dropLines.empty()) {
        std::vector<std::string> kept;
        kept.reserve(rawLines_.size() - dropLines.size());
        for (size_t i = 0; i < rawLines_.size(); ++i)
            if (!dropLines.count(i)) kept.push_back(std::move(rawLines_[i]));
        rawLines_.swap(kept);
    }
    return true;
}

bool ModelAssembler::verifyCarryoverOutput(const std::string& deckPath, carryover::Report& rep) const {
    std::vector<Problem>& P = rep.problems;
    const size_t before = P.size();
    auto problem = [&](long long pid, const char* kind, const std::string& detail) { P.push_back({pid, kind, detail}); };
    auto finish = [&]() {
        if (P.size() == before) return true;
        for (auto& pr : rep.parts) {
            if (pr.result != "applied") continue;
            const bool own = std::any_of(P.begin() + static_cast<long>(before), P.end(), [&](const Problem& p) { return p.pid == pr.pid; });
            pr.result = own ? "refused" : "skipped";
        }
        for (auto& ar : rep.added) {
            if (ar.result != "applied") continue;
            const bool own = std::any_of(P.begin() + static_cast<long>(before), P.end(), [&](const Problem& p) { return p.pid == ar.pid; });
            ar.result = own ? "refused" : "skipped";
        }
        return false;
    };
    const Mesh& base = carry_.base ? *carry_.base : baseMesh_;   // 대조의 「앞」 — 인클루드 덱은 닫힘째 읽은 메시
    Mesh out;
    try {
        KFileReader reader;
        if (!carry_.includes) {
            out = reader.readFile(deckPath);
        } else {
            // 판 2 인클루드 덱 — 산출은 주 덱 옆에 있고 `*INCLUDE` 줄을 그대로 두었다. 산출의 닫힘이 대조한 닫힘(파일 · 바이트)과 같아야 하고
            // 그 닫힘째 다시 읽는다(LS-DYNA 가 그 산출을 읽는 꼴)
            std::vector<std::string> outLines;
            {
                std::ifstream f(deckPath, std::ios::binary);
                for (std::string l; std::getline(f, l);) {
                    if (!l.empty() && l.back() == '\r') l.pop_back();
                    outLines.push_back(std::move(l));
                }
            }
            const auto oc = include_closure::read(deckPath, outLines);
            const auto got = closureEntries(oc, deckPath);
            bool same = oc.complete() && oc.cycles.empty() && got.size() == carry_.includeList.size();
            for (size_t k = 0; same && k < got.size(); ++k)
                same = got[k].relpath == carry_.includeList[k].relpath && got[k].sha256 == carry_.includeList[k].sha256;
            if (!same) {
                problem(0, "verify", "쓴 덱의 *INCLUDE 닫힘이 입력 덱의 닫힘(deck.includes 와 대조한 것)과 다르다 — 산출이 다른 파일을 끌어온다");
                return finish();
            }
            std::string note;
            bool complete = true;
            out = reader.readFileWithIncludes(deckPath, &note, &complete);
            if (!complete) {
                problem(0, "verify", "쓴 덱을 인클루드 닫힘째 다시 읽지 못했다 — " + note);
                return finish();
            }
        }
    } catch (const std::exception& e) {
        problem(0, "verify", std::string("쓴 덱을 다시 읽지 못했다: ") + e.what());
        return finish();
    }
    Vector3D bmin, bmax;
    base.calculateBoundingBox(bmin, bmax);
    const double tol = 1e-6 * std::max(1.0, (bmax - bmin).magnitude());

    // ① 옮긴 절점 — 기대 자리(대각선의 1e-6 안)
    {
        std::map<long long, std::pair<long long, double>> bad;
        for (const auto& [n, y] : carry_.moved) {
            const Node* o = out.getNode(n);
            const double err = o ? (o->position - y).magnitude() : std::numeric_limits<double>::infinity();
            if (err <= tol) continue;
            auto& b = bad[carry_.movedPid.at(n)];
            ++b.first;
            b.second = std::max(b.second, err);
        }
        for (const auto& [pid, b] : bad)
            problem(pid, "verify", "옮긴 절점 " + std::to_string(b.first) + " 개가 쓴 덱에서 기대 자리에 없다(가장 먼 차 " + num(b.second) + " · 허용 " + num(tol) + ")");
    }
    // ② 지운 번호가 없다 · ③ 넣은 번호가 조각 좌표 · 절점으로 있다
    {
        long long n = 0, e = 0;
        for (int id : carry_.removedNodes) n += out.getNode(id) && !carry_.insertedNodes.count(id) ? 1 : 0;
        for (int id : carry_.removedElems) e += out.getElement(id) && !carry_.insertedElems.count(id) ? 1 : 0;
        if (n || e) problem(0, "verify", "지운 절점 " + std::to_string(n) + " · 요소 " + std::to_string(e) + " 개가 쓴 덱에 남았다");
        long long nodeBad = 0, elemBad = 0;
        for (const auto& [id, xyz] : carry_.insertedNodes) {
            const Node* o = out.getNode(static_cast<int>(id));
            if (!o || (o->position - Vector3D(xyz[0], xyz[1], xyz[2])).magnitude() > tol) ++nodeBad;
        }
        for (const auto& [id, ins] : carry_.insertedElems) {
            const Element* o = out.getElement(static_cast<int>(id));
            if (!o || o->partId != ins.pid) { ++elemBad; continue; }
            std::vector<long long> got;
            out.forEachElementNode(*o, [&](int v) { got.push_back(v); });
            std::sort(got.begin(), got.end());
            got.erase(std::unique(got.begin(), got.end()), got.end());
            if (got != ins.nodes) ++elemBad;
        }
        if (nodeBad || elemBad)
            problem(0, "verify", "넣은 절점 " + std::to_string(nodeBad) + " · 요소 " + std::to_string(elemBad) + " 개가 쓴 덱에서 조각과 다르다(없거나 좌표 · PID · 절점이 다르다)");
    }
    // ④ 손대지 않은 절점 — 좌표가 그대로다(바이트를 그대로 내보냈으니 읽은 값도 같아야 한다)
    {
        long long changed = 0;
        int first = 0;
        for (const auto& [id, nd] : base.nodes) {
            if (carry_.moved.count(id) || carry_.removedNodes.count(id)) continue;
            const Node* o = out.getNode(id);
            if (o && o->position.x == nd.position.x && o->position.y == nd.position.y && o->position.z == nd.position.z) continue;
            if (changed++ == 0) first = id;
        }
        if (changed) problem(0, "verify", "손대지 않을 절점 " + std::to_string(changed) + " 개가 쓴 덱에서 없거나 움직였다(첫 절점 " + std::to_string(first) + ")");
    }
    // ⑤ 파트별 요소 수 — 입력 − 지움 + 넣음
    {
        std::map<long long, long long> expect, got;
        for (const auto& [eid, e] : base.elements)
            if (!carry_.removedElems.count(eid)) ++expect[e.partId];
        for (const auto& [eid, ins] : carry_.insertedElems) {
            (void)eid;
            ++expect[ins.pid];
        }
        for (const auto& [eid, e] : out.elements) {
            (void)eid;
            ++got[e.partId];
        }
        std::set<long long> all;
        for (const auto& kv : expect) all.insert(kv.first);
        for (const auto& kv : got) all.insert(kv.first);
        for (long long pid : all) {
            const long long a = expect.count(pid) ? expect.at(pid) : 0, b = got.count(pid) ? got.at(pid) : 0;
            if (a != b) problem(pid, "verify", "요소 수 — 기대 " + std::to_string(a) + " · 쓴 덱 " + std::to_string(b));
        }
    }
    // ⑥ *PART — 지운 파트는 없고, 새 섹션을 이었고, 새 파트가 있다
    for (long long pid : carry_.deletedPids)
        if (out.parts.count(static_cast<int>(pid))) problem(pid, "verify", "지운 PID 의 *PART 가 쓴 덱에 남았다");
    for (const auto& [pid, sec] : carry_.newSecid) {
        auto it = out.parts.find(static_cast<int>(pid));
        if (it == out.parts.end() || it->second.sectionId != sec)
            problem(pid, "verify", "쓴 덱의 *PART 가 새 SECID " + std::to_string(sec) + " 를 가리키지 않는다");
    }
    // 판 2 — 모프가 넣은 새 셸 섹션이 쓴 덱에 그 두께로 있다(리더가 읽은 T1)
    for (const auto& [sec, t] : carry_.newShellT) {
        auto it = out.shellSections.find(static_cast<int>(sec));
        if (it == out.shellSections.end() || std::fabs(it->second.thickness - t) > 1e-9 * std::max(1.0, std::fabs(t)))
            problem(0, "verify", "쓴 덱에 새 셸 섹션 SECID " + std::to_string(sec) + "(두께 " + num(t) + ")이 없다");
    }
    for (const auto& [pid, ap] : carry_.addedParts) {
        auto it = out.parts.find(static_cast<int>(pid));
        if (it == out.parts.end() || it->second.sectionId != ap.secid || it->second.materialId != ap.mid)
            problem(pid, "verify", "새 파트의 *PART(SECID " + std::to_string(ap.secid) + " · MID " + std::to_string(ap.mid) + ")가 쓴 덱에 없다");
    }
    if (P.size() != before) return finish();   // 대조가 틀린 덱의 품질은 재지 않는다

    // ⑦ 품질 관문 — 새로 뒤집힌 솔리드(야코비안 ≤ 0) · 법선이 뒤집힌 셸(모프)
    std::map<long long, std::vector<const Element*>> inBefore, inAfter;
    {
        std::set<long long> gp;
        for (const auto& g : carry_.gates) gp.insert(g.pid);
        for (const auto& [eid, e] : base.elements) {
            (void)eid;
            if (gp.count(e.partId)) inBefore[e.partId].push_back(&e);
        }
        for (const auto& [eid, e] : out.elements) {
            (void)eid;
            if (gp.count(e.partId)) inAfter[e.partId].push_back(&e);
        }
    }
    for (const auto& g : carry_.gates) {
        long long ib = 0, ia = 0, fresh = 0, flipped = 0, solids = 0, shells = 0;
        const auto& olds = inBefore[g.pid];
        const auto& news = inAfter[g.pid];
        if (g.action == Action::Transform || g.action == Action::Morph) {
            for (const Element* pb : olds) {
                const Element& eb = *pb;
                const Element* ea = out.getElement(eb.id);
                if (!ea) continue;   // ⑤가 이미 말했다
                if (eb.type == ElementType::QUAD4) {
                    // 셸 법선은 모프에서만 견준다 — 옮기기는 det +1 강체라 뒤집을 수 없고, 세계 축으로 앞뒤 법선을 견주면 크게 돌린 셸이
                    // 「뒤집혔다」고 나왔다(리뷰 11-07 — 180° · 100° 회전)
                    if (g.action != Action::Morph) continue;
                    ++shells;
                    Vector3D nb, na;
                    const bool okB = shellNormal(base, eb, nb), okA = shellNormal(out, *ea, na);
                    if (okB && (!okA || nb.dot(na) < 0)) ++flipped;
                    continue;
                }
                ++solids;
                const bool b = solidInverted(base, eb), a = solidInverted(out, *ea);
                ib += b ? 1 : 0;
                ia += a ? 1 : 0;
                fresh += (a && !b) ? 1 : 0;
            }
        } else {
            // 바꿔 넣기 · 새 파트 — 새 요소는 전부 새것이다(옛 요소의 뒤집힘은 앞 값으로만 적는다)
            if (!g.added)
                for (const Element* pb : olds)
                    if (pb->type != ElementType::QUAD4 && solidInverted(base, *pb)) ++ib;
            for (const Element* pa : news) {
                if (pa->type == ElementType::QUAD4) continue;
                ++solids;
                if (solidInverted(out, *pa)) ++ia;
            }
            fresh = ia;
        }
        if (!g.added) {
            auto& pr = rep.parts[g.row];
            if (solids || ib) { pr.hasInverted = true; pr.invertedBefore = ib; pr.invertedAfter = ia; }
            if (shells) { pr.hasFlipped = true; pr.flipped = flipped; }
        }
        if (fresh)
            problem(g.pid, "quality_inverted", "새로 뒤집힌 솔리드 " + std::to_string(fresh) + " 개(야코비안 ≤ 0) — 덱을 쓰지 않는다(답신 Q5)");
        if (flipped)
            problem(g.pid, "quality_flipped", "법선이 뒤집힌(또는 넓이가 0 이 된) 셸 " + std::to_string(flipped) + " 개 — 덱을 쓰지 않는다(답신 Q5)");
    }
    return finish();
}

}  // namespace KooRemapper
