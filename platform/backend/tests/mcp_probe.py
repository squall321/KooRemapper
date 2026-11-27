# MCP 서버(platform/mcp_server/server.py)를 그쪽 venv 로 띄우지 않고 import 해 도구 목록 · 시간 한도를 재는 탐침 — 백엔드 시험이 하위 프로세스로 부른다
"""백엔드 venv 에는 `mcp` 가 없고 MCP 서버는 별도 venv · 프로세스다(server.py 머리말). 그래서 백엔드 시험
(`test_mcp_tools_contract.py`)이 이 파일을 `platform/mcp_server/venv/bin/python -I` 로 돌리고 JSON 한 줄을 받는다.
pytest 는 이 파일을 모으지 않는다(이름이 test_ 로 시작하지 않는다).

    schemas <도구…>   — FastMCP 목록(`mcp.list_tools()`)이 내는 inputSchema 를 도구별로
    limits            — 느린 가짜 백엔드에 붙여 한도 · 기한 · 문구를 잰다(KOORM_MCP_API_TIMEOUT_S 를 작게 두고)
    paths <값…>       — 경로에 사용자 값을 넣는 도구를 값마다 불러 가짜 백엔드가 받은 요청 대상(퍼센트 인코딩 그대로)을 낸다
    compare           — report_compare 의 지표 표를 케이스 응답(CaseRead 꼴) 가짜 백엔드로 — 칸이 「—」 가 아니라 값인지
    contract          — 도구 전부의 설명 · inputSchema · outputSchema · 표지(공통 계약 C1 ~ C8 전수 시험)
    stateless         — 실제 streamable-http 앱(ASGI)에 JSON-RPC 를 보내 세션 번호 · initialize 없는 호출 · 옛 세션 번호 · 머리 나르기를 잰다
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


def _input_schema(t) -> dict:
    """도구의 inputSchema — 1.x 는 `inputSchema`, 2.x(mcp_types)는 `input_schema` 칸이다. 줄로 나가는 JSON 은 둘 다 inputSchema 다."""
    got = getattr(t, "inputSchema", None)
    return got if got is not None else t.input_schema


def schemas(names: list[str]) -> dict:
    server = _load()
    tools = asyncio.run(server.mcp.list_tools())
    got = {t.name: _input_schema(t) for t in tools if not names or t.name in names}
    return {"tools": got, "api_timeout_s": getattr(server, "API_TIMEOUT_S", None),
            "gateway_call_timeout_s": getattr(server, "GATEWAY_CALL_TIMEOUT_S", None),
            "knob": getattr(server, "API_TIMEOUT_KNOB", None)}


def contract() -> dict:
    server = _load()
    out = {}
    for t in asyncio.run(server.mcp.list_tools()):
        ann = t.annotations
        output = getattr(t, "outputSchema", None) if hasattr(t, "outputSchema") else t.output_schema
        out[t.name] = {"description": t.description or "", "input": _input_schema(t), "output": output,
                       "annotations": None if ann is None else ann.model_dump(by_alias=True, exclude_none=True)}
    return out


class _Cases(BaseHTTPRequestHandler):
    """리포트 · 케이스 · 미디어만 답하는 가짜 백엔드 — 케이스는 백엔드 CaseRead 꼴(롤업은 맨 위 칸, 파트 값은 parts_metrics)."""
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.endswith("/media"):
            data = {"media": []}
        elif "/cases/" in path:
            data = {"case_key": path.rsplit("/", 1)[-1], "max_stress": 123.5, "max_g": 45.0, "max_disp": 2.5, "min_safety_factor": 1.2,
                    "parts_metrics": {"1": {"peak_strain": 0.01, "min_principal": -3.0}, "2": {"peak_strain": 0.03, "min_principal": -7.0}}}
        else:
            data = {"id": "r1", "kind": "impact", "session_id": "s1"}
        raw = json.dumps({"success": True, "data": data, "message": None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def compare() -> dict:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Cases)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = _load(f"http://127.0.0.1:{srv.server_address[1]}")
    server._forward_headers = lambda ctx: {}
    try:
        out = {}
        for label, metrics in (("default", None), ("named", ["max_stress", "min_safety_factor", "peak_strain", "min_principal", "nope"])):
            got = server.mcp.call_tool("report_compare", {"report_id": "r1", "case_keys": ["c1"], "metrics": metrics, "max_images": 0})
            res = asyncio.run(got)
            blocks = res[0] if isinstance(res, tuple) else getattr(res, "content", res)
            text = next(b.text for b in blocks if getattr(b, "type", "") == "text")
            row = next(l for l in text.splitlines() if l.startswith("| c1 |"))
            out[label] = [c.strip() for c in row.strip("|").split("|")][1:]
        return out
    finally:
        srv.shutdown()


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


class _Record(BaseHTTPRequestHandler):
    """받은 요청 대상을 **보낸 그대로**(퍼센트 인코딩 포함) 적기만 하는 가짜 백엔드."""
    def log_message(self, *a):
        pass

    def _ok(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.server.seen.append([self.command, self.path])
        raw = json.dumps({"success": True, "data": {}, "message": None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _ok


# 경로에 사용자 값을 넣는 도구 — (이름, 값 하나로 인자 만들기). 과제 · 리포트 · 세션 · 레시피 · 케이스 · 객체가 모두 든다.
PATH_CALLS = (
    ("report_summary", lambda v: {"report_id": v}),
    ("delete_report", lambda v: {"report_id": v}),
    ("report_revision", lambda v: {"report_id": v}),
    ("unlink_report_revision", lambda v: {"report_id": v}),
    ("clear_report_unlink", lambda v: {"report_id": v}),
    ("report_case", lambda v: {"report_id": v, "case_key": v}),
    ("get_session", lambda v: {"session_id": v}),
    ("task_revisions", lambda v: {"task_key": v}),
    ("compare_task_revisions", lambda v: {"task_key": v}),
    ("ontology_object", lambda v: {"type_slug": v, "key": v}),
    ("recipe_get", lambda v: {"name": v}),
    ("ingest_campaign_manifest", lambda v: {"campaign_id": v, "runs": [{"run_key": "k"}]}),
)


def paths(values: list[str]) -> dict:
    """값마다 경로 도구를 불러 가짜 백엔드가 받은 요청 대상을 돌려준다(경로 칸 감싸기 — 검토 반영 11-11)."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Record)
    srv.seen = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = _load(f"http://127.0.0.1:{srv.server_address[1]}")
    server._forward_headers = lambda ctx: {}
    calls: dict = {}
    for v in values:
        for name, make in PATH_CALLS:
            srv.seen.clear()
            err = None
            try:
                asyncio.run(server.mcp.call_tool(name, make(v)))
            except Exception as exc:  # noqa: BLE001 — 시험이 모양을 본다
                err = f"{type(exc).__name__}: {exc}"
            calls.setdefault(name, {})[v] = {"seen": list(srv.seen), "error": err}
    srv.shutdown()

    def enc(fn, v):
        try:
            return fn(v)
        except ValueError as exc:            # `/` · `\` 는 id 칸에서 거절된다(재검토 11-12 rr4)
            return f"REFUSED: {exc}"

    return {"calls": calls, "seg": {v: enc(server._seg, v) for v in values},
            "seg_key": {v: enc(server._seg_key, v) for v in values}}


