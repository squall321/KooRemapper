from __future__ import annotations

from pathlib import Path

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
    entry = catalog.get_operation(body.operation)
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"알 수 없는 오퍼레이션: {body.operation}")
    errs = catalog.validate_args(body.operation, body.args)
    if errs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "인자 검증 실패: " + "; ".join(errs))

    # Pre-check that file-typed args reference files that exist in the session,
    # so the user gets a clear error instead of a worker failure later.
    from app.modules.sessions.services import list_files

    names = {f.filename for f in await list_files(db, session_id)}
    missing = [
        f"{p['name']}={body.args[p['name']]}"
        for p in entry.get("params", [])
        if p.get("type") == "file" and body.args.get(p["name"]) and body.args[p["name"]] not in names
    ]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "세션에 없는 입력 파일: " + ", ".join(missing) + " (먼저 업로드하세요)",
        )
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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    rows = (
        await db.execute(
            select(Job)
            .where(Job.session_id == session_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return ok([JobRead.model_validate(j).model_dump() for j in rows])


import re

_PCT = re.compile(r"(\d{1,3})\s*%")


def _live_progress(stdout_path: str | None) -> int | None:
    """Parse the most recent NN% marker from a running job's stdout."""
    if not stdout_path:
        return None
    try:
        with open(stdout_path, "rb") as fh:
            try:
                fh.seek(-4096, 2)
            except OSError:
                fh.seek(0)
            tail = fh.read().decode("utf-8", "ignore")
    except OSError:
        return None
    matches = _PCT.findall(tail)
    if not matches:
        return None
    return min(100, int(matches[-1]))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    data = JobRead.model_validate(job).model_dump()
    if job.status == "running" and data.get("progress") is None:
        data["progress"] = _live_progress(job.stdout_path)
    return ok(data)


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
        # defense in depth: only read log files inside the storage dir
        from app.config import settings as _s

        try:
            rp = Path(path).resolve()
            root = _s.storage_dir.resolve()
            if root not in rp.parents:
                return ""
            with open(rp, encoding="utf-8", errors="ignore") as fh:
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
