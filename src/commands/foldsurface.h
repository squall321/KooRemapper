#pragma once
// 접힘 곡면(평면 elastica)의 중심선을 푸는 op — 정점 곡률을 고정하고 B 를 연속법+이분법으로 찾는다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/foldsurface]]

int runFoldSurface(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
