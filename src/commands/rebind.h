// 재메시 뒤 덧붙인 블록의 절점 번호를 (파트 이름, 좌표)로 새 덱 번호에 다시 묶는 op 의 본체
#pragma once

#include <string>

namespace KooRemapper {
class ConsoleOutput;

namespace rebind {

// 경로는 부르는 쪽이 이미 YAML 폴더 기준으로 푼 것이다.
struct Input {
    std::string oldDeck;     // 덧붙인 블록이 가리키던 덱(그 번호의 정본)
    std::string newDeck;     // 다시 구운 덱
    std::string entities;    // 우리가 덧붙인 블록만 든 .k — old_deck 번호를 가리킨다
    std::string output;      // new_deck 번호로 옮긴 블록(.k)
    std::string rangeDiff;   // (선택) StepForge 구간 표 JSON — 두 덱을 `coord_sha` 로 대조한다
};

// rc 0 = 다 묶어 썼다. rc 1 = 하나라도 못 풀었거나 거절했다(산출을 쓰지 않는다).
int run(const Input& in, ConsoleOutput& console);

}  // namespace rebind
}  // namespace KooRemapper
