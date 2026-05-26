"""Pull theory document sections into lat.md/theory/<slug>.md.

KooRemapper_Theory_Document.md uses:
  # N. Title          (chapter)
  ## N.M Title        (section)
  ### N.M.K Title     (subsection)

We match by `## N.M ` heading and inject under "## Theory text".

Also pulls bend/indent/formstrain/isoparametric theory from KooRemapper_Manual.md §40.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
THEORY_DOC = ROOT / "docs" / "KooRemapper_Theory_Document.md"
MANUAL = ROOT / "docs" / "KooRemapper_Manual.md"
THDIR = ROOT / "lat.md" / "theory"

# theory_doc section (e.g. "1.2") -> theory page slug
DOC_TO_SLUG = {
    "1.2": "coordinate-systems",
    "2.1": "edge-interpolation",
    "2.2": "arc-length-param",
    "2.3": "transfinite",
    "2.4": "trilinear",
    "2.5": "coons-patch",
    "2.6": "structured-grid",
    "3.1": "deformation-gradient",
    "3.2": "strain-tensor",
    "3.3": "stress-tensor",
    "4.1": "gauss-quadrature",
    "4.2": "shape-functions",
    "4.3": "jacobian",
    "5.1": "isotropic-elastic",
    "5.2": "viscoelastic",
}

# manual section (e.g. "40.3") -> theory slug. (manual numbering, not theory doc)
MANUAL_TO_SLUG = {
    "40.1": "isoparametric-map",
    "40.3": "kirchhoff-plate",
    "40.4": "formstrain-theory",
}

EXCERPT_BEGIN = "<!-- BEGIN EXCERPT -->"
EXCERPT_END = "<!-- END EXCERPT -->"


def parse_sections(text: str, level_marker: str) -> dict[str, tuple[str, str]]:
    """Returns {section_number: (heading_text, body)}."""
    pattern = re.compile(
        r"^" + re.escape(level_marker) + r"\s+(\d+(?:\.\d+)+)\s+(.+?)$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    sections: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(matches):
        num = m.group(1)
        title = m.group(2).strip()
        body_start = m.end()
        # Stop at the NEXT same-or-higher-level heading
        body_end = len(text)
        next_pat = re.compile(r"^" + re.escape(level_marker) + r"\s+\d", re.MULTILINE)
        nm = next_pat.search(text, body_start + 1)
        if nm:
            body_end = nm.start()
        body = text[body_start:body_end].rstrip()
        sections[num] = (title, body)
    return sections


def parse_manual_sub(text: str, parent_section: int) -> dict[str, tuple[str, str]]:
    """Parse `### N.M Title` subsections anywhere in the manual.

    Note: the manual has a numbering quirk — §40 theory subsections
    (### 40.1, 40.2, …) actually live under the ## 41. 수학 이론 chapter.
    So we just grep globally."""
    sub_re = re.compile(r"^### " + str(parent_section) + r"\.(\d+)\s+(.+?)$", re.MULTILINE)
    matches = list(sub_re.finditer(text))
    out: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(matches):
        sub = m.group(1)
        title = m.group(2).strip()
        body_start = m.end()
        # Stop at next ### or ## heading
        next_hd = re.search(r"^#{2,3} ", text[body_start:], re.MULTILINE)
        body_end = body_start + next_hd.start() if next_hd else len(text)
        body = text[body_start:body_end].rstrip()
        out[f"{parent_section}.{sub}"] = (title, body)
    return out


def update_page(page: Path, heading: str, body: str, source_ref: str) -> None:
    text = page.read_text(encoding="utf-8")
    excerpt = (
        f"\n## Theory text\n\n"
        f"_From {source_ref}._\n\n"
        f"{EXCERPT_BEGIN}\n\n{body}\n\n{EXCERPT_END}\n"
    )
    if EXCERPT_BEGIN in text:
        pat = re.compile(
            r"\n## Theory text\n.*?" + re.escape(EXCERPT_END) + r"\n",
            re.DOTALL,
        )
        m = pat.search(text)
        if m:
            text = text[: m.start()] + excerpt + text[m.end():]
        else:
            text = text.rstrip() + "\n" + excerpt
    else:
        text = text.rstrip() + "\n" + excerpt
    page.write_text(text, encoding="utf-8")


def main():
    th_text = THEORY_DOC.read_text(encoding="utf-8")
    man_text = MANUAL.read_text(encoding="utf-8")

    th_sections = parse_sections(th_text, "##")
    man_sub = parse_manual_sub(man_text, 40)

    print(f"Theory doc: parsed {len(th_sections)} ## sections")
    print(f"Manual §40 subsections: {len(man_sub)}")

    n = 0
    skipped = []
    for sec, slug in DOC_TO_SLUG.items():
        page = THDIR / f"{slug}.md"
        if not page.exists():
            skipped.append(f"missing page {slug}.md")
            continue
        if sec not in th_sections:
            skipped.append(f"theory doc §{sec} not found")
            continue
        title, body = th_sections[sec]
        ref = f"[`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §{sec} — {title}"
        update_page(page, title, body, ref)
        n += 1

    for sec, slug in MANUAL_TO_SLUG.items():
        page = THDIR / f"{slug}.md"
        if not page.exists():
            skipped.append(f"missing page {slug}.md")
            continue
        if sec not in man_sub:
            skipped.append(f"manual §{sec} not found")
            continue
        title, body = man_sub[sec]
        ref = f"[`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §{sec} — {title}"
        update_page(page, title, body, ref)
        n += 1

    print(f"Updated {n} theory pages.")
    for s in skipped:
        print(f"  skip: {s}")


if __name__ == "__main__":
    main()
