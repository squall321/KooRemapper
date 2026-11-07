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

#include <cstddef>
#include <functional>
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

// 덱에 `*KEYWORD` 카드가 있나. 매뉴얼은 「*KEYWORD 가 **첫 카드**가 아니면 옛 structured
// 입력으로 읽는다」고 못박았다(Vol_I 18086-18087, 18566-18568) — 쓰는 쪽은 없으면 넣어야
// 하고, **있으면 앞세우면 안 된다**(deckFieldWidth 가 첫 것에서 멈추므로 i10 덱이 8칸으로
// 읽힌다). 그 판정을 세 쓰기 경로가 따로 베끼지 않도록 여기 하나로 둔다.
bool hasKeywordCard(const std::vector<std::string>& lines);

// 키워드 줄 접미사('%'=10, '+'=20, '-'=8)가 덱 기본값을 덮어쓴다(19342-19360).
int keywordFieldWidth(const std::string& keywordLine, int deckFw);

// 같은 카드의 실수 칸 폭 — 표준·i10 은 16, long 은 20 (19345, 19348, 19360).
int realFieldWidth(int intFw);

// ── 보·질량·이산 족 — **격자 요소가 아닌** `*ELEMENT_*` ──────────────────────
//
// 왜 `ElemFamily` 를 넓히지 않고 **별도 축**인가 (2026-10-11).
//   `ElemFamily` 는 격자(솔리드·셸·티쉘)를 뜻하고, 그 값을 보는 소비자가 셋 더 있다.
//     · `ModelAssembler::ecBuildIndex` — `famOf` 를 'S'/'H'/**'T'(그 밖 전부)** 로 적고
//       `countByPid` 를 센다. 보를 끼우면 보가 **티쉘로 거짓 분류**되고 파트 요소 수가 바뀐다.
//     · `KFileReader` — 섹션별 카드 줄 수로 요소를 읽는다.
//     · `cnrb2spring` — `supported`/`extraCards` 로 거절을 판정한다.
//   그 셋은 격자만 다루면 되고, 넓히면 **조용히** 동작이 바뀐다. 그래서 지식은 이 한 파일에
//   모으되(사본을 만들지 않는다) 축을 갈라, `cleanup-nodes`·`extract-parts` 만 이쪽을 묻는다.
//
// 근거: Vol_I (R16@e545952c7 03/21/25)
//   *ELEMENT_BEAM     : `*ELEMENT_BEAM_{OPTION}_{OPTION}`, 옵션마다 카드 **한 장**씩
//                       (THICKNESS/SCALAR/SCALR/SECTION/PID/OFFSET/ORIENTATION/WARPAGE/ELBOW).
//                       Card 1 = EID PID N1 N2 N3 RT1 RR1 RT2 RR2 LOCAL → 절점은 칸 2·3·4 **셋만**.
//   *ELEMENT_DISCRETE : Card 1 = EID PID N1 N2 VID S PF OFFSET → 절점은 칸 2·3.
//                       `_LCO` 는 "a second card is read" → +1 장.
//   *ELEMENT_MASS     : Card 1 = EID(I8) ID(I8) MASS(E16) PID(I8) → 절점은 칸 **1** 하나 (159866-159930).
//                       ⚠ MASS 는 10칸 표에서 **두 칸**(17-32열)이다 — PID 는 33-40열(8칸으로 자르면 칸 4)이고
//                         8칸 칸 3(25-32열)은 MASS 의 뒤 절반이다. 칸 차례(EID ID MASS PID)로 PID 는 3 이지만
//                         그 차례로 자르는 것은 `auxCardFields` 뿐이다(2026-11-07 — 정수 폭으로 잘라 PID 를 MASS 에서 읽었다).
//                       ⚠ `_NODE_SET` 변형은 그 칸이 **절점 세트 ID** 다 — 절점으로 읽으면
//                         엉뚱한 절점을 지키고 세트 멤버는 놓친다. 그래서 **미지원**으로 둔다.
//   *ELEMENT_SEATBELT : Card 1 = EID PID N1 N2 SBRID SLEN N3 N4 → 절점이 **두 구간**이다
//                       (칸 2·3 과 칸 6·7). 사이의 SBRID·SLEN 을 절점으로 읽으면 번호를 다시
//                       매길 때 그 칸을 **덮어써 카드가 깨진다**.
//   *ELEMENT_PLOTEL   : Card 1 = EID N1 N2 → **PID 칸이 없다**. 'PID 는 칸 1' 로 뭉개면
//                       N1 을 파트로 읽는다.
enum class AuxFamily { NONE, BEAM, DISCRETE, MASS, SEATBELT, PLOTEL };

