"""외부 잡 — 다른 클러스터에서 도는 잡의 수명을 **프로세스가 아니라 칸으로** 판정한다.

왜 필요한가. 로컬 잡은 워커의 자식이라 워커가 죽으면 같이 죽고, 그래서 기동할 때
`reconcile_orphans()` 가 남은 running 을 전부 failed 로 지우는 것이 옳다. stcx 에 던진
잡은 다르다 — API 를 재기동해도 클러스터에서 계속 돈다. 둘을 안 가르면 재기동 한 번에
네 시간짜리 잡이 화면에서 사라지고 정작 계산은 계속 돈다. **성공처럼 생긴 실패가 아니라
실패처럼 생긴 성공**이고, 사용자는 잡을 두 번 던진다.

두 번째 함정은 직렬화다. 같은 세션의 잡은 하나씩 도는데(한 work_dir 를 공유해서다),
외부 잡은 그 work_dir 에 쓰지 않는다. 그런데도 막는 쪽에 세면 stcx 잡 하나가 그 세션의
모든 로컬 작업을 몇 시간 잠근다 — 화면에는 "큐에 걸린 채 아무 일도 안 일어남" 으로 보인다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, func, select

from app.models import Job, PersonalAccessToken, Session, User
from app.shared import security
from app.shared.storage import session_rel_dir

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _mk_user(db):
    u = User(email=f"ext_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _cleanup(user_id):
    from app.database import SessionLocal
    async with SessionLocal() as s:
        await s.execute(delete(Job).where(Job.user_id == user_id))
        await s.execute(delete(Session).where(Session.user_id == user_id))
        await s.execute(delete(PersonalAccessToken).where(PersonalAccessToken.user_id == user_id))
        await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


async def _seed(user_id, *, jobs):
    """(session_id, [job_id...]) — jobs 는 (status, external_kind) 의 목록."""
    from app.database import SessionLocal
    sid = ulid.new().str
    ids = []
    async with SessionLocal() as s:
        s.add(Session(id=sid, user_id=user_id, name="s", storage_path=session_rel_dir(user_id, sid)))
        await s.flush()
        for status, kind in jobs:
            jid = ulid.new().str
            ids.append(jid)
            s.add(Job(id=jid, session_id=sid, user_id=user_id, operation="map", args={},
                      status=status, external_kind=kind))
        await s.commit()
    return sid, ids


async def test_reconcile_spares_external_jobs(db):
    """재기동해도 stcx 잡은 살아 있어야 한다. 로컬 잡은 예전처럼 failed 다."""
    from app.database import SessionLocal
    from app.worker.runner_loop import reconcile_orphans

    async with SessionLocal() as sg:
        others = (await sg.execute(
            select(func.count(Job.id)).where(Job.status == "running"))).scalar_one()
    if others:
        pytest.skip(f"{others}개가 이미 running — reconcile_orphans 는 전역이라 건드리지 않는다")

    u = await _mk_user(db)
    try:
        _, (local_id, ext_id) = await _seed(
            u.id, jobs=[("running", None), ("running", "stcx_mcp")])

        await reconcile_orphans()

        async with SessionLocal() as s:
            local, ext = await s.get(Job, local_id), await s.get(Job, ext_id)
            assert local.status == "failed", "로컬 고아는 예전처럼 정리된다"
            assert ext.status == "running", (
                "외부 잡은 이 워커의 자식이 아니다 — 재기동이 그 잡의 생사와 무관하다")
            assert ext.error_summary is None
    finally:
        await _cleanup(u.id)


async def test_a_running_external_job_does_not_block_the_session(db):
    """직렬화의 이유는 work_dir 공유다. 외부 잡은 거기 쓰지 않으므로 막지 않는다."""
    from app.database import SessionLocal
    from app.worker.runner_loop import _claim_one

    u = await _mk_user(db)
    try:
        _, (_, queued_id) = await _seed(
            u.id, jobs=[("running", "stcx_mcp"), ("queued", None)])

        async with SessionLocal() as s:
            claimed = await _claim_one(s)
        assert claimed == queued_id, (
            "stcx 잡이 도는 동안 같은 세션의 로컬 작업이 큐에 갇히면 안 된다")
    finally:
        await _cleanup(u.id)


async def test_a_running_local_job_still_blocks_the_session(db):
    """**반대쪽도 고정한다.** 위 시험만 있으면 직렬화를 통째로 없애도 통과한다."""
    from app.database import SessionLocal
    from app.worker.runner_loop import _claim_one

    u = await _mk_user(db)
    try:
        await _seed(u.id, jobs=[("running", None), ("queued", None)])

        async with SessionLocal() as s:
            claimed = await _claim_one(s)
        # 다른 세션의 잡이 잡힐 수는 있으므로, "내 세션의 queued 가 아닌 것" 으로 본다
        if claimed is not None:
            async with SessionLocal() as s2:
                j = await s2.get(Job, claimed)
                assert j.user_id != u.id, (
                    "로컬 잡이 도는 동안 같은 세션의 다음 잡이 잡히면 work_dir 이 덮인다")
    finally:
        await _cleanup(u.id)


async def test_external_columns_round_trip(db):
    """폴링이 쓸 칸들이 실제로 오간다 — 마이그레이션이 걸렸는지까지 여기서 걸린다."""
    from app.database import SessionLocal

    u = await _mk_user(db)
    try:
        sid, (jid,) = await _seed(u.id, jobs=[("running", "stcx_mcp")])
        ref = {"registry_id": 42, "slurm_job_ids": ["100", "101"],
               "work_dir": "/somewhere/on/the/share", "sphere_job_id": "262"}
        async with SessionLocal() as s:
            j = await s.get(Job, jid)
            j.external_ref = ref
            await s.commit()
        async with SessionLocal() as s2:
            j = await s2.get(Job, jid)
            assert j.external_ref == ref
            assert j.external_kind == "stcx_mcp"
            assert j.external_poll_at is None
    finally:
        await _cleanup(u.id)
