# 레시피 REST 라우트 (/api/v1) — 제안 · 검색 · 상세 · 실행(잡) · 평가 · 등록 · 내리기.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RecipeRun, User
from app.modules.recipes import services as svc
from app.modules.sessions import services as sess_svc
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["recipes"], prefix="/recipes")


def _svc_error(exc: svc.RecipeServiceError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


class ProposeBody(BaseModel):
    name: str = Field(min_length=3, max_length=64)
    code: str = Field(min_length=1, max_length=200_000)
    meta: dict | None = None


class RunBody(BaseModel):
    session_id: str
    report_ids: list[str] = Field(min_length=1, max_length=32)
    params: dict | None = None
    version: int | None = None


class EvaluateBody(BaseModel):
    useful: bool
    note: str = Field(default="", max_length=2000)


class RegisterBody(BaseModel):
    version: int | None = None


class DeprecateBody(BaseModel):
    reason: str = Field(default="", max_length=1000)


@router.post("/propose", status_code=status.HTTP_201_CREATED)
async def propose_recipe(
    body: ProposeBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """분석 함수를 올린다 — 정적 검사 → 자기 시험(+앞 판 호환) → candidate/draft.

    code 는 run(reports, params) 와 하나 이상의 test_* 를 정의해야 한다. 즉석 분석이 효과를 보면 여기로 올려라.
    """
    try:
        return ok(await svc.propose(db, user, name=body.name, code=body.code, meta=body.meta))
    except svc.RecipeServiceError as exc:
        raise _svc_error(exc)


@router.get("")
async def list_recipes(
    q: str = Query(default=""),
    kind: str = Query(default=""),
    tag: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """등록된(그리고 내 초안·후보) 레시피를 검색한다. 새 분석 코드를 쓰기 전에 여기부터 보라."""
    return ok(await svc.search(db, user.id, q=q, kind=kind, tag=tag, limit=limit))


@router.get("/runs/{run_id}")
async def get_recipe_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(RecipeRun, run_id)
    if run is None or (run.user_id != user.id and not user.is_system_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "실행 기록을 찾을 수 없습니다.")
    return ok({
        "run_id": run.id, "recipe_id": run.recipe_id, "version": run.version,
        "job_id": run.job_id, "status": run.status, "report_ids": run.report_ids,
        "report_kinds": run.report_kinds, "params": run.params,
        "result": run.result, "result_truncated": run.result_truncated,
        "output_file_id": run.output_file_id, "error": run.error,
        "stdout_tail": run.stdout_tail, "elapsed_ms": run.elapsed_ms,
        "sandbox": run.sandbox, "useful": run.useful, "note": run.note,
    })


@router.post("/runs/{run_id}/evaluate")
async def evaluate_run(
    run_id: str,
    body: EvaluateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """실행이 쓸모 있었는지 · 왜 그런지 남긴다. useful=true 평가(글 20자↑)가 등록 관문의 근거다."""
    try:
        return ok(await svc.evaluate(db, user, run_id=run_id, useful=body.useful, note=body.note))
    except svc.RecipeServiceError as exc:
        raise _svc_error(exc)


@router.get("/{name}")
async def get_recipe(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return ok(await svc.get_detail(db, name, user.id))
    except svc.RecipeServiceError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post("/{name}/run", status_code=status.HTTP_201_CREATED)
async def run_recipe(
    name: str,
    body: RunBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """레시피를 실데이터 리포트로 돌린다 — 플랫폼 잡으로(세션 소유 · 슬롯 · 로그). 돌려주는 것은 job_id·run_id."""
    s = await sess_svc.get_owned_session(db, user.id, body.session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    try:
        job, run = await svc.create_run(
            db, user, s, recipe_name=name, version=body.version,
            report_ids=body.report_ids, params=body.params,
        )
    except svc.RecipeServiceError as exc:
        raise _svc_error(exc)
    return ok({"job_id": job.id, "run_id": run.id, "status": job.status})


@router.post("/{name}/register")
async def register_recipe(
    name: str,
    body: RegisterBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """자동 관문을 통과하면 등록한다(LLM 자동 + 자동 관문). 등록 시 platform/recipes/ 로 내보낸다."""
    try:
        return ok(await svc.register(db, user, name=name, version=body.version))
    except svc.RecipeServiceError as exc:
        raise _svc_error(exc)


@router.post("/{name}/deprecate")
async def deprecate_recipe(
    name: str,
    body: DeprecateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """레시피를 내린다(올린 사람 · 관리자). 검색과 남의 실행에서 빠진다 — 판 기록은 남는다."""
    try:
        return ok(await svc.deprecate(db, user, name=name, reason=body.reason))
    except svc.RecipeServiceError as exc:
        raise _svc_error(exc)
