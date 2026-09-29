"""Async job worker — claims queued jobs and runs the KooRemapper binary.

Runs as a background asyncio task inside the API process (started in lifespan).
Concurrency is bounded by settings.worker_concurrency. Each job:
  1. atomic-claim (status queued→running)
  2. argbuild → argv + any written config.yaml
  3. snapshot session dir, run binary (cwd=session dir), capture stdout/stderr to files
  4. register NEW files as session_files(kind=output, origin_job_id)
  5. status → succeeded|failed|canceled, exit_code, output_file_ids, error_summary
"""
from __future__ import annotations

import asyncio
import logging
import os
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
from app.runner.stcx_client import (StcxClient, build_scenario_overrides, parse_state,
                                    parse_submit)
from app.shared import storage
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
    }


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


def _run_blocking(job_id: str, argv: list[str], cwd: Path, out_path: Path, err_path: Path) -> int:
    """Run the binary synchronously (called via asyncio.to_thread)."""
    cmd = [str(settings.kooremapper_bin), *argv]
    with out_path.open("w") as out, err_path.open("w") as err:
        # start_new_session=True → the binary leads its own process group, so a
        # timeout/cancel can kill the whole group (incl. gmsh grandchildren).
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=out, stderr=err, text=True, start_new_session=True
        )
        _running[job_id] = proc
        try:
            return proc.wait(timeout=settings.job_timeout_sec)
        except subprocess.TimeoutExpired:
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


async def _submit_external(db, job: Job, work_dir: Path) -> None:
    """다른 클러스터에 제출하고, 이 잡을 **running 인 채로** 둔다(폴링이 마무리한다).

    파일을 나르지 않는다 — 세션 디렉터리의 절대경로를 그대로 넘긴다. 경로 값은
    박스마다 다르므로 코드에 박지 않는다.
    """
    args = dict(job.args or {})
    errs = catalog.validate_args(job.operation, args)
    if errs:
        _fail(job, "; ".join(errs))
        await db.commit()
        return

    # 경로 탈출 방어 — 이름 성분만 남긴다(업로드 이름은 사용자가 준다).
    name = Path(str(args.get("model") or "")).name
    model_path = work_dir / name
    if not name or not model_path.is_file():
        _fail(job, f"모델 파일을 찾을 수 없다: {args.get('model')!r}")
        await db.commit()
        return

    # 각도 목록 파일도 **나르지 않는다** — 세션 경로를 그대로 넘긴다(모델과 같은 규칙).
    case_txt_path = ""
    if args.get("case_txt"):
        cname = Path(str(args["case_txt"])).name
        cpath = work_dir / cname
        if not cname or not cpath.is_file():
            _fail(job, f"각도 파일을 찾을 수 없다: {args.get('case_txt')!r}")
            await db.commit()
            return
        case_txt_path = str(cpath)

    try:
        overrides = build_scenario_overrides(args, has_case_txt=bool(case_txt_path))
    except ValueError as exc:
        # 고를 수 없는 것을 골라 주지 않는다 — 여기서 막아야 몇 시간 뒤가 아니라 지금 안다.
        _fail(job, str(exc))
        await db.commit()
        return

    client = _stcx()
    try:
        res = await client.submit_fullangle_drop(
            model_path=str(model_path),
            job_name=str(args.get("job_name") or ""),
            angle_preset=str(args.get("angle_preset") or ""),
            case_txt_path=case_txt_path,
            scenario_overrides=overrides or None,
            memory=str(args.get("memory") or ""),
            time_limit=str(args.get("time_limit") or ""),
            dry_run=False,
        )
    finally:
        await client.close()

    if not res.get("ok"):
        _fail(job, f"제출 실패({res.get('error')}): {str(res.get('detail'))[:400]}")
        await db.commit()
        return

    parsed = parse_submit(res.get("result"))
    if not parsed.get("ok"):
        # 응답을 못 읽었으면 **제출된 것으로 치지 않는다** — 없는 잡을 영영 폴링하게 된다.
        _fail(job, f"제출 응답을 해석하지 못했다({parsed.get('error')}): {str(parsed.get('detail'))[:400]}")
        await db.commit()
        return

    delay = _next_poll_delay(None)
    job.external_kind = EXTERNAL_KIND
    job.external_ref = {
        "job_id": parsed["job_id"],
        "model_path": str(model_path),
        "case_txt_path": case_txt_path or None,
        "scenario_overrides": overrides or None,
        "submitted": parsed.get("detail", "")[:2000],
        "poll_interval": delay,
    }
    job.external_poll_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    job.progress = 5
    job.resolved_cmd = {"external": EXTERNAL_KIND, "tool": "smarttwin_submit",
                        "model_path": str(model_path)}
    await db.commit()
    logger.info("external job %s submitted → cluster job %s", job.id, parsed["job_id"])


async def _poll_external_once() -> int:
    """기한이 된 외부 잡의 상태를 한 번씩 본다. 돌본 개수를 돌려준다."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        due = (await db.execute(
            select(Job).where(Job.status == "running",
                              Job.external_kind.is_not(None),
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
                res = await client.job_results(str(ref.get("job_id") or ""))
                verdict = (parse_state(res.get("result")) if res.get("ok")
                           else {"state": "unknown", "reason": res.get("error"),
                                 "raw": str(res.get("detail"))[:500]})
                state = verdict["state"]
                if state == "succeeded":
                    job.status, job.progress = "succeeded", 100
                    job.finished_at = now
                elif state == "failed":
                    job.status = "failed"
                    job.error_summary = f"클러스터 잡 {ref.get('job_id')} 상태 {verdict.get('slurm')}"
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

        # 외부 작업은 여기서 갈라 나간다 — 로컬 바이너리를 부르지 않는다.
        if _is_external(job.operation):
            await _submit_external(db, job, work_dir)
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


async def reconcile_orphans() -> None:
    """On startup, fail any job left 'running' by a previous (crashed/restarted)
    worker — its subprocess is gone, so it can never complete.

    ⚠ 외부 잡(`external_kind IS NOT NULL`)은 **제외한다.** 그것은 이 워커의 자식이
    아니라 다른 클러스터에서 도는 것이라, 워커가 죽었다는 사실과 잡의 생사가 무관하다.
    빼지 않으면 API 재기동 한 번에 4시간짜리 stcx 잡이 화면에서 failed 로 사라지고,
    정작 클러스터에서는 멀쩡히 계속 돈다 — 가장 나쁜 종류의 거짓말이다."""
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
    while not _stop.is_set():
        loop_now = asyncio.get_running_loop().time()
        if loop_now >= next_scan:
            next_scan = loop_now + max(5, settings.stcx_poll_min_sec // 2)
            try:
                await _poll_external_once()
            except Exception:       # 폴링 실패가 워커를 멈추면 로컬 잡까지 선다
                logger.exception("external job poll failed")

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


async def stop_worker() -> None:
    _stop.set()
    # Kill any in-flight subprocess groups so a shutdown/restart doesn't leave
    # orphaned binaries running (and mutating session dirs).
    for proc in list(_running.values()):
        _kill_proc_group(proc, signal.SIGKILL)
    if _worker_task is not None:
        await _worker_task
