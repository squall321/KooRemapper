# LS-DYNA ELEMENT cards in KooRemapper

Stub.

## Topologies parsed

| Card | Internal type | Storage |
|------|---------------|---------|
| `*ELEMENT_SOLID` (HEX8) | `ElementType::HEX8` | [Mesh.cpp](../../src/core/Mesh.cpp) `elements` |
| `*ELEMENT_SOLID` (TET4, degenerate) | `ElementType::HEX8` (N5..N8 collapsed to N4) | same |
| `*ELEMENT_SHELL` (QUAD4) | `ElementType::QUAD4` | [ShellMesh.cpp](../../src/core/ShellMesh.cpp) |
| `*ELEMENT_SHELL` (TRIA3) | QUAD4 with N4==N3 (or N4==0) | same |

## Quadratic promotion

[[commands/convert#convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)]] promotes via `applyTet10Convert()` dispatched by the
`convertType` field. Mid-edge nodes are interned in `edgeMidNodeMap_` (member —
persists across calls so HEX20 / TET10 / QUAD8 share mid-side nodes consistently).

TRIA3 detection: `nodeIds[3] == nodeIds[2] || nodeIds[3] == 0`.

## Refinement

[[commands/refine#refine — 1:2 / 1:3 subdivision (§17)]] supports:
- QUAD4 / TRIA3 / HEX8 — 1:2 and 1:3 subdivision.
- TET4 — 1:2 only (stored as degenerate HEX8).

State is stored in `removedElementIds_` + `addedElements_` / `addedShellElements_` to
keep `writeOutput()` agnostic of the operation.

## IGA

`*ELEMENT_SOLID_NURBS_PATCH` is emitted by [[commands/iga#iga — IGA NURBS box generation (§20)]] into a per-PID
include file `<output>_iga_p<pid>.k`. See [[commands/iga#iga — IGA NURBS box generation (§20)]] for MID/SECID/MID
assignment rules (must differ from FE MID).

TODO: NPLANE/NTHICK semantics for shell mid-surface; HEX20 connectivity ordering.
