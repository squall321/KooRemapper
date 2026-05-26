"""Fix the bad relative paths that _normalize_for_lat.py produced.

Two bugs to repair, post-hoc:
  1. Depth off by one: `[X](../src/foo.cpp)` from lat.md/<sub>/X.md should be
     `[X](../../src/foo.cpp)`. Files directly under lat.md/ already had the
     right depth.
  2. Empty labels for directory references: `[](../src/generator/)` → use the
     directory name as the label.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LATMD = ROOT / "lat.md"

REPO_PREFIXES = ("src/", "include/", "docs/", "materials/", "examples/", "tests/")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((\.\./[^)]+)\)")


def fix_file(path: Path) -> int:
    """Returns count of fixes applied."""
    depth = len(path.relative_to(LATMD).parents) - 1  # 0 for top-level, 1 for sub/
    text = path.read_text(encoding="utf-8")
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        label = m.group(1)
        href = m.group(2)
        # Strip leading "../"
        m2 = re.match(r"^((?:\.\./)+)(.*)$", href)
        if not m2:
            return m.group(0)
        dots, tail = m2.group(1), m2.group(2)
        # Only fix if tail starts with a repo-root prefix (src/, include/, …)
        if not tail.startswith(REPO_PREFIXES):
            return m.group(0)
        existing_levels = dots.count("../")
        # We want `(depth + 1) * "../"` to reach repo root from lat.md/<sub>/file.md
        # depth=0 → 1×".."  (already correct, leave alone)
        # depth=1 → 2×".."  (we wrote 1×".." — needs fix)
        wanted = depth + 1
        if existing_levels == wanted:
            return m.group(0)
        new_dots = "../" * wanted
        # Fix empty label: use last path component (dir or file)
        if not label:
            label = tail.rstrip("/").split("/")[-1] or tail
        count += 1
        return f"[{label}]({new_dots}{tail})"

    new_text = MD_LINK_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return count


def main():
    total = 0
    files = 0
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        n = fix_file(p)
        if n:
            files += 1
            total += n
    print(f"Fixed {total} links across {files} files.")


if __name__ == "__main__":
    main()
