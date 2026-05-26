#pragma once
#include "cli/ConsoleOutput.h"
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

// ================================================================
// hfdamp - High-Frequency Damping generator
// Inserts *DAMPING_FREQUENCY_RANGE_DEFORM into a K-file.
//
// FLOW  = 1 / (2 * dt_target)
// FHIGH = FLOW * fhigh_ratio
// Targets frequencies corresponding to elements with dt <= dt_target.
// ================================================================

// Standalone command: KooRemapper hfdamp config.yaml
int runHFDamp(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);

struct HFDampConfig {
    double dtTarget     = 0.0;      // REQUIRED: target timestep [model time units]
    double cdamp        = 0.99;     // Fraction of critical damping (0 < cdamp <= 1)
    double fhighRatio   = 100.0;    // FHIGH = FLOW * fhigh_ratio  (10~300 recommended)
    std::string mode    = "global"; // "global" | "selective"
    double tssfac       = 0.9;      // Timestep safety factor for element dt estimate
};

// Core transform: inserts damping keyword(s) into raw K-file lines.
// maxSetId is updated if a new *SET_PART_LIST is created.
// Returns 0 on success, -1 on error (dtTarget not set, etc.)
int hfdamp_apply(std::vector<std::string>& lines,
                 const HFDampConfig& cfg,
                 int& maxSetId,
                 KooRemapper::ConsoleOutput& console);
