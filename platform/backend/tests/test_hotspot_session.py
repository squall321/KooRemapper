# 핫스팟 자리(DF-07) · 덱 세션 관리(DF-15) — 묶기 · 이동값 · bbox 포함률 · 제목 바꾸기는 순수 함수로, REST 는 진짜 앱 + DB 로 잰다
"""핫스팟 자리 · 덱 세션 관리 (2026-11-22 · 계획 docs/01-plan/features/df-hotspot-session-1122.plan.md 5절).

왜 이 시험이 있나.

  리포트의 핫스팟 군집 좌표는 결과(d3plot) 틀이라 덱 틀과 어긋난다(요청서 함정 줄 — 보정 없이 bbox 포함률 3.2 %). 이동값을 캠페인에 두고 덱
  틀로 옮겨 각도 사이 같은 자리를 묶는다. 리스크 앱이 덱 세션을 근거로 쓸 때 덱 판과 CAD 판이 엇갈린 일이 있었다 — 세션 응답에 환경 · 판 ·
  CAD 연결 · 경고를 싣는다. 파트 이름을 바꿀 길이 없었다 — *PART 제목 줄만 제자리에서 바꾼다.
"""
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
from sqlalchemy import delete, select, update  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import ImpactReport, Session, SessionFile, User  # noqa: E402
from app.modules.campaigns import hotspots as HS  # noqa: E402
from app.modules.sessions import part_title as PT  # noqa: E402

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")
_aio = pytest.mark.asyncio(loop_scope="session")
GOOD = {"normal_termination": True}
PROV = {"wrapper_name": "w"}


# ---------------------------------------------------------------- 순수 함수

def _it(run, case, c, s, r=1.0):
    return {"run_key": run, "case_key": case, "doe": run, "report_id": "R" + run, "center": c, "stress_max": s, "radius_enclosing": r}


def test_sites_group_by_radius_after_offset():
    items = [_it("a", "x", [0, 0, 0], 100), _it("b", "x", [1, 0, 0], -150), _it("a", "y", [0.5, 0.5, 0], 90),
             _it("c", "x", [20, 0, 0], 50), _it("d", "x", [None, 0, 0], 999)]
    assert HS.default_radius(items) == pytest.approx(2.0)
    s = HS.sites(items, (10.0, 0.0, -1.0), 3.0)
    assert len(s) == 2                                          # 중심이 깨진 군집은 뺀다
    a, b = s
    assert (a["n_clusters"], a["n_angles"]) == (3, 3) and b["n_angles"] == 1
    assert a["representative"]["stress_max"] == -150 and a["representative"]["run_key"] == "b"   # |응력| 최대
    assert a["center_deck"] == pytest.approx([10.5, 0.5 / 3, -1.0], abs=1e-6)                     # 군집 중심 평균 + 이동값(6 자리)
    assert b["center_deck"] == [30.0, 0.0, -1.0]
    assert a["stress_max_distribution"]["n"] == 3
    # 같은 각도의 두 군집은 각도 하나로 센다 — |응력| 큰 것
    s2 = HS.sites([_it("a", "x", [0, 0, 0], 10), _it("a", "x", [0.1, 0, 0], -30)], (0, 0, 0), 1.0)
    assert s2[0]["n_angles"] == 1 and s2[0]["stress_max_distribution"]["max"] == -30
    assert HS.default_radius([]) == HS.DEFAULT_RADIUS_MM
    # 자리 차례는 |응력| 큰 군집부터 — 멀리 떨어진 센 음수 군집이 첫 자리다
    far = HS.sites([_it("a", "x", [0, 0, 0], 100), _it("b", "x", [50, 0, 0], -300)], (0, 0, 0), 3.0)
    assert far[0]["representative"]["stress_max"] == -300 and far[1]["representative"]["stress_max"] == 100


