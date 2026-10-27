# cae00 요청 KR-01(과제코드 매칭)·KR-02('/' 든 key 경로)·KR-17(sync 읽기 개방) — 실제 DB + ASGI.
import sys
from pathlib import Path

import pytest
import ulid
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import OntoObject, User
from app.modules.ontology import services as svc
from app.modules.ontology.routes import require_ontology
from app.shared import security
from app.shared.auth import get_current_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

P = "/api/v1"


async def _mk_task(db, *, key, task_code):
    o = OntoObject(type_slug=svc.TYPE_TASK, key=key, label=key,
                   properties={"task_code": task_code}, source="hub",
                   status="active", deleted=False)
    db.add(o)
    await db.commit()
    return o


async def _user(db, admin=False):
    u = User(email=f"kr_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _cleanup(db, keys, user):
    for k in keys:
        await db.execute(delete(OntoObject).where(OntoObject.key == k))
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()


# ── KR-01 — 과제코드로 과제를 찾는다 ───────────────────────────────────
async def test_resolve_task_by_task_code(db):
    key = f"과제명 {ulid.new().str[:6]}"
    code = f"KR-{ulid.new().str[:8]}"
    u = await _user(db)
    try:
        await _mk_task(db, key=key, task_code=code)
        # 과제코드로 → key 를 과제코드 경로로 푼다
        rk, how = await svc.resolve_task(db, code)
        assert rk == key and how == "task_code", (rk, how)
        # 과제명(key) 그대로 → exact
        rk2, how2 = await svc.resolve_task(db, key)
        assert rk2 == key and how2 == "exact"
        # 없는 것 → 못 푼다
        rk3, how3 = await svc.resolve_task(db, "없는문자열ZZZ")
        assert rk3 == "" and how3 == ""
    finally:
        await _cleanup(db, [key], u)


async def test_task_candidates_surface_task_code(db):
    key = f"과제명 {ulid.new().str[:6]}"
    code = f"KR{ulid.new().str[:6]}"   # 구분기호 없는 꼴
    u = await _user(db)
    try:
        await _mk_task(db, key=key, task_code=code)
        # 과제코드에 하이픈을 끼운 변형 → 정규화 일치로 후보에 뜨고 근거가 '과제코드'
        cands = await svc.task_candidates(db, code[:2] + "-" + code[2:])
        hit = [c for c in cands if c["key"] == key]
        assert hit and "과제코드" in hit[0]["why"], cands
    finally:
        await _cleanup(db, [key], u)


# ── KR-02 — '/' 든 key 의 개정 조회가 404 가 아니다 ────────────────────
async def _client():
    import httpx
    from httpx import ASGITransport
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    return app, ASGITransport(app=app, raise_app_exceptions=False)


async def test_slash_key_revisions_not_404(db):
    import httpx
    key = f"과제 {ulid.new().str[:5]}/하위"   # '/' 포함
    u = await _user(db)
    try:
        await _mk_task(db, key=key, task_code=f"KR-{ulid.new().str[:6]}")
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: u
        from urllib.parse import quote
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"{P}/ontology/tasks/{quote(key, safe='')}/revisions")
        assert r.status_code == 200, (r.status_code, r.text[:200])
        assert r.json()["data"]["task"] == key
    finally:
        await _cleanup(db, [key], u)


# ── KR-01(검색 matched_by) + KR-17(sync 읽기 개방) ─────────────────────
async def test_list_tasks_matched_by_and_sync_read_open(db):
    import httpx
    key = f"과제명 {ulid.new().str[:6]}"
    code = f"KR-{ulid.new().str[:8]}"
    u = await _user(db, admin=False)   # 일반 사용자
    try:
        await _mk_task(db, key=key, task_code=code)
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # KR-01 — 과제코드로 검색하면 그 과제가 나오고 matched_by=task_code
            r = await c.get(f"{P}/ontology/tasks", params={"q": code})
            assert r.status_code == 200, r.text[:200]
            items = r.json()["data"]["items"]
            mine = [it for it in items if it["key"] == key]
            assert mine and mine[0]["matched_by"] == "task_code", items
            # KR-17 — 일반 사용자가 sync 읽기를 할 수 있다(403 아님)
            rs = await c.get(f"{P}/ontology/sync")
            assert rs.status_code == 200, (rs.status_code, rs.text[:200])
            assert "enabled" in rs.json()["data"]
    finally:
        await _cleanup(db, [key], u)
