// contact 카드 정본 — 자유 형식 칸 · 값을 지키는 실수 표기 · 형마다 필수 카드 수 · 카드 자리 파서 · 쓰기 순서
//
// 왜 이 파일이 있나 (2026-10-23).
//
//   contact op 과 그 카드를 고치는 op(optimize · stabilize)이 카드를 저마다 세고 형식 그대로 써서, 덱을 조용히 틀리게 썼다
//   — 빈 줄 · `_MPP` · TIEBREAK Card 4 · THRM 을 몰라 다른 카드를 고치고, `%10.2f` 로 값을 반올림하고, Card C 를 한 칸
//   밀어 썼다. 고친 정본(kw_util · contact_helpers)이 매뉴얼(Vol_I R16 *CONTACT 카드 순서)과 같은지 여기서 본다.
//   덱 → 바이너리 거동은 회귀 `test_contact_cards.py` 가 잰다.
#include "TestFramework.h"

#include "commands/contact_helpers.h"
#include "commands/kw_util.h"

#include <cstdlib>
#include <string>
#include <vector>

namespace {

std::vector<std::string> deckLines(const std::string& body) {
    std::vector<std::string> out;
    size_t a = 0;
    while (a <= body.size()) {
        size_t b = body.find('\n', a);
        if (b == std::string::npos) { if (a < body.size()) out.push_back(body.substr(a)); break; }
        out.push_back(body.substr(a, b - a));
        a = b + 1;
    }
    return out;
}

const char* C123 =
    "         1         3         3         3\n"
    "       0.2       0.1\n"
    "       1.0       1.0\n";

}  // namespace

TEST(ContactCards_쉼표가_있으면_자유_형식) {
    auto t = kw_tok10("1,3,3,3");
    ASSERT_EQ(t.size(), (size_t)4);
    ASSERT_EQ(t[1], std::string("3"));
    auto f = kw_tok10("         1         3");   // 쉼표가 없으면 10칸
    ASSERT_EQ(f.size(), (size_t)2);
    ASSERT_EQ(f[1], std::string("3"));
}

TEST(ContactCards_쉼표_줄의_칸을_고치면_고정폭으로) {
    const std::string r = kw_setField("0.3,0.2", 0, 10, "0.5");
    ASSERT_EQ(r, std::string("       0.5       0.2"));
}

TEST(ContactCards_실수_표기는_값을_바꾸지_않는다) {
    ASSERT_EQ(kw_realKeep(0.2, "%10.2f"), std::string("      0.20"));   // 예전 글자 그대로(골든)
    ASSERT_EQ(std::strtod(kw_realKeep(0.125, "%10.2f").c_str(), nullptr), 0.125);   // 예전엔 0.13
    ASSERT_EQ(std::strtod(kw_realKeep(0.0005, "%10.2f").c_str(), nullptr), 0.0005); // 예전엔 0.00
    ASSERT_EQ(std::strtod(kw_realKeep(123.456, "%10.3g").c_str(), nullptr), 123.456); // 예전엔 123
    ASSERT_EQ(kw_realKeep(1.0e20, "%10.3E"), std::string(" 1.000E+20"));
    ASSERT_EQ(kw_real(1.0).size(), (size_t)10);
}

TEST(ContactCards_형마다_필수_카드) {
    auto tb = ct_cardSpec("AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK");
    ASSERT_TRUE(tb.known);
    ASSERT_TRUE(tb.tiebreakAuto);
    ASSERT_EQ(tb.card4, 1);
    auto er = ct_cardSpec("ERODING_SURFACE_TO_SURFACE");
    ASSERT_TRUE(er.eroding);
    ASSERT_EQ(er.card4, 1);
    ASSERT_EQ(ct_cardSpec("TIED_SURFACE_TO_SURFACE_THERMAL").thrm, 1);
    ASSERT_FALSE(ct_cardSpec("TIED_SURFACE_TO_SURFACE_THERMAL_FRICTION").known);
    ASSERT_FALSE(ct_cardSpec("AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK_USER").known);
    ASSERT_FALSE(ct_cardSpec("TIEBREAK_SURFACE_TO_SURFACE").known);   // AUTOMATIC 과 Card 4 꼴이 다르다
    ASSERT_FALSE(ct_cardSpec("DRAWBEAD").known);
    auto plain = ct_cardSpec("AUTOMATIC_SURFACE_TO_SURFACE");
    ASSERT_TRUE(plain.known);
    ASSERT_EQ(plain.card4 + plain.thrm + plain.orfr, 0);
}

