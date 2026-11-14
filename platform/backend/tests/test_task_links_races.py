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


# ── 아직 없는 같은 판을 둘이 같은 순간 처음 만들 때(재검토 11-12 rr1) ─────────────────────────────────────
# 리포트 행 잠금은 리포트마다라 **다른 리포트 둘**이 같은 새 판을 만들면 서로 막지 않았다 — 둘째가 유일 제약
# (`uq_onto_objects_type_key`)에 걸려 인제스트는 리포트째 잃고(500 · HTML 고아), 손 확정은 500, 자동 잇기는 회차 전체가 되감겼다.
# 이제 판을 만들거나 고치는 길은 리포트 행 다음에 **판 이름 잠금**을 건다 — 둘째는 첫째가 끝날 때까지 기다렸다가 그 판을 쓴다.

async def _hold_new_revision(task: str, code: str, uid: int, sid: str):
    """다른 세션이 리포트 A 를 새 판 task@code 에 잇고 **커밋하지 않은 채** 쥔다(인제스트 때 잇기 · 자동 잇기의 긴 트랜잭션)."""
    s = SessionLocal()
    rid = uuid.uuid4().hex[:26].upper()
    s.add(ImpactReport(id=rid, session_id=sid, user_id=uid, kind="sphere", n_cases=0,
                       eng_meta={"project": task, "dev_revision": {"code": code}}))
    await s.commit()
    rep = await s.get(ImpactReport, rid)
    assert (await onto.link_from_eng_meta(s, rep))["ok"]
    return s, rid


async def test_an_ingest_linking_a_revision_another_transaction_is_creating_keeps_the_report(db):
    """인제스트 때 잇기가 같은 새 판을 만들던 트랜잭션과 겹쳐도 리포트는 남고 같은 판에 이어진다(예전엔 PendingRollbackError 로 통째로 잃었다)."""
    from app.modules.reports import services as rsvc
    t = _tag()
    task = f"RF-{t}"
    uid, sid = await _owner(db)
    holder, a_id = await _hold_new_revision(task, "dv1", uid, sid)
    bid = uuid.uuid4().hex[:26].upper()
    try:
        async def ingest(other):
            other.add(ImpactReport(id=bid, session_id=sid, user_id=uid, kind="sphere", n_cases=0,
                                   eng_meta={"project": task, "dev_revision": {"code": "dv1"}}))
            await rsvc._link_revision(other, await other.get(ImpactReport, bid))   # ingest_report 의 차례 — 넣고 커밋 전에 잇기
            return "linked"

        job = asyncio.create_task(_in_other_session(ingest))
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await holder.commit()                                    # 먼저 만든 쪽이 커밋한다
        outcome = await asyncio.wait_for(job, 30)
        assert blocked, "같은 새 판을 만들던 트랜잭션을 기다리지 않았다"
        assert outcome == ("ok", "linked"), f"인제스트가 깨졌다 — 리포트를 잃는다: {outcome}"
        async with SessionLocal() as f:
            assert await f.get(ImpactReport, bid) is not None, "리포트가 남지 않았다"
        assert (await _live(a_id), await _live(bid)) == ([f"{task}@dv1"], [f"{task}@dv1"])
    finally:
        await holder.close()
        await _drop(uid, sid, [task])


async def test_a_hand_confirm_of_a_revision_another_transaction_is_creating_succeeds(db):
    """손 확정(PUT)이 같은 새 판을 만들던 트랜잭션과 겹치면 기다렸다가 200(예전엔 500)."""
    import httpx

    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    t = _tag()
    task = f"RH-{t}"
    uid, sid = await _owner(db)
    bid = await _rep(db, uid, sid, project="", code="")
    holder, a_id = await _hold_new_revision(task, "dv1", uid, sid)
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    try:
        async def put():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                         base_url="http://test") as c:
                return await c.put(f"/api/v1/reports/{bid}/revision", json={"task_key": task, "code": "dv1"},
                                   headers={"authorization": f"Bearer {security.create_access_token(uid)}"})

        job = asyncio.create_task(put())
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await holder.commit()
        r = await asyncio.wait_for(job, 30)
        assert blocked, "같은 새 판을 만들던 트랜잭션을 기다리지 않았다"
        assert r.status_code == 200, r.text[:300]
        assert await _live(bid) == [f"{task}@dv1"]
    finally:
        await holder.close()
        await _drop(uid, sid, [task])


