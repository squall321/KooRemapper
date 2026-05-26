#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/modal]]

namespace KooRemapper { class ConsoleOutput; }

int runModal(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
