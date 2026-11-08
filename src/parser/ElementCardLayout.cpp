// *ELEMENT_* 키워드 옵션을 매뉴얼 표대로 카드 줄 수로 바꾸는 판정기 (헤더의 인용 참조)
#include "parser/ElementCardLayout.h"

#include "parser/DeckScan.h"   // 카드 칸 읽기(cardFields · fieldInt) — 격자 밖 요소 걸음이 쓴다

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iterator>
#include <vector>

namespace KooRemapper {

namespace {

// 키워드 줄에서 칸 폭 접미사를 떼어 내고 키워드 토큰만 돌려준다.
// 매뉴얼이 정한 접미사는 '%'(i10) '+'(long) '-'(standard) 셋뿐이고, 매뉴얼 예시는
// "*NODE %" 처럼 공백을 두고 쓴다(19342-19348, 19356-19360) — 붙여 쓴 형태도 같이 받는다.
// 그 밖의 꼬리글(LS-PrePost 의 "(ten nodes format)" 같은 주석)은 매뉴얼에 없다 —
// 공백에서 잘라 버리고 줄 수·칸 폭 판정에는 절대 쓰지 않는다.
std::string stripKeyword(const std::string& line, bool* i10, bool* lng, bool* stdw) {
    size_t s = line.find_first_not_of(" \t");
    if (s == std::string::npos) return std::string();
    std::string kw = line.substr(s);
    while (!kw.empty() && (kw.back() == '\r' || kw.back() == '\n' || kw.back() == ' ' || kw.back() == '\t'))
        kw.pop_back();
    // 접미사는 줄 맨 끝에만 온다. 떼어 낸 나머지에 공백이 남으면 그건 꼬리글이지 접미사가 아니다.
    while (!kw.empty() && (kw.back() == '%' || kw.back() == '+' || kw.back() == '-')) {
        char suf = kw.back();
        std::string head = kw.substr(0, kw.size() - 1);
        while (!head.empty() && (head.back() == ' ' || head.back() == '\t')) head.pop_back();
        if (head.find_first_of(" \t") != std::string::npos) break;   // 꼬리글이 붙은 줄
        if (suf == '%' && i10)  *i10 = true;
        if (suf == '+' && lng)  *lng = true;
        if (suf == '-' && stdw) *stdw = true;
        kw = head;
    }
    size_t sp = kw.find_first_of(" \t");
    if (sp != std::string::npos) kw = kw.substr(0, sp);
    for (auto& c : kw) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return kw;
}

std::string normalizeKeyword(const std::string& line, ElementKeywordInfo& info) {
    return stripKeyword(line, &info.i10Suffix, &info.longSuffix, &info.stdSuffix);
}

// '_' 로 나눈 옵션 토큰들(키워드 본체 뒤)
std::vector<std::string> splitOptions(const std::string& kw, const std::string& base) {
    std::vector<std::string> out;
    if (kw.size() <= base.size()) return out;
    std::string rest = kw.substr(base.size());
    if (rest.empty() || rest[0] != '_') {
        out.push_back("<BAD>");    // *ELEMENT_SOLIDXYZ 처럼 붙어 있으면 옵션이 아니다
        return out;
    }
    size_t i = 1;
    while (i <= rest.size()) {
        size_t j = rest.find('_', i);
        if (j == std::string::npos) j = rest.size();
        if (j > i) out.push_back(rest.substr(i, j - i));
        i = j + 1;
    }
    return out;
}

}  // namespace

int solidNodesFromElform(int elform) {
    // Vol_I 228671-228677
    switch (elform) {
        // 10절점 사면체. 표에 없어서 `0`(= 모름) 으로 떨어졌는데 **사실과 다르다** —
        // 그래서 `restack` 이 TET10 파트를 '고차라 못 한다' 가 아니라 '유효한 압출이 아니다' 라는
        // **엉뚱한 까닭**으로 거절했다. 카드 폭은 그대로다: solidCardLines(10,·) = 2 + extra 이고
        // 등록 전 폴백도 2 + extra 였다(실측으로 덱 바이트가 바뀌지 않는다).
        case 16: return 10;   // 10-node tetrahedron
        case 17: return 10;   // 10-node composite tetrahedron
        case 23: return 20;   // 20-node solid
        case 24: return 27;   // 27-node solid
        case 25: return 21;   // 21-noded quadratic pentahedron
        case 26: return 15;   // 15-noded quadratic tetrahedron
        case 27: return 20;   // 20-noded cubic tetrahedron
        case 28: return 40;   // 40-noded cubic pentahedron
        case 29: return 64;   // 64-noded cubic hexahedron
        default: return 0;
    }
}

// *KEYWORD 줄의 i10 / long 옵션 (Vol_I 19305-19312, 19356-19360).
// "long=s" 는 표준을 읽고 long 으로 쓰라는 뜻이라 읽기 폭은 표준(8)이다(19308).
int keywordCardDeckWidth(const std::string& keywordLine) {
    std::string up = keywordLine;
    for (auto& c : up) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    if (up.find("*KEYWORD") == std::string::npos) return 0;
    auto optValue = [&](const char* name) -> char {
        size_t p = up.find(name);
        if (p == std::string::npos) return 0;
        p += std::string(name).size();
        while (p < up.size() && (up[p] == ' ' || up[p] == '\t')) ++p;
        if (p >= up.size() || up[p] != '=') return 'Y';       // 값 없이 쓴 형태는 켠 것으로 본다
        ++p;
        while (p < up.size() && (up[p] == ' ' || up[p] == '\t')) ++p;
        return p < up.size() ? up[p] : 'Y';
    };
    char lv = optValue("LONG");
    if (lv == 'Y' || lv == 'K') return 20;
    char iv = optValue("I10");
    if (iv && iv != 'N') return 10;
    if (lv == 'S') return 8;
    return 0;
}

int deckFieldWidth(const std::vector<std::string>& lines) {
    for (const auto& l : lines) {
        size_t s = l.find_first_not_of(" \t");
        if (s == std::string::npos || l[s] != '*') continue;
        int w = keywordCardDeckWidth(l);
        if (w > 0) return w;
        // *KEYWORD 가 아무 말도 안 했으면 표준이다. 다른 키워드는 건너뛴다.
        std::string up = l.substr(s, 8);
        for (auto& c : up) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (up == "*KEYWORD") return 8;
    }
    return 8;
}

bool hasKeywordCard(const std::vector<std::string>& lines) {
    for (const auto& l : lines) {
        size_t s = l.find_first_not_of(" \t");
        if (s == std::string::npos || l[s] != '*') continue;
        std::string up = l.substr(s, 8);
        for (auto& ch : up) ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
        if (up == "*KEYWORD") return true;
    }
    return false;
}

int keywordFieldWidth(const std::string& keywordLine, int deckFw) {
    bool i10 = false, lng = false, stdw = false;
    stripKeyword(keywordLine, &i10, &lng, &stdw);
    if (lng)  return 20;
    if (i10)  return 10;
    if (stdw) return 8;
    return deckFw > 0 ? deckFw : 8;
}

int realFieldWidth(int intFw) { return intFw >= 20 ? 20 : 16; }

int solidCardLines(int nodes, int extraCards) {
    if (nodes < 1) nodes = 8;
    int nodeCards = (nodes + 9) / 10;          // Card 2 + Card 3 반복 (163632-163634)
    if (nodeCards < 1) nodeCards = 1;
    return 1 + nodeCards + extraCards;
}

ElementKeywordInfo parseElementKeyword(const std::string& keywordLine) {
    ElementKeywordInfo info;
    std::string kw = normalizeKeyword(keywordLine, info);
    info.keyword = kw;
    if (kw.rfind("*ELEMENT_SOLID", 0) == 0)       info.family = ElemFamily::SOLID;
    else if (kw.rfind("*ELEMENT_TSHELL", 0) == 0) info.family = ElemFamily::TSHELL;
    else if (kw.rfind("*ELEMENT_SHELL", 0) == 0)  info.family = ElemFamily::SHELL;
    else { info.family = ElemFamily::NONE; return info; }

    const char* base = (info.family == ElemFamily::SOLID)  ? "*ELEMENT_SOLID"
                     : (info.family == ElemFamily::TSHELL) ? "*ELEMENT_TSHELL"
                                                           : "*ELEMENT_SHELL";
    auto opts = splitOptions(kw, base);

    auto unsupported = [&](const std::string& why) {
        info.supported = false;
        if (info.reason.empty()) info.reason = why;
    };

    for (const auto& o : opts) {
        if (o == "TITLE") continue;   // 이 저장소가 예전부터 받아 온 변형 — 카드 줄 수를 바꾸지 않는다
        if (info.family == ElemFamily::SOLID) {
            // 절점 수를 정하는 옵션 (163574-163587, 164055-164057)
            if      (o == "H20" || o == "T20") info.optionNodes = 20;
            else if (o == "T15")               info.optionNodes = 15;
            else if (o == "P21")               info.optionNodes = 21;
            else if (o == "H27")               info.optionNodes = 27;
            else if (o == "P40")               info.optionNodes = 40;
            else if (o == "H64")               info.optionNodes = 64;
            // 변환 옵션 — 덱에는 원래 4·8 절점 그대로다(Remark 1, 164017-164034)
            else if (o == "TET4TOTET10" || o == "H8TOH20" || o == "H8TOH27" || o == "H8TOH64") {}
            else if (o == "ORTHO") info.extraCards += 2;   // Card 4, Card 5 (163645-163656)
            else if (o == "DOF")   info.extraCards += 1;   // Card 6 (163657-163667)
            else unsupported("*ELEMENT_SOLID 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
        } else if (info.family == ElemFamily::SHELL) {
            if      (o == "THICKNESS" || o == "BETA" || o == "MCID") info.thicknessCard = true;
            else if (o == "OFFSET") info.extraCards += 1;  // Card 4 (162206-162219)
            else if (o == "DOF")    info.extraCards += 1;  // Card 5 (162243-162261)
            else if (o == "COMPOSITE" || o == "LONG") info.dataDependent = true;
            else if (o == "SHL4TOSHL8" || o == "SHL4" || o == "TO" || o == "SHL8") {}
            else unsupported("*ELEMENT_SHELL 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
        } else {   // TSHELL — 옵션은 셋뿐이다(165153-165157)
            if      (o == "BETA")      info.extraCards += 1;   // Card 2a (165185-165189)
            else if (o == "COMPOSITE") info.dataDependent = true;
            else unsupported("*ELEMENT_TSHELL 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
        }
    }

    if (info.dataDependent) {
        // 매뉴얼이 주는 종료 규칙은 '칸 4 가 0 이거나 빈칸'(162317/162354/165336-165337) 뿐이고
        // 그 규칙이 깨지는 경우를 말하지 않는다. 틀린 덱을 조용히 내보내는 대신 거절한다.
        unsupported("COMPOSITE 계열은 적층점 수에 따라 카드 줄 수가 달라집니다 —"
                    " 요소를 지우거나 새로 만드는 op 는 이 덱을 다루지 않습니다");
    }
    return info;
}

namespace {

int ecsInt(const std::vector<std::string>& f, size_t i) {
    if (i >= f.size() || f[i].empty()) return 0;
    const std::string& t = f[i];
    size_t p = (t[0] == '-' || t[0] == '+') ? 1u : 0u;
    if (p >= t.size()) return 0;
    for (size_t q = p; q < t.size(); ++q)
        if (!std::isdigit(static_cast<unsigned char>(t[q]))) return 0;
    try { return std::stoi(t); } catch (...) { return 0; }
}

// Card 1 의 칸 3-10 에 절점이 들어 있는가 — 구 포맷(164121-164158) 한 줄 카드의 표시다.
bool ecsLegacyOneLine(const std::vector<std::string>& f) {
    if (f.size() < 3) return false;
    for (size_t q = 2; q < f.size() && q < 10; ++q)
        if (ecsInt(f, q) > 0) return true;
    return false;
}

}  // namespace

ElementCardSpan elementCardSpan(const ElementKeywordInfo& info,
                                const std::vector<std::string>& f,
                                int pidNodeCount) {
    ElementCardSpan s;
    if (info.family == ElemFamily::SOLID) {
        int nodes = info.optionNodes;
        if (nodes == 0) nodes = pidNodeCount;
        if (nodes >= 11) {
            s.lines = solidCardLines(nodes, info.extraCards);   // Card 1 + 노드 카드 + 추가
            s.nodeFirst = 1;
            s.nodeLines = s.lines - 1 - info.extraCards;
            s.nodeFieldSkip = 0;
        } else if (nodes == 0 && ecsLegacyOneLine(f)) {
            s.lines = 1 + info.extraCards;                      // 구 포맷 — 절점이 Card 1 에 있다
            s.nodeFirst = 0;
            s.nodeLines = 1;
            s.nodeFieldSkip = 2;
        } else {
            s.lines = 2 + info.extraCards;                      // Card 1(EID·PID) + Card 2(절점)
            s.nodeFirst = 1;
            s.nodeLines = 1;
            s.nodeFieldSkip = 0;
        }
    } else if (info.family == ElemFamily::SHELL) {
        // 절점은 Card 1 에만 있다(EID,PID,N1..N4 와 중간절점 N5..N8). Card 2·3 은 두께다.
        s.lines = 1;
        if (info.thicknessCard) {
            s.lines += 1;
            bool midside = false;
            for (size_t q = 6; q < f.size() && q < 10; ++q)
                if (ecsInt(f, q) > 0) midside = true;
            if (midside) s.lines += 1;
        }
        s.lines += info.extraCards;
        s.nodeFirst = 0;
        s.nodeLines = 1;
        s.nodeFieldSkip = 2;
    } else {
        s.lines = 1 + info.extraCards;   // TSHELL — Card 1 은 언제나 N1..N8 한 줄(165174-165184)
        s.nodeFirst = 0;
        s.nodeLines = 1;
        s.nodeFieldSkip = 2;
    }
    if (s.nodeLines < 1) s.nodeLines = 1;
    return s;
}

// ── 보·질량·이산 족 (헤더의 인용 참조) ───────────────────────────────────────
//
// ★여기서 `supported=false` 를 내는 것은 "읽을 수 없다" 가 아니라 **"추측하지 않는다"** 다.
//   부르는 쪽(`cleanup-nodes`·`extract-parts`)은 그때 보수적으로 남기거나 거절한다.
AuxElementCard auxElementCard(const std::string& keywordLine) {
    AuxElementCard a;
    ElementKeywordInfo dummy;
    const std::string kw = normalizeKeyword(keywordLine, dummy);
    a.keyword = kw;
    if (kw.rfind("*ELEMENT_", 0) != 0) return a;
    // 격자 족은 `parseElementKeyword` 소관이다 — 두 판정기는 배타적이다.
    if (kw.rfind("*ELEMENT_SOLID", 0) == 0 || kw.rfind("*ELEMENT_SHELL", 0) == 0 ||
        kw.rfind("*ELEMENT_TSHELL", 0) == 0)
        return a;

    const char* base = nullptr;
    if      (kw.rfind("*ELEMENT_BEAM", 0) == 0)     { a.family = AuxFamily::BEAM;     base = "*ELEMENT_BEAM"; }
    else if (kw.rfind("*ELEMENT_DISCRETE", 0) == 0) { a.family = AuxFamily::DISCRETE; base = "*ELEMENT_DISCRETE"; }
    else if (kw.rfind("*ELEMENT_MASS", 0) == 0)     { a.family = AuxFamily::MASS;     base = "*ELEMENT_MASS"; }
    else if (kw.rfind("*ELEMENT_SEATBELT", 0) == 0) { a.family = AuxFamily::SEATBELT; base = "*ELEMENT_SEATBELT"; }
    else if (kw.rfind("*ELEMENT_PLOTEL", 0) == 0)   { a.family = AuxFamily::PLOTEL;   base = "*ELEMENT_PLOTEL"; }
    else return a;                                  // 그 밖 변형은 이 축도 모른다

    const auto opts = splitOptions(kw, base);
    auto unsupported = [&](const std::string& why) {
        a.supported = false;
        if (a.reason.empty()) a.reason = why;
    };
    a.supported = true;

    switch (a.family) {
        case AuxFamily::BEAM:
            // Card 1 = EID PID N1 N2 N3 RT1 RR1 RT2 RR2 LOCAL — 절점은 셋**만**이다.
            a.nodeSkip = 2; a.nodeCount = 3;
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                if (o == "PULLEY" || o == "SOURCE") {
                    // 보 요소가 아니라 **다른 키워드**다 — 8칸 표(I10)이고 PID 칸이 없다(156795 PUID BID1 BID2 PNID FD FS LMIN DC ·
                    // 156905 BSID BSNID BSEID NELE …). 칸 1(BID1 · BSNID)을 PID 로 읽지 않는다 — 보 요소 번호 칸만 적는다
                    a.hasPart = false;
                    a.partField = -1;
                    a.nodeCount = 0;
                    a.elemRefFields = (o == "PULLEY") ? std::vector<int>{1, 2} : std::vector<int>{2};
                    unsupported("*ELEMENT_BEAM_" + o + " 은 별개 키워드이고 PID 칸이 없습니다");
                    break;
                }
                if (o == "THICKNESS" || o == "SCALAR" || o == "SCALR" || o == "SECTION" ||
                    o == "PID" || o == "OFFSET" || o == "ORIENTATION" || o == "WARPAGE" ||
                    o == "ELBOW")
                    a.lines += 1;                   // 옵션마다 카드 한 장
                else
                    unsupported("*ELEMENT_BEAM 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
            }
            // 옵션 카드는 설명서 차례(Card 2 … 10)로 온다 — `_ELBOW` 의 Card 10(MN · 가운데 절점)은 늘 마지막 줄, `_WARPAGE` 의
            // Card 9(SN1 · SN2 — 스칼라 절점)는 그 앞(ELBOW 가 없으면 마지막) 줄이다
            if (a.supported && a.hasPart) {
                const bool elbow = std::find(opts.begin(), opts.end(), "ELBOW") != opts.end();
                const bool warp = std::find(opts.begin(), opts.end(), "WARPAGE") != opts.end();
                if (warp) a.optNodes.push_back({a.lines - 1 - (elbow ? 1 : 0), {0, 1}});
                if (elbow) a.optNodes.push_back({a.lines - 1, {0}});
            }
            break;
        case AuxFamily::DISCRETE:
            // Card 1 = EID PID N1 N2 VID S PF OFFSET
            a.nodeSkip = 2; a.nodeCount = 2;
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                if (o == "LCO") a.lines += 1;       // "If the LCO option is active, a second card is read"
                else unsupported("*ELEMENT_DISCRETE 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
            }
            break;
        case AuxFamily::MASS: {
            // Card 1 = EID(I8) ID(I8) MASS(E16) PID(I8) (159866-159930). ⚠ PID 는 칸 차례 **3** 이다(칸 1 이 아니다) —
            // MASS 가 넓은 칸이라 8칸으로 자르면 33-40열(칸 4)이다. 그 차례는 `auxCardReadings` 가 자른다.
            a.nodeSkip = 1; a.nodeCount = 1;
            a.partField = 3;
            a.wideFields = {2};
            a.card1Fields = 4;
            const bool part = std::find(opts.begin(), opts.end(), "PART") != opts.end();
            if (part) {
                // `_PART(_SET)` — 파트(세트)에 질량을 얹는 카드다. Card 1 = ID(I8) ADDMASS(F16) FINMASS(F16) LCID(I8) MWD(I8)
                // (160135-160207) — 칸 0 이 PID(`_SET` 이면 파트 세트 ID)이고 요소 번호 · 절점 칸이 없다
                a.nodeSkip = -1; a.nodeCount = 0;
                a.partField = 0;
                a.wideFields = {1, 2};
                a.card1Fields = 5;
                a.hasEid = false;
            }
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                if (part && o == "PART") continue;
                if (part && o == "SET") { a.partIsSet = true; continue; }
                // `_NODE_SET` 은 칸 1 이 **절점 세트 ID** 다 — 절점으로 읽으면 엉뚱한 절점을
                // 지키고 세트 멤버는 놓친다. 추측하지 않는다.
                if (o == "NODE" || o == "SET")
                    unsupported("*ELEMENT_MASS_NODE_SET 은 칸 1 이 절점이 아니라 **절점 세트 ID** 입니다");
                else
                    unsupported("*ELEMENT_MASS 의 옵션 '" + o + "' 은 칸 뜻을 확정할 수 없습니다");
            }
            break;
        }
        case AuxFamily::SEATBELT:
            // Card 1 = EID PID N1 N2 SBRID(I8 다섯) SLEN(F16) N3 N4(I8) (160311-160353) — 절점이 **두 구간**이다(칸 차례 2·3 · 6·7).
            // SLEN 이 넓은 칸이라 N3 · N4 는 57-64 · 65-72열이다(8칸으로 자르면 칸 7·8). 그 차례는 `auxCardReadings` 가 자른다.
            a.nodeSkip = 2; a.nodeCount = 2;
            a.nodeSkip2 = 6; a.nodeCount2 = 2;
            a.wideFields = {5};
            a.card1Fields = 8;
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                // `_ACCELEROMETER`·`_PRETENSIONER`·`_RETRACTOR`·`_SENSOR`·`_SLIPRING` 은 변형이 아니라 **다른 키워드**다 —
                // 10칸 폭 표이고 PID 칸이 없다(160482 · 160602 · 160931 · 161342 · 161725). 칸 자리를 짐작하지 않는다.
                a.hasPart = false;
                a.partField = -1;
                a.nodeCount = 0; a.nodeSkip2 = -1; a.nodeCount2 = 0;
                a.wideFields.clear();
                a.card1Fields = 0;
                unsupported("*ELEMENT_SEATBELT_" + o + " 은 별개 키워드이고 칸 배치가 다릅니다");
            }
            break;
        case AuxFamily::PLOTEL:
            // Card 1 = EID N1 N2 — **PID 칸이 없다**.
            a.nodeSkip = 1; a.nodeCount = 2;
            a.hasPart = false;
            a.partField = -1;
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                unsupported("*ELEMENT_PLOTEL 의 옵션 '" + o + "' 은 확정할 수 없습니다");
            }
            break;
        default:
            break;
    }
    return a;
}

namespace {

// 정수 칸 글자 — 부호와 숫자뿐(자리 수는 보지 않는다 · i10 의 열 자리 번호도 꼴로는 정수다)
bool isIntText(const std::string& s) {
    size_t i = (!s.empty() && (s[0] == '+' || s[0] == '-')) ? 1 : 0;
    if (i >= s.size()) return false;
    for (; i < s.size(); ++i)
        if (!std::isdigit(static_cast<unsigned char>(s[i]))) return false;
    return true;
}

// 실수 칸 글자 — 부호 · 소수점 · 지수(E · D · 글자 없이 부호 — 「1.0-3」). 정수도 실수다
bool isRealText(const std::string& s) {
    size_t i = 0;
    const size_t n = s.size();
    if (i < n && (s[i] == '+' || s[i] == '-')) ++i;
    bool digits = false, dot = false;
    for (; i < n; ++i) {
        const char c = s[i];
        if (std::isdigit(static_cast<unsigned char>(c))) { digits = true; continue; }
        if (c == '.' && !dot) { dot = true; continue; }
        break;
    }
    if (!digits) return false;
    if (i == n) return true;
    const char c = s[i];
    if (c == 'E' || c == 'e' || c == 'D' || c == 'd') ++i;
    else if (c != '+' && c != '-') return false;
    if (i < n && (s[i] == '+' || s[i] == '-')) ++i;
    const size_t d0 = i;
    while (i < n && std::isdigit(static_cast<unsigned char>(s[i]))) ++i;
    return i == n && i > d0;
}

bool hasInnerBlank(const std::string& s) { return s.find_first_of(" \t") != std::string::npos; }

// 소비자가 쓰는 칸(EID · PID · 절점 칸 — 카드 안) — 이 칸만 깨끗하면 manual 이 깨끗하다(헤더 「읽기들」)
bool usedFieldsClean(const AuxElementCard& a, const std::vector<std::string>& f) {
    auto bad = [&](int k) { return k >= 0 && static_cast<size_t>(k) < f.size() && hasInnerBlank(f[static_cast<size_t>(k)]); };
    if (a.hasEid && bad(0)) return false;
    if (a.hasPart && bad(a.partField)) return false;
    for (int q = 0; a.nodeSkip >= 0 && q < a.nodeCount; ++q)
        if (bad(a.nodeSkip + q)) return false;
    for (int q = 0; a.nodeSkip2 >= 0 && q < a.nodeCount2; ++q)
        if (bad(a.nodeSkip2 + q)) return false;
    return true;
}

// 다른 읽기(정수 폭) 가 「그 줄을 그렇게 썼을 수 있는」 읽기인가 — 헤더의 규칙 (a)-(d). `manualDoubtful` 이면(설명서 칸 하나에 빈칸이
// 낀다 — 설명서 꼴로 쓴 줄이 아닐 수 있다) (c) 는 보지 않는다(정수 폭으로 쓴 N3 만 있는 줄도 그 N3 을 지킨다)
bool altReadingValid(const AuxElementCard& a, const std::vector<std::string>& f, size_t contentLen, int fw, bool manualDoubtful) {
    if (a.card1Fields <= 0 || fw <= 0) return false;
    const size_t n = static_cast<size_t>(a.card1Fields);
    if (contentLen > n * static_cast<size_t>(fw)) return false;                         // (b)
    for (size_t k = n; k < f.size(); ++k)
        if (!f[k].empty()) return false;                                                // 카드 칸 밖에 글자
    for (size_t k = 0; k < n && k < f.size(); ++k) {                                    // (a)
        const std::string& t = f[k];
        if (t.empty()) continue;
        if (hasInnerBlank(t)) return false;
        const bool real = std::find(a.wideFields.begin(), a.wideFields.end(), static_cast<int>(k)) != a.wideFields.end();
        if (real ? !isRealText(t) : !isIntText(t)) return false;
    }
    if (!manualDoubtful && a.family == AuxFamily::SEATBELT && a.nodeSkip2 >= 0 && a.nodeCount2 == 2) {     // (c)
        const int n3 = deckscan::fieldInt(f, static_cast<size_t>(a.nodeSkip2));
        const int n4 = deckscan::fieldInt(f, static_cast<size_t>(a.nodeSkip2 + 1));
        if ((n3 > 0) != (n4 > 0)) return false;
    }
    if (a.family == AuxFamily::MASS && a.hasEid && (f.size() <= 2 || f[2].empty())) return false;   // (d)
    return true;
}

// manual 과 든 다른 읽기 — 차례대로(manual 먼저)
std::vector<const std::vector<std::string>*> usedReadings(const AuxCardReadings& r) {
    std::vector<const std::vector<std::string>*> out{&r.manual.f};
    if (r.plainAlt) out.push_back(&r.plain.f);
    return out;
}

}  // namespace

AuxCardReadings auxCardReadings(const AuxElementCard& a, const std::string& line, int fw) {
    AuxCardReadings r;
    std::string body = line;
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    // 줄의 끝 — 꼬리 `$…` 주석과 꼬리 공백을 뺀다(주석이 칸을 더럽히거나 줄을 카드 폭 밖으로 늘리지 않게 · 재검토 결정 (b))
    const size_t cmt = body.find('$');
    r.commentAt = cmt;
    if (cmt != std::string::npos) body.erase(cmt);
    while (!body.empty() && (body.back() == ' ' || body.back() == '\t')) body.pop_back();
    r.contentLen = body.size();
    if (body.find(',') != std::string::npos) {               // 자유형식 — 콤마 토큰이 곧 칸 차례 · 열 자리 없음
        r.comma = true;
        r.manual.f = deckscan::cardFields(body, fw);
        r.manualClean = std::none_of(r.manual.f.begin(), r.manual.f.end(), hasInnerBlank);
        r.plain = r.manual;
        return r;
    }
    // 고정폭 — 열로 자른다(LS-DYNA 가 읽는 칸 — 카드 폭 뒤 글자는 읽지 않는다). 칸 안에 공백이 끼어도 자르기는 그대로 둔다
    const size_t rw = static_cast<size_t>(realFieldWidth(fw));
    auto cut = [&](bool wideAware, AuxCardCut& t) {
        for (size_t pos = 0, q = 0; pos < body.size(); ++q) {
            const bool wide = wideAware &&
                              std::find(a.wideFields.begin(), a.wideFields.end(), static_cast<int>(q)) != a.wideFields.end();
            const size_t w = wide ? rw : static_cast<size_t>(fw);
            t.f.push_back(deckscan::trim(body.substr(pos, w)));
            t.col.push_back(pos);
            t.width.push_back(w);
            pos += w;
        }
    };
    cut(true, r.manual);
    // 깨끗함은 소비자가 쓰는 칸만 — 카드 폭 뒤 글자(「belt left 1」) · 쓰지 않는 칸의 빈칸(SLEN 「- 1.5」 · MASS 「1.0 E-03」)은
    // manual 을 흐리지 않는다(예전엔 줄 전체를 보아 공백 토큰이 manual 을 갈음했다 — 절점 103 · 질량을 버렸다, 2026-11-08)
    r.manualClean = usedFieldsClean(a, r.manual.f);
    if (a.wideFields.empty()) {
        r.plain = r.manual;
        return r;
    }
    cut(false, r.plain);
    // 다른 읽기 — 정수 폭이 규칙 (a)-(d)를 지킬 때만 든다. 넓은 칸이 없는 족은 plain 이 manual 이라 다른 읽기가 없다
    const size_t n = static_cast<size_t>(std::max(a.card1Fields, 0));
    bool doubtful = false;
    for (size_t k = 0; k < n && k < r.manual.f.size(); ++k) doubtful = doubtful || hasInnerBlank(r.manual.f[k]);
    r.plainAlt = altReadingValid(a, r.plain.f, r.contentLen, fw, doubtful);
    return r;
}

const std::vector<std::string>& auxPrimaryFields(const AuxCardReadings& r) { return r.manual.f; }

std::vector<int> auxNodesOf(const AuxElementCard& a, const std::vector<std::string>& f) {
    std::vector<int> out;
    auto take = [&](int from, int cnt) {
        for (int q = 0; from >= 0 && q < cnt; ++q) {
            const int v = deckscan::fieldInt(f, static_cast<size_t>(from + q));
            if (v > 0) out.push_back(v);
        }
    };
    take(a.nodeSkip, a.nodeCount);
    take(a.nodeSkip2, a.nodeCount2);
    return out;
}

std::vector<int> auxNodesUnion(const AuxElementCard& a, const AuxCardReadings& r) {
    std::vector<int> out;
    for (const auto* f : usedReadings(r))
        for (int v : auxNodesOf(a, *f)) out.push_back(v);
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return out;
}

std::vector<int> auxNodesAlt(const AuxElementCard& a, const AuxCardReadings& r, const std::vector<std::string>& base) {
    std::vector<int> b = auxNodesOf(a, base);
    std::sort(b.begin(), b.end());
    std::vector<int> out;
    for (int v : auxNodesUnion(a, r))
        if (!std::binary_search(b.begin(), b.end(), v)) out.push_back(v);
    return out;
}

std::vector<int> auxNodesDisputed(const AuxElementCard& a, const AuxCardReadings& r) {
    return auxNodesAlt(a, r, r.manual.f);
}

std::vector<int> auxNodesSure(const AuxElementCard& a, const AuxCardReadings& r) {
    auto sorted = [&](const std::vector<std::string>& f) {
        std::vector<int> v = auxNodesOf(a, f);
        std::sort(v.begin(), v.end());
        v.erase(std::unique(v.begin(), v.end()), v.end());
        return v;
    };
    const std::vector<int> m = sorted(r.manual.f);
    if (!r.plainAlt) return m;
    const std::vector<int> p = sorted(r.plain.f);
    std::vector<int> out;
    std::set_intersection(m.begin(), m.end(), p.begin(), p.end(), std::back_inserter(out));
    return out;
}

std::vector<int> auxNodesUnsure(const AuxElementCard& a, const AuxCardReadings& r) {
    const std::vector<int> s = auxNodesSure(a, r);
    std::vector<int> out;
    for (int v : auxNodesUnion(a, r))
        if (!std::binary_search(s.begin(), s.end(), v)) out.push_back(v);
    return out;
}

bool auxManualNodesPlaceable(const AuxElementCard& a, const AuxCardReadings& r) {
    if (r.comma || !r.manualClean) return false;   // manual 이 깨끗하지 않으면 LS-DYNA 가 읽는 칸 자체가 쓴 꼴과 다르다
    auto ok = [&](int from, int cnt) {
        for (int q = 0; from >= 0 && q < cnt; ++q) {
            const size_t k = static_cast<size_t>(from + q);
            if (k >= r.manual.f.size() || r.manual.f[k].empty()) continue;
            int v = 0;
            if (!cards::toInt(r.manual.f[k], v)) return false;
            if (v <= 0) continue;   // 번호가 아니다(0) — 바꿔 쓰지 않으니 주석과 겹쳐도 된다
            if (r.commentAt != std::string::npos && r.manual.col[k] + r.manual.width[k] > r.commentAt) return false;   // 주석과 겹친다
        }
        return true;
    };
    return ok(a.nodeSkip, a.nodeCount) && ok(a.nodeSkip2, a.nodeCount2);
}

int auxOptTableWidth(int fw) { return fw >= 20 ? 20 : 10; }

const std::vector<int>* auxOptNodeFields(const AuxElementCard& a, int cardLine) {
    if (cardLine <= 0) return nullptr;
    for (const auto& o : a.optNodes)
        if (o.line == cardLine) return &o.fields;
    return nullptr;
}

bool auxOptNodesPlaceable(const AuxElementCard& a, int cardLine, const std::string& line, int fw) {
    const std::vector<int>* fields = auxOptNodeFields(a, cardLine);
    if (!fields) return true;
    std::string body = line;
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    const size_t cmt = body.find('$');
    if (cmt != std::string::npos) body.erase(cmt);
    if (body.find(',') != std::string::npos) return false;   // 콤마 자유형식 — 칸 자리가 없다
    const size_t w = static_cast<size_t>(auxOptTableWidth(fw));
    for (int q : *fields) {
        const size_t c0 = static_cast<size_t>(q) * w;
        std::string t = c0 < body.size() ? body.substr(c0, w) : std::string();
        const size_t b0 = t.find_first_not_of(" \t");
        if (b0 == std::string::npos) continue;
        t = t.substr(b0, t.find_last_not_of(" \t") - b0 + 1);
        int v = 0;
        if (t.find_first_of(" \t") != std::string::npos || !cards::toInt(t, v)) return false;   // 칸 안에 빈칸 · 정수가 아니다
        if (v <= 0) continue;
        if (cmt != std::string::npos && c0 + w > cmt) return false;   // `$` 주석이 그 칸 안에서 시작한다 — 새 번호가 주석 머리를 덮는다
    }
    return true;
}

std::vector<int> auxOptNodesOf(const AuxElementCard& a, int cardLine, const std::string& line, int fw) {
    std::vector<int> out;
    const std::vector<int>* fields = auxOptNodeFields(a, cardLine);
    if (!fields) return out;
    std::string body = line;
    const size_t cmt = body.find('$');
    if (cmt != std::string::npos) body.erase(cmt);
    const auto f = deckscan::cardFields(body, auxOptTableWidth(fw));
    for (int q : *fields) {
        const int v = deckscan::fieldInt(f, static_cast<size_t>(q));
        if (v > 0) out.push_back(v);
    }
    return out;
}

std::vector<int> auxPidsOf(const AuxElementCard& a, const AuxCardReadings& r) {
    std::vector<int> out;
    if (!a.hasPart || a.partField < 0) return out;
    const size_t pf = static_cast<size_t>(a.partField);
    for (const auto* f : usedReadings(r)) {   // primary 먼저 — 언제나 든다(예전엔 primary 가 plain 이면 건너뛰었다)
        const int v = deckscan::fieldInt(*f, pf);
        if (v > 0 && std::find(out.begin(), out.end(), v) == out.end()) out.push_back(v);
    }
    return out;
}

bool gridReaderReadsKeyword(const std::string& keywordLine) {
    // 리더의 키워드 줄 규칙 그대로 — 0열이 `*` 이고 그다음이 글자인 줄만(`KFileReader::isKeywordLine`). 들여쓴 `*` 줄은 리더에게
    // 키워드가 아니라 앞 블록의 데이터다 — 여기서 너그러우면 그 블록을 「리더가 담았다」 고 보고 아무도 안 본다(11-07).
    // 이름은 `KFileReader::extractKeyword` 와 같은 토큰 — `*` 뒤 영숫자 · `_` · `-` 를 대문자로(접미사 `%`·`+` 와 공백에서 멈춘다)
    if (keywordLine.size() < 2 || keywordLine[0] != '*' ||
        !std::isalpha(static_cast<unsigned char>(keywordLine[1]))) return false;
    std::string k;
    for (size_t i = 1; i < keywordLine.size(); ++i) {
        const unsigned char ch = static_cast<unsigned char>(keywordLine[i]);
        if (!std::isalnum(ch) && ch != '_' && ch != '-') break;
        k += static_cast<char>(std::toupper(ch));
    }
    if (k == "ELEMENT_SOLID" || k == "ELEMENT_SOLID_TITLE" || k == "ELEMENT_TSHELL" || k == "ELEMENT_TSHELL_TITLE")
        return true;
    // 셸 분기는 줄 수를 확정하지 못하는 변형(COMPOSITE 계열)을 통째로 건너뛴다(`parseElementShellSection`)
    if (k.rfind("ELEMENT_SHELL", 0) == 0) return parseElementKeyword(keywordLine).supported;
    return false;
}

void forEachNonGridElementCard(const std::vector<std::string>& lines,
                               const std::function<void(const NonGridElementCard&)>& f) {
    const int deckFw = deckFieldWidth(lines);
    bool in = false;            // 격자 리더가 담지 않는 *ELEMENT_ 블록 안
    AuxElementCard aux;         // 격자 밖 족(보 · 질량 …) — 격자 변형이면 기본값(supported=false)
    ElementKeywordInfo grid;    // 리더가 안 읽는 격자 변형
    bool gridKnown = false;     // 그 변형의 카드 줄 수가 PID 에 달리지 않는다(헤더 참조)
    std::string kw;
    int fw = deckFw;
    int remaining = 0;          // 칸 자리를 아는 카드의 남은 줄
    // 격자 변형 카드는 절점이 여러 줄에 있어 카드가 끝날 때 넘긴다(카드가 모자라게 끝나도 넘긴다 — EID 를 잃지 않는다)
    NonGridElementCard pend;
    bool pending = false;
    ElementCardSpan span;
    int lineIdx = 0;
    auto flush = [&]() {
        if (pending) f(pend);
        pending = false;
    };
    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string& l = lines[i];
        const size_t g = l.find_first_not_of(" \t");
        if (deckscan::isKeywordLine(l)) {   // 1열 규칙(리더와 같다) — 들여쓴 `*` 줄은 앞 블록의 데이터다
            flush();
            in = false;
            remaining = 0;
            const ElementKeywordInfo info = parseElementKeyword(l);
            if (info.keyword.rfind("*ELEMENT_", 0) != 0) continue;
            if (info.family != ElemFamily::NONE && gridReaderReadsKeyword(l)) continue;   // 리더가 메시에 담는다
            in = true;
            grid = info;
            aux = info.family == ElemFamily::NONE ? auxElementCard(l) : AuxElementCard();
            gridKnown = info.family != ElemFamily::NONE && info.supported &&
                        (info.family != ElemFamily::SOLID || info.optionNodes > 0);
            kw = info.keyword;
            fw = keywordFieldWidth(l, deckFw);
            continue;
        }
        if (!in) continue;
        if (g != std::string::npos && l[g] == '$') continue;
        if (g == std::string::npos && remaining == 0) continue;   // 카드 밖의 빈 줄
        if (gridKnown) {
            const auto fs = deckscan::cardFields(l, fw);
            if (remaining == 0) {
                flush();
                span = elementCardSpan(grid, fs, 0);   // 줄 수가 PID 에 달리지 않는 변형만 여기 온다
                remaining = span.lines;
                lineIdx = 0;
                pend = NonGridElementCard();
                pend.keyword = kw;
                pend.line = i;
                pend.known = true;
                pend.eid = deckscan::fieldInt(fs, 0);
                pend.pid = deckscan::fieldInt(fs, 1);
                if (pend.pid > 0) pend.pids = {pend.pid};
                pending = true;
            }
            if (lineIdx >= span.nodeFirst && lineIdx < span.nodeFirst + span.nodeLines) {
                const size_t from = lineIdx == span.nodeFirst ? static_cast<size_t>(span.nodeFieldSkip) : 0u;
                for (size_t q = from; q < fs.size(); ++q) {
                    const int v = deckscan::fieldInt(fs, q);
                    if (v > 0) pend.nodes.push_back(v);
                }
            }
            ++lineIdx;
            if (--remaining == 0) flush();
            continue;
        }
        NonGridElementCard c;
        c.keyword = kw;
        c.line = i;
        if (aux.supported) {
            if (!aux.hasEid) continue;   // 요소가 아니다(`*ELEMENT_MASS_PART(_SET)` — EID · 절점 칸이 없다 · PID 는 IdRefs 가 본다)
            if (remaining > 0 && pending && auxOptNodeFields(aux, lineIdx)) {   // 옵션 카드의 절점(보 `_WARPAGE` 의 SN · `_ELBOW` 의 MN)
                for (int v : auxOptNodesOf(aux, lineIdx, l, fw)) pend.nodes.push_back(v);
                std::sort(pend.nodes.begin(), pend.nodes.end());
                pend.nodes.erase(std::unique(pend.nodes.begin(), pend.nodes.end()), pend.nodes.end());
            }
            if (remaining == 0) {
                remaining = aux.lines;
                lineIdx = 0;
                // 절점은 읽기 전부의 합집합 · PID 는 후보 전부(헤더 「읽기들」 — 이월 적용의 나눠 쓴 절점 · aux_in_part 가 본다)
                const AuxCardReadings rd = auxCardReadings(aux, l, fw);
                const auto& fs = auxPrimaryFields(rd);
                c.known = true;
                c.eid = deckscan::fieldInt(fs, 0);
                c.pid = (aux.hasPart && aux.partField >= 0) ? deckscan::fieldInt(fs, static_cast<size_t>(aux.partField)) : 0;
                c.pids = auxPidsOf(aux, rd);
                c.nodes = auxNodesUnion(aux, rd);
                if (!aux.optNodes.empty()) { pend = c; pending = true; }   // 옵션 카드의 절점까지 읽고 넘긴다
                else f(c);
            }
            ++lineIdx;
            if (--remaining == 0) flush();
            continue;
        }
        if (g == std::string::npos) continue;
        c.eid = deckscan::fieldInt(deckscan::cardFields(l, fw), 0);   // 넘치게 센다 — 바닥은 높아질 뿐이다
        f(c);
    }
    flush();
}

