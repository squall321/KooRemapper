# 자동 파이프라인 전각도 낙하 KR-AP2 — 확인(읽기만) · 제출(idem) · 사슬 나아가기 · 상태 다섯 낱말 · 결과 봉투(단위 · unknown) · 취소
"""포털 계약 v1.1 §2 · §4(1 · 2 · 4 · 5) · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md · 사용자 결정 11-27.

stcx · 후처리 예약은 돌리지 않는다 — 잡 행의 상태 · 외부 표지를 시험이 바꿔 워커가 한 일을 흉내 낸다(사슬의 이음만 잰다).
공유 시험 DB 라 이 시험이 만든 행만 치운다. 잡은 status 를 queued 로 넣지 않는다 — 떠 있는 dev 워커가 집을 수 있다(시험 환경
함정) — 그래서 만든 즉시 시험이 running 으로 바꾼다.
"""
from __future__ import annotations

import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import delete, func, select, update

from app.config import settings
from app.database import SessionLocal
from app.models import AutoRun, ImpactReport, Job, Session, SessionFile, User
from app.modules.auto import drop
from app.modules.auto.services import AutoError
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")
DECK = b"*KEYWORD\n*PART\npart\n1,1,1\n*END\n"


async def _user(db) -> User:
    u = User(email=f"ad_{uuid.uuid4().hex}@kooremapper.test", password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _source(db, u, *, files=(("main.k", DECK),), task="과제-A", rev="dv1") -> Session:
    sid = uuid.uuid4().hex[:26]
    s = Session(id=sid, user_id=u.id, name="src", storage_path=storage.session_rel_dir(u.id, sid), task_key=task, dev_rev=rev)
    db.add(s)
    await db.flush()
    for name, body in files:
        rel = f"{s.storage_path}/{name}"
        storage.abs_path(rel).parent.mkdir(parents=True, exist_ok=True)
        storage.abs_path(rel).write_bytes(body)
        db.add(SessionFile(session_id=sid, filename=name, rel_path=rel, kind="input", size_bytes=len(body), sha256=None))
    await db.commit()
    return s


def _subject(s):
    return {"project": s.task_key, "revision": s.dev_rev, "refs": {"dynaforge": s.id}}


@pytest.fixture()
def ready(monkeypatch):
    """제출할 수 있는 박스 — stcx 설정 · 공유 폴더 스위치 · 제출 계정(만든 뒤 email 을 넣는다)."""
    for k, v in (("gateway_pat", "kr_x"), ("stcx_backend_url", "http://stcx.test"), ("stcx_work_root", "/w"),
                 ("stcx_lstc_ip", "10.0.0.1"), ("auto_drop_infra_ready", True)):
        monkeypatch.setattr(settings, k, v)

    def set_submitter(u):
        monkeypatch.setattr(settings, "auto_submit_email", u.email)
    return set_submitter


async def _cleanup(users):
    ids = [u if isinstance(u, int) else u.id for u in users]
    async with SessionLocal() as db:
        runs = (await db.execute(select(AutoRun).where(AutoRun.created_by.in_(ids)))).scalars().all()
        rids = [r.report_id for r in runs if r.report_id]
        await db.execute(delete(AutoRun).where(AutoRun.created_by.in_(ids)))
        if rids:
            await db.execute(delete(ImpactReport).where(ImpactReport.id.in_(rids)))
        sids = (await db.execute(select(Session.id).where(Session.user_id.in_(ids)))).scalars().all()
        await db.execute(delete(Job).where(Job.session_id.in_(sids)))
        await db.execute(delete(ImpactReport).where(ImpactReport.session_id.in_(sids)))
        await db.execute(delete(SessionFile).where(SessionFile.session_id.in_(sids)))
        await db.execute(delete(Session).where(Session.id.in_(sids)))
        await db.execute(delete(User).where(User.id.in_(ids)))
        await db.commit()
    for uid in ids:
        shutil.rmtree(storage.abs_path(storage.session_rel_dir(uid, "x")).parent, ignore_errors=True)


async def _counts(db):
    return tuple([(await db.execute(select(func.count()).select_from(t))).scalar_one() for t in (AutoRun, Job, Session)])


# ── profile · 확인 ─────────────────────────────────────────────────────────

async def test_profiles_say_two_profiles_and_whether_a_submit_identity_exists(db, monkeypatch):
    u = await _user(db)
    try:
        monkeypatch.setattr(settings, "auto_submit_email", "")
        got = await drop.profiles(db)
        assert [p["id"] for p in got["profiles"]] == ["fullangle_162", "fullangle_26"] and got["service_identity"] is False
        assert got["profiles"][0]["cost"]["cores"] == 324 and got["profiles"][0]["criteria_source"] is None
        monkeypatch.setattr(settings, "auto_submit_email", u.email)
        assert (await drop.profiles(db))["service_identity"] is True
    finally:
        await _cleanup([u])


async def test_check_names_every_missing_thing_and_changes_nothing(db, monkeypatch):
    u = await _user(db)
    uid = u.id
    try:
        monkeypatch.setattr(settings, "auto_submit_email", "")
        monkeypatch.setattr(settings, "auto_drop_infra_ready", False)
        s = await _source(db, u, task=None, rev=None, files=(("a.k", DECK), ("b.k", DECK)))
        sid = s.id
        before = await _counts(db)
        got = await drop.check(db, u, _subject(s), "fullangle_162")
        await db.rollback()                         # 확인이 남긴 것이 있으면 여기서 버려진다 — 아래는 새 세션으로 본다
        kinds = [m["kind"] for m in got["missing"]]
        assert got["ready"] is False
        assert {"project_key", "revision", "input", "infra", "permission"} <= set(kinds), kinds
        assert any("SH-01" in m["why"] for m in got["missing"] if m["kind"] == "infra"), "공유 폴더 전을 infra 로 말하지 않았다"
        assert await _counts(db) == before, "확인이 무언가를 만들었다(계약 §4-2)"
        async with SessionLocal() as f:
            assert not (await f.execute(select(SessionFile.sha256).where(SessionFile.session_id == sid))).scalars().first(), \
                "확인이 sha 를 남겼다 — 아무것도 바꾸지 않는다"
    finally:
        await _cleanup([uid])


async def test_a_deck_with_an_include_is_not_ready(db, ready):
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u, files=(("main.k", b"*KEYWORD\n*INCLUDE\nparts.k\n*END\n"),))
        got = await drop.check(db, u, _subject(s), "fullangle_26")
        assert [m.get("name") for m in got["missing"]] == ["deck_include"], got["missing"]
    finally:
        await _cleanup([u])


