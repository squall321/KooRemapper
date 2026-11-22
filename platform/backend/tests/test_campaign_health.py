# 캠페인 런 출처 · 유효성(DF-02 · DF-03) — 판정 규칙 · 문턱 묶음 · 거르기 · 받는 꼴 · REST 넷을 진짜 앱 + DB 로 잰다
"""런 출처 · 유효성 (2026-11-22 · 계획 docs/01-plan/features/df-provenance-health-1122.plan.md 6절).

왜 이 시험이 있나.

  한 캠페인에 옛 설정 런과 새 설정 런이 섞이고, 스케줄러는 「완료」 라 했지만 해석이 중간에 멈춘 런 · 첫 운동에너지가 0 인 런 ·
  NaN 으로 바뀐 런 · 잘린 JSON 이 통계에 들어갔다. 이제 런 목록이 출처 · 설정 세대 · 대체 · 건강 수치를 받고, 읽을 때 캠페인의
  문턱으로 판정해 기본 통계에서 뺀다. 판정 규칙은 순수 함수로, 나머지는 진짜 ASGI 앱을 실제 DB 에 대고 잰다.
"""
import json
import math
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
from app.modules.campaigns import health as H  # noqa: E402
from app.shared import security  # noqa: E402

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")
_aio = pytest.mark.asyncio(loop_scope="session")

# 판정에 쓰는 「정상 런」 — 하나씩 바꿔 까닭을 본다
GOOD = {
    "normal_termination": True, "scheduler_state": "COMPLETED", "energy_ratio_max": 1.01, "hg_over_ie_max": 0.03,
    "added_mass_pct_device": 0.2, "added_mass_pct_total": 0.01, "ke0_measured": 1000.0, "ke0_expected": 1000.0,
    "contact_energy_min_mJ": -5.0, "nan_onset_ms": None, "json_complete": True,
}


def _judge(**over):
    return H.judge({**GOOD, **over}, H.effective(None), has_report=True)


# ---------------------------------------------------------------- 판정 규칙(순수)

def test_good_run_is_valid():
    assert _judge() == {"status": "valid", "reasons": []}


@pytest.mark.parametrize("over, status, reason", [
    ({"normal_termination": False}, "invalid", "abnormal_termination"),       # 스케줄러는 COMPLETED · d3hsp 는 비정상
    ({"normal_termination": None}, "invalid", "termination_unknown"),          # Slurm 상태만으로 valid 금지
    ({"ke0_measured": 0.0}, "invalid", "ke0_zero"),                            # 첫 KE 0
    ({"nan_onset_ms": 2.37}, "invalid", "nan"),                                # NaN 시작 시각
    ({"json_complete": False}, "invalid", "json_incomplete"),                  # 잘린 JSON
    ({"ke0_measured": 600.0}, "warn", "ke0_mismatch"),                         # 몸통이 빠진 런(기대의 60 %)
    ({"contact_energy_min_mJ": -150.0, "energy_ratio_max": 1.018}, "warn", "contact_energy"),   # 에너지비만으론 정상
    ({"added_mass_pct_device": 0.66, "added_mass_pct_total": 0.01}, "warn", "added_mass"),     # 낙하판에 희석된 전체 값
    ({"hg_over_ie_max": 0.12}, "warn", "hourglass"),
    ({"energy_ratio_max": 1.06}, "warn", "energy_ratio"),
])
def test_each_rule(over, status, reason):
    got = _judge(**over)
    assert got["status"] == status and reason in got["reasons"], got


def test_boundaries_follow_the_request_wording():
    """에너지비 ≤ 1.05 · HG/IE < 10 % · 추가 질량 0.5 % 넘으면 — 경계값 자체는 문턱 안쪽이다(HG/IE 는 10 % 부터 warn)."""
    assert _judge(energy_ratio_max=1.05)["status"] == "valid"
    assert _judge(added_mass_pct_device=0.5)["status"] == "valid"
    assert "hourglass" in _judge(hg_over_ie_max=0.10)["reasons"]
    assert _judge(hg_over_ie_max=0.0999)["status"] == "valid"
    assert _judge(ke0_measured=1100.0)["status"] == "valid"            # 상대 차이 10 % 는 안쪽
    assert "ke0_mismatch" in _judge(ke0_measured=1100.1)["reasons"]


