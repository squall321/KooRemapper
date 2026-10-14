# 온톨로지 API — 과제 거울·개발 개정·과거 붙이기. **받은 것은 읽기 전용**이다
"""과제의 정본은 허브다(계획서 §1-6). 그래서 과제를 **만들거나 고치는 길을 열지 않는다** —
여기 있는 쓰기는 모두 **우리 것**(개발 개정 · 별칭 · 수신 실행)에만 닿는다.

권한 —
  읽기            로그인한 누구나(과제·개정은 전사 공용 축이다)
  리포트의 개정   그 리포트 **소유자**(리포트를 바꾸는 일이다 — `_require_owned_report` 와 같은 자세)
  과거 붙이기·별칭·수신  **시스템 관리자**(전사 데이터를 움직인다)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OntoAlias, OntoObject, OntoSyncState, User
from app.modules.ontology import services as svc
from app.modules.reports import services as rsvc
from app.shared.auth import get_current_user, require_system_admin
from app.shared.features import ontology_state
from app.shared.responses import ok

def require_ontology() -> dict:
    """기능이 꺼져 있으면 **거절한다.** 화면에서만 숨기고 API 가 계속 답하면 그것은 꺼진 것이
    아니라 **숨긴 것**이다.

    ★404 가 아니라 **409 + 사유**다. 404 는 "그런 길이 없다"로 읽히고, 그러면 꺼진 것인지
    주소를 잘못 쳤는지 부르는 쪽이 못 가린다. 꺼짐은 **왜 꺼졌는지 말한다.**
    """
    st = ontology_state()
    if not st["enabled"]:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"과제·개정 기능이 꺼져 있습니다 — {st['reason']}")
    return st


router = APIRouter(tags=["ontology"], dependencies=[Depends(require_ontology)])


# ── 과제 거울 ──────────────────────────────────────────────────────────────

@router.get("/ontology/tasks")
async def list_tasks(
    q: str | None = Query(default=None, description="과제코드·과제명 일부"),
    include_deleted: bool = Query(default=False, description="허브에서 사라진 것도"),
    limit: int = Query(default=100, ge=1, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """허브에서 받은 과제 목록. **비어 있는 것과 수신이 꺼진 것을 갈라 말한다** —
    빈 목록만 주면 「과제가 없다」 로 읽히는데, 실제로는 물어보지도 못한 것이다."""
    stmt = select(OntoObject).where(OntoObject.type_slug == svc.TYPE_TASK)
    if not include_deleted:
        stmt = stmt.where(OntoObject.deleted.is_(False))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(OntoObject.key.ilike(like) | OntoObject.label.ilike(like))
    rows = (await db.execute(stmt.order_by(OntoObject.key).limit(limit))).scalars().all()
    state = (await db.execute(select(OntoSyncState).where(
        OntoSyncState.type_slug == svc.TYPE_TASK))).scalar_one_or_none()
    from app.worker import plm_sync
    return ok({
        "items": [{"key": r.key, "label": r.label, "status": r.status,
                   "deleted": r.deleted, "properties": r.properties or {},
                   "updated_at": r.updated_at} for r in rows],
        "sync_enabled": plm_sync.enabled(),
        "last_status": state.last_status if state else None,
        "last_error": state.last_error if state else None,
        "last_run_at": state.last_run_at if state else None,
        "reason": (None if rows else
                   ("허브 수신이 꺼져 있다 — 아직 한 번도 받지 않았다"
                    if not plm_sync.enabled() else "받았지만 과제가 없다")),
    })


@router.get("/ontology/tasks/{task_key}/revisions")
async def task_revisions(
    task_key: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """한 과제의 개정 줄 — `rev_seq` 순, 각 판에 달린 리포트와 앞 판."""
    return ok({"task": task_key, "revisions": await svc.history(db, task_key)})


# ── 리포트의 개정 ──────────────────────────────────────────────────────────

class RevisionSet(BaseModel):
    task_key: str = Field(min_length=1, max_length=300)
    code: str = Field(min_length=1, max_length=8)      # pre|dv1..dvr|pv..|pra|mp
    model_key: str = Field(default="", max_length=300)
    supersedes: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)


@router.get("/reports/{report_id}/revision")
async def get_report_revision(
    report_id: str,
    task_key: str | None = Query(default=None, description="후보를 물을 때 과제를 좁힌다"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """이어진 개정 · **어긋남** · 후보를 함께 준다.

    어긋남을 함께 주는 것이 요점이다 — 화면이 그것을 보여 줘야 사람이 고를 수 있다.
    서버가 조용히 맞추면 사람이 넣은 값과 저장된 값이 달라지고 그 차이는 아무 데도 안 뜬다.
    """
    rep = await rsvc.get_owned_report(db, user.id, report_id)
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    free = svc.report_free_task(rep)
    resolved, how = await svc.resolve_task(db, free) if free else ("", "")
    return ok({
        "report_id": rep.id,
        "eng_meta": rep.eng_meta or {},
        "free_task": free,
        "resolved_task": resolved or None,
        "resolved_how": how or None,
        "mismatch": await svc.mismatch(db, rep),
        "candidates": await svc.candidates(db, rep, task_key=task_key or resolved or ""),
        "task_candidates": ([] if resolved or not free
                            else await svc.task_candidates(db, free)),
    })


@router.put("/reports/{report_id}/revision")
async def set_report_revision(
    report_id: str,
    body: RevisionSet,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사람이 확정한다. **이 확정은 재인제스트에 지워지지 않는다**(`rev_source=manual`)."""
    rep = await rsvc.get_owned_report(db, user.id, report_id)
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    got = await svc.set_revision(db, rep, task_key=body.task_key, code=body.code,
                                 model_key=body.model_key, supersedes=body.supersedes,
                                 decided_by=user.email, note=body.note, source="manual")
    if not got.get("ok"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"{got.get('error')}: {got.get('detail') or ''}")
    await db.commit()
    return ok(got, message="개정을 확정했습니다.")


