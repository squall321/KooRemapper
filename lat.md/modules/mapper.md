# Module: src/mapper/

Mesh-to-mesh mapping. The core problem: project the field of a deformed
"template" mesh onto a fresh structured target mesh.

| File | Role |
|------|------|
| [ParametricMapper.cpp](../../src/mapper/ParametricMapper.cpp) | arc-length parameterization (arc/width/thickness axis triple) |
| [FlatMeshGenerator.cpp](../../src/mapper/FlatMeshGenerator.cpp) | flat counterpart for unfolded mapping |
| [MeshRemapper.cpp](../../src/mapper/MeshRemapper.cpp) | applies the mapping back to a curved mesh |
| [EdgeInterpolator.cpp](../../src/mapper/EdgeInterpolator.cpp) | edge-based interpolation along arc |
| [FaceInterpolator.cpp](../../src/mapper/FaceInterpolator.cpp) | Coons-patch face interpolation |
| [ShellUnfolder.cpp](../../src/mapper/ShellUnfolder.cpp) | bent shell → flat |
| [ShellMapper.cpp](../../src/mapper/ShellMapper.cpp) | QUAD4 shell mapping driver |
| [UnstructuredMeshAnalyzer.cpp](../../src/mapper/UnstructuredMeshAnalyzer.cpp) | inspection / sanity checks |

## Axis-permutation invariant

`ParametricMapper`, `FlatMeshGenerator`, and `MeshRemapper` must agree on which
physical axis is `arc`, `width`, `thickness`. The legacy assumption
"`bent-i == arc`" is wrong for closed-loop meshes. See [[project_unfold_axis_perm]].

## Theory anchors

- [[theory/arc-length-param#Arc-length parameterization]] — actual algorithm in use.
- [[theory/coons-patch#Coons patch]] — face interpolation.
- [[theory/transfinite#Transfinite interpolation (Gordon-Hall)]] / [[theory/trilinear#Trilinear interpolation]] — implemented but currently unused.

## Cross-references

- [[commands/map#map — HEX8 structured mesh mapping (§4)]] — HEX8 mapping driver.
- [[commands/shellmap#shellmap — QUAD4 shell-based mapping (§5)]] — QUAD4 driver.
- [[commands/unfold#unfold — bent mesh → flat (§9)]] — bent → flat preprocessor.
