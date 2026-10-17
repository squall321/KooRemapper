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
#include "parser/NodeRefs.h"
#include "parser/KFileWriter.h"
#include "core/Mesh.h"

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
    const auto a = auxElementCard("*ELEMENT_MASS");
    ASSERT_TRUE(a.supported);
    ASSERT_EQ(a.partField, 3);
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
