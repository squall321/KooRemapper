# 캠페인 각도 행(방향 · 26 방향 라벨 · 무리 피크 · 충격 차수)과 그 위의 통계 · 여유 · 리비전 비교 · 설정 쌍 셈 — 순수 함수(DB 를 모른다)
"""캠페인 분석의 공용 바탕(요청서 DF-05 · 06 · 08 · 11 · 12 · 계획 docs/01-plan/features/df-campaign-analysis-1122.plan.md 3 · 4절).

각도 행 하나는 런(또는 전각도 리포트의 케이스) 하나다. 방향은 요청서 식 그대로 두께 틀에서 d = (sin p·cos r, −sin r, −cos p·cos r)이고,
덱 틀로는 두께축에 따라 오른손 순환으로 옮긴다. 라벨 · 범주는 덱 틀에서 가장 가까운 26 방향이다.
"""
from __future__ import annotations

import math
from itertools import product

from app.modules.analysis.ndjson import FACTS, UNITS

# 요청서의 지표 이름 → 리포트 파트 지표
METRIC_ALIASES = {"MET-STRESS": "peak_stress", "MET-STRAIN": "peak_strain", "MET-ACCEL": "peak_g", "MET-DISP": "peak_disp"}
# 지표 → 단위(ReportArchive 내보내기 표 · ton-mm-s) — 표에 없는 주응력 · 변형률 이름은 같은 물리량으로
METRIC_UNITS: dict[str, str] = {k: UNITS.get(q, "") for k, q, _t in FACTS}
METRIC_UNITS.update({"peak_principal_stress": "MPa", "min_principal_stress": "MPa", "peak_plastic_strain": "",
                     "peak_principal_strain": "", "min_principal_strain": ""})
METRICS = tuple(METRIC_UNITS)
# 피크 시각 칸(초) — 없으면 시각 · 충격 차수가 null
TIME_KEYS = {"peak_stress": "time_of_peak_stress", "peak_g": "time_of_peak_g"}
AXES_THICK = ("X", "Y", "Z")

# 여유의 지표 축(DF-08) — (읽을 파트 지표 · 앞의 것부터, 배율, 단위, 절댓값)
MARGIN_AXES: dict[str, tuple[tuple[str, ...], float, str, bool]] = {
    "tension_principal_stress": (("peak_principal_stress", "peak_principal"), 1.0, "MPa", False),
    "von_mises": (("peak_stress",), 1.0, "MPa", False),
    "compressive_strain": (("min_principal_strain",), 1.0, "", True),
    "board_strain_ue": (("peak_principal_strain",), 1e6, "µε", False),
    "effective_plastic_strain": (("peak_plastic_strain", "peak_strain"), 1.0, "", False),
}


def resolve_metric(name: str) -> str | None:
    """요청서 별칭 · 리포트 지표 이름 → 리포트 지표(모르면 None)."""
    m = METRIC_ALIASES.get(name, name)
    return m if m in METRIC_UNITS else None


def _num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ── 방향 ─────────────────────────────────────────────────────────────────────

def frame_vec(pitch_deg: float, roll_deg: float) -> tuple[float, float, float]:
    """두께 틀의 방향 — d = (sin p·cos r, −sin r, −cos p·cos r)."""
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    return (math.sin(p) * math.cos(r), -math.sin(r), -math.cos(p) * math.cos(r))


def to_deck(f: tuple[float, float, float], thickness_axis: str) -> tuple[float, float, float]:
    """두께 틀(셋째 성분이 두께) → 덱 틀. Z 는 그대로, X 는 (f₃, f₁, f₂), Y 는 (f₂, f₃, f₁) — 오른손 순환."""
    if thickness_axis == "X":
        return (f[2], f[0], f[1])
    if thickness_axis == "Y":
        return (f[1], f[2], f[0])
    return f


def lonlat(f: tuple[float, float, float]) -> tuple[float, float]:
    """두께 틀의 경도 · 위도(도) — 위도 = asin(f₃), 경도 = atan2(f₂, f₁)."""
    lat = math.degrees(math.asin(max(-1.0, min(1.0, f[2]))))
    lon = math.degrees(math.atan2(f[1], f[0])) if abs(f[0]) + abs(f[1]) > 1e-15 else 0.0
    return lon, lat


