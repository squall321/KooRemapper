"""Parse an LS-DYNA .k file into structured metadata.

Two sources combined:
  1. `KooRemapper info <file>`  → nodes / elements / parts / bounding box
  2. direct text scan          → *INCLUDE references + *PART titles + keyword list

The result is cached in session_files.meta so the frontend / MCP can answer
"안에 어떤 파일이 들어있는지" (what's inside) without re-running the binary.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.runner.binary import run_kooremapper
from app.runner.kfile_modelmeta import run_modelmeta

_NUM = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
_RE_NODES = re.compile(r"^Nodes:\s+(\d+)", re.M)
_RE_ELEMS = re.compile(r"^Elements:\s+(\d+)", re.M)
_RE_PARTS = re.compile(r"^Parts:\s+(\d+)", re.M)
_RE_MIN = re.compile(rf"^Min bound:\s+\({_NUM},\s*{_NUM},\s*{_NUM}\)", re.M)
_RE_MAX = re.compile(rf"^Max bound:\s+\({_NUM},\s*{_NUM},\s*{_NUM}\)", re.M)
_RE_SIZE = re.compile(rf"^Size:\s+\({_NUM},\s*{_NUM},\s*{_NUM}\)", re.M)


def _parse_info_stdout(text: str) -> dict:
    out: dict = {}
    if m := _RE_NODES.search(text):
        out["nodes"] = int(m.group(1))
    if m := _RE_ELEMS.search(text):
        out["elements"] = int(m.group(1))
    if m := _RE_PARTS.search(text):
        out["parts"] = int(m.group(1))
    if m := _RE_MIN.search(text):
        out["bbox_min"] = [float(m.group(i)) for i in (1, 2, 3)]
    if m := _RE_MAX.search(text):
        out["bbox_max"] = [float(m.group(i)) for i in (1, 2, 3)]
    if m := _RE_SIZE.search(text):
        out["size"] = [float(m.group(i)) for i in (1, 2, 3)]
    out["valid"] = "[OK] Mesh is valid" in text
    return out


# Only scan files that look like keyword decks (skip binary/large blobs).
_KEYWORD_HINT = re.compile(r"^\s*\*", re.M)


def _scan_keywords(path: Path, max_bytes: int = 8_000_000) -> dict:
    """Lightweight text scan for *INCLUDE paths, *PART titles, and keyword set."""
    includes: list[str] = []
    part_titles: list[str] = []
    keywords: dict[str, int] = {}
    try:
        size = path.stat().st_size
        with path.open("r", errors="ignore") as fh:
            text = fh.read(max_bytes)
    except OSError:
        return {}

    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("*"):
            kw = stripped.split()[0].upper()
            keywords[kw] = keywords.get(kw, 0) + 1
            if kw == "*INCLUDE":
                # next non-comment line is the path
                j = i + 1
                while j < n and (lines[j].lstrip().startswith("$") or not lines[j].strip()):
                    j += 1
                if j < n:
                    includes.append(lines[j].strip())
            elif kw == "*PART":
                # the title is the first non-comment data line after *PART
                j = i + 1
                while j < n and (lines[j].lstrip().startswith("$")):
                    j += 1
                if j < n and lines[j].strip() and not lines[j].strip().startswith("*"):
                    part_titles.append(lines[j].strip())
        i += 1

    return {
        "includes": includes,
        "part_titles": part_titles[:50],
        "keyword_counts": keywords,
        "truncated_scan": size > max_bytes,
    }


def inspect_kfile(path: Path) -> dict:
    """Return combined metadata dict for a .k file (best-effort, never raises)."""
    meta: dict = {"filename": path.name}
    suffix = path.suffix.lower()

    # Mesh stats via the binary (only meaningful for keyword decks).
    if suffix in (".k", ".key", ".dyn", ".dynain", ".inc"):
        try:
            res = run_kooremapper(["info", str(path)], cwd=path.parent, timeout=120)
            meta.update(_parse_info_stdout(res.stdout))
            if res.exit_code != 0 and not meta.get("nodes"):
                meta["info_error"] = (res.stderr or res.stdout)[-500:]
        except FileNotFoundError as exc:
            meta["info_error"] = str(exc)
        meta.update(_scan_keywords(path))
        # 파트 메트릭·재료·접촉 connectivity 자동 추출 (detect off — 빠름; 카드 기반).
        # 기하 탐지(detect on)는 무거우므로 온디맨드 엔드포인트에서 실행한다.
        try:
            mm = run_modelmeta(path, detect=False)
            if mm is not None:
                meta["modelmeta"] = mm
        except Exception as exc:  # noqa: BLE001 — inspect 는 절대 실패하면 안 됨
            meta["modelmeta"] = {"error": str(exc)}

    return meta
