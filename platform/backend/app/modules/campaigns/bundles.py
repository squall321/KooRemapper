# 보고서용 묶음의 항목 · 표 · 기준 줄 · 판 견주기를 짓는 순수 함수 — DB 를 모른다(서비스가 읽어 넘긴다)
"""보고서용 묶음(요청서 DF-13 · 계획 docs/01-plan/features/df-report-bundles-1122.plan.md 3 ~ 5절).

숫자는 항목 하나가 한 줄이다 — `item_key` 는 `<표 종류>/<캠페인 id>/<run_key>/<case_key>[/<파트>]/<지표>`, `source_path` 는
`report:<id>/case:<case_key>[/part:<pid>]/<지표>`(런 표의 숫자는 `campaign:<id>/run:<run_key>/<지표>`). 글 조각의 `/` 는 `%2F` 로 쓴다.
"""
from __future__ import annotations

import math
from urllib.parse import quote, unquote

from app.modules.analysis.ndjson import FACTS, UNITS

TABLE_KINDS = ("runs", "case_metrics", "part_peaks")
ITEMS_MAX = 200_000
EXT_DEFAULT = ("png", "svg")
# 케이스 롤업(impact_cases 의 승격 칸) — 지표 → 단위 표의 물리량(안전율은 무차원)
CASE_METRICS: dict[str, str | None] = {"max_stress": "stress", "max_g": "g", "max_disp": "disp", "min_safety_factor": None}
CASE_DEFAULT = tuple(CASE_METRICS)
# 파트 피크 — ReportArchive 내보내기와 같은 표(parts_metrics 키 → 물리량)
PART_METRICS: dict[str, str] = {key: q for key, q, _t in FACTS}
PART_DEFAULT = ("peak_stress", "peak_g")
RUN_METRICS = {"pitch": "deg", "roll": "deg"}


class TooMany(ValueError):
    """한 판의 항목이 상한을 넘는다."""


def _q(s) -> str:
    return quote(str(s), safe=":@-_.,=+~")


def _unit(quantity: str | None) -> str:
    return "" if quantity is None else UNITS.get(quantity, "")


def _num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_source(path: str) -> dict:
    """`source_path` → `{report_id, case_key, part_id, metric}`(런 표는 `{campaign_id, run_key, metric}`)."""
    parts = path.split("/")
    out: dict = {"metric": unquote(parts[-1])}
    for seg in parts[:-1]:
        k, _, v = seg.partition(":")
        v = unquote(v)
        if k == "report":
            out["report_id"] = v
        elif k == "case":
            out["case_key"] = v
        elif k == "part":
            out["part_id"] = int(v) if v.lstrip("-").isdigit() else v
        elif k == "campaign":
            out["campaign_id"] = v
        elif k == "run":
            out["run_key"] = v
    return out


