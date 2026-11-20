# 캠페인 묶음 적재(DF-01) — 런 목록 · 받음 · 건너뜀 · 거절 · 수 맞춤 · 동시에 같은 런을 진짜 앱 + DB 로 잰다
"""캠페인 묶음 적재 · 중복 막기 (2026-11-20 · 계획 docs/01-plan/features/df-campaign-intake-1120.plan.md 6절).

왜 이 시험이 있나.

  천 건 넘는 런을 올리다 끊기면 어디까지 올라갔는지 알 길이 없었고, 처음부터 다시 올리면 같은 리포트가 둘이 됐다. 이제 캠페인이
  런 목록을 먼저 받고, intake 가 `campaign_id` · `run_key` 로 온 리포트를 그 런에 묶는다 — 같은 내용은 건너뛰고(중복 0) 다른
  내용은 거절하며, 받음 + 건너뜀 + 거절 + 아직 = 목록 수가 늘 맞는다. 진짜 ASGI 앱을 실제 DB 에 대고 부른다.
"""
import asyncio
import gzip
import hashlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import ulid  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import CampaignRun, ImpactReport, Session, SessionFile, User  # noqa: E402
from app.shared import security  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")


@pytest_asyncio.fixture(loop_scope="session")
async def db_up():
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DB unavailable: {exc}")


@pytest.fixture(autouse=True)
def _no_ratelimit():
    prev = settings.ratelimit_enabled
    settings.ratelimit_enabled = False
    yield
    settings.ratelimit_enabled = prev


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_up):
    from app.main import create_app

    async with httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test", timeout=300) as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def user(client):
    """사용자 하나 — 끝나면 그가 만든 세션(디스크 포함)을 API 로 지우고 사용자를 지운다(캠페인 · 런은 FK 로 함께)."""
    email = f"dfcamp_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash=security.hash_password("password123"), display_name="DFC",
                 is_active=True, is_system_admin=False)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        uid = u.id
    h = {"Authorization": f"Bearer {security.create_access_token(uid)}"}
    yield {"id": uid, "h": h}
    for sid in await _session_ids(uid):
        await client.delete(f"{API}/sessions/{sid}", headers=h)
    async with SessionLocal() as s:
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


async def _session_ids(uid: int) -> list[str]:
    async with SessionLocal() as s:
        return list((await s.execute(select(Session.id).where(Session.user_id == uid))).scalars())


async def _n_reports(uid: int) -> int:
    async with SessionLocal() as s:
        return (await s.execute(
            select(func.count(ImpactReport.id)).join(Session, Session.id == ImpactReport.session_id)
            .where(Session.user_id == uid))).scalar_one()


async def _campaign(client, h, keys=(), **fields) -> str:
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"camp-{ulid.new().str.lower()}", **fields})
    assert r.status_code == 201, r.text
    cid = r.json()["data"]["campaign_id"]
    if keys:
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [{"run_key": k} for k in keys]})
        assert r.status_code == 200, r.text
    return cid


async def _intake(client, h, raw: bytes, *, name: str = "Test_001_report.html", **form):
    return await client.post(f"{API}/reports/intake", headers=h, files={"file": (name, raw, "text/html")}, data=form)


async def _status(client, h, cid: str, **params) -> dict:
    r = await client.get(f"{API}/campaigns/{cid}/ingest-status", headers=h, params=params)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    c = d["counts"]
    assert c["listed"] == c["pending"] + c["received"] + c["skipped"] + c["rejected"], c   # 수 맞춤은 늘 잰다
    return d


def _by_key(d: dict) -> dict:
    return {r["run_key"]: r for r in d["runs"]}


