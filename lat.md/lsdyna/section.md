# LS-DYNA SECTION cards in KooRemapper

Stub.

| Section | Linked from |
|---------|-------------|
| `*SECTION_SOLID` | parsed by [KFileReader.cpp](../../src/parser/KFileReader.cpp); ELFORM read into `solidSectionElforms_` map in [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) |
| `*SECTION_SHELL` | parsed + thickness (T1) stored in `shellSectionElforms_`; thickness priority — YAML `shell_thickness` overrides K-file value |
| `*SECTION_SOLID_PERI` | emitted by [[commands/disconnect#disconnect — node duplication — full / czm / mefem (§19)]] full mode (ELFORM=48, DR=1.01) |

## ELFORM aliases

[[commands/elform#elform — ELFORM remap (§18)]] accepts human-readable aliases; resolution in
[standalone_ops.cpp](../../src/commands/standalone_ops.cpp) / [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp).

TODO: enumerate the alias table (solid: hex/tet/mat-flow; shell: belytschko/hughes-liu/…).

## SECID sharing

Operations that mutate ELFORM check whether the SECID is shared across parts.
If so, a **new SECID** is created and only the targeted parts repointed —
see [[commands/ale#ale — Lagrangian → ALE converter (§35)]], [[commands/convert#convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)]].