async def test_an_auto_link_round_with_a_colliding_new_revision_keeps_every_link(db, monkeypatch):
    """받기 뒤 자동 잇기 — 리포트 하나의 판이 다른 트랜잭션의 새 판과 겹쳐도 회차가 되감기지 않는다(다른 리포트까지 잃었다)."""
    from app.config import settings
    from app.worker import plm_sync
    monkeypatch.setattr(settings, "ontology", "1")              # 받기 뒤 잇기는 과제·개정 기능이 켜져 있을 때만 돈다
    t = _tag()
    task, other = f"RA-{t}", f"RB-{t}"
    uid, sid = await _owner(db)
    await _task(db, task, task_code=f"RAC-{t}")
    await _task(db, other, task_code=f"RBC-{t}")
    early = await _rep(db, uid, sid, project=f"RBC-{t}", code="dv1")        # 따로 이을 수 있는 리포트
    late = await _rep(db, uid, sid, project=f"RAC-{t}", code="dv1")         # 겹치는 판(task@dv1)
    holder, a_id = await _hold_new_revision(task, "dv1", uid, sid)
    real = onto.auto_link_tasks

    async def yes(_db):
        return True

    monkeypatch.setattr(plm_sync, "try_lock", yes)
    monkeypatch.setattr(onto, "auto_link_tasks", lambda sdb, report_ids=None: real(sdb, report_ids=sorted([early, late])))
    try:
        async def round_():
            async with SessionLocal() as s3:
                return await plm_sync._link_tasks(s3)

        job = asyncio.create_task(round_())
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await holder.commit()
        got = await asyncio.wait_for(job, 30)
        assert blocked, "같은 새 판을 만들던 트랜잭션을 기다리지 않았다"
        assert not got.get("error") and got["linked"] == 2, got
        assert (await _live(early), await _live(late)) == ([f"{other}@dv1"], [f"{task}@dv1"])
    finally:
        await holder.close()
        await _drop(uid, sid, [task, other, f"RAC-{t}", f"RBC-{t}"])


# ── 판 옮기기(허브 이름 바뀜 · 합침)도 잠근 뒤 다시 읽고 잠금 차례를 지킨다(재검토 11-12 rr6 · rr5) ─────────────────

async def test_a_move_waiting_on_a_hand_confirm_keeps_the_confirmed_revision_fields(db):
    """rr6 — 옮기기가 사람의 손 확정(커밋 전)을 기다렸으면 **그때의** 판 칸으로 옮긴다. 예전엔 기다리기 전에 읽은 판 객체로 덮어
    `rev_source` 가 되돌고 `decided_by` · `note` 가 사라졌다."""
    t = _tag()
    old, new = f"RM-{t}", f"RMN-{t}"
    uid, sid = await _owner(db)
    x = await _rep(db, uid, sid, project=old, code="dv1")
    async with SessionLocal() as s:                              # X 는 인제스트 때 잇기로 old@dv1(eng_meta)에 있다
        assert (await onto.link_from_eng_meta(s, await s.get(ImpactReport, x)))["ok"]
        await s.commit()
    hand = SessionLocal()
    try:
        assert (await onto.set_revision(hand, await hand.get(ImpactReport, x), task_key=old, code="dv1",
                                        decided_by="owner@x", note="사람이 본 판", source="manual"))["ok"]

        async def move(other):
            return await onto.move_task_revisions(other, old, new, by="admin@x", reason=onto.MOVE_MERGE)

        job = asyncio.create_task(_in_other_session(move))
        await asyncio.sleep(1.0)
        blocked = not job.done()
        await hand.commit()                                      # 주인의 손 확정이 굳는다
        outcome = await asyncio.wait_for(job, 30)
        assert blocked, "옮기기가 커밋 전인 손 확정을 기다리지 않았다"
        assert outcome[0] == "ok" and outcome[1]["revisions"] == 1, outcome
        async with SessionLocal() as f:
            obj = (await f.execute(select(OntoObject).where(OntoObject.type_slug == onto.TYPE_REVISION,
                                                            OntoObject.key == f"{new}@dv1"))).scalar_one()
        p = obj.properties or {}
        assert (p.get("rev_source"), p.get("decided_by"), p.get("note")) == ("manual", "owner@x", "사람이 본 판"), \
            f"옮기기가 기다리기 전에 읽은 칸으로 판을 덮었다: {p}"
        assert await _live(x) == [f"{new}@dv1"]
    finally:
        await hand.close()
        await _drop(uid, sid, [old, new])


