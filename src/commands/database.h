#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/database]]

namespace KooRemapper { class ConsoleOutput; }

int runDatabase(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
