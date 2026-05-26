# Module: src/assembly/

The composer pipeline. `ModelAssembler` is the single biggest class in the
project and the engine behind [[commands/assemble#assemble — multi-operation YAML composer (§39)]] and the standalone variants
of bend/indent/squeeze/restack/etc.

## Components

| File | Role |
|------|------|
| [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) | core operation pipeline |
| [AssemblyConfigReader.cpp](../../src/assembly/AssemblyConfigReader.cpp) | YAML → `AssemblyConfig` struct |
| [DeflectionGrid.cpp](../../src/assembly/DeflectionGrid.cpp) | bilinear-interpolated deflection field + finite-difference curvature |
| [FormulaEvaluator.cpp](../../src/assembly/FormulaEvaluator.cpp) | recursive-descent math expressions (`sin`, `cos`, …) |
| [IndentProfile.cpp](../../src/assembly/IndentProfile.cpp) | quarter-arc fillet `h(d), h''(d)` for r1/r2 zones |
| [ClosedLoop.cpp](../../src/assembly/ClosedLoop.cpp) | signed-distance via winding number + min-edge distance |
| [ShellCurvature.cpp](../../src/assembly/ShellCurvature.cpp) | dihedral curvature for formstrain |
| [WarpageGrid.cpp](../../src/assembly/WarpageGrid.cpp) | warpage field representation |

## Operation contract

Each operation is a `ModelAssembler` method (e.g. `applyReplace`, `applyBend`,
`applyIndent`, `applyConvert`, `applyRefine`, `applyDisconnect`, `applyIGA`,
`applyOffset`, …). Shared rules:

1. **Stress before geometry** — bending-style ops (`bend`, `indent`) compute
   per-element stress *before* moving nodes, so the neutral surface stays put.
2. **Accumulator merge** — `writeOutput()` merges stresses with `std::map<eid,
   StressTensor>` summing across ops; EPS uses `max()` (see [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]]).
3. **Line-by-line preservation** — unparsed `*KEYWORDS` flow through unchanged.
4. **State buckets** — mutations live in member maps rather than rewriting
   `baseMesh_`: `addedElements_`, `addedShellElements_`, `addedNodes_`,
   `removedElementIds_`, `modifiedElementNodes_`, `modifiedShellElementNodes_`,
   `edgeMidNodeMap_`, `edgeThirdNodeMap_`, `faceCenterNodeMap_`.

## Geometric helpers

- `parseNodeIdFromLine()` — extracts first integer token. Required because LS-DYNA
  field widths vary across keyword variants (don't assume 8 or 10 char fields).
- `DeflectionGrid`: row 0 = `x2_max`, row N-1 = `x2_min` (inverted y-axis). The
  curvature convention is `kappa = -d²w/dx²`.
- `FormulaEvaluator`: variables `x1, x2` are relative to bbox-min; `L1, L2` are
  bbox dimensions; `pi` is built-in.
- `IndentProfile`: `k = depth/(r1+r2)`. The curvature `h''(d)` has a singularity
  at `d=r1`; it's capped at `strainLimit/(thickness/2)`.

## Dynamic relaxation insertion

`dynamic_relaxation: true` in the YAML triggers automatic insertion of
`*CONTROL_DYNAMIC_RELAXATION` + `*CONTROL_TERMINATION` (endtim=0). An existing
`*CONTROL_TERMINATION` is replaced via the standard "skip until next keyword"
mechanism — see [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]].

## Cross-references

- See [[commands/assemble#assemble — multi-operation YAML composer (§39)]] for per-operation YAML.
- See [[theory/kirchhoff-plate#Kirchhoff plate theory]] for bend/indent mathematical model.
- See [[project_unfold_axis_perm]] for the arc/width/thickness axis invariant.
