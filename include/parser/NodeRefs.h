// 절점을 가리키는 카드 칸 — 정본 하나(`info --strict` 의 미정의 절점 · meshfix 의 쓰기 뒤 대조가 같은 표를 본다)
#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <vector>

namespace KooRemapper {
namespace noderefs {

// 절점 하나를 가리키는 칸 하나. 키워드 글자는 담지 않는다(전체 절점 세트가 1,300만 멤버인 덱이 있다) —
// `keywordOf` 로 꺼낸다.
struct Ref {
    size_t line = 0;        // 0-기반 줄
    size_t kwLine = 0;      // 그 카드의 키워드 줄(0-기반)
    int value = 0;          // 칸에 적힌 절점 번호(양수만 — 0 은 「없음」 관례다)
    int col = -1;           // 고정폭 칸이 시작하는 열(0-기반). 자유형식·어긋난 줄이면 -1 — 제자리에 바꿔 쓸 수 없다
    int width = 0;          // 그 칸의 폭
};

struct Scan {
    std::vector<Ref> refs;
    // 절점을 가리키는 줄 알지만 칸 뜻을 **단정하지 못해** 건너뛴 블록·줄 수 — 감추지 않고 센다.
    int notChecked = 0;
    std::vector<std::string> notCheckedKeywords;   // 처음 본 몇 개
};

// 덱 줄에서 절점을 가리키는 칸을 모은다. `deckFw` 는 덱의 기본 정수 칸 폭(`deckFieldWidth` — 8·10·20).
// `keep` 이 있으면 그것이 참인 값만 담는다(미정의만 · 지운 절점만 — 큰 덱에서 전부 담지 않으려고).
Scan find(const std::vector<std::string>& lines, int deckFw,
          const std::function<bool(int)>& keep = nullptr);

// 이 키워드(대문자 · 칸폭 접미사 뗌) 블록이 `find` 가 칸을 읽는 갈래인가 — 큰 덱을 흘려 읽는 쪽이
// 이 블록만 담으려고 쓴다(`*NODE`·`*ELEMENT_` 를 통째로 들지 않는다).
bool mayReference(const std::string& kw);

// 그 참조의 키워드(대문자 · 칸폭 접미사 뗌).
std::string keywordOf(const std::vector<std::string>& lines, const Ref& r);

// 정의된 절점 번호(정렬 · 중복 없음) — `*NODE` 계열 블록의 첫 칸을 **넘치게** 모은다(놓칠 수는 있어도
// 없는 것을 있다고 말하지 않는다). 맨 `*NODE` 블록이 하나라도 있었는지를 `anyNodeBlock` 으로 돌려준다.
std::vector<int> defined(const std::vector<std::string>& lines, int deckFw, bool* anyNodeBlock = nullptr);

}  // namespace noderefs
}  // namespace KooRemapper
