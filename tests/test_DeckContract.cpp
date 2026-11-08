// 덱 계약의 기본 조각들 — 폭 · 칸 · 카드 줄 수 · 개행. **여기가 비어 있었다.**
//
// 왜 이 파일이 있나 (2026-10-15, deck-contract 감사 `:363`):
//
//   감사가 적었다 — "`ctest 1/1` 은 덱 계약에 관해 **신호가 아니다.** 단언 52개가 전부
//   기하이고 `KFileReader`·`DeckWriter`·`ModelAssembler`·`ReferenceIntegrity`·`SetDef`
//   단위 시험은 0건이다."
//
//   그 말대로였다. 덱 계약은 `tools/regress/*.py` 73개로만 지켜졌는데, 그것들은 **바이너리를
//   돌려** 산출물을 비교한다 — 느리고(분 단위), 빨개졌을 때 **어느 조각이 틀렸는지** 말해
//   주지 않는다. 폭 계산 한 줄이 틀려도 "46 op 중 3개가 깨졌다" 로 나온다.
//
//   그래서 **결정을 내리는 조각**들을 여기서 직접 못 박는다. 이 파일이 빨개지면 어느 함수가
//   틀렸는지 바로 보인다. 느린 전수 관문은 그대로 두고, 그 앞에 빠른 그물을 하나 둔다.
//
// 고른 기준 — 한 곳이 틀리면 **여러 op 이 조용히 같이 틀리는** 것만 넣었다.
#include "TestFramework.h"

#include "parser/DeckScan.h"
#include "parser/DeckNewline.h"
#include "parser/DeckWriter.h"
#include "parser/ElementCardLayout.h"
#include "parser/IdRefs.h"
#include "parser/KFileReader.h"
#include "parser/NodeRefs.h"
#include "parser/KFileWriter.h"
#include "core/Mesh.h"

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <fstream>

#include <sstream>
#include <vector>
#include <string>

using namespace KooRemapper;

// ── 덱 폭 — 정본이 하나여야 한다 ──────────────────────────────────────────
// 리더가 8칸으로 읽고 쓰는 쪽이 10칸으로 쓰면 **새 층이 통째로 사라진다**
// (`ElementCardLayout.h:54` 가 경고하는 그 사고). 그 값을 정하는 함수가 이것뿐이다.

TEST(deckFieldWidth_기본은_8) {
    ASSERT_EQ(deckFieldWidth({}), 8);                       // *KEYWORD 가 없으면
    ASSERT_EQ(deckFieldWidth({"*KEYWORD", "*END"}), 8);     // 말하지 않으면
    ASSERT_EQ(deckFieldWidth({"$ 주석", "*NODE"}), 8);
}

TEST(deckFieldWidth_I10과_LONG을_읽는다) {
    ASSERT_EQ(deckFieldWidth({"*KEYWORD I10=Y"}), 10);
    ASSERT_EQ(deckFieldWidth({"*KEYWORD LONG=Y"}), 20);
    // long=s 는 "read standard … write long" 이므로 **읽기 폭은 표준**이다(19308).
    ASSERT_EQ(deckFieldWidth({"*KEYWORD LONG=S"}), 8);
}

TEST(deckFieldWidth_는_첫_KEYWORD_만_본다) {
    // 뒤에 또 나오는 *KEYWORD(인클루드를 펼친 덱에서 흔하다)가 폭을 바꾸면,
    // 같은 파일의 앞뒤가 다른 폭으로 읽힌다.
    const std::vector<std::string> lines = {"*KEYWORD", "*NODE", "*KEYWORD I10=Y"};
    ASSERT_EQ(deckFieldWidth(lines), 8);
}

TEST(keywordCardDeckWidth_는_말하지_않으면_0) {
    ASSERT_EQ(keywordCardDeckWidth("*KEYWORD"), 0);
    ASSERT_EQ(keywordCardDeckWidth("*KEYWORD I10=Y"), 10);
}

// ── 칸 자르기 — 폭이 다르면 값이 다른 칸으로 들어간다 ────────────────────

TEST(cardFields_가_폭대로_자른다) {
    //            1234567812345678
    const std::string l8  = "       1     200";
    const auto f8 = deckscan::cardFields(l8, 8);
    ASSERT_EQ(deckscan::fieldInt(f8, 0), 1);
    ASSERT_EQ(deckscan::fieldInt(f8, 1), 200);

    const std::string l10 = "         1       200";
    const auto f10 = deckscan::cardFields(l10, 10);
    ASSERT_EQ(deckscan::fieldInt(f10, 0), 1);
    ASSERT_EQ(deckscan::fieldInt(f10, 1), 200);
}

TEST(cardFields_를_틀린_폭으로_자르면_값이_섞인다) {
    // ★이것이 폭을 틀렸을 때 **실제로 벌어지는 일**이다 — 오류가 아니라 **다른 숫자**다.
    //   그래서 조용히 틀리고, 그래서 정본이 하나여야 한다.
    const std::string l10 = "         1       200";
    const auto wrong = deckscan::cardFields(l10, 8);
    ASSERT_NE(deckscan::fieldInt(wrong, 1), 200);
}

TEST(fieldInt_는_빈칸을_0으로_본다) {
    const auto f = deckscan::cardFields("       1        ", 8);
    ASSERT_EQ(deckscan::fieldInt(f, 1), 0);
    ASSERT_EQ(deckscan::fieldInt(f, 9), 0);      // 없는 칸도 0
}

TEST(readNodeLine_이_두_폭에서_같은_절점을_읽는다) {
    int nid = 0; double xyz[3] = {0, 0, 0};
    ASSERT_TRUE(deckscan::readNodeLine(
        "       7      1.00000000      2.00000000      3.00000000", 8, nid, xyz));
    ASSERT_EQ(nid, 7);
    ASSERT_NEAR(xyz[0], 1.0, 1e-9);
    ASSERT_NEAR(xyz[2], 3.0, 1e-9);

    nid = 0;
    ASSERT_TRUE(deckscan::readNodeLine(
        "         7      1.00000000      2.00000000      3.00000000", 10, nid, xyz));
    ASSERT_EQ(nid, 7);
    ASSERT_NEAR(xyz[1], 2.0, 1e-9);
}

// ── 줄의 종류 — 주석을 데이터로 읽으면 쓰레기가 들어온다 ────────────────

TEST(isDataLine_이_주석과_키워드와_빈줄을_가른다) {
    ASSERT_TRUE(deckscan::isDataLine("       1     200"));
    ASSERT_FALSE(deckscan::isDataLine("$ 주석"));
    ASSERT_FALSE(deckscan::isDataLine("*NODE"));
    ASSERT_FALSE(deckscan::isDataLine(""));
    ASSERT_FALSE(deckscan::isDataLine("   "));
}

TEST(keywordToken_과_kwBare_가_꼬리를_뗀다) {
    ASSERT_EQ(deckscan::keywordToken("*ELEMENT_SOLID  $ 뒤 주석"), std::string("*ELEMENT_SOLID"));
    ASSERT_EQ(deckscan::kwBare("*ELEMENT_SOLID%"), std::string("*ELEMENT_SOLID"));
    ASSERT_EQ(deckscan::kwBare("*NODE+"), std::string("*NODE"));
}

// ── *SET_NODE 의 세 갈래 — 여기를 틀리면 멤버를 참조로 센다 ──────────────
// 요청자의 원래 실패가 이 자리였다. LIST 는 멤버를 담고, COLUMN 은 칸이 다르고,
// OPAQUE(GENERAL 등)는 **해석하지 않고 그대로 둬야** 한다.

TEST(classifySetNode_가_세_갈래를_가른다) {
    ASSERT_TRUE(deckscan::classifySetNode("*SET_NODE_LIST") == deckscan::SetKind::LIST);
    ASSERT_TRUE(deckscan::classifySetNode("*SET_NODE_LIST_TITLE") == deckscan::SetKind::LIST);
    ASSERT_TRUE(deckscan::classifySetNode("*SET_NODE_COLUMN") == deckscan::SetKind::COLUMN);
    ASSERT_TRUE(deckscan::classifySetNode("*SET_NODE_GENERAL") == deckscan::SetKind::OPAQUE);
}

// ── 요소 카드 줄 수 — 한 줄 틀리면 그 뒤 전부가 밀린다 ──────────────────

