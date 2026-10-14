"""외부 잡 반입·제출·폴링 — 실패와 모름이 **성공으로 새지 않는지**를 고정한다.

이 경로의 위험은 전부 한 모양이다. 안 된 것이 됐다고 남으면 사용자는 네 시간을 기다린
뒤에야 안다. 그래서 여기서 고정하는 것은 "잘 되는 길" 이 아니라 **안 된 것이 안 됐다고
남는지**다.

2026-10-14 에 흐름이 바뀌었다 — SmartTwinMCP(:5013)로 옮기면서 **덱을 나른다.** 그래서
새로 지키는 것 넷.
  ① 반입이 제출보다 **먼저** 일어나고, 올린 경로가 제출 인자에 실린다
  ② `work_dir` 가 **잡마다 고유**하다 — 받는 쪽은 그 자리에 덱이 이미 있으면 새 덱을
     조용히 무시한다(`script.sh:46-52`)
  ③ 시간 초과에 **다시 제출하지 않는다** — ②가 있으므로 재제출은 묵은 덱으로 돈다
  ④ 끝났는지는 `job_status` **와** `get_job_details` 를 합쳐서 판정한다
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
UPLOADED = "/shared/uploads/jobs/J/data/model.k"

_BODY = {"ok": True, "registry_id": 12, "job_id": "98765",
         "work_dir": "/data/df/J", "output_dir": "/data/df/J/output",
         "sphere_report_path": "/data/df/J/output/sphere_report.html"}


def _env(body, *, ok=True, exit_code=0, stderr=""):
    return {"tool": "fullangle_drop_simulation@1.1.0", "ok": ok, "exit_code": exit_code,
            "stdout": "", "stderr": stderr, "result": body,
            "transport": "local", "command": ""}


def _status_env(squeue):
    return _env({"ok": True, "job_id": 12, "tool": "fullangle_drop_simulation",
                 "work_dir": "/data/df/J", "output_dir": "/data/df/J/output",
                 "squeue": squeue})


def _details_env(ids):
    return _env({"ok": True, "job": {"id": 12, "tool_name": "fullangle_drop_simulation",
                                     "work_dir": "/data/df/J", "slurm_job_ids": list(ids)}})


def _q(**by_id):
    return {k: {"state": v, "name": "drop", "reason": None} for k, v in by_id.items()}


class _FakeUploader:
    """StcxUploader 대역 — 올렸는지, 무엇을 올렸는지 들고 있다."""

    def __init__(self, reply=None):
        self.reply = reply if reply is not None else {
            "ok": True, "file_path": UPLOADED, "bytes": 14, "chunks": 1, "upload_id": "up-1"}
        self.calls: list[dict] = []

    async def upload(self, src, *, job_id):
        self.calls.append({"src": str(src), "job_id": job_id})
        return self.reply

    async def close(self):
        pass


class _Fake:
    """StcxClient 대역 — 무엇을 어떤 인자로 불렀는지 들고 있다."""

    def __init__(self, *, submit=None, status=None, details=None, found=None):
        self.submit_reply = submit if submit is not None else {"ok": True, "result": _env(_BODY)}
        self.status_reply = (status if status is not None
                             else {"ok": True, "result": _status_env(_q(**{"101": "RUNNING"}))})
        self.details_reply = (details if details is not None
                              else {"ok": True, "result": _details_env(["101"])})
        self.found_reply = found          # work_dir 로 찾을 때의 답(시간초과 복구 경로)
        self.submits: list[dict] = []
        self.status_calls: list[tuple] = []
        self.detail_calls: list[tuple] = []
        self.uploader: _FakeUploader | None = None

    async def submit_fullangle_drop(self, args, *, dry_run=False):
        self.submits.append({"args": dict(args), "dry_run": dry_run})
        return self.submit_reply

    async def job_status(self, registry_id=None, *, work_dir=""):
        self.status_calls.append((registry_id, work_dir))
        if registry_id in (None, "") and work_dir:
            return self.found_reply if self.found_reply is not None else {"ok": False,
                                                                         "error": "not_found"}
        return self.status_reply

    async def job_details(self, registry_id=None, *, work_dir=""):
        self.detail_calls.append((registry_id, work_dir))
        return self.details_reply

    async def close(self):
        pass


@pytest.fixture()
def patched(monkeypatch):
    """_stcx()·StcxUploader·설정 넷을 대역으로 바꾼다. 망도 게이트웨이도 필요 없다."""
    from app.config import settings
    from app.worker import runner_loop

    monkeypatch.setattr(settings, "gateway_pat", "pat-test")
    monkeypatch.setattr(settings, "stcx_backend_url", "http://stcx.test")
    monkeypatch.setattr(settings, "stcx_work_root", "/data/df")
    monkeypatch.setattr(settings, "stcx_lstc_ip", "192.168.122.1")

    def _install(fake, uploader=None):
        up = uploader if uploader is not None else _FakeUploader()
        fake.uploader = up
        monkeypatch.setattr(runner_loop, "_stcx", lambda: fake)
        monkeypatch.setattr(runner_loop, "StcxUploader", lambda _url: up)
        return fake

    return _install


async def _mk(db, deck="*KEYWORD\n*END\n"):
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
    (wd / "model.k").write_text(deck, encoding="utf-8")
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
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "num_directions": 162})
        assert job.status == "running", "제출 직후 끝난 것으로 접으면 안 된다"
        assert job.external_kind == "stcx_mcp"
        assert job.external_ref["registry_id"] == 12
        assert job.external_ref["slurm_job_id"] == "98765"
        assert job.external_ref["sphere_report_path"].endswith("sphere_report.html")
        assert job.external_poll_at is not None
        assert fake.submits[-1]["dry_run"] is False
    finally:
        await _cleanup(u.id)


async def test_the_deck_is_uploaded_before_submitting_and_its_path_is_what_we_send(db, patched):
    """★stcx 는 이 서버의 경로를 못 연다 — 올린 **그쪽 경로**를 보내야 한다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert fake.uploader.calls, "반입이 아예 일어나지 않았다"
        assert fake.uploader.calls[-1]["src"] == str(wd / "model.k")
        assert fake.uploader.calls[-1]["job_id"] == job.id, "잡마다 경로를 갈라야 한다"
        assert fake.submits[-1]["args"]["model_file_path"] == UPLOADED
        assert job.external_ref["uploaded_path"] == UPLOADED
    finally:
        await _cleanup(u.id)


