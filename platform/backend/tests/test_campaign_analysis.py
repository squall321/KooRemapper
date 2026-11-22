# 캠페인 분석(DF-05 · 06 · 08 ~ 12) — 방향 · 라벨 · 무리 피크 · 충격 · 여유 · 격자 · 짝 · 쌍은 순수 함수로, 받는 꼴 · REST 는 진짜 앱 + DB 로 잰다
"""캠페인 분석 (2026-11-22 · 계획 docs/01-plan/features/df-campaign-analysis-1122.plan.md 5절).

왜 이 시험이 있나.

  각도 통계 · 피크 표 · 여유 · 구면 지도 · 자리 지도 · 리비전 비교 · 설정 쌍 판정을 리포트 하나씩 손으로 모으고 있었다 — 방향식 ·
  두께축 · 라벨이 스크립트마다 달라 같은 캠페인이 다른 숫자를 냈다(요청서 함정 줄). 이제 캠페인 단위로 한 규칙으로 센다. 요청서의
  대조 파일은 이 박스에 없어 같은 꼴의 합성 사례로 잰다 — 전각도 표본 26 방향의 범주가 생성기 범주와 같고, 격자가 전부 훑기와 같고,
  여유의 넘은 비율 · 쌍 판정이 규칙대로 갈린다.
"""
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
from sqlalchemy import delete, select, update  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import Campaign, ImpactCase, Session, User  # noqa: E402
from app.modules.campaigns import angles as G  # noqa: E402
from app.modules.campaigns import sphere as SP  # noqa: E402

API = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 리포트 표본이 이 박스에 없다")
_aio = pytest.mark.asyncio(loop_scope="session")
GOOD = {"normal_termination": True}
PROV = {"wrapper_name": "w"}


# ---------------------------------------------------------------- 순수 함수

def test_direction_formula_axes_and_labels():
    assert G.label_of(G.to_deck(G.frame_vec(0, 0), "Z")) == ("-Z", "face")          # 평판 낙하 — 두께 아래
    assert G.label_of(G.to_deck(G.frame_vec(0, 0), "X")) == ("-X", "face")          # 닫힌 덱(두께 X) — 라벨이 덱 축을 따른다
    assert G.label_of(G.to_deck(G.frame_vec(0, 0), "Y")) == ("-Y", "face")
    assert G.label_of(G.to_deck(G.frame_vec(45, 0), "Z")) == ("+X-Z", "edge")
    assert G.label_of(G.to_deck(G.frame_vec(45, 45), "Z"))[1] == "corner"
    f = G.frame_vec(30, 20)
    assert math.isclose(sum(c * c for c in f), 1.0)
    assert f == pytest.approx((math.sin(math.radians(30)) * math.cos(math.radians(20)), -math.sin(math.radians(20)),
                               -math.cos(math.radians(30)) * math.cos(math.radians(20))))
    assert G.to_deck(f, "X") == (f[2], f[0], f[1]) and G.to_deck(f, "Y") == (f[1], f[2], f[0])
    assert len(G.CANON) == 26 and sum(1 for c in G.CANON if c[1] == "corner") == 8
    assert G.resolve_metric("MET-ACCEL") == "peak_g" and G.resolve_metric("nope") is None


def test_group_peak_time_and_impact_attribution():
    pm = {"1": {"peak_stress": 100.0, "time_of_peak_stress": 0.004}, "2": {"peak_stress": 250.0, "time_of_peak_stress": 0.0123},
          "3": {"peak_stress": 300.0}}
    gp = G.group_peak(pm, [1, 2], "peak_stress")
    assert gp == {"value": 250.0, "part_id": 2, "t_peak_ms": pytest.approx(12.3)}
    assert G.group_peak(pm, None, "peak_stress")["part_id"] == 3
    assert G.group_peak({"1": {"min_principal_strain": -0.01}, "2": {"min_principal_strain": -0.03}}, None,
                        "min_principal_strain")["value"] == -0.03
    imps = [{"index": 2, "t_start_ms": 10.0, "t_end_ms": 15.0, "ke_frac": 0.4}, {"index": 1, "t_start_ms": 0.0, "t_end_ms": 5.0, "ke_frac": 1.0}]
    assert G.impact_info(imps, 12.3) == {"n_impacts": 2, "second_impact_ms": 10.0, "peak_impact": 2, "ke_frac_at_impact": 0.4}
    assert G.impact_info(imps, 7.0)["peak_impact"] is None          # 두 충격 사이
    assert G.impact_info(None, 1.0)["n_impacts"] is None
    # 끝이 없으면 다음 충격 시작까지
    assert G.impact_info([{"index": 1, "t_start_ms": 0.0}, {"index": 2, "t_start_ms": 9.0}], 8.0)["peak_impact"] == 1
    # 끝이 없는 첫 충격은 둘째 충격이 시작하면 끝난다 — 10 ms 는 둘째 충격
    assert G.impact_info([{"index": 1, "t_start_ms": 0.0}, {"index": 2, "t_start_ms": 9.0, "t_end_ms": 12.0}], 10.0)["peak_impact"] == 2


