// StepForge 이월 계획 리더 — 칸 표(모르는 칸 · 빠진 칸) · 변위장 이진(리틀엔디언 · 꼴 바이트) · 조각 값 대조 · 넣을 블록 · 보고 JSON 을 못 박는다
//
// 왜 이 파일이 있나 (2026-11-07).
//
//   답신(`docs/requests/stepforge-carryover-reply-2026-11-07.md`)이 「계획 v1 의 칸을 그대로 받는다 · 모르는 칸 · 빠진 칸은
//   거절한다」고 약속했다. 그 약속을 지키는 것은 리더다 — 덱 없이 순수하게 시험한다(덱과의 대조는 회귀 시험
//   `tools/regress/test_apply_carryover_plan.py` 가 실물 진리값 판으로 본다).
#include "TestFramework.h"
#include "parser/CarryoverPlan.h"
#include "parser/IncludeClosure.h"
#include "util/StrictJson.h"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
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
    // 판 1 계획 — 맨 위 모르는 칸 + transform 줄의 모르는 칸 — 한 번에 둘 다 나와야 한다(전부 아니면 전무)
    ASSERT_FALSE(carryover::parsePlan(coPlanJson("\"extra\": 1, ", ", \"scale\": 1.0", 1), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'extra'"));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'scale'"));
    ASSERT_FALSE(plan.parts[1].valid);   // 칸이 틀린 줄은 덱과 대조하지 않는다
    ASSERT_TRUE(plan.parts[0].valid);    // 다른 줄은 그대로 읽는다
    // 모르는 판(3) — 판을 말하고 칸도 그대로 본다(판 2 가 받아진 뒤로 판 1 · 2 만 받는다 · 2026-11-07)
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(coPlanJson("\"extra\": 1, ", "", 3), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_format", "판 1 · 2 만"));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "'extra'"));

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
    // 산출을 바꿔 넣었나 — 거절 · 실패면 false(output 자리의 앞 파일은 이번 산출이 아니다 · 11-07 밤)
    ASSERT_TRUE(v.get("output_written") && v.get("output_written")->type == json::Value::Type::Bool && !v.get("output_written")->b);
    ASSERT_TRUE(v.get("deck")->get("sha256_out")->isNull());
    ASSERT_TRUE(v.get("shift")->isNull());
    ASSERT_EQ(v.get("problems")->arr.size(), static_cast<size_t>(2));
    ASSERT_TRUE(v.get("problems")->arr[1].get("pid") == nullptr);   // 줄과 무관한 것은 pid 칸이 없다
    ASSERT_EQ(v.get("plan")->get("report_key")->s, std::string("k\"q"));
    ASSERT_EQ(v.get("parts")->arr[0].get("inserted")->get("node")->arr[1].i, 17LL);
    ASSERT_EQ(v.get("touches_changed")->arr[0].get("with")->arr[0].i, 3LL);
}