// ── 목록 카드 정본 — 찾는 쪽(`noderefs::find`)과 고치는 쪽(`cleanupDeadNodeRefs`)이 같은 표를 본다(2026-10-17) ──
// 고치는 쪽은 `_ADD` 만 건너뛰어 `_INTERSECT` 의 세트 ID 를 절점으로 읽었고(restack 이 교집합 세트를 비웠다),
// 맨 `*SET_NODE` 를 목록으로 옮기지 않았다(같은 세트가 `_LIST` 면 옮겨지고 맨 이름이면 빠졌다).
TEST(listCardOf_세트_ID_와_범위는_목록이_아니다) {
    using noderefs::ListCard;
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE") == ListCard::SetNodeList);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_LIST_TITLE") == ListCard::SetNodeList);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_LIST_SMOOTH") == ListCard::SetNodeList);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_COLUMN") == ListCard::SetNodeColumn);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_GENERAL") == ListCard::SetNodeGeneral);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_INTERSECT") == ListCard::None);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_ADD") == ListCard::None);
    ASSERT_TRUE(noderefs::listCardOf("*SET_NODE_LIST_GENERATE") == ListCard::None);
    ASSERT_TRUE(noderefs::listCardOf("*SET_SEGMENT") == ListCard::SetSegment);
    ASSERT_TRUE(noderefs::listCardOf("*SET_SEGMENT_INTERSECT") == ListCard::None);
    ASSERT_TRUE(noderefs::listCardOf("*SET_SEGMENT_GENERAL") == ListCard::None);
    ASSERT_TRUE(noderefs::listCardOf("*DATABASE_HISTORY_NODE") == ListCard::HistoryNode);
    ASSERT_TRUE(noderefs::listCardOf("*DATABASE_HISTORY_NODE_SET") == ListCard::None);
}

TEST(listCardFields_는_매뉴얼_칸_범위다) {
    using noderefs::ListCard;
    ASSERT_EQ(noderefs::listCardFields(ListCard::SetNodeList).size(), (size_t)8);      // 칸 1-8
    ASSERT_EQ(noderefs::listCardFields(ListCard::SetNodeColumn).size(), (size_t)1);    // 칸 1
    ASSERT_EQ(noderefs::listCardFields(ListCard::SetNodeGeneral).front(), 1);          // 칸 2-8 (칸 1 은 OPTION)
    ASSERT_EQ(noderefs::listCardFields(ListCard::SetNodeGeneral).size(), (size_t)7);
    ASSERT_EQ(noderefs::listCardFields(ListCard::SetSegment).size(), (size_t)4);       // N1..N4
    ASSERT_EQ(noderefs::listCardFields(ListCard::HistoryNode).size(), (size_t)8);
    ASSERT_EQ(noderefs::listCardHeader(ListCard::SetNodeList, "*SET_NODE_LIST_TITLE"), (size_t)2);
    ASSERT_EQ(noderefs::listCardHeader(ListCard::SetSegment, "*SET_SEGMENT"), (size_t)1);
    ASSERT_EQ(noderefs::listCardHeader(ListCard::HistoryNode, "*DATABASE_HISTORY_NODE"), (size_t)0);
}

TEST(elementCardSpan_솔리드의_두_포맷을_가른다) {
    // ★`*ELEMENT_SOLID` 는 **두 꼴**이 있다. 섞으면 그 뒤 카드 전부가 밀린다.
    //   구 포맷 — 절점이 Card 1 에 있다(EID PID N1..N8). `pidNodeCount` 를 모를 때만 쓴다.
    //   현대 포맷 — Card 1 은 EID·PID 뿐이고 절점은 Card 2 다.
    const auto info = parseElementKeyword("*ELEMENT_SOLID");
    const std::vector<std::string> oneLine = {"1", "1", "1", "2", "3", "4", "5", "6", "7", "8"};

    const auto legacy = elementCardSpan(info, oneLine, 0);   // 절점 수를 모른다 → 줄을 보고 판정
    ASSERT_EQ(legacy.lines, 1);
    ASSERT_EQ(legacy.nodeFirst, 0);
    ASSERT_EQ(legacy.nodeFieldSkip, 2);

    const auto modern = elementCardSpan(info, {"1", "1"}, 8);  // 8절점임을 안다
    ASSERT_EQ(modern.lines, 2);
    ASSERT_EQ(modern.nodeFirst, 1);
    ASSERT_EQ(modern.nodeFieldSkip, 0);
}

TEST(elementCardSpan_고차_솔리드는_절점_카드가_여러_줄) {
    // 11절점을 넘으면 노드 카드가 10칸씩 반복된다 — 한 줄만 세면 나머지를 요소로 읽는다.
    const auto h20 = parseElementKeyword("*ELEMENT_SOLID_H20");
    const auto span = elementCardSpan(h20, {"1", "1"}, 20);
    ASSERT_GT(span.lines, 2);
    ASSERT_GT(span.nodeLines, 1);
}

TEST(elementCardSpan_두께카드가_있으면_줄이_는다) {
    // THICKNESS 옵션은 Card 2 를 반드시 끌고 온다 — 안 세면 그 줄을 요소로 읽는다.
    const auto plain = parseElementKeyword("*ELEMENT_SHELL");
    const auto thick = parseElementKeyword("*ELEMENT_SHELL_THICKNESS");
    const std::vector<std::string> f = {"1", "1", "1", "2", "3", "4"};
    ASSERT_GT(elementCardSpan(thick, f, 4).lines, elementCardSpan(plain, f, 4).lines);
}

// ── 보조 요소 — PID 칸이 타입마다 다르다 ────────────────────────────────

TEST(auxElementCard_BEAM_의_절점과_PID) {
    const auto a = auxElementCard("*ELEMENT_BEAM");
    ASSERT_TRUE(a.supported);
    ASSERT_TRUE(a.hasPart);
    ASSERT_EQ(a.partField, 1);
    ASSERT_EQ(a.nodeSkip, 2);
}

TEST(auxElementCard_MASS_의_PID_는_세번째_칸) {
    // ★`EID ID MASS PID` 다. 1 로 가정하면 **질량값을 파트 번호로** 읽는다.
    //   칸 3 은 **칸 차례**다 — MASS 가 E16(넓은 칸 2)이라 8칸으로 자르면 PID 는 칸 4(33-40열)다(2026-11-07).
    const auto a = auxElementCard("*ELEMENT_MASS");
    ASSERT_TRUE(a.supported);
    ASSERT_EQ(a.partField, 3);
    ASSERT_EQ(a.wideFields.size(), (size_t)1);
    ASSERT_EQ(a.wideFields[0], 2);
}

// 하나로 읽은 칸(`auxPrimaryFields`) — 칸 하나만 보는 시험이 쓴다
static std::vector<std::string> primaryOf(const AuxElementCard& a, const std::string& line, int fw) {
    return auxPrimaryFields(auxCardReadings(a, line, fw));
}

TEST(auxPrimaryFields_질량_PID_는_33_40열이다) {
    // Vol_I 159866-159930 — EID(I8) ID(I8) MASS(E16) PID(I8). 예전 판정은 8칸 칸 3(25-32열 — MASS 의 뒤 절반)을
    // PID 로 읽어 33-40열의 PID 를 놓치고, 질량값 숫자를 PID 로 셌다(이월 적용 · extract-parts · 재결속이 같이 틀렸다).
    const auto a = auxElementCard("*ELEMENT_MASS");
    const size_t pf = static_cast<size_t>(a.partField);
    const std::string std8 = "   95001       1             1.0       7";
    ASSERT_EQ(std8.substr(32, 8), std::string("       7"));
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, std8, 8), pf), 7);
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, std8, 8), (size_t)a.nodeSkip), 1);
    ASSERT_EQ(deckscan::fieldInt(deckscan::cardFields(std8, 8), 3), 0);        // 정수 폭 칸 3 = "     1.0"
    const std::string big = "   95001       1            1000       0";   // 질량 1000 · PID 0
    ASSERT_EQ(deckscan::fieldInt(deckscan::cardFields(big, 8), 3), 1000);     // 예전 판정이 PID 로 읽은 값
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, big, 8), pf), 0);
    // i10 — 정수 칸만 10칸(10·10·16·10) · long — 넷 다 20칸 · 콤마 자유형식 — 토큰 차례(Vol_I 19315 · 19353)
    char b[128];
    std::snprintf(b, sizeof b, "%10d%10d%16s%10d", 95001, 1, "1.0", 1234567);
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, b, 10), pf), 1234567);
    std::snprintf(b, sizeof b, "%10d%10d%16s%10d", 95001, 1, "1.0000000000E-03", 7);
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, b, 10), pf), 7);
    std::snprintf(b, sizeof b, "%20d%20d%20s%20d", 95001, 1, "1.0", 7);
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, b, 20), pf), 7);
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, "95001,1,1.0,7", 8), pf), 7);
    // MASS 를 8칸에 쓴 줄 — 하나로 읽은 칸은 늘 설명서 칸이다(33-40열이 비어 PID 0). 정수 폭의 PID 9 는 다른 읽기가 낸다(`auxPidsOf`)
    ASSERT_EQ(deckscan::fieldInt(primaryOf(a, "      12     105     0.5       9", 8), pf), 0);
    // 넓은 칸이 없는 족은 정수 폭 그대로다
    const auto beam = auxElementCard("*ELEMENT_BEAM");
    ASSERT_TRUE(primaryOf(beam, std8, 8) == deckscan::cardFields(std8, 8));
}

TEST(forEachNonGridElementCard_질량_PID_를_33_40열에서_읽는다) {
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_MASS", "$#   eid      id            mass     pid",
                                        "   95001       1             1.0       7",
                                        "   95002       2            1000       0", "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& c) { cs.push_back(c); });
    ASSERT_EQ(cs.size(), (size_t)2);
    ASSERT_TRUE(cs[0].known && cs[1].known);
    ASSERT_EQ(cs[0].pid, 7);
    ASSERT_EQ(cs[1].pid, 0);
    ASSERT_EQ(cs[0].nodes.size(), (size_t)1);
    ASSERT_EQ(cs[0].nodes[0], 1);
    ASSERT_EQ(cs[1].nodes[0], 2);
}

