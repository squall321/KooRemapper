# Architecture

KooRemapper is a single-binary CLI: one executable, many subcommands. Each subcommand
parses a YAML config (or positional args), loads LS-DYNA `.k` files via a streaming
parser, mutates an in-memory model, and emits a new `.k` file plus optional artifacts.

> See [[modules/commands#Module: src/commands/]] for dispatch; [[modules/parser#Module: src/parser/]] for I/O; [[modules/assembly#Module: src/assembly/]]
> for the multi-operation pipeline.

## Top-down structure

```text
main.cpp  ─►  ArgumentParser  ─►  runXxx() per command
                                 │
                                 ├─ KFileReader   ► Mesh / ShellMesh / raw lines
                                 ├─ <command logic>
                                 └─ KFileWriter / DynainWriter
```

- Entry: [main.cpp](src/main.cpp) — dispatches by `argv[1]`.
- Argument parsing: [ArgumentParser.cpp](src/cli/ArgumentParser.cpp).
- Each subcommand lives under `src/commands/` as `runXxx`. See [[modules/commands#Module: src/commands/]] for the per-file map.

## In-memory model

Three coexisting representations of an LS-DYNA `.k` file:

1. **Parsed mesh** — [Mesh.cpp](src/core/Mesh.cpp) (nodes + 3D elements) and
   [ShellMesh.cpp](src/core/ShellMesh.cpp) (shells).
2. **Material/section/contact tables** — extracted into typed structs by [KFileReader.cpp](src/parser/KFileReader.cpp).
3. **Raw line buffer** — every unrecognised keyword block is preserved verbatim so
   round-trip writes don't lose `*CONTACT`, `*BOUNDARY`, `*DEFINE_CURVE`, etc.
   This is the *line-by-line preservation invariant* relied on by [[commands/assemble#assemble — multi-operation YAML composer (§39)]].

The raw-line layer is why most operations mutate state via *line splicing* rather than
re-serializing from typed structures.

## Operation pipeline (assemble)

`assemble` ([[commands/assemble#assemble — multi-operation YAML composer (§39)]]) is the central composer: it accepts a list of
operations and runs them sequentially over one base model, accumulating dynain stress
contributions. Each operation (`replace`, `squeeze`, `restack`, `bend`, `indent`,
`formstrain`, `convert`, `refine`, `elform`, `disconnect`, `iga`, `warpage`, `offset`,
`matswap`, `matdb`, `wrap`, `update`, `control`, `database`) is implemented as a method
on [ModelAssembler.cpp](src/assembly/ModelAssembler.cpp).

Operations share these conventions:

- Stresses from multiple ops on the same element are **summed** in `writeOutput()`
  (`std::map<elemId, StressTensor>` accumulator).
- Bending-style ops (bend/indent) compute stress **before** displacing nodes
  (otherwise the neutral surface drifts — see [[theory/kirchhoff-plate#Kirchhoff plate theory]]).
- Element ID/node ID offsets for `replace` follow the rule
  `nodeIdOffset = maxNodeId; elemIdOffset = maxElementId`.

## Solver-mode conversions

Several commands rewrite a `.k` file to switch solver modes. They follow a common
"strip + insert" pattern handled in [strip.cpp](src/commands/strip.cpp) and per-mode files
([implicit.cpp](src/commands/implicit.cpp), [modal.cpp](src/commands/modal.cpp), [relax.cpp](src/commands/relax.cpp),
[ale.cpp](src/commands/ale.cpp), [stabilize.cpp](src/commands/stabilize.cpp)):

1. Remove DR / BULK / D3DRLF / existing `*CONTROL_IMPLICIT_*` etc.
2. Adjust `*CONTROL_TIMESTEP` / `*CONTROL_TERMINATION`.
3. Insert the cards required by the target mode at a deterministic location.

See per-command pages for level spectra and idempotency notes.

## Mesh-mapping pipeline

For closed-loop / arc geometries the mapping chain is:

```text
ParametricMapper  ──►  FlatMeshGenerator  ──►  MeshRemapper
   (arc/width/thickness invariant — see [[project_unfold_axis_perm]])
```

All three must agree on which physical axis is arc, which is width, which is
thickness. The legacy assumption "bent-i == arc" is wrong for closed loops; the
current implementation passes the axis triple explicitly.

## LS-DYNA contract

KooRemapper interoperates with LS-DYNA at the keyword level only — it parses and
emits `.k` text, never binary d3plot/dynain[binary]. Cards it understands or emits are
indexed in [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]]. Material cards have a stricter contract:
fixed-width 10-char fields (see [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]).

## Build

- CMake + MSVC. `cmake --build build --config Release`.
- Output: `build\bin\Release\KooRemapper.exe`.
- Third-party: TetGen, Gmsh (for [[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]]).
- Tests under `tests/`, integration via YAML files in `examples/`.
