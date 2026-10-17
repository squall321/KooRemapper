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

// ── 정본 표 — `find` 와 `ModelAssembler::cleanupDeadNodeRefs`(지운 절점을 고치는 쪽)가 **같은 표**를 본다 ──
// 칸 하나가 절점인 한 줄짜리 카드(이름이 정확히 같을 때만 — `_ID` 등 변종은 카드가 한 장 더 붙는다).
// `eightWide` — 매뉴얼 표가 1-10 칸(8칸 폭)이라 i10·long 덱에서 덱 정수 폭을 따른다. 나머지는 1-8 칸 표(10칸 폭).
struct OneFieldCard { const char* keyword; int field; bool eightWide; };
const std::vector<OneFieldCard>& oneFieldCards();
// 정의 카드의 정해진 칸이 절점인 카드 — CNRB 의 PNODE · 좌표계 절점. 옵션 없는 맨 키워드는 줄마다 정의 하나다.
struct DefinitionNodeCard { const char* keyword; std::vector<int> fields; };
const std::vector<DefinitionNodeCard>& definitionNodeCards();

// ── 정본 표 ③ — 멤버 줄의 칸이 절점인 **목록** 카드(세트 · 세그먼트 · 이력) ──
// 고치는 동작(다시 채우기 · 줄 빼기 · 칸 비우기)은 갈래마다 달라 `cleanupDeadNodeRefs` 에 둔다 — **어느 블록이 목록인가**와
// **어느 칸이 절점인가**만 여기서 정한다(2026-10-17). 예전에는 그 장치에 범위 사본이 있었고 세트 분류도 따로 해서
// `_ADD` 만 건너뛰었다 — `*SET_NODE_INTERSECT`·`*SET_SEGMENT_INTERSECT` 의 멤버(**세트 ID**)를 절점으로 읽어, restack 이
// 지운 절점과 번호가 같은 세트 ID 를 교집합에서 빼 세트를 **비웠다**(실측).
//   SetNodeList    — `*SET_NODE`·`_LIST`·`_LIST_SMOOTH` Card 2a 칸 1-8                       Vol_I 234448-234512
//   SetNodeColumn  — `*SET_NODE_COLUMN` Card 2b 칸 1                                        234448-234512
//   SetNodeGeneral — `*SET_NODE_GENERAL` 의 OPTION 이 NODE·DNODE 인 줄의 E1..E7(칸 2-8)          234634-234779
//   SetSegment     — `*SET_SEGMENT` 멤버 줄 칸 1-4 = N1..N4                                    235953-236060
//   HistoryNode    — `*DATABASE_HISTORY_NODE` Card 1a 칸 1-8                                  122112-122180
//   None           — 목록이 아니다. `_ADD`·`_INTERSECT`(멤버가 세트 ID) · `_GENERATE`(범위) · `_GENERAL` 세그먼트(옵션 줄) …
enum class ListCard { None, SetNodeList, SetNodeColumn, SetNodeGeneral, SetSegment, HistoryNode };
// 이 키워드(대문자 · 칸폭 접미사 뗌)가 어느 목록 카드인가 — 세트 분류는 `deckscan::classifySetNode` 를 따른다.
ListCard listCardOf(const std::string& kw);
// 그 목록 카드의 멤버 줄에서 절점인 칸(0-기반).
const std::vector<int>& listCardFields(ListCard c);
// 첫 멤버 줄 앞에 오는 데이터 줄 수 — 세트·세그먼트는 [제목] + Card 1(SID …), 이력은 0.
size_t listCardHeader(ListCard c, const std::string& kw);

// 그 참조의 키워드(대문자 · 칸폭 접미사 뗌).
std::string keywordOf(const std::vector<std::string>& lines, const Ref& r);

// 정의된 절점 번호(정렬 · 중복 없음) — `*NODE` 계열 블록의 첫 칸을 **넘치게** 모은다(놓칠 수는 있어도
// 없는 것을 있다고 말하지 않는다). 맨 `*NODE` 블록이 하나라도 있었는지를 `anyNodeBlock` 으로 돌려준다.
std::vector<int> defined(const std::vector<std::string>& lines, int deckFw, bool* anyNodeBlock = nullptr);

}  // namespace noderefs
}  // namespace KooRemapper