TEST(idrefs_질량_PID_는_33_40열에서만_센다) {
    // `*ELEMENT_MASS` 의 0 아닌 PID 는 정본이 「단정하지 못한 자리」로 센다 — 재결속은 그 블록을 거절한다.
    // 33-40열의 PID 7 은 센다 · 25-32열에 걸친 질량값 1000(PID 0)은 세지 않는다(예전엔 거꾸로였다).
    // (한 덱에 두 줄을 같이 두면 예전 판정도 「1」 이 나온다 — 틀린 줄을 센 1 이다. 줄마다 따로 잰다.)
    const std::vector<std::string> L7 = {"*KEYWORD", "*ELEMENT_MASS", "   95001       1             1.0       7", "*END"};
    const std::vector<std::string> L0 = {"*KEYWORD", "*ELEMENT_MASS", "   95002       2            1000       0", "*END"};
    ASSERT_EQ(idrefs::find(L7, 8).notChecked, 1);
    ASSERT_EQ(idrefs::find(L0, 8).notChecked, 0);
    char b[128];
    std::snprintf(b, sizeof b, "%10d%10d%16s%10d", 95001, 1, "1.0", 7);
    const std::vector<std::string> L10 = {"*KEYWORD I10=Y", "*ELEMENT_MASS", b, "*END"};
    ASSERT_EQ(idrefs::find(L10, 10).notChecked, 1);
    // 다른 읽기의 PID 는 덱의 파트일 때만 센다(`pidExists` — 재결속이 옛 덱의 PID 로 댄다 · 2026-11-07). 8칸 MASS 에 붙은 8자리 PID 는
    // 정수 폭 읽기로 쓴 꼴이다. PID 칸(33-40열)까지 쓴 줄(L0) · 정수 폭 읽기의 MASS 가 빈 줄(L32 — 재검토 R6)은 쓴 꼴이 아니라 세지 않는다
    const std::vector<std::string> LG = {"*KEYWORD", "*ELEMENT_MASS", "   95002       21.00E-0310000005", "*END"};
    ASSERT_EQ(idrefs::find(LG, 8).notChecked, 0);
    ASSERT_EQ(idrefs::find(LG, 8, nullptr, [](int p) { return p == 10000005; }).notChecked, 1);
    ASSERT_EQ(idrefs::find(LG, 8, nullptr, [](int p) { return p == 7; }).notChecked, 0);
    const std::vector<std::string> L32 = {"*KEYWORD", "*ELEMENT_MASS", "   95002       2            1000", "*END"};
    ASSERT_EQ(idrefs::find(L32, 8, nullptr, [](int p) { return p == 1000; }).notChecked, 0);
    ASSERT_EQ(idrefs::find(L0, 8, nullptr, [](int p) { return p == 1000; }).notChecked, 0);
    // `_PART` 는 칸 1 이 PID(센다) · `_PART_SET` 은 파트 세트 · `_MATRIX` 는 PID 칸이 없다(세지 않는다) — 칸 꼴이 달라
    // 질량 카드의 자리를 거기 대지 않는다
    const std::vector<std::string> P = {
        "*KEYWORD", "*ELEMENT_MASS_PART", "       7             1.0             0.0",
        "*ELEMENT_MASS_PART_SET", "       3             1.0             0.0",
        "*ELEMENT_MASS_MATRIX", "      9001         1         0",
        "       1.0       0.0       1.0       0.0       0.0       1.0       0.0",
        "       0.0       0.0       0.0       0.0       0.0       0.0       0.0",
        "       0.0       0.0       0.0       0.0       0.0       0.0       0.0", "*END"};
    ASSERT_EQ(idrefs::find(P, 8).notChecked, 1);
}

// ── 격자 리더가 담지 않는 솔리드 · 티쉘 변형 — 번호 바닥이 그 EID 를 몰랐다(2026-11-07) ─────────────
// 리더는 `*ELEMENT_SOLID`·`*ELEMENT_TSHELL` 맨 이름만 메시에 담는다. 격자 밖 걸음은 「parseElementKeyword 가 supported 면
// 리더가 담는다」고 보아 `_ORTHO` · `_H20` · `*ELEMENT_TSHELL_BETA` … 를 아무도 세지 않았다(id_floor · 조각 삽입 · 이월 적용).

TEST(gridReaderReadsKeyword_는_KFileReader_분기와_같다) {
    // 키워드마다 작은 덱을 써서 **리더로 읽어 본다** — 판정이 리더 분기와 갈리면 여기서 빨개진다.
    namespace fs = std::filesystem;
    const std::string solid8 = "       1       1\n       1       2       3       4       5       6       7       8\n";
    const std::string tshell8 = "       1       1       1       2       3       4       5       6       7       8\n";
    const std::string shell8 = "       1       1       1       2       3       4\n";
    struct Case { const char* kw; std::string data; bool reads; };
    const std::vector<Case> cases = {
        {"*ELEMENT_SOLID", solid8, true},
        {"*ELEMENT_SOLID %", "         1         1\n         1         2         3         4         5         6         7         8\n", true},
        {"*ELEMENT_SOLID_ORTHO", solid8 + "             1.0             0.0             0.0\n"
                                          "             0.0             1.0             0.0\n", false},
        {"*ELEMENT_SOLID_DOF", solid8 + "       1       2       3       4       5       6       7       8\n", false},
        {"*ELEMENT_SOLID_H20", solid8 + "       1       2       3       4       5       6       7       8       1       2\n", false},
        {"*ELEMENT_SOLID_H8TOH20", solid8, false},
        {"*ELEMENT_SOLID_TET4TOTET10", solid8, false},
        {"*ELEMENT_TSHELL", tshell8, true},
        {"*ELEMENT_TSHELL_BETA", tshell8 + "            30.0\n", false},
        {"*ELEMENT_SHELL", shell8, true},
        {"*ELEMENT_SHELL_THICKNESS", shell8 + "             1.0             1.0             1.0             1.0\n", true},
        {"*ELEMENT_SHELL_COMPOSITE", shell8 + "       1     1.0     0.0\n", false},
    };
    const fs::path tmp = fs::temp_directory_path() / "koorm_grid_reader_reads.k";
    for (const auto& c : cases) {
        ASSERT_EQ(gridReaderReadsKeyword(c.kw), c.reads);
        {
            std::ofstream o(tmp);
            o << "*KEYWORD\n*NODE\n";
            for (int n = 1; n <= 8; ++n) o << std::string(7, ' ') << n << "             0.0             0.0             0.0\n";
            o << c.kw << "\n" << c.data << "*END\n";
        }
        KFileReader r;
        const Mesh m = r.readFile(tmp.string());
        if ((m.getElementCount() > 0) != c.reads) {
            KooRemapper::Test::TestFramework::instance().fail(std::string("리더와 판정이 갈린다: ") + c.kw);
            std::error_code ec;
            fs::remove(tmp, ec);
            return;
        }
    }
    std::error_code ec;
    fs::remove(tmp, ec);
}

