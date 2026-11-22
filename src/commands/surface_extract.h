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
//   --output-pid N    PID of the emitted shell part (default: 1) — 솔리드 덱(인클루드까지)에 이미 있는 번호면 rc 1.
//                     새 번호에 *PART 와 *SECTION_SHELL(ELFORM 2 · NIP 2 · 새 SECID · MID 는 셸을 뽑은 솔리드 파트의 것)을 쓴다
//   --thickness T     그 *SECTION_SHELL 의 두께 T1~T4 — 새 번호면 필수(없으면 rc 1 · 2026-11-22 사용자 결정)
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
    double thickness = 0.0;       // 새 셸 파트의 *SECTION_SHELL 두께 — 0 이면 「없다」(새 번호면 rc 1)
    bool midSurface = false;      // average top↔bottom node positions → midsurface shells
};

int runExtractSurface(const std::string& solidFile,
                      const std::string& outputFile,
                      const ExtractSurfaceOptions& opts,
                      KooRemapper::ConsoleOutput& console);