def test_angle_rows_stats_multi_impact():
    runs = []
    for k in range(10):
        imps = [{"index": 1, "t_start_ms": 0.0, "t_end_ms": 5.0, "ke_frac": 1.0}]
        if k < 7:
            imps.append({"index": 2, "t_start_ms": 6.0, "t_end_ms": 20.0, "ke_frac": 0.3})
        runs.append({"run_key": f"r{k}", "doe": k, "pitch": 10.0 * k, "roll": 0.0, "impacts": imps if k != 9 else None,
                     "health": {"ke0_measured": 1.5}, "report": {"cases": [{"case_key": "single", "identity": {},
                     "parts_metrics": {"1": {"peak_stress": float(k), "time_of_peak_stress": 0.010 if k < 7 else 0.002}}}]}})
    rows = G.angle_rows(runs, [], ["peak_stress"], "Z")
    assert len(rows) == 10 and rows[0]["ke0"] == 1.5 and rows[0]["category"] == "face"
    st = G.angle_stats(rows, ["all"], "peak_stress", top=3)
    # 충격 구간을 받은 9 각도 가운데 2 회 이상 7 → 다회 충격 비율 7/9
    assert (st["impacts_known"], st["multi_impact"]) == (9, 7) and st["multi_impact_ratio"] == pytest.approx(7 / 9)
    g = st["groups"]["all"]
    assert g["distribution"]["median"] == pytest.approx(4.5) and [x["value"] for x in g["top"]] == [9.0, 8.0, 7.0]
    assert g["peak_impact_counts"] == {"1": 2, "2": 7}
    assert st["coverage"]["labels_total"] == 26 and st["coverage"]["labels_hit"] >= 1


def test_margin_and_axes():
    pm = {"1": {"peak_principal_stress": 120.0, "peak_stress": 150.0, "min_principal_strain": -0.002, "peak_principal_strain": 0.0009},
          "2": {"peak_principal": 80.0}}
    assert G.axis_value(pm, [1, 2], "tension_principal_stress") == 120.0
    assert G.axis_value(pm, [2], "tension_principal_stress") == 80.0        # 앞 지표가 없으면 다음 지표
    assert G.axis_value(pm, [1], "compressive_strain") == pytest.approx(0.002)
    assert G.axis_value(pm, [1], "board_strain_ue") == pytest.approx(900.0)
    vals = [({"run_key": f"r{i}", "case_key": "c", "doe": i, "label": "-Z"}, float(v)) for i, v in enumerate([90, 95, 100, 105, 110])]
    m = G.margin(vals, 100.0)
    assert (m["value"], m["median"], m["ratio"], m["exceed_ratio"]) == (110.0, 100.0, 1.1, pytest.approx(0.6))
    assert [x["value"] for x in m["top_angles"]] == [110.0]                 # 상위 10 % — 다섯 가운데 하나
    assert G.margin(vals, None)["ratio"] is None


