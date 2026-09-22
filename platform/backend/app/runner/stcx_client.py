# stcx(356대 클러스터) 전각도 낙하를 **게이트웨이 MCP 로** 제출·조회하는 래퍼
"""왜 게이트웨이를 거치나 — 직접 ssh 를 하려면 이 컨테이너에 ssh·키·클러스터 자격이
들어와야 하고, 시나리오 생성·파티션 오토튠을 통째로 중복 구현해야 한다. 그 순간
DynaForge 가 클러스터 자격증명을 쥔 앱이 된다. 게이트웨이 뒤에는 이미 그 일을 하는
도구가 있고, 제출이 대시보드를 거치므로 **웹 제출과 같은 인증·권한·이력**이 붙는다.

**파일을 나르지 않는다.** `model_path` 는 서버측 절대경로다 — ste 든 여기든, 올린 쪽이
알려 준 경로를 그대로 넘긴다. 경로 값을 코드에 박지 않는 것이 요점이다(박스마다 다르다).

**도구 이름은 접두사 붙은 별칭을 쓴다.** 게이트웨이는 이름 충돌 여부와 무관하게
`<백엔드키에서 하이픈 뺀 것>_<도구이름>` 별칭을 **항상** 등록하고, 맨이름은 그 이름이
유일할 때만 노출한다. 맨이름으로 부르면 나중에 다른 백엔드에 같은 이름이 생기는 순간
조용히 사라진다.

어떤 실패도 예외로 올리지 않는다 — `{"ok": False, "error": …}` 로 돌려준다. 잡 하나가
실패하는 것과 워커가 죽는 것은 다르다.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import httpx

# 게이트웨이 호출 시한(GATEWAY_CALL_TIMEOUT 기본 120s) **아래**로 잡는다. 위로 잡으면
# 게이트웨이가 먼저 끊고, 우리는 그것을 전송 오류로 읽어 원인을 잘못 짚는다.
DEFAULT_TIMEOUT = 60.0
PROTOCOL_VERSION = "2025-06-18"

# 백엔드 키 `smart-twin-cluster` → 별칭 접두사 `smarttwincluster`(하이픈 제거).
_PREFIX = "smarttwincluster"
TOOL_SUBMIT = f"{_PREFIX}_smarttwin_submit"
TOOL_OPTIONS = f"{_PREFIX}_smarttwin_scenario_options"
TOOL_RESULTS = f"{_PREFIX}_slurm_job_results"
TOOL_LOG = f"{_PREFIX}_slurm_job_log"


class McpHttpClient:
    """streamable-http MCP 엔드포인트에 JSON-RPC 로 tools/call 하는 최소 클라이언트.

    `client` 를 주입받는다 — 시험은 MockTransport 를 실은 AsyncClient 를 넣어 망 없이 돈다.
    """

    def __init__(self, endpoint: str, *, headers: Mapping[str, str] | None = None,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self._headers = dict(headers or {})
        self._client = client
        self._owns_client = client is None
        self._session_id: str | None = None
        self._next_id = 0

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _rpc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _base_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            **self._headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _decode(response: httpx.Response) -> dict | None:
        """application/json 과 text/event-stream 을 **둘 다** 받는다 — 서버가 어느 쪽으로
        답할지는 요청마다 달라진다. 한쪽만 읽으면 간헐적으로 '응답을 못 읽는' 모양이 된다."""
        text = response.text
        if "text/event-stream" in response.headers.get("content-type", ""):
            last = None
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    last = json.loads(line[len("data:"):].strip())
                except ValueError:
                    continue
            return last
        try:
            return json.loads(text)
        except ValueError:
            return None

    async def _post(self, payload: dict) -> dict:
        response = await self._http().post(
            self.endpoint, headers=self._base_headers(),
            content=json.dumps(payload).encode("utf-8"), timeout=self.timeout)
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        if response.status_code >= 400:
            return {"ok": False, "error": f"http_{response.status_code}",
                    "detail": response.text[:500]}
        if response.status_code == 202:
            return {"ok": True, "result": {}}
        message = self._decode(response)
        if message is None:
            return {"ok": False, "error": "unparsable_response", "detail": response.text[:500]}
        if isinstance(message, dict) and message.get("error"):
            return {"ok": False, "error": "rpc_error", "detail": message["error"]}
        return {"ok": True, "result": (message or {}).get("result") or {}}

    async def _handshake(self) -> dict:
        if self._session_id is not None:
            return {"ok": True, "result": {}}
        reply = await self._post({
            "jsonrpc": "2.0", "id": self._rpc_id(), "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "dynaforge", "version": "1"}},
        })
        if not reply["ok"]:
            return reply
        # 세션 헤더를 안 주는 서버에서도 재핸드셰이크를 반복하지 않게 표시만 남긴다.
        if self._session_id is None:
            self._session_id = ""
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return {"ok": True, "result": {}}

    @staticmethod
    def _unwrap(result: Mapping[str, Any]) -> Any:
        """structuredContent > text(JSON) > text 원문 순으로 꺼낸다."""
        if not isinstance(result, Mapping):
            return result
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, Mapping) and first.get("type") == "text":
                text = first.get("text")
                try:
                    return json.loads(text)
                except (TypeError, ValueError):
                    return text
        return result

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict:
        try:
            handshake = await self._handshake()
            if not handshake["ok"]:
                return handshake
            reply = await self._post({
                "jsonrpc": "2.0", "id": self._rpc_id(), "method": "tools/call",
                "params": {"name": name, "arguments": dict(arguments or {})},
            })
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "transport_error",
                    "detail": f"{type(exc).__name__}: {exc}"}
        if not reply["ok"]:
            return reply
        result = reply["result"] if isinstance(reply["result"], Mapping) else {}
        if result.get("isError"):
            return {"ok": False, "error": "tool_error", "detail": self._unwrap(result)}
        return {"ok": True, "result": self._unwrap(result)}

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


class StcxClient:
    """DynaForge → 게이트웨이 → stcx. 자격이 없으면 **아무것도 부르지 않는다**."""

    def __init__(self, endpoint: str, token: str | None, *,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT,
                 mcp: McpHttpClient | None = None) -> None:
        self.endpoint = endpoint
        self.token = (token or "").strip()
        self._mcp = mcp
        self._client = client
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.token)

    def _client_or_none(self) -> McpHttpClient | None:
        if self._mcp is not None:
            return self._mcp
        if not self.available:
            return None
        self._mcp = McpHttpClient(
            self.endpoint, headers={"Authorization": f"Bearer {self.token}"},
            client=self._client, timeout=self._timeout)
        return self._mcp

    async def _call(self, tool: str, args: Mapping[str, Any]) -> dict:
        mcp = self._client_or_none()
        if mcp is None:
            # 꺼져 있는 것을 실패로 낸다 — 조용히 성공으로 넘어가면 잡이 제출된 줄 안다.
            return {"ok": False, "error": "unavailable",
                    "detail": "게이트웨이 주소 또는 PAT 가 설정되지 않았다(KOORM_GATEWAY_MCP/KOORM_GATEWAY_PAT)"}
        return await mcp.call(tool, args)

    async def scenario_options(self, sim_type: str = "fullangle_drop") -> dict:
        """각도 프리셋·옵션 카탈로그. **live 다** — 코드에 프리셋을 박지 않는다."""
        return await self._call(TOOL_OPTIONS, {"sim_type": sim_type})

    async def submit_fullangle_drop(
        self, *, model_path: str, job_name: str = "", angle_preset: str = "",
        scenario_overrides: dict | None = None, memory: str = "", time_limit: str = "",
        dry_run: bool = False,
    ) -> dict:
        """전각도 낙하 제출.

        ⚠ `dry_run` 의 **도구 기본값은 True** 다. 우리가 명시하지 않으면 미리보기만 하고
        아무것도 돌지 않는데, 응답은 성공처럼 생겼다. 그래서 여기서 언제나 실어 보낸다.
        """
        args: dict[str, Any] = {
            "sim_type": "fullangle_drop",
            "model_path": model_path,
            "dry_run": dry_run,
        }
        if job_name:
            args["job_name"] = job_name
        if angle_preset:
            args["angle_preset"] = angle_preset
        if scenario_overrides:
            args["scenario_overrides"] = scenario_overrides
        if memory:
            args["memory"] = memory
        if time_limit:
            args["time_limit"] = time_limit
        return await self._call(TOOL_SUBMIT, args)

    async def job_results(self, job_id: str) -> dict:
        return await self._call(TOOL_RESULTS, {"job_id": str(job_id)})

    async def job_log(self, job_id: str, tail: int = 100) -> dict:
        return await self._call(TOOL_LOG, {"job_id": str(job_id), "tail": tail})

    async def close(self) -> None:
        if self._mcp is not None:
            await self._mcp.close()
