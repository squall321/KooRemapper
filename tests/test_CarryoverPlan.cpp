// StepForge 이월 계획 리더 — 칸 표(모르는 칸 · 빠진 칸) · 변위장 이진(리틀엔디언 · 꼴 바이트) · 조각 값 대조 · 넣을 블록 · 보고 JSON 을 못 박는다
//
// 왜 이 파일이 있나 (2026-11-07).
//
//   답신(`docs/requests/stepforge-carryover-reply-2026-11-07.md`)이 「계획 v1 의 칸을 그대로 받는다 · 모르는 칸 · 빠진 칸은
//   거절한다」고 약속했다. 그 약속을 지키는 것은 리더다 — 덱 없이 순수하게 시험한다(덱과의 대조는 회귀 시험
//   `tools/regress/test_apply_carryover_plan.py` 가 실물 진리값 판으로 본다).
#include "TestFramework.h"
#include "parser/CarryoverPlan.h"
#include "util/StrictJson.h"

#include <cstring>
#include <string>
#include <vector>

using namespace KooRemapper;

namespace {

bool coAnyProblem(const std::vector<carryover::Problem>& v, const std::string& kind, const std::string& needle) {
    for (const auto& p : v)
        if (p.kind == kind && p.detail.find(needle) != std::string::npos) return true;
    return false;
}

bool coAnyText(const std::vector<std::string>& v, const std::string& needle) {
    for (const auto& s : v)
        if (s.find(needle) != std::string::npos) return true;
    return false;
}

const char* kCoSha = "0713a659789236408247e4a1e1f27a87a60e9e9fd8dbb135f3226cca563f1f03";

// 진리값 판(StepForge fixtures/carryover)의 꼴을 줄인 계획 — 줄 넷(keep · transform · remesh · delete)과 새 파트 하나
std::string coPlanJson(const std::string& extraTop = "", const std::string& transformExtra = "", int version = 1) {
    return std::string("{\"format\": \"stepforge-carryover-plan\", \"version\": ") + std::to_string(version) +
           ", \"unit\": \"mm-t-s\", \"frame\": \"world\", " + extraTop +
           "\"deck\": {\"project_id\": \"p\", \"relpath\": \"deck.k\", \"sha256\": \"" + kCoSha +
           "\", \"max\": {\"node\": 12, \"elem\": 2, \"pid\": 2, \"secid\": 2, \"mid\": 2}, \"unread_cards\": []},"
           " \"report_key\": \"k\", \"cad\": {}, \"floor_mm\": 0.0003, \"summary\": {},"
           " \"parts\": ["
           "{\"pid\": 1, \"name\": \"A\", \"action\": \"keep\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [], \"touches_changed\": [2]},"
           "{\"pid\": 2, \"name\": \"B\", \"action\": \"transform\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [\"/x\"],"
           " \"transform\": [1,0,0,2, 0,1,0,0, 0,0,1,0, 0,0,0,1], \"translation\": [2,0,0], \"rotation_deg\": 0.0, \"check\": {}" +
           transformExtra + "},"
           "{\"pid\": 3, \"name\": \"C\", \"action\": \"remesh\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [],"
           " \"fragment\": {\"ok\": true, \"file\": \"fragment_3.k\", \"pid\": 3, \"secid\": 9, \"mid\": 3,"
           " \"new_section\": {\"secid\": 9, \"elform\": 10, \"why\": \"tet\"}, \"ranges\": {\"node\": [13, 20], \"elem\": [3, 4]},"
           " \"nodes\": 8, \"elements\": 2, \"bytes\": 100, \"mesh\": {}, \"target\": {}, \"check\": {}}},"
           "{\"pid\": 4, \"name\": \"D\", \"action\": \"delete\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": []}],"
           " \"added\": [{\"path\": \"/n\", \"name\": \"N\", \"action\": \"add\", \"suggestion\": {}, \"fragment\": null, \"why\": \"screw\"}],"
           " \"files\": {\"fragment_3.k\": {\"sha256\": \"" + kCoSha + "\", \"bytes\": 100}}, \"code_build\": \"abc\"}";
}

