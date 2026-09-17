// YAML 한 줄 값에서 인라인 주석을 떼는 공용 함수 — 명령마다 따로 짠 미니 파서가 같은 규칙을 쓰게 한다
#pragma once

#include <string>

namespace KooRemapper {

// 'key: value   # 주석' 의 value 부분에서 주석을 뗀다. YAML 규칙대로 따옴표 밖에서 공백 뒤(또는 맨 앞)의 '#'
// 부터가 주석이다 — "Part #1" 같은 따옴표 안 #, 공백 없이 붙은 #(예: A#1)은 값으로 둔다.
// 예전엔 파서 대부분이 주석까지 값으로 읽어 'box.k   # 모델' 파일을 찾거나, 'vrh  # 평균' 을 모르는 값으로 보고
// 조용히 기본값으로 계산했다.
// 따옴표는 값 맨 앞뿐 아니라 '[' '{' ',' 공백 뒤에서도 열린다 — 예전엔 맨 앞 따옴표만 봐
// 'keywords: ["*NODE # x", "*ELEMENT_SOLID"]' 가 '#' 에서 잘려 '"*NODE' 하나만 남았다.
inline std::string yamlStripComment(const std::string& s) {
    size_t start = s.find_first_not_of(" \t");
    if (start == std::string::npos) return s;
    for (size_t i = start; i < s.size(); ++i) {
        bool afterSpace = (i == 0 || s[i - 1] == ' ' || s[i - 1] == '\t');
        if ((s[i] == '"' || s[i] == '\'') &&
            (i == start || afterSpace || s[i - 1] == '[' || s[i - 1] == '{' || s[i - 1] == ',')) {
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

}  // namespace KooRemapper
