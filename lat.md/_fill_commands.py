"""Pull manual sections into lat.md/commands/<name>.md.

Each command page keeps its existing top matter (title, source/manual/theory refs,
wiki links) and gains the manual section verbatim under "## From the manual".

Idempotent: re-running replaces the prior excerpt block, never duplicates it.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "KooRemapper_Manual.md"
CMDDIR = ROOT / "lat.md" / "commands"

# Manual section number -> command stub filename
SECTION_TO_CMD = {
    4: "map", 5: "shellmap", 6: "prestress", 7: "squeeze",
    8: "generate", 9: "unfold", 10: "strain", 11: "info",
    12: "restack", 13: "bend", 14: "indent", 15: "formstrain",
    16: "convert", 17: "refine", 18: "elform", 19: "disconnect",
    20: "iga", 21: "warpage", 22: "offset", 23: "matswap",
    24: "matdb", 25: "contact", 26: "load", 27: "boundary",
    28: "rbe", 29: "implicit", 30: "modal", 31: "relax",
    32: "explicit", 33: "wrap", 34: "optimize", 35: "ale",
    36: "stabilize", 37: "database", 39: "assemble", 40: "meshfix",
}

EXCERPT_MARK_BEGIN = "<!-- BEGIN MANUAL EXCERPT -->"
EXCERPT_MARK_END = "<!-- END MANUAL EXCERPT -->"

# Manual is structured as `## N. name — description`. Parse on that.
SECTION_RE = re.compile(r"^## (\d+)\.\s+(.+?)$", re.MULTILINE)


def split_manual_sections(text: str) -> dict[int, tuple[str, str]]:
    """Returns {section_number: (heading, body_text)}."""
    matches = list(SECTION_RE.finditer(text))
    sections: dict[int, tuple[str, str]] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        heading = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].rstrip()
        sections[num] = (heading, body)
    return sections


def demote_headings(body: str) -> str:
    """Manual uses ### for subsections inside a section. Keep them ### in the
    target page so they nest under our existing ## headings."""
    return body  # no change needed — ### stays ###


def update_command_page(page: Path, heading: str, body: str) -> bool:
    text = page.read_text(encoding="utf-8")
    excerpt_block = (
        f"\n## From the manual\n\n"
        f"_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) "
        f"§{heading}._\n\n"
        f"{EXCERPT_MARK_BEGIN}\n\n{body}\n\n{EXCERPT_MARK_END}\n"
    )

    if EXCERPT_MARK_BEGIN in text:
        # Replace existing excerpt block (avoid re.sub: backslashes in body
        # would be interpreted as regex escapes in the replacement string)
        pattern = re.compile(
            r"\n## From the manual\n.*?" + re.escape(EXCERPT_MARK_END) + r"\n",
            re.DOTALL,
        )
        m = pattern.search(text)
        if m:
            new_text = text[: m.start()] + excerpt_block + text[m.end():]
        else:
            new_text = text.rstrip() + "\n" + excerpt_block
    else:
        # Drop the trailing "## TODO" block (and anything after it) if present;
        # the manual excerpt now stands in for those open items.
        m = re.search(r"\n## TODO\n", text)
        if m:
            text = text[: m.start()].rstrip() + "\n"
        new_text = text.rstrip() + "\n" + excerpt_block

    page.write_text(new_text, encoding="utf-8")
    return True


def main():
    text = MANUAL.read_text(encoding="utf-8")
    sections = split_manual_sections(text)
    print(f"Parsed {len(sections)} manual sections")

    n = 0
    skipped = []
    for sec, cmd in SECTION_TO_CMD.items():
        if sec not in sections:
            skipped.append(f"§{sec} ({cmd}): not in manual")
            continue
        page = CMDDIR / f"{cmd}.md"
        if not page.exists():
            skipped.append(f"§{sec}: lat.md/commands/{cmd}.md missing")
            continue
        heading, body = sections[sec]
        body = demote_headings(body)
        update_command_page(page, f"{sec}. {heading}", body)
        n += 1

    print(f"Updated {n} command pages.")
    for s in skipped:
        print(f"  skip: {s}")


if __name__ == "__main__":
    main()
