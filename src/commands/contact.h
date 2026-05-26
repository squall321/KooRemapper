#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/contact]]

namespace KooRemapper { class ConsoleOutput; }

int runContact(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
