# 캠페인(런 묶음)과 런 목록 · 런마다의 적재 상태를 다루는 서비스 — 리포트 서비스를 부르지 않는다(거꾸로만 부른다)
"""캠페인 묶음 적재(요청서 DF-01 · 계획 docs/01-plan/features/df-campaign-intake-1120.plan.md).

런의 `ingest_state` 는 **마지막 시도의 결과**고, `report_id` · `content_sha256` · `ingested_at` 은 그 런이 **가진 리포트**다.
리포트가 지워져 `report_id` 가 비면 받았거나 건너뛴 런은 읽을 때 `pending` 으로 보인다(`_EFFECTIVE`) — 행은 고치지 않는다.
"""
from __future__ import annotations

import ulid
from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, CampaignRun, ImpactReport
from app.modules.campaigns import extraction as X
from app.modules.campaigns import health as H

STATES = ("pending", "received", "skipped", "rejected")
_REASON_MAX = 2000

# 읽을 때의 상태 — 리포트를 잃은 received · skipped 는 pending 이다(다시 받을 수 있다).
_EFFECTIVE = case(
    (and_(CampaignRun.report_id.is_(None), CampaignRun.ingest_state.in_(("received", "skipped"))), "pending"),
    else_=CampaignRun.ingest_state,
)


class BadManifest(ValueError):
    """목록을 다 맞춘 뒤 대조가 깨졌다(`superseded_by` 가 없는 런 · 자기 자신 · 고리) — 라우트가 422 로 돌린다."""


class RunTaken(Exception):
    """잠그고 보니 그 런이 이미 리포트를 가졌다 — 같은 런이 동시에 왔고 이쪽이 늦었다."""


async def create_campaign(db: AsyncSession, user_id: int, fields: dict) -> Campaign | None:
    """캠페인을 만든다. 같은 사람이 같은 이름을 이미 썼으면 None(부르는 쪽이 `find_by_name` 으로 id 를 준다)."""
    row = Campaign(id=ulid.new().str, created_by=user_id, **fields)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    await db.refresh(row)
    return row


async def find_by_name(db: AsyncSession, user_id: int, name: str) -> str | None:
    return (await db.execute(
        select(Campaign.id).where(Campaign.created_by == user_id, Campaign.name == name)
    )).scalar_one_or_none()


async def get_owned(db: AsyncSession, user_id: int, campaign_id: str) -> Campaign | None:
    row = await db.get(Campaign, campaign_id)
    if row is None or row.created_by != user_id:
        return None
    return row


async def upsert_runs(db: AsyncSession, campaign_id: str, items: list[dict]) -> dict:
    """런 목록을 올린다 — 새 `run_key` 는 pending 으로 더하고, 있는 것은 **온 칸만**(doe · pitch · roll · provenance ·
    config_generation · superseded_by · health · extraction) 맞춘다.

    상태 · 리포트는 건드리지 않고 목록에서 빼지도 않는다. 같은 캠페인의 목록 올리기는 캠페인 행 잠금으로 줄 세운다.
    다 맞춘 뒤 `superseded_by` 가 같은 캠페인의 다른 런을 가리키는지 · 고리가 없는지 보고, 깨졌으면 되감고 `BadManifest`.
    """
    await db.execute(select(Campaign.id).where(Campaign.id == campaign_id).with_for_update())
    have = {r.run_key: r for r in (await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign_id)
    )).scalars()}
    added = updated = 0
    for it in items:
        row = have.get(it["run_key"])
        if row is None:
            db.add(CampaignRun(campaign_id=campaign_id, **it))
            added += 1
            continue
        changed = {k: v for k, v in it.items() if k != "run_key" and getattr(row, k) != v}
        for k, v in changed.items():
            setattr(row, k, v)
        updated += bool(changed)
    keys = set(have) | {it["run_key"] for it in items}
    sup = {k: r.superseded_by for k, r in have.items()}
    sup.update({it["run_key"]: it["superseded_by"] for it in items if "superseded_by" in it})
    why = _superseded_problems(sup, keys)
    if why:
        await db.rollback()
        raise BadManifest(why)
    await db.commit()
    return {"added": added, "updated": updated, "unchanged": len(items) - added - updated,
            "listed": len(have) + added}


