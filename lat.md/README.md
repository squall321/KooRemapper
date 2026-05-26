# lat.md — KooRemapper Knowledge Graph

This directory is a [lat.md](https://github.com/1st1/lat.md)-style knowledge graph for the
KooRemapper project. It interlinks three sources of truth:

1. **Code** — `src/`, `include/` C++ sources.
2. **Manuals** — [`docs/KooRemapper_Manual.md`](../docs/KooRemapper_Manual.md) (user-facing) and
   [`docs/KooRemapper_Theory_Document.md`](../docs/KooRemapper_Theory_Document.md) (algorithms).
3. **LS-DYNA references** — `docs/LSDyna/Vol_I.txt`, `Vol_II.txt`, `Vol_III.txt`, `IGA.txt`.

## Entry points

- [[index#KooRemapper — Knowledge Graph Index]] — top-level table of contents
- [[architecture#Architecture]] — system-level design
- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] — LS-DYNA keyword cross-reference
- [[theory/index#Theory Index]] — algorithmic theory anchors
- [[glossary#Glossary]] — domain terminology

## Conventions

| Token | Meaning |
| ----- | ------- |
| `[` + `[name]` + `]` | wiki link to `lat.md/<name>.md` (literal example: see [[index#KooRemapper — Knowledge Graph Index]]) |
| `[` + `[name#Section]` + `]` | wiki link to a heading inside `<name>.md` |
| `[` + `[src/<path>.cpp#symbol]` + `]` | code reference (header symbol, free function, class method) |
| `[file:line](path#Lnnn)` | clickable external reference (LS-DYNA manuals, generated artifacts) |
| `// @lat: [` + `[file#Section]` + `]` | source-side backlink — to be added incrementally |

## Status

**Populated**: command pages mirror the user manual; theory pages mirror the theory
document; LS-DYNA keyword pages cross-reference Vol_I/II line numbers. Source files
under `src/` and `include/` carry `// @lat: [[...]]` backlinks (182 files, 40 dispatch
branches in `src/main.cpp`).

The graph tracks the source of truth that produced it; when behavior changes in code,
update the corresponding node here. Treat lat.md as documentation of the *why*; the
*what* lives in code.

## Validation

Two validators are checked in under `lat.md/_*.py`:

```sh
python lat.md/_check.py            # our wiki-link validator (currently: 0 unresolved)
npx --yes lat.md@latest check md   # official lat CLI — see Windows compat note below
```

### Windows compat note (lat.md 0.11.0)

The official `lat.md` CLI has a Windows-specific bug in `buildFileIndex` —
`s.file.split('/')` doesn't split Windows-style backslash paths, so bare-stem
resolution (`[[file#H1]]`) fails. Workarounds:

1. Use our `lat.md/_check.py` for validation on Windows (already passes 100%).
2. Or, on WSL / Linux / macOS, the official `lat check md` works against this graph.
3. The C++ family (`.cpp`) is not on the lat.md supported-extensions list. Our
   source backlinks remain valid documentation pointers but don't validate via
   `lat check code-refs`. We treat them as semantically meaningful regardless.

## Regeneration

The graph was built by composable scripts (idempotent — safe to re-run):

| Script | Purpose |
|--------|---------|
| `_generate_stubs.py` | initial command + theory page skeleton |
| `_fill_commands.py`  | inject manual sections into command pages |
| `_fill_theory.py`    | inject theory-doc sections into theory pages |
| `_add_backlinks.py`  | insert `// @lat:` comments into `src/` + `include/` |
| `_normalize_for_lat.py` | append `#H1` anchors to wiki links + convert source refs to markdown |
| `_fix_paths.py`      | repair relative-path depth in source refs |
| `_finalize_for_lat.py` | strip markdown emphasis from H1s + re-anchor |
| `_check.py`          | validate all internal wiki links |

## File map

```text
lat.md/
├── README.md             (this file)
├── index.md              top-level TOC + node summary
├── architecture.md       system architecture
├── glossary.md           domain vocabulary
├── modules/              code-module nodes (one per src/<dir>)
│   ├── analysis.md       (strain/stress/material)
│   ├── assembly.md       (ModelAssembler + operations)
│   ├── battery.md        (battery mesh + control)
│   ├── cli.md
│   ├── commands.md       (command dispatch overview)
│   ├── core.md           (Mesh/Node/Element/Vector3D)
│   ├── generator.md
│   ├── grid.md
│   ├── mapper.md
│   ├── parser.md
│   ├── remesh.md
│   ├── squeeze.md
│   ├── util.md
│   └── validation.md
├── commands/             (one node per CLI subcommand)
│   └── ... (see commands/index.md)
├── theory/               (algorithmic theory; mirrors KooRemapper_Theory_Document.md)
│   └── index.md
└── lsdyna/               (LS-DYNA manual cross-reference)
    ├── keywords.md       master keyword → Vol_X.txt line map
    ├── mat.md            *MAT_* nodes used by KooRemapper
    ├── control.md        *CONTROL_* nodes
    ├── ale.md            ALE-specific
    ├── eos.md            equation-of-state
    ├── initial.md        *INITIAL_*
    ├── section.md        *SECTION_*
    └── element.md        *ELEMENT_*
```