async def test_check_is_ready_with_the_deck_sha_when_everything_is_set(db, ready):
    import hashlib
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        got = await drop.check(db, u, _subject(s), "fullangle_162")
        assert got["ready"] is True and got["missing"] == []
        assert got["inputs"] == [{"kind": "deck", "ref": got["inputs"][0]["ref"], "name": "main.k",
                                  "sha256": hashlib.sha256(DECK).hexdigest(), "at": got["inputs"][0]["at"]}]
        async with SessionLocal() as f:                # 답에는 재서 싣되 남기지 않는다(계약 §4-2)
            assert (await f.execute(select(SessionFile.sha256).where(SessionFile.session_id == s.id))).scalar_one() is None, \
                "확인이 sha 를 DB 에 남겼다"
        with pytest.raises(AutoError) as e:
            await drop.check(db, u, _subject(s), "nope")
        assert e.value.error == "bad_profile"
    finally:
        await _cleanup([u])


# ── 제출 · 사슬 ───────────────────────────────────────────────────────────

async def _submit(db, u, s, key="ab" * 32):
    got = await drop.submit(db, u, _subject(s), "fullangle_162", key)
    run = await db.get(AutoRun, got["run_ref"])
    await db.execute(update(Job).where(Job.id == run.stcx_job_id).values(status="running"))   # 떠 있는 워커가 집지 않게
    await db.commit()
    await db.refresh(run)
    return got, run


async def test_the_same_idem_key_submits_once(db, ready):
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        key = uuid.uuid4().hex * 2
        first, run = await _submit(db, u, s, key)
        again = await drop.submit(db, u, _subject(s), "fullangle_162", key)
        assert first["created"] is True and again == {"run_ref": first["run_ref"], "state": "running", "created": False}
        assert (await db.execute(select(func.count()).select_from(AutoRun).where(AutoRun.idem_key == key))).scalar_one() == 1
        job = await db.get(Job, run.stcx_job_id)
        assert job.operation == "stcx_fullangle_drop" and job.args["num_directions"] == 162 and job.user_id == u.id
        assert job.session_id != s.id, "원천 세션에서 돌렸다 — 실행 세션(제출 계정 소유)에 복사해야 한다"
        copied = (await db.execute(select(SessionFile).where(SessionFile.session_id == job.session_id))).scalar_one()
        assert copied.filename == "main.k" and storage.abs_path(copied.rel_path).read_bytes() == DECK
    finally:
        await _cleanup([u])


