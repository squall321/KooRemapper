from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Job, SessionFile, User
from app.modules.jobs.schemas import JobCreate, JobRead
from app.modules.sessions.services import get_owned_session
from app.runner import catalog
from app.shared.auth import get_current_user
from app.shared.responses import ok
from app.worker.runner_loop import request_cancel

router = APIRouter(tags=["jobs"])


async def _require_session(db, user, session_id):
    s = await get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_job(db, user, job_id) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "작업을 찾을 수 없습니다.")
    return job


@router.post("/sessions/{session_id}/jobs")
async def create_job(
    session_id: str,
    body: JobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    if catalog.get_operation(body.operation) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"알 수 없는 오퍼레이션: {body.operation}")
    errs = catalog.validate_args(body.operation, body.args)
    if errs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "인자 검증 실패: " + "; ".join(errs))
    job = Job(
        id=ulid.new().str,
        session_id=session_id,
        user_id=user.id,
        operation=body.operation,
        args=body.args,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return ok(JobRead.model_validate(job).model_dump(), message="작업이 큐에 등록되었습니다.", status_code=201)


@router.get("/sessions/{session_id}/jobs")
async def list_session_jobs(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    rows = (
        await db.execute(
            select(Job).where(Job.session_id == session_id).order_by(Job.created_at.desc())
        )
    ).scalars()
    return ok([JobRead.model_validate(j).model_dump() for j in rows])


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    return ok(JobRead.model_validate(job).model_dump())


@router.get("/jobs/{job_id}/logs", response_class=PlainTextResponse)
async def get_job_logs(
    job_id: str,
    which: str = Query("both", pattern="^(stdout|stderr|both)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)

    def _read(path: str | None) -> str:
        if not path:
            return ""
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except OSError:
            return ""

    if which == "stdout":
        return _read(job.stdout_path)
    if which == "stderr":
        return _read(job.stderr_path)
    return f"===== STDOUT =====\n{_read(job.stdout_path)}\n===== STDERR =====\n{_read(job.stderr_path)}"


@router.get("/jobs/{job_id}/outputs")
async def get_job_outputs(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    if not job.output_file_ids:
        return ok([])
    rows = (
        await db.execute(select(SessionFile).where(SessionFile.id.in_(job.output_file_ids)))
    ).scalars()
    from app.modules.sessions.schemas import FileRead

    return ok([FileRead.model_validate(f).model_dump() for f in rows])


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    if job.status not in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"취소할 수 없는 상태입니다: {job.status}")
    request_cancel(job_id)
    return ok(message="취소 요청됨")
