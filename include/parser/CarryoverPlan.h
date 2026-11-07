// StepForge 이월 계획(plan.json 판 1 · 2) · 변위장 · 조각 · 새 셸 섹션을 엄격히 읽고 적용 보고 JSON 을 쓴다 — 모르는 칸 · 꼴 밖은 말하고 거절한다
#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace KooRemapper {
namespace carryover {

// 왜 이 단위가 있나 (2026-11-07).
//
//   StepForge 가 CAD 개정을 해석 덱으로 이월하는 재료 셋(계획 · 변위장 · 조각)을 낸다(그쪽 `REQUEST-2026-11-06-carryover.md`).
//   덱을 고치는 일은 우리 몫이고(경계 합의 §1), 우리 답신(`docs/requests/stepforge-carryover-reply-2026-11-07.md`)이
//   「계획 v1 의 칸을 그대로 받는다 · 모르는 칸 · 빠진 칸은 거절한다」고 약속했다. 그 약속은 읽는 쪽이 엄격해야 지킨다 —
//   그래서 덱을 모르는 순수 읽기를 여기 둔다(덱과 대조하는 일은 `ModelAssembler::applyCarryoverPlan`).
//
// 지키는 것.
//   · 칸 표는 **한 곳**(CarryoverPlan.cpp 머리의 `kKeys`)이다 — 판마다 칸이 다르다(판 1 그대로 · 판 2 는 그쪽 요청서 §10.2 의
//     칸을 더한다 — 줄마다 덱 자리 · `deck.deck_from` · `deck.includes` · `field.new_section` · `refused_transform` · `summary`).
//     모르는 칸 · 빠진 칸은 **그 판의** 표로 거절한다(사용자 결정 11-07)
//   · 걸린 것을 **전부** 모은다 — 한 줄이 틀려도 다음 줄을 본다(사전 검사는 전부 아니면 전무)
//   · 꼴만 보는 칸(mesh · target · check · solver · face_pairs · kinds · cad · suggestion · layout 의 codes · 판 1 의 summary)은
//     객체인지만 보고 속은 읽지 않는다. 판 2 의 summary 는 칸을 보고 actions · sections · failed 를 계획 줄과 대조한다

// 걸린 것 하나.
struct Problem {
    long long pid = 0;      // 0 = 어느 PID 줄과도 무관
    std::string kind;       // 기계가 읽는 갈래(plan_schema · deck_sha · shared_nodes …)
    std::string detail;     // 사람이 읽는 까닭
};

enum class Action { Keep, Transform, Morph, Remesh, Delete, Review };
const char* actionName(Action a);

// 다른 PID 와 나눠 쓰는 절점(계획 줄 `shared_nodes` — 없으면 칸이 없다)
struct SharedNodes {
    bool present = false;
    std::vector<long long> nodes, with;
};

// 변위장 차례 한 칸(`field.layout[]`). 이름 · dtype · 개수는 읽을 때 확인하고, 자리만 들고 간다.
struct LayoutEntry {
    long long offset = 0;
    long long sharedBit = 8;    // kind 의 「다른 PID 와 나눠 쓰는 절점」 비트(그쪽 꼴 — 넷째 비트 8)
};

// morph 줄의 새 셸 섹션(판 2 `field.new_section` — 요청서 §10.2). null 이면 present=false.
// built 면 그쪽이 카드를 지었다(secid · file) — 그 카드를 넣고 그 PID 의 `*PART` SECID 만 잇는다(답신 Q8).
// 아니면 두께가 바뀌었는데 못 지었다(secid · file 이 null · 까닭은 why) — 그 줄은 조각으로 물러선다(instead).
struct MorphSection {
    bool present = false;
    bool built = false;
    long long secid = 0;
    double thickness = 0;       // 카드의 T1~T4 에 쓴 값 그대로(10칸 · 유효숫자 다섯을 되읽은 수)
    std::string file, why;
};

// morph 줄의 `field` 머리.
struct FieldHead {
    bool present = false;
    bool built = false;         // file 이 이름이다 — 못 지었으면 file 이 null 이고 why 가 있다
    std::string file, why;
    long long nodes = 0, bytes = 0;
    LayoutEntry node, disp, kind;
    bool hasThickness = false;  // 셸 두께가 바뀐 모프 — 판 1 은 받지 않는다(판 2 는 new_section 이 정한다)
    MorphSection newSection;    // 판 2
    bool hasElementThickness = false;   // 판 2 — 그 PID 셸 요소가 요소마다 두께를 싣는다(섹션 두께를 덮는다)
    long long elementThicknessCount = 0;
};

// 판 2 — 줄마다 그 PID 의 덱 자리(`parts[].deck` — 그쪽 `KDeck.part_ranges()` 와 `*PART`). null 칸은 has* 가 거짓이다.
struct PartDeck {
    bool present = false;
    bool hasNode = false, hasElem = false, hasSecid = false, hasMid = false;
    long long nodeLo = 0, nodeHi = 0, nodeCount = 0;
    long long elemLo = 0, elemHi = 0, elemCount = 0;
    int contiguous = -1;        // -1 null · 0 거짓 · 1 참
    long long secid = 0, mid = 0;
};

// 조각이 함께 싣는 새 섹션(`fragment.new_section`).
struct NewSection {
    bool present = false;
    long long secid = 0, elform = 0;
    bool hasNip = false;
    long long nip = 0;
    bool hasT = false;
    double t = 0;
    std::string why;
};

// remesh 줄 · 새 파트 줄의 `fragment` 머리.
struct FragmentHead {
    bool present = false;       // 객체다(added 줄의 null 은 false)
    bool ok = false;            // 못 지었으면 false — why 는 있는 까닭(맨 위 why · notes.why · check.why · check.problems), 없으면 빈 글자
    std::string file, why;
    long long pid = 0, secid = 0, mid = 0;
    NewSection newSection;
    long long nodeLo = 0, nodeHi = 0, elemLo = 0, elemHi = 0;
    long long nodes = 0, elements = 0, bytes = 0;
};

struct PartRow {
    bool valid = false;         // 칸 검사를 다 지났다 — 아니면 덱과 대조하지 않는다(까닭은 이미 담았다)
    long long pid = 0;
    std::string name, why;
    std::string actionText;                     // 적힌 그대로(모르는 처리면 action 은 기본값이다 — 보고는 이 글자를 쓴다)
    Action action = Action::Keep;
    std::vector<std::string> absorbed;          // keep
    std::vector<long long> touchesChanged;      // keep
    std::array<double, 16> m{};                 // transform — 4×4 행 우선
    std::array<double, 3> translation{};        // transform — m 의 이동 칸과 같아야 한다
    FieldHead field;                            // morph
    bool hasInstead = false;                    // morph — 받지 않는다(우리는 변위장만 쓴다)
    FragmentHead fragment;                      // remesh
    SharedNodes shared;
    PartDeck deck;                              // 판 2 — 모든 줄
    // 판 2 review 줄 — 1단계가 옮김으로 냈으나 강체가 아니라 계획이 사람 확인으로 돌린 4×4(옮기지 않는다 · 보고에 그대로 싣는다)
    bool hasRefusedTransform = false;
    std::array<double, 16> refusedM{};
    double refusedDet = 0, refusedScale = 0, refusedOrth = 0;
};

struct AddedRow {
    bool valid = false;
    std::string path, name, why;
    bool hasPid = false;
    long long pid = 0;
    FragmentHead fragment;      // present=false 면 조각이 없다(보고만)
};

struct FileEntry {
    std::string name, sha256;
    long long bytes = 0;
};

// 판 2 `deck.includes` 한 줄 — 주 덱 폴더 기준 상대 경로(`/` · 정규화)와 그 파일 바이트 전부의 sha256(LS-DYNA 가 읽는 차례)
struct IncludeEntry {
    std::string relpath, sha256;
};

struct Plan {
    std::string format, unit, frame, reportKey, codeBuild;
    long long version = 0;
    std::string deckSha256, deckRelpath, deckProjectId;
    std::string deckFrom;               // 판 2 — raw · mesh(덱을 relpath 로 찾지 않는다 — 보고에 되돌려 줄 뿐이다)
    bool hasIncludes = false;           // 판 2 — deck.includes 칸을 읽었다(빈 목록일 수 있다)
    std::vector<IncludeEntry> includes;
    long long maxNode = 0, maxElem = 0, maxPid = 0, maxSecid = 0, maxMid = 0;
    std::vector<std::string> unreadCards;
    std::vector<PartRow> parts;
    std::vector<AddedRow> added;
    std::vector<FileEntry> files;   // 적힌 차례
};

// 계획 JSON 을 읽는다. 걸린 것(문법 · 모르는 칸 · 빠진 칸 · 꼴 · 값 · 판 2 의 summary 대조)을 `problems` 에 **모두** 더하고,
// 하나도 없으면 true. 문법이 틀리면 그 하나만 담고 멈춘다(속을 읽을 수 없다).
bool parsePlan(const std::string& text, Plan& out, std::vector<Problem>& problems);

// 변위장 이진 — 머리의 차례대로 리틀엔디언으로 읽는다. 절점 오름차순(중복 없음) · 변위 유한 · 꼴 바이트(아래 세 비트 0~4,
// 넷째 비트 = 나눠 쓴 절점, 그 위 비트 0)를 본다. 크기는 머리(`bytes` · kind 자리 + N)와 같아야 한다.
struct Field {
    std::vector<uint32_t> node;
    std::vector<double> disp;    // 3N — dx dy dz
    std::vector<uint8_t> kind;
};
bool readField(const std::string& bytes, const FieldHead& h, Field& out, std::string& err);

// 조각(.k)을 줄 단위로 읽는다 — 계약 키워드(*KEYWORD · *END · *NODE · *ELEMENT_SOLID · *ELEMENT_SHELL · *PART ·
// *SECTION_SOLID_TITLE · *SECTION_SHELL_TITLE) · 표준 8칸 고정폭 · 자유 형식 금지(CadSolidMerge `remapFragment` 와 같은 규칙).
// 요소 꼴은 파일에서 정한다 — 사면체는 n5..n8 = n4, 셸 삼각형은 n4 = n3(계획의 `mesh.kind` 를 믿지 않는다).
struct FragmentScan {
    struct Node { long long id = 0; std::array<double, 3> xyz{}; };
    struct Elem { long long id = 0, pid = 0; std::array<long long, 8> n{}; bool shell = false; };
    struct PartCard { std::string title; long long pid = 0, secid = 0, mid = 0; bool otherIdsZero = true; };
    struct Section {
        bool shell = false;
        long long secid = 0, elform = 0, nip = 0;
        double t1 = 0;
        bool t1Given = false;
    };
    std::vector<Node> nodes;
    std::vector<Elem> elems;
    std::vector<PartCard> parts;
    std::vector<Section> sections;

