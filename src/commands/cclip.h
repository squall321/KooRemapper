#pragma once
// C-clip(스프링 접점) 생성 op — 육면체 파트를 F-δ 캘리브레이션된 C형 쉘 스트립(눌린 상태+초기응력)으로 치환.
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cclip]]

int runCclip(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
