"""One-shot stub generator for lat.md/ skeleton.

Run from the repo root:  python lat.md/_generate_stubs.py
After running, this file can be deleted — stubs are committed to lat.md/commands and
lat.md/theory. It exists so the skeleton can be re-generated reproducibly.
"""

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent

COMMAND_STUB = """\
# `{name}` — {tagline}

Source: {src}
Manual: [`KooRemapper_Manual.md`{anchor}](../../docs/KooRemapper_Manual.md{anchor})
{theory_line}

## Synopsis

```
KooRemapper {name} {usage}
```

## What it does

{summary}

## Key references

{refs}

## TODO

- Fill YAML schema table from manual.
- Add per-field cross-reference into [[lsdyna/{lsdyna_anchor}]].
- Note edge cases / idempotency where applicable.
"""

THEORY_STUB = """\
# {title}

Stub mirroring `docs/KooRemapper_Theory_Document.md` §{section}.

Source code: {src}

## Summary

{summary}

## See also

{see}
"""


def cmd(name, tagline, src, anchor, summary, refs, theory_line="", usage="<args>", lsdyna_anchor="keywords"):
    return COMMAND_STUB.format(
        name=name, tagline=tagline, src=src,
        anchor=anchor, theory_line=theory_line,
        usage=usage, summary=summary, refs=refs,
        lsdyna_anchor=lsdyna_anchor,
    )


