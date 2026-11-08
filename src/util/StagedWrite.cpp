// 임시 파일 + 바꿔 넣기 공용 도우미의 구현 — 같은 폴더의 임시 이름을 잡고 · 쓰고 · 바꿔 넣고 · 이번 실행이 만든 것만 지운다
#include "util/StagedWrite.h"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <mutex>
#include <system_error>

#ifdef _WIN32
#include <process.h>
#else
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#endif

namespace KooRemapper {
namespace staged_write {

namespace {

namespace fs = std::filesystem;

std::string absOf(const std::string& p) {
    std::error_code ec;
    const fs::path a = fs::absolute(fs::path(p), ec);
    return ec ? p : a.lexically_normal().string();
}

// ── 신호 때 지울 경로 표 ──────────────────────────────────────────────────────
// 처리기 안에서는 할당 · 잠금 · stdio 를 쓰지 않는다 — 미리 적어 둔 경로를 unlink 하고 원래 처분으로 되돌려 그 신호를 다시 보낸다
// (종료 상태가 그 신호다). 플랫폼 취소는 SIGTERM 다음 SIGKILL · 시간 초과는 SIGKILL 이다 — SIGKILL 이 남긴 것은 다음 실행이 치운다
// (`sweepStale`). 이름에 pid · 시작 시각이 들어 이 프로세스 말고는 그 이름을 만들지 않는다 — 바꿔 넣은 뒤 표에서 빼기 전에 신호가
// 와도 지우는 것은 없는 이름이다.
#ifndef _WIN32
constexpr int kSlots = 32;
constexpr size_t kPathCap = 4096;
struct Slot {
    std::atomic<int> state{0};   // 0 빈 자리 · 1 적는 중 · 2 지울 경로
    char path[kPathCap];
};
Slot g_slot[kSlots];
static_assert(std::atomic<int>::is_always_lock_free, "신호 처리기가 읽는 표지는 잠금 없이 읽혀야 한다");
const int kSignals[3] = {SIGTERM, SIGINT, SIGHUP};
struct sigaction g_prev[3];
volatile sig_atomic_t g_hooked[3] = {0, 0, 0};

extern "C" void krStagedWriteOnSignal(int sig) {
    const int saved = errno;
    for (int i = 0; i < kSlots; ++i)
        if (g_slot[i].state.load(std::memory_order_acquire) == 2) ::unlink(g_slot[i].path);
    for (int k = 0; k < 3; ++k)
        if (kSignals[k] == sig && g_hooked[k]) ::sigaction(sig, &g_prev[k], nullptr);
    errno = saved;
    ::raise(sig);   // 처리기를 나가면 원래 처분(보통 끝내기)으로 그 신호가 간다
}

void hookSignals() {
    static std::once_flag once;
    std::call_once(once, [] {
        for (int k = 0; k < 3; ++k) {
            struct sigaction prev;
            if (::sigaction(kSignals[k], nullptr, &prev) != 0) continue;
            // 무시하라던 신호(nohup 의 SIGHUP 등)는 그대로 둔다
            if (!(prev.sa_flags & SA_SIGINFO) && prev.sa_handler == SIG_IGN) continue;
            struct sigaction sa;
            std::memset(&sa, 0, sizeof sa);
            sa.sa_handler = krStagedWriteOnSignal;
            sigemptyset(&sa.sa_mask);
            for (int s : kSignals) sigaddset(&sa.sa_mask, s);
            g_prev[k] = prev;
            g_hooked[k] = 1;   // 처리기가 처분을 되돌릴 수 있게 설치 **앞**에 적는다
            if (::sigaction(kSignals[k], &sa, nullptr) != 0) g_hooked[k] = 0;
        }
    });
}

int arm(const std::string& path) {
    const std::string a = absOf(path);
    if (a.empty() || a.size() >= kPathCap) return -1;
    hookSignals();
    for (int i = 0; i < kSlots; ++i) {
        int expect = 0;
        if (!g_slot[i].state.compare_exchange_strong(expect, 1, std::memory_order_acq_rel)) continue;
        std::memcpy(g_slot[i].path, a.c_str(), a.size() + 1);
        g_slot[i].state.store(2, std::memory_order_release);
        return i;
    }
    return -1;   // 표가 찼다 — 그 파일은 신호 때 남고 다음 실행이 치운다
}

void disarm(int i) {
    if (i >= 0 && i < kSlots) g_slot[i].state.store(0, std::memory_order_release);
}
#else
int arm(const std::string&) { return -1; }
void disarm(int) {}
#endif

// FNV-1a 64 — 이름 해시 · 호스트 표지(암호가 아니다 — 같은 폴더 안에서 산출을 가르는 데 쓴다)
uint64_t fnv1a(const std::string& s) {
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : s) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    return h;
}

std::string hex8(uint64_t v) {
    char b[16];
    std::snprintf(b, sizeof b, "%08x", static_cast<unsigned>(v & 0xffffffffULL));
    return b;
}

std::string hexU(unsigned long long v) {
    char b[24];
    std::snprintf(b, sizeof b, "%llx", v);
    return b;
}

std::atomic<unsigned long long> g_serial{0};

#ifdef __linux__
// /proc/<pid>/stat 의 starttime(칸 22 · 부팅 뒤 클록 틱) — 0 = 모른다(없다 · 못 읽는다)
unsigned long long procStart(long pid) {
    char p[64];
    std::snprintf(p, sizeof p, "/proc/%ld/stat", pid);
    std::FILE* f = std::fopen(p, "r");
    if (!f) return 0;
    char buf[1024];
    const size_t n = std::fread(buf, 1, sizeof buf - 1, f);
    std::fclose(f);
    buf[n] = '\0';
    const char* s = std::strrchr(buf, ')');   // 이름 칸(2)은 괄호 안 — 빈칸 · 괄호가 들 수 있다
    if (!s) return 0;
    ++s;
    for (int field = 3; *s; ++field) {
        while (*s == ' ') ++s;
        if (field == 22) return std::strtoull(s, nullptr, 10);
        while (*s && *s != ' ') ++s;
    }
    return 0;
}
#else
unsigned long long procStart(long) { return 0; }
#endif

// 호스트 이름 · pid 이름공간 — 같은 값이면 pid 로 주인이 살았는지 잴 수 있다
std::string hostTag() {
    static const std::string tag = [] {
        std::string id;
#ifndef _WIN32
        char h[256] = {0};
        if (::gethostname(h, sizeof h - 1) == 0) id = h;
        struct stat st;
        if (::stat("/proc/self/ns/pid", &st) == 0) id += ":" + std::to_string(static_cast<unsigned long long>(st.st_ino));
#else
        if (const char* c = std::getenv("COMPUTERNAME")) id = c;
#endif
        return hex8(fnv1a(id));
    }();
    return tag;
}

#ifndef _WIN32
// 주인 프로세스가 살았나 — 모르면 산 것으로 본다(지우지 않는다)
bool ownerAlive(long pid, unsigned long long start) {
    if (pid <= 0 || pid > 0x7fffffffL) return true;
    if (::kill(static_cast<pid_t>(pid), 0) != 0 && errno == ESRCH) return false;
    const unsigned long long now = procStart(pid);
    if (now != 0 && start != 0 && now != start) return false;   // 그 번호를 다른 프로세스가 물려받았다 — 주인은 죽었다
    return true;
}
#endif

#ifndef _WIN32
const char* kindOf(mode_t m) {
    if (S_ISDIR(m)) return "폴더";
    if (S_ISCHR(m)) return "문자 장치";
    if (S_ISBLK(m)) return "블록 장치";
    if (S_ISFIFO(m)) return "FIFO";
    if (S_ISSOCK(m)) return "소켓";
    return "일반 파일이 아닌 것";
}
#endif

std::string errText(int e) { return std::strerror(e); }

std::string baseOf(const std::string& p) {
    const size_t sep = p.find_last_of("/\\");
    return sep == std::string::npos ? p : p.substr(sep + 1);
}

// 폴더 몫(끝의 `/` 까지) — 없으면 빈 글(현재 폴더)
std::string dirPartOf(const std::string& p) {
    const size_t sep = p.find_last_of("/\\");
    return sep == std::string::npos ? std::string() : p.substr(0, sep + 1);
}

// ── 대상 ─────────────────────────────────────────────────────────────────────
// 대상 — 심볼릭 링크면 끝까지 따라간 파일(매달린 링크면 링크가 가리키는 자리 — 앞 판은 링크를 따라 썼다). 일반 파일이 아니면 special
struct Target {
    std::string path;
    bool exists = false, special = false, dir = false;
    unsigned perm = 0;
    std::string err;
};

Target resolveTarget(const std::string& dst) {
    Target t;
    t.path = dst;
#ifndef _WIN32
    struct stat st;
    if (::stat(dst.c_str(), &st) == 0) {
        t.exists = true;
        if (S_ISDIR(st.st_mode)) { t.dir = true; return t; }
        if (!S_ISREG(st.st_mode)) { t.special = true; return t; }
        t.perm = static_cast<unsigned>(st.st_mode & 0777);
        struct stat lst;
        if (::lstat(dst.c_str(), &lst) == 0 && S_ISLNK(lst.st_mode)) {
            if (char* rp = ::realpath(dst.c_str(), nullptr)) {
                t.path = rp;
                std::free(rp);
            } else {
                t.err = errText(errno);
            }
        }
        return t;
    }
    const int e = errno;
    if (e != ENOENT) { t.err = errText(e); return t; }
    std::string p = dst;
    for (int hop = 0; hop < 40; ++hop) {
        struct stat lst;
        if (::lstat(p.c_str(), &lst) != 0 || !S_ISLNK(lst.st_mode)) break;
        std::error_code ec;
        fs::path to = fs::read_symlink(p, ec);
        if (ec) break;
        if (to.is_relative()) to = fs::path(p).parent_path() / to;
        p = to.lexically_normal().string();
    }
    t.path = p;
#else
    std::error_code ec;
    const auto s = fs::status(dst, ec);
    if (!ec && fs::exists(s)) {
        t.exists = true;
        if (fs::is_directory(s)) t.dir = true;
        else if (!fs::is_regular_file(s)) t.special = true;
    }
#endif
    return t;
}

#ifndef _WIN32
bool writeAll(int fd, const char* data, size_t n, int& e) {
    size_t off = 0;
    while (off < n) {
        const ssize_t w = ::write(fd, data + off, n - off);
        if (w < 0) {
            if (errno == EINTR) continue;
            e = errno;
            return false;
        }
        off += static_cast<size_t>(w);
    }
    return true;
}

// 임시 파일을 있는 대상에 제자리로 옮겨 쓴다(자르고 쓴다 — 원자적이 아니다). 대상은 있어야 한다(새로 만들지 않는다)
bool copyInto(const std::string& from, const std::string& to, std::string& why) {
    const int in = ::open(from.c_str(), O_RDONLY | O_CLOEXEC);
    if (in < 0) { why = "임시 파일을 다시 열지 못했다(" + errText(errno) + ")"; return false; }
    const int out = ::open(to.c_str(), O_WRONLY | O_TRUNC | O_CLOEXEC);
    if (out < 0) {
        const int e = errno;
        ::close(in);
        why = "대상을 열지 못했다(" + errText(e) + ")";
        return false;
    }
    char buf[1 << 16];
    bool ok = true;
    int e = 0;
    for (;;) {
        const ssize_t r = ::read(in, buf, sizeof buf);
        if (r < 0) {
            if (errno == EINTR) continue;
            ok = false;
            e = errno;
            break;
        }
        if (r == 0) break;
        if (!writeAll(out, buf, static_cast<size_t>(r), e)) { ok = false; break; }
    }
    if (::close(out) != 0 && ok) { ok = false; e = errno; }
    ::close(in);
    if (!ok) why = "제자리로 옮겨 쓰다 멈췄다(" + errText(e) + ") — 그 파일은 반쯤 쓴 채일 수 있다";
    return ok;
}
#endif

}  // namespace

// ── detail(시험이 이름 꼴을 잰다) ─────────────────────────────────────────────
namespace detail {

Owner self() {
    static std::mutex mu;
    static long cachedPid = 0;
    static unsigned long long cachedStart = 0;
    Owner o;
    o.host = hostTag();
#ifdef _WIN32
    o.pid = static_cast<long>(_getpid());
#else
    o.pid = static_cast<long>(::getpid());
#endif
    std::lock_guard<std::mutex> lk(mu);
    if (cachedPid != o.pid) {   // fork 뒤에는 다시 잰다
        cachedPid = o.pid;
        cachedStart = procStart(o.pid);
    }
    o.start = cachedStart;
    return o;
}

std::string nameHash(const std::string& targetBase) { return hex8(fnv1a(targetBase)); }

std::string tempBaseName(const Owner& o, unsigned long long n, const std::string& targetBase, const std::string& suffix) {
    return ".kr_tmp_" + o.host + "_" + std::to_string(o.pid) + "_" + hexU(o.start) + "_" + std::to_string(n) + "_" +
           nameHash(targetBase) + suffix;
}

bool parseTempName(const std::string& name, Owner& o, std::string& hash) {
    static const std::string pre = ".kr_tmp_";
    if (name.compare(0, pre.size(), pre) != 0) return false;
    size_t i = pre.size();
    auto take = [&](bool hex, size_t minLen, size_t maxLen, std::string& out) {
        size_t j = i;
        while (j < name.size() && j - i < maxLen &&
               (hex ? std::isxdigit(static_cast<unsigned char>(name[j])) : std::isdigit(static_cast<unsigned char>(name[j]))))
            ++j;
        if (j - i < minLen) return false;
        out = name.substr(i, j - i);
        i = j;
        return true;
    };
    auto under = [&]() {
        if (i >= name.size() || name[i] != '_') return false;
        ++i;
        return true;
    };
    std::string host, pid, start, n, h;
    if (!take(true, 8, 8, host) || !under() || !take(false, 1, 10, pid) || !under() || !take(true, 1, 16, start) || !under() ||
        !take(false, 1, 20, n) || !under() || !take(true, 8, 8, h))
        return false;
    o.host = host;
    o.pid = std::strtol(pid.c_str(), nullptr, 10);
    o.start = std::strtoull(start.c_str(), nullptr, 16);
    hash = h;
    return true;
}

}  // namespace detail

// ── StagedFiles ──────────────────────────────────────────────────────────────
StagedFiles::~StagedFiles() { discardAll(); }

bool StagedFiles::reserve(const std::string& dst, const std::string& suffix, std::string& writePath, std::string& why) {
    discard(dst);   // 같은 자리를 다시 잡으면 앞 임시 파일은 버린다
    why.clear();
    if (dst.empty()) { why = "쓸 자리가 비었다"; return false; }
    const Target t = resolveTarget(dst);
    if (!t.err.empty()) { why = t.err; return false; }
    if (t.dir) { why = "폴더다"; return false; }
    Item it;
    it.dst = dst;
    it.target = t.path;
    it.existed = t.exists;
    it.perm = t.perm;
    if (t.special) {   // 장치 · FIFO — 바로 쓴다(임시 파일 없음 · 바꿔 넣지도 지우지도 않는다)
        it.mode = Mode::Direct;
        it.tmp = dst;
        items_.push_back(it);
        writePath = dst;
        return true;
    }
#ifndef _WIN32
    // 쓸 수 없는 파일은 앞 판(제자리 쓰기)처럼 거절한다 — 읽기 전용으로 둔 산출을 이름 바꾸기로 덮지 않는다
    if (t.exists && ::access(t.path.c_str(), W_OK) != 0) { why = errText(errno); return false; }
    // 짧은 이름 — 산출 이름 길이와 무관하다(예전 `.<이름>.kr_tmp_<시각>_<n>` 은 30 글자를 더해 NAME_MAX 가까운 이름이 끝에서 실패했다).
    // O_EXCL 로 만들어 이름을 잡는다. 있던 파일 자리면 쓰는 동안은 나만 읽게(0600) 만들고 바꿔 넣을 때 그 파일의 권한 비트로 맞춘다
    const detail::Owner me = detail::self();
    const std::string tb = baseOf(t.path);
    auto stageIn = [&](const std::string& dir, mode_t mode, int& lastErr) {
        for (int k = 0; k < 1000; ++k) {
            const std::string cand = dir + detail::tempBaseName(me, ++g_serial, tb, suffix);
            const int fd = ::open(cand.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, mode);
            if (fd < 0) {
                lastErr = errno;
                if (lastErr == EEXIST) continue;
                return std::string();
            }
            ::close(fd);
            return cand;
        }
        return std::string();
    };
    int lastErr = 0;
    std::string tmp = stageIn(dirPartOf(t.path), t.exists ? 0600 : 0666, lastErr);
    if (tmp.empty()) {
        if (!t.exists) { why = errText(lastErr); return false; }
        // 대상 폴더에 새 파일을 만들 수 없다(읽기 전용 폴더 등) — 있는 일반 파일(위에서 쓸 수 있음을 봤다)에 바꿔 넣을 때 제자리로 쓴다.
        // 그때까지는 시스템 임시 폴더에 써 둔다 — 거절 · 실패면 그 파일은 그대로다
        std::error_code ec;
        std::string td = fs::temp_directory_path(ec).string();
        if (ec || td.empty()) { why = errText(lastErr); return false; }
        if (td.back() != '/') td += '/';
        int e2 = 0;
        tmp = stageIn(td, 0600, e2);
        if (tmp.empty()) { why = errText(lastErr); return false; }
        it.mode = Mode::InPlace;
        notes_.push_back({true, "「" + dst + "」 의 폴더에 임시 파일을 만들 수 없다(" + errText(lastErr) + ") — 시스템 임시 폴더에 써 두었다가 "
                                "바꿔 넣을 때 그 파일에 제자리로 쓴다. 원자적이 아니다(옮겨 쓰는 사이에 멈추면 반쯤 쓴 파일이 남는다)"});
    }
#else
    std::string tmp;
    for (int k = 0; k < 1000 && tmp.empty(); ++k) {
        const std::string cand = dirPartOf(t.path) + detail::tempBaseName(detail::self(), ++g_serial, baseOf(t.path), suffix);
        std::error_code ec;
        if (fs::exists(cand, ec)) continue;
        if (std::FILE* f = std::fopen(cand.c_str(), "wb")) {
            std::fclose(f);
            tmp = cand;
        } else {
            why = errText(errno);
            return false;
        }
    }
    if (tmp.empty()) { why = "임시 이름을 잡지 못했다"; return false; }
#endif
    it.tmp = tmp;
    it.slot = arm(tmp);   // 신호 때 지울 경로 — 이 이름은 이 프로세스만 만든다
    items_.push_back(it);
    writePath = tmp;
    return true;
}

bool StagedFiles::writeText(const std::string& dst, const std::string& text, std::string& why) {
    std::string path;
    if (!reserve(dst, "", path, why)) return false;
#ifndef _WIN32
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) { why = errText(errno); return false; }
    int e = 0;
    bool ok = writeAll(fd, text.data(), text.size(), e);
    if (::close(fd) != 0 && ok) { ok = false; e = errno; }
    if (!ok) why = errText(e);
    return ok;
#else
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { why = errText(errno); return false; }
    const bool wrote = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    const bool closed = std::fclose(f) == 0;
    if (!wrote || !closed) why = "쓰지 못했다";
    return wrote && closed;
#endif
}

