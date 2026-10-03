#pragma once
// 자유면만 뽑아 직교투영·깊이정렬로 그리는 op — 전체 와이어프레임은 검은 덩어리가 된다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/surfview]]

int runSurfView(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
