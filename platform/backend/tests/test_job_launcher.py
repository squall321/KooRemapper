# 실행기(launcher) 설정 — 비면 지금과 똑같고, 있으면 접두 · TERM 먼저 · 정리 · 환경 허용 목록이 붙나
"""왜 이 시험이 있나 (2026-10-23).

HWAX Portal 운영이 prod 의 job 자식을 다른 노드에서 돌리려 한다(요청서
`docs/requests/hwax-job-launcher-request-2026-10-23.md`). 앱이 받는 것은 실행기 명령 한 줄
(`KOORM_JOB_LAUNCHER`)뿐이다. 여기서 못 박는 것은 요청서 5장의 V1–V10 과 K3 · K4 · K6 · K7 이다.

  · **설정이 비면 지금과 똑같다(V1).** argv · 환경 · 시간 초과의 바로 SIGKILL · 종료 때의 SIGKILL.
  · 실제 노드 기록(답신 ③ 안 A) · `.nfs*` 를 출력에서 뺀다(답신 ② 덧붙임) — 10-23 결정.
  · 실행기를 거쳐도 연산 꼴마다 결과가 같다(V2 그 자리 exec · V3 다른 그룹의 자식).
  · 실행기는 **TERM 먼저**다(V7 · K3). 바로 죽이면 원격이 아직 쓰는 파일을 출력으로 등록한다.
  · 재기동은 행을 닫기 **전에** `--reap` 한다(V8).

⚠ 시험 DB 는 떠 있는 API 의 DB 다. 행을 queued 로 넣으면 그 워커가 1초 안에 집어 가 실행기 없이
돌린다 — 행은 **running** 으로 넣고 `_execute` 를 직접 부른다. V9 는 `_loop` 를 그대로 돌리되 클레임만
메모리 큐로 바꾼다. 세션당 하나는 `test_a_running_local_job_still_blocks_the_session` 이 고정한다.
"""
import asyncio
import hashlib
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, func, select

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Session, SessionFile, User
from app.shared import security, storage
from app.worker import runner_loop as rl

_aio = pytest.mark.asyncio(loop_scope="session")
LAUNCH = Path(__file__).resolve().parent / "data" / "launcher"
REPO = Path(__file__).resolve().parents[3]
REAL_BIN = settings.kooremapper_bin
_needs_bin = pytest.mark.skipif(not REAL_BIN.exists(), reason="배포 바이너리가 없다")

_DECK = (
    "*KEYWORD\n"
    "*NODE\n"
    "         1             0.0             0.0             0.0\n"
    "         2            10.0             0.0             0.0\n"
    "*END\n"
)
_DB_ARGS = {"config": {"model": "model.k", "output": "model_db.k",
                       "preset": "all", "dt": 0.001, "dt_plot": 0.01}}


# ── 도우미 ─────────────────────────────────────────────────────────────────────
def _slow_bin(tmp_path: Path, *, hold: float = 60, mark: Path | None = None) -> Path:
    """느린 가짜 바이너리 래퍼. tmp_path 가 곧 이 시험의 표식이다 — 남은 프로세스를 그것으로 찾는다."""
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    w = d / "KooRemapper"
    opts = f"--tag {tmp_path} --hold {hold}" + (f" --mark {mark}" if mark else "")
    w.write_text(f'#!/bin/sh\nexec {sys.executable} {LAUNCH / "slowbin.py"} {opts} "$@"\n')
    w.chmod(0o755)
    return w


def _alive_with(tag: str) -> list[int]:
    """cmdline 에 tag 가 든 살아 있는 프로세스(좀비는 뺀다)."""
    found = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            state = (p / "stat").read_text().rsplit(") ", 1)[1].split()[0]
        except (OSError, IndexError):
            continue
        if tag in cmd and state != "Z":
            found.append(int(p.name))
    return found


def _kill_all(tag: str) -> None:
    for pid in _alive_with(tag):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


