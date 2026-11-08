// 임시 파일 + 바꿔 넣기 공용 도우미(StagedWrite.h)의 이름 꼴 · 쓰기 · 바꿔 넣기를 못 박는 단위 시험
//
// 왜 이 파일이 있나 (2026-11-08).
//
//   extract-parts · apply_carryover_plan 의 사본 둘을 공용 도우미 하나로 모으며, 두 리뷰가 찾은 자리(긴 이름 …)를 여기서 직접 본다.
#include "TestFramework.h"

#include "util/StagedWrite.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#ifndef _WIN32
#include <csignal>
#include <sys/resource.h>
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

TEST(StagedWrite_unstage_는_임시_경로의_꼴마다_제_이름으로_바꾼다) {
    SwScratch s("unstage");
    fs::create_directories(s.root / "dir");
    const std::string dst = s.at("dir/applied.k");
    staged_write::StagedFiles st;
    std::string tmp, why;
    ASSERT_TRUE(st.reserve(dst, ".k", tmp, why));
    const std::string stem = tmp.substr(0, tmp.size() - 2);
    const std::string base = fs::path(tmp).filename().string();
    ASSERT_EQ(st.unstage("Cannot open file: " + tmp), "Cannot open file: " + dst);                         // 되읽기 예외
    ASSERT_EQ(st.unstage("출력 파일을 쓰지 않았습니다: " + stem + " /"), "출력 파일을 쓰지 않았습니다: " + dst.substr(0, dst.size() - 2) + " /");   // long 덱 — 접두
    ASSERT_EQ(st.unstage(fs::absolute(tmp).lexically_normal().string()), dst);
    ASSERT_EQ(st.unstage("[" + base + "]"), std::string("[applied.k]"));
    st.discardAll();   // 지운 뒤에도 말은 고친다
    ASSERT_EQ(st.unstage(tmp + " · " + tmp), dst + " · " + dst);
    ASSERT_EQ(st.unstage("상관없는 글"), std::string("상관없는 글"));
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
    ASSERT_TRUE(notes[0].text.find(".kr_tmp_") == std::string::npos);   // 수만 — 임시 이름은 찍지 않는다
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

TEST(StagedWrite_매달린_링크는_커널처럼_물리로_따라간다) {
    // L → real/sub · real/sub/x.k → ../deck.k — 커널은 real/deck.k 에 쓴다. 낱말로 풀면(L/../deck.k) 맨 위 deck.k 였다(여섯째 검토 S3)
    SwScratch s("dotdot");
    fs::create_directories(s.root / "real" / "sub");
    std::ofstream(s.at("deck.k")) << "INPUT\n";
    fs::create_directory_symlink("real/sub", s.root / "L");
    fs::create_symlink("../deck.k", s.root / "real" / "sub" / "x.k");
    const std::string dst = s.at("L/x.k");
    const std::string want = (fs::canonical(s.root) / "real" / "deck.k").string();
    ASSERT_EQ(staged_write::physicalTarget(dst), want);
    staged_write::StagedFiles st;
    std::string why;
    ASSERT_TRUE(st.writeText(dst, "NEW\n", why));
    ASSERT_TRUE(st.commit(dst, why));
    ASSERT_EQ(slurp(s.at("deck.k")), std::string("INPUT\n"));   // 입력 그대로
    ASSERT_EQ(slurp(want), std::string("NEW\n"));
    ASSERT_TRUE(fs::is_symlink(s.root / "real" / "sub" / "x.k"));
    // 링크가 아닌 자리 — 폴더를 물리로 푼 절대 경로
    ASSERT_EQ(staged_write::physicalTarget(s.at("L/plain.k")), (fs::canonical(s.root) / "real" / "sub" / "plain.k").string());
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

TEST(StagedWrite_CommitLock_은_같은_산출을_쥔_다른_프로세스가_풀_때까지_기다린다) {
    SwScratch s("lock");
    const std::string dst = s.at("out.k");
    int ready[2];
    ASSERT_EQ(::pipe(ready), 0);
    const pid_t c = ::fork();
    if (c == 0) {   // 자식 — 잠그고 알린 뒤 0.4 초 쥔다
        ::close(ready[0]);
        {
            staged_write::CommitLock lk(dst);
            if (!lk.held()) ::_exit(3);
            if (::write(ready[1], "x", 1) != 1) ::_exit(4);
            ::usleep(400000);
        }
        ::_exit(0);
    }
    ::close(ready[1]);
    char b = 0;
    ASSERT_EQ(::read(ready[0], &b, 1), (ssize_t)1);
    ::close(ready[0]);
    {   // 짧게만 기다리면 잠그지 못하고 경고한다
        staged_write::CommitLock quick(dst, 0.05);
        ASSERT_FALSE(quick.held());
        auto n = quick.takeNotes();
        ASSERT_EQ(n.size(), (size_t)1);
        ASSERT_TRUE(n[0].warn);
    }
    const auto t0 = std::chrono::steady_clock::now();
    {
        staged_write::CommitLock lk(dst);
        ASSERT_TRUE(lk.held());
        const double waited = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        ASSERT_GT(waited, 0.2);   // 자식이 풀 때까지 기다렸다
    }
    int st = 0;
    ASSERT_EQ(::waitpid(c, &st, 0), c);
    ASSERT_TRUE(WIFEXITED(st) && WEXITSTATUS(st) == 0);
    ASSERT_EQ(countTemps(s.root), 0);   // 잠금 파일(.kr_tmp_lock_…)도 지웠다
}

TEST(StagedWrite_CommitLock_quietIfNoFolder_는_폴더가_없거나_쓸_수_없을_때만_말없이_잠그지_않는다) {
    SwScratch s("lockq");
    const std::string missing = s.at("nodir/out.k");
    {
        staged_write::CommitLock loud(missing);
        ASSERT_FALSE(loud.held());
        ASSERT_EQ(loud.takeNotes().size(), (size_t)1);   // 바꿔 넣는 차례는 말한다
    }
    {
        staged_write::CommitLock quiet(missing, 30.0, true);
        ASSERT_FALSE(quiet.held());
        ASSERT_TRUE(quiet.takeNotes().empty());   // 거절 보고 — 그 폴더에 바꿔 넣을 것이 없다
    }
    if (::geteuid() != 0) {   // root 는 폴더 권한을 넘는다
        fs::create_directories(s.root / "ro");
        fs::permissions(s.root / "ro", fs::perms::owner_read | fs::perms::owner_exec);
        staged_write::CommitLock quiet(s.at("ro/out.k"), 30.0, true);
        const bool silent = !quiet.held() && quiet.takeNotes().empty();
        fs::permissions(s.root / "ro", fs::perms::owner_all);
        ASSERT_TRUE(silent);
    }
    {   // 쓸 수 있는 폴더면 조용한 쪽도 잠근다
        staged_write::CommitLock quiet(s.at("out.k"), 30.0, true);
        ASSERT_TRUE(quiet.held());
    }
}

namespace {
// 그 블록 동안만 파일 크기 상한(SIGXFSZ 무시 — 넘는 쓰기가 EFBIG 로 짧게 끝난다) — 빠져나갈 때(ASSERT 의 return 도) 되돌린다
struct FsizeCap {
    struct rlimit old {};
    struct sigaction oldAct {};
    explicit FsizeCap(rlim_t cap) {
        struct sigaction ign {};
        ign.sa_handler = SIG_IGN;
        ::sigaction(SIGXFSZ, &ign, &oldAct);
        ::getrlimit(RLIMIT_FSIZE, &old);
        struct rlimit nw = old;
        nw.rlim_cur = cap;
        ::setrlimit(RLIMIT_FSIZE, &nw);
    }
    ~FsizeCap() {
        ::setrlimit(RLIMIT_FSIZE, &old);
        ::sigaction(SIGXFSZ, &oldAct, nullptr);
    }
};
}  // namespace

TEST(StagedWrite_제자리로_옮겨_쓰다_멈추면_damaged_가_참이고_대상을_열지_못했으면_거짓이다) {
    if (::geteuid() == 0) return;   // root 는 폴더 · 파일 권한을 넘는다
    SwScratch s("dmg");
    fs::create_directories(s.root / "ro");
    const std::string dst = s.at("ro/out.k"), keep = s.at("ro/keep.k");
    std::ofstream(dst) << "old\n";
    std::ofstream(keep) << "old\n";
    fs::permissions(s.root / "ro", fs::perms::owner_read | fs::perms::owner_exec);
    staged_write::StagedFiles st;
    std::string why;
    const std::string big(64 * 1024, 'x');
    ASSERT_TRUE(st.writeText(dst, big, why));   // 읽기 전용 폴더 — 시스템 임시 폴더에 써 둔다(InPlace)
    ASSERT_TRUE(st.writeText(keep, big, why));
    fs::permissions(keep, fs::perms::owner_read);   // 대상을 열지 못한다 — 앞 파일 그대로
    bool failed = false;
    {
        FsizeCap cap(1000);
        failed = !st.commit(dst, why);
    }
    ASSERT_TRUE(failed);
    ASSERT_TRUE(st.damaged(dst));
    ASSERT_TRUE(why.find("잘려") != std::string::npos);
    ASSERT_EQ(fs::file_size(dst), (uintmax_t)1000);   // 잘렸다 — 앞 내용도 새 내용도 아니다
    ASSERT_FALSE(st.commit(keep, why));
    ASSERT_FALSE(st.damaged(keep));
    ASSERT_EQ(slurp(keep), std::string("old\n"));
    st.discardAll();
    ASSERT_TRUE(st.damaged(dst));   // 지운 뒤에도 남는다(실패 보고가 묻는다)
    fs::permissions(keep, fs::perms::owner_read | fs::perms::owner_write);
    fs::permissions(s.root / "ro", fs::perms::owner_all);
}
#endif
