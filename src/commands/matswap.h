#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runMatswap(const std::string& modelFile, const std::string& bundleFile,
               int targetPid, const std::string& outputFile,
               KooRemapper::ConsoleOutput& console);

int runMatswapYaml(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