def test_bbox_containment():
    items = [_it("a", "x", [0, 0, 0], 1), _it("b", "x", [5, 5, 5], 1), _it("c", "x", [50, 0, 0], 1)]
    got = HS.bbox_containment(items, (1.0, 1.0, 1.0), [0, 0, 0], [10, 10, 10])
    assert (got["inside"], got["total"]) == (2, 3) and got["ratio"] == pytest.approx(2 / 3)
    # 허용 1 mm — 경계 밖 0.9 mm 는 안이다
    assert HS.bbox_containment([_it("a", "x", [-0.9, 0, 0], 1)], (0, 0, 0), [0, 0, 0], [1, 1, 1])["inside"] == 1
    assert HS.bbox_containment(items, (0, 0, 0), None, [1, 1, 1])["ratio"] is None


DECK = (b"*KEYWORD\r\n$ comment\r\n*PART\r\nFront\\Metal\r\n         1         1         1\r\nFront\\Wall\r\n         2         1         1\r\n"
        b"*PART_INERTIA\r\nPCB board\r\n         3         2         2\r\n  1.0 2.0 3.0 4.0 5.0\r\n"
        b"*SECTION_SHELL\r\n         1\r\n  *PART\r\n*END\r\n*PART\r\ndead\r\n         9         1         1\r\n")


def test_part_title_rename_bytes():
    new, info = PT.rename(DECK, 2, "Wall_v2")
    assert info == {"line_no": 6, "old_title": "Front\\Wall"}
    assert new == DECK.replace(b"Front\\Wall\r\n", b"Wall_v2\r\n")            # 그 줄만 · CRLF 그대로
    new, info = PT.rename(DECK, 3, "PCB")
    assert info["old_title"] == "PCB board" and new.count(b"PCB\r\n") == 1
    with pytest.raises(PT.TitleError, match="없습니다"):
        PT.rename(DECK, 9, "x")                                              # *END 뒤의 파트는 읽히지 않는다
    with pytest.raises(PT.TitleError, match="없습니다"):
        PT.rename(DECK, 77, "x")
    dup = DECK.replace(b"Front\\Wall\r\n         2", b"Front\\Wall\r\n         1")
    with pytest.raises(PT.TitleError, match="두 곳|곳입니다"):
        PT.rename(dup, 1, "x")
    for bad in ("x" * 71, "한글", "*PART", "$c", "a\nb"):
        with pytest.raises(PT.TitleError):
            PT.rename(DECK, 1, bad)
    # 들여 쓴 `*` 로 시작하는 제목 줄은 데이터다(1열 규칙)
    assert PT.rename(b"*PART\n  *bolt\n         4         1         1\n", 4, "bolt")[1]["old_title"] == "*bolt"
    # 콤마 · long 20 칸 Card 1
    assert PT.rename(b"*PART\nt\n5,1,1\n", 5, "u")[0] == b"*PART\nu\n5,1,1\n"
    assert PT.rename(b"*PART\nt\n" + b"%20d%20d%20d\n" % (6, 1, 1), 6, "u")[1]["line_no"] == 2


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
    email = f"dfhot_{tag}_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash="x", display_name="DFH", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        uid = u.id
    from app.shared import security
    return {"id": uid, "h": {"Authorization": f"Bearer {security.create_access_token(uid)}"}}


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
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"hot-{ulid.new().str.lower()}"})
    cid = r.json()["data"]["campaign_id"]
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": list(runs)})
    assert r.status_code == 200, r.text
    return cid


async def _intake(client, h, cid: str, key: str) -> str:
    r = await client.post(f"{API}/reports/intake", headers=h, files={"file": ("Test_001_report.html", _SPHERE.read_bytes(), "text/html")},
                          data={"campaign_id": cid, "run_key": key})
    assert r.status_code == 201, r.text
    return r.json()["data"]["report_id"]