# ── 캠페인 만들기 ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_create_campaign_and_same_name_gives_the_id(client, user):
    h = user["h"]
    name = f"camp-{ulid.new().str.lower()}"
    body = {"name": f"  {name} ", "project": "PRJ-A", "dev_rev": "dv1", "analysis_method": "drop",
            "analysis_target": "set", "doe_strategy": "full-angle", "drop_height_mm": 1500, "duration_ms": 3.5,
            "thickness_axis": "z", "impactor": {"mass_g": 32.6, "height_mm": 200, "ke_mj": 64}}
    r = await client.post(f"{API}/campaigns", headers=h, json=body)
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    cid = d["campaign_id"]
    assert d["name"] == name and d["thickness_axis"] == "Z" and d["dev_rev"] == "dv1", d
    assert d["impactor"] == {"mass_g": 32.6, "height_mm": 200.0, "ke_mj": 64.0} and d["environment"] == settings.environment, d

    again = await client.post(f"{API}/campaigns", headers=h, json={"name": name})
    assert again.status_code == 409, again.text
    assert again.json()["data"] == {"campaign_id": cid} and cid in again.json()["message"], again.text

    # 모르는 칸 · 틀린 개발단계 · 빈 이름은 422 — 글이 까닭을 말한다(MCP 는 글만 본다)
    assert (await client.post(f"{API}/campaigns", headers=h, json={"name": "x", "thicknes_axis": "Z"})).status_code == 422
    bad = await client.post(f"{API}/campaigns", headers=h, json={"name": f"{name}-b", "dev_rev": "dv"})
    assert bad.status_code == 422 and "dev_rev" in bad.json()["message"], bad.text
    assert (await client.post(f"{API}/campaigns", headers=h, json={"name": "   "})).status_code == 422
    assert (await client.post(f"{API}/campaigns", headers=h, json={"name": "x", "thickness_axis": "W"})).status_code == 422

    # 남은 못 본다 — 없는 것과 같은 404
    async with SessionLocal() as s:
        o = User(email=f"dfcamp_{ulid.new().str.lower()}@test.local", password_hash="x", display_name="O",
                 is_active=True, is_system_admin=False)
        s.add(o)
        await s.commit()
        await s.refresh(o)
        oid = o.id
    try:
        oh = {"Authorization": f"Bearer {security.create_access_token(oid)}"}
        for path, call in ((f"{API}/campaigns/{cid}/ingest-status", client.get),):
            assert (await call(path, headers=oh)).status_code == 404
        assert (await client.post(f"{API}/campaigns/{cid}/runs", headers=oh,
                                  json={"runs": [{"run_key": "a"}]})).status_code == 404
        assert (await _intake(client, oh, b"x", campaign_id=cid, run_key="a")).status_code == 404
        # 같은 이름을 남이 쓰는 것은 된다(이름은 만든 사람 안에서만 유일)
        mine = await client.post(f"{API}/campaigns", headers=oh, json={"name": name})
        assert mine.status_code == 201 and mine.json()["data"]["campaign_id"] != cid, mine.text
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(User).where(User.id == oid))
            await s.commit()
    assert (await client.get(f"{API}/campaigns/NOPE/ingest-status", headers=h)).status_code == 404