COMMANDS = {
    "map": cmd(
        "map", "HEX8 structured mesh mapping (§4)",
        "[[src/mapper/MeshRemapper.cpp]], [[src/mapper/ParametricMapper.cpp]]",
        "#4-map--hex8-구조화-메시-매핑",
        "Maps a reference structured HEX8 mesh onto a deformed template mesh "
        "via isoparametric (i,j,k) coordinates. The arc/width/thickness axis "
        "triple is determined by [[src/grid/StructuredGridIndexer.cpp]].",
        "- [[modules/mapper]] — interpolator family\n"
        "- [[theory/isoparametric-map]]\n"
        "- [[theory/structured-grid]]",
        theory_line="Theory: [[theory/isoparametric-map]], [[theory/arc-length-param]]",
        usage="reference.k template.k output.k",
    ),
    "shellmap": cmd(
        "shellmap", "QUAD4 shell-based mapping (§5)",
        "[[src/mapper/ShellMapper.cpp]]",
        "#5-shellmap--quad4-셸-기반-매핑",
        "Maps solid-detail meshes using a QUAD4 shell representation as the "
        "parametric domain. Useful when only a shell mid-surface is available.",
        "- [[modules/mapper]]\n- [[lsdyna/section#sectionshell]]",
        usage="reference_shell.k template.k output.k",
    ),
    "prestress": cmd(
        "prestress", "reference → deformed strain/stress + dynain (§6)",
        "[[src/main.cpp#runPrestress]], [[modules/analysis]]",
        "#6-prestress--초기-응력변형률-계산",
        "Computes deformation gradient F per element, derives strain "
        "(engineering or Green-Lagrange), applies Hooke's law via "
        "[[src/analysis/MaterialModel.cpp]], and emits `*INITIAL_STRESS_SOLID` "
        "to a dynain file via [[src/parser/DynainWriter.cpp]].\n\n"
        "Material priority: command-line `-mat` > K-file `*MAT_*` > built-in default.",
        "- [[theory/deformation-gradient]]\n- [[theory/stress-tensor]]\n"
        "- [[lsdyna/initial#initialstresssolid]]\n- [[lsdyna/mat#materialmodel-mapping]]",
        usage="reference.k deformed.k output.dynain",
        lsdyna_anchor="initial",
    ),
    "squeeze": cmd(
        "squeeze", "interference-fit compression + reverse prestress (§7)",
        "[[src/commands/squeeze_assemble.cpp]], [[src/squeeze/SqueezeConfigReader.cpp]]",
        "#7-squeeze--간섭-끼워맞춤",
        "Two modes: (1) direct strain spec — displace nodes inward and inject "
        "reverse prestress via dynain; (2) thermal swelling — insert "
        "`*MAT_ADD_THERMAL_EXPANSION` and let LS-DYNA solve the equilibrium.",
        "- [[modules/squeeze]]\n- [[lsdyna/mat#matadd_thermal_expansion]]\n"
        "- [[commands/prestress]] (reverse stress)",
        usage="config.yaml",
        lsdyna_anchor="mat",
    ),
    "generate": cmd(
        "generate", "YAML-driven mesh generation (§8)",
        "[[src/generator/]] (CurvedMeshGenerator, VariableDensityMeshGenerator)",
        "#8-generate--generate-var--메시-생성",
        "Builds a fresh `.k` file from a YAML description (curves, density "
        "fields). `generate-var` is the variable-density variant.",
        "- [[modules/generator]]",
        usage="config.yaml",
    ),
    "unfold": cmd(
        "unfold", "bent mesh → flat (§9)",
        "[[src/mapper/ShellUnfolder.cpp]]",
        "#9-unfold--굽힘-메시-전개",
        "Unfolds a bent mesh onto its flat counterpart by accumulating arc "
        "length along the arc axis. Critical for the closed-loop case — see "
        "[[project_unfold_axis_perm]].",
        "- [[modules/mapper]]\n- [[theory/arc-length-param]]",
    ),
    "strain": cmd(
        "strain", "strain reporting (§10)",
        "[[src/main.cpp]], [[modules/analysis]]",
        "#10-strain--변형률-계산",
        "Reports per-element strain (engineering, Green-Lagrange, principal, "
        "von Mises, volumetric). No K-file output by default; CSV/console.",
        "- [[theory/strain-tensor]]",
    ),
    "info": cmd(
        "info", "mesh statistics (§11)",
        "[[src/main.cpp]]",
        "#11-info--메시-정보",
        "Prints node/element counts per type, bounding box, material/section "
        "table sizes.",
        "- [[modules/parser]]",
        usage="mesh.k",
    ),
    "restack": cmd(
        "restack", "layer restacking (§12)",
        "[[src/assembly/ModelAssembler.cpp#applyRestack]]",
        "#12-restack--레이어-재적층",
        "Re-orders or re-spaces plate/tier layers (e.g., battery cells). "
        "Operates on z-ordered HEX8 stacks.",
        "- [[modules/assembly]]",
    ),
    "bend": cmd(
        "bend", "Kirchhoff plate bending (§13)",
        "[[src/assembly/ModelAssembler.cpp#applyBend]], [[src/assembly/DeflectionGrid.cpp]]",
        "#13-bend--굽힘-변형--초기-응력",
        "Applies a deflection field (formula, dat file, or dat pair) and "
        "computes bending strain/stress under Kirchhoff plate theory. "
        "Stress computed BEFORE node movement (centroid invariance).",
        "- [[theory/kirchhoff-plate]]\n- [[src/assembly/FormulaEvaluator.cpp]]\n"
        "- [[lsdyna/initial]]",
        theory_line="Theory: [[theory/kirchhoff-plate]]",
        lsdyna_anchor="initial",
    ),
    "indent": cmd(
        "indent", "indent/emboss (§14)",
        "[[src/assembly/ModelAssembler.cpp#applyIndent]], [[src/assembly/IndentProfile.cpp]]",
        "#14-indent--압입엠보싱",
        "Quarter-arc fillet indent (depth < 0 for emboss). Profile "
        "`h(d), h''(d)` driven by r1/r2 radii; curvature decomposed by gradient "
        "direction: κ_x = -h''·gx², κ_y = -h''·gy², κ_xy = -h''·gx·gy. "
        "Singularity at d=r1 capped at strainLimit/(thickness/2).",
        "- [[theory/indent-profile]]\n- [[theory/kirchhoff-plate]]\n"
        "- [[src/assembly/ClosedLoop.cpp]] (signed distance + gradient)",
        theory_line="Theory: [[theory/indent-profile]]",
    ),
    "formstrain": cmd(
        "formstrain", "shell forming plastic EPS (§15)",
        "[[src/assembly/ModelAssembler.cpp#applyFormstrain]], [[src/assembly/ShellCurvature.cpp]]",
        "#15-formstrain--성형-소성-변형률",
        "Computes dihedral angle across shell edges via `ShellCurvature` "
        "(edge adjacency map). κ = θ/L where L is centroid distance. "
        "Bending strain → plastic EPS (sigy from MAT_024 Card 1 Field 5). "
        "Multiple ops merge EPS via max() (not sum).",
        "- [[theory/formstrain-theory]]\n- [[lsdyna/mat#mat024]]\n- [[lsdyna/initial#initialstressshell]]",
        theory_line="Theory: [[theory/formstrain-theory]]",
        lsdyna_anchor="initial",
    ),
    "convert": cmd(
        "convert", "TET10/HEX20/QUAD8/TRIA6 promotion (§16)",
        "[[src/assembly/ModelAssembler.cpp#applyTet10Convert]]",
        "#16-convert--2차-요소-변환",
        "Dispatched by `convertType` field; mid-edge nodes interned in "
        "`edgeMidNodeMap_` (member — persists across calls so multi-op runs "
        "share mid-side nodes). Auto-updates SECID→ELFORM via "
        "`solidSectionElforms_` / `shellSectionElforms_`.",
        "- [[lsdyna/element]]\n- [[lsdyna/section]]",
        lsdyna_anchor="element",
    ),
    "refine": cmd(
        "refine", "1:2 / 1:3 subdivision (§17)",
        "[[src/assembly/ModelAssembler.cpp#applyRefine]]",
        "#17-refine--메시-세분화",
        "Supports QUAD4/TRIA3/HEX8 (1:2, 1:3) and TET4 (1:2). Edge midpoints "
        "via `edgeMidNodeMap_`, edge thirds via `edgeThirdNodeMap_`, face "
        "centers via `faceCenterNodeMap_`. HEX8 1:3 face interior dedup uses "
        "canonical bilinear ordering (min ID + direction toward smaller "
        "neighbor) with affine (s,t) transform.",
        "- [[lsdyna/element#refinement]]",
        lsdyna_anchor="element",
    ),
    "elform": cmd(
        "elform", "ELFORM remap (§18)",
        "[[src/commands/standalone_ops.cpp]]",
        "#18-elform--요소-공식-변경",
        "Changes `*SECTION_*` ELFORM with alias support (solid: hex/tet/…; "
        "shell: belytschko/hughes-liu/…). Splits shared SECID if only some "
        "parts target it.",
        "- [[lsdyna/section]]",
        lsdyna_anchor="section",
    ),
    "disconnect": cmd(
        "disconnect", "node duplication — full / czm / mefem (§19)",
        "[[src/assembly/ModelAssembler.cpp#applyDisconnect]]",
        "#19-disconnect--노드-분리",
        "Duplicates shared nodes between selected parts. Modes:\n"
        "- `full` — inserts `*SECTION_SOLID_PERI` (ELFORM=48, DR=1.01).\n"
        "- `czm` — cohesive-zone elements at interface.\n"
        "- `mefem` — mesh-free enrichment.\n\n"
        "Builds `activeElems` from baseMesh_ (not-removed) + addedElements_ "
        "for post-restack use.",
        "- [[lsdyna/section#sectionsolid_peri]]",
        lsdyna_anchor="section",
    ),
    "iga": cmd(
        "iga", "IGA NURBS box generation (§20)",
        "[[src/assembly/ModelAssembler.cpp#applyIGA]]",
        "#20-iga--등기하해석-nurbs-박스-생성",
        "Generates `*ELEMENT_SOLID_NURBS_PATCH` into a per-PID include file "
        "`<output>_iga_p<pid>.k`. IGA and FE parts MUST use different MID. "
        "New PID/SECID/MID allocated from `++maxPartId_`/`++maxMaterialId_`.",
        "- [[lsdyna/element#iga]]\n- [`IGA.txt`](../../docs/LSDyna/IGA.txt)",
        lsdyna_anchor="element",
    ),
    "warpage": cmd(
        "warpage", "warpage correction (§21)",
        "[[src/assembly/ModelAssembler.cpp]], [[src/assembly/WarpageGrid.cpp]]",
        "#21-warpage--워피지-보정",
        "Applies an out-of-plane warpage field (typically from molding "
        "simulation) and recomputes stress.",
        "- [[modules/assembly]]",
    ),
    "offset": cmd(
        "offset", "shell offset → solid extrusion (§22)",
        "[[src/assembly/ModelAssembler.cpp#applyOffset]]",
        "#22-offset--셸-오프셋-솔리드-생성",
        "Extrudes a shell surface into a solid layer (with optional CZM "
        "connection). Variable thickness via `thickness_formula` (uses "
        "[[src/assembly/FormulaEvaluator.cpp]]). Local per-node averaged "
        "normals improve Jacobian on curved surfaces (+324% vs global avg).\n\n"
        "Quality validation integrated: AspectRatio warn>10/err>20, "
        "Jacobian warn<0.1/err<-1e-10, Warping warn>30°/err>45°.",
        "- [[modules/validation]]\n- [[lsdyna/element]]",
        lsdyna_anchor="element",
    ),
    "matswap": cmd(
        "matswap", "material bundle parameter swap (§23)",
        "[[src/commands/matswap.cpp]], [[src/assembly/ModelAssembler.cpp]] (mw_*)",
        "#23-matswap--재료-번들-교체",
        "Replaces a bundle of materials (with `*PARAMETER` definitions) by "
        "PID match. ID type auto-detected by name prefix "
        "(`HGID/LCID/SECID/MID/PID`). Output has resolved numbers — no "
        "`*PARAMETER` blocks remain.",
        "- [[lsdyna/mat]]\n- bundle examples: `examples/matswap/`",
        lsdyna_anchor="mat",
    ),
    "matdb": cmd(
        "matdb", "material DB lookup + replacement (§24)",
        "[[src/commands/matdb.cpp]]",
        "#24-matdb--재료-db-교체",
        "Uses `materials/material_db.json` to replace `*MAT_*` cards. "
        "Auto-matches by title→name/tag substring (case-insensitive) or "
        "direct MID. Supports structural card type selection "
        "(MAT_ELASTIC/024/RIGID/…), optional thermal insertion "
        "(`*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` with TMID "
        "linkage). `match: \"*\"` is catch-all.",
        "- [[lsdyna/mat]]\n- [[modules/commands#yaml-conventions]] (stripQuotes)",
        lsdyna_anchor="mat",
    ),
    "contact": cmd(
        "contact", "*CONTACT_* analyze/create/convert/modify/remove/detect (§25)",
        "[[src/commands/contact.cpp]], [[src/commands/contact_helpers.cpp]]",
        "#25-contact--접촉-정의-관리",
        "Six sub-actions on `*CONTACT_*` cards. Optional cards A-G are "
        "modeled via `ct_modifyOptionalCards()` with re-parse. Auto-detect "
        "scans for part adjacency.",
        "- [[lsdyna/control#controlcontact]]",
        lsdyna_anchor="control",
    ),
    "load": cmd(
        "load", "load application (§26)",
        "[[src/commands/load_boundary.cpp]]",
        "#26-load--하중-적용",
        "Emits `*LOAD_BODY/NODE/SEGMENT/SHELL/THERMAL_*` cards from YAML.",
        "- [[lsdyna/keywords#boundary--load]]",
    ),
    "boundary": cmd(
        "boundary", "boundary conditions (§27)",
        "[[src/commands/load_boundary.cpp]]",
        "#27-boundary--경계-조건-적용",
        "Emits `*BOUNDARY_SPC_*` cards from YAML.",
        "- [[lsdyna/keywords#boundary--load]]",
    ),
    "rbe": cmd(
        "rbe", "RBE constraint (§28)",
        "[[src/commands/load_boundary.cpp]]",
        "#28-rbe--rbe-구속-조건",
        "Emits `*CONSTRAINED_NODAL_RIGID_BODY` or related cards.",
        "- [[lsdyna/keywords]]",
    ),
    "implicit": cmd(
        "implicit", "Explicit → Implicit converter (§29)",
        "[[src/commands/implicit.cpp]]",
        "#29-implicit--explicitimplicit-변환",
        "8-level spectrum (1=aggressive → 8=buckling/snap-through). Removes "
        "DR/BULK/D3DRLF, modifies TIMESTEP/TERMINATION, inserts "
        "`*CONTROL_IMPLICIT_*`. Level 5+ adds STABILIZATION, 6+ MUMPS, "
        "8 arc-length. Overrides: "
        "dctol/ectol/dt0/dtmax/nsolvr/kfail/rctol/lsolvr/stab/stab_scale/arc_length.",
        "- [[lsdyna/control]]",
        lsdyna_anchor="control",
    ),
    "modal": cmd(
        "modal", "natural frequency / modal analysis (§30)",
        "[[src/commands/modal.cpp]]",
        "#30-modal--고유진동수모달-해석-변환",
        "Inserts `*CONTROL_IMPLICIT_EIGENVALUE` + GENERAL/SOLUTION. "
        "Options: nmode(10), fmin(0), fmax(0), center(0), eigmth "
        "(2=Lanczos/101=MCMS/102=LOBPCG/103=FastLanczos), solver(7/30=MUMPS), "
        "fix_shell_elform, keep_dr_curves. Existing `*CONTROL_IMPLICIT_*` → "
        "WARNING + replace.",
        "- [[lsdyna/control]]",
        lsdyna_anchor="control",
    ),
    "relax": cmd(
        "relax", "Dynamic Relaxation setup (§31)",
        "[[src/commands/relax.cpp]]",
        "#31-relax--dynamic-relaxation-설정",
        "5-level preset. Overrides: "
        "nrcyck/drtol/drfctr/tssfdr/irelal/edttl. Inserts "
        "`*CONTROL_DYNAMIC_RELAXATION`.",
        "- [[lsdyna/control]]",
        lsdyna_anchor="control",
    ),
    "explicit": cmd(
        "explicit", "pure explicit restoration (§32)",
        "[[src/commands/strip.cpp]]",
        "#32-explicit--순수-explicit-복원",
        "Removes all `*CONTROL_IMPLICIT_*`, `*CONTROL_DYNAMIC_RELAXATION` "
        "etc., restoring a pure explicit `.k`. Counterpart to `strip`.",
        "- [[commands/strip]]",
    ),
    "wrap": cmd(
        "wrap", "winding-tension prestress (§33)",
        "[[src/assembly/ModelAssembler.cpp]]",
        "#33-wrap--와인딩-인장-프리스트레스",
        "Applies winding tension to jelly-roll layers — translates tension "
        "to hoop stress per layer.",
        "- [[modules/assembly]]\n- [[modules/battery]]",
    ),
    "optimize": cmd(
        "optimize", "material-specific solver presets (§34)",
        "[[src/commands/optimize.cpp]]",
        "#34-optimize--재료별-해석-최적화",
        "Per-material solver presets (rubber etc.). Idempotent.",
        "- [[modules/commands]]",
    ),
    "ale": cmd(
        "ale", "Lagrangian → ALE converter (§35)",
        "[[src/commands/ale.cpp]]",
        "#35-ale--ale-변환",
        "14 presets: gas/liquid/explosive/vacuum. Auto-inserts "
        "`*SECTION_SOLID` ELFORM change, `*HOURGLASS` IHQ=3, "
        "`*CONTROL_ALE`, `*ALE_MULTI-MATERIAL_GROUP`, "
        "`*ALE_REFERENCE_SYSTEM_GROUP` (PRTYPE=4), "
        "`*CONSTRAINED_LAGRANGE_IN_SOLID` (FSI), `*INITIAL_DETONATION` (HE). "
        "Shared SECID detection → new section created. Unit: t/mm/s → MPa.",
        "- [[lsdyna/ale]]\n- [[lsdyna/eos]]",
        lsdyna_anchor="ale",
    ),
    "stabilize": cmd(
        "stabilize", "explicit solver stabilization (§36)",
        "[[src/commands/stabilize.cpp]]",
        "#36-stabilize--explicit-솔버-안정화",
        "12-level cumulative system. 1=energy, 2=accuracy, 3=TSSFAC 0.80, "
        "4=IHQ=4, 5=shell, 6=contact soft stage1, 7=TSSFAC 0.67+bulk "
        "viscosity, 8=pinball SOFT=2+Card C IGNORE, 9=IHQ=6 BB, "
        "10=TSSFAC 0.60, 11=ERODE (interactive), 12=max conservative. "
        "`stab_resolveLevel()` + `stab_applyExplicit()`. "
        "`stab_ensureControlContactCard2()` guarantees Card 2 exists.",
        "- [[lsdyna/control]]\n- [[../feedback_no_erode]] (level 11 is the only ERODE path)",
        lsdyna_anchor="control",
    ),
    "database": cmd(
        "database", "DATABASE output control (§37)",
        "[[src/commands/database.cpp]]",
        "#37-database--database-출력-제어",
        "8 presets + per-keyword spec. Emits `*DATABASE_*` cards.",
        "- [[lsdyna/keywords#database]]",
    ),
    "strip": cmd(
        "strip", "keyword removal (§38)",
        "[[src/commands/strip.cpp]]",
        "#38-키워드-제거strip-기능",
        "Per-command `strip: true` flag (modal/implicit/relax) removes "
        "the mode-specific cards without inserting replacements. "
        "Contrasts with [[commands/explicit]] which targets a different "
        "scope.",
        "- [[modules/commands]]",
    ),
    "assemble": cmd(
        "assemble", "multi-operation YAML composer (§39)",
        "[[src/assembly/ModelAssembler.cpp]]",
        "#39-assemble--통합-어셈블리",
        "Central composer. Operations: replace, squeeze, restack, bend, "
        "indent, formstrain, convert (tet10/hex20/quad8/tria6), refine, "
        "elform, disconnect, iga, warpage, offset, matswap, matdb, wrap, "
        "generate, update, control, database. Stresses from multiple ops "
        "on the same element sum; EPS uses max(). See [[modules/assembly]].",
        "- [[modules/assembly]]\n- per-op nodes under [[commands/index]]",
    ),
    "meshfix": cmd(
        "meshfix", "TET4 Gmsh-based remesh (§40)",
        "[[src/commands/meshfix.cpp]], [[modules/remesh]]",
        "#40-meshfix--tet4-재메시-gmsh-기반",
        "Gmsh-driven adaptive TET4 remesh with scaled-Jacobian quality, "
        "patch polishing, thin-solid handling. Per-component bad-element "
        "patch remesh (commit `04a97dd`); pure-Gmsh geomThin field optimal "
        "(commit `f7036a6`).",
        "- [[modules/remesh]]",
    ),
    "battery": cmd(
        "battery", "battery mesh/control generator",
        "[[src/commands/battery.cpp]], [[modules/battery]]",
        "",  # no manual section
        "Generates stacked or wound battery cell meshes with materials, "
        "contacts, swelling, and control cards from a YAML config.",
        "- [[modules/battery]]\n- artifacts: `battery_*.k` in repo root",
    ),
    "cnrb2solid": cmd(
        "cnrb2solid", "CNRB → solid conversion",
        "[[src/commands/cnrb2solid.cpp]]",
        "",
        "Converts `*CONSTRAINED_NODAL_RIGID_BODY` definitions into "
        "rigid-solid representations. See [`cnrb2solid_concept.md`]"
        "(../../docs/cnrb2solid_concept.md).",
        "- [[lsdyna/keywords]]",
    ),
}


