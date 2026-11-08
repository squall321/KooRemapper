// 주 덱 폴더 기준 상대 경로(RelPath.h) — std::filesystem 의 어휘적 셈만 쓴다(파일을 열지 않는다 · 링크를 풀지 않는다)
#include "util/RelPath.h"

#include <filesystem>
#include <system_error>

namespace KooRemapper {
namespace util {

std::string relpathOf(const std::string& path, const std::string& dir) {
    namespace fs = std::filesystem;
    std::error_code ec;
    const fs::path a = fs::absolute(path, ec).lexically_normal();
    fs::path b = fs::absolute(dir.empty() ? std::string(".") : dir, ec).lexically_normal();
    // `.` 은 끝 `/` 를 남긴다("/cwd/"). libstdc++ 는 LWG 3096 대로 그 빈 끝을 무시하지만(같은 값) 표준 라이브러리마다 다를 수 있어 뗀다
    if (!b.has_filename() && b.has_relative_path()) b = b.parent_path();
    const fs::path r = a.lexically_relative(b);
    return r.empty() ? a.generic_string() : r.generic_string();
}

}  // namespace util
}  // namespace KooRemapper
