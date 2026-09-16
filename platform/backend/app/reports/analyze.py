# 리포트 케이스 분석의 DB-free 코어 — 서비스(DB행)와 CLI(파싱 study)가 공유하는 한 벌.
# 표준라이브러리 + parser 만 쓴다(SQLAlchemy 불필요) — CLI 로도 그대로 돈다.
from __future__ import annotations

import math
import statistics

from app.reports import parser


def _view(c) -> tuple[str, dict, dict]:
    """케이스를 (case_key, identity, parts_metrics) 로 통일 — ImpactCase(속성)·study 케이스(dict) 둘 다."""
    if isinstance(c, dict):
        return c.get("case_key") or "", c.get("identity") or {}, c.get("parts_metrics") or {}
    return (getattr(c, "case_key", "") or ""), (getattr(c, "identity", None) or {}), (getattr(c, "parts_metrics", None) or {})


def _angle_of(identity: dict) -> dict:
    return (identity.get("angle") or {}) if isinstance(identity, dict) else {}


def _category_of(identity: dict, kind: str) -> str:
    """방향 범주. sphere=angle.category(면/엣지/코너), impact=face, deep=single."""
    idt = identity or {}
    if kind == "sphere":
        return (idt.get("angle") or {}).get("category") or "unknown"
    if kind == "impact":
        return idt.get("face") or "unknown"
    return "single"


def _name_map(parts) -> dict:
    out = {}
    for p in (parts or []):
        try:
            out[int(p["part_id"])] = p.get("name")
        except (TypeError, ValueError, KeyError):
            continue
    return out


def available_metrics(cases: list) -> list[str]:
    """리포트에 실제로 존재하는 파트 물리량 키(시계열 *_ts·시각 time_of_*/*_time 제외)."""
    keys: set[str] = set()
    for c in cases:
        _, _, pm = _view(c)
        for m in pm.values():
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                if k.startswith("time_of_") or k.endswith(("_ts", "_time")):
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    keys.add(k)
    return sorted(keys)


def _percentile(s: list[float], q: float) -> float:
    """정렬된 표본의 백분위(선형보간). q∈[0,100]."""
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * (q / 100.0)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# 값이 '작을수록 나쁜' 물리량 — worst 는 max 가 아니라 min, top_risk 는 오름차순.
LOWER_IS_WORSE = {"safety_factor", "min_principal", "min_principal_strain", "min_principal_stress"}


def _cov(std: float, mean: float) -> float | None:
    """변동계수 — 부호 있는/0 근처 평균에서 음수·발산 방지(크기 기준)."""
    return (std / abs(mean)) if mean else None


def stat_block(vals: list[float]) -> dict:
    """표준 통계 블록 — 어느 각도군이든 동일 스키마라 비교 가능. std 는 표본(n-1)."""
    s = sorted(vals)
    n = len(s)
    mean = statistics.fmean(s)
    std = statistics.stdev(s) if n > 1 else 0.0
    p25, p75 = _percentile(s, 25), _percentile(s, 75)
    return {
        "n": n, "mean": mean, "std": std, "cov": _cov(std, mean),
        "min": s[0], "p05": _percentile(s, 5), "p25": p25, "median": _percentile(s, 50),
        "p75": p75, "p95": _percentile(s, 95), "max": s[-1],
        "iqr": p75 - p25, "range": s[-1] - s[0],
    }


def _part_breakdown(recs: list[dict], name_of: dict, top: int, lower: bool = False) -> dict:
    """각도군 안에서 부품별 위험(worst)·민감도(CoV) 분해. lower=True 면 작을수록 위험(min, 오름차순)."""
    by_part: dict[int, list[float]] = {}
    for r in recs:
        for pid, v in r["per_part"].items():
            by_part.setdefault(pid, []).append(v)
    rows = []
    for pid, vs in by_part.items():
        mean = statistics.fmean(vs)
        std = statistics.stdev(vs) if len(vs) > 1 else 0.0
        rows.append({"part_id": pid, "part_name": name_of.get(pid), "n": len(vs),
                     "mean": mean, "worst": (min(vs) if lower else max(vs)), "cov": _cov(std, mean)})
    top_risk = sorted(rows, key=lambda d: (d["worst"] if lower else -d["worst"]))[:top]
    sens = [d for d in rows if d["n"] >= 2 and d["cov"] is not None]
    most_sensitive = sorted(sens, key=lambda d: -(d["cov"] or 0))[:top]
    return {"top_risk": top_risk, "most_sensitive": most_sensitive}


