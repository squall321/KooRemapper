// *ELEMENT_* 키워드 옵션을 매뉴얼 표대로 카드 줄 수로 바꾸는 판정기 (헤더의 인용 참조)
#include "parser/ElementCardLayout.h"

#include <algorithm>
#include <cctype>
#include <vector>

namespace KooRemapper {

namespace {

// 키워드 줄에서 키워드 토큰만 뽑는다(대문자, 앞뒤 공백·CR 제거, 첫 공백 뒤는 버린다).
std::string normalizeKeyword(const std::string& line, ElementKeywordInfo& info) {
    size_t s = line.find_first_not_of(" \t");
    if (s == std::string::npos) return std::string();
    std::string kw = line.substr(s);
    // 매뉴얼이 정한 키워드 줄 접미사는 '%'(i10), '+'(long), '-'(standard) 셋뿐이다(19342-19360).
    // 그 밖의 꼬리글(LS-PrePost 의 "(ten nodes format)" 같은 주석)은 매뉴얼에 없다 —
    // 공백에서 잘라 버리고 줄 수 판정에는 절대 쓰지 않는다.
    size_t sp = kw.find_first_of(" \t");
    if (sp != std::string::npos) kw = kw.substr(0, sp);
    while (!kw.empty() && (kw.back() == '\r' || kw.back() == '\n')) kw.pop_back();
    while (!kw.empty() && (kw.back() == '%' || kw.back() == '+' || kw.back() == '-')) {
        if (kw.back() == '%') info.i10Suffix = true;
        else if (kw.back() == '+') info.longSuffix = true;
        else info.stdSuffix = true;
        kw.pop_back();
    }
    for (auto& c : kw) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return kw;
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
