#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/squeeze]]

namespace KooRemapper { class ConsoleOutput; }

int runSqueeze(const std::string& meshFile, const std::string& configFile,
               const std::string& outputPrefix,
               const KooRemapper::ConsoleOutput& console);

int runAssemble(const std::string& configFile,
                const KooRemapper::ConsoleOutput& console);
