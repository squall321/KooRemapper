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
            # 자기완결 메타만 남긴다 (model 의 절점·요소·파트 **카운트**는 inspect 의 info 와 중복).
            #
            # ★단 `model` 의 고아·bbox 기준 세 필드는 **버리지 않는다.** info 는 요소 기준
            #   bbox 만 정규식으로 노출하고 고아 수는 하류가 받을 길이 없다. 그 신호가 없어서
            #   현장에서 낙하판이 기기 밖 53mm 에 생겼다(요소 기준 14.55mm vs 전체 절점
            #   67.50mm). 정규식이 아니라 **JSON 으로** 받으므로 깨지지 않는다.
            model = data.get("model") or {}
            return {
                "parts": data.get("parts", []),
                "connectivity": data.get("connectivity", {}),
                "conventions": data.get("conventions", {}),
                "orphan_nodes": model.get("orphan_nodes"),
                "bbox_basis": model.get("bbox_basis"),
                "bbox_all_min": model.get("bbox_min"),
                "bbox_all_max": model.get("bbox_max"),
                "bbox_used_min": model.get("bbox_used_min"),
                "bbox_used_max": model.get("bbox_used_max"),
                "detect": detect,
            }
        return {"error": (res.stderr or res.stdout or "modelmeta produced no output")[-500:]}
    finally:
        cfg.unlink(missing_ok=True)
        out_json.unlink(missing_ok=True)