async def test_submit_refuses_when_not_ready_and_creates_nothing(db, monkeypatch):
    u = await _user(db)
    uid = u.id
    try:
        monkeypatch.setattr(settings, "auto_drop_infra_ready", False)
        s = await _source(db, u)
        subject = _subject(s)
        before = await _counts(db)
        with pytest.raises(AutoError) as e:
            await drop.submit(db, u, subject, "fullangle_162", "cd" * 32)
        assert e.value.error == "not_ready" and any(m["kind"] == "infra" for m in e.value.extra["missing"])
        await db.rollback()
        assert await _counts(db) == before
        with pytest.raises(AutoError) as e:
            await drop.submit(db, await db.get(User, uid), subject, "fullangle_162", "NOT-HEX")
        assert e.value.error == "bad_idem_key"
    finally:
        await _cleanup([uid])


async def test_the_chain_runs_to_a_result_with_units_and_an_unknown_verdict(db, ready):
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        got, run = await _submit(db, u, s, uuid.uuid4().hex * 2)
        assert (await drop.status(db, u, got["run_ref"]))["state"] == "running"
        with pytest.raises(AutoError) as e:
            await drop.result(db, u, got["run_ref"])
        assert e.value.error == "not_done"
        await db.execute(update(Job).where(Job.id == run.stcx_job_id).values(external_ref={"slurm_job_id": "4242"}))
        await db.commit()
        st = await drop.status(db, u, got["run_ref"])
        await db.refresh(run)
        pp = await db.get(Job, run.postprocess_job_id)
        assert st["state"] == "running" and "4242" in st["detail"] and run.stage == "postprocess"
        assert (pp.operation, pp.args["job_key"], pp.args["project"], pp.args["dev_rev"]) == \
            ("postprocess", "stcx:4242", "과제-A", "dv1"), pp.args
        rid = uuid.uuid4().hex[:26].upper()
        db.add(ImpactReport(id=rid, session_id=pp.session_id, user_id=u.id, kind="sphere", n_cases=162, max_severity="WARNING",
                            summary={"worst_stress": {"value": 812.5}, "worst_g": {"value": 4321.0}, "successful_runs": 160,
                                     "failed_runs": 2, "unit_system": {"id": "ton-mm-s", "detected": True, "g_factor": 9806.65}},
                            reservation={"manifest": {"result_dir": "/data/single/x/drop_4242"}}))
        await db.execute(update(Job).where(Job.id == pp.id).values(status="succeeded", external_ref={"report_ids": [rid]}))
        await db.commit()
        assert (await drop.status(db, u, got["run_ref"]))["state"] == "done"
        env = await drop.result(db, u, got["run_ref"])
        assert env["verdict"] == "unknown" and env["subject"] == _subject(s) and env["report_id"] == rid
        m = {x["name"]: x for x in env["metrics"]}
        assert (m["peak_stress"]["value"], m["peak_stress"]["unit"]) == (812.5, "MPa")
        assert (m["peak_acceleration"]["unit"], m["failed_runs"]["value"]) == ("G", 2.0)
        assert all(x["unit"] and x["verdict"] == "unknown" and x["limit"] is None for x in env["metrics"]), "계약 §4-4"
        assert env["artifacts"] == [{"kind": "result_dir", "location": "/data/single/x/drop_4242"}]
        assert any("기준" in n for n in env["notes"]) and "error" not in env
    finally:
        await _cleanup([u])


@pytest.mark.parametrize("us,want", [(None, set()), ({"id": "ton-mm-s", "detected": False, "note": "밀도 없음"}, set()),
                                     ({"id": "ton-mm-ms", "detected": True}, {"peak_acceleration"}),
                                     ({"id": "SI", "detected": True}, {"peak_stress", "peak_acceleration"})])
