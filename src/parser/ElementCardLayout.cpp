// *ELEMENT_* 키워드 옵션을 매뉴얼 표대로 카드 줄 수로 바꾸는 판정기 (헤더의 인용 참조)
#include "parser/ElementCardLayout.h"

#include "parser/DeckScan.h"   // 카드 칸 읽기(cardFields · fieldInt) — 격자 밖 요소 걸음이 쓴다

#include <algorithm>
#include <cctype>
#include <sstream>
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
                if (o == "THICKNESS" || o == "SCALAR" || o == "SCALR" || o == "SECTION" ||
                    o == "PID" || o == "OFFSET" || o == "ORIENTATION" || o == "WARPAGE" ||
                    o == "ELBOW")
                    a.lines += 1;                   // 옵션마다 카드 한 장
                else
                    unsupported("*ELEMENT_BEAM 의 옵션 '" + o + "' 은 카드 줄 수를 확정할 수 없습니다");
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
        case AuxFamily::MASS:
            // Card 1 = EID(I8) ID(I8) MASS(E16) PID(I8) (159866-159930). ⚠ PID 는 칸 차례 **3** 이다(칸 1 이 아니다) —
            // MASS 가 넓은 칸이라 8칸으로 자르면 33-40열(칸 4)이다. 그 차례는 `auxCardReadings` 가 자른다.
            a.nodeSkip = 1; a.nodeCount = 1;
            a.partField = 3;
            a.wideFields = {2};
            a.card1Fields = 4;
            for (const auto& o : opts) {
                if (o == "TITLE") continue;
                // `_NODE_SET` 은 칸 1 이 **절점 세트 ID** 다 — 절점으로 읽으면 엉뚱한 절점을
                // 지키고 세트 멤버는 놓친다. 추측하지 않는다.
                if (o == "NODE" || o == "SET")
                    unsupported("*ELEMENT_MASS_NODE_SET 은 칸 1 이 절점이 아니라 **절점 세트 ID** 입니다");
                else
                    unsupported("*ELEMENT_MASS 의 옵션 '" + o + "' 은 칸 뜻을 확정할 수 없습니다");
            }
            break;
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

AuxCardReadings auxCardReadings(const AuxElementCard& a, const std::string& line, int fw) {
    AuxCardReadings r;
    std::string body = line;
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    auto inner = [](const std::string& s) { return s.find_first_of(" \t") != std::string::npos; };
    if (body.find(',') != std::string::npos) {               // 자유형식 — 콤마 토큰이 곧 칸 차례 · 열 자리 없음
        r.comma = true;
        r.manual.f = deckscan::cardFields(body, fw);
        r.manualClean = std::none_of(r.manual.f.begin(), r.manual.f.end(), inner);
        r.plain = r.manual;
        r.plainClean = r.manualClean;
        return r;
    }
    // 고정폭 — 열로 자른다. 칸 안에 공백이 끼어도 자르기는 그대로 두고 깨끗하지 않다고만 적는다
    const size_t rw = static_cast<size_t>(realFieldWidth(fw));
    auto cut = [&](bool wideAware, AuxCardCut& t) {
        bool clean = true;
        for (size_t pos = 0, q = 0; pos < body.size(); ++q) {
            const bool wide = wideAware &&
                              std::find(a.wideFields.begin(), a.wideFields.end(), static_cast<int>(q)) != a.wideFields.end();
            const size_t w = wide ? rw : static_cast<size_t>(fw);
            std::string f = deckscan::trim(body.substr(pos, w));
            if (inner(f)) clean = false;
            t.f.push_back(std::move(f));
            t.col.push_back(pos);
            t.width.push_back(w);
            pos += w;
        }
        return clean;
    };
    r.manualClean = cut(true, r.manual);
    if (a.wideFields.empty()) {
        r.plain = r.manual;
        r.plainClean = r.manualClean;
    } else {
        r.plainClean = cut(false, r.plain);
        // 정수 폭으로 쓴 줄은 칸 수 × fw 안에서 끝난다 — 그 뒤에 글자가 있으면 설명서 칸으로 쓴 줄이다(헤더 「갈림」)
        r.plainFits = a.card1Fields <= 0 ||
                      body.find_first_not_of(" \t", static_cast<size_t>(a.card1Fields) * static_cast<size_t>(fw)) == std::string::npos;
    }
    if (!r.manualClean || !r.plainClean) {                   // 칸이 어긋난 줄 — 공백 토큰도 한 읽기다
        std::istringstream iss(body);
        for (std::string t; iss >> t;) r.tokens.push_back(t);
    }
    return r;
}

const std::vector<std::string>& auxPrimaryFields(const AuxCardReadings& r) {
    if (r.comma || r.manualClean) return r.manual.f;
    if (r.plainClean) return r.plain.f;
    return r.tokens;
}

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
    std::vector<int> out = auxNodesOf(a, r.manual.f);
    for (int v : auxNodesOf(a, r.plain.f)) out.push_back(v);
    for (int v : auxNodesOf(a, r.tokens)) out.push_back(v);
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
    std::vector<int> m = auxNodesOf(a, r.manual.f);
    std::sort(m.begin(), m.end());
    std::vector<int> out;
    auto add = [&](const std::vector<std::string>& f) {
        for (int v : auxNodesOf(a, f))
            if (!std::binary_search(m.begin(), m.end(), v)) out.push_back(v);
    };
    if (r.plainFits) add(r.plain.f);
    add(r.tokens);
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return out;
}

bool auxManualNodesPlaceable(const AuxElementCard& a, const AuxCardReadings& r) {
    if (r.comma) return false;
    auto ok = [&](int from, int cnt) {
        for (int q = 0; from >= 0 && q < cnt; ++q) {
            const size_t k = static_cast<size_t>(from + q);
            if (k >= r.manual.f.size() || r.manual.f[k].empty()) continue;
            int v = 0;
            if (!cards::toInt(r.manual.f[k], v)) return false;
        }
        return true;
    };
    return ok(a.nodeSkip, a.nodeCount) && ok(a.nodeSkip2, a.nodeCount2);
}

std::vector<int> auxPidsOf(const AuxElementCard& a, const AuxCardReadings& r) {
    std::vector<int> out;
    if (!a.hasPart || a.partField < 0) return out;
    const size_t pf = static_cast<size_t>(a.partField);
    for (const auto* f : {&auxPrimaryFields(r), &r.manual.f, &r.plain.f, &r.tokens}) {
        if (f == &r.plain.f && !r.plainFits) continue;   // 설명서 칸으로 쓴 줄 — 정수 폭 읽기의 PID 는 후보가 아니다(primary 면 이미 들었다)
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
        if (g != std::string::npos && l[g] == '*') {
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
            if (remaining == 0) {
                remaining = aux.lines;
                // 절점은 읽기 전부의 합집합 · PID 는 후보 전부(헤더 「읽기들」 — 이월 적용의 나눠 쓴 절점 · aux_in_part 가 본다)
                const AuxCardReadings rd = auxCardReadings(aux, l, fw);
                const auto& fs = auxPrimaryFields(rd);
                c.known = true;
                c.eid = deckscan::fieldInt(fs, 0);
                c.pid = (aux.hasPart && aux.partField >= 0) ? deckscan::fieldInt(fs, static_cast<size_t>(aux.partField)) : 0;
                c.pids = auxPidsOf(aux, rd);
                c.nodes = auxNodesUnion(aux, rd);
                f(c);
            }
            --remaining;
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

}  // namespace KooRemapper
