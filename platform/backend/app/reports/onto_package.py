# 후처리 온톨로지 꾸러미(dynaforge.onto_package)를 받아들인 판의 어휘로 검사하고 캠페인 수준 행 · 선으로 바꾸는 순수 함수 — I/O 는 어휘 파일 읽기뿐
"""계약 — KooD3plotReader `docs/ontology_2026-10/package-contract.md`(초안 2). 어휘 정본 — `platform/core/ontology/dynaforge-cae.json`.
사용자 결정 10-31 — DynaForge 가 채택 · 적재 · 질의를 맡고 **(가) 캠페인 수준만 행으로** 싣는다. 계획 `docs/01-plan/features/cae-ontology-1031.plan.md`.

- 받아들인 판(`ACCEPTED`) 안의 어휘 지문이어야 하고, **그 판의 어휘로** 검사한다 — 정본 하나와만 견주면 정본을 올리는 순간 옛 판을 싣는
  배포판(늦게 바뀌는 노드 SIF 포함)의 꾸러미가 모두 막힌다. 정본을 올릴 때는 옛 바이트를 `history/` 로 옮겨 여기 남긴다.
- 짝 — 꾸러미의 `source.html.sha256` 이 리포트 원본 HTML 의 지문과 같아야 한다. 종류(scenario_kind)가 리포트 종류와 같아야 한다.
- 지어내지 않는다 — 모르는 타입 · 칸 · 관계 · 열거값, 빠진 필수값, 가리킬 곳 없는 참조가 있으면 통째로 거절한다(전부 아니면 전무).
- 행으로 바꾸는 것은 `LOADED_TYPES` 뿐이다. 런 · 파트 응답의 정본은 `impact_cases`(`case_key` 가 같다), 하중 전달은 꾸러미 파일에 남는다.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FORMAT = "dynaforge.onto_package"
FORMAT_VERSION = 1
VOCAB_DIR = Path(__file__).resolve().parents[3] / "core" / "ontology"
CANONICAL = "dynaforge-cae.json"
# 받아들인 판 — 어휘 바이트의 sha256 → 그 바이트가 든 파일(VOCAB_DIR 기준). 정본을 올리면 옛 바이트는 history/ 로 옮겨 여기 남긴다.
ACCEPTED = {
    "59b4e70b3d308b46574a28dc4b5745a909e4923a5a062fe5ddbdaf17522124fa": CANONICAL,                         # 0.4 — cae_run.flow_scalars_only(10-31)
    "72ff9b49edd5a38bc1112268df85de5b61eb36cba09bf3e2bc4c07a08d4c4d64": "history/dynaforge-cae-0.3.json",  # 0.3 — 생산 쪽 첫 배포판
}
LOADED_TYPES = ("cae_campaign", "cae_part", "cae_contact", "cae_load_path", "cae_finding", "cae_hotspot")
SCENARIO_OF = {"sphere": "drop_all_angle", "impact": "impact_all_position", "deep": "single_run"}
REPORT_TYPE = "impact_report"
CAMPAIGN_REPORT = "campaign_report"


class OntoPackageError(ValueError):
    """계약에 맞지 않는 꾸러미 — 까닭을 그대로 사람에게 보인다. 아무것도 싣지 않는다."""


@lru_cache(maxsize=8)
def vocabulary(sha256: str) -> dict:
    """받아들인 판의 어휘. 파일의 바이트 지문이 목록과 다르면 고장이다(정본을 손으로 고치고 목록을 안 고친 것)."""
    name = ACCEPTED.get(sha256)
    if name is None:
        raise OntoPackageError(f"받아들이지 않은 어휘 판이다(sha256={sha256[:12]}…) — 받아들인 판: "
                               + ", ".join(s[:12] + "…" for s in ACCEPTED))
    raw = (VOCAB_DIR / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise OntoPackageError(f"어휘 파일 {name} 의 지문이 받아들인 판 목록과 다르다 — 정본을 고쳤으면 판을 올리고 목록을 고친다")
    return json.loads(raw)


def _shape(vocab: dict) -> tuple[dict, dict]:
    types = {t["slug"]: {p["key"]: p for p in t.get("properties") or []} for t in vocab.get("types") or []}
    rels = {r["slug"]: r for r in vocab.get("relation_types") or []}
    return types, rels


def _enum_values(prop: dict) -> set:
    return {o.get("value") if isinstance(o, dict) else o for o in prop.get("enum_options") or []}


def _check_value(where: str, prop: dict, value: Any) -> None:
    kind = prop.get("data_type")
    ok = {"number": isinstance(value, (int, float)) and not isinstance(value, bool),
          "bool": isinstance(value, bool),
          "enum": value in _enum_values(prop),
          "object_ref": isinstance(value, str) and bool(value)}.get(kind, isinstance(value, str))
    if not ok:
        raise OntoPackageError(f"{where} 값이 어휘의 꼴({kind})과 다르다: {value!r}")


def check(pkg: Any, *, report_id: str, report_kind: str, html_sha256: str | None, case_keys: set[str]) -> dict:
    """꾸러미를 검사하고 싣을 행 · 선을 돌려준다. 맞지 않으면 OntoPackageError(아무것도 싣지 않는다).

    → {"vocabulary": {version, sha256}, "rows": [...], "edges": [...], "counts": {...}, "runs": {...}, "warnings": [...]}
    키는 `<report_id>/<꾸러미 키>` 로, 참조 값도 같게 바꾼다. `cae_campaign.report` 는 report_id 로 채운다.
    """
    if not isinstance(pkg, dict) or pkg.get("format") != FORMAT or pkg.get("format_version") != FORMAT_VERSION:
        got = (pkg.get("format"), pkg.get("format_version")) if isinstance(pkg, dict) else type(pkg).__name__
        raise OntoPackageError(f"모르는 꾸러미 꼴이다({got}) — {FORMAT} v{FORMAT_VERSION} 만 받는다")
    voc = pkg.get("vocabulary") if isinstance(pkg.get("vocabulary"), dict) else {}
    types, rels = _shape(vocabulary(str(voc.get("sha256") or "")))
    want = SCENARIO_OF.get(report_kind)
    scope = pkg.get("scope") if isinstance(pkg.get("scope"), dict) else {}
    if scope.get("scenario_kind") != want:
        raise OntoPackageError(f"리포트 종류({report_kind})와 꾸러미 범위({scope.get('scenario_kind')!r})가 다르다 — {want!r} 여야 한다")
    warnings: list[str] = []
    src = pkg.get("source") if isinstance(pkg.get("source"), dict) else {}
    html = src.get("html") if isinstance(src.get("html"), dict) else None
    if html and html_sha256 and str(html.get("sha256") or "").lower() != html_sha256.lower():
        raise OntoPackageError(f"이 리포트의 꾸러미가 아니다 — 꾸러미가 가리키는 HTML({html.get('file')}) 지문이 리포트 원본과 다르다")
    if not html:
        warnings.append("꾸러미에 짝 HTML 지문(source.html)이 없다 — 붙인 사람이 고른 리포트를 믿는다")

    objects = pkg.get("objects") if isinstance(pkg.get("objects"), list) else None
    relations = pkg.get("relations") if isinstance(pkg.get("relations"), list) else []
    if not objects:
        raise OntoPackageError("objects 가 비었거나 목록이 아니다")
    keys: dict[str, set[str]] = {}
    for o in objects:
        t, k = (o.get("type"), o.get("key")) if isinstance(o, dict) else (None, None)
        if t not in types or not isinstance(k, str) or not k:
            raise OntoPackageError(f"모르는 타입이거나 key 가 없다: {t!r} · {k!r}")
        if k in keys.setdefault(t, set()):
            raise OntoPackageError(f"{t} {k!r} 가 두 번 나온다")
        keys[t].add(k)

    rows: list[dict] = []
    for o in objects:
        t, k, props = o["type"], o["key"], o.get("properties") if isinstance(o.get("properties"), dict) else {}
        defs = types[t]
        for name, value in props.items():
            if name not in defs:
                raise OntoPackageError(f"{t} {k!r} 에 어휘에 없는 칸이 있다: {name!r}")
            _check_value(f"{t} {k!r} 의 {name}", defs[name], value)
            target = defs[name].get("ref_type_slug")
            if defs[name].get("data_type") == "object_ref" and target != REPORT_TYPE and value not in keys.get(target, ()):
                raise OntoPackageError(f"{t} {k!r} 의 {name} 가 가리키는 {target} {value!r} 가 꾸러미에 없다")
        missing = [n for n, d in defs.items() if d.get("required") and n not in props
                   and not (t == "cae_campaign" and n == "report")]           # report 는 받는 쪽이 채운다(계약 §3)
        if missing:
            raise OntoPackageError(f"{t} {k!r} 에 필수 칸이 없다: {missing}")
        if t not in LOADED_TYPES:
            continue
        out = {}
        for name, value in props.items():
            d = defs[name]
            out[name] = (f"{report_id}/{value}" if d.get("data_type") == "object_ref" and d.get("ref_type_slug") != REPORT_TYPE
                         else value)
        if t == "cae_campaign":
            out["report"] = report_id
        rows.append({"type_slug": t, "key": f"{report_id}/{k}", "label": str(o.get("label") or k)[:500], "properties": out})

    edges: list[dict] = []
    for r in relations:
        slug = r.get("relation") if isinstance(r, dict) else None
        src_, dst_ = (r.get("src"), r.get("dst")) if isinstance(r, dict) else (None, None)
        if slug not in rels or not (isinstance(src_, list) and isinstance(dst_, list) and len(src_) == len(dst_) == 2):
            raise OntoPackageError(f"모르는 관계이거나 끝의 꼴이 틀렸다: {slug!r}")
        d = rels[slug]
        for (typ, key), allowed in ((src_, d.get("src_type_slugs") or []), (dst_, d.get("dst_type_slugs") or [])):
            if allowed and typ not in allowed:
                raise OntoPackageError(f"관계 {slug} 의 끝 타입 {typ!r} 는 어휘가 허락하지 않는다({allowed})")
            if key not in keys.get(typ, ()):
                raise OntoPackageError(f"관계 {slug} 의 끝 {typ} {key!r} 가 꾸러미에 없다")
        if src_[0] in LOADED_TYPES and dst_[0] in LOADED_TYPES:
            edges.append({"relation": slug, "src_type": src_[0], "src_key": f"{report_id}/{src_[1]}",
                          "dst_type": dst_[0], "dst_key": f"{report_id}/{dst_[1]}",
                          "properties": r.get("properties") if isinstance(r.get("properties"), dict) else None})
    campaigns = [x for x in rows if x["type_slug"] == "cae_campaign"]
    if len(campaigns) != 1:
        raise OntoPackageError(f"캠페인이 하나여야 한다(지금 {len(campaigns)})")
    edges.append({"relation": CAMPAIGN_REPORT, "src_type": "cae_campaign", "src_key": campaigns[0]["key"],
                  "dst_type": REPORT_TYPE, "dst_key": report_id, "properties": None})

    run_keys = {str((o.get("properties") or {}).get("case_key") or "") for o in objects if o["type"] == "cae_run"}
    matched = sorted(run_keys & case_keys)
    missing_runs = sorted(run_keys - case_keys)
    if run_keys and not matched:
        raise OntoPackageError(f"꾸러미의 런 {len(run_keys)}개가 이 리포트의 각도와 하나도 맞지 않는다 — 다른 리포트의 꾸러미다")
    if missing_runs:
        warnings.append(f"꾸러미의 런 {len(missing_runs)}개가 이 리포트에 없다(예 {missing_runs[:3]})")
    counts = {"objects": {t: len(v) for t, v in sorted(keys.items())},
              "loaded": {t: sum(1 for x in rows if x["type_slug"] == t) for t in LOADED_TYPES},
              "edges": len(edges)}
    return {"vocabulary": {"version": voc.get("version"), "sha256": voc.get("sha256")}, "rows": rows, "edges": edges,
            "counts": counts, "runs": {"package": len(run_keys), "matched": len(matched), "missing": missing_runs[:20]},
            "warnings": warnings + [str(w) for w in pkg.get("warnings") or []]}