TEST(forEachNonGridElementCard_리더가_안_읽는_격자_변형을_센다) {
    const std::string hex = "       1       2       3       4       5       6       7       8";
    const std::vector<std::string> L = {
        "*KEYWORD",
        "*ELEMENT_SOLID", "       1       1", hex,                       // 리더가 담는다 — 걸음은 건너뛴다
        // 절점 수 옵션이 없는 솔리드 변형 — 줄 수가 그 PID 의 ELFORM 에 달려 **데이터 줄마다** 첫 칸을 센다
        "*ELEMENT_SOLID_ORTHO", "   98000       1", hex, "             1.0             0.0             0.0",
        "             0.0             1.0             0.0", "   99000       1", hex,
        "             1.0             0.0             0.0", "             0.0             1.0             0.0",
        // 줄 수가 PID 에 달리지 않는다 — 카드마다 한 번(Card 1 · 절점 줄 전부)
        "*ELEMENT_TSHELL_BETA", "   97000       2       1       2       3       4       5       6       7       8",
        "            30.0",
        "*ELEMENT_SOLID_H20", "   96000       3", "       1       2       3       4       5       6       7       8       9      10",
        "      11      12      13      14      15      16      17      18      19      20",
        "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& c) { cs.push_back(c); });
    std::vector<int> ortho;
    const NonGridElementCard* tsh = nullptr;
    const NonGridElementCard* h20 = nullptr;
    for (const auto& c : cs) {
        ASSERT_NE(c.keyword, std::string("*ELEMENT_SOLID"));
        if (c.keyword == "*ELEMENT_SOLID_ORTHO") {
            ASSERT_FALSE(c.known);
            ortho.push_back(c.eid);
        }
        if (c.keyword == "*ELEMENT_TSHELL_BETA") { ASSERT_TRUE(tsh == nullptr); tsh = &c; }
        if (c.keyword == "*ELEMENT_SOLID_H20") { ASSERT_TRUE(h20 == nullptr); h20 = &c; }
    }
    ASSERT_TRUE(std::find(ortho.begin(), ortho.end(), 98000) != ortho.end());
    ASSERT_TRUE(std::find(ortho.begin(), ortho.end(), 99000) != ortho.end());
    ASSERT_TRUE(tsh != nullptr && tsh->known);
    ASSERT_EQ(tsh->eid, 97000);
    ASSERT_EQ(tsh->pid, 2);
    ASSERT_EQ(tsh->nodes.size(), (size_t)8);
    ASSERT_TRUE(h20 != nullptr && h20->known);
    ASSERT_EQ(h20->eid, 96000);
    ASSERT_EQ(h20->pid, 3);
    ASSERT_EQ(h20->nodes.size(), (size_t)20);
    ASSERT_EQ(h20->nodes.back(), 20);
    ASSERT_EQ(nonGridElementMaxId(L), 99000);
}

TEST(auxElementCard_PLOTEL_은_PID_가_없다) {
    const auto a = auxElementCard("*ELEMENT_PLOTEL");
    ASSERT_TRUE(a.supported);
    ASSERT_FALSE(a.hasPart);
}

TEST(auxElementCard_모르는_변형은_supported_가_아니다) {
    // 추측해서 읽으면 **조용히 틀린 파트**로 옮긴다. 모르면 모른다고 해야 한다.
    const auto a = auxElementCard("*ELEMENT_MASS_NODE_SET");
    ASSERT_FALSE(a.supported);
    ASSERT_FALSE(a.reason.empty());
}

TEST(auxElementCard_SEATBELT_은_절점_구간이_둘) {
    const auto a = auxElementCard("*ELEMENT_SEATBELT");
    ASSERT_TRUE(a.supported);
    ASSERT_GT(a.nodeSkip2, 0);
    ASSERT_GT(a.nodeCount2, 0);
    // SLEN(칸 차례 5)이 E16 — 10칸 표에 아홉 자리(Vol_I 160311-160353)
    ASSERT_EQ(a.wideFields.size(), (size_t)1);
    ASSERT_EQ(a.wideFields[0], 5);
}

TEST(auxCardReadings_안전띠_N3_N4_는_57_72열이다) {
    // EID PID N1 N2 SBRID(I8) SLEN(F16) N3 N4(I8) — N3 57-64열 · N4 65-72열. 예전 판정은 8칸 칸 6·7(49-64열 — SLEN 의 뒤
    // 절반과 N3)을 읽어 N4 를 놓쳤다 — cleanup-nodes 가 쓰는 N4 를 지웠고 extract-parts 가 빠뜨렸다(2026-11-07 실측).
    const auto a = auxElementCard("*ELEMENT_SEATBELT");
    char b[200];
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%16s%8d%8d", 13, 9, 101, 102, 888, "0.0", 103, 104);
    const std::string std8 = b;
    ASSERT_EQ(deckscan::fieldInt(deckscan::cardFields(std8, 8), 6), 0);      // 정수 폭 칸 6 = SLEN 의 뒤 절반
    ASSERT_EQ(deckscan::fieldInt(deckscan::cardFields(std8, 8), 7), 103);    // 정수 폭 칸 7 = N3(N4 가 아니다)
    auto r = auxCardReadings(a, std8, 8);
    ASSERT_FALSE(r.comma);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 103);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 104);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 4), 888);                       // SBRID 는 절점 칸이 아니다(칸 차례 4)
    ASSERT_EQ(r.manual.col.size(), r.manual.f.size());
    ASSERT_EQ(r.manual.col[6], (size_t)56);
    ASSERT_EQ(r.manual.col[7], (size_t)64);
    ASSERT_EQ(r.manual.width[5], (size_t)16);
    ASSERT_TRUE(auxPrimaryFields(r) == r.manual.f);
    ASSERT_TRUE(primaryOf(a, std8, 8) == r.manual.f);
    // 설명서대로 쓴 줄 — 정수 폭 읽기는 SLEN 의 뒤 절반(「0.0」)을 읽어 절점이 아니다 · 다른 읽기만 말하는 절점이 없다
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
    ASSERT_TRUE(auxNodesAlt(a, r, r.manual.f).empty());
    ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    // i10 — 정수 칸만 10칸(SLEN 16 그대로) · long — 모두 20칸
    std::snprintf(b, sizeof b, "%10d%10d%10d%10d%10d%16s%10d%10d", 13, 9, 101, 102, 888, "0.0", 1000003, 1000004);
    r = auxCardReadings(a, b, 10);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 1000003);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 1000004);
    ASSERT_EQ(r.manual.col[6], (size_t)66);
    ASSERT_EQ(r.manual.col[7], (size_t)76);
    ASSERT_TRUE(auxNodesAlt(a, r, r.manual.f).empty());
    std::snprintf(b, sizeof b, "%20d%20d%20d%20d%20d%20s%20d%20d", 13, 9, 101, 102, 888, "0.0", 103, 104);
    r = auxCardReadings(a, b, 20);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 104);
    ASSERT_EQ(r.manual.col[7], (size_t)140);
    // 콤마 자유형식 — 콤마 토큰이 칸 차례 · 제자리에 쓸 열이 없다
    r = auxCardReadings(a, "13,9,101,102,888,0.0,103,104", 8);
    ASSERT_TRUE(r.comma);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 7), 104);
    ASSERT_FALSE(auxManualNodesPlaceable(a, r));
    // 공백으로만 가른 줄 — 고정폭 줄이라 열로만 읽는다(공백 토큰은 읽기가 아니다 · 2026-11-08). EID 칸(1-8열)에 빈칸이 껴 깨끗하지
    // 않고 제자리가 없다. 절점은 열 자리의 값뿐이다(칸 4 = 25-32열의 104)
    r = auxCardReadings(a, "13 9 101 102 888 0.0 103 104", 8);
    ASSERT_FALSE(r.manualClean);
    ASSERT_TRUE(auxPrimaryFields(r) == r.manual.f);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({104}));
    ASSERT_FALSE(auxManualNodesPlaceable(a, r));
    // 걸음(이월 적용의 나눠 쓴 절점 · 바닥)도 같은 칸을 본다
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_SEATBELT", std8, "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& x) { cs.push_back(x); });
    ASSERT_EQ(cs.size(), (size_t)1);
    ASSERT_TRUE(cs[0].nodes == std::vector<int>({101, 102, 103, 104}));
    ASSERT_EQ(cs[0].pid, 9);
    ASSERT_TRUE(cs[0].pids == std::vector<int>({9}));
}

