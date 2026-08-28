# ReportArchive pull 연동 — 소유 리포트 목록(증분/커서)과 내보내기 로드.
"""Service layer for the ReportArchive pull integration.

목록은 인증된 PAT 소유자의 리포트만 준다(기존 소유권 모델). ULID id 는 생성시각
순서라 커서(after)로 쓰기 좋다 — id asc 정렬 + id > after 로 페이지를 나눈다.
``since`` 는 analyzed_at(created_at) 워터마크로 증분 필터.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImpactCase, ImpactReport


async def list_runs(
    db: AsyncSession,
    user_id: int,
    *,
    since: datetime | None = None,
    after: str | None = None,
    limit: int = 100,
) -> list[ImpactReport]:
    """소유 리포트를 id(=ULID, 시각순) 오름차순으로. since=증분, after=커서."""
    q = select(ImpactReport).where(ImpactReport.user_id == user_id)
    if since is not None:
        q = q.where(ImpactReport.created_at >= since)
    if after:
        q = q.where(ImpactReport.id > after)
    q = q.order_by(ImpactReport.id.asc()).limit(limit)
    return list((await db.execute(q)).scalars())


async def get_owned_report(
    db: AsyncSession, user_id: int, run_key: str
) -> Optional[ImpactReport]:
    """run_key(=report.id) 로 소유 리포트 조회."""
    row = await db.get(ImpactReport, run_key)
    if row is None or row.user_id != user_id:
        return None
    return row


async def load_cases(db: AsyncSession, report_id: str) -> list[ImpactCase]:
    return list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report_id).order_by(ImpactCase.id.asc())
    )).scalars())
