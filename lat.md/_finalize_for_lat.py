"""Final pass: produce H1s that survive the lat.md parser intact.

The lat.md parser treats markdown emphasis specially: `*text*`, `_text_`,
and inline-code `` `text` `` are stripped from headings before they become
section IDs. To get faithful section IDs, the H1 needs to be plain text.

This script:
  1. Rewrites every lat.md/**/*.md H1 to plain text (strip `, *, _, [, ]).
  2. Rebuilds the slug→H1 map from the rewritten files.
  3. Walks every [[wiki]] link without an anchor and appends the (now plain)
     H1. Links that already have an anchor are updated only if the anchor
     is stale relative to the current H1.

Re-runs are safe: H1 cleaning + anchor rewriting are both idempotent.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LATMD = ROOT / "lat.md"

H1_RE = re.compile(r"^# +(.+?)$", re.MULTILINE)
WIKI_RE = re.compile(r"\[\[([^\]\|#]+?)(#([^\]\|]+))?\]\]")

EMPH_CHARS = r"`*_[]"


def plainify(h1: str) -> str:
    out = []
    for ch in h1:
        if ch in EMPH_CHARS:
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def update_h1(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    m = H1_RE.search(text)
    if not m:
        return None
    orig = m.group(1)
    cleaned = plainify(orig)
    if orig != cleaned:
        text = text[: m.start()] + f"# {cleaned}" + text[m.end():]
        path.write_text(text, encoding="utf-8")
    return cleaned


def build_slug_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(LATMD).with_suffix("").as_posix()
        h1 = update_h1(p)
        if h1:
            out[rel] = h1
            out.setdefault(p.stem, h1)
    return out


def rewrite_links(path: Path, slug_map: dict[str, str]) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        target = m.group(1).strip()
        anchor = m.group(3)
        # Only act on lat.md-internal wiki links (no file extension)
        if "." in target.split("/")[-1]:
            return m.group(0)
        h1 = slug_map.get(target) or slug_map.get(target.split("/")[-1])
        if not h1:
            return m.group(0)
        if anchor == h1:
            return m.group(0)
        n += 1
        return f"[[{target}#{h1}]]"

    new_text = WIKI_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n


def main():
    slug_map = build_slug_map()
    print(f"Slug map: {len(slug_map)} entries")
    print("Sample cleaned H1s:")
    for k in ("lsdyna/mat", "commands/ale", "modules/assembly", "theory/viscoelastic"):
        print(f"  {k} → {slug_map.get(k)!r}")
    total = 0
    files = 0
    for p in LATMD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        n = rewrite_links(p, slug_map)
        if n:
            total += n
            files += 1
    print(f"Rewrote {total} link anchors across {files} files.")


if __name__ == "__main__":
    main()
