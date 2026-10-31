# MCP 서버(platform/mcp_server/server.py)를 그쪽 venv 로 띄우지 않고 import 해 도구 목록 · 시간 한도를 재는 탐침 — 백엔드 시험이 하위 프로세스로 부른다
"""백엔드 venv 에는 `mcp` 가 없고 MCP 서버는 별도 venv · 프로세스다(server.py 머리말). 그래서 백엔드 시험
(`test_mcp_tools_contract.py`)이 이 파일을 `platform/mcp_server/venv/bin/python -I` 로 돌리고 JSON 한 줄을 받는다.
pytest 는 이 파일을 모으지 않는다(이름이 test_ 로 시작하지 않는다).

    schemas <도구…>   — FastMCP 목록(`mcp.list_tools()`)이 내는 inputSchema 를 도구별로
    limits            — 느린 가짜 백엔드에 붙여 한도 · 기한 · 문구를 잰다(KOORM_MCP_API_TIMEOUT_S 를 작게 두고)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[2] / "mcp_server"


def _load(api_base: str | None = None, knob: str | None = None):
    if api_base:
        os.environ["KOOREMAPPER_API_BASE"] = api_base
    if knob is not None:
        os.environ["KOORM_MCP_API_TIMEOUT_S"] = knob
    sys.path.insert(0, str(MCP_DIR))
    import server  # noqa: E402 — 환경을 먼저 둔다(한도는 import 때 읽는다)
    return server


def schemas(names: list[str]) -> dict:
    server = _load()
    tools = asyncio.run(server.mcp.list_tools())
    got = {t.name: t.inputSchema for t in tools if not names or t.name in names}
    return {"tools": got, "api_timeout_s": getattr(server, "API_TIMEOUT_S", None),
            "gateway_call_timeout_s": getattr(server, "GATEWAY_CALL_TIMEOUT_S", None),
            "knob": getattr(server, "API_TIMEOUT_KNOB", None)}


class _Slow(BaseHTTPRequestHandler):
    """느린 가짜 백엔드 — 경로마다 늦게 답한다. 그림 잡은 영영 running 이다."""
    delay = {"/api/v1/reports": 3.0}            # 찾기 — 한도(1초)보다 늦다
    def log_message(self, *a):                   # 시험 출력을 더럽히지 않는다
        pass

    def _send(self, body: dict, wait: float = 0.0):
        time.sleep(wait)
        raw = json.dumps({"success": True, "data": body, "message": None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/v1/reports":
            return self._send([{"id": "r"}], self.server.find_delay)
        if path.startswith("/api/v1/reports/") and path.endswith("/parts"):     # compare_reports 가 읽는 꼴
            return self._send({"parts": [{"part_id": 1, "part_name": "p", "worst_stress": {"value": 1.0}}]}, 0.4)
        if path.startswith("/api/v1/reports/"):
            return self._send({"id": path.rsplit("/", 1)[-1], "kind": "sphere"}, 0.4)
        if path.endswith("/files"):                                               # 그림 도구가 file_id 를 찾는 목록
            return self._send([{"id": 7, "filename": "a.k", "kind": "kfile"}])
        if path.startswith("/api/v1/jobs/"):
            return self._send({"id": "j1", "status": "running"}, 0.1)
        return self._send({})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        if self.path.split("?")[0].endswith("/jobs"):
            return self._send({"id": "j1", "status": "queued"})
        return self._send({})


def limits() -> dict:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Slow)
    srv.find_delay = 3.0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = _load(f"http://127.0.0.1:{srv.server_address[1]}", "1")
    # MCP 요청 밖에서 도구를 부르므로 ctx.request_context 가 없다(운영에서는 늘 있다) — 이 탐침은 헤더가 아니라 한도를 잰다.
    server._forward_headers = lambda ctx: {}
    out: dict = {"api_timeout_s": server.API_TIMEOUT_S, "knob": server.API_TIMEOUT_KNOB}

    async def call(name: str, args: dict) -> dict:
        t0 = time.monotonic()
        try:
            await server.mcp.call_tool(name, args)
            return {"ok": True, "elapsed": time.monotonic() - t0, "error": None}
        except Exception as exc:  # noqa: BLE001 — 도구 오류가 그대로 Claude 에게 간다
            return {"ok": False, "elapsed": time.monotonic() - t0, "error": f"{type(exc).__name__}: {exc}"}

    out["find_slow"] = asyncio.run(call("find_reports", {}))            # 3초 늦은 백엔드 · 한도 1초
    srv.find_delay = 0.2
    out["find_fast"] = asyncio.run(call("find_reports", {}))            # 한도 안 — 결과
    out["compare_six"] = asyncio.run(call("compare_reports", {"report_ids": [f"r{i}" for i in range(6)]}))
    out["figure_never"] = asyncio.run(call("mesh_surface_figure", {"session_id": "s", "file_id": 7, "timeout_s": 300}))
    srv.shutdown()
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "schemas"
    result = schemas(sys.argv[2:]) if mode == "schemas" else limits()
    print(json.dumps(result, ensure_ascii=False))
