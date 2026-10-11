#pragma once
// 아무도 참조하지 않는 절점을 **키워드별 필드 해석**으로 찾아 보고하고(기본) 지우는 op
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cleanup-nodes]]

int runCleanupNodes(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
