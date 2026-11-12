# 낙하 파이프라인 DynaForge 몫 API 셋 — get_job 외부 요약 · find_reports 잡 키 거르기 · 시스템 상태의 후처리 판
"""포털 낙하 파이프라인 개선(사용자 지시 2026-11-12) — 덧붙이기만 하는 API 셋을 고정한다.

(a) `JobRead.external` — 원본 `external_ref` 대신 가린 요약 `{kind, cluster_state, ontology: {state, why?}}`.
(b) `find_reports(external_job_key=…)` — 후처리 예약이 반입한 리포트의 잡 키 `stcx:<Slurm 잡 id>` 정확히 같음.
(c) `/system/status.postprocess_versions` — 최근 리포트의 `ontology.producer` 서로 다른 판 · 수 · 마지막 시각.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import ulid
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ImpactReport, Session, User  # noqa: E402
from app.modules.jobs.schemas import JobRead  # noqa: E402
from app.modules.reports import services as svc  # noqa: E402
from app.modules.system.routes import _postprocess_versions  # noqa: E402
from app.shared import security, storage  # noqa: E402

async_db = pytest.mark.asyncio(loop_scope="session")


def _job(**over):
    base = dict(id="J", session_id="S", operation="op", args={}, resolved_cmd=None, status="succeeded",
                progress=100, exit_code=0, input_file_ids=[], output_file_ids=[], error_summary=None,
                warnings=None, created_at=datetime.now(timezone.utc), started_at=None, finished_at=None,
                external_kind=None, external_ref=None)
    base.update(over)
    return SimpleNamespace(**base)


# ── (a) get_job 의 외부 요약 ────────────────────────────────────────────────

def test_an_external_job_carries_a_redacted_summary_and_not_the_raw_ref():
    ref = {"job_key": "stcx:924", "slurm_job_id": "924", "result_dir": str(Path.home() / "r" / "x"),
           "upload_id": "up-9", "cluster_state": "COMPLETED",
           "ontology": {"state": "failed", "why": f"꾸러미가 결과 폴더 밖에 있다(path={Path.home()}/a.json) — a@b.com"}}
    d = JobRead.model_validate(_job(external_kind="kooslurm_return", external_ref=ref)).model_dump()
    assert "external_ref" not in d and "external_kind" not in d, "원본은 응답에 나가지 않는다"
    ext = d["external"]
    assert ext["kind"] == "kooslurm_return" and ext["cluster_state"] == "COMPLETED"
    assert ext["ontology"]["state"] == "failed"
    why = ext["ontology"]["why"]
    assert str(Path.home()) not in why and "<home>" in why, "경로는 진단 번들처럼 접힌다"
    assert "a@b.com" not in why and "<email>" in why
    assert "upload_id" not in ext and "result_dir" not in ext, "요약에 없는 칸은 싣지 않는다"


def test_a_loaded_package_has_no_why_and_a_missing_one_is_null():
    d = JobRead.model_validate(_job(external_kind="kooslurm_return",
                                    external_ref={"cluster_state": "RUNNING", "ontology": {"state": "loaded"}})).model_dump()
    assert d["external"]["ontology"] == {"state": "loaded"}
    d = JobRead.model_validate(_job(external_kind="stcx_mcp", external_ref={"registry_id": 12})).model_dump()
    assert d["external"] == {"kind": "stcx_mcp", "cluster_state": None, "ontology": None}


def test_a_local_job_has_no_external_summary():
    assert JobRead.model_validate(_job()).model_dump()["external"] is None


# ── (b)(c) DB ──────────────────────────────────────────────────────────────

async def _owner(db):
    u = User(email=f"dl_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="dl", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    return u, s


async def _report(db, u, s, **over):
    r = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=u.id, kind="sphere", **over)
    db.add(r)
    await db.commit()
    return r


async def _cleanup(db, u, s):
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


@async_db
async def test_find_reports_filters_by_the_exact_external_job_key(db):
    u, s = await _owner(db)
    try:
        tag = ulid.new().str[-8:]
        a = await _report(db, u, s, external_job_key=f"stcx:{tag}1")
        await _report(db, u, s, external_job_key=f"stcx:{tag}2")
        await _report(db, u, s)
        got = await svc.find_reports(db, u.id, external_job_key=f"stcx:{tag}1")
        assert [r.id for r in got] == [a.id]
        assert await svc.find_reports(db, u.id, external_job_key=f"stcx:{tag}") == [], "앞부분만 같으면 안 걸린다"
        assert len(await svc.find_reports(db, u.id, session_id=s.id)) == 3, "거르기를 안 주면 예전과 같다"
    finally:
        await _cleanup(db, u, s)


@async_db
async def test_system_status_counts_postprocess_versions_from_recent_reports(db):
    u, s = await _owner(db)
    try:
        name = f"test-postprocessor-{ulid.new().str[-8:]}"     # 공용 dev DB — 이 이름의 행만 본다
        for v in ("v50", "v51", "v51"):
            await _report(db, u, s, ontology={"producer": {"name": name, "version": v}})
        await _report(db, u, s, ontology={"producer": {"name": name}})        # 판이 없는 꾸러미 — 세지 않는다
        await _report(db, u, s)                                                # 꾸러미가 없는 리포트 — 세지 않는다
        mine = [r for r in await _postprocess_versions(db) if r["name"] == name]
        assert {r["version"]: r["n"] for r in mine} == {"v50": 1, "v51": 2}
        assert mine[0]["version"] == "v51", "마지막 시각이 늦은 판이 앞에 온다"
        assert all(r["last_at"] for r in mine)
    finally:
        await _cleanup(db, u, s)
