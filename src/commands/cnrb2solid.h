#pragma once
#include "cli/ConsoleOutput.h"
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cnrb2solid]]

// Standalone: KooRemapper cnrb2solid config.yaml
int runCnrb2Solid(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);

// Core transform: operates on a raw K-file line buffer.
// maxNodeId/maxElemId/maxSecId/maxMatId/maxSetId/maxPartId are updated in place.
struct Cnrb2SolidConfig {
    std::vector<int> targetPids;   // empty = all CNRBs
    double E             = 200000.0;
    double PR            = 0.3;
    double RHO           = 7.85e-9;
    double radiusScale   = 0.999;
    int    numCircumNodes = 0;     // 0 = auto
    double innerRadiusRatio = 0.3;
    std::string axisDirection = "auto"; // auto|x|y|z
    double zTolerance    = 0.1;
    double rTolerance    = 0.5;
    // bolt head
    double headOffsetR   = 0.0;    // 0 = no head
    double headThickness = 2.0;
    std::string headPosition = "auto"; // auto|top|bottom|none
};

// Returns number of CNRBs converted, or -1 on error.
// `maxContactId` — 덱(과 인클루드)의 기존 `*CONTACT_*_ID` CID 최대값. 새 tied 접촉의 CID 를 그 위로 낸다.
int cnrb2solid_convert(std::vector<std::string>& lines,
                       const Cnrb2SolidConfig& cfg,
                       int& maxNodeId, int& maxElemId,
                       int& maxSecId,  int& maxMatId,
                       int& maxSetId,  int& maxPartId,
                       int& maxContactId,
                       KooRemapper::ConsoleOutput& console);
