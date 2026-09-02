# 리포트 provenance — scenario 조건 요약·K파일 자동매칭·과제메타 수동설정 검증.
"""1 K : N 해석결과 매칭 + scenario.json 조건 + 과제명/rev 수동 설정.

- summarize_scenario: cuboid+tolerance → 26×doe_count(실측 검증된 확장 규칙) 등.
- E2E(실 DB): scenario 동반 인제스트 → template 로 K 자동매칭, eng_meta 수동 설정,
  kfile_id 필터(한 K에 매달린 리포트들), 등재 폴백.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Session, SessionFile, User
from app.modules.reports import services as svc
from app.reports.scenario import ScenarioParseError, summarize_scenario
from app.shared import security, storage

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


# ── scenario 요약 유닛 ───────────────────────────────────────────────
def _cuboid_scatter_scenario(doe_count=5, template="MinimumModel.k"):
    return {
        "project_name": "Scatter26",
        "simulation_params": {"height": 1500, "tFinal": 0.001, "dt": 1e-6},
        "scenarios": [{
            "scenario_name": "Cuboid26_scatter",
            "template": template,
            "angle_source": {"source_type": "cuboid_geometry",
                             "cuboid_geometry": {"include_faces": True, "include_edges": True,
                                                 "include_corners": True}},
            "cumulative": {"num_steps": 1, "mode_sequence": ["DROP"]},
            "tolerance": {"roll": {"min": -2, "max": 2}, "pitch": {"min": -2, "max": 2},
                          "yaw": {"min": -2, "max": 2}, "doe_type": "lhs", "doe_count": doe_count},
        }],
    }


def test_summarize_cuboid_scatter():
    s = summarize_scenario(_cuboid_scatter_scenario(doe_count=5))
    sc = s["scenarios"][0]
    assert sc["source_type"] == "cuboid_geometry"
    assert sc["n_base_directions"] == 26
    assert sc["tolerance"]["doe_count"] == 5 and sc["tolerance"]["doe_type"] == "lhs"
    assert sc["expected_runs"] == 130  # 26 × 5 (방향마다 doe_count — 실측 규칙)
    assert s["templates"] == ["MinimumModel.k"]
    assert s["sim_params"]["drop_height"] == 1500.0


def test_summarize_guards_inf_and_sweep_off_by_one():
    # json 은 1e999→inf 를 통과시킨다 — int(inf) 500 이 아니라 None 으로 방어.
    s = summarize_scenario({"scenarios": [{"template": "m.k", "angle_source": {
        "source_type": "fibonacci_lattice", "fibonacci_lattice": {"num_directions": 1e999}}}]})
    assert s["scenarios"][0]["n_base_directions"] is None
    # 스윕 부동소수 절단: 0→0.3 step 0.1 은 4점(0,.1,.2,.3)이어야 한다.
    s2 = summarize_scenario({"scenarios": [{"template": "m.k", "angle_source": {
        "source_type": "pitching_sweep",
        "pitching_sweep": {"pitch_min": 0, "pitch_max": 0.3, "pitch_step": 0.1}}}]})
    assert s2["scenarios"][0]["n_base_directions"] == 4


def test_summarize_fibonacci_and_errors():
    s = summarize_scenario({
        "scenarios": [{"template": "m.k", "angle_source": {
            "source_type": "fibonacci_lattice", "fibonacci_lattice": {"num_directions": 162}}}],
    })
    assert s["scenarios"][0]["n_base_directions"] == 162
    assert s["scenarios"][0]["expected_runs"] == 162  # tolerance 없으면 기준방향수 그대로
    with pytest.raises(ScenarioParseError):
        summarize_scenario({"not": "a scenario"})


# ── E2E (실 DB) ─────────────────────────────────────────────────────
async def _mk_user_session(db):
    u = User(email=f"prov_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="prov",
                storage_path=storage.session_rel_dir(u.id, sid))
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


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_ingest_with_scenario_meta_and_kfile_match(db):
    u, s = await _mk_user_session(db)
    try:
        # 세션에 K파일(scenario template 와 동명) 등록.
        kf = SessionFile(session_id=s.id, filename="MinimumModel.k",
                         rel_path=f"{s.storage_path}/MinimumModel.k", kind="input", size_bytes=1)
        db.add(kf)
        await db.commit()
        await db.refresh(kf)

        scen = json.dumps(_cuboid_scatter_scenario()).encode()
        rep = await svc.ingest_report(
            db, s, filename="Test_001_report.html", raw=_SPHERE.read_bytes(),
            scenario_raw=scen, scenario_filename="scenario.json",
            project="S26-DROP", dev_rev="dv1", variation="antA",
        )
        # ① scenario 조건 요약 캐시 + ② template 로 K 자동매칭 + ③ 수동 과제메타.
        assert rep.scenario["scenarios"][0]["expected_runs"] == 130
        assert rep.source_kfile_id == kf.id
        assert rep.eng_meta["project"] == "S26-DROP"
        assert rep.eng_meta["dev_revision"] == {"phase": "dv", "round": "1", "code": "dv1"}
        assert rep.eng_meta["design_variation"] == "antA"
        assert rep.scenario_file_id is not None

        # ④ 1 K : N — 같은 K로 리포트 하나 더 → kfile 필터로 둘 다 조회.
        rep2 = await svc.ingest_report(
            db, s, filename="Test_001_again.html", raw=_SPHERE.read_bytes(), kfile_id=kf.id)
        both = await svc.list_reports(db, s.id, kfile_id=kf.id)
        assert {r.id for r in both} == {rep.id, rep2.id}
        none = await svc.list_reports(db, s.id, kfile_id=999999999)
        assert none == []

        # ⑤ PATCH 수동 갱신 — rev 만 바꿔도 기존 project 보존.
        rep = await svc.update_report_meta(db, rep, dev_rev="pv1")
        assert rep.eng_meta["project"] == "S26-DROP"
        assert rep.eng_meta["dev_revision"]["code"] == "pv1"
        # ⑤-b ""=삭제 시맨틱 — 칸 비우고 저장하면 그 필드가 지워진다(조용한 no-op 금지).
        rep = await svc.update_report_meta(db, rep, variation="")
        assert "design_variation" not in (rep.eng_meta or {})
        assert rep.eng_meta["project"] == "S26-DROP"  # 다른 필드는 보존
        # ⑤-c 동명 K 재업로드(dedup: _1) 시 최신 파일에 매칭.
        kf2 = SessionFile(session_id=s.id, filename="MinimumModel_1.k",
                          rel_path=f"{s.storage_path}/MinimumModel_1.k", kind="input", size_bytes=1)
        db.add(kf2)
        await db.commit()
        await db.refresh(kf2)
        from app.modules.reports.services import _match_kfile_by_templates
        assert await _match_kfile_by_templates(db, s.id, ["MinimumModel.k"]) == kf2.id
        with pytest.raises(ValueError):
            await svc.update_report_meta(db, rep, dev_rev="banana")  # 형식 오류
        with pytest.raises(ValueError):
            await svc.update_report_meta(db, rep, kfile_id=999999999)  # 남의/없는 파일

        # ⑥ project 자동 폴백 — 수동 project 안 줘도 임베드 project_name 이 eng_meta 에 채워짐.
        assert rep2.eng_meta and rep2.eng_meta["project"] == "Test_001_Full26_1Step"
        # dev_rev 는 여전히 없으므로 등재는 stage 없음으로 400(project 는 폴백으로 있음).
        with pytest.raises(ValueError, match="project/stage"):
            await svc.publish_to_datahub(db, rep2, hub_url="http://127.0.0.1:1")
    finally:
        await _cleanup(db, u, s)
