#pragma once
// 적층 층 구조를 모식도로 그리는 op — 평면을 고를 필요가 없고 중립축을 함께 긋는다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/stackdiagram]]

int runStackDiagram(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