def angle_group_stats(cases: list, kind: str, parts, *, metric: str = "peak_stress",
                      part_id: int | None = None, category: str | None = None,
                      angle_name: str | None = None, near_lon: float | None = None,
                      near_lat: float | None = None, tol_deg: float = 15.0,
                      top_parts: int = 5) -> dict:
    """특정 각도군 표준 통계(분포 + 부품별 분해). cases 는 ImpactCase 행 또는 study 케이스(dict) 리스트.

    선택(우선순위): near(임의 각도 콘, sphere) > angle_name(그 방향 최근접 26-base 퍼터베이션 구름,
    sphere) > category(면/엣지/코너·impact 면) > 미지정(전체: sphere=base별, 그 외 범주별).
    """
    avail = available_metrics(cases)
    base = {"kind": kind, "metric": metric, "part_id": part_id, "available_metrics": avail}
    if metric not in avail:
        return {**base, "groups": [], "n_cases_total": 0,
                "note": f"이 리포트엔 '{metric}' 가 없습니다. 사용 가능: {avail}"}
    name_of = _name_map(parts)
    is_sphere = kind == "sphere"
    lower = metric in LOWER_IS_WORSE

    recs: list[dict] = []
    for c in cases:
        case_key, identity, pm = _view(c)
        ang = _angle_of(identity)
        per_part: dict[int, float] = {}
        for pid_s, m in pm.items():
            if not isinstance(m, dict):
                continue
            v = m.get(metric)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                try:
                    per_part[int(pid_s)] = float(v)
                except (TypeError, ValueError):
                    pass
        if part_id is not None:
            if part_id not in per_part:
                continue
            case_val, val_part = per_part[part_id], part_id
        else:
            if not per_part:
                continue
            val_part = (min if lower else max)(per_part, key=lambda k: per_part[k])
            case_val = per_part[val_part]
        vec = parser._angle_vec(ang) if is_sphere else None
        bkey, berr = parser._nearest_base(vec) if vec else (None, None)
        recs.append({"case_key": case_key, "angle_name": ang.get("name"),
                     "category": _category_of(identity, kind), "base_key": bkey, "base_err": berr,
                     "vec": vec, "case_val": case_val, "val_part": val_part, "per_part": per_part})

    buckets: dict[str, dict] = {}
    if near_lon is not None and near_lat is not None:
        if not is_sphere:
            return {**base, "groups": [], "n_cases_total": len(recs),
                    "selection": {"mode": "near"}, "note": "near 각도 콘은 sphere 전용입니다."}
        selection = {"mode": "near", "near_lon": near_lon, "near_lat": near_lat, "tol_deg": tol_deg}
        la, lo = math.radians(near_lat), math.radians(near_lon)
        tvec = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
        picked = [r for r in recs if math.degrees(math.acos(
            max(-1.0, min(1.0, sum(a * b for a, b in zip(r["vec"], tvec)))))) <= tol_deg]
        if picked:
            buckets[f"near({near_lon:.0f},{near_lat:.0f})"] = {"cat": "near", "rep": None, "recs": picked}
    elif angle_name:
        if not is_sphere:
            return {**base, "groups": [], "n_cases_total": len(recs),
                    "selection": {"mode": "base"}, "note": "기준방향(퍼터베이션 구름) 선택은 sphere 전용입니다."}
        selection = {"mode": "base", "angle_name": angle_name}
        target = next((r for r in recs if r["angle_name"] == angle_name), None)
        if target and target["base_key"] is not None:
            key = target["base_key"]
            picked = [r for r in recs if r["base_key"] == key]
            buckets[f"base:{angle_name}"] = {"cat": parser._base_category(key), "rep": angle_name, "recs": picked}
    elif category:
        selection = {"mode": "category", "category": category}
        picked = [r for r in recs if r["category"] == category]
        if picked:
            buckets[category] = {"cat": category, "rep": None, "recs": picked}
    else:
        selection = {"mode": "all_bases" if is_sphere else "all_categories"}
        for r in recs:
            if is_sphere and r["base_key"] is not None:
                label = ",".join(str(x) for x in r["base_key"])
                b = buckets.setdefault(label, {"cat": parser._base_category(r["base_key"]),
                                               "rep": r["angle_name"], "rep_err": r["base_err"], "recs": []})
                if r["base_err"] is not None and r["base_err"] < (b.get("rep_err") or 1e9):
                    b["rep_err"], b["rep"] = r["base_err"], r["angle_name"]
                b["recs"].append(r)
            else:
                b = buckets.setdefault(r["category"], {"cat": r["category"], "rep": None, "recs": []})
                b["recs"].append(r)

    groups = []
    for label, b in buckets.items():
        rs = b["recs"]
        stats = stat_block([r["case_val"] for r in rs])
        w = (min if lower else max)(rs, key=lambda r: r["case_val"])
        g = {"group_key": label, "category": b["cat"], "representative": b.get("rep"),
             "stats": stats,
             "worst": {"value": w["case_val"], "angle_name": w["angle_name"],
                       "part_id": w["val_part"], "part_name": name_of.get(w["val_part"]),
                       "case_key": w["case_key"]}}
        if part_id is None:
            g["parts"] = _part_breakdown(rs, name_of, top_parts, lower)
        groups.append(g)
    groups.sort(key=lambda d: (d["stats"]["mean"] or 0) * (1 if lower else -1))
    return {**base, "selection": selection, "n_cases_total": len(recs),
            "n_groups": len(groups), "groups": groups,
            "note": None if recs else "선택 조건에 맞는 케이스가 없습니다."}


def directional(cases: list, kind: str, parts, part_id: int | None = None) -> dict:
    """방향 취약도 — 방향 범주(면/엣지/코너·F1~F6)별 최악 응력·G. part_id 로 파트 한정."""
    name_of = _name_map(parts)
    agg: dict[str, dict] = {}
    for c in cases:
        case_key, identity, pm = _view(c)
        cat = _category_of(identity, kind)
        slot = agg.setdefault(cat, {
            "category": cat, "n_cases": 0,
            "worst_stress": {"value": None, "part_id": None, "part_name": None, "case_key": None},
            "worst_g": {"value": None, "part_id": None, "part_name": None, "case_key": None},
        })
        slot["n_cases"] += 1
        for pid_s, m in pm.items():
            try:
                pid = int(pid_s)
            except (TypeError, ValueError):
                continue
            if part_id is not None and pid != part_id:
                continue
            for key, mk in (("worst_stress", "peak_stress"), ("worst_g", "peak_g")):
                v = (m or {}).get(mk)
                if v is not None and (slot[key]["value"] is None or v > slot[key]["value"]):
                    slot[key] = {"value": v, "part_id": pid, "part_name": name_of.get(pid), "case_key": case_key}
    directions = sorted(
        agg.values(),
        key=lambda d: (d["worst_stress"]["value"] is None, -(d["worst_stress"]["value"] or 0)),
    )
    return {"kind": kind, "part_id": part_id, "directions": directions}
