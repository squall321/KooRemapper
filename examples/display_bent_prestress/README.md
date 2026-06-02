# Display Bent Prestress

Compute initial stress on a detail flat mesh by mapping it onto a 3D bent
reference shape.

## Inputs (you provide these)

| File | Content |
|------|---------|
| `simple_bent_display.k` | 3D HEX8 reference geometry of the bent shape |
| `detail_flat_display.k` | 3D HEX8 fine flat mesh **with** `*MAT_*` + `*PART` + `*SECTION_SOLID` |

## Outputs

| File | Content |
|------|---------|
| `detail_bent_display.k` | bent mesh + detail_flat's material/part/section + `*INCLUDE detail_bent_display.dynain` |
| `detail_bent_display.dynain` | `*INITIAL_STRESS_SOLID` from Kirchhoff plate prestress |

The output deck is self-contained — feed `detail_bent_display.k` directly to LS-DYNA.

## Two ways to run

### Path A — single YAML (`assemble`, default)

`replace` op accepts a 3D HEX8 reference directly via the `simple_bent:` key.
KooRemapper auto-extracts the top free-face shell in memory, maps detail_flat
onto it, and computes prestress — all in one pass.

```bash
run.bat              # Windows
./run.sh             # Linux / macOS
```

Underlying YAML: [`prestress.yaml`](prestress.yaml)
```yaml
base_model: detail_flat_display.k
output: detail_bent_display

operations:
  - type: replace
    target_pid: 1
    detail_flat: detail_flat_display.k
    simple_bent: simple_bent_display.k   # 3D HEX8 directly
    prestress: true
```

### Path B — standalone 2-command chain (`map` + `prestress`)

The classic path, no assemble involved. Equivalent result.

```bash
run_standalone.bat   # Windows
./run_standalone.sh  # Linux / macOS
```

Under the hood:
```bash
KooRemapper map       simple_bent_display.k detail_flat_display.k detail_bent_display.k
KooRemapper prestress detail_flat_display.k detail_bent_display.k detail_bent_display.dynain
```

Either path produces the same output files. Pick whichever fits your workflow.

## What happens inside (Path A)

1. `assemble` loads `detail_flat_display.k` as base_model. Its
   `*MAT_*`/`*PART`/`*SECTION_SOLID` cards (plus any `*CONTROL_*`,
   `*BOUNDARY_*`, `*INCLUDE`) are held in `rawLines_`.
2. The `replace` op sees `simple_bent:`. It loads
   `simple_bent_display.k` as a 3D mesh, walks every HEX8 face,
   keeps only those that appear in exactly one element (free faces),
   filters to the top side via element-centroid Z, and builds an
   in-memory `ShellMesh` from them.
3. `ShellMapper` consumes that shell, builds the parametric bent-shell
   map, projects `detail_flat_display.k`'s nodes onto it, and produces
   the bent mesh. With `prestress: true` it also runs Kirchhoff plate
   prestress and accumulates the per-element stress tensors.
4. `writeOutput` emits the bent geometry into the surviving rawLines_
   (so MAT/PART/SECTION pass through verbatim) and writes the
   accumulated stresses to `detail_bent_display.dynain` as
   `*INITIAL_STRESS_SOLID`.

## Variants

### Multi-layer panel (display stack)

If `detail_flat_display.k` contains multiple PIDs, list one `replace` op
per PID — all share the same `simple_bent`:
```yaml
operations:
  - { type: replace, target_pid: 1, detail_flat: detail_flat_display.k, simple_bent: simple_bent_display.k, prestress: true }
  - { type: replace, target_pid: 2, detail_flat: detail_flat_display.k, simple_bent: simple_bent_display.k, prestress: true }
  - { type: replace, target_pid: 3, detail_flat: detail_flat_display.k, simple_bent: simple_bent_display.k, prestress: true }
```

### Embed dynain inline (single file output)

Add `dynain_embed: true` at the top of `prestress.yaml` — skips the
separate `.dynain` and inlines `*INITIAL_STRESS_SOLID` directly into the
`.k` output.

### Material override (when detail_flat has no MAT cards)

```yaml
material:
  E:  70000
  nu: 0.33
```

This is used for stress calculation only — the output still inherits
whatever `*MAT_*` cards exist in base_model.

### Pre-extracted shell (legacy, mutually exclusive with `simple_bent:`)

```bash
KooRemapper extract-surface simple_bent_display.k bent_shell.k --face top
```
Then in YAML:
```yaml
shell_bent: bent_shell.k         # instead of simple_bent:
```
Useful if you want to inspect or hand-edit the shell before mapping.

## Troubleshooting

- **"X nodes could not be mapped (outside shell domain)"** — detail_flat's
  XY extent reaches outside the projected shell. Trim detail_flat or use
  a wider simple_bent. A small percentage is usually harmless.
- **"only N/8 corner nodes found"** — the 3D bent reference's
  StructuredGridIndexer collapsed two axes. Fixed in commit `e15dbea`
  (REQ-003). If it still happens, the mesh may be too irregular to be
  treated as structured.
- **All-zero stress in the dynain** — base_model lacks `*MAT_*` cards.
  Check the console: `Part 1 -> Material 1: E=..., nu=...` confirms
  the material was found. Add `material:` override in the YAML if needed.
- **`replace cannot use both shell_bent and simple_bent`** — pick one.
  `simple_bent:` is the newer single-step path.

## Cleanup

```bash
run.bat clean
run_standalone.bat clean
```
