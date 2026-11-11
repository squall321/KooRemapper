# 리포트 선을 고치는 길끼리 겹칠 때 — 리포트 행 잠금(FOR UPDATE)과 잠근 뒤 다시 읽기로 선이 둘이 되거나 끊은 기록이 지워지지 않는다(검토 R11 · R7 · R2)
"""받기 뒤 자동 잇기는 긴 트랜잭션이다(받은 것을 커밋한 뒤 잠금을 다시 걸고 리포트 전부를 본다). 그동안 사람이 같은 리포트를 손으로
확정하거나(PUT) 끊으면, 예전엔 잠금 없이 옛 선을 읽고 지우고 넣어서 —
  R11  리포트 하나가 두 판에 이어졌다(그 뒤 자동 잇기는 kept_manual 이라 영영 낫지 않았다)
  R7   끊기가 다른 트랜잭션이 지운 선을 고치려다 500(StaleDataError)이었다
  R2   기록을 본 직후 커밋된 끊기를 자동 잇기가 지우고 다시 이었다
이제 리포트 선을 고치는 모든 길이 리포트 행을 먼저 잠그고(id 차례) 잠근 뒤에 다시 읽는다. 겹친 쪽은 기다렸다가 그때의 상태로 한다.

두 세션을 실제로 겹친다(공유 dev DB) — 이 시험의 행만 만들고 치운다. 기다림은 「1초 뒤에도 안 끝났다」 로 잰다 — 잠금이 있으면
상대가 커밋하기 전에는 끝날 수 없다.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import ImpactReport, OntoAlias, OntoObject, OntoRelation, Session, SessionFile, User
from app.modules.ontology import services as onto
from app.runner import sp_core
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    return uuid.uuid4().hex[:16]            # 1초 안에 겹치지 않는다(ulid 앞자리는 시각이라 겹친다)


async def _owner(db):
    u = User(email=f"race_{uuid.uuid4().hex}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True)
    db.add(u)
    await db.flush()
    sid = uuid.uuid4().hex[:26]
    db.add(Session(id=sid, user_id=u.id, name="race", storage_path=storage.session_rel_dir(u.id, sid)))
    await db.commit()
    return u.id, sid


async def _rep(db, uid: int, sid: str, *, project: str, code: str) -> str:
    rid = uuid.uuid4().hex[:26].upper()
    db.add(ImpactReport(id=rid, session_id=sid, user_id=uid, kind="sphere", n_cases=0,
                        eng_meta={"project": project, "dev_revision": {"code": code}}))
    await db.commit()
    return rid


async def _task(db, key: str, **props) -> None:
    await sp_core.save_rows(db, onto.TYPE_TASK, [{"key": key, "label": f"과제 {key}", "status": "active",
                                                  "updated_at": "T1", "properties": props}])
    await db.commit()


async def _live(rid: str) -> list[str]:
    async with SessionLocal() as f:
        return sorted((await f.execute(select(OntoRelation.dst_key).where(
            OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_type == onto.TYPE_REPORT,
            OntoRelation.src_key == rid, OntoRelation.deleted.is_(False)))).scalars().all())


async def _marks(rid: str) -> list[str]:
    async with SessionLocal() as f:
        return sorted(m.dst_key for m in await onto.unlink_rows(f, rid))


async def _drop(uid: int, sid: str, keys=()) -> None:
    async with SessionLocal() as db:
        mine = (await db.execute(select(ImpactReport.id).where(ImpactReport.session_id == sid))).scalars().all()
        if mine:
            await db.execute(delete(OntoRelation).where(OntoRelation.src_type == onto.TYPE_REPORT,
                                                        OntoRelation.src_key.in_(mine)))
        for k in keys:
            await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{k}@%")))
            await db.execute(delete(OntoRelation).where(OntoRelation.dst_key.like(f"{k}@%")))
            await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{k}@%")))
            await db.execute(delete(OntoObject).where(OntoObject.key == k))
            await db.execute(delete(OntoAlias).where(OntoAlias.key == k))
        await db.execute(delete(ImpactReport).where(ImpactReport.session_id == sid))
        await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
        await db.execute(delete(Session).where(Session.id == sid))
        await db.execute(delete(User).where(User.id == uid))
        await db.commit()
    shutil.rmtree(storage.session_abs_dir(uid, sid), ignore_errors=True)


async def _open_auto_link(db, task: str, code: str, rid: str) -> None:
    """리포트는 인제스트 때 잇기로 「과제코드 글자 그대로의 판」 에 있고, 허브가 그 코드의 과제를 냈다 — 자동 잇기가 옮기고 **커밋 전**."""
    async with SessionLocal() as s:
        rep = await s.get(ImpactReport, rid)
        assert (await onto.link_from_eng_meta(s, rep))["ok"]
        await s.commit()
    await _task(db, task, task_code=code)
    got = await onto.auto_link_tasks(db, report_ids=[rid])
    assert got["linked"] == 1, got


async def _in_other_session(fn):
    async with SessionLocal() as other:
        try:
            res = await fn(other)
            await other.commit()
            return "ok", res
        except Exception as exc:                  # noqa: BLE001 — 깨지면 그 모양을 단언에 보인다
            await other.rollback()
            return "error", f"{type(exc).__name__}: {str(exc)[:200]}"


async def test_a_hand_confirm_during_an_open_auto_link_waits_and_leaves_one_link(db):
    """R11 — 사람이 손으로 확정(PUT)하면 자동 잇기가 커밋할 때까지 기다렸다가 그때의 선을 떼고 잇는다. 선은 하나다."""
    t = _tag()
    task, code = f"RC-{t}", f"RCC-{t}"
    uid, sid = await _owner(db)
    rid = await _rep(db, uid, sid, project=code, code="dv1")
    try:
        await _open_auto_link(db, task, code, rid)

        async def confirm(other):
            rep = await other.get(ImpactReport, rid)
            return await onto.set_revision(other, rep, task_key=task, code="pv1", decided_by="kim@x", source="manual")

        job = asyncio.create_task(_in_other_session(confirm))
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await db.commit()                                         # 자동 잇기가 끝난다
        outcome = await asyncio.wait_for(job, 30)
        assert blocked, "사람의 확정이 커밋 전인 자동 잇기를 기다리지 않았다(리포트 행 잠금이 없다)"
        assert outcome[0] == "ok" and outcome[1]["ok"], outcome
        assert await _live(rid) == [f"{task}@pv1"], "리포트 하나가 두 판에 이어졌다"
    finally:
        await db.rollback()
        await _drop(uid, sid, [task, code])


async def test_an_unlink_during_an_open_auto_link_waits_and_records_no_500(db):
    """R7 — 끊기도 기다렸다가 그때 이어진 선(자동 잇기가 이은 것)을 끊고 기록한다. 예외가 아니다."""
    t = _tag()
    task, code = f"RU-{t}", f"RUC-{t}"
    uid, sid = await _owner(db)
    rid = await _rep(db, uid, sid, project=code, code="dv1")
    try:
        await _open_auto_link(db, task, code, rid)

        async def unlink(other):
            rep = await other.get(ImpactReport, rid)
            return await onto.unlink_revision(other, rep, by="kim@x")

        job = asyncio.create_task(_in_other_session(unlink))
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await db.commit()
        outcome = await asyncio.wait_for(job, 30)
        assert blocked, "끊기가 커밋 전인 자동 잇기를 기다리지 않았다"
        assert outcome[0] == "ok" and outcome[1]["ok"], f"끊기가 깨졌다: {outcome}"
        assert await _live(rid) == [] and await _marks(rid) == [f"{task}@dv1"], "끊은 기록이 그때 이어진 선을 가리키지 않는다"
        async with SessionLocal() as s:                           # 다음 자동 잇기도 다시 잇지 않는다
            again = await onto.auto_link_tasks(s, report_ids=[rid])
            await s.commit()
        assert (again["skipped_unlinked"], again["linked"]) == (1, 0), again
    finally:
        await db.rollback()
        await _drop(uid, sid, [task, code])


async def test_an_unlink_landing_after_the_auto_links_first_look_is_respected(db, monkeypatch):
    """R2 — 자동 잇기가 상태를 본(잠그기 전) 직후 사람이 끊고 커밋하면, 자동 잇기는 잠근 뒤 다시 읽어 그 끊음을 본다."""
    t = _tag()
    task, code = f"RL-{t}", f"RLC-{t}"
    uid, sid = await _owner(db)
    rid = await _rep(db, uid, sid, project=code, code="dv1")
    try:
        async with SessionLocal() as s:
            rep = await s.get(ImpactReport, rid)
            assert (await onto.link_from_eng_meta(s, rep))["ok"]
            await s.commit()
        await _task(db, task, task_code=code)
        real = onto._link_state
        fired = []

        async def look_then_owner_unlinks(sdb, ids):
            got = await real(sdb, ids)
            if not fired:                                         # 첫 번째 보기(잠그기 전) 직후 — 주인이 끊고 커밋한다
                fired.append(1)
                async with SessionLocal() as other:
                    rep2 = await other.get(ImpactReport, rid)
                    assert (await onto.unlink_revision(other, rep2, by="kim@x"))["ok"]
                    await other.commit()
            return got

        monkeypatch.setattr(onto, "_link_state", look_then_owner_unlinks)
        got = await onto.auto_link_tasks(db, report_ids=[rid])
        await db.commit()
        assert fired, "끊기가 끼어들지 않았다 — 시험이 틀렸다"
        assert (got["skipped_unlinked"], got["linked"]) == (1, 0), got
        assert await _live(rid) == [] and await _marks(rid) == [f"{code}@dv1"], "자동 잇기가 그새 끊은 기록을 지우고 다시 이었다"
    finally:
        await db.rollback()
        await _drop(uid, sid, [task, code])
