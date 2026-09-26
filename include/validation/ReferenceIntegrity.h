// 덱이 가리키는 세트 ID 가 실제로 정의돼 있나 — 없으면 LS-DYNA 가 키워드 단계에서 즉사한다
#pragma once

#include <string>
#include <vector>

namespace KooRemapper {

// 한 건의 미정의 참조.
struct DanglingRef {
    int line = 0;             // 1-기반 줄 번호
    std::string keyword;      // 그 참조가 있던 카드
    std::string what;         // "세트" 등 무엇을 가리키나
    int id = 0;               // 가리킨 ID
};

// 참조가 아니라 **카드 자체가 망가진** 것 — LS-DYNA 가 읽을 수 없거나 우리와 다르게 읽는다.
// 이 리포가 실제로 만들어 낸 손상들이다: `contact modify` 가 `_ID` 덱에서 줄을 한 칸 밀어
// 마찰계수를 SSID 칸에 덮어썼고, 선택 카드를 다시 쓰면서 필수 Card 3 를 지웠다(P1-4 가 그
// 쓰기를 고쳤다). 이 검사는 **이미 그렇게 망가진 덱을 알아보는** 쪽이다.
struct DamagedCard {
    int line = 0;             // 1-기반 줄 번호
    std::string keyword;      // 그 카드의 키워드
    std::string what;         // 사람이 읽을 한 문장
};

struct ReferenceReport {
    std::vector<DanglingRef> dangling;
    std::vector<DamagedCard> damaged;
    // ⚠ `*INCLUDE` 가 있으면 세트가 그 안에 정의됐을 수 있다. 그때는 "0건" 이라고 **말하면 안 된다**.
    bool hasUnreadIncludes = false;
    std::vector<std::string> includeNames;
    // 칸 뜻을 확신하지 못해 검사하지 않은 카드들 — 감추지 않고 세어 둔다.
    int notChecked = 0;
};

// 덱 원문에서 세트 ID 참조의 무결성을 본다.
//
// ⚠ 왜 필요한가 — 기존 스캐너(`scanDeadReferences`)는 **"이번 op 이 지웠나"** 만 보는 델타 검사다.
// "애초에 정의돼 있나" 는 아무도 안 본다. 실측: 없는 세트를 가리키는 카드를 5종 심은 덱이
// `info` 에서 `[OK] Mesh is valid` · rc=0 으로 통과했다. LS-DYNA 는 그 덱에서 Error 10144 로
// 키워드 단계에서 즉사한다 — 해석 시간을 쓰기도 전에.
//
// 강건성 원칙(오탐이 한 번 나면 아무도 이 보고를 안 믿는다):
//   · **칸 뜻이 확실한 카드만** 본다. 애매하면 검사하지 않고 `notChecked` 로 센다.
//   · `*PARAMETER` 참조(`&name`)가 있는 줄은 건너뛴다 — 값이 기호다.
//   · ID 0 은 "없음/전체" 의 관례라 절대 dangling 이 아니다.
//   · `*INCLUDE` 가 있으면 0건을 단정하지 않는다.
ReferenceReport checkSetReferences(const std::vector<std::string>& lines);

}  // namespace KooRemapper