@needs_sphere
@_aio
async def test_frame_offset_and_hotspot_sites(client, user, monkeypatch):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "a", "provenance": PROV, "health": GOOD}, {"run_key": "b", "provenance": PROV, "health": GOOD}])
    ra = await _intake(client, h, cid, "a")
    rb = await _intake(client, h, cid, "b")
    fake = {ra: [{"case_key": "c1", "center": [0, -80, 6], "stress_max": 120.0, "radius_enclosing": 1.0, "criterion": "vm"},
                 {"case_key": "c1", "center": [30, -80, 6], "stress_max": 40.0, "radius_enclosing": 1.0, "criterion": "vm"},
                 {"case_key": "c1", "center": [0, -80, 6], "stress_max": 5.0, "radius_enclosing": 1.0, "criterion": "strain"}],
            rb: [{"case_key": "c1", "center": [0.5, -80, 6], "stress_max": -200.0, "radius_enclosing": 1.0, "criterion": "vm"}]}

    async def hotspots(db, report, *, criterion=None, part_id=None, top=20, order="stress_max", case_key=None):
        assert part_id == 7 and top == 0
        return {"available": True, "clusters": fake.get(report.id, [])}
    from app.modules.reports import services as rsvc
    monkeypatch.setattr(rsvc, "hotspots", hotspots)
    r = await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=h, params={"part_id": 7})
    assert r.status_code == 422 and "strain" in r.text and "vm" in r.text, r.text          # 기준이 둘 — 고르라고 한다
    r = await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=h, params={"part_id": 7, "criterion": "vm", "dx": 1})
    assert r.status_code == 422, r.text                                                     # 이동값은 셋 다
    d = (await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=h, params={"part_id": 7, "criterion": "vm"})).json()["data"]
    assert d["frame_offset"]["source"] == "none" and any("이동값이 없다" in w for w in d["warnings"])
    for bad in ({"dx": 1, "dy": 2}, {"dx": 1, "dy": 2, "dz": "inf"}, {"dx": 1, "dy": 2, "dz": 3, "extra": 1}):
        r = await client.put(f"{API}/campaigns/{cid}/frame-offset", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    r = await client.put(f"{API}/campaigns/{cid}/frame-offset", headers=h, json={"dx": 0, "dy": 79.6, "dz": -6.24, "source": "덱 원점 메모"})
    assert r.status_code == 200 and r.json()["data"]["frame_offset"]["dy"] == 79.6, r.text
    # 덱 bbox — 리포트 a 의 원본 K 파일 메타(modelmeta)에 파트 7 bbox
    async with SessionLocal() as s:
        rep = await s.get(ImpactReport, ra)
        f = await s.get(SessionFile, rep.source_file_id)
        f2 = SessionFile(session_id=f.session_id, filename="deck.k", rel_path=f.rel_path, kind="input", size_bytes=1,
                         meta={"modelmeta": {"parts": [{"pid": 7, "title": "Bracket", "bbox_min": [-1, -1, -1], "bbox_max": [2, 1, 1]}]}})
        s.add(f2)
        await s.flush()
        await s.execute(update(ImpactReport).where(ImpactReport.id == ra).values(source_kfile_id=f2.id))
        await s.commit()
    d = (await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=h, params={"part_id": 7, "criterion": "vm", "radius_mm": 2})).json()["data"]
    assert d["frame_offset"] == {"dx": 0.0, "dy": 79.6, "dz": -6.24, "source": "campaign"} and d["n_clusters"] == 3
    assert len(d["sites"]) == 2
    top = d["sites"][0]
    assert top["n_angles"] == 2 and top["representative"]["report_id"] == rb and top["representative"]["stress_max"] == -200.0
    assert top["center_deck"] == pytest.approx([0.25, -0.4, -0.24], abs=1e-9)
    bc = d["bbox_containment"]
    assert (bc["inside"], bc["total"]) == (2, 3) and d["bbox"]["title"] == "Bracket"
    assert any("bbox 포함률 66.7 %" in w for w in d["warnings"]) and d["merged_part"] is None
    # 조회 인자 이동값이 캠페인의 것보다 앞선다
    d = (await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=h,
                          params={"part_id": 7, "criterion": "vm", "dx": 0, "dy": 0, "dz": 0})).json()["data"]
    assert d["frame_offset"]["source"] == "query" and d["bbox_containment"]["inside"] == 0
    other = await _mk_user("b")
    try:
        r = await client.get(f"{API}/campaigns/{cid}/hotspot-sites", headers=other["h"], params={"part_id": 7})
        assert r.status_code == 404, r.text
        r = await client.put(f"{API}/campaigns/{cid}/frame-offset", headers=other["h"], json={"dx": 0, "dy": 0, "dz": 0})
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)


