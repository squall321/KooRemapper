# 캠페인 분석(DF-05 · 06 · 08 ~ 12)의 서비스 — 넣는 런 · 리포트 케이스를 읽어 순수 함수(angles · sphere)에 넘기고, 무리 · 기준값 · 자리 · 짝 표 · 쌍 규칙을 쓴다
"""캠페인 분석 서비스(계획 docs/01-plan/features/df-campaign-analysis-1122.plan.md).

넣는 런은 건강 표와 같은 규칙이다 — 제외 까닭이 없는 런(`include_invalid` 면 리포트가 있는 런 모두). 첫 KE 가 ½mv² 와 어긋난 런
(`ke0_mismatch` — KE 튐)은 기본으로 빼고 따로 센다. 설정 쌍 비교는 옛 세대 런이 새 세대로 대체돼 있으므로 대체 까닭만 무시한다.
"""
from __future__ import annotations

import ulid
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (Campaign, CampaignPartGroup, CampaignRun, CampaignSite, CampaignSiteMetric, CriteriaBinding,
                        ImpactCase, ImpactReport, PartMap)
from app.modules.campaigns import health as H
from app.modules.campaigns import services as svc


async def analysis_runs(db: AsyncSession, campaign: Campaign, *, include_invalid: bool = False, include_ke_jump: bool = False,
                        config_generation: str | None = None, ignore_superseded: bool = False) -> tuple[list[dict], dict]:
    """넣는 런(리포트 케이스까지)과 머리 — `(runs, header)`."""
    tb = H.bundle(campaign.health_thresholds)
    rows = list((await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign.id).order_by(CampaignRun.id)
    )).scalars())
    total = len(rows)
    by: dict[str, int] = {}
    ke_jump = 0
    picked: list[tuple[CampaignRun, dict]] = []
    gens: dict[str | None, int] = {}
    for r in rows:
        j = svc._judged(r, tb["values"], tb["ref"])
        excl = [x for x in j["excluded_by"] if not (ignore_superseded and x == "superseded")]
        jump = "ke0_mismatch" in j["validity"]["reasons"]
        if config_generation is not None and r.config_generation != config_generation:
            by["other_generation"] = by.get("other_generation", 0) + 1
            continue
        if r.report_id is None:
            for why in excl or ["no_report"]:
                by[why] = by.get(why, 0) + 1
            continue
        if excl and not include_invalid:
            for why in excl:
                by[why] = by.get(why, 0) + 1
            continue
        if jump and not include_ke_jump:
            ke_jump += 1
            continue
        picked.append((r, j))
        gens[r.config_generation] = gens.get(r.config_generation, 0) + 1
    cases: dict[str, list[dict]] = {}
    rids = {r.report_id for r, _ in picked}
    if rids:
        for cs in (await db.execute(
            select(ImpactCase).where(ImpactCase.report_id.in_(rids)).order_by(ImpactCase.report_id, ImpactCase.id)
        )).scalars():
            cases.setdefault(cs.report_id, []).append({"case_key": cs.case_key, "identity": cs.identity,
                                                       "parts_metrics": cs.parts_metrics or {}})
    runs = [{"run_key": r.run_key, "doe": r.doe, "pitch": r.pitch, "roll": r.roll, "report_id": r.report_id,
             "config_generation": r.config_generation, "impacts": r.impacts, "health": r.health, "extraction": r.extraction,
             "validity": j["validity"], "report": {"cases": cases.get(r.report_id, [])}} for r, j in picked]
    header = {"total": total, "included": len(runs), "excluded_by": by, "excluded_ke_jump": ke_jump,
              "include_invalid": include_invalid, "include_ke_jump": include_ke_jump, "config_generation": config_generation,
              "generations": [{"config_generation": g, "runs": n} for g, n in sorted(gens.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))],
              "thresholds_ref": tb["ref"]}
    line = f"유효 {len(runs)} / 전체 {total}"
    if by or ke_jump:
        parts = [f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))]
        if ke_jump:
            parts.append(f"excluded_ke_jump {ke_jump}")
        line += " · 제외 " + " · ".join(parts)
    header["line"] = line
    return runs, header


