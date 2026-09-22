"""외부 잡 제출·폴링 — 실패와 모름이 **성공으로 새지 않는지**를 고정한다.

이 경로의 위험은 전부 한 모양이다. 상대 도구가 JSON 이 아니라 글을 돌려주고, 실패도
정상 반환값으로 온다. 그래서 여기서 고정하는 것은 "잘 되는 길" 이 아니라 **안 된 것이
안 됐다고 남는지**다. 잘못 접히면 사용자는 네 시간을 기다린 뒤에야 안다.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import Job, PersonalAccessToken, Session, User
from app.shared import security, storage
from app.shared.storage import session_rel_dir

pytestmark = pytest.mark.asyncio(loop_scope="session")

OP = "stcx_fullangle_drop"
SUBMIT_OK = "✅ 제출 완료 — job_id=98765\n결과 폴더: /data/single/u/drop_98765/"
STATE = ("잡 98765 결과\n  이름: drop\n  상태: {s}  (ExitCode 0:0)\n"
         "  경과: 00:10:00  파티션: alpha")


class _Fake:
    """StcxClient 대역 — 무엇을 어떤 인자로 불렀는지 들고 있다."""

    def __init__(self, submit=None, results=None):
        self.submit_reply = submit if submit is not None else {"ok": True, "result": SUBMIT_OK}
        self.results_reply = results if results is not None else {"ok": True, "result": STATE.format(s="RUNNING")}
        self.submits: list[dict] = []
        self.result_calls: list[str] = []

    async def submit_fullangle_drop(self, **kw):
        self.submits.append(kw)
        return self.submit_reply

    async def job_results(self, job_id):
        self.result_calls.append(job_id)
        return self.results_reply

    async def close(self):
        pass


@pytest.fixture()
def patched(monkeypatch):
    """_stcx() 가 대역을 돌려주게 한다. 망도 게이트웨이도 필요 없다."""
    from app.worker import runner_loop

    holder = {}

    def _install(fake):
        holder["fake"] = fake
        monkeypatch.setattr(runner_loop, "_stcx", lambda: fake)
        return fake

    return _install


async def _mk(db):
    u = User(email=f"x_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    from app.database import SessionLocal
    async with SessionLocal() as s:
        s.add(Session(id=sid, user_id=u.id, name="s", storage_path=session_rel_dir(u.id, sid)))
        await s.commit()
    wd = storage.ensure_session_dir(u.id, sid)
    (wd / "model.k").write_text("*KEYWORD\n*END\n", encoding="utf-8")
    return u, sid, wd


async def _cleanup(uid):
    from app.database import SessionLocal
    async with SessionLocal() as s:
        await s.execute(delete(Job).where(Job.user_id == uid))
        await s.execute(delete(Session).where(Session.user_id == uid))
        await s.execute(delete(PersonalAccessToken).where(PersonalAccessToken.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


async def _submit(db, uid, sid, wd, args):
    from app.database import SessionLocal
    from app.worker.runner_loop import _submit_external
    jid = ulid.new().str
    async with SessionLocal() as s:
        s.add(Job(id=jid, session_id=sid, user_id=uid, operation=OP, args=args, status="running"))
        await s.commit()
    async with SessionLocal() as s:
        job = await s.get(Job, jid)
        await _submit_external(s, job, wd)
    async with SessionLocal() as s:
        return await s.get(Job, jid)


# ── 제출 ────────────────────────────────────────────────────────────────────
async def test_submit_keeps_the_job_running_and_records_the_handle(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "angle_preset": "fibonacci-100"})
        assert job.status == "running", "제출 직후 끝난 것으로 접으면 안 된다"
        assert job.external_kind == "stcx_mcp"
        assert job.external_ref["job_id"] == "98765"
        assert job.external_poll_at is not None
        # 세션의 절대경로가 그대로 넘어갔다 — 파일을 나르지 않는다
        assert fake.submits[-1]["model_path"] == str(wd / "model.k")
        assert fake.submits[-1]["dry_run"] is False
        assert fake.submits[-1]["angle_preset"] == "fibonacci-100"
    finally:
        await _cleanup(u.id)


async def test_a_path_escape_in_the_model_name_is_refused(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "../../etc/passwd"})
        assert job.status == "failed" and not fake.submits
    finally:
        await _cleanup(u.id)


async def test_a_missing_model_is_refused_before_calling_out(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "nope.k"})
        assert job.status == "failed" and not fake.submits
    finally:
        await _cleanup(u.id)


async def test_a_tool_error_string_fails_the_job(db, patched):
    """도구는 실패를 **정상 반환값**으로 준다 — 여기서 걸러야 한다."""
    patched(_Fake(submit={"ok": True, "result": "error: 제출 실패(status=500)"}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed"
        assert job.external_kind is None, "제출 안 된 잡에 핸들을 달면 영영 폴링한다"
    finally:
        await _cleanup(u.id)


async def test_a_dry_run_reply_fails_the_job(db, patched):
    patched(_Fake(submit={"ok": True, "result": "[DRY-RUN] 제출 계획"}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed" and job.external_kind is None
    finally:
        await _cleanup(u.id)


async def test_gateway_unavailable_fails_the_job(db, patched):
    patched(_Fake(submit={"ok": False, "error": "unavailable", "detail": "PAT 없음"}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed" and "unavailable" in (job.error_summary or "")
    finally:
        await _cleanup(u.id)


async def test_num_directions_becomes_a_fibonacci_override(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        await _submit(db, u.id, sid, wd, {"model": "model.k", "num_directions": 162, "height": 900})
        ov = fake.submits[-1]["scenario_overrides"]
        assert ov["simulation_params"]["height"] == 900
        assert ov["scenarios"][0]["angle_source"]["num_points"] == 162
        assert ov["scenarios"][0]["angle_source"]["source_type"] == "fibonacci_lattice"
    finally:
        await _cleanup(u.id)


# ── 폴링 ────────────────────────────────────────────────────────────────────
async def _poll_with(db, uid, sid, wd, fake, patched):
    from app.database import SessionLocal
    from app.worker.runner_loop import _poll_external_once
    patched(fake)
    job = await _submit(db, uid, sid, wd, {"model": "model.k"})
    # 기한을 과거로 당겨 이번 스캔에 걸리게 한다
    async with SessionLocal() as s:
        j = await s.get(Job, job.id)
        j.external_poll_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()
    await _poll_external_once()
    async with SessionLocal() as s:
        return await s.get(Job, job.id)


@pytest.mark.parametrize("slurm,expect", [("COMPLETED", "succeeded"), ("FAILED", "failed"),
                                          ("TIMEOUT", "failed"), ("RUNNING", "running")])
async def test_poll_maps_cluster_state_to_job_status(db, patched, slurm, expect):
    u, sid, wd = await _mk(db)
    try:
        fake = _Fake(results={"ok": True, "result": STATE.format(s=slurm)})
        job = await _poll_with(db, u.id, sid, wd, fake, patched)
        assert job.status == expect
        if expect == "running":
            assert job.external_poll_at is not None, "계속 볼 기한이 있어야 한다"
        else:
            assert job.external_poll_at is None, "끝난 잡을 계속 두드리지 않는다"
    finally:
        await _cleanup(u.id)


async def test_an_unreadable_status_never_becomes_done(db, patched):
    """**이 시험이 이 파일의 이유다.** 모름이 완료로 새면 결과 없이 succeeded 가 뜬다."""
    u, sid, wd = await _mk(db)
    try:
        for reply in ({"ok": True, "result": "error: 인증 실패"},
                      {"ok": True, "result": "상태: WEIRD"},
                      {"ok": False, "error": "transport_error", "detail": "down"}):
            job = await _poll_with(db, u.id, sid, wd, _Fake(results=reply), patched)
            assert job.status == "running", f"{reply} 로 상태가 {job.status} 가 됐다"
            assert job.external_ref.get("last_state") == "unknown"
            assert job.external_ref.get("last_unknown")
    finally:
        await _cleanup(u.id)


async def test_poll_backs_off(db, patched):
    """시간 단위 잡을 30초마다 두드리지 않는다."""
    from app.config import settings
    u, sid, wd = await _mk(db)
    try:
        job = await _poll_with(db, u.id, sid, wd,
                               _Fake(results={"ok": True, "result": STATE.format(s="RUNNING")}), patched)
        assert job.external_ref["poll_interval"] > settings.stcx_poll_min_sec
        assert job.external_ref["poll_interval"] <= settings.stcx_poll_max_sec
    finally:
        await _cleanup(u.id)


# ── 각도 파일도 나르지 않는다 ───────────────────────────────────────────────
async def test_a_case_file_is_passed_as_a_path(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        (wd / "angles.txt").write_text("0 0 0\n90 0 0\n", encoding="utf-8")
        await _submit(db, u.id, sid, wd, {"model": "model.k", "case_txt": "angles.txt"})
        kw = fake.submits[-1]
        assert kw["case_txt_path"] == str(wd / "angles.txt")
        assert kw["scenario_overrides"]["scenarios"][0]["angle_source"]["source_type"] == "case_txt_file"
    finally:
        await _cleanup(u.id)


async def test_a_missing_case_file_is_refused_before_calling_out(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "case_txt": "nope.txt"})
        assert job.status == "failed" and not fake.submits
    finally:
        await _cleanup(u.id)


async def test_a_path_escape_in_the_case_file_is_refused(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "case_txt": "../../etc/passwd"})
        assert job.status == "failed" and not fake.submits
    finally:
        await _cleanup(u.id)


async def test_the_submitted_scenario_is_recorded_on_the_job(db, patched):
    """무엇으로 돌렸는지 잡에 남아야 한다 — 나중에 '왜 이 결과인가' 를 물을 수 있게."""
    patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {
            "model": "model.k", "height": 900,
            "scenario_overrides": {"simulation_params": {"dt": 5e-7}}})
        ref = job.external_ref
        assert ref["scenario_overrides"]["simulation_params"] == {"height": 900, "dt": 5e-7}
        assert ref["case_txt_path"] is None
    finally:
        await _cleanup(u.id)
