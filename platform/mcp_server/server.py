"""KooRemapper MCP 서버 — Claude 가 K파일 세션을 관리하고 45개 메쉬/해석 오퍼레이션을
실행·다운로드하게 하는 도구.

백엔드(FastAPI)와 의존성 충돌을 피하려고 **별도 venv·프로세스**로 돌리고, 백엔드와는
**REST API** 로만 통신한다. 들어온 MCP 요청의 `Authorization: Bearer kr_...`(개인 토큰)을
그대로 백엔드에 전달해 **그 사용자 권한**으로 동작한다.

실행:
    KOOREMAPPER_API_BASE=http://127.0.0.1:8700 \
    ./venv/bin/python server.py            # streamable-http, 기본 127.0.0.1:8701/mcp

Claude Code 등록(개인 토큰):
    claude mcp add --transport http kooremapper http://<host>:8701/mcp \
      --header "Authorization: Bearer kr_..."
"""
from __future__ import annotations

import base64
import os

import httpx
from mcp.server.fastmcp import Context, FastMCP

API_BASE = os.environ.get("KOOREMAPPER_API_BASE", "http://127.0.0.1:8700").rstrip("/")
API = f"{API_BASE}/api/v1"

mcp = FastMCP("kooremapper")


def _forward_headers(ctx: Context) -> dict:
    headers: dict[str, str] = {}
    req = getattr(getattr(ctx, "request_context", None), "request", None)
    if req is not None:
        v = req.headers.get("authorization")
        if v:
            headers["Authorization"] = v
    return headers


def _unwrap(r: httpx.Response):
    try:
        body = r.json()
    except Exception:
        return {"error": f"HTTP {r.status_code} (non-JSON)", "status": r.status_code}
    if r.status_code >= 400 or (isinstance(body, dict) and not body.get("success", True)):
        msg = body.get("message") if isinstance(body, dict) else None
        return {"error": msg or f"HTTP {r.status_code}", "detail": body}
    return body.get("data", body) if isinstance(body, dict) else body


async def _get(ctx, path, params=None):
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.get(path, params=params, headers=_forward_headers(ctx)))


async def _post(ctx, path, json_body=None):
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        return _unwrap(await c.post(path, json=json_body, headers=_forward_headers(ctx)))


async def _delete(ctx, path):
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.delete(path, headers=_forward_headers(ctx)))


# ── 오퍼레이션 카탈로그 ──────────────────────────────────────────────
@mcp.tool()
async def list_operations(ctx: Context) -> list:
    """사용 가능한 45개 오퍼레이션 요약(name, category, summary, 입력유형). 무엇을 할 수
    있는지 먼저 조회. 상세 인자는 describe_operation 으로."""
    return await _get(ctx, "/operations")


@mcp.tool()
async def describe_operation(operation: str, ctx: Context) -> dict:
    """한 오퍼레이션의 상세 — 인자 JSON Schema(args_schema), 입출력, 예제 args, 매뉴얼.
    run_operation 호출 전에 args 를 어떻게 구성할지 여기서 확인하라."""
    return await _get(ctx, f"/operations/{operation}")


# ── 세션 / 파일 ──────────────────────────────────────────────────────
@mcp.tool()
async def list_sessions(ctx: Context) -> list:
    """내 세션(프로젝트) 목록. 각 세션은 업로드/생성된 K파일 묶음이다."""
    return await _get(ctx, "/sessions")


@mcp.tool()
async def create_session(name: str, ctx: Context, description: str | None = None) -> dict:
    """새 세션 생성. 이후 이 session_id 로 파일을 업로드하고 오퍼레이션을 실행한다."""
    return await _post(ctx, "/sessions", {"name": name, "description": description})


@mcp.tool()
async def get_session(session_id: str, ctx: Context) -> dict:
    """세션 상세 + 포함된 파일 목록(meta 포함)."""
    return await _get(ctx, f"/sessions/{session_id}")