# ── 무리 ─────────────────────────────────────────────────────────────────────

async def part_groups(db: AsyncSession, campaign_id: str) -> list[dict]:
    return [{"group_key": g.group_key, "label": g.label, "part_ids": g.part_ids, "part_key": g.part_key}
            for g in (await db.execute(
                select(CampaignPartGroup).where(CampaignPartGroup.campaign_id == campaign_id).order_by(CampaignPartGroup.id)
            )).scalars()]


async def set_part_groups(db: AsyncSession, campaign_id: str, groups: list[dict]) -> list[dict]:
    await db.execute(delete(CampaignPartGroup).where(CampaignPartGroup.campaign_id == campaign_id))
    if groups:
        await db.execute(insert(CampaignPartGroup), [{"campaign_id": campaign_id, **g} for g in groups])
    await db.commit()
    return await part_groups(db, campaign_id)


# ── 기준값 ───────────────────────────────────────────────────────────────────

async def criteria(db: AsyncSession, campaign_id: str) -> list[dict]:
    return [{"part_id": c.part_id, "group_key": c.group_key, "failure_mode": c.failure_mode, "metric_axis": c.metric_axis,
             "criterion_value": c.criterion_value, "unit": c.unit, "source_platform": c.source_platform,
             "source_record_id": c.source_record_id, "version": c.version}
            for c in (await db.execute(
                select(CriteriaBinding).where(CriteriaBinding.campaign_id == campaign_id).order_by(CriteriaBinding.id)
            )).scalars()]


async def set_criteria(db: AsyncSession, campaign_id: str, items: list[dict]) -> list[dict]:
    await db.execute(delete(CriteriaBinding).where(CriteriaBinding.campaign_id == campaign_id))
    if items:
        await db.execute(insert(CriteriaBinding), [{"campaign_id": campaign_id, **c} for c in items])
    await db.commit()
    return await criteria(db, campaign_id)


# ── 자리 ─────────────────────────────────────────────────────────────────────

_SITE_COLS = ("site_id", "face", "col", "row", "x_mm", "y_mm", "under_category", "impactor", "run_key", "footprint")


async def sites(db: AsyncSession, campaign_id: str) -> list[dict]:
    rows = list((await db.execute(
        select(CampaignSite).where(CampaignSite.campaign_id == campaign_id).order_by(CampaignSite.id)
    )).scalars())
    mets: dict[int, list[dict]] = {}
    if rows:
        for m in (await db.execute(
            select(CampaignSiteMetric).where(CampaignSiteMetric.site_row_id.in_([r.id for r in rows])).order_by(CampaignSiteMetric.id)
        )).scalars():
            mets.setdefault(m.site_row_id, []).append({"part": m.part, "metric": m.metric, "value": m.value, "time_ms": m.time_ms,
                                                       "elem_id": m.elem_id, "ratio": m.ratio})
    return [{**{c: getattr(r, c) for c in _SITE_COLS}, "metrics": mets.get(r.id, [])} for r in rows]


async def set_sites(db: AsyncSession, campaign_id: str, items: list[dict]) -> int:
    await db.execute(delete(CampaignSite).where(CampaignSite.campaign_id == campaign_id))
    for it in items:
        mets = it.pop("metrics", None) or []
        row = CampaignSite(campaign_id=campaign_id, **it)
        db.add(row)
        await db.flush()
        if mets:
            await db.execute(insert(CampaignSiteMetric), [{"site_row_id": row.id, **m} for m in mets])
    await db.commit()
    return len(items)


