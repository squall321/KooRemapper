# 레시피 DB 통합 — 제안 → 실행(execute_run 직접) → 평가 → 등록 관문 → 내보내기. 실제 dev DB.
"""Full recipe lifecycle against the live dev DB.

★ The dev DB is the running worker's DB — we must NOT leave a queued recipe job,
or the worker claims it (memory: kooremapper-test-env-traps). So the run row is
inserted with status 'running' and execute_run is called in-process.
"""
import sys
from pathlib import Path

import pytest
import ulid
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models import (ImpactReport, Job, Recipe, RecipeRun, RecipeVersion, Session,
                        SessionFile, User)
from app.modules.recipes import services as rsvc
from app.modules.reports import services as report_svc
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")

# cases 만 쓰는(데이터 재파싱 없는) 레시피 — 파트별 최악 응력 상위 N.
TOP_PARTS = '''
def run(reports, params):
    n = int(params.get("top", 3))
    out = []
    for rep in reports:
        worst = rep.part_worst()
        ranked = sorted(worst.values(), key=lambda a: -(a["worst_stress"]["value"] or 0))[:n]
        out.append({"report": rep.id, "top": [
            {"part_id": p["part_id"], "name": p["part_name"],
             "stress": p["worst_stress"]["value"], "case": p["worst_stress"]["case_key"]}
            for p in ranked]})
    return {"reports": out}

def test_top_parts():
    import recipe_kit
    rep = recipe_kit.make_report(kind="sphere",
        parts=[{"part_id": 1, "name": "A"}, {"part_id": 2, "name": "B"}],
        cases=[{"case_key": "k1", "parts_metrics": {"1": {"peak_stress": 9.0}, "2": {"peak_stress": 3.0}}}])
    out = run([rep], {"top": 1})
    assert out["reports"][0]["top"][0]["part_id"] == 1
    assert out["reports"][0]["top"][0]["stress"] == 9.0
'''


async def _mk(db):
    u = User(email=f"rcp_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="rcp", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _cleanup(db, u, s, recipe_name):
    r = await rsvc.get_recipe(db, recipe_name)
    if r is not None:
        await db.execute(delete(RecipeRun).where(RecipeRun.recipe_id == r.id))
        await db.execute(delete(RecipeVersion).where(RecipeVersion.recipe_id == r.id))
        await db.execute(delete(Recipe).where(Recipe.id == r.id))
    await db.execute(delete(Job).where(Job.user_id == u.id))
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    import shutil
    shutil.rmtree(storage.session_abs_dir(u.id, s.id), ignore_errors=True)


async def test_propose_validation_errors(db):
    u, s = await _mk(db)
    name = f"t_{ulid.new().str.lower()[:12]}"
    try:
        # 이름 규칙
        with pytest.raises(rsvc.RecipeServiceError):
            await rsvc.propose(db, u, name="Bad-Name", code=TOP_PARTS, meta=None)
        # 정적 검사 실패(금지 import)
        with pytest.raises(rsvc.RecipeServiceError):
            await rsvc.propose(db, u, name=name, code="import os\ndef run(r,p):\n return 1\ndef test_x():\n assert run([],{})", meta=None)
    finally:
        await _cleanup(db, u, s, name)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_full_lifecycle(db, tmp_path):
    u, s = await _mk(db)
    name = f"t_{ulid.new().str.lower()[:12]}"
    old_export = settings.recipe_export_dir
    settings.recipe_export_dir = str(tmp_path / "recipes")
    try:
        rep = await report_svc.ingest_report(db, s, filename="t.html", raw=_SPHERE.read_bytes(),
                                              project="RCP", dev_rev="dv1")

        # ① 제안 → 후보(자기 시험 통과)
        pr = await rsvc.propose(db, u, name=name, code=TOP_PARTS,
                                meta={"title": "파트별 최악 응력", "kinds": ["sphere"], "tags": ["stress"]})
        assert pr["status"] == "candidate", pr
        assert pr["checks"]["selftest_ok"] is True

        r = await rsvc.get_recipe(db, name)
        v = await rsvc.get_version(db, r.id, 1)

        # ② 실행 — running 으로 넣고 execute_run 직접(워커 레이스 회피)
        run_id = ulid.new().str
        job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id, operation="recipe",
                  status="running",
                  args={"recipe": name, "version": 1, "recipe_id": r.id, "version_id": v.id,
                        "run_id": run_id, "report_ids": [rep.id], "params": {"top": 2},
                        "with_data": False})
        db.add(job)
        run = RecipeRun(id=run_id, recipe_id=r.id, version_id=v.id, version=1, job_id=job.id,
                        session_id=s.id, user_id=u.id, report_ids=[rep.id], report_kinds=["sphere"],
                        params={"top": 2}, status="running")
        db.add(run)
        await db.commit()

        await rsvc.execute_run(db, job)
        await db.refresh(run)
        assert run.status == "succeeded", run.error
        assert run.result and run.result["reports"][0]["top"], run.result
        assert run.output_file_id is not None
        assert run.sandbox.get("limits") is True

        # ③ 등록 관문 — 평가 전에는 막힌다
        with pytest.raises(rsvc.RecipeServiceError) as exc:
            await rsvc.register(db, u, name=name, version=1)
        assert "평가" in str(exc.value)

        # ④ 평가 → ⑤ 등록
        await rsvc.evaluate(db, u, run_id=run_id, useful=True,
                            note="sphere 리포트에서 파트 최악 응력 상위를 한 번에 뽑아 비교가 빨라졌다")
        reg = await rsvc.register(db, u, name=name, version=1)
        assert reg["status"] == "registered"
        assert Path(reg["exported"]).exists()
        assert (tmp_path / "recipes" / name / "recipe.py").exists()

        await db.refresh(r)
        assert r.current_version == 1

        # ⑥ 검색 · 상세
        found = await rsvc.search(db, u.id, q="stress")
        assert any(d["name"] == name and d["registered"] for d in found)
        detail = await rsvc.get_detail(db, name, u.id)
        assert detail["current_version"] == 1
        assert detail["versions"][0]["status"] == "registered"
    finally:
        settings.recipe_export_dir = old_export
        await _cleanup(db, u, s, name)
