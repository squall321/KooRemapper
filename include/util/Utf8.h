// 보고 JSON 에 싣는 글자를 바른 UTF-8 로 고치는 공용 함수(이월 적용 · extract-parts 의 보고)
#pragma once

#include <string>

namespace KooRemapper {
namespace util {

// 깨진 바이트(넘친 꼴 · 서로게이트 · U+10FFFF 위 · 잘린 꼴)를 U+FFFD 로 바꾼다(RFC 3629). 계획 · 덱 줄 · 경로(CP949 인클루드 이름 등)
// 어디서 온 글자든 보고가 엄격한 리더에서 깨지지 않게(이월 적용 54ac559 — extract-parts 보고가 두 번째 소비자다, 2026-11-08)
std::string validUtf8(const std::string& s);

}  // namespace util
}  // namespace KooRemapper
