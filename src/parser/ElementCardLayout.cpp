// *ELEMENT_* 키워드 옵션을 매뉴얼 표대로 카드 줄 수로 바꾸는 판정기 (헤더의 인용 참조)
#include "parser/ElementCardLayout.h"

#include <algorithm>
#include <cctype>
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

}  // namespace KooRemapper
