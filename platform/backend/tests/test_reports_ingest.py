# 리포트 인제스트 서비스 end-to-end (실 DB): 저장·정규화·랭킹·파트리스크.
"""End-to-end DB tests for impact/drop report ingestion.

Runs against the live dev postgres (see conftest). Uses REAL generated report
HTML; each test is self-cleaning. Skips when a sample HTML is unavailable.
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
_DEEP = Path("/data/SmartTwinPostprocessor/lib/koo_deep_report/single_report/report.html")
_IMPACT = Path("/tmp/claude-1000/-home-koopark-claude-KooRemapper/"
               "c1650bf4-b3b2-4d9d-88d1-a34a9ec0f959/scratchpad/impact_report.html")


async def _mk_user_session(db):
    u = User(
        email=f"rpt_{ulid.new().str}@kooremapper.test",
        password_hash=security.hash_password("x"),
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(
        id=sid, user_id=u.id, name="rpt-test",
        storage_path=storage.session_rel_dir(u.id, sid),
    )
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
    d = storage.session_abs_dir(u.id, s.id)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_ingest_sphere_and_query(db):
    u, s = await _mk_user_session(db)
    try:
        raw = _SPHERE.read_bytes()
        rep = await svc.ingest_report(db, s, filename="Test_001_report.html", raw=raw)
        assert rep.kind == "sphere"
        assert rep.n_cases == 26
        assert rep.source_file_id is not None  # 원본 HTML 이 SessionFile 로 저장됨

        # 랭킹: 최대 응력 내림차순 top1 이 전역 최악과 일치.
        top = await svc.list_cases(db, rep.id, sort="max_stress", order="desc", limit=1)
        assert top and top[0].case_key == rep.summary["worst_stress"]["case_key"]

        # 파트 리스크: 전 파트 최악값 계산.
        pr = await svc.part_risk(db, rep)
        assert pr["parts"] and pr["parts"][0]["worst_stress"]["value"] is not None

        # 방향 취약도: cuboid_26 → 면/엣지/코너 범주가 잡힌다.
        dr = await svc.directional(db, rep)
        cats = {d["category"] for d in dr["directions"]}
        assert cats & {"face", "edge", "corner"}
        assert dr["directions"][0]["worst_stress"]["value"] is not None

        # 에너지 상세(원본 재파싱) — sphere 는 하중경로(이 샘플은 비어 note).
        en = await svc.case_energy(db, rep, top[0].case_key)
        assert en["kind"] == "sphere"
    finally:
        await _cleanup(db, u, s)


@pytest.mark.skipif(not _DEEP.exists(), reason="deep 샘플 없음")
async def test_ingest_deep(db):
    u, s = await _mk_user_session(db)
    try:
        rep = await svc.ingest_report(db, s, filename="report.html", raw=_DEEP.read_bytes())
        assert rep.kind == "deep"
        assert rep.n_cases == 1
        cases = await svc.list_cases(db, rep.id, limit=5)
        assert cases[0].case_key == "single"
        assert cases[0].max_stress == pytest.approx(3748.51419693, rel=1e-6)
    finally:
        await _cleanup(db, u, s)


@pytest.mark.skipif(not _IMPACT.exists(), reason="impact 샘플 없음")
async def test_ingest_impact(db):
    u, s = await _mk_user_session(db)
    try:
        rep = await svc.ingest_report(db, s, filename="impact_report.html", raw=_IMPACT.read_bytes())
        assert rep.kind == "impact"
        assert rep.n_cases == 50  # 2면 × 25위치
        top = await svc.list_cases(db, rep.id, sort="max_g", order="desc", limit=1)
        assert top and top[0].identity.get("face") in {"F1", "F2"}
    finally:
        await _cleanup(db, u, s)
