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

#ifndef _WIN32
#include <csignal>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

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

#ifndef _WIN32
TEST(StagedWrite_SIGTERM_을_받으면_이번_임시_파일을_지우고_그_신호로_끝난다) {
    SwScratch s("sig");
    const std::string dst = s.at("out.k");
    std::ofstream(dst) << "old\n";
    const pid_t c = ::fork();
    if (c == 0) {   // 자식 — 임시 파일을 쓰고 바꿔 넣기 전에 스스로 SIGTERM
        staged_write::StagedFiles st;
        std::string why;
        if (!st.writeText(dst, "half\n", why)) ::_exit(3);
        ::raise(SIGTERM);
        ::_exit(4);   // 오지 않는다
    }
    int status = 0;
    ASSERT_EQ(::waitpid(c, &status, 0), c);
    ASSERT_TRUE(WIFSIGNALED(status));
    ASSERT_EQ(WTERMSIG(status), SIGTERM);
    ASSERT_EQ(countTemps(s.root), 0);
    ASSERT_EQ(slurp(dst), std::string("old\n"));
}

TEST(StagedWrite_sweepStale_은_주인_없는_같은_산출의_임시_파일만_지운다) {
    SwScratch s("sweep");
    const std::string dst = s.at("out.k");
    const auto me = staged_write::detail::self();
    // 죽은 pid — 끝난 자식의 번호(거둔 뒤라 없다)
    const pid_t dead = ::fork();
    if (dead == 0) ::_exit(0);
    int st = 0;
    ::waitpid(dead, &st, 0);
    auto put = [&](const staged_write::detail::Owner& o, const std::string& target) {
        const std::string n = staged_write::detail::tempBaseName(o, 1, target, "");
        std::ofstream((s.root / n).string()) << "x";
        return n;
    };
    staged_write::detail::Owner deadOwner{me.host, static_cast<long>(dead), 1};
    staged_write::detail::Owner reused{me.host, me.pid, me.start + 1};      // 이 프로세스의 번호 · 다른 시작 — 번호를 물려받았다
    staged_write::detail::Owner other{"0badc0de", static_cast<long>(dead), 1};
    if (other.host == me.host) other.host = "0badc0df";
    staged_write::detail::Owner parent{me.host, static_cast<long>(::getppid()), 0};   // 산 프로세스(시작 시각 모름)
    const std::string gone1 = put(deadOwner, "out.k");
    const std::string gone2 = put(reused, "out.k");
    const std::string keepMine = put(me, "out.k");
    const std::string keepHost = put(other, "out.k");
    const std::string keepOther = put(deadOwner, "other.k");
    const std::string keepLive = put(parent, "out.k");
    std::vector<staged_write::Note> notes;
    const bool knowsStart = me.start != 0;   // 리눅스 /proc — 모르면 번호를 물려받은 것을 가리지 못해 산 것으로 둔다
    ASSERT_EQ(staged_write::sweepStale(dst, &notes), knowsStart ? 2 : 1);
    ASSERT_FALSE(fs::exists(s.root / gone1));
    ASSERT_EQ(fs::exists(s.root / gone2), !knowsStart);
    ASSERT_TRUE(fs::exists(s.root / keepMine));
    ASSERT_TRUE(fs::exists(s.root / keepHost));
    ASSERT_TRUE(fs::exists(s.root / keepOther));
    ASSERT_TRUE(fs::exists(s.root / keepLive));
    ASSERT_EQ(notes.size(), (size_t)1);
    ASSERT_FALSE(notes[0].warn);
}