async def _until(pred, timeout: float) -> None:
    end = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > end:
            raise AssertionError(f"{timeout}초 안에 조건이 서지 않았다")
        await asyncio.sleep(0.05)


def _spy_kills(monkeypatch) -> list:
    """`_kill_proc_group` 이 보낸 신호를 (신호, 시각) 으로 적고 실제로도 보낸다."""
    sent, real = [], rl._kill_proc_group

    def spy(proc, sig):
        sent.append((sig, time.monotonic()))
        real(proc, sig)

    monkeypatch.setattr(rl, "_kill_proc_group", spy)
    return sent


async def _mk_session(db, tag):
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
    shutil.rmtree(storage.session_abs_dir(u.id, s.id), ignore_errors=True)


@pytest.fixture
async def sess(db):
    u, s = await _mk_session(db, "launch")
    try:
        yield u, s
    finally:
        await _drop(db, u, s)


async def _add_job(db, u, s, op, args) -> Job:
    """행을 **running** 으로 넣는다(모듈 docstring ⚠)."""
    job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id,
              operation=op, args=args, status="running")
    db.add(job)
    await db.commit()
    return job


async def _run_job(db, u, s, op, args) -> Job:
    job = await _add_job(db, u, s, op, args)
    await rl._execute(job.id)
    await db.refresh(job)
    return job


async def _outputs(db, job) -> dict[str, str]:
    rows = (await db.execute(
        select(SessionFile).where(SessionFile.id.in_(job.output_file_ids or [])))).scalars()
    return {f.filename: f.sha256 for f in rows}


# ── V1 · 설정이 비면 지금과 똑같다 ──────────────────────────────────────────────
class _FakeProc:
    pid = 2 ** 22 + 1

    def __init__(self, waits):
        self._waits = list(waits)

    def wait(self, timeout=None):
        w = self._waits.pop(0)
        if isinstance(w, BaseException):
            raise w
        return w


def test_v1_empty_setting_runs_the_binary_exactly_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "job_launcher", "")
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(cmd=cmd, kw=kw)
        return _FakeProc([0])

    monkeypatch.setattr(rl.subprocess, "Popen", fake_popen)
    assert rl._run_blocking("J1", ["info", "m.k"], tmp_path, tmp_path / "o", tmp_path / "e") == 0
    assert seen["cmd"] == [str(settings.kooremapper_bin), "info", "m.k"]
    assert "env" not in seen["kw"], "설정이 비면 환경을 건드리지 않는다 — API 환경을 그대로 물려준다"
    assert seen["kw"]["cwd"] == str(tmp_path)
    assert seen["kw"]["start_new_session"] is True and seen["kw"]["text"] is True


def test_v1_empty_setting_times_out_with_sigkill_and_no_sigterm(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "job_launcher", "")
    monkeypatch.setattr(rl.subprocess, "Popen",
                        lambda cmd, **kw: _FakeProc([subprocess.TimeoutExpired(cmd, 1), -9]))
    sent = []
    monkeypatch.setattr(rl, "_kill_proc_group", lambda proc, sig: sent.append(sig))
    assert rl._run_blocking("J1", ["info"], tmp_path, tmp_path / "o", tmp_path / "e") == 124
    assert sent == [signal.SIGKILL], "로컬 바이너리는 그룹 리더다 — 지금처럼 바로 SIGKILL"
    assert (tmp_path / "e").read_text().endswith("[timeout exceeded]\n")


async def test_v1_empty_setting_stops_the_worker_with_sigkill(monkeypatch):
    monkeypatch.setattr(settings, "job_launcher", "")
    sent = []
    monkeypatch.setattr(rl, "_kill_proc_group", lambda proc, sig: sent.append(sig))
    monkeypatch.setattr(rl, "_worker_task", None)
    monkeypatch.setitem(rl._running, "J1", object())
    try:
        await rl.stop_worker()
    finally:
        rl._stop.clear()
    assert sent == [signal.SIGKILL]


