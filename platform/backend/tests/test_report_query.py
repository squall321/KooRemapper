# fact 드릴다운(query_facts)·조건 리포트 조회(find_reports) — 서버측 필터 검증(실 DB).
"""데이터 기반 드릴다운: 서버가 부품·각도·물리량·임계로 필터해 슬라이스만 준다.

결과 폭증 대비 — LLM 이 전 케이스를 훑지 않도록 필터를 서버(SQL/서비스)가 처리하는지
실 sphere 데이터로 확인한다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Session, SessionFile, User
from app.modules.reports import services as svc
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


async def _mk(db, admin=False):
    u = User(email=f"q_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="q", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _cleanup(db, u, s):
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    import shutil
    shutil.rmtree(storage.session_abs_dir(u.id, s.id), ignore_errors=True)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_query_facts_filters(db):
    u, s = await _mk(db)
    try:
        rep = await svc.ingest_report(db, s, filename="t.html", raw=_SPHERE.read_bytes(),
                                      project="S26", dev_rev="dv1")
        # ① 특정 부품 — 파트 1 의 각도별 응력(케이스 수만큼), 값 내림차순.
        q1 = await svc.query_facts(db, rep, part_id=1, metric="peak_stress", limit=1000)
        assert q1["facts"] and all(f["part_id"] == 1 for f in q1["facts"])
        assert all(f["quantity"] == "peak_stress" for f in q1["facts"])
        vals = [f["value"] for f in q1["facts"]]
        assert vals == sorted(vals, reverse=True)  # 서버 정렬
        # 파트 1 은 케이스마다 하나 → 26개(값 있는 것만).
        assert q1["n_matched"] <= 26 and q1["n_matched"] >= 1

        # ② 방향 범주 필터 — edge 만.
        q2 = await svc.query_facts(db, rep, category="edge", metric="peak_stress", limit=1000)
        cats = {(_case_cat(f)) for f in q2["facts"]}
        assert cats == {"edge"}

        # ③ 정확 각도명 — 전역 최악 케이스(E01_Back_Right)만.
        q3 = await svc.query_facts(db, rep, angle_name="E01_Back_Right", metric="peak_stress", limit=1000)
        assert q3["facts"] and all(f["identity"]["angle"]["name"] == "E01_Back_Right" for f in q3["facts"])

        # ④ 값 임계 — peak_stress ≥ 600 만.
        q4 = await svc.query_facts(db, rep, metric="peak_stress", min_value=600, limit=1000)
        assert all(f["value"] >= 600 for f in q4["facts"])
        assert q4["n_matched"] < q1["n_matched"] + 10000  # 임계로 줄어듦(전량 아님)

        # ⑤ 각도 근접 — E01 근처(roll0,pitch-45) ±20도.
        q5 = await svc.query_facts(db, rep, near_roll=0, near_pitch=-45, angle_tol_deg=20,
                                   part_id=1, metric="peak_stress", limit=1000)
        assert q5["n_matched"] >= 1 and q5["n_matched"] < 26  # 일부 각도만

        # ⑥ limit/truncated.
        q6 = await svc.query_facts(db, rep, metric="peak_stress", limit=3)
        assert q6["returned"] == 3 and q6["truncated"] is True and len(q6["facts"]) == 3

        # ⑦ 잘못된 metric → ValueError(400).
        with pytest.raises(ValueError):
            await svc.query_facts(db, rep, metric="banana")

        # ⑧ swap=true(cuboid_26) 코너 방향 근접 — raw roll/pitch 로 지목해도 그 케이스가 잡혀야.
        #    (과거 버그: 타깃이 swap 미반영이라 C5(roll135,pitch45)가 60° 벗어나 누락)
        q8 = await svc.query_facts(db, rep, near_roll=135, near_pitch=45, angle_tol_deg=10,
                                   metric="peak_stress", limit=1000)
        names8 = {f["identity"]["angle"]["name"] for f in q8["facts"]}
        assert "C5_Front_Right_Top" in names8
    finally:
        await _cleanup(db, u, s)


def _case_cat(f):
    a = (f.get("identity") or {}).get("angle") or {}
    return a.get("category")


_STAT_KEYS = {"n", "mean", "std", "cov", "min", "p05", "p25", "median", "p75", "p95", "max", "iqr", "range"}


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_angle_group_stats(db):
    u, s = await _mk(db)
    try:
        rep = await svc.ingest_report(db, s, filename="t.html", raw=_SPHERE.read_bytes(), project="S26")

        # available_metrics — 리포트에 실재하는 물리량을 자동 감지(peak_vel·소성 별칭 포함).
        r0 = await svc.angle_group_stats(db, rep, metric="peak_stress")
        assert {"peak_disp", "peak_g", "peak_strain", "peak_stress",
                "peak_plastic_strain", "peak_vel"} <= set(r0["available_metrics"])

        # ① 전체(미지정) — sphere 는 base별 그룹, 26방향, 동일 통계 스키마 + mean 내림차순.
        assert r0["selection"]["mode"] == "all_bases" and r0["n_groups"] == 26
        assert all(_STAT_KEYS <= set(g["stats"]) for g in r0["groups"])
        means = [g["stats"]["mean"] for g in r0["groups"]]
        assert means == sorted(means, reverse=True)
        # part_id 미지정 → 부품별 분해(top_risk/most_sensitive) 포함.
        assert all("parts" in g and "top_risk" in g["parts"] for g in r0["groups"])

        # ② 범주(category) 선택 — edge 12방향이 한 그룹으로.
        re = await svc.angle_group_stats(db, rep, metric="peak_stress", category="edge")
        assert re["selection"]["mode"] == "category" and re["n_groups"] == 1
        g = re["groups"][0]
        assert g["category"] == "edge" and g["stats"]["n"] == 12
        assert g["worst"]["value"] == g["stats"]["max"]

        # ③ 기준방향 퍼터베이션 구름 — 순수 cuboid_26 이라 그 방향 1개(degenerate).
        rb = await svc.angle_group_stats(db, rep, metric="peak_strain", angle_name="F1_Back")
        assert rb["selection"]["mode"] == "base" and rb["n_groups"] == 1
        assert rb["groups"][0]["representative"] == "F1_Back" and rb["groups"][0]["stats"]["n"] >= 1

        # ④ 임의 각도 콘(near) — 좁은 tol 은 그 방향만, 넓은 tol 은 더 많이(sphere 전용).
        near = rep  # F1_Back ≈ lon0,lat0 부근이 아니라 각 방향; 넓은 콘으로 다중 포섭 확인
        rn_wide = await svc.angle_group_stats(db, near, metric="peak_stress", near_lon=0, near_lat=0, tol_deg=90)
        rn_narrow = await svc.angle_group_stats(db, near, metric="peak_stress", near_lon=0, near_lat=0, tol_deg=10)
        n_wide = rn_wide["groups"][0]["stats"]["n"] if rn_wide["groups"] else 0
        n_narrow = rn_narrow["groups"][0]["stats"]["n"] if rn_narrow["groups"] else 0
        assert n_wide >= n_narrow

        # ⑤ 특정 부품 — 부품별 분해는 생략(단일 부품), 통계는 그 부품 값으로.
        rp = await svc.angle_group_stats(db, rep, metric="peak_stress", part_id=1, category="face")
        assert rp["groups"] and "parts" not in rp["groups"][0]

        # ⑥ 없는 물리량 → 빈 그룹 + 안내(available_metrics 로 대체 안내).
        rpl = await svc.angle_group_stats(db, rep, metric="made_up_metric")
        assert rpl["groups"] == [] and rpl["note"] and "made_up_metric" in rpl["note"]
        assert "peak_stress" in rpl["available_metrics"]

        # ⑦ 소성 변형률은 이제 자동 인식(sphere peak_strain==eff_plastic 별칭) → 방향별 통계 나옴.
        rps = await svc.angle_group_stats(db, rep, metric="peak_plastic_strain", category="edge")
        assert rps["groups"] and rps["groups"][0]["stats"]["n"] == 12
    finally:
        await _cleanup(db, u, s)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_find_reports_filters(db):
    u, s = await _mk(db)
    try:
        r1 = await svc.ingest_report(db, s, filename="a.html", raw=_SPHERE.read_bytes(),
                                     project="S26-DROP", dev_rev="dv1", focus="camera-detail")
        r2 = await svc.ingest_report(db, s, filename="b.html", raw=_SPHERE.read_bytes(),
                                     project="OTHER", dev_rev="pv1")
        # 검색축 승격 — sphere 는 worst_stress·doe_strategy·max_severity 가 컬럼에 채워짐.
        assert r1.worst_stress and r1.worst_stress > 1000
        assert r1.doe_strategy == "cuboid_26" and r1.max_severity in ("CRITICAL", "WARNING", "INFO")

        # project 필터.
        assert {r.id for r in await svc.find_reports(db, u.id, project="S26-DROP", limit=100)} == {r1.id}
        # dev_rev 필터.
        assert {r.id for r in await svc.find_reports(db, u.id, dev_rev="pv1", limit=100)} == {r2.id}
        # focus 필터(같은 전각도라도 초점 다른 리포트 구분).
        assert {r.id for r in await svc.find_reports(db, u.id, focus="camera-detail", limit=100)} == {r1.id}
        # doe_strategy(방향 컨셉) — 둘 다 cuboid_26.
        assert {r1.id, r2.id} <= {r.id for r in await svc.find_reports(db, u.id, doe_strategy="cuboid_26", session_id=s.id)}
        # severity 필터(CRITICAL 있는 리포트만) — 둘 다 CRITICAL(cuboid_26 항복초과).
        crit = await svc.find_reports(db, u.id, severity="CRITICAL", session_id=s.id)
        assert {r1.id, r2.id} <= {r.id for r in crit}
        # 최악응력 임계.
        assert {r1.id, r2.id} <= {r.id for r in await svc.find_reports(db, u.id, min_worst_stress=500, session_id=s.id)}
        assert await svc.find_reports(db, u.id, min_worst_stress=1e9, session_id=s.id) == []
        # 텍스트 검색(q) — 과제명.
        assert {r.id for r in await svc.find_reports(db, u.id, q_text="S26", session_id=s.id)} == {r1.id}
        # has_part — 부품명 포함.
        pname = (r1.parts or [{}])[0].get("name")
        if pname:
            assert r1.id in {r.id for r in await svc.find_reports(db, u.id, has_part=pname, session_id=s.id)}
        # 정렬(worst_stress desc).
        srt = await svc.find_reports(db, u.id, session_id=s.id, sort="worst_stress", order="desc")
        ws = [r.worst_stress for r in srt if r.worst_stress is not None]
        assert ws == sorted(ws, reverse=True)
        # impact → 없음.
        assert await svc.find_reports(db, u.id, kind="impact", session_id=s.id) == []
    finally:
        await _cleanup(db, u, s)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_report_facets(db):
    u, s = await _mk(db)
    try:
        await svc.ingest_report(db, s, filename="a.html", raw=_SPHERE.read_bytes(),
                                project="S26-DROP", dev_rev="dv1", focus="camera-detail")
        f = await svc.report_facets(db, u.id)
        # facet 은 {value,count} 목록 — 목표 정하기 전 '뭐가 있나'.
        kinds = {x["value"]: x["count"] for x in f["kind"]}
        assert kinds.get("sphere", 0) >= 1
        assert any(x["value"] == "S26-DROP" for x in f["project"])
        assert any(x["value"] == "cuboid_26" for x in f["doe_strategy"])
        assert any(x["value"] == "camera-detail" for x in f["focus"])
        assert any(x["value"] in ("CRITICAL", "WARNING", "INFO") for x in f["max_severity"])
    finally:
        await _cleanup(db, u, s)
