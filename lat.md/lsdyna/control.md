# LS-DYNA CONTROL cards in KooRemapper

Stub — see [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] for the line index.

## Used by

- [[commands/implicit#implicit — Explicit → Implicit converter (§29)]] — inserts `*CONTROL_IMPLICIT_GENERAL/SOLUTION/AUTO/STABILIZATION`.
- [[commands/modal#modal — natural frequency / modal analysis (§30)]] — inserts `*CONTROL_IMPLICIT_EIGENVALUE` (+ GENERAL/SOLUTION).
- [[commands/relax#relax — Dynamic Relaxation setup (§31)]] — inserts `*CONTROL_DYNAMIC_RELAXATION`.
- [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] — modifies `*CONTROL_CONTACT`, `*CONTROL_SHELL`, `*CONTROL_HOURGLASS`.
- [[commands/database#database — DATABASE output control (§37)]] — pairs with `*CONTROL_OUTPUT`.
- [[commands/ale#ale — Lagrangian → ALE converter (§35)]] — inserts `*CONTROL_ALE`.

## Cross-cutting rules

- Existing `*CONTROL_IMPLICIT_*` cards trigger a **WARNING + replace** in
  [[commands/modal#modal — natural frequency / modal analysis (§30)]] / [[commands/implicit#implicit — Explicit → Implicit converter (§29)]].
- `*CONTROL_TERMINATION` is replaced (existing block skipped until next keyword)
  whenever a converter needs `endtim` adjustments — see
  [implicit.cpp](../../src/commands/implicit.cpp), [modal.cpp](../../src/commands/modal.cpp).
- `*CONTROL_CONTACT` has both Card 1 and Card 2; [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] uses
  `stab_ensureControlContactCard2()` to guarantee Card 2 exists before tuning.

## TODO

- Per-keyword field meanings actually relied upon (dctol/ectol/nsolvr/lsolvr/…).
- IHQ values modified by [[commands/stabilize#stabilize — explicit solver stabilization (§36)]] (1→4→6) — see level spectrum.
