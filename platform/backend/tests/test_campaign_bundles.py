# 보고서용 묶음(DF-13) — 항목 · 기준 줄 · 판 규칙은 순수 함수로, 받는 꼴 · REST · 출처 거슬러 가기는 진짜 앱 + DB 로 잰다
"""보고서용 묶음 출력 (2026-11-22 · 계획 docs/01-plan/features/df-report-bundles-1122.plan.md 6절).

왜 이 시험이 있나.

  보고서 · 영상 생성기가 숫자를 손으로 옮기거나 고정 경로의 숫자 JSON 하나를 읽었다 — 결과가 바뀌어도 어느 숫자가 바뀌었는지,
  숫자가 어느 리포트 · 케이스 · 지표에서 왔는지 거슬러 갈 길이 없었다. 이제 묶음은 주소 하나에 판을 쌓고(숫자가 같으면 판을 올리지
  않는다), 판마다 수치 기준 줄 · 표 · 그림 인용 · 출처 · 바뀐 숫자를 두며, 숫자마다 출처 경로가 리포트 · 케이스 · 지표에 닿는다.
  요청서의 검증 사례(보고 영상이 읽던 숫자 JSON 과 같은 값)는 같은 꼴의 합성 사례로 잰다 — 묶음의 숫자가 리포트 경로가 주는 값과 같다.
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
from sqlalchemy import delete, select, update  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import ImpactReport, Session, SessionFile, User  # noqa: E402
from app.modules.campaigns import bundles as B  # noqa: E402

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")
_aio = pytest.mark.asyncio(loop_scope="session")

GOOD = {"normal_termination": True, "energy_ratio_max": 1.01}
PROV = {"wrapper_name": "w", "wrapper_version": "1"}


# ---------------------------------------------------------------- 순수 함수

def _run(key, *, excluded=(), cases=None, media=None, report=True, **kw):
    rep = {"unit_system": "ton-mm-s", "cases": cases or [], "media": media or []} if report else None
    return {"run_key": key, "doe": kw.get("doe"), "pitch": kw.get("pitch"), "roll": kw.get("roll"),
            "config_generation": kw.get("gen"), "report_id": f"R{key}" if report else None,
            "validity": {"status": "valid", "reasons": []}, "excluded_by": list(excluded), "report": rep}


CASE = {"case_key": "roll_0/pitch_30", "max_stress": 210.5, "max_g": 1500.0, "max_disp": None, "min_safety_factor": 1.2,
        "parts_metrics": {"7": {"peak_stress": 200.0, "peak_g": 900.0}, "3": {"peak_stress": 50.0}}}


def _camp(runs, cid="C1"):
    return [{"campaign_id": cid, "name": "camp", "thresholds_ref": "thr-x", "runs": runs}]


def test_items_tables_and_basis():
    spec = {"tables": [{"kind": "runs", "metrics": ["pitch", "roll"], "parts": None},
                       {"kind": "case_metrics", "metrics": list(B.CASE_DEFAULT), "parts": None},
                       {"kind": "part_peaks", "metrics": ["peak_stress", "peak_g"], "parts": [7]}],
            "figures": None, "include_invalid": False}
    runs = [_run("a", cases=[CASE], pitch=30.0, roll=0.0, gen="g1"), _run("b", excluded=["superseded"], cases=[CASE]),
            _run("c", excluded=["no_report"], report=False)]
    got = B.build(campaigns=_camp(runs), spec=spec)
    keys = {i["item_key"]: i for i in got["items"]}
    # 런 표 둘 · 케이스 롤업 셋(max_disp 는 값이 없어 항목이 없다) · 파트 7 의 피크 둘 — 제외된 런 b 는 없다
    assert set(keys) == {"runs/C1/a/pitch", "runs/C1/a/roll",
                         "case_metrics/C1/a/roll_0%2Fpitch_30/max_stress", "case_metrics/C1/a/roll_0%2Fpitch_30/max_g",
                         "case_metrics/C1/a/roll_0%2Fpitch_30/min_safety_factor",
                         "part_peaks/C1/a/roll_0%2Fpitch_30/7/peak_stress", "part_peaks/C1/a/roll_0%2Fpitch_30/7/peak_g"}
    it = keys["case_metrics/C1/a/roll_0%2Fpitch_30/max_stress"]
    assert (it["value"], it["unit"]) == (210.5, "MPa")
    assert B.parse_source(it["source_path"]) == {"report_id": "Ra", "case_key": "roll_0/pitch_30", "metric": "max_stress"}
    assert B.parse_source(keys["part_peaks/C1/a/roll_0%2Fpitch_30/7/peak_g"]["source_path"]) == \
        {"report_id": "Ra", "case_key": "roll_0/pitch_30", "part_id": 7, "metric": "peak_g"}
    assert keys["runs/C1/a/pitch"]["unit"] == "deg"
    assert B.parse_source(keys["runs/C1/a/pitch"]["source_path"]) == {"campaign_id": "C1", "run_key": "a", "metric": "pitch"}
    b = got["basis"]["campaigns"][0]
    assert (b["total"], b["included"], b["valid_runs"]) == (3, 1, 1) and b["excluded_by"] == {"superseded": 1, "no_report": 1}
    assert b["generations"] == [{"config_generation": "g1", "runs": 1}]
    assert got["basis"]["line"].startswith("camp — 유효 1 / 전체 3 · 제외 no_report 1 · superseded 1")
    assert got["basis"]["units"]["unit_systems"] == ["ton-mm-s"] and got["basis"]["items"] == 7
    rows = got["tables"][2]["rows"]
    assert [r["part_id"] for r in rows] == [7] and rows[0]["peak_g"] == 900.0
    # include_invalid — 리포트가 있는 제외 런은 넣고, 리포트가 없는 런은 넣을 것이 없다
    got2 = B.build(campaigns=_camp(runs), spec={**spec, "include_invalid": True})
    assert got2["basis"]["campaigns"][0]["included"] == 2 and "제외 까닭이 있는 런도 넣음" in got2["basis"]["line"]


def test_figures_cite_report_media_without_video():
    media = [{"path": "fig/a.png", "file_id": 1, "kind": "image", "role": "contour", "case_key": "k", "sha256": "aa"},
             {"path": "fig/b.jpg", "file_id": 2, "kind": "image", "role": "contour", "sha256": "bb"},
             {"path": "mov/c.mp4", "file_id": 3, "kind": "video", "role": "contour", "sha256": "cc"},
             {"path": "fig/d.png", "file_id": 4, "kind": "image", "role": "plot", "sha256": "dd"}]
    spec = {"tables": [{"kind": "runs", "metrics": ["pitch"], "parts": None}], "include_invalid": False,
            "figures": {"roles": ["contour"], "exts": ["png", "svg"]}}
    got = B.build(campaigns=_camp([_run("a", media=media)]), spec=spec)
    assert [(f["file_id"], f["sha256"], f["ext"]) for f in got["figures"]] == [(1, "aa", "png")]
    got = B.build(campaigns=_camp([_run("a", media=media)]), spec={**spec, "figures": {"roles": None, "exts": ["png", "jpg", "mp4"]}})
    assert [f["file_id"] for f in got["figures"]] == [1, 2, 4]          # 영상은 확장자를 주어도 싣지 않는다
    assert got["sources"]["figures"] == [{"report_id": "Ra", "file_id": i, "sha256": h} for i, h in ((1, "aa"), (2, "bb"), (4, "dd"))]


def test_same_and_diff():
    spec = {"tables": [{"kind": "case_metrics", "metrics": ["max_stress", "max_g"], "parts": None}], "figures": None,
            "include_invalid": False}
    a = B.build(campaigns=_camp([_run("a", cases=[CASE])]), spec=spec)
    assert B.same(a, B.build(campaigns=_camp([_run("a", cases=[CASE])]), spec=spec))
    c2 = {**CASE, "max_stress": 300.0, "max_g": None}
    b = B.build(campaigns=_camp([_run("a", cases=[c2]), _run("n", cases=[CASE])]), spec=spec)
    assert not B.same(a, b)
    d = B.diff(a["items"], b["items"])
    assert d["counts"] == {"added": 2, "removed": 1, "changed": 1}
    assert d["changed"][0]["old"] == 210.5 and d["changed"][0]["new"] == 300.0 and d["changed"][0]["unit"] == "MPa"
    assert d["removed"][0]["item_key"].endswith("/max_g")
    # 기준 줄만 바뀌어도(제외 런이 늘었다) 같지 않다 — 숫자가 같아도 n / N 이 다르다
    c = B.build(campaigns=_camp([_run("a", cases=[CASE]), _run("x", excluded=["superseded"], cases=[CASE])]), spec=spec)
    assert B.diff(a["items"], c["items"])["counts"] == {"added": 0, "removed": 0, "changed": 0} and not B.same(a, c)


def test_items_cap(monkeypatch):
    monkeypatch.setattr(B, "ITEMS_MAX", 2)
    spec = {"tables": [{"kind": "case_metrics", "metrics": list(B.CASE_DEFAULT), "parts": None}], "figures": None,
            "include_invalid": False}
    with pytest.raises(B.TooMany):
        B.build(campaigns=_camp([_run("a", cases=[CASE])]), spec=spec)


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
    email = f"dfbun_{tag}_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash="x", display_name="DFB", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        uid = u.id
    from app.shared import security
    return {"id": uid, "email": email, "h": {"Authorization": f"Bearer {security.create_access_token(uid)}"}}


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


async def _campaign(client, h, runs) -> str:
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"bun-{ulid.new().str.lower()}"})
    assert r.status_code == 201, r.text
    cid = r.json()["data"]["campaign_id"]
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": list(runs)})
    assert r.status_code == 200, r.text
    return cid


async def _intake(client, h, cid: str, key: str) -> str:
    r = await client.post(f"{API}/reports/intake", headers=h,
                          files={"file": ("Test_001_report.html", _SPHERE.read_bytes(), "text/html")},
                          data={"campaign_id": cid, "run_key": key})
    assert r.status_code == 201, r.text
    return r.json()["data"]["report_id"]


SPEC = {"tables": [{"kind": "runs"}, {"kind": "case_metrics", "metrics": ["max_stress", "max_g"]},
                   {"kind": "part_peaks", "metrics": ["peak_stress"]}],
        "figures": {"roles": ["contour"]}}


@_aio
async def test_spec_validation_and_ownership(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "a"}])
    for bad in ({"campaign_ids": [cid], "spec": {"tables": []}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "angles"}]}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "case_metrics", "metrics": ["peak_stress"]}]}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs", "parts": [1]}]}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}, {"kind": "runs"}]}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}], "figure": {}}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}], "figures": {"exts": ["mp4"]}}},
                {"campaign_ids": [], "spec": {"tables": [{"kind": "runs"}]}},
                {"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}]}, "extra": 1}):
        r = await client.post(f"{API}/bundles", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    other = await _mk_user("b")
    try:
        r = await client.post(f"{API}/bundles", headers=other["h"], json={"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}]}})
        assert r.status_code == 404, r.text
        r = await client.post(f"{API}/bundles", headers=h, json={"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}]}})
        assert r.status_code == 201, r.text
        bid = r.json()["data"]["bundle_id"]
        for path in (f"/bundles/{bid}", f"/bundles/{bid}/diff", f"/campaigns/{cid}/bundles/latest"):
            r = await client.get(f"{API}{path}", headers=other["h"])
            assert r.status_code == 404, (path, r.text)
        r = await client.post(f"{API}/bundles", headers=other["h"],
                              json={"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}]}, "bundle_id": bid})
        assert r.status_code == 404, r.text
        r = await client.post(f"{API}/bundles", headers=h,
                              json={"campaign_ids": [cid], "spec": {"tables": [{"kind": "case_metrics"}]}, "bundle_id": bid})
        assert r.status_code == 422 and "한 질문" in r.text, r.text           # 주소는 한 명세
        r = await client.get(f"{API}/bundles/{bid}/diff", headers=h)
        assert r.status_code == 422, r.text                                     # 판이 하나뿐
        empty = await _campaign(client, h, [{"run_key": "z"}])                   # 묶음이 없는 캠페인의 마지막 판은 없다
        r = await client.get(f"{API}/campaigns/{empty}/bundles/latest", headers=h)
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)


@needs_sphere
@_aio
async def test_versions_numbers_and_provenance(client, user):
    h = user["h"]
    runs = [{"run_key": k, "pitch": p, "roll": 0.0, "provenance": PROV, "health": GOOD, "config_generation": "g1"}
            for k, p in (("r1", 0.0), ("r2", 30.0))]
    cid = await _campaign(client, h, runs)
    rid1 = await _intake(client, h, cid, "r1")
    rid2 = await _intake(client, h, cid, "r2")
    # 그림 — 리포트 원본 파일을 contour 그림으로 인용해 본다(매체는 번들로 오지만, 인용 · sha256 만 잰다)
    async with SessionLocal() as s:
        rep = await s.get(ImpactReport, rid1)
        f = await s.get(SessionFile, rep.source_file_id)
        want_sha = f.sha256
        await s.execute(update(ImpactReport).where(ImpactReport.id == rid1).values(media=[
            {"path": "fig/a.png", "file_id": f.id, "kind": "image", "role": "contour", "case_key": None, "bytes": f.size_bytes},
            {"path": "mov/a.mp4", "file_id": f.id, "kind": "video", "role": "contour", "case_key": None, "bytes": f.size_bytes}]))
        await s.commit()
    r = await client.post(f"{API}/bundles", headers=h, json={"campaign_ids": [cid], "spec": SPEC, "label": "보고 1"})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    bid, n1 = d["bundle_id"], d["counts"]["items"]
    assert d["version"] == 1 and not d["unchanged"] and d["changes_counts"] is None and n1 > 0
    assert d["citation"] == {"source_platform": "dynaforge", "source_kind": "dynaforge_bundle", "source_id": bid,
                             "source_version": 1, "scope": {"campaign_ids": [cid]}}
    assert d["basis"]["campaigns"][0]["line"].endswith("유효 2 / 전체 2") and d["counts"]["figures"] == 1
    # 같은 숫자로 다시 지으면 판 그대로(200 · unchanged)
    r = await client.post(f"{API}/bundles", headers=h, json={"campaign_ids": [cid], "spec": SPEC, "bundle_id": bid})
    assert r.status_code == 200 and r.json()["data"]["unchanged"] is True and r.json()["data"]["version"] == 1, r.text
    # 판 읽기 · 그림 sha256 · 항목 쪽
    v = (await client.get(f"{API}/bundles/{bid}", headers=h, params={"items": True, "limit": 20000})).json()["data"]
    assert v["latest_version"] == 1 and v["label"] == "보고 1" and v["figures"][0]["sha256"] == want_sha
    assert v["items"]["total"] == n1 and len(v["items"]["rows"]) == n1
    # 검증 사례(합성) — 묶음의 케이스 숫자가 리포트 경로가 주는 값과 같고, 출처 경로가 그 리포트 · 케이스 · 지표에 닿는다
    cases = (await client.get(f"{API}/reports/{rid2}/cases", headers=h, params={"limit": 500})).json()["data"]
    by_case = {c["case_key"]: c for c in cases}
    seen = 0
    for it in v["items"]["rows"]:
        src = it["source"]
        if it["item_key"].startswith("case_metrics/") and src["report_id"] == rid2:
            want = by_case[src["case_key"]]["max_stress" if src["metric"] == "max_stress" else "max_g"]
            assert it["value"] == pytest.approx(want), it
            seen += 1
    assert seen > 0
    # 런 하나를 대체하면 다음 판 — 그 런의 숫자가 빠지고 기준 줄이 바뀐다
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [{"run_key": "r2", "superseded_by": "r1"}]})
    assert r.status_code == 200, r.text
    r = await client.post(f"{API}/bundles", headers=h, json={"campaign_ids": [cid], "spec": SPEC, "bundle_id": bid})
    assert r.status_code == 201, r.text
    d2 = r.json()["data"]
    assert d2["version"] == 2 and d2["changes_counts"]["removed"] > 0 and d2["changes_counts"]["added"] == 0
    assert d2["label"] == "보고 1" and "superseded 1" in d2["basis"]["line"]
    df = (await client.get(f"{API}/bundles/{bid}/diff", headers=h)).json()["data"]
    assert (df["from_version"], df["to_version"]) == (1, 2) and df["counts"] == d2["changes_counts"]
    assert all(x["item_key"].split("/")[2] == "r2" or x["item_key"].startswith("runs/") for x in df["removed"])
    # 리포트 값을 바꾸면 값 바뀜(바뀐 숫자 목록에 옛 값 · 새 값)
    async with SessionLocal() as s:
        from app.models import ImpactCase
        c0 = (await s.execute(select(ImpactCase).where(ImpactCase.report_id == rid1).order_by(ImpactCase.id).limit(1))).scalar_one()
        old, key = c0.max_stress, c0.case_key
        c0.max_stress = (old or 0.0) + 1.0
        await s.commit()
    d3 = (await client.post(f"{API}/bundles", headers=h, json={"campaign_ids": [cid], "spec": SPEC, "bundle_id": bid})).json()["data"]
    assert d3["version"] == 3 and d3["changes_counts"] == {"added": 0, "removed": 0, "changed": 1}, d3
    ch = (await client.get(f"{API}/bundles/{bid}", headers=h)).json()["data"]["changes"]["changed"][0]
    assert ch["old"] == pytest.approx(old) and ch["new"] == pytest.approx(old + 1.0) and f"case:{key}" in ch["source_path"].replace("%2F", "/")
    # 두 판을 골라 견준다 · 캠페인의 마지막 판
    df = (await client.get(f"{API}/bundles/{bid}/diff", headers=h, params={"from": 1, "to": 3})).json()["data"]
    assert df["counts"]["changed"] == 1 and df["counts"]["removed"] == d2["changes_counts"]["removed"]
    last = (await client.get(f"{API}/campaigns/{cid}/bundles/latest", headers=h)).json()["data"]
    assert (last["bundle_id"], last["version"]) == (bid, 3) and [x["version"] for x in last["versions"]] == [1, 2, 3]
    one = (await client.get(f"{API}/bundles/{bid}", headers=h, params={"version": 1})).json()["data"]
    assert one["version"] == 1 and one["changes"] is None
    r = await client.get(f"{API}/bundles/{bid}", headers=h, params={"version": 9})
    assert r.status_code == 404, r.text


@needs_sphere
@_aio
async def test_as_of_excludes_later_reports(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "early", "provenance": PROV, "health": GOOD},
                                      {"run_key": "late", "provenance": PROV, "health": GOOD}])
    await _intake(client, h, cid, "early")
    async with SessionLocal() as s:
        from app.models import CampaignRun
        t = (await s.execute(select(CampaignRun.ingested_at).where(CampaignRun.campaign_id == cid,
                                                                   CampaignRun.run_key == "early"))).scalar_one()
    await _intake(client, h, cid, "late")
    async with SessionLocal() as s:
        from app.models import CampaignRun
        await s.execute(update(CampaignRun).where(CampaignRun.campaign_id == cid, CampaignRun.run_key == "late")
                        .values(ingested_at=t.replace(year=t.year + 1)))
        await s.commit()
    r = await client.post(f"{API}/bundles", headers=h,
                          json={"campaign_ids": [cid], "spec": {"tables": [{"kind": "runs"}]}, "as_of": t.isoformat()})
    assert r.status_code == 201, r.text
    b = r.json()["data"]["basis"]["campaigns"][0]
    assert (b["total"], b["included"]) == (2, 1) and b["excluded_by"] == {"after_as_of": 1}, b