# ── K1 · K5 · K6 · 접두 꼴 · 환경 · 스냅샷 ─────────────────────────────────────
def test_k1_the_launcher_prefixes_the_original_command(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "job_launcher", "/opt/hw/forge-launch --app 'kooremapper prod'")
    seen = {}
    monkeypatch.setattr(rl.subprocess, "Popen",
                        lambda cmd, **kw: (seen.update(cmd=cmd, kw=kw), _FakeProc([0]))[1])
    rl._run_blocking("J7", ["database", "/w/config.yaml"], tmp_path, tmp_path / "o", tmp_path / "e")
    assert seen["cmd"] == [
        "/opt/hw/forge-launch", "--app", "kooremapper prod",          # shlex.split — 따옴표가 산다
        "--job-id", "J7", "--kind", "database",
        "--", str(settings.kooremapper_bin), "database", "/w/config.yaml",
    ]
    assert seen["kw"]["cwd"] == str(tmp_path) and seen["kw"]["start_new_session"] is True


@_needs_bin
def test_v10_the_launcher_gets_no_koorm_names(tmp_path, monkeypatch):
    """실제 프로세스가 받은 환경의 **이름**을 본다(값은 적지 않는다 — 계약 L2 · H8)."""
    names = tmp_path / "env.txt"
    monkeypatch.setattr(settings, "job_launcher", f"{LAUNCH / 'envdump.sh'} {names}")
    for k, v in {"KOORM_JWT_SECRET": "not-a-secret", "KOORM_DATABASE_URL": "postgresql://x",
                 "GH_TOKEN": "x", "OMP_NUM_THREADS": "3", "KOO_MAP_DEBUG": "1",
                 "KOOREMAPPER_GMSH": "/x/gmsh", "LC_ALL": "C.UTF-8"}.items():
        monkeypatch.setenv(k, v)
    rl._run_blocking("JE", ["info", "nonexistent.k"], tmp_path, tmp_path / "o", tmp_path / "e")
    got = set(names.read_text().split())
    assert not {n for n in got if n.startswith("KOORM_")}, got
    assert "GH_TOKEN" not in got, "허용 목록 밖의 비밀 꼴 이름도 가지 않는다"
    assert {"PATH", "HOME", "OMP_NUM_THREADS", "KOO_MAP_DEBUG", "KOOREMAPPER_GMSH", "LC_ALL"} <= got, got


def test_k6_the_snapshot_says_which_launcher_ran_the_job(monkeypatch):
    monkeypatch.setattr(settings, "job_launcher", "")
    assert rl._env_snapshot()["launcher"] is None
    monkeypatch.setattr(settings, "job_launcher", "/opt/hw/forge-launch --app kooremapper")
    snap = rl._env_snapshot()
    assert snap["launcher"] == "/opt/hw/forge-launch --app kooremapper"
    assert snap["host"]["nodename"] == os.uname().nodename, "nodename 은 그대로 API 노드다"


# ── 답신 ③ 안 A · 실제 노드 기록 / ② 덧붙임 · `.nfs*` (10-23 결정) ────────────────
def test_3a_job_node_reads_one_clean_line(tmp_path):
    f = tmp_path / ".job_J9.node"
    assert rl._job_node(tmp_path, "J9") is None, "파일이 없으면 null"
    for text, want in (("h02\n", "h02"), ("  node-3.cluster_a  \n두번째 줄\n", "node-3.cluster_a"),
                       ("h02; rm -rf /\n", None), ("x" * 65 + "\n", None), ("", None), ("\n", None)):
        f.write_text(text, encoding="utf-8")
        assert rl._job_node(tmp_path, "J9") == want, (text, want)


