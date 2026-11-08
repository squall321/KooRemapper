// battery 덱 글자의 번호를 족마다 옮기는 bat::shiftBatteryIds 의 칸 자리 · 거절을 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-08).
//
//   assemble 의 battery 가 battery 덱 번호를 기존 모델과 겹치는 족만 옮긴다(어디에 놓나 — `placeBatteryIds` · 2026-11-08 G3).
//   옮기는 칸이 하나라도 어긋나면 덱이 그럴듯하게 틀린다 —
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

// ── 어디에 놓나(2026-11-08 · 6차 검토 G3) — 실제로 겹칠 때만 옮긴다 ─────────────────────────────────────────────────────────
TEST(BatteryIdShift_정의한_번호를_나온_차례로_모은다) {
    const std::string deck = "*KEYWORD\n*NODE\n       3        0.000000        0.000000        0.000000\n"
                             "       1        1.000000        0.000000        0.000000\n*END\n";
    std::string err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::scanBatteryIds(deck, res, err));
    ASSERT_EQ(res.ids[bat::FAM_NODE].size(), 2u);
    ASSERT_EQ(res.ids[bat::FAM_NODE][0], 3LL);
    ASSERT_EQ(res.ids[bat::FAM_NODE][1], 1LL);
}

TEST(BatteryIdShift_spansOf_는_붙은_번호를_한_구간으로_모은다) {
    const bat::IdSpans s = bat::spansOf({5, 1, 2, 3, 3, 9}, {{10, 12}, {20, 19}});
    ASSERT_EQ(s.size(), 3u);   // [1,3] [5,5] [9,12] — 거꾸로 된 구간(20~19)은 버린다
    ASSERT_EQ(s[0].first, 1LL);
    ASSERT_EQ(s[0].second, 3LL);
    ASSERT_EQ(s[1].first, 5LL);
    ASSERT_EQ(s[2].first, 9LL);
    ASSERT_EQ(s[2].second, 12LL);
}

TEST(BatteryIdShift_겹치지_않으면_옮기지_않고_겹치면_최대값_위로) {
    long long by = -1;
    std::string why;
    // 절점 90000001~08 인 덱에 battery 절점 1~8282 — 겹치지 않는다(예전엔 늘 최대값만큼 옮겨 8칸 상한을 넘겼다)
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_NODE, {1, 2, 8282}, {{90000001, 90000008}}, 0, "node_id_offset", by, why));
    ASSERT_EQ(by, 0LL);
    // 상자 절점 1~198 — 겹친다 → 최대값(198) 위로
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_NODE, {1, 8282}, {{1, 198}}, 0, "node_id_offset", by, why));
    ASSERT_EQ(by, 198LL);
    // 띄엄띄엄한 번호(세트 1 · 2 · 504)가 기존 사이(3 · 100)에 끼어도 같은 번호가 없으면 그대로
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_SET, {1, 2, 504}, {{3, 3}, {100, 100}}, 0, "", by, why));
    ASSERT_EQ(by, 0LL);
}

TEST(BatteryIdShift_최대값_위가_상한을_넘으면_빈자리로_없으면_거절한다) {
    long long by = -1;
    std::string why;
    // 절점 1~198 + 99999990 — 최대값 위(99999990 + 8282)는 8칸을 넘으니 199~ 빈자리로(+198)
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_NODE, {1, 8282}, {{1, 198}, {99999990, 99999990}}, 0, "", by, why));
    ASSERT_EQ(by, 198LL);
    // 빈자리가 모자란다(1~198 · 300~99999999) — 거절 · 까닭을 말한다
    ASSERT_FALSE(bat::placeBatteryIds(bat::FAM_NODE, {1, 8282}, {{1, 198}, {300, 99999999}}, 0, "", by, why));
    ASSERT_TRUE(why.find("놓을 자리가 없다") != std::string::npos);
    // 10칸 족은 int 상한이다 — 같은 꼴이라도 최대값 위로 놓인다
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_SET, {1, 8282}, {{1, 198}, {300, 99999999}}, 0, "", by, why));
    ASSERT_EQ(by, 99999999LL);
}

