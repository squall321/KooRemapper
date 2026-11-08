// 재질 번호 공용 훑기(matids) — 쌓인 재질 묶음 · 열 재질 · 덧붙임 카드를 세고 · 지우고 · 베끼는 규칙(MaterialIds.h)
#include "TestFramework.h"

#include "parser/DeckScan.h"
#include "parser/MaterialIds.h"

#include <sstream>

using namespace KooRemapper;

namespace {
std::vector<std::string> matDeckLines(const std::string& text) {
    std::vector<std::string> out;
    std::istringstream is(text);
    std::string l;
    while (std::getline(is, l)) out.push_back(l);
    return out;
}
const char* kMatEl2 = "         2   7.85E-9    210000       0.3";
const char* kMatEl3 = "         3   7.85E-9    210000       0.3";
}  // namespace

TEST(MaterialIds_쌓인_묶음을_센다) {
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 + "\n" + kMatEl3 + "\n*END\n");
    const auto d = matids::defined(L);
    ASSERT_EQ((int)d.size(), 2);
    ASSERT_TRUE(d.count(3) == 1);
    ASSERT_EQ(matids::maxId(L), 3);
    const auto at = matids::definitionLines(L);
    ASSERT_EQ((int)at.at(3).front(), 3);   // 그 묶음의 Card 1 줄
}

TEST(MaterialIds_열_재질과_덧붙임은_MID_가_아니다) {
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 +
                       "\n*MAT_T01\n        50       0.0       0.0       0.0\n       1.0       1.0\n"
                       "*MAT_THERMAL_ISOTROPIC\n        60       0.0       0.0       0.0\n       1.0       1.0\n"
                       "*MAT_ADD_EROSION\n        70\n*END\n");
    ASSERT_EQ(matids::maxId(L), 2);
    ASSERT_TRUE(matids::isMidKeyedAddOn("*MAT_ADD_EROSION_TITLE"));
    ASSERT_FALSE(matids::isMidKeyedAddOn("*MAT_ADD_THERMAL_EXPANSION"));
    ASSERT_FALSE(matids::isStructuralKeyword("*MAT_T01"));
    ASSERT_TRUE(matids::isStructuralKeyword("*MAT_TABULATED_JOHNSON_COOK"));
}

TEST(MaterialIds_E가_음수면_Card_1_1을_건넌다) {
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n         2   7.85E-9      -1.0       0.3\n        12         0         0\n") +
                       kMatEl3 + "\n*END\n");
    const auto d = matids::defined(L);
    ASSERT_TRUE(d.count(3) == 1);
    ASSERT_TRUE(d.count(12) == 0);
    ASSERT_EQ(matids::maxId(L), 3);
}

TEST(MaterialIds_모르는_꼴은_행마다_넉넉히_센다) {
    auto L = matDeckLines("*KEYWORD\n*MAT_ORTHOTROPIC_ELASTIC\n         3   7.85E-9    1000.0\n     500.0\n         9   7.85E-9    1000.0\n*END\n");
    ASSERT_TRUE(matids::defined(L).count(9) == 0);   // 있나는 묶음의 Card 1 만
    ASSERT_TRUE(matids::inUse(L).count(9) == 1);     // 커서 · 겹침은 넉넉히
    ASSERT_EQ(matids::maxId(L), 9);
}

TEST(MaterialIds_정의만_지운다_쌓인_다른_재질과_열_재질은_둔다) {
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 + "\n" + kMatEl3 +
                       "\n*MAT_T01\n         2       0.0       0.0       0.0\n       1.0       1.0\n"
                       "*MAT_ADD_THERMAL_EXPANSION\n         2         0       1.0\n*END\n");
    const auto r = matids::removeDefinition(L, 2);
    ASSERT_EQ(r.sets, 1);
    ASSERT_FALSE(r.stillUsed);
    ASSERT_TRUE(matids::defined(L).count(3) == 1);
    std::string all;
    for (const auto& l : L) all += l + "\n";
    ASSERT_TRUE(all.find("*MAT_T01") != std::string::npos);
    ASSERT_TRUE(all.find("*MAT_ADD_THERMAL_EXPANSION") != std::string::npos);
    ASSERT_TRUE(all.find("*MAT_ELASTIC") != std::string::npos);   // MID 3 이 남아 키워드도 남는다
    auto L2 = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 + "\n*END\n");
    matids::removeDefinition(L2, 2);
    ASSERT_EQ((int)L2.size(), 2);                     // 블록의 묶음이 다 지워지면 키워드 줄째
}

