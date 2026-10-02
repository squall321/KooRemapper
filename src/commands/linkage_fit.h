#pragma once
// 접힌 덱에서 군별 강체변환(힌지 축·각·피벗)을 역산하는 op — 피벗 산포를 반드시 함께 보고한다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/linkage-fit]]

int runLinkageFit(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
