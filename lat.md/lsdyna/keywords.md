# LS-DYNA Keyword Cross-Reference

Master index of LS-DYNA keywords that KooRemapper either **parses**, **emits**, or
**references** in its commands. Line numbers point to the canonical card definition
in the LS-DYNA manual volumes shipped under [`docs/LSDyna/`](../../docs/LSDyna/).

Column legend:
- **Vol/Line** — clickable jump to the keyword's definition page.
- **Used by** — KooRemapper commands or modules.

> Volumes are very large (Vol_I ≈ 257k lines, Vol_II ≈ 164k, Vol_III ≈ 52k).
> The first hit per keyword is the canonical definition; later hits are usage examples.

## *MAT_* (material cards)

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*MAT_ELASTIC` | [Vol_II.txt:9390](../../docs/LSDyna/Vol_II.txt#L9390) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]], [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] |
| `*MAT_PIECEWISE_LINEAR_PLASTICITY` (`MAT_024`) | [Vol_II.txt:9672](../../docs/LSDyna/Vol_II.txt#L9672) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]], [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]] |
| `*MAT_PLASTIC_KINEMATIC` | [Vol_II.txt:9678](../../docs/LSDyna/Vol_II.txt#L9678) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]] |
| `*MAT_RIGID` | [Vol_II.txt:9747](../../docs/LSDyna/Vol_II.txt#L9747) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]] |
| `*MAT_VISCOELASTIC` | [Vol_II.txt:9940](../../docs/LSDyna/Vol_II.txt#L9940) | [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]], [[theory/viscoelastic#Viscoelastic (MATVISCOELASTIC)]] |
| `*MAT_NULL` | [Vol_II.txt:9644](../../docs/LSDyna/Vol_II.txt#L9644) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (gas/liquid) |
| `*MAT_VACUUM` | [Vol_II.txt:9932](../../docs/LSDyna/Vol_II.txt#L9932) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (vacuum preset) |
| `*MAT_HIGH_EXPLOSIVE_BURN` (alias `*MAT_HE_BURN`) | [Vol_II.txt:9492](../../docs/LSDyna/Vol_II.txt#L9492) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (TNT/C4) |
| `*MAT_ADD_EROSION` | [Vol_II.txt:9206](../../docs/LSDyna/Vol_II.txt#L9206) | manual reference — KooRemapper **never** emits ERODE (see [[../feedback_no_erode]]) |
| `*MAT_ADD_THERMAL_EXPANSION` | [Vol_II.txt:9217](../../docs/LSDyna/Vol_II.txt#L9217) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]] (thermal), [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]] (method 2) |
| `*MAT_THERMAL_ISOTROPIC` | [Vol_II.txt:5660](../../docs/LSDyna/Vol_II.txt#L5660) | [[commands/matdb#matdb — material DB lookup + replacement (§24)]] (thermal) |

Detail page: [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]].

## *EOS_* (equation of state)

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*EOS_LINEAR_POLYNOMIAL` | [Vol_I.txt:29108](../../docs/LSDyna/Vol_I.txt#L29108) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (gas) |
| `*EOS_IDEAL_GAS` | [Vol_I.txt:29109](../../docs/LSDyna/Vol_I.txt#L29109) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |
| `*EOS_GRUNEISEN` | [Vol_II.txt:605](../../docs/LSDyna/Vol_II.txt#L605) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (liquid) |
| `*EOS_JWL` | [Vol_II.txt:601](../../docs/LSDyna/Vol_II.txt#L601) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (explosive) |

Detail page: [[lsdyna/eos#LS-DYNA EOS (equation of state) in KooRemapper]].

## *CONTROL_*

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*CONTROL_TERMINATION` | [Vol_I.txt:18326](../../docs/LSDyna/Vol_I.txt#L18326) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]], [[commands/modal#modal — natural frequency / modal analysis (§30)]], [[commands/relax#relax — Dynamic Relaxation setup (§31)]] |
| `*CONTROL_TIMESTEP` | [Vol_I.txt:78601](../../docs/LSDyna/Vol_I.txt#L78601) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]], [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] |
| `*CONTROL_IMPLICIT_GENERAL` | [Vol_I.txt:78475](../../docs/LSDyna/Vol_I.txt#L78475) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]], [[commands/modal#modal — natural frequency / modal analysis (§30)]] |
| `*CONTROL_IMPLICIT_SOLUTION` | [Vol_I.txt:78494](../../docs/LSDyna/Vol_I.txt#L78494) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] |
| `*CONTROL_IMPLICIT_EIGENVALUE` | [Vol_I.txt:78473](../../docs/LSDyna/Vol_I.txt#L78473) | [[commands/modal#modal — natural frequency / modal analysis (§30)]] |
| `*CONTROL_IMPLICIT_AUTO` | [Vol_I.txt:78469](../../docs/LSDyna/Vol_I.txt#L78469) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] |
| `*CONTROL_IMPLICIT_STABILIZATION` | [Vol_I.txt:78497](../../docs/LSDyna/Vol_I.txt#L78497) | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] (level ≥5) |
| `*CONTROL_DYNAMIC_RELAXATION` | [Vol_I.txt:78420](../../docs/LSDyna/Vol_I.txt#L78420) | [[commands/relax#relax — Dynamic Relaxation setup (§31)]] |
| `*CONTROL_CONTACT` | [Vol_I.txt:18267](../../docs/LSDyna/Vol_I.txt#L18267) | [[commands/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]], [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] |
| `*CONTROL_SHELL` | [Vol_I.txt:9503](../../docs/LSDyna/Vol_I.txt#L9503) | [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] |
| `*CONTROL_HOURGLASS` | [Vol_I.txt:18262](../../docs/LSDyna/Vol_I.txt#L18262) | [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] |
| `*CONTROL_OUTPUT` | [Vol_I.txt:18316](../../docs/LSDyna/Vol_I.txt#L18316) | [[commands/database#database — DATABASE output control (§37)]] |
| `*CONTROL_ALE` | [Vol_I.txt:29088](../../docs/LSDyna/Vol_I.txt#L29088) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |

Detail page: [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]].

## *ALE_*

All ALE family keywords concentrate in Vol_I.txt around L29023-29079 (definition
block) and L29120+ (usage).

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*ALE_MULTI-MATERIAL_GROUP` | [Vol_I.txt:29048](../../docs/LSDyna/Vol_I.txt#L29048) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |
| `*ALE_REFERENCE_SYSTEM_GROUP` | [Vol_I.txt:29051](../../docs/LSDyna/Vol_I.txt#L29051) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (PRTYPE=4) |
| `*CONSTRAINED_LAGRANGE_IN_SOLID` | [Vol_I.txt:29087](../../docs/LSDyna/Vol_I.txt#L29087) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (FSI coupling) |
| `*INITIAL_DETONATION` | (Vol_I — INITIAL section) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (HE preset) |
| `*BOUNDARY_AMBIENT_EOS` | [Vol_I.txt:29085](../../docs/LSDyna/Vol_I.txt#L29085) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |

Detail page: [[lsdyna/ale#ALE keywords in KooRemapper]].

## *INITIAL_*

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*INITIAL_STRESS_SOLID` | [Vol_I.txt:190149](../../docs/LSDyna/Vol_I.txt#L190149) | [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] (dynain emit) |
| `*INITIAL_STRESS_SHELL` (NPLANE=1, NTHICK=2, T=±1) | [Vol_I.txt:189459](../../docs/LSDyna/Vol_I.txt#L189459) | [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]], [[commands/indent#indent — indent/emboss (§14)]] (shell) |
| `*INITIAL_STRAIN_SOLID` | [Vol_I.txt:187880](../../docs/LSDyna/Vol_I.txt#L187880) | [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] |
| `*INITIAL_DETONATION` | [Vol_I.txt:112483](../../docs/LSDyna/Vol_I.txt#L112483) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |

Detail page: [[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]].

## *SECTION_* / *ELEMENT_* / *HOURGLASS

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*SECTION_SOLID` | [Vol_I.txt:18254](../../docs/LSDyna/Vol_I.txt#L18254) | [[modules/parser#Module: src/parser/]], [[commands/convert#convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)]], [[commands/elform#elform — ELFORM remap (§18)]] |
| `*SECTION_SHELL` | [Vol_I.txt:18253](../../docs/LSDyna/Vol_I.txt#L18253) | [[commands/shellmap#shellmap — QUAD4 shell-based mapping (§5)]], [[commands/elform#elform — ELFORM remap (§18)]] |
| `*SECTION_SOLID_PERI` | [Vol_I.txt:222147](../../docs/LSDyna/Vol_I.txt#L222147) | [[commands/disconnect#disconnect — node duplication — full / czm / mefem (§19)]] (full mode, ELFORM=48) |
| `*ELEMENT_SHELL` | [Vol_I.txt:17829](../../docs/LSDyna/Vol_I.txt#L17829) | [[modules/parser#Module: src/parser/]], shell pipelines |
| `*ELEMENT_SOLID` | [Vol_I.txt:18221](../../docs/LSDyna/Vol_I.txt#L18221) | [[modules/parser#Module: src/parser/]], all 3D ops |
| `*HOURGLASS` | [Vol_I.txt:17904](../../docs/LSDyna/Vol_I.txt#L17904) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]], [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] (IHQ tuning) |

Detail pages: [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]], [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]].

## Structural cards (verbatim pass-through)

KooRemapper preserves these line-by-line; it does not parse them into typed structs.

| Keyword | Vol/Line |
|---------|----------|
| `*PART` | [Vol_I.txt:17895](../../docs/LSDyna/Vol_I.txt#L17895) |
| `*INCLUDE` | [Vol_I.txt:18033](../../docs/LSDyna/Vol_I.txt#L18033) |
| `*PARAMETER` | [Vol_I.txt:18102](../../docs/LSDyna/Vol_I.txt#L18102) |
| `*TITLE` | [Vol_I.txt:18184](../../docs/LSDyna/Vol_I.txt#L18184) |
| `*DEFINE_CURVE` | [Vol_I.txt:18288](../../docs/LSDyna/Vol_I.txt#L18288) |
| `*CONSTRAINED_NODE_SET` | [Vol_I.txt:18293](../../docs/LSDyna/Vol_I.txt#L18293) |

## *CONTACT_*

The contact family is large. Detail page [[lsdyna/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]] enumerates the
specific variants KooRemapper's [[commands/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]] supports (analyze / create /
convert / modify / remove / detect / optional cards A-G).

## *DATABASE_*

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*DATABASE_OPTION` | [Vol_I.txt:18318](../../docs/LSDyna/Vol_I.txt#L18318) | [[commands/database#database — DATABASE output control (§37)]] |
| `*DATABASE_BINARY_OPTION` | [Vol_I.txt:18321](../../docs/LSDyna/Vol_I.txt#L18321) | [[commands/database#database — DATABASE output control (§37)]] |
| `*DATABASE_HISTORY_OPTION` | [Vol_I.txt:18314](../../docs/LSDyna/Vol_I.txt#L18314) | [[commands/database#database — DATABASE output control (§37)]] |
| `*DATABASE_FSI` | [Vol_I.txt:29089](../../docs/LSDyna/Vol_I.txt#L29089) | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (when FSI) |

## *BOUNDARY_* / *LOAD_*

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*BOUNDARY_SPC_OPTION` | [Vol_I.txt:18277](../../docs/LSDyna/Vol_I.txt#L18277) | [[commands/boundary#boundary — boundary conditions (§27)]] |
| `*LOAD_BODY_OPTION` | [Vol_I.txt:18279](../../docs/LSDyna/Vol_I.txt#L18279) | [[commands/load#load — load application (§26)]] |
| `*LOAD_NODE_OPTION` | [Vol_I.txt:18281](../../docs/LSDyna/Vol_I.txt#L18281) | [[commands/load#load — load application (§26)]] |
| `*LOAD_SEGMENT_OPTION` | [Vol_I.txt:18283](../../docs/LSDyna/Vol_I.txt#L18283) | [[commands/load#load — load application (§26)]] |
| `*LOAD_SHELL_OPTION` | [Vol_I.txt:18284](../../docs/LSDyna/Vol_I.txt#L18284) | [[commands/load#load — load application (§26)]] |
| `*LOAD_THERMAL_OPTION` | [Vol_I.txt:18286](../../docs/LSDyna/Vol_I.txt#L18286) | [[commands/load#load — load application (§26)]] |

## IGA

| Keyword | Vol/Line | Used by |
|---------|----------|---------|
| `*ELEMENT_SOLID_NURBS_PATCH` | [Vol_I.txt:13437](../../docs/LSDyna/Vol_I.txt#L13437) | [[commands/iga#iga — IGA NURBS box generation (§20)]] |
| (IGA overview) | [IGA.txt](../../docs/LSDyna/IGA.txt) | [[commands/iga#iga — IGA NURBS box generation (§20)]] |

## Conventions

- KooRemapper **never** emits `*MAT_ADD_EROSION` automatically — see [[../feedback_no_erode]].
- MAT card format is strictly 10-char fixed-width — see [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]].
- `*PART` cards always have a title line before the data line, even without `_TITLE` suffix.

All canonical definitions resolved; usage examples (later line numbers in Vol_I/II)
are intentionally not indexed — use the file open + Ctrl-F if you need them.