TEST(auxCardReadings_정수_폭으로_쓴_안전띠_줄은_두_읽기를_다_낸다) {
    // 사용자 결정(2026-11-07) 「둘 다 남기고 번호 매기기는 거절」 — SLEN 을 8칸에 쓴 줄은 설명서 칸(SLEN 16)과 정수 폭이 갈린다.
    // 예전 판정(3ce0c4c)은 넓은 칸 자르기가 「깨끗하면」 그것만 믿었다 — SLEN 이 비면 깨끗해서 N3 을 SLEN 자리로 · N4 를 N3 으로 읽었다.
    const auto a = auxElementCard("*ELEMENT_SEATBELT");
    char b[200];
    // ① 빈 SLEN(8칸) — 설명서 칸은 깨끗하다(SLEN = 「103」 · N3 = 104 · N4 없음). 깨끗함만으로는 못 가른다
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%8s%8d%8d", 13, 9, 101, 102, 0, "", 103, 104);
    auto r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 104);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 0);
    ASSERT_EQ(deckscan::fieldInt(r.plain.f, 6), 103);
    ASSERT_EQ(deckscan::fieldInt(r.plain.f, 7), 104);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));      // 지키는 쪽 — 둘 다
    ASSERT_TRUE(r.plainAlt);                                                          // 64열 안 · 칸이 다 깨끗 · N3 · N4 둘 다 — 그렇게 썼을 수 있다
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({103}));                  // 번호 매기기 — 덱에 103 이 있으면 모호하다
    ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    ASSERT_TRUE(auxNodesSure(a, r) == std::vector<int>({101, 102, 104}));            // 두 읽기가 다 말한다
    ASSERT_TRUE(auxNodesUnsure(a, r) == std::vector<int>({103}));                    // 정수 폭만 — 덱에 있을 때만 쓰는 절점
    // ② SLEN 「0.0」 을 8칸에 — 설명서 칸의 SLEN 자리(41-56열)에 공백이 낀다. SLEN 은 쓰는 칸이 아니라 manual 은 깨끗하고 하나로 읽은
    //   칸이다(N3 = 104 · N4 없음). 정수 폭 읽기가 다른 읽기로 든다
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%8s%8d%8d", 13, 9, 101, 102, 888, "0.0", 103, 104);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_TRUE(auxPrimaryFields(r) == r.manual.f);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 6), 104);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_EQ(r.plain.col[7], (size_t)56);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({103}));
    // ③ 8자리 절점 + SLEN 「0.0」(8칸) — 칸 사이 공백이 없어 설명서 칸도 깨끗하다(SLEN = 「0.010000003」)
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%8s%8d%8d", 13, 9, 10000001, 10000002, 0, "0.0", 10000003, 10000004);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 10000004);
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({10000003}));
    // ④ i10 에 10칸 빈 SLEN · 7자리 N3 — 설명서 칸이 N3 을 둘로 잘라 「100」 · 「0003」(= 3)을 읽는다
    std::snprintf(b, sizeof b, "%10d%10d%10d%10d%10d%10s%10d%10d", 13, 9, 1000001, 1000002, 0, "", 1000003, 42);
    r = auxCardReadings(a, b, 10);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 3);
    ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 42);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({3, 42, 1000001, 1000002, 1000003}));
    ASSERT_TRUE(r.plainAlt);                                                          // i10 — 80열에서 끝난다
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({1000003}));
    // 설명서대로 쓴 줄은 갈리지 않는다 — 빈 SLEN · 빈 SBRID · 지수 · D 지수 · 왼쪽 맞춤 · 꼬리 주석
    for (const char* slen : {"", "0.0", "-1.234567890E-01", "-5.0D+00", "1.5", "100.0"}) {
        std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8s%16s%8d%8d", 13, 9, 101, 102, "", slen, 103, 104);
        r = auxCardReadings(a, b, 8);
        ASSERT_TRUE(auxNodesAlt(a, r, r.manual.f).empty());
        ASSERT_TRUE(auxNodesDisputed(a, r).empty());
        ASSERT_TRUE(auxManualNodesPlaceable(a, r));
        std::snprintf(b, sizeof b, "%8d%8d%8d%8d%-8d%-16s%-8d%-8d", 13, 9, 101, 102, 0, slen, 103, 104);   // 왼쪽 맞춤
        r = auxCardReadings(a, b, 8);
        ASSERT_TRUE(auxNodesAlt(a, r, r.manual.f).empty());
        ASSERT_TRUE(auxNodesDisputed(a, r).empty());
        ASSERT_EQ(deckscan::fieldInt(r.manual.f, 6), 103);
        ASSERT_EQ(deckscan::fieldInt(r.manual.f, 7), 104);
    }
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8s%16s%8d%8d  $ belt A", 13, 9, 101, 102, "", "0.0", 103, 104);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(auxNodesAlt(a, r, r.manual.f).empty());
    ASSERT_TRUE(auxNodesDisputed(a, r).empty());
    ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
    // 정수꼴 SLEN(「10」 · 「5」) — 정수 폭 읽기는 SLEN 의 뒤 절반을 N3 으로 읽지만 N4 가 65-72열에 있어 줄이 64열 밖에서 끝난다(규칙 (b)) —
    // 다른 읽기가 아니다. 유령 절점이 합집합에 들지 않는다(재검토 R1 — 예전엔 고아 절점을 남기고 · 싣고 · 번호를 매겼다)
    for (const char* slen : {"10", "5", "2621"}) {
        std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%16s%8d%8d", 13, 9, 101, 102, 0, slen, 103, 104);
        r = auxCardReadings(a, b, 8);
        ASSERT_FALSE(r.plainAlt);
        ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
        ASSERT_TRUE(auxNodesDisputed(a, r).empty());
        ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    }
    // 두 절점 띠(N3 · N4 없음) + 정수꼴 SLEN — 줄은 56열에서 끝나지만 정수 폭 읽기는 N3 = 10 · N4 없음이라 N3 ⟺ N4 를 어긴다(규칙 (c))
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%16s", 13, 9, 101, 102, 0, "10");
    r = auxCardReadings(a, b, 8);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102}));
    // i10 왼쪽 맞춤(N3 7자리 · N4 2자리 · 78열에서 끝난다) — 정수 폭 읽기의 N4 칸(71-80)에 빈칸이 낀다(규칙 (a)) — 다른 읽기가 아니다(재검토 R2)
    std::snprintf(b, sizeof b, "%-10d%-10d%-10d%-10d%-10d%-16s%-10d%-10d", 13, 9, 101, 102, 0, "0.0", 1000003, 42);
    std::string left = b;
    while (!left.empty() && left.back() == ' ') left.pop_back();
    r = auxCardReadings(a, left, 10);
    ASSERT_TRUE(r.manualClean);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({42, 101, 102, 1000003}));
    ASSERT_TRUE(auxNodesDisputed(a, r).empty());
    // 8칸에 SLEN 「0.5」 · N3 만(첫 검토의 꼴) — 설명서 칸의 SLEN 자리에 「0.5     103」 이 든다(빈칸이 낀 칸 — 설명서 꼴이 아닐 수 있다)
    // → 규칙 (c) 를 보지 않아 정수 폭의 N3 103 이 다른 읽기로 든다. 절점 셋을 다 지키고 번호 매기기는 갈림(103)으로 거절한다
    std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8d%8s%8d", 13, 9, 101, 102, 7, "0.5", 103);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103}));
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({103}));
}

TEST(auxCardReadings_고정폭_줄은_늘_설명서_칸이다) {
    // 2026-11-08 재검토 — 깨끗함을 줄 전체의 칸으로 재어, 카드 폭 뒤 글자나 SLEN · MASS 의 빈칸이 끼면 공백 토큰이 manual 을 갈음했다.
    // 꼬리 글이 붙은 안전띠 줄은 N4 를 버려 cleanup-nodes safe 가 쓰는 절점 103 을 지웠고(rc 0) 질량 줄은 버려졌다. LS-DYNA 는 열로
    // 읽고 카드 폭 뒤 글자를 읽지 않는다 — 고정폭 줄은 늘 manual 이 하나로 읽은 칸이고 깨끗함은 쓰는 칸(EID · PID · 절점)만 본다
    const auto belt = auxElementCard("*ELEMENT_SEATBELT");
    auto r = auxCardReadings(belt, "      13       9     101     102                     0.0     103     104        belt left 1", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(belt, r) == std::vector<int>({101, 102, 103, 104}));
    ASSERT_TRUE(auxManualNodesPlaceable(belt, r));
    for (const char* slen : {"- 1.5", "1 000.0", "1. 5"}) {   // SLEN 칸 안의 빈칸 — 쓰는 칸이 아니다
        char b[160];
        std::snprintf(b, sizeof b, "%8d%8d%8d%8d%8s%16s%8d%8d", 13, 9, 101, 102, "", slen, 103, 104);
        r = auxCardReadings(belt, b, 8);
        ASSERT_TRUE(r.manualClean);
        ASSERT_TRUE(auxNodesUnion(belt, r) == std::vector<int>({101, 102, 103, 104}));
        ASSERT_TRUE(auxNodesDisputed(belt, r).empty());
        ASSERT_TRUE(auxManualNodesPlaceable(belt, r));
    }
    // 쓰는 칸(N3 57-64열)에 빈칸이 끼면 그 칸은 값이 없고 제자리가 없다 — 다른 칸의 절점은 그대로
    r = auxCardReadings(belt, "      13       9     101     102                     0.0  10 3      104", 8);
    ASSERT_FALSE(r.manualClean);
    ASSERT_TRUE(auxNodesUnion(belt, r) == std::vector<int>({101, 102, 104}));
    ASSERT_FALSE(auxManualNodesPlaceable(belt, r));
    // 질량 — MASS 칸의 빈칸 · 칸이 붙은 줄 뒤 꼬리 글. PID 는 33-40열(예전엔 공백 토큰으로 읽어 질량을 버렸다)
    const auto mass = auxElementCard("*ELEMENT_MASS");
    r = auxCardReadings(mass, "   95001     105        1.0 E-03       7", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 1), 105);
    ASSERT_TRUE(auxPidsOf(mass, r) == std::vector<int>({7}));
    r = auxCardReadings(mass, "   9500110000005           0.001       7  mass on lid", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 0), 95001);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 1), 10000005);
    ASSERT_TRUE(auxPidsOf(mass, r) == std::vector<int>({7}));
    ASSERT_TRUE(auxNodesUnion(mass, r) == std::vector<int>({10000005}));
}

