# Module: src/commands/

Each CLI subcommand has its own translation unit under
[`src/commands/`](../../src/commands). All entry points have the signature
`int runXxx(const std::vector<std::string>& args)` and are dispatched from
[main.cpp](../../src/main.cpp).

## Dispatch

The dispatcher in [main.cpp](../../src/main.cpp) selects by `argv[1]`. Argument shapes:

- **Positional** (legacy): `KooRemapper map input.k template.k output.k`.
- **YAML config**: `KooRemapper <cmd> config.yaml` — preferred for new commands.

Many commands now accept **both**, with YAML taking precedence.

## File map

| File | Command(s) | Wiki node |
|------|------------|-----------|
| `ale.cpp` | `ale` | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] |
| `battery.cpp` | `battery` | [[commands/battery#battery — battery mesh/control generator]] |
| `cnrb2solid.cpp` | `cnrb2solid` | [[commands/cnrb2solid#cnrb2solid — CNRB → solid conversion]] |
| `contact.cpp` + `contact_helpers.cpp` | `contact` (analyze/create/convert/modify/remove/detect) | [[commands/contact#contact — CONTACT analyze/create/convert/modify/remove/detect (§25)]] |
| `core_ops.cpp` | shared core ops invoked by `assemble` | [[modules/assembly#Module: src/assembly/]] |
| `database.cpp` | `database` | [[commands/database#database — DATABASE output control (§37)]] |
| `hfdamp.cpp` | `hfdamp` | TODO |
| `implicit.cpp` | `implicit` | [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] |
| `load_boundary.cpp` | `load`, `boundary`, `rbe` | [[commands/load#load — load application (§26)]], [[commands/boundary#boundary — boundary conditions (§27)]], [[commands/rbe#rbe — RBE constraint (§28)]] |
| `matdb.cpp` | `matdb` | [[commands/matdb#matdb — material DB lookup + replacement (§24)]] |
| `matswap.cpp` | `matswap` | [[commands/matswap#matswap — material bundle parameter swap (§23)]] |
| `merge.cpp` | mesh merge (low-level) | TODO |
| `meshfix.cpp` | `meshfix` (Gmsh-based TET4 remesh) | [[commands/meshfix#meshfix — TET4 Gmsh-based remesh (§40)]] |
| `modal.cpp` | `modal` | [[commands/modal#modal — natural frequency / modal analysis (§30)]] |
| `optimize.cpp` | `optimize` | [[commands/optimize#optimize — material-specific solver presets (§34)]] |
| `relax.cpp` | `relax` | [[commands/relax#relax — Dynamic Relaxation setup (§31)]] |
| `squeeze_assemble.cpp` | `squeeze` (assemble-mode integration) | [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]] |
| `stabilize.cpp` | `stabilize` | [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] |
| `standalone_ops.cpp` | `convert`, `refine`, `elform`, `unfold`, `wrap`, … | various |
| `strip.cpp` | `strip` (keyword removal) | [[commands/strip#strip — keyword removal (§38)]] |
| `tetremesh.cpp` | TET remesh integration | [[modules/remesh#Module: src/remesh/]] |

## YAML conventions

- Path resolution: only prepend the YAML's directory if the value has **no**
  directory separator (avoids double-prefixing absolute paths).
- Quote stripping (`stripQuotes`) is required for YAML values that may appear
  quoted (`"value"`) — see [[commands/matdb#matdb — material DB lookup + replacement (§24)]].
- `*` as a `match:` value means catch-all auto-match in [[commands/matdb#matdb — material DB lookup + replacement (§24)]].

## Cross-cutting helpers

- `kw_util.h` — small keyword string helpers (uppercase compare, prefix match).
- `contact_defs.h` — type tags shared across contact files.
