"""Subprocess wrapper around the KooRemapper binary.

Used by the k-file inspector (Phase 3) and the job runner (Phase 5). Runs the
binary with a working directory and timeout, capturing stdout/stderr.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_kooremapper(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> RunResult:
    """Run `KooRemapper <args...>`. Returns captured output (never raises on
    non-zero exit; raises FileNotFoundError only if the binary is missing)."""
    binary = settings.kooremapper_bin
    if not binary.exists():
        raise FileNotFoundError(f"KooRemapper binary not found: {binary}")
    cmd = [str(binary), *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout or settings.job_timeout_sec,
        )
        return RunResult(proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            exit_code=124,
            stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
            + "\n[timeout exceeded]",
            timed_out=True,
        )