def _canon() -> list[tuple[str, str, tuple[float, float, float]]]:
    out = []
    for s in product((-1, 0, 1), repeat=3):
        k = sum(1 for c in s if c)
        if not k:
            continue
        name = "".join(("+" if c > 0 else "-") + ax for c, ax in zip(s, AXES_THICK) if c)
        n = math.sqrt(k)
        out.append((name, ("face", "edge", "corner")[k - 1], (s[0] / n, s[1] / n, s[2] / n)))
    return out


CANON = _canon()   # 26 방향 — 면(face) 6 · 모서리(edge) 12 · 꼭짓점(corner) 8 — 범주 이름은 전각도 리포트 생성기와 같다


def label_of(d: tuple[float, float, float]) -> tuple[str, str]:
    """덱 틀 방향 → 가장 가까운 26 방향의 (라벨, 범주)."""
    best = max(CANON, key=lambda c: c[2][0] * d[0] + c[2][1] * d[1] + c[2][2] * d[2])
    return best[0], best[1]


# ── 무리 피크 · 충격 ────────────────────────────────────────────────────────

def group_peak(parts_metrics: dict, part_ids, metric: str) -> dict:
    """무리의 파트 가운데 지표 최댓값(`min_` 지표는 최솟값)과 그 파트 · 시각(ms). 값이 없으면 value None."""
    want = None if part_ids is None else {str(p) for p in part_ids}
    best = None
    lowest = metric.startswith("min_")
    for pid, m in (parts_metrics or {}).items():
        if want is not None and str(pid) not in want or not isinstance(m, dict):
            continue
        v = _num(m.get(metric))
        if v is None:
            continue
        if best is None or (v < best[0] if lowest else v > best[0]):
            t = _num(m.get(TIME_KEYS.get(metric, ""))) if metric in TIME_KEYS else None
            best = (v, pid, None if t is None else t * 1000.0)
    if best is None:
        return {"value": None, "part_id": None, "t_peak_ms": None}
    pid = best[1]
    return {"value": best[0], "part_id": int(pid) if str(pid).lstrip("-").isdigit() else pid, "t_peak_ms": best[2]}


def impact_info(impacts: list | None, t_ms: float | None) -> dict:
    """충격 구간으로 충격 수 · 두 번째 충격 시작 · 피크가 난 충격의 차수와 KE 비. 구간이 없으면 모두 None."""
    if not impacts:
        return {"n_impacts": None, "second_impact_ms": None, "peak_impact": None, "ke_frac_at_impact": None}
    imps = sorted((i for i in impacts if isinstance(i, dict)), key=lambda i: (i.get("index") or 0))
    out = {"n_impacts": len(imps), "second_impact_ms": _num(imps[1].get("t_start_ms")) if len(imps) > 1 else None,
           "peak_impact": None, "ke_frac_at_impact": None}
    if t_ms is None:
        return out
    for k, i in enumerate(imps):
        a = _num(i.get("t_start_ms"))
        b = _num(i.get("t_end_ms"))
        if b is None and k + 1 < len(imps):
            b = _num(imps[k + 1].get("t_start_ms"))
        if a is not None and t_ms >= a and (b is None or t_ms <= b):
            out["peak_impact"] = i.get("index")
            out["ke_frac_at_impact"] = _num(i.get("ke_frac"))
            break
    return out