@mcp.tool()
async def upload_kfile(
    session_id: str, filename: str, content: str, ctx: Context, base64_encoded: bool = False
) -> dict:
    """세션에 파일 업로드. `content` 는 파일 내용(LS-DYNA .k 등 텍스트). 바이너리면
    base64 로 주고 base64_encoded=true. 업로드 즉시 백엔드가 `info` 로 노드/요소/파트/
    bbox/*INCLUDE 를 파싱해 meta 에 캐시한다."""
    raw = base64.b64decode(content) if base64_encoded else content.encode("utf-8")
    files = {"files": (filename, raw, "application/octet-stream")}
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        return _unwrap(
            await c.post(
                f"/sessions/{session_id}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool()
async def list_session_files(session_id: str, ctx: Context) -> list:
    """세션 안의 파일 목록 + 각 파일의 meta(노드/요소/파트/bbox/*INCLUDE/키워드).
    "이 K파일 안에 뭐가 들어있는지" 를 여기서 확인한다."""
    return await _get(ctx, f"/sessions/{session_id}/files")


@mcp.tool()
async def inspect_file(session_id: str, file_id: int, ctx: Context) -> dict:
    """단일 파일의 상세 메타(info 결과 + *INCLUDE 내부 파일 목록)."""
    return await _get(ctx, f"/sessions/{session_id}/files/{file_id}/inspect")


# ── 실행 / 결과 ──────────────────────────────────────────────────────
@mcp.tool()
async def run_operation(session_id: str, operation: str, args: dict, ctx: Context) -> dict:
    """세션 파일에 오퍼레이션을 적용(비동기 Job 생성) → job_id 반환. args 는
    describe_operation 의 args_schema 를 따른다(파일 인자는 세션 내 파일명). 진행상황은
    get_job 으로 폴링하고, 끝나면 download_result 로 산출물을 가져온다."""
    return await _post(
        ctx, f"/sessions/{session_id}/jobs", {"operation": operation, "args": args}
    )


@mcp.tool()
async def get_job(job_id: str, ctx: Context, include_logs: bool = False) -> dict:
    """Job 상태/진행/exit_code/산출 파일. include_logs=true 면 stdout/stderr 일부도."""
    job = await _get(ctx, f"/jobs/{job_id}")
    if include_logs and isinstance(job, dict):
        async with httpx.AsyncClient(base_url=API, timeout=60) as c:
            r = await c.get(f"/jobs/{job_id}/logs", headers=_forward_headers(ctx))
            job = {**job, "logs": r.text[-4000:]}
    return job


@mcp.tool()
async def get_job_outputs(job_id: str, ctx: Context) -> list:
    """Job 이 생성한 산출 파일 목록(session_file id/이름/meta)."""
    return await _get(ctx, f"/jobs/{job_id}/outputs")


@mcp.tool()
async def download_result(
    session_id: str, file_id: int, ctx: Context, as_base64: bool = False
) -> dict:
    """세션 파일 내용을 가져온다(오퍼레이션 산출물 회수). 기본은 텍스트로 반환하고,
    바이너리거나 큰 파일이면 as_base64=true 로 base64 반환."""
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        r = await c.get(
            f"/sessions/{session_id}/files/{file_id}/download",
            headers=_forward_headers(ctx),
        )
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "detail": r.text[:500]}
    data = r.content
    if as_base64:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data)}
    try:
        return {"filename_id": file_id, "content": data.decode("utf-8"), "bytes": len(data)}
    except UnicodeDecodeError:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data),
                "note": "binary content returned as base64"}


if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = int(os.environ.get("KOORM_MCP_PORT", os.environ.get("MCP_PORT", "8701")))

    if host not in ("127.0.0.1", "localhost", "::1"):
        from mcp.server.transport_security import TransportSecuritySettings

        allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(allowed),
            allowed_hosts=allowed,
            allowed_origins=[],
        )

    mcp.run(transport="streamable-http")