@_needs_bin
@_aio
async def test_3a_the_job_records_where_it_actually_ran(db, sess, monkeypatch):
    u, s = sess
    (storage.session_abs_dir(u.id, s.id) / "model.k").write_text(_DECK, encoding="latin-1")
    monkeypatch.setattr(settings, "job_launcher", f"{LAUNCH / 'nodewrite.sh'} h03")
    job = await _run_job(db, u, s, "database", _DB_ARGS)
    assert job.status == "succeeded", job.error_summary
    host = job.env_snapshot["host"]
    assert host["job_node"] == "h03", host
    assert host["nodename"] == os.uname().nodename, "nodename 은 그대로 API 노드다(같은 칸이 잡마다 다른 뜻이 되지 않는다)"
    assert not [n for n in await _outputs(db, job) if n.startswith(".job_")], "노드 기록 파일은 산출이 아니다"


@_needs_bin
@_aio
async def test_3a_without_a_launcher_job_node_is_null(db, sess, monkeypatch):
    u, s = sess
    (storage.session_abs_dir(u.id, s.id) / "model.k").write_text(_DECK, encoding="latin-1")
    monkeypatch.setattr(settings, "job_launcher", "")
    job = await _run_job(db, u, s, "database", _DB_ARGS)
    assert job.status == "succeeded", job.error_summary
    assert job.env_snapshot["host"]["job_node"] is None


@_needs_bin
@_aio
async def test_nfs_leftovers_are_not_registered_as_outputs(db, sess, monkeypatch):
    u, s = sess
    d = storage.session_abs_dir(u.id, s.id)
    (d / "model.k").write_text(_DECK, encoding="latin-1")
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "nfsjunk.sh"))
    job = await _run_job(db, u, s, "database", _DB_ARGS)
    assert job.status == "succeeded", job.error_summary
    outs = await _outputs(db, job)
    assert "model_db.k" in outs, outs
    assert not [n for n in outs if n.rsplit("/", 1)[-1].startswith(".nfs")], outs
    assert (d / ".nfs000000000badc0de00000001").exists(), "판정 때 그 파일이 있었다(시험이 헛돌지 않았다)"


# ── V2 · V3 · 연산 꼴마다 같은 결과 ────────────────────────────────────────────
# 위치 인자 둘(generate → map: OpenMP · 진행률 %) · yaml · matdb(번들 DB) · meshfix(gmsh)
_SHAPES = [
    ("generate", {"type": "torus", "output_prefix": "torus", "dim-i": 10, "dim-j": 5, "dim-k": 5}),
    ("map", {"bent_mesh": "torus_bent.k", "flat_mesh": "torus_flat.k", "output": "torus_mapped.k"}),
    ("database", _DB_ARGS),
    ("matdb", {"model": "test_matdb_model.k", "output": "test_matdb_result.k",
               "mat_type": "MAT_ELASTIC", "thermal": True}),
    ("meshfix", {"model": "tetramesh.k", "output": "meshfix_out.k", "pid": 1}),
]


def _content_key(p: Path) -> str:
    """`$ Date:` 줄(실행 시각)을 뺀 내용의 해시. 같은 op 을 두 번 돌려 diff 하면 다른 것은 그 줄뿐이다
    (generate · map 산출에만 있고 database · matdb · meshfix 산출은 바이트까지 같다)."""
    keep = [ln for ln in p.read_bytes().splitlines(keepends=True) if not ln.startswith(b"$ Date:")]
    return hashlib.sha256(b"".join(keep)).hexdigest()


async def _run_shapes(db, u, s) -> dict:
    from app.modules.jobs.routes import _live_progress

    d = storage.session_abs_dir(u.id, s.id)
    (d / "model.k").write_text(_DECK, encoding="latin-1")
    shutil.copy(REPO / "materials" / "test_matdb_model.k", d)
    shutil.copy(REPO / "examples" / "mesh" / "tetramesh.k", d)
    got = {}
    for op, args in _SHAPES:
        job = await _run_job(db, u, s, op, args)
        outs = await _outputs(db, job)
        for name, sha in outs.items():
            assert sha == hashlib.sha256((d / name).read_bytes()).hexdigest(), (
                f"{op} · {name} — 등록한 해시가 디스크와 다르다")
        got[op] = {"status": job.status, "exit": job.exit_code, "error": job.error_summary,
                   "outputs": {n: _content_key(d / n) for n in outs},
                   "progress": _live_progress(job.stdout_path)}
    return got


