# 레시피 샌드박스 부모 실행기 — 최소 환경·프로세스 그룹·벽시계 상한으로 자식을 띄우고 결과를 받는다.
"""Spawn :mod:`app.recipes.sandbox_main` as an isolated child and collect its
result envelope.

The parent's only job is isolation plumbing the child can't do for itself:
  * a minimal environment with NO secrets (no DB url, JWT, gateway token) and
    BLAS threads pinned to 1;
  * a result passed back over an inherited fd (writable even under Landlock,
    which governs ``open`` not ``write``), with stdout/stderr to capped files;
  * a wall-clock timeout that kills the whole process group.

Everything inside the child (rlimits, Landlock, seccomp, audit hook, restricted
builtins) is set up by sandbox_main. See the plan/notes under
docs/01-plan/features/recipes-1026.*.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

_SANDBOX_MAIN = str(Path(__file__).with_name("sandbox_main.py"))


@dataclass
class SandboxResult:
    ok: bool
    error: str | None = None
    result: dict | None = None
    tests_passed: list[str] = field(default_factory=list)
    layers: dict = field(default_factory=dict)
    stdout_tail: str = ""
    elapsed_ms: int | None = None
    timed_out: bool = False
    returncode: int | None = None


def _minimal_env(result_fd: int, bundle_dir: str) -> dict[str, str]:
    """비밀 없는 최소 환경. BLAS 스레드 1(NPROC=0 뒤 스레드풀을 못 만든다 · 재현성)."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": bundle_dir,                 # 실제 홈 대신 읽기 전용 번들 — 라이브러리가 홈을 뒤지지 않게
        "TMPDIR": bundle_dir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OPENBLAS_MAIN_FREE": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "RECIPE_RESULT_FD": str(result_fd),
    }


async def run_in_sandbox(
    *,
    code: str,
    mode: str = "selftest",
    report_dirs: list[str] | None = None,
    params: dict | None = None,
    timeout_sec: int | None = None,
    mem_mb: int | None = None,
    fsize_mb: int | None = None,
) -> SandboxResult:
    """격리된 자식에서 레시피를 돌린다. mode='selftest' → test_* 전부, 'run' → run(reports, params).

    report_dirs 는 이미 만들어진 리포트 번들 디렉터리들(meta.json·cases.json·필요 시 data.json)이다.
    selftest 는 리포트가 없어도 된다(시험은 make_report 로 리포트를 만든다).
    """
    report_dirs = report_dirs or []
    mem_mb = mem_mb or settings.recipe_sandbox_mem_mb
    fsize_mb = fsize_mb or settings.recipe_sandbox_fsize_mb
    timeout_sec = timeout_sec or (
        settings.recipe_run_timeout_sec if mode == "run" else settings.recipe_selftest_timeout_sec
    )

    work = Path(tempfile.mkdtemp(prefix="recipe_sbx_"))
    bundle = work / "bundle"
    bundle.mkdir()
    # 리포트 번들을 읽기 뿌리(bundle) 아래로 모은다 — 자식은 여기만 읽는다.
    staged_dirs: list[str] = []
    for i, rd in enumerate(report_dirs):
        dst = bundle / f"r{i}"
        shutil.copytree(rd, dst)
        staged_dirs.append(str(dst))

    spec = {
        "mode": mode,
        "code": code,
        "bundle_dir": str(bundle),
        "report_dirs": staged_dirs,
        "params": params or {},
        "limits": {"mem_mb": mem_mb, "fsize_mb": fsize_mb, "cpu_sec": timeout_sec},
    }
    spec_path = work / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    out_path = work / "stdout.txt"
    res_path = work / "result.json"
    t0 = time.time()
    res_fd = os.open(res_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    out_f = open(out_path, "wb")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-B", _SANDBOX_MAIN, str(spec_path),
            stdin=asyncio.subprocess.DEVNULL, stdout=out_f, stderr=asyncio.subprocess.STDOUT,
            cwd=str(bundle), env=_minimal_env(res_fd, str(bundle)),
            pass_fds=(res_fd,), start_new_session=True,
        )
    finally:
        os.close(res_fd)
        out_f.close()

    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_sec + 3)
    except asyncio.TimeoutError:
        timed_out = True
        _kill_group(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

    elapsed = int((time.time() - t0) * 1000)
    stdout_tail = _tail(out_path, settings.recipe_stdout_cap_kb * 1024)
    payload = _read_result(res_path)
    shutil.rmtree(work, ignore_errors=True)

    if timed_out:
        return SandboxResult(ok=False, error=f"벽시계 상한({timeout_sec}초) 초과",
                             stdout_tail=stdout_tail, elapsed_ms=elapsed, timed_out=True,
                             returncode=proc.returncode)
    if payload is None:
        why = _signal_reason(proc.returncode) or "결과를 내지 못했다(샌드박스가 비정상 종료)"
        return SandboxResult(ok=False, error=why, stdout_tail=stdout_tail,
                             elapsed_ms=elapsed, returncode=proc.returncode)
    return SandboxResult(
        ok=bool(payload.get("ok")),
        error=payload.get("error"),
        result=payload.get("result"),
        tests_passed=payload.get("tests_passed") or [],
        layers=payload.get("layers") or {},
        stdout_tail=stdout_tail,
        elapsed_ms=payload.get("elapsed_ms", elapsed),
        returncode=proc.returncode,
    )


def _kill_group(proc) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def _tail(path: Path, cap: int) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > cap:
        data = b"...(truncated)...\n" + data[-cap:]
    return data.decode("utf-8", errors="replace")


def _read_result(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _signal_reason(rc: int | None) -> str | None:
    if rc is None or rc >= 0:
        return None
    sig = -rc
    names = {
        signal.SIGKILL: "메모리/시간 상한으로 강제 종료(SIGKILL)",
        signal.SIGXCPU: "CPU 시간 상한 초과(SIGXCPU)",
        signal.SIGXFSZ: "출력 파일 크기 상한 초과(SIGXFSZ)",
        signal.SIGSEGV: "세그폴트(SIGSEGV)",
        signal.SIGSYS: "허용되지 않은 시스템콜(seccomp SIGSYS)",
    }
    return names.get(sig, f"시그널 {sig} 로 종료")