def test_device_mass_wins_over_total_and_total_is_used_alone():
    assert "added_mass" not in _judge(added_mass_pct_device=0.1, added_mass_pct_total=3.0)["reasons"]
    assert "added_mass" in _judge(added_mass_pct_device=None, added_mass_pct_total=0.7)["reasons"]


def test_sliding_energy_has_no_threshold_and_missing_numbers_are_not_judged():
    """미끄럼 에너지는 칸도 문턱도 없다 — 수치가 빠진 항목은 판정하지 않는다(정상 종료만 있어도 valid)."""
    only = {"normal_termination": True}
    assert H.judge(only, H.effective(None), has_report=True) == {"status": "valid", "reasons": []}


def test_invalid_wins_and_all_reasons_are_listed():
    got = _judge(normal_termination=False, hg_over_ie_max=0.2, nan_onset_ms=1.0)
    assert got["status"] == "invalid"
    assert set(got["reasons"]) == {"abnormal_termination", "nan", "hourglass"}


def test_missing_health_and_missing_report():
    assert H.judge(None, H.effective(None), has_report=True) == {"status": "invalid", "reasons": ["health_missing"]}
    got = H.judge(GOOD, H.effective(None), has_report=False)
    assert got["status"] == "invalid" and got["reasons"][0] == "no_report"


def test_thresholds_bundle_and_ref():
    d = H.effective(None)
    assert d == {"energy_ratio_max": 1.05, "hg_over_ie_max": 0.10, "added_mass_pct_max": 0.5, "ke0_rel_tol": 0.10,
                 "contact_energy_min_mJ": -100.0}
    ref = H.ref(d)
    assert ref.startswith("thr-") and len(ref) == 16 and ref == H.ref(dict(reversed(list(d.items()))))
    loose = H.effective({"hg_over_ie_max": 0.15})
    assert loose["hg_over_ie_max"] == 0.15 and loose["energy_ratio_max"] == 1.05 and H.ref(loose) != ref
    assert H.judge({**GOOD, "hg_over_ie_max": 0.12}, loose, has_report=True)["status"] == "valid"


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


async def _mk_user(tag: str, *, admin: bool = False) -> dict:
    email = f"dfhealth_{tag}_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash=security.hash_password("password123"), display_name="DFH",
                 is_active=True, is_system_admin=admin)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        uid = u.id
    return {"id": uid, "email": email, "h": {"Authorization": f"Bearer {security.create_access_token(uid)}"}}


AFF, SECRET = "DFHG", "dfh-gateway-secret"


def _aff(email: str) -> dict:
    """게이트웨이가 찍은 소속 증명(app/shared/affiliation.py 의 v1 꼴) — 같은 소속으로 리포트를 읽는 사람을 만든다."""
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


async def _intake(client, h, cid: str, key: str, extra: dict | None = None) -> str:
    raw = _SPHERE.read_bytes()
    r = await client.post(f"{API}/reports/intake", headers={**h, **(extra or {})},
                          files={"file": ("Test_001_report.html", raw, "text/html")}, data={"campaign_id": cid, "run_key": key})
    assert r.status_code == 201, r.text
    return r.json()["data"]["report_id"]


def _prov(gen: str) -> dict:
    return {"wrapper_name": "wrap", "wrapper_version": "4", "deck_sha256": "ab" * 32, "include_sha256": ["cd" * 32],
            "solver": {"version": "R16", "parallel": "MPP", "cores": 32}, "deep_report_tool_commit": "abc1234",
            "deep_report_flags": ["--impact"], "submitted_at": "2026-11-13T09:00:00Z", "sif_version": "v51"}