@_needs_bin
@_aio
async def test_v2_v3_every_op_shape_gives_the_same_result_through_a_launcher(db, monkeypatch):
    runs = {}
    for name, launcher in [("direct", ""),
                           ("passthrough", str(LAUNCH / "passthrough.sh")),
                           ("childwrap", str(LAUNCH / "childwrap.py"))]:
        monkeypatch.setattr(settings, "job_launcher", launcher)
        u, s = await _mk_session(db, f"shape_{name}")
        try:
            runs[name] = await _run_shapes(db, u, s)
        finally:
            await _drop(db, u, s)
    base = runs["direct"]
    for op, r in base.items():
        assert r["status"] == "succeeded" and r["outputs"], (op, r)
    assert base["map"]["progress"] is not None, "진행률을 찍는 op 이 하나는 있어야 V3 가 뜻이 있다"
    for name in ("passthrough", "childwrap"):
        for op, r in runs[name].items():
            assert r == base[op], f"{name} · {op} 가 직접 실행과 다르다 — {r} / {base[op]}"


# ── V5 · V6 · 실행기의 실패와 죽음 ─────────────────────────────────────────────
@_needs_bin
@_aio
async def test_v5_launcher_failure_is_a_failed_job_with_its_line(db, sess, monkeypatch):
    u, s = sess
    (storage.session_abs_dir(u.id, s.id) / "model.k").write_text(_DECK, encoding="latin-1")
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "fail125.sh"))
    job = await _run_job(db, u, s, "database", _DB_ARGS)
    assert job.status == "failed" and job.exit_code == 125, (job.status, job.exit_code)
    assert "[launcher] no node" in job.error_summary, job.error_summary
    assert job.output_file_ids == [], "원격에서 시작하지 못했으면 아무것도 남지 않는다"


@_needs_bin
@_aio
async def test_v6_a_killed_launcher_fails_the_job_and_the_next_one_runs(db, sess, tmp_path, monkeypatch):
    u, s = sess
    tag = str(tmp_path)
    (storage.session_abs_dir(u.id, s.id) / "model.k").write_text(_DECK, encoding="latin-1")
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "childwrap.py"))
    job = await _add_job(db, u, s, "database", _DB_ARGS)
    task = asyncio.create_task(rl._execute(job.id))
    try:
        await _until(lambda: job.id in rl._running and len(_alive_with(tag)) >= 2, 15)
        os.kill(rl._running[job.id].pid, signal.SIGKILL)      # 실행기 하나만 — 그룹이 아니다
        await asyncio.wait_for(task, 10)
        await _until(lambda: not _alive_with(tag), 5)         # 시험 실행기는 PDEATHSIG 로 자식을 끝낸다
    finally:
        _kill_all(tag)
        if not task.done():
            task.cancel()
    await db.refresh(job)
    assert job.status == "failed" and job.error_summary.startswith("exit -9"), job.error_summary

    monkeypatch.setattr(settings, "kooremapper_bin", REAL_BIN)
    nxt = await _run_job(db, u, s, "database", _DB_ARGS)
    assert nxt.status == "succeeded", (nxt.status, nxt.error_summary)


# ── V4 · 취소 ──────────────────────────────────────────────────────────────────
@_aio
async def test_v4_cancel_through_childwrap_ends_the_child_group(db, sess, tmp_path, monkeypatch):
    u, s = sess
    tag = str(tmp_path)
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "childwrap.py"))
    job = await _add_job(db, u, s, "database", _DB_ARGS)
    task = asyncio.create_task(rl._execute(job.id))
    try:
        await _until(lambda: job.id in rl._running and len(_alive_with(tag)) >= 2, 15)
        t0 = time.monotonic()
        assert rl.request_cancel(job.id)
        await asyncio.wait_for(task, 5)
        took = time.monotonic() - t0
        left = _alive_with(tag)
    finally:
        _kill_all(tag)
        if not task.done():
            task.cancel()
    await db.refresh(job)
    assert job.status == "canceled", (job.status, job.error_summary)
    assert took < 5, took
    assert not left, f"남은 프로세스 {left}"