async def test_metrics_carry_a_unit_or_are_left_out_with_a_note(us, want):
    r = ImpactReport(id="R", session_id="S", user_id=1, kind="sphere", n_cases=1,
                     summary={"worst_stress": {"value": 5.0e8}, "worst_g": {"value": 10.0}, "unit_system": us})
    metrics, notes = drop._metrics(r)
    assert {x["name"] for x in metrics} - {"successful_runs", "failed_runs"} == want, (us, metrics)
    if us and us["id"] == "SI":
        assert next(x for x in metrics if x["name"] == "peak_stress") ["value"] == 500.0, "SI 응력을 MPa 로 바꾸지 않았다"
    if want != {"peak_stress", "peak_acceleration"}:
        assert any("싣지 않았다" in n for n in notes), notes


async def test_a_failed_or_cancelled_job_ends_the_run_with_its_reason(db, ready):
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        got, run = await _submit(db, u, s, uuid.uuid4().hex * 2)
        await db.execute(update(Job).where(Job.id == run.stcx_job_id).values(status="failed", error_summary="덱 반입 실패"))
        await db.commit()
        st = await drop.status(db, u, got["run_ref"])
        assert st["state"] == "failed" and "덱 반입 실패" in st["detail"]
        got2, run2 = await _submit(db, u, s, uuid.uuid4().hex * 2)
        await db.execute(update(Job).where(Job.id == run2.stcx_job_id).values(status="canceled"))
        await db.commit()
        assert (await drop.status(db, u, got2["run_ref"]))["state"] == "cancelled", "canceled → cancelled 로 바꾸지 않았다"
    finally:
        await _cleanup([u])


async def test_cancel_only_before_it_reaches_the_cluster_and_others_cannot_see_the_run(db, ready, monkeypatch):
    u, other = await _user(db), await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        got = await drop.submit(db, u, _subject(s), "fullangle_26", uuid.uuid4().hex * 2)
        assert (await drop.cancel(db, u, got["run_ref"]))["state"] == "cancelled"
        job = await db.get(Job, (await db.get(AutoRun, got["run_ref"])).stcx_job_id)
        assert job.status == "canceled"
        got2, run2 = await _submit(db, u, s, uuid.uuid4().hex * 2)
        with pytest.raises(AutoError) as e:
            await drop.cancel(db, u, got2["run_ref"])
        assert e.value.error == "not_cancellable"
        with pytest.raises(AutoError) as e:
            await drop.status(db, other, got2["run_ref"])
        assert e.value.error == "not_found", "남의 실행이 보였다"
        monkeypatch.setattr(type(settings), "auto_service_email_set", property(lambda self: frozenset({other.email.lower()})))
        assert (await drop.status(db, other, got2["run_ref"]))["state"] == "running", "서비스 계정이 실행을 못 봤다"
    finally:
        await _cleanup([u, other])


async def test_a_finished_stcx_job_without_a_slurm_number_fails_plainly(db, ready):
    """제출 응답을 잃고 work_dir 로 되찾은 잡은 Slurm 번호가 없을 수 있다 — 후처리 예약을 걸 키가 없으니 까닭과 함께 실패다."""
    u = await _user(db)
    try:
        ready(u)
        s = await _source(db, u)
        got, run = await _submit(db, u, s, uuid.uuid4().hex * 2)
        await db.execute(update(Job).where(Job.id == run.stcx_job_id).values(status="succeeded",
                                                                             external_ref={"registry_id": 9}))
        await db.commit()
        st = await drop.status(db, u, got["run_ref"])
        assert st["state"] == "failed" and "Slurm 잡 번호가 없다" in st["detail"], st
    finally:
        await _cleanup([u])


@pytest.mark.parametrize("info", [{"revision": None}, {}, None, "raise"])
async def test_app_version_is_never_empty_even_without_a_binary_revision(info, monkeypatch):
    """바이너리 판을 모르는 박스에서도 app_version 은 빈 글이 아니다(계약 §2 · §4-4 — 포털이 봉투를 버린다, 13c3ac3e)."""
    import app.shared.buildinfo as bi

    def fake(_path):
        if info == "raise":
            raise OSError("BUILD_INFO 를 못 읽음")
        return info
    monkeypatch.setattr(bi, "build_info", fake)
    assert drop.app_version() == "unknown"
    monkeypatch.setattr(bi, "build_info", lambda _p: {"revision": "6a90a4166a4e34613d71f6ab11bfc2831fd23973"})
    assert drop.app_version() == "6a90a416"

