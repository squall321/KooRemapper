#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/matdb]]

namespace KooRemapper { class ConsoleOutput; }

int runMatdb(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runMatdbList(const std::string& dbPath, KooRemapper::ConsoleOutput& console);
