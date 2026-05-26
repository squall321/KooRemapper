# Module: src/parser/

LS-DYNA keyword file I/O. The parser is **streaming + line-preserving**: known
keywords parse into typed structs (`Mesh`, `ShellMesh`, MAT tables, …); unknown
keywords are kept in a `rawLines_` buffer for verbatim emit.

## Components

| File | Role |
|------|------|
| [KFileReader.cpp](../../src/parser/KFileReader.cpp) | reads `.k` → mesh + section/material tables + raw lines |
| [KFileWriter.cpp](../../src/parser/KFileWriter.cpp) | writes `.k` (with `useMappedPositions` flag) |
| [DynainWriter.cpp](../../src/parser/DynainWriter.cpp) | emits `*INITIAL_STRESS_SOLID` dynain |
| [ShellReader.cpp](../../src/parser/ShellReader.cpp) | shell-specific parsing helpers |

## Tokenization

- `tokenizeFixed(line, 10)` — 10-char fixed-width fields, used for `*MAT_*` cards.
- For node/element IDs, use `parseNodeIdFromLine` from [[modules/assembly#Module: src/assembly/]] — field
  widths vary (8 or 10) across keyword variants.
- `*PART` always has a title line preceding the data line — even without
  `_TITLE` suffix. Skip the title line as non-comment-non-data.

## Material/section tables

The reader populates:
- per-PID material/section indirection.
- `*SECTION_SOLID` ELFORM → `solidSectionElforms_` map (in [[modules/assembly#Module: src/assembly/]]).
- `*SECTION_SHELL` ELFORM + T1 thickness → `shellSectionElforms_`.

YAML `shell_thickness` overrides the K-file `*SECTION_SHELL` value where present.

## Dynain output

`*INITIAL_STRESS_SOLID` (8-int point integration). For shells,
`*INITIAL_STRESS_SHELL` uses `NPLANE=1, NTHICK=2, T=-1/+1`.

See [[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]] for format and [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] for emission rules.

## Format pitfalls

- `*MAT_ELASTIC` fields are 10-char fixed-width. `7.8500e-09` is 10 chars but a
  separator space breaks alignment — use `  7.85E-09` (10-char padded form).
- PART title lines: `$# comment` is *skipped as comment*. Use a plain string
  ("Inner block") as title.
