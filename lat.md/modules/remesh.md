# Module: src/remesh/

Local-quality and global remeshing.

| File | Role |
|------|------|
| [RemeshOrchestrator.cpp](../../src/remesh/RemeshOrchestrator.cpp) | top-level controller |
| [PatchExtractor.cpp](../../src/remesh/PatchExtractor.cpp) | identifies bad-element neighborhoods |
| [LocalImproveRemesher.cpp](../../src/remesh/LocalImproveRemesher.cpp) | edge/face flips, smoothing |
| [TetGenRemesher.cpp](../../src/remesh/TetGenRemesher.cpp) | TetGen wrapper for tet remesh |

## meshfix command

[[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]] is the user-facing entry. It uses Gmsh for full remesh and
the local improvers for per-component bad-element polish (see recent commits
"polish pass — per-component bad-element patch remesh").

## Theory

- Scaled Jacobian quality criterion: see [[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]].
- Adaptive size field for thin solids — `geomThin = pure Gmsh` is optimal
  (commit `f7036a6`).

TODO: patch boundary preservation rules; thin-field guard logic.