// ── 판 2(2026-11-07 — StepForge 요청서 §10 · 그쪽 main 60f8969) ─────────────────────────────────────────────
// 칸 표는 판마다 하나다 — 판 2 는 판 1 위에 줄마다 덱 자리 · deck.deck_from · deck.includes · field.new_section(늘 있다) ·
// element_thickness · review 줄의 refused_transform · summary(여섯 칸)를 더했다. summary 의 actions · sections · failed 는 줄과 대조한다.
namespace {

// 판 2 계획 — keep · transform · 셸 모프(새 섹션 SECID 10) · 강체가 아닌 옮김을 돌린 review(요소 없는 PID)
std::string coPlanV2() {
    const std::string sha = kCoSha;
    const std::string place = "\"deck\": {\"node\": [1, 8], \"node_count\": 8, \"elem\": [1, 1], \"elem_count\": 1, \"contiguous\": true, "
                              "\"secid\": 1, \"mid\": 1}";
    return std::string("{\"format\": \"stepforge-carryover-plan\", \"version\": 2, \"unit\": \"mm-t-s\", \"frame\": \"world\",") +
           " \"deck\": {\"project_id\": \"p\", \"relpath\": \"export/assembled.k\", \"deck_from\": \"mesh\", \"sha256\": \"" + sha +
           "\", \"includes\": [{\"relpath\": \"inc/a.k\", \"sha256\": \"" + sha + "\"}],"
           " \"max\": {\"node\": 12, \"elem\": 3, \"pid\": 4, \"secid\": 9, \"mid\": 4}, \"unread_cards\": []},"
           " \"report_key\": \"k\", \"cad\": {}, \"floor_mm\": 0.0003,"
           " \"summary\": {\"actions\": {\"keep\": 1, \"transform\": 1, \"morph\": 1, \"review\": 1}, \"added\": 0, \"fields\": 1,"
           " \"fragments\": 0, \"sections\": 1, \"failed\": 0},"
           " \"parts\": ["
           "{\"pid\": 1, \"name\": \"A\", \"action\": \"keep\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [], " + place +
           ", \"touches_changed\": [2]},"
           "{\"pid\": 2, \"name\": \"B\", \"action\": \"transform\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [], " + place +
           ", \"transform\": [1,0,0,2, 0,1,0,0, 0,0,1,0, 0,0,0,1], \"translation\": [2,0,0], \"rotation_deg\": 0.0},"
           "{\"pid\": 3, \"name\": \"C\", \"action\": \"morph\", \"why\": \"w\", \"mapping\": \"one_to_one\", \"members\": [], " + place +
           ", \"field\": {\"file\": \"field_3.bin\", \"nodes\": 2, \"bytes\": 58, \"layout\": ["
           "{\"name\": \"node\", \"dtype\": \"<u4\", \"offset\": 0, \"count\": 2},"
           "{\"name\": \"disp\", \"dtype\": \"<f8\", \"offset\": 8, \"shape\": [2, 3], \"unit\": \"mm\"},"
           "{\"name\": \"kind\", \"dtype\": \"<u1\", \"offset\": 56, \"count\": 2, \"shared_bit\": 8}],"
           " \"surface_nodes\": 2, \"kinds\": {}, \"max_disp\": 0.1, \"faces\": 2, \"face_pairs\": {}, \"dropped_directions\": 0,"
           " \"projection_fallbacks\": 0, \"solver\": {}, \"check\": {\"ok\": true}, \"thickness\": {\"old\": 0.4, \"new\": 0.6},"
           " \"new_section\": {\"secid\": 10, \"thickness\": 0.6, \"file\": \"section_3.k\", \"why\": \"0.4 → 0.6\"}}},"
           "{\"pid\": 4, \"name\": \"D\", \"action\": \"review\", \"why\": \"옮김 4×4 가 강체가 아니다\", \"mapping\": \"one_to_one\", \"members\": [],"
           " \"deck\": {\"node\": null, \"node_count\": 0, \"elem\": null, \"elem_count\": 0, \"contiguous\": null, \"secid\": null, \"mid\": null},"
           " \"refused_transform\": {\"transform\": [1.01,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1], \"det\": 1.01, \"scale\": 1.003322, "
           "\"orthogonality_error\": 0.0201}}],"
           " \"added\": [],"
           " \"files\": {\"field_3.bin\": {\"sha256\": \"" + sha + "\", \"bytes\": 58}, \"section_3.k\": {\"sha256\": \"" + sha +
           "\", \"bytes\": 300}}}";
}

std::string coReplace(std::string s, const std::string& from, const std::string& to) {
    const size_t at = s.find(from);
    if (at != std::string::npos) s.replace(at, from.size(), to);
    return s;
}

// 요청서 §10.5 의 `section_4.k` 전문(329 바이트) — 진리값 판 CAN(SECID 4 · 0.4)을 옮겨 SECID 10 · 0.6 으로 바꾼 카드
const char* kCoSection =
    "*KEYWORD\n"
    "$# StepForge — 이월 모프 PID 4 의 새 셸 섹션(옛 SECID 4) — deck.k\n"
    "*SECTION_SHELL_TITLE\n"
    "CAN#4_sec\n"
    "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n"
    "        10         2         1         2\n"
    "$#      t1        t2        t3        t4\n"
    "       0.6       0.6       0.6       0.6\n"
    "*END\n";

// 그 카드가 옮긴 덱의 옛 카드(키워드 줄부터 다음 키워드 앞까지)
const char* kCoDeckSection =
    "*SECTION_SHELL_TITLE\n"
    "CAN#4_sec\n"
    "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n"
    "         4         2         1         2\n"
    "$#      t1        t2        t3        t4\n"
    "       0.4       0.4       0.4       0.4\n";

}  // namespace

