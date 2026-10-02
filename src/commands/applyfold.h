#pragma once
// linkage-fit 이 적은 군별 변환을 큰 덱에 찍는 op — 조용히 빠지는 절점이 하나도 없어야 한다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/applyfold]]

int runApplyFold(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
