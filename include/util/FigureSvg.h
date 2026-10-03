#pragma once
// 그림(SVG)을 쓰는 자리들이 함께 쓰는 유틸 — 이스케이프·인코딩 판정·범주 색.
//
// 왜 한 자리인가. 그림을 내는 op 이 둘 이상이 되면(단면·자유면) 이스케이프와 색 배정이 **갈린다**
// (StepForge D-236 이 같은 값을 치렀다). 특히 둘은 그냥 편의 함수가 아니라 **실측으로 값을 치른
// 규율**이다.
//   · 파트 제목은 `*PART` 다음 줄의 **자유 텍스트**다 — STEP 라벨과 같은 노출이다.
//   · XML 1.0 은 제어문자를 담지 못해 **이름에 하나만 있어도 SVG 가 통째로 안 읽힌다.**
//   · 한국어 윈도 덱은 **CP949** 가 기본이고, 그 바이트를 UTF-8 선언 SVG 에 쓰면 XML 파싱이
//     실패해 **그림이 죽는다**(실측: "알루미늄 집전체" → `not well-formed`).
//   · 색을 호출마다 새로 배정하면 두 그림을 견줄 수 없다 — **pid 로 고정**한다.
#include <string>

namespace KooRemapper {
namespace figure {

// 문자열이 **유효한 UTF-8** 인가. 파트 제목은 덱 바이트 그대로이고 한국어 윈도 LS-DYNA 덱은
// CP949 가 기본이다 — 그 바이트를 UTF-8 선언 SVG 에 그대로 쓰면 **XML 파싱이 통째로 실패해
// 그림이 죽는다**(실측: 제목 "알루미늄 집전체" 를 CP949 로 넣으니 `not well-formed` 로 안 읽혔다).
// 그래서 먼저 판정한다. 리포에 CP949 표를 싣지 않으므로 변환은 하지 않고, **읽을 수 있는 그림을
// 내고 사실을 말한다** — 원본 바이트는 매니페스트에 16진으로 남겨 복원할 수 있게 한다.
inline bool isUtf8(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        size_t n = 0;
        if (c < 0x80) n = 0;
        else if ((c & 0xE0) == 0xC0) n = 1;
        else if ((c & 0xF0) == 0xE0) n = 2;
        else if ((c & 0xF8) == 0xF0) n = 3;
        else return false;
        if (i + n >= s.size() + (n ? 0 : 1)) { if (n) return false; }
        for (size_t k = 1; k <= n; ++k) {
            if (i + k >= s.size()) return false;
            if ((static_cast<unsigned char>(s[i + k]) & 0xC0) != 0x80) return false;
        }
        i += n + 1;
    }
    return true;
}

inline std::string hexOf(const std::string& s) {
    static const char* H = "0123456789abcdef";
    std::string out;
    out.reserve(s.size() * 2);
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        out += H[u >> 4];
        out += H[u & 0xF];
    }
    return out;
}

// 비 ASCII 바이트를 `?` 로 바꾼다 — 읽을 수 있는 그림을 내기 위해서다(그리고 그 사실을 적는다).
inline std::string asciiOnly(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        out += (u < 0x80) ? ch : '?';
    }
    return out;
}

// XML 이스케이프. 파트 제목은 `*PART` 다음 줄의 **자유 텍스트**라 무엇이든 들어 있다 —
// STEP 라벨과 같은 노출이다. 그리고 XML 1.0 은 제어문자를 담지 못해 **이름에 \x01 하나면 SVG 가
// 통째로 안 읽힌다**(StepForge 실측). 그래서 지우지 않고 보이는 기호로 바꾸고, 바꿨다는 사실을
// 매니페스트에 싣는다.
inline std::string xesc(const std::string& s, bool* stripped = nullptr) {
    std::string out;
    out.reserve(s.size() + 16);
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        switch (ch) {
            case '&': out += "&amp;";  continue;
            case '<': out += "&lt;";   continue;
            case '>': out += "&gt;";   continue;
            case '"': out += "&quot;"; continue;
            case '\'': out += "&apos;"; continue;
            default: break;
        }
        if (u < 0x20 || u == 0x7F) {
            out += '?';                       // 보이는 자리표시 — 지우면 사라진 줄 모른다
            if (stripped) *stripped = true;
            continue;
        }
        out += ch;
    }
    return out;
}

// 색맹 안전 범주 색(Okabe-Ito). **pid 로 고정**한다 — 호출마다 바뀌면 두 그림을 견줄 수 없다.
inline const char* colorFor(int pid) {
    static const char* P[] = {"#0072B2","#E69F00","#009E73","#CC79A7",
                              "#56B4E9","#D55E00","#F0E442","#999999"};
    const int n = 8;
    int k = pid % n;
    if (k < 0) k += n;
    return P[k];
}

}  // namespace figure
}  // namespace KooRemapper
