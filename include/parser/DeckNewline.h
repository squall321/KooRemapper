// 덱의 개행 종류를 읽을 때 기억했다가 쓸 때 되붙인다 — CRLF 덱이 LF 로 바뀌는 것을 막는다
#pragma once

#include <cstdio>
#include <string>
#include <vector>

namespace KooRemapper {

// 덱이 쓰는 개행. 읽을 때 판정해서 쓸 때 그대로 되붙인다.
enum class DeckNewline { LF, CRLF };

namespace deck_newline {

// 파일의 개행 종류를 센다. 규약은 `count("\r\n") * 2 > count("\n")` —
// 절반 넘게 CRLF 면 CRLF 덱으로 본다(섞인 덱에서도 지배적인 쪽을 따른다).
//
// ⚠ 왜 필요한가 — 리더가 `getline` 뒤 `line.pop_back()` 으로 CR 을 떼는 자리가 78곳이다.
// 그 자체는 옳다(뗀 CR 이 남으면 `stoi`·`substr`·`back()` 분기가 전부 오동작한다).
// 없던 것은 **뗀 사실을 기억해 쓸 때 되붙이는 것**이라, 700MB 덱이 LF 로 바뀌며
// 바이트가 −12MB 씩 달라져도 구조 카운트는 전부 정상이라 아무도 못 알아봤다.
inline DeckNewline detect(const std::string& path) {
    std::FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return DeckNewline::LF;
    std::vector<char> buf(1 << 16);
    unsigned long long lf = 0, crlf = 0;
    bool prevCR = false;
    size_t n;
    while ((n = std::fread(buf.data(), 1, buf.size(), f)) > 0) {
        for (size_t i = 0; i < n; ++i) {
            const char c = buf[i];
            if (c == '\n') {
                ++lf;
                if (prevCR) ++crlf;
            }
            prevCR = (c == '\r');
        }
    }
    std::fclose(f);
    return (crlf * 2 > lf) ? DeckNewline::CRLF : DeckNewline::LF;
}

// 파일이 개행으로 끝나나. 리더는 `getline` 으로 읽으므로 **마지막 줄에 개행이 있었는지를 잃는다** —
// 쓰는 쪽이 줄마다 `\n` 을 붙이면 말미 개행이 없던 덱에 하나가 생긴다(무편집 진입점 실측 — 그것만으로
// sha256 이 달라진다). CR 을 기억했다가 되붙이는 것과 같은 규율로, 이것도 기억했다가 따른다.
// 빈 파일은 참으로 본다(뗄 것이 없다).
inline bool endsWithNewline(const std::string& path) {
    std::FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return true;
    bool ends = true;
    if (std::fseek(f, -1, SEEK_END) == 0) {
        const int c = std::fgetc(f);
        ends = (c == EOF) || (c == '\n');
    }                                          // fseek 이 실패하면 빈 파일이다 — 뗄 것이 없다
    std::fclose(f);
    return ends;
}

// `\n` 으로 조립된 본문을 그 덱의 개행으로 바꾼다.
// 본문에는 CR 이 없다(리더가 이미 뗐다) — 그래서 단순 치환이 안전하다.
inline std::string apply(const std::string& text, DeckNewline nl) {
    if (nl != DeckNewline::CRLF) return text;
    std::string out;
    out.reserve(text.size() + text.size() / 32 + 16);
    for (char c : text) {
        if (c == '\n') out.push_back('\r');
        out.push_back(c);
    }
    return out;
}

}  // namespace deck_newline
}  // namespace KooRemapper
