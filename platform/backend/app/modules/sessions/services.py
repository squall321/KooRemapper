from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Session, SessionFile, User
from app.shared import visibility as vis
from app.runner.kfile_inspect import inspect_kfile
from app.runner.kfile_modelmeta import run_modelmeta
from app.shared import storage


async def create_session(
    db: AsyncSession, user_id: int, name: str, description: str | None
) -> Session:
    sid = ulid.new().str
    row = Session(
        id=sid,
        user_id=user_id,
        name=name,
        description=description,
        storage_path=storage.session_rel_dir(user_id, sid),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    storage.ensure_session_dir(user_id, sid)
    return row


async def list_sessions(db: AsyncSession, viewer: User) -> list[tuple[Session, int]]:
    """내 세션 + 내가 볼 수 있는 공개 세션(회사·부서·팀).

    예전에는 user_id 로만 걸렀다. 그러면 조직이 공개해 둔 레퍼런스 모델도 안 보이고,
    게이트웨이 서비스 계정으로 조회하는 심의는 아무것도 못 본다.
    """
    rows = (
        await db.execute(
            select(Session, func.count(SessionFile.id))
            .outerjoin(SessionFile, SessionFile.session_id == Session.id)
            .where(vis.visible_filter(viewer))
            .group_by(Session.id)
            .order_by(Session.updated_at.desc())
        )
    ).all()
    return [(s, c) for s, c in rows]


async def get_owned_session(
    db: AsyncSession, user_id: int, session_id: str
) -> Optional[Session]:
    """쓰기·삭제용 — 소유자 본인만. 공개 세션이어도 남이 고치지는 못한다."""
    row = await db.get(Session, session_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def get_viewable_session(
    db: AsyncSession, viewer: User, session_id: str
) -> Optional[Session]:
    """읽기용 — 내 것이거나, 공개 범위에 걸리는 남의 세션."""
    row = await db.get(Session, session_id)
    if row is None:
        return None
    if row.user_id == viewer.id:
        return row
    owner = await db.get(User, row.user_id)
    return row if vis.can_view(viewer, row, owner) else None


async def get_viewable_file(
    db: AsyncSession, viewer: User, session_id: str, file_id: int
) -> Optional[SessionFile]:
    """읽기용 파일 — 세션이 보이면 그 안의 파일도 보인다."""
    sess = await get_viewable_session(db, viewer, session_id)
    if sess is None:
        return None
    f = await db.get(SessionFile, file_id)
    if f is None or f.session_id != session_id:
        return None
    return f


async def set_visibility(
    db: AsyncSession, user_id: int, session_id: str, level: str
) -> Optional[Session]:
    """공개 범위 변경 — 소유자만. 잘못된 값은 예외로 구분한다."""
    if not vis.is_valid(level):
        raise ValueError(f"visibility 는 {'|'.join(vis.LEVELS)} 중 하나여야 한다: {level!r}")
    row = await get_owned_session(db, user_id, session_id)
    if row is None:
        return None
    row.visibility = level
    await db.commit()
    await db.refresh(row)
    return row


async def list_files(db: AsyncSession, session_id: str) -> list[SessionFile]:
    return list(
        (
            await db.execute(
                select(SessionFile)
                .where(SessionFile.session_id == session_id)
                .order_by(SessionFile.id.asc())
            )
        ).scalars()
    )


async def get_owned_file(
    db: AsyncSession, user_id: int, session_id: str, file_id: int
) -> Optional[SessionFile]:
    sess = await get_owned_session(db, user_id, session_id)
    if sess is None:
        return None
    f = await db.get(SessionFile, file_id)
    if f is None or f.session_id != session_id:
        return None
    return f


async def add_uploaded_file(
    db: AsyncSession,
    session: Session,
    *,
    filename: str,
    raw: bytes,
    kind: str = "input",
) -> SessionFile:
    """Persist an uploaded file to disk, inspect it, and record metadata."""
    safe = storage.safe_filename(filename)
    sess_dir = storage.ensure_session_dir(session.user_id, session.id)
    dest = sess_dir / safe
    # de-dup name collisions: foo.k, foo_1.k, ...
    if dest.exists():
        stem, suffix = Path(safe).stem, Path(safe).suffix
        n = 1
        while (sess_dir / f"{stem}_{n}{suffix}").exists():
            n += 1
        safe = f"{stem}_{n}{suffix}"
        dest = sess_dir / safe
    # Offload the blocking I/O + `info` subprocess (up to 120s) off the event loop
    # so one upload doesn't stall the single-process API for all other requests.
    await asyncio.to_thread(dest.write_bytes, raw)

    rel = f"{session.storage_path}/{safe}"
    meta = await asyncio.to_thread(inspect_kfile, dest)
    sha = await asyncio.to_thread(storage.sha256_of, dest)
    row = SessionFile(
        session_id=session.id,
        filename=safe,
        rel_path=rel,
        kind=kind,
        size_bytes=dest.stat().st_size,
        sha256=sha,
        meta=meta,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def run_file_connectivity(
    db: AsyncSession, f: SessionFile, *, detect: bool = True
) -> dict:
    """온디맨드 connectivity 재추출 (detect=기하 탐지). 결과를 file.meta 에 갱신.

    modelmeta 는 별도 프로세스라 이벤트 루프를 막지 않게 스레드로 오프로드한다.
    """
    p = storage.abs_path(f.rel_path)
    mm = await asyncio.to_thread(run_modelmeta, p, detect=detect, timeout=300)
    if mm is not None:
        meta = dict(f.meta or {})
        meta["modelmeta"] = mm
        f.meta = meta
        await db.commit()
        await db.refresh(f)
    return mm or {"error": "not a keyword deck"}


async def delete_file(db: AsyncSession, f: SessionFile) -> None:
    p = storage.abs_path(f.rel_path)
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(f)
    await db.commit()


async def delete_session(db: AsyncSession, session: Session) -> None:
    # remove files on disk
    d = storage.session_abs_dir(session.user_id, session.id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    await db.delete(session)
    await db.commit()
