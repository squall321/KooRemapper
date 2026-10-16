#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

namespace KooRemapper { class ConsoleOutput; }

int runWrap(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runUpdate(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRestack(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runBend(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runIndent(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runFormstrain(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runConvert(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRefine(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runElform(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runDisconnect(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runIga(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runWarpage(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runOffset(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
// StepForge 조각을 기존 덱에 넣는다(경계 합의 §3-3 — 우리 몫)
int runCadSolidMerge(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