struct AuxElementCard {
    AuxFamily family = AuxFamily::NONE;
    std::string keyword;
    int  lines = 1;            // 카드 한 장의 데이터 줄 수(옵션 카드 포함)
    int  nodeSkip = 2;         // 절점 칸이 시작하는 자리(Card 1 기준)
    int  nodeCount = 0;        // 그 구간의 칸 수
    int  nodeSkip2 = -1;       // 둘째 절점 구간(없으면 -1) — `*ELEMENT_SEATBELT`
    int  nodeCount2 = 0;
    bool hasPart = true;       // false = PID 칸이 없다(`*ELEMENT_PLOTEL`)
    int  partField = 1;        // PID 가 든 칸 — **칸 차례**(`auxCardFields` 가 나눈 차례). ⚠ `*ELEMENT_MASS` 는 3(EID ID MASS PID)
    std::vector<int> wideFields;   // Card 1 에서 정수 칸보다 넓은 실수 칸의 차례(`*ELEMENT_MASS` 의 MASS = 2)
    bool supported = false;    // false 면 이 변형을 추측하지 않는다
    std::string reason;        // supported=false 일 때 댈 이유
};

// 키워드 줄을 푼다. 격자 족(`parseElementKeyword` 가 아는 것)이면 family=NONE 을 돌려준다 —
// 두 판정기는 **배타적**이다. 모르는 `*ELEMENT_*` 변형도 family=NONE 이다.
AuxElementCard auxElementCard(const std::string& keywordLine);

// 그 족 Card 1 한 줄을 **칸 차례대로** 나눈다 — `partField`·`nodeSkip` 은 이 차례를 가리킨다.
// 고정폭이면 `wideFields` 의 칸은 실수 폭(`realFieldWidth` — 표준·i10 16 · long 20), 나머지는 정수 폭 `fw` 다
// (Vol_I 19315-19316 long 은 20 이하를 20 으로 · 19353-19354 i10 은 8칸짜리만 10칸으로). 콤마 자유형식과 칸이 어긋난 줄(고정 칸 안에 공백)은
// `deckscan::cardFields` 와 같이 토큰 차례가 곧 칸 차례다. `wideFields` 가 비면 `deckscan::cardFields(line, fw)` 그대로다.
// ⚠ 절점 칸은 넓은 칸 **앞**에 있다(질량의 ID 는 칸 1) — 칸 차례 × 폭으로 자리를 잡아 쓰는 쪽(extract-parts 의 번호 다시 매기기)이 맞다.
std::vector<std::string> auxCardFields(const AuxElementCard& a, const std::string& line, int fw);

