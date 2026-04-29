#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runTetRemesh(const std::string& configPath,
                 const KooRemapper::ConsoleOutput& console);
