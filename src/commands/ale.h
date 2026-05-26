#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/ale]]

namespace KooRemapper { class ConsoleOutput; }

int runAle(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