TEST(BatteryIdShift_준_오프셋은_실제로_겹치거나_상한을_넘을_때만_거절한다) {
    long long by = -1;
    std::string why;
    // 기존 최대값(90000008) 아래로 걸쳐도 같은 번호가 없으면 받는다(예전엔 거절)
    ASSERT_TRUE(bat::placeBatteryIds(bat::FAM_NODE, {1, 8282}, {{90000001, 90000008}}, 5, "node_id_offset", by, why));
    ASSERT_EQ(by, 5LL);
    // 옮긴 번호(6~8287)가 상자 절점(1~198)과 겹친다
    ASSERT_FALSE(bat::placeBatteryIds(bat::FAM_NODE, {1, 8282}, {{1, 198}}, 5, "node_id_offset", by, why));
    ASSERT_TRUE(why.find("node_id_offset 5") != std::string::npos && why.find("겹친다") != std::string::npos);
    // 8칸 상한을 넘는다
    ASSERT_FALSE(bat::placeBatteryIds(bat::FAM_ELEM, {1, 8282}, {}, 99999990, "elem_id_offset", by, why));
    ASSERT_TRUE(why.find("상한") != std::string::npos);
}

// ── 접촉 선택 카드(2026-11-08 · 6차 검토 P2) — Card B 에 번호 칸이 없고 Card C 는 DPRFAC · CID_RCF 만 본다 ─────────────────────
TEST(BatteryIdShift_접촉_Card_B_의_21_30열은_SHLTHK_라_옮기지_않는다) {
    const std::string deck =
        "*KEYWORD\n*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n         2\n"
        "       102         0         2         0         0         0         0         0\n"
        "         0         0         0         0        20         0         0     1e+20\n"
        "     1.000     1.000    0.0100    0.0100     1.000     1.000     1.000     1.000\n"
        "         2    0.0040         0    1.3750     3.000         5         0         1\n"
        "    0.0000         0         1         0         0         0    0.0000    0.0000\n"
        "         1         1    0.0000    0.0000    0.0000              0.0000         0\n*END\n";
    std::string out, err;
    bat::ShiftResult res;
    // 곡선을 옮겨도 Card B 의 SHLTHK(1)는 그대로다 — 예전엔 그 칸을 LCBCKT 로 보아 1 → 9001 로 바꿨다
    ASSERT_TRUE(bat::shiftBatteryIds(deck, shiftOf(0, 0, 0, 0, 0, 100, 0, 9000), out, res, err));
    ASSERT_TRUE(out.find("    0.0000         0         1         0") != std::string::npos);
    ASSERT_TRUE(out.find("         1         1    0.0000") != std::string::npos);   // Card C 그대로
}

TEST(BatteryIdShift_접촉_Card_C_의_DPRFAC_번호_좌표계는_거절한다) {
    const std::string head =
        "*KEYWORD\n*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n         2\n"
        "       102         0         2         0         0         0         0         0\n"
        "         0         0         0         0        20         0         0     1e+20\n"
        "     1.000     1.000    0.0100    0.0100     1.000     1.000     1.000     1.000\n"
        "         2    0.0040         0    1.3750     3.000         5         0         1\n"
        "    0.0000         0         0         0         0         0    0.0000    0.0000\n";
    std::string out, err;
    bat::ShiftResult res;
    ASSERT_TRUE(bat::shiftBatteryIds(head + "         1         1    0.5000    0.0000    0.0000              0.0000         0\n*END\n",
                                     bat::IdShift{}, out, res, err));   // 0 < DPRFAC < 1 은 계수다
    ASSERT_FALSE(bat::shiftBatteryIds(head + "         1         1    2.0000    0.0000    0.0000              0.0000         0\n*END\n",
                                      bat::IdShift{}, out, res, err));   // ≥ 1 은 세트 번호
    ASSERT_TRUE(err.find("DPRFAC") != std::string::npos);
    ASSERT_FALSE(bat::shiftBatteryIds(head + "         1         1    0.0000    0.0000    0.0000              0.0000         5\n*END\n",
                                      bat::IdShift{}, out, res, err));   // CID_RCF — 좌표계는 옮기는 규칙을 모른다
    ASSERT_TRUE(err.find("CID_RCF") != std::string::npos);
}
