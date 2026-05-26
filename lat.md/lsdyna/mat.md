# LS-DYNA MAT cards in KooRemapper

Stub. See [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] for the canonical line index.

## Format rules

LS-DYNA MAT cards use **strict 10-character fixed-width fields**. Values
that don't fit exactly break field alignment. Notable case:

- `7.8500e-09` → 10 chars but a separator space pushes the next field. Use the
  padded form `  7.85E-09` (2 spaces + 8-char number = 10 chars) instead.

This is enforced by [KFileReader.cpp](../../src/parser/KFileReader.cpp) (10-char tokenizer)
and the writers in [[modules/parser#Module: src/parser/]].

## Material model mapping

KooRemapper's internal [MaterialModel.cpp](../../src/analysis/MaterialModel.cpp) is
constructed via the factory `MaterialModel::isotropicElastic(E, nu)` (constructor
is private). Only the elastic family round-trips to stress/strain analysis;
plasticity values (sigy from MAT_024 Card 1 Field 5) are consumed by
[[commands/formstrain#formstrain — shell forming plastic EPS (§15)]] but not modelled as a constitutive law.

## TODO

- Per-card field tables (`MAT_ELASTIC`: RO/E/PR/DA/DB; `MAT_024`: SIGY/ETAN/EPPF/…).
- Cross-reference to [[modules/validation#Module: src/validation/]].
- Title→name matcher rules used by [[commands/matdb#matdb — material DB lookup + replacement (§24)]].