@_aio
async def test_session_revision_fields_and_warning(client, user):
    h = user["h"]
    r = await client.post(f"{API}/sessions", headers=h, json={"name": "rev"})
    sid = r.json()["data"]["id"]
    assert r.json()["data"]["environment"] == settings.environment and r.json()["data"]["revision_warning"] is None
    r = await client.patch(f"{API}/sessions/{sid}", headers=h, json={"deck_revision_label": "H8 PV1", "linked_cad": {"project_id": "SF-1", "revision": "H8 PV2"}})
    d = r.json()["data"]
    assert r.status_code == 200 and d["deck_revision_label"] == "H8 PV1" and d["linked_cad"] == {"project_id": "SF-1", "revision": "H8 PV2"}
    assert "H8 PV1" in d["revision_warning"] and "H8 PV2" in d["revision_warning"]
    d = (await client.get(f"{API}/sessions/{sid}", headers=h)).json()["data"]
    assert d["revision_warning"] and d["environment"] == settings.environment
    r = await client.patch(f"{API}/sessions/{sid}", headers=h, json={"linked_cad": {"project_id": "SF-1", "revision": " h8 pv1 "}})
    assert r.json()["data"]["revision_warning"] is None                    # 공백 · 대소문자는 같은 판
    r = await client.patch(f"{API}/sessions/{sid}", headers=h, json={"name": "rev2"})
    assert r.json()["data"]["deck_revision_label"] == "H8 PV1"             # 안 보낸 칸은 그대로
    r = await client.patch(f"{API}/sessions/{sid}", headers=h, json={"deck_revision_label": None, "linked_cad": None})
    assert r.json()["data"]["deck_revision_label"] is None and r.json()["data"]["linked_cad"] is None
    r = await client.patch(f"{API}/sessions/{sid}", headers=h, json={"linked_cad": {"project_id": "SF-1", "rev": "x"}})
    assert r.status_code == 422, r.text
    lst = (await client.get(f"{API}/sessions", headers=h)).json()["data"]
    assert all("environment" in x for x in lst)


@_aio
async def test_rename_session_part(client, user):
    h = user["h"]
    sid = (await client.post(f"{API}/sessions", headers=h, json={"name": "deck"})).json()["data"]["id"]
    r = await client.post(f"{API}/sessions/{sid}/files", headers=h, files=[("files", ("box.k", DECK, "application/octet-stream"))])
    assert r.status_code in (200, 201), r.text
    fid = (await client.get(f"{API}/sessions/{sid}/files", headers=h)).json()["data"][0]["id"]
    r = await client.patch(f"{API}/sessions/{sid}/parts/2", headers=h, json={"file_id": fid, "title": "Wall_v2"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert (d["old_title"], d["title"], d["line_no"]) == ("Front\\Wall", "Wall_v2", 6)
    got = (await client.get(f"{API}/sessions/{sid}/files/{fid}/download", headers=h)).content
    assert got == DECK.replace(b"Front\\Wall\r\n", b"Wall_v2\r\n") and d["sha256"] == hashlib.sha256(got).hexdigest()
    async with SessionLocal() as s:
        assert (await s.get(SessionFile, fid)).sha256 == d["sha256"]
    for pid, body in ((77, {"file_id": fid, "title": "x"}), (1, {"file_id": fid, "title": "한글"}), (1, {"file_id": fid, "title": "x" * 71}),
                      (1, {"file_id": fid}), (1, {"file_id": fid, "title": "x", "z": 1})):
        r = await client.patch(f"{API}/sessions/{sid}/parts/{pid}", headers=h, json=body)
        assert r.status_code == 422, (pid, body, r.text)
    r = await client.patch(f"{API}/sessions/{sid}/parts/1", headers=h, json={"file_id": 999999999, "title": "x"})
    assert r.status_code == 404, r.text
    other = await _mk_user("c")
    try:
        r = await client.patch(f"{API}/sessions/{sid}/parts/1", headers=other["h"], json={"file_id": fid, "title": "x"})
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)
