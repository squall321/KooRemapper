# sphere 리포트 임베드 데이터를 가벼운 본과 각도별 시계열로 나눠 원본 옆 곁파일로 두는 저장소
"""Sidecar block store for large sphere reports.

A 1,000-angle sphere report embeds ~0.5 GB of JSON, almost all of it per-angle,
per-part time series (``results[i].parts[pid].*_ts``). Detail queries other than
``part_series`` never read those series, so next to the source HTML we keep::

    .<html name>.blocks/
        meta.json            format · source sha256 · case index · list_blocks(full)
        slim.json.gz         the data minus every results[i].parts[pid].*_ts
        cases/<i>.json.gz    {pid: {*_ts: …}} for results[i]

Pure file I/O and dict surgery — callers run it in a worker thread.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from pathlib import Path

from app.reports import parser

FORMAT = 1
_GZ_LEVEL = 3


def sidecar_dir(html_path: Path) -> Path:
    return html_path.with_name(f".{html_path.name}.blocks")


def _is_series(key: str) -> bool:
    return key.endswith("_ts")


def case_key_of(result: dict) -> str | None:
    """케이스 키 — `normalize_sphere` · `part_series` 와 같은 규칙(folder, 없으면 각도 이름)."""
    return result.get("folder") or (result.get("angle") or {}).get("name")


def split(data: dict) -> tuple[dict, list[dict]]:
    """→ (slim, heavy). heavy[i] = {pid: {시계열 키: 값}} — results[i] 의 `*_ts` 전부."""
    slim_results: list = []
    heavy: list[dict] = []
    for r in data.get("results") or []:
        parts = r.get("parts") if isinstance(r, dict) else None
        if not isinstance(parts, dict):
            slim_results.append(r)
            heavy.append({})
            continue
        light, series = {}, {}
        for pid, p in parts.items():
            if not isinstance(p, dict):
                light[pid] = p
                continue
            light[pid] = {k: v for k, v in p.items() if not _is_series(k)}
            s = {k: v for k, v in p.items() if _is_series(k)}
            if s:
                series[pid] = s
        slim_results.append({**r, "parts": light})
        heavy.append(series)
    return {**data, "results": slim_results}, heavy


def merge_case(slim: dict, index: int, heavy_case: dict) -> None:
    """slim 의 results[index] 에 그 각도의 시계열을 제자리에서 되붙인다."""
    parts = slim["results"][index].get("parts") or {}
    for pid, series in heavy_case.items():
        if isinstance(parts.get(pid), dict):
            parts[pid].update(series)


def _dump_gz(path: Path, obj) -> int:
    """gzip JSON 으로 쓰고, `parser._rough_bytes` 와 같은 셈(직렬화 글자 수)을 돌려준다."""
    s = json.dumps(obj, ensure_ascii=False, default=str)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=_GZ_LEVEL) as f:
        f.write(s)
    return len(s)


def _load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write(html_path: Path, data: dict, src_sha256: str | None) -> dict:
    """곁파일을 새로 만든다 — 임시 폴더에 다 쓴 뒤 이름을 바꾼다(반쯤 쓴 곁파일을 남기지 않는다)."""
    slim, heavy = split(data)
    index: dict[str, int] = {}
    for i, r in enumerate(data.get("results") or []):
        k = case_key_of(r) if isinstance(r, dict) else None
        if k is not None:
            index.setdefault(str(k), i)
    final = sidecar_dir(html_path)
    tmp = Path(tempfile.mkdtemp(prefix=final.name + ".", dir=final.parent))
    try:
        (tmp / "cases").mkdir()
        _dump_gz(tmp / "slim.json.gz", slim)
        heavy_bytes = sum(_dump_gz(tmp / "cases" / f"{i}.json.gz", h) for i, h in enumerate(heavy))
        # 블록 목록은 **전체 기준**이어야 한다 — slim 으로 세면 results 가 작게 보인다. 시계열의 글자 수를 더한다
        # (전체를 한 번 더 직렬화하지 않는다 — 1,000각도면 수백 MB 문자열이 생긴다). 크기는 원래 어림이다.
        blocks = parser.list_blocks(slim)
        for b in blocks["blocks"]:
            if b["name"] == "results" and b["bytes"] >= 0:
                b["bytes"] += heavy_bytes
        meta = {"format": FORMAT, "src_sha256": src_sha256, "n_cases": len(heavy),
                "case_index": index, "blocks": blocks}
        (tmp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        os.replace(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return meta


def read_meta(html_path: Path) -> dict | None:
    try:
        return json.loads((sidecar_dir(html_path) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_fresh(meta: dict | None, src_sha256: str | None) -> bool:
    """꼴 판과 원본 sha256 이 맞을 때만 쓴다. sha 를 모르면(None) 믿지 않는다."""
    return bool(meta) and meta.get("format") == FORMAT and src_sha256 is not None \
        and meta.get("src_sha256") == src_sha256


def load_slim(html_path: Path) -> dict:
    return _load_gz(sidecar_dir(html_path) / "slim.json.gz")


def load_case(html_path: Path, index: int) -> dict:
    return _load_gz(sidecar_dir(html_path) / "cases" / f"{index}.json.gz")


def remove(html_path: Path) -> None:
    shutil.rmtree(sidecar_dir(html_path), ignore_errors=True)
