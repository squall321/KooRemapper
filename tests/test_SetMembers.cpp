// 세트 멤버 해석 정본 — `_ADD`·`_INTERSECT`·`_COLLECT`·범위·순환을 매뉴얼 규칙대로 푸는가(규칙은 set_members.h)
//
// 왜 이 파일이 있나 (2026-10-23).
//
//   modelmeta · contact · optimize 가 세트를 각자 `SetDef::ids` 로 읽었다. 파서는 `_ADD` 의 멤버(세트 ID)를
//   개체로 오인하지 않으려고 `ids` 를 비워 두므로, 그 세트를 가리키는 접촉은 연결도에서 **0쌍 · 미해석 0** 으로
//   사라졌다. 푸는 일을 정본 하나로 모았으니 그 정본이 매뉴얼(Vol_I `*SET_PART_ADD`·`*SET` COLLECT)과 같은지
//   여기서 본다. 파서와 맞물린 거동(덱 → 연결 변)은 회귀 `test_set_add_resolution.py` 가 잰다.
#include "TestFramework.h"

#include "commands/set_members.h"

#include <array>
#include <string>
#include <vector>

namespace {

SetDef plain(const std::string& type, int id, std::vector<int> ids) {
    SetDef s;
    s.type = type;
    s.id = id;
    s.ids = std::move(ids);
    return s;
}

// 파서가 `_ADD`·`_INTERSECT` 를 읽은 꼴 — `ids` 는 비우고(닫히는 쪽) 멤버 세트는 따로.
SetDef combined(const std::string& type, const std::string& dialect, int id, std::vector<int> members) {
    SetDef s;
    s.type = type;
    s.id = id;
    s.dialect = dialect;
    s.membersKnown = false;
    s.memberSets = std::move(members);
    return s;
}

SetDef segs(int id, std::vector<std::array<int,4>> g) {
    SetDef s;
    s.type = "SEGMENT";
    s.id = id;
    s.segments = std::move(g);
    return s;
}

}  // namespace

TEST(SetMembers_평범한_목록은_그대로) {
    std::vector<SetDef> sets{plain("PART", 10, {3, 1, 2})};
    auto m = ct_setMembers(sets, 10, "PART");
    ASSERT_TRUE(m.found);
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1, 2, 3}));
}

TEST(SetMembers_ADD_는_멤버_세트의_합집합) {
    std::vector<SetDef> sets{plain("PART", 10, {1, 2}), plain("PART", 11, {2, 4}),
                             combined("PART", "ADD", 20, {10, 11})};
    auto m = ct_setMembers(sets, 20, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1, 2, 4}));
}

TEST(SetMembers_ADD_의_음수는_앞_칸부터의_범위) {
    // Vol_I *SET_PART_ADD — PSID[N] LT.0: PSID[N-1] 부터 -PSID[N] 까지(양끝 포함)의 세트를 다 더한다.
    // 덱에 **있는** 세트만 고른다(13 은 없다).
    std::vector<SetDef> sets{plain("PART", 10, {1}), plain("PART", 11, {2}), plain("PART", 12, {3}),
                             plain("PART", 14, {4}), plain("PART", 15, {5}),
                             combined("PART", "ADD", 30, {10, -14})};
    auto m = ct_setMembers(sets, 30, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1, 2, 3, 4}));   // 15 는 범위 밖
}

TEST(SetMembers_ADD_의_없는_멤버는_빼고_적는다) {
    // "Ignore any nonexistant part set IDs in *SET_PART_ADD" — 무시하되 조용히 넘기지 않는다.
    std::vector<SetDef> sets{plain("PART", 10, {1}), combined("PART", "ADD", 20, {10, 99})};
    auto m = ct_setMembers(sets, 20, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1}));
    ASSERT_TRUE(m.note.find("99") != std::string::npos);
}

TEST(SetMembers_ADD_안의_ADD_를_따라간다) {
    std::vector<SetDef> sets{plain("PART", 10, {1}), combined("PART", "ADD", 20, {10}),
                             plain("PART", 11, {7}), combined("PART", "ADD", 30, {20, 11})};
    auto m = ct_setMembers(sets, 30, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1, 7}));
}

TEST(SetMembers_순환은_못_푼다) {
    std::vector<SetDef> sets{combined("PART", "ADD", 20, {30}), combined("PART", "ADD", 30, {20})};
    auto m = ct_setMembers(sets, 20, "PART");
    ASSERT_TRUE(m.found);
    ASSERT_FALSE(m.resolved);
    ASSERT_TRUE(m.why.find("순환") != std::string::npos);
    ASSERT_TRUE(m.ids.empty());
}

TEST(SetMembers_같은_세트를_두_길로_만나도_순환이_아니다) {
    // 마름모 — 40 = 20 + 30, 20 = 10, 30 = 10. 10 을 두 번 만나지만 자기 자신을 포함하지는 않는다.
    std::vector<SetDef> sets{plain("PART", 10, {1}), combined("PART", "ADD", 20, {10}),
                             combined("PART", "ADD", 30, {10}), combined("PART", "ADD", 40, {20, 30})};
    auto m = ct_setMembers(sets, 40, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1}));
}

