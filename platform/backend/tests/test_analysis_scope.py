# analysis pull 의 권한 스코프(소유자 vs admin 전사) 검증 — 실 DB.
"""admin-scope pull: 시스템 관리자 PAT 는 전 사용자 리포트, 일반은 소유분만.

ReportArchive 가 한 인스턴스의 전사 리포트를 한 계정으로 당길 수 있어야 하므로,
list_runs/get_report 의 is_admin 분기를 실제 DB 로 확인한다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Session, User
from app.modules.analysis import services as svc
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _mk_user(db, admin=False):
    u = User(email=f"an_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _mk_report(db, user_id):
    sid = ulid.new().str
    db.add(Session(id=sid, user_id=user_id, name="s",
                   storage_path=storage.session_rel_dir(user_id, sid)))
    await db.commit()
    r = ImpactReport(id=ulid.new().str, session_id=sid, user_id=user_id,
                     kind="sphere", label="t", n_cases=0)
    db.add(r)
    await db.commit()
    return r


async def _cleanup(db, *uids):
    for uid in uids:
        await db.execute(delete(ImpactReport).where(ImpactReport.user_id == uid))
        await db.execute(delete(Session).where(Session.user_id == uid))
        await db.execute(delete(User).where(User.id == uid))
    await db.commit()


async def test_owner_vs_admin_scope(db):
    a = await _mk_user(db, admin=False)
    b = await _mk_user(db, admin=False)
    admin = await _mk_user(db, admin=True)
    try:
        ra = await _mk_report(db, a.id)
        rb = await _mk_report(db, b.id)

        # 일반 A: 자기 것만.
        a_ids = {r.id for r in await svc.list_runs(db, a.id, is_admin=False, limit=1000)}
        assert ra.id in a_ids and rb.id not in a_ids

        # admin: A·B 둘 다 보인다(전사).
        admin_ids = {r.id for r in await svc.list_runs(db, admin.id, is_admin=True, limit=1000)}
        assert ra.id in admin_ids and rb.id in admin_ids

        # 다운로드 권한: A 는 B 것 못 봄(None), admin 은 봄.
        assert await svc.get_report(db, a.id, rb.id, is_admin=False) is None
        got = await svc.get_report(db, admin.id, rb.id, is_admin=True)
        assert got is not None and got.id == rb.id
    finally:
        await _cleanup(db, a.id, b.id, admin.id)
