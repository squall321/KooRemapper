"""Async job worker — claims queued jobs and runs the KooRemapper binary.

Runs as a background asyncio task inside the API process (started in lifespan).
Concurrency is bounded by settings.worker_concurrency. Each job:
  1. atomic-claim (status queued→running)
  2. argbuild → argv + any written config.yaml
  3. snapshot session dir, run binary (cwd=session dir), capture stdout/stderr to files
     (through the KOORM_JOB_LAUNCHER command when set — it may run the binary on another node)
  4. register NEW files as session_files(kind=output, origin_job_id)
  5. status → succeeded|failed|canceled, exit_code, output_file_ids, error_summary
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import signal
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm.exc import StaleDataError

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Session, SessionFile
from app.runner import catalog
from app.runner.argbuild import build_command
from app.runner.gmsh_probe import probe as gmsh_probe
from app.runner.kfile_inspect import inspect_kfile
from app.runner.newline_audit import audit_newlines
from app.runner.stcx_client import (StcxClient, StcxUploader, parse_status, parse_submit,
                                    registry_id_of, result_dir_of)
from app.shared import storage
from app.worker import plm_sync
from app.shared.buildinfo import build_info
from app.shared.logctx import reset_correlator, set_correlator

logger = logging.getLogger("koorm.worker")

# 외부 잡 표식. Job.external_kind 에 들어가고, 고아 회수·세션 직렬화가 이 값으로 갈린다.
EXTERNAL_KIND = "stcx_mcp"
# 한 번의 폴링 스캔에서 볼 잡 수. 많이 잡으면 게이트웨이를 한꺼번에 두드린다.
_POLL_BATCH = 20

# job_id -> Popen, for cancellation
_running: dict[str, subprocess.Popen] = {}
# job_id -> stderr 파일 경로. **잡 행이 사라져도** 크래시를 적을 자리가 필요해서 둔다.
# 실측(2026-09-29): 잡이 도는 중에 세션이 지워지면 `ON DELETE CASCADE` 로 행이 사라지고,
# 복구가 `db.get(Job, jid)` 로 None 을 받아 아무것도 쓰지 못했다 — 잡 4건이 제품에서 흔적 없이
# 사라졌고 `error_summary='worker exception'` 인 잡은 **0건**이었다. 행에서 경로를 되찾을 수
# 없으므로 여기에 들고 있는다(`_running` 과 같은 규율).
_err_paths: dict[str, str] = {}
_stop = asyncio.Event()


def _env_snapshot() -> dict:
    """이 잡이 **어느 빌드·어느 환경**에서 돌았나. 기존 계산기를 그대로 쓴다 — 새로 세지 않는다.

    ⚠ gmsh 의 **경로는 담지 않는다.** 호스트 절대 경로라 번들로 내보낼 때 접어야 하고, 정작 그
    값은 이미 잡 stdout 에 찍힌다(`meshfix.cpp` 가 `Gmsh: <경로> (v…)` 를 낸다). 없는 정보를
    만드는 칸이 아니라, **바이너리 리비전**을 남기는 칸이다 — 배너는 상수 `Version 1.8.0` 이어서
    로그만으로는 어느 빌드였는지 알 수 없었다.

    `launcher` 는 실행기 명령 줄 그대로다(없으면 None). `host.nodename` 은 **API 노드**다 — 실행기를 쓰면
    job 이 실제로 돈 노드는 실행기가 `.job_<id>.node` 에 남기고, 잡이 끝난 뒤 `host.job_node` 로 옮긴다
    (`_job_node` — HWAX 답신 ③ 안 A, 10-23).
    `omp_num_threads` 는 바이너리가 받은 OpenMP 스레드 수다 — 실행기가 없으면 `_omp_threads` 가 정하고
    (운영자가 API 환경에 준 값이 있으면 그 값), 실행기가 있으면 실행기 몫이라 None 이다.
    """
    b = build_info(settings.kooremapper_bin)
    g = gmsh_probe(settings.kooremapper_bin)
    return {
        "binary": {
            "revision": b.get("revision"),
            "revision_describe": b.get("revision_describe"),
            "revision_matches_binary": b.get("revision_matches_binary"),
            "sha256": b.get("binary_sha256"),
            "mtime_utc": b.get("binary_mtime_utc"),
            "published_utc": b.get("published_utc"),
            "build_method": b.get("build_method"),
        },
        "gmsh": {"available": g.get("available"), "version": g.get("version")},
        "platform": {"app_env": settings.app_env},
        "host": {"nodename": os.uname().nodename},
        "launcher": settings.job_launcher or None,
        "omp_num_threads": (None if settings.job_launcher
                            else os.environ.get("OMP_NUM_THREADS") or _omp_threads()),
    }


def _omp_threads() -> int | None:
    """실행기가 없을 때 잡 하나가 쓸 OpenMP 스레드 수 — 코어 ÷ 동시 슬롯(10-23 결정 4B).

    OpenMP 를 쓰는 op(map · prestress 등)은 스레드 수를 주지 않으면 libgomp 가 코어를 **다** 쓴다. 슬롯이
    넷이면 그런 잡 넷이 32코어에 128스레드를 올려 서로 다툰다. 운영자가 API 환경에 `OMP_NUM_THREADS` 를
    줬으면 그 값을 존중한다(None — 환경을 건드리지 않는다). 코어는 이 프로세스가 쓸 수 있는 CPU 다(affinity).
    """
    if "OMP_NUM_THREADS" in os.environ:
        return None
    try:
        cores = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cores = os.cpu_count() or 1
    return max(1, cores // max(1, settings.worker_concurrency))


# 실행기가 남기는 노드 이름 한 줄(계약 — 노드 이름만, 영숫자 · `.` · `-` · `_`). 꼴이 아니면 적지 않는다.
_JOB_NODE_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def _job_node(work_dir: Path, job_id: str) -> str | None:
    """실행기가 cwd 에 남긴 `.job_<id>.node` 의 첫 줄 — job 이 **실제로 돈** 노드. 없거나 꼴이 아니면 None."""
    try:
        with (work_dir / f".job_{job_id}.node").open("r", encoding="utf-8", errors="replace") as f:
            line = f.readline(256).strip()
    except OSError:
        return None
    return line if _JOB_NODE_RE.fullmatch(line) else None


def _note_crash(job_id: str, exc: BaseException) -> bool:
    """크래시를 **잡 행이 없어도 남는 자리**에 적는다. 파일에 적었으면 True.

    행이 사라지는 경우가 실제로 있다 — 잡이 도는 중에 세션을 지우면 `ON DELETE CASCADE` 로
    행이 날아가고 `UPDATE` 가 `StaleDataError` 를 낸다. 그때 DB 에만 쓰려 하면 아무것도 남지
    않는다(실측 4건).

    ⚠ **로그가 정본이다.** 처음 판은 "파일은 세션 삭제와 별개로 남는다" 고 보고 잡의 stderr
    파일에만 적었는데 **그것이 틀렸다.** `delete_session` 이 세션 폴더를 `shutil.rmtree` 로
    통째로 없앤다(`sessions/services.py:287-289`). 그러면 이 함수의 `open(path, "a")` 가
    `FileNotFoundError` 로 실패해서, 정작 이 함수가 대비하려던 바로 그 부류에서 아무것도 남지
    않는다(손으로 재현해 확인했다). 인스턴스 로그는 세션 삭제와 무관하게 남으므로 **먼저**
    로그에 적고, 파일은 보조 수단으로 둔다(세션이 살아 있는 크래시에서는 잡 옆에 남는 편이 낫다).
    """
    stale = isinstance(exc, StaleDataError)
    why = (
        "잡이 도는 중에 이 잡의 행이 사라졌다 — 세션 삭제(ON DELETE CASCADE)가 가장 흔한 원인이다."
        if stale
        else "워커가 예외로 멈췄다."
    )
    logger.error("job %s crash: %s | %s: %s", job_id, why, type(exc).__name__, exc)
    path = _err_paths.get(job_id)
    if not path:
        return False
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with open(path, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(
                f"\n===== KOORM WORKER CRASH {stamp} =====\n"
                f"job    : {job_id}\n"
                f"reason : {why}\n"
                f"error  : {type(exc).__name__}: {exc}\n"
                f"=====================================\n"
            )
        return True
    except OSError as werr:
        # 세션 폴더가 이미 지워진 경우가 여기다 — 조용히 넘기면 위 로그만 남는데, 그것이 정본이다.
        logger.warning("job %s: 크래시 기록을 파일에 쓰지 못했다(%s) — 로그가 정본이다",
                       job_id, type(werr).__name__)
        return False


async def _claim_one(db) -> str | None:
    """Atomically claim the oldest queued job whose session has no running job.

    Jobs in the SAME session are serialized: they share one work_dir, so running
    two concurrently would let one overwrite the other's config.yaml and mis-
    attribute outputs. Different sessions still run concurrently (up to the
    worker concurrency).

    ⚠ 외부 잡은 그 직렬화의 **이유에 해당하지 않는다.** 그것은 세션 work_dir 에 쓰지
    않고 다른 클러스터에서 돈다. 그런데도 막는 쪽에 세면, 몇 시간짜리 stcx 잡 하나가
    그 세션의 모든 로컬 작업을 그 시간 내내 잠근다 — 사용자에게는 "큐에 걸린 채로
    아무 일도 안 일어나는" 것으로 보인다."""
    row = (
        await db.execute(
            text(
                "UPDATE jobs SET status='running', started_at=now() "
                "WHERE id = (SELECT id FROM jobs q WHERE q.status='queued' "
                "AND NOT EXISTS (SELECT 1 FROM jobs r WHERE r.status='running' "
                "AND r.session_id = q.session_id AND r.external_kind IS NULL) "
                "ORDER BY q.created_at LIMIT 1 FOR UPDATE SKIP LOCKED) "
                "RETURNING id"
            )
        )
    ).first()
    await db.commit()
    return row[0] if row else None


