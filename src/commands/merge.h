#pragma once
// =============================================================
// merge.h — KooRemapper merge command
// =============================================================
// Merge multiple stacked solid layers into one homogenized layer.
// Supports Voigt/Reuss/VRH rule-of-mixtures for material properties.
//
// Material types handled:
//   MAT_ELASTIC (001)                → direct E, nu, rho
//   MAT_PIECEWISE_LINEAR (024)       → elastic E, nu, rho
//   MAT_GENERAL_VISCOELASTIC (076)   → fully-relaxed G∞, K → E∞, nu∞
//   MAT_RIGID (020)                  → E, nu, rho
//
// CTE: mixed via volume-weighted average if MAT_ADD_THERMAL_EXPANSION present.
//
// Usage:
//   KooRemapper merge config.yaml
//
// YAML:
//   model: input.k
//   output: merged.k
//   direction: z              # stacking direction (x/y/z, default z)
//   method: vrh               # voigt / reuss / vrh (default)
//   merge:
//     - pids: [1, 2, 3]
//       name: "Homogenized_Stack_A"
//     - pids: [4, 5]
//       name: "Stack_B"
// =============================================================

#include "cli/ConsoleOutput.h"
#include <string>

int runMerge(const std::string& yamlFile,
             KooRemapper::ConsoleOutput& console);