def test_grid_matches_brute_force_and_centering():
    pts = []
    for k in range(60):
        lat = math.degrees(math.asin(-1 + 2 * (k + 0.5) / 60))
        lon = (k * 137.508) % 360 - 180
        pts.append({"lon": lon, "lat": lat, "value": 10 + math.cos(math.radians(lon - 40)) * math.cos(math.radians(lat))})
    g = SP.grid(pts)
    assert len(g) == 181 and len(g[0]) == 361

    def brute(lon, lat):
        u = SP._unit(lon, lat)
        ds = sorted((SP._ang(u, SP._unit(p["lon"], p["lat"])), i) for i, p in enumerate(pts))[:8]
        ws = [1 / max(d, 0.5) ** 2 for d, _ in ds]
        return sum(w * pts[i]["value"] for w, (_, i) in zip(ws, ds)) / sum(ws)
    for lon, lat in ((0, 0), (40, 0), (-179, 33), (90, -88), (12, 90)):
        assert g[lat + 90][lon + 180] == pytest.approx(brute(lon, lat), abs=1e-12)
    shift = SP.center_shift(g)
    assert abs(SP.wrap_lon(shift - 40)) <= 15                              # 센 띠(경도 40° 근처)를 찾는다
    r = SP.rotate(g, shift)
    assert r[90][180] == g[90][(180 + shift) % 360] and r[0][360] == r[0][0]
    # 가운데 맞춤은 cos(위도) 가중 — 극 근처의 센 조각보다 적도의 넓은 띠가 센 띠다
    band = [[(10.0 if lat >= 70 and -110 <= lon <= -90 else 3.0 if abs(lat) <= 20 and 50 <= lon <= 70 else 0.0)
             for lon in range(-180, 181)] for lat in range(-90, 91)]
    assert 50 <= SP.center_shift(band) <= 70
    png = SP.raster_png(g, min(map(min, g)), max(map(max, g)), 200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    sv = SP.svg(g, 9, 11, pts, title="t", unit="MPa")
    assert sv.startswith("<svg") and "data:image/png;base64," in sv and "<path" in sv


def test_pairs_spearman_and_verdict():
    assert G.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert G.spearman([1, 1, 1], [1, 2, 3]) is None

    def rows(vals):
        return [{"doe": i, "run_key": f"k{i}", "peaks": {"all": {"peak_stress": {"value": v}}}} for i, v in enumerate(vals)]
    rule = {"metrics": [{"metric": "peak_stress", "group_key": None, "max_diff_pct": 3.0}], "rank_corr_min": 0.9, "max_failed_pairs": 2}
    ok_ = G.config_pairs(rows([100, 200, 300, 400]), rows([101, 202, 303, 404]), rule)
    assert ok_["verdict"] == "pass" and ok_["failed_pairs"] == 0 and ok_["rank_correlation"][0]["rank_corr"] == pytest.approx(1.0)
    bad = G.config_pairs(rows([100, 200, 300, 400]), rows([110, 220, 330, 404]), rule)
    assert bad["failed_pairs"] == 3 and bad["verdict"] == "rerun_required" and bad["reasons"] == ["failed_pairs"]
    flip = G.config_pairs(rows([100, 200, 300, 400]), rows([400, 300, 200, 100]), {**rule, "metrics": [{**rule["metrics"][0], "max_diff_pct": 1e9}]})
    assert flip["reasons"] == ["rank_corr"]
    assert G.config_pairs(rows([1]), [], rule)["verdict"] == "no_pairs"
    assert G.size_class(1.5) == "high" and G.size_class(1.1) == "low" and G.size_class(1.2) == "mid" and G.size_class(0.8) == "mid"


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
    email = f"dfana_{tag}_{ulid.new().str.lower()}@test.local"
    async with SessionLocal() as s:
        u = User(email=email, password_hash="x", display_name="DFA", is_active=True)
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


async def _campaign(client, h, runs, **fields) -> str:
    r = await client.post(f"{API}/campaigns", headers=h, json={"name": f"ana-{ulid.new().str.lower()}", **fields})
    assert r.status_code == 201, r.text
    cid = r.json()["data"]["campaign_id"]
    r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": list(runs)})
    assert r.status_code == 200, r.text
    return cid


async def _intake(client, h, cid: str, key: str) -> str:
    r = await client.post(f"{API}/reports/intake", headers=h, files={"file": ("Test_001_report.html", _SPHERE.read_bytes(), "text/html")},
                          data={"campaign_id": cid, "run_key": key})
    assert r.status_code == 201, r.text
    return r.json()["data"]["report_id"]


IMPS = [{"index": 1, "t_start_ms": 0.0, "t_end_ms": 4.0, "ke_frac": 1.0, "peaks": {"all": 50.0}},
        {"index": 2, "t_start_ms": 6.0, "t_end_ms": 12.0, "ke_frac": 0.35}]


@_aio
async def test_manifest_impacts_and_groups_validation(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "a", "impacts": IMPS}])
    for bad in ({"run_key": "a", "impacts": [{"index": 1, "t_start_ms": 0}, {"index": 1, "t_start_ms": 3}]},
                {"run_key": "a", "impacts": [{"index": 1, "t_start_ms": 5, "t_end_ms": 1}]},
                {"run_key": "a", "impacts": [{"index": 0, "t_start_ms": 0}]},
                {"run_key": "a", "impacts": [{"index": 1, "t_start_ms": 0, "energy": 1}]}):
        r = await client.post(f"{API}/campaigns/{cid}/runs", headers=h, json={"runs": [bad]})
        assert r.status_code == 422, (bad, r.text)
    for bad in ({"groups": [{"group_key": "g", "part_ids": [1]}, {"group_key": "g", "part_ids": [2]}]},
                {"groups": [{"group_key": "g", "part_ids": []}]}, {"groups": [{"group_key": "a b", "part_ids": [1]}]}):
        r = await client.put(f"{API}/campaigns/{cid}/part-groups", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    r = await client.put(f"{API}/campaigns/{cid}/part-groups", headers=h,
                         json={"groups": [{"group_key": "pcb", "label": "PCB", "part_ids": [3, 3]}, {"group_key": "front", "part_ids": [1, 2]}]})
    assert r.status_code == 200 and r.json()["data"]["groups"][0]["part_ids"] == [3], r.text
    for path, params in (("angle-table", {"metrics": "nope"}), ("angle-table", {"groups": "zzz"}), ("angle-stats", {"metric": "MET-X"})):
        r = await client.get(f"{API}/campaigns/{cid}/{path}", headers=h, params=params)
        assert r.status_code == 422, (path, r.text)
    other = await _mk_user("b")
    try:
        for path in ("angle-table", "angle-stats", "peaks", "part-margin", "sphere-map", "sites", "site-map"):
            r = await client.get(f"{API}/campaigns/{cid}/{path}", headers=other["h"])
            assert r.status_code == 404, (path, r.text)
        r = await client.put(f"{API}/campaigns/{cid}/part-groups", headers=other["h"], json={"groups": []})
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)


