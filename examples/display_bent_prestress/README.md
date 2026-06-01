# Display Bent Prestress

Compute initial stress on a detail flat mesh by mapping it onto a bent
reference shape, in a single `assemble` pass.

## Inputs

| File | Content | Source |
|------|---------|--------|
| `simple_bent_display.k` | 3D HEX8 reference geometry of the bent shape | user / CAD / `generate-var` |
| `detail_flat_display.k` | 3D HEX8 fine flat mesh **with** `*MAT_*` + `*PART` + `*SECTION_SOLID` | user |

## Outputs

| File | Content |
|------|---------|
| `detail_bent_display.k` | bent mesh + detail_flat's material/part/section + `*INCLUDE detail_bent_display.dynain` |
| `detail_bent_display.dynain` | `*INITIAL_STRESS_SOLID` from Kirchhoff plate prestress |

The output deck is self-contained — feed `detail_bent_display.k` directly to LS-DYNA.

## Workflow

```bash
# Step 1 — extract a QUAD4 mid/top shell from the 3D bent reference
#          (replace op requires a SHELL bent reference, not 3D HEX8)
KooRemapper extract-surface simple_bent_display.k bent_shell.k --face top

# Step 2 — single assemble pass: map detail flat onto bent shell + compute stress
KooRemapper assemble prestress.yaml
```

That's it. Two commands, one of which is a one-time prep.

## What happens inside

1. `extract-surface` walks `simple_bent_display.k`'s HEX8 faces, keeps those that
   belong to exactly one element (free faces), filters to the top side via
   element-centroid Z, and emits them as `*ELEMENT_SHELL`. Output =
   `bent_shell.k`.
2. `assemble` loads `detail_flat_display.k` as the base model — its
   `*MAT_*`/`*PART`/`*SECTION_SOLID` cards (and any `*CONTROL_*`, `*BOUNDARY_*`,
   `*INCLUDE` etc.) are kept verbatim in `rawLines_`.
3. The `replace` op runs `ShellMapper(bent_shell.k)` to build the parametric
   bent-shell map, projects `detail_flat_display.k`'s nodes through it, and
   removes the old PID-1 elements + adds the bent ones (same PID, so the
   material chain stays valid).
4. With `prestress: true`, the mapper also computes per-element strain via
   Kirchhoff plate theory and turns it into a stress tensor using the
   material attached to PID 1. The results accumulate in
   `ModelAssembler::accumulatedResults_`.
5. `writeOutput` emits two files: `detail_bent_display.k` (raw lines minus
   the replaced NODE/ELEMENT block + new bent geometry + `*INCLUDE`) and
   `detail_bent_display.dynain` (the accumulated stresses as
   `*INITIAL_STRESS_SOLID`).

## Variants

### Multi-layer panel (display stack: cover / OCA / panel / PCB)

If `detail_flat_display.k` contains multiple PIDs and all should be bent
to the same shape, list one `replace` op per PID:

```yaml
operations:
  - { type: replace, target_pid: 1, detail_flat: detail_flat_display.k, shell_bent: bent_shell.k, prestress: true }
  - { type: replace, target_pid: 2, detail_flat: detail_flat_display.k, shell_bent: bent_shell.k, prestress: true }
  - { type: replace, target_pid: 3, detail_flat: detail_flat_display.k, shell_bent: bent_shell.k, prestress: true }
```
Each PID's MAT (from base_model) is used to compute that layer's stress;
all contributions land in the same `.dynain`.

### Using a midsurface shell instead of top face

Better when the bent reference is a thick layered solid and you want the
neutral plane rather than the outer skin:

```bash
KooRemapper extract-surface simple_bent_display.k bent_shell.k --mid-surface
```

### Embedding dynain inline (single file output)

Set `dynain_embed: true` at the top of `prestress.yaml` to skip the
separate `.dynain` and inline `*INITIAL_STRESS_SOLID` directly into the
`.k` output.

### Material override (when detail_flat has no MAT cards)

```yaml
material:
  E:  70000      # whatever unit system the model uses
  nu: 0.33
```

This overrides whatever `*MAT_*` cards exist in base_model for stress
calculation only — the output still inherits the base's MAT cards via
raw-line preservation.

## Troubleshooting

- **"only N/8 corner nodes found"** in the extract-surface output → the
  3D bent reference is unstructured or has degenerate axis topology. See
  REQ-003 commit (`e15dbea`) for the StructuredGridIndexer fix that
  handles curved meshes.
- **"X nodes could not be mapped (outside shell domain)"** → the shell
  extracted from simple_bent doesn't cover all of detail_flat's XY
  extent. Either trim detail_flat, use `--face all`, or extract from a
  larger reference.
- **All-zero stress in the dynain** → check the console output for
  `Part 1 -> Material 1: E=..., nu=...`. If you see `NOT FOUND` or
  `E=0`, your base_model is missing material cards. Add them or use the
  `material:` override above.
