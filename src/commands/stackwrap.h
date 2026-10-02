#pragma once
// 적층을 EI 중립축 기준으로 옮긴 뒤 기준 셸에 감는 op — shellmap 의 "축=0 이 중립면" 전제를 실제로 맞춘다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/stackwrap]]

int runStackWrap(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
