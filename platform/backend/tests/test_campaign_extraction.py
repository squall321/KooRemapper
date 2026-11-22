# 캠페인 추출 완전성 · d3plot 삭제 허가 · 피크 출처 표지(DF-04) — 규칙은 순수 함수로, 받는 꼴 · REST 는 진짜 앱 + DB 로 잰다
"""추출 완전성 · 삭제 관문 (2026-11-22 · 계획 docs/01-plan/features/df-extraction-clearance-1122.plan.md 6절).

왜 이 시험이 있나.

  d3plot 은 런마다 수십 ~ 수백 GB 라 리포트 뒤에 지운다. 지운 뒤 다시 못 뽑는 장(판 변형률장)이 캠페인에 필요했는데 아무도 막지
  않았고, 201 상태 가운데 40 상태만 읽은 피크(77 MPa — 전 상태는 209 MPa)가 그대로 쓰였다. 이제 런 목록이 추출 목록을 받고,
  캠페인의 필수 목록과 견줘 삭제 허가(조회만)를 내고, 피크를 돌려주는 리포트 응답마다 피크 출처 표지를 싣는다. 요청서의 검증 사례
  둘은 같은 꼴의 합성 사례로 잰다(과제 이름 · 경로는 옮기지 않는다).
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import ulid  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import Session, User  # noqa: E402
from app.modules.campaigns import extraction as X  # noqa: E402
from app.shared import security  # noqa: E402

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")
_aio = pytest.mark.asyncio(loop_scope="session")

PLATE, STRESS = "판 변형률장", "부품 응력장"
FULL = {"d3plot_states_total": 201, "d3plot_states_read": 201, "peak_source": "d3plot_full",
        "fields_extracted": [PLATE, STRESS], "d3plot_retained": True}
SAMPLED = {"d3plot_states_total": 201, "d3plot_states_read": 40, "peak_source": "d3plot_sampled",
           "fields_extracted": [STRESS], "d3plot_retained": True}
REQ = [{"field": PLATE, "parts": None, "states": "all"}, {"field": STRESS, "parts": [3, 7], "states": "sampled"}]


def _clear(extraction, required=REQ, has_report=True):
    return X.clearance(has_report=has_report, extraction=extraction, required=required)


# ---------------------------------------------------------------- 규칙(순수)

def test_run_states_from_counts_then_source():
    assert X.run_states({"d3plot_states_total": 201, "d3plot_states_read": 201}) == "all"
    assert X.run_states({"d3plot_states_total": 201, "d3plot_states_read": 40}) == "sampled"
    assert X.run_states({"peak_source": "d3plot_full"}) == "all"
    assert X.run_states({"peak_source": "d3plot_sampled"}) == "sampled"
    assert X.run_states({"peak_source": "binout"}) is None


def test_field_names_compare_without_case_and_spaces():
    assert X.field_key("  Plate  Strain ") == X.field_key("plate strain")


def test_allow_when_every_required_item_is_covered():
    assert _clear(FULL) == {"status": "allow", "reasons": [], "missing": []}
    # 객체 꼴 · 파트가 필수를 덮는다
    ext = {**FULL, "fields_extracted": [PLATE, {"field": STRESS, "parts": [1, 3, 7], "states": "sampled"}]}
    assert _clear(ext)["status"] == "allow"


def test_hold_reasons():
    assert _clear(FULL, required=None)["reasons"] == ["required_extractions_unset"]
    assert _clear(FULL, required=[])["reasons"] == ["required_extractions_unset"]
    assert _clear(FULL, has_report=False)["reasons"] == ["no_report"]
    assert _clear(None)["reasons"] == ["extraction_missing"]
    got = _clear(SAMPLED)                       # 검증 사례 ② 꼴 — 판 변형률장이 없다
    assert got["status"] == "hold" and got["reasons"] == ["extraction_incomplete"]
    assert got["missing"] == [{"field": PLATE, "parts": None, "states": "all", "reason": "field_missing"}]


def test_missing_parts_and_states():
    ext = {**FULL, "fields_extracted": [PLATE, {"field": STRESS, "parts": [3]}]}
    got = _clear(ext)
    assert got["missing"] == [{"field": STRESS, "parts": [3, 7], "states": "sampled", "reason": "parts_missing",
                               "parts_missing": [7]}]
    ext = {**FULL, "d3plot_states_read": 40, "peak_source": "d3plot_sampled"}       # 판 변형률장을 표본 상태에서만
    assert _clear(ext)["missing"][0]["reason"] == "states_sampled"
    ext = {"fields_extracted": [PLATE, STRESS], "peak_source": "binout"}             # 상태를 모른다
    assert _clear(ext)["missing"][0]["reason"] == "states_unknown"
    # 필수가 「모든 파트」 인데 추출은 일부 파트
    ext = {**FULL, "fields_extracted": [{"field": PLATE, "parts": [1]}, STRESS]}
    assert _clear(ext)["missing"][0] == {"field": PLATE, "parts": None, "states": "all", "reason": "parts_missing",
                                         "parts_missing": None}
    # 같은 field 의 추출이 여럿이면 하나만 덮어도 된다
    ext = {**FULL, "fields_extracted": [{"field": PLATE, "parts": [1]}, PLATE, STRESS]}
    assert _clear(ext)["status"] == "allow"


def test_already_deleted_runs():
    got = _clear({**FULL, "d3plot_retained": False})
    assert got == {"status": "deleted", "reasons": ["already_deleted"], "missing": []}
    got = _clear({**SAMPLED, "d3plot_deleted_at": "2026-10-27T00:00:00Z"})
    assert got["status"] == "deleted" and got["reasons"] == ["already_deleted", "extraction_lost"] and got["missing"]


def test_peak_provenance_flags():
    assert X.peak_provenance(None) == {"known": False, "peak_source": None, "states_read": None, "states_total": None,
                                       "peak_may_be_missed": None}
    s = X.peak_provenance(SAMPLED)              # 검증 사례 ① 꼴 — 201 상태 중 40
    assert s == {"known": True, "peak_source": "d3plot_sampled", "states_read": 40, "states_total": 201,
                 "peak_may_be_missed": True}
    assert X.peak_provenance(FULL)["peak_may_be_missed"] is False
    assert X.peak_provenance({**FULL, "d3plot_states_read": 200})["peak_may_be_missed"] is True
    assert X.peak_provenance({"peak_source": "binout"})["peak_may_be_missed"] is False
    assert X.peak_provenance({"peak_source": "elout"})["peak_may_be_missed"] is False
    assert X.peak_provenance({"fields_extracted": [PLATE]})["peak_may_be_missed"] is None


def test_header_counts():
    rows = [{"clearance": _clear(FULL)}, {"clearance": _clear(SAMPLED)}, {"clearance": _clear(None)},
            {"clearance": _clear({**FULL, "d3plot_retained": False})}]
    hd = X.header(rows)
    assert (hd["total"], hd["allow"], hd["hold"], hd["deleted"]) == (4, 1, 2, 1)
    assert hd["reasons"] == {"extraction_incomplete": 1, "extraction_missing": 1, "already_deleted": 1}
    assert hd["line"].startswith("삭제 허가 1 / 전체 4 · 보류 2 · 이미 지움 1")


# ---------------------------------------------------------------- 앱 + DB


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


async def _mk_user(tag: str) -> dict:
    email = f"dfext_{tag}_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash=security.hash_password("password123"), display_name="DFX", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        uid = u.id
    return {"id": uid, "email": email, "h": {"Authorization": f"Bearer {security.create_access_token(uid)}"}}


AFF, SECRET = "DFXG", "dfx-gateway-secret"


def _aff(email: str) -> dict:
    import hashlib
    import hmac
    import time
    exp = int(time.time()) + 600
    sig = hmac.new(SECRET.encode(), f"v1|{email.strip().lower()}|{AFF}|{exp}".encode(), hashlib.sha256).hexdigest()
    return {"X-Heax-User-Affiliation": AFF, "X-Heax-Aff-Proof": f"v1.{exp}.{sig}"}


async def _drop_user(client, u: dict) -> None:
    async with SessionLocal() as s:
        sids = list((await s.execute(select(Session.id).where(Session.user_id == u["id"]))).scalars())
    for sid in sids:
        await client.delete(f"{API}/sessions/{sid}", headers=u["h"])
    async with SessionLocal() as s:
        await s.execute(delete(User).where(User.id == u["id"]))
        await s.commit()


@pytest_asyncio.fixture(loop_scope="session")
async def user(client):
    u = await _mk_user("a")
    yield u
    await _drop_user(client, u)


async def _campaign(client, h, runs=(), **fields) -> str:
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"camp-{ulid.new().str.lower()}", **fields})
    assert r.status_code == 201, r.text
    cid = r.json()["data"]["campaign_id"]
    if runs:
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": list(runs)})
        assert r.status_code == 200, r.text
    return cid


async def _intake(client, h, cid: str | None, key: str | None, extra: dict | None = None) -> str:
    raw = _SPHERE.read_bytes()
    data = {"campaign_id": cid, "run_key": key} if cid else None
    r = await client.post(f"{API}/reports/intake", headers={**h, **(extra or {})},
                          files={"file": ("Test_001_report.html", raw, "text/html")}, data=data)
    assert r.status_code == 201, r.text
    return r.json()["data"]["report_id"]


@_aio
async def test_manifest_takes_extraction_and_rejects_bad_shapes(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "r1", "extraction": FULL}])
    for bad in ({"run_key": "r1", "extraction": {"states_total": 3}},                         # 요청서에 없는 열쇠
                {"run_key": "r1", "extraction": {"d3plot_states_total": 10, "d3plot_states_read": 11}},
                {"run_key": "r1", "extraction": {"peak_source": "d3plot"}},
                {"run_key": "r1", "extraction": {"fields_extracted": [{"field": PLATE, "parts": [0]}]}},
                {"run_key": "r1", "extraction": {"fields_extracted": ["  "]}},
                {"run_key": "r1", "extraction": {"fields_extracted": [{"field": PLATE, "states": "half"}]}},
                {"run_key": "r1", "extraction": {"d3plot_states_read": -1}}):
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [bad]})
        assert r.status_code == 422, (bad, r.text)
    # 보낸 칸만 맞춘다 — health 만 보내면 extraction 은 그대로
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [{"run_key": "r1", "health": {"normal_termination": True}}]})
    assert r.status_code == 200, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h)).json()["data"]
    assert d["runs"][0]["extraction"]["peak_source"] == "d3plot_full"
    assert d["runs"][0]["extraction"]["fields_extracted"] == [PLATE, STRESS]


@_aio
async def test_required_extractions_put_create_and_validation(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "x"}], required_extractions=REQ)
    d = (await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h)).json()["data"]
    assert d["required_extractions"] == REQ
    r = await client.put(f"{API}/campaigns/{cid}/required-extractions", headers=h,
                         json={"required_extractions": [{"field": " Plate ", "parts": [7, 3, 3]}]})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["required_extractions"] == [{"field": "Plate", "parts": [3, 7], "states": "all"}]
    for bad in ({"required_extractions": [{"field": PLATE}, {"field": PLATE.upper(), "states": "all"}]},   # 같은 항목 둘
                {"required_extractions": [{"field": PLATE, "states": "some"}]},
                {"required_extractions": [{"name": PLATE}]},
                {"required": []}):
        r = await client.put(f"{API}/campaigns/{cid}/required-extractions", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    r = await client.put(f"{API}/campaigns/{cid}/required-extractions", headers=h, json={"required_extractions": []})
    assert r.status_code == 200 and r.json()["data"]["required_extractions"] is None, r.text
    async with SessionLocal() as s:
        from app.models import Campaign
        assert (await s.get(Campaign, cid)).required_extractions is None
    d = (await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h)).json()["data"]
    assert d["runs"][0]["clearance"]["reasons"][0] == "required_extractions_unset"


@needs_sphere
@_aio
async def test_deletion_clearance_table(client, user):
    h = user["h"]
    runs = [
        {"run_key": "full", "extraction": FULL},
        {"run_key": "sampled", "extraction": SAMPLED},                             # 검증 사례 ② — 판 변형률장 없음
        {"run_key": "gone", "extraction": {**SAMPLED, "d3plot_retained": False, "d3plot_deleted_at": "2026-10-27T00:00:00Z"}},
        {"run_key": "noext"},
        {"run_key": "pending", "extraction": FULL},
    ]
    cid = await _campaign(client, h, runs, required_extractions=REQ)
    for k in ("full", "sampled", "gone", "noext"):
        await _intake(client, h, cid, k)
    r = await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    hd = d["header"]
    assert (hd["total"], hd["allow"], hd["hold"], hd["deleted"]) == (5, 1, 3, 1), hd
    assert hd["reasons"] == {"extraction_incomplete": 1, "extraction_missing": 1, "no_report": 1, "already_deleted": 1,
                             "extraction_lost": 1}, hd
    by = {x["run_key"]: x for x in d["runs"]}
    assert by["full"]["clearance"]["status"] == "allow"
    assert by["sampled"]["clearance"]["missing"][0]["field"] == PLATE
    assert by["sampled"]["peak_provenance"]["peak_may_be_missed"] is True
    assert by["gone"]["clearance"]["reasons"] == ["already_deleted", "extraction_lost"]
    assert by["gone"]["extraction"]["d3plot_deleted_at"].startswith("2026-10-27T00:00:00")
    assert by["pending"]["clearance"]["reasons"] == ["no_report"]
    d = (await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h, params={"status": "hold"})).json()["data"]
    assert d["matched"] == 3 and {x["run_key"] for x in d["runs"]} == {"sampled", "noext", "pending"}
    r = await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=h, params={"status": "maybe"})
    assert r.status_code == 422, r.text
    other = await _mk_user("b")
    try:
        r = await client.get(f"{API}/campaigns/{cid}/deletion-clearance", headers=other["h"])
        assert r.status_code == 404, r.text
        r = await client.put(f"{API}/campaigns/{cid}/required-extractions", headers=other["h"], json={"required_extractions": []})
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)


@needs_sphere
@_aio
async def test_report_extraction_and_peak_flags_on_peak_responses(client, user, monkeypatch):
    h = user["h"]
    monkeypatch.setattr(settings, "heax_gateway_secret", SECRET)
    cid = await _campaign(client, h, [{"run_key": "s", "extraction": SAMPLED}], required_extractions=REQ)
    rid = await _intake(client, h, cid, "s", extra=_aff(user["email"]))       # 같은 소속에 읽기 공유
    d = (await client.get(f"{API}/reports/{rid}/extraction", headers=h)).json()["data"]
    # 검증 사례 ① — 201 상태 중 40 상태만 읽은 피크
    assert d["peak_provenance"] == {"known": True, "peak_source": "d3plot_sampled", "states_read": 40, "states_total": 201,
                                    "peak_may_be_missed": True}
    assert d["campaign"]["run_key"] == "s" and d["clearance"]["status"] == "hold"
    want = d["peak_provenance"]
    # 피크를 돌려주는 응답 — 객체면 칸, 목록이면 항목마다
    seen = []
    for path, params in (("", None), ("/query", None), ("/parts", None), ("/directional", None), ("/hotspots", None),
                         ("/angle-stats", None), ("/scatter", None)):
        r = await client.get(f"{API}/reports/{rid}{path}", headers=h, params=params)
        if r.status_code == 400:            # 그 종류의 리포트에 없는 물리량 — 응답이 피크를 돌려주지 않는다
            continue
        assert r.status_code == 200, (path, r.text)
        assert r.json()["data"]["peak_provenance"] == want, path
        seen.append(path)
    assert len(seen) == 7, seen             # sphere 표본은 일곱 경로 다 피크를 돌려준다
    cases = (await client.get(f"{API}/reports/{rid}/cases", headers=h, params={"limit": 3})).json()["data"]
    assert cases and all(c["peak_provenance"] == want for c in cases)
    one = (await client.get(f"{API}/reports/{rid}/cases/{cases[0]['case_key']}", headers=h)).json()["data"]
    assert one["peak_provenance"] == want
    found = (await client.get(f"{API}/reports/{rid}/findings", headers=h)).json()["data"]
    assert all(f["peak_provenance"] == want for f in found if isinstance(f, dict))
    # 캠페인 밖 리포트 — 모른다
    lone = await _intake(client, h, None, None)
    d = (await client.get(f"{API}/reports/{lone}/extraction", headers=h)).json()["data"]
    assert d["campaign"] is None and d["extraction"] is None and d["peak_provenance"]["known"] is False
    assert (await client.get(f"{API}/reports/{lone}", headers=h)).json()["data"]["peak_provenance"]["known"] is False
    # 같은 소속 독자 — 추출 · 표지는 보되 캠페인 · 허가는 비어 있다(캠페인은 만든 사람만)
    reader = await _mk_user("r")
    try:
        r = await client.get(f"{API}/reports/{rid}/extraction", headers={**reader["h"], **_aff(reader["email"])})
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["campaign"] is None and d["clearance"] is None and d["run_key"] is None
        assert d["peak_provenance"]["peak_may_be_missed"] is True
    finally:
        await _drop_user(client, reader)
