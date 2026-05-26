#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/implicit]]

namespace KooRemapper { class ConsoleOutput; }

int runImplicit(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runExplicit(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
