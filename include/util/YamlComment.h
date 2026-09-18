// YAML 미니 파서 공용 함수 — 인라인 주석 제거·BOM 제거·들여쓰기(탭) 검사·상대 경로 해석을 한곳에 모아,
// 명령마다 따로 짠 파서가 같은 규칙을 쓰게 한다
#pragma once

#include <fstream>
#include <istream>
#include <sstream>
#include <string>

namespace KooRemapper {

// 'key: value   # 주석' 의 value 부분에서 주석을 뗀다. YAML 규칙대로 따옴표 밖에서 공백 뒤(또는 맨 앞)의 '#'
// 부터가 주석이다 — "Part #1" 같은 따옴표 안 #, 공백 없이 붙은 #(예: A#1)은 값으로 둔다.
// 예전엔 파서 대부분이 주석까지 값으로 읽어 'box.k   # 모델' 파일을 찾거나, 'vrh  # 평균' 을 모르는 값으로 보고
// 조용히 기본값으로 계산했다.
// 따옴표는 값 맨 앞과 '[' '{' ',' 뒤(사이 공백 허용)에서 열린다 — 예전엔 맨 앞 따옴표만 봐
// 'keywords: ["*NODE # x", "*ELEMENT_SOLID"]' 가 '#' 에서 잘려 '"*NODE' 하나만 남았다.
// 평문 스칼라 중간의 따옴표(it's)는 인용을 열지 않는다(YAML 규칙) — 뒤의 주석을 값으로 남기지 않으려는 것.
inline std::string yamlStripComment(const std::string& s) {
    size_t start = s.find_first_not_of(" \t");
    if (start == std::string::npos) return s;
    for (size_t i = start; i < s.size(); ++i) {
        bool afterSpace = (i == 0 || s[i - 1] == ' ' || s[i - 1] == '\t');
        // 앞의 비공백 글자가 없거나 '[' '{' ',' 일 때만 인용 시작으로 본다
        size_t prev = s.find_last_not_of(" \t", i == 0 ? 0 : i - 1);
        bool quoteStart = (i == start) ||
                          (prev != std::string::npos && prev < i &&
                           (s[prev] == '[' || s[prev] == '{' || s[prev] == ','));
        if ((s[i] == '"' || s[i] == '\'') && quoteStart) {
            size_t close = s.find(s[i], i + 1);
            if (close == std::string::npos) {
                if (i == start) return s;  // 닫히지 않은 맨 앞 따옴표 — 통째로 값
                continue;                  // 중간의 짝 없는 따옴표는 글자로 본다
            }
            i = close;
            continue;
        }
        if (s[i] == '#' && afterSpace) {
            size_t e = i;
            while (e > 0 && (s[e - 1] == ' ' || s[e - 1] == '\t')) --e;
            return s.substr(0, e);
        }
    }
    return s;
}

// UTF-8 BOM(EF BB BF) — 윈도우 편집기가 기본으로 붙이는 세 바이트다. 그대로 두면 첫 키가 'model' 이
// 아니라 '<BOM>model' 이 되어 어떤 파서도 매칭하지 못하고, op 이 통째로 "model not specified"(assemble 은
// base_model) 로 끝났다. 에러 메시지엔 힌트가 없었다. YAML 을 읽는 모든 자리에서 이 둘 중 하나를 쓴다.
inline void yamlStripBOM(std::string& s) {
    if (s.size() >= 3 && (unsigned char)s[0] == 0xEF && (unsigned char)s[1] == 0xBB &&
        (unsigned char)s[2] == 0xBF)
        s.erase(0, 3);
}

// 막 연 스트림 앞의 BOM 을 건너뛴다. BOM 이 아니면 위치를 되돌린다.
inline void yamlSkipBOM(std::istream& in) {
    if (in.peek() != 0xEF) return;
    char b[3] = {0, 0, 0};
    in.read(b, 3);
    if (in.gcount() == 3 && (unsigned char)b[1] == 0xBB && (unsigned char)b[2] == 0xBF) return;
    in.clear();
    in.seekg(0);
}

// 줄 앞 여백(첫 비공백 글자 앞)에 탭이 있는가 — 들여쓰기만 본다. 값 안의 탭(따옴표 문자열,
// '|' 블록 카드 줄)은 보지 않는다.
inline bool yamlTabIndent(const std::string& s) {
    for (char c : s) {
        if (c == '\t') return true;
        if (c != ' ') return false;
    }
    return false;
}

// 들여쓰기 칸 수 — 공백만 센다. 탭이 섞이면 0 이 나와 블록 구조가 통째로 무너지므로,
// 파서는 이 값을 쓰기 전에 탭 들여쓰기를 걸러야 한다.
inline int yamlCountIndent(const std::string& s) {
    int n = 0;
    while (n < (int)s.size() && s[n] == ' ') ++n;
    return n;
}

// 탭 들여쓰기 거부 메시지 — 모든 YAML 파서가 load 가 쓰던 문구 그대로 쓴다.
inline std::string yamlTabIndentMessage(const std::string& tag, const std::string& trimmedLine) {
    return "[" + tag + "] YAML 들여쓰기에 탭을 쓸 수 없습니다 (공백을 쓰세요): " + trimmedLine;
}

// YAML 파일 전체에서 들여쓰기 탭을 찾는다(찾으면 true + 그 줄). 파서마다 흩어져 있던 countIndent 는
// 공백만 세서, 탭으로 들여쓴 YAML 은 모든 줄이 indent 0 이 되어 블록이 통째로 무너지고도 rc=0 으로
// '아무 일도 안 한' 덱을 냈다 — 파싱 전에 한 번 걸러 rc=1 로 알린다.
// '|'/'>' 리터럴 블록 안의 줄은 구조가 아니라 값이므로 보지 않는다(LS-DYNA 카드 줄).
inline bool yamlScanTabIndent(std::istream& f, std::string& badLine) {
    yamlSkipBOM(f);
    int literalIndent = -1;  // '|' 블록을 연 키의 들여쓰기 (-1 = 블록 밖)
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        size_t ns = ln.find_first_not_of(" \t");
        std::string tr = (ns == std::string::npos) ? "" : ln.substr(ns);
        while (!tr.empty() && (tr.back() == ' ' || tr.back() == '\t')) tr.pop_back();
        int width = (ns == std::string::npos) ? -1 : (int)ns;
        if (literalIndent >= 0) {
            // 블록은 '공백만으로 들여쓴 얕은 줄' 에서만 닫는다 — 앞이 탭인 카드 줄(LS-DYNA 자유 형식)도
            // 값으로 남겨 막지 않는다
            if (tr.empty() || width > literalIndent || yamlTabIndent(ln)) continue;
            literalIndent = -1;
        }
        if (tr.empty() || tr[0] == '#') continue;
        if (yamlTabIndent(ln)) { badLine = tr; return true; }
        // 블록을 여는 줄 — standalone_ops 의 countOperations 와 같은 판정.
        // 목록 항목 '- |' 는 대시 열이, 'key: |'(항목 안의 '- key: |' 포함)은 키 열이 기준이다.
        std::string item = yamlStripComment(tr);
        while (!item.empty() && (item.back() == ' ' || item.back() == '\t')) item.pop_back();
        if (item == "- |" || item == "-|" || item == "- >") { literalIndent = width; continue; }
        std::string body = tr;
        int keyCol = width;
        if (body.substr(0, 2) == "- ") {
            size_t i = 1;
            while (i < body.size() && body[i] == ' ') ++i;
            keyCol += (int)i;
            body = body.substr(i);
        }
        size_t cp = body.find(':');
        if (cp == std::string::npos) continue;
        std::string val = yamlStripComment(body.substr(cp + 1));
        size_t a = val.find_first_not_of(" \t");
        val = (a == std::string::npos) ? "" : val.substr(a);
        while (!val.empty() && (val.back() == ' ' || val.back() == '\t')) val.pop_back();
        if (val == "|" || val == ">" || val == "|-" || val == ">-" || val == "|+" || val == ">+")
            literalIndent = keyCol;
    }
    return false;
}

inline bool yamlScanTabIndent(const std::string& path, std::string& badLine) {
    std::ifstream f(path);
    if (!f.is_open()) return false;
    return yamlScanTabIndent(f, badLine);
}

// YAML 안의 상대 경로는 그 YAML 파일이 있는 폴더(configDir, 끝 슬래시 없음) 기준으로 푼다.
// 절대 경로는 그대로 두고, 작업 폴더(CWD)로 되돌아가지 않는다. 예전엔 일부 op 이 '/' 없는
// 이름만 붙여 '../data/box.k' 같은 상대 경로를 실행 폴더에서 찾다 열지 못했다.
inline std::string yamlResolvePath(const std::string& configDir, const std::string& p) {
    if (configDir.empty() || p.empty()) return p;
    if (p.size() >= 2 && p[1] == ':') return p;      // Windows 절대 경로(X:\...)
    if (p[0] == '/' || p[0] == '\\') return p;       // POSIX 절대 경로 / UNC
    return configDir + "/" + p;
}

}  // namespace KooRemapper