# ── V7 · K2 · 시간 초과 ────────────────────────────────────────────────────────
def test_v7_timeout_through_a_launcher_sends_term_then_kill(tmp_path, monkeypatch):
    """TERM 을 무시하는 실행기 — 유예가 지나야 KILL 이 간다. 순서와 간격을 잰다."""
    tag = str(tmp_path)
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "ignoreterm.sh"))
    monkeypatch.setattr(settings, "job_timeout_sec", 1)
    monkeypatch.setattr(settings, "job_term_grace_sec", 1)
    sent = _spy_kills(monkeypatch)
    try:
        rc = rl._run_blocking("JT", ["database", "x.yaml"], tmp_path, tmp_path / "o", tmp_path / "e")
        left = _alive_with(tag)
    finally:
        _kill_all(tag)
    assert rc == 124
    assert [sig for sig, _ in sent] == [signal.SIGTERM, signal.SIGKILL]
    assert 0.8 <= sent[1][1] - sent[0][1] <= 2.5, "SIGKILL 은 유예(1초) 뒤에 간다"
    assert (tmp_path / "e").read_text().rstrip().endswith("[timeout exceeded]")
    assert not left


def test_k2_a_launcher_that_honours_term_needs_no_kill(tmp_path, monkeypatch):
    tag = str(tmp_path)
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "childwrap.py"))
    monkeypatch.setattr(settings, "job_timeout_sec", 1)
    monkeypatch.setattr(settings, "job_term_grace_sec", 5)
    sent = _spy_kills(monkeypatch)
    t0 = time.monotonic()
    try:
        rc = rl._run_blocking("JT", ["database", "x.yaml"], tmp_path, tmp_path / "o", tmp_path / "e")
        took = time.monotonic() - t0
        left = _alive_with(tag)
    finally:
        _kill_all(tag)
    assert rc == 124 and [sig for sig, _ in sent] == [signal.SIGTERM]
    assert took < 4, "TERM 을 받은 실행기는 원격을 끝내고 바로 나온다 — 유예를 다 쓰지 않는다"
    assert not left


@_aio
async def test_v7_outputs_are_registered_only_after_the_remote_child_ended(db, sess, tmp_path, monkeypatch):
    """원격 흉내 실행기 — 실행기가 죽어도 자식은 산다. 바로 KILL 하면 등록 뒤에도 파일이 자란다."""
    u, s = sess
    tag = str(tmp_path)
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "remotewrap.py"))
    monkeypatch.setattr(settings, "job_timeout_sec", 2)
    monkeypatch.setattr(settings, "job_term_grace_sec", 5)
    try:
        job = await _run_job(db, u, s, "database", _DB_ARGS)
        await asyncio.sleep(0.6)            # 원격이 살아 있으면 이 사이에 줄이 는다
        left = _alive_with(tag)
    finally:
        _kill_all(tag)
    assert job.exit_code == 124 and job.status == "failed", (job.status, job.exit_code)
    assert "[timeout exceeded]" in job.error_summary
    registered = await _outputs(db, job)
    disk = hashlib.sha256(
        (storage.session_abs_dir(u.id, s.id) / "slow_out.k").read_bytes()).hexdigest()
    assert registered.get("slow_out.k") == disk, "등록한 뒤에 파일이 바뀌었다 — 원격이 쓰는 중에 등록했다"
    assert not left, f"남은 프로세스 {left}"