@needs_sphere
@_aio
async def test_angle_table_stats_peaks_on_sphere_sample(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "s", "doe": "d1", "provenance": PROV, "health": GOOD, "impacts": IMPS},
                                      {"run_key": "jump", "provenance": PROV,
                                       "health": {**GOOD, "ke0_measured": 2.0, "ke0_expected": 1.0}}])
    await _intake(client, h, cid, "s")
    await _intake(client, h, cid, "jump")
    d = (await client.get(f"{API}/campaigns/{cid}/angle-table", headers=h, params={"metrics": "MET-STRESS,peak_g"})).json()["data"]
    assert d["header"]["excluded_ke_jump"] == 1 and d["header"]["included"] == 1, d["header"]
    assert d["header"]["line"].endswith("excluded_ke_jump 1")
    rows = d["rows"]
    assert d["matched"] == 26 and len(rows) == 26 and d["metrics"] == ["peak_stress", "peak_g"]
    assert sorted({r["category"] for r in rows}) == ["corner", "edge", "face"]
    assert len({r["label"] for r in rows}) == 26                     # 26 방향 표본 — 라벨이 다 다르다
    assert all(r["n_impacts"] == 2 and r["second_impact_ms"] == 6.0 for r in rows)
    one = rows[0]["peaks"]["all"]["peak_stress"]
    assert one["value"] is not None and one["t_peak_ms"] is None and one["peak_impact"] is None   # 표본에 피크 시각이 없다
    st = (await client.get(f"{API}/campaigns/{cid}/angle-stats", headers=h)).json()["data"]["stats"]
    assert st["n"] == 26 and st["multi_impact_ratio"] == 1.0 and st["coverage"]["labels_hit"] == 26
    st2 = (await client.get(f"{API}/campaigns/{cid}/angle-stats", headers=h, params={"include_ke_jump": True})).json()["data"]
    assert st2["header"]["included"] == 2 and st2["stats"]["n"] == 52
    pk = (await client.get(f"{API}/campaigns/{cid}/peaks", headers=h)).json()["data"]
    assert pk["matched"] == 26 and len(pk["impacts"]) == 2
    assert pk["impacts"][0] == {"run_key": "s", "doe": "d1", "impact": 1, "t_start_ms": 0.0, "t_end_ms": 4.0, "ke_frac": 1.0,
                                "group_key": "all", "value": 50.0}
    # 두께축 X — 라벨이 덱 축을 따라 돈다(같은 각도 · 다른 이름)
    dx = (await client.get(f"{API}/campaigns/{cid}/angle-table", headers=h, params={"thickness_axis": "X"})).json()["data"]
    assert dx["thickness_axis"] == "X" and [r["label"] for r in dx["rows"]] != [r["label"] for r in rows]
    assert sorted(r["category"] for r in dx["rows"]) == sorted(r["category"] for r in rows)


