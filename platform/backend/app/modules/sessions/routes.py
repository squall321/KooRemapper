from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.modules.sessions import services as svc
from app.modules.sessions.schemas import (
    FileRead,
    SessionCreate,
    SessionRead,
    SessionUpdate,
)
from app.shared import storage
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["sessions"])


# ── sessions ────────────────────────────────────────────────────────
@router.get("/sessions")
async def list_sessions(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await svc.list_sessions(db, user.id))[offset : offset + limit]
    data = []
    for s, count in rows:
        d = SessionRead.model_validate(s).model_dump()
        d["file_count"] = count
        data.append(d)
    return ok(data)


@router.post("/sessions")
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await svc.create_session(db, user.id, body.name, body.description)
    return ok(SessionRead.model_validate(s).model_dump(), message="세션 생성됨", status_code=201)


async def _require_session(db, user, session_id):
    s = await svc.get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    files = await svc.list_files(db, session_id)
    d = SessionRead.model_validate(s).model_dump()
    d["file_count"] = len(files)
    d["files"] = [FileRead.model_validate(f).model_dump() for f in files]
    return ok(d)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.status is not None:
        s.status = body.status
    await db.commit()
    await db.refresh(s)
    return ok(SessionRead.model_validate(s).model_dump(), message="수정됨")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    await svc.delete_session(db, s)
    return ok(message="세션이 삭제되었습니다.")


# ── files ───────────────────────────────────────────────────────────
@router.post("/sessions/{session_id}/files")
async def upload_files(
    session_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.config import settings

    s = await _require_session(db, user, session_id)
    cap = settings.max_upload_mb * 1024 * 1024
    created = []
    for uf in files:
        raw = await uf.read()
        if len(raw) > cap:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{uf.filename}: 파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
            )
        row = await svc.add_uploaded_file(db, s, filename=uf.filename or "file", raw=raw)
        created.append(FileRead.model_validate(row).model_dump())
    return ok(created, message=f"{len(created)}개 파일 업로드됨", status_code=201)


@router.get("/sessions/{session_id}/files")
async def list_files(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    files = await svc.list_files(db, session_id)
    return ok([FileRead.model_validate(f).model_dump() for f in files])


@router.get("/sessions/{session_id}/files/{file_id}")
async def get_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    return ok(FileRead.model_validate(f).model_dump())


@router.get("/sessions/{session_id}/files/{file_id}/inspect")
async def inspect_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cached metadata (nodes/elements/parts/bbox/*INCLUDE/keywords)."""
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    return ok({"filename": f.filename, "meta": f.meta or {}})


@router.get("/sessions/{session_id}/files/{file_id}/download")
async def download_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    path = storage.abs_path(f.rel_path)
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "파일 실물이 없습니다.")
    return FileResponse(path, filename=f.filename, media_type="application/octet-stream")


@router.delete("/sessions/{session_id}/files/{file_id}")
async def delete_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    await svc.delete_file(db, f)
    return ok(message="파일이 삭제되었습니다.")
