// 임시 파일 + 바꿔 넣기 공용 도우미(StagedWrite.h)의 이름 꼴 · 쓰기 · 바꿔 넣기를 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-08).
//
//   extract-parts · apply_carryover_plan 의 사본 둘을 공용 도우미 하나로 모으며, 두 리뷰가 찾은 자리(긴 이름 …)를 여기서 직접 본다.
#include "TestFramework.h"

#include "util/StagedWrite.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

using namespace KooRemapper;

namespace {

namespace fs = std::filesystem;

// 시험마다 빈 폴더 하나(같은 번역 단위의 다른 시험과 이름이 겹치지 않게 SwScratch)
struct SwScratch {
    fs::path root;
    explicit SwScratch(const std::string& tag) {
        root = fs::temp_directory_path() / ("koorm_sw_" + tag);
        std::error_code ec;
        fs::remove_all(root, ec);
        fs::create_directories(root);
    }
    ~SwScratch() {
        std::error_code ec;
        fs::remove_all(root, ec);
    }
    std::string at(const std::string& rel) const { return (root / rel).string(); }
};

std::string slurp(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    std::ostringstream s;
    s << f.rdbuf();
    return s.str();
}

int countTemps(const fs::path& d) {
    int n = 0;
    for (const auto& e : fs::directory_iterator(d))
        if (e.path().filename().string().find(".kr_tmp_") != std::string::npos) ++n;
    return n;
}

}  // namespace

TEST(StagedWrite_임시_이름은_산출_이름_길이와_무관하게_짧고_다시_읽힌다) {
    const auto me = staged_write::detail::self();
    ASSERT_EQ(me.host.size(), (size_t)8);
    ASSERT_GT(me.pid, 0L);
    const std::string longName(250, 'a');
    const std::string a = staged_write::detail::tempBaseName(me, 7, longName, ".k");
    const std::string b = staged_write::detail::tempBaseName(me, 7, "x.k", ".k");
    ASSERT_EQ(a.size(), b.size());   // 대상 이름의 해시 8 자리만 든다
    ASSERT_LT(a.size(), (size_t)64);
    staged_write::detail::Owner o;
    std::string h;
    ASSERT_TRUE(staged_write::detail::parseTempName(a, o, h));
    ASSERT_EQ(o.host, me.host);
    ASSERT_EQ(o.pid, me.pid);
    ASSERT_EQ(o.start, me.start);
    ASSERT_EQ(h, staged_write::detail::nameHash(longName));
    ASSERT_FALSE(staged_write::detail::parseTempName(".out.k.kr_tmp_123_1", o, h));   // 옛 꼴 · 다른 파일은 임시 이름이 아니다
    ASSERT_FALSE(staged_write::detail::parseTempName(".kr_tmp_lock_0a1b2c3d", o, h));
}

TEST(StagedWrite_긴_이름도_쓰고_바꿔_넣고_실패면_임시_파일만_지운다) {
    SwScratch s("long");
    const std::string dst = s.at(std::string(240, 'b') + ".k");   // 예전 꼴이면 . + 242 + .kr_tmp_<19>_<n> 이 255 를 넘었다
    staged_write::StagedFiles st;
    std::string why;
    ASSERT_TRUE(st.writeText(dst, "new\n", why));
    ASSERT_EQ(countTemps(s.root), 1);
    ASSERT_TRUE(st.commit(dst, why));
    ASSERT_EQ(slurp(dst), std::string("new\n"));
    ASSERT_EQ(countTemps(s.root), 0);
    {   // 바꿔 넣지 않고 사라지면 이번 임시 파일만 지운다 — 앞 파일은 그대로
        staged_write::StagedFiles st2;
        ASSERT_TRUE(st2.writeText(dst, "newer\n", why));
        ASSERT_EQ(countTemps(s.root), 1);
    }
    ASSERT_EQ(countTemps(s.root), 0);
    ASSERT_EQ(slurp(dst), std::string("new\n"));
}