# ── K3 · 종료 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("launcher,want", [
    ("childwrap.py", [signal.SIGTERM]),                    # TERM 을 받으면 원격을 끝내고 나온다
    ("ignoreterm.sh", [signal.SIGTERM, signal.SIGKILL]),   # 안 나오면 유예 뒤 KILL
])
async def test_k3_shutdown_sends_term_first_through_a_launcher(tmp_path, monkeypatch, launcher, want):
    tag = str(tmp_path)
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / launcher))
    monkeypatch.setattr(rl, "_worker_task", None)
    sent = _spy_kills(monkeypatch)
    run = asyncio.create_task(asyncio.to_thread(
        rl._run_blocking, "JS", ["database", "x.yaml"], tmp_path, tmp_path / "o", tmp_path / "e"))
    try:
        await _until(lambda: "JS" in rl._running and _alive_with(tag), 15)
        await asyncio.sleep(0.3)            # 실행기가 신호 손잡이를 걸 틈
        t0 = time.monotonic()
        await rl.stop_worker()
        took = time.monotonic() - t0
        await asyncio.wait_for(run, 5)
        await _until(lambda: not _alive_with(tag), 3)
    finally:
        rl._stop.clear()
        _kill_all(tag)
    assert [sig for sig, _ in sent] == want
    assert took < 3.5, "lifespan 이 3.5초에 끊는다 — 그 안에 들어야 한다"


# ── V8 · K4 · 재기동 ──────────────────────────────────────────────────────────
async def _no_running_local_jobs() -> bool:
    async with SessionLocal() as sg:
        n = (await sg.execute(select(func.count(Job.id)).where(
            Job.status == "running", Job.external_kind.is_(None)))).scalar_one()
    return n == 0


@_aio
async def test_v8_restart_reaps_through_the_launcher_before_closing_rows(db, tmp_path, monkeypatch):
    if not await _no_running_local_jobs():
        pytest.skip("running 잡이 이미 있다 — reconcile_orphans 는 전역이라 건드리지 않는다")
    rec = tmp_path / "reaped.txt"
    monkeypatch.setattr(settings, "job_launcher", f"{LAUNCH / 'reaprec.sh'} {rec} 0")
    pairs = [await _mk_session(db, "reap_a"), await _mk_session(db, "reap_b")]
    try:
        ids = [(await _add_job(db, u, s, "database", {})).id for u, s in pairs]
        t0 = time.monotonic()
        await rl.reconcile_orphans()
        took = time.monotonic() - t0
        reaped = dict(reversed(ln.split()) for ln in rec.read_text().splitlines())
        async with SessionLocal() as s2:
            rows = [await s2.get(Job, i) for i in ids]
    finally:
        for u, s in pairs:
            await _drop(db, u, s)
    assert set(reaped) == set(ids), f"--reap 를 받은 id {sorted(reaped)} / 고아 {sorted(ids)}"
    for r in rows:
        assert r.status == "failed" and r.error_summary == "worker restarted while job was running"
        assert r.finished_at.timestamp() >= max(float(t) for t in reaped.values()), (
            "행이 정리보다 먼저 닫혔다 — 같은 세션의 다음 잡이 끝나는 중인 원격 job 과 겹친다")
    assert took < 1.8, f"정리는 한꺼번에 부른다(하나에 1초) — {took:.2f}초"


@_aio
@pytest.mark.parametrize("how", ["3", "hang"])
async def test_k4_a_failing_reap_does_not_block_the_restart(db, tmp_path, monkeypatch, caplog, how):
    if not await _no_running_local_jobs():
        pytest.skip("running 잡이 이미 있다 — reconcile_orphans 는 전역이라 건드리지 않는다")
    monkeypatch.setattr(settings, "job_launcher", f"{LAUNCH / 'reaprec.sh'} {tmp_path / 'r.txt'} {how}")
    monkeypatch.setattr(rl, "_REAP_TIMEOUT_SEC", 1)
    u, s = await _mk_session(db, "reap_fail")
    try:
        jid = (await _add_job(db, u, s, "database", {})).id
        with caplog.at_level(logging.WARNING, logger="koorm.worker"):
            await rl.reconcile_orphans()
        async with SessionLocal() as s2:
            row = await s2.get(Job, jid)
    finally:
        await _drop(db, u, s)
    assert row.status == "failed", "정리가 실패해도 회수는 진행한다"
    assert any("--reap" in r.getMessage() and jid in r.getMessage() for r in caplog.records)


