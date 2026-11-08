// 보고 글자를 바른 UTF-8 로 고치는 공용 함수(util::validUtf8 — 이월 적용 · extract-parts 보고)를 못 박는 단위 시험
#include "TestFramework.h"

#include "util/Utf8.h"

#include <string>

using namespace KooRemapper;

TEST(Utf8_validUtf8_은_바른_글자는_그대로_깨진_바이트는_U_FFFD_로) {
    const std::string fffd = "\xEF\xBF\xBD";
    ASSERT_EQ(util::validUtf8("ascii · 한글 ✓ 😀"), std::string("ascii · 한글 ✓ 😀"));
    // CP949 「한글」(C7 D1 B1 DB) — 가운데 D1 B1 은 우연히 바른 UTF-8(U+0471)이라 남고 앞뒤 홀로 선 바이트만 바뀐다
    ASSERT_EQ(util::validUtf8("\xC7\xD1\xB1\xDB.k"), fffd + "\xD1\xB1" + fffd + ".k");
    ASSERT_EQ(util::validUtf8("\xC0\xAF"), fffd + fffd);                                  // 넘친 꼴(overlong '/')
    ASSERT_EQ(util::validUtf8("\xED\xA0\x80"), fffd + fffd + fffd);                       // 서로게이트 U+D800
    ASSERT_EQ(util::validUtf8("\xF4\x90\x80\x80"), fffd + fffd + fffd + fffd);            // U+10FFFF 위
    ASSERT_EQ(util::validUtf8("\xEA\xB0"), fffd + fffd);                                  // 잘린 꼴(「가」 의 앞 두 바이트)
    ASSERT_EQ(util::validUtf8(""), std::string());
}
