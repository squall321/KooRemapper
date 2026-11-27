# 자동 파이프라인 원천 KR-AP1 — 세션의 허브 과제 · 개발 단계 칸과 auto_changes(쪽 끝까지 · null · refs 고정 · 입력 지문 · 시야)
"""포털 계약 v1.1 §1 · §4(5 · 6) · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md · 사용자 결정 11-27(맥락 1 · 3절).

공유 시험 DB 라 이 시험이 만든 행만 보고 치운다. 다른 시험이 남긴 세션이 쪽에 섞여도 우리 세션이 한 번씩 · 차례대로 오는지만 본다.
"""
from __future__ import annotations

import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.config import settings
from app.database import SessionLocal
from app.models import OntoObject, Session, SessionFile, User
from app.modules.auto import services as auto
from app.modules.ontology import services as onto
from app.runner import sp_core
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    return uuid.uuid4().hex[:12]


async def _user(db, **kw) -> User:
    u = User(email=f"ap_{uuid.uuid4().hex}@kooremapper.test", password_hash=security.hash_password("x"), is_active=True, **kw)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _session(db, u: User, *, visibility="private", files=(), at=None) -> Session:
    sid = uuid.uuid4().hex[:26]
    s = Session(id=sid, user_id=u.id, name=f"ap-{sid[:6]}", storage_path=storage.session_rel_dir(u.id, sid),
                visibility=visibility)
    db.add(s)
    await db.flush()
    for name, body, sha in files:
        rel = f"{s.storage_path}/{name}"
        p = storage.abs_path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        db.add(SessionFile(session_id=sid, filename=name, rel_path=rel, kind="input", size_bytes=len(body), sha256=sha,
                           created_at=at or datetime.now(timezone.utc)))
    await db.commit()
    return s


async def _drop(users, keys=()):
    async with SessionLocal() as db:
        for u in users:
            sids = (await db.execute(select(Session.id).where(Session.user_id == u.id))).scalars().all()
            await db.execute(delete(SessionFile).where(SessionFile.session_id.in_(sids)))
            await db.execute(delete(Session).where(Session.user_id == u.id))
            await db.execute(delete(User).where(User.id == u.id))
            for sid in sids:
                shutil.rmtree(storage.session_abs_dir(u.id, sid), ignore_errors=True)
        for k in keys:
            await db.execute(delete(OntoObject).where(OntoObject.key == k))
        await db.commit()


async def _all_pages(db, u, limit=50):
    seen, since, pages = [], None, 0
    while True:
        got = await auto.changes(db, u, since=since, limit=limit)
        seen += got["items"]
        since, pages = got["next_since"], pages + 1
        if got["complete"]:
            return seen, since, pages
        assert pages < 500, "쪽이 끝나지 않는다"


def _mine(items, sids):
    return [i for i in items if i["subject"]["refs"]["dynaforge"] in sids]


# ── 세션 칸 둘(REST) ───────────────────────────────────────────────────────

async def _patch(u, sid, body):
    from app.main import create_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(), raise_app_exceptions=False),
                                 base_url="http://t") as c:
        return await c.patch(f"/api/v1/sessions/{sid}", json=body,
                             headers={"authorization": f"Bearer {security.create_access_token(u.id)}"})


async def test_the_task_field_resolves_like_a_revision_confirm_and_refuses_unknown_names(db):
    t = _tag()
    name, code = f"과제-{t}", f"TC{t}"
    u = await _user(db)
    try:
        await sp_core.save_rows(db, onto.TYPE_TASK, [{"key": name, "label": name, "status": "active", "updated_at": "T1",
                                                       "properties": {"task_code": code}}])
        await db.commit()
        s = await _session(db, u)
        r = await _patch(u, s.id, {"task_key": code, "dev_rev": "dv1"})
        assert r.status_code == 200, r.text
        assert (r.json()["data"]["task_key"], r.json()["data"]["dev_rev"]) == (name, "dv1"), "과제코드가 과제명으로 풀리지 않았다"
        r = await _patch(u, s.id, {"task_key": f"없는-{t}", "name": "바뀌면 안 되는 이름"})
        assert r.status_code == 400 and r.json()["data"]["error"] == "task_unresolved", r.text
        r = await _patch(u, s.id, {"dev_rev": "DV9x"})
        assert r.status_code == 400 and r.json()["data"]["error"] == "bad_dev_rev", r.text
        async with SessionLocal() as f:
            row = await f.get(Session, s.id)
            assert (row.task_key, row.dev_rev, row.name) == (name, "dv1", s.name), "거절했는데 다른 칸이 바뀌었다"
        r = await _patch(u, s.id, {"task_key": None, "dev_rev": None})
        assert (r.json()["data"]["task_key"], r.json()["data"]["dev_rev"]) == (None, None), "null 은 지운다"
    finally:
        await _drop([u], [name])


# ── auto_changes ───────────────────────────────────────────────────────────

