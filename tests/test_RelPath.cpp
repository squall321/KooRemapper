// 주 덱 폴더 기준 상대 경로를 내는 공용 함수(util/RelPath.h)의 셈을 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-08).
//
//   이월 적용의 인클루드 목록(relpath)과 assemble battery 의 *INCLUDE 이름이 같은 셈을 따로 두었다 — 하나로 모으면서 두 쓰임이
//   바란 꼴(같은 폴더 · 아래 폴더 · `../` · `.` 과 끝 `/` · 정규화 · 작업 폴더 기준 상대 경로)을 여기서 직접 본다.
#include "TestFramework.h"

#include "util/RelPath.h"

#include <string>

using namespace KooRemapper;

TEST(RelPath_relpathOf_는_같은_폴더_아래_폴더_위_폴더를_주_덱_기준으로_낸다) {
    ASSERT_EQ(util::relpathOf("/a/b/c.k", "/a/b"), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("/a/b/sub/c.k", "/a/b"), std::string("sub/c.k"));
    ASSERT_EQ(util::relpathOf("/a/x/c.k", "/a/b"), std::string("../x/c.k"));
    ASSERT_EQ(util::relpathOf("/a/b", "/a/b"), std::string("."));
}

TEST(RelPath_relpathOf_는_끝_슬래시_점_겹친_구분자를_정규화한다) {
    ASSERT_EQ(util::relpathOf("/a/b/c.k", "/a/b/"), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("/a/b/c.k", "/a/b/."), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("/a/b/./sub/../c.k", "/a//b"), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("/a/b/c.k", "/"), std::string("a/b/c.k"));
}

TEST(RelPath_relpathOf_는_상대_경로를_작업_폴더_기준으로_편다) {
    ASSERT_EQ(util::relpathOf("c.k", ""), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("c.k", "."), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("d/c.k", "d"), std::string("c.k"));
    ASSERT_EQ(util::relpathOf("c.k", "d"), std::string("../c.k"));
    ASSERT_EQ(util::relpathOf("d/c.k", "."), std::string("d/c.k"));
}
