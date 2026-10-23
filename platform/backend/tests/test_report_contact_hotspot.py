# 전각도 낙하 리포트의 핫스팟 군집 · 파트쌍 접촉 프로파일 · 하중경로가 플랫폼에서 꺼내지는가(새 판 생성기 꼴)
"""왜 이 시험이 있나 (2026-10-23).

사용자 질문 「전각도 낙하 데이터가 핫스팟 클러스터 기능까지도 다 올라오고 조회도 되는지」를 재 보니 **반입은 되는데 조회가
안 됐다.** sphere 생성기(10-17~)가 플랫폼보다 앞서 있었다.

  · 핫스팟 — 각도 런마다 `results[i].hotspot`(압축 꼴)에 싣는데 `/hotspots` 는 deep 꼴(최상위 `hotspot`)만 알아
    sphere 에는 「없다」 고 답했다.
  · 하중경로 — HTML 은 압축 꼴(sphere `pf`·`tw`·`ti` · impact `peak_f`·`total_w`·`total_imp` · 흐름 `ke_init`·노드 `id`)인데
    중립 꼴 이름만 읽어 **값이 전부 null** 이었다. 요청한 각도에 상세가 없으면 **다른 각도의 흐름을 그 각도 이름으로**
    돌려줬다.
  · 파트쌍 × 각도 접촉 프로파일(`contact_profile` — sphere · impact 같은 꼴)은 어디서도 해석하지 않았다.

합성 시험은 생성기 압축 함수의 꼴을 그대로 옮겼다(`koo_sphere_report/report/html_report.py` `_compact_cluster`·
`_compact_energy_flows`·`_contact_profile`, impact `report/payload/core.py`). 실제 고정본 시험은 운영 이미지로 만든 새 판
리포트(`/data/koopark/report_fixtures/sphere_hotspot_v1018` — README 에 출처)와 impact 실리포트를 쓴다(없으면 건너뛴다).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Session, SessionFile, User
from app.reports import parser as P
from app.shared import security, storage

_aio = pytest.mark.asyncio(loop_scope="session")
_SPHERE_NEW = Path("/data/koopark/report_fixtures/sphere_hotspot_v1018/report.html")
_IMPACT = Path("/data/koopark/Test_Impact_A/impact_report.html")
_needs_sphere = pytest.mark.skipif(not _SPHERE_NEW.exists(), reason="새 판 sphere 고정본 없음")
_needs_impact = pytest.mark.skipif(not _IMPACT.exists(), reason="impact 실리포트 없음")


def _raw(path: Path) -> dict:
    return P.extract_embedded_data(path.read_text(encoding="utf-8", errors="replace"))


# ── 하중경로 — 세 꼴 ───────────────────────────────────────────────────────────
def _sphere_compact():
    return {"Run_A": {"t": [0.0, 1e-4], "ke_init": 12.0, "ke_final": 3.0, "dissipated": 9.0,
                      "nodes": [{"id": "1", "name": "plate", "is_impactor": True, "ke": [12.0, 3.0], "ie": [0.0, 1.0]},
                                {"id": "2", "name": "case", "is_impactor": False, "ke": [0.0, 1.0], "ie": [0.0, 5.0]}],
                      "edges": [{"src": "1", "dst": "2", "name": "c1", "cid": 7, "f": [0.0, 900.0], "fei": 1,
                                 "tw": 6.0, "ti": 0.02, "pf": 900.0}]}}


def test_energy_sphere_html_compact_form_is_read():
    """압축 꼴의 값이 이름만 달라 null 로 사라지지 않는다."""
    e = P.case_energy({"energy_flows": _sphere_compact()}, "sphere", "Run_A")
    f = e["energy_flow"]
    assert f["form"] == "html_compact" and e["flow_case_key"] == "Run_A"
    assert (f["impactor_ke_initial"], f["impactor_ke_final"], f["energy_dissipated"]) == (12.0, 3.0, 9.0)
    edge = f["edges"][0]
    assert (edge["peak_force"], edge["total_work"], edge["total_impulse"], edge["contact_id"]) == (900.0, 6.0, 0.02, 7)
    assert f["nodes"][0]["node_id"] == "1" and f["nodes"][0]["name"] == "plate"
    # ★솎은 시계열로 피크를 다시 재지 않는다 — null 과 까닭
    assert f["nodes"][0]["peak_ke"] is None and "원해상도 피크" in f["form_note"]


def test_energy_impact_compact_edge_names_are_read():
    """impact 압축본은 엣지 이름이 또 다르다(peak_f · total_w · total_imp · conf) — 실측."""
    flow = {"F1_DOE_001": {"ke_init": 201.5, "ke_final": 1.0, "dissipated": 5.0, "propagation_order": ["2", "1"],
                           "contact_available": True, "contact_n_iface": 3,
                           "nodes": [{"id": "2", "name": "n2", "is_impactor": True, "ke": [], "ie": [], "t": []}],
                           "edges": [{"src": "2", "dst": "1", "cid": 92, "name": "CR", "conf": 1.0, "t": [], "f": [],
                                      "imp": [], "w": [], "peak_f": 34.89, "total_imp": 0.0151, "total_w": 0.6009}]}}
    f = P.case_energy({"energy_flows": flow}, "impact", "F1_DOE_001")["energy_flow"]
    e = f["edges"][0]
    assert (e["peak_force"], e["total_work"], e["total_impulse"], e["confidence"]) == (34.89, 0.6009, 0.0151, 1.0)
    assert f["propagation_order"] == ["2", "1"]
    assert f["contact"]["available"] is True and f["contact"]["n_iface"] == 3, "접촉 계측 요약을 버리지 않는다"
    assert "엣지 confidence" not in f["form_note"], "있는 칸을 없다고 말하지 않는다"


def test_energy_neutral_form_still_reads():
    flow = {"Run_A": {"impactor_ke_initial": 12.0, "impactor_ke_final": 3.0, "energy_dissipated": 9.0,
                      "propagation_order": ["1", "2"],
                      "nodes": [{"node_id": "1", "name": "plate", "is_impactor": True, "peak_ke": 12.0, "peak_ie": 1.0}],
                      "edges": [{"src": "1", "dst": "2", "contact_id": 7, "peak_force": 900.0, "total_work": 6.0,
                                 "total_impulse": 0.02, "confidence": 0.9, "first_engage_t": 2e-5}]}}
    f = P.case_energy({"energy_flows": flow}, "sphere", "Run_A")["energy_flow"]
    assert f["form"] == "neutral" and "form_note" not in f
    assert f["nodes"][0]["peak_ke"] == 12.0 and f["edges"][0]["confidence"] == 0.9


def test_energy_does_not_fall_back_to_another_case():
    """★예전엔 요청한 각도에 상세가 없으면 **첫 흐름을 그 각도 이름으로** 돌려줬다(조용히 틀린 값)."""
    data = {"energy_flows": _sphere_compact(), "energy_flows_note": "상위 60 각도만 담았다"}
    e = P.case_energy(data, "sphere", "Run_Z")
    assert e["energy_flow"] is None and e["flow_case_key"] is None
    assert "Run_A" in e["available_case_keys"]
    assert "상위 60 각도" in e["note"] and "contact_profile" in e["note"]


def test_energy_without_case_key_says_which_case():
    e = P.case_energy({"energy_flows": _sphere_compact()}, "sphere", None)
    assert e["flow_case_key"] == "Run_A", "대표를 고르면 어느 케이스인지 적는다"


# ── 핫스팟 — sphere 각도별 ──────────────────────────────────────────────────────
def _run(folder, name, items):
    return {"folder": folder, "angle": {"name": name, "roll": 1.0, "pitch": 2.0, "yaw": 3.0}, "parts": {},
            "hotspot": items}


def _sphere_hotspot_data():
    # 압축 꼴 그대로 — p · cr · cl[c, r, k, n, s, (e, w, wd, t)]
    a = [{"p": 1, "cr": "von_mises", "cl": [{"c": [0, 0, 0], "r": 1.0, "k": 1, "n": 5, "s": 100.0},
                                            {"c": [1, 0, 0], "r": 0.5, "k": 2, "n": 3, "s": 80.0}]},
         {"p": 2, "cr": "min_principal", "cl": [{"c": [0, 1, 0], "r": 2.0, "k": 1, "n": 9, "s": -300.0,
                                                 "t": 5e-5}]}]
    b = [{"p": 1, "cr": "von_mises", "cl": [{"c": [0, 0, 1], "r": 1.5, "k": 1, "n": 7, "s": 250.0}]}]
    return {"parts": {"1": {"name": "Case"}, "2": {"name": "Board"}},
            "results": [_run("Run_A", "P0001", a), _run("Run_B", "P0002", b), _run("Run_C", "P0003", [])],
            "hotspot_parts": [1, 2]}


def test_sphere_hotspot_envelope_picks_the_worst_angle():
    h = P.hotspot_clusters(_sphere_hotspot_data(), top=10)
    assert h["available"] is True and h["kind"] == "sphere"
    assert (h["n_angles_total"], h["n_angles_with_clusters"], h["n_records"], h["n_clusters_all"]) == (3, 2, 3, 4)
    env = {(e["part_id"], e["criterion"]): e for e in h["envelope"]}
    vm = env[(1, "von_mises")]
    assert vm["worst_case_key"] == "Run_B" and vm["stress_max"] == 250.0 and vm["n_angles"] == 2
    assert vm["worst_angle"]["name"] == "P0002" and vm["part_name"] == "Case"
    # 절대값 순 — min_principal 의 -300 이 맨 앞
    assert h["envelope"][0]["criterion"] == "min_principal"
    assert [abs(c["stress_max"]) for c in h["clusters"]] == sorted(
        (abs(c["stress_max"]) for c in h["clusters"]), reverse=True)


def test_sphere_hotspot_case_filter_and_nothing_fabricated():
    h = P.hotspot_clusters(_sphere_hotspot_data(), case_key="Run_A", criterion="von_mises")
    assert {c["case_key"] for c in h["clusters"]} == {"Run_A"} and len(h["clusters"]) == 2
    # 포락은 각도 필터와 무관하게 전 각도 — von_mises 의 최강은 여전히 Run_B
    assert h["envelope"][0]["worst_case_key"] == "Run_B"
    row = h["clusters"][0]
    assert "volume" not in row and "stress_mean" not in row and "peak_element_id" not in row, "압축본에 없는 값"
    assert row["strain_max"] is None and row["peak_time"] is None, "없는 값은 0 이 아니라 null"
    assert "uniform" in h["compact_note"]


def test_sphere_hotspot_cap_note_is_passed_through():
    d = _sphere_hotspot_data()
    d["hotspot_cap_note"] = "군집은 순위 상위 20,000개만 담았습니다 (전체 31,000개)."
    assert P.hotspot_clusters(d)["cap_note"].startswith("군집은 순위 상위")


@_needs_sphere
def test_real_new_sphere_hotspots_come_out():
    h = P.hotspot_clusters(_raw(_SPHERE_NEW), top=200)
    assert h["available"] is True and h["kind"] == "sphere"
    assert (h["n_records"], h["n_clusters_all"]) == (13, 58), (h["n_records"], h["n_clusters_all"])
    assert all(c["case_key"] == "Run_20261017_165146_82a815" and c["angle"]["name"] == "P0001"
               for c in h["clusters"])
    vals = [abs(e["stress_max"]) for e in h["envelope"] if e["stress_max"] is not None]
    assert vals == sorted(vals, reverse=True)
    assert h["hotspot_parts"] == [1, 3, 15, 20, 21, 22, 23] and h["mesh_available"] is False
    assert "d3plot" in h["mesh_note"]


# ── 파트쌍 × 각도 접촉 프로파일 ────────────────────────────────────────────────
def _profile_data():
    return {
        "parts": {"1": {"name": "Case"}, "2": {"name": "Board"}, "3": {"name": "Glass"}},
        "results": [{"folder": "Run_A", "angle": {"name": "P0001"}}, {"folder": "Run_B", "angle": {"name": "P0002"}},
                    {"folder": "Run_C", "angle": {"name": "P0003"}}],
        "contact_profile": {
            "pairs": [{"key": "1>2", "src": "1", "dst": "2", "cid": 5, "name": "c12", "resolved": True},
                      {"key": "2>3", "src": "2", "dst": "3", "cid": 6, "name": "c23", "resolved": True},
                      {"key": "SS>1", "src": "SS", "dst": "1", "cid": 7, "name": "self", "resolved": False}],
            "pf": [[10.0, None, 30.0], [None, 50.0, None], [99.0, 1.0, None]],
            "ti": [[0.1, None, 0.3], [None, 0.5, None], [0.9, 0.1, None]],
            "tw": [[1.0, None, -3.0], [None, 2.0, None], [4.0, 1.0, None]],
        },
        "contact_trust": {"n_runs": 3, "newton3_worst_rel": 1e-6},
    }


def test_contact_profile_pairs_axis_and_none_are_honest():
    cp = P.contact_profile(_profile_data(), "sphere", top=10, case_key="Run_B")
    assert cp["available"] is True and (cp["n_pairs"], cp["n_resolved"], cp["n_axis"]) == (3, 2, 3)
    first = cp["pairs"][0]
    # 해석된 쌍이 먼저, 그 안에서 |최대| 순 — 미해석 쌍(SS>1)은 값이 커도 뒤
    assert first["key"] == "2>3" and first["peak"] == 50.0 and first["peak_case_key"] == "Run_B"
    assert cp["pairs"][-1]["resolved"] is False
    c12 = next(p for p in cp["pairs"] if p["key"] == "1>2")
    assert c12["n_engaged"] == 2 and c12["src_name"] == "Case", "None 칸은 접촉한 각도로 세지 않는다"
    a_b = next(a for a in cp["axis_summary"] if a["case_key"] == "Run_B")
    assert a_b["top_pair"] == "2>3" and a_b["n_engaged"] == 2
    keys = {e["key"] for e in cp["at"]["edges"]}
    assert keys == {"2>3", "SS>1"}, "그 각도에 접촉이 없는 쌍(1>2)은 엣지가 아니다"
    assert cp["trust"]["n_runs"] == 3


def test_contact_profile_work_uses_magnitude_and_matrix_guard():
    cp = P.contact_profile(_profile_data(), "sphere", metric="tw", matrix=True)
    c12 = next(p for p in cp["pairs"] if p["key"] == "1>2")
    assert c12["peak"] == -3.0 and c12["peak_case_key"] == "Run_C", "tw 는 음수가 있다 — |값| 으로 비교"
    assert len(cp["matrix"]["values"]) == 3 and len(cp["matrix"]["values"][0]) == 3
    small = P.contact_profile(_profile_data(), "sphere", matrix=True, max_cells=4)
    assert small["matrix"] is None and "상한" in small["matrix_note"], "크면 잘랐다고 말한다"
    assert P.contact_profile(_profile_data(), "sphere", metric="xx")["available"] is False


def test_contact_profile_absent_says_why():
    cp = P.contact_profile({"results": []}, "sphere")
    assert cp["available"] is False and "matsum" in cp["note"]


@_needs_sphere
def test_real_new_sphere_contact_profile():
    cp = P.contact_profile(_raw(_SPHERE_NEW), "sphere", top=50, case_key="Run_20261017_165146_82a815")
    assert (cp["n_pairs"], cp["n_axis"]) == (22, 1)
    assert cp["at"]["found"] is True and len(cp["at"]["edges"]) == 22
    assert cp["trust"]["n_interfaces"] == 26


@_needs_impact
def test_real_impact_contact_profile_runs_over_positions():
    cp = P.contact_profile(_raw(_IMPACT), "impact", top=1, axis_top=1)
    assert cp["axis_kind"] == "position" and (cp["n_pairs"], cp["n_axis"]) == (23, 25)
    top = cp["pairs"][0]
    assert (top["key"], top["peak"], top["peak_case_key"]) == ("20>1", 3532.6212, "F5_DOE_025"), top
    assert cp["axis_summary"][0]["case_key"] == "F5_DOE_025"


@_needs_impact
def test_real_impact_energy_values_are_not_null():
    raw = _raw(_IMPACT)
    k = next(k for k, v in raw["energy_flows"].items() if v.get("edges"))
    f = P.case_energy(raw, "impact", k)["energy_flow"]
    assert all(e["peak_force"] is not None and e["total_work"] is not None for e in f["edges"]), (
        "impact 압축본의 접촉력이 이름 때문에 null 로 사라졌다")


# ── 정규화의 새 키 ─────────────────────────────────────────────────────────────
@_needs_sphere
def test_real_new_sphere_normalization_reads_new_keys():
    st = P.parse_data(_raw(_SPHERE_NEW))
    assert st["sim_params"]["unit_system"] == "ton-mm-s"
    assert st["summary"]["unit_system"]["detected"] is True
    assert st["summary"]["analyzer_builds"] == {"be9d2b0": 1}
    m = next(iter(st["cases"][0]["parts_metrics"].values()))
    assert {"pulse_width_ms", "pulse_impulse"} <= set(m), "원해상도 펄스 지표를 평탄화한다"


# ── 실 DB 반입 → 서비스 · 라우트 ────────────────────────────────────────────────
async def _mk(db):
    u = User(email=f"cthot_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="cthot", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _cleanup(db, u, s):
    import shutil
    await db.execute(delete(ImpactReport).where(ImpactReport.session_id == s.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    shutil.rmtree(storage.session_abs_dir(u.id, s.id), ignore_errors=True)


@_needs_sphere
@_aio
async def test_ingested_new_sphere_is_queryable(db):
    from app.modules.reports import services as svc

    u, s = await _mk(db)
    try:
        rep = await svc.ingest_report(db, s, filename="sphere_new.html", raw=_SPHERE_NEW.read_bytes())
        assert rep.kind == "sphere" and rep.n_cases == 1
        h = await svc.hotspots(db, rep, top=5)
        assert h["available"] is True and h["n_records"] == 13
        ck = "Run_20261017_165146_82a815"
        cp = await svc.contact_profile(db, rep, case_key=ck)
        assert cp["at"]["found"] and len(cp["at"]["edges"]) == 22
        e = await svc.case_energy(db, rep, ck)
        assert e["energy_flow"]["edges"][0]["peak_force"] is not None
        bad = await svc.case_energy(db, rep, "Run_nope")
        assert bad["energy_flow"] is None
    finally:
        await _cleanup(db, u, s)


@pytest.fixture
async def api(db):
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    transport = ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@_needs_sphere
@_aio
async def test_contact_profile_route(api, db, monkeypatch):
    from app.config import settings
    from app.modules.reports import services as svc

    monkeypatch.setattr(settings, "ratelimit_enabled", False)
    u, s = await _mk(db)
    try:
        rep = await svc.ingest_report(db, s, filename="sphere_new.html", raw=_SPHERE_NEW.read_bytes())
        tok = (await api.post("/api/v1/auth/login", json={"email": u.email, "password": "pw123456"})
               ).json()["data"]["access_token"]
        h = {"Authorization": "Bearer %s" % tok}
        r = await api.get("/api/v1/reports/%s/contact_profile" % rep.id, params={"metric": "ti", "axis_top": 1},
                          headers=h)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["available"] is True and d["metric_name"] == "total_impulse" and len(d["axis_summary"]) == 1
        bad = await api.get("/api/v1/reports/%s/contact_profile" % rep.id, params={"metric": "xx"}, headers=h)
        assert bad.status_code == 422
        hs = await api.get("/api/v1/reports/%s/hotspots" % rep.id,
                           params={"case_key": "Run_20261017_165146_82a815", "top": 3}, headers=h)
        assert hs.status_code == 200 and hs.json()["data"]["kind"] == "sphere"
    finally:
        await _cleanup(db, u, s)
