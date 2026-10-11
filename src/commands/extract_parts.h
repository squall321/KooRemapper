#pragma once
// 고른 파트만 뽑아 **돌아가는** 덱으로 쓰는 op — ID·고정폭·CRLF 를 보존한다
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/extract-parts]]

int runExtractParts(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