@_aio
async def test_manifest_takes_provenance_and_health_and_rejects_unknown_keys(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "r1", "provenance": _prov("new"), "config_generation": "new",
                                       "health": GOOD}])
    for bad in ({"run_key": "r1", "provenance": {"wrapper": "x"}},           # 요청서에 없는 열쇠
                {"run_key": "r1", "health": {"energy_ratio": 1.0}},
                {"run_key": "r1", "health": {"normal_termination": True, "energy_ratio_max": "high"}},
                {"run_key": "r1", "config_generation": "x" * 65}):
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [bad]})
        assert r.status_code == 422, (bad, r.text)
    raw = json.dumps({"runs": [{"run_key": "r1", "health": {"energy_ratio_max": math.inf}}]})   # Infinity
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers={**h, "Content-Type": "application/json"}, content=raw)
    assert r.status_code == 422, r.text
    # 보낸 칸만 맞춘다 — health 만 보내면 provenance 는 그대로, null 은 비운다
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h,
                          json={"runs": [{"run_key": "r1", "health": {**GOOD, "hg_over_ie_max": 0.2}}]})
    assert r.status_code == 200 and r.json()["data"]["updated"] == 1, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/provenance", headers=h)).json()["data"]
    assert d["runs"][0]["provenance"]["wrapper_name"] == "wrap" and d["runs"][0]["config_generation"] == "new"
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [{"run_key": "r1", "provenance": None}]})
    assert r.status_code == 200, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/provenance", headers=h)).json()["data"]
    assert d["runs"][0]["provenance"] is None and d["counts"]["provenance_missing"] == 1


@_aio
async def test_superseded_by_must_name_another_run_of_the_campaign(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "a"}, {"run_key": "b"}])
    for runs in ([{"run_key": "a", "superseded_by": "zzz"}],                         # 목록에 없다
                 [{"run_key": "a", "superseded_by": "a"}],                           # 자기 자신
                 [{"run_key": "a", "superseded_by": "b"}, {"run_key": "b", "superseded_by": "a"}]):   # 고리
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": runs})
        assert r.status_code == 422, (runs, r.text)
    # 같은 요청 안에서 새로 더하는 런은 가리켜도 된다
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h,
                          json={"runs": [{"run_key": "a", "superseded_by": "c"}, {"run_key": "c"}]})
    assert r.status_code == 200, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/provenance", headers=h)).json()["data"]
    assert d["counts"]["superseded"] == 1 and d["counts"]["listed"] == 3


@_aio
async def test_provenance_generations_and_mixed_flag(client, user):
    h = user["h"]
    runs = [{"run_key": f"o{i}", "provenance": _prov("old"), "config_generation": "old"} for i in range(3)]
    runs += [{"run_key": f"n{i}", "provenance": _prov("new"), "config_generation": "new"} for i in range(2)]
    runs += [{"run_key": "bare"}]
    cid = await _campaign(client, h, runs)
    d = (await client.get(f"{API}/campaigns/{cid}/provenance", headers=h)).json()["data"]
    gens = {g["config_generation"]: g["runs"] for g in d["generations"]}
    assert gens == {"old": 3, "new": 2, None: 1} and d["mixed_config"] is True, d
    assert d["counts"] == {"listed": 6, "with_provenance": 5, "provenance_missing": 1, "superseded": 0}
    d = (await client.get(f"{API}/campaigns/{cid}/provenance", headers=h, params={"config_generation": "new"})).json()["data"]
    assert d["matched"] == 2 and {r["run_key"] for r in d["runs"]} == {"n0", "n1"}
    one = await _campaign(client, h, [{"run_key": "x", "provenance": _prov("g"), "config_generation": "g"}])
    assert (await client.get(f"{API}/campaigns/{one}/provenance", headers=h)).json()["data"]["mixed_config"] is False