TEST(Carryover_계획_v2_꼴을_받는다) {
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;
    const bool ok = carryover::parsePlan(coPlanV2(), plan, pr);
    for (const auto& p : pr) std::printf("    %s — %s\n", p.kind.c_str(), p.detail.c_str());
    ASSERT_TRUE(ok);
    ASSERT_EQ(plan.version, 2LL);
    ASSERT_EQ(plan.deckFrom, std::string("mesh"));
    ASSERT_TRUE(plan.hasIncludes);
    ASSERT_EQ(plan.includes.size(), static_cast<size_t>(1));
    ASSERT_EQ(plan.includes[0].relpath, std::string("inc/a.k"));
    ASSERT_EQ(plan.maxSecid, 9LL);
    const auto& keep = plan.parts[0];
    ASSERT_TRUE(keep.valid && keep.deck.present && keep.deck.hasNode && keep.deck.nodeHi == 8 && keep.deck.contiguous == 1);
    ASSERT_TRUE(keep.deck.hasSecid && keep.deck.secid == 1);
    const auto& morph = plan.parts[2];
    ASSERT_TRUE(morph.valid && morph.field.built && morph.field.hasThickness);
    ASSERT_TRUE(morph.field.newSection.present && morph.field.newSection.built);
    ASSERT_EQ(morph.field.newSection.secid, 10LL);
    ASSERT_NEAR(morph.field.newSection.thickness, 0.6, 0.0);
    ASSERT_EQ(morph.field.newSection.file, std::string("section_3.k"));
    const auto& review = plan.parts[3];
    ASSERT_TRUE(review.valid && review.action == carryover::Action::Review && review.hasRefusedTransform);
    ASSERT_NEAR(review.refusedM[0], 1.01, 0.0);
    ASSERT_NEAR(review.refusedOrth, 0.0201, 0.0);
    ASSERT_TRUE(review.deck.present && !review.deck.hasNode && !review.deck.hasElem && review.deck.contiguous == -1 && !review.deck.hasSecid);
    // 못 지은 새 섹션(secid · file null) — 받아 두고(적용 쪽이 거절한다) built 가 아니다
    std::string failed = coReplace(coPlanV2(), "\"new_section\": {\"secid\": 10, \"thickness\": 0.6, \"file\": \"section_3.k\"",
                                   "\"element_thickness\": {\"elements\": 2, \"why\": \"요소마다 두께\"}, \"new_section\": {\"secid\": null, "
                                   "\"thickness\": 0.6, \"file\": null");
    failed = coReplace(failed, "\"sections\": 1, \"failed\": 0", "\"sections\": 0, \"failed\": 1");
    pr.clear();
    ASSERT_TRUE(carryover::parsePlan(failed, plan, pr));
    ASSERT_TRUE(plan.parts[2].field.newSection.present && !plan.parts[2].field.newSection.built);
    ASSERT_TRUE(plan.parts[2].field.hasElementThickness && plan.parts[2].field.elementThicknessCount == 2);
}

