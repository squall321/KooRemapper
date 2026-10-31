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

from app.config import settings
from app.database import get_db
from app.models import (OntoAlias, OntoCatalog, OntoObject, OntoPreviousKey, OntoRelation,
                        OntoRelationType, OntoSyncRun, OntoSyncState, OntoType, User)
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
    q: str | None = Query(default=None, description="과제코드(properties.task_code)·과제명(key)·별칭·이름 일부"),
    project: str | None = Query(default=None, description="이 프로젝트의 과제만(properties.project) — KR-16"),
    include_deleted: bool = Query(default=False, description="허브에서 사라진 것도"),
    limit: int = Query(default=100, ge=1, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """허브에서 받은 과제 목록. **비어 있는 것과 수신이 꺼진 것을 갈라 말한다** —
    빈 목록만 주면 「과제가 없다」 로 읽히는데, 실제로는 물어보지도 못한 것이다.

    검색은 key(과제명)·properties.task_code(과제코드)·별칭(허브 `properties.aliases` · 우리 별칭 표)·label 을 본다.
    **순위를 매긴 뒤 자른다**(KR-16 다시) — 앞부분 · 낱말 경계 · 부분 순이고, 항목마다 `matched_by` · `match_kind` 를 단다.
    `project` 로 그 프로젝트의 과제만 좁힐 수 있다(properties.project — 허브 필드명 기준)."""
    got = await svc.search_tasks(db, q or "", project=project or "", include_deleted=include_deleted, limit=limit)
    rows = got["items"]
    state = (await db.execute(select(OntoSyncState).where(
        OntoSyncState.type_slug == svc.TYPE_TASK))).scalar_one_or_none()
    from app.worker import plm_sync
    return ok({
        **got,
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
    정본에 그 과제가 없다는 뜻이다(개정이 0 인 것과 다르다). 단 개정이 있으면 그 자체로 '아는' 과제다
    (개정은 거울에 없는 자유 문자열 key 에도 붙는다)."""
    revs = await svc.history(db, task_key)
    if revs:
        return ok({"task": task_key, "task_found": True, "revisions": revs})
    if await svc.task_exists(db, task_key):
        return ok({"task": task_key, "task_found": True, "revisions": []})
    return ok({"task": task_key, "task_found": False, "reason": "unknown_task", "revisions": [],
               "hint": "list_tasks 로 정본 과제명을 먼저 찾으라 — 과제코드로도 검색된다(matched_by)"})


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
    linked = await svc.linked_revision(db, rep)
    # 이어진 개정의 과제(없으면 풀린 과제)가 허브에서 어떤 처지인가 — 합쳐졌으면 화면이 「A 는 B 로 합쳐짐」 을
    # 띄우고 관리자가 옮긴다(사용자 결정 10-30). 사라짐 · 그만 씀도 여기서 말한다.
    about = (linked or {}).get("task") or resolved
    return ok({
        "report_id": rep.id,
        "eng_meta": rep.eng_meta or {},
        "free_task": free,
        "resolved_task": resolved or None,
        "resolved_how": how or None,
        "linked": linked,
        "task_state": await svc.task_state(db, about) if about else None,
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


def _run_out(r: OntoSyncRun, *, who: bool) -> dict:
    out = {"id": r.id, "started_at": r.started_at, "finished_at": r.finished_at, "mode": r.mode,
           "allow_shrink": r.allow_shrink, "trigger": r.trigger, "result": r.result, "revision": r.revision,
           "counts": r.counts or {}, "problems": r.problems or [], "notes": r.notes or [], "error": r.error}
    if who:
        out["requested_by"] = r.requested_by     # 누른 사람은 관리 화면에만 — 읽기 창구는 누구나 본다
    return out


async def _object_states(db) -> dict[str, dict[str, int]]:
    """타입별 건수 — 활성 · 그만 씀 · 사용 안 함(사라짐 · 합쳐짐) · 그중 안 보이게 됨."""
    # 리포트에서 나온 행(cae_* — report_id)은 리포트 가시성을 따른다 — 전사 공개인 이 창들에는 세지도 내지도 않는다
    rows = (await db.execute(select(OntoObject.type_slug, OntoObject.deleted, OntoObject.hidden,
                                    OntoObject.status, func.count())
                             .where(OntoObject.report_id.is_(None))
                             .group_by(OntoObject.type_slug, OntoObject.deleted, OntoObject.hidden,
                                       OntoObject.status))).all()
    out: dict[str, dict[str, int]] = {}
    for slug, deleted, hidden, st, n in rows:
        c = out.setdefault(slug, {"total": 0, "active": 0, "deprecated": 0, "inactive": 0, "hidden": 0})
        c["total"] += n
        if deleted:
            c["inactive"] += n
            c["hidden"] += n if hidden else 0
        elif st == "deprecated":
            c["deprecated"] += n
        else:
            c["active"] += n
    return out


@router.get("/ontology/sync")
async def sync_state(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """받기 상태 — 타입별 시계 · 마지막 실행(결과 셋과 「확인 필요」 사유) · 정의 판 · 타입별 건수.

    읽기는 로그인한 일반 사용자에게 연다(KR-17, 2026-10-27) — 챗이 '받기가 됐나' 에 답할 수 있게.
    수신 자체(받기 · 처음부터 · 강제 정리 · 과거 붙이기 · 별칭 · 합친 과제 옮기기)는 여전히 관리자만이다(admin 라우터).
    """
    from app.worker import plm_sync
    rows = (await db.execute(select(OntoSyncState)
                             .order_by(OntoSyncState.type_slug))).scalars().all()
    states = await _object_states(db)
    counts = {slug: c["total"] for slug, c in states.items()}
    last = (await db.execute(select(OntoSyncRun).order_by(OntoSyncRun.id.desc()).limit(1))).scalar_one_or_none()
    cat = (await db.execute(select(OntoCatalog).order_by(OntoCatalog.id.desc()).limit(1))).scalar_one_or_none()
    return ok({
        "enabled": plm_sync.enabled(),
        "types": [{"type_slug": r.type_slug, "objects_as_of": r.objects_as_of,
                   "relations_as_of": r.relations_as_of,
                   "catalog_revision": r.catalog_revision, "last_run_at": r.last_run_at,
                   "last_status": r.last_status, "last_error": r.last_error,
                   "objects": counts.get(r.type_slug, 0)} for r in rows],
        "objects_by_type": counts,
        "object_states": states,
        "last_run": _run_out(last, who=False) if last else None,
        "catalog": ({"revision": cat.revision, "received_at": cat.received_at,
                     "system": (cat.body or {}).get("system"),
                     "types": len((cat.body or {}).get("types") or [])} if cat else None),
        "full_every_days": settings.sp_core_full_every_days,
        "merged_waiting": len(await svc.merged_tasks(db)),
    })


@admin.get("/ontology/sync/runs")
async def sync_runs(limit: int = Query(default=20, ge=1, le=200),
                    db: AsyncSession = Depends(get_db)):
    """최근 받기 실행 — 결과 · 사유 · 알림 · 건수 · 누른 사람(관리자)."""
    rows = (await db.execute(select(OntoSyncRun).order_by(OntoSyncRun.id.desc()).limit(limit))).scalars().all()
    return ok([_run_out(r, who=True) for r in rows])


@admin.post("/ontology/sync")
async def run_sync(
    full: bool = Query(default=False, description="처음부터 다시 받는다(부재 대조 — 안 온 것은 「사용 안 함」)"),
    allow_shrink: bool = Query(default=False, description="강제 정리 — 「절반 넘게 안 옴」 을 사람이 확인한 뒤에만"),
    actor: User = Depends(require_system_admin),
):
    """지금 한 번 받는다. 꺼져 있으면 **조용히 성공하지 않고** 꺼졌다고 말한다.

    결과는 셋이다(SP 키트 규칙 16) — `ok` · `needs_check`(받은 것은 반영했고 사유가 `problems` 에) · `failed`.
    ★멈춘 실행도 **끝까지 받은 흐름은 이미 커밋됐다**(전부-아니면-무가 아니다). 그때는 409 로 통째 실패라 말하지 않고
    타입별 결과(`types`)와 함께 돌려준다(KR-13). 아예 못 돈 것(꺼짐 · 받는 중 · 예외 · 카탈로그 불가 — `types` 가 비었다)만 409 다.
    `allow_shrink` 는 `full` 일 때만 뜻이 있다 — 증분은 부재 대조를 안 한다."""
    from app.worker import plm_sync
    got = await plm_sync.sync_once(full=full, allow_shrink=allow_shrink and full, trigger="admin",
                                   requested_by=actor.email)
    if got.get("result") == "ok":
        return ok(got, message="받았습니다.")
    if got.get("result") == "needs_check":
        return ok(got, message="받았습니다 — 확인할 것이 있습니다(problems 를 보세요).")
    if got.get("types"):
        return ok(got, message="멈췄습니다 — 끝까지 받은 타입은 반영됐습니다(types · error 를 보세요).")
    raise HTTPException(status.HTTP_409_CONFLICT,
                        str(got.get("error")) + (f": {got['detail']}" if got.get("detail") else ""))


@admin.get("/ontology/merged-tasks")
async def merged_tasks(db: AsyncSession = Depends(get_db)):
    """허브에서 합쳐졌는데 우리 개정 · 별칭이 아직 진 쪽에 매달린 과제 — 「B 로 옮기기」 를 기다린다."""
    return ok(await svc.merged_tasks(db))


class MoveIn(BaseModel):
    note: str = Field(default="", max_length=2000)


@admin.post("/ontology/merged-tasks/{task_key:path}/move")
async def move_merged(task_key: str, body: MoveIn, actor: User = Depends(require_system_admin),
                      db: AsyncSession = Depends(get_db)):
    """합쳐진 과제(A)의 우리 것을 허브가 정한 곳(B)으로 옮긴다(사용자 결정 10-30 「알리고 사람이 옮긴다」).

    받는 중이면 거절한다 — 받기의 층 2 반영과 같은 표를 고친다(규칙 14 의 잠금을 함께 건다)."""
    from app.worker import plm_sync
    if not await plm_sync.try_lock(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "busy: 지금 받는 중입니다 — 끝난 뒤 다시 누르세요")
    got = await svc.move_merged_task(db, task_key, by=actor.email, note=body.note)
    if not got.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{got.get('error')}: {got.get('detail') or ''}")
    await db.commit()
    return ok(got, message=f"{got['from']} 의 개정 {got['revisions'] + got['collapsed']}개 · 별칭 {got['aliases']}개를 "
                           f"{got['to']} 로 옮겼습니다.")


# ── 보기(읽기 전용) — 받은 모든 공개 타입의 객체와 선 ──────────────────────
# 정본은 허브다 — 여기서 고치는 길은 없다(SP `managed_by`). 우리 것(개정)도 같은 표에 살아 함께 보인다(`source`).

@router.get("/ontology/types")
async def ontology_types(_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """타입 정의(허브 카탈로그에서 채운 것 · 우리 것)와 타입별 건수 · 관계 종류."""
    states = await _object_states(db)
    defs = (await db.execute(select(OntoType).order_by(OntoType.slug))).scalars().all()
    seen = {d.slug for d in defs}
    types = [{"slug": d.slug, "label": d.label, "description": d.description, "source": d.source,
              "catalog_revision": d.catalog_revision, "properties": d.properties or [],
              "relations": d.relations or [], "counts": states.get(d.slug, {})} for d in defs]
    # 정의 없이 행만 있는 타입(정의를 받기 전 판에 받은 것)도 빠뜨리지 않는다
    types += [{"slug": slug, "label": slug, "description": "", "source": None, "catalog_revision": None,
               "properties": [], "relations": [], "counts": c} for slug, c in sorted(states.items()) if slug not in seen]
    rels = (await db.execute(select(OntoRelationType).order_by(OntoRelationType.slug))).scalars().all()
    return ok({"types": types,
               "relation_types": [{"slug": r.slug, "label": r.label, "inverse_label": r.inverse_label,
                                   "src": r.src or [], "dst": r.dst or [], "source": r.source} for r in rels]})


_STATES = ("all", "active", "deprecated", "inactive")


@router.get("/ontology/objects")
async def ontology_objects(
    type: str = Query(min_length=1, max_length=80, description="타입 slug"),
    q: str | None = Query(default=None, max_length=200, description="key · 이름 일부"),
    state: str = Query(default="all", description="all · active · deprecated(그만 씀) · inactive(사용 안 함)"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """한 타입의 객체 — 사라진 것도 지우지 않았으므로 「사용 안 함」 으로 함께 보인다(거르개 `state`)."""
    if state not in _STATES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"state 는 {_STATES} 중 하나")
    stmt = select(OntoObject).where(OntoObject.type_slug == type, OntoObject.report_id.is_(None))
    if state == "active":
        stmt = stmt.where(OntoObject.deleted.is_(False), OntoObject.status != "deprecated")
    elif state == "deprecated":
        stmt = stmt.where(OntoObject.deleted.is_(False), OntoObject.status == "deprecated")
    elif state == "inactive":
        stmt = stmt.where(OntoObject.deleted.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(OntoObject.key.ilike(like) | OntoObject.label.ilike(like))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(OntoObject.key).offset(offset).limit(limit))).scalars().all()
    return ok({"type": type, "total": total, "offset": offset,
               "items": [_obj_out(r) for r in rows]})


def _obj_out(r: OntoObject, *, full: bool = False) -> dict:
    out = {"type": r.type_slug, "key": r.key, "label": r.label, "status": r.status,
           "active": not r.deleted, "hidden": r.hidden, "merged_into": r.merged_into,
           "source": r.source, "updated_at": r.updated_at, "synced_at": r.synced_at}
    if full:
        out.update(properties=r.properties or {}, previous_keys=r.previous_keys or [])
    return out


@router.get("/ontology/objects/{type_slug}/{key:path}")
async def ontology_object(type_slug: str, key: str,
                          _user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    """객체 하나 — 칸 · 상태 · 합쳐진 곳 · 옛 식별자 · 나가는/들어오는 선(지금 이어진 것)."""
    obj = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == type_slug, OntoObject.key == key,
        OntoObject.report_id.is_(None)))).scalar_one_or_none()
    if obj is None:
        now = await svc.current_key(db, type_slug, key)
        if now != key:
            # 옛 식별자로 물었다 — 없다고만 하지 않고 지금 것을 알려 준다
            return ok({"object": None, "renamed_to": now, "out": [], "in": [], "previous": []})
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{type_slug} {key!r} 는 받은 적이 없습니다.")
    out_rows = (await db.execute(select(OntoRelation).where(
        OntoRelation.src_type == type_slug, OntoRelation.src_key == key, OntoRelation.report_id.is_(None),
        OntoRelation.deleted.is_(False)).order_by(OntoRelation.relation, OntoRelation.dst_key))).scalars().all()
    in_rows = (await db.execute(select(OntoRelation).where(
        OntoRelation.dst_type.in_([type_slug, ""]), OntoRelation.dst_key == key, OntoRelation.report_id.is_(None),
        OntoRelation.deleted.is_(False)).order_by(OntoRelation.relation, OntoRelation.src_key))).scalars().all()
    labels = await _labels(db, [(r.dst_type, r.dst_key) for r in out_rows] + [(r.src_type, r.src_key) for r in in_rows])
    previous = (await db.execute(select(OntoPreviousKey.old_key).where(
        OntoPreviousKey.type_slug == type_slug, OntoPreviousKey.key == key)
        .order_by(OntoPreviousKey.old_key))).scalars().all()
    merged = None
    if obj.deleted and obj.merged_into:
        merged = await svc.current_key(db, type_slug, obj.merged_into)

    def edge(r: OntoRelation, t: str, k: str) -> dict:
        return {"relation": r.relation, "type": t, "key": k, "label": labels.get((t, k)),
                "source": r.source, "evidence_note": r.evidence_note, "updated_at": r.updated_at}

    return ok({"object": _obj_out(obj, full=True), "merged_into_now": merged,
               "out": [edge(r, r.dst_type, r.dst_key) for r in out_rows],
               "in": [edge(r, r.src_type, r.src_key) for r in in_rows],
               "previous": list(previous)})


async def _labels(db, ends: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """선 끝의 이름 — 받은 표에 있는 것만(리포트 같은 우리 1급 표는 id 그대로 둔다)."""
    keys = sorted({k for _, k in ends})
    if not keys:
        return {}
    rows = (await db.execute(select(OntoObject.type_slug, OntoObject.key, OntoObject.label).where(
        OntoObject.key.in_(keys), OntoObject.report_id.is_(None)))).all()
    return {(t, k): lab for t, k, lab in rows}
