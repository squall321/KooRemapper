# KooRemapper 플랫폼 REST API를 감싸는 동기/비동기 Python 클라이언트.
"""KooRemapper Python client — sync + async wrappers over the platform REST API.

Same surface as the web UI and the MCP server (sessions, file upload/inspect,
operation catalog, async jobs, downloads). Authenticate with a kr_ personal
access token (issued from the web dashboard → "MCP 토큰").

    from kooremapper import KooRemapper
    kr = KooRemapper("http://127.0.0.1:8700", token="kr_...")
    s = kr.create_session("warpage")
    kr.upload(s.id, "flat.k"); kr.upload(s.id, "bent.k")
    job = kr.run(s.id, "map", {"bent_mesh": "bent.k", "flat_mesh": "flat.k",
                               "output": "out.k", "single": True})
    kr.wait(job.id)                 # poll until the job finishes
    kr.download(s.id, "out.k", "./out.k")

Async mirror (same methods, awaited):

    async with AsyncKooRemapper(token="kr_...") as kr:
        s = await kr.create_session("warpage")
        job = await kr.run(s.id, "map", {...})
        await kr.wait(job.id)

base_url / token fall back to env KOOREMAPPER_API_BASE / KOOREMAPPER_TOKEN.
Responses are returned as attribute-accessible objects (s.id, job.status, ...).
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import httpx

__all__ = ["KooRemapper", "AsyncKooRemapper", "KooRemapperError"]

_DEFAULT_BASE = "http://127.0.0.1:8700"
_FINAL_STATES = ("succeeded", "failed", "canceled", "cancelled")


class KooRemapperError(RuntimeError):
    """Raised when the platform returns an error response."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _box(x):
    """Wrap dicts/lists so responses are attribute-accessible (s.id, job.status)."""
    if isinstance(x, dict):
        return SimpleNamespace(**{k: _box(v) for k, v in x.items()})
    if isinstance(x, list):
        return [_box(v) for v in x]
    return x


def _unwrap(resp: httpx.Response):
    """Parse the {success,data,message,errors} envelope; raise on error."""
    try:
        body = resp.json()
    except Exception:
        raise KooRemapperError(f"non-JSON response (HTTP {resp.status_code})", resp.status_code)
    if resp.status_code >= 400 or (isinstance(body, dict) and not body.get("success", True)):
        msg = (body.get("message") if isinstance(body, dict) else None) or f"HTTP {resp.status_code}"
        errs = body.get("errors") if isinstance(body, dict) else None
        if errs:
            msg = f"{msg} — {errs}"
        raise KooRemapperError(msg, resp.status_code)
    data = body.get("data", body) if isinstance(body, dict) else body
    return _box(data)


def _resolve(base_url, token):
    base = (base_url or os.environ.get("KOOREMAPPER_API_BASE") or _DEFAULT_BASE).rstrip("/")
    tok = token or os.environ.get("KOOREMAPPER_TOKEN")
    if not tok:
        raise KooRemapperError(
            "token required — pass token='kr_...' or set KOOREMAPPER_TOKEN "
            "(issue one from the web dashboard → MCP 토큰)"
        )
    return f"{base}/api/v1", {"Authorization": f"Bearer {tok}"}


def _upload_files(filename: str, raw: bytes) -> dict:
    return {"files": (filename, raw, "application/octet-stream")}


