// 카드 줄을 칸으로 쪼개고 블록 줄을 가르는 보조 — 절점·파트·요소 참조 정본(NodeRefs·IdRefs)이 같이 쓴다
#pragma once

#include "parser/CardFields.h"
#include "parser/DeckScan.h"

#include <sstream>
#include <string>
#include <vector>

namespace KooRemapper {
namespace cardcut {

inline bool isKeywordLine(const std::string& l) {
    const size_t g = l.find_first_not_of(" \t");
    return g != std::string::npos && l[g] == '*';
}
inline bool isCommentLine(const std::string& l) {
    const size_t g = l.find_first_not_of(" \t");
    return g != std::string::npos && l[g] == '$';
}
inline bool isBlank(const std::string& l) { return l.find_first_not_of(" \t\r\n") == std::string::npos; }

// 카드 줄을 칸으로 — 콤마면 자유형식, 아니면 **고정폭**(칸 안에 공백이 남으면 어긋난 줄이라 공백 토큰).
// 규율은 `deckscan::cardFields` 와 같다. `fixed` 가 참일 때만 칸 자리(열)가 뜻을 가진다.
struct Cut { std::vector<std::string> f; bool fixed = false; };
inline Cut cut(const std::string& line, int w) {
    std::string body = line;
    const size_t cm = body.find('$');
    if (cm != std::string::npos) body = body.substr(0, cm);
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    Cut c;
    if (body.find(',') != std::string::npos) { c.f = deckscan::cardFields(body, w); return c; }
    c.f = cards::fieldsFixed(body, w);
    for (const auto& s : c.f) {
        if (s.find(' ') == std::string::npos && s.find('\t') == std::string::npos) continue;
        c.f.clear();
        std::istringstream iss(body);
        std::string t;
        while (iss >> t) c.f.push_back(t);
        return c;
    }
    c.fixed = true;
    return c;
}

// 키워드 블록 하나 — 키워드 줄과 데이터 줄(주석을 뺀다 · 빈 줄은 카드다 · 끝의 빈 줄은 여백이라 뗀다).
struct Block { size_t kwLine = 0; std::string kw; std::vector<size_t> data; };
inline std::vector<Block> blocks(const std::vector<std::string>& L) {
    std::vector<Block> out;
    for (size_t i = 0; i < L.size();) {
        if (!isKeywordLine(L[i])) { ++i; continue; }
        Block b;
        b.kwLine = i;
        b.kw = deckscan::kwBare(deckscan::keywordToken(L[i]));
        size_t j = i + 1;
        for (; j < L.size() && !isKeywordLine(L[j]); ++j)
            if (!isCommentLine(L[j])) b.data.push_back(j);
        while (!b.data.empty() && isBlank(L[b.data.back()])) b.data.pop_back();
        out.push_back(std::move(b));
        i = j;
    }
    return out;
}

}  // namespace cardcut
}  // namespace KooRemapper
