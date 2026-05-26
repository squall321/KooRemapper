#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/load]]
//   @lat: [[commands/boundary]]
//   @lat: [[commands/rbe]]

namespace KooRemapper { class ConsoleOutput; }

int runLoad(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runBoundary(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRbe(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