TEST(StagedWrite_링크는_따라간_파일로_바꿔_넣고_권한_비트를_잇는다) {
    SwScratch s("link");
    fs::create_directories(s.root / "real");
    const std::string target = s.at("real/t.k");
    std::ofstream(target) << "old\n";
    fs::permissions(target, fs::perms::owner_read | fs::perms::owner_write | fs::perms::group_read);   // 0640
    fs::create_symlink("real/t.k", s.root / "out.k");
    staged_write::StagedFiles st;
    std::string why;
    ASSERT_TRUE(st.writeText(s.at("out.k"), "new\n", why));
    ASSERT_TRUE(st.mode(s.at("out.k")) == staged_write::Mode::Rename);
    ASSERT_EQ(countTemps(s.root / "real"), 1);   // 따라간 파일 옆
    ASSERT_TRUE(st.commit(s.at("out.k"), why));
    ASSERT_TRUE(fs::is_symlink(s.root / "out.k"));
    ASSERT_EQ(slurp(target), std::string("new\n"));
    ASSERT_TRUE((fs::status(target).permissions() & fs::perms::all) ==
                (fs::perms::owner_read | fs::perms::owner_write | fs::perms::group_read));
    // 매달린 링크 — 링크가 가리키는 자리에 만든다
    fs::create_symlink("real/new.k", s.root / "dangle.k");
    ASSERT_TRUE(st.writeText(s.at("dangle.k"), "made\n", why));
    ASSERT_TRUE(st.commit(s.at("dangle.k"), why));
    ASSERT_TRUE(fs::is_symlink(s.root / "dangle.k"));
    ASSERT_EQ(slurp(s.at("real/new.k")), std::string("made\n"));
}

TEST(StagedWrite_장치는_바로_쓰고_지우지_않으며_일반_파일이_아니게_된_자리로는_바꿔_넣지_않는다) {
    SwScratch s("dev");
    staged_write::StagedFiles st;
    std::string why, path;
    ASSERT_TRUE(st.reserve("/dev/null", ".k", path, why));
    ASSERT_TRUE(st.mode("/dev/null") == staged_write::Mode::Direct);
    ASSERT_EQ(path, std::string("/dev/null"));
    st.discardAll();   // 장치는 지우지 않는다
    ASSERT_TRUE(fs::is_character_file("/dev/null"));
    // 잡을 때는 일반 파일이었는데 바꿔 넣기 전에 FIFO 로 바뀌었다 — 그 위로 바꿔 넣지 않는다(root 여도)
    const std::string dst = s.at("out.k");
    std::ofstream(dst) << "old\n";
    ASSERT_TRUE(st.writeText(dst, "new\n", why));
    fs::remove(dst);
    ASSERT_EQ(::mkfifo(dst.c_str(), 0644), 0);
    ASSERT_FALSE(st.commit(dst, why));
    ASSERT_TRUE(why.find("FIFO") != std::string::npos);
    ASSERT_TRUE(fs::is_fifo(dst));
    st.discardAll();
    ASSERT_EQ(countTemps(s.root), 0);
    ASSERT_TRUE(fs::is_fifo(dst));
}

TEST(StagedWrite_읽기_전용_폴더의_쓸_수_있는_파일은_바꿔_넣을_때_제자리로_쓰고_경고한다) {
    if (::geteuid() == 0) return;   // root 는 폴더 권한을 넘는다
    SwScratch s("ro");
    fs::create_directories(s.root / "ro");
    const std::string dst = s.at("ro/out.k");
    std::ofstream(dst) << "old\n";
    fs::permissions(s.root / "ro", fs::perms::owner_read | fs::perms::owner_exec);
    staged_write::StagedFiles st;
    std::string why;
    ASSERT_TRUE(st.writeText(dst, "new\n", why));
    ASSERT_TRUE(st.mode(dst) == staged_write::Mode::InPlace);
    auto notes = st.takeNotes();
    ASSERT_EQ(notes.size(), (size_t)1);
    ASSERT_TRUE(notes[0].warn);
    ASSERT_EQ(slurp(dst), std::string("old\n"));   // 바꿔 넣기 전에는 그대로
    ASSERT_TRUE(st.commit(dst, why));
    ASSERT_EQ(slurp(dst), std::string("new\n"));
    fs::permissions(s.root / "ro", fs::perms::owner_all);
    // 읽기 전용 파일은 앞 판(제자리 쓰기)처럼 거절한다
    fs::permissions(dst, fs::perms::owner_read);
    ASSERT_FALSE(st.writeText(dst, "newer\n", why));
    ASSERT_EQ(slurp(dst), std::string("new\n"));
    fs::permissions(dst, fs::perms::owner_read | fs::perms::owner_write);
}
#endif