class _Who(BaseHTTPRequestHandler):
    """받은 머리를 그대로 돌려주는 가짜 백엔드 — 도구가 들어온 MCP 요청의 머리를 나르는지(_forward_headers) 본다."""
    def log_message(self, *a):
        pass

    def do_GET(self):
        got = {h: self.headers.get(h) for h in ("authorization", "x-heax-user-affiliation", "x-heax-aff-proof")}
        raw = json.dumps({"success": True, "data": {"headers": got}, "message": None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _rpc_body(r) -> dict | None:
    """SSE 한 덩이(`data: {...}`) 또는 JSON 본문에서 JSON-RPC 응답을 꺼낸다 — 세션 오류(400 · 404)는 JSON 본문으로 온다."""
    for line in r.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    try:
        return r.json()
    except ValueError:
        return None


def stateless() -> dict:
    import httpx
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Who)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = _load(f"http://127.0.0.1:{srv.server_address[1]}")
    # 2.x 는 stateless 를 기동 선택지로 준다 — server.py 의 기동이 쓰는 http_options() 그대로. 1.x 는 생성자에서 이미 켰다.
    opts = server.http_options() if getattr(server, "SDK2", False) else {}
    app = server.mcp.streamable_http_app(**opts)
    accept = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    init = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}

    def rpc(i: int, method: str, params: dict | None = None) -> dict:
        return {"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}

    def seen(r, b) -> dict:
        return {"status": r.status_code, "ctype": (r.headers.get("content-type") or "").split(";")[0],
                "session_id": r.headers.get("mcp-session-id"), "error": (b or {}).get("error")}

    async def run() -> dict:
        conf = opts or {"stateless_http": server.mcp.settings.stateless_http, "json_response": server.mcp.settings.json_response}
        out = {"sdk2": bool(opts), "stateless_http": conf["stateless_http"], "json_response": conf["json_response"]}
        async with server.mcp.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8701") as c:
                r = await c.post("/mcp", json=rpc(1, "initialize", init), headers=accept)
                out["initialize"] = seen(r, _rpc_body(r))
                # initialize 도 세션 번호도 없이 바로 부른다 — 게이트웨이가 재기동 뒤 · 다른 대로 보내는 꼴
                h = {**accept, "authorization": "Bearer probe-token", "x-heax-user-affiliation": "probe-aff"}
                r = await c.post("/mcp", json=rpc(2, "tools/call", {"name": "whoami", "arguments": {}}), headers=h)
                b = _rpc_body(r)
                out["call_without_initialize"] = seen(r, b)
                content = ((b or {}).get("result") or {}).get("content") or []
                out["forwarded"] = json.loads(content[0]["text"]).get("headers") if content else None
                r = await c.post("/mcp", json=rpc(3, "tools/list"), headers={**accept, "mcp-session-id": "stale-before-restart"})
                b = _rpc_body(r)
                out["stale_session_id"] = {**seen(r, b), "tools": len(((b or {}).get("result") or {}).get("tools") or [])}
                # 본문 5 MiB — 덱을 본문에 싣는 upload_kfile 꼴. 2.x 기본 상한(4 MiB)이면 413 이다
                big = rpc(4, "tools/list", {"_meta": {"pad": "x" * (5 << 20)}})
                r = await c.post("/mcp", json=big, headers=accept)
                out["big_body"] = seen(r, _rpc_body(r))
        return out

    try:
        return asyncio.run(run())
    finally:
        srv.shutdown()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "schemas"
    if mode == "schemas":
        result = schemas(sys.argv[2:])
    elif mode == "paths":
        result = paths(sys.argv[2:])
    elif mode == "stateless":
        result = stateless()
    elif mode == "contract":
        result = contract()
    elif mode == "compare":
        result = compare()
    else:
        result = limits()
    print(json.dumps(result, ensure_ascii=False))
