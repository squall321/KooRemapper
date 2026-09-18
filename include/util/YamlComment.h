// YAML 미니 파서 공용 함수 — 인라인 주석 제거·BOM 제거·들여쓰기(탭) 검사·상대 경로 해석을 한곳에 모아,
// 명령마다 따로 짠 파서가 같은 규칙을 쓰게 한다
#pragma once

#include <fstream>
#include <cctype>
#include <istream>
#include <sstream>
#include <string>
#include <vector>

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

// 앞뒤 공백·탭을 뗀다 — 파서마다 따로 있는 trim 과 같은 규칙.
inline std::string yamlTrimEdges(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t");
    return s.substr(a, b - a + 1);
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

// ── 블록 스칼라 머리표 ───────────────────────────────────────────────────────
// YAML 블록 스칼라는 '|'(줄바꿈 보존)·'>'(접기)에 잘라내기 지시자(-, +)와 명시 들여쓰기 숫자(1..9)가
// 어느 순서로든 붙을 수 있다('|-', '|+', '|2', '|2-', '|-2', '>', '>-' …).
// 예전엔 파서들이 val == "|" 로 정확 비교해 '|-' 같은 정상 표기를 '값' 으로 읽었고, 그 두 글자가
// 그대로 *MAT 카드가 되어 덱에 쓰레기 한 줄이 찍히고 MID 가 0 이 됐다.
struct YamlBlockHeader {
    bool isBlock = false;   // '|' 또는 '>' 로 여는 블록 스칼라인가
    bool folded  = false;   // '>' 계열 — 줄을 접는다(카드에는 사실상 오류)
    char chomp   = ' ';     // '-' = strip, '+' = keep, ' ' = clip(기본)
    int  indent  = 0;       // 명시 들여쓰기 지시자(0 = 없음)
};

// 값 부분(주석을 뗀 뒤)이 블록 머리표인지 본다. 머리표 문법이 아니면 isBlock=false —
// 그 값은 평문/따옴표 스칼라로 다뤄야 한다.
inline YamlBlockHeader yamlParseBlockHeader(const std::string& v) {
    YamlBlockHeader h;
    if (v.empty() || (v[0] != '|' && v[0] != '>')) return h;
    bool sawChomp = false, sawIndent = false;
    for (size_t i = 1; i < v.size(); ++i) {
        char c = v[i];
        if ((c == '-' || c == '+') && !sawChomp) { h.chomp = c; sawChomp = true; }
        else if (c >= '1' && c <= '9' && !sawIndent) { h.indent = c - '0'; sawIndent = true; }
        else return YamlBlockHeader();   // 머리표가 아니다 (예: '|foo')
    }
    h.isBlock = true;
    h.folded  = (v[0] == '>');
    return h;
}

// 탭 들여쓰기 거부 메시지 — 모든 YAML 파서가 load 가 쓰던 문구 그대로 쓴다.
// 검사는 파일 전체를 훑으므로 op 이 읽지도 않는 구역(주석 대신 쓴 메모, 미사용 키 블록)의 탭도 걸린다.
// 어느 줄인지 바로 찾도록 yamlScanTabIndent 가 badLine 을 '5번째 줄: <내용>' 꼴로 채워 준다.
inline std::string yamlTabIndentMessage(const std::string& tag, const std::string& trimmedLine) {
    return "[" + tag + "] YAML 들여쓰기에 탭을 쓸 수 없습니다 (공백을 쓰세요): " + trimmedLine;
}

// YAML 파일 전체에서 들여쓰기 탭을 찾는다(찾으면 true + 그 줄). 파서마다 흩어져 있던 countIndent 는
// 공백만 세서, 탭으로 들여쓴 YAML 은 모든 줄이 indent 0 이 되어 블록이 통째로 무너지고도 rc=0 으로
// '아무 일도 안 한' 덱을 냈다 — 파싱 전에 한 번 걸러 rc=1 로 알린다.
// '|'/'>' 리터럴 블록 안의 줄은 구조가 아니라 값이므로 보지 않는다(LS-DYNA 카드 줄) — 단 블록 안이라는
// 판정은 파서(countIndent)와 똑같이 '공백 들여쓰기' 만으로 한다. 예전엔 여기서 탭으로 시작한 카드 줄도
// 블록 안으로 봐 통과시켰는데, 파서는 공백만 세어 그 줄을 블록 밖으로 튕겨 조용히 버렸다 —
// *MAT 카드가 데이터 줄 없이 덱에 실리고도 rc=0 이었다. 이제 그 줄은 구조 줄로 보아 rc=1 로 막는다.
inline bool yamlScanTabIndent(std::istream& f, std::string& badLine) {
    yamlSkipBOM(f);
    int literalIndent = -1;  // '|' 블록을 연 키의 들여쓰기 (-1 = 블록 밖)
    std::string ln;
    int lineNo = 0;
    while (std::getline(f, ln)) {
        ++lineNo;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        size_t ns = ln.find_first_not_of(" \t");
        std::string tr = (ns == std::string::npos) ? "" : ln.substr(ns);
        while (!tr.empty() && (tr.back() == ' ' || tr.back() == '\t')) tr.pop_back();
        int width = (ns == std::string::npos) ? -1 : (int)ns;
        if (literalIndent >= 0) {
            // 블록은 파서와 같은 규칙으로 닫는다 — 들여쓰기는 공백만 센다(yamlCountIndent).
            if (tr.empty() || yamlCountIndent(ln) > literalIndent) continue;
            literalIndent = -1;
        }
        if (tr.empty() || tr[0] == '#') continue;
        if (yamlTabIndent(ln)) { badLine = std::to_string(lineNo) + "번째 줄: " + tr; return true; }
        // 블록을 여는 줄 — standalone_ops 의 countOperations 와 같은 판정.
        // 목록 항목 '- |' 는 대시 열이, 'key: |'(항목 안의 '- key: |' 포함)은 키 열이 기준이다.
        std::string item = yamlStripComment(tr);
        while (!item.empty() && (item.back() == ' ' || item.back() == '\t')) item.pop_back();
        if (item.size() >= 1 && item[0] == '-' &&
            yamlParseBlockHeader(yamlTrimEdges(item.substr(1))).isBlock) { literalIndent = width; continue; }
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
        if (yamlParseBlockHeader(val).isBlock) literalIndent = keyCol;
    }
    return false;
}

// 경로판 — 검사를 위해 설정 파일을 '한 번 더' 여는 것이므로, 되감을 수 없는 입력(파이프, 프로세스
// 치환 <(...), /dev/stdin)이면 그 한 번이 전부다. 그런 입력은 검사가 스트림을 먹어 뒤따르는 파서가
// 빈 설정을 보고 "'model' not specified" 로 끝나므로, 아예 훑지 않고 통과시킨다 —
// 탭 들여쓰기 검사는 되감을 수 있는 보통 파일에서만 돈다.
inline bool yamlScanTabIndent(const std::string& path, std::string& badLine) {
    std::ifstream f(path);
    if (!f.is_open()) return false;
    if (!f.seekg(0)) return false;  // seek 불가 = 되감을 수 없는 스트림 (아직 한 글자도 읽지 않았다)
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

// 블록 끝의 빈 줄 처리(chomping). strip('-')·clip(기본)은 끝 줄바꿈을 버리고, keep('+')은 남긴다.
// 카드는 줄 단위라 끝 빈 줄이 덱에 그대로 찍히면 assemble 과 단독 결과가 갈렸다.
inline void yamlChompBlock(std::string& block, char chomp) {
    if (chomp == '+') return;
    while (!block.empty() && (block.back() == '\n' || block.back() == '\r')) block.pop_back();
}

// ── 따옴표 스칼라 ────────────────────────────────────────────────────────────
// 플랫폼(argbuild)·pyKooCAE(yaml.safe_dump)는 조건에 따라 카드를 따옴표 스칼라 한 값으로 내보낸다
// ("*MAT_ELASTIC_TITLE\nSubstrate\n…"). 이스케이프를 풀지 않으면 그 한 줄이 통째로 카드가 되어
// 덱이 깨졌다 — 웹·MCP·체인 경로로 들어온 정상 카드가 조용히 망가지는 자리다.
inline bool yamlIsQuotedScalar(const std::string& v) {
    return v.size() >= 2 && ((v.front() == '"' && v.back() == '"') ||
                             (v.front() == '\'' && v.back() == '\''));
}

// 코드포인트를 UTF-8 로 붙인다(\uXXXX 복원용 — safe_dump 는 한글 제목을 이 꼴로 내보낸다).
inline void yamlAppendUtf8(std::string& out, unsigned long cp) {
    if (cp < 0x80) out += (char)cp;
    else if (cp < 0x800) { out += (char)(0xC0 | (cp >> 6)); out += (char)(0x80 | (cp & 0x3F)); }
    else if (cp < 0x10000) {
        out += (char)(0xE0 | (cp >> 12));
        out += (char)(0x80 | ((cp >> 6) & 0x3F));
        out += (char)(0x80 | (cp & 0x3F));
    } else {
        out += (char)(0xF0 | (cp >> 18));
        out += (char)(0x80 | ((cp >> 12) & 0x3F));
        out += (char)(0x80 | ((cp >> 6) & 0x3F));
        out += (char)(0x80 | (cp & 0x3F));
    }
}

// 따옴표 스칼라를 YAML 규격대로 푼다. 큰따옴표는 \n \t \r \\ \" \/ \0 \a \b \f \v \e \<공백>
// \xHH \uHHHH \UHHHHHHHH 를, 작은따옴표는 '' 만 이스케이프로 본다. 따옴표가 아니면 그대로 돌려준다.
inline std::string yamlDecodeQuotedScalar(const std::string& v) {
    if (!yamlIsQuotedScalar(v)) return v;
    std::string body = v.substr(1, v.size() - 2);
    std::string out;
    if (v.front() == '\'') {
        for (size_t i = 0; i < body.size(); ++i) {
            if (body[i] == '\'' && i + 1 < body.size() && body[i + 1] == '\'') { out += '\''; ++i; }
            else out += body[i];
        }
        return out;
    }
    for (size_t i = 0; i < body.size(); ++i) {
        if (body[i] != '\\') { out += body[i]; continue; }
        if (++i >= body.size()) break;
        char c = body[i];
        int hex = (c == 'x') ? 2 : (c == 'u') ? 4 : (c == 'U') ? 8 : 0;
        if (hex > 0) {
            unsigned long cp = 0; int got = 0;
            while (got < hex && i + 1 < body.size() && std::isxdigit((unsigned char)body[i + 1])) {
                char d = body[++i];
                cp = cp * 16 + (unsigned long)(d <= '9' ? d - '0' : (d | 0x20) - 'a' + 10);
                ++got;
            }
            if (got == hex) yamlAppendUtf8(out, cp);
            else out += c;               // 자릿수가 모자라면 이스케이프가 아니다 — 글자 그대로
            continue;
        }
        switch (c) {
            case 'n':  out += '\n'; break;
            case 't':  out += '\t'; break;
            case 'r':  out += '\r'; break;
            case '0':  out += '\0'; break;
            case 'a':  out += '\a'; break;
            case 'b':  out += '\b'; break;
            case 'f':  out += '\f'; break;
            case 'v':  out += '\v'; break;
            case 'e':  out += '\x1b'; break;
            case 'N':  yamlAppendUtf8(out, 0x85); break;
            case '_':  yamlAppendUtf8(out, 0xA0); break;
            case 'L':  yamlAppendUtf8(out, 0x2028); break;
            case 'P':  yamlAppendUtf8(out, 0x2029); break;
            default:   out += c; break;  // \" \\ \/ \<공백> 와 모르는 이스케이프는 글자 그대로
        }
    }
    return out;
}

// 값이 따옴표로 열렸는데 그 줄에서 닫히지 않으면 YAML 은 다음 줄로 이어 읽는다.
// PyYAML(yaml.safe_dump)은 80칸이 넘는 카드를 '\' + 줄바꿈으로 접어 내보내므로, 이어 읽지 않으면
// 체인·웹에서 온 긴 카드가 통째로 깨진다. lines[li] 의 값이 firstVal 일 때 닫는 따옴표까지 이어 붙여
// 따옴표째로 joined 에 담고, 마지막으로 소비한 줄 번호를 endLine 에 준다. 닫히지 않으면 false.
inline bool yamlJoinQuotedScalar(const std::vector<std::string>& lines, size_t li,
                                 const std::string& firstVal, std::string& joined, size_t& endLine) {
    if (firstVal.empty() || (firstVal[0] != '"' && firstVal[0] != '\'')) return false;
    const char q = firstVal[0];
    std::string acc, cur = firstVal.substr(1);
    size_t i = li;
    for (;;) {
        size_t p = 0, closeAt = std::string::npos;
        while (p < cur.size()) {
            if (q == '"') {
                if (cur[p] == '\\') { p += 2; continue; }
                if (cur[p] == '"') { closeAt = p; break; }
            } else if (cur[p] == '\'') {
                if (p + 1 < cur.size() && cur[p + 1] == '\'') { p += 2; continue; }
                closeAt = p; break;
            }
            ++p;
        }
        if (closeAt != std::string::npos) {
            acc += cur.substr(0, closeAt);
            endLine = i;
            joined = std::string(1, q) + acc + std::string(1, q);
            return true;
        }
        // 줄이 끝났다 — 다음 줄로 이어진다. 끝 공백은 버리고, 홀수 개 '\' 로 끝나면
        // 줄바꿈 자체가 이스케이프된 것이라 아무것도 넣지 않는다(아니면 공백 하나로 접힌다).
        while (!cur.empty() && (cur.back() == ' ' || cur.back() == '\t')) cur.pop_back();
        bool escapedBreak = false;
        if (q == '"') {
            size_t bs = 0;
            while (bs < cur.size() && cur[cur.size() - 1 - bs] == '\\') ++bs;
            escapedBreak = (bs % 2) == 1;
        }
        if (escapedBreak) { cur.pop_back(); acc += cur; }
        else { acc += cur; acc += ' '; }
        if (++i >= lines.size()) return false;
        cur = lines[i];
        if (!cur.empty() && cur.back() == '\r') cur.pop_back();
        size_t a = cur.find_first_not_of(" \t");
        cur = (a == std::string::npos) ? "" : cur.substr(a);
    }
}

// ── 카드 값 판정 ─────────────────────────────────────────────────────────────
// 카드로 쓸 수 없는 값을 걸러 낸다. *MAT 키워드 줄이 없거나(예: '|-', 'Substrate'),
// 키워드 줄만 있고 데이터 줄이 없으면(예: 한 줄짜리 '*MAT_ELASTIC') MID 를 찾을 자리가 없어
// *PART 의 mid 칸이 0 인 덱이 조용히 나온다 — 그런 값은 rc=1 로 거절한다.
// 이유를 why 에 한국어+영어로 담는다. 카드로 볼 수 있으면 true.
inline bool yamlCardLooksUsable(const std::string& card, std::string& why) {
    std::vector<std::string> body;
    {
        std::istringstream iss(card);
        std::string ln;
        while (std::getline(iss, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            size_t a = ln.find_first_not_of(" \t");
            if (a == std::string::npos) continue;          // 빈 줄
            body.push_back(ln.substr(a));
        }
    }
    size_t kw = body.size();
    for (size_t i = 0; i < body.size(); ++i)
        if (body[i][0] == '*') { kw = i; break; }
    if (kw == body.size()) {
        why = "*MAT 키워드 줄이 없습니다 / no '*MAT...' keyword line";
        return false;
    }
    for (size_t i = kw + 1; i < body.size(); ++i)
        if (body[i][0] != '$') return true;                 // 주석($)이 아닌 내용 줄이 있다
    why = "키워드 줄 뒤에 데이터 줄이 없습니다 — MID 를 쓸 자리가 없어 mid 0 덱이 됩니다 / "
          "no data line after the keyword line";
    return false;
}

// '>' 블록은 줄을 접어 카드를 한 줄로 만든다 — LS-DYNA 카드는 줄 단위라 접힌 카드는 반드시 깨진다.
// 받아들여 경고만 내면 '조용히 틀린 덱' 이 되므로 거절한다('|' 로 바꾸라고 알린다).
inline std::string yamlFoldedCardMessage(const std::string& key) {
    return key + ": '>' 블록은 카드를 한 줄로 접어 덱이 깨집니다 — '|' 를 쓰세요 / "
                 "folded ('>') block scalars join the card into one line; use '|'";
}

}  // namespace KooRemapper
