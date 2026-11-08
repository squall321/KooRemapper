// 임시 파일 + 바꿔 넣기 공용 도우미의 구현 — 같은 폴더의 임시 이름을 잡고 · 쓰고 · 바꿔 넣고 · 이번 실행이 만든 것만 지운다
#include "util/StagedWrite.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <system_error>

namespace KooRemapper {
namespace staged_write {

StagedFiles::~StagedFiles() { discardAll(); }

bool StagedFiles::reserve(const std::string& dst, const std::string& suffix, std::string& writePath, std::string& why) {
    static unsigned serial = 0;
    discard(dst);   // 같은 자리를 다시 잡으면 앞 임시 파일은 버린다
    const size_t sep = dst.find_last_of("/\\");
    const std::string dir = sep == std::string::npos ? std::string() : dst.substr(0, sep + 1);
    const std::string base = sep == std::string::npos ? dst : dst.substr(sep + 1);
    const std::string stamp = std::to_string((long long)std::chrono::steady_clock::now().time_since_epoch().count());
    for (int k = 0; k < 100; ++k) {
        const std::string t = dir + "." + base + ".kr_tmp_" + stamp + "_" + std::to_string(++serial) + suffix;
        std::error_code ec;
        if (std::filesystem::exists(t, ec) || ec) continue;
        items_.push_back({dst, t});
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
    items_.erase(it);
    return true;
}

void StagedFiles::discard(const std::string& dst) {
    for (auto it = items_.begin(); it != items_.end();) {
        if (it->dst != dst) { ++it; continue; }
        std::error_code ec;
        std::filesystem::remove(it->tmp, ec);
        it = items_.erase(it);
    }
}

void StagedFiles::discardAll() {
    while (!items_.empty()) discard(items_.front().dst);
}

}  // namespace staged_write
}  // namespace KooRemapper
