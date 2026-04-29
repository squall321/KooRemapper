#pragma once
#include "analysis/StrainTensor.h"
#include <string>

namespace KooRemapper { class ConsoleOutput; }

// runMapping
//   bboxAlignMode: "" / "none" / "source" / "target"
//     - "source": rescale detail flat XYZ to match bent ijk neutral lengths
//                 (writes scaled flat to a temp file; *outScaledFlatPath
//                  receives the path so the caller's prestress chain can
//                  use it as reference). Detail mesh modified in memory too.
//     - "target": rescale bent XYZ to match detail XYZ (in memory only).
//                 Detail flat untouched, prestress reference is original flat.
//     - "none"/"" (default): no rescaling.
//   bboxAlignMaxDriftPct: reject scaling and abort if any axis ratio drifts
//                         beyond this percent. Safety net against accidentally
//                         applying bbox_align on grossly mismatched meshes.
//   outScaledFlatPath: (optional, source mode only) receives the temp file
//                      path the caller should use as prestress reference.
int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile,
               const KooRemapper::ConsoleOutput& console,
               bool useParallel = true,
               bool forcePositive = false,
               bool flipX = false, bool flipY = false, bool flipZ = false,
               const std::string& bboxAlignMode = "none",
               double bboxAlignMaxDriftPct = 2.0,
               std::string* outScaledFlatPath = nullptr);

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