    // 넣을 블록을 짤 때 쓰는 줄 표(입력 줄과 같은 차례)
    enum class LineKind : char { Skip, Keyword, Comment, Node, ElemCard, ElemNodes, Verbatim };
    struct Line { LineKind kind = LineKind::Skip; int block = -1; std::vector<long long> f; };
    std::vector<Line> lines;
    std::vector<std::string> blockKw;   // 블록 차례 → 키워드(대문자 · 접미사 뗌)
};
bool scanFragment(const std::vector<std::string>& lines, FragmentScan& out, std::vector<std::string>& problems);

// 조각을 계획 머리와 대조한다(값 대조) — 번호 구간 · 수 · PID · SECID · MID · 새 섹션 카드 · 요소 꼴 하나 ·
// 요소가 쓰는 절점이 다 있고 안 쓰는 절점이 없다. 덱과 견주는 일(섹션 · 재질이 덱에 있나)은 부르는 쪽이 한다.
void checkFragment(const FragmentScan& s, const FragmentHead& h, long long expectPid, std::vector<std::string>& problems);

// 넣을 블록 — 번호 칸만 옮겨(절점 shiftNode · 요소 shiftElem) 덱 폭(fw 8 · 10)으로 쓰고 나머지 글자는 그대로 둔다.
// `*KEYWORD` · `*END` 는 뺀다. withPart=false 면 `*PART` 블록을 통째로 뺀다(바꿔 넣기 — 덱의 `*PART` 를 그대로 쓴다).
std::string renderFragment(const std::vector<std::string>& lines, const FragmentScan& s, long long shiftNode,
                           long long shiftElem, int fw, bool withPart);

// 판 2 — 모프 줄의 새 셸 섹션 파일(`section_<PID>.k` — 요청서 §10.3 ②)을 엄격히 읽는다: `*KEYWORD` · 셸 섹션 카드
// **하나**(`*SECTION_SHELL` · `_TITLE` — 제목 · Card 1 · Card 2 · ICOMP 1 이면 각도 카드) · `*END`. 그 밖의 키워드 · 데이터 줄 ·
// 쌓인 둘째 카드 · 사용자 정의 셸(ELFORM 101~105)의 딸린 카드 · 자유 형식 · 제어 문자는 거절한다.
struct SectionFileScan {
    std::vector<std::string> head;    // `*KEYWORD` 와 섹션 키워드 사이의 주석 줄(넣을 때 함께 간다)
    std::vector<std::string> block;   // 섹션 키워드 줄부터 `*END` 앞까지 — 덱에 넣는 줄이고 덱의 옛 카드와 줄마다 견준다
    size_t row1 = 0, row2 = 0;        // block 안의 Card 1(SECID …) · Card 2(T1~T4 …) 자리
    long long secid = 0, elform = 0;
    double t[4] = {0, 0, 0, 0};
};
bool scanSectionFile(const std::vector<std::string>& lines, SectionFileScan& out, std::vector<std::string>& problems);

// 셸 섹션 블록(키워드 줄부터 다음 키워드 앞까지 — 덱의 것이든 파일의 것이든)에서 **카드 하나**의 Card 1 · Card 2 자리를 찾는다.
// 빈 줄은 카드다(끝의 빈 줄만 여백) — LS-DYNA 가 읽는 차례다. 카드 하나가 아니면 false 와 까닭.
bool shellSectionRows(const std::vector<std::string>& block, size_t& row1, size_t& row2, std::string& why);

// 새 카드가 덱의 옛 카드를 **그대로 옮기고** SECID(Card 1 앞 10칸)와 T1~T4(Card 2 앞 40칸)만 바꾼 것인가(요청서 §10.3 ②) —
// 다른 줄 · 다른 칸이 하나라도 있으면 그 자리를 `problems` 에 담는다.
void compareSectionCards(const std::vector<std::string>& deckBlock, const SectionFileScan& s, std::vector<std::string>& problems);

// 이 바이트가 그 줄을 내나 — 지문(sha256)은 늘 **훑고 고친 줄을 낸 바이트**의 것이어야 한다(줄은 덱을 담을 때 읽고 지문은 적용할 때
// 파일을 다시 열어 잰다 — 그 사이에 파일이 바뀌면 다른 바이트의 지문을 계획과 견주었다 · 적대적 검토 11-07). 줄 나누기는 읽기와 같다 —
// `std::getline`(LF) · 줄 끝 CR 하나를 뗀다. include = 인클루드 파일 꼴(`include_closure::read` 가 담는 꼴 — 맨 앞 UTF-8 BOM 을 떼고
// 첫 `*END` 줄 앞까지 · IncludeClosure.cpp `Walker::card` 규칙의 사본이라 단위 시험이 둘을 묶는다). 줄 사본을 짓지 않는다.
bool bytesGiveLines(const std::string& bytes, const std::vector<std::string>& lines, bool include);

// ── 보고(`dynaforge-carryover-apply` v1) ─────────────────────────────────────
struct PartResult {
    long long pid = 0;
    std::string action;
    std::string result = "skipped";     // applied · skipped · refused
    bool hasMove = false;
    long long nodesMoved = 0;
    double maxDisp = 0;
    bool hasRemoved = false;
    long long removedNodes = 0, removedElements = 0;
    bool hasInserted = false;
    long long insNodeLo = 0, insNodeHi = 0, insElemLo = 0, insElemHi = 0;
    bool hasNewSection = false;
    long long newSecid = 0, newElform = 0;
    bool newSectionShell = false;           // 판 2 모프 — 셸 두께(아래)를 싣는다(바꿔 넣기는 ELFORM 을 싣는다)
    double newThickness = 0;
    bool hasInverted = false;
    long long invertedBefore = 0, invertedAfter = 0;
    bool hasFlipped = false;
    long long flipped = 0;
    std::vector<std::string> absorbed;
    bool hasRefusedTransform = false;       // 판 2 review 줄 — 계획이 실은 그대로 되돌려 준다
    std::array<double, 16> refusedM{};
    double refusedDet = 0, refusedScale = 0, refusedOrth = 0;
};
struct AddedResult {
    std::string name;
    bool hasPid = false;
    long long pid = 0;
    std::string result = "skipped";
    std::string why;
};
struct Touch {
    long long pid = 0;
    std::vector<long long> with;
};
struct Report {
    bool ok = false;
    bool outputWritten = false;         // 이번 실행이 output 자리에 덱을 바꿔 넣었다(거절 · 실패면 false — 앞 파일은 그대로다)
    bool planRead = false;              // 계획 바이트를 읽었다(sha256 이 있다)
    std::string planSha256, reportKey;
    long long planVersion = 0;
    bool planParsed = false;            // version · report_key 를 읽었다
    std::string deckFrom;               // 판 2 deck.deck_from — 비면 null
    std::string deckShaIn, deckShaOut;  // 비면 null
    bool includesChecked = false;       // 판 2 — 덱의 인클루드 닫힘을 deck.includes 와 대조해 같았다(아니면 null)
    std::vector<IncludeEntry> includes;
    std::vector<Problem> problems, warnings;
    bool shifted = false;
    long long shiftNode = 0, shiftElem = 0;
    std::vector<PartResult> parts;
    std::vector<AddedResult> added;
    std::vector<Touch> touches;
};
std::string toJson(const Report& r);

}  // namespace carryover
}  // namespace KooRemapper
