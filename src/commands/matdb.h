#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runMatdb(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runMatdbList(const std::string& dbPath, KooRemapper::ConsoleOutput& console);
