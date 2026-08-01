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
    """Unwrap {success,data,message}. RAISE on error so Claude sees a tool error
    (a returned error dict would look like a successful result)."""
    try:
        body = r.json()
    except Exception:
        raise RuntimeError(f"Backend returned HTTP {r.status_code} (non-JSON)")
    if r.status_code >= 400 or (isinstance(body, dict) and not body.get("success", True)):
        msg = (body.get("message") if isinstance(body, dict) else None) or f"HTTP {r.status_code}"
        raise RuntimeError(msg)
    if not isinstance(body, dict):
        return body
    data = body.get("data")
    # Success responses with no data but a message (delete/cancel) would return
    # an empty result — surface the message so Claude sees the outcome.
    if data is None and body.get("message"):
        return {"message": body["message"]}
    return data if "data" in body else body


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
async def whoami(ctx: Context) -> dict:
    """현재 토큰의 사용자 정보. / The current authenticated user."""
    return await _get(ctx, "/me")


@mcp.tool()
async def system_status(ctx: Context) -> dict:
    """플랫폼 상태(api/db/worker 큐/gmsh/바이너리/op 수). / Platform health + worker queue."""
    return await _get(ctx, "/system/status")


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
async def upload_local_path(session_id: str, path: str, ctx: Context, filename: str | None = None) -> dict:
    """로컬 디스크의 파일을 그대로 세션에 업로드한다(대형 메쉬에 적합). MCP 서버가 그 파일을
    읽을 수 있는 같은 머신에서 돌 때만 동작한다(예: Claude Desktop + 로컬 실행). 대화로
    내용을 실어나르지 않으므로 수십 MB도 OK.
    Upload a file straight from local disk (best for large meshes). Only works when the
    MCP server can read `path` (server runs on the same machine, e.g. Claude Desktop local)."""
    import os as _os
    if not _os.path.isfile(path):
        raise RuntimeError(f"file not found on the MCP host: {path}")
    name = filename or _os.path.basename(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    files = {"files": (name, raw, "application/octet-stream")}
    async with httpx.AsyncClient(base_url=API, timeout=300) as c:
        return _unwrap(
            await c.post(
                f"/sessions/{session_id}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool()
async def save_result_to_path(session_id: str, file_id: int, dest_path: str, ctx: Context) -> dict:
    """세션 파일(산출물)을 로컬 디스크 경로로 저장한다(대형 파일에 적합, 대화로 안 실어나름).
    MCP 서버가 dest_path 에 쓸 수 있는 같은 머신에서 돌 때만 동작.
    Save a session file to a local disk path (best for large outputs; same-machine only)."""
    import os as _os
    async with httpx.AsyncClient(base_url=API, timeout=300) as c:
        r = await c.get(
            f"/sessions/{session_id}/files/{file_id}/download", headers=_forward_headers(ctx)
        )
    if r.status_code >= 400:
        raise RuntimeError(f"download failed: HTTP {r.status_code}")
    d = _os.path.dirname(dest_path)
    if d:
        _os.makedirs(d, exist_ok=True)
    with open(dest_path, "wb") as fh:
        fh.write(r.content)
    return {"saved": dest_path, "bytes": len(r.content)}


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
            job = {**job, "logs": r.text[-4000:] if r.status_code < 400 else f"(logs unavailable: HTTP {r.status_code})"}
    return job


@mcp.tool()
async def cancel_job(job_id: str, ctx: Context) -> dict:
    """실행 중이거나 대기 중인 Job 을 취소한다. / Cancel a queued or running job."""
    return await _post(ctx, f"/jobs/{job_id}/cancel", None)


@mcp.tool()
async def update_session(
    session_id: str, ctx: Context, name: str | None = None, description: str | None = None
) -> dict:
    """세션 이름/설명 수정. / Rename or re-describe a session."""
    body = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.patch(f"/sessions/{session_id}", json=body, headers=_forward_headers(ctx)))


@mcp.tool()
async def delete_session(session_id: str, ctx: Context) -> dict:
    """세션과 그 안의 모든 파일을 삭제. / Delete a session and all its files (irreversible)."""
    return await _delete(ctx, f"/sessions/{session_id}")


@mcp.tool()
async def delete_file(session_id: str, file_id: int, ctx: Context) -> dict:
    """세션에서 파일 1건 삭제. / Delete a single file from a session."""
    return await _delete(ctx, f"/sessions/{session_id}/files/{file_id}")


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
        # Surface as a tool error (like every other tool) instead of a dict that
        # would look like a successful result.
        try:
            msg = r.json().get("message") or f"HTTP {r.status_code}"
        except Exception:
            msg = f"HTTP {r.status_code}"
        raise RuntimeError(f"다운로드 실패: {msg}")
    data = r.content
    # Guard against dumping a huge file into the model context. The cap applies to
    # BOTH the text and base64 branches — base64 is ~33% bigger, so it can't be the
    # escape hatch. For genuinely large files use save_result_to_path (writes to
    # disk, same-machine) instead of pulling bytes through the conversation.
    MAX = int(os.environ.get("KOORM_MCP_MAX_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
    if len(data) > MAX:
        return {
            "filename_id": file_id, "bytes": len(data),
            "error": f"파일이 큽니다({len(data)} bytes > {MAX}). 대화로 실어나르기엔 큽니다. "
                     f"같은 머신이면 save_result_to_path 로 디스크에 저장하세요.",
            "preview": data[:2000].decode("utf-8", "ignore"),
        }
    if as_base64:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data)}
    try:
        return {"filename_id": file_id, "content": data.decode("utf-8"), "bytes": len(data)}
    except UnicodeDecodeError:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data),
                "note": "binary content returned as base64"}


@mcp.tool()
async def list_session_jobs(session_id: str, ctx: Context) -> list:
    """세션에서 실행된 Job 이력(상태/오퍼레이션/exit_code/생성시각).
    The job history of a session — status, operation, exit_code, timestamps."""
    return await _get(ctx, f"/sessions/{session_id}/jobs")


@mcp.tool()
async def system_capabilities(ctx: Context) -> dict:
    """플랫폼 기능 카탈로그 — 오퍼레이션 수, MCP 도구 수, 웹/MCP 패리티 매트릭스,
    Claude 연결 방법 힌트. / Capability + web-MCP parity matrix + connect hints."""
    return await _get(ctx, "/system/capabilities")


if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.host = host
    port = int(os.environ.get("KOORM_MCP_PORT", os.environ.get("MCP_PORT", "8701")))
    mcp.settings.port = port

    # DNS-rebinding 보호는 항상 ON으로 두되 허용 Host를 명시한다. 리버스 프록시
    # (nginx, HEAX Caddy)는 Host를 포트 없이(예: '127.0.0.1') 보내기도 하므로
    # 포트 유무 양쪽을 기본 허용에 넣는다 — 이게 없으면 프록시 경유가 421로 막힌다.
    from mcp.server.transport_security import TransportSecuritySettings

    extra = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    allowed = extra + [
        "127.0.0.1", "localhost", "::1",
        f"127.0.0.1:{port}", f"localhost:{port}",
    ]
    if host not in ("127.0.0.1", "localhost", "::1") and not extra:
        print(
            "⚠ MCP bound to non-localhost but MCP_ALLOWED_HOSTS is empty — 외부 도메인으로 "
            "접근하려면 MCP_ALLOWED_HOSTS(예: 'mcp.example.com')를 설정하라. 프록시(nginx/Caddy) "
            "뒤에서는 프록시가 보내는 Host를 넣어야 한다.",
            flush=True,
        )
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
        allowed_origins=[],
    )

    mcp.run(transport="streamable-http")
