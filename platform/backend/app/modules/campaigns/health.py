# 캠페인 런의 건강 수치를 문턱 묶음으로 판정하는 순수 함수 — DB 를 모른다(서비스가 읽고 이 함수가 가른다)
"""런 유효성 판정(요청서 DF-03 · 계획 docs/01-plan/features/df-provenance-health-1122.plan.md 4절).

판정은 저장하지 않는다 — 읽을 때 지금 문턱으로 센다. 문턱을 바꾸면 그 자리에서 다시 판정되고 응답의 `ref` 가 바뀐다.
기본값 넷(에너지비 · HG/IE · 추가 질량 · 미끄럼 무문턱)은 사용자 결정 11-21, KE · 접촉 에너지는 11-22 다.
"""
from __future__ import annotations

import hashlib
import json
import math

DEFAULTS: dict[str, float] = {
    "energy_ratio_max": 1.05,        # 에너지비 ≤ 1.05
    "hg_over_ie_max": 0.10,          # HG/IE < 10 % — 비로 받는다(0.10 = 10 %)
    "added_mass_pct_max": 0.5,       # 추가 질량(기기 값, 없으면 전체 값) 0.5 % 넘으면 warn
    "ke0_rel_tol": 0.10,             # 첫 KE 가 ½mv² 와 10 % 넘게 다르면 warn(우리가 정한 값)
    "contact_energy_min_mJ": -100.0,  # 자체 접촉 에너지가 이보다 낮으면 warn(요청서 함정 줄의 값)
}
# 판정 상태가 invalid 인 까닭 — 나머지 까닭은 warn 이다
INVALID = ("no_report", "health_missing", "termination_unknown", "abnormal_termination", "json_incomplete", "nan", "ke0_zero")


def effective(stored: dict | None) -> dict[str, float]:
    """캠페인에 적힌 문턱(바뀐 열쇠만)과 기본값을 합친 묶음."""
    out = dict(DEFAULTS)
    for k, v in (stored or {}).items():
        if k in out and v is not None:
            out[k] = float(v)
    return out


def ref(values: dict[str, float]) -> str:
    """문턱 묶음의 이름표 — 열쇠를 정렬한 JSON 의 sha256 앞 12 자. 런의 `thresholds_ref` 가 이 값이다."""
    blob = json.dumps({k: float(values[k]) for k in sorted(values)}, separators=(",", ":"))
    return "thr-" + hashlib.sha256(blob.encode()).hexdigest()[:12]


def bundle(stored: dict | None) -> dict:
    """응답에 싣는 문턱 묶음 — 값 · 이름표 · 기본값에서 바뀐 열쇠 · 기본값."""
    values = effective(stored)
    return {"values": values, "ref": ref(values), "changed": sorted(k for k in values if values[k] != DEFAULTS[k]),
            "defaults": dict(DEFAULTS)}


def _num(h: dict, key: str) -> float | None:
    v = h.get(key)
    if v is None or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def judge(health: dict | None, thr: dict[str, float], *, has_report: bool) -> dict:
    """`{status: valid | warn | invalid, reasons: [...]}`. 수치가 빠진 항목은 판정하지 않는다."""
    if not has_report:
        return {"status": "invalid", "reasons": ["no_report"]}
    if not health:
        return {"status": "invalid", "reasons": ["health_missing"]}
    reasons: list[str] = []
    term = health.get("normal_termination")
    if term is None:
        reasons.append("termination_unknown")       # 스케줄러 상태만으로 valid 로 보지 않는다
    elif term is False:
        reasons.append("abnormal_termination")
    if health.get("json_complete") is False:
        reasons.append("json_incomplete")
    if _num(health, "nan_onset_ms") is not None:
        reasons.append("nan")
    ke0, ke0x = _num(health, "ke0_measured"), _num(health, "ke0_expected")
    if ke0 is not None and ke0 <= 0:
        reasons.append("ke0_zero")
    er = _num(health, "energy_ratio_max")
    if er is not None and er > thr["energy_ratio_max"]:
        reasons.append("energy_ratio")
    hg = _num(health, "hg_over_ie_max")
    if hg is not None and hg >= thr["hg_over_ie_max"]:
        reasons.append("hourglass")
    am = _num(health, "added_mass_pct_device")
    if am is None:
        am = _num(health, "added_mass_pct_total")
    if am is not None and am > thr["added_mass_pct_max"]:
        reasons.append("added_mass")
    if ke0 is not None and ke0 > 0 and ke0x is not None and ke0x > 0 and abs(ke0 / ke0x - 1.0) > thr["ke0_rel_tol"] + 1e-12:
        reasons.append("ke0_mismatch")
    ce = _num(health, "contact_energy_min_mJ")
    if ce is not None and ce < thr["contact_energy_min_mJ"]:
        reasons.append("contact_energy")
    if any(r in INVALID for r in reasons):
        status = "invalid"
    elif reasons:
        status = "warn"
    else:
        status = "valid"
    return {"status": status, "reasons": reasons}


def excluded_by(verdict: dict, *, superseded: bool, has_provenance: bool) -> list[str]:
    """기본 통계에서 빼는 까닭 — invalid 의 까닭 · 대체된 런 · 출처가 빈 런. warn 은 넣는다."""
    out = [r for r in verdict["reasons"] if r in INVALID] if verdict["status"] == "invalid" else []
    if superseded:
        out.append("superseded")
    if not has_provenance:
        out.append("provenance_missing")
    return out