void coPutU32(std::string& b, size_t off, uint32_t v) {
    for (int k = 0; k < 4; ++k) b[off + static_cast<size_t>(k)] = static_cast<char>((v >> (8 * k)) & 0xFF);
}
void coPutF64(std::string& b, size_t off, double d) {
    uint64_t u = 0;
    std::memcpy(&u, &d, sizeof u);
    for (int k = 0; k < 8; ++k) b[off + static_cast<size_t>(k)] = static_cast<char>((u >> (8 * k)) & 0xFF);
}

// 절점 둘의 변위장 — node(0) · disp(8) · kind(56) · 크기 58
carryover::FieldHead coTwoNodeHead() {
    carryover::FieldHead h;
    h.present = h.built = true;
    h.file = "field_2.bin";
    h.nodes = 2;
    h.bytes = 58;
    h.node.offset = 0;
    h.disp.offset = 8;
    h.kind.offset = 56;
    return h;
}
std::string coTwoNodeField(uint32_t n0, uint32_t n1, uint8_t k0 = 1, uint8_t k1 = 3) {
    std::string b(58, '\0');
    coPutU32(b, 0, n0);
    coPutU32(b, 4, n1);
    const double d[6] = {0.0, -0.2, 0.0, 0.0, 0.2, 1e-13};
    for (int i = 0; i < 6; ++i) coPutF64(b, 8 + 8 * static_cast<size_t>(i), d[i]);
    b[56] = static_cast<char>(k0);
    b[57] = static_cast<char>(k1);
    return b;
}

// 사면체 둘(n5..n8 = n4) · 절점 다섯 · 새 섹션 카드 — StepForge 조각 꼴
const char* kCoFragment =
    "*KEYWORD\n"
    "$# StepForge — 이월 조각 PID 3\n"
    "*NODE\n"
    "$#   nid               x               y               z\n"
    "      13 0.000000000e+00 0.000000000e+00 0.000000000e+00\n"
    "      14 1.000000000e+00 0.000000000e+00 0.000000000e+00\n"
    "      15 0.000000000e+00 1.000000000e+00 0.000000000e+00\n"
    "      16 0.000000000e+00 0.000000000e+00 1.000000000e+00\n"
    "      17 1.000000000e+00 1.000000000e+00 1.000000000e+00\n"
    "*ELEMENT_SOLID\n"
    "       3       3      13      14      15      16      16      16      16      16\n"
    "       4       3      14      15      16      17      17      17      17      17\n"
    "*PART\n"
    "$# C\n"
    "C\n"
    "         3         9         3\n"
    "*SECTION_SOLID_TITLE\n"
    "C_sec\n"
    "         9        10\n"
    "*END\n";

std::vector<std::string> coLines(const std::string& text) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : text) {
        if (c == '\n') { out.push_back(cur); cur.clear(); }
        else cur += c;
    }
    if (!cur.empty()) out.push_back(cur);
    return out;
}

carryover::FragmentHead coFragHead() {
    carryover::FragmentHead h;
    h.present = h.ok = true;
    h.file = "fragment_3.k";
    h.pid = 3;
    h.secid = 9;
    h.mid = 3;
    h.newSection.present = true;
    h.newSection.secid = 9;
    h.newSection.elform = 10;
    h.nodeLo = 13;
    h.nodeHi = 17;
    h.elemLo = 3;
    h.elemHi = 4;
    h.nodes = 5;
    h.elements = 2;
    return h;
}

}  // namespace