# ── synchronous client ──────────────────────────────────────────────────────
class KooRemapper:
    """Synchronous KooRemapper client (scripts, Jupyter, REPL)."""

    def __init__(self, base_url: str | None = None, *, token: str | None = None, timeout: float = 120):
        api, headers = _resolve(base_url, token)
        self._c = httpx.Client(base_url=api, headers=headers, timeout=timeout)

    def __enter__(self) -> "KooRemapper":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._c.close()

    # reads
    def whoami(self):
        return _unwrap(self._c.get("/me"))

    def system_status(self):
        return _unwrap(self._c.get("/system/status"))

    def system_capabilities(self):
        return _unwrap(self._c.get("/system/capabilities"))

    def list_operations(self):
        return _unwrap(self._c.get("/operations"))

    def describe_operation(self, operation: str):
        return _unwrap(self._c.get(f"/operations/{operation}"))

    def list_sessions(self):
        return _unwrap(self._c.get("/sessions"))

    def get_session(self, session_id: str):
        return _unwrap(self._c.get(f"/sessions/{session_id}"))

    def list_files(self, session_id: str):
        return _unwrap(self._c.get(f"/sessions/{session_id}/files"))

    def inspect_file(self, session_id: str, file_id: int):
        return _unwrap(self._c.get(f"/sessions/{session_id}/files/{file_id}/inspect"))

    # sessions / files
    def create_session(self, name: str, description: str | None = None):
        return _unwrap(self._c.post("/sessions", json={"name": name, "description": description}))

    def update_session(self, session_id: str, name: str | None = None, description: str | None = None):
        body = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
        return _unwrap(self._c.patch(f"/sessions/{session_id}", json=body))

    def delete_session(self, session_id: str):
        return _unwrap(self._c.delete(f"/sessions/{session_id}"))

    def delete_file(self, session_id: str, file_id: int):
        return _unwrap(self._c.delete(f"/sessions/{session_id}/files/{file_id}"))

    def upload(self, session_id: str, path, filename: str | None = None):
        """Upload a local file into the session."""
        p = Path(path)
        if not p.is_file():
            raise KooRemapperError(f"file not found: {path}")
        files = _upload_files(filename or p.name, p.read_bytes())
        return _unwrap(self._c.post(f"/sessions/{session_id}/files", files=files))

    def upload_content(self, session_id: str, filename: str, content):
        """Upload in-memory content (str or bytes) as a session file."""
        raw = content.encode("utf-8") if isinstance(content, str) else content
        return _unwrap(self._c.post(f"/sessions/{session_id}/files", files=_upload_files(filename, raw)))

    # operations / jobs
    def run(self, session_id: str, operation: str, args: dict):
        """Start an operation (async job). Returns the job; poll with wait()."""
        return _unwrap(self._c.post(f"/sessions/{session_id}/jobs",
                                    json={"operation": operation, "args": args}))

    def get_job(self, job_id: str):
        return _unwrap(self._c.get(f"/jobs/{job_id}"))

    def list_session_jobs(self, session_id: str):
        return _unwrap(self._c.get(f"/sessions/{session_id}/jobs"))

    def job_outputs(self, job_id: str):
        return _unwrap(self._c.get(f"/jobs/{job_id}/outputs"))

    def job_logs(self, job_id: str) -> str:
        r = self._c.get(f"/jobs/{job_id}/logs")
        if r.status_code >= 400:
            _unwrap(r)
        return r.text

    def cancel_job(self, job_id: str):
        return _unwrap(self._c.post(f"/jobs/{job_id}/cancel"))

    def wait(self, job_id: str, *, timeout: float = 1800, poll: float = 1.0):
        """Poll until the job reaches a terminal state; returns the final job."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            if getattr(job, "status", None) in _FINAL_STATES:
                return job
            if time.monotonic() > deadline:
                raise KooRemapperError(f"job {job_id} not finished within {timeout}s (status={job.status})")
            time.sleep(poll)

    # download
    def _resolve_file_id(self, session_id: str, file_ref) -> int:
        if isinstance(file_ref, int):
            return file_ref
        matches = [f for f in self.list_files(session_id) if f.filename == file_ref]
        if not matches:
            raise KooRemapperError(f"no file named {file_ref!r} in session {session_id}")
        return matches[-1].id  # newest if duplicate names

    def download(self, session_id: str, file_ref, dest=None):
        """Fetch a file's bytes (by id or filename). If dest given, write it and return the path."""
        fid = self._resolve_file_id(session_id, file_ref)
        r = self._c.get(f"/sessions/{session_id}/files/{fid}/download")
        if r.status_code >= 400:
            _unwrap(r)
        if dest is not None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(r.content)
            return str(dest)
        return r.content


