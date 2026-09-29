# 진단 번들이 '재현 없이 고칠 수 있는' 것을 담고, 담아선 안 되는 것은 담지 않나
"""왜 이 시험이 있나 (2026-09-29).

번들은 **고객 덱을 다루는 시스템에서 밖으로 나가는 데이터**다. 그래서 두 가지를 같이 지켜야 한다 —
진단에 필요한 것이 다 있어야 하고, 비밀·호스트 절대 경로·타인의 것이 섞이지 않아야 한다.

여기서 특히 못 박는 것 셋.

  · **빌드 정체.** 잡마다 어느 바이너리로 돌았는지 남아야 한다. 배포 자리 바이너리가 이 캠페인에서
    다섯 번 덮였으므로(context-notes 27), 이것이 없는 로그는 증거가 아니다.
  · **덱 본문은 켜야 나온다.** 기본으로 나가면 형상·물성이 사용자 동의 없이 밖으로 간다.
  · **잡 행이 사라져도 크래시는 남는다.** 실측으로 잡 4건이 흔적 없이 사라졌고
    `error_summary='worker exception'` 인 잡은 0건이었다(복구가 한 번도 성공한 적이 없다).
"""
import json
import logging
import sys
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete
from sqlalchemy.orm.exc import StaleDataError

from app.models import Job, Session, SessionFile, User
from app.shared import diagnostics, logctx, security, storage

_aio = pytest.mark.asyncio(loop_scope="session")

_DECK = (
    "*KEYWORD\n"
    "*NODE\n"
    "         1             0.0             0.0             0.0\n"
    "         2            10.0             0.0             0.0\n"
    "*END\n"
)
_DB_ARGS = {"config": {"model": "model.k", "output": "model_db.k",
                       "preset": "all", "dt": 0.001, "dt_plot": 0.01}}


