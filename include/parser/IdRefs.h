// 파트·요소를 가리키는 카드 칸 — 정본(재결속이 PID·EID 를 옮길 때 쓴다). 칸 뜻이 확실한 갈래만 보고 나머지는 세어만 둔다
#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <vector>

namespace KooRemapper {
namespace idrefs {

enum class Axis { Part, Elem };

// 파트(PID) 또는 요소(EID) 하나를 가리키는 칸 하나 — 꼴은 `noderefs::Ref` 와 같다.
struct Ref {
    size_t line = 0;        // 0-기반 줄
    size_t kwLine = 0;      // 그 카드의 키워드 줄
    Axis axis = Axis::Part;
    int value = 0;          // 양수만
    int col = -1;           // 고정폭 칸이 시작하는 열 · 자유형식·어긋난 줄이면 -1
    int width = 0;
};

struct Scan {
    std::vector<Ref> refs;
    int notChecked = 0;                            // PID·EID 를 가리키는 줄 알지만 칸 뜻을 단정하지 못한 자리
    std::vector<std::string> notCheckedKeywords;
};

// 덱 줄에서 파트·요소를 가리키는 칸을 모은다. `keep(axis, value)` 가 있으면 참인 것만 담는다.
//   파트 — `*SET_PART`(목록 · `_COLUMN` 칸 1) · `*CONTACT_*` Card 1 의 SSID/MSID(SSTYP/MSTYP = 3 일 때만 —
//          서명 STYP 0..6 이 맞을 때) · `*CONSTRAINED_RIGID_BODIES`(PIDL PIDC)
//   요소 — `*SET_SOLID`·`*SET_SHELL`·`*SET_BEAM`·`*SET_TSHELL`(목록 · `_COLUMN` 칸 1) ·
//          `*DATABASE_HISTORY_SOLID`·`_SHELL`·`_BEAM`·`_TSHELL`(맨 키워드 · 칸 1-8)
//   세어만 둔다 — `_GENERATE`·`_GENERAL` 세트 · 이력 `_ID`·`_LOCAL` · 초기응력·변형률 · 파트 감쇠 · 강체 강제운동 ·
//          `*ELEMENT_MASS` 의 0 아닌 PID · 서명이 안 맞는 접촉
Scan find(const std::vector<std::string>& lines, int deckFw,
          const std::function<bool(Axis, int)>& keep = nullptr);

// 이 키워드(대문자 · 접미사 뗌) 블록이 `find` 가 칸을 읽거나 세어 두는 갈래인가.
bool mayReference(const std::string& kw);

std::string keywordOf(const std::vector<std::string>& lines, const Ref& r);

}  // namespace idrefs
}  // namespace KooRemapper