async def find_run_id(db: AsyncSession, campaign_id: str, run_key: str) -> int | None:
    return (await db.execute(
        select(CampaignRun.id).where(CampaignRun.campaign_id == campaign_id, CampaignRun.run_key == run_key)
    )).scalar_one_or_none()


async def held(db: AsyncSession, run_id: int) -> tuple[str, str | None, str] | None:
    """그 런이 지금 가진 리포트 — (report_id, content_sha256, session_id). 없으면 None. 늘 DB 에서 새로 읽는다."""
    row = (await db.execute(
        select(CampaignRun.report_id, CampaignRun.content_sha256, ImpactReport.session_id)
        .join(ImpactReport, ImpactReport.id == CampaignRun.report_id)
        .where(CampaignRun.id == run_id)
    )).first()
    return None if row is None else (row.report_id, row.content_sha256, row.session_id)


async def lock_free_run(db: AsyncSession, run_id: int) -> None:
    """리포트를 쓰기 직전에 런 행을 잠근다(커밋까지 쥔다). 이미 리포트를 가졌거나 행이 없으면 RunTaken."""
    row = (await db.execute(
        select(CampaignRun.report_id).where(CampaignRun.id == run_id).with_for_update()
    )).first()
    if row is None or row.report_id is not None:
        raise RunTaken()


async def bind_run(db: AsyncSession, run_id: int, *, report_id: str, sha256: str) -> None:
    """방금 쓴 리포트를 런에 묶는다 — 커밋은 부르는 쪽(리포트와 한 트랜잭션)."""
    await db.flush()  # 리포트 행이 먼저 있어야 FK 가 선다
    await db.execute(update(CampaignRun).where(CampaignRun.id == run_id).values(
        report_id=report_id, content_sha256=sha256, ingest_state="received", reject_reason=None,
        ingested_at=func.now(),
    ))


async def mark(db: AsyncSession, run_id: int, state: str, reason: str | None = None) -> None:
    """마지막 시도의 결과를 적는다(skipped · rejected) — 가진 리포트 칸은 그대로 둔다."""
    await db.execute(update(CampaignRun).where(CampaignRun.id == run_id).values(
        ingest_state=state, reject_reason=(reason or "")[:_REASON_MAX] or None,
    ))
    await db.commit()


async def ingest_status(db: AsyncSession, campaign_id: str, *, state: str | None, limit: int, offset: int) -> dict:
    """목록 수 · 상태별 수 · 런마다 상태. `listed = pending + received + skipped + rejected` 가 늘 맞는다."""
    sub = select(_EFFECTIVE.label("state"), CampaignRun.report_id).where(
        CampaignRun.campaign_id == campaign_id).subquery()
    counts = dict.fromkeys(("listed", *STATES, "with_report"), 0)
    for st, n, n_rep in await db.execute(
        select(sub.c.state, func.count(), func.count(sub.c.report_id)).group_by(sub.c.state)
    ):
        counts[st] = n
        counts["listed"] += n
        counts["with_report"] += n_rep
    q = select(
        CampaignRun.run_key, CampaignRun.doe, CampaignRun.pitch, CampaignRun.roll, _EFFECTIVE.label("state"),
        CampaignRun.report_id, CampaignRun.content_sha256, CampaignRun.reject_reason, CampaignRun.ingested_at,
    ).where(CampaignRun.campaign_id == campaign_id)
    if state:
        q = q.where(_EFFECTIVE == state)
    runs = [{
        "run_key": r.run_key, "doe": r.doe, "pitch": r.pitch, "roll": r.roll, "ingest_state": r.state,
        "report_id": r.report_id,
        # 지문 · 받은 시각은 가진 리포트의 것이다 — 리포트가 지워졌으면 같이 비운다
        "content_sha256": r.content_sha256 if r.report_id else None,
        "ingested_at": r.ingested_at if r.report_id else None,
        "reject_reason": r.reject_reason if r.state == "rejected" else None,
    } for r in await db.execute(q.order_by(CampaignRun.id).limit(limit).offset(offset))]
    return {"counts": counts, "matched": counts[state] if state else counts["listed"], "runs": runs}