async def run_facts(db: AsyncSession, campaign_id: str, run_keys: set[str]) -> dict[str, dict]:
    """자리에 묶인 런 → `{run_key: {report_id, parts_metrics(첫 케이스), health}}`."""
    if not run_keys:
        return {}
    runs = list((await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign_id, CampaignRun.run_key.in_(run_keys))
    )).scalars())
    rids = {r.report_id for r in runs if r.report_id}
    first: dict[str, dict] = {}
    if rids:
        for cs in (await db.execute(
            select(ImpactCase).where(ImpactCase.report_id.in_(rids)).order_by(ImpactCase.report_id, ImpactCase.id)
        )).scalars():
            first.setdefault(cs.report_id, cs.parts_metrics or {})
    return {r.run_key: {"report_id": r.report_id, "parts_metrics": first.get(r.report_id) if r.report_id else None,
                        "health": r.health} for r in runs}


# ── 파트 짝 표 ───────────────────────────────────────────────────────────────

async def create_part_map(db: AsyncSession, user_id: int, body: dict) -> PartMap:
    row = PartMap(id=ulid.new().str, created_by=user_id, **body)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_part_map(db: AsyncSession, user_id: int, map_id: str) -> PartMap | None:
    return (await db.execute(select(PartMap).where(PartMap.id == map_id, PartMap.created_by == user_id))).scalar_one_or_none()


def part_map_dict(m: PartMap) -> dict:
    return {"map_id": m.id, "label": m.label, "from_model": m.from_model, "to_model": m.to_model, "rows": m.rows,
            "n_rows": len(m.rows or []), "created_at": m.created_at}


async def report_parts(db: AsyncSession, report_ids: set[str]) -> dict[str, list[dict]]:
    """리포트의 파트 목록 — `{report_id: [{part_id, name, group}]}`."""
    if not report_ids:
        return {}
    return {r.id: list(r.parts or []) for r in (await db.execute(
        select(ImpactReport).where(ImpactReport.id.in_(report_ids))
    )).scalars()}


# ── 쌍 규칙 ──────────────────────────────────────────────────────────────────

async def set_pair_rule(db: AsyncSession, campaign: Campaign, rule: dict | None) -> dict | None:
    campaign.pair_rule = rule
    await db.commit()
    return campaign.pair_rule


# ── 핫스팟 자리(DF-07) ───────────────────────────────────────────────────────

async def set_frame_offset(db: AsyncSession, campaign: Campaign, offset: dict | None) -> dict | None:
    campaign.frame_offset = offset
    await db.commit()
    return campaign.frame_offset


async def hotspot_items(db: AsyncSession, runs: list[dict], part_id: int) -> list[dict]:
    """넣은 런의 리포트 핫스팟 군집(그 파트 · 모든 기준) — 군집마다 런 · 각도 · 중심(결과 틀) · 최대 응력 · 반경 · 기준."""
    from app.modules.reports import services as rsvc

    out = []
    for run in runs:
        rep = await db.get(ImpactReport, run["report_id"])
        if rep is None:
            continue
        res = await rsvc.hotspots(db, rep, part_id=part_id, top=0)
        if not res.get("available"):
            continue
        for c in res.get("clusters") or []:
            out.append({"run_key": run["run_key"], "case_key": c.get("case_key") or "single", "doe": run["doe"],
                        "report_id": run["report_id"], "center": c.get("center"), "stress_max": c.get("stress_max"),
                        "radius_enclosing": c.get("radius_enclosing"), "criterion": c.get("criterion")})
    return out


async def deck_part_bbox(db: AsyncSession, report_ids: list[str], part_id: int) -> dict | None:
    """리포트의 원본 K 파일 메타(modelmeta)에서 그 파트의 덱 틀 bbox — 처음 찾은 것."""
    from app.models import SessionFile

    for rid in report_ids:
        rep = await db.get(ImpactReport, rid)
        if rep is None or rep.source_kfile_id is None:
            continue
        f = await db.get(SessionFile, rep.source_kfile_id)
        mm = ((f.meta or {}).get("modelmeta") or {}) if f is not None else {}
        for p in mm.get("parts") or []:
            if isinstance(p, dict) and str(p.get("pid")) == str(part_id) and p.get("bbox_min") and p.get("bbox_max"):
                return {"bbox_min": p["bbox_min"], "bbox_max": p["bbox_max"], "report_id": rid, "file_id": f.id,
                        "title": p.get("title")}
    return None