TEST(SetMembers_INTERSECT_는_교집합) {
    std::vector<SetDef> sets{plain("PART", 10, {1, 2, 3}), plain("PART", 11, {2, 3, 4}),
                             combined("PART", "INTERSECT", 20, {10, 11})};
    auto m = ct_setMembers(sets, 20, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{2, 3}));
}

TEST(SetMembers_COLLECT_는_같은_ID_정의를_합친다) {
    SetDef a = plain("PART", 10, {1}); a.dialect = "COLLECT";
    SetDef b = plain("PART", 10, {2}); b.dialect = "COLLECT";
    std::vector<SetDef> sets{a, b};
    auto m = ct_setMembers(sets, 10, "PART");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.ids, (std::vector<int>{1, 2}));
}

TEST(SetMembers_COLLECT_가_아닌_같은_ID_정의는_못_푼다) {
    // Vol_I *SET — COLLECT 가 아닌 정의가 섞이면 LS-DYNA 는 오류로 끝낸다. 첫 것만 쓰면 반만 맞는 답이다.
    SetDef a = plain("PART", 10, {1}); a.dialect = "COLLECT";
    SetDef b = plain("PART", 10, {2});
    std::vector<SetDef> sets{a, b};
    auto m = ct_setMembers(sets, 10, "PART");
    ASSERT_FALSE(m.resolved);
    ASSERT_TRUE(m.why.find("COLLECT") != std::string::npos);
}

TEST(SetMembers_GENERAL_과_ADVANCED_는_못_푼다고_말한다) {
    SetDef g; g.type = "PART"; g.id = 10; g.dialect = "GENERAL"; g.membersKnown = false;
    SetDef v = combined("NODE", "ADD_ADVANCED", 11, {});
    std::vector<SetDef> sets{g, v};
    auto mg = ct_setMembers(sets, 10, "PART");
    ASSERT_FALSE(mg.resolved);
    ASSERT_TRUE(mg.why.find("GENERAL") != std::string::npos);
    auto mv = ct_setMembers(sets, 11, "NODE");
    ASSERT_FALSE(mv.resolved);
    ASSERT_TRUE(mv.why.find("ADVANCED") != std::string::npos);
}

TEST(SetMembers_없는_세트는_found_false) {
    std::vector<SetDef> sets{plain("NODE", 10, {1})};
    auto m = ct_setMembers(sets, 10, "PART");      // 같은 ID 라도 종류가 다르면 다른 세트다
    ASSERT_FALSE(m.found);
    ASSERT_FALSE(m.resolved);
}

TEST(SetMembers_좁히지_않은_GENERATE_범위는_못_푼다) {
    SetDef r; r.type = "PART"; r.id = 10; r.dialect = "GENERATE";
    r.ranges.push_back({1, 5, 1});                  // rangesResolved=false — 메시를 안 읽은 op
    std::vector<SetDef> sets{r};
    auto m = ct_setMembers(sets, 10, "PART");
    ASSERT_FALSE(m.resolved);
    ASSERT_EQ(ct_setHas(sets, 10, "PART", 3), 1);   // 포함 판정은 범위만으로 답한다
    ASSERT_EQ(ct_setHas(sets, 10, "PART", 9), 0);
}

TEST(SetMembers_SEGMENT_ADD_는_세그먼트를_합친다) {
    std::vector<SetDef> sets{segs(10, {{1, 2, 3, 4}}), segs(11, {{5, 6, 7, 8}, {1, 2, 3, 4}}),
                             combined("SEGMENT", "ADD", 20, {10, 11})};
    auto m = ct_setMembers(sets, 20, "SEGMENT");
    ASSERT_TRUE(m.resolved);
    ASSERT_EQ(m.segments.size(), (size_t)2);        // 같은 면은 한 번만
}

TEST(SetMembers_PART_가_아닌_ADD_의_음수는_못_푼다) {
    std::vector<SetDef> sets{plain("NODE", 10, {1}), combined("NODE", "ADD", 20, {10, -12})};
    auto m = ct_setMembers(sets, 20, "NODE");
    ASSERT_FALSE(m.resolved);
}

TEST(SetMembers_포함_판정이_ADD_와_INTERSECT_를_따라간다) {
    std::vector<SetDef> sets{plain("PART", 10, {1, 2}), plain("PART", 11, {2, 3}),
                             combined("PART", "ADD", 20, {10, 11}),
                             combined("PART", "INTERSECT", 21, {10, 11})};
    ASSERT_EQ(ct_setHas(sets, 20, "PART", 3), 1);
    ASSERT_EQ(ct_setHas(sets, 20, "PART", 9), 0);
    ASSERT_EQ(ct_setHas(sets, 21, "PART", 2), 1);
    ASSERT_EQ(ct_setHas(sets, 21, "PART", 1), 0);
    ASSERT_EQ(ct_setHas(sets, 99, "PART", 1), -1);  // 없는 세트 — 모른다
}
