#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runLoad(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runBoundary(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRbe(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