# ── V9 · 동시 수 ──────────────────────────────────────────────────────────────
async def test_v9_the_concurrency_cap_holds_through_a_launcher(tmp_path, monkeypatch):
    mark = tmp_path / "mark"
    mark.mkdir()
    monkeypatch.setattr(settings, "kooremapper_bin", _slow_bin(tmp_path, hold=1.5, mark=mark))
    monkeypatch.setattr(settings, "job_launcher", str(LAUNCH / "passthrough.sh"))
    monkeypatch.setattr(settings, "worker_concurrency", 8)
    queue = [f"J{i:02d}" for i in range(12)]
    done: list[str] = []

    class _NoDb:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    async def fake_claim(_db):
        return queue.pop(0) if queue else None

    async def fake_execute(jid):
        await asyncio.to_thread(rl._run_blocking, jid, ["database", "x.yaml"], tmp_path,
                                tmp_path / f"{jid}.out", tmp_path / f"{jid}.err")
        done.append(jid)

    async def _noop(*_a, **_k):
        return 0

    monkeypatch.setattr(rl, "SessionLocal", _NoDb)
    monkeypatch.setattr(rl, "_claim_one", fake_claim)
    monkeypatch.setattr(rl, "_execute", fake_execute)
    monkeypatch.setattr(rl, "reconcile_orphans", _noop)
    monkeypatch.setattr(rl, "_poll_external_once", _noop)
    monkeypatch.setattr(rl.plm_sync, "enabled", lambda: False)
    rl._stop.clear()
    loop_task = asyncio.create_task(rl._loop())
    try:
        await _until(lambda: len(done) == 12, 40)
    finally:
        rl._stop.set()
        await asyncio.wait_for(loop_task, 10)
        rl._stop.clear()
        _kill_all(str(tmp_path))
    spans = [(float((mark / f"{p.stem}.start").read_text()), float(p.read_text()))
             for p in mark.glob("*.end")]
    assert len(spans) == 12, spans
    peak = max(sum(1 for a, b in spans if a <= t < b) for t, _ in spans)
    assert peak == 8, f"동시에 뜬 수 {peak} — 상한 8 까지 뜨고 넘지 않아야 한다"


# ── K7 · 세션 삭제 뒤 남은 폴더 ───────────────────────────────────────────────
@_aio
@pytest.mark.parametrize("removable_on_retry", [True, False])
async def test_k7_a_folder_left_after_rmtree_is_retried_then_reported(db, monkeypatch, caplog,
                                                                       removable_on_retry):
    from app.modules.sessions import services as svc

    u, s = await _mk_session(db, "k7")
    d = storage.session_abs_dir(u.id, s.id)
    (d / ".nfs000000000001").write_text("held by another node")
    calls = []

    def rmtree(path, ignore_errors=False):          # 첫 번째는 NFS 처럼 못 지운다
        calls.append(path)
        if removable_on_retry and len(calls) > 1:
            shutil.rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(svc, "shutil", SimpleNamespace(rmtree=rmtree))
    monkeypatch.setattr(svc, "_RMTREE_RETRY_SEC", 0.01)
    try:
        with caplog.at_level(logging.WARNING, logger=svc.logger.name):
            await svc.delete_session(db, s)
        gone = await db.get(Session, s.id) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)
        await db.execute(delete(User).where(User.id == u.id))
        await db.commit()
    assert gone and len(calls) == 2, calls
    said = " ".join(r.getMessage() for r in caplog.records)
    if removable_on_retry:
        assert "폴더가 남았다" not in said
    else:
        assert "폴더가 남았다(항목 1개, 그중 .nfs* 1개)" in said, said
