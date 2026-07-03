from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Session, SessionFile
from app.runner.kfile_inspect import inspect_kfile
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


async def list_sessions(db: AsyncSession, user_id: int) -> list[tuple[Session, int]]:
    rows = (
        await db.execute(
            select(Session, func.count(SessionFile.id))
            .outerjoin(SessionFile, SessionFile.session_id == Session.id)
            .where(Session.user_id == user_id)
            .group_by(Session.id)
            .order_by(Session.updated_at.desc())
        )
    ).all()
    return [(s, c) for s, c in rows]


async def get_owned_session(
    db: AsyncSession, user_id: int, session_id: str
) -> Optional[Session]:
    row = await db.get(Session, session_id)
    if row is None or row.user_id != user_id:
        return None
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
