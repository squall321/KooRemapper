"""Lightweight link-integrity check for the lat.md/ knowledge graph.

Reports unresolved [[wiki]] links — both lat.md-internal and source-file refs.
This is a stand-in for `lat check` until the official CLI is installed.

Run from repo root:  python lat.md/_check.py
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
LATMD = ROOT / "lat.md"

WIKI_RE = re.compile(r"\[\[([^\]\|]+?)(?:#([^\]\|]+))?\]\]")
# Match wiki links inside inline code (backticks) so we can skip them
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def collect_known_targets() -> set[str]:
    """All .md files under lat.md/ — keyed by slug without extension, with
    posix-style path relative to lat.md/."""
    known = set()
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(LATMD).with_suffix("").as_posix()
        known.add(rel)
        # Also accept the bare filename (e.g. "architecture")
        known.add(p.stem)
    return known


def resolve(target: str, known: set[str]) -> bool:
    """Return True iff target resolves to a known lat.md page OR a source path."""
    # Normalize: strip leading ./ or /
    t = target.strip().lstrip("/")
    # Source code reference: starts with src/, include/, docs/, or has /
    if t.startswith(("src/", "include/", "docs/", "materials/", "examples/", "tests/")):
        # Check the underlying file exists (drop any #symbol fragment)
        path = t
        candidate = ROOT / path
        return candidate.exists()
    # lat.md internal — try the full path, then the bare stem
    if t in known:
        return True
    if t.split("/")[-1] in known:
        return True
    # Allow references to memory files at repo root (feedback_*, project_*)
    if (ROOT / Path("C:/Users/Sonic/.claude/projects/d--KooRemapper/memory") /
            f"{t.lstrip('../')}.md").exists():
        return True
    return False


def main():
    known = collect_known_targets()
    print(f"Known lat.md targets: {len(known)}")

    total = 0
    unresolved: list[tuple[str, str]] = []
    for md in LATMD.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        # Mask out inline-code spans so syntax-example wiki links don't count
        text = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
        for m in WIKI_RE.finditer(text):
            total += 1
            target = m.group(1)
            if not resolve(target, known):
                unresolved.append((str(md.relative_to(ROOT)), target))

    print(f"Total [[wiki]] refs: {total}")
    print(f"Unresolved: {len(unresolved)}")
    if unresolved:
        print()
        seen = set()
        for src, tgt in unresolved:
            key = (src, tgt)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {src}  ->  [[{tgt}]]")

    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())
