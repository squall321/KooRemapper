# strip — keyword removal (§38)

Source: [strip.cpp](../../src/commands/strip.cpp)
Manual: [`KooRemapper_Manual.md`#38-키워드-제거strip-기능](../../docs/KooRemapper_Manual.md#38-키워드-제거strip-기능)


## Synopsis

```
KooRemapper strip <args>
```

## What it does

Per-command `strip: true` flag (modal/implicit/relax) removes the mode-specific cards without inserting replacements. Contrasts with [[commands/explicit#explicit — pure explicit restoration (§32)]] which targets a different scope.

## Key references

- [[modules/commands#Module: src/commands/]]

## TODO

- Fill YAML schema table from manual.
- Add per-field cross-reference into [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]].
- Note edge cases / idempotency where applicable.
