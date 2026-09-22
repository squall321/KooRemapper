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

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Session, SessionFile
from app.runner import catalog
from app.runner.argbuild import build_command
from app.runner.kfile_inspect import inspect_kfile
from app.runner.stcx_client import (StcxClient, build_scenario_overrides, parse_state,
                                    parse_submit)
from app.shared import storage

logger = logging.getLogger("koorm.worker")

# 외부 잡 표식. Job.external_kind 에 들어가고, 고아 회수·세션 직렬화가 이 값으로 갈린다.
EXTERNAL_KIND = "stcx_mcp"
# 한 번의 폴링 스캔에서 볼 잡 수. 많이 잡으면 게이트웨이를 한꺼번에 두드린다.
_POLL_BATCH = 20

# job_id -> Popen, for cancellation
_running: dict[str, subprocess.Popen] = {}
_stop = asyncio.Event()


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
            fpath = work_dir / name
            # Offload hashing + the `info` subprocess off the event loop so output
            # registration doesn't stall the API (worker shares the loop).
            sha = await asyncio.to_thread(storage.sha256_of, fpath)
            meta = await asyncio.to_thread(inspect_kfile, fpath)
            existing = (
                await db.execute(
                    select(SessionFile).where(
                        SessionFile.session_id == session.id,
                        SessionFile.filename == name,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.kind = "output"
                existing.origin_job_id = job_id
                existing.size_bytes = fpath.stat().st_size
                existing.sha256 = sha
                existing.meta = meta
                await db.flush()
                output_ids.append(existing.id)
            else:
                row = SessionFile(
                    session_id=session.id,
                    filename=name,  # may include a subdir (posix) for nested outputs
                    rel_path=f"{session.storage_path}/{name}",
                    kind="output",
                    origin_job_id=job_id,
                    size_bytes=fpath.stat().st_size,
                    sha256=sha,
                    meta=meta,
                )
                db.add(row)
                await db.flush()
                output_ids.append(row.id)

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
            try:
                await _execute(jid)
            except Exception:
                logger.exception("job %s crashed", jid)
                async with SessionLocal() as db:
                    j = await db.get(Job, jid)
                    if j and j.status == "running":
                        j.status = "failed"
                        j.error_summary = "worker exception"
                        j.finished_at = datetime.now(timezone.utc)
                        await db.commit()
            finally:
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