def _kill_proc_group(proc: subprocess.Popen, sig: int) -> None:
    """Signal the whole process group (the binary + any children like gmsh),
    falling back to the direct child if the group can't be addressed."""
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(sig)
        except ProcessLookupError:
            pass


# 실행기에 넘기는 환경의 허용 목록. 바이너리가 읽는 이름은 `KOOREMAPPER_GMSH`·`PATH`(meshfix)와 `KOO_*_DEBUG`
# 뿐이고 `OMP_*` 는 OpenMP 런타임이 읽는다. API 환경에는 DB 주소 · JWT 비밀 · 게이트웨이 토큰이 있다 — 다른
# 노드로 가지 않게 한다. 실행기도 거르므로(계약 L2) 겹 방어다. 실행기가 없으면 쓰지 않는다(지금처럼 물려준다).
_LAUNCH_ENV_NAMES = frozenset({"PATH", "LANG", "HOME", "TMPDIR", "KOOREMAPPER_GMSH"})
_LAUNCH_ENV_PREFIXES = ("LC_", "OMP_")


def _launcher_env() -> dict[str, str]:
    return {
        k: v for k, v in os.environ.items()
        if k in _LAUNCH_ENV_NAMES or k.startswith(_LAUNCH_ENV_PREFIXES)
        or (k.startswith("KOO_") and k.endswith("_DEBUG"))
    }