TEST(Carryover_칸_표는_판마다_다르다) {
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;
    // 판 1 계획에 판 2 칸 — 모르는 칸
    ASSERT_FALSE(carryover::parsePlan(coReplace(coPlanJson(), "\"relpath\": \"deck.k\",", "\"relpath\": \"deck.k\", \"deck_from\": \"raw\","), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "모르는 칸 'deck_from' — 계획 판 1"));
    // 판 2 칸 표 — 빠진 칸(줄의 deck · deck.includes · field.new_section) · 모르는 칸(덱 자리 안 · review 줄의 transform · 새 파트 줄의 deck)
    const std::string v2 = coPlanV2();
    struct Case { std::string from, to, needle; };
    const Case cases[] = {
        {"\"members\": [], \"deck\": {\"node\": [1, 8]", "\"members\": [], \"deckx\": {\"node\": [1, 8]", "칸 'deck' 가 없다"},
        {"\"includes\": [{\"relpath\": \"inc/a.k\", \"sha256\": \"" + std::string(kCoSha) + "\"}],", "", "칸 'includes' 가 없다"},
        {", \"new_section\": {\"secid\": 10, \"thickness\": 0.6, \"file\": \"section_3.k\", \"why\": \"0.4 → 0.6\"}", "",
         "칸 'new_section' 가 없다"},
        {"\"contiguous\": true, \"secid\": 1", "\"contiguous\": true, \"gap\": 0, \"secid\": 1", "모르는 칸 'gap'"},
        {"\"refused_transform\": {", "\"translation\": [0, 0, 0], \"refused_transform\": {", "모르는 칸 'translation'"},
        {"\"deck_from\": \"mesh\"", "\"deck_from\": \"job\"", "raw · mesh 만"},
        {"\"added\": []", "\"added\": [{\"path\": \"/n\", \"name\": \"N\", \"action\": \"add\", \"suggestion\": {}, \"fragment\": null, \"why\": \"x\","
                          " \"deck\": {}}]", "모르는 칸 'deck'"},
    };
    for (const auto& c : cases) {
        pr.clear();
        const bool ok = carryover::parsePlan(coReplace(v2, c.from, c.to), plan, pr);
        if (ok || !coAnyProblem(pr, "plan_schema", c.needle)) {
            std::printf("    기대한 거절이 없다: %s\n", c.needle.c_str());
            for (const auto& p : pr) std::printf("      %s — %s\n", p.kind.c_str(), p.detail.c_str());
        }
        ASSERT_FALSE(ok);
        ASSERT_TRUE(coAnyProblem(pr, "plan_schema", c.needle));
    }
    // 판 1 의 summary 는 꼴만 본다 — 판 2 의 여섯 칸이 없어도 받는다(판 1 그대로)
    pr.clear();
    ASSERT_TRUE(carryover::parsePlan(coPlanJson(), plan, pr));
}

