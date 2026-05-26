# Commands

See [[index#KooRemapper — Knowledge Graph Index]] for the full grouped catalog.

This page is a flat alphabetical index of CLI subcommand nodes.

| Command | Source | Manual § |
|---------|--------|----------|
| [[commands/ale#ale — Lagrangian → ALE converter (§35)]] | [ale.cpp](../../src/commands/ale.cpp) | §35 |
| [[commands/assemble#assemble — multi-operation YAML composer (§39)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §39 |
| [[commands/battery#battery — battery mesh/control generator]] | [battery.cpp](../../src/commands/battery.cpp) | (no §) |
| [[commands/bend#bend — Kirchhoff plate bending (§13)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) + standalone | §13 |
| [[commands/boundary#boundary — boundary conditions (§27)]] | [load_boundary.cpp](../../src/commands/load_boundary.cpp) | §27 |
| [[commands/cnrb2solid#cnrb2solid — CNRB → solid conversion]] | [cnrb2solid.cpp](../../src/commands/cnrb2solid.cpp) | (no §) |
| [[commands/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]] | [contact.cpp](../../src/commands/contact.cpp) | §25 |
| [[commands/convert#convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)]] | [standalone_ops.cpp](../../src/commands/standalone_ops.cpp) | §16 |
| [[commands/database#database — DATABASE output control (§37)]] | [database.cpp](../../src/commands/database.cpp) | §37 |
| [[commands/disconnect#disconnect — node duplication — full / czm / mefem (§19)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §19 |
| [[commands/elform#elform — ELFORM remap (§18)]] | [standalone_ops.cpp](../../src/commands/standalone_ops.cpp) | §18 |
| [[commands/explicit#explicit — pure explicit restoration (§32)]] | [strip.cpp](../../src/commands/strip.cpp) | §32 |
| [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §15 |
| [[commands/generate#generate — YAML-driven mesh generation (§8)]] | [generator](../../src/generator/) | §8 |
| [[commands/iga#iga — IGA NURBS box generation (§20)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §20 |
| [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] | [implicit.cpp](../../src/commands/implicit.cpp) | §29 |
| [[commands/indent#indent — indent/emboss (§14)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §14 |
| [[commands/info#info — mesh statistics (§11)]] | [main.cpp](../../src/main.cpp) | §11 |
| [[commands/load#load — load application (§26)]] | [load_boundary.cpp](../../src/commands/load_boundary.cpp) | §26 |
| [[commands/map#map — HEX8 structured mesh mapping (§4)]] | [mapper](../../src/mapper/) | §4 |
| [[commands/matdb#matdb — material DB lookup + replacement (§24)]] | [matdb.cpp](../../src/commands/matdb.cpp) | §24 |
| [[commands/matswap#matswap — material bundle parameter swap (§23)]] | [matswap.cpp](../../src/commands/matswap.cpp) | §23 |
| [[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]] | [meshfix.cpp](../../src/commands/meshfix.cpp) | §40 |
| [[commands/modal#modal — natural frequency / modal analysis (§30)]] | [modal.cpp](../../src/commands/modal.cpp) | §30 |
| [[commands/offset#offset — shell offset → solid extrusion (§22)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §22 |
| [[commands/optimize#optimize — material-specific solver presets (§34)]] | [optimize.cpp](../../src/commands/optimize.cpp) | §34 |
| [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] | [main.cpp](../../src/main.cpp) (`runPrestress`) | §6 |
| [[commands/rbe#rbe — RBE constraint (§28)]] | [load_boundary.cpp](../../src/commands/load_boundary.cpp) | §28 |
| [[commands/refine#refine — 1:2 / 1:3 subdivision (§17)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §17 |
| [[commands/relax#relax — Dynamic Relaxation setup (§31)]] | [relax.cpp](../../src/commands/relax.cpp) | §31 |
| [[commands/restack#restack — layer restacking (§12)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §12 |
| [[commands/shellmap#shellmap — QUAD4 shell-based mapping (§5)]] | [ShellMapper.cpp](../../src/mapper/ShellMapper.cpp) | §5 |
| [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]] | [squeeze_assemble.cpp](../../src/commands/squeeze_assemble.cpp) | §7 |
| [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] | [stabilize.cpp](../../src/commands/stabilize.cpp) | §36 |
| [[commands/strain#strain — strain reporting (§10)]] | [main.cpp](../../src/main.cpp) | §10 |
| [[commands/strip#strip — keyword removal (§38)]] | [strip.cpp](../../src/commands/strip.cpp) | §38 |
| [[commands/unfold#unfold — bent mesh → flat (§9)]] | [ShellUnfolder.cpp](../../src/mapper/ShellUnfolder.cpp) | §9 |
| [[commands/warpage#warpage — warpage correction (§21)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §21 |
| [[commands/wrap#wrap — winding-tension prestress (§33)]] | [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | §33 |
