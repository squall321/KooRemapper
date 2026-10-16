// 엄격한 JSON 리더 — 계약 파일(StepForge 조각 대응표 등)을 읽는다. 문법 밖의 꼴은 말하고 거절한다
#pragma once

#include <string>
#include <utility>
#include <vector>

namespace KooRemapper {
namespace json {

// 왜 따로 두나 (2026-10-16). matdb 의 `md_parseJson` 은 너그럽다 — `\uXXXX` 를 풀지 않고, 잘못된 꼴을 말없이
// 넘긴다. 재질 DB 에는 그것이 맞았을지 몰라도(옮기지 않는다 — 동작이 바뀐다) 계약 파일은 「모르는 칸은
// 거절한다」고 저쪽에 약속했다. 그 약속은 문법부터 엄격해야 지킬 수 있다.
struct Value {
    enum class Type { Null, Bool, Int, Real, String, Array, Object };
    Type type = Type::Null;
    bool b = false;
    long long i = 0;        // Int — 소수점·지수가 없는 정수(int64 안)
    double d = 0;           // Real
    std::string s;          // String(UTF-8)
    std::vector<Value> arr;
    std::vector<std::pair<std::string, Value>> obj;   // 적힌 차례 그대로

    const Value* get(const std::string& key) const;
    bool isNull() const { return type == Type::Null; }
};

// 성공하면 true. 실패하면 err 에 「몇째 바이트에서 무엇이」를 적는다.
// 거절 — 꼬리 쓰레기 · 한 객체 안의 같은 키 · 잘못된 이스케이프 · 문자열 안의 제어 문자 · JSON 문법 밖의 수
// (앞 0 · `+` · `.5` · `1.`) · int64 를 넘는 정수 · 짝이 맞지 않는 서로게이트 `\u` · 깊이 64 초과.
bool parse(const std::string& text, Value& out, std::string& err);

}  // namespace json
}  // namespace KooRemapper
