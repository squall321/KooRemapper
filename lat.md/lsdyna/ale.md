# ALE keywords in KooRemapper

Stub — see [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] and [[commands/ale#ale — Lagrangian → ALE converter (§35)]] for the full pipeline.

## Insertion sequence by [[commands/ale#ale — Lagrangian → ALE converter (§35)]]

For each target solid part, the converter:

1. Changes `*SECTION_SOLID` ELFORM (typical 1 → 11 multi-material).
2. Inserts `*HOURGLASS` with IHQ=3.
3. Inserts `*CONTROL_ALE` (one global card).
4. Inserts `*ALE_MULTI-MATERIAL_GROUP` per MMG.
5. Inserts `*ALE_REFERENCE_SYSTEM_GROUP` with PRTYPE=4.
6. Inserts `*CONSTRAINED_LAGRANGE_IN_SOLID` for FSI coupling (target ↔ Lagrangian).
7. If HE preset: `*INITIAL_DETONATION`.

## Material/EOS pairing

| Preset family | MAT | EOS |
|---------------|-----|-----|
| gas (air/N2/Ar) | `*MAT_NULL` | `*EOS_LINEAR_POLYNOMIAL` |
| liquid (water/oil/coolant/…) | `*MAT_NULL` | `*EOS_GRUNEISEN` |
| explosive (TNT/C4) | `*MAT_HE_BURN` | `*EOS_JWL` |
| vacuum | `*MAT_VACUUM` | — |

See [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]], [[lsdyna/eos#LS-DYNA EOS (equation of state) in KooRemapper]].

## Notes

- Unit assumption: t · mm · s → MPa. Other unit systems require custom bundle files.
- Shared SECID detection: if a target SECID is shared with non-ALE parts, a new
  SECID is created — see [ale.cpp](../../src/commands/ale.cpp).
- `*PART` always has a title line before the data line (with or without `_TITLE`)
  — `ale_buildPartMap` and `ale_updatePartField` must always skip the title.
