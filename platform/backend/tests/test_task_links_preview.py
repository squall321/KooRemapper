# SRC-10 — 과거 붙이기 계획(GET /ontology/task-links)을 일반 사용자 읽기로 연다: 읽을 수 있는 리포트만 · 적용은 403 (실 DB + ASGI + 진짜 토큰)
"""사용자 결정(11-10) — 일반 사용자의 계획에는 **자기가 읽을 수 있는 리포트(소유 · 같은 소속)만** 들고 수도 그것으로 센다.
시스템 관리자는 전부. 까닭은 리포트 수치가 새지 않게 — 일반 보기에서 `cae_*` 를 뺀 10-31 결정과 같다.

토큰은 진짜로 찍는다(`create_access_token`) — `get_current_user` 를 바꿔 끼우면 관문(`require_system_admin`)의 403 을 못 잰다.
소속은 게이트웨이 서명(`X-Heax-Aff-Proof`)을 시험 비밀로 찍어 보낸다(리포트 상세 · 검색과 같은 판정).
"""
import hashlib
import hmac
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.models import SOURCE_HUB, ImpactReport, OntoObject, OntoRelation, Session, User
from app.modules.ontology.routes import require_ontology
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

P = "/api/v1"
SECRET = "src10-gateway-secret"
AFF = "CAEG-SRC10"


def _proof(email: str, aff: str) -> dict:
    exp = int(time.time()) + 300
    msg = f"v1|{email.strip().lower()}|{aff}|{exp}"
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {"x-heax-user-affiliation": aff, "x-heax-aff-proof": f"v1.{exp}.{sig}"}


def _bearer(u: User) -> dict:
    return {"authorization": f"Bearer {security.create_access_token(u.id)}"}


async def _user(db, *, admin=False):
    u = User(email=f"src10_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="src10", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    return u, s


async def _report(db, u, s, *, project: str, shared: str | None = None, code: str = "dv1") -> ImpactReport:
    r = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=u.id, kind="sphere", n_cases=0,
                     shared_affiliation=shared, eng_meta={"project": project, "dev_revision": {"code": code}})
    db.add(r)
    await db.commit()
    return r


@pytest.fixture()
async def world(db, monkeypatch):
    """주인 A(소속 AFF 로 하나 공유 · 하나 혼자) · 같은 소속 B · 남 C(자기 리포트 하나) · 관리자 D. 과제 하나는 정본에 있다."""
    from app.config import settings
    monkeypatch.setattr(settings, "heax_gateway_secret", SECRET)
    tag = ulid.new().str[:8]
    task = f"SRC10-{tag}"                       # 정본 과제명 — 이 문자열은 `links`
    db.add(OntoObject(type_slug="plm_task", key=task, label=task, source=SOURCE_HUB, properties={}))
    await db.commit()
    a, sa = await _user(db)
    b, sb = await _user(db)
    c, sc = await _user(db)
    d, sd = await _user(db, admin=True)
    w = {"task": task, "a": a, "b": b, "c": c, "d": d,
         "shared": await _report(db, a, sa, project=task, shared=AFF),
         "private": await _report(db, a, sa, project=f"혼자-{tag}"),
         "others": await _report(db, c, sc, project=f"남의것-{tag}")}
    try:
        yield w
    finally:
        users = [a, b, c, d]
        ids = [r.id for r in (w["shared"], w["private"], w["others"])]
        await db.execute(delete(OntoRelation).where(OntoRelation.src_type == "impact_report",
                                                    OntoRelation.src_key.in_(ids)))
        await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{task}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{task}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key == task))
        await db.execute(delete(ImpactReport).where(ImpactReport.id.in_(ids)))
        await db.execute(delete(Session).where(Session.id.in_([sa.id, sb.id, sc.id, sd.id])))
        await db.execute(delete(User).where(User.id.in_([u.id for u in users])))
        await db.commit()


def _client():
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                             base_url="http://test")


