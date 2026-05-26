#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

namespace KooRemapper { class ConsoleOutput; }

int runTetRemesh(const std::string& configPath,
                 const KooRemapper::ConsoleOutput& console);
