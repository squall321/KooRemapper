"""DB-integration tests for security-critical authorization paths.

Covers PAT resolution (valid / revoked / expired / inactive-user), session
ownership isolation, and worker orphan reconciliation — none of which the
pure-unit tests can exercise.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, func, select, text

from app.models import Job, PersonalAccessToken, Session, User
from app.shared import auth, security
from app.shared.storage import session_rel_dir

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _mk_user(db, *, active=True, suffix=""):
    u = User(
        email=f"test_{ulid.new().str}{suffix}@kooremapper.test",
        password_hash=security.hash_password("x"),
        is_active=active,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _mk_pat(db, user_id, *, expires_at=None, revoked=False):
    plain = security.new_pat_plaintext()
    row = PersonalAccessToken(
        user_id=user_id, name="t", token_prefix=plain[:12],
        token_hash=security.hash_pat(plain),
        expires_at=expires_at,
        revoked_at=datetime.now(timezone.utc) if revoked else None,
    )
    db.add(row)
    await db.commit()
    return plain


async def _cleanup_user(db, uid):
    await db.execute(delete(Job).where(Job.user_id == uid))
    await db.execute(delete(Session).where(Session.user_id == uid))
    await db.execute(delete(PersonalAccessToken).where(PersonalAccessToken.user_id == uid))
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()


async def test_pat_valid_resolves(db):
    u = await _mk_user(db)
    try:
        plain = await _mk_pat(db, u.id)
        resolved = await auth._resolve_pat(db, plain)
        assert resolved is not None and resolved.id == u.id
    finally:
        await _cleanup_user(db, u.id)


async def test_pat_revoked_rejected(db):
    u = await _mk_user(db)
    try:
        plain = await _mk_pat(db, u.id, revoked=True)
        assert await auth._resolve_pat(db, plain) is None
    finally:
        await _cleanup_user(db, u.id)


async def test_pat_expired_rejected(db):
    u = await _mk_user(db)
    try:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        plain = await _mk_pat(db, u.id, expires_at=past)
        assert await auth._resolve_pat(db, plain) is None
    finally:
        await _cleanup_user(db, u.id)


async def test_pat_inactive_user_rejected(db):
    u = await _mk_user(db, active=False)
    try:
        plain = await _mk_pat(db, u.id)
        assert await auth._resolve_pat(db, plain) is None
    finally:
        await _cleanup_user(db, u.id)


async def test_pat_unknown_token_rejected(db):
    assert await auth._resolve_pat(db, security.new_pat_plaintext()) is None


async def test_session_ownership_isolation(db):
    from app.modules.sessions.services import create_session, get_owned_session

    a = await _mk_user(db, suffix="a")
    b = await _mk_user(db, suffix="b")
    try:
        s = await create_session(db, a.id, "owned-by-a", None)
        # owner sees it
        assert (await get_owned_session(db, a.id, s.id)) is not None
        # other user cannot
        assert (await get_owned_session(db, b.id, s.id)) is None
    finally:
        await _cleanup_user(db, a.id)
        await _cleanup_user(db, b.id)


async def test_reconcile_orphans_fails_running_jobs(db):
    from app.database import SessionLocal
    from app.worker.runner_loop import reconcile_orphans

    # reconcile_orphans fails ALL 'running' jobs (global, by design). Against the
    # shared dev DB that would clobber a genuinely in-flight job, so skip if any
    # other job is running.
    async with SessionLocal() as sg:
        running = (await sg.execute(select(func.count(Job.id)).where(Job.status == "running"))).scalar_one()
    if running:
        pytest.skip(f"{running} job(s) already running — reconcile_orphans is global; skipping to avoid clobbering them")

    u = await _mk_user(db)
    sid = ulid.new().str
    jid = ulid.new().str
    try:
        # setup in its own session/transaction
        async with SessionLocal() as s1:
            s1.add(Session(id=sid, user_id=u.id, name="s", storage_path=session_rel_dir(u.id, sid)))
            await s1.flush()  # ensure session row exists before the job FK
            s1.add(Job(id=jid, session_id=sid, user_id=u.id, operation="map", args={}, status="running"))
            await s1.commit()

        await reconcile_orphans()

        async with SessionLocal() as s2:
            j = await s2.get(Job, jid)
            assert j.status == "failed"
            assert j.error_summary and "restarted" in j.error_summary
    finally:
        async with SessionLocal() as s3:
            await s3.execute(delete(Job).where(Job.user_id == u.id))
            await s3.execute(delete(Session).where(Session.user_id == u.id))
            await s3.execute(delete(PersonalAccessToken).where(PersonalAccessToken.user_id == u.id))
            await s3.execute(delete(User).where(User.id == u.id))
            await s3.commit()
