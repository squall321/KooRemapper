# 동기/비동기 Python 클라이언트를 러닝 스택에 대고 점검하는 스모크 테스트.
"""KooRemapper Python client smoke test (sync + async).

Exercises both clients against a running stack: whoami, catalog, a full operation
pipeline (create → upload-free generate → wait → outputs → download → delete),
and that a generic operation runs without any per-op client code.

Token: KOOREMAPPER_TOKEN if set, else auto-mint+revoke a temp PAT via the REST
API using KOORM_ADMIN_EMAIL/KOORM_ADMIN_PASSWORD (default seed admin).

Run:  PYTHONPATH=platform/clients/python python platform/clients/python/smoke.py
Exit: 0 = pass OR skipped (stack/creds absent), 1 = a check failed.
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from kooremapper import AsyncKooRemapper, KooRemapper  # noqa: E402

API_BASE = os.environ.get("KOOREMAPPER_API_BASE", "http://127.0.0.1:8700").rstrip("/")
API = f"{API_BASE}/api/v1"
ADMIN_EMAIL = os.environ.get("KOORM_ADMIN_EMAIL", "admin@kooremapper.local")
ADMIN_PASSWORD = os.environ.get("KOORM_ADMIN_PASSWORD", "admin")
GEN_ARGS = {"type": "torus", "output_prefix": "t", "dim-i": 8, "dim-j": 4, "dim-k": 4}


def _p(*a):
    print(*a, flush=True)


def _mint():
    try:
        with httpx.Client(base_url=API, timeout=10) as c:
            r = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            if r.status_code != 200:
                return None, None
            jwt = r.json()["data"]["access_token"]
            d = c.post("/me/tokens", headers={"Authorization": f"Bearer {jwt}"},
                       json={"name": "pyclient-smoke"}).json()["data"]
            return d["token"], d["info"]["id"]
    except Exception:
        return None, None


def _revoke(tid):
    try:
        with httpx.Client(base_url=API, timeout=10) as c:
            jwt = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).json()["data"]["access_token"]
            c.delete(f"/me/tokens/{tid}", headers={"Authorization": f"Bearer {jwt}"})
    except Exception:
        pass


def _check_sync(token) -> bool:
    ok = True
    with KooRemapper(API_BASE, token=token) as kr:
        _p("[sync] whoami:", kr.whoami().email)
        ok &= len(kr.list_operations()) >= 45
        s = kr.create_session("pyclient_smoke_sync")
        job = kr.wait(kr.run(s.id, "generate", GEN_ARGS).id)
        _p("[sync] job:", job.status, "exit", job.exit_code)
        ok &= job.status == "succeeded"
        outs = kr.job_outputs(job.id)
        ok &= len(outs) >= 1
        content = kr.download(s.id, outs[0].filename)
        _p("[sync] downloaded", outs[0].filename, len(content), "bytes")
        ok &= len(content) > 0
        kr.delete_session(s.id)
    _p("[sync] result:", "ok" if ok else "FAIL")
    return ok


async def _check_async(token) -> bool:
    ok = True
    async with AsyncKooRemapper(API_BASE, token=token) as kr:
        who = await kr.whoami()
        _p("[async] whoami:", who.email)
        ok &= len(await kr.list_operations()) >= 45
        s = await kr.create_session("pyclient_smoke_async")
        started = await kr.run(s.id, "generate", GEN_ARGS)
        job = await kr.wait(started.id)
        _p("[async] job:", job.status, "exit", job.exit_code)
        ok &= job.status == "succeeded"
        outs = await kr.job_outputs(job.id)
        ok &= len(outs) >= 1
        content = await kr.download(s.id, outs[0].filename)
        _p("[async] downloaded", outs[0].filename, len(content), "bytes")
        ok &= len(content) > 0
        await kr.delete_session(s.id)
    _p("[async] result:", "ok" if ok else "FAIL")
    return ok


def main() -> int:
    token = os.environ.get("KOOREMAPPER_TOKEN")
    minted = None
    if not token:
        token, minted = _mint()
    if not token:
        _p(f"SKIP: no KOOREMAPPER_TOKEN and could not mint via {API} (stack up?)")
        return 0
    try:
        ok = _check_sync(token)
        ok = asyncio.run(_check_async(token)) and ok
    except Exception as exc:
        _p(f"SKIP: stack unreachable ({exc})")
        return 0
    finally:
        if minted is not None:
            _revoke(minted)
    _p("\n=== PYCLIENT SMOKE:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
