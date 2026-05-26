# battery — battery mesh/control generator

Source: [battery.cpp](../../src/commands/battery.cpp), [[modules/battery#Module: src/battery/]]
Manual: [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md)


## Synopsis

```
KooRemapper battery <args>
```

## What it does

Generates stacked or wound battery cell meshes with materials, contacts, swelling, and control cards from a YAML config.

## Key references

- [[modules/battery#Module: src/battery/]]
- artifacts: `battery_*.k` in repo root

## TODO

- Fill YAML schema table from manual.
- Add per-field cross-reference into [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]].
- Note edge cases / idempotency where applicable.
