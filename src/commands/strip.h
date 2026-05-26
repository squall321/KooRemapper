#pragma once
// =============================================================
// strip.h — KooRemapper strip command
// =============================================================
// Strip specified keyword blocks from an LS-DYNA K-file.
// Useful for debugging: remove bulky data (*NODE, *ELEMENT_*, etc.)
// to compare only option/control keywords.
//
// Usage:
//   KooRemapper strip config.yaml
//
// YAML:
//   model: input.k
//   output: input_stripped.k
//   keywords:
//     - "*NODE"
//     - "*ELEMENT_SOLID"
//     - "*INITIAL_STRESS_SOLID"
// =============================================================

#include "cli/ConsoleOutput.h"
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/strip]]

int runStrip(const std::string& yamlFile,
             KooRemapper::ConsoleOutput& console);