bool StagedFiles::commit(const std::string& dst, std::string& why) {
    why.clear();
    auto it = std::find_if(items_.begin(), items_.end(), [&](const Item& x) { return x.dst == dst; });
    if (it == items_.end()) { why = "바꿔 넣을 임시 파일이 없다"; return false; }
    if (it->mode == Mode::Direct) {   // 이미 대상에 썼다
        items_.erase(it);
        return true;
    }
#ifndef _WIN32
    if (it->mode == Mode::InPlace) {
        if (!copyInto(it->tmp, it->target, why)) return false;
        ::unlink(it->tmp.c_str());
        disarm(it->slot);
        items_.erase(it);
        return true;
    }
    struct stat st;
    const bool present = ::lstat(it->target.c_str(), &st) == 0;
    // ★장치 노드 · FIFO · 폴더 위로는 바꿔 넣지 않는다(root 여도 — `/dev/null` 이 일반 파일로 바뀐다). 잡을 때는 일반 파일이었다
    if (present && !S_ISREG(st.st_mode) && !S_ISLNK(st.st_mode)) {
        why = std::string("대상이 일반 파일이 아니다(") + kindOf(st.st_mode) + ") — 그 위로 바꿔 넣지 않는다";
        return false;
    }
    // 권한 비트는 있던 파일의 것을 잇는다(지금 있으면 지금 것)
    if (present && S_ISREG(st.st_mode)) ::chmod(it->tmp.c_str(), st.st_mode & 0777);
    else if (it->existed) ::chmod(it->tmp.c_str(), static_cast<mode_t>(it->perm));
    if (::rename(it->tmp.c_str(), it->target.c_str()) == 0) {
        disarm(it->slot);
        items_.erase(it);
        return true;
    }
    const int e = errno;
    // 폴더 권한(끈적 폴더 · 바뀐 권한)이 이름 바꾸기를 막는데 있는 파일에 쓸 수 있으면 제자리로 쓴다 — 원자적이 아니다
    if ((e == EACCES || e == EPERM) && present && S_ISREG(st.st_mode) && ::access(it->target.c_str(), W_OK) == 0) {
        if (!copyInto(it->tmp, it->target, why)) return false;
        ::unlink(it->tmp.c_str());
        disarm(it->slot);
        notes_.push_back({true, "「" + dst + "」 를 이름 바꾸기로 바꿔 넣지 못해(" + errText(e) + ") 그 파일에 제자리로 썼다 — 원자적이 아니다"});
        items_.erase(it);
        return true;
    }
    why = errText(e);
    return false;
#else
    std::error_code ec;
    fs::rename(it->tmp, it->target, ec);
    if (ec) { why = ec.message(); return false; }
    items_.erase(it);
    return true;
#endif
}