async def test_the_work_dir_is_unique_per_job(db, patched):
    """★받는 쪽은 `work_dir/<model_file>` 이 이미 있으면 새 덱을 조용히 무시한다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert fake.submits[-1]["args"]["work_dir"] == f"/data/df/{job.id}"
    finally:
        await _cleanup(u.id)


async def test_the_form_values_are_mapped_to_the_receiving_names(db, patched):
    """이름이 다르다 — 우리 이름으로 보내면 `additionalProperties: False` 가 통째로 거절한다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        await _submit(db, u.id, sid, wd, {
            "model": "model.k", "num_directions": 162, "height": 900, "t_final": 0.004,
            "drop_surface": "RigidWall", "ncpu": 8, "memory": "16G", "time_limit": "06:00:00",
            "postprocess_enabled": True, "auto_deep": False, "auto_sphere": True,
            "yield_stress_mpa": 280, "scenario_name": "낙하-A"})
        a = fake.submits[-1]["args"]
        assert a["num_angles"] == 162
        assert a["drop_height_mm"] == 900
        assert a["simulation_time_s"] == 0.004
        assert a["drop_surface_type"] == "RigidWall"
        assert a["enable_postprocess"] is True and a["auto_deep"] is False
        assert a["yield_stress_mpa"] == 280
        assert a["project_name"] == "낙하-A"
        assert a["lstc_license_ip"] == "192.168.122.1"
        # 우리 이름이 섞여 나가면 안 된다
        for ours in ("num_directions", "height", "t_final", "drop_surface",
                     "postprocess_enabled", "scenario_name"):
            assert ours not in a, f"{ours} 는 받는 쪽 이름이 아니다"
    finally:
        await _cleanup(u.id)


async def test_no_scenario_overrides_are_ever_sent(db, patched):
    """★`extra_scenario_overrides` 는 **리스트를 통째로 바꾼다** — 기본 시나리오(피보나치
    각도·후처리)가 지워진다. 이번 판에서는 한 번도 보내지 않는다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        await _submit(db, u.id, sid, wd, {"model": "model.k", "num_directions": 50})
        assert "extra_scenario_overrides" not in fake.submits[-1]["args"]
        assert "scenario_overrides" not in fake.submits[-1]["args"]
    finally:
        await _cleanup(u.id)


async def test_a_path_escape_in_the_model_name_is_refused(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "../../etc/passwd"})
        assert job.status == "failed"
        assert not fake.submits and not fake.uploader.calls
    finally:
        await _cleanup(u.id)


async def test_a_missing_model_is_refused_before_calling_out(db, patched):
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "nope.k"})
        assert job.status == "failed"
        assert not fake.submits and not fake.uploader.calls
    finally:
        await _cleanup(u.id)


@pytest.mark.parametrize("key", ["gateway_pat", "stcx_backend_url", "stcx_work_root",
                                 "stcx_lstc_ip"])
async def test_a_missing_setting_turns_the_job_off_loudly(db, patched, monkeypatch, key):
    """넷 중 **하나라도** 비면 꺼진 것이다 — 조용히 성공하면 제출된 줄 알고 기다린다."""
    from app.config import settings
    fake = patched(_Fake())
    monkeypatch.setattr(settings, key, "")
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed"
        assert key.upper().replace("STCX_", "STCX_") in (job.error_summary or "").upper() \
            or key.upper() in (job.error_summary or "").upper().replace("KOORM_", "")
        assert not fake.submits and not fake.uploader.calls
    finally:
        await _cleanup(u.id)


async def test_an_unsupported_option_is_refused_by_the_catalog(db, patched):
    """각도 프리셋은 이번 판에 칸이 없다 — 보내면 **거절**된다(조용히 안 버려진다)."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "angle_preset": "fib-100"})
        assert job.status == "failed"
        assert "angle_preset" in (job.error_summary or "")
        assert not fake.submits and not fake.uploader.calls
    finally:
        await _cleanup(u.id)