# ── 런 목록 ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_manifest_adds_new_keeps_old_and_refuses_duplicates(client, user):
    h = user["h"]
    cid = await _campaign(client, h)
    runs = [{"run_key": "stcx:100:1", "doe": 1, "pitch": 0, "roll": 0},
            {"run_key": "stcx:100:2", "doe": "2", "pitch": 15.5, "roll": -30},
            {"run_key": "stcx:100:3"}]
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": runs})
    assert r.status_code == 200, r.text
    assert {k: r.json()["data"][k] for k in ("added", "updated", "unchanged", "listed")} == \
        {"added": 3, "updated": 0, "unchanged": 0, "listed": 3}, r.text
    d = await _status(client, h, cid)
    assert d["counts"] == {"listed": 3, "pending": 3, "received": 0, "skipped": 0, "rejected": 0, "with_report": 0}, d
    assert [x["run_key"] for x in d["runs"]] == ["stcx:100:1", "stcx:100:2", "stcx:100:3"], d   # 올린 차례
    assert d["runs"][0]["doe"] == "1" and d["runs"][1]["pitch"] == 15.5 and d["runs"][2]["doe"] is None, d
    assert all(x["ingest_state"] == "pending" and x["report_id"] is None for x in d["runs"]), d

    # 다시 올리기 — 새 것만 더하고, 있는 것은 **보낸 칸만** 맞춘다(안 보낸 칸은 그대로 · null 은 비운다)
    again = [{"run_key": "stcx:100:1", "pitch": 90},          # pitch 만 바뀐다 — doe · roll 은 그대로
             {"run_key": "stcx:100:2", "roll": None},          # roll 을 비운다
             {"run_key": "stcx:100:3"},                         # 그대로
             {"run_key": "stcx:100:4", "doe": 4}]
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": again})
    assert {k: r.json()["data"][k] for k in ("added", "updated", "unchanged", "listed")} == \
        {"added": 1, "updated": 2, "unchanged": 1, "listed": 4}, r.text
    got = _by_key(await _status(client, h, cid))
    assert (got["stcx:100:1"]["doe"], got["stcx:100:1"]["pitch"], got["stcx:100:1"]["roll"]) == ("1", 90.0, 0.0), got
    assert (got["stcx:100:2"]["pitch"], got["stcx:100:2"]["roll"]) == (15.5, None), got

    # 한 요청 안에 같은 run_key 둘 · 빈 목록 · 빈칸 든 열쇠 · 모르는 칸은 422 이고 목록은 그대로다
    dup = await client.post(f"{API}/campaigns/{cid}/runs", headers=h,
                            json={"runs": [{"run_key": "n1"}, {"run_key": "n2"}, {"run_key": "n1"}]})
    assert dup.status_code == 422 and "n1" in dup.json()["message"], dup.text
    for body in ({"runs": []}, {"runs": [{"run_key": "a b"}]}, {"runs": [{"run_key": "a", "yaw": 1}]},
                 {"runs": [{"run_key": "a", "doe": "x" * 65}]}):
        assert (await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json=body)).status_code == 422, body
    assert (await _status(client, h, cid))["counts"]["listed"] == 4

    # 쪽 나눔 · 상태 거르기
    page = await _status(client, h, cid, limit=2, offset=1)
    assert [x["run_key"] for x in page["runs"]] == ["stcx:100:2", "stcx:100:3"] and page["matched"] == 4, page
    assert (await client.get(f"{API}/campaigns/{cid}/ingest-status", headers=h, params={"state": "done"})).status_code == 400


