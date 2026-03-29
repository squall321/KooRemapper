#pragma once
#include <string>

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