TEST(Carryover_계획_v1_꼴을_받는다) {
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;
    ASSERT_TRUE(carryover::parsePlan(coPlanJson(), plan, pr));
    ASSERT_EQ(pr.size(), static_cast<size_t>(0));
    ASSERT_EQ(plan.version, 1LL);
    ASSERT_EQ(plan.deckSha256, std::string(kCoSha));
    ASSERT_EQ(plan.parts.size(), static_cast<size_t>(4));
    ASSERT_TRUE(plan.parts[0].valid && plan.parts[0].action == carryover::Action::Keep);
    ASSERT_EQ(plan.parts[0].touchesChanged.size(), static_cast<size_t>(1));
    ASSERT_TRUE(plan.parts[1].action == carryover::Action::Transform);
    ASSERT_NEAR(plan.parts[1].m[3], 2.0, 0.0);
    ASSERT_NEAR(plan.parts[1].m[15], 1.0, 0.0);
    ASSERT_TRUE(plan.parts[2].fragment.ok && plan.parts[2].fragment.newSection.present);
    ASSERT_EQ(plan.parts[2].fragment.newSection.elform, 10LL);
    ASSERT_EQ(plan.parts[2].fragment.nodeLo, 13LL);
    ASSERT_EQ(plan.parts[2].fragment.elemHi, 4LL);
    ASSERT_TRUE(plan.parts[3].action == carryover::Action::Delete);
    ASSERT_EQ(plan.added.size(), static_cast<size_t>(1));
    ASSERT_FALSE(plan.added[0].fragment.present);   // null — 조각 없이 까닭만
    ASSERT_EQ(plan.files.size(), static_cast<size_t>(1));
    ASSERT_EQ(plan.codeBuild, std::string("abc"));
}