# ── 받음 · 건너뜀 · 거절 · 수 맞춤 ───────────────────────────────────────────────────────────────────────────────
@needs_sphere
async def test_received_skipped_rejected_and_the_counts_add_up(client, user):
    h, uid = user["h"], user["id"]
    raw = _SPHERE.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    cid = await _campaign(client, h, keys=["k1", "k2", "k3", "k4", "k5"])

    # 받음 — 지금 intake 와 같은 응답에 캠페인 칸 넷이 더 실린다. 지문은 저장된 리포트 파일의 sha256 과 같다
    r = await _intake(client, h, raw, campaign_id=cid, run_key="k1", label="k1")
    assert r.status_code == 201, r.text
    first = r.json()["data"]
    assert (first["campaign_id"], first["run_key"], first["ingest_state"], first["content_sha256"]) == (cid, "k1", "received", sha)
    assert first["n_cases"] > 0 and first["kind"] == "sphere", first
    async with SessionLocal() as s:
        stored = (await s.execute(
            select(SessionFile.sha256).join(ImpactReport, ImpactReport.source_file_id == SessionFile.id)
            .where(ImpactReport.id == first["report_id"]))).scalar_one()
    assert stored == sha
    n_sess, n_rep = len(await _session_ids(uid)), await _n_reports(uid)
    assert (n_sess, n_rep) == (1, 1)

    # 건너뜀 — 같은 내용을 다시(그대로 · .gz 로) 올려도 리포트 · 세션이 늘지 않는다(중복 0)
    for name, body in (("Test_001_report.html", raw), ("Test_001_report.html.gz", gzip.compress(raw, 1))):
        r = await _intake(client, h, body, name=name, campaign_id=cid, run_key="k1")
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert (d["ingest_state"], d["report_id"], d["session_id"], d["content_sha256"]) == \
            ("skipped", first["report_id"], first["session_id"], sha), d
        assert (len(await _session_ids(uid)), await _n_reports(uid)) == (n_sess, n_rep)
    assert _by_key(await _status(client, h, cid))["k1"]["ingest_state"] == "skipped"

    # 거절(다른 내용) — 409 · 까닭에 두 지문 · 가진 리포트는 그대로
    other = raw + b"\n<!-- other -->"
    osha = hashlib.sha256(other).hexdigest()
    r = await _intake(client, h, other, campaign_id=cid, run_key="k1")
    assert r.status_code == 409, r.text
    j = r.json()
    assert sha in j["message"] and osha in j["message"], j["message"]
    assert (j["data"]["ingest_state"], j["data"]["report_id"], j["data"]["content_sha256"], j["data"]["offered_sha256"]) == \
        ("rejected", first["report_id"], sha, osha), j
    assert (len(await _session_ids(uid)), await _n_reports(uid)) == (n_sess, n_rep)

    # 거절(해석 못 함) — 원래 400 그대로이고 런에 까닭이 남는다. 이번 호출이 만든 세션은 거둔다
    r = await _intake(client, h, b"<html><body>not a report</body></html>", name="junk.html", campaign_id=cid, run_key="k2")
    assert r.status_code == 400, r.text
    why = r.json()["message"]
    assert (len(await _session_ids(uid)), await _n_reports(uid)) == (n_sess, n_rep)

    d = await _status(client, h, cid)
    assert d["counts"] == {"listed": 5, "pending": 3, "received": 0, "skipped": 0, "rejected": 2, "with_report": 1}, d
    got = _by_key(d)
    assert got["k1"]["report_id"] == first["report_id"] and got["k1"]["content_sha256"] == sha, got["k1"]   # 가진 것은 남는다
    assert sha in got["k1"]["reject_reason"] and osha in got["k1"]["reject_reason"], got["k1"]
    assert (got["k2"]["ingest_state"], got["k2"]["report_id"], got["k2"]["reject_reason"]) == ("rejected", None, why), got["k2"]
    only = await _status(client, h, cid, state="rejected")
    assert sorted(x["run_key"] for x in only["runs"]) == ["k1", "k2"] and only["matched"] == 2, only

    # 거절 뒤 바른 것을 올리면 받음으로 바뀌고 까닭이 지워진다 · 가진 것과 같은 내용이면 다시 건너뜀
    r = await _intake(client, h, raw, campaign_id=cid, run_key="k2")
    assert r.status_code == 201 and r.json()["data"]["ingest_state"] == "received", r.text
    assert r.json()["data"]["report_id"] != first["report_id"]            # 런마다 제 리포트
    assert (await _intake(client, h, raw, campaign_id=cid, run_key="k1")).status_code == 200
    d = await _status(client, h, cid)
    assert d["counts"] == {"listed": 5, "pending": 3, "received": 1, "skipped": 1, "rejected": 0, "with_report": 2}, d
    assert all(x["reject_reason"] is None for x in d["runs"]), d


# ── 목록에 없는 열쇠 · 칸 하나만 ─────────────────────────────────────────────────────────────────────────────────
async def test_unlisted_key_or_half_a_pair_is_refused_and_nothing_is_stored(client, user):
    h, uid = user["h"], user["id"]
    cid = await _campaign(client, h, keys=["k1"])
    before = len(await _session_ids(uid))
    r = await _intake(client, h, b"x", campaign_id=cid, run_key="k9")
    assert r.status_code == 400 and "k9" in r.json()["message"] and "/runs" in r.json()["message"], r.text
    assert (await _intake(client, h, b"x", campaign_id=cid)).status_code == 400
    assert (await _intake(client, h, b"x", run_key="k1")).status_code == 400
    assert (await _intake(client, h, b"x", campaign_id="NOPE", run_key="k1")).status_code == 404
    d = await _status(client, h, cid)
    assert d["counts"]["listed"] == 1 and d["runs"][0]["ingest_state"] == "pending", d   # 행이 늘지도 적히지도 않는다
    assert len(await _session_ids(uid)) == before


