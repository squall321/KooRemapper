#pragma once
// =============================================================
// surface_extract.h — KooRemapper extract-surface command
// =============================================================
// Extract the free (outer) surface of a solid HEX8/TET4 mesh as
// QUAD4 *ELEMENT_SHELL. Free face = a face shared by exactly one
// element (interior faces appear in exactly two elements and are
// dropped).
//
// Usage:
//   KooRemapper extract-surface <solid.k> <output_shell.k> [options]
//
// Options:
//   --pid N           filter by PID (default: all parts)
//   --face top|bottom|all
//                     directional filter using face normal sign on
//                     +Z (default: all)
//   --output-pid N    PID of the emitted shell part (default: 1)
//
// See examples/replace_test/Q8_Display_Bent/ for the original use
// case (Simcenter unstructured HEX8 → shellmap reference).
// =============================================================

#include "cli/ConsoleOutput.h"
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/extract-surface]]

struct ExtractSurfaceOptions {
    int filterPid = 0;            // 0 = all parts
    std::string face = "all";     // top | bottom | all (ignored when midSurface=true)
    int outputPid = 1;            // PID for emitted shell part
    bool midSurface = false;      // average top↔bottom node positions → midsurface shells
};

int runExtractSurface(const std::string& solidFile,
                      const std::string& outputFile,
                      const ExtractSurfaceOptions& opts,
                      KooRemapper::ConsoleOutput& console);