def build(*, campaigns: list[dict], spec: dict) -> dict:
    """캠페인마다 판정된 런 행 · 리포트 사실을 받아 판 하나의 `{basis, tables, figures, sources, items}` 를 짓는다.

    `campaigns` 항목 — `{campaign_id, name, thresholds_ref, runs: [{run_key, doe, pitch, roll, config_generation, report_id,
    validity, excluded_by, report: {unit_system, cases: [{case_key, max_stress, …, parts_metrics}], media: [...]} | None}]}`.
    런의 `excluded_by` 에는 서비스가 기준 시각(`after_as_of`)까지 넣어 온다. 넣는 런은 제외 까닭이 없는 런(`include_invalid` 면
    리포트가 있는 런 모두)이다.
    """
    include_invalid = bool(spec.get("include_invalid"))
    items: list[dict] = []
    tables: list[dict] = []
    figures: list[dict] = []
    basis_rows: list[dict] = []
    reports: list[dict] = []
    unit_systems: set[str] = set()
    picked: list[tuple[str, dict]] = []
    for c in campaigns:
        cid = c["campaign_id"]
        runs = c["runs"]
        by: dict[str, int] = {}
        for r in runs:
            for why in r["excluded_by"]:
                by[why] = by.get(why, 0) + 1
        inc = [r for r in runs if r.get("report") is not None and (include_invalid or not r["excluded_by"])]
        gens: dict[str | None, int] = {}
        for r in inc:
            gens[r.get("config_generation")] = gens.get(r.get("config_generation"), 0) + 1
        included_clean = sum(1 for r in runs if not r["excluded_by"])
        line = f"{c.get('name') or cid} — 유효 {included_clean} / 전체 {len(runs)}"
        if by:
            line += " · 제외 " + " · ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))
        if include_invalid:
            line += f" · 제외 까닭이 있는 런도 넣음(넣은 런 {len(inc)})"
        basis_rows.append({
            "campaign_id": cid, "name": c.get("name"), "total": len(runs), "included": len(inc),
            "valid_runs": included_clean, "excluded_by": by, "thresholds_ref": c.get("thresholds_ref"),
            "generations": [{"config_generation": g, "runs": n}
                            for g, n in sorted(gens.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))],
            "line": line,
        })
        for r in inc:
            picked.append((cid, r))
            rep = r["report"]
            if rep.get("unit_system"):
                unit_systems.add(str(rep["unit_system"]))
            reports.append({"campaign_id": cid, "run_key": r["run_key"], "report_id": r["report_id"],
                            "cases": len(rep.get("cases") or [])})

    def add(key: str, value, unit: str, source: str) -> None:
        items.append({"item_key": key, "value": value, "unit": unit, "source_path": source})
        if len(items) > ITEMS_MAX:
            raise TooMany(f"한 판의 숫자가 {ITEMS_MAX:,} 개를 넘습니다 — 표 종류 · 지표 · 파트를 좁히세요")

    for t in spec.get("tables") or []:
        kind = t["kind"]
        if kind == "runs":
            cols = ["campaign_id", "run_key", "doe", "pitch", "roll", "config_generation", "validity", "report_id"]
            rows = []
            for cid, r in picked:
                rows.append({"campaign_id": cid, "run_key": r["run_key"], "doe": r.get("doe"), "pitch": _num(r.get("pitch")),
                             "roll": _num(r.get("roll")), "config_generation": r.get("config_generation"),
                             "validity": r["validity"]["status"], "report_id": r["report_id"]})
                for m, unit in RUN_METRICS.items():
                    v = _num(r.get(m))
                    if v is not None:
                        add(f"runs/{_q(cid)}/{_q(r['run_key'])}/{m}", v, unit, f"campaign:{_q(cid)}/run:{_q(r['run_key'])}/{m}")
            tables.append({"kind": kind, "columns": cols, "rows": rows, "units": dict(RUN_METRICS)})
        elif kind == "case_metrics":
            metrics = list(t.get("metrics") or CASE_DEFAULT)
            cols = ["campaign_id", "run_key", "report_id", "case_key", *metrics]
            rows = []
            for cid, r in picked:
                for cs in r["report"].get("cases") or []:
                    row = {"campaign_id": cid, "run_key": r["run_key"], "report_id": r["report_id"], "case_key": cs["case_key"]}
                    for m in metrics:
                        v = _num(cs.get(m))
                        row[m] = v
                        if v is not None:
                            add(f"case_metrics/{_q(cid)}/{_q(r['run_key'])}/{_q(cs['case_key'])}/{m}", v, _unit(CASE_METRICS[m]),
                                f"report:{_q(r['report_id'])}/case:{_q(cs['case_key'])}/{m}")
                    rows.append(row)
            tables.append({"kind": kind, "columns": cols, "rows": rows,
                           "units": {m: _unit(CASE_METRICS[m]) for m in metrics}})
        elif kind == "part_peaks":
            metrics = list(t.get("metrics") or PART_DEFAULT)
            want = set(t["parts"]) if t.get("parts") else None
            cols = ["campaign_id", "run_key", "report_id", "case_key", "part_id", *metrics]
            rows = []
            for cid, r in picked:
                for cs in r["report"].get("cases") or []:
                    pm = cs.get("parts_metrics") or {}
                    for pid in sorted(pm, key=lambda p: (not str(p).lstrip("-").isdigit(), int(p) if str(p).lstrip("-").isdigit() else 0, str(p))):
                        try:
                            ipid = int(pid)
                        except (TypeError, ValueError):
                            continue
                        if want is not None and ipid not in want:
                            continue
                        vals = pm.get(pid) or {}
                        row = {"campaign_id": cid, "run_key": r["run_key"], "report_id": r["report_id"],
                               "case_key": cs["case_key"], "part_id": ipid}
                        for m in metrics:
                            v = _num(vals.get(m))
                            row[m] = v
                            if v is not None:
                                add(f"part_peaks/{_q(cid)}/{_q(r['run_key'])}/{_q(cs['case_key'])}/{ipid}/{m}", v,
                                    _unit(PART_METRICS[m]), f"report:{_q(r['report_id'])}/case:{_q(cs['case_key'])}/part:{ipid}/{m}")
                        rows.append(row)
            tables.append({"kind": kind, "columns": cols, "rows": rows,
                           "units": {m: _unit(PART_METRICS[m]) for m in metrics}})

    fig = spec.get("figures")
    if fig:
        roles = set(fig["roles"]) if fig.get("roles") else None
        exts = {e.lower().lstrip(".") for e in (fig.get("exts") or EXT_DEFAULT)}
        for cid, r in picked:
            for m in r["report"].get("media") or []:
                ext = (m.get("path") or "").rsplit(".", 1)[-1].lower() if "." in (m.get("path") or "") else ""
                if m.get("kind") == "video" or ext not in exts or (roles is not None and m.get("role") not in roles):
                    continue
                figures.append({"campaign_id": cid, "run_key": r["run_key"], "report_id": r["report_id"],
                                "file_id": m.get("file_id"), "path": m.get("path"), "ext": ext, "case_key": m.get("case_key"),
                                "role": m.get("role"), "set_name": m.get("set_name"), "bytes": m.get("bytes"),
                                "sha256": m.get("sha256")})

    units = {"convention": "ton-mm-s (MPa · G · mm)", "unit_systems": sorted(unit_systems),
             "by_metric": {**{m: _unit(q) for m, q in CASE_METRICS.items()}, **{m: _unit(q) for m, q in PART_METRICS.items()},
                           **RUN_METRICS}}
    basis = {"campaigns": basis_rows, "include_invalid": include_invalid, "units": units, "items": len(items),
             "line": " | ".join(b["line"] for b in basis_rows)}
    sources = {"reports": reports, "figures": [{"report_id": f["report_id"], "file_id": f["file_id"], "sha256": f["sha256"]}
                                               for f in figures],
               "thresholds_refs": {b["campaign_id"]: b["thresholds_ref"] for b in basis_rows},
               "part_map_id": None, "criteria_version": None}
    return {"basis": basis, "tables": tables, "figures": figures, "sources": sources, "items": items}


