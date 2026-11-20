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

STATES = ("pending", "received", "skipped", "rejected")
_REASON_MAX = 2000

# 읽을 때의 상태 — 리포트를 잃은 received · skipped 는 pending 이다(다시 받을 수 있다).
_EFFECTIVE = case(
    (and_(CampaignRun.report_id.is_(None), CampaignRun.ingest_state.in_(("received", "skipped"))), "pending"),
    else_=CampaignRun.ingest_state,
)


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
    """런 목록을 올린다 — 새 `run_key` 는 pending 으로 더하고, 있는 것은 **온 칸만**(doe · pitch · roll) 맞춘다.

    상태 · 리포트는 건드리지 않고 목록에서 빼지도 않는다. 같은 캠페인의 목록 올리기는 캠페인 행 잠금으로 줄 세운다.
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