// `KFileReader` 가 메시에 담는 요소 키워드인가 — 그 리더의 키워드 분기(`KFileReader::parseFile`)와 **같은 판정**이다
// (키워드 토큰도 그 리더처럼 `*` 뒤 영숫자 · `_` · `-` 를 대문자로 모은다).
//   담는다 — `*ELEMENT_SOLID`·`_SOLID_TITLE`·`*ELEMENT_TSHELL`·`_TSHELL_TITLE`(맨 이름 그대로) · `*ELEMENT_SHELL` 로
//            시작하고 `parseElementKeyword` 가 줄 수를 확정하는 셸 변형
//   안 담는다 — 솔리드 · 티쉘의 옵션 변형(`_ORTHO` · `_DOF` · `_H20`·`_T15`·`_P21`·`_H27`·`_P40`·`_H64` · `_H8TOH20` ·
//            `_TET4TOTET10` · `*ELEMENT_TSHELL_BETA` …). `parseElementKeyword` 가 줄 수를 알아도(supported) 메시에 **없다**.
// 왜 있나 (2026-11-07). 격자 밖 걸음이 「parseElementKeyword 가 supported 면 리더가 담는다」고 보아 그 변형을 아무도 세지
// 않았다 — 번호 바닥(`id_floor` · 조각 삽입 · 이월 적용)이 그 EID 를 몰랐다. 리더 분기가 바뀌면 이것도 바꾼다
// (`tests/test_DeckContract.cpp` 가 키워드마다 리더로 읽어 대조한다).
bool gridReaderReadsKeyword(const std::string& keywordLine);

// ── 격자 리더가 메시에 담지 않는 `*ELEMENT_*` 카드 ──────────────────────────
//
// 왜 있나 (2026-11-07). `KFileReader` 는 격자 족(솔리드 · 셸 · 티쉘)의 몇 키워드만 메시에 담는다(`gridReaderReadsKeyword`).
// 보 · 이산 · 질량 · 안전띠 · 플롯 요소, 줄 수를 모르는 변형(COMPOSITE · `*ELEMENT_INERTIA` …), 리더가 읽지 않는 솔리드 ·
// 티쉘 옵션 변형(`_ORTHO` · `_DOF` · `_H20` … · `*ELEMENT_TSHELL_BETA`)은 메시에 없다 — 그래서 번호 바닥이 그 EID 를
// 몰랐고(11-07 답신은 「바닥은 빔 · 이산 · 질량까지 센다」고 했다), 이월 적용은 그 요소가 쓰는 절점을 몰랐다.
// 두 소비자(바닥 `nonGridElementMaxId` · 이월 적용의 나눠 쓴 절점)가 이 **한 걸음**을 쓴다.
//   known  — 칸 자리와 카드 줄 수를 안다. 카드마다 한 번(Card 1 줄) · EID · PID(없으면 0) · 절점 칸
//            · 격자 밖 족 — `auxElementCard` 가 안다(칸은 `auxCardFields` 차례)
//            · 리더가 안 읽는 격자 변형 — 줄 수가 PID 에 달리지 않을 때만(절점 수 옵션 `_H20` 등 · 티쉘 `_BETA`) ·
//              `elementCardSpan` 의 절점 줄 전부
//   !known — 칸 자리나 카드 줄 수를 모른다. **데이터 줄마다** 한 번 · 그 줄의 첫 칸을 EID 로 넘치게 센다(바닥은 높아질
//            뿐 낮아지지 않는다). 절점 수 옵션이 없는 솔리드 변형(`_ORTHO` · `_DOF` · `_H8TOH20` · `_TET4TOTET10` …)은
//            카드 줄 수가 그 PID 의 ELFORM(다른 파일의 `*SECTION_SOLID` 일 수 있다)과 구 포맷 여부에 달려 여기 든다
// 빈 줄은 카드 안에서만 카드다(격자 카드와 같은 규칙) · 주석은 건너뛴다.
struct NonGridElementCard {
    std::string keyword;        // 대문자 · 접미사 뗌
    size_t line = 0;            // 그 카드(또는 줄)의 0-기반 줄
    bool known = false;
    int eid = 0;
    int pid = 0;                // known 이고 PID 칸이 있을 때만
    std::vector<int> nodes;     // known 일 때만 — 양수인 절점 칸
};
void forEachNonGridElementCard(const std::vector<std::string>& lines,
                               const std::function<void(const NonGridElementCard&)>& f);
// 그 줄들의 격자 밖 요소 EID 최대값(없으면 0) — `ModelAssembler::idMaxima` 의 바닥
int nonGridElementMaxId(const std::vector<std::string>& lines);

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