TEST(Carryover_v2_summary_를_계획_줄과_대조한다) {
    carryover::Plan plan;
    std::vector<carryover::Problem> pr;
    // review 로 돌린 옮김은 review 로 센다(§10.2 「바뀐 뜻」 ②) — transform 2 로 적으면 다르다
    ASSERT_FALSE(carryover::parsePlan(coReplace(coPlanV2(), "\"transform\": 1, \"morph\": 1, \"review\": 1", "\"transform\": 2, \"morph\": 1"),
                                      plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_inconsistent", "summary.actions.transform"));
    ASSERT_TRUE(coAnyProblem(pr, "plan_inconsistent", "summary.actions.review"));
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(coReplace(coPlanV2(), "\"sections\": 1", "\"sections\": 0"), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_inconsistent", "summary.sections"));
    // 못 지은 새 섹션은 failed 에 든다 — 0 이면 다르다
    std::string failed = coReplace(coPlanV2(), "\"new_section\": {\"secid\": 10, \"thickness\": 0.6, \"file\": \"section_3.k\"",
                                   "\"new_section\": {\"secid\": null, \"thickness\": 0.6, \"file\": null");
    failed = coReplace(failed, "\"sections\": 1", "\"sections\": 0");
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(failed, plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_inconsistent", "summary.failed — 0"));
    // secid 만 null(file 은 이름) — 함께 있거나 함께 null 이다
    pr.clear();
    ASSERT_FALSE(carryover::parsePlan(coReplace(coPlanV2(), "\"secid\": 10, \"thickness\": 0.6", "\"secid\": null, \"thickness\": 0.6"), plan, pr));
    ASSERT_TRUE(coAnyProblem(pr, "plan_schema", "함께 있거나 함께 null"));
}

TEST(Carryover_v2_새_셸_섹션_파일_엄격_읽기와_옛_카드_대조) {
    carryover::SectionFileScan s;
    std::vector<std::string> pr;
    ASSERT_EQ(std::strlen(kCoSection), static_cast<size_t>(329));   // 요청서 §10.5 「329 바이트」
    ASSERT_TRUE(carryover::scanSectionFile(coLines(kCoSection), s, pr));
    ASSERT_EQ(s.secid, 10LL);
    ASSERT_EQ(s.elform, 2LL);
    ASSERT_NEAR(s.t[0], 0.6, 0.0);
    ASSERT_NEAR(s.t[3], 0.6, 0.0);
    ASSERT_EQ(s.block.size(), static_cast<size_t>(6));
    ASSERT_EQ(s.head.size(), static_cast<size_t>(1));
    carryover::compareSectionCards(coLines(kCoDeckSection), s, pr);
    ASSERT_EQ(pr.size(), static_cast<size_t>(0));
    // 옛 카드와 다른 칸(SHRF 1 → 0.8) · 다른 주석 — SECID · T1~T4 밖은 그대로여야 한다
    std::string other = coReplace(kCoSection, "        10         2         1         2", "        10         2       0.8         2");
    ASSERT_TRUE(carryover::scanSectionFile(coLines(other), s, pr));
    carryover::compareSectionCards(coLines(kCoDeckSection), s, pr);
    ASSERT_TRUE(coAnyText(pr, "블록 4째 줄(Card 1)의 SECID 밖 칸"));
    pr.clear();
    std::string note = coReplace(kCoSection, "$#      t1", "$#      T1");
    ASSERT_TRUE(carryover::scanSectionFile(coLines(note), s, pr));
    carryover::compareSectionCards(coLines(kCoDeckSection), s, pr);
    ASSERT_TRUE(coAnyText(pr, "블록 5째 줄이 덱의 옛 카드와 다르다"));
    // 꼴 밖 — 쌓인 둘째 카드 · 다른 키워드 · *END 없음 · 사용자 정의 셸
    const std::string stacked = coReplace(kCoSection, "*END", "         3         2\n       1.0       1.0       1.0       1.0\n*END");
    pr.clear();
    ASSERT_FALSE(carryover::scanSectionFile(coLines(stacked), s, pr));
    ASSERT_TRUE(coAnyText(pr, "카드 하나가 아니다"));
    pr.clear();
    ASSERT_FALSE(carryover::scanSectionFile(coLines(coReplace(kCoSection, "*END", "*MAT_ELASTIC\n         9       1.0\n*END")), s, pr));
    ASSERT_TRUE(coAnyText(pr, "섹션 카드 뒤의 키워드 *MAT_ELASTIC"));
    pr.clear();
    ASSERT_FALSE(carryover::scanSectionFile(coLines(coReplace(kCoSection, "*END\n", "")), s, pr));
    ASSERT_TRUE(coAnyText(pr, "*END 가 없다"));
    pr.clear();
    ASSERT_FALSE(carryover::scanSectionFile(coLines(coReplace(kCoSection, "        10         2", "        10       101")), s, pr));
    ASSERT_TRUE(coAnyText(pr, "사용자 정의 셸"));
    // ICOMP 1 — 각도 카드 ceil(NIP/8) 장까지가 카드 하나다
    const std::string comp = coReplace(coReplace(kCoSection, "        10         2         1         2",
                                                 "        10         2         1         3         0         0         1"),
                                       "*END", "       0.0      45.0      90.0\n*END");
    pr.clear();
    ASSERT_TRUE(carryover::scanSectionFile(coLines(comp), s, pr));
}

// 보고는 늘 바른 UTF-8(2026-11-07 적대적 검토 #4) — 계획 · 덱에서 온 깨진 바이트는 U+FFFD 로, 줄을 보일 때는 글자 경계에서 자른다
TEST(Carryover_보고의_글자는_바른_UTF8) {
    auto valid = [](const std::string& t) {
        for (size_t i = 0; i < t.size();) {
            const unsigned char c = static_cast<unsigned char>(t[i]);
            const size_t n = c < 0x80 ? 0 : (c & 0xE0) == 0xC0 ? 1 : (c & 0xF0) == 0xE0 ? 2 : (c & 0xF8) == 0xF0 ? 3 : 9;
            if (n == 9 || i + n >= t.size()) return false;
            for (size_t k = 1; k <= n; ++k)
                if ((static_cast<unsigned char>(t[i + k]) & 0xC0) != 0x80) return false;
            i += n + 1;
        }
        return true;
    };
    carryover::Report r;
    r.planRead = r.planParsed = true;
    r.planSha256 = kCoSha;
    r.reportKey = std::string("k\xff\xfe") + "\xED\xA0\x80" + "\xC0\xAF" + "끝";   // 깨진 바이트 · 서로게이트 · 넘친 꼴
    r.problems.push_back({0, "plan_schema", std::string("이름 '\xE7\x95' 잘린 꼴")});
    const std::string j = carryover::toJson(r);
    ASSERT_TRUE(valid(j));
    ASSERT_TRUE(j.find("\xEF\xBF\xBD") != std::string::npos);
    ASSERT_TRUE(j.find("끝") != std::string::npos);
    json::Value v;
    std::string err;
    ASSERT_TRUE(json::parse(j, v, err));
    // 줄을 보이는 자르기 — 60 바이트 자리가 한글 한가운데여도 반쪽을 남기지 않는다
    carryover::SectionFileScan s;
    std::vector<std::string> pr;
    std::string longTitle = "X";
    for (int k = 0; k < 30; ++k) longTitle += "가";
    std::string other = "Y";
    for (int k = 0; k < 30; ++k) other += "가";
    ASSERT_TRUE(carryover::scanSectionFile(coLines(coReplace(kCoSection, "CAN#4_sec", other)), s, pr));
    carryover::compareSectionCards(coLines(coReplace(kCoDeckSection, "CAN#4_sec", longTitle)), s, pr);
    ASSERT_EQ(pr.size(), static_cast<size_t>(1));
    ASSERT_TRUE(valid(pr[0]));
}

TEST(Carryover_보고의_수는_다시_읽으면_같은_값) {
    // %.15g 는 끝자리를 잃었다 — 계획이 낸 refused_transform 을 보고가 그대로 되돌려 주지 못했다(적대적 검토 11-07 #7)
    const double vals[] = {1.0000000000000002, 0.30000000000000004, 2.0 / 3.0, 0.1, 1e-300, 5e-324, 1.7976931348623157e308, -0.0,
                           123456789.12345679, 1.01, 0.6, 1.0, 0.0, -2.5e-17, 9007199254740993.0, 0.9999999999999999};
    carryover::Report r;
    r.planRead = r.planParsed = true;
    r.planSha256 = kCoSha;
    carryover::PartResult p;
    p.pid = 4;
    p.action = "review";
    p.hasRefusedTransform = true;
    size_t n = 0;
    for (double x : vals) p.refusedM[n++ % 16] = x;
    p.refusedDet = vals[0];
    p.refusedScale = vals[1];
    p.refusedOrth = vals[2];
    r.parts.push_back(p);
    carryover::PartResult m;
    m.pid = 3;
    m.action = "morph";
    m.result = "applied";
    m.hasMove = true;
    m.maxDisp = 0.30000000000000004;
    m.hasNewSection = m.newSectionShell = true;
    m.newSecid = 10;
    m.newThickness = 0.6;
    r.parts.push_back(m);
    const std::string j = carryover::toJson(r);
    json::Value v;
    std::string err;
    ASSERT_TRUE(json::parse(j, v, err));
    // 소수점 · 지수가 없는 글자(1 · 0 · 9007199254740992)는 엄격한 리더가 정수로 담는다
    auto numOf = [](const json::Value& x) { return x.type == json::Value::Type::Int ? static_cast<double>(x.i) : x.d; };
    const auto* rt = v.get("parts")->arr[0].get("refused_transform");
    for (size_t k = 0; k < 16; ++k) ASSERT_TRUE(numOf(rt->get("transform")->arr[k]) == p.refusedM[k]);
    ASSERT_TRUE(numOf(*rt->get("det")) == vals[0]);
    ASSERT_TRUE(numOf(*rt->get("scale")) == vals[1]);
    ASSERT_TRUE(numOf(*rt->get("orthogonality_error")) == vals[2]);
    ASSERT_TRUE(numOf(*v.get("parts")->arr[1].get("max_disp")) == 0.30000000000000004);
    // 짧게 맞는 값은 예전 글자 그대로(0.6 이 0.59999999999999998 로 길어지지 않는다)
    ASSERT_TRUE(j.find("\"thickness\": 0.6}") != std::string::npos);
    ASSERT_TRUE(j.find("1.0000000000000002") != std::string::npos);
}


TEST(Carryover_셸_섹션의_정수_칸_실수_꼴은_그_정수) {
    // StepForge 권고 D-681 — LS-DYNA 실행 기록이 NIP `3.000E+00` 을 3 으로 받는다 · 정수가 아닌 값은 그대로 거절
    auto rows = [](const std::string& card1, const std::vector<std::string>& more, std::string& why) {
        std::vector<std::string> b{"*SECTION_SHELL", card1, "       0.6       0.6       0.6       0.6"};
        b.insert(b.end(), more.begin(), more.end());
        size_t r1 = 0, r2 = 0;
        return carryover::shellSectionRows(b, r1, r2, why);
    };
    std::string why;
    ASSERT_TRUE(rows("        10         2         1 5.000e+00", {}, why));
    ASSERT_TRUE(rows("        10 1.600e+01         1         5", {}, why));                       // ELFORM 16
    ASSERT_TRUE(rows("        10         2         1 3.000E+00         0         0 1.000e+00", {"       0.0"}, why));   // ICOMP 1 · 각도 카드 하나
    ASSERT_FALSE(rows("        10         2         1 2.500e+00", {}, why));
    ASSERT_TRUE(why.find("NIP") != std::string::npos);
    ASSERT_FALSE(rows("        10         2         1         2         0         0       1.5", {}, why));
    ASSERT_TRUE(why.find("ICOMP") != std::string::npos);
}

TEST(Carryover_v2_보고에_deck_from_인클루드_refused_transform) {
    carryover::Report r;
    r.planRead = r.planParsed = true;
    r.planSha256 = kCoSha;
    r.planVersion = 2;
    r.deckFrom = "raw";
    r.includesChecked = true;
    r.includes.push_back({"inc/part8.k", kCoSha});
    carryover::PartResult p;
    p.pid = 4;
    p.action = "review";
    p.hasRefusedTransform = true;
    p.refusedM[0] = 1.01;
    p.refusedM[15] = 1.0;
    p.refusedDet = 1.01;
    r.parts.push_back(p);
    carryover::PartResult m;
    m.pid = 3;
    m.action = "morph";
    m.result = "applied";
    m.hasNewSection = m.newSectionShell = true;
    m.newSecid = 10;
    m.newThickness = 0.6;
    r.parts.push_back(m);
    json::Value v;
    std::string err;
    ASSERT_TRUE(json::parse(carryover::toJson(r), v, err));
    ASSERT_EQ(v.get("plan")->get("deck_from")->s, std::string("raw"));
    ASSERT_EQ(v.get("deck")->get("includes")->arr[0].get("relpath")->s, std::string("inc/part8.k"));
    ASSERT_NEAR(v.get("parts")->arr[0].get("refused_transform")->get("transform")->arr[0].d, 1.01, 0.0);
    ASSERT_NEAR(v.get("parts")->arr[1].get("new_section")->get("thickness")->d, 0.6, 0.0);
    carryover::Report v1;   // 판 1 — 대조하지 않은 닫힘은 null · deck_from 도 null
    ASSERT_TRUE(json::parse(carryover::toJson(v1), v, err));
    ASSERT_TRUE(v.get("deck")->get("includes")->isNull());
    ASSERT_TRUE(v.get("plan")->get("deck_from")->isNull());
}

namespace {

// 바이트를 그대로 쓴다(텍스트 모드 · 개행 바꿈 없이)
void coWriteBytes(const std::filesystem::path& p, const std::string& body) {
    std::ofstream f(p, std::ios::binary | std::ios::trunc);
    f << body;
}

// 덱을 담는 읽기(loadBaseModel)와 같은 줄 — std::getline · 줄 끝 CR 하나
std::vector<std::string> coGetlines(const std::string& body) {
    std::vector<std::string> out;
    std::istringstream in(body);
    for (std::string l; std::getline(in, l);) {
        if (!l.empty() && l.back() == '\r') l.pop_back();
        out.push_back(l);
    }
    return out;
}

}  // namespace

TEST(Carryover_바이트가_읽은_줄을_내나는_닫힘_리더와_같은_규칙) {
    // bytesGiveLines 의 인클루드 꼴은 `include_closure::read`(Walker::card) 규칙의 사본이다 — 갈리면 여기서 빨강
    namespace fs = std::filesystem;
    const fs::path root = fs::temp_directory_path() / "koorm_co_bytes";
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(root);
    const std::vector<std::string> bodies = {
        "\xEF\xBB\xBF*NODE\r\n       1     0.0\r\n*END\r\ntail after end\r\n",   // BOM · CRLF · *END 뒤 꼬리
        "*NODE\n$*END\n*END_X\n       2\n  *end   \nafter\n",                    // 주석 · *END_X 는 끝이 아니다 · 앞 공백 소문자 *end 는 끝
        "*NODE\n       3",                                                     // 끝 개행 없음
        "",                                                                     // 빈 파일
        "*END\n",                                                               // 첫 줄이 *END
        "\n\n*NODE\n\n",                                                        // 빈 줄
        "\xEF\xBB\xBF",                                                         // BOM 뿐
        "a\r\r\nb\n",                                                           // CR 둘 — 하나만 뗀다
    };
    std::string main = "*KEYWORD\n";
    for (size_t k = 0; k < bodies.size(); ++k) {
        coWriteBytes(root / ("i" + std::to_string(k) + ".k"), bodies[k]);
        main += "*INCLUDE\ni" + std::to_string(k) + ".k\n";
    }
    main += "*END\n";
    coWriteBytes(root / "main.k", main);
    const auto c = include_closure::read((root / "main.k").string(), coGetlines(main));
    ASSERT_EQ(c.files.size(), bodies.size());
    for (size_t k = 0; k < bodies.size(); ++k) ASSERT_TRUE(carryover::bytesGiveLines(bodies[k], c.files[k].lines, true));
    // *END 앞이 바뀌면 거짓 · *END 뒤만 바뀌면 참(닫힘도 LS-DYNA 도 그 뒤를 읽지 않는다 — 지문은 지금 바이트의 것이다)
    ASSERT_FALSE(carryover::bytesGiveLines(coReplace(bodies[0], "0.0", "0.5"), c.files[0].lines, true));
    ASSERT_TRUE(carryover::bytesGiveLines(coReplace(bodies[0], "tail", "TAIL"), c.files[0].lines, true));
    ASSERT_FALSE(carryover::bytesGiveLines(bodies[2] + "\n       4\n", c.files[2].lines, true));
    ASSERT_FALSE(carryover::bytesGiveLines(bodies[2].substr(0, bodies[2].size() - 1), c.files[2].lines, true));
    ASSERT_FALSE(carryover::bytesGiveLines("x\n" + bodies[3], c.files[3].lines, true));
    // 주 덱 꼴(include false) — 줄을 전부(BOM · *END 뒤까지) · std::getline + CR 하나
    for (const auto& b : bodies) ASSERT_TRUE(carryover::bytesGiveLines(b, coGetlines(b), false));
    ASSERT_FALSE(carryover::bytesGiveLines(bodies[0], c.files[0].lines, false));
    ASSERT_FALSE(carryover::bytesGiveLines(bodies[1] + "x\n", coGetlines(bodies[1]), false));
    fs::remove_all(root, ec);
}
