# 포털 요청 R-09 — 사람이 판을 확정할 때 적은 과제 이름(과제명 · 과제코드 · 별칭)을 풀고, 못 풀면 거절하는지 본다
"""사용자 결정 2026-11-25 「풀고, 안 풀리면 거절」 — 계획 docs/01-plan/features/hwax-request-1125.plan.md · 맥락 4절.

화면 자리표시는 「과제코드」 였는데 확정(PUT /reports/{id}/revision)은 입력을 글자 그대로 과제 열쇠(과제명)로 써서, 과제코드를
치면 허브 과제에 안 붙는 판이 생겼다. 자동 잇기와 같은 규칙으로 풀고, 없음 · 둘 이상이면 400 과 후보, 허브 거울에 과제가 하나도
없는 박스는 글자 그대로. 공유 DB 라 이 시험의 행만 만들고 치운다.
"""
from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.database import SessionLocal
from app.models import SOURCE_HUB, SOURCE_SELF, ImpactReport, OntoObject, OntoRelation, Session, User
from app.modules.ontology import services as onto
from app.runner import sp_core
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    return uuid.uuid4().hex[:12]


async def _task(db, key: str, **props) -> None:
    await sp_core.save_rows(db, onto.TYPE_TASK, [{"key": key, "label": f"과제 {key}", "status": "active",
                                                  "updated_at": "T1", "properties": props}])
    await db.commit()


async def _drop_tasks(keys) -> None:
    async with SessionLocal() as db:
        for k in keys:
            await db.execute(delete(OntoRelation).where(OntoRelation.dst_key.like(f"{k}@%")))
            await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{k}@%")))
            await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{k}@%")))
            await db.execute(delete(OntoObject).where(OntoObject.key == k))
        await db.commit()


# ── 풀기 ───────────────────────────────────────────────────────────────────

async def test_a_task_code_and_the_task_name_both_resolve_to_the_task_name(db):
    t = _tag()
    name, code = f"과제-{t}", f"TC{t}"
    try:
        await _task(db, name, task_code=code)
        assert await onto.resolve_confirm_task(db, code) == {"ok": True, "key": name, "how": "task_code"}
        assert await onto.resolve_confirm_task(db, f"  {name} ") == {"ok": True, "key": name, "how": "exact"}
    finally:
        await _drop_tasks([name])


async def test_an_unknown_name_is_refused_with_candidates(db):
    t = _tag()
    name = f"Proj-{t}"
    try:
        await _task(db, name, task_code=f"TC{t}")
        got = await onto.resolve_confirm_task(db, name.lower())          # 정규화해서만 같다 — 짐작으로 잇지 않는다
        assert got["ok"] is False and got["error"] == "task_unresolved" and got["ambiguous"] is False
        assert name in [c["key"] for c in got["candidates"]], got
        assert "찾지 못했다" in got["detail"]
    finally:
        await _drop_tasks([name])


async def test_a_code_shared_by_two_tasks_is_refused_as_ambiguous(db):
    t = _tag()
    a, b, code = f"A-{t}", f"B-{t}", f"TC{t}"
    try:
        await _task(db, a, task_code=code)
        await _task(db, b, task_code=code)
        got = await onto.resolve_confirm_task(db, code)
        assert got["ok"] is False and got["ambiguous"] is True
        assert {a, b} <= {c["key"] for c in got["candidates"]} and "둘 이상" in got["detail"]
    finally:
        await _drop_tasks([a, b])


async def test_a_box_without_a_hub_mirror_keeps_the_name_verbatim(db):
    """코어 받기가 꺼진 박스 — 풀 거울이 없으니 막으면 개정을 아예 못 붙인다. 거울을 잠깐 「우리 것」 으로 바꿔 보고 되돌린다.
    우리가 만든 과제 행(허브가 준 것이 아니다)은 거울로 세지 않는다 — 하나 넣어 둔다(빈 DB 에서도 그 구분을 잰다)."""
    await db.execute(update(OntoObject).where(OntoObject.type_slug == onto.TYPE_TASK,
                                              OntoObject.source == SOURCE_HUB).values(source=SOURCE_SELF))
    db.add(OntoObject(type_slug=onto.TYPE_TASK, key=f"self-{_tag()}", label="우리 것", source=SOURCE_SELF))
    await db.flush()
    try:
        assert await onto.resolve_confirm_task(db, "  아무 이름 ") == {"ok": True, "key": "아무 이름", "how": "verbatim"}
    finally:
        await db.rollback()