def same(a: dict, b: dict) -> bool:
    """두 판이 같은가 — 항목(키 · 값 · 단위 · 출처) · 그림(파일 · sha256) · 기준 줄 셈이 같으면 같다."""
    def key(x):
        return (sorted((i["item_key"], i["value"], i["unit"], i["source_path"]) for i in x["items"]),
                sorted((f.get("report_id"), f.get("file_id"), f.get("sha256")) for f in x["figures"]),
                [(c["campaign_id"], c["total"], c["included"], c["valid_runs"], sorted(c["excluded_by"].items()),
                  [(g["config_generation"], g["runs"]) for g in c["generations"]], c["thresholds_ref"])
                 for c in x["basis"]["campaigns"]])
    return key(a) == key(b)


def diff(old_items: list[dict], new_items: list[dict]) -> dict:
    """앞 판 → 새 판의 바뀐 숫자 — 더해짐 · 빠짐 · 값(또는 단위) 바뀜. 머리 줄에 수."""
    o = {i["item_key"]: i for i in old_items}
    n = {i["item_key"]: i for i in new_items}
    added = [n[k] for k in sorted(n.keys() - o.keys())]
    removed = [o[k] for k in sorted(o.keys() - n.keys())]
    changed = [{"item_key": k, "old": o[k]["value"], "new": n[k]["value"], "unit": n[k]["unit"], "old_unit": o[k]["unit"],
                "source_path": n[k]["source_path"]}
               for k in sorted(o.keys() & n.keys())
               if o[k]["value"] != n[k]["value"] or o[k]["unit"] != n[k]["unit"]]
    return {"added": added, "removed": removed, "changed": changed,
            "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)}}
