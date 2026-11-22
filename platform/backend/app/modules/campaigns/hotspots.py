# 캠페인 핫스팟 자리(DF-07) — 각도마다의 핫스팟 군집을 덱 틀로 옮겨 반경 안에서 묶고 자리마다 되풀이 · 응력 분포 · bbox 포함률을 세는 순수 함수
"""핫스팟 자리 묶기(요청서 DF-07 · 계획 docs/01-plan/features/df-hotspot-session-1122.plan.md 3절).

군집 중심은 결과(d3plot) 틀이다 — 덱 틀 = 결과 틀 + 이동값. 묶기는 최대 응력(절댓값)이 큰 군집부터 반경 안의 첫 자리에 넣고 없으면 새 자리를
만든다(자리 중심 = 든 군집 중심의 평균). 같은 입력이면 같은 자리가 나온다.
"""
from __future__ import annotations

import math

from app.modules.campaigns.angles import distribution, quantile

DEFAULT_RADIUS_MM = 5.0
BBOX_TOL_MM = 1.0


def _vec(c) -> list[float] | None:
    if not isinstance(c, (list, tuple)) or len(c) != 3:
        return None
    try:
        v = [float(x) for x in c]
    except (TypeError, ValueError):
        return None
    return v if all(math.isfinite(x) for x in v) else None


def default_radius(items: list[dict]) -> float:
    """군집 반경(radius_enclosing) 가운데값의 2 배 — 없으면 5 mm."""
    rs = sorted(r for i in items if (r := i.get("radius_enclosing")) is not None and r > 0)
    return 2.0 * quantile(rs, 0.5) if rs else DEFAULT_RADIUS_MM


def sites(items: list[dict], offset: tuple[float, float, float], radius: float) -> list[dict]:
    """군집 → 자리. `items` 항목 — `{run_key, case_key, doe, report_id, center, stress_max, radius_enclosing}`(center 는 결과 틀)."""
    pts = []
    for it in items:
        c = _vec(it.get("center"))
        if c is None:
            continue
        pts.append({**it, "center_deck": [c[0] + offset[0], c[1] + offset[1], c[2] + offset[2]]})
    pts.sort(key=lambda x: (x.get("stress_max") is None, -abs(x.get("stress_max") or 0.0)))
    groups: list[dict] = []
    for p in pts:
        home = None
        for g in groups:
            d = math.dist(g["center"], p["center_deck"])
            if d <= radius:
                home = g
                break
        if home is None:
            home = {"center": list(p["center_deck"]), "members": []}
            groups.append(home)
        home["members"].append(p)
        n = len(home["members"])
        home["center"] = [sum(m["center_deck"][k] for m in home["members"]) / n for k in range(3)]
    out = []
    for k, g in enumerate(groups, 1):
        per_angle: dict = {}
        for m in g["members"]:
            key = (m["run_key"], m.get("case_key"))
            v = m.get("stress_max")
            if v is None:
                per_angle.setdefault(key, None)
                continue
            if per_angle.get(key) is None or abs(v) > abs(per_angle[key]["stress_max"]):
                per_angle[key] = m
        best = max((m for m in per_angle.values() if m is not None), key=lambda m: abs(m["stress_max"]), default=None)
        out.append({"site": k, "center_deck": [round(x, 6) for x in g["center"]], "n_clusters": len(g["members"]),
                    "n_angles": len(per_angle),
                    "stress_max_distribution": distribution([m["stress_max"] for m in per_angle.values() if m is not None]),
                    "representative": None if best is None else {
                        "run_key": best["run_key"], "case_key": best.get("case_key"), "doe": best.get("doe"),
                        "report_id": best.get("report_id"), "stress_max": best["stress_max"], "center_deck": best["center_deck"]},
                    "angles": sorted({f"{a}|{b}" for a, b in per_angle}, key=str)})
    return out


def bbox_containment(items: list[dict], offset, bbox_min, bbox_max, tol: float = BBOX_TOL_MM) -> dict:
    """옮긴 군집 중심이 덱 파트 bbox(허용 tol mm) 안에 드는 비율."""
    lo, hi = _vec(bbox_min), _vec(bbox_max)
    cs = [c for it in items if (c := _vec(it.get("center"))) is not None]
    if lo is None or hi is None or not cs:
        return {"ratio": None, "inside": None, "total": len(cs)}
    inside = 0
    for c in cs:
        d = [c[k] + offset[k] for k in range(3)]
        if all(lo[k] - tol <= d[k] <= hi[k] + tol for k in range(3)):
            inside += 1
    return {"ratio": inside / len(cs), "inside": inside, "total": len(cs), "tol_mm": tol}
