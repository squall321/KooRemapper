#pragma once
// LS-DYNA 카드 줄에서 칸을 읽는 공용 보조 — 고정폭/자유형식 둘 다, 그리고 그 함정들
//
// 왜 한 곳인가 (2026-10-11). 이 지식은 `ReferenceIntegrity.cpp` 의 익명 네임스페이스에만
// 있었고, 절점 참조를 추적해야 하는 `cleanup-nodes` 가 그것을 **베껴 쓸 수밖에** 없었다.
// 이 리포는 같은 지식의 사본이 갈려 생긴 결함을 이미 여러 번 치렀다(요소 위상 표 여섯 벌이
// 서로 달라 11개 소비자가 틀린 답을 받았다 — 매뉴얼 §46). 그래서 베끼지 않고 옮겼다.
//
// ★여기 담긴 것은 편의 함수가 아니라 **실측으로 값을 치른 규율**이다. 주석을 지우지 말라.
//
// @lat: [[modules/parser]]

#include <cctype>
#include <sstream>
#include <string>
#include <vector>

namespace KooRemapper {
namespace cards {

inline std::string upper(std::string s) {
    for (auto& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}

inline std::string trim(const std::string& s) {
    size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    size_t e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

inline bool isComment(const std::string& t) { return !t.empty() && t[0] == '$'; }
inline bool isKeyword(const std::string& t) { return !t.empty() && t[0] == '*'; }

// 카드 줄을 10칸 고정폭으로 자른다. 칸이 공백으로 갈려 있으면 자유형식으로도 읽는다.
// ⚠ 둘 다 보는 이유 — 운영 덱은 칸을 꽉 채우기도 하고(공백 없음) 느슨하게 쓰기도 한다.
inline std::vector<std::string> fields10(const std::string& line) {
    std::vector<std::string> out;
    for (size_t i = 0; i < line.size(); i += 10) out.push_back(trim(line.substr(i, 10)));
    // 자유형식이 더 그럴듯하면(고정폭 첫 칸이 통째로 숫자가 아닌데 공백 분해는 숫자면) 그쪽을 쓴다.
    std::vector<std::string> ws;
    size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() && std::isspace((unsigned char)line[i])) ++i;
        size_t b = i;
        while (i < line.size() && !std::isspace((unsigned char)line[i])) ++i;
        if (i > b) ws.push_back(line.substr(b, i - b));
    }
    if (!ws.empty() && (out.empty() || out[0].empty())) return ws;
    return out;
}

// 임의 폭(8·10·20)으로 카드 줄을 자른다. `*ELEMENT_*`·`*NODE` 는 10칸이 아니다.
// ⚠ 공백으로 되돌리지 **않는다** — 절점 ID 8자리가 칸을 꽉 채우면 공백이 사라져
//   `split()` 이 두 토큰으로 읽고, 그것을 2줄 포맷으로 오판해 **연결성이 통째로 뒤섞인**
//   사고가 현장에서 있었다(요청서 §6). 폭을 아는 자리에서는 폭만 믿는다.
inline std::vector<std::string> fieldsFixed(const std::string& line, int fw) {
    std::vector<std::string> out;
    if (fw <= 0) return out;
    for (size_t i = 0; i < line.size(); i += (size_t)fw)
        out.push_back(trim(line.substr(i, (size_t)fw)));
    return out;
}

inline bool toInt(const std::string& s, int& v) {
    if (s.empty()) return false;
    size_t i = 0;
    if (s[0] == '+' || s[0] == '-') i = 1;
    if (i >= s.size()) return false;
    for (size_t k = i; k < s.size(); ++k)
        if (!std::isdigit((unsigned char)s[k])) return false;
    try { v = std::stoi(s); } catch (...) { return false; }
    return true;
}

inline bool starts(const std::string& kw, const char* p) { return kw.rfind(p, 0) == 0; }
inline bool has(const std::string& kw, const char* p) { return kw.find(p) != std::string::npos; }

// 카드 첫 칸의 ID. **10칸 → 자유형식** 순서로 읽는다.
//
// ⚠ `fields10` 만으로는 안 된다. 그 함수는 첫 칸이 **비었을 때만** 자유형식으로 되돌리므로,
// `       9 7.85E-9  210000     0.3` 같은 자유형식 줄에서 첫 칸이 `"9 7"` 이 되어 정수가 아니고
// 조용히 아무 값도 내지 않는다. 실측으로 이 때문에 `*MAT` 중복 검사가 **통째로 죽어 있었다**
// (10칸 정렬된 `*MAT_THERMAL_` 만 우연히 잡혀 오탐으로 보였다).
inline bool firstFieldId(const std::string& line, int& out) {
    auto f = fields10(line);
    if (!f.empty() && toInt(f[0], out)) return true;
    std::istringstream iss(line);
    std::string tok;
    if (iss >> tok && toInt(tok, out)) return true;
    return false;
}

// `&name` — *PARAMETER 참조가 있는 줄은 값이 기호라 숫자로 읽으면 안 된다.
inline bool hasParameterRef(const std::string& line) { return line.find('&') != std::string::npos; }

// `*SET_*` 정의의 제목줄 수. `_TITLE` 이면 SID 줄 앞에 제목이 한 줄 더 있다.
inline int titleLines(const std::string& kw) { return has(kw, "_TITLE") ? 1 : 0; }

// 정수 칸에 **실수**가 들어 있는가 — `0.33`, `1.0E+20` 같은 표기. LS-DYNA 는 정수 칸의
// 그런 글자를 우리와 다르게 읽는다(대개 앞자리만, 또는 0 으로).
inline bool looksReal(const std::string& s) {
    bool digit = false, mark = false;
    for (char c : s) {
        if (std::isdigit((unsigned char)c)) { digit = true; continue; }
        if (c == '.') { mark = true; continue; }
        if ((c == 'e' || c == 'E' || c == 'd' || c == 'D') && digit) { mark = true; continue; }
        if (c == '+' || c == '-') continue;
        return false;                       // 그 밖의 글자는 우리가 아는 수가 아니다
    }
    return digit && mark;
}

}  // namespace cards
}  // namespace KooRemapper