int nonGridElementMaxId(const std::vector<std::string>& lines) {
    int m = 0;
    forEachNonGridElementCard(lines, [&](const NonGridElementCard& c) { m = std::max(m, c.eid); });
    return m;
}

bool isScalarNodeKeyword(const std::string& kw) { return kw == "*NODE_SCALAR" || kw == "*NODE_SCALAR_VALUE"; }

int scalarNodeMaxIdFile(const std::string& path) {
    std::ifstream in(path);
    if (!in.is_open()) return 0;
    // 덱 폭은 첫 `*KEYWORD` 카드가 정한다(`deckFieldWidth` 와 같다) — 흘려 읽으니 그 줄에서 정한다
    int deckFw = 8, fw = 8, m = 0;
    bool kwSeen = false, inScalar = false;
    std::string l;
    while (std::getline(in, l)) {
        if (!l.empty() && l.back() == '\r') l.pop_back();
        const size_t g = l.find_first_not_of(" \t");
        if (g == std::string::npos) continue;
        if (deckscan::isKeywordLine(l)) {   // 1열 규칙(리더와 같다)
            const std::string kw = deckscan::kwBare(deckscan::keywordToken(l));
            if (!kwSeen && kw == "*KEYWORD") {
                const int w = keywordCardDeckWidth(l);
                deckFw = w > 0 ? w : 8;
                kwSeen = true;
            }
            inScalar = isScalarNodeKeyword(kw);
            fw = keywordFieldWidth(l, deckFw);
            continue;
        }
        if (!inScalar || l[g] == '$') continue;
        std::string body = l;
        const size_t cmt = body.find('$');
        if (cmt != std::string::npos) body.erase(cmt);
        m = std::max(m, deckscan::fieldInt(deckscan::cardFields(body, fw), 0));
    }
    return m;
}

int scalarNodeMaxId(const std::vector<std::string>& lines) {
    const int deckFw = deckFieldWidth(lines);
    int fw = deckFw, m = 0;
    bool in = false;
    for (const auto& l : lines) {
        const size_t g = l.find_first_not_of(" \t");
        if (g == std::string::npos) continue;
        if (deckscan::isKeywordLine(l)) {   // 1열 규칙(리더와 같다)
            in = isScalarNodeKeyword(deckscan::kwBare(deckscan::keywordToken(l)));
            fw = keywordFieldWidth(l, deckFw);
            continue;
        }
        if (!in || l[g] == '$') continue;
        std::string body = l;
        const size_t cmt = body.find('$');
        if (cmt != std::string::npos) body.erase(cmt);
        m = std::max(m, deckscan::fieldInt(deckscan::cardFields(body, fw), 0));
    }
    return m;
}

}  // namespace KooRemapper
