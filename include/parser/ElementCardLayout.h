#pragma once
// LS-DYNA *ELEMENT_{SOLID,SHELL,TSHELL} 카드 한 장이 몇 줄인지를 매뉴얼 표로 확정하는 공용 판정기
//
// 왜 따로 두는가: 리더(KFileReader)와 쓰기(ModelAssembler::writeOutput)가 서로 다른 어림짐작을
// 쓰면 한쪽이 요소로 읽은 줄을 다른 쪽이 노드 줄로 버린다. 현장에서 AP 칩 37,100 요소가
// 조용히 사라진 사고가 정확히 그것이었다. 판정은 여기 한 곳에서만 한다.
//
// 근거: LS-DYNA R16 Keyword Manual Vol_I (docs/LSDyna/Vol_I.txt, R16@e545952c7 03/21/25)
//   *ELEMENT_SOLID  : 163572-163667 (옵션·Card Summary), 164017-164034(변환 옵션),
//                     164055-164057(옵션 이름 = 절점 수), 164121-164158(구 포맷 Remark 4)
//   *ELEMENT_SHELL  : 162018-162029(옵션), 162066-162372(Card 1-7), 162567-162571(Remark 6)
//   *ELEMENT_TSHELL : 165153-165157(옵션), 165173-165198(Card Summary), 165328-165337(COMPOSITE)
//   칸 폭          : 19315-19322(long '+'), 19342-19360(i10 '%')
//
// @lat: [[modules/parser]]

#include <string>
#include <vector>

namespace KooRemapper {

enum class ElemFamily { NONE, SOLID, SHELL, TSHELL };

// 키워드 줄 하나를 풀어 놓은 결과
struct ElementKeywordInfo {
    ElemFamily family = ElemFamily::NONE;
    std::string keyword;          // 정규화(대문자, 접미사·꼬리글 제거)한 키워드
    // --- 솔리드 ---
    int  optionNodes = 0;         // H20/T15/... 옵션이 정한 절점 수. 0 = 옵션이 말하지 않음
    // --- 공통 ---
    int  extraCards = 0;          // 노드 카드 뒤에 반드시 따라오는 고정 카드 수
    bool thicknessCard = false;   // shell: THICKNESS/BETA/MCID → Card 2(중간절점이면 Card 3 도)
    bool dataDependent = false;   // COMPOSITE 계열 — 줄 수가 데이터로만 정해진다
    // --- 칸 폭 접미사 (19342-19360) ---
    bool i10Suffix = false;       // '%'
    bool longSuffix = false;      // '+'
    bool stdSuffix = false;       // '-'
    // --- 판정 ---
    bool supported = true;        // 이 변형을 읽고 쓸 수 있는가
    std::string reason;           // supported=false 일 때 rc=1 로 낼 이유
};

// 키워드 줄(예: "*ELEMENT_SOLID_ORTHO", "*ELEMENT_SHELL_THICKNESS") 을 푼다.
// 키워드 뒤에 붙는 설명 문구(LS-PrePost 의 "(ten nodes format)" 등)는 매뉴얼에 없는 관행이라
// 첫 공백에서 잘라 버린다 — 줄 수 판정에 쓰지 않는다.
ElementKeywordInfo parseElementKeyword(const std::string& keywordLine);

// ── 칸 폭 ────────────────────────────────────────────────────────────────────
// 매뉴얼이 정한 것은 셋뿐이다(Vol_I 19305-19360).
//   표준      : 정수 8 칸, *NODE 는 (I8,3F16,2I8)                       19348
//   i10=y / % : 8 칸짜리 정수 칸만 10 칸으로 — *NODE 는 (I10,3F16,2I10)  19356-19360
//   long=y / +: 20 칸으로 — *NODE 는 (I20,3F20,2I20)                     19307, 19342-19345
// long=s 는 "read standard … write long" 이므로 읽기 폭은 표준이다(19308).
// 리더도 쓰기도 이 한 곳에서만 폭을 정한다 — 한쪽이 8 칸으로 쓰고 다른 쪽이 10 칸으로 읽으면
// 새 층이 통째로 사라진다(현장 사고와 같은 모양).

// *KEYWORD 줄 하나가 정하는 덱 기본 정수 칸 폭. 정하지 않으면 0.
int keywordCardDeckWidth(const std::string& keywordLine);

// 덱 전체의 기본 정수 칸 폭(*KEYWORD 가 없거나 말하지 않으면 8).
int deckFieldWidth(const std::vector<std::string>& lines);

// 키워드 줄 접미사('%'=10, '+'=20, '-'=8)가 덱 기본값을 덮어쓴다(19342-19360).
int keywordFieldWidth(const std::string& keywordLine, int deckFw);

// 같은 카드의 실수 칸 폭 — 표준·i10 은 16, long 은 20 (19345, 19348, 19360).
int realFieldWidth(int intFw);

// *SECTION_SOLID 의 ELFORM → 절점 수. 고차 정식이 아니면 0.
// Vol_I 228671-228677: 23=20절점, 24=27, 25=21, 26=15, 27=20(cubic tet), 28=40, 29=64.
int solidNodesFromElform(int elform);

// ── 카드 한 장의 줄 수 + **절점 칸이 어디인가** ─────────────────────────────
// 왜 공용인가 (2026-10-11). 이 사다리(고차 정식 → `solidCardLines`, 구 포맷 → 한 줄,
// 그 밖 → Card 1 + Card 2)는 `src/assembly/ModelAssembler.cpp` 의 `ecBuildIndex` **안에만**
// 있었다. `cleanup-nodes` 는 절점 참조를 세려면 **같은 판정**이 필요하다 — 베끼면 둘이 갈리고,
// 갈리면 한쪽이 '연결 줄' 로 본 줄을 다른 쪽이 'Card 1' 로 읽어 절점 참조를 통째로 놓친다.
// 그러면 **쓰이는 절점이 지워진다.** 그래서 베끼지 않고 여기로 옮겼다.
//
// ⚠ 표준 포맷의 Card 1 에는 **절점이 없다** — EID·PID 뿐이고 절점은 Card 2 부터다
// (163572-163667). 절점이 Card 1 에 있는 것은 구 포맷(164121-164158) 과 셸·티쉘뿐이다.
// 그래서 '첫 줄의 칸 2 부터가 절점' 이라고 뭉개면 솔리드에서 전부 틀린다.
struct ElementCardSpan {
    int lines = 1;          // 카드 전체 데이터 줄 수(두께·재질축 등 고정 추가 카드 포함)
    int nodeFirst = 0;      // 절점 칸이 시작하는 **카드 안 줄 번호**(0 = 카드 첫 줄)
    int nodeLines = 1;      // 그 줄부터 **몇 줄**이 절점 칸인가
    int nodeFieldSkip = 2;  // `nodeFirst` 줄에서 절점이 시작하는 칸 번호
};

// card1Fields  : 카드 첫 줄을 칸으로 나눈 것(칸 0=EID, 1=PID).
// pidNodeCount : 그 PID 요소의 절점 수(모르면 0) — *PART → *SECTION_SOLID 의 ELFORM.
ElementCardSpan elementCardSpan(const ElementKeywordInfo& info,
                                const std::vector<std::string>& card1Fields,
                                int pidNodeCount);

// 솔리드 카드 줄 수 = Card 1(1줄) + 노드 카드 ceil(nodes/10) + 고정 추가 카드.
// Card 3 은 "Include as many of this card as needed"(163632-163634)라 10 칸씩 반복한다.
int solidCardLines(int nodes, int extraCards);

}  // namespace KooRemapper