async def test_an_unsupported_option_is_refused_by_the_drift_guard(db, patched, monkeypatch):
    """카탈로그가 먼저 막는다. 그러나 **칸이 다시 생기고 매핑을 잊으면** 이 관문이 잡는다 —
    그때 조용히 버려지면 고른 값이 해석에 아무 영향을 안 주는데 잡은 성공한다."""
    from app.runner import catalog as cat
    fake = patched(_Fake())
    monkeypatch.setattr(cat, "validate_args", lambda op, args: [])
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k", "include_faces": True})
        assert job.status == "failed"
        assert "include_faces" in (job.error_summary or "")
        assert not fake.submits and not fake.uploader.calls
    finally:
        await _cleanup(u.id)


async def test_an_include_deck_is_refused_before_uploading(db, patched):
    """받는 쪽은 모델 파일 **하나**만 받는다 — 인클루드를 두고 올리면 반쪽 모델이 돈다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db, deck="*KEYWORD\n*INCLUDE\nparts/frame.k\n*END\n")
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed"
        assert "INCLUDE" in (job.error_summary or "")
        assert not fake.uploader.calls, "한 바이트도 올리지 않아야 한다"
    finally:
        await _cleanup(u.id)


async def test_a_commented_out_include_is_not_mistaken_for_one(db, patched):
    """`$` 로 주석 처리된 줄은 인클루드가 아니다 — 멀쩡한 덱을 막으면 그것도 결함이다."""
    fake = patched(_Fake())
    u, sid, wd = await _mk(db, deck="*KEYWORD\n$*INCLUDE\n$ parts/frame.k\n*END\n")
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "running" and fake.submits
    finally:
        await _cleanup(u.id)


async def test_an_upload_failure_fails_the_job_without_submitting(db, patched):
    fake = patched(_Fake(), uploader=_FakeUploader({"ok": False, "error": "http_413",
                                                    "detail": "too big"}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed" and "반입" in (job.error_summary or "")
        assert not fake.submits
        assert job.external_kind is None, "제출 안 된 잡에 핸들을 달면 영영 폴링한다"
    finally:
        await _cleanup(u.id)


async def test_a_tool_refusal_fails_the_job(db, patched):
    patched(_Fake(submit={"ok": True, "result": _env({"ok": False, "reason": "backend 제출 실패"},
                                                     ok=False, exit_code=1)}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed" and job.external_kind is None
    finally:
        await _cleanup(u.id)


async def test_an_arg_validation_failure_fails_the_job(db, patched):
    """검증 실패는 봉투가 **아니다** — `{"ok": false, "error": …}` 로만 온다."""
    patched(_Fake(submit={"ok": True, "result": {
        "ok": False, "error": "lstc_license_ip: does not match", "tool": "x@1.1.0"}}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert job.status == "failed" and job.external_kind is None
        assert "does not match" in (job.error_summary or "")
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


# ── 시간 초과 — 재제출 금지 ─────────────────────────────────────────────────
async def test_a_timeout_does_not_resubmit_and_recovers_the_registry_id(db, patched):
    """★끊긴 것은 응답뿐이고 제출은 됐을 수 있다. 그리고 두 번째 제출은 첫 번째가 둔
    **묵은 덱**으로 돈다(`script.sh:46-52`). 그래서 재제출 대신 찾는다."""
    fake = patched(_Fake(
        submit={"ok": False, "error": "transport_error", "detail": "ReadTimeout"},
        found={"ok": True, "result": _status_env({})}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert len(fake.submits) == 1, f"재제출이 일어났다({len(fake.submits)}번)"
        assert job.status == "running"
        assert job.external_ref["registry_id"] == 12
        assert fake.status_calls[-1][1] == f"/data/df/{job.id}", "work_dir 로 찾아야 한다"
    finally:
        await _cleanup(u.id)


async def test_a_timeout_with_nothing_found_fails_the_job(db, patched):
    fake = patched(_Fake(submit={"ok": False, "error": "transport_error", "detail": "ReadTimeout"},
                         found={"ok": False, "error": "not_found"}))
    u, sid, wd = await _mk(db)
    try:
        job = await _submit(db, u.id, sid, wd, {"model": "model.k"})
        assert len(fake.submits) == 1
        assert job.status == "failed" and job.external_kind is None
    finally:
        await _cleanup(u.id)


# ── 폴링 ────────────────────────────────────────────────────────────────────
async def _poll_with(db, uid, sid, wd, fake, patched):
    from app.database import SessionLocal
    from app.worker.runner_loop import _poll_external_once
    patched(fake)
    job = await _submit(db, uid, sid, wd, {"model": "model.k"})
    async with SessionLocal() as s:          # 기한을 과거로 당겨 이번 스캔에 걸리게 한다
        j = await s.get(Job, job.id)
        j.external_poll_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()
    await _poll_external_once()
    async with SessionLocal() as s:
        return await s.get(Job, job.id)


@pytest.mark.parametrize("squeue,ids,expect", [
    ({}, ["101"], "succeeded"),                        # 큐에서 다 사라졌다
    (_q(**{"101": "RUNNING"}), ["101"], "running"),
    (_q(**{"101": "FAILED"}), ["101"], "failed"),
    (_q(**{"101": "TIMEOUT"}), ["101"], "failed"),
    ({}, [], "running"),                               # ★제출 직후 — 끝난 것이 아니다
])
async def test_poll_maps_cluster_state_to_job_status(db, patched, squeue, ids, expect):
    u, sid, wd = await _mk(db)
    try:
        fake = _Fake(status={"ok": True, "result": _status_env(squeue)},
                     details={"ok": True, "result": _details_env(ids)})
        job = await _poll_with(db, u.id, sid, wd, fake, patched)
        assert job.status == expect
        if expect == "running":
            assert job.external_poll_at is not None, "계속 볼 기한이 있어야 한다"
        else:
            assert job.external_poll_at is None, "끝난 잡을 계속 두드리지 않는다"
    finally:
        await _cleanup(u.id)


async def test_poll_asks_both_tools_with_the_registry_id(db, patched):
    """★종료 근거(`slurm_job_ids`)가 상태 응답에 없어서 둘을 합친다."""
    u, sid, wd = await _mk(db)
    try:
        fake = _Fake()
        await _poll_with(db, u.id, sid, wd, fake, patched)
        assert fake.status_calls[-1][0] == 12
        assert fake.detail_calls[-1][0] == 12, "get_job_details 를 안 불렀다"
    finally:
        await _cleanup(u.id)


async def test_an_unreadable_status_never_becomes_done(db, patched):
    """**이 시험이 이 파일의 이유다.** 모름이 완료로 새면 결과 없이 succeeded 가 뜬다."""
    u, sid, wd = await _mk(db)
    try:
        cases = [
            # 상태는 멀쩡한데 모르는 slurm 상태
            _Fake(status={"ok": True, "result": _status_env(_q(**{"101": "WEIRD"}))}),
            # 상태 도구가 거절
            _Fake(status={"ok": True, "result": {"ok": False, "error": "no such job"}}),
            # 전송 실패
            _Fake(status={"ok": False, "error": "transport_error", "detail": "down"}),
            # ★id 목록을 못 읽었다 — 빈 목록으로 읽어 성공으로 접지 않는다
            _Fake(details={"ok": False, "error": "transport_error", "detail": "down"},
                  status={"ok": True, "result": _status_env({})}),
        ]
        for fake in cases:
            job = await _poll_with(db, u.id, sid, wd, fake, patched)
            assert job.status == "running", f"상태가 {job.status} 가 됐다"
            assert job.external_ref.get("last_state") == "unknown"
            assert job.external_ref.get("last_unknown")
    finally:
        await _cleanup(u.id)


async def test_poll_backs_off(db, patched):
    """시간 단위 잡을 30초마다 두드리지 않는다."""
    from app.config import settings
    u, sid, wd = await _mk(db)
    try:
        job = await _poll_with(db, u.id, sid, wd, _Fake(), patched)
        assert job.external_ref["poll_interval"] > settings.stcx_poll_min_sec
        assert job.external_ref["poll_interval"] <= settings.stcx_poll_max_sec
    finally:
        await _cleanup(u.id)


async def test_the_raw_reply_is_recorded_every_time(db, patched):
    """요청서 §4 — 종료 판정을 고치려면 **실제 응답**이 필요하다."""
    u, sid, wd = await _mk(db)
    try:
        job = await _poll_with(db, u.id, sid, wd, _Fake(), patched)
        assert "101" in job.external_ref["last_raw"]
    finally:
        await _cleanup(u.id)