TEST(auxCardReadings_정수_폭_읽기는_칸마다_같은_꼴로_쓴_줄만) {
    // 규칙 (e) — 정수 폭 쓰개는 칸마다 같은 꼴로 쓴다. 칸마다 맞춤이 다른 설명서 꼴 i10 줄(N3 오른쪽 · N4 왼쪽 맞춤)을 정수 폭으로
    // 자르면 「10」(SLEN 의 끝)이 칸 61-70 의 가운데 · 「103104」 가 칸 71-80 의 가운데에 놓인다 — 다른 읽기가 아니다. 2026-11-08 전엔
    // 고아 절점 10 을 남기고 번호 매기기를 거절했다(재검토 퍼즈 i10 1200 줄 가운데 34)
    const auto a = auxElementCard("*ELEMENT_SEATBELT");
    char b[200];
    std::snprintf(b, sizeof b, "%10d%10d%10d%10d%10s%16s%10d%-10s", 1, 9, 101, 102, "", "10", 103, "104");
    auto r = auxCardReadings(a, b, 10);
    ASSERT_TRUE(r.manualClean);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
    ASSERT_TRUE(auxNodesDisputed(a, r).empty());
    ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    ASSERT_TRUE(auxNodesSure(a, r) == std::vector<int>({101, 102, 103, 104}));   // 다른 읽기가 없으면 manual 이 다 확실하다
    ASSERT_TRUE(auxNodesUnsure(a, r).empty());
    // 정수 폭으로 고르게 쓴 줄은 그대로 든다 — 오른쪽 맞춤(긴 N3 · 짧은 N4) · 왼쪽 맞춤 · 칸마다 뒤 한 칸 비움(`%7d `)
    std::snprintf(b, sizeof b, "%10d%10d%10d%10d%10s%10s%10d%10d", 13, 9, 101, 102, "", "", 123456789, 1234);
    r = auxCardReadings(a, b, 10);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 1234, 6789, 123456789}));   // 설명서 칸은 N3 을 「12345」 · 「6789」 로 자른다
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({123456789}));
    // 확실한 절점은 두 읽기가 다 말하는 것 · 나머지는 한 읽기만 — 설명서 칸의 6789 는 덱에 없을 수 있다(되읽기가 미정의로 세지 않는다)
    ASSERT_TRUE(auxNodesSure(a, r) == std::vector<int>({101, 102, 1234}));
    ASSERT_TRUE(auxNodesUnsure(a, r) == std::vector<int>({6789, 123456789}));
    std::snprintf(b, sizeof b, "%-8d%-8d%-8d%-8d%-8d%-8s%-8d%-8d", 13, 9, 101, 102, 0, "", 103, 104);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 103, 104}));
    std::snprintf(b, sizeof b, "%7d %7d %7d %7d %7s %7s %7d %7d ", 13, 9, 101, 102, "", "0.5", 1031, 1041);
    r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxNodesUnion(a, r) == std::vector<int>({101, 102, 1031, 1041}));
    ASSERT_TRUE(auxNodesDisputed(a, r) == std::vector<int>({1031}));
    // 질량 — 고르게 쓴 정수 폭 줄의 PID 는 후보로 든다 · 칸마다 맞춤이 다른 줄은 아니다
    const auto m = auxElementCard("*ELEMENT_MASS");
    r = auxCardReadings(m, "   95001     105     1.0       7", 8);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxPidsOf(m, r) == std::vector<int>({7}));
    r = auxCardReadings(m, "95001   105        1.0      77", 8);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxPidsOf(m, r).empty());
}

TEST(auxManualNodesPlaceable_0_인_칸은_주석과_겹쳐도_된다) {
    // 왼쪽 맞춤 1D 띠(N3 · N4 = 0) 뒤 꼬리 주석이 N4 칸(65-72열) 안에서 시작한다 — 0 은 번호가 아니라 바꿔 쓰지 않으니 거절할 까닭이
    // 없다(검토자 퍼즈 — 예전엔 「번호 칸에 겹친 $ 주석」 으로 renumber 를 거절했다). 같은 자리의 주석이 양수 N4 와 겹치면 여전히 못 쓴다
    const auto a = auxElementCard("*ELEMENT_SEATBELT");
    char b[160];
    std::snprintf(b, sizeof b, "%-8d%-8d%-8d%-8d%-8d%-16s%-8d%-8d", 13, 9, 101, 102, 0, "0.0", 0, 0);
    std::string l = b;
    while (!l.empty() && l.back() == ' ') l.pop_back();
    auto r = auxCardReadings(a, l + "  $ belt", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_TRUE(auxManualNodesPlaceable(a, r));
    std::snprintf(b, sizeof b, "%-8d%-8d%-8d%-8d%-8d%-16s%-8d%-8d", 13, 9, 101, 102, 0, "0.0", 103, 104);
    l = b;
    while (!l.empty() && l.back() == ' ') l.pop_back();
    r = auxCardReadings(a, l + "  $ belt", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_FALSE(auxManualNodesPlaceable(a, r));
}

TEST(auxPidsOf_질량_PID_후보는_읽기마다) {
    // 질량 PID(33-40열)는 MASS(E16) 뒤에 있다 — 줄을 정수 폭으로 썼으면(MASS 8칸) 읽기마다 PID 가 갈린다
    const auto a = auxElementCard("*ELEMENT_MASS");
    ASSERT_EQ(a.card1Fields, 4);
    auto r = auxCardReadings(a, "   95001       1             1.0       7", 8);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({7}));
    // 정수꼴 질량(1000) 뒤에 PID 칸(33-40열)까지 쓴 줄은 설명서 꼴이다 — 정수 폭 읽기(25-32열의 1000)는 후보가 아니다(규칙 (b))
    r = auxCardReadings(a, "   95001       1            1000       0", 8);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxPidsOf(a, r).empty());
    r = auxCardReadings(a, "   95001       1            1000       7", 8);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({7}));
    // 줄이 32열에서 끝나도 정수 폭 읽기의 MASS 칸(17-24열)이 비면 질량 요소로 쓴 꼴이 아니다(규칙 (d) · 재검토 R6) — PID 후보가 아니다
    r = auxCardReadings(a, "   95001       1            1000", 8);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 3), 0);
    ASSERT_TRUE(auxPidsOf(a, r).empty());
    r = auxCardReadings(a, "    9003       1               1", 8);
    ASSERT_TRUE(auxPidsOf(a, r).empty());
    // 8칸 MASS 에 8자리 PID 가 붙은 줄 — 칸 사이 공백이 없어 설명서 칸도 깨끗하다(MASS 「1.00E-0310000005」 · PID 없음)
    r = auxCardReadings(a, "   95001       11.00E-0310000005", 8);
    ASSERT_TRUE(r.manualClean);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 3), 0);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({10000005}));
    // 8칸에 쓴 줄 — 하나로 읽은 칸은 설명서 칸(33-40열이 비어 PID 0), 정수 폭의 PID 9 는 다른 읽기로 든다(MASS 칸에 빈칸이 낀다)
    r = auxCardReadings(a, "      12     105     0.5       9", 8);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 3), 0);
    ASSERT_TRUE(r.plainAlt);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({9}));
    // 줄이 33-40열까지 가면 그 PID 가 LS-DYNA 가 읽는 PID 다 — 정수 폭 읽기는 32열 밖에 글자가 있어 다른 읽기가 아니다(규칙 (b))
    r = auxCardReadings(a, "      12     105     0.5       9       7", 8);
    ASSERT_EQ(deckscan::fieldInt(auxPrimaryFields(r), 3), 7);
    ASSERT_FALSE(r.plainAlt);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({7}));
    // 걸음은 후보 전부를 넘긴다(이월 적용 aux_in_part 가 본다)
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_MASS", "   95001       11.00E-0310000005", "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& x) { cs.push_back(x); });
    ASSERT_EQ(cs.size(), (size_t)1);
    ASSERT_EQ(cs[0].pid, 0);
    ASSERT_TRUE(cs[0].pids == std::vector<int>({10000005}));
    // PID 칸이 없는 족은 비었다
    const auto pl = auxElementCard("*ELEMENT_PLOTEL");
    ASSERT_TRUE(auxPidsOf(pl, auxCardReadings(pl, "       1     101     102", 8)).empty());
}

TEST(auxElementCard_보_장치는_PID_칸이_없다) {
    // `*ELEMENT_BEAM_PULLEY`(PUID BID1 BID2 PNID …) · `*ELEMENT_BEAM_SOURCE`(BSID BSNID BSEID …)는 보 요소가 아니라 별개 키워드다
    // (Vol_I 156795 · 156905) — 칸 1 을 PID 로 읽지 않는다(예전엔 BID1 · BSNID 를 PID 로 셌다). 보 요소 번호 칸만 적는다
    auto a = auxElementCard("*ELEMENT_BEAM_PULLEY");
    ASSERT_TRUE(a.family == AuxFamily::BEAM);
    ASSERT_FALSE(a.supported);
    ASSERT_FALSE(a.hasPart);
    ASSERT_EQ(a.partField, -1);
    ASSERT_TRUE(a.elemRefFields == std::vector<int>({1, 2}));
    a = auxElementCard("*ELEMENT_BEAM_SOURCE");
    ASSERT_FALSE(a.hasPart);
    ASSERT_TRUE(a.elemRefFields == std::vector<int>({2}));
    a = auxElementCard("*ELEMENT_BEAM_ORIENTATION");   // 보의 옵션은 그대로다
    ASSERT_TRUE(a.supported);
    ASSERT_TRUE(a.hasPart);
    ASSERT_TRUE(a.elemRefFields.empty());
}

