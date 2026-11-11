# 개정 줄 · 비교 · 객체 보기의 리포트 줄 · 수치는 읽을 수 있는 리포트만(사용자 결정 11-11 · 검토 R9) — 실 DB + ASGI + 진짜 토큰
"""과제 · 개정은 전사 공용 축이라 다 보인다. 그 안의 **리포트** 줄(id)과 수치(최악 응력 · 최악 G · 심각도 · 케이스 수)는 리포트 검색과
같은 술어(소유 · 게이트웨이가 서명한 같은 소속)로 거른다 — 예전엔 읽지 못하는 남의 리포트 id · 최악값이 개정 비교로 보였다(R9 —
SRC-09 자동 잇기가 과제코드로 새로 잇는 리포트가 그 길로 샜다). 시스템 관리자는 전부다.
"""
import hashlib
import hmac
import sys
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from sqlalchemy import delete, select

from app.models import SOURCE_HUB, ImpactReport, OntoObject, OntoRelation, Session, User
from app.modules.ontology import routes as onto_routes
from app.modules.ontology import services as onto
from app.modules.ontology.routes import require_ontology
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

P = "/api/v1"
SECRET = "rv-gateway-secret"
AFF = "CAEG-RV"


def _proof(email: str, aff: str) -> dict:
    exp = int(time.time()) + 300
    sig = hmac.new(SECRET.encode(), f"v1|{email.strip().lower()}|{aff}|{exp}".encode(), hashlib.sha256).hexdigest()
    return {"x-heax-user-affiliation": aff, "x-heax-aff-proof": f"v1.{exp}.{sig}"}


def _bearer(uid: int) -> dict:
    return {"authorization": f"Bearer {security.create_access_token(uid)}"}


async def _user(db, *, admin=False):
    u = User(email=f"rvw_{uuid.uuid4().hex}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.flush()
    sid = uuid.uuid4().hex[:26]
    db.add(Session(id=sid, user_id=u.id, name="rvw", storage_path=storage.session_rel_dir(u.id, sid)))
    await db.commit()
    return u, sid


@pytest.fixture()
async def world(db, monkeypatch):
    """주인 A 의 리포트 둘(하나는 소속 AFF 로 공유 · 하나는 혼자)이 같은 과제의 같은 판에 이어져 있다. B 는 같은 소속, C 는 남, D 는 관리자."""
    from app.config import settings
    monkeypatch.setattr(settings, "heax_gateway_secret", SECRET)
    task = f"RVW-{uuid.uuid4().hex[:16]}"
    db.add(OntoObject(type_slug="plm_task", key=task, label=task, source=SOURCE_HUB, properties={}))
    await db.commit()
    (a, sa), (b, sb), (c, sc), (d, sd) = [await _user(db) for _ in range(3)] + [await _user(db, admin=True)]
    reps = {}
    for name, shared, stress, cases in (("shared", AFF, 812.5, 162), ("private", None, 900.0, 26)):
        r = ImpactReport(id=uuid.uuid4().hex[:26].upper(), session_id=sa, user_id=a.id, kind="sphere", n_cases=cases,
                         shared_affiliation=shared, worst_stress=stress, worst_g=1450.0, max_severity="CRITICAL",
                         eng_meta={"project": task, "dev_revision": {"code": "dv1"}})
        db.add(r)
        await db.flush()
        assert (await onto.link_from_eng_meta(db, r))["ok"]
        reps[name] = r.id
    await db.commit()
    try:
        yield {"task": task, "a": a, "b": b, "c": c, "d": d, **reps}
    finally:
        ids = list(reps.values())
        await db.execute(delete(OntoRelation).where(OntoRelation.src_type == "impact_report", OntoRelation.src_key.in_(ids)))
        await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{task}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{task}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key == task))
        await db.execute(delete(ImpactReport).where(ImpactReport.id.in_(ids)))
        await db.execute(delete(Session).where(Session.id.in_([sa, sb, sc, sd])))
        await db.execute(delete(User).where(User.id.in_([a.id, b.id, c.id, d.id])))
        await db.commit()


def _client():
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")


async def _views(w, headers) -> tuple[dict, dict, dict]:
    t = w["task"]
    async with _client() as c:
        cmp_ = await c.get(f"{P}/ontology/tasks/{t}/compare", headers=headers)
        line = await c.get(f"{P}/ontology/tasks/{t}/revisions", headers=headers)
        obj = await c.get(f"{P}/ontology/objects/dev_revision/{t}@dv1", headers=headers)
    for r in (cmp_, line, obj):
        assert r.status_code == 200, (r.status_code, r.text[:300])
    return cmp_.json()["data"], line.json()["data"], obj.json()["data"]


def _report_ends(obj: dict) -> list[str]:
    return sorted(e["key"] for e in obj["in"] if e["type"] == "impact_report")


async def test_a_stranger_sees_the_revision_but_no_report_rows_or_numbers(world):
    w = world
    cmp_, line, obj = await _views(w, _bearer(w["c"].id))
    rev = cmp_["revisions"][0]
    assert cmp_["scope"] == line["scope"] == obj["scope"] == "readable"
    assert rev["code"] == "dv1", "판(개정)은 전사 공용 축이라 보여야 한다"
    assert rev["reports"] == [] and rev["n_reports"] == 0 and rev["measured_from"] == 0, rev
    assert (rev["worst_stress"], rev["worst_g"], rev["max_severity"], rev["n_cases"]) == (None, None, None, 0), \
        "읽지 못하는 남의 리포트 수치가 개정 비교로 보인다"
    assert line["revisions"][0]["reports"] == []
    assert _report_ends(obj) == [], "객체 보기로 읽지 못하는 리포트 id 가 보인다"
    assert any(e["relation"] == "revision_of" for e in obj["out"]), "개정 자체의 선은 보여야 한다"


async def test_the_same_affiliation_sees_only_the_shared_report(world):
    w = world
    cmp_, line, obj = await _views(w, {**_bearer(w["b"].id), **_proof(w["b"].email, AFF)})
    rev = cmp_["revisions"][0]
    assert rev["reports"] == [w["shared"]] and rev["worst_stress"] == 812.5 and rev["n_cases"] == 162, rev
    assert line["revisions"][0]["reports"] == [w["shared"]]
    assert _report_ends(obj) == [w["shared"]]


async def test_the_owner_and_a_system_admin_see_every_report(world):
    w = world
    both = sorted([w["shared"], w["private"]])
    for who, label in ((w["a"], "readable"), (w["d"], "all")):
        cmp_, line, obj = await _views(w, _bearer(who.id))
        rev = cmp_["revisions"][0]
        assert cmp_["scope"] == label
        assert sorted(rev["reports"]) == both and rev["worst_stress"] == 900.0 and rev["n_cases"] == 188, rev
        assert sorted(line["revisions"][0]["reports"]) == both
        assert _report_ends(obj) == both


async def test_an_inside_call_without_a_user_is_not_filtered(world, db):
    """시험장(test_sp_testbed)은 라우트 함수를 사용자 없이 바로 부른다 — 그 길은 그대로 된다(거르지 않는다)."""
    w = world
    import json
    res = await onto_routes.ontology_object(type_slug="dev_revision", key=f"{w['task']}@dv1", _user=None, db=db)
    data = json.loads(res.body)["data"]
    assert data["scope"] == "all" and _report_ends(data) == sorted([w["shared"], w["private"]])
