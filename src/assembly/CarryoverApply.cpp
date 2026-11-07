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
//   · 절점 칸을 다 읽지 못하는 요소 블록(리더가 담지 않는 솔리드 · 티쉘 변형 · 보 `_WARPAGE` · `_ELBOW` …)이나 EID 가 겹친 덱은
//     덱을 고치는 줄을 하나도 적용하지 않는다(리뷰 11-07)
//   · 조각 번호는 덱 바닥(`idMaxima` — 보 · 이산 · 질량 요소까지) 위여야 한다. 아래에 걸치면 조각 전부를 **한 이동량**으로 옮긴다
//   · 쓴 뒤 **다시 읽어** 대조하고 품질 관문(새로 뒤집힌 솔리드 · 모프가 법선을 뒤집은 셸)을 건다 — 걸리면 부르는 쪽이 산출을 지운다

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
};
struct PartIndex {
    std::map<long long, PartLoc> plain;
    std::set<long long> duplicate;
    std::vector<size_t> oddBlocks;          // 데이터 줄이 짝으로 안 떨어지는 블록의 키워드 줄
};

PartIndex indexParts(const std::vector<std::string>& L) {
    PartIndex idx;
    const auto blocks = cardcut::blocks(L);
    for (size_t b = 0; b < blocks.size(); ++b) {
        const auto& blk = blocks[b];
        if (blk.kw != "*PART" && blk.kw != "*PART_TITLE") continue;
        const size_t end = (b + 1 < blocks.size()) ? blocks[b + 1].kwLine : L.size();
        if (blk.data.size() % 2 != 0) idx.oddBlocks.push_back(blk.kwLine);
        for (size_t k = 0; k + 1 < blk.data.size(); k += 2) {
            const std::string& card = L[blk.data[k + 1]];
            const auto c = cardcut::cut(card, 10);
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
            if (!idx.plain.emplace(pid, loc).second) idx.duplicate.insert(pid);
        }
    }
    return idx;
}

// 리더(`KFileReader::parseFile`)가 보는 키워드 이름 — 0열 '*' 다음이 글자인 줄만 키워드 줄이고(isKeywordLine), 이름은 그 뒤
// 영숫자 · '_' · '-' 를 대문자로 모은 것이다(extractKeyword). 키워드 줄이 아니면 빈 글자.
std::string readerKeyword(const std::string& line) {
    if (line.size() < 2 || line[0] != '*' || !std::isalpha(static_cast<unsigned char>(line[1]))) return std::string();
    std::string kw;
    for (size_t i = 1; i < line.size(); ++i) {
        const unsigned char c = static_cast<unsigned char>(line[i]);
        if (!(std::isalnum(c) || c == '_' || c == '-')) break;
        kw += static_cast<char>(std::toupper(c));
    }
    return kw;
}