def _run_blocking(job_id: str, argv: list[str], cwd: Path, out_path: Path, err_path: Path) -> int:
    """Run the binary synchronously (called via asyncio.to_thread)."""
    cmd = [str(settings.kooremapper_bin), *argv]
    launcher = settings.job_launcher
    extra: dict = {}
    if launcher:
        # 실행기가 노드를 골라 같은 이미지 · 같은 cwd 로 원래 명령을 띄운다. 앱은 노드를 모른다.
        # cwd · 로그 파일 · 프로세스 그룹은 그대로 준다 — 실행기가 그룹 리더가 된다.
        cmd = [*shlex.split(launcher), "--job-id", job_id, "--kind", argv[0], "--", *cmd]
        extra["env"] = _launcher_env()
    else:
        threads = _omp_threads()
        if threads is not None:
            # 나머지 환경은 그대로 물려준다 — 더하는 것은 이 한 이름뿐이다(`_omp_threads`).
            extra["env"] = {**os.environ, "OMP_NUM_THREADS": str(threads)}
    with out_path.open("w") as out, err_path.open("w") as err:
        # start_new_session=True → the binary leads its own process group, so a
        # timeout/cancel can kill the whole group (incl. gmsh grandchildren).
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=out, stderr=err, text=True, start_new_session=True, **extra
        )
        _running[job_id] = proc
        try:
            return proc.wait(timeout=settings.job_timeout_sec)
        except subprocess.TimeoutExpired:
            if launcher:
                # ⚠ 실행기는 **TERM 먼저**다. 로컬에서는 바이너리가 그룹 리더라 wait() 가 돌아오면 바이너리도
                # 죽어 있지만, 실행기를 바로 죽이면 원격 job 은 실행기 쪽 임대가 끊을 때까지 계속 돈다. 그 사이
                # `_execute` 가 아직 쓰이는 파일을 출력으로 등록하고, 같은 세션의 다음 job 이 같은 폴더에서 먼저
                # 시작될 수 있다. TERM 을 받은 실행기는 원격이 끝난 것을 보고 나온다(계약 L6).
                _kill_proc_group(proc, signal.SIGTERM)
                try:
                    proc.wait(timeout=settings.job_term_grace_sec)
                except subprocess.TimeoutExpired:
                    _kill_proc_group(proc, signal.SIGKILL)
                    proc.wait()
            else:
                _kill_proc_group(proc, signal.SIGKILL)
                proc.wait()
            err.write("\n[timeout exceeded]\n")
            return 124
        finally:
            _running.pop(job_id, None)


def _is_external(op: str) -> bool:
    entry = catalog.get_operation(op)
    return bool(entry) and entry.get("invocation") == "external"


def _stcx() -> StcxClient:
    return StcxClient(settings.gateway_mcp, settings.gateway_pat)


def _fail(job: Job, why: str) -> None:
    job.status = "failed"
    job.error_summary = why[:2000]
    job.finished_at = datetime.now(timezone.utc)


def _next_poll_delay(prev: int | None) -> int:
    """처음엔 자주, 그다음 늘린다. 시간 단위 잡을 30초마다 두드리지 않는다."""
    lo, hi = settings.stcx_poll_min_sec, settings.stcx_poll_max_sec
    return lo if not prev else min(int(prev) * 2, hi)


# ── stcx 인자 매핑 (요청서 §2) ─────────────────────────────────────────────
# 우리 폼 이름 → 받는 쪽(`fullangle_drop_simulation`) 이름.
# **여기 없는 것은 보내지 않는다** — 받는 쪽 스키마가 `additionalProperties: False` 라
# 모르는 인자를 보내면 제출이 통째로 거절된다(조용히 버려지지는 않는다).
STCX_ARG_MAP: dict[str, str] = {
    "num_directions": "num_angles",
    "height": "drop_height_mm",
    "t_final": "simulation_time_s",
    "drop_surface": "drop_surface_type",
    "ncpu": "ncpu",
    "memory": "memory",
    "time_limit": "time_limit",
    "postprocess_enabled": "enable_postprocess",
    "auto_deep": "auto_deep",
    "auto_sphere": "auto_sphere",
    "yield_stress_mpa": "yield_stress_mpa",
}
# `project_name` 은 이 중 먼저 값이 있는 것을 쓴다.
STCX_PROJECT_KEYS = ("scenario_name", "job_name")
# 이번 판에 보낼 수 있는 폼 칸 전부. 나머지가 값으로 들어오면 **거절**한다.
STCX_SUPPORTED = frozenset({"model", *STCX_ARG_MAP, *STCX_PROJECT_KEYS})

_INCLUDE_TOKEN = b"*INCLUDE"


def _deck_has_include(path: Path, chunk: int = 4 << 20) -> bool:
    """덱 **전체**에서 줄머리의 `*INCLUDE` 를 찾는다.

    ⚠ `session_files.meta["includes"]` 를 쓰지 않는다 — 그것은 **앞 8MB 만** 본다
    (`kfile_inspect.py:86` 의 `max_bytes`). 큰 덱에서 뒤쪽 `*INCLUDE` 를 놓치면 **반쪽
    모델이 stcx 로 올라가 조용히 틀린 결과**가 나온다. 제출 한 번에 GB 를 나르는 길이므로
    전수 훑는 값은 싸다.

    `$` 로 주석 처리된 줄은 넘긴다. `*INCLUDE_PATH`·`*INCLUDE_TRANSFORM` 도 걸리는데,
    그것들도 바깥 파일을 전제하므로 막는 쪽이 맞다. 청크 경계에서는 안전한 방향으로
    (막는 쪽으로) 틀릴 수 있다.
    """
    tail = b""
    with path.open("rb") as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                return False
            hay = (tail + buf).upper()
            pos = hay.find(_INCLUDE_TOKEN)
            while pos != -1:
                head = hay.rfind(b"\n", 0, pos) + 1
                if hay[head:pos].strip(b" \t") == b"":      # 줄머리에서 공백만 지나왔다
                    return True
                pos = hay.find(_INCLUDE_TOKEN, pos + 1)
            tail = hay[-(len(_INCLUDE_TOKEN) - 1):]


