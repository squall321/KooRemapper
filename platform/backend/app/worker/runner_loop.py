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
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Session, SessionFile
from app.runner.argbuild import build_command
from app.runner.kfile_inspect import inspect_kfile
from app.shared import storage

logger = logging.getLogger("koorm.worker")

# job_id -> Popen, for cancellation
_running: dict[str, subprocess.Popen] = {}
_stop = asyncio.Event()


async def _claim_one(db) -> str | None:
    """Atomically claim the oldest queued job whose session has no running job.

    Jobs in the SAME session are serialized: they share one work_dir, so running
    two concurrently would let one overwrite the other's config.yaml and mis-
    attribute outputs. Different sessions still run concurrently (up to the
    worker concurrency)."""
    row = (
        await db.execute(
            text(
                "UPDATE jobs SET status='running', started_at=now() "
                "WHERE id = (SELECT id FROM jobs q WHERE q.status='queued' "
                "AND NOT EXISTS (SELECT 1 FROM jobs r WHERE r.status='running' "
                "AND r.session_id = q.session_id) "
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
    worker — its subprocess is gone, so it can never complete."""
    async with SessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE jobs SET status='failed', "
                "error_summary='worker restarted while job was running', "
                "finished_at=now() WHERE status='running'"
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
    while not _stop.is_set():
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
