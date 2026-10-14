"""stcx 제출 래퍼 + 덱 반입 — 망 없이(MockTransport) 계약을 고정한다.

이 파일이 지키는 것 셋.

1. **인자 모양** — 직접 노출 도구는 `args` **한 겹**을 받는다(`server.py:218-219`).
   평평하게 보내면 스키마 검증에서 통째로 떨어진다.
2. **도구 이름** — 게이트웨이는 접두사 붙은 별칭을 언제나 등록하지만 그것은 **호출 전용**
   이라 `tools/list` 에는 안 보인다(`gateway.py:718-726`·`:3419`). 맨이름으로 부르면
   나중에 다른 백엔드에 같은 이름이 생기는 순간 조용히 사라진다.
3. **반입** — stcx 는 이 서버의 경로를 못 연다. 올려야 하고, 올린 이름은 `.k` 로 끝나야
   하고(`model_file_path` 패턴 `^/.+\\.k$`), 이름 앞에 잡 id 를 붙여 **잡마다 이름을 갈라야**
   한다. `job_id` 를 실으면 jobs/ 아래로 가서 받는 쪽이 그 경로를 거절한다.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.runner.stcx_client import (MAX_UPLOAD_BYTES, TOOL_DETAILS, TOOL_STATUS, TOOL_SUBMIT,
                                    StcxClient, StcxUploader)

pytestmark = pytest.mark.asyncio(loop_scope="function")

_ARGS = {"work_dir": "/data/df/01J", "lstc_license_ip": "192.168.122.1",
         "model_file_path": "/shared/uploads/jobs/01J/data/m.k", "num_angles": 162}


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

    def last_args(self) -> dict:
        """도구에 실제로 건너간 `args` 한 겹 안쪽."""
        return self.tool_calls[-1]["params"]["arguments"]["args"]


def _client(gw: _Gateway, *, token="pat-x") -> StcxClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(gw.handler))
    return StcxClient("http://gw.test/mcp", token, client=http)


# ── 인자 모양 — 이 파일의 첫 이유 ───────────────────────────────────────────
async def test_the_tool_args_go_inside_one_args_layer():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS)
    sent = gw.tool_calls[-1]["params"]["arguments"]
    assert set(sent) == {"args"}, "직접 노출 도구는 `args` 하나만 받는다 — 평평하면 다 떨어진다"
    assert sent["args"]["work_dir"] == "/data/df/01J"


async def test_submit_always_sends_dry_run_false():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS)
    assert gw.last_args()["dry_run"] is False


async def test_dry_run_true_is_honoured_when_asked():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS, dry_run=True)
    assert gw.last_args()["dry_run"] is True


async def test_nothing_is_added_to_the_mapped_args():
    """받는 쪽이 `additionalProperties: False` 다 — 한 칸만 더해도 제출이 통째로 거절된다."""
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS)
    assert set(gw.last_args()) == set(_ARGS) | {"dry_run"}


# ── 도구 이름 ───────────────────────────────────────────────────────────────
async def test_calls_the_prefixed_alias_not_the_bare_name():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS)
    name = gw.tool_calls[-1]["params"]["name"]
    assert name == TOOL_SUBMIT == "smarttwinmcp_fullangle_drop_simulation"
    assert name != "fullangle_drop_simulation", "맨이름은 충돌이 생기는 순간 조용히 사라진다"


async def test_status_and_details_use_their_own_aliases():
    gw = _Gateway()
    c = _client(gw)
    await c.job_status(12)
    assert gw.tool_calls[-1]["params"]["name"] == TOOL_STATUS
    await c.job_details(12)
    assert gw.tool_calls[-1]["params"]["name"] == TOOL_DETAILS


# ── 지목 ───────────────────────────────────────────────────────────────────
async def test_registry_id_wins_and_only_one_locator_is_sent():
    """둘 다 실으면 어긋났을 때 어느 쪽이 이겼는지 모르는 상태가 된다."""
    gw = _Gateway()
    c = _client(gw)
    await c.job_status(12, work_dir="/w")
    assert gw.last_args() == {"registry_id": 12}


async def test_work_dir_is_the_fallback_when_the_registry_id_is_unknown():
    gw = _Gateway()
    c = _client(gw)
    await c.job_status(work_dir="/data/df/01J")
    assert gw.last_args() == {"work_dir": "/data/df/01J"}


# ── 실패를 실패로 낸다 ──────────────────────────────────────────────────────
async def test_gateway_down_is_an_error_not_an_exception():
    r = await _client(_Gateway(boom=True)).submit_fullangle_drop(_ARGS)
    assert r["ok"] is False and r["error"] == "transport_error"


async def test_http_error_is_surfaced():
    r = await _client(_Gateway(status=503)).submit_fullangle_drop(_ARGS)
    assert r["ok"] is False and r["error"] == "http_503"


async def test_tool_error_is_not_a_success():
    gw = _Gateway(is_error=True, tool_result={"detail": "model not found"})
    r = await _client(gw).submit_fullangle_drop(_ARGS)
    assert r["ok"] is False and r["error"] == "tool_error"


async def test_without_a_pat_nothing_is_called():
    """꺼져 있는 것을 조용한 성공으로 바꾸지 않는다 — 제출된 줄 알고 기다리게 된다."""
    gw = _Gateway()
    c = _client(gw, token="")
    assert c.available is False
    r = await c.submit_fullangle_drop(_ARGS)
    assert r["ok"] is False and r["error"] == "unavailable"
    assert gw.calls == []


# ── 전송 세부 ───────────────────────────────────────────────────────────────
async def test_sse_responses_decode_too():
    """서버가 어느 형식으로 답할지는 요청마다 다르다 — 한쪽만 읽으면 간헐적으로 깨진다."""
    gw = _Gateway(sse=True, tool_result={"ok": True, "result": {"ok": True, "registry_id": 9}})
    r = await _client(gw).submit_fullangle_drop(_ARGS)
    assert r["ok"] and r["result"]["result"]["registry_id"] == 9


async def test_handshake_happens_once_across_calls():
    gw = _Gateway()
    c = _client(gw)
    await c.submit_fullangle_drop(_ARGS)
    await c.job_status(1)
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
    await c.job_status(1)
    assert seen["auth"] == "Bearer pat-xyz"


async def test_timeout_stays_under_the_gateway_budget():
    """게이트웨이가 먼저 끊으면 우리는 그것을 전송 오류로 읽어 원인을 잘못 짚는다."""
    from app.runner.stcx_client import DEFAULT_TIMEOUT
    assert DEFAULT_TIMEOUT < 120, "GATEWAY_CALL_TIMEOUT 기본값(120초) 아래여야 한다"


# ══ 반입 ══════════════════════════════════════════════════════════════════
# 받는 쪽은 Flask 다 — init·complete 는 JSON, chunk 는 **multipart** 다.
# 필드 이름을 `file_upload_api.py` 에서 읽어 맞췄고, 여기서 고정한다.

def _form(body: bytes, name: str) -> str | None:
    m = re.search(rb'name="' + name.encode() + rb'"(?:[^\r\n]*)\r?\n\r?\n(.*?)\r?\n--',
                  body, re.S)
    return m.group(1).decode() if m else None


class _Dashboard:
    """stcx 대시보드(:5010) 대역."""

    def __init__(self, *, chunk_size=8, file_path=None, chunk_status=200,
                 init_status=201, complete_status=200, init_body=None, flaky_429=0,
                 delete_status=200):
        self.chunk_size = chunk_size
        self.file_path = file_path
        self.chunk_status, self.init_status = chunk_status, init_status
        self.complete_status = complete_status
        self.init_body = init_body
        self.flaky_429 = flaky_429
        self.delete_status = delete_status
        self.deleted: list[str] = []
        self.steps: list[str] = []
        self.init_payload: dict = {}
        self.chunks: dict[int, bytes] = {}
        self.chunk_names: set[str] = set()
        self.checksums: dict[int, str] = {}
        self.attempts = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "DELETE" and path.startswith("/api/v2/files/uploads/"):
            self.steps.append("delete")
            self.deleted.append(path.rsplit("/", 1)[-1])
            if self.delete_status >= 400:
                return httpx.Response(self.delete_status, json={"error": "nope"})
            return httpx.Response(200, json={"message": "Upload cancelled successfully",
                                             "upload_id": self.deleted[-1]})
        if path.endswith("/upload/init"):
            self.steps.append("init")
            self.init_payload = json.loads(request.content)
            if self.init_status >= 400:
                return httpx.Response(self.init_status, json={"error": "nope"})
            size = int(self.init_payload["file_size"])
            total = (size + self.chunk_size - 1) // self.chunk_size
            body = self.init_body if self.init_body is not None else {
                "upload_id": "up-1", "chunk_size": self.chunk_size, "total_chunks": total,
                "storage_path": "/shared/uploads/users/admin/data", "file_info": {"type": "data"}}
            return httpx.Response(self.init_status, json=body)

        if path.endswith("/upload/chunk"):
            self.steps.append("chunk")
            self.attempts += 1
            if self.flaky_429 > 0:
                self.flaky_429 -= 1
                return httpx.Response(429, text="rate limited")
            if self.chunk_status >= 400:
                return httpx.Response(self.chunk_status, text="nope")
            raw = request.content
            index = int(_form(raw, "chunk_index"))
            self.checksums[index] = _form(raw, "checksum") or ""
            m = re.search(rb'name="chunk"; filename="([^"]+)"\r?\n'
                          rb'(?:[^\r\n]+\r?\n)*\r?\n(.*?)\r?\n--', raw, re.S)
            self.chunk_names.add(m.group(1).decode())
            self.chunks[index] = m.group(2)
            return httpx.Response(200, json={"message": "ok", "uploaded_chunks": index + 1,
                                             "total_chunks": len(self.chunks), "progress": 1.0})

        if path.endswith("/upload/complete"):
            self.steps.append("complete")
            if self.complete_status >= 400:
                return httpx.Response(self.complete_status, json={"error": "nope"})
            name = self.init_payload.get("filename", "m.k")
            # 받는 쪽 그대로 — `job_id` 가 있으면 jobs/ 아래, 없으면 사용자 폴더(SSO 꺼짐 → admin)
            jid = self.init_payload.get("job_id")
            fp = self.file_path or (f"/shared/uploads/jobs/{jid}/data/{name}" if jid
                                    else f"/shared/uploads/users/admin/data/{name}")
            return httpx.Response(200, json={"message": "ok", "file_path": fp,
                                             "file_info": {"type": "data"}})

        return httpx.Response(404, text="?")

    def merged(self) -> bytes:
        return b"".join(self.chunks[i] for i in sorted(self.chunks))


def _uploader(dash: _Dashboard, *, base="http://stcx.test") -> StcxUploader:
    return StcxUploader(base, client=httpx.AsyncClient(transport=httpx.MockTransport(dash.handler)))


async def test_the_three_steps_happen_in_order_and_the_bytes_arrive_whole(tmp_path):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"*KEYWORD\n*NODE\n*END\n")
    dash = _Dashboard(chunk_size=8)
    got = await _uploader(dash).upload(deck, job_id="01JOB")
    assert got["ok"], got
    assert dash.steps[0] == "init" and dash.steps[-1] == "complete"
    assert dash.steps.count("chunk") == got["chunks"] == 3     # 20바이트 / 8
    assert dash.merged() == deck.read_bytes(), "조각을 다시 이어 붙이면 원본이어야 한다"


async def test_the_job_id_goes_into_the_name_not_the_init_so_the_path_stays_readable(tmp_path):
    """★`job_id` 를 실으면 `/shared/uploads/jobs/<id>/` 에 저장되고 fullangle 1.1.2 가 그
    경로를 **허용 범위 밖** 이라 거절한다(`stmc_exec.py:76`·`:204`). 그런데 빼기만 하면 SSO 가
    꺼져 모든 요청이 `admin` 이라 같은 이름의 덱이 `users/admin/data/` 한 자리에서 **서로를
    덮는다** — 그래서 이름에 잡 id 를 넣는다."""
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x" * 5)
    dash = _Dashboard()
    got = await _uploader(dash).upload(deck, job_id="01JOB")
    assert "job_id" not in dash.init_payload
    assert dash.init_payload["filename"] == "01JOB_model.k"
    assert got["file_path"] == "/shared/uploads/users/admin/data/01JOB_model.k"


async def test_two_jobs_with_the_same_deck_name_land_on_different_paths(tmp_path):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x" * 5)
    a = await _uploader(_Dashboard()).upload(deck, job_id="01AAA")
    b = await _uploader(_Dashboard()).upload(deck, job_id="01BBB")
    assert a["ok"] and b["ok"]
    assert a["file_path"] != b["file_path"]


async def test_the_chunk_fields_are_the_ones_the_server_reads(tmp_path):
    """`upload_id` · `chunk_index`(0부터) · 파일 `chunk` · `checksum`(MD5)."""
    import hashlib
    deck = tmp_path / "model.k"
    deck.write_bytes(b"abcdefghij")
    dash = _Dashboard(chunk_size=4)
    await _uploader(dash).upload(deck, job_id="j")
    assert sorted(dash.chunks) == [0, 1, 2]
    assert dash.chunks[0] == b"abcd"
    assert dash.checksums[0] == hashlib.md5(b"abcd").hexdigest()


@pytest.mark.parametrize("given,sent", [
    ("model.key", "j_model.k"), ("model.dyn", "j_model.k"), ("model.k", "j_model.k"),
])
async def test_the_deck_is_renamed_to_dot_k_on_the_way_up(tmp_path, given, sent):
    """받는 쪽 패턴이 `^/.+\\.k$` 다. **원본 파일은 건드리지 않는다.**"""
    deck = tmp_path / given
    deck.write_bytes(b"x" * 3)
    dash = _Dashboard()
    await _uploader(dash).upload(deck, job_id="j")
    assert dash.init_payload["filename"] == sent
    assert dash.chunk_names == {sent}
    assert deck.exists() and deck.name == given, "원본 이름이 바뀌면 세션이 깨진다"


async def test_a_file_path_that_is_not_a_dot_k_absolute_path_is_refused(tmp_path):
    """제출이 거절되고 나서 되짚는 것보다 반입 단계에서 말하는 편이 훨씬 싸다."""
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x")
    dash = _Dashboard(file_path="relative/m.k")
    got = await _uploader(dash).upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "bad_file_path"


async def test_a_rate_limited_chunk_is_retried(tmp_path, monkeypatch):
    """분당 2000 청크 제한에 걸릴 수 있다. 재전송은 안전하다 —
    `complete` 가 인덱스별 파일 존재를 다시 확인한다."""
    import app.runner.stcx_client as mod
    monkeypatch.setattr(mod, "_CHUNK_BACKOFF_S", 0.0)
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x" * 3)
    dash = _Dashboard(flaky_429=1)
    got = await _uploader(dash).upload(deck, job_id="j")
    assert got["ok"] and dash.attempts == 2


async def test_a_chunk_that_keeps_failing_is_a_failure_not_a_silent_success(tmp_path,
                                                                           monkeypatch):
    import app.runner.stcx_client as mod
    monkeypatch.setattr(mod, "_CHUNK_BACKOFF_S", 0.0)
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x" * 3)
    dash = _Dashboard(chunk_status=500)
    got = await _uploader(dash).upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "http_500"
    assert "complete" not in dash.steps, "조각이 다 안 올라갔는데 완료를 부르면 안 된다"


async def test_an_oversized_deck_is_refused_before_any_request(tmp_path, monkeypatch):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x" * 10)
    dash = _Dashboard()
    import app.runner.stcx_client as mod
    monkeypatch.setattr(mod, "MAX_UPLOAD_BYTES", 5)
    got = await _uploader(dash).upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "too_large"
    assert dash.steps == [], "상한을 넘는 것은 한 바이트도 보내지 않는다"


async def test_an_empty_deck_is_refused(tmp_path):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"")
    got = await _uploader(_Dashboard()).upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "empty_model"


async def test_a_missing_deck_is_an_error_not_an_exception(tmp_path):
    got = await _uploader(_Dashboard()).upload(tmp_path / "nope.k", job_id="j")
    assert got["ok"] is False and got["error"] == "unreadable_model"


async def test_a_nonsense_init_reply_stops_the_upload(tmp_path):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x")
    dash = _Dashboard(init_body={"upload_id": "", "chunk_size": 0, "total_chunks": 0})
    got = await _uploader(dash).upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "bad_init_reply"
    assert dash.steps == ["init"]


async def test_without_a_backend_url_nothing_is_called(tmp_path):
    deck = tmp_path / "model.k"
    deck.write_bytes(b"x")
    dash = _Dashboard()
    got = await _uploader(dash, base="").upload(deck, job_id="j")
    assert got["ok"] is False and got["error"] == "unavailable"
    assert dash.steps == []


async def test_delete_calls_the_cancel_route_with_the_upload_id():
    """`DELETE /api/v2/files/uploads/<upload_id>` — 받는 쪽 `cancel_upload` 그대로."""
    dash = _Dashboard()
    got = await _uploader(dash).delete("up-1")
    assert got == {"ok": True}
    assert dash.deleted == ["up-1"]


async def test_a_refused_delete_is_an_error_not_an_exception():
    dash = _Dashboard(delete_status=403)
    got = await _uploader(dash).delete("up-1")
    assert got["ok"] is False and got["error"] == "http_403"


@pytest.mark.parametrize("base,upload_id", [("", "up-1"), ("http://stcx.test", "")])
async def test_delete_without_a_url_or_an_id_calls_nothing(base, upload_id):
    dash = _Dashboard()
    got = await _uploader(dash, base=base).delete(upload_id)
    assert got["ok"] is False and got["error"] == "unavailable"
    assert dash.steps == []


async def test_the_size_cap_matches_the_server():
    assert MAX_UPLOAD_BYTES == 50 * 1024 * 1024 * 1024