def _stcx_tool_args(args: dict, *, job: Job, model_file_path: str) -> dict:
    """폼 값을 받는 쪽 이름으로 옮긴다. `work_dir` 는 **잡마다 고유**해야 한다."""
    out: dict = {
        # ★고유해야 하는 이유 — 받는 쪽은 `work_dir/<model_file>` 이 이미 있으면 새 덱을
        #   조용히 무시한다(`fullangle_drop_simulation/latest/script.sh:46-52`).
        "work_dir": f"{settings.stcx_work_root.rstrip('/')}/{job.id}",
        "lstc_license_ip": settings.stcx_lstc_ip.strip(),
        "model_file_path": model_file_path,
    }
    for ours, theirs in STCX_ARG_MAP.items():
        v = args.get(ours)
        if v not in (None, ""):
            out[theirs] = v
    for key in STCX_PROJECT_KEYS:
        if args.get(key):
            out["project_name"] = str(args[key])
            break
    return out


def _stcx_disabled() -> list[str]:
    """비어서 이 작업을 꺼 놓는 설정 이름들. 비면 **조용히 성공하지 않고** 실패한다."""
    return [name for name, value in (
        ("KOORM_GATEWAY_PAT", settings.gateway_pat),
        ("KOORM_STCX_BACKEND_URL", settings.stcx_backend_url),
        ("KOORM_STCX_WORK_ROOT", settings.stcx_work_root),
        ("KOORM_STCX_LSTC_IP", settings.stcx_lstc_ip),
    ) if not str(value or "").strip()]


async def _submit_external(db, job: Job, work_dir: Path) -> None:
    """stcx 로 **덱을 올린 뒤** 제출하고, 이 잡을 **running 인 채로** 둔다(폴링이 마무리한다).

    ★예전에는 파일을 나르지 않고 이 서버의 절대경로를 넘겼다 — 두 쪽이 같은 경로를 본다는
    전제였는데 사실이 아니다. cae00 `/data` 는 로컬 디스크, stcx `/data` 는 다른 NFS 다.
    """
    args = dict(job.args or {})
    errs = catalog.validate_args(job.operation, args)
    if errs:
        _fail(job, "; ".join(errs))
        await db.commit()
        return

    off = _stcx_disabled()
    if off:
        _fail(job, "stcx 제출이 꺼져 있다 — " + " · ".join(off) + " 가 비었다")
        await db.commit()
        return

    # 경로 탈출 방어 — 이름 성분만 남긴다(업로드 이름은 사용자가 준다).
    name = Path(str(args.get("model") or "")).name
    model_path = work_dir / name
    if not name or not model_path.is_file():
        _fail(job, f"모델 파일을 찾을 수 없다: {args.get('model')!r}")
        await db.commit()
        return

    # 이번 판이 못 보내는 옵션 — **조용히 버리지 않는다.** 화면에서 고른 값이 해석에 아무
    # 영향을 안 주는데 잡은 성공하는 것이 가장 나쁘다(실제로 한 번 그랬다).
    extra = sorted(k for k, v in args.items()
                   if k not in STCX_SUPPORTED and v not in (None, "", [], {}))
    if extra:
        _fail(job, "이번 판에서 stcx 가 받지 않는 옵션이다 — " + " · ".join(extra)
                   + ". 각도 방식·공차·DR·접촉·연속 낙하는 다음 판이다(조용히 버리지 않는다)")
        await db.commit()
        return

    # 받는 쪽은 **모델 파일 하나**만 받는다 — 인클루드가 있으면 반쪽 모델이 올라간다.
    if await asyncio.to_thread(_deck_has_include, model_path):
        _fail(job, "*INCLUDE 가 있는 덱은 아직 stcx 로 못 보낸다 — 받는 쪽은 모델 파일 하나만"
                   " 받는다. `extract-parts` 로 인클루드를 펼쳐 **홀로 서는 덱**을 만들어 올려라")
        await db.commit()
        return

    # ① 반입 — stcx 는 이 서버의 경로를 못 연다.
    uploader = StcxUploader(settings.stcx_backend_url)
    try:
        up = await uploader.upload(model_path, job_id=str(job.id))
    finally:
        await uploader.close()
    if not up.get("ok"):
        _fail(job, f"덱 반입 실패({up.get('error')}): {str(up.get('detail'))[:400]}")
        await db.commit()
        return

    # ② 제출
    tool_args = _stcx_tool_args(args, job=job, model_file_path=up["file_path"])
    client = _stcx()
    try:
        res = await client.submit_fullangle_drop(tool_args, dry_run=False)
        parsed = parse_submit(res.get("result")) if res.get("ok") else {"ok": False}
        if not parsed.get("ok"):
            # ★**다시 제출하지 않는다.** 끊긴 것은 응답뿐이고 제출은 됐을 수 있다. 그리고 더
            #   나쁜 것 — 두 번째 제출은 첫 번째가 `work_dir` 에 둔 **묵은 덱**으로 돈다
            #   (`script.sh:46-52` 가 이미 있는 파일을 그냥 쓴다). 그래서 먼저 찾아본다.
            found = await client.job_status(work_dir=tool_args["work_dir"])
            recovered = registry_id_of(found.get("result")) if found.get("ok") else None
            if recovered in (None, ""):
                why = (f"제출 실패({res.get('error')}): {str(res.get('detail'))[:300]}"
                       if not res.get("ok")
                       else f"제출 응답을 해석하지 못했다({parsed.get('error')}):"
                            f" {str(parsed.get('detail'))[:300]}")
                _fail(job, why)
                await db.commit()
                return
            logger.warning("job %s: 제출 응답은 못 받았지만 레지스트리 %s 를 찾았다 — 재제출하지 않는다",
                           job.id, recovered)
            parsed = {"ok": True, "registry_id": recovered, "job_id": "",
                      "work_dir": tool_args["work_dir"], "output_dir": "",
                      "sphere_report_path": "",
                      "result_dir": result_dir_of(found.get("result")),
                      "detail": "recovered_by_work_dir"}
    finally:
        await client.close()

    delay = _next_poll_delay(None)
    job.external_kind = EXTERNAL_KIND
    job.external_ref = {
        # ⚠ `registry_id` 가 지목용이다. `slurm_job_id` 는 사람이 보는 값일 뿐이다 —
        #   받는 쪽 `job_status` 응답의 `job_id` 는 **레지스트리 행 id** 라 이름이 겹친다.
        "registry_id": parsed["registry_id"],
        "slurm_job_id": parsed.get("job_id") or None,
        "work_dir": parsed.get("work_dir") or tool_args["work_dir"],
        "output_dir": parsed.get("output_dir") or None,
        "sphere_report_path": parsed.get("sphere_report_path") or None,
        "result_dir": parsed.get("result_dir") or None,      # 결과를 가져올 때의 기준
        "model_source": parsed.get("model_source") or None,
        "model_path": str(model_path),
        "uploaded_path": up["file_path"],
        "uploaded_bytes": up.get("bytes"),
        "upload_id": up.get("upload_id") or None,     # 지우기가 실패했을 때 사람이 다시 지울 손잡이
        "submitted": str(parsed.get("detail", ""))[:2000],
        "poll_interval": delay,
    }
    job.external_poll_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    job.progress = 5
    job.resolved_cmd = {"external": EXTERNAL_KIND, "tool": "fullangle_drop_simulation",
                        "work_dir": tool_args["work_dir"],
                        "model_file_path": up["file_path"]}
    await db.commit()
    logger.info("external job %s submitted → registry %s (slurm %s)",
                job.id, parsed["registry_id"], parsed.get("job_id") or "-")
    if parsed.get("model_source") == "existing":
        # `work_dir` 이 잡마다 고유하니 늘 "copied" 여야 한다. existing 이면 받는 쪽이 올린 덱 대신
        # 작업 폴더에 이미 있던 덱으로 돌았다 — 결과가 이 잡의 덱 것이 아닐 수 있다.
        logger.warning("job %s: stcx 가 작업 폴더 %s 에 이미 있던 덱을 썼다(model_source=existing)"
                       " — 올린 덱이 아닐 수 있다", job.id, tool_args["work_dir"])

    # ③ 반입 정리 — 업로드는 잡마다 따로 쌓이는데 잡은 그것을 **다시 보지 않는다.** 받는 쪽
    #   도구가 스테이징으로 복사하고(`prepare_model_workdir`), backend 에는 그 **사본**을
    #   보낸다(`fullangle_drop_simulation/latest/script.sh`). `registry_id` 는 그 뒤에야 생기므로
    #   그것이 있다는 것이 복사가 끝났다는 근거다 — 못 받았으면 위에서 실패로 닫혀 여기 안 온다.
    #   잡을 **먼저 커밋하고** 지운다. 지우기가 걸리거나 실패해도 제출 기록은 남고, 경고뿐이다.
    uploader = StcxUploader(settings.stcx_backend_url)
    try:
        gone = await uploader.delete(str(up.get("upload_id") or ""))
    finally:
        await uploader.close()
    if not gone.get("ok"):
        logger.warning("job %s: stcx 업로드 %s 를 지우지 못했다(%s): %s — 잡에는 영향 없음",
                       job.id, up.get("upload_id") or "-", gone.get("error"),
                       str(gone.get("detail"))[:200])