// 리더가 이 블록의 요소를 메시에 **그대로** 담는가 — 그 리더의 갈래를 옮긴다(KFileReader.cpp parseFile): ELEMENT_SOLID · _SOLID_TITLE ·
// ELEMENT_TSHELL · _TSHELL_TITLE 은 이름이 똑같을 때만, ELEMENT_SHELL 은 머리가 같고 `parseElementKeyword` 가 받는 변형일 때.
// 그 밖(`*ELEMENT_SOLID_ORTHO` · `_H20` · `_TET4TOTET10` · `*ELEMENT_TSHELL_BETA` …)은 리더가 통째로 건너뛴다 — 메시에 없다.
bool readerReadsGrid(const std::string& line) {
    const std::string kw = readerKeyword(line);
    if (kw == "ELEMENT_SOLID" || kw == "ELEMENT_SOLID_TITLE" || kw == "ELEMENT_TSHELL" || kw == "ELEMENT_TSHELL_TITLE") return true;
    return kw.rfind("ELEMENT_SHELL", 0) == 0 && parseElementKeyword(line).supported;
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
//   · 칸 자리를 아는 격자 밖 블록(`auxElementCard`) 가운데 옵션 카드에 절점이 없는 것 — 보의 `_WARPAGE`(SN1 · SN2) ·
//     `_ELBOW`(MN)는 그 카드를 읽지 않는다(Vol_I 156529-156610). Card 1 의 N3(방향 절점)은 읽는다
std::string elementBlockGap(const std::string& line) {
    const ElementKeywordInfo info = parseElementKeyword(line);
    if (info.family != ElemFamily::NONE) {
        if (!readerReadsGrid(line)) return info.supported ? "리더가 메시에 담지 않는 변형" : "카드 줄 수를 확정할 수 없는 변형";
        if (info.family == ElemFamily::SHELL && hasOption(info.keyword, "*ELEMENT_SHELL", "DOF"))
            return "DOF 카드의 스칼라 절점(NS1-NS4)을 읽지 않는다";
        return std::string();
    }
    // `*ELEMENT_MASS_PART(_SET)` 은 파트(세트)에 질량을 나눠 얹는 카드다 — 칸은 ID ADDMASS FINMASS LCID MWD 뿐, 절점 칸이 없다(Vol_I 160154)
    if (hasOption(info.keyword, "*ELEMENT_MASS", "PART")) return std::string();
    const AuxElementCard a = auxElementCard(line);
    if (a.family == AuxFamily::NONE) return "칸 자리를 모르는 요소 키워드";
    if (!a.supported) return "칸 자리를 확정할 수 없는 변형";
    if (a.family == AuxFamily::BEAM && hasOption(a.keyword, "*ELEMENT_BEAM", "WARPAGE")) return "WARPAGE 카드의 절점(SN1 · SN2)을 읽지 않는다";
    if (a.family == AuxFamily::BEAM && hasOption(a.keyword, "*ELEMENT_BEAM", "ELBOW")) return "ELBOW 카드의 가운데 절점(MN)을 읽지 않는다";
    return std::string();
}

// 리더가 담는 격자 요소 카드를 카드마다 한 번 — Card 1 줄과 그 칸. 카드 경계는 정본(`elementCardSpan`)이 정하고, 2차 솔리드의 절점
// 수는 리더가 담은 PID → ELFORM(`Mesh::partSolidElform`)에서 온다. 주석은 건너뛰고 빈 줄은 카드 안에서만 카드다.
struct GridCard {
    size_t line = 0;
    ElemFamily family = ElemFamily::NONE;
    const std::string* keyword = nullptr;
    std::vector<std::string> f;
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
            in = readerReadsGrid(l);
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

// 고정폭 10칸 하나를 제자리에서 바꾼다 — 다른 칸의 글자는 그대로(`extract_parts` putField 와 같은 꼴)
bool putField10(std::string& line, size_t idx, long long v) {
    char buf[32];
    if (std::snprintf(buf, sizeof(buf), "%10lld", v) != 10) return false;
    const size_t off = idx * 10;
    if (line.size() < off + 10) line.resize(off + 10, ' ');
    line.replace(off, 10, buf, 10);
    return true;
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

bool ModelAssembler::applyCarryoverPlan(const std::string& planPath, carryover::Report& rep) {
    namespace fs = std::filesystem;
    carry_ = CarryExpect{};
    std::vector<Problem>& P = rep.problems;
    auto problem = [&](long long pid, const char* kind, const std::string& detail) { P.push_back({pid, kind, detail}); };
    auto warn = [&](long long pid, const char* kind, const std::string& detail) { rep.warnings.push_back({pid, kind, detail}); };
    const std::string tag = "[apply_carryover_plan] ";

    // ── ① 덱 — 지문 · 폭 · 인클루드 ────────────────────────────────────────────
    {
        std::string bytes;
        if (!readBytes(baseModelPath_, bytes)) { problem(0, "deck_read", "덱을 다시 열지 못했다: " + baseModelPath_); return false; }
        rep.deckShaIn = util::sha256Hex(bytes);
    }
    const int fw = deckFieldWidth(rawLines_);
    if (fw == 20)
        problem(0, "deck_width", "long 폭 덱(*KEYWORD long=y)은 받지 않는다 — 조각의 좌표 글자를 그대로 둘 수 없고 쓰기 길이 20칸 꼴을 확정하지 않았다");
    {
        size_t first = 0, n = 0;
        for (size_t i = 0; i < rawLines_.size(); ++i) {
            if (deckscan::isDataLine(rawLines_[i])) continue;
            if (deckscan::kwBare(deckscan::keywordToken(rawLines_[i])).rfind("*INCLUDE", 0) == 0 && n++ == 0) first = i;
        }
        if (n)
            problem(0, "deck_include", "덱에 *INCLUDE 카드가 " + std::to_string(n) + " 장 있다(첫 줄 " + std::to_string(first + 1) +
                                           ") — 계획 v1 에는 deck.includes 가 없어 인클루드 닫힘을 지문으로 지킬 수 없다(답신 Q3)");
    }

    // ── ② 계획 — 엄격히 읽는다(칸 표 하나 · 걸린 것 전부) ────────────────────────
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
        rep.parts.push_back(pr);
        if (row.pid > 0) planPids.insert(row.pid);
        if (row.valid && row.action == Action::Keep && !row.touchesChanged.empty()) rep.touches.push_back({row.pid, row.touchesChanged});
    }
    for (const auto& a : plan.added) {
        carryover::AddedResult ar;
        ar.name = a.name;
        ar.hasPid = a.hasPid || (a.fragment.present && a.fragment.ok && a.fragment.pid > 0);
        ar.pid = a.hasPid ? a.pid : a.fragment.pid;
        rep.added.push_back(ar);
    }

    // ── ③ 동반 파일 — 계획 폴더 바로 아래 · 지문 ───────────────────────────────
    // 파일의 몫은 **줄이 정한다**(morph 의 field.file · remesh · 새 파트의 fragment.file) — 확장자로 가르면 `.k` 로 이름 지은 변위장이
    // 조각으로 읽혀 아무 문제도 남기지 않고 적용 단계에서 터졌다(리뷰 11-07). 변위장은 지문이 다르면 거절, 조각은 값으로 대조(⑧),
    // 어느 줄도 안 쓰는 파일은 경고만 한다(덱에 닿지 않는다).
    std::set<std::string> fieldFiles, fragmentFiles;
    for (const auto& row : plan.parts) {
        if (row.action == Action::Morph && row.field.built && !row.field.file.empty()) fieldFiles.insert(row.field.file);
        if (row.action == Action::Remesh && row.fragment.present && row.fragment.ok && !row.fragment.file.empty())
            fragmentFiles.insert(row.fragment.file);
    }
    for (const auto& a : plan.added)
        if (a.fragment.present && a.fragment.ok && !a.fragment.file.empty()) fragmentFiles.insert(a.fragment.file);
    for (const auto& n : fieldFiles)
        if (fragmentFiles.count(n)) problem(0, "plan_inconsistent", n + " 을 변위장과 조각이 함께 가리킨다 — 한 파일의 몫은 하나다");
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
        if (fieldFiles.count(fe.name)) problem(0, "file_mismatch", detail);   // 변위장 — 바이트가 곧 값이다
        else c.mismatch = detail;   // 조각은 값으로 대조한다(⑧) · 안 쓰는 파일은 경고(⑧ 끝)
    }
    // 줄이 가리키는 파일 — files 에 있어야 하고 머리의 bytes 가 files 의 bytes 와 같아야 한다(계획 안의 두 주장)
    std::set<std::string> usedFiles;   // 줄이 가리킨 동반 파일 — 바이트가 달랐는데 아무 줄도 안 쓴 조각은 값으로 못 대조했다고 말한다
    auto companion = [&](long long pid, const std::string& name, long long bytes, const char* what) -> const Companion* {
        usedFiles.insert(name);
        auto it = comp.find(name);
        if (it == comp.end()) {
            problem(pid, "file_unlisted", std::string(what) + " " + name + " 이 계획의 files 에 없다 — 지문으로 대조할 수 없다");
            return nullptr;
        }
        if (it->second.claimBytes != bytes)
            problem(pid, "plan_inconsistent", std::string(what) + " " + name + " 의 bytes " + std::to_string(bytes) + " 가 files 의 " +
                                                  std::to_string(it->second.claimBytes) + " 와 다르다");
        return it->second.exists ? &it->second : nullptr;
    };

    // ── ④ 덱 표 — *PART · 섹션 · 재질 · 격자 밖 요소 · 셸 중간절점 ─────────────────
    const PartIndex parts = indexParts(rawLines_);
    const auto variants = definedPartVariantIds();
    const auto sections = definedSectionIds();
    const auto mids = definedMaterialIds();
    for (size_t kwl : parts.oddBlocks)
        problem(0, "deck_part_block", "줄 " + std::to_string(kwl + 1) + " 의 *PART 블록 — 데이터 줄이 제목 · 카드 짝으로 떨어지지 않는다");
    std::vector<NonGridElementCard> auxCards;   // 칸 자리를 아는 격자 밖 요소(보 · 이산 · 질량 · 안전띠 · 플롯) — 나눠 쓴 절점 · EID 겹침이 본다
    forEachNonGridElementCard(rawLines_, [&](const NonGridElementCard& c) {
        if (c.known) auxCards.push_back(c);
    });
    // 절점 칸을 다 읽지 못하는 요소 블록 — 키워드마다 첫 줄 · 블록 수 · 까닭(`elementBlockGap`)
    struct Gap { size_t first = 0, blocks = 0; std::string why; };
    std::map<std::string, Gap> elemGaps;
    bool hasEnd = false;   // 넣을 블록은 쓰기가 *END 자리에 낸다(writeOutput — 대문자 머리 「*END」)
    for (size_t i = 0; i < rawLines_.size(); ++i) {
        if (!cardcut::isKeywordLine(rawLines_[i])) continue;
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(rawLines_[i]));
        hasEnd = hasEnd || kw.rfind("*END", 0) == 0;
        if (kw.rfind("*ELEMENT_", 0) != 0) continue;
        std::string why = elementBlockGap(rawLines_[i]);
        if (why.empty()) continue;
        Gap& g = elemGaps[kw];
        if (g.blocks++ == 0) { g.first = i; g.why = std::move(why); }
    }
    const auto midside = shellMidsideNodes(rawLines_, baseMesh_);
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
        baseMesh_.forEachElementNode(e, f);
        if (e.type != ElementType::QUAD4) return;
        auto it = midside.find(e.id);
        if (it != midside.end()) for (int n : it->second) f(n);
    };
    std::map<long long, std::vector<int>> elemsOf, nodesOf;
    {
        std::map<long long, std::set<int>> ns;
        for (const auto& [eid, e] : baseMesh_.elements) {
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
            list += (list.empty() ? "" : ", ") + kw + "(줄 " + std::to_string(g.first + 1) + " · 블록 " + std::to_string(g.blocks) + " · " + g.why + ")";
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
        forEachGridCard(rawLines_, baseMesh_, [&](const GridCard& c) { gridCards += deckscan::fieldInt(c.f, 0) > 0 ? 1 : 0; });
        eidSuspect = gridCards != baseMesh_.elements.size();
        std::unordered_set<int> auxSeen;
        for (const auto& c : auxCards)
            if (c.eid > 0 && (baseMesh_.elements.count(c.eid) || !auxSeen.insert(c.eid).second)) eidSuspect = true;
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
            const auto at = std::make_pair(ki.first->second, line);
            auto f = first.emplace(eid, at);
            if (f.second) return;
            auto& d = dup[eid];
            if (d.empty()) d.push_back(f.first->second);
            d.push_back(at);
        };
        forEachGridCard(rawLines_, baseMesh_, [&](const GridCard& c) { note(deckscan::fieldInt(c.f, 0), *c.keyword, c.line); });
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
                for (const auto& o : occ) where += (where.empty() ? "" : " · ") + kwNames[o.first] + " 줄 " + std::to_string(o.second + 1);
                list += (list.empty() ? "" : ", ") + ("EID " + std::to_string(eid) + "(" + where + ")");
            }
            problem(0, "eid_collision", "요소 번호가 겹친다 " + std::to_string(dup.size()) + " 개 — " + list + " · 키워드 " + join(kws) +
                                            " · 이 덱은 요소를 번호로 가를 수 없다(리더는 한쪽만 들고 쓰기는 지울 번호를 모든 요소 블록에서 지운다)");
        }
    }

    // ── ⑤ 줄마다 — 덱에 있나 · 처리별 검사 ────────────────────────────────────
    std::map<long long, carryover::Field> fields;
    std::set<long long> ready;   // 덱에서 찾았고 요소가 있는 고칠 PID
    for (const auto& row : plan.parts) {
        if (!row.valid) continue;
        const long long pid = row.pid;
        const bool plain = parts.plain.count(pid) != 0;
        const bool variant = variants.count(static_cast<int>(pid)) != 0;
        if (!plain && !variant) { problem(pid, "part_missing", "PID " + std::to_string(pid) + " 가 덱의 *PART 에 없다"); continue; }
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
        if (elemsOf[pid].empty()) {
            problem(pid, "part_empty", "PID 의 요소가 메시에 없다 — 리더가 읽지 못한 블록에 있을 수 있다");
            continue;
        }
        {
            std::vector<int> undefinedNodes;
            for (int n : nodesOf[pid])
                if (!baseMesh_.getNode(n)) undefinedNodes.push_back(n);
            if (!undefinedNodes.empty()) {
                problem(pid, "node_undefined", "PID 의 요소가 정의되지 않은 절점을 가리킨다 — " + idList(undefinedNodes));
                continue;
            }
        }
        {
            std::set<std::string> kinds;
            for (const auto& c : auxCards)
                if (c.pid == pid) kinds.insert(c.keyword);
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
                if (row.field.hasThickness)
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
            for (const auto& [eid, e] : baseMesh_.elements) {
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
        const auto nr = noderefs::find(rawLines_, fw, [&](int v) { return nodeOwner.count(v) != 0; });
        for (const auto& r : nr.refs) {
            auto& h = nodeHits[{nodeOwner.at(r.value), r.kwLine}];
            if (h.count++ == 0) { h.firstLine = r.line; h.kw = noderefs::keywordOf(rawLines_, r); }
            if (h.values.size() < 12) h.values.insert(r.value);
        }
        for (const auto& [key, h] : nodeHits)
            problem(key.first, "node_ref", h.kw + "(줄 " + std::to_string(key.second + 1) + ")이 이 PID 의 절점을 " + std::to_string(h.count) +
                                               " 곳 가리킨다(첫 줄 " + std::to_string(h.firstLine + 1) + " · 절점 " + idList(h.values, 10) +
                                               ") — 바꿔 넣거나 지우면 그 참조를 옮길 수 없다");
        std::map<std::tuple<long long, size_t, int>, Hit> idHits;
        const auto ir = idrefs::find(rawLines_, fw, [&](idrefs::Axis ax, int v) {
            return ax == idrefs::Axis::Elem ? elemOwner.count(v) != 0 : deletePids.count(v) != 0;
        });
        for (const auto& r : ir.refs) {
            const long long owner = r.axis == idrefs::Axis::Elem ? elemOwner.at(r.value) : r.value;
            auto& h = idHits[{owner, r.kwLine, r.axis == idrefs::Axis::Elem ? 0 : 1}];
            if (h.count++ == 0) { h.firstLine = r.line; h.kw = idrefs::keywordOf(rawLines_, r); }
            if (h.values.size() < 12) h.values.insert(r.value);
        }
        for (const auto& [key, h] : idHits) {
            const bool elem = std::get<2>(key) == 0;
            problem(std::get<0>(key), elem ? "elem_ref" : "part_ref",
                    h.kw + "(줄 " + std::to_string(std::get<1>(key) + 1) + ")이 이 PID 의 " + (elem ? "요소" : "PID") + "를 " +
                        std::to_string(h.count) + " 곳 가리킨다(첫 줄 " + std::to_string(h.firstLine + 1) +
                        (elem ? " · 요소 " + idList(h.values, 10) : std::string()) + ") — " +
                        (elem ? "바꿔 넣거나 지우면 그 참조를 옮길 수 없다" : "지우면 그 참조가 매달린다(PID 로 건 참조는 지우기를 막는다)"));
        }
        // 정본이 칸 뜻을 단정하지 못한 자리 — 칸 자리를 아는 격자 밖 요소 블록(⑥이 절점을 셌다)은 뺀다
        {
            std::vector<std::string> auxOnly;
            bool inAux = false;
            for (const auto& l : rawLines_) {
                const size_t g = l.find_first_not_of(" \t");
                if (g != std::string::npos && l[g] == '*') {
                    const AuxElementCard a = auxElementCard(l);
                    inAux = a.family != AuxFamily::NONE && a.supported;
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
            for (size_t i = 0; i < rawLines_.size(); ++i) {   // 키워드 줄만 본다(큰 *NODE 블록의 줄 표를 짓지 않는다)
                if (!cardcut::isKeywordLine(rawLines_[i])) continue;
                const std::string kw = deckscan::kwBare(deckscan::keywordToken(rawLines_[i]));
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
                        for (size_t d = i + 1; d < rawLines_.size() && !cardcut::isKeywordLine(rawLines_[d]); ++d) {
                            if (cardcut::isCommentLine(rawLines_[d])) continue;
                            const auto c = cardcut::cut(rawLines_[d], fw >= 20 ? 20 : 10);
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
                problem(0, "ref_unscanned", kw + "(줄 " + std::to_string(u.first + 1) + " · 블록 " + std::to_string(u.blocks) + ") — " +
                                                (u.partOnly ? std::string("파트 ID 칸을 정본이 읽지 않는다 · 지우는 PID 를 가리키지 않는다고 증명할 수 없다")
                                                            : std::string("절점 · 요소 · 파트 칸을 정본(NodeRefs · IdRefs)이 읽지 않고 참조 없는 키워드 표에도 없다 · "
                                                                          "바꿔 넣거나 지우는 PID 를 가리키지 않는다고 증명할 수 없다")));
        }
        // 접촉 면 — 세트로 건 면은 정본(`ct_setMembers`)으로 풀어 본다(방언 `_ADD` · `_GENERATE` … 까지)
        auto sets = ct_parseSets(rawLines_);
        ct_resolveSetRanges(sets, baseMesh_);
        for (const auto& c : ct_parseContacts(rawLines_)) {
            if (c.cardLine[0] < 0) continue;   // Card 1 이 없으면 정본이 단정하지 않았다고 이미 셌다
            const std::string where = c.fullKeyword + "(줄 " + std::to_string(c.startLine + 1) + ")";
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
            const std::string where = deckscan::kwBare(deckscan::keywordToken(rawLines_[static_cast<size_t>(s.startLine)])) + " " +
                                      std::to_string(s.id) + "(줄 " + std::to_string(s.startLine + 1) + ")";
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
            const PartLoc& loc = parts.plain.at(j.pid);
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
            if (!newSecids.insert(ns).second) fp.push_back("new_section.secid " + std::to_string(ns) + " 를 다른 조각도 쓴다");
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
                    const Vector3D x = baseMesh_.getNode(n)->position;
                    modifiedNodePositions_[n] = y;
                    carry_.moved[n] = y;
                    carry_.movedPid[n] = pid;
                    maxd = std::max(maxd, (y - x).magnitude());
                    ++moved;
                };
                if (row.action == Action::Transform) {
                    const auto& m = row.m;
                    for (int n : nodesOf[pid]) {
                        const Vector3D x = baseMesh_.getNode(n)->position;
                        put(n, Vector3D(m[0] * x.x + m[1] * x.y + m[2] * x.z + m[3], m[4] * x.x + m[5] * x.y + m[6] * x.z + m[7],
                                        m[8] * x.x + m[9] * x.y + m[10] * x.z + m[11]));
                    }
                } else {
                    const auto& f = fields.at(pid);
                    for (size_t i = 0; i < f.node.size(); ++i) {
                        const int n = static_cast<int>(f.node[i]);
                        const Vector3D x = baseMesh_.getNode(n)->position;
                        put(n, Vector3D(x.x + f.disp[3 * i], x.y + f.disp[3 * i + 1], x.z + f.disp[3 * i + 2]));
                    }
                }
                pr.hasMove = true;
                pr.nodesMoved = moved;
                pr.maxDisp = maxd;
                pr.result = "applied";
                carry_.gates.push_back({pid, row.action, false, k});
                infoMessages.push_back(tag + "PID " + std::to_string(pid) + " " + row.actionText + " — 절점 " + std::to_string(moved) +
                                       " 개 · 최대 변위 " + num(maxd));
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
                    const PartLoc& loc = parts.plain.at(pid);
                    putField10(rawLines_[loc.cardLine], 1, h.newSection.secid);   // *PART 의 SECID 만 잇는다(같은 섹션을 쓰는 다른 파트는 그대로)
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
                const PartLoc& loc = parts.plain.at(pid);
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
        const PartLoc& loc = parts.plain.at(row.pid);
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
    Mesh out;
    try {
        KFileReader reader;
        out = reader.readFile(deckPath);
    } catch (const std::exception& e) {
        problem(0, "verify", std::string("쓴 덱을 다시 읽지 못했다: ") + e.what());
        return finish();
    }
    Vector3D bmin, bmax;
    baseMesh_.calculateBoundingBox(bmin, bmax);
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
        for (const auto& [id, nd] : baseMesh_.nodes) {
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
        for (const auto& [eid, e] : baseMesh_.elements)
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
        for (const auto& [eid, e] : baseMesh_.elements) {
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
                    const bool okB = shellNormal(baseMesh_, eb, nb), okA = shellNormal(out, *ea, na);
                    if (okB && (!okA || nb.dot(na) < 0)) ++flipped;
                    continue;
                }
                ++solids;
                const bool b = solidInverted(baseMesh_, eb), a = solidInverted(out, *ea);
                ib += b ? 1 : 0;
                ia += a ? 1 : 0;
                fresh += (a && !b) ? 1 : 0;
            }
        } else {
            // 바꿔 넣기 · 새 파트 — 새 요소는 전부 새것이다(옛 요소의 뒤집힘은 앞 값으로만 적는다)
            if (!g.added)
                for (const Element* pb : olds)
                    if (pb->type != ElementType::QUAD4 && solidInverted(baseMesh_, *pb)) ++ib;
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