void StagedFiles::discard(const std::string& dst) {
    for (auto it = items_.begin(); it != items_.end();) {
        if (it->dst != dst) { ++it; continue; }
        if (it->mode != Mode::Direct) {   // Direct 의 대상(장치 · FIFO)은 지우지 않는다
            std::error_code ec;
            fs::remove(it->tmp, ec);
            disarm(it->slot);
        }
        it = items_.erase(it);
    }
}

void StagedFiles::discardAll() {
    while (!items_.empty()) discard(items_.front().dst);
}

bool StagedFiles::has(const std::string& dst) const {
    return std::any_of(items_.begin(), items_.end(), [&](const Item& x) { return x.dst == dst; });
}

Mode StagedFiles::mode(const std::string& dst) const {
    for (const auto& x : items_)
        if (x.dst == dst) return x.mode;
    return Mode::Rename;
}

std::vector<Note> StagedFiles::takeNotes() {
    std::vector<Note> out;
    out.swap(notes_);
    return out;
}

// ── 주인 없는 임시 파일 ───────────────────────────────────────────────────────
int sweepStale(const std::string& dst, std::vector<Note>* notes) {
#ifdef _WIN32
    (void)dst;
    (void)notes;
    return 0;
#else
    if (dst.empty()) return 0;
    const Target t = resolveTarget(dst);   // 링크면 임시 파일은 따라간 파일 옆에 있다
    if (!t.err.empty() || t.special || t.dir) return 0;
    const std::string want = detail::nameHash(baseOf(t.path));
    const detail::Owner me = detail::self();
    // 대상 폴더 · 시스템 임시 폴더(InPlace 의 자리)
    std::vector<fs::path> dirs;
    const std::string d0 = dirPartOf(t.path);
    dirs.push_back(d0.empty() ? fs::path(".") : fs::path(d0));
    std::error_code ec;
    const fs::path td = fs::temp_directory_path(ec);
    if (!ec && !td.empty() && !fs::equivalent(td, dirs[0], ec)) dirs.push_back(td);
    std::vector<std::string> gone;
    for (const auto& d : dirs) {
        std::error_code ie;
        for (fs::directory_iterator itr(d, ie), end; !ie && itr != end; itr.increment(ie)) {
            const std::string n = itr->path().filename().string();
            detail::Owner o;
            std::string h;
            if (!detail::parseTempName(n, o, h) || h != want || o.host != me.host) continue;   // 다른 산출 · 다른 호스트(잴 수 없다)
            if (o.pid == me.pid && o.start == me.start) continue;                               // 이 프로세스의 것
            if (ownerAlive(o.pid, o.start)) continue;                                           // 산 프로세스의 것은 지우지 않는다
            struct stat lst;
            if (::lstat(itr->path().c_str(), &lst) != 0 || !S_ISREG(lst.st_mode)) continue;
            if (::unlink(itr->path().c_str()) == 0) gone.push_back(n);
        }
    }
    if (!gone.empty() && notes) {
        std::string list;
        for (size_t i = 0; i < gone.size() && i < 3; ++i) list += (i ? " · " : "") + gone[i];
        if (gone.size() > 3) list += " …";
        notes->push_back({false, "앞 실행이 끝나지 못하고 남긴 「" + dst + "」 의 임시 파일 " + std::to_string(gone.size()) +
                                     " 개를 지웠다(주인 프로세스가 없다): " + list});
    }
    return static_cast<int>(gone.size());
#endif
}

}  // namespace staged_write
}  // namespace KooRemapper
