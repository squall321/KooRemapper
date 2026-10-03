#pragma once
// 메시를 평면으로 잘라 요소 다각형을 내는 op — 그림의 엔진. 모서리∩평면이라 거짓말할 경로가 없다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/section]]

int runSection(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
