# K파일에서 파트별 메트릭·재료·접촉 connectivity 를 modelmeta op 로 추출한다.
"""Run the `modelmeta` op and return its structured JSON.

Used on upload (detect off — card-based connectivity + per-part metrics, fast)
and on demand (detect on — geometric contact-pair detection, slower). The op
writes ``<output>_modelmeta.json``; we read, parse, and clean up temp files.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.runner.binary import run_kooremapper

_MM_SUFFIXES = (".k", ".key", ".dyn", ".dynain", ".inc")


def run_modelmeta(path: Path, *, detect: bool = False, timeout: int = 120) -> dict | None:
    """Return the modelmeta result dict for a keyword deck, or None if N/A.

    ``detect=True`` also runs geometric contact-pair detection (slower). Never
    raises — returns ``{"error": ...}`` on failure so callers can store it.
    """
    if path.suffix.lower() not in _MM_SUFFIXES:
        return None

    stem = path.stem
    cfg = path.parent / f".mm_{stem}.yaml"
    out_base = f".mm_{stem}"
    out_json = path.parent / f"{out_base}_modelmeta.json"
    cfg.write_text(
        f"model: {path.name}\noutput: {out_base}\n"
        f"detect: {'true' if detect else 'false'}\ngap_tol: 0.05\n"
    )
    try:
        res = run_kooremapper(["modelmeta", cfg.name], cwd=path.parent, timeout=timeout)
        if out_json.exists():
            try:
                data = json.loads(out_json.read_text())
            except (OSError, ValueError) as exc:
                return {"error": f"modelmeta JSON parse failed: {exc}"}
            # 자기완결 메타만 남긴다 (model 카운트는 inspect 의 info 와 중복).
            return {
                "parts": data.get("parts", []),
                "connectivity": data.get("connectivity", {}),
                "conventions": data.get("conventions", {}),
                "detect": detect,
            }
        return {"error": (res.stderr or res.stdout or "modelmeta produced no output")[-500:]}
    finally:
        cfg.unlink(missing_ok=True)
        out_json.unlink(missing_ok=True)