THEORY = {
    "coordinate-systems": ("Coordinate systems", "1.2",
        "Reference (X) vs deformed (x) configuration; arc/width/thickness "
        "axis convention for closed-loop meshes.",
        "- [[project_unfold_axis_perm]]"),
    "arc-length-param": ("Arc-length parameterization", "2.2",
        "Normalize node positions to u ∈ [0,1] along the arc axis. The "
        "actual mapping algorithm in production. See "
        "[[src/mapper/ParametricMapper.cpp]].",
        "- [[theory/edge-interpolation]]\n- [[modules/mapper]]"),
    "edge-interpolation": ("Edge-based interpolation", "2.1",
        "Per-edge piecewise-linear field reconstruction along arc length.",
        "- [[src/mapper/EdgeInterpolator.cpp]]"),
    "coons-patch": ("Coons patch", "2.5",
        "Bilinear blend of four boundary curves. Used by "
        "[[src/mapper/FaceInterpolator.cpp]].",
        "- [[modules/mapper]]"),
    "structured-grid": ("Structured grid BFS indexing", "2.6",
        "Assigns (i,j,k) to unstructured HEX8 cells via BFS over face "
        "adjacency. Seed face on boundary; arc/width/thickness fall out of "
        "neighbor counts. Implemented in [[src/grid/StructuredGridIndexer.cpp]].",
        "- [[modules/grid]]"),
    "transfinite": ("Transfinite interpolation (Gordon-Hall)", "2.3",
        "Implemented but currently unused; kept for reference.",
        "- [[modules/mapper]]"),
    "trilinear": ("Trilinear interpolation", "2.4",
        "Implemented but currently unused; kept for reference.",
        "- [[modules/mapper]]"),
    "deformation-gradient": ("Deformation gradient F", "3.1",
        "F = ∂x/∂X. Computed via HEX8 shape function derivatives at the "
        "element centroid (single-point integration).",
        "- [[src/analysis/DeformationGradient.cpp]]\n- [[theory/shape-functions]]"),
    "strain-tensor": ("Strain tensor", "3.2",
        "Engineering ε = (F+Fᵀ)/2 − I (default) and Green-Lagrange "
        "E = (FᵀF − I)/2 (option). Voigt, principal, von Mises, volumetric, "
        "and triaxiality forms all in [[src/analysis/StrainTensor.cpp]].",
        "- [[theory/stress-tensor]]"),
    "stress-tensor": ("Stress tensor", "3.3",
        "Hooke law σ = λ·tr(ε)·I + 2μ·ε. Lamé parameters from E, ν. "
        "Verification: E=210000, ν=0.3, ε=0.02 → σ_xx=5654, σ_yy=σ_zz=2423.",
        "- [[src/analysis/StressTensor.cpp]]\n- [[theory/isotropic-elastic]]"),
    "gauss-quadrature": ("Gauss quadrature", "4.1",
        "HEX8: 2×2×2 (8 points) at ±1/√3. TET4: 1-pt or 4-pt at standard "
        "barycentric.",
        "- [[modules/analysis]]"),
    "shape-functions": ("Shape functions", "4.2",
        "HEX8 trilinear N_i(ξ,η,ζ) = (1±ξ)(1±η)(1±ζ)/8. Derivatives "
        "evaluated at integration points feed F.",
        "- [[src/analysis/DeformationGradient.cpp]]"),
    "jacobian": ("Jacobian matrix", "4.3",
        "J = ∂x/∂ξ. det(J) drives the integration weight; inv(J) maps "
        "natural derivatives to physical derivatives.",
        "- [[modules/analysis]]"),
    "isotropic-elastic": ("Isotropic elastic material", "5.1",
        "λ = Eν / ((1+ν)(1-2ν)), μ = E / (2(1+ν)). Constraint: -1 < ν < 0.5. "
        "Factory `MaterialModel::isotropicElastic(E, ν)`.",
        "- [[src/analysis/MaterialModel.cpp]]\n- [[lsdyna/mat#matelastic]]"),
    "viscoelastic": ("Viscoelastic (MAT_VISCOELASTIC)", "5.2",
        "Prony-series relaxation. Used by prestress on rubbery components.",
        "- [[lsdyna/mat#matviscoelastic]]"),
    "kirchhoff-plate": ("Kirchhoff plate theory", "40.3",
        "Thin plate: normals remain normal. Bending strain "
        "ε = -z·κ where z is distance from neutral surface and κ is "
        "curvature from the deflection field.\n\n"
        "**Order of operations**: compute stress BEFORE displacing nodes, "
        "otherwise the centroid z shifts and the distance from the neutral "
        "surface becomes inconsistent.",
        "- [[commands/bend]]\n- [[commands/indent]]"),
    "indent-profile": ("Indent profile h(d), h''(d)", "(40.3 derivation)",
        "Quarter-arc fillet: k = depth/(r1+r2). In r1 zone: "
        "h(d) = -depth + k·r1·(1 - √(1 - (d/r1)²)). Curvature h''(d) has a "
        "singularity at d=r1, capped at strainLimit/(thickness/2). For "
        "emboss (depth<0), exact mirror of indent.",
        "- [[src/assembly/IndentProfile.cpp]]\n- [[src/assembly/ClosedLoop.cpp]]"),
    "formstrain-theory": ("Formstrain (dihedral curvature)", "40.4",
        "Edge dihedral angle θ → bending strain ε_b = (t/2)·κ where "
        "κ = θ/L (L = centroid distance between adjacent shells). "
        "Plastic EPS = max(0, ε_b - ε_y). Merges across ops via max().",
        "- [[src/assembly/ShellCurvature.cpp]]\n- [[lsdyna/mat#mat024]]"),
    "isoparametric-map": ("Isoparametric mapping", "40.1",
        "Inverse-map a target point's physical coordinates back into the "
        "(ξ,η,ζ) natural space of the host element via Newton iteration, "
        "then sample the field via shape functions.",
        "- [[commands/map]]\n- [[theory/shape-functions]]"),
}


def main():
    cmds_dir = ROOT / "commands"
    th_dir = ROOT / "theory"
    cmds_dir.mkdir(exist_ok=True)
    th_dir.mkdir(exist_ok=True)

    for name, content in COMMANDS.items():
        (cmds_dir / f"{name}.md").write_text(content, encoding="utf-8")

    for slug, (title, sec, summary, see) in THEORY.items():
        (th_dir / f"{slug}.md").write_text(
            THEORY_STUB.format(title=title, section=sec, src="(see See-also)",
                               summary=summary, see=see),
            encoding="utf-8",
        )
    print(f"Wrote {len(COMMANDS)} command stubs + {len(THEORY)} theory stubs.")


if __name__ == "__main__":
    main()