TEST(MaterialIds_MID_꼴_덧붙임만_지운다) {
    auto L = matDeckLines("*KEYWORD\n*MAT_ADD_EROSION\n         2\n*MAT_ADD_THERMAL_EXPANSION\n         2         0       1.0\n*END\n");
    ASSERT_EQ(matids::removeMidAddOns(L, 2), 1);
    std::string all;
    for (const auto& l : L) all += l + "\n";
    ASSERT_TRUE(all.find("*MAT_ADD_EROSION") == std::string::npos);
    ASSERT_TRUE(all.find("*MAT_ADD_THERMAL_EXPANSION") != std::string::npos);
}

TEST(MaterialIds_구조_재질만_베낀다_칸_폭_그대로) {
    auto L = matDeckLines("*KEYWORD\n*MAT_T01\n         2       0.0       0.0       0.0\n       1.0       1.0\n*MAT_ELASTIC_TITLE\nSTEEL\n"
                       "$#     mid        ro         e        pr\n         2   7.85E-9    210000       0.3\n*END\n");
    const std::string c = matids::copyDefinition(L, 2, 12);
    ASSERT_TRUE(c.find("*MAT_ELASTIC_TITLE\nSTEEL\n") == 0);
    ASSERT_TRUE(c.find("        12   7.85E-9    210000       0.3\n") != std::string::npos);
    ASSERT_TRUE(c.find("*MAT_T01") == std::string::npos);
    ASSERT_TRUE(matids::copyDefinition(L, 7, 8).empty());
}

TEST(MaterialIds_지울_줄_표시는_묶음이_다_들면_블록째) {
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 + "\n" + kMatEl3 + "\n*END\n");
    const auto one = matids::definitionMask(L, {2});
    ASSERT_TRUE(one[2]);
    ASSERT_FALSE(one[1]);    // 키워드 줄은 남는다(MID 3 이 남는다)
    ASSERT_FALSE(one[3]);
    const auto both = matids::definitionMask(L, {2, 3});
    ASSERT_TRUE(both[1] && both[2] && both[3]);
    ASSERT_FALSE(both[4]);   // *END
}

// 번호 칸은 정수 칸이 받는 꼴로 읽는다 — 부호 · 앞의 0 · 칸 폭을 다 채운 10 자리 · 묶음의 Card 1 이면 실수 꼴 정수(적대적 검토 11-08 S8)
TEST(MaterialIds_번호_칸은_정수_칸이_받는_꼴로_읽는다) {
    int v = 0;
    ASSERT_TRUE(deckscan::digitsField("        +6         1", 10, v));
    ASSERT_EQ(v, 6);
    ASSERT_TRUE(deckscan::digitsField("0000000006         1", 10, v));
    ASSERT_EQ(v, 6);
    ASSERT_TRUE(deckscan::digitsField("1000000006         1", 10, v));
    ASSERT_EQ(v, 1000000006);
    ASSERT_TRUE(deckscan::digitsField("00000000000000000007", 20, v));   // long 20 칸
    ASSERT_EQ(v, 7);
    ASSERT_FALSE(deckscan::digitsField("       6.0         1", 10, v));   // 넉넉한 셈은 실수 꼴을 세지 않는다(두께와 못 가른다)
    ASSERT_FALSE(deckscan::digitsField("        -6", 10, v));
    ASSERT_FALSE(deckscan::digitsField("12 mm plate", 10, v));
    ASSERT_FALSE(deckscan::digitsField("2147483648", 10, v));            // int 밖
    auto L = matDeckLines(std::string("*KEYWORD\n*MAT_ELASTIC\n") + kMatEl2 + "\n       3.0   7.85E-9    210000       0.3\n*END\n");
    ASSERT_TRUE(matids::defined(L).count(3) == 1);                        // 묶음의 Card 1 은 실수 꼴 정수도 MID 다(리더처럼)
    const std::string c = matids::copyDefinition(L, 3, 12);
    ASSERT_TRUE(c.find("        12   7.85E-9    210000       0.3\n") != std::string::npos);   // 그 칸을 칸 폭 그대로 바꾼다
}
