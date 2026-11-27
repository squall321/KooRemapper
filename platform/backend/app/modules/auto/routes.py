# 자동 파이프라인 REST — MCP auto_* 가 부른다(계약 v1.1 · 실패는 {error, detail} 을 data 에 싣는다)
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
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
