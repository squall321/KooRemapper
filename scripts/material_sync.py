#!/usr/bin/env python3
# 물성 레이크(MaterialTwin) ↔ 사용 집합(material_db.json) 대조·판단·갱신
"""MaterialTwin 은 **데이터 레이크**(출처·측정법·불확실도까지 쌓는 곳)이고,
`material_db.json` 은 **정리된 사용 집합**(해석 덱에 실제로 꽂히는 것)이다. 지금까지
레이크 → 사용 집합 방향의 길이 없어서, 4월 이후 쌓인 것이 해석에 닿지 못했다.

규율 넷 — 이 도구가 지키는 것.

1. **기본은 보고서다.** 값을 바꾸는 것은 `--apply` 로만 한다.
2. **짝을 추측으로 짓지 않는다.** 이름 정확→정규화→별칭(사람이 적은 것) 순이고,
   못 지은 것은 목록으로 낸다. 비슷해 보인다고 붙이지 않는다.
3. **환산은 명시적으로, 범위 밖은 버린다.** 레이크는 SI, 사용 집합은 t/mm/s 다.
   환산 뒤 값이 물리적으로 말이 안 되면 쓰지 않고 사유와 함께 보고한다.
4. **근거 없는 값은 쓰지 않는다.** 갱신마다 레이크의 출처·측정법·등급·조회 일시를 남긴다.

`material_db.json` 은 `.k` 에서 통째로 **재생성되는 생성물**이라 직접 고치지 않는다.
갱신은 `materials/material_overrides.yaml` 오버레이로 나가고, 빌더가 마지막에 얹는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from material_cards import CARD_FIELDS  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DEFAULT_DB = HERE / "materials" / "material_db.json"
DEFAULT_OVERLAY = HERE / "materials" / "material_overrides.yaml"
LAKE_CANDIDATES = (
    Path("/home/koopark/claude/HEAXHub/var/app_data/materialtwin_web/materialtwin.db"),
    Path("/home/koopark/claude/MaterialTwinWeb/backend/var/data/materialtwin.db"),
)

# 레이크 물성 키 → 사용 집합 필드 + SI→(t/mm/s) 환산 계수
#   밀도 kg/m³ → t/mm³ (×1e-12) · 응력 Pa → MPa (×1e-6) · 포아송비 무차원
FIELD_MAP = {
    "physical.density":            ("RHO",  1e-12),
    "mechanical.youngs_modulus":   ("E",    1e-6),
    "mechanical.poisson_ratio":    ("PR",   1.0),
    "mechanical.yield_strength":   ("SIGY", 1e-6),
}
# 환산 뒤 **물리적으로 말이 되는 범위**. 벗어나면 쓰지 않는다 —
# 단위를 잘못 읽은 값이 조용히 들어가는 것이 이 판에서 가장 흔한 사고다.
SANE = {
    "RHO":  (1e-11, 3.0e-8),      # 0.01 ~ 30 g/cm³
    # 하한은 **연질 접착제·겔**까지 받는다(1 kPa). 처음에 0.1MPa 로 뒀더니 PSA·OCA 의
    # 실측 0.09MPa 를 "단위 오해" 로 버렸다 — 밴드가 틀렸지 값이 틀린 게 아니었다.
    # Pa↔MPa 오해는 1e6 배라 이 하한으로도 충분히 걸린다.
    "E":    (1e-3, 1.5e6),        # 1 kPa(연질 PSA) ~ 1.5 TPa(다이아몬드)
    "PR":   (-0.5, 0.499),
    "SIGY": (0.01, 1.0e5),
}
# 신뢰 등급 — MaterialTwin 정의(models.py): 1 측정(1차문헌) · 2 핸드북/권위DB ·
# 3 데이터시트 · 4 계산 · 5 추정. **작을수록 좋다**(반대로 알기 쉬워 여기 적어 둔다).
METHOD_RANK = {"measured": 0, "digitized": 1, "handbook": 2, "computed": 3,
               "estimated": 4}
TRUSTED_TIER = 3          # 이보다 나쁜 근거로는 갱신을 제안하지 않는다
# **이보다 큰 차이는 교정이 아니라 짝을 잘못 지은 것일 때가 많다.** 실측 —
# `NBR Cushion Rubber`(1.3 g/cc) 가 레이크에서 같은 이름의 **스펀지** 데이터시트
# (0.15 g/cc)와 짝지어져 밀도 -88% 갱신을 제안했다. 이름은 같아도 물리적 형태가 다르다.
# 자동 제안에서 빼고 사람이 보게 한다(`--include-large` 로 넣을 수 있다).
LARGE_DELTA = 0.5


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_lake(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            sys.exit(f"레이크 DB 가 없다: {p}")
        return p
    for p in LAKE_CANDIDATES:
        if p.is_file():
            return p
    sys.exit("레이크 DB 를 못 찾았다 — --lake 로 경로를 줄 것")


def load_used_set(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["materials"]


def load_lake(path: Path) -> dict[str, dict]:
    """레이크 재료마다 **대표값 한 개**를 고른다.

    한 재료에 논문·데이터시트별 값이 여럿 있다(그것이 레이크의 성질이다). 고르는 규칙은
    측정법 → 등급 → 최신 순이고, **얼마나 흩어져 있는지도 함께 남긴다**(대표값만 보면
    합의가 있는 값인지 아닌지 알 수 없다).
    """
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    keys = tuple(FIELD_MAP)
    rows = con.execute(
        "SELECT m.id, m.name, m.category, pv.property_key, pv.value_num, pv.unit,"
        "       pv.method, pv.quality_tier, pv.created_at,"
        "       s.kind AS src_kind, s.title AS src_title, s.doi AS src_doi,"
        "       s.year AS src_year"
        "  FROM property_value pv"
        "  JOIN material m ON m.id = pv.material_id"
        "  LEFT JOIN source s ON s.id = pv.source_id"
        f" WHERE pv.property_key IN ({','.join('?' * len(keys))})"
        "   AND pv.value_num IS NOT NULL", keys).fetchall()
    con.close()

    grouped: dict[int, dict] = {}
    for r in rows:
        mat = grouped.setdefault(r["id"], {"name": r["name"], "category": r["category"],
                                           "props": defaultdict(list)})
        mat["props"][r["property_key"]].append(dict(r))

    out: dict[str, dict] = {}
    for mat in grouped.values():
        picked = {}
        for key, cands in mat["props"].items():
            best = sorted(cands, key=lambda c: (
                METHOD_RANK.get(c["method"], 9), c["quality_tier"] or 9,
                -(c["src_year"] or 0), str(c["created_at"] or "")))[0]
            vals = [c["value_num"] for c in cands]
            spread = (max(vals) - min(vals)) / abs(best["value_num"]) \
                if best["value_num"] else None
            picked[key] = {**best, "candidates": len(cands),
                           "spread_rel": round(spread, 4) if spread is not None else None}
        out[mat["name"]] = {"name": mat["name"], "category": mat["category"],
                            "props": picked}
    return out


def load_aliases(path: Path | None) -> dict[str, str]:
    """사용 집합 이름 → 레이크 이름. **사람이 적는 파일**이다(추측으로 채우지 않는다)."""
    if not path or not Path(path).is_file():
        return {}
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    aliases = data.get("aliases") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in (aliases or {}).items()}


def match(used: dict, lake: dict, aliases: dict[str, str]) -> tuple[dict, list]:
    by_norm: dict[str, list[str]] = defaultdict(list)
    for name in lake:
        by_norm[norm_name(name)].append(name)
    pairs, unmatched = {}, []
    for mid, m in used.items():
        name = m.get("name") or ""
        target = None
        how = ""
        if name in aliases and aliases[name] in lake:
            target, how = aliases[name], "alias"
        elif name in lake:
            target, how = name, "exact"
        else:
            cands = by_norm.get(norm_name(name), [])
            if len(cands) == 1:
                target, how = cands[0], "normalized"
            elif len(cands) > 1:
                # **여럿이면 고르지 않는다** — 사람이 별칭으로 지목해야 한다
                unmatched.append({"mid": mid, "name": name, "reason": "동명 후보 여럿",
                                  "candidates": cands[:5]})
                continue
        if target is None:
            unmatched.append({"mid": mid, "name": name, "reason": "레이크에 없음"})
            continue
        pairs[mid] = {"used": m, "lake": lake[target], "how": how}
    return pairs, unmatched


def compare(pairs: dict, tol: float) -> list[dict]:
    """짝지어진 것끼리 값 비교. 판단은 하되 **바꾸지는 않는다**."""
    findings = []
    for mid, pair in pairs.items():
        used, lake = pair["used"], pair["lake"]
        mech = used.get("mechanical") or {}
        writable = CARD_FIELDS.get(used.get("mat_type"), {})
        for key, (field, factor) in FIELD_MAP.items():
            got = lake["props"].get(key)
            if not got:
                continue
            new = got["value_num"] * factor
            lo, hi = SANE[field]
            if not (lo <= new <= hi):
                findings.append({
                    "mid": mid, "name": used.get("name"), "field": field,
                    "verdict": "범위밖", "old": mech.get(field), "new": new,
                    "why": f"환산값이 {lo:g}~{hi:g} 범위를 벗어난다 — 단위 오해 의심",
                    "lake_material": lake["name"]})
                continue
            old = mech.get(field)
            item = {
                "mid": mid, "name": used.get("name"), "mat_type": used.get("mat_type"),
                "field": field, "old": old, "new": round(new, 12),
                "lake_material": lake["name"], "match": pair["how"],
                "method": got["method"], "quality_tier": got["quality_tier"],
                "candidates": got["candidates"], "spread_rel": got["spread_rel"],
                "source": {"kind": got["src_kind"], "title": got["src_title"],
                           "doi": got["src_doi"], "year": got["src_year"]},
            }
            weak = (got["quality_tier"] or 9) > TRUSTED_TIER
            if old in (None, 0):
                item["verdict"] = "빈칸채움" if not weak else "빈칸(근거약함)"
            else:
                rel = abs(new - old) / abs(old)
                item["delta_rel"] = round(rel, 4)
                if rel <= tol:
                    item["verdict"] = "일치"
                elif rel > LARGE_DELTA:
                    item["verdict"] = "차이(큼·짝 확인)"
                elif weak:
                    item["verdict"] = "차이(근거약함)"
                else:
                    item["verdict"] = "차이"
            if field not in writable and item["verdict"] not in ("일치",):
                item["writable"] = False
                item["why"] = (f"{used.get('mat_type')} 카드에 {field} 칸이 없다 "
                               f"— 파생값이라 되쓸 수 없다")
            else:
                item["writable"] = field in writable
            findings.append(item)
    return findings


def proposals(findings: list[dict], include_large: bool = False) -> list[dict]:
    """실제로 반영을 제안하는 것만. 근거가 약하거나·못 쓰는 칸·차이가 너무 큰 것은 뺀다."""
    ok = {"차이", "빈칸채움"}
    if include_large:
        ok.add("차이(큼·짝 확인)")
    return [f for f in findings if f.get("verdict") in ok and f.get("writable")]


def write_overlay(path: Path, props: list[dict], tol: float) -> dict:
    import yaml
    existing = {}
    if path.is_file():
        old = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        existing = old.get("overrides") or {}
    for p in props:
        entry = existing.setdefault(str(p["mid"]), {"name": p["name"],
                                                    "mechanical": {}, "provenance": {}})
        entry["mechanical"][p["field"]] = p["new"]
        entry["provenance"][p["field"]] = {
            "from": p.get("old"), "lake_material": p["lake_material"],
            "match": p["match"], "method": p["method"],
            "quality_tier": p["quality_tier"], "candidates": p["candidates"],
            "spread_rel": p["spread_rel"], "source": p["source"],
            "checked_at": str(date.today()),
        }
    doc = {
        "# ": "material_sync.py 가 쓴 갱신분. 손으로 고쳐도 된다 — 다음 실행이 존중한다.",
        "version": 1,
        "generated": str(date.today()),
        "tolerance_rel": tol,
        "overrides": existing,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return {"path": str(path), "materials": len(existing),
            "fields": sum(len(e["mechanical"]) for e in existing.values())}


def report(findings, unmatched, pairs_n, used_n, lake_n, tol,
           include_large: bool = False) -> None:
    counts = defaultdict(int)
    for f in findings:
        counts[f["verdict"]] += 1
    print(f"사용 집합 {used_n}종 · 레이크 {lake_n}종 · 짝지음 {pairs_n}종 "
          f"(허용오차 {tol:.1%})")
    print("판정:", dict(counts) or "비교할 값이 없다")
    props = proposals(findings, include_large)
    print(f"갱신 제안 {len(props)}건")
    for p in sorted(props, key=lambda x: -(x.get("delta_rel") or 0))[:20]:
        d = f"{p['delta_rel']:+.1%}" if p.get("delta_rel") is not None else "빈칸"
        src = p["source"]["title"] or p["source"]["kind"] or "-"
        # 흩어짐(같은 물성에 대한 레이크 값들의 폭)을 함께 보여 준다 — 대표값만 보면
        # 합의가 있는 값인지 논문마다 갈리는 값인지 알 수 없다.
        sp = f"±{p['spread_rel']:.0%}" if p.get("spread_rel") else "  -"
        print(f"  {p['name'][:24]:<24} {p['field']:<5} "
              f"{p['old']!s:>11} → {p['new']:<11.6g} {d:>8} {sp:>5} n={p['candidates']:<3}"
              f"tier{p['quality_tier']} {p['method'][:8]:<8} {p['match'][:4]:<4} {str(src)[:26]}")
    large = [f for f in findings if f["verdict"] == "차이(큼·짝 확인)"]
    if large and not include_large:
        print(f"\n차이가 커서 뺀 것 {len(large)}건 — **짝이 맞는지 사람이 볼 것**"
              f"(같은 이름이어도 형태가 다를 수 있다):")
        for b in sorted(large, key=lambda x: -x["delta_rel"])[:8]:
            print(f"  {b['name'][:24]:<24} {b['field']:<5} {b['old']!s:>11} → "
                  f"{b['new']:<11.6g} {b['delta_rel']:+.0%}  ← {b['lake_material'][:40]}")
    blocked = [f for f in findings if f.get("writable") is False]
    if blocked:
        print(f"\n되쓸 수 없는 칸 {len(blocked)}건(파생값) — 예:")
        for b in blocked[:5]:
            print(f"  {b['name'][:26]:<26} {b['field']:<5} {b.get('why','')}")
    out_of_range = [f for f in findings if f["verdict"] == "범위밖"]
    if out_of_range:
        print(f"\n범위 밖이라 버린 값 {len(out_of_range)}건 — 예:")
        for b in out_of_range[:5]:
            print(f"  {b['name'][:26]:<26} {b['field']:<5} {b['new']:.4g}  {b['why']}")
    if unmatched:
        print(f"\n짝 못 지은 사용 집합 {len(unmatched)}종 "
              f"(별칭 파일에 사람이 적어야 한다) — 예:")
        for u in unmatched[:8]:
            extra = f" 후보 {u['candidates']}" if u.get("candidates") else ""
            print(f"  {u['name'][:34]:<34} {u['reason']}{extra}")


def main() -> int:
    ap = argparse.ArgumentParser(description="물성 레이크 ↔ 사용 집합 대조·갱신")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="material_db.json")
    ap.add_argument("--lake", default=None, help="materialtwin.db (읽기 전용)")
    ap.add_argument("--alias", default=None, help="별칭 YAML (aliases: {사용집합명: 레이크명})")
    ap.add_argument("--tol", type=float, default=0.05, help="상대 허용오차(기본 5%%)")
    ap.add_argument("--json", default=None, help="전체 결과를 JSON 으로 저장")
    ap.add_argument("--apply", action="store_true",
                    help="갱신 제안을 오버레이에 반영한다(기본은 보고서만)")
    ap.add_argument("--overlay", default=str(DEFAULT_OVERLAY))
    ap.add_argument("--include-large", action="store_true",
                    help=f"차이가 {LARGE_DELTA:.0%} 넘는 것도 제안에 넣는다(짝을 확인한 뒤에)")
    a = ap.parse_args()

    used = load_used_set(Path(a.db))
    lake = load_lake(find_lake(a.lake))
    pairs, unmatched = match(used, lake, load_aliases(a.alias))
    findings = compare(pairs, a.tol)
    report(findings, unmatched, len(pairs), len(used), len(lake), a.tol,
           a.include_large)

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"findings": findings, "unmatched": unmatched,
             "counts": {"used": len(used), "lake": len(lake), "paired": len(pairs)}},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {a.json}")
    if a.apply:
        st = write_overlay(Path(a.overlay), proposals(findings, a.include_large), a.tol)
        print(f"\n오버레이 갱신 — {st['materials']}종 {st['fields']}칸 → {st['path']}")
        print("  ⚠ 반영은 build_material_db.py 를 다시 돌려야 material_db.json 에 들어간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
