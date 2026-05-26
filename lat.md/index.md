# KooRemapper — Knowledge Graph Index

KooRemapper is a Windows C++ command-line toolchain for LS-DYNA mesh remapping,
prestress transfer, assembly composition, and explicit/implicit solver setup.

## Navigation

- [[architecture#Architecture]] — top-level system view
- [[modules/commands#Module: src/commands/]] — CLI command dispatch
- [[commands/index#Commands]] — full list of CLI subcommands
- [[theory/index#Theory Index]] — algorithmic foundations
- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] — LS-DYNA keyword cross-reference
- [[glossary#Glossary]] — domain terms

## Command catalog

(Mirrors the section numbering in [`docs/KooRemapper_Manual.md`](../docs/KooRemapper_Manual.md).)

### Mesh mapping (§4-5)
- [[commands/map#map — HEX8 structured mesh mapping (§4)]] — HEX8 structured mesh mapping
- [[commands/shellmap#shellmap — QUAD4 shell-based mapping (§5)]] — QUAD4 shell-driven mapping

### Stress & strain transfer (§6-7, §13-15, §33)
- [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] — reference → deformed strain/stress + dynain
- [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]] — interference-fit compression + reverse prestress
- [[commands/bend#bend — Kirchhoff plate bending (§13)]] — Kirchhoff plate bending field
- [[commands/indent#indent — indent/emboss (§14)]] — axisymmetric indent/emboss profile
- [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]] — dihedral curvature → plastic EPS
- [[commands/wrap#wrap — winding-tension prestress (§33)]] — winding-tension prestress

### Mesh generation & topology (§8-11, §16-22, §40)
- [[commands/generate#generate — YAML-driven mesh generation (§8)]] — YAML-driven mesh generator
- [[commands/unfold#unfold — bent mesh → flat (§9)]] — bend → flat
- [[commands/strain#strain — strain reporting (§10)]] — strain reporting
- [[commands/info#info — mesh statistics (§11)]] — mesh statistics
- [[commands/convert#convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)]] — TET10/HEX20/QUAD8/TRIA6 promotion
- [[commands/refine#refine — 1:2 / 1:3 subdivision (§17)]] — 1:2 / 1:3 element subdivision
- [[commands/elform#elform — ELFORM remap (§18)]] — ELFORM remap
- [[commands/disconnect#disconnect — node duplication — full / czm / mefem (§19)]] — node duplication (full/CZM/MEFEM)
- [[commands/iga#iga — IGA NURBS box generation (§20)]] — IGA NURBS box generation
- [[commands/warpage#warpage — warpage correction (§21)]] — warpage correction
- [[commands/offset#offset — shell offset → solid extrusion (§22)]] — shell offset → solid extrusion
- [[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]] — TET4 Gmsh-based remesh

### Material & contact (§23-25)
- [[commands/matswap#matswap — material bundle parameter swap (§23)]] — bundle parameter swap
- [[commands/matdb#matdb — material DB lookup + replacement (§24)]] — material DB lookup + replacement
- [[commands/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]] — *CONTACT_* analyze / create / convert / modify / remove / detect

### Loads & BCs (§12, §26-28)
- [[commands/restack#restack — layer restacking (§12)]] — layer restacking
- [[commands/load#load — load application (§26)]] — load application
- [[commands/boundary#boundary — boundary conditions (§27)]] — SPC etc.
- [[commands/rbe#rbe — RBE constraint (§28)]] — RBE constraint

### Solver mode conversion (§29-32, §35-37)
- [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] — Explicit → Implicit (8-level)
- [[commands/modal#modal — natural frequency / modal analysis (§30)]] — natural-frequency (eigenvalue) setup
- [[commands/relax#relax — Dynamic Relaxation setup (§31)]] — Dynamic Relaxation (5-level)
- [[commands/explicit#explicit — pure explicit restoration (§32)]] — explicit restoration
- [[commands/ale#ale — Lagrangian → ALE converter (§35)]] — Lagrangian → ALE (14 presets)
- [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] — explicit stabilization (12-level)
- [[commands/database#database — DATABASE output control (§37)]] — DATABASE output cards
- [[commands/strip#strip — keyword removal (§38)]] — keyword stripping

### Orchestration (§39)
- [[commands/assemble#assemble — multi-operation YAML composer (§39)]] — multi-operation YAML composer

### Domain workflows
- [[commands/battery#battery — battery mesh/control generator]] — battery mesh/control generator
- [[commands/optimize#optimize — material-specific solver presets (§34)]] — material-specific solver presets

## Source-module nodes

| Module | Purpose |
|--------|---------|
| [[modules/analysis#Module: src/analysis/]] | strain/stress/material model |
| [[modules/assembly#Module: src/assembly/]] | `ModelAssembler` + operation pipeline |
| [[modules/battery#Module: src/battery/]] | battery domain helpers |
| [[modules/cli#Module: src/cli/]] | argument parsing / console output |
| [[modules/commands#Module: src/commands/]] | per-command entry points (`runXxx`) |
| [[modules/core#Module: src/core/]] | `Mesh`, `Element`, `Node`, `Vector3D` |
| [[modules/generator#Module: src/generator/]] | mesh generation (variable density, curves) |
| [[modules/grid#Module: src/grid/]] | structured grid extraction |
| [[modules/mapper#Module: src/mapper/]] | parametric mapping (`Edge/Face/ParametricMapper`) |
| [[modules/parser#Module: src/parser/]] | LS-DYNA keyword I/O (`KFileReader/Writer`, dynain) |
| [[modules/remesh#Module: src/remesh/]] | local-improve / TetGen / patch orchestration |
| [[modules/squeeze#Module: src/squeeze/]] | squeeze config reader |
| [[modules/util#Module: src/util/]] | logging, timer, spatial hash, validator |
| [[modules/validation#Module: src/validation/]] | element quality, intersection, MAT cards |

## Theory nodes

See [[theory/index#Theory Index]] for the algorithmic spine
(mirrors `docs/KooRemapper_Theory_Document.md`).

## LS-DYNA references

See [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] for the master keyword → line index, then per-family
nodes [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]], [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]], [[lsdyna/ale#ALE keywords in KooRemapper]], [[lsdyna/eos#LS-DYNA EOS (equation of state) in KooRemapper]],
[[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]], [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]], [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]].