def _ids(plan: dict) -> set[str]:
    return {rid for e in plan["plan"] for rid in e["reports"]} | set(plan["reports_without_a_name"])


async def test_a_regular_user_sees_only_the_reports_they_can_read(world):
    w = world
    async with _client() as c:
        owner = await c.get(f"{P}/ontology/task-links", headers=_bearer(w["a"]))
        mate = await c.get(f"{P}/ontology/task-links", headers={**_bearer(w["b"]), **_proof(w["b"].email, AFF)})
        blind = await c.get(f"{P}/ontology/task-links", headers=_bearer(w["b"]))          # 소속 증명 없음
        other = await c.get(f"{P}/ontology/task-links", headers=_bearer(w["c"]))
    for r in (owner, mate, blind, other):
        assert r.status_code == 200, (r.status_code, r.text[:300])
    owner, mate, blind, other = (r.json()["data"] for r in (owner, mate, blind, other))

    assert owner["scope"] == "readable"
    assert _ids(owner) == {w["shared"].id, w["private"].id}, "주인은 자기 것 둘만 — 남의 리포트가 끼었다"
    assert _ids(mate) == {w["shared"].id}, "같은 소속은 그 소속으로 공유된 것만"
    assert _ids(blind) == set(), "소속 증명이 없으면 남의 공유분도 안 보인다"
    assert _ids(other) == {w["others"].id}

    # ★수도 그것으로 센다 — 전사 수가 새면 안 된다
    assert owner["counts"]["reports"] == 2 and owner["counts"]["strings"] == 2
    assert mate["counts"] == {"reports": 1, "reports_without_a_name": 0, "strings": 1,
                              "links": 1, "proposal": 0, "unmatched": 0}, mate["counts"]
    assert blind["counts"]["reports"] == 0 and blind["plan"] == []
    linked = [e for e in mate["plan"] if e["verdict"] == "links"]
    assert [e["task_key"] for e in linked] == [w["task"]] and linked[0]["how"] == "exact"


async def test_a_system_admin_sees_every_report(world, db):
    w = world
    async with _client() as c:
        r = await c.get(f"{P}/ontology/task-links", headers=_bearer(w["d"]))
    assert r.status_code == 200, r.text[:300]
    got = r.json()["data"]
    assert got["scope"] == "all"
    assert {w["shared"].id, w["private"].id, w["others"].id} <= _ids(got)
    total = len((await db.execute(select(ImpactReport.id))).scalars().all())
    assert got["counts"]["reports"] == total, "관리자의 수는 전사다"


async def test_the_preview_writes_nothing_and_apply_stays_admin_only(world, db):
    w = world
    async with _client() as c:
        await c.get(f"{P}/ontology/task-links", headers=_bearer(w["a"]))
        refused = await c.post(f"{P}/ontology/task-links/apply", json={}, headers=_bearer(w["a"]))
        refused_mate = await c.post(f"{P}/ontology/task-links/apply", json={"only": [w["task"]]},
                                    headers={**_bearer(w["b"]), **_proof(w["b"].email, AFF)})
        # 관리자는 적용할 수 있다 — 없는 문자열만 골라 아무것도 잇지 않는다(공유 dev DB 를 건드리지 않게)
        allowed = await c.post(f"{P}/ontology/task-links/apply", json={"only": ["SRC10-아무것도아님"]},
                               headers=_bearer(w["d"]))
    assert refused.status_code == 403 and refused_mate.status_code == 403, (refused.status_code, refused_mate.status_code)
    assert allowed.status_code == 200 and allowed.json()["data"]["linked"] == 0, allowed.text[:300]
    edges = (await db.execute(select(OntoRelation).where(
        OntoRelation.src_type == "impact_report", OntoRelation.src_key == w["shared"].id))).scalars().all()
    assert edges == [], "미리 보기 · 거절된 적용이 선을 만들었다"


async def test_no_token_is_still_refused(world):
    async with _client() as c:
        r = await c.get(f"{P}/ontology/task-links")
    assert r.status_code == 401, r.status_code
