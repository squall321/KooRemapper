#pragma once
// 적층 단면의 EI 가중 중립축을 계산해 보고하는 op — shellmap 의 "z=0 이 중립축" 전제를 수치로 확인한다.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/neutralaxis]]

// axis: 0=x, 1=y, 2=z
int runNeutralAxis(const std::string& meshFile, int axis, KooRemapper::ConsoleOutput& console);
