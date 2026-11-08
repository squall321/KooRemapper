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
// 위가 쓸 덱 경로(`<output><tier>_phase{1|2}.k`) — 쓰기 전에 견주려고 따로 낸다(2026-11-07)
std::string batteryKFilePath(const BatteryConfig& cfg);
// 위를 둘로 — 덱 글자만 짓고(파일은 쓰지 않는다 · `what` 은 「Generating:」 줄의 이름) · 지은 글자를 쓴다(2026-11-08). assemble 의
// battery 가 그 사이에서 번호를 옮긴다(bat::shiftBatteryIds). 실패면 false(까닭은 console)
bool buildBatteryKFileText(const BatteryConfig& cfg, KooRemapper::ConsoleOutput& console, const std::string& what,
                           std::string& text);
bool writeBatteryKFileText(const std::string& path, const std::string& text, KooRemapper::ConsoleOutput& console);
// use_dynain: true 인데 dynain_file 이 비어 *INCLUDE_DYNAIN 을 쓰지 않는 덱이면 그 사실을 적은 경고 문장, 아니면 ""(2026-11-08) —
// 홑 실행 · assemble 의 battery · 자동 이름이 없는 batch 조합이 낸다(batch 의 첫 phase 는 이어지는 사슬의 머리라 내지 않는다)
std::string batteryDynainSkipWarning(const BatteryConfig& cfg);