TEST(auxElementCard_보_ELBOW_의_가운데_절점은_마지막_옵션_카드) {
    // `*ELEMENT_BEAM_ELBOW` Card 10 = MN(가운데 절점 · 8칸 표 I10 — Vol_I 156596-156638). 옵션 카드는 설명서 차례(2 … 10)로 오니
    // ELBOW 카드는 늘 마지막 줄이다. 예전엔 Card 1 만 읽어 cleanup-nodes safe 가 MN 을 지웠다(재검토 D2)
    auto a = auxElementCard("*ELEMENT_BEAM_ELBOW");
    ASSERT_TRUE(a.supported);
    ASSERT_EQ(a.lines, 2);
    ASSERT_EQ(a.optNodes.size(), (size_t)1);
    ASSERT_TRUE(auxOptNodeFields(a, 1) && *auxOptNodeFields(a, 1) == std::vector<int>({0}));
    ASSERT_TRUE(auxOptNodeFields(a, 0) == nullptr);   // Card 1 은 옵션 카드가 아니다
    ASSERT_TRUE(auxOptNodesOf(a, 1, "       104", 8) == std::vector<int>({104}));
    ASSERT_TRUE(auxOptNodesOf(a, 1, "104,0", 8) == std::vector<int>({104}));
    ASSERT_TRUE(auxOptNodesOf(a, 0, "       104", 8).empty());
    // 번호를 제자리에 바꿔 쓸 수 있나 — MN 칸(1-10열) 안에서 시작하는 `$` 주석 · 콤마 · 칸 안 빈칸이면 못 쓴다(새 번호가 `$` 를 덮었다)
    ASSERT_TRUE(auxOptNodesPlaceable(a, 1, "       104", 8));
    ASSERT_TRUE(auxOptNodesPlaceable(a, 1, "       104 $ mid node", 8));   // 칸 뒤 주석
    ASSERT_FALSE(auxOptNodesPlaceable(a, 1, "     104 $m", 8));             // 주석이 10열에서 시작 — 칸 안
    ASSERT_FALSE(auxOptNodesPlaceable(a, 1, "104,0", 8));
    ASSERT_FALSE(auxOptNodesPlaceable(a, 1, "  10 4", 8));
    ASSERT_TRUE(auxOptNodesPlaceable(a, 1, "0 $ none", 8));                 // 0 은 번호가 아니다 — 바꿔 쓰지 않는다
    a = auxElementCard("*ELEMENT_BEAM_ORIENTATION_ELBOW");
    ASSERT_EQ(a.lines, 3);
    ASSERT_TRUE(auxOptNodeFields(a, 2) != nullptr && auxOptNodeFields(a, 1) == nullptr);
    ASSERT_TRUE(auxElementCard("*ELEMENT_BEAM_ORIENTATION").optNodes.empty());
    // 걸음은 MN 까지 읽고 카드를 넘긴다(이월 적용의 나눠 쓴 절점 · 바닥)
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_BEAM_ELBOW", "      21       8     101     102     103", "       104",
                                        "      22       8     105     106     107", "       108", "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& x) { cs.push_back(x); });
    ASSERT_EQ(cs.size(), (size_t)2);
    ASSERT_EQ(cs[0].eid, 21);
    ASSERT_TRUE(cs[0].nodes == std::vector<int>({101, 102, 103, 104}));
    ASSERT_TRUE(cs[1].nodes == std::vector<int>({105, 106, 107, 108}));
}

TEST(auxElementCard_보_WARPAGE_의_스칼라_절점은_Card_9) {
    // `*ELEMENT_BEAM_WARPAGE` Card 9 = SN1 SN2(스칼라 절점 · 8칸 표 I10 — Vol_I 155889 · 156529-156548). 옵션 카드는 설명서 차례
    // (2 … 10)로 오니 WARPAGE 카드는 ELBOW(Card 10) 앞, ELBOW 가 없으면 마지막이다. 예전엔 아무 걸음도 SN 을 읽지 않았다(셋째 묶음)
    auto a = auxElementCard("*ELEMENT_BEAM_WARPAGE");
    ASSERT_TRUE(a.supported);
    ASSERT_EQ(a.lines, 2);
    ASSERT_TRUE(auxOptNodeFields(a, 1) && *auxOptNodeFields(a, 1) == std::vector<int>({0, 1}));
    ASSERT_TRUE(auxOptNodesOf(a, 1, "       201       202", 8) == std::vector<int>({201, 202}));
    ASSERT_TRUE(auxOptNodesOf(a, 1, "                 201                 202", 20) == std::vector<int>({201, 202}));   // long 은 칸 폭 20
    ASSERT_FALSE(auxOptNodesPlaceable(a, 1, "     201 $       202", 8));        // 주석이 SN1 칸 안에서 시작한다
    // 옵션 셋 — ORIENTATION(Card 8 · 줄 1) · WARPAGE(Card 9 · 줄 2) · ELBOW(Card 10 · 줄 3)
    a = auxElementCard("*ELEMENT_BEAM_WARPAGE_ELBOW_ORIENTATION");
    ASSERT_TRUE(a.supported);
    ASSERT_EQ(a.lines, 4);
    ASSERT_TRUE(auxOptNodeFields(a, 1) == nullptr);
    ASSERT_TRUE(auxOptNodeFields(a, 2) && *auxOptNodeFields(a, 2) == std::vector<int>({0, 1}));
    ASSERT_TRUE(auxOptNodeFields(a, 3) && *auxOptNodeFields(a, 3) == std::vector<int>({0}));
    // 걸음은 SN 까지 읽고 카드를 넘긴다
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_BEAM_WARPAGE", "      21       8     101     102     103", "       201       202",
                                        "      22       8     105     106     107", "       203       204", "*END"};
    std::vector<NonGridElementCard> cs;
    forEachNonGridElementCard(L, [&](const NonGridElementCard& x) { cs.push_back(x); });
    ASSERT_EQ(cs.size(), (size_t)2);
    ASSERT_TRUE(cs[0].nodes == std::vector<int>({101, 102, 103, 201, 202}));
    ASSERT_TRUE(cs[1].nodes == std::vector<int>({105, 106, 107, 203, 204}));
    // 스칼라 절점 번호는 `*NODE` 번호와 겹치지 않는다 — 새 절점 번호의 바닥이 그 위다
    const std::vector<std::string> S = {"*KEYWORD", "*NODE", "       1             0.0             0.0             0.0",
                                        "*NODE_SCALAR", "     201       1", "*NODE_SCALAR_VALUE",
                                        "     907             0.0             0.0             0.0       1", "*END"};
    ASSERT_EQ(scalarNodeMaxId(S), 907);
    ASSERT_TRUE(isScalarNodeKeyword("*NODE_SCALAR") && isScalarNodeKeyword("*NODE_SCALAR_VALUE") && !isScalarNodeKeyword("*NODE"));
}

TEST(auxElementCard_질량_얹기는_칸_0_이_PID) {
    // `*ELEMENT_MASS_PART` = ID(I8) ADDMASS(F16) FINMASS(F16) LCID(I8) MWD(I8) (Vol_I 160135-160207) — 칸 0 이 PID(`_SET` 이면
    // 파트 세트 ID)이고 요소 번호 · 절점 칸이 없다. 예전엔 질량 카드의 칸 3 을 PID 로 읽어 고른 파트의 추가 질량을 버렸다
    auto a = auxElementCard("*ELEMENT_MASS_PART");
    ASSERT_TRUE(a.supported);
    ASSERT_TRUE(a.hasPart);
    ASSERT_FALSE(a.hasEid);
    ASSERT_FALSE(a.partIsSet);
    ASSERT_EQ(a.partField, 0);
    ASSERT_EQ(a.nodeCount, 0);
    char b[128];
    std::snprintf(b, sizeof b, "%8d%16s%16s%8d%8d", 9, "0.25", "0.0", 105, 0);
    const auto r = auxCardReadings(a, b, 8);
    ASSERT_TRUE(auxPidsOf(a, r) == std::vector<int>({9}));
    ASSERT_TRUE(auxNodesUnion(a, r).empty());                 // LCID(105)는 절점이 아니다
    a = auxElementCard("*ELEMENT_MASS_PART_SET");
    ASSERT_TRUE(a.supported);
    ASSERT_TRUE(a.partIsSet);
    ASSERT_FALSE(a.hasEid);
    // 걸음은 질량 얹기를 넘긴다(요소가 아니다 — 번호 바닥이 그 PID 를 EID 로 세지 않는다)
    const std::vector<std::string> L = {"*KEYWORD", "*ELEMENT_MASS_PART", b, "*ELEMENT_MASS_PART_SET", b, "*END"};
    size_t n = 0;
    forEachNonGridElementCard(L, [&](const NonGridElementCard&) { ++n; });
    ASSERT_EQ(n, (size_t)0);
    ASSERT_FALSE(auxElementCard("*ELEMENT_MASS_NODE_SET").supported);   // 그 밖 질량 변형은 그대로다
    ASSERT_FALSE(auxElementCard("*ELEMENT_MASS_MATRIX").supported);
}

TEST(auxElementCard_안전띠_장치_키워드는_PID_칸이_없다) {
    // `_ACCELEROMETER`·`_PRETENSIONER`·`_RETRACTOR`·`_SENSOR`·`_SLIPRING` 은 별개 키워드다 — 10칸 폭 표이고 PID 칸이 없다
    // (Vol_I 160482 · 160602 · 160931 · 161342 · 161725). 칸 자리를 짐작하지 않는다(extract-parts 가 칸 1 을 PID 로 읽었다).
    for (const char* k : {"*ELEMENT_SEATBELT_ACCELEROMETER", "*ELEMENT_SEATBELT_PRETENSIONER", "*ELEMENT_SEATBELT_RETRACTOR",
                          "*ELEMENT_SEATBELT_SENSOR", "*ELEMENT_SEATBELT_SLIPRING"}) {
        const auto a = auxElementCard(k);
        ASSERT_FALSE(a.supported);
        ASSERT_FALSE(a.hasPart);
        ASSERT_EQ(a.partField, -1);
        ASSERT_TRUE(a.wideFields.empty());
    }
}