# ── 런을 찾은 뒤의 4xx 는 적고, 5xx 는 적지 않는다 ────────────────────────────────────────────────────────────────
@needs_sphere
async def test_client_errors_are_recorded_server_errors_are_not(client, user, monkeypatch):
    h, uid = user["h"], user["id"]
    raw = _SPHERE.read_bytes()
    cid = await _campaign(client, h, keys=["k1", "k2", "k3"])
    before = len(await _session_ids(uid))

    r = await _intake(client, h, raw, campaign_id=cid, run_key="k1", session_id="NOPE")      # 없는 세션
    assert r.status_code == 404, r.text
    monkeypatch.setattr(settings, "max_upload_mb", 1)                                        # 크기 상한
    r2 = await _intake(client, h, raw, campaign_id=cid, run_key="k2")
    assert r2.status_code == 413, r2.text
    monkeypatch.undo()
    settings.ratelimit_enabled = False

    from app.main import create_app
    from app.modules.reports import routes as rr

    async def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(rr.svc, "ingest_report", boom)                                       # 서버 결함
    async with httpx.AsyncClient(transport=ASGITransport(app=create_app(), raise_app_exceptions=False),
                                 base_url="http://test", timeout=300) as c:
        r3 = await _intake(c, h, raw, campaign_id=cid, run_key="k3")
    assert r3.status_code == 500, r3.text
    monkeypatch.undo()
    settings.ratelimit_enabled = False

    got = _by_key(await _status(client, h, cid))
    assert (got["k1"]["ingest_state"], got["k1"]["reject_reason"]) == ("rejected", r.json()["message"]), got["k1"]
    assert (got["k2"]["ingest_state"], got["k2"]["reject_reason"]) == ("rejected", r2.json()["message"]), got["k2"]
    assert (got["k3"]["ingest_state"], got["k3"]["reject_reason"]) == ("pending", None), got["k3"]
    # 500 으로 끝난 호출이 만든 세션 하나는 남는다(캠페인이 없던 때와 같다) — 그 밖에는 늘지 않았다
    assert len(await _session_ids(uid)) == before + 1


# ── 런에 적히지 않는 실패 — 요청 꼴 오류 · 분당 한도 ────────────────────────────────────────────
@needs_sphere
async def test_shape_errors_and_the_rate_limit_are_not_recorded(client, user):
    import hashlib
    import time

    from app.shared import ratelimit

    h = user["h"]
    cid = await _campaign(client, h, keys=["k1"])
    # file 칸이 없다 — FastAPI 의 꼴 검사(422)는 HTTPException 이 아니라 런에 적히지 않는다
    r = await client.post(f"{API}/reports/intake", headers=h, data={"campaign_id": cid, "run_key": "k1", "kind": "sphere"})
    assert r.status_code == 422, r.text
    # 분당 한도 — 올리기 길의 한도는 런을 찾는 것보다 먼저 돈다(429 · Retry-After)
    token = h["Authorization"].split(" ", 1)[1]
    key = "upload:" + hashlib.sha256(token.encode()).hexdigest()[:24]
    settings.ratelimit_enabled = True
    ratelimit._hits[key].extend([time.monotonic()] * settings.ratelimit_upload_per_min)
    try:
        r2 = await _intake(client, h, _SPHERE.read_bytes(), campaign_id=cid, run_key="k1")
    finally:
        settings.ratelimit_enabled = False
        ratelimit._hits.pop(key, None)
    assert r2.status_code == 429 and int(r2.headers["Retry-After"]) >= 1, (r2.status_code, r2.text)
    got = _by_key(await _status(client, h, cid))
    assert (got["k1"]["ingest_state"], got["k1"]["reject_reason"], got["k1"]["report_id"]) == ("pending", None, None), got["k1"]


# ── 리포트 · 세션을 지우면 런이 다시 열린다 ──────────────────────────────────────────────────────────────────────
@needs_sphere
async def test_deleting_the_report_reopens_the_run(client, user):
    h = user["h"]
    raw = _SPHERE.read_bytes()
    cid = await _campaign(client, h, keys=["k1", "k2"])
    a = (await _intake(client, h, raw, campaign_id=cid, run_key="k1")).json()["data"]
    b = (await _intake(client, h, raw, campaign_id=cid, run_key="k2")).json()["data"]
    assert (await _intake(client, h, raw, campaign_id=cid, run_key="k2")).status_code == 200      # k2 는 건너뜀으로
    assert (await client.delete(f"{API}/reports/{a['report_id']}", headers=h)).status_code == 200
    assert (await client.delete(f"{API}/sessions/{b['session_id']}", headers=h)).status_code == 200
    d = await _status(client, h, cid)
    assert d["counts"] == {"listed": 2, "pending": 2, "received": 0, "skipped": 0, "rejected": 0, "with_report": 0}, d
    assert all(x["report_id"] is None and x["content_sha256"] is None and x["ingested_at"] is None for x in d["runs"]), d

    # 다시 받는다 — 이번에는 있는 세션에 담는다
    again = await _intake(client, h, raw, campaign_id=cid, run_key="k1", session_id=a["session_id"])
    assert again.status_code == 201, again.text
    assert again.json()["data"]["session_id"] == a["session_id"] and again.json()["data"]["report_id"] != a["report_id"]
    assert _by_key(await _status(client, h, cid))["k1"]["ingest_state"] == "received"


