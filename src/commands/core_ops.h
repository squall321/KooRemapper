#pragma once
#include "analysis/StrainTensor.h"
#include <string>

namespace KooRemapper { class ConsoleOutput; }

int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile,
               const KooRemapper::ConsoleOutput& console,
               bool useParallel = true);

int runShellMapping(const std::string& bentShellFile, const std::string& flatFile,
                    const std::string& outputFile, double thickness,
                    const KooRemapper::ConsoleOutput& console);

int runGenerate(const std::string& type, const std::string& outputPrefix,
                int dimI, int dimJ, int dimK,
                const KooRemapper::ConsoleOutput& console);

int runStrain(const std::string& refFile, const std::string& defFile,
              const std::string& outputFile, const std::string& strainType,
              const KooRemapper::ConsoleOutput& console);

int runUnfold(const std::string& bentFile, const std::string& outputFile,
              const KooRemapper::ConsoleOutput& console);

int runPrestress(const std::string& refFile, const std::string& defFile,
                 const std::string& outputFile,
                 double E, double nu,
                 KooRemapper::StrainType strainType,
                 bool outputCSV,
                 const KooRemapper::ConsoleOutput& console);

int runInfo(const std::string& meshFile, const KooRemapper::ConsoleOutput& console);

int runGenerateBox(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);

int runGenerateVar(const std::string& configFile, const std::string& outputFile,
                   const std::string& refFile, bool noScale,
                   const KooRemapper::ConsoleOutput& console);