async def _mk_user_session(db, tag):
    u = User(email=f"{tag}_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name=tag,
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _drop(db, u, s):
    await db.execute(delete(Job).where(Job.session_id == s.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    d = storage.session_abs_dir(u.id, s.id)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
async def sess(db):
    u, s = await _mk_user_session(db, "diag")
    try:
        yield u, s
    finally:
        await _drop(db, u, s)


# ── 1. 빌드 정체가 잡에 남나 (실제 잡을 돌린다) ────────────────────────────────
@_aio
async def test_a_job_records_which_binary_ran_it(db, sess):
    """`/api/health` 는 '지금' 만 말한다. 사흘 전 로그를 받아도 그때의 빌드를 알아야 한다."""
    from app.config import settings
    from app.shared.buildinfo import build_info
    from app.worker.runner_loop import _execute
    from app.modules.sessions import services as svc

    u, s = sess
    await svc.add_uploaded_file(db, s, filename="model.k", raw=_DECK.encode("latin-1"))
    job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id,
              operation="database", args=_DB_ARGS, status="queued")
    db.add(job)
    await db.commit()
    await _execute(job.id)
    await db.refresh(job)

    assert job.status == "succeeded", f"{job.status} / {job.error_summary}"
    env = job.env_snapshot
    assert env, "잡에 환경 스냅샷이 없다 — 어느 빌드로 돌았는지 영영 알 수 없다"
    want = build_info(settings.kooremapper_bin)
    assert env["binary"]["sha256"] == want["binary_sha256"], (
        "스냅샷의 바이너리 해시가 실제와 다르다 — %s vs %s"
        % (env["binary"]["sha256"], want["binary_sha256"])
    )
    assert "gmsh" in env and "available" in env["gmsh"], f"gmsh 칸이 없다 — {env}"
    assert env["host"]["nodename"], "호스트 이름이 비었다"


# ── 2. 담아선 안 되는 것 ───────────────────────────────────────────────────────
async def _job_with_logs(db, u, s, *, err_text, stdout="", stderr=""):
    d = storage.session_abs_dir(u.id, s.id)
    out = d / ".job_diag.out"
    err = d / ".job_diag.err"
    out.write_text(stdout, encoding="utf-8")
    err.write_text(stderr, encoding="utf-8")
    job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id,
              operation="database", args=_DB_ARGS, status="failed",
              exit_code=1, error_summary=err_text,
              stdout_path=str(out), stderr_path=str(err))
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@_aio
async def test_the_bundle_carries_no_host_paths_no_email_no_token(db, sess):
    """번들은 밖으로 나간다 — 경로는 접고, 이메일·토큰은 지운다."""
    u, s = sess
    secret = "kr_abcdef0123456789"
    abs_dir = str(storage.session_abs_dir(u.id, s.id))
    job = await _job_with_logs(
        db, u, s,
        err_text=f"exit 1: 실패했다 {abs_dir}/model.k",
        stderr=f"Authorization: Bearer {secret}\n연락 who@example.com\n{abs_dir}/model.k 없음\n",
    )
    diag = diagnostics.build(job, inputs=[], outputs=[], deck_lines=False)
    blob = json.dumps(diag, ensure_ascii=False)

    assert abs_dir not in blob, "호스트 절대 경로가 번들에 그대로 있다"
    assert "<storage>" in blob, "경로를 접지 않았다 — 구조를 읽을 수 없으면 진단이 안 된다"
    assert secret not in blob, "API 토큰이 번들에 실렸다"
    assert "who@example.com" not in blob, "이메일이 번들에 실렸다"
    assert "<token>" in blob and "<email>" in blob, "지운 자리에 표시가 없다"


# ── 3. 덱 본문은 켜야 나온다 ───────────────────────────────────────────────────
@_aio
async def test_deck_body_is_absent_unless_asked(db, sess):
    """고객 CAE 모델이 IP 다. 기본으로 나가면 사용자 동의 없이 형상이 밖으로 간다."""
    from app.modules.sessions import services as svc

    u, s = sess
    row = await svc.add_uploaded_file(db, s, filename="model.k", raw=_DECK.encode("latin-1"))
    job = await _job_with_logs(db, u, s, err_text="exit 1: line 3 이 이상하다")
    job.input_file_ids = [row.id]
    await db.commit()
    await db.refresh(job)

    # `rel_path` 는 스토리지 루트 기준이다 — `abs_path` 가 정본 접근자다.
    inputs = [(row.filename, str(storage.abs_path(row.rel_path)))]

    off = diagnostics.build(job, inputs=inputs, outputs=[], deck_lines=False)
    assert off["deck_excerpts"] is None, "켜지 않았는데 덱 본문이 담겼다"
    assert "10.0" not in json.dumps(off, ensure_ascii=False), "덱 좌표가 새어 나갔다"

    on = diagnostics.build(job, inputs=inputs, outputs=[], deck_lines=True)
    ex = on["deck_excerpts"]
    assert ex and row.filename in ex, f"켰는데도 덱 줄이 없다 — {ex}"
    joined = "\n".join(ex[row.filename])
    assert "*NODE" in joined or "0.0" in joined, f"가리킨 줄 근처가 아니다 — {joined}"


# ── 4. 남의 잡은 못 본다 ───────────────────────────────────────────────────────
@pytest.fixture
async def api(db):
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    transport = ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@_aio
async def test_another_users_job_is_not_reachable(db, api, sess):
    """소유권은 기존 검사를 그대로 쓴다 — 새 권한 개념을 만들지 않았으니 여기서 확인한다."""
    from app.config import settings

    settings.ratelimit_enabled = False
    u_a, s_a = sess
    job = await _job_with_logs(db, u_a, s_a, err_text="exit 1: 남의 잡")

    email = "diagother_%s@kooremapper.test" % ulid.new().str
    u_b = User(email=email, password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u_b)
    await db.commit()
    await db.refresh(u_b)
    try:
        tok = (await api.post("/api/v1/auth/login",
                              json={"email": email, "password": "pw123456"})
               ).json()["data"]["access_token"]
        h = {"Authorization": "Bearer %s" % tok}
        for url in (f"/api/v1/jobs/{job.id}/diagnostics",
                    f"/api/v1/jobs/{job.id}/diagnostics.zip"):
            r = await api.get(url, headers=h)
            assert r.status_code == 404, f"{url} 이 남에게 {r.status_code} 를 냈다"
    finally:
        await db.execute(delete(User).where(User.id == u_b.id))
        await db.commit()


# ── 5. zip 구성 ────────────────────────────────────────────────────────────────
@_aio
async def test_the_zip_has_the_expected_members(db, sess):
    u, s = sess
    job = await _job_with_logs(db, u, s, err_text="exit 1: 무언가", stdout="나온 것\n", stderr="터진 것\n")
    diag = diagnostics.build(job, inputs=[], outputs=[], deck_lines=False)
    blob = diagnostics.zip_bytes(job, diag)
    with zipfile.ZipFile(BytesIO(blob)) as z:
        names = set(z.namelist())
        assert {"diagnostic.json", "summary.txt", "stdout.log", "stderr.log",
                "resolved_cmd.json", "server.log"} <= names, f"빠진 항목 — {names}"
        assert "터진 것" in z.read("stderr.log").decode("utf-8")
        assert job.id in z.read("summary.txt").decode("utf-8")


# ── 6. 로그 한 줄에 시각과 상관자가 있나 ───────────────────────────────────────
def test_log_lines_carry_time_and_correlator():
    """시각이 없으면 '14:30 에 실패했다' 를 로그와 맞출 수 없다 — 그것이 원래 상태였다."""
    buf = StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(logging.Formatter(logctx.FORMAT))
    h.addFilter(logctx.CorrelatorFilter())
    lg = logging.getLogger("koorm.test.fmt")
    lg.handlers = [h]
    lg.propagate = False
    lg.setLevel(logging.INFO)

    tok = logctx.set_correlator("JOBID123")
    try:
        lg.info("무언가 일어났다")
    finally:
        logctx.reset_correlator(tok)
    line = buf.getvalue().strip()

    assert "[JOBID123]" in line, f"상관자가 없다 — {line}"
    assert line[:4].isdigit(), f"줄이 시각으로 시작하지 않는다 — {line}"
    assert "무언가 일어났다" in line


def test_health_noise_is_folded():
    """감독자가 분당 폴링해서 그 줄만 1,461개였다(실측). 읽을 수 없는 로그는 기록이 아니다."""
    f = logctx.HealthNoiseFilter()
    mk = lambda msg: logging.LogRecord("x", logging.INFO, "p", 1, msg, None, None)
    assert f.filter(mk('127.0.0.1 - "GET /api/health HTTP/1.1" 200 OK')) is False
    assert f.filter(mk('127.0.0.1 - "GET /api/v1/sessions HTTP/1.1" 200 OK')) is True


def test_a_correlator_from_outside_cannot_inject_a_log_line():
    """바깥 값이 그대로 들어가면 개행으로 한 줄을 여러 줄로 갈라 grep 을 어긋나게 할 수 있다."""
    got = logctx.sanitize("abc\ndef INFO fake line")
    assert "\n" not in got and " " not in got, got
    assert logctx.sanitize("") and logctx.sanitize("!!!!"), "쓸 게 없으면 새로 만들어야 한다"


# ── 7. 잡 행이 사라져도 크래시가 남나 ─────────────────────────────────────────
@_aio
async def test_a_crash_is_recorded_even_when_the_job_row_is_gone(db, sess):
    """실측 — 이렇게 사라진 잡 4건이 DB 에 없고 `worker exception` 인 잡은 0건이었다."""
    from app.worker import runner_loop

    u, s = sess
    d = storage.session_abs_dir(u.id, s.id)
    err = d / ".job_gone.err"
    err.write_text("이전 출력\n", encoding="utf-8")
    jid = ulid.new().str
    runner_loop._err_paths[jid] = str(err)
    try:
        runner_loop._note_crash(
            jid,
            StaleDataError("UPDATE statement on table 'jobs' expected to update 1 row(s); 0 were matched."),
        )
    finally:
        runner_loop._err_paths.pop(jid, None)

    text = err.read_text(encoding="utf-8")
    assert "이전 출력" in text, "기존 내용을 덮어썼다 — 이어 붙여야 한다"
    assert "KOORM WORKER CRASH" in text, "크래시 블록이 없다"
    assert jid in text and "행이 사라졌다" in text, f"원인을 말하지 않는다 — {text[-300:]}"


def test_a_crash_without_a_known_path_does_not_raise():
    """경로를 모를 때 예외를 내면 복구 경로 자체가 또 죽는다."""
    from app.worker import runner_loop
    runner_loop._note_crash("NOSUCHJOB", RuntimeError("boom"))


@_aio
async def test_a_crash_is_logged_when_the_session_folder_is_already_gone(db, sess, caplog):
    """**첫 판이 여기서 틀렸다.** `delete_session` 은 세션 폴더를 `shutil.rmtree` 한다
    (`sessions/services.py:287-289`). 그러면 잡의 stderr 파일도 사라져서 "파일에 남긴다" 는
    설계가 정작 이 부류에서 아무것도 남기지 못한다. 그래서 **로그가 정본**이어야 한다."""
    import shutil

    from app.worker import runner_loop

    u, s = sess
    d = storage.session_abs_dir(u.id, s.id)
    err = d / ".job_gone2.err"
    err.write_text("이전 출력\n", encoding="utf-8")
    shutil.rmtree(d)  # ← 세션 삭제가 하는 것
    assert not err.exists()

    jid = ulid.new().str
    runner_loop._err_paths[jid] = str(err)
    try:
        with caplog.at_level(logging.ERROR, logger="koorm.worker"):
            noted = runner_loop._note_crash(jid, StaleDataError("0 were matched."))
    finally:
        runner_loop._err_paths.pop(jid, None)

    assert noted is False, "폴더가 없는데 파일에 남겼다고 보고했다 — 그 보고를 믿고 안심하게 된다"
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert jid in joined and "행이 사라졌다" in joined, f"로그에 원인이 없다 — {joined}"