def angle_rows(runs: list[dict], groups: list[dict], metrics: list[str], thickness_axis: str, *, keep_pm: bool = False) -> list[dict]:
    """넣는 런 → 각도 행. 런의 리포트 케이스가 하나면 런이 한 각도, 여럿이고 각도가 있으면 케이스마다 한 각도.

    `runs` 항목 — `{run_key, doe, pitch, roll, impacts, health, extraction, report: {cases: [{case_key, identity, parts_metrics}]}}`.
    `groups` — `[{group_key, label, part_ids}]`(비면 `all` 하나). `keep_pm` 이면 행에 케이스의 파트 지표(`_pm`)를 남긴다(여유 · 비교가 쓴다).
    """
    gs = groups or [{"group_key": "all", "label": "모든 파트", "part_ids": None}]
    rows = []
    for r in runs:
        cases = (r.get("report") or {}).get("cases") or []
        multi = len(cases) > 1
        for cs in cases:
            ang = ((cs.get("identity") or {}).get("angle") or {}) if isinstance(cs.get("identity"), dict) else {}
            if multi and (ang.get("pitch") is None or ang.get("roll") is None):
                continue
            # 케이스 각도는 생성기 규약 — `swap` 이면 roll · pitch 칸이 바뀌어 있다(roll 칸이 식의 p). 전각도 표본 26 방향의 범주가 생성기의
            # 범주와 26 / 26 맞는다(맥락 노트). 런 목록의 pitch · roll 은 그대로 식의 p · r 이다
            cp, cr = (ang.get("roll"), ang.get("pitch")) if ang.get("swap") else (ang.get("pitch"), ang.get("roll"))
            pitch = _num(cp) if multi else (_num(r.get("pitch")) if r.get("pitch") is not None else _num(cp))
            roll = _num(cr) if multi else (_num(r.get("roll")) if r.get("roll") is not None else _num(cr))
            row = {"run_key": r["run_key"], "case_key": cs.get("case_key"), "doe": r.get("doe"), "report_id": r.get("report_id"),
                   "pitch": pitch, "roll": roll, "direction": None, "lon": None, "lat": None, "label": None, "category": None,
                   "ke0": _num((r.get("health") or {}).get("ke0_measured")),
                   "peak_source": (r.get("extraction") or {}).get("peak_source")}
            if pitch is not None and roll is not None:
                f = frame_vec(pitch, roll)
                d = to_deck(f, thickness_axis)
                row["direction"] = [round(c, 12) for c in d]
                row["lon"], row["lat"] = lonlat(f)
                row["label"], row["category"] = label_of(d)
            imp = impact_info(r.get("impacts"), None)
            row["n_impacts"], row["second_impact_ms"] = imp["n_impacts"], imp["second_impact_ms"]
            peaks = {}
            for g in gs:
                pm = {}
                for m in metrics:
                    gp = group_peak(cs.get("parts_metrics") or {}, g.get("part_ids"), m)
                    gp.update({k: v for k, v in impact_info(r.get("impacts"), gp["t_peak_ms"]).items()
                               if k in ("peak_impact", "ke_frac_at_impact")})
                    pm[m] = gp
                peaks[g["group_key"]] = pm
            row["peaks"] = peaks
            if keep_pm:
                row["_pm"] = cs.get("parts_metrics") or {}
            rows.append(row)
    return rows


# ── 분포 · 통계 ─────────────────────────────────────────────────────────────

def quantile(sorted_vals: list[float], q: float) -> float | None:
    """선형 보간 분위수(numpy 기본과 같다)."""
    if not sorted_vals:
        return None
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def distribution(vals: list[float]) -> dict:
    v = sorted(x for x in vals if x is not None)
    if not v:
        return {"n": 0, "min": None, "p10": None, "median": None, "p90": None, "max": None, "mean": None}
    return {"n": len(v), "min": v[0], "p10": quantile(v, 0.1), "median": quantile(v, 0.5), "p90": quantile(v, 0.9), "max": v[-1],
            "mean": sum(v) / len(v)}