# ── 과거 붙이기 · 별칭 · 수신 (관리자) ────────────────────────────────────

admin = APIRouter(tags=["ontology"],
                  dependencies=[Depends(require_ontology), Depends(require_system_admin)])


@admin.get("/ontology/task-links")
async def plan_links(
    limit: int | None = Query(default=None, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """★**계획이다 — 아무것도 쓰지 않는다.** 붙는 것·후보·못 붙인 것을 갈라서 준다."""
    return ok(await svc.plan_task_links(db, limit=limit))


class ApplyLinks(BaseModel):
    # 비우면 **계획의 「붙는 것」 전부**. 고른 것만 적용하려면 자유 문자열을 적는다.
    only: list[str] | None = None


@admin.post("/ontology/task-links/apply")
async def apply_links(body: ApplyLinks, actor: User = Depends(require_system_admin),
                      db: AsyncSession = Depends(get_db)):
    done = await svc.apply_task_links(db, only=body.only, decided_by=actor.email)
    await db.commit()
    return ok(done, message="붙는 것만 이었습니다.")


class AliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=500)
    key: str = Field(min_length=1, max_length=300)
    note: str = Field(default="", max_length=2000)


@admin.post("/ontology/aliases")
async def add_alias(body: AliasIn, actor: User = Depends(require_system_admin),
                    db: AsyncSession = Depends(get_db)):
    """사람이 "이 문자열은 저 과제다" 를 적는다. 한 문자열은 **한 과제만** 가리킨다."""
    got = await svc.confirm_alias(db, alias=body.alias, key=body.key,
                                  by=actor.email, note=body.note)
    if not got.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{got.get('error')}: {got.get('detail') or ''}")
    await db.commit()
    return ok(got, message="별칭을 적었습니다.")


@admin.get("/ontology/aliases")
async def list_aliases(limit: int = Query(default=200, ge=1, le=2000),
                       db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(OntoAlias).order_by(OntoAlias.alias)
                             .limit(limit))).scalars().all()
    return ok([{"alias": a.alias, "key": a.key, "type_slug": a.type_slug,
                "confirmed_by": a.confirmed_by, "confirmed_at": a.confirmed_at,
                "note": a.note} for a in rows])


@admin.get("/ontology/sync")
async def sync_state(db: AsyncSession = Depends(get_db)):
    from app.worker import plm_sync
    rows = (await db.execute(select(OntoSyncState)
                             .order_by(OntoSyncState.type_slug))).scalars().all()
    counts = dict((await db.execute(
        select(OntoObject.type_slug, func.count()).group_by(OntoObject.type_slug))).all())
    return ok({
        "enabled": plm_sync.enabled(),
        "types": [{"type_slug": r.type_slug, "objects_as_of": r.objects_as_of,
                   "relations_as_of": r.relations_as_of,
                   "catalog_revision": r.catalog_revision, "last_run_at": r.last_run_at,
                   "last_status": r.last_status, "last_error": r.last_error,
                   "objects": counts.get(r.type_slug, 0)} for r in rows],
        "objects_by_type": counts,
    })


@admin.post("/ontology/sync")
async def run_sync(full: bool = Query(default=False, description="처음부터 다시 받는다")):
    """지금 한 번 받는다. 꺼져 있으면 **조용히 성공하지 않고** 꺼졌다고 말한다."""
    from app.worker import plm_sync
    got = await plm_sync.sync_once(full=full)
    if not got.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{got.get('error')}: {got.get('detail') or ''}")
    return ok(got, message="받았습니다.")
