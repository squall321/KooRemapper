#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runDatabase(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
