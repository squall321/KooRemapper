#pragma once
#include "cli/ConsoleOutput.h"

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/meshfix]]

// Part-level TET4 remesh via external Gmsh subprocess.
// Requires dist/gmsh/gmsh.exe or dist/gmsh-<ver>/gmsh.exe next to KooRemapper.exe.
int runMeshFix(const char* configPath, KooRemapper::ConsoleOutput& console);