def _superseded_problems(sup: dict[str, str | None], keys: set[str]) -> str | None:
    """`superseded_by` 대조 — 목록에 없는 열쇠 · 자기 자신 · 고리. 문제가 없으면 None."""
    missing = sorted(k for k, v in sup.items() if v and v not in keys)
    if missing:
        return ("superseded_by 가 이 캠페인의 런 목록에 없는 run_key 를 가리킵니다 — "
                + ", ".join(f"{k} → {sup[k]}" for k in missing[:10]))
    selfish = sorted(k for k, v in sup.items() if v and v == k)
    if selfish:
        return "superseded_by 가 자기 자신을 가리킵니다 — " + ", ".join(selfish[:10])
    for start in sup:
        seen, cur = {start}, sup.get(start)
        while cur:
            if cur in seen:
                return f"superseded_by 가 고리를 이룹니다 — {start} 에서 시작해 {cur} 로 돌아옵니다"
            seen.add(cur)
            cur = sup.get(cur)
    return None


async def set_thresholds(db: AsyncSession, campaign: Campaign, changed: dict | None) -> dict:
    """캠페인의 건강 문턱 — 기본값에서 바꾼 열쇠만 둔다(빈 것 · 기본값과 같은 값은 지운다). 묶음을 돌려준다."""
    vals = H.effective(changed)
    keep = {k: v for k, v in vals.items() if v != H.DEFAULTS[k]}
    campaign.health_thresholds = keep or None
    await db.commit()
    return H.bundle(campaign.health_thresholds)


def _judged(r, thr: dict, tref: str) -> dict:
    """런 한 행 → 판정 · 제외 까닭을 붙인 응답 행."""
    verdict = H.judge(r.health, thr, has_report=r.report_id is not None)
    excl = H.excluded_by(verdict, superseded=bool(r.superseded_by), has_provenance=bool(r.provenance))
    health = dict(r.health) if r.health else None
    if health is not None:
        health["thresholds_ref"] = tref
    return {
        "run_key": r.run_key, "doe": r.doe, "pitch": r.pitch, "roll": r.roll, "report_id": r.report_id,
        "config_generation": r.config_generation, "superseded_by": r.superseded_by,
        "validity": verdict, "health": health, "excluded_by": excl,
    }


def _header(rows: list[dict]) -> dict:
    """머리 줄 — 유효 n / 전체 N · 제외 까닭별 건수(런 하나가 까닭 여럿이면 여럿에 센다)."""
    total = len(rows)
    included = sum(1 for r in rows if not r["excluded_by"])
    by: dict[str, int] = {}
    for r in rows:
        for why in r["excluded_by"]:
            by[why] = by.get(why, 0) + 1
    status = {st: sum(1 for r in rows if r["validity"]["status"] == st) for st in ("valid", "warn", "invalid")}
    line = f"유효 {included} / 전체 {total}"
    if by:
        line += " · 제외 " + " · ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))
    return {"total": total, "included": included, "excluded": total - included, "excluded_by": by, **status,
            "line": line}


async def health_table(db: AsyncSession, campaign: Campaign, *, include_invalid: bool, limit: int, offset: int) -> dict:
    """캠페인의 런마다 건강 수치 · 판정 · 제외 까닭과 머리 줄. 기본(`include_invalid=False`)은 넣는 런만 싣는다."""
    tb = H.bundle(campaign.health_thresholds)
    rows = [_judged(r, tb["values"], tb["ref"]) for r in (await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign.id).order_by(CampaignRun.id)
    )).scalars()]
    header = _header(rows)
    shown = rows if include_invalid else [r for r in rows if not r["excluded_by"]]
    return {"header": header, "thresholds": tb, "include_invalid": include_invalid, "matched": len(shown),
            "runs": shown[offset:offset + limit]}


