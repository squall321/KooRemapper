// 보고 JSON 에 싣는 글자를 바른 UTF-8 로 고치는 공용 함수의 구현 — 깨진 바이트는 U+FFFD
#include "util/Utf8.h"

#include <cstdint>

namespace KooRemapper {
namespace util {

std::string validUtf8(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    size_t i = 0;
    while (i < s.size()) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) { out += static_cast<char>(c); ++i; continue; }
        size_t n = 0;
        uint32_t cp = 0;
        if ((c & 0xE0) == 0xC0) { n = 1; cp = c & 0x1Fu; }
        else if ((c & 0xF0) == 0xE0) { n = 2; cp = c & 0x0Fu; }
        else if ((c & 0xF8) == 0xF0) { n = 3; cp = c & 0x07u; }
        bool ok = n > 0;
        for (size_t k = 1; ok && k <= n; ++k) {
            if (i + k >= s.size() || (static_cast<unsigned char>(s[i + k]) & 0xC0) != 0x80) ok = false;
            else cp = (cp << 6) | (static_cast<unsigned char>(s[i + k]) & 0x3Fu);
        }
        if (ok && ((n == 1 && cp < 0x80) || (n == 2 && cp < 0x800) || (n == 3 && cp < 0x10000) || (cp >= 0xD800 && cp <= 0xDFFF) || cp > 0x10FFFF))
            ok = false;
        if (ok) { out.append(s, i, n + 1); i += n + 1; }
        else { out += "\xEF\xBF\xBD"; ++i; }
    }
    return out;
}

}  // namespace util
}  // namespace KooRemapper
