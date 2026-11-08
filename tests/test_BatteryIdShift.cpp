// battery 덱 글자의 번호를 족마다 옮기는 bat::shiftBatteryIds 의 칸 자리 · 거절을 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-08).
//
//   assemble 의 battery 가 battery 덱 번호를 기존 모델 위로 옮긴다. 옮기는 칸이 하나라도 어긋나면 덱이 그럴듯하게 틀린다 —
//   정의와 참조가 같이 옮겨지는지(요소의 절점 · 파트, 파트의 섹션 · 재질, 접촉의 STYP 별 족), 칸 폭이 그대로인지, 모르는 키워드 ·
//   붙은 칸 · 상한을 넘는 번호 · 뜻을 모르는 0 아닌 칸을 거절하는지를 여기서 직접 본다. 덱 전체는 회귀
//   (tools/regress/test_assemble_battery_ids.py)가 본다.
#include "TestFramework.h"

#include "battery/BatteryIdShift.h"

#include <string>

namespace {

bat::IdShift shiftOf(long long node, long long elem, long long part, long long sec, long long mat, long long set,
                     long long contact, long long curve) {
    bat::IdShift by{};
    by[bat::FAM_NODE] = node;
    by[bat::FAM_ELEM] = elem;
    by[bat::FAM_PART] = part;
    by[bat::FAM_SECTION] = sec;
    by[bat::FAM_MAT] = mat;
    by[bat::FAM_SET] = set;
    by[bat::FAM_CONTACT] = contact;
    by[bat::FAM_CURVE] = curve;
    return by;
}

}  // namespace

TEST(BatteryIdShift_절점_요소_파트_섹션_재질을_정의와_참조째_옮기고_칸_폭을_지킨다) {
    const std::string deck =
        "$ head\n*KEYWORD\n"
        "*NODE\n       1        0.000000        0.000000        0.000000\n"
        "*ELEMENT_SHELL\n       7      10       1       2       3       4\n"
        "*PART\nTitle\n        10         1         2         0         0         0         0         0\n"
        "*SECTION_SHELL\n         1         2    0.8333         5         1         0         0         1\n"
        "     0.012     0.012     0.012     0.012\n"
        "*MAT_ELASTIC_TITLE\nM\n         22.5000E-09     800.0    0.3000\n"
        "*END\n";
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::shiftBatteryIds(deck, shiftOf(100, 200, 5, 3, 4, 0, 0, 0), out, res, err));
    ASSERT_TRUE(out.find("     101        0.000000") != std::string::npos);
    ASSERT_TRUE(out.find("     207      15     101     102     103     104") != std::string::npos);
    ASSERT_TRUE(out.find("        15         4         6") != std::string::npos);
    ASSERT_TRUE(out.find("         4         2    0.8333") != std::string::npos);
    ASSERT_TRUE(out.find("         62.5000E-09") != std::string::npos);   // 붙은 MID · RO 칸 — MID 만 바뀐다
    ASSERT_EQ(res.defined[bat::FAM_NODE].lo, 1LL);
    ASSERT_EQ(res.defined[bat::FAM_ELEM].hi, 7LL);
    ASSERT_EQ(res.defined[bat::FAM_PART].lo, 10LL);
    ASSERT_EQ(out.size(), deck.size());   // 칸 폭 그대로 — 글자 수가 같다
}

TEST(BatteryIdShift_옮기지_않으면_글자_그대로이고_범위만_잰다) {
    const std::string deck = "*KEYWORD\n*NODE\n       3        0.000000        0.000000        0.000000\n"
                             "*NODE\n       9        1.000000        0.000000        0.000000\n*END\n";
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::shiftBatteryIds(deck, bat::IdShift{}, out, res, err));
    ASSERT_EQ(out, deck);
    ASSERT_EQ(res.defined[bat::FAM_NODE].lo, 3LL);
    ASSERT_EQ(res.defined[bat::FAM_NODE].hi, 9LL);
}

TEST(BatteryIdShift_접촉의_SSID_MSID_는_STYP_로_족을_정한다) {
    const std::string deck =
        "*KEYWORD\n*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n         1  Title\n"
        "       100       102         3         2         0         0         0         0\n"
        "         0         0         0         0        20         0         0     1e+20\n"
        "     1.000     1.000    0.0500    0.0500     1.000     1.000     1.000     1.000\n"
        "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n         2\n"
        "       102         0         2         5         0         0         0         0\n"
        "         0         0         0         0        20         0         0     1e+20\n"
        "     1.000     1.000    0.0100    0.0100     1.000     1.000     1.000     1.000\n*END\n";
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::shiftBatteryIds(deck, shiftOf(0, 0, 1000, 0, 0, 500, 7, 0), out, res, err));
    ASSERT_TRUE(out.find("         8  Title") != std::string::npos);                     // CID + 7 · 제목 그대로
    ASSERT_TRUE(out.find("      1100       602         3         2") != std::string::npos);   // 3 = 파트 · 2 = 세트
    ASSERT_TRUE(out.find("       602         0         2         5") != std::string::npos);   // MSID 0 은 그대로
}

TEST(BatteryIdShift_모르는_키워드_붙은_칸_상한_넘침_뜻_모를_칸은_거절한다) {
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_FALSE(bat::shiftBatteryIds("*KEYWORD\n*CONSTRAINED_NODAL_RIGID_BODY\n         1\n*END\n", bat::IdShift{}, out, res, err));
    ASSERT_TRUE(err.find("*CONSTRAINED_NODAL_RIGID_BODY") != std::string::npos);
    // 9자리 절점이 8칸 칸에 붙었다(탭 줄이 격자 밖을 읽은 덱 — 실측)
    ASSERT_FALSE(bat::shiftBatteryIds("*KEYWORD\n*ELEMENT_SHELL\n     249      21     283174421089     285     284\n*END\n",
                                      bat::IdShift{}, out, res, err));
    // 8칸 절점 번호의 상한(99999999)을 넘긴다
    ASSERT_FALSE(bat::shiftBatteryIds("*KEYWORD\n*NODE\n99999990        0.000000        0.000000        0.000000\n*END\n",
                                      shiftOf(100, 0, 0, 0, 0, 0, 0, 0), out, res, err));
    ASSERT_TRUE(err.find("상한") != std::string::npos);
    // 좌표계(CID)가 0 이 아닌 SPC — 옮기는 규칙을 모른다
    ASSERT_FALSE(bat::shiftBatteryIds("*KEYWORD\n*BOUNDARY_SPC_NODE\n         1         5         1         1         1\n*END\n",
                                      bat::IdShift{}, out, res, err));
}

TEST(BatteryIdShift_INCLUDE_DYNAIN_은_표시만_하고_글자는_그대로다) {
    const std::string deck = "*KEYWORD\n*INCLUDE_DYNAIN\np1.dynain\n*END\n";
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::shiftBatteryIds(deck, shiftOf(5, 5, 0, 0, 0, 0, 0, 0), out, res, err));
    ASSERT_TRUE(res.includesDynain);
    ASSERT_EQ(out, deck);
}
