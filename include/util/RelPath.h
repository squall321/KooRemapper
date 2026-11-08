// 주 덱 폴더 기준 상대 경로를 내는 공용 함수 — 이월 적용의 인클루드 목록과 assemble battery 의 *INCLUDE 이름이 같이 쓴다
#pragma once

#include <string>

namespace KooRemapper {
namespace util {

// 왜 한 곳인가 (2026-11-08). 이월 적용(CarryoverApply · 판 2 `deck.includes` 의 relpath)과 assemble 의 battery `*INCLUDE` 이름
// (ModelAssembler)이 같은 셈을 따로 두었다(11-07 의 두 번째 소비자). 규칙이 갈리면 같은 파일이 두 이름으로 적힌다.
//
// `path` 를 `dir`(빈 문자열이면 작업 폴더) 기준 상대 경로로 — 둘 다 절대 경로로 펴고 `.` · `..` · 겹친 `/` 를 정규화한 뒤 견준다.
// 심볼릭 링크는 풀지 않는다(StepForge `os.path.relpath(p, main_dir)` 와 같은 꼴). 구분자는 `/`. 상대 경로를 낼 수 없으면
// (윈도우의 다른 드라이브) 정규화한 절대 경로를 낸다.
std::string relpathOf(const std::string& path, const std::string& dir);

}  // namespace util
}  // namespace KooRemapper
