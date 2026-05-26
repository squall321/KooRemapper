# LS-DYNA INITIAL cards in KooRemapper

Stub. KooRemapper emits initial-state cards for prestress / formstrain / indent
pipelines.

| Keyword | Emitter |
|---------|---------|
| `*INITIAL_STRESS_SOLID` | [DynainWriter.cpp](../../src/parser/DynainWriter.cpp) — solid dynain output |
| `*INITIAL_STRESS_SHELL` (NPLANE=1, NTHICK=2, T=±1) | [[commands/formstrain#formstrain — shell forming plastic EPS (§15)]], [[commands/indent#indent — indent/emboss (§14)]] (shell) |
| `*INITIAL_STRAIN_SOLID` | [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] (large-strain mode) |
| `*INITIAL_DETONATION` | [[commands/ale#ale — Lagrangian → ALE converter (§35)]] (HE preset) |

## Stress merging convention

When [[commands/assemble#assemble — multi-operation YAML composer (§39)]] runs multiple stress-producing operations over the
same element, the contributions are **summed** in
[ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) via a `std::map<elemId, StressTensor>`
accumulator. Plastic strain (EPS) uses **max()** instead of sum (see
[[commands/formstrain#formstrain — shell forming plastic EPS (§15)]]).

## TODO

- `*INITIAL_STRESS_SOLID` field layout (8 stress components + history vars).
- Shell sampling sign convention (T=-1 bottom, T=+1 top — verified against Vol_I).
