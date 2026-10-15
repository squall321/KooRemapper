// 번호 발행의 한 길 — 본 최대값 위로 내고, 못 본 자리는 말한다(규칙은 IdAllocator.h)
#include "TestFramework.h"

#include "parser/IdAllocator.h"

using namespace KooRemapper;

TEST(IdAllocator_본_최대값_위로_하나씩) {
    ids::UsedIds u;
    u.raise(ids::Ns::Set, 10);
    u.raise(ids::Ns::Set, 7);                       // 더 작은 값은 최대값을 못 내린다
    ids::IdAllocator a(u);
    ASSERT_EQ(a.issue(ids::Ns::Set), 11);
    ASSERT_EQ(a.issue(ids::Ns::Set), 12);
}

TEST(IdAllocator_네임스페이스는_따로_센다) {
    ids::UsedIds u;
    u.raise(ids::Ns::Set, 40);
    u.raise(ids::Ns::Contact, 3);
    ids::IdAllocator a(u);
    ASSERT_EQ(a.issue(ids::Ns::Contact), 4);        // SET 의 40 에 끌려가지 않는다
    ASSERT_EQ(a.issue(ids::Ns::Set), 41);
    ASSERT_EQ(a.issue(ids::Ns::Contact), 5);
}

TEST(IdAllocator_아무것도_없으면_1부터) {
    ids::IdAllocator a{ids::UsedIds{}};
    ASSERT_EQ(a.issue(ids::Ns::Set), 1);
    ASSERT_EQ(a.issue(ids::Ns::Contact), 1);
}

TEST(IdAllocator_못_본_인클루드는_말한다) {
    include_closure::Closure c;
    c.unresolved.push_back({"main.k", 12, "gone.k", "없다"});
    c.notFollowed.push_back({"main.k", 20, "*INCLUDE_TRANSFORM", "t.k"});
    ids::UsedIds u;
    ASSERT_TRUE(u.complete());
    u.noteClosure(c);
    ASSERT_FALSE(u.complete());
    ASSERT_EQ(u.blind.size(), (size_t)2);
    ASSERT_TRUE(u.blind[0].find("gone.k") != std::string::npos);
    ASSERT_TRUE(u.blind[1].find("*INCLUDE_TRANSFORM") != std::string::npos);
}

TEST(IdAllocator_다_읽은_닫힘은_말할_것이_없다) {
    include_closure::Closure c;                     // 파일이 있어도 못 본 자리가 없으면 완전하다
    c.files.push_back({"inc.k", {"*SET_PART", "3"}, 1, "main.k", 4});
    ids::UsedIds u;
    u.noteClosure(c);
    ASSERT_TRUE(u.complete());
}
