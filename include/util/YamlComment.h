// YAML 한 줄 값에서 인라인 주석을 떼는 공용 함수 — 명령마다 따로 짠 미니 파서가 같은 규칙을 쓰게 한다
#pragma once

#include <string>

namespace KooRemapper {

// 'key: value   # 주석' 의 value 부분에서 주석을 뗀다. YAML 규칙대로 따옴표 밖에서 공백 뒤(또는 맨 앞)의 '#'
// 부터가 주석이다 — "Part #1" 같은 따옴표 안 #, 공백 없이 붙은 #(예: A#1)은 값으로 둔다.
// 예전엔 파서 대부분이 주석까지 값으로 읽어 'box.k   # 모델' 파일을 찾거나, 'vrh  # 평균' 을 모르는 값으로 보고
// 조용히 기본값으로 계산했다.
inline std::string yamlStripComment(const std::string& s) {
    size_t i = s.find_first_not_of(" \t");
    if (i == std::string::npos) return s;
    if (s[i] == '"' || s[i] == '\'') {
        size_t close = s.find(s[i], i + 1);
        if (close == std::string::npos) return s;
        i = close + 1;
    }
    for (; i < s.size(); ++i) {
        if (s[i] == '#' && (i == 0 || s[i - 1] == ' ' || s[i - 1] == '\t')) {
            size_t e = i;
            while (e > 0 && (s[e - 1] == ' ' || s[e - 1] == '\t')) --e;
            return s.substr(0, e);
        }
    }
    return s;
}

}  // namespace KooRemapper