// ── 개행 — 한 파일 안에서 갈리면 최악이다 ───────────────────────────────
// `relax` 가 그랬다: 원본 줄은 CRLF, 새로 넣은 줄은 LF. 25곳 넘는 자체 `ofstream` 이
// 각자 개행을 정하던 것이 원인이었다(DF-01).

TEST(NewlineStreambuf_가_LF_를_CRLF_로_바꾼다) {
    std::ostringstream sink;
    {
        NewlineStreambuf buf(sink.rdbuf(), DeckNewline::CRLF);
        std::ostream out(&buf);
        out << "a\nb\n";
        out.flush();
    }
    ASSERT_EQ(sink.str(), std::string("a\r\nb\r\n"));
}

TEST(NewlineStreambuf_가_이미_CRLF_인_것을_두_번_바꾸지_않는다) {
    // ★`\r\n` 을 `\r\r\n` 으로 만들면 LS-DYNA 가 줄을 못 읽는다. 들어온 CR 을 기억해야 한다.
    std::ostringstream sink;
    {
        NewlineStreambuf buf(sink.rdbuf(), DeckNewline::CRLF);
        std::ostream out(&buf);
        out << "a\r\nb\r\n";
        out.flush();
    }
    ASSERT_EQ(sink.str(), std::string("a\r\nb\r\n"));
}

TEST(NewlineStreambuf_LF_모드는_그대로_둔다) {
    std::ostringstream sink;
    {
        NewlineStreambuf buf(sink.rdbuf(), DeckNewline::LF);
        std::ostream out(&buf);
        out << "a\nb\n";
        out.flush();
    }
    ASSERT_EQ(sink.str(), std::string("a\nb\n"));
}

// ── 쓰기 오류 — 잘린 덱을 멀쩡한 스트림으로 끝내지 않는다(여섯째 검토 S2) ───────────
// 디스크가 차거나 파일 크기 상한에 걸리면 아래 파일 버퍼가 짧게 쓴다. CRLF 갈래가 그 결과를 버려 스트림이 멀쩡했고
// `DeckWriter::close()` 는 아무것도 돌려주지 않았다.

namespace {
// `cap` 글자만 받고 그 뒤로는 실패하는 버퍼(디스크가 찬 파일의 대역)
struct CappedSink : std::streambuf {
    std::string got;
    size_t cap;
    explicit CappedSink(size_t c) : cap(c) {}
    int_type overflow(int_type c) override {
        if (traits_type::eq_int_type(c, traits_type::eof())) return traits_type::not_eof(c);
        if (got.size() >= cap) return traits_type::eof();
        got.push_back(traits_type::to_char_type(c));
        return c;
    }
    std::streamsize xsputn(const char* s, std::streamsize n) override {
        const std::streamsize room = static_cast<std::streamsize>(cap) - static_cast<std::streamsize>(got.size());
        const std::streamsize w = std::max<std::streamsize>(0, std::min(room, n));
        got.append(s, static_cast<size_t>(w));
        return w;
    }
};
}  // namespace

TEST(NewlineStreambuf_는_짧은_쓰기를_스트림_실패로_올린다_CRLF_LF) {
    for (DeckNewline nl : {DeckNewline::CRLF, DeckNewline::LF}) {
        CappedSink sink(5);
        NewlineStreambuf buf(&sink, nl);
        std::ostream out(&buf);
        out << "abc\ndef\nghi\n";
        out.flush();
        ASSERT_TRUE(out.bad());
        ASSERT_TRUE(buf.failed());
        ASSERT_EQ(sink.got.size(), (size_t)5);
    }
}

TEST(DeckWriter_close_는_쓰기_오류를_돌려주고_공용_기록에_남긴다) {
    if (!std::filesystem::exists("/dev/full")) return;   // 리눅스의 「늘 찬 장치」 — 쓰기마다 ENOSPC
    const size_t before = deck_write::failures().size();
    for (DeckNewline nl : {DeckNewline::CRLF, DeckNewline::LF}) {
        DeckWriter w("/dev/full", nl);
        ASSERT_TRUE(w.ok());
        for (int i = 0; i < 20000; ++i) w.stream() << "       1     0.0     0.0     0.0\n";   // 파일 버퍼를 넘게
        ASSERT_FALSE(w.close());
        ASSERT_TRUE(w.failed());
        ASSERT_TRUE(w.error().find("/dev/full") != std::string::npos);
        ASSERT_FALSE(w.close());   // 두 번 닫아도 같은 답
    }
    ASSERT_EQ(deck_write::failures().size(), before + 2);
    deck_write::failures().resize(before);   // 다른 시험에 남기지 않는다
    {   // 멀쩡한 쓰기는 true 이고 기록이 없다
        const std::string p = (std::filesystem::temp_directory_path() / "koorm_deckwriter_ok.k").string();
        DeckWriter w(p, DeckNewline::LF);
        w.stream() << "*KEYWORD\n*END\n";
        ASSERT_TRUE(w.close());
        std::filesystem::remove(p);
    }
    ASSERT_EQ(deck_write::failures().size(), before);
}

// ── 정렬·탐색 — 세트 멤버 판정이 여기 얹힌다 ────────────────────────────

TEST(sortUnique_와_inSorted) {
    std::vector<int> v = {5, 1, 5, 3, 1};
    deckscan::sortUnique(v);
    ASSERT_EQ(static_cast<int>(v.size()), 3);
    ASSERT_TRUE(deckscan::inSorted(v, 3));
    ASSERT_FALSE(deckscan::inSorted(v, 4));
    ASSERT_FALSE(deckscan::inSorted({}, 1));
}

TEST(harvestInts_는_일부러_과수집한다) {
    // ★이 함수는 8칸·10칸·공백 **세 번** 훑어 모두 담는다 — 그래서 중복이 나온다.
    //   참조를 훑는 자리에서는 **과수집이 안전하고 누락이 위험**하다(쓰이는 절점을 하나라도
    //   놓치면 고아로 보고 지운다). 그러니 "개수" 가 아니라 **빠짐없음**을 못 박는다.
    std::vector<int> out;
    deckscan::harvestInts("   1   2   3", out);
    deckscan::sortUnique(out);
    ASSERT_EQ(static_cast<int>(out.size()), 3);
    ASSERT_TRUE(deckscan::inSorted(out, 1));
    ASSERT_TRUE(deckscan::inSorted(out, 2));
    ASSERT_TRUE(deckscan::inSorted(out, 3));
}

// ── 경로 — 인클루드를 못 찾으면 반쪽 모델로 돈다 ────────────────────────

TEST(dirOf_와_joinPath) {
    ASSERT_EQ(deckscan::dirOf("/a/b/c.k"), std::string("/a/b"));
    ASSERT_EQ(deckscan::joinPath("/a/b", "d.k"), std::string("/a/b/d.k"));
    // 절대 경로는 그대로 둔다 — 붙이면 `/a/b//x/y.k` 가 된다.
    ASSERT_EQ(deckscan::joinPath("/a/b", "/x/y.k"), std::string("/x/y.k"));
}

// ── 2차 솔리드 쓰기 — 전체 절점으로 쓰고, 없으면 쓰지 않는다(2026-10-17) ─────────────────────
// 예전 쓰기는 모든 솔리드를 옛 한 줄 꼴(EID PID N1..N8)로 썼다 — 2차 요소는 중간절점이 사라졌다.
TEST(KFileWriter_TET10_은_두_카드_꼴로_전체_절점을_쓴다) {
    namespace fs = std::filesystem;
    Mesh m;
    for (int i = 1; i <= 10; ++i) m.addNode(Node(i, 0.1 * i, 0.0, 0.0));
    Element e(1, 1, {1, 2, 3, 4, 4, 4, 4, 4});
    e.type = ElementType::TET10;
    m.addElement(e);
    const fs::path tmp = fs::temp_directory_path() / "koorm_writer_tet10.k";
    {
        KFileWriter w;
        ASSERT_FALSE(w.writeFile(tmp.string(), m));                    // 중간절점 목록이 없다 — 쓰지 않는다
        ASSERT_TRUE(w.getErrorMessage().find("중간절점") != std::string::npos);
    }
    m.solidAllNodes[1] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    {
        KFileWriter w;
        ASSERT_TRUE(w.writeFile(tmp.string(), m));
    }
    std::ifstream in(tmp);
    std::vector<std::string> L;
    for (std::string l; std::getline(in, l);) L.push_back(l);
    std::error_code ec;
    fs::remove(tmp, ec);
    size_t k = 0;
    while (k < L.size() && L[k].rfind("*ELEMENT_SOLID", 0) != 0) ++k;
    ASSERT_TRUE(k + 3 < L.size());
    // 주석 눈금 다음이 Card 1(EID PID) · Card 2(N1..N10)다
    size_t c1 = k + 1;
    while (c1 < L.size() && L[c1].rfind("$", 0) == 0) ++c1;
    ASSERT_EQ(deckscan::cardFields(L[c1], 8).size(), (size_t)2);
    const auto n = deckscan::cardFields(L[c1 + 1], 8);
    ASSERT_EQ(n.size(), (size_t)10);
    ASSERT_EQ(deckscan::fieldInt(n, 9), 10);
}
