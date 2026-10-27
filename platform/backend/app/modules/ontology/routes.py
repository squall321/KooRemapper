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
    q: str | None = Query(default=None, description="과제코드(properties.task_code)·과제명(key)·이름 일부"),
    project: str | None = Query(default=None, description="이 프로젝트의 과제만(properties.project) — KR-16"),
    include_deleted: bool = Query(default=False, description="허브에서 사라진 것도"),
    limit: int = Query(default=100, ge=1, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """허브에서 받은 과제 목록. **비어 있는 것과 수신이 꺼진 것을 갈라 말한다** —
    빈 목록만 주면 「과제가 없다」 로 읽히는데, 실제로는 물어보지도 못한 것이다.

    검색은 key(과제명)·properties.task_code(과제코드)·label 을 본다. 결과는 **앞부분·낱말경계
    일치를 위로** 올리고(KR-16 — 짧은 꼴이 다른 프로젝트 과제를 섞던 것), 항목마다 `matched_by` 를 단다.
    `project` 로 그 프로젝트의 과제만 좁힐 수 있다(properties.project — 허브 필드명 기준)."""
    stmt = select(OntoObject).where(OntoObject.type_slug == svc.TYPE_TASK)
    if not include_deleted:
        stmt = stmt.where(OntoObject.deleted.is_(False))
    if project:
        stmt = stmt.where(OntoObject.properties["project"].astext == project)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(OntoObject.key.ilike(like) | OntoObject.label.ilike(like)
                          | OntoObject.properties["task_code"].astext.ilike(like))
    # q 가 있으면 순위를 매겨야 하므로 limit 전에 넉넉히 받아(상한 있음) Python 에서 정렬·절단한다.
    fetch = min(1000, max(limit, limit * 5)) if q else limit
    rows = (await db.execute(stmt.order_by(OntoObject.key).limit(fetch))).scalars().all()
    state = (await db.execute(select(OntoSyncState).where(
        OntoSyncState.type_slug == svc.TYPE_TASK))).scalar_one_or_none()
    from app.worker import plm_sync

    def _fields(r):
        return (r.key or "", str((r.properties or {}).get("task_code") or ""), r.label or "")

    def _matched_by(r) -> str | None:
        if not q:
            return None
        ql = q.lower()
        name, code, label = (s.lower() for s in _fields(r))
        if ql in name:
            return "task_name"
        if code and ql in code:
            return "task_code"
        if ql in label:
            return "label"
        return None

    def _rank(r) -> int:
        # 0 앞부분 일치(key·task_code) · 1 낱말 경계 · 2 그 밖(부분 문자열). 짧은 꼴의 섞임을 눌러 준다(KR-16).
        if not q:
            return 0
        ql = q.lower()
        name, code, label = (s.lower() for s in _fields(r))
        if name.startswith(ql) or (code and code.startswith(ql)):
            return 0
        import re as _re
        if any(_re.search(r"(^|[\s\-_./])" + _re.escape(ql), s) for s in (name, code, label) if s):
            return 1
        return 2

    if q:
        rows = sorted(rows, key=lambda r: (_rank(r), r.key or ""))[:limit]

    return ok({
        "items": [{"key": r.key, "label": r.label, "status": r.status,
                   "deleted": r.deleted, "properties": r.properties or {},
                   "matched_by": _matched_by(r),
                   "updated_at": r.updated_at} for r in rows],
        "sync_enabled": plm_sync.enabled(),
        "last_status": state.last_status if state else None,
        "last_error": state.last_error if state else None,
        "last_run_at": state.last_run_at if state else None,
        "reason": (None if rows else
                   ("허브 수신이 꺼져 있다 — 아직 한 번도 받지 않았다"
                    if not plm_sync.enabled() else "받았지만 과제가 없다")),
    })


@router.get("/ontology/tasks/{task_key:path}/compare")
async def compare_revisions(
    task_key: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """한 과제의 개정을 **나란히** — 판마다 최악값·심각도·케이스 수와 앞 판 대비 변화.

    숫자는 리포트에 **이미 승격된 칸**을 그대로 쓴다(다시 계산하지 않는다 — 같은 값을 두
    곳에서 계산하면 반드시 갈린다). 안 잰 것은 **`null` 이고 0 이 아니다.**
    """
    return ok(await svc.compare(db, task_key))


@router.get("/ontology/tasks/{task_key:path}/revisions")
async def task_revisions(
    task_key: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """한 과제의 개정 줄 — `rev_seq` 순, 각 판에 달린 리포트와 앞 판.

    ★모르는 과제와 '개정 없음' 을 가른다(KR-07) — `task_found:false` · reason `unknown_task` 면
    정본에 그 과제가 없다는 뜻이다(개정이 0 인 것과 다르다)."""
    if not await svc.task_exists(db, task_key):
        return ok({"task": task_key, "task_found": False, "reason": "unknown_task", "revisions": [],
                   "hint": "list_tasks 로 정본 과제명을 먼저 찾으라 — 과제코드로도 검색된다(matched_by)"})
    return ok({"task": task_key, "task_found": True, "revisions": await svc.history(db, task_key)})


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


@router.delete("/reports/{report_id}/revision")
async def unlink_report_revision(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """이어 둔 개정을 **끊는다**(개정 객체는 남는다).

    확정하는 기능에 되돌리는 길이 없으면 반쪽이다. 객체를 지우지 않는 이유는 그 판에 다른
    리포트가 달려 있거나 `supersedes` 줄의 가운데일 수 있어서다 — 지우면 되돌릴 수 없다.
    """
    rep = await rsvc.get_owned_report(db, user.id, report_id)
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    got = await svc.unlink_revision(db, rep)
    if not got.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{got.get('error')}: {got.get('detail') or ''}")
    await db.commit()
    return ok(got, message="개정 연결을 끊었습니다.")


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


@admin.delete("/ontology/aliases")
async def drop_alias(
    alias: str = Query(min_length=1, max_length=500, description="뗄 자유 문자열"),
    db: AsyncSession = Depends(get_db),
):
    """붙여 둔 별칭을 뗀다.

    ★`POST` 가 "먼저 떼야 한다" 고 말하는데 뗄 길이 없으면 **불가능한 것을 지시하는 오류
    메시지**가 된다 — 사람이 그 말을 믿고 찾아다닌다. 그래서 이 길이 있다.
    이미 이어 둔 개정은 **건드리지 않는다**(별칭은 다음부터의 규칙이고, 과거에 붙인 것은
    사람이 확정한 사실이다).
    """
    got = await svc.remove_alias(db, alias=alias)
    if not got.get("ok"):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"{got.get('error')}: {got.get('detail') or ''}")
    await db.commit()
    return ok(got, message="별칭을 뗐습니다.")


@router.get("/ontology/sync")
async def sync_state(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 읽기는 로그인한 일반 사용자에게 연다(KR-17, 2026-10-27) — 챗이 '받기가 됐나' 에 답할 수 있게.
    # 수신 자체(받기·과거 붙이기·별칭)는 여전히 관리자만이다(admin 라우터).
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