async def test_changes_page_to_the_end_once_each_in_order(db):
    u = await _user(db)
    try:
        base = datetime.now(timezone.utc) - timedelta(days=3650)       # 다른 시험 행보다 앞 — 차례를 우리가 정한다
        made = []
        for i in range(7):
            s = await _session(db, u)
            await db.execute(update(Session).where(Session.id == s.id).values(updated_at=base + timedelta(seconds=i)))
            made.append(s.id)
        await db.commit()
        items, _, pages = await _all_pages(db, u, limit=2)
        mine = [i["subject"]["refs"]["dynaforge"] for i in _mine(items, set(made))]
        assert mine == made, "쪽을 넘기며 빠지거나 겹치거나 차례가 틀렸다"
        assert pages >= 4
    finally:
        await _drop([u])


async def test_subject_is_null_until_filled_and_refs_stay_the_session_id(db):
    u = await _user(db)
    try:
        s = await _session(db, u)
        item = _mine((await _all_pages(db, u))[0], {s.id})[0]
        assert item["subject"] == {"project": None, "revision": None, "refs": {"dynaforge": s.id}}, "모르는 과제를 지어냈다"
        assert "links" not in item
        await db.execute(update(Session).where(Session.id == s.id).values(
            task_key="과제-X", dev_rev="pv1", linked_cad={"project_id": "p-77", "revision": "r2"}))
        await db.commit()
        item = _mine((await _all_pages(db, u))[0], {s.id})[0]
        assert item["subject"] == {"project": "과제-X", "revision": "pv1", "refs": {"dynaforge": s.id}}, "refs 가 바뀌었다"
        assert item["links"] == {"step_forge": "p-77"}
    finally:
        await _drop([u])


async def test_inputs_carry_sha256_and_deck_ready_needs_exactly_one_deck(db):
    u = await _user(db)
    try:
        one = await _session(db, u, files=[("main.k", b"*KEYWORD\n*END\n", None), ("mat.csv", b"a,b\n", "ab" * 32)])
        two = await _session(db, u, files=[("a.k", b"*KEYWORD\n", "cd" * 32), ("b.key", b"*KEYWORD\n", "ef" * 32)])
        none = await _session(db, u, files=[("part.inc", b"*NODE\n", "12" * 32)])
        items = {i["subject"]["refs"]["dynaforge"]: i for i in _mine((await _all_pages(db, u))[0], {one.id, two.id, none.id})}
        import hashlib
        deck = next(i for i in items[one.id]["inputs"] if i["name"] == "main.k")
        assert deck["sha256"] == hashlib.sha256(b"*KEYWORD\n*END\n").hexdigest() and deck["kind"] == "deck", "빈 sha 를 재지 않았다"
        assert all(i["sha256"] for it in items.values() for i in it["inputs"]), "입력 지문이 비었다"
        async with SessionLocal() as f:
            assert (await f.execute(select(SessionFile.sha256).where(SessionFile.filename == "main.k",
                                                                     SessionFile.session_id == one.id))).scalar_one()
        assert [items[k]["ready"]["deck_ready"] for k in (one.id, two.id, none.id)] == [True, False, False]
    finally:
        await _drop([u])


async def test_a_new_file_brings_the_session_back_after_the_cursor(db):
    u = await _user(db)
    try:
        s = await _session(db, u)
        _, since, _ = await _all_pages(db, u)
        assert not _mine((await auto.changes(db, u, since=since, limit=50))["items"], {s.id}), "바뀐 것이 없는데 또 왔다"
        rel = f"{s.storage_path}/new.k"
        storage.abs_path(rel).parent.mkdir(parents=True, exist_ok=True)
        storage.abs_path(rel).write_bytes(b"*KEYWORD\n")
        db.add(SessionFile(session_id=s.id, filename="new.k", rel_path=rel, kind="input", size_bytes=9, sha256="aa" * 32,
                           created_at=datetime.now(timezone.utc) + timedelta(seconds=5)))
        await db.commit()
        got = await auto.changes(db, u, since=since, limit=50)
        items = _mine(got["items"], {s.id})
        while not items and not got["complete"]:
            got = await auto.changes(db, u, since=got["next_since"], limit=50)
            items = _mine(got["items"], {s.id})
        assert items and items[0]["inputs"][0]["name"] == "new.k", "파일이 와도 세션이 다시 오지 않았다(세션 수정 시각만 봤다)"
    finally:
        await _drop([u])


async def test_the_service_account_sees_every_session_and_others_only_what_they_may(db, monkeypatch):
    owner, svc_user, stranger = await _user(db), await _user(db), await _user(db)
    try:
        s = await _session(db, owner, visibility="private")
        assert not _mine((await _all_pages(db, stranger))[0], {s.id}), "남의 비공개 세션이 보였다"
        assert not _mine((await _all_pages(db, svc_user))[0], {s.id}), "설정 전 서비스 계정이 다 봤다"
        monkeypatch.setattr(type(settings), "auto_service_email_set", property(lambda self: frozenset({svc_user.email.lower()})))
        assert _mine((await _all_pages(db, svc_user))[0], {s.id}), "서비스 계정이 모든 세션을 못 봤다(계약 §4-6)"
        assert not _mine((await _all_pages(db, stranger))[0], {s.id}), "서비스 계정 설정이 남에게 샜다"
    finally:
        await _drop([owner, svc_user, stranger])


async def test_a_bad_cursor_is_refused_plainly(db):
    u = await _user(db)
    try:
        with pytest.raises(auto.AutoError) as e:
            await auto.changes(db, u, since="not-a-cursor", limit=10)
        assert e.value.error == "bad_cursor"
    finally:
        await _drop([u])