@needs_sphere
@_aio
async def test_criteria_and_part_margin(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "s", "provenance": PROV, "health": GOOD}])
    await _intake(client, h, cid, "s")
    await client.put(f"{API}/campaigns/{cid}/part-groups", headers=h, json={"groups": [{"group_key": "front", "part_ids": [1, 2]},
                                                                                      {"group_key": "pcb", "part_ids": [3]}]})
    for bad in ({"criteria": [{"part_id": 1, "group_key": "front", "metric_axis": "von_mises", "criterion_value": 100, "unit": "MPa"}]},
                {"criteria": [{"metric_axis": "von_mises", "criterion_value": 100, "unit": "MPa"}]},
                {"criteria": [{"part_id": 1, "metric_axis": "von_mises", "criterion_value": 100, "unit": "GPa"}]},
                {"criteria": [{"part_id": 1, "metric_axis": "von_mises", "criterion_value": 0, "unit": "MPa"}]},
                {"criteria": [{"part_id": 1, "metric_axis": "hoop", "criterion_value": 1, "unit": "MPa"}]},
                {"criteria": [{"part_id": 1, "metric_axis": "von_mises", "criterion_value": 1, "unit": "MPa"}] * 2}):
        r = await client.put(f"{API}/campaigns/{cid}/criteria", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    # 기준값을 무리 front 의 각도 가운데값으로 — 넘은 비율이 절반 근처여야 한다
    tab = (await client.get(f"{API}/campaigns/{cid}/angle-table", headers=h, params={"groups": "front"})).json()["data"]["rows"]
    vals = sorted(r["peaks"]["front"]["peak_stress"]["value"] for r in tab)
    med = G.quantile(vals, 0.5)
    r = await client.put(f"{API}/campaigns/{cid}/criteria", headers=h, json={"criteria": [
        {"group_key": "front", "failure_mode": "FM-YIELD", "metric_axis": "von_mises", "criterion_value": med, "unit": "MPa",
         "source_platform": "matnexus", "source_record_id": "MN-1", "version": "v1"},
        {"group_key": "ghost", "metric_axis": "von_mises", "criterion_value": 10, "unit": "MPa"}]})
    assert r.status_code == 200, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/part-margin", headers=h)).json()["data"]
    assert d["axes"] == ["von_mises"]
    by = {(tuple(x["target"].items())[0], x["status"]): x for x in d["rows"]}
    front = by[(("group_key", "front"), "ok")]
    assert front["value"] == vals[-1] and front["median"] == pytest.approx(med) and front["ratio"] == pytest.approx(vals[-1] / med)
    assert front["exceed_ratio"] == pytest.approx(sum(1 for v in vals if v >= med) / len(vals))
    assert front["criterion_source"] == {"source_platform": "matnexus", "source_record_id": "MN-1", "version": "v1"}
    assert len(front["top_angles"]) == math.ceil(26 * 0.1)
    assert by[(("group_key", "ghost"), "group_unknown")]["criterion"] == 10
    assert by[(("group_key", "pcb"), "criterion_unset")]["ratio"] is None       # 기준 미지정 — 리포트 항복값을 쓰지 않는다
    r = await client.put(f"{API}/campaigns/{cid}/criteria", headers=h, json={"criteria": []})
    d = (await client.get(f"{API}/campaigns/{cid}/part-margin", headers=h)).json()
    assert d["data"]["rows"] == [] and "기준값이 없습니다" in d["message"]


@needs_sphere
@_aio
async def test_sphere_map_json_svg_png(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "s", "provenance": PROV, "health": GOOD, "config_generation": "g1"}])
    await _intake(client, h, cid, "s")
    d = (await client.get(f"{API}/campaigns/{cid}/sphere-map", headers=h, params={"center": False})).json()["data"]
    gr = d["grid"]["values"]
    assert (len(gr), len(gr[0])) == (181, 361) and len(d["points"]) == 26 and d["shift_deg"] == 0
    want = SP.grid([{"lon": p["lon"], "lat": p["lat"], "value": p["value"]} for p in d["points"]])
    assert gr[90][180] == pytest.approx(want[90][180], rel=1e-5) and gr[10][33] == pytest.approx(want[10][33], rel=1e-5)
    assert "유효 1 / 전체 1" in d["provenance"] and "g1 1" in d["provenance"]
    c = (await client.get(f"{API}/campaigns/{cid}/sphere-map", headers=h)).json()["data"]
    assert c["shift_deg"] == SP.center_shift(want)
    r = await client.get(f"{API}/campaigns/{cid}/sphere-map", headers=h, params={"format": "svg"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and r.text.startswith("<svg")
    import hashlib
    assert r.headers["x-content-sha256"] == hashlib.sha256(r.content).hexdigest()
    r = await client.get(f"{API}/campaigns/{cid}/sphere-map", headers=h, params={"format": "png"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    empty = await _campaign(client, h, [{"run_key": "x"}])
    r = await client.get(f"{API}/campaigns/{empty}/sphere-map", headers=h)
    assert r.status_code == 422, r.text
    # 무리를 정하지 않은 캠페인 — 기준값을 무리 all(모든 파트)에 걸 수 있다(각도 표 · 지도 · 쌍 규칙과 같다)
    r = await client.put(f"{API}/campaigns/{cid}/criteria", headers=h,
                         json={"criteria": [{"group_key": "all", "metric_axis": "von_mises", "criterion_value": 100, "unit": "MPa"}]})
    rows = (await client.get(f"{API}/campaigns/{cid}/part-margin", headers=h)).json()["data"]["rows"]
    assert [(x["target"], x["status"]) for x in rows] == [({"group_key": "all"}, "ok")] and rows[0]["ratio"] is not None


@needs_sphere
@_aio
async def test_sites_table_map_and_coverage(client, user):
    h = user["h"]
    cid = await _campaign(client, h, [{"run_key": "s", "provenance": PROV, "health": {**GOOD, "energy_ratio_max": 0.995}}])
    await _intake(client, h, cid, "s")
    await client.put(f"{API}/campaigns/{cid}/criteria", headers=h,
                     json={"criteria": [{"part_id": 7, "metric_axis": "board_strain_ue", "criterion_value": 330, "unit": "µε"}]})
    for bad in ({"sites": [{"site_id": "A"}, {"site_id": "A"}]}, {"sites": [{"site_id": "A", "face": "SIDE"}]},
                {"sites": [{"site_id": "A", "metrics": [{"part": "7", "metric": "m", "value": "x"}]}]}):
        r = await client.put(f"{API}/campaigns/{cid}/sites", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    sites = [{"site_id": "T01", "face": "TOP", "col": 1, "row": 1, "x_mm": 0, "y_mm": 0, "under_category": "pcb",
              "impactor": {"mass_g": 20, "height_mm": 100}, "footprint": {"measured": True},
              "metrics": [{"part": "7", "metric": "board_strain_ue", "value": 660, "time_ms": 1.2, "elem_id": 99},
                          {"part": "model", "metric": "contact_force_N", "value": 450}]},
             {"site_id": "T02", "face": "TOP", "col": 2, "row": 1, "x_mm": 5, "y_mm": 0, "run_key": "s"},
             {"site_id": "B01", "face": "BOT", "col": 1, "row": 1, "x_mm": 0, "y_mm": 5}]
    r = await client.put(f"{API}/campaigns/{cid}/sites", headers=h, json={"sites": sites})
    assert r.status_code == 200 and r.json()["data"]["sites"] == 3, r.text
    d = (await client.get(f"{API}/campaigns/{cid}/sites", headers=h)).json()["data"]
    cov, by = d["coverage"], {x["site_id"]: x for x in d["rows"]}
    assert cov["missing"] == ["B01"] and cov["with_results"] == 2 and cov["by_face"] == {"BOT": 1, "TOP": 2}
    assert cov["footprints_are_measured"] is False and "합성" in cov["warning"]
    t1 = by["T01"]
    assert t1["source"] == "site_metrics" and t1["max_ratio"] == pytest.approx(2.0) and t1["footprint_measured"] is True
    t2 = by["T02"]
    assert t2["source"] == "run_report" and any(m["metric"] == "energy_ratio_max" and m["value"] == 0.995 for m in t2["metrics"])
    r = await client.get(f"{API}/campaigns/{cid}/site-map", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and "합성" in r.text
    j = (await client.get(f"{API}/campaigns/{cid}/site-map", headers=h,
                          params={"format": "json", "metric": "board_strain_ue", "part": "7"})).json()["data"]
    assert {p["site_id"]: p["value"] for p in j["points"]} == {"T01": 660.0, "T02": None, "B01": None}
    r = await client.put(f"{API}/campaigns/{cid}/sites", headers=h, json={"sites": []})
    assert (await client.get(f"{API}/campaigns/{cid}/sites", headers=h)).json()["data"]["rows"] == []


@needs_sphere
@_aio
async def test_part_map_and_compare_campaigns(client, user):
    h = user["h"]
    ca = await _campaign(client, h, [{"run_key": "a", "provenance": PROV, "health": GOOD}])
    cb = await _campaign(client, h, [{"run_key": "b", "provenance": PROV, "health": GOOD}])
    await _intake(client, h, ca, "a")
    rb = await _intake(client, h, cb, "b")
    for bad in ({"from_model": "H8", "to_model": "H9", "rows": [{"a_pid": 1, "b_pid": 1}]},          # basis 필수
                {"from_model": "H8", "to_model": "H9", "rows": [{"basis": "geometry"}]},
                {"from_model": "H8", "to_model": "H9", "rows": []}):
        r = await client.post(f"{API}/part-maps", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    rows = [{"a_pid": 1, "b_pid": 1, "basis": "geometry", "center_dist_mm": 0.1}, {"a_pid": 4, "b_pid": 4, "basis": "manual"},
            {"a_pid": 2, "b_pid": 2, "basis": "name"}, {"a_pid": 5, "basis": "geometry"}]
    r = await client.post(f"{API}/part-maps", headers=h, json={"from_model": "H8", "to_model": "H9", "rows": rows})
    assert r.status_code == 201, r.text
    mid = r.json()["data"]["map_id"]
    assert (await client.get(f"{API}/part-maps/{mid}", headers=h)).json()["data"]["n_rows"] == 4
    # 뒤 캠페인의 파트 4 피크를 두 배로 — 짝 (4, 4) 의 비가 2 · 크기 상(표본의 파트 3 은 지표가 없다)
    async with SessionLocal() as s:
        for cs in (await s.execute(select(ImpactCase).where(ImpactCase.report_id == rb))).scalars():
            pm = dict(cs.parts_metrics)
            if "4" in pm and pm["4"].get("peak_stress") is not None:
                pm["4"] = {**pm["4"], "peak_stress": pm["4"]["peak_stress"] * 2}
                cs.parts_metrics = pm
        await s.commit()
    d = (await client.get(f"{API}/campaigns/compare", headers=h,
                          params={"a": ca, "b": cb, "part_map": mid, "match": "angle", "tol_deg": 1})).json()["data"]
    hd = d["header"]
    assert hd["common_angles"] == 26 and hd["name_only_skipped"] == 1 and hd["pairs_compared"] == 2
    by = {p["a_pid"]: p for p in d["pairs"]}
    assert by[1]["median_ratio"] == pytest.approx(1.0) and by[1]["size"] == "low"
    assert by[4]["median_ratio"] == pytest.approx(2.0) and by[4]["size"] == "high" and by[4]["top5_ratio"] == pytest.approx(2.0)
    assert hd["size_counts"] == {"high": 1, "mid": 0, "low": 1} and hd["top5"][0]["a_pid"] == 4
    assert "2" in d["disappeared_parts"] and "1" not in d["disappeared_parts"]
    dd = (await client.get(f"{API}/campaigns/compare", headers=h, params={"a": ca, "b": cb, "part_map": mid})).json()["data"]
    assert dd["header"]["common_angles"] == 0                       # 기본 doe 맞춤 — 두 런에 DOE 가 없다
    other = await _mk_user("c")
    try:
        assert (await client.get(f"{API}/part-maps/{mid}", headers=other["h"])).status_code == 404
        r = await client.get(f"{API}/campaigns/compare", headers=other["h"], params={"a": ca, "b": cb, "part_map": mid})
        assert r.status_code == 404, r.text
    finally:
        await _drop_user(client, other)


@needs_sphere
@_aio
async def test_pair_rule_and_config_pairs(client, user):
    h = user["h"]
    runs = [{"run_key": "old1", "doe": "D1", "provenance": PROV, "health": GOOD, "config_generation": "old", "superseded_by": "new1"},
            {"run_key": "new1", "doe": "D1", "provenance": PROV, "health": GOOD, "config_generation": "new"}]
    cid = await _campaign(client, h, runs)
    r = await client.get(f"{API}/campaigns/{cid}/config-pairs", headers=h, params={"old": "old", "new": "new"})
    assert r.status_code == 422 and "쌍 규칙" in r.text, r.text
    for bad in ({"metrics": []}, {"metrics": [{"metric": "peak_stress", "max_diff_pct": 0}]},
                {"metrics": [{"metric": "nope", "max_diff_pct": 3}]}, {"metrics": [{"metric": "peak_stress", "max_diff_pct": 3}], "rank_corr_min": 2}):
        r = await client.put(f"{API}/campaigns/{cid}/pair-rule", headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
    r = await client.put(f"{API}/campaigns/{cid}/pair-rule", headers=h,
                         json={"metrics": [{"metric": "MET-STRESS", "max_diff_pct": 3}], "max_failed_pairs": 0})
    assert r.status_code == 200 and r.json()["data"]["pair_rule"]["metrics"][0]["metric"] == "peak_stress", r.text
    await _intake(client, h, cid, "old1")
    rn = await _intake(client, h, cid, "new1")
    d = (await client.get(f"{API}/campaigns/{cid}/config-pairs", headers=h, params={"old": "old", "new": "new"})).json()["data"]
    assert d["common_doe"] == 1 and d["verdict"] == "pass" and d["pairs"][0]["diff_pct"] == pytest.approx(0.0)
    assert d["old"]["header"]["included"] == 1                       # 대체된 옛 런도 넣는다
    async with SessionLocal() as s:
        for cs in (await s.execute(select(ImpactCase).where(ImpactCase.report_id == rn))).scalars():
            cs.parts_metrics = {k: ({**v, "peak_stress": v["peak_stress"] * 1.1} if isinstance(v, dict) and v.get("peak_stress") else v)
                                for k, v in (cs.parts_metrics or {}).items()}
        await s.commit()
    d = (await client.get(f"{API}/campaigns/{cid}/config-pairs", headers=h, params={"old": "old", "new": "new"})).json()["data"]
    assert d["verdict"] == "rerun_required" and d["failed_pairs"] == 1 and d["pairs"][0]["diff_pct"] == pytest.approx(10.0)
    await client.put(f"{API}/campaigns/{cid}/pair-rule", headers=h,
                     json={"metrics": [{"metric": "peak_stress", "group_key": "ghost", "max_diff_pct": 3}]})
    r = await client.get(f"{API}/campaigns/{cid}/config-pairs", headers=h, params={"old": "old", "new": "new"})
    assert r.status_code == 422 and "ghost" in r.text, r.text
    async with SessionLocal() as s:
        assert (await s.get(Campaign, cid)).pair_rule["metrics"][0]["group_key"] == "ghost"
