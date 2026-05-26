"""Insert `// @lat: [[...]]` backlinks into source files.

Idempotent: re-running is safe; existing markers are detected and skipped.

Strategy:
1. For every src/<dir>/*.cpp and *.h, add `// @lat: [[modules/<dir>]]` near the
   top of the file (after the first contiguous #include block, before the first
   non-include statement).
2. For include/<dir>/*.h, same — pointing at modules/<dir>.
3. For src/commands/<name>.cpp, ALSO add `// @lat: [[commands/<name>]]` if a
   command page exists at lat.md/commands/<name>.md.
4. For src/main.cpp, add a per-dispatch backlink immediately before each
   `if (command == "X") {` line where a commands/X.md page exists.

Run from repo root:  python lat.md/_add_backlinks.py
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LATMD = ROOT / "lat.md"

# Maps subdir → wiki node. Some subdirs map to a different page than their name.
MODULE_PAGE = {
    "analysis": "modules/analysis",
    "assembly": "modules/assembly",
    "battery": "modules/battery",
    "cli": "modules/cli",
    "commands": "modules/commands",
    "core": "modules/core",
    "example": "modules/generator",  # example/ folds into generator family
    "generator": "modules/generator",
    "grid": "modules/grid",
    "mapper": "modules/mapper",
    "parser": "modules/parser",
    "remesh": "modules/remesh",
    "squeeze": "modules/squeeze",
    "util": "modules/util",
    "validation": "modules/validation",
}

# Command files in src/commands/ that match lat.md/commands/<name>.md
COMMAND_FILES = {
    "ale": "ale",
    "battery": "battery",
    "cnrb2solid": "cnrb2solid",
    "contact": "contact",
    "contact_helpers": "contact",
    "database": "database",
    "implicit": "implicit",
    "load_boundary": None,  # multi-command file; handled below
    "matdb": "matdb",
    "matswap": "matswap",
    "meshfix": "meshfix",
    "modal": "modal",
    "optimize": "optimize",
    "relax": "relax",
    "squeeze_assemble": "squeeze",
    "stabilize": "stabilize",
    "strip": "strip",
    # core_ops, standalone_ops, merge, tetremesh, hfdamp — no single command
}

# load_boundary.cpp implements load + boundary + rbe. Give it all three.
LOAD_BOUNDARY_LINKS = ["commands/load", "commands/boundary", "commands/rbe"]

# main.cpp dispatch → commands/<page>
MAIN_DISPATCH = {
    "map": "commands/map",
    "shellmap": "commands/shellmap",
    "unfold": "commands/unfold",
    "generate": "commands/generate",
    "generate-var": "commands/generate",
    "strain": "commands/strain",
    "prestress": "commands/prestress",
    "squeeze": "commands/squeeze",
    "assemble": "commands/assemble",
    "matswap": "commands/matswap",
    "matdb": "commands/matdb",
    "load": "commands/load",
    "boundary": "commands/boundary",
    "rbe": "commands/rbe",
    "relax": "commands/relax",
    "explicit": "commands/explicit",
    "implicit": "commands/implicit",
    "modal": "commands/modal",
    "ale": "commands/ale",
    "contact": "commands/contact",
    "optimize": "commands/optimize",
    "stabilize": "commands/stabilize",
    "database": "commands/database",
    "meshfix": "commands/meshfix",
    "info": "commands/info",
    "restack": "commands/restack",
    "bend": "commands/bend",
    "indent": "commands/indent",
    "formstrain": "commands/formstrain",
    "convert": "commands/convert",
    "refine": "commands/refine",
    "elform": "commands/elform",
    "disconnect": "commands/disconnect",
    "iga": "commands/iga",
    "warpage": "commands/warpage",
    "offset": "commands/offset",
    "wrap": "commands/wrap",
    "cnrb2solid": "commands/cnrb2solid",
    "battery": "commands/battery",
    "strip": "commands/strip",
}

LAT_MARKER = "// @lat:"
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]')
DISPATCH_RE = re.compile(r'^(\s*)if\s*\(\s*command\s*==\s*"([^"]+)"\s*\)\s*\{')


def insert_module_backlink(path: Path, wiki_links: list[str]) -> bool:
    """Insert `// @lat: [[...]]` line(s) after the first contiguous include block.

    Returns True if modified, False if already present or no anchor found.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if LAT_MARKER in text:
        return False  # already has at least one backlink — leave alone

    lines = text.splitlines(keepends=True)
    last_include_idx = -1
    for i, ln in enumerate(lines):
        if INCLUDE_RE.match(ln):
            last_include_idx = i
        elif last_include_idx >= 0 and ln.strip() and not ln.strip().startswith("//") \
                and not ln.strip().startswith("/*") and not ln.strip().startswith("*"):
            # First substantive non-include, non-comment line after the include block
            break

    insert_at = last_include_idx + 1 if last_include_idx >= 0 else 0

    # Build the comment block
    comment = "\n// Knowledge graph (lat.md):\n"
    for w in wiki_links:
        comment += f"//   @lat: [[{w}]]\n"

    lines.insert(insert_at, comment)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def annotate_main_dispatch(path: Path) -> int:
    """Add backlink comment before each `if (command == "X") {` dispatch."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    out = []
    inserted = 0
    for ln in lines:
        m = DISPATCH_RE.match(ln)
        if m:
            cmd = m.group(2)
            indent = m.group(1)
            page = MAIN_DISPATCH.get(cmd)
            # Don't re-insert if previous non-empty line already mentions @lat for this cmd
            already = False
            for prev in reversed(out):
                stripped = prev.strip()
                if not stripped:
                    continue
                if stripped.startswith("//") and "@lat:" in stripped and page and f"[[{page}]]" in stripped:
                    already = True
                break
            if page and not already:
                out.append(f"{indent}// @lat: [[{page}]]\n")
                inserted += 1
        out.append(ln)
    if inserted:
        path.write_text("".join(out), encoding="utf-8")
    return inserted


def process_src_tree():
    src = ROOT / "src"
    inc = ROOT / "include"

    modified = []
    skipped = []

    # src/main.cpp gets two treatments: top-level + per-dispatch
    main_cpp = src / "main.cpp"
    if main_cpp.exists():
        if insert_module_backlink(main_cpp, ["modules/commands", "architecture"]):
            modified.append(str(main_cpp.relative_to(ROOT)))
        else:
            skipped.append(str(main_cpp.relative_to(ROOT)))
        n = annotate_main_dispatch(main_cpp)
        if n:
            print(f"  main.cpp: annotated {n} dispatch branches")

    # src/<dir>/*.{cpp,h}
    for cpp in list(src.rglob("*.cpp")) + list(src.rglob("*.h")):
        if cpp.name == "main.cpp":
            continue
        if cpp.suffix == ".bak" or cpp.name.endswith(".bak"):
            continue
        if "_skipped" in cpp.name:
            continue
        rel_parent = cpp.parent.relative_to(src)
        parts = rel_parent.parts
        if not parts:
            continue
        subdir = parts[0]
        module_link = MODULE_PAGE.get(subdir)
        if not module_link:
            continue

        links = [module_link]

        # Special: commands/<name>.cpp → also link to commands/<name>
        if subdir == "commands":
            stem = cpp.stem
            if stem == "load_boundary":
                links.extend(LOAD_BOUNDARY_LINKS)
            else:
                cpage = COMMAND_FILES.get(stem)
                if cpage:
                    links.append(f"commands/{cpage}")

        if insert_module_backlink(cpp, links):
            modified.append(str(cpp.relative_to(ROOT)))
        else:
            skipped.append(str(cpp.relative_to(ROOT)))

    # include/<dir>/*.h
    if inc.exists():
        for hdr in inc.rglob("*.h"):
            rel_parent = hdr.parent.relative_to(inc)
            parts = rel_parent.parts
            if not parts:
                continue
            subdir = parts[0]
            module_link = MODULE_PAGE.get(subdir)
            if not module_link:
                continue
            if insert_module_backlink(hdr, [module_link]):
                modified.append(str(hdr.relative_to(ROOT)))
            else:
                skipped.append(str(hdr.relative_to(ROOT)))

    print(f"\nModified: {len(modified)} files")
    print(f"Skipped (already annotated or no anchor): {len(skipped)} files")


if __name__ == "__main__":
    process_src_tree()