async def test_the_rename_loop_never_waits_on_a_report_while_holding_revisions_and_defers_that_task(db, monkeypatch):
    """rr5 — 이름 바뀜 옮기기(받기 뒤 층 2)는 과제마다 옮긴다. 앞 과제의 판을 쥔 채 뒤 과제에 그새 이어진 리포트를 기다리면, 그
    리포트를 쥐고 앞 판을 기다리는 손 확정과 교착했다. 이제 판 이름을 쥔 뒤에는 리포트를 기다리지 않고 그 과제를 미룬다(`deferred`) —
    다음 받기가 옮긴다."""
    t = _tag()
    old1, new1, old2, new2 = f"RD1-{t}", f"RN1-{t}", f"RD2-{t}", f"RN2-{t}"
    uid, sid = await _owner(db)
    a = await _rep(db, uid, sid, project="", code="")
    y = await _rep(db, uid, sid, project="", code="")
    z = await _rep(db, uid, sid, project="", code="")
    for rid, task in ((a, old1), (y, old2)):
        async with SessionLocal() as s:
            assert (await onto.set_revision(s, await s.get(ImpactReport, rid), task_key=task, code="dv1",
                                            decided_by="kim@x", source="manual"))["ok"]
            await s.commit()

    async def mine(_db, type_slug):                              # 받은 사본 전체 대신 이 시험의 이름 바뀜 둘만(공유 DB)
        return {old1: new1, old2: new2} if type_slug == onto.TYPE_TASK else {}

    real = onto._reports_on
    side: dict = {}

    async def hooked(sdb, keys):
        if list(keys) == [f"{old2}@dv1"] and "t2" not in side:  # 뒤 과제 옮기기의 첫 보기 — 앞 과제의 판 이름은 이미 쥐었다
            async with SessionLocal() as s:                      # Z 가 뒤 과제의 판에 이어진다(커밋)
                assert (await onto.set_revision(s, await s.get(ImpactReport, z), task_key=old2, code="dv1",
                                                decided_by="kim@x", source="manual"))["ok"]
                await s.commit()

            async def hand(other):                               # 다른 사람 손: Z 를 쥐고 앞 과제의 판(옮기는 중)으로 확정
                return await onto.set_revision(other, await other.get(ImpactReport, z), task_key=old1, code="dv1",
                                               decided_by="lee@x", source="manual")
            side["t2"] = asyncio.create_task(_in_other_session(hand))
            await asyncio.sleep(0.7)
        return await real(sdb, keys)

    monkeypatch.setattr(onto, "renamed_keys", mine)
    monkeypatch.setattr(onto, "_reports_on", hooked)
    try:
        try:
            first = ("ok", await onto.reflect_after_sync(db))
            await db.commit()
        except Exception as exc:                                 # noqa: BLE001 — 깨지면 그 모양을 단언에 보인다
            await db.rollback()
            first = ("error", f"{type(exc).__name__}: {str(exc)[:200]}")
        second = await asyncio.wait_for(side["t2"], 30)
        assert first[0] == "ok", f"이름 바뀜 옮기기가 깨졌다(교착): {first}"
        assert second[0] == "ok" and second[1]["ok"], f"손 확정이 깨졌다(교착): {second}"
        assert (first[1]["renamed"], first[1]["deferred"]) == (1, 1), first[1]
        monkeypatch.setattr(onto, "_reports_on", real)
        again = await onto.reflect_after_sync(db)                # 다음 받기 — 미룬 과제를 옮긴다
        await db.commit()
        assert again["deferred"] == 0 and await _live(y) == [f"{new2}@dv1"], (again, await _live(y))
    finally:
        await db.rollback()
        await _drop(uid, sid, [old1, new1, old2, new2])


# ── 지우기와 겹친 손 확정(재검토 11-12) ─────────────────────────────────────────────────────────────

async def test_a_hand_confirm_racing_a_report_delete_is_a_404_and_leaves_no_line(db, monkeypatch):
    """손 확정(PUT)이 리포트를 읽은 뒤 그 리포트가 지워지면, 잠글 행이 없어 지나가던 `lock_reports` 뒤에 선을 넣어 지운 리포트의 선이
    남았다(0019 트리거는 지울 때 한 번 돈다). 이제 잠근 뒤 리포트 행이 없으면 `report_gone` — 라우트는 404 다."""
    import httpx

    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    t = _tag()
    task = f"RG-{t}"
    uid, sid = await _owner(db)
    rid = await _rep(db, uid, sid, project="", code="")
    real = onto.lock_reports
    fired = []

    async def delete_first(sdb, ids):
        if rid in {str(i) for i in ids} and not fired:          # PUT 이 리포트를 읽은 뒤 · 잠그기 전에 주인이 지운다(커밋)
            fired.append(1)
            async with SessionLocal() as other:
                await other.execute(delete(ImpactReport).where(ImpactReport.id == rid))
                await other.commit()
        return await real(sdb, ids)

    monkeypatch.setattr(onto, "lock_reports", delete_first)
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as c:
            r = await c.put(f"/api/v1/reports/{rid}/revision", json={"task_key": task, "code": "dv1"},
                            headers={"authorization": f"Bearer {security.create_access_token(uid)}"})
        assert fired, "지우기가 끼어들지 않았다 — 시험이 틀렸다"
        assert r.status_code == 404 and "report_gone" in r.text, (r.status_code, r.text[:300])
        assert await _live(rid) == [], "지운 리포트의 선이 남았다"
    finally:
        await _drop(uid, sid, [task])