@needs_sphere
@_aio
async def test_health_table_judges_filters_and_counts(client, user):
    h = user["h"]
    runs = [
        {"run_key": "ok", "provenance": _prov("new"), "config_generation": "new", "health": GOOD},
        {"run_key": "hg", "provenance": _prov("new"), "config_generation": "new", "health": {**GOOD, "hg_over_ie_max": 0.12}},
        {"run_key": "dead", "provenance": _prov("new"), "config_generation": "new",
         "health": {**GOOD, "normal_termination": False, "scheduler_state": "COMPLETED"}},
        {"run_key": "nohealth", "provenance": _prov("new"), "config_generation": "new"},
        {"run_key": "old", "provenance": _prov("old"), "config_generation": "old", "health": GOOD, "superseded_by": "ok"},
        {"run_key": "noprov", "health": GOOD},
        {"run_key": "pending", "provenance": _prov("new"), "health": GOOD},
    ]
    cid = await _campaign(client, h, runs)
    for k in ("ok", "hg", "dead", "nohealth", "old", "noprov"):
        await _intake(client, h, cid, k)
    r = await client.get(f"{API}/campaigns/{cid}/health", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    hd = d["header"]
    assert hd["total"] == 7 and hd["included"] == 2 and hd["excluded"] == 5, hd
    assert hd["excluded_by"] == {"abnormal_termination": 1, "health_missing": 1, "superseded": 1,
                                 "provenance_missing": 1, "no_report": 1}, hd
    assert hd["line"].startswith("유효 2 / 전체 7"), hd["line"]
    assert {r["run_key"] for r in d["runs"]} == {"ok", "hg"}                    # 기본은 넣는 런만
    by = {r["run_key"]: r for r in d["runs"]}
    assert by["hg"]["validity"] == {"status": "warn", "reasons": ["hourglass"]}
    assert d["thresholds"]["ref"] == by["ok"]["health"]["thresholds_ref"]
    assert d["thresholds"]["values"]["energy_ratio_max"] == 1.05 and d["thresholds"]["changed"] == []
    d = (await client.get(f"{API}/campaigns/{cid}/health", headers=h, params={"include_invalid": "true"})).json()["data"]
    by = {r["run_key"]: r for r in d["runs"]}
    assert len(by) == 7
    assert by["dead"]["validity"]["status"] == "invalid" and by["dead"]["health"]["scheduler_state"] == "COMPLETED"
    assert by["old"]["excluded_by"] == ["superseded"] and by["old"]["validity"]["status"] == "valid"
    assert by["noprov"]["excluded_by"] == ["provenance_missing"]
    assert by["pending"]["validity"]["reasons"][0] == "no_report"
    # 문턱을 바꾸면 그 자리에서 다시 판정된다
    r = await client.put(f"{API}/campaigns/{cid}/health-thresholds", headers=h, json={"hg_over_ie_max": 0.15})
    assert r.status_code == 200, r.text
    t = r.json()["data"]["thresholds"]
    assert t["values"]["hg_over_ie_max"] == 0.15 and t["changed"] == ["hg_over_ie_max"]
    async with SessionLocal() as s:     # 바꾼 열쇠만 둔다 — 기본값이 바뀌면 나머지 열쇠는 새 기본값을 따른다
        from app.models import Campaign
        assert (await s.get(Campaign, cid)).health_thresholds == {"hg_over_ie_max": 0.15}
    d = (await client.get(f"{API}/campaigns/{cid}/health", headers=h)).json()["data"]
    by = {r["run_key"]: r for r in d["runs"]}
    assert by["hg"]["validity"]["status"] == "valid" and d["thresholds"]["ref"] == t["ref"]
    for bad in ({"hourglass": 0.1}, {"hg_over_ie_max": "x"}, {"energy_ratio_max": None, "zzz": 1}):
        r = await client.put(f"{API}/campaigns/{cid}/health-thresholds", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    r = await client.put(f"{API}/campaigns/{cid}/health-thresholds", headers=h, json={})   # 빈 몸 = 기본값으로
    assert r.json()["data"]["thresholds"]["changed"] == []


@_aio
async def test_create_campaign_takes_thresholds(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "x"}], health_thresholds={"energy_ratio_max": 1.1})
    d = (await client.get(f"{API}/campaigns/{cid}/health", headers=h)).json()["data"]
    assert d["thresholds"]["values"]["energy_ratio_max"] == 1.1 and d["thresholds"]["changed"] == ["energy_ratio_max"]
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"c-{ulid.new().str.lower()}",
                                                               "health_thresholds": {"nope": 1}})
    assert r.status_code == 422, r.text