# ── 동시에 같은 런 ─────────────────────────────────────────────────────────────────────────────────────────────
@needs_sphere
async def test_the_same_run_at_once_makes_one_report(client, user):
    h, uid = user["h"], user["id"]
    raw = _SPHERE.read_bytes()
    cid = await _campaign(client, h, keys=["k1"])
    s0, r0 = len(await _session_ids(uid)), await _n_reports(uid)
    rs = await asyncio.gather(*(_intake(client, h, raw, campaign_id=cid, run_key="k1") for _ in range(3)))
    assert sorted(r.status_code for r in rs) == [200, 200, 201], [r.text[:300] for r in rs]
    assert len({r.json()["data"]["report_id"] for r in rs}) == 1                       # 셋 다 같은 리포트를 가리킨다
    assert sorted(r.json()["data"]["ingest_state"] for r in rs) == ["received", "skipped", "skipped"]
    assert (len(await _session_ids(uid)), await _n_reports(uid)) == (s0 + 1, r0 + 1)   # 세션 · 리포트 찌꺼기 없음
    d = await _status(client, h, cid)
    assert d["counts"]["with_report"] == 1 and d["counts"]["listed"] == 1, d


@needs_sphere
async def test_the_late_one_backs_off_at_the_lock(client, user, monkeypatch):
    """먼저 살핀 때는 비어 있었는데 쓰려고 잠그니 이미 가진 런 — 늦은 쪽은 제가 만든 세션을 거두고 건너뜀으로 답한다."""
    from app.modules.campaigns import services as camp_svc

    h, uid = user["h"], user["id"]
    raw = _SPHERE.read_bytes()
    cid = await _campaign(client, h, keys=["k1"])
    first = (await _intake(client, h, raw, campaign_id=cid, run_key="k1")).json()["data"]
    s0, r0 = len(await _session_ids(uid)), await _n_reports(uid)

    real, calls = camp_svc.held, []

    async def blind_once(db, run_id):
        calls.append(run_id)
        return None if len(calls) == 1 else await real(db, run_id)    # 첫 살핌만 「아직 없다」 — 동시에 온 늦은 쪽의 눈

    monkeypatch.setattr(camp_svc, "held", blind_once)
    r = await _intake(client, h, raw, campaign_id=cid, run_key="k1")
    assert r.status_code == 200 and len(calls) == 2, (r.status_code, calls, r.text[:300])
    assert (r.json()["data"]["ingest_state"], r.json()["data"]["report_id"]) == ("skipped", first["report_id"])
    assert (len(await _session_ids(uid)), await _n_reports(uid)) == (s0, r0)

    # 다른 내용으로 늦게 온 쪽은 같은 자리에서 거절이다
    calls.clear()
    r = await _intake(client, h, raw + b"\n<!-- other -->", campaign_id=cid, run_key="k1")
    assert r.status_code == 409 and r.json()["data"]["report_id"] == first["report_id"], r.text[:300]
    assert (len(await _session_ids(uid)), await _n_reports(uid)) == (s0, r0)
    async with SessionLocal() as s:
        row = (await s.execute(select(CampaignRun).where(CampaignRun.campaign_id == cid))).scalar_one()
    assert row.report_id == first["report_id"] and row.ingest_state == "rejected"


# ── 캠페인 없이 부른 intake 는 그대로다 ──────────────────────────────────────────────────────────────────────────
@needs_sphere
async def test_plain_intake_is_unchanged(client, user):
    r = await _intake(client, user["h"], _SPHERE.read_bytes(), label="plain")
    assert r.status_code == 201, r.text
    assert set(r.json()["data"]) == {"session_id", "report_id", "kfile_id", "kind", "n_cases", "label",
                                     "source_kfile_id", "task_links", "environment"}, sorted(r.json()["data"])