TEST(ContactCards_MPP_카드는_Card_1_앞) {
    const auto lines = deckLines(std::string("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n") +
                                 "         0       200\n&         0\n" + C123 + "*END\n");
    const auto cs = ct_parseContacts(lines);
    ASSERT_EQ(cs.size(), (size_t)1);
    ASSERT_TRUE(cs[0].hasMpp);
    ASSERT_EQ(cs[0].mppLines.size(), (size_t)2);
    ASSERT_EQ(cs[0].ssid, 1);
    ASSERT_EQ(cs[0].msid, 3);
    ASSERT_EQ(cs[0].type, std::string("AUTOMATIC_SURFACE_TO_SURFACE"));
}

TEST(ContactCards_빈_줄은_카드) {
    const auto lines = deckLines(std::string("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n") + C123 +
                                 "         1\n\n         1         2\n*END\n");
    const auto cs = ct_parseContacts(lines);
    ASSERT_EQ(cs[0].optLines.size(), (size_t)3);
    ASSERT_TRUE(cs[0].hasCardC);
    ASSERT_EQ(cs[0].ignore_, 2);     // 빈 Card B 뒤의 Card C — 예전엔 Card B 로 읽었다
}

TEST(ContactCards_TIEBREAK_Card_4_는_선택_카드가_아니다) {
    const auto lines = deckLines(std::string("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK\n") + C123 +
                                 "         2      10.0      50.0\n         1\n*END\n");
    const auto cs = ct_parseContacts(lines);
    ASSERT_TRUE(cs[0].hasTiebreak);
    ASSERT_EQ(cs[0].tbOption, 2);
    ASSERT_EQ(cs[0].card4Lines.size(), (size_t)1);
    ASSERT_EQ(cs[0].optLines.size(), (size_t)1);
    ASSERT_EQ(cs[0].soft, 1);        // Card A 는 Card 4 다음 줄
}

TEST(ContactCards_TIEBREAK_OPTION_13_은_카드가_둘_더) {
    const auto lines = deckLines(std::string("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK\n") + C123 +
                                 "        13\n       1.0\n       2.0\n         1\n*END\n");
    const auto cs = ct_parseContacts(lines);
    ASSERT_EQ(cs[0].card4Lines.size(), (size_t)3);   // Card 4 · 4.1b · 4.2b
    ASSERT_EQ(cs[0].optLines.size(), (size_t)1);
}

TEST(ContactCards_자리를_모르는_형은_선택_카드를_읽지_않는다) {
    const auto lines = deckLines(std::string("*CONTACT_DRAWBEAD\n") + C123 + "         1\n*END\n");
    auto cs = ct_parseContacts(lines);
    ASSERT_FALSE(cs[0].layoutKnown);
    ASSERT_TRUE(cs[0].optLines.empty());
    std::vector<std::string> ls = lines;
    ContactDef merged = cs[0];
    merged.hasCardA = true;
    std::string why;
    ASSERT_FALSE(ct_modifyOptionalCards(ls, cs[0], merged, &why));   // 손대지 않는다
    ASSERT_EQ(ls, lines);
}

TEST(ContactCards_Card_C_는_FLANGL_7열_CID_RCF_8열) {
    const auto lines = deckLines(std::string("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n") + C123 + "\n\n"
                                 "         1         0       0.0       0.0       0.0                 0.5         9\n*END\n");
    const auto cs = ct_parseContacts(lines);
    ASSERT_EQ(cs[0].flangl, 0.5);
    ASSERT_EQ(cs[0].cid_rcf, 9);
    ContactDef d;
    d.type = "AUTOMATIC_SURFACE_TO_SURFACE";
    d.hasCardA = d.hasCardB = d.hasCardC = true;
    d.flangl = 0.5;
    d.cid_rcf = 9;
    const std::string out = ct_generateContact(d);
    // 6열 공란 · 7열 FLANGL(예전 형식 `%10.4f` 그대로 — 값이 같으니 글자도 같다) · 8열 CID_RCF
    ASSERT_TRUE(out.find(std::string(10, ' ') + "    0.5000" + "         9") != std::string::npos);
}

TEST(ContactCards_쓰기는_Card_4_를_선택_카드_앞에) {
    ContactDef d;
    d.type = "AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK";
    d.hasTiebreak = true;
    d.tbOption = 2;
    d.hasCardA = true;
    d.soft = 1;
    const std::string out = ct_generateContact(d);
    const size_t c4 = out.find("$#  option");
    const size_t ca = out.find("$#    soft");
    ASSERT_TRUE(c4 != std::string::npos && ca != std::string::npos);
    ASSERT_TRUE(c4 < ca);
}

TEST(ContactCards_tied_mortar_는_있는_키워드) {
    ASSERT_EQ(ct_getPreset("tied_mortar").keyword, std::string("AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED"));
}
