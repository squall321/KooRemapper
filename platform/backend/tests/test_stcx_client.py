"""stcx 제출 래퍼 — 망 없이(MockTransport) 계약을 고정한다.

이 파일이 지키는 것 중 가장 중요한 하나는 **`dry_run`** 이다. 도구의 기본값이 `True` 라서
우리가 명시하지 않으면 미리보기만 하고 아무것도 돌지 않는데 **응답은 성공처럼 생겼다.**
그러면 사용자는 네 시간을 기다린 뒤에야 아무 일도 없었다는 것을 안다.

두 번째는 **도구 이름**이다. 게이트웨이는 접두사 붙은 별칭을 언제나 등록하고, 맨이름은
그 이름이 유일할 때만 노출한다. 맨이름으로 부르면 나중에 다른 백엔드에 같은 이름이
생기는 순간 조용히 사라진다.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.runner.stcx_client import (TOOL_OPTIONS, TOOL_SUBMIT, McpHttpClient, StcxClient)

pytestmark = pytest.mark.asyncio(loop_scope="function")


class _Gateway:
    """게이트웨이 대역. 주고받은 요청을 전부 들고 있어 무엇이 건너갔는지 볼 수 있다."""

    def __init__(self, *, tool_result=None, is_error=False, status=200, sse=False, boom=False):
        self.calls: list[dict] = []
        self.tool_result = tool_result if tool_result is not None else {"ok": True}
        self.is_error, self.status, self.sse, self.boom = is_error, status, sse, boom

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.boom:
            raise httpx.ConnectError("refused", request=request)
        body = json.loads(request.content)
        self.calls.append(body)
        if body.get("method") != "tools/call":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body.get("id"), "result": {}},
                                  headers={"mcp-session-id": "s-1"})
        if self.status >= 400:
            return httpx.Response(self.status, text="nope")
        payload = {"jsonrpc": "2.0", "id": body.get("id"),
                   "result": {"structuredContent": self.tool_result, "isError": self.is_error}}
        if self.sse:
            return httpx.Response(200, text=f"event: message\ndata: {json.dumps(payload)}\n\n",
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=payload)

    @property
    def tool_calls(self):
        return [c for c in self.calls if c.get("method") == "tools/call"]


def _client(gw: _Gateway, *, token="pat-x") -> StcxClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(gw.handler))
    return StcxClient("http://gw.test/mcp", token, client=http)


# ── dry_run — 이 파일의 이유 ────────────────────────────────────────────────
async def test_submit_always_sends_dry_run_false():
    gw = _Gateway(tool_result={"job_id": "777"})
    c = _client(gw)
    r = await c.submit_fullangle_drop(model_path="/share/jobs/abc/input/m.k")
    assert r["ok"], r
    args = gw.tool_calls[-1]["params"]["arguments"]
    assert args["dry_run"] is False, (
        "도구 기본값이 True 다 — 명시하지 않으면 미리보기만 하고 아무것도 안 돈다")


async def test_dry_run_true_is_honoured_when_asked():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(model_path="/m.k", dry_run=True)
    assert gw.tool_calls[-1]["params"]["arguments"]["dry_run"] is True


# ── 도구 이름 ───────────────────────────────────────────────────────────────
async def test_calls_the_prefixed_alias_not_the_bare_name():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(model_path="/m.k")
    name = gw.tool_calls[-1]["params"]["name"]
    assert name == TOOL_SUBMIT == "smarttwincluster_smarttwin_submit"
    assert name != "smarttwin_submit", "맨이름은 충돌이 생기는 순간 조용히 사라진다"


async def test_options_uses_its_own_alias():
    gw = _Gateway(tool_result={"result": "카탈로그"})
    c = _client(gw)
    r = await c.scenario_options()
    assert r["ok"] and gw.tool_calls[-1]["params"]["name"] == TOOL_OPTIONS
    assert gw.tool_calls[-1]["params"]["arguments"]["sim_type"] == "fullangle_drop"


# ── 경로는 그대로 넘긴다 ────────────────────────────────────────────────────
async def test_the_model_path_goes_through_untouched():
    """경로 값을 코드가 손대면 박스마다 다른 경로에서 조용히 어긋난다."""
    gw = _Gateway()
    c = _client(gw)
    p = "/srv/ste/jobs/01J.../input/model.k"
    await c.submit_fullangle_drop(model_path=p)
    assert gw.tool_calls[-1]["params"]["arguments"]["model_path"] == p


async def test_optional_args_are_omitted_not_blanked():
    """빈 문자열을 보내면 도구가 '지정됨' 으로 읽어 프리셋을 덮어 버릴 수 있다."""
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(model_path="/m.k")
    args = gw.tool_calls[-1]["params"]["arguments"]
    for k in ("job_name", "angle_preset", "scenario_overrides", "memory", "time_limit"):
        assert k not in args, f"{k} 를 빈 값으로 보내면 안 된다"


async def test_given_options_are_passed():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(model_path="/m.k", angle_preset="fibonacci-100",
                                  job_name="drop-1", scenario_overrides={"simulation_params": {"height": 800}})
    args = gw.tool_calls[-1]["params"]["arguments"]
    assert args["angle_preset"] == "fibonacci-100"
    assert args["job_name"] == "drop-1"
    assert args["scenario_overrides"]["simulation_params"]["height"] == 800


# ── 실패를 실패로 낸다 ──────────────────────────────────────────────────────
async def test_gateway_down_is_an_error_not_an_exception():
    gw = _Gateway(boom=True)
    c = _client(gw)
    r = await c.submit_fullangle_drop(model_path="/m.k")
    assert r["ok"] is False and r["error"] == "transport_error"


async def test_http_error_is_surfaced():
    gw = _Gateway(status=503)
    c = _client(gw)
    r = await c.submit_fullangle_drop(model_path="/m.k")
    assert r["ok"] is False and r["error"] == "http_503"


async def test_tool_error_is_not_a_success():
    gw = _Gateway(is_error=True, tool_result={"detail": "model not found"})
    c = _client(gw)
    r = await c.submit_fullangle_drop(model_path="/nope.k")
    assert r["ok"] is False and r["error"] == "tool_error"


async def test_without_a_pat_nothing_is_called():
    """꺼져 있는 것을 조용한 성공으로 바꾸지 않는다 — 제출된 줄 알고 기다리게 된다."""
    gw = _Gateway()
    c = _client(gw, token="")
    assert c.available is False
    r = await c.submit_fullangle_drop(model_path="/m.k")
    assert r["ok"] is False and r["error"] == "unavailable"
    assert gw.calls == []


# ── 전송 세부 ───────────────────────────────────────────────────────────────
async def test_sse_responses_decode_too():
    """서버가 어느 형식으로 답할지는 요청마다 다르다 — 한쪽만 읽으면 간헐적으로 깨진다."""
    gw = _Gateway(sse=True, tool_result={"job_id": "9"})
    c = _client(gw)
    r = await c.submit_fullangle_drop(model_path="/m.k")
    assert r["ok"] and r["result"]["job_id"] == "9"


async def test_handshake_happens_once_across_calls():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(model_path="/a.k")
    await c.submit_fullangle_drop(model_path="/b.k")
    inits = [x for x in gw.calls if x.get("method") == "initialize"]
    assert len(inits) == 1, f"핸드셰이크가 {len(inits)}번 — 세션을 재사용해야 한다"


async def test_authorization_header_is_sent():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        body = json.loads(request.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body.get("id"), "result": {}})

    c = StcxClient("http://gw.test/mcp", "pat-xyz",
                   client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await c.scenario_options()
    assert seen["auth"] == "Bearer pat-xyz"


async def test_timeout_stays_under_the_gateway_budget():
    """게이트웨이가 먼저 끊으면 우리는 그것을 전송 오류로 읽어 원인을 잘못 짚는다."""
    from app.runner.stcx_client import DEFAULT_TIMEOUT
    assert DEFAULT_TIMEOUT < 120, "GATEWAY_CALL_TIMEOUT 기본값(120초) 아래여야 한다"
