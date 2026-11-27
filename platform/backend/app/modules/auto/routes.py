# 자동 파이프라인 REST — MCP auto_* 가 부른다(계약 v1.1 · 실패는 {error, detail} 을 data 에 싣는다)
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.modules.auto import drop
from app.modules.auto import services as svc
from app.shared.auth import get_current_user
from app.shared.responses import fail, ok

router = APIRouter(prefix="/auto", tags=["auto"])


def _fail(e: svc.AutoError):
    return fail(f"{e.error}: {e.detail}", status_code=400, data={"error": e.error, "detail": e.detail, **e.extra})


@router.get("/changes")
async def auto_changes(since: str | None = Query(None, max_length=512),
                       limit: int = Query(200, ge=1, le=svc.CHANGES_MAX),
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """바뀐 세션(덱) — 계약 §1. 쪽 커서로 끝까지(`complete` · `next_since`)."""
    try:
        return ok(await svc.changes(db, user, since=since, limit=limit))
    except svc.AutoError as e:
        return _fail(e)


# ── 전각도 낙하 해석(계약 §2) ─────────────────────────────────────────────

class CheckIn(BaseModel):
    subject: dict = Field(default_factory=dict)
    profile: str = Field(min_length=1, max_length=32)
    upstream: dict | None = None            # 앞 단계 결과 봉투 — 이 해석은 쓰지 않는다


class SubmitIn(CheckIn):
    idem_key: str = Field(min_length=64, max_length=64)


async def _call(coro):
    try:
        return ok(await coro)
    except svc.AutoError as e:
        return _fail(e)


@router.get("/profiles")
async def auto_profiles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _call(drop.profiles(db))


@router.post("/check")
async def auto_check(body: CheckIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """읽기만 한다(계약 §4-2)."""
    return await _call(drop.check(db, user, body.subject, body.profile))


@router.post("/submit")
async def auto_submit(body: SubmitIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """같은 idem_key 면 같은 run_ref(created false) — 계약 §2 · §4-1."""
    return await _call(drop.submit(db, user, body.subject, body.profile, body.idem_key))


@router.get("/runs/{run_ref}/status")
async def auto_status(run_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _call(drop.status(db, user, run_ref))


@router.get("/runs/{run_ref}/result")
async def auto_result(run_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _call(drop.result(db, user, run_ref))


@router.post("/runs/{run_ref}/cancel")
async def auto_cancel(run_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _call(drop.cancel(db, user, run_ref))