TEST(Carryover_모르는_칸_빠진_칸_판을_모두_말한다) {
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;
    // 맨 위 모르는 칸 + transform 줄의 모르는 칸 + 판 2 — 한 번에 셋 다 나와야 한다(전부 아니면 전무)
    ASSERT_FALSE(carryover::parsePlan(coPlanJson("\"extra\": 1, ", ", \"scale\": 1.0", 2), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'extra'"));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'scale'"));
    ASSERT_TRUE(coAnyProblem(pr, "plan_format", "판 1 만"));
    ASSERT_FALSE(plan.parts[1].valid);   // 칸이 틀린 줄은 덱과 대조하지 않는다
    ASSERT_TRUE(plan.parts[0].valid);    // 다른 줄은 그대로 읽는다

    std::string missing = coPlanJson();
    missing.replace(missing.find("\"report_key\": \"k\", "), std::strlen("\"report_key\": \"k\", "), "");
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(missing, plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'report_key' 가 없다"));

    std::string dup = coPlanJson();
    dup.replace(dup.find("{\"pid\": 4,"), std::strlen("{\"pid\": 4,"), "{\"pid\": 1,");
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(dup, plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_rows", "두 번"));

    pr.clear();
    ASSERT_FALSE(carryover::parsePlan("{\"format\": ", plan, pr));
    ASSERT_EQ(pr.size(), static_cast<size_t>(1));
    ASSERT_EQ(pr[0].kind, std::string("plan_json"));
}

TEST(Carryover_변위장_리틀엔디언_꼴_바이트) {
    const auto h = coTwoNodeHead();
    carryover::Field f;
    std::string err;
    ASSERT_TRUE(carryover::readField(coTwoNodeField(5, 9), h, f, err));
    ASSERT_EQ(f.node.size(), static_cast<size_t>(2));
    ASSERT_EQ(f.node[1], 9u);
    ASSERT_NEAR(f.disp[1], -0.2, 0.0);
    ASSERT_NEAR(f.disp[5], 1e-13, 0.0);
    ASSERT_EQ(static_cast<int>(f.kind[1]), 3);
    // 오름차순이 아니다 · 꼴 바이트의 모르는 비트 · 크기가 머리와 다르다
    ASSERT_FALSE(carryover::readField(coTwoNodeField(9, 5), h, f, err));
    ASSERT_TRUE(err.find("오름차순") != std::string::npos);
    ASSERT_FALSE(carryover::readField(coTwoNodeField(5, 9, 1, 0x13), h, f, err));
    ASSERT_TRUE(err.find("꼴 바이트") != std::string::npos);
    ASSERT_TRUE(carryover::readField(coTwoNodeField(5, 9, 1, 8 | 2), h, f, err));   // 나눠 쓴 절점 비트(8)는 읽는다 — 거절은 적용 쪽
    ASSERT_FALSE(carryover::readField(coTwoNodeField(5, 9) + "x", h, f, err));
}

TEST(Carryover_조각_값_대조) {
    carryover::FragmentScan s;
    std::vector<std::string> pr;
    ASSERT_TRUE(carryover::scanFragment(coLines(kCoFragment), s, pr));
    ASSERT_EQ(s.nodes.size(), static_cast<size_t>(5));
    ASSERT_EQ(s.elems.size(), static_cast<size_t>(2));
    ASSERT_EQ(s.parts.size(), static_cast<size_t>(1));
    ASSERT_EQ(s.sections.size(), static_cast<size_t>(1));
    carryover::checkFragment(s, coFragHead(), 3, pr);
    ASSERT_EQ(pr.size(), static_cast<size_t>(0));
    // 구간 · 수가 머리와 다르다 · 새 섹션 ELFORM 이 다르다 · 줄의 PID 가 다르다
    auto h = coFragHead();
    h.nodeHi = 18;
    h.elements = 3;
    h.newSection.elform = 13;
    carryover::checkFragment(s, h, 7, pr);
    ASSERT_TRUE(coAnyText(pr, "ranges.node"));
    ASSERT_TRUE(coAnyText(pr, "elements 3"));
    ASSERT_TRUE(coAnyText(pr, "new_section.elform"));
    ASSERT_TRUE(coAnyText(pr, "줄의 PID 7"));
}

TEST(Carryover_조각_계약_밖은_거절) {
    std::string t = kCoFragment;
    // 안 쓰는 절점 · 계약 밖 키워드 · 셸 중간절점
    t.insert(t.find("*ELEMENT_SOLID"), "      18 5.000000000e+00 5.000000000e+00 5.000000000e+00\n");
    t.insert(t.find("*END"), "*SET_NODE_LIST\n         1\n        13\n*ELEMENT_SHELL\n       5       3      13      14      15      15      16\n");
    carryover::FragmentScan s;
    std::vector<std::string> pr;
    ASSERT_FALSE(carryover::scanFragment(coLines(t), s, pr));
    ASSERT_TRUE(coAnyText(pr, "계약 밖 키워드 *SET_NODE_LIST"));
    ASSERT_TRUE(coAnyText(pr, "셸 중간절점"));
    std::string u = kCoFragment;
    u.insert(u.find("*ELEMENT_SOLID"), "      18 5.000000000e+00 5.000000000e+00 5.000000000e+00\n");
    pr.clear();
    ASSERT_TRUE(carryover::scanFragment(coLines(u), s, pr));
    auto h = coFragHead();
    h.nodes = 6;
    h.nodeHi = 18;
    carryover::checkFragment(s, h, 3, pr);
    ASSERT_TRUE(coAnyText(pr, "쓰지 않는 절점 1 개(첫 절점 18)"));
    // *END 가 없는 조각(잘린 파일)
    std::string cut = kCoFragment;
    cut.erase(cut.find("*END"));
    pr.clear();
    ASSERT_FALSE(carryover::scanFragment(coLines(cut), s, pr));
    ASSERT_TRUE(coAnyText(pr, "*END 가 없다"));
}

TEST(Carryover_넣을_블록_번호만_옮긴다) {
    const auto L = coLines(kCoFragment);
    carryover::FragmentScan s;
    std::vector<std::string> pr;
    ASSERT_TRUE(carryover::scanFragment(L, s, pr));
    // 바꿔 넣기(withPart=false) · i10 덱 · 절점 +100 · 요소 +10
    const std::string b = carryover::renderFragment(L, s, 100, 10, 10, false);
    ASSERT_TRUE(b.find("*KEYWORD") == std::string::npos);
    ASSERT_TRUE(b.find("*END") == std::string::npos);
    ASSERT_TRUE(b.find("*PART") == std::string::npos);
    ASSERT_TRUE(b.find("\n       113 0.000000000e+00 0.000000000e+00 0.000000000e+00\n") != std::string::npos);
    ASSERT_TRUE(b.find("\n        13         3       113       114       115       116       116       116       116       116\n") !=
                std::string::npos);
    ASSERT_TRUE(b.find("*SECTION_SOLID_TITLE\nC_sec\n         9        10\n") != std::string::npos);
    // 새 파트(withPart=true) — *PART 블록이 그대로 간다(제목 앞 주석까지)
    const std::string a = carryover::renderFragment(L, s, 0, 0, 8, true);
    ASSERT_TRUE(a.find("*PART\n$# C\nC\n         3         9         3\n") != std::string::npos);
}

// StepForge 의 실제 꼴(리뷰 11-07 · `carryover_build.py`) — 못 지은 조각은 notes 를 싣고 why 가 null 이거나 없다 · transform 은 check 를
// 빼기도 한다. 그 꼴을 plan_schema 로 거절하면 저쪽의 까닭이 사라진다.
TEST(Carryover_StepForge_실제_꼴_못_지은_조각과_check_없는_transform) {
    const std::string base = coPlanJson();
    const std::string fragHead = "\"fragment\": {\"ok\": true";
    const size_t f0 = base.find(fragHead);
    const size_t f1 = base.find("\"check\": {}}", f0) + std::strlen("\"check\": {}}");
    auto withFragment = [&](const std::string& frag) { return base.substr(0, f0) + "\"fragment\": " + frag + base.substr(f1); };
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;

    std::string noCheck = base;
    noCheck.replace(noCheck.find("\"rotation_deg\": 0.0, \"check\": {}"), std::strlen("\"rotation_deg\": 0.0, \"check\": {}"), "\"rotation_deg\": 0.0");
    ASSERT_TRUE(carryover::parsePlan(noCheck, plan, pr));
    ASSERT_TRUE(plan.parts[1].valid && plan.parts[1].action == carryover::Action::Transform);

    pr.clear();
    ASSERT_TRUE(carryover::parsePlan(withFragment("{\"ok\": false, \"why\": null, \"notes\": {\"why\": \"형상을 못 찾았다\", \"defeatured\": []}}"), plan, pr));
    ASSERT_TRUE(plan.parts[2].valid && !plan.parts[2].fragment.ok);
    ASSERT_EQ(plan.parts[2].fragment.why, std::string("형상을 못 찾았다"));

    std::string built = base.substr(f0, f1 - f0);   // 지었으나 확인을 못 지났다 — 조각 칸 전부 + check.problems, why 없음
    built.replace(built.find("\"ok\": true"), std::strlen("\"ok\": true"), "\"ok\": false");
    built.replace(built.rfind("\"check\": {}"), std::strlen("\"check\": {}"), "\"check\": {\"ok\": false, \"problems\": [\"요소 수 2 가 3 와 다르다\"]}");
    pr.clear();
    ASSERT_TRUE(carryover::parsePlan(base.substr(0, f0) + built + base.substr(f1), plan, pr));
    ASSERT_EQ(plan.parts[2].fragment.why, std::string("요소 수 2 가 3 와 다르다"));

    pr.clear();
    ASSERT_TRUE(carryover::parsePlan(withFragment("{\"ok\": false}"), plan, pr));   // 까닭이 없다 — 부르는 쪽이 그렇게 말한다
    ASSERT_TRUE(plan.parts[2].fragment.why.empty());

    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(withFragment("{\"ok\": false, \"why\": 3}"), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "문자열 · null 이 아니다"));
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(withFragment("{\"ok\": false, \"why\": \"x\", \"extra\": 1}"), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'extra'"));   // 모르는 칸은 그대로 거절한다
}

// 셸 새 섹션의 T1 — StepForge 는 카드에 %10.5g 로 쓰고 계획에는 round(t, 9) 를 싣는다(리뷰 11-07). 상대 1e-4 안이면 같다.
TEST(Carryover_셸_새_섹션_T1_은_상대_만분의_일) {
    const char* frag =
        "*KEYWORD\n"
        "*NODE\n"
        "      13 0.000000000e+00 0.000000000e+00 0.000000000e+00\n"
        "      14 1.000000000e+00 0.000000000e+00 0.000000000e+00\n"
        "      15 1.000000000e+00 1.000000000e+00 0.000000000e+00\n"
        "      16 0.000000000e+00 1.000000000e+00 0.000000000e+00\n"
        "*ELEMENT_SHELL\n"
        "       3       3      13      14      15      16\n"
        "*PART\n"
        "C\n"
        "         3        10         3\n"
        "*SECTION_SHELL_TITLE\n"
        "C_sec\n"
        "        10         2         1         2\n"
        "   0.61235   0.61235   0.61235   0.61235\n"
        "*END\n";
    carryover::FragmentScan s;
    std::vector<std::string> pr;
    ASSERT_TRUE(carryover::scanFragment(coLines(frag), s, pr));
    carryover::FragmentHead h;
    h.present = h.ok = true;
    h.pid = 3;
    h.secid = 10;
    h.mid = 3;
    h.newSection.present = true;
    h.newSection.secid = 10;
    h.newSection.elform = 2;
    h.newSection.hasNip = true;
    h.newSection.nip = 2;
    h.newSection.hasT = true;
    h.newSection.t = 0.612345678;
    h.nodeLo = 13;
    h.nodeHi = 16;
    h.elemLo = h.elemHi = 3;
    h.nodes = 4;
    h.elements = 1;
    carryover::checkFragment(s, h, 3, pr);
    ASSERT_EQ(pr.size(), static_cast<size_t>(0));
    h.newSection.t = 0.6125;   // 상대 2.4e-4 — 다른 두께다
    carryover::checkFragment(s, h, 3, pr);
    ASSERT_TRUE(coAnyText(pr, "T1 0.61235"));
}

// 조각 줄의 제어 문자 — 주석 · 제목 줄은 글자 그대로 덱에 들어간다. 줄 가운데 CR 은 다른 리더에서 줄을 끊는다(리뷰 11-07)
TEST(Carryover_조각_제어_문자는_거절) {
    std::string t = kCoFragment;
    t.replace(t.find("$# StepForge"), std::strlen("$# StepForge"), "$# Step\rForge");
    carryover::FragmentScan s;
    std::vector<std::string> pr;
    ASSERT_FALSE(carryover::scanFragment(coLines(t), s, pr));
    ASSERT_TRUE(coAnyText(pr, "제어 문자"));
    std::string tab = kCoFragment;   // 주석의 탭은 받는다(절점 · 요소 줄의 탭은 따로 거절한다)
    tab.replace(tab.find("$# StepForge"), std::strlen("$# StepForge"), "$#\tStepForge");
    pr.clear();
    ASSERT_TRUE(carryover::scanFragment(coLines(tab), s, pr));
}

TEST(Carryover_보고_JSON_은_엄격한_리더로_읽힌다) {
    carryover::Report r;
    r.ok = false;
    r.planRead = true;
    r.planSha256 = kCoSha;
    r.planParsed = true;
    r.planVersion = 1;
    r.reportKey = "k\"q";
    r.deckShaIn = kCoSha;
    r.problems.push_back({4, "node_ref", "*SET_NODE_LIST(줄 9)"});
    r.problems.push_back({0, "deck_sha", "다르다"});
    carryover::PartResult p;
    p.pid = 4;
    p.action = "remesh";
    p.result = "refused";
    p.hasInserted = true;
    p.insNodeLo = 13;
    p.insNodeHi = 17;
    r.parts.push_back(p);
    r.touches.push_back({8, {3}});
    json::Value v;
    std::string err;
    ASSERT_TRUE(json::parse(carryover::toJson(r), v, err));
    ASSERT_EQ(v.get("format")->s, std::string("dynaforge-carryover-apply"));
    ASSERT_TRUE(v.get("ok")->type == json::Value::Type::Bool && !v.get("ok")->b);
    ASSERT_TRUE(v.get("deck")->get("sha256_out")->isNull());
    ASSERT_TRUE(v.get("shift")->isNull());
    ASSERT_EQ(v.get("problems")->arr.size(), static_cast<size_t>(2));
    ASSERT_TRUE(v.get("problems")->arr[1].get("pid") == nullptr);   // 줄과 무관한 것은 pid 칸이 없다
    ASSERT_EQ(v.get("plan")->get("report_key")->s, std::string("k\"q"));
    ASSERT_EQ(v.get("parts")->arr[0].get("inserted")->get("node")->arr[1].i, 17LL);
    ASSERT_EQ(v.get("touches_changed")->arr[0].get("with")->arr[0].i, 3LL);
}
