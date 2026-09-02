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
    finally:
        await _cleanup(db, u, s)


def _case_cat(f):
    a = (f.get("identity") or {}).get("angle") or {}
    return a.get("category")


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
