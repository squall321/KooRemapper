"""Normalize lat.md/ wiki links so the official `lat check` accepts them.

Findings from running `npx lat.md check md`:
  1. Every wiki link must include the target file's H1 heading after `#`.
     `[[architecture]]` ── nope.   `[[architecture#Architecture]]` ── yes.
  2. The lat.md parser truncates H1 text at the first backtick. So we strip
     backticks from all H1s before building the slug→H1 map.
  3. .cpp / .k / .yaml files are not supported by `lat check`. Convert any
     `[[src/foo.cpp]]` style references to plain markdown links `[foo.cpp](src/foo.cpp)`.

Idempotent: re-running detects already-normalized links and leaves them alone.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LATMD = ROOT / "lat.md"

H1_RE = re.compile(r"^# +(.+?)$", re.MULTILINE)
WIKI_RE = re.compile(r"\[\[([^\]\|#]+?)(#([^\]\|]+))?\]\]")

UNSUPPORTED_EXTS = {".cpp", ".k", ".yaml", ".yml", ".json", ".md~", ".bak"}


def clean_h1(h1: str) -> str:
    """Strip backticks; collapse spaces."""
    return re.sub(r"\s+", " ", h1.replace("`", "").strip())


def normalize_h1(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = H1_RE.search(text)
    if not m:
        return None
    orig = m.group(1)
    cleaned = clean_h1(orig)
    if orig != cleaned:
        new_text = text[: m.start()] + f"# {cleaned}" + text[m.end():]
        path.write_text(new_text, encoding="utf-8")
    return cleaned


def build_slug_map() -> dict[str, str]:
    """slug → H1 heading text, with slug as relative path without .md."""
    out: dict[str, str] = {}
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(LATMD).with_suffix("").as_posix()
        h1 = normalize_h1(p)
        if h1:
            out[rel] = h1
            # Also accept the bare stem
            stem = p.stem
            out.setdefault(stem, h1)
    return out


def is_source_ref(target: str) -> bool:
    t = target.strip()
    if t.startswith(("src/", "include/", "docs/", "materials/", "examples/", "tests/")):
        return True
    # Anything with a file extension other than .md
    if "/" in t and Path(t).suffix and Path(t).suffix != ".md":
        return True
    return False


def rewrite_file(path: Path, slug_map: dict[str, str]) -> tuple[int, int]:
    """Returns (anchors_added, source_refs_converted)."""
    text = path.read_text(encoding="utf-8")
    anchors_added = 0
    source_refs = 0

    def repl(m: re.Match) -> str:
        nonlocal anchors_added, source_refs
        target = m.group(1).strip()
        anchor = m.group(3)
        # Code/source reference → plain markdown link
        if is_source_ref(target):
            # Drop any #symbol fragment for the path part
            base = target.split("#", 1)[0]
            label = base if "/" in base else base
            source_refs += 1
            return f"[{label}](../../{base})" if path.parent != LATMD else f"[{label}]({base})"
        # Already anchored → leave alone
        if anchor:
            return m.group(0)
        # Resolve to H1
        h1 = slug_map.get(target) or slug_map.get(target.split("/")[-1])
        if not h1:
            return m.group(0)  # leave broken; we'll see it in lat check
        anchors_added += 1
        return f"[[{target}#{h1}]]"

    new_text = WIKI_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return anchors_added, source_refs


def compute_relpath(from_file: Path, to_target: str) -> str:
    """Compute correct relative path from from_file (inside lat.md/) to a
    repo-root-relative target like 'src/foo.cpp'."""
    # How many directory levels deep is from_file under lat.md/?
    depth = len(from_file.relative_to(LATMD).parents) - 1
    # Need depth ".." prefix
    return ("../" * depth) + to_target


def rewrite_file_v2(path: Path, slug_map: dict[str, str]) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    anchors_added = 0
    source_refs = 0

    def repl(m: re.Match) -> str:
        nonlocal anchors_added, source_refs
        target = m.group(1).strip()
        anchor = m.group(3)
        if is_source_ref(target):
            base = target.split("#", 1)[0]
            symbol = target.split("#", 1)[1] if "#" in target else ""
            label = base.split("/")[-1]
            if symbol:
                label = f"{label}#{symbol}"
            rel = compute_relpath(path, base)
            source_refs += 1
            return f"[{label}]({rel})"
        if anchor:
            return m.group(0)
        h1 = slug_map.get(target) or slug_map.get(target.split("/")[-1])
        if not h1:
            return m.group(0)
        anchors_added += 1
        return f"[[{target}#{h1}]]"

    new_text = WIKI_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return anchors_added, source_refs


def main():
    slug_map = build_slug_map()
    print(f"Built slug map: {len(slug_map)} entries")

    total_anchors = 0
    total_source = 0
    files_touched = 0
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        a, s = rewrite_file_v2(p, slug_map)
        if a or s:
            files_touched += 1
            total_anchors += a
            total_source += s

    print(f"Files modified: {files_touched}")
    print(f"Anchors appended: {total_anchors}")
    print(f"Source refs converted: {total_source}")


if __name__ == "__main__":
    main()
