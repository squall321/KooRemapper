# LS-DYNA EOS (equation of state) in KooRemapper

Stub. EOS is only consumed by the ALE converter ([[commands/ale#ale — Lagrangian → ALE converter (§35)]]) so far.

| EOS | Preset family | Reference |
|-----|---------------|-----------|
| `*EOS_LINEAR_POLYNOMIAL` | gas (ideal-gas approximation) | [Vol_I.txt:29108](../../docs/LSDyna/Vol_I.txt#L29108) |
| `*EOS_IDEAL_GAS` | gas (alternate) | [Vol_I.txt:29109](../../docs/LSDyna/Vol_I.txt#L29109) |
| `*EOS_GRUNEISEN` | liquid / dense fluid | (Vol_I EOS section) |
| `*EOS_JWL` | high explosive | (Vol_I EOS section) |

TODO: fill exact line numbers, polynomial coefficients used in each preset, and
link to bundle files under `materials/`.
