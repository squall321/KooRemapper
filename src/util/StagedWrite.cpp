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
    const size_t sep = dst.find_last_of("/\\");
    const std::string dir = sep == std::string::npos ? std::string() : dst.substr(0, sep + 1);
    const std::string base = sep == std::string::npos ? dst : dst.substr(sep + 1);
    // 짧은 이름 — 산출 이름 길이와 무관하다(예전 `.<이름>.kr_tmp_<시각>_<n>` 은 30 글자를 더해 NAME_MAX 가까운 이름이 끝에서 실패했다)
    const detail::Owner me = detail::self();
    for (int k = 0; k < 100; ++k) {
        const std::string t = dir + detail::tempBaseName(me, ++g_serial, base, suffix);
        std::error_code ec;
        if (std::filesystem::exists(t, ec) || ec) continue;
        // 신호 때 지울 경로로 먼저 적는다 — 이 이름은 이 프로세스만 만든다(없을 때 unlink 는 아무것도 지우지 않는다)
        items_.push_back({dst, t, arm(t)});
        writePath = t;
        return true;
    }
    why = "임시 파일 이름을 잡지 못했다";
    return false;
}

bool StagedFiles::writeText(const std::string& dst, const std::string& text, std::string& why) {
    std::string path;
    if (!reserve(dst, "", path, why)) return false;
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { why = std::strerror(errno); return false; }
    const bool wrote = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    const bool closed = std::fclose(f) == 0;
    if (!wrote || !closed) why = "쓰지 못했다";
    return wrote && closed;
}

bool StagedFiles::commit(const std::string& dst, std::string& why) {
    auto it = std::find_if(items_.begin(), items_.end(), [&](const Item& x) { return x.dst == dst; });
    if (it == items_.end()) { why = "바꿔 넣을 임시 파일이 없다"; return false; }
    std::error_code ec;
    std::filesystem::rename(it->tmp, dst, ec);
    if (ec) { why = ec.message(); return false; }
    disarm(it->slot);
    items_.erase(it);
    return true;
}

void StagedFiles::discard(const std::string& dst) {
    for (auto it = items_.begin(); it != items_.end();) {
        if (it->dst != dst) { ++it; continue; }
        std::error_code ec;
        std::filesystem::remove(it->tmp, ec);
        disarm(it->slot);
        it = items_.erase(it);
    }
}

void StagedFiles::discardAll() {
    while (!items_.empty()) discard(items_.front().dst);
}

// ── 주인 없는 임시 파일 ───────────────────────────────────────────────────────
int sweepStale(const std::string& dst, std::vector<Note>* notes) {
#ifdef _WIN32
    (void)dst;
    (void)notes;
    return 0;
#else
    if (dst.empty()) return 0;
    const size_t sep = dst.find_last_of('/');
    const std::string dir = sep == std::string::npos ? std::string(".") : dst.substr(0, sep + 1);
    const std::string want = detail::nameHash(sep == std::string::npos ? dst : dst.substr(sep + 1));
    const detail::Owner me = detail::self();
    std::vector<std::string> gone;
    std::error_code ec;
    for (fs::directory_iterator itr(dir, ec), end; !ec && itr != end; itr.increment(ec)) {
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
