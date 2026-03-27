#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runImplicit(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runExplicit(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