# ── asynchronous client ─────────────────────────────────────────────────────
class AsyncKooRemapper:
    """Asynchronous KooRemapper client (asyncio apps)."""

    def __init__(self, base_url: str | None = None, *, token: str | None = None, timeout: float = 120):
        api, headers = _resolve(base_url, token)
        self._c = httpx.AsyncClient(base_url=api, headers=headers, timeout=timeout)

    async def __aenter__(self) -> "AsyncKooRemapper":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._c.aclose()

    async def whoami(self):
        return _unwrap(await self._c.get("/me"))

    async def system_status(self):
        return _unwrap(await self._c.get("/system/status"))

    async def system_capabilities(self):
        return _unwrap(await self._c.get("/system/capabilities"))

    async def list_operations(self):
        return _unwrap(await self._c.get("/operations"))

    async def describe_operation(self, operation: str):
        return _unwrap(await self._c.get(f"/operations/{operation}"))

    async def list_sessions(self):
        return _unwrap(await self._c.get("/sessions"))

    async def get_session(self, session_id: str):
        return _unwrap(await self._c.get(f"/sessions/{session_id}"))

    async def list_files(self, session_id: str):
        return _unwrap(await self._c.get(f"/sessions/{session_id}/files"))

    async def inspect_file(self, session_id: str, file_id: int):
        return _unwrap(await self._c.get(f"/sessions/{session_id}/files/{file_id}/inspect"))

    async def create_session(self, name: str, description: str | None = None):
        return _unwrap(await self._c.post("/sessions", json={"name": name, "description": description}))

    async def update_session(self, session_id: str, name: str | None = None, description: str | None = None):
        body = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
        return _unwrap(await self._c.patch(f"/sessions/{session_id}", json=body))

    async def delete_session(self, session_id: str):
        return _unwrap(await self._c.delete(f"/sessions/{session_id}"))

    async def delete_file(self, session_id: str, file_id: int):
        return _unwrap(await self._c.delete(f"/sessions/{session_id}/files/{file_id}"))

    async def upload(self, session_id: str, path, filename: str | None = None):
        p = Path(path)
        if not p.is_file():
            raise KooRemapperError(f"file not found: {path}")
        files = _upload_files(filename or p.name, p.read_bytes())
        return _unwrap(await self._c.post(f"/sessions/{session_id}/files", files=files))

    async def upload_content(self, session_id: str, filename: str, content):
        raw = content.encode("utf-8") if isinstance(content, str) else content
        return _unwrap(await self._c.post(f"/sessions/{session_id}/files", files=_upload_files(filename, raw)))

    async def run(self, session_id: str, operation: str, args: dict):
        return _unwrap(await self._c.post(f"/sessions/{session_id}/jobs",
                                          json={"operation": operation, "args": args}))

    async def get_job(self, job_id: str):
        return _unwrap(await self._c.get(f"/jobs/{job_id}"))

    async def list_session_jobs(self, session_id: str):
        return _unwrap(await self._c.get(f"/sessions/{session_id}/jobs"))

    async def job_outputs(self, job_id: str):
        return _unwrap(await self._c.get(f"/jobs/{job_id}/outputs"))

    async def job_logs(self, job_id: str) -> str:
        r = await self._c.get(f"/jobs/{job_id}/logs")
        if r.status_code >= 400:
            _unwrap(r)
        return r.text

    async def cancel_job(self, job_id: str):
        return _unwrap(await self._c.post(f"/jobs/{job_id}/cancel"))

    async def wait(self, job_id: str, *, timeout: float = 1800, poll: float = 1.0):
        deadline = time.monotonic() + timeout
        while True:
            job = await self.get_job(job_id)
            if getattr(job, "status", None) in _FINAL_STATES:
                return job
            if time.monotonic() > deadline:
                raise KooRemapperError(f"job {job_id} not finished within {timeout}s (status={job.status})")
            await asyncio.sleep(poll)

    async def _resolve_file_id(self, session_id: str, file_ref) -> int:
        if isinstance(file_ref, int):
            return file_ref
        matches = [f for f in await self.list_files(session_id) if f.filename == file_ref]
        if not matches:
            raise KooRemapperError(f"no file named {file_ref!r} in session {session_id}")
        return matches[-1].id

    async def download(self, session_id: str, file_ref, dest=None):
        fid = await self._resolve_file_id(session_id, file_ref)
        r = await self._c.get(f"/sessions/{session_id}/files/{fid}/download")
        if r.status_code >= 400:
            _unwrap(r)
        if dest is not None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(r.content)
            return str(dest)
        return r.content