def angle_stats(rows: list[dict], group_keys: list[str], metric: str, *, top: int = 10) -> dict:
    """요약 — n · 다회 충격 비율 · 무리별 분포 · 상위 · 하위 · 범주별 · 라벨별 · 덮임(26 방향 가운데 맞은 라벨 수)."""
    known = [r for r in rows if r["n_impacts"] is not None]
    multi = sum(1 for r in known if r["n_impacts"] >= 2)
    out = {"n": len(rows), "impacts_known": len(known), "multi_impact": multi,
           "multi_impact_ratio": (multi / len(known)) if known else None, "groups": {}}
    for g in group_keys:
        vals = [(r, r["peaks"][g][metric]["value"]) for r in rows if r["peaks"].get(g, {}).get(metric, {}).get("value") is not None]
        ranked = sorted(vals, key=lambda rv: rv[1], reverse=True)

        def key(rv):
            r, v = rv
            return {"run_key": r["run_key"], "case_key": r["case_key"], "doe": r["doe"], "label": r["label"], "value": v,
                    "peak_impact": r["peaks"][g][metric]["peak_impact"]}
        by_cat: dict = {}
        by_lab: dict = {}
        for r, v in vals:
            by_cat.setdefault(r["category"], []).append(v)
            by_lab.setdefault(r["label"], []).append(v)
        imp_known = [r["peaks"][g][metric]["peak_impact"] for r, _v in vals if r["peaks"][g][metric]["peak_impact"] is not None]
        out["groups"][g] = {
            "distribution": distribution([v for _r, v in vals]),
            "top": [key(x) for x in ranked[:top]], "bottom": [key(x) for x in ranked[::-1][:top]],
            "by_category": {str(k): distribution(v) for k, v in sorted(by_cat.items(), key=lambda kv: str(kv[0]))},
            "by_label": {str(k): distribution(v) for k, v in sorted(by_lab.items(), key=lambda kv: str(kv[0]))},
            "peak_impact_counts": {str(k): imp_known.count(k) for k in sorted(set(imp_known))},
        }
    labels = {r["label"] for r in rows if r["label"]}
    out["coverage"] = {"labels_hit": len(labels), "labels_total": len(CANON), "missing_labels": sorted(c[0] for c in CANON if c[0] not in labels)}
    return out


# ── 여유(DF-08) ─────────────────────────────────────────────────────────────

def axis_value(parts_metrics: dict, part_ids, axis: str) -> float | None:
    """무리(또는 파트)의 지표 축 값 — 파트마다 축이 읽는 첫 지표를 배율 · 절댓값으로 바꿔 그 가운데 최댓값."""
    keys, scale, _unit, absolute = MARGIN_AXES[axis]
    want = None if part_ids is None else {str(p) for p in part_ids}
    best = None
    for pid, m in (parts_metrics or {}).items():
        if want is not None and str(pid) not in want or not isinstance(m, dict):
            continue
        v = next((_num(m.get(k)) for k in keys if _num(m.get(k)) is not None), None)
        if v is None:
            continue
        v = abs(v) * scale if absolute else v * scale
        best = v if best is None or v > best else best
    return best


def margin(values: list[tuple[dict, float]], criterion: float | None) -> dict:
    """각도별 값 → 최댓값 · 가운데값 · (기준이 있으면) 비 · 넘은 비율 · 상위 10 % 각도."""
    vs = sorted(v for _r, v in values)
    ranked = sorted(values, key=lambda rv: rv[1], reverse=True)
    k = max(1, math.ceil(len(ranked) * 0.1)) if ranked else 0
    out = {"n": len(vs), "value": vs[-1] if vs else None, "median": quantile(vs, 0.5), "criterion": criterion,
           "ratio": None, "median_ratio": None, "exceed_ratio": None,
           "top_angles": [{"run_key": r["run_key"], "case_key": r["case_key"], "doe": r["doe"], "label": r["label"], "value": v}
                          for r, v in ranked[:k]]}
    if criterion and vs:
        out["ratio"] = vs[-1] / criterion
        out["median_ratio"] = out["median"] / criterion
        out["exceed_ratio"] = sum(1 for v in vs if v >= criterion) / len(vs)
    return out


# ── 순위 상관 · 설정 쌍(DF-12) ──────────────────────────────────────────────

def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    """스피어먼 순위 상관(같은 값은 평균 순위). 쌍이 둘 미만이거나 한쪽이 상수면 None."""
    if len(a) != len(b) or len(a) < 2:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / math.sqrt(va * vb)


