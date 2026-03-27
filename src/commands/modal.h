#pragma once
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runModal(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
