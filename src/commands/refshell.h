#pragma once
// 2D 곡선을 폭 방향으로 쓸어 QUAD4 기준 셸 덱을 만드는 op — shellmap 의 기준면 공급원.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/refshell]]

int runRefShell(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
