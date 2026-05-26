#pragma once
// =============================================================
// battery.h — KooRemapper battery command
// =============================================================
// Generate LS-DYNA K-files for battery cell models.
//
// Usage:
//   KooRemapper battery config.yaml
//
// Supported model types:
//   stacked: Z-stacked unit cells (Phase 1 + 2)
//   wound:   Wound jellyroll (flat mode only, Phase 1)
// =============================================================

#include "cli/ConsoleOutput.h"
#include "battery/BatteryConfig.h"
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/battery]]

// Standalone command entry point
int runBattery(const std::string& yamlFile,
               KooRemapper::ConsoleOutput& console);

// Parse a BatteryConfig from YAML file
BatteryConfig parseBatteryConfig(const std::string& yamlFile);

// Generate a single K-file for the given config
// Returns output file path written, or "" on error
std::string generateBatteryKFile(const BatteryConfig& cfg,
                                  KooRemapper::ConsoleOutput& console);
