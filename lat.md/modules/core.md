# Module: src/core/

Foundational types. Anything that talks geometry uses these.

| File | Role |
|------|------|
| [Vector3D.cpp](../../src/core/Vector3D.cpp) | 3D vector, `magnitude()` (not `length()`), arithmetic |
| [Node.cpp](../../src/core/Node.cpp) | mesh node — position accessed via `n.position.x` (getter) |
| [Element.cpp](../../src/core/Element.cpp) | 3D element (HEX8/TET4 — TET4 as degenerate HEX8 with `NUM_NODES==8`) |
| [ShellElement.h](../../include/core/ShellElement.h) | shell element (QUAD4/TRIA3) — header-only |
| [Mesh.cpp](../../src/core/Mesh.cpp) | nodes + 3D elements; `getNode(id)` (not `getNodeById`) |
| [ShellMesh.cpp](../../src/core/ShellMesh.cpp) | nodes + shell elements |
| [Matrix3x3.h](../../include/core/Matrix3x3.h) | 3×3 matrix, used by [[modules/analysis#Module: src/analysis/]] — header-only |
| [Platform.cpp](../../src/core/Platform.cpp) | platform-specific helpers |

## Element type enum

```
ElementType { HEX8, TET4, QUAD4, TRIA3 }
```

- HEX8 is the "main" 3D type. TET4 is stored as degenerate HEX8 (N5..N8 = N4).
- QUAD4 is the main shell type. TRIA3 is detected when
  `nodeIds[3] == nodeIds[2] || nodeIds[3] == 0`.

## API notes

These conventions appear in CLAUDE.md/memory because they have bitten contributors:

- `Vector3D::magnitude()` (not `length()`).
- `Node::position.x` (getter access).
- `Mesh::getNode(id)` (not `getNodeById`).
