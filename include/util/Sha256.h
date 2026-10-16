// SHA-256(FIPS 180-4) — 조각 대응표의 `coord_sha` 를 StepForge 와 같은 값으로 재려고 둔다
#pragma once

#include <string>

namespace KooRemapper {
namespace util {

// 바이트열의 SHA-256 을 소문자 16진 64자로 돌려준다.
// 외부 라이브러리를 쓰지 않는다 — 리눅스 바이너리는 glibc 호환 빌드 상자에서 굽는다(OpenSSL 의존을 더하지 않는다).
std::string sha256Hex(const std::string& data);

}  // namespace util
}  // namespace KooRemapper
