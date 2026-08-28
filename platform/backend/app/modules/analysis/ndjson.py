# 리포트+케이스를 ReportArchive 규격 ra.analysis.v1 NDJSON(run + fact)으로 흘려보낸다.
"""Emit ``ra.analysis.v1`` NDJSON for a report (ReportArchive pull integration).

한 줄에 레코드 하나(NDJSON) — 대용량을 상수 메모리로 흘려보내기 위함. 맨 앞 ``run``
줄에 메타(units/parts/findings)를, 이어서 ``fact`` 줄(케이스×파트×물리량 = 값)을 낸다.
series(시간이력)는 v1 미포함(원본 HTML 재파싱이라 무거움 — 후속).

DynaForge 데이터 모델이 규격의 fact(축·부품·물리량·값)와 1:1이라 변환 로직이 얇다.
sphere 의 axis_meta 에 roll/pitch 가 실리면 ReportArchive 가 구면 분포도를 자동 생성한다.
"""
from __future__ import annotations

import json
from typing import Iterator

SCHEMA = "ra.analysis.v1"

# kind → 해석 종류 식별자(자유 문자열).
_WORKFLOW = {"sphere": "full_angle_drop", "impact": "partial_impact_dwi", "deep": "single_deep"}

# 물리량 단위(SmartTwin ton-mm-s 관례: 응력 MPa, 가속 G, 변위 mm). 단위를 비우면
# 보고서에서 가장 위험한 오류가 되므로 명시한다(규격 §3.1).
_UNITS = {
    "stress": "MPa", "strain": "", "g": "G", "disp": "mm",
    "max_principal_stress": "MPa", "min_principal_stress": "MPa", "vm_strain": "",
}

# (parts_metrics 키, quantity 이름, at_time 키) — 값이 숫자일 때만 fact 로 낸다.
_FACTS = [
    ("peak_stress", "stress", "time_of_peak_stress"),
    ("peak_strain", "strain", None),
    ("peak_g", "g", "time_of_peak_g"),
    ("peak_disp", "disp", None),
    ("peak_principal", "max_principal_stress", None),
    ("min_principal", "min_principal_stress", None),
    ("peak_vm_strain", "vm_strain", None),
]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _axis_meta(identity: dict | None, kind: str) -> dict:
    """케이스 축 메타 — sphere: roll/pitch/yaw, impact: face/x/y. deep: 빈 값."""
    idt = identity or {}
    if kind == "sphere":
        a = idt.get("angle") or {}
        return {k: a.get(k) for k in ("roll", "pitch", "yaw", "category") if a.get(k) is not None}
    if kind == "impact":
        m: dict = {}
        if idt.get("face"):
            m["face"] = idt["face"]
        if idt.get("pos_x") is not None:
            m["x"] = idt["pos_x"]
        if idt.get("pos_y") is not None:
            m["y"] = idt["pos_y"]
        return m
    return {}


def _dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def iter_ndjson_lines(report, cases) -> Iterator[str]:
    """``run`` 1줄 + ``fact`` N줄. report=ImpactReport, cases=list[ImpactCase]."""
    parts = {}
    for p in report.parts or []:
        pid = p.get("part_id")
        if pid is not None:
            parts[str(pid)] = {"part_name": p.get("name"), "group": p.get("group")}

    run = {
        "type": "run",
        "schema": SCHEMA,
        "schema_version": 1,
        "workflow": _WORKFLOW.get(report.kind, report.kind),
        "title": report.label,
        "run_key": report.id,
        "units": _UNITS,
        "parts": parts,
        "quality": {"n_findings": len(report.findings or [])},
        "findings": report.findings or [],
        "analyzed_at": report.created_at.isoformat() if report.created_at else None,
        "project_name": report.project_name,
        "test_dir": report.test_dir,
    }
    yield _dump(run)

    for c in cases:
        meta = _axis_meta(c.identity, report.kind)
        for pid, m in (c.parts_metrics or {}).items():
            if not isinstance(m, dict):
                continue
            for mkey, quantity, tkey in _FACTS:
                v = m.get(mkey)
                if not _is_num(v):
                    continue  # 미측정(None)·비숫자는 건너뜀 (규격 §3.2)
                fact = {
                    "type": "fact",
                    "axis_key": c.case_key,
                    "axis_meta": meta,
                    "part_key": str(pid),
                    "quantity": quantity,
                    "value": v,
                }
                if tkey and _is_num(m.get(tkey)):
                    fact["at_time"] = m.get(tkey)
                yield _dump(fact)