async def _poll_external_once() -> int:
    """기한이 된 외부 잡의 상태를 한 번씩 본다. 돌본 개수를 돌려준다."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        due = (await db.execute(
            select(Job).where(Job.status == "running",
                              Job.external_kind == EXTERNAL_KIND,
                              Job.external_poll_at.is_not(None),
                              Job.external_poll_at <= now)
            .order_by(Job.external_poll_at).limit(_POLL_BATCH)
        )).scalars().all()
        if not due:
            return 0
        client = _stcx()
        try:
            for job in due:
                ref = dict(job.external_ref or {})
                rid = ref.get("registry_id")
                where = str(ref.get("work_dir") or "")
                # **두 번 부른다.** 끝났는지 판정할 근거(`slurm_job_ids`)가 상태 응답에
                # 없다 — 자세한 이유는 `parse_status` 의 주석에 있다.
                status = await client.job_status(rid, work_dir=where)
                details = await client.job_details(rid, work_dir=where)
                if not status.get("ok") or not details.get("ok"):
                    verdict = {
                        "state": "unknown",
                        "reason": status.get("error") or details.get("error") or "call_failed",
                        "raw": str(status.get("detail") or details.get("detail") or "")[:500],
                    }
                else:
                    verdict = parse_status(status["result"], details["result"])
                state = verdict["state"]
                if state == "succeeded":
                    job.status, job.progress = "succeeded", 100
                    job.finished_at = now
                elif state == "failed":
                    job.status = "failed"
                    job.error_summary = (f"클러스터 잡 {rid} 실패 — slurm 상태"
                                         f" {verdict.get('slurm')}")
                    job.finished_at = now
                else:
                    # **모르면 접지 않는다.** 도구가 고장 난 것과 잡이 끝난 것을 같은 모양으로
                    # 만들지 않는다 — 다음에 다시 본다. 대신 왜 몰랐는지는 남겨 화면에 뜨게 한다.
                    ref["last_unknown"] = verdict.get("reason") or "unparsed"
                    ref["unknown_count"] = int(ref.get("unknown_count") or 0) + (
                        1 if state == "unknown" else 0)
                delay = _next_poll_delay(ref.get("poll_interval"))
                ref["poll_interval"] = delay
                ref["last_state"] = state
                # 요청서 §4 — 종료 판정을 고치려면 **실제 응답**이 필요하다. 매번 남긴다.
                ref["last_raw"] = verdict.get("raw") or ""
                job.external_ref = ref
                job.external_poll_at = (None if job.status != "running"
                                        else now + timedelta(seconds=delay))
        finally:
            await client.close()
        await db.commit()
        return len(due)


async def _register_file(
    db, session, name: str, fpath: Path, *, kind: str, job_id: str, inspect: bool = True
) -> int:
    """세션 디렉터리의 파일 하나를 session_files 에 등록(있으면 갱신)하고 id 를 돌려준다.

    산출물 등록과 설정 파일 등록이 같은 일을 하므로 한 자리로 모은다.
    `inspect=False` 는 K파일이 아닌 것(config.yaml 등)용 — `info` 를 돌려 봐야 실패만 한다.
    """
    # Offload hashing + the `info` subprocess off the event loop so registration
    # doesn't stall the API (worker shares the loop).
    sha = await asyncio.to_thread(storage.sha256_of, fpath)
    meta = await asyncio.to_thread(inspect_kfile, fpath) if inspect else None
    existing = (
        await db.execute(
            select(SessionFile).where(
                SessionFile.session_id == session.id,
                SessionFile.filename == name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.kind = kind
        existing.origin_job_id = job_id
        existing.size_bytes = fpath.stat().st_size
        existing.sha256 = sha
        if meta is not None:
            existing.meta = meta
        await db.flush()
        return existing.id
    row = SessionFile(
        session_id=session.id,
        filename=name,  # may include a subdir (posix) for nested files
        rel_path=f"{session.storage_path}/{name}",
        kind=kind,
        origin_job_id=job_id,
        size_bytes=fpath.stat().st_size,
        sha256=sha,
        meta=meta,
    )
    db.add(row)
    await db.flush()
    return row.id


async def _execute(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(Job, job_id)
        if job is None:
            return
        session = await db.get(Session, job.session_id)
        if session is None:
            job.status = "failed"
            job.error_summary = "session not found"
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return

        work_dir = storage.ensure_session_dir(session.user_id, session.id)

        # 후처리 예약도 외부 잡이지만 stcx 제출이 아니다 — 귀환 매니페스트를 기다릴 뿐이다.
        # (그쪽 모듈이 이 모듈을 가져다 쓰므로 순환을 피해 여기서 들인다.)
        if job.operation == "postprocess":
            from app.worker import postprocess_return
            await postprocess_return.start(db, job)
            return

        # 외부 작업은 여기서 갈라 나간다 — 로컬 바이너리를 부르지 않는다.
        if _is_external(job.operation):
            await _submit_external(db, job, work_dir)
            return

        # 레시피 실행도 바이너리가 아니다 — 격리 샌드박스에서 파이썬 함수를 돌린다.
        # execute_run 이 RecipeRun 과 Job 상태를 모두 적는다(여기선 바로 반환).
        if job.operation == "recipe":
            from app.modules.recipes import services as recipe_svc
            await recipe_svc.execute_run(db, job)
            return

        built = build_command(job.operation, job.args or {}, work_dir)
        if built.error:
            job.status = "failed"
            job.error_summary = built.error
            job.resolved_cmd = {"error": built.error}
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return

        job.resolved_cmd = {"argv": built.argv, "written_files": list(built.written_files)}
        out_path = work_dir / f".job_{job_id}.out"
        err_path = work_dir / f".job_{job_id}.err"
        job.stdout_path = str(out_path)
        job.stderr_path = str(err_path)
        # 행이 사라져도 크래시를 적을 자리를 알아야 한다(`_err_paths` 주석 참조).
        _err_paths[job_id] = str(err_path)
        job.env_snapshot = _env_snapshot()
        await db.commit()

        # 플랫폼이 만든 설정 파일(config.yaml 등)을 **파일 목록에 올린다.**
        # ⚠ 아래 스냅샷에 맡기면 안 된다 — build_command 가 이미 썼으므로 `before` 에 들어가
        # '새 파일'로 안 잡힌다. 그래서 디스크에는 있는데 목록·다운로드에는 영영 안 보였다.
        # kind 는 output 이 아니라 **generated** 다. 바이너리의 산출물이 아니라 플랫폼이 만든 입력이다.
        # (내용은 jobs.args 로도 복원되지만, 실제로 무엇이 실행됐는지는 이 파일이 정본이다.)
        for wname in built.written_files:
            wpath = work_dir / wname
            if not wpath.is_file():
                continue
            await _register_file(
                db, session, wname, wpath, kind="generated", job_id=job_id, inspect=False
            )
        await db.commit()

        # snapshot existing files (name -> mtime) to detect outputs (recursive —
        # some ops write into subdirs; paths are relative to the session dir). We
        # track mtime so an op that OVERWRITES an existing file (same name) is
        # still detected as an output, not silently missed.
        def _snap() -> dict[str, float]:
            return {
                p.relative_to(work_dir).as_posix(): p.stat().st_mtime
                for p in work_dir.rglob("*")
                if p.is_file()
            }

        before = _snap()

        # 개행 왕복 대조용 — 이 잡이 **덮어쓰기 전** 메타다. 디스크는 곧 바뀌지만 DB 행은
        # `_register_file` 이 갱신하기 전까지 옛 값을 들고 있으므로, 여기서 떠 두면 된다.
        nl_before = {
            f.filename: (f.meta or {})
            for f in (
                await db.execute(
                    select(SessionFile).where(SessionFile.session_id == session.id)
                )
            ).scalars()
        }

        try:
            exit_code = await asyncio.to_thread(
                _run_blocking, job_id, built.argv, work_dir, out_path, err_path
            )
        except FileNotFoundError as exc:
            job.status = "failed"
            job.error_summary = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return

        canceled = job_id in _CANCELED
        _CANCELED.discard(job_id)

        # job 이 실제로 돈 노드(실행기가 남긴 한 줄). `nodename`(API 노드)은 그대로 둔다 — 같은 칸이 잡마다
        # 다른 뜻이 되지 않게 칸을 더한다(HWAX 답신 ③ 안 A). JSONB 는 새 dict 로 바꿔 넣어야 저장된다.
        snap = dict(job.env_snapshot or {})
        snap["host"] = {**(snap.get("host") or {}), "job_node": _job_node(work_dir, job_id)}
        job.env_snapshot = snap

        # register outputs: files that are new OR whose mtime advanced (overwritten
        # by this run). For an overwritten file, update the existing row instead of
        # inserting a duplicate.
        after = _snap()
        changed = sorted(
            n for n, mt in after.items()
            if n not in before or mt > before[n]
        )
        output_ids: list[int] = []
        for name in changed:
            base = name.rsplit("/", 1)[-1]
            if base.startswith(".job_"):  # our log files
                continue
            # NFS 는 열린 채로 지운 파일을 `.nfs<16진수>` 로 남겼다가 닫힐 때 지운다 — 곧 사라질 그 파일을
            # 산출로 올리지 않는다(HWAX 답신 ② 덧붙임, 10-23 결정).
            if base.startswith(".nfs"):
                continue
            fid = await _register_file(
                db, session, name, work_dir / name, kind="output", job_id=job_id
            )
            output_ids.append(fid)

        # 덱이 왕복에서 개행을 잃었나 — rc=0 인데 산출물이 상한 경우를 화면에 올린다(P1-8).
        # ⚠ 판정(`newline`) 대조만으로는 **섞인 덱**을 놓친다. `newline_audit` 가 그 규칙까지 본다.
        if output_ids:
            nl_after = {
                f.filename: (f.meta or {})
                for f in (
                    await db.execute(select(SessionFile).where(SessionFile.id.in_(output_ids)))
                ).scalars()
            }
            nl_warns = audit_newlines(nl_before, nl_after)
            if nl_warns:
                # ⚠ **이어 붙인다.** 덮어쓰면 제출 시점에 붙은 경고(미정의 참조 — 라우트에서
                # 넣는다)가 사라진다. 경고는 축마다 쌓이는 것이고 마지막 것만 남을 이유가 없다.
                job.warnings = (job.warnings or []) + nl_warns

        job.exit_code = exit_code
        job.output_file_ids = output_ids
        job.finished_at = datetime.now(timezone.utc)
        if canceled:
            job.status = "canceled"
        elif exit_code == 0:
            job.status = "succeeded"
            job.progress = 100
        else:
            job.status = "failed"
            try:
                tail = err_path.read_text()[-800:]
            except OSError:
                tail = ""
            if not tail.strip():
                # KooRemapper 는 [ERROR] 를 stdout 으로 찍는다 — stderr 가 비면 요약이 'exit 1:' 뿐이었다
                try:
                    out_lines = out_path.read_text(errors="replace").splitlines()
                except OSError:
                    out_lines = []
                errs = [ln for ln in out_lines if "[ERROR]" in ln]
                tail = "\n".join((errs or out_lines)[-5:])[-800:]
            job.error_summary = f"exit {exit_code}: {tail}".strip()
        await db.commit()
        logger.info("job %s %s (exit=%s, %d outputs)", job_id, job.status, exit_code, len(output_ids))


_CANCELED: set[str] = set()


def request_cancel(job_id: str) -> bool:
    """Mark a running job for cancellation and stop its process if active.
    SIGTERM first, then SIGKILL after a short grace period (binary may ignore TERM)."""
    _CANCELED.add(job_id)
    proc = _running.get(job_id)
    if proc is not None:
        _kill_proc_group(proc, signal.SIGTERM)

        def _kill_if_alive():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _kill_proc_group(proc, signal.SIGKILL)

        threading.Thread(target=_kill_if_alive, daemon=True).start()
        return True
    return False  # queued (not yet running) — worker will see _CANCELED


# 실행기 정리 하위 명령(`--reap <id>`) 하나를 기다리는 상한. 계약은 10초 안에 끝나는 것이다(L10).
_REAP_TIMEOUT_SEC = 15


def _reap(job_id: str) -> None:
    """실행기에게 이 잡의 원격 프로세스를 끝내게 한다. 실패해도 회수는 진행한다 — 까닭만 로그에 남긴다."""
    cmd = [*shlex.split(settings.job_launcher), "--reap", job_id]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=_REAP_TIMEOUT_SEC, env=_launcher_env())
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("job %s: 실행기 --reap 실패(%s) — 그대로 회수한다",
                       job_id, type(exc).__name__)
        return
    if r.returncode != 0:
        logger.warning("job %s: 실행기 --reap rc=%s — 그대로 회수한다 | %s",
                       job_id, r.returncode, (r.stderr or "").strip()[-300:])


async def reconcile_orphans() -> None:
    """On startup, fail any job left 'running' by a previous (crashed/restarted)
    worker — its subprocess is gone, so it can never complete.

    실행기를 쓰면 **행을 닫기 전에** 잡마다 `<실행기> --reap <id>` 를 부른다. 원격 job 은 API 와 함께 죽지
    않는다 — 행부터 닫으면 같은 세션의 다음 잡이 아직 끝나는 중인 원격 job 과 같은 폴더에서 겹친다.
    (로컬 바이너리도 새 세션이라 API 가 갑자기 죽으면 남는다 — 같은 틈이지만 이번 범위 밖이다.)

    ⚠ 외부 잡(`external_kind IS NOT NULL`)은 **제외한다.** 그것은 이 워커의 자식이
    아니라 다른 클러스터에서 도는 것이라, 워커가 죽었다는 사실과 잡의 생사가 무관하다.
    빼지 않으면 API 재기동 한 번에 4시간짜리 stcx 잡이 화면에서 failed 로 사라지고,
    정작 클러스터에서는 멀쩡히 계속 돈다 — 가장 나쁜 종류의 거짓말이다."""
    if settings.job_launcher:
        async with SessionLocal() as db:
            ids = list((await db.execute(text(
                "SELECT id FROM jobs WHERE status='running' AND external_kind IS NULL"
            ))).scalars())
        if ids:
            # 한꺼번에 부른다 — 하나씩이면 고아 8개에 최대 80초 동안 큐가 선다.
            await asyncio.gather(*(asyncio.to_thread(_reap, jid) for jid in ids))
    async with SessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE jobs SET status='failed', "
                "error_summary='worker restarted while job was running', "
                "finished_at=now() WHERE status='running' AND external_kind IS NULL"
            )
        )
        await db.commit()
        if result.rowcount:
            logger.warning("reconciled %d orphaned running job(s) → failed", result.rowcount)


async def _loop() -> None:
    sem = asyncio.Semaphore(settings.worker_concurrency)
    tasks: set[asyncio.Task] = set()
    await reconcile_orphans()
    logger.info("worker loop started (concurrency=%d)", settings.worker_concurrency)
    # 외부 잡 스캔은 **시간 기준**이다. "할 일이 없을 때만" 으로 하면 로컬 큐가 바쁜 동안
    # 외부 잡이 영영 마무리되지 않는다(기다리는 쪽은 그게 제일 답답하다).
    next_scan = 0.0
    # 기준정보 수신도 **시간 기준**이다(외부 잡 스캔과 같은 자리·같은 모양). 끄면 아예 안 돈다.
    # 첫 틱을 0 으로 두지 않는 이유 — 기동 직후에 바깥을 두드리면 기동 실패와 수신 실패가
    # 같은 순간에 섞여 로그에서 갈라지지 않는다.
    next_plm = asyncio.get_running_loop().time() + 30.0
    while not _stop.is_set():
        loop_now = asyncio.get_running_loop().time()
        if loop_now >= next_scan:
            next_scan = loop_now + max(5, settings.stcx_poll_min_sec // 2)
            try:
                await _poll_external_once()
            except Exception:       # 폴링 실패가 워커를 멈추면 로컬 잡까지 선다
                logger.exception("external job poll failed")
            # 후처리 예약은 따로 본다 — 한쪽이 깨져도 다른 쪽은 돈다(실패 영역을 가른다).
            try:
                from app.worker import postprocess_return
                await postprocess_return.poll_due()
            except Exception:
                logger.exception("postprocess reservation poll failed")

        if plm_sync.enabled() and loop_now >= next_plm:
            next_plm = loop_now + max(60, settings.sp_core_sync_sec)
            try:
                # 시간마다 증분 + 주 1회 처음부터(사용자 결정 10-30 — 지시서 기본안)
                await plm_sync.sync_once(full=await plm_sync.full_due())
            except Exception:       # 수신 실패가 워커를 멈추면 로컬 잡까지 선다
                logger.exception("plm sync poll failed")

        async with SessionLocal() as db:
            job_id = await _claim_one(db)
        if job_id is None:
            await asyncio.sleep(1.0)
            continue
        # honor cancel requested while queued
        if job_id in _CANCELED:
            async with SessionLocal() as db:
                j = await db.get(Job, job_id)
                if j:
                    j.status = "canceled"
                    j.finished_at = datetime.now(timezone.utc)
                    await db.commit()
            _CANCELED.discard(job_id)
            continue

        await sem.acquire()

        async def _wrapped(jid=job_id):
            # 이 잡 구간의 모든 로그 줄에 **잡 id** 를 붙인다. 그러면 잡 기록과 로그 줄이 같은
            # 문자열로 만나고, 번들이 "이 잡의 서버 줄" 만 골라낼 수 있다.
            token = set_correlator(jid)
            try:
                await _execute(jid)
            except Exception as exc:
                logger.exception("job %s crashed", jid)
                # ⚠ **DB 에만 쓰려 하면 안 된다.** 잡 행은 도는 중에 사라질 수 있고(세션 삭제 +
                # ON DELETE CASCADE) 그러면 아래 복구가 None 을 받아 아무것도 남기지 못한다.
                # 실측 — 그렇게 사라진 잡 4건이 로그에만 있고 DB 에는 없었으며
                # `error_summary='worker exception'` 인 잡은 **0건**이었다(복구가 한 번도 성공한
                # 적이 없다). 그래서 파일에 **먼저** 적는다.
                noted = _note_crash(jid, exc)
                async with SessionLocal() as db:
                    j = await db.get(Job, jid)
                    if j is None:
                        # 행이 없다는 사실 자체가 진단이다 — 조용히 넘기지 않는다.
                        # ⚠ 파일에 남겼다고 **단정하지 않는다.** 세션 폴더가 지워졌으면 못 남긴다.
                        logger.error(
                            "job %s crashed and its row is gone — %s",
                            jid,
                            ("진단을 %s 에도 남겼다" % _err_paths.get(jid)) if noted
                            else "세션 폴더까지 지워져 파일에는 못 남겼다 — 위 crash 로그가 정본이다",
                        )
                    elif j.status == "running":
                        j.status = "failed"
                        j.error_summary = (
                            "worker exception: %s: %s" % (type(exc).__name__, exc)
                        )[:2000]
                        j.finished_at = datetime.now(timezone.utc)
                        await db.commit()
            finally:
                reset_correlator(token)
                _err_paths.pop(jid, None)
                sem.release()

        t = asyncio.create_task(_wrapped())
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


_worker_task: asyncio.Task | None = None


def start_worker() -> None:
    global _worker_task
    _stop.clear()
    _worker_task = asyncio.create_task(_loop())


# 종료 때 실행기에 SIGTERM 을 보내고 SIGKILL 까지 기다리는 초. lifespan 이 stop_worker 를 3.5초(main.py),
# uvicorn 이 5초(api.def)에 끊으므로 그 안에 든다.
_STOP_TERM_GRACE_SEC = 2.0


async def stop_worker() -> None:
    _stop.set()
    if settings.job_launcher:
        # 시간 초과와 같은 까닭으로 TERM 먼저다 — 종료 때도 `_execute` 가 이어서 출력 목록을 뜬다.
        for proc in list(_running.values()):
            _kill_proc_group(proc, signal.SIGTERM)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _STOP_TERM_GRACE_SEC
        while _running and loop.time() < deadline:
            await asyncio.sleep(0.05)
    # Kill any in-flight subprocess groups so a shutdown/restart doesn't leave
    # orphaned binaries running (and mutating session dirs).
    for proc in list(_running.values()):
        _kill_proc_group(proc, signal.SIGKILL)
    if _worker_task is not None:
        await _worker_task
