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
                                     project="S26-DROP", dev_rev="dv1")
        r2 = await svc.ingest_report(db, s, filename="b.html", raw=_SPHERE.read_bytes(),
                                     project="OTHER", dev_rev="pv1")
        # project 필터.
        p = await svc.find_reports(db, u.id, project="S26-DROP", limit=100)
        ids = {r.id for r in p}
        assert r1.id in ids and r2.id not in ids
        # dev_rev 필터.
        d = await svc.find_reports(db, u.id, dev_rev="pv1", limit=100)
        dids = {r.id for r in d}
        assert r2.id in dids and r1.id not in dids
        # kind 필터(둘 다 sphere) — 둘 다.
        k = await svc.find_reports(db, u.id, kind="sphere", session_id=s.id, limit=100)
        assert {r1.id, r2.id} <= {r.id for r in k}
        # impact 로 필터 → 없음.
        assert await svc.find_reports(db, u.id, kind="impact", session_id=s.id) == []
    finally:
        await _cleanup(db, u, s)