# ── 확정 라우트 ─────────────────────────────────────────────────────────────

async def _owner_and_report(db):
    u = User(email=f"rcr_{uuid.uuid4().hex}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True)
    db.add(u)
    await db.flush()
    sid = uuid.uuid4().hex[:26]
    db.add(Session(id=sid, user_id=u.id, name="rcr", storage_path=storage.session_rel_dir(u.id, sid)))
    await db.flush()                     # 관계가 없어 한 번에 넣으면 리포트가 세션보다 먼저 들어갈 수 있다
    rid = uuid.uuid4().hex[:26].upper()
    db.add(ImpactReport(id=rid, session_id=sid, user_id=u.id, kind="sphere", n_cases=0, eng_meta={}))
    await db.commit()
    return u.id, sid, rid


async def _drop_owner(uid, sid):
    async with SessionLocal() as db:
        mine = (await db.execute(select(ImpactReport.id).where(ImpactReport.session_id == sid))).scalars().all()
        if mine:
            await db.execute(delete(OntoRelation).where(OntoRelation.src_type == onto.TYPE_REPORT,
                                                        OntoRelation.src_key.in_(mine)))
        await db.execute(delete(ImpactReport).where(ImpactReport.session_id == sid))
        await db.execute(delete(Session).where(Session.id == sid))
        await db.execute(delete(User).where(User.id == uid))
        await db.commit()
    shutil.rmtree(storage.session_abs_dir(uid, sid), ignore_errors=True)


async def _put(uid, rid, task_key):
    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                 base_url="http://test") as c:
        return await c.put(f"/api/v1/reports/{rid}/revision", json={"task_key": task_key, "code": "dv1"},
                           headers={"authorization": f"Bearer {security.create_access_token(uid)}"})


async def _links(rid):
    async with SessionLocal() as f:
        return sorted((await f.execute(select(OntoRelation.dst_key).where(
            OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_type == onto.TYPE_REPORT,
            OntoRelation.src_key == rid, OntoRelation.deleted.is_(False)))).scalars().all())


async def test_confirming_with_a_task_code_links_the_hub_task(db):
    t = _tag()
    name, code = f"과제-{t}", f"TC{t}"
    uid, sid, rid = await _owner_and_report(db)
    try:
        await _task(db, name, task_code=code)
        r = await _put(uid, rid, code)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["task_resolved"] == {"input": code, "key": name, "how": "task_code"}
        assert await _links(rid) == [f"{name}@dv1"], "과제코드 글자 그대로의 판을 만들었다"
    finally:
        await _drop_owner(uid, sid)
        await _drop_tasks([name, code])


async def test_confirming_with_an_unknown_name_is_refused_and_changes_nothing(db):
    t = _tag()
    name = f"Proj-{t}"
    uid, sid, rid = await _owner_and_report(db)
    try:
        await _task(db, name, task_code=f"TC{t}")
        r = await _put(uid, rid, name.lower())
        assert r.status_code == 400, r.text
        body = r.json()
        assert body["data"]["error"] == "task_unresolved" and name in [c["key"] for c in body["data"]["candidates"]]
        assert "후보" in body["message"] and name in body["message"], "화면 · MCP 는 글을 보인다 — 후보가 글에도 있어야 한다"
        assert await _links(rid) == [] and not (await db.execute(select(OntoObject.key).where(
            OntoObject.key == f"{name.lower()}@dv1"))).first(), "거절했는데 판이 생겼다"
    finally:
        await _drop_owner(uid, sid)
        await _drop_tasks([name, name.lower()])