def config_pairs(old_rows: list[dict], new_rows: list[dict], rule: dict) -> dict:
    """같은 DOE 의 옛 · 새 각도 행을 쌍으로 — 규칙의 지표 · 무리마다 차 % · 순위 상관 · 넘은 쌍 · 판정."""
    def by_doe(rows):
        out: dict = {}
        for r in rows:
            if r["doe"] is not None:
                out.setdefault(str(r["doe"]), r)
        return out
    o, n = by_doe(old_rows), by_doe(new_rows)
    common = sorted(o.keys() & n.keys())
    items = rule.get("metrics") or []
    pairs, failed_keys, corr = [], set(), []
    for it in items:
        g = it.get("group_key") or "all"
        m = it["metric"]
        xs, ys = [], []
        for doe in common:
            a = o[doe]["peaks"].get(g, {}).get(m, {}).get("value")
            b = n[doe]["peaks"].get(g, {}).get(m, {}).get("value")
            diff = None if a in (None, 0) or b is None else (b - a) / abs(a) * 100.0
            over = diff is not None and abs(diff) > float(it["max_diff_pct"])
            if over:
                failed_keys.add(doe)
            if a is not None and b is not None:
                xs.append(a)
                ys.append(b)
            pairs.append({"doe": doe, "group_key": g, "metric": m, "old": a, "new": b, "diff_pct": diff,
                          "max_diff_pct": float(it["max_diff_pct"]), "over": over,
                          "old_run_key": o[doe]["run_key"], "new_run_key": n[doe]["run_key"]})
        rc = spearman(xs, ys)
        corr.append({"group_key": g, "metric": m, "n": len(xs), "rank_corr": rc,
                     "below_min": rc is not None and rc < float(rule.get("rank_corr_min", 0.9))})
    max_failed = int(rule.get("max_failed_pairs", 2))
    verdict = "pass"
    reasons = []
    if len(failed_keys) > max_failed:
        verdict, reasons = "rerun_required", reasons + ["failed_pairs"]
    if any(c["below_min"] for c in corr):
        verdict, reasons = "rerun_required", reasons + ["rank_corr"]
    if not common:
        verdict, reasons = "no_pairs", ["no_common_doe"]
    return {"common_doe": len(common), "only_old": sorted(o.keys() - n.keys()), "only_new": sorted(n.keys() - o.keys()),
            "pairs": pairs, "rank_correlation": corr, "failed_pairs": len(failed_keys), "failed_doe": sorted(failed_keys),
            "max_failed_pairs": max_failed, "rank_corr_min": float(rule.get("rank_corr_min", 0.9)), "verdict": verdict, "reasons": reasons}


# ── 리비전 비교(DF-11) ─────────────────────────────────────────────────────

def angular_deg(a: list[float], b: list[float]) -> float:
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(dot))


def match_angles(rows_a: list[dict], rows_b: list[dict], *, mode: str, tol_deg: float) -> list[tuple[dict, dict]]:
    """공통 각도 — `doe`(같은 DOE) 또는 `angle`(각거리 허용치 안의 가장 가까운 짝 · 한 번씩만)."""
    if mode == "doe":
        b = {}
        for r in rows_b:
            if r["doe"] is not None:
                b.setdefault(str(r["doe"]), r)
        out, seen = [], set()
        for r in rows_a:
            k = None if r["doe"] is None else str(r["doe"])
            if k is not None and k in b and k not in seen:
                seen.add(k)
                out.append((r, b[k]))
        return out
    cand = []
    for i, ra in enumerate(rows_a):
        if ra["direction"] is None:
            continue
        for j, rb in enumerate(rows_b):
            if rb["direction"] is None:
                continue
            d = angular_deg(ra["direction"], rb["direction"])
            if d <= tol_deg:
                cand.append((d, i, j))
    out, ua, ub = [], set(), set()
    for d, i, j in sorted(cand):
        if i in ua or j in ub:
            continue
        ua.add(i)
        ub.add(j)
        out.append((rows_a[i], rows_b[j]))
    return out


def size_class(ratio: float | None) -> str | None:
    """크기 — |log₂ 비| 0.5 이상 상 · 0.25 이상 중 · 나머지 하."""
    if ratio is None or ratio <= 0:
        return None
    x = abs(math.log2(ratio))
    return "high" if x >= 0.5 else "mid" if x >= 0.25 else "low"
