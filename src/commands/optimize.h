#pragma once
#include <string>
#include <vector>

namespace KooRemapper { class ConsoleOutput; }

struct OptimizeConfig {
    std::string mode;               // "rubber" (extendable later)
    double tssfac = 0.67;          // TSSFAC default for rubber
    std::vector<int> pids;         // target PIDs for CONTACT modification
    std::string analysisType;      // "explicit" / "implicit" / "" (auto-detect)
};

// Defined in main.cpp (bridge to anonymous-namespace ct_* helpers)
std::vector<std::string> opt_applyRubber(std::vector<std::string>& lines,
                                          const OptimizeConfig& cfg);

// Defined in optimize.cpp
int runOptimize(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
