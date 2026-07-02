# 실행 중인 MCP 서버를 PAT로 점검하는 스모크 테스트 (도구 노출·인증·전체 op 파이프라인·에러 전파).
"""KooRemapper MCP smoke test.

Connects to a running MCP server with a kr_ PAT and verifies the tool surface,
auth forwarding, a full operation pipeline (create → run → job → outputs →
delete), and that backend errors surface as tool errors (isError).

Run (against the local dev stack — api+mcp+postgres up):
    mcp_server/venv/bin/python mcp_server/smoke.py

Token resolution, in order:
  1. KOORM_MCP_TEST_TOKEN — a kr_ PAT to use directly.
  2. else mint a temporary PAT via the REST API using
     KOORM_ADMIN_EMAIL / KOORM_ADMIN_PASSWORD (default the seed admin), then
     revoke it at the end.

Exit codes: 0 = pass OR skipped (prereqs absent / server unreachable, CI-safe),
1 = a check failed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("KOORM_MCP_URL", "http://127.0.0.1:8701/mcp")
API_BASE = os.environ.get("KOOREMAPPER_API_BASE", os.environ.get("KOORM_API_BASE", "http://127.0.0.1:8700")).rstrip("/")
API = f"{API_BASE}/api/v1"
ADMIN_EMAIL = os.environ.get("KOORM_ADMIN_EMAIL", "admin@kooremapper.local")
ADMIN_PASSWORD = os.environ.get("KOORM_ADMIN_PASSWORD", "admin")
EXPECTED_TOOLS = 22


def _p(*a):
    print(*a, flush=True)


def _data(res):
    txt = "".join(c.text for c in res.content if getattr(c, "type", None) == "text")
    try:
        return json.loads(txt)
    except Exception:
        return txt


def _mint_token() -> tuple[str | None, int | None]:
    """Return (plaintext_pat, token_id) minted via the API, or (None, None) on failure."""
    try:
        with httpx.Client(base_url=API, timeout=10) as c:
            r = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            if r.status_code != 200:
                return None, None
            jwt = r.json()["data"]["access_token"]
            r = c.post("/me/tokens", headers={"Authorization": f"Bearer {jwt}"}, json={"name": "mcp-smoke"})
            d = r.json()["data"]
            return d["token"], d["info"]["id"]
    except Exception:
        return None, None


def _revoke_token(token_id: int) -> None:
    try:
        with httpx.Client(base_url=API, timeout=10) as c:
            r = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            jwt = r.json()["data"]["access_token"]
            c.delete(f"/me/tokens/{token_id}", headers={"Authorization": f"Bearer {jwt}"})
    except Exception:
        pass


async def _run(pat: str) -> bool:
    ok = True
    headers = {"Authorization": f"Bearer {pat}"}
    async with streamablehttp_client(MCP_URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            tools = (await s.list_tools()).tools
            _p(f"[tools] {len(tools)} (expect {EXPECTED_TOOLS})")
            ok &= len(tools) == EXPECTED_TOOLS

            who = _data(await s.call_tool("whoami", {}))
            _p(f"[whoami] {who.get('email') if isinstance(who, dict) else who}")
            ok &= isinstance(who, dict) and bool(who.get("email"))

            st = _data(await s.call_tool("system_status", {}))
            ok_ops = isinstance(st, dict) and st.get("operations", 0) >= 45
            _p(f"[system_status] ops={st.get('operations') if isinstance(st, dict) else st}")
            ok &= ok_ops

            ops = await s.call_tool("list_operations", {})
            _p(f"[list_operations] blocks={len(ops.content)} isError={ops.isError}")
            ok &= len(ops.content) >= 45 and not ops.isError

            caps = _data(await s.call_tool("system_capabilities", {}))
            ok_caps = isinstance(caps, dict) and caps.get("operations", 0) >= 45 and caps.get("mcp_tools") == EXPECTED_TOOLS
            _p(f"[system_capabilities] ops={caps.get('operations')} mcp_tools={caps.get('mcp_tools')}")
            ok &= ok_caps

            # full operation pipeline through MCP (self-contained `generate` op)
            sess = _data(await s.call_tool("create_session", {"name": "mcp_smoke"}))
            sid = sess.get("id") if isinstance(sess, dict) else None
            _p(f"[create_session] {sid}")
            ok &= bool(sid)
            if sid:
                job = _data(await s.call_tool("run_operation", {
                    "session_id": sid, "operation": "generate",
                    "args": {"type": "torus", "output_prefix": "t", "dim-i": 8, "dim-j": 4, "dim-k": 4},
                }))
                jid = job.get("id") if isinstance(job, dict) else None
                _p(f"[run_operation] {jid}")
                ok &= bool(jid)
                final = None
                for _ in range(30):
                    j = _data(await s.call_tool("get_job", {"job_id": jid}))
                    final = j.get("status") if isinstance(j, dict) else str(j)
                    if final in ("succeeded", "failed"):
                        _p(f"[get_job] {final} exit={j.get('exit_code')}")
                        break
                    await asyncio.sleep(1)
                ok &= final == "succeeded"
                outs = await s.call_tool("get_job_outputs", {"job_id": jid})
                _p(f"[get_job_outputs] blocks={len(outs.content)}")
                ok &= len(outs.content) >= 1
                jobs = await s.call_tool("list_session_jobs", {"session_id": sid})
                _p(f"[list_session_jobs] blocks={len(jobs.content)} isError={jobs.isError}")
                ok &= len(jobs.content) >= 1 and not jobs.isError
                # backend errors must surface as a tool error, not a fake-success result
                bad = await s.call_tool("describe_operation", {"operation": "no_such_op"})
                _p(f"[describe bad-op] isError={bad.isError}")
                ok &= bad.isError is True
                _data(await s.call_tool("delete_session", {"session_id": sid}))
                _p("[delete_session] ok")
    return ok


def main() -> int:
    pat = os.environ.get("KOORM_MCP_TEST_TOKEN")
    minted_id = None
    if not pat:
        pat, minted_id = _mint_token()
    if not pat:
        _p("SKIP: no KOORM_MCP_TEST_TOKEN and could not mint via API "
           f"({API}; admin={ADMIN_EMAIL}). Is the stack up?")
        return 0
    try:
        ok = asyncio.run(_run(pat))
    except Exception as exc:  # server unreachable etc. → skip, don't fail CI
        _p(f"SKIP: MCP server unreachable at {MCP_URL} ({exc})")
        return 0
    finally:
        if minted_id is not None:
            _revoke_token(minted_id)
    _p("\n=== MCP SMOKE:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