async def provenance_view(db: AsyncSession, campaign: Campaign, *, config_generation: str | None,
                          limit: int, offset: int) -> dict:
    """설정 세대 분포 · `mixed_config`(이름표가 붙은 세대가 둘 이상) · 출처가 빈 런 수 · 대체된 런 수 · 런마다 출처."""
    runs = list((await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign.id).order_by(CampaignRun.id)
    )).scalars())
    gens: dict[str | None, int] = {}
    for r in runs:
        gens[r.config_generation] = gens.get(r.config_generation, 0) + 1
    counts = {"listed": len(runs), "with_provenance": sum(1 for r in runs if r.provenance),
              "provenance_missing": sum(1 for r in runs if not r.provenance),
              "superseded": sum(1 for r in runs if r.superseded_by)}
    picked = [r for r in runs if config_generation is None or r.config_generation == config_generation]
    return {
        "generations": [{"config_generation": g, "runs": n}
                        for g, n in sorted(gens.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))],
        "mixed_config": sum(1 for g in gens if g is not None) > 1,
        "counts": counts, "matched": len(picked),
        "runs": [{"run_key": r.run_key, "doe": r.doe, "report_id": r.report_id, "config_generation": r.config_generation,
                  "superseded_by": r.superseded_by, "provenance": r.provenance}
                 for r in picked[offset:offset + limit]],
    }


async def run_of_report(db: AsyncSession, report_id: str) -> tuple[CampaignRun, Campaign] | None:
    """그 리포트를 가진 캠페인 런과 캠페인 — 없으면 None(캠페인 밖 리포트)."""
    row = (await db.execute(
        select(CampaignRun, Campaign).join(Campaign, Campaign.id == CampaignRun.campaign_id)
        .where(CampaignRun.report_id == report_id).order_by(CampaignRun.id).limit(1)
    )).first()
    return None if row is None else (row[0], row[1])


def judged_run(run: CampaignRun, campaign: Campaign) -> dict:
    """리포트 건강 응답 한 덩이 — 판정 · 제외 까닭 · 문턱 묶음."""
    tb = H.bundle(campaign.health_thresholds)
    return {**_judged(run, tb["values"], tb["ref"]), "thresholds": tb}


async def set_required(db: AsyncSession, campaign: Campaign, items: list[dict]) -> list[dict] | None:
    """캠페인의 필수 추출 목록을 통째로 바꾼다 — 빈 목록이면 지운다(null). 저장한 목록을 돌려준다."""
    campaign.required_extractions = items or None
    await db.commit()
    return campaign.required_extractions


def cleared_run(run: CampaignRun, campaign: Campaign) -> dict:
    """런 한 행 → 추출 · 피크 표지 · 삭제 허가를 붙인 응답 행."""
    return {
        "run_key": run.run_key, "doe": run.doe, "report_id": run.report_id,
        "extraction": run.extraction, "peak_provenance": X.peak_provenance(run.extraction),
        "clearance": X.clearance(has_report=run.report_id is not None, extraction=run.extraction,
                                 required=campaign.required_extractions),
    }


async def clearance_table(db: AsyncSession, campaign: Campaign, *, status: str | None, limit: int, offset: int) -> dict:
    """캠페인의 런마다 삭제 허가 — 머리 줄(허가 · 보류 · 이미 지움 수와 까닭별 수) · 필수 목록 · 런마다 허가와 빠진 항목."""
    rows = [cleared_run(r, campaign) for r in (await db.execute(
        select(CampaignRun).where(CampaignRun.campaign_id == campaign.id).order_by(CampaignRun.id)
    )).scalars()]
    shown = rows if status is None else [r for r in rows if r["clearance"]["status"] == status]
    return {"header": X.header(rows), "required_extractions": campaign.required_extractions, "matched": len(shown),
            "runs": shown[offset:offset + limit]}


async def peak_provenance_of(db: AsyncSession, report_id: str) -> dict:
    """리포트의 피크 출처 표지 — 그 리포트를 가진 캠페인 런의 추출에서. 캠페인 밖이면 모른다(`known: false`)."""
    ext = (await db.execute(
        select(CampaignRun.extraction).where(CampaignRun.report_id == report_id).order_by(CampaignRun.id).limit(1)
    )).scalar_one_or_none()
    return X.peak_provenance(ext)