@needs_sphere
@_aio
async def test_report_health_and_find_reports_by_generation(client, user, monkeypatch):
    h = user["h"]
    monkeypatch.setattr(settings, "heax_gateway_secret", SECRET)
    cid = await _campaign(client, h, [
        {"run_key": "g1", "provenance": _prov("g1"), "config_generation": "gen-1", "health": {**GOOD, "nan_onset_ms": 2.37}},
        {"run_key": "g2", "provenance": _prov("g2"), "config_generation": "gen-2", "health": GOOD},
    ])
    r1 = await _intake(client, h, cid, "g1", extra=_aff(user["email"]))      # 같은 소속에 읽기 공유
    r2 = await _intake(client, h, cid, "g2")
    d = (await client.get(f"{API}/reports/{r1}/health", headers=h)).json()["data"]
    assert d["campaign"]["campaign_id"] == cid and d["campaign"]["run_key"] == "g1"
    assert d["validity"] == {"status": "invalid", "reasons": ["nan"]} and d["health"]["nan_onset_ms"] == 2.37
    # 캠페인 밖 리포트
    raw = _SPHERE.read_bytes()
    r = await client.post(f"{API}/reports/intake", headers=h, files={"file": ("Test_001_report.html", raw, "text/html")})
    lone = r.json()["data"]["report_id"]
    d = (await client.get(f"{API}/reports/{lone}/health", headers=h)).json()["data"]
    assert d["campaign"] is None and d["validity"] == {"status": "invalid", "reasons": ["health_missing"]}
    # 세대로 거르기 — 그 세대의 런에 묶인 리포트만
    d = (await client.get(f"{API}/reports", headers=h, params={"config_generation": "gen-2"})).json()["data"]
    ids = {x["id"] for x in (d["items"] if isinstance(d, dict) else d)}
    assert ids == {r2}, ids
    # 같은 소속 독자는 리포트 건강을 읽되 캠페인 칸은 비어 있다(캠페인은 만든 사람만)
    reader = await _mk_user("r")
    admin = await _mk_user("adm", admin=True)
    other = await _mk_user("b")
    try:
        r = await client.get(f"{API}/reports/{r1}/health", headers={**reader["h"], **_aff(reader["email"])})
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["campaign"] is None and d["run_key"] is None and d["validity"]["reasons"] == ["nan"]
        # 관리자는 모든 리포트를 검색하지만 세대 거르기는 제 캠페인만 센다
        d = (await client.get(f"{API}/reports", headers=admin["h"], params={"config_generation": "gen-2"})).json()["data"]
        assert not (d["items"] if isinstance(d, dict) else d)
        d = (await client.get(f"{API}/reports", headers=other["h"], params={"config_generation": "gen-2"})).json()["data"]
        assert not (d["items"] if isinstance(d, dict) else d)
        r = await client.get(f"{API}/reports/{r1}/health", headers=other["h"])
        assert r.status_code in (403, 404), r.text
        r = await client.get(f"{API}/campaigns/{cid}/health", headers=other["h"])
        assert r.status_code == 404, r.text
    finally:
        for u in (other, reader, admin):
            await _drop_user(client, u)
