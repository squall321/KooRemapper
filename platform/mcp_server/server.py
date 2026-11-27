"""KooRemapper MCP 서버 — Claude 가 K파일 세션을 관리하고 메쉬/해석 오퍼레이션을
실행·다운로드하게 하는 도구. (op 개수는 카탈로그 단일 소스에서 동적으로 결정된다.)

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
import contextvars
import functools
import hashlib
import json
import os
import sys
import time
from typing import Annotated, Any, Literal  # noqa: F401 — Literal 은 닫힌 어휘 인자(계약 C3)
from urllib.parse import quote

import httpx
try:                    # SDK 2.x — 2026-07-28 새 세대(initialize 없는 POST 하나)와 옛 세대(initialize)를 같은 자리에서 받는다
    from mcp.server.mcpserver import Context, Image, MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    SDK2 = True
except ImportError:     # SDK 1.x — 시험 · 스모크 venv(옛 세대 클라이언트)와 옛 mcp.sif. 둘 다 같은 server.py 로 돈다
    from mcp.server.fastmcp import Context, FastMCP as MCPServer, Image
    from mcp.server.fastmcp.exceptions import ToolError
    SDK2 = False
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, create_model, model_serializer, model_validator

from figure_png import FigurePngError, rasterize

API_BASE = os.environ.get("KOOREMAPPER_API_BASE", "http://127.0.0.1:8700").rstrip("/")
API = f"{API_BASE}/api/v1"

# MCP serverInfo.name — 포탈/HEAX 카탈로그와 통일한 브랜드 표시명.
# (라우트 슬러그·URL 은 여전히 kooremapper 로 유지된다.)
# stateless(포털 MCP 현대화 1단계 · 사용자 결정 11-27) — 서버가 세션을 쥐지 않는다. 요청마다 새 전송을 열어 답하고 닫으므로 Mcp-Session-Id 를
# 내지도 보지도 않고, initialize 없이 온 호출 · 재기동 전의 세션 번호를 단 호출도 받는다. 서버 → 클라이언트 채널(elicit · sampling ·
# list_changed · roots)은 버려지는데 이 서버는 쓰지 않는다 — ctx 는 들어온 HTTP 요청의 머리(_forward_headers)만 읽는다. 응답은 SSE 그대로라
# 같은 요청의 진행 알림은 간다. 시험 `tests/test_mcp_tools_contract.py` 의 stateless 절. 1.x 는 생성자에서, 2.x 는 기동(http_options)에서 켠다.
STATELESS_HTTP = True
# 요청 본문 상한 — 1.x 는 상한이 없었다. 2.x 기본(4 MiB)이면 덱을 본문에 싣는 upload_kfile 이 큰 덱에서 막힌다. 앞단 nginx 의
# client_max_body_size(1g)와 같게 둔다 — 파일 하나의 실제 상한은 백엔드 KOORM_MAX_UPLOAD_MB(기본 512)가 건다.
MAX_REQUEST_BODY_BYTES = 1 << 30
mcp = MCPServer("DynaForge") if SDK2 else MCPServer("DynaForge", stateless_http=STATELESS_HTTP)


def http_options(security=None) -> dict:
    """2.x streamable-http 앱 선택지 — 기동(__main__)과 탐침(tests/mcp_probe.py stateless)이 같은 것을 쓴다. 1.x 는 생성자 · settings 로 준다."""
    if not SDK2:
        return {}
    return {"stateless_http": STATELESS_HTTP, "json_response": False, "transport_security": security,
            "max_request_body_size": MAX_REQUEST_BODY_BYTES}

# ── 시간 한도 — 손잡이 하나 · 도구 호출 하나에 벽시계 기한 하나(포털 time-limits 1-1, 사용자 결정 10-31) ──────────────────
# ★바깥 층(게이트웨이가 도구 호출을 기다리는 600초 — 그쪽 `GATEWAY_CALL_TIMEOUT`)보다 안쪽이어야 이 층이 먼저 걸려 값과 손잡이
#   이름이 든 문구가 나온다. 바깥이 먼저 끊으면 「답하지 않았다」 만 남고 백엔드 일은 계속 돈다(포털 D-17 층 규칙). 업로드 ·
#   내려받기 · 반입도 이 값이다(예전엔 60 · 120 · 180 · 300 이 열여덟 곳에 글자로 박혀 있었다). 더 긴 일은 잡(제출 + 상태 조회)으로 간다.
GATEWAY_CALL_TIMEOUT_S = 600
API_TIMEOUT_KNOB = "KOORM_MCP_API_TIMEOUT_S"
API_TIMEOUT_S = float(os.environ.get(API_TIMEOUT_KNOB) or 540)
if not 0 < API_TIMEOUT_S < GATEWAY_CALL_TIMEOUT_S:
    print(f"⚠ {API_TIMEOUT_KNOB}={API_TIMEOUT_S:g} 는 0 과 게이트웨이 한도 {GATEWAY_CALL_TIMEOUT_S}초 사이가 아니다 — 540 으로 둔다",
          file=sys.stderr)
    API_TIMEOUT_S = 540.0
_DEADLINE: contextvars.ContextVar[float | None] = contextvars.ContextVar("koorm_mcp_deadline", default=None)


class _Late(RuntimeError):
    """이 도구 호출의 기한이 다 됐다 — 문구에 값과 손잡이 이름이 있다. 그림 기다림은 이것을 잡아 job_id 를 함께 말한다."""


def _late() -> _Late:
    return _Late(f"DynaForge 백엔드가 이 도구 호출의 기한 {API_TIMEOUT_S:g}초 안에 답하지 않았다({API_TIMEOUT_KNOB}) — "
                 "오래 걸리는 일은 잡(run_operation → get_job)으로 하라")


def _left() -> float:
    """이 도구 호출에 남은 초. 다 됐으면 다음 요청을 내지 않고 손잡이 이름이 든 문구로 멈춘다."""
    deadline = _DEADLINE.get()
    left = API_TIMEOUT_S if deadline is None else deadline - time.monotonic()
    if left <= 0:
        raise _late()
    return left


def _client() -> httpx.AsyncClient:
    """백엔드 REST 클라이언트 — 기다림은 이 도구 호출에 남은 시간만큼이다(요청마다 새로 재지 않는다)."""
    return httpx.AsyncClient(base_url=API, timeout=_left())


_register = mcp.tool


def _bounded_tool(*args, **kwargs):
    """`mcp.tool()` 과 같되 도구 호출 하나에 벽시계 기한 하나를 건다 — REST 를 여러 번 부르는 도구(compare_reports · 그림 잡
    기다림)도 합쳐서 그 안이다. httpx 시간 초과는 값과 손잡이 이름이 든 문구로 바꾼다. 끊긴 요청은 다시 보내지 않는다(쓰기가 두 번
    나갈 수 있다). 인자 꼴은 그대로다(FastMCP 는 `__wrapped__` 의 서명으로 스키마를 만든다). 도구가 다른 도구를 부르면 바깥 기한을 쓴다.

    도구 밖으로 나가는 예외는 ToolError 로 바꾼다(포털 공통 계약 P3) — 2.x 는 ToolError 가 아닌 예외의 글을 서버에 남기고 모델에는
    「Error executing tool <이름>」 만 보낸다. 1.x 는 어느 예외든 「Error executing tool <이름>: <글>」 이라 글이 그대로다. 바꾸기는 몸통
    밖에서만 하므로 몸통이 _Late 를 잡아 job_id 를 덧붙이는 그림 기다림(_run_figure_job)은 그대로다."""
    register = _register(*args, **kwargs)

    def deco(fn):
        @functools.wraps(fn)
        async def bounded(*a, **kw):
            mine = time.monotonic() + API_TIMEOUT_S
            outer = _DEADLINE.get()
            token = _DEADLINE.set(min(outer, mine) if outer is not None else mine)
            try:
                try:
                    return await fn(*a, **kw)
                except httpx.TimeoutException:
                    raise _late() from None
            except Exception as exc:
                if isinstance(exc, ToolError):
                    raise
                raise ToolError(str(exc)) from exc
            finally:
                _DEADLINE.reset(token)
        return register(bounded)
    return deco


mcp.tool = _bounded_tool

# ── 읽기 · 쓰기 표지(포털 공통 계약 C6) — 도구마다 `@mcp.tool(annotations=…)` 로 하나를 고른다 ─────────────────────────────
# 바꾸는 도구는 덮는지(destructive) · 같은 호출을 거듭해도 같은지(idempotent)를 함께 말한다. openWorld 는 DynaForge 백엔드 · DB 밖(DataHub ·
# stcx 클러스터 · StepForge · 이 박스의 세션 밖 파일)에 닿는지다 — 우리 백엔드만 부르면 닫힌 세계다.
_READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
_READ_OUT = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)
_ADD = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)   # 새 세션 · 잡 · 파일 · 행
_ADD_OUT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
_SET = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)     # 덮어쓰기 — 같은 값이면 같다
_SET_OUT = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)
_DELETE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
_REPLACE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)  # 덮되 부를 때마다 새 파일


# ── 결과 꼴(공통 계약 C7) — 반환 타입으로 적으면 FastMCP 가 칸 이름 · 뜻이 든 outputSchema 와 structuredContent 를 낸다 ──────────
# 칸 형은 Any 로 둔다 — 백엔드 값이 그대로 지나가고 출력 검증이 실제 값에 걸리지 않는다. 적지 않은 칸도 싣고(extra allow), 백엔드가 보내지
# 않은 칸을 null 로 지어 넣지 않는다(_as_sent). 꼴과 다른 값(목록 · null)이 오면 value 칸에 그대로 싣는다 — 꼴을 잘못 적어도 도구는 산다.
# 1.x FastMCP 는 구조 결과가 있으면 같은 내용을 글(content)로도 낸다.
class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _not_a_dict(cls, v):
        return v if isinstance(v, dict) else {"value": v}

    @model_serializer(mode="wrap")
    def _as_sent(self, handler):
        d = handler(self)
        keep = self.model_fields_set | set(self.model_extra or {})
        return {k: v for k, v in d.items() if k in keep}


def _shape(name: str, fields: dict[str, str]) -> type[_Out]:
    """결과 꼴 — `{칸 이름: 뜻}` 만 적는다. 목록을 돌려주는 도구는 `-> list[행 꼴]`(FastMCP 가 `{"result": [...]}` 로 감싼다)."""
    return create_model(name, __base__=_Out, **{k: (Any, Field(None, description=v)) for k, v in fields.items()})

# ── 인자 설명(포털 arg-descriptions §2-3, 사용자 결정 10-31) — 게이트웨이가 세는 것은 inputSchema 맨 위 인자의 description 이다 ─────
# 허용값 · 상한 · 단위는 손으로 옮겨 적지 않는다 — 아래 상수에서 만든다. 이 값이 백엔드의 실제 제약(GET /reports 의 Query 패턴 ·
# 상한 · 높이 허용차, 세션 이름 길이, 심각도 순위, 단위 관례)과 같은지는 백엔드 시험 `tests/test_mcp_tools_contract.py` 가 대조한다
# (MCP 는 백엔드를 import 하지 않는다). ★같은 이름의 인자라도 도구마다 뜻이 다르면 문구를 따로 쓴다 — find_reports 의 severity 는
# 「이 심각도 이상」, report_findings 의 severity 는 「같은 것만」 이다.
REPORT_KINDS = ("deep", "sphere", "impact")
DEV_REV_CODES = ("pre", "dv1", "dv2", "dv3", "dvr", "pv1", "pv2", "pv3", "pvr", "pra", "mp")  # 개발 단계(datahub.parse_stage)
SEVERITIES = ("CRITICAL", "WARNING", "INFO")            # 높은 것부터
FIND_SORTS = ("created_at", "worst_stress", "worst_g", "drop_height")
SORT_ORDERS = ("asc", "desc")
FIND_LIMIT_MAX = 500
HEIGHT_TOL_MM = 1.0
SESSION_NAME_MAX = 255
UNIT_STRESS, UNIT_ACCEL, UNIT_LENGTH = "MPa", "G", "mm"   # SmartTwin ton-mm-s 관례


def _one_of(values) -> str:
    return " · ".join(values)


_A_SESSION_ID = "세션 id — create_session 응답의 id · list_sessions 의 id."
_A_REPORT_ID = "리포트 id — find_reports 의 items[].id · ingest_report 응답의 id."
_A_PART_ID_OPT = "파트 번호(LS-DYNA PID) — report_summary 의 parts[].part_id. 비우면 모든 파트."
_A_FACET = "report_facets 가 주는 값 그대로(같은 것만 걸린다)."


def _forward_headers(ctx: Context) -> dict:
    headers: dict[str, str] = {}
    req = getattr(getattr(ctx, "request_context", None), "request", None)
    if req is not None:
        v = req.headers.get("authorization")
        if v:
            headers["Authorization"] = v
        # 소속 헤더 둘은 그대로 나르기만 한다 — 검증(서명·이메일 결속·만료)은 백엔드가 한다.
        # 요청서 platform/docs/REQUEST-postprocess-operation.md §8(2026-09-18 개정).
        for h in ("x-heax-user-affiliation", "x-heax-aff-proof"):
            hv = req.headers.get(h)
            if hv:
                headers[h] = hv
    return headers


def _seg(value) -> str:
    """사용자 값을 경로 칸 **하나**로 — `quote(…, safe='')` 에 칸 전체가 `.`·`..` 인 것까지 감싼다(httpx 가 점 칸을 접는다).

    감싸지 않으면 `ID?` 가 `DELETE /api/v1/reports/ID`(리포트 지우기)로, `#` 은 뒤를 잘라 다른 길로 간다(검토 반영 11-11). 경로에
    들어가는 사용자 값(리포트 · 세션 · 잡 · 레시피 · 케이스 …)은 모두 이것을 지난다 — `tests/test_mcp_tools_contract.py` 가 f-문자열
    경로를 훑어 못박는다. ★`/` · `\\` 가 든 값은 **거절한다**(ValueError — 보내지 않는다). 감싸도 백엔드(uvicorn)가 `%2F` 를 `/` 로
    풀어 그 길로 라우팅한다(재검토 11-12 rr4 — `delete_report(id+'/revision')` 가 끊기 라우트로 갔다). 리포트 · 세션 · 잡 · 파일 id 에는
    이 글자가 없다. `/` 가 들 수 있는 과제명 · 객체 key 만 `_seg_key` 를 쓴다(받는 라우트가 `{…:path}`).
    """
    s = str(value)
    if "/" in s or "\\" in s:
        raise ValueError(f"경로 값에 '/' · '\\' 를 쓸 수 없다(id 에는 없는 글자다): {s!r}")
    return _seg_key(s)


def _seg_key(value) -> str:
    """과제명 · 객체 key — `/` 가 들 수 있다(허브의 과제명). 받는 라우트가 `{…:path}` 라 백엔드가 `%2F` 를 풀어도 같은 라우트가
    통째로 받는다. 감싸기는 `_seg` 와 같다(점 칸 포함). `task_revisions` · `compare_task_revisions` · `ontology_object` 의 key 밖에
    쓰지 않는다(다른 칸에 쓰면 `/` 가 다른 라우트로 샌다 — 시험이 못박는다)."""
    s = quote(str(value), safe="")
    return s.replace(".", "%2E") if s in (".", "..") else s


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
    async with _client() as c:
        return _unwrap(await c.get(path, params=params, headers=_forward_headers(ctx)))


async def _post(ctx, path, json_body=None):
    async with _client() as c:
        return _unwrap(await c.post(path, json=json_body, headers=_forward_headers(ctx)))


async def _put(ctx, path, json_body=None):
    async with _client() as c:
        return _unwrap(await c.put(path, json=json_body, headers=_forward_headers(ctx)))


async def _delete(ctx, path, params=None):
    # ⚠쿼리를 **문자열로 이어 붙이지 않는다** — 값에 공백·`&`·`=` 가 들어오면 조용히
    #   다른 요청이 된다(별칭은 사람이 쓰는 자유 문자열이라 그런 글자가 들어온다).
    async with _client() as c:
        return _unwrap(await c.delete(path, params=params, headers=_forward_headers(ctx)))


# ── 오퍼레이션 카탈로그 ──────────────────────────────────────────────
# 카탈로그 · 세션 · 파일 · 잡 도구의 인자 설명과 결과 꼴(계약 C2 · C7) — 칸 이름은 백엔드 응답(카탈로그 항목 · UserRead · SessionRead ·
# FileRead · JobRead · /system/status)에서 그대로 옮겼다. 세션 · 파일 · 잡 칸은 여러 도구가 함께 쓴다.
_A_CORE_FILE_ID = "세션 파일 id(정수) — get_session 의 files[].id · list_session_files 의 id · get_job_outputs 의 id."
_A_CORE_JOB_ID = "잡 id — run_operation 응답의 id · list_session_jobs 의 id."
_CORE_SESSION_FIELDS = {
    "id": "세션 id — 다른 도구의 session_id.",
    "name": "세션 이름.",
    "description": "세션 설명(없으면 null).",
    "status": "active · archived.",
    "visibility": "공개 범위 — company · department · team · private(만들 때 private).",
    "deck_revision_label": "덱 판 라벨(없으면 null).",
    "linked_cad": "연결된 StepForge 과제 {project_id, revision}(없으면 null).",
    "task_key": "허브 과제명(자동 파이프라인의 과제 — 없으면 null).",
    "dev_rev": "개발 단계 — pre · dv1 … · pv1 … · pra · mp(없으면 null).",
    "created_at": "만든 시각(ISO 8601).",
    "updated_at": "마지막으로 고친 시각(ISO 8601).",
    "file_count": "파일 수 — 목록 · 상세에서만 채운다(만들기 · 고치기 응답은 null).",
    "environment": "이 플랫폼의 환경 — dev · prod · unknown.",
    "revision_warning": "덱 판 라벨과 연결된 CAD 판이 다르면 경고 글(같거나 한쪽이 없으면 null).",
}
_CORE_FILE_FIELDS = {
    "id": "세션 파일 id — inspect_file · download_result · save_result_to_path · delete_file 의 file_id.",
    "session_id": "세션 id.",
    "filename": "세션 안 파일 이름(하위 경로 포함 — 예 sub/part.k).",
    "kind": "input(올린 것) · output(잡 산출물) · generated(서버가 만든 것).",
    "origin_job_id": "만든 잡 id(올린 파일은 null).",
    "size_bytes": "크기(바이트).",
    "sha256": "내용 지문(16진 64자).",
    "meta": "업로드 때 잰 메타 — 덱이면 nodes · elements · parts · bbox_min · bbox_max · includes · part_titles(앞 50개) · "
            "keyword_counts · modelmeta 등, 덱이 아니면 {filename} 만, 재지 않은 파일은 null.",
    "created_at": "만든 시각(ISO 8601).",
}
_CORE_JOB_FIELDS = {
    "id": "잡 id — get_job · cancel_job · get_job_outputs 의 job_id.",
    "session_id": "세션 id.",
    "operation": "오퍼레이션 이름.",
    "args": "제출한 인자.",
    "resolved_cmd": "실제로 돈 명령 · 설정(아직 안 돌았으면 null).",
    "status": "queued · running · succeeded · failed · canceled.",
    "progress": "진행률 0~100(도는 동안은 출력의 마지막 NN% 표지 · 모르면 null).",
    "exit_code": "종료 코드(끝나기 전 null).",
    "input_file_ids": "입력 파일 id 목록(비어 있을 수 있다).",
    "output_file_ids": "산출 파일 id 목록 — 이름 · meta 는 get_job_outputs.",
    "error_summary": "실패 까닭 요약(없으면 null).",
    "warnings": "경고 글 목록 — 덱이 정의되지 않은 세트 · 파트 · 재질 · 절점을 가리킨다 등(없으면 null).",
    "created_at": "제출 시각(ISO 8601).",
    "started_at": "시작 시각(ISO 8601 · 대기 중이면 null).",
    "finished_at": "끝난 시각(ISO 8601 · 끝나기 전 null).",
    "external": "외부 잡(stcx 제출 · 후처리 예약)의 요약 {kind, cluster_state, ontology: {state, why?}, images?} — 로컬 잡은 null.",
}
_CORE_MESSAGE_FIELD = {"message": "백엔드가 돌려준 결과 문구."}
ListOperationsRow = _shape("ListOperationsRow", {
    "name": "오퍼레이션 이름 — describe_operation · run_operation 의 operation.",
    "category": "분류(목록은 분류 · 이름 순).",
    "summary": "한 줄 요약.",
    "invocation": "positional · yaml(이 서버의 바이너리) · external(다른 클러스터에서 돈다).",
    "takes_kfile": "K파일 입력을 받는가.",
    "requires_gmsh": "gmsh 가 필요한가(서버에 없으면 run_operation 이 422).",
    "requires_tetgen": "tetgen 이 필요한가.",
})
DescribeOperationOut = _shape("DescribeOperationOut", {
    "name": "오퍼레이션 이름.",
    "category": "분류.",
    "summary": "한 줄 요약.",
    "description": "자세한 설명.",
    "invocation": "positional · yaml · external.",
    "config_style": "yaml 설정 꼴 — null · structured · freeform.",
    "takes_kfile": "K파일 입력을 받는가.",
    "requires_gmsh": "gmsh 가 필요한가.",
    "requires_tetgen": "tetgen 이 필요한가.",
    "params": "인자 정의 목록 [{name, type, role, required, description, enum?, default?, pattern?, group?}].",
    "args_schema": "run_operation 의 args 가 따를 JSON Schema {type: object, properties, required, additionalProperties}.",
    "example": "예제 {args, note}.",
    "notes": "주의 사항(글).",
    "example_folder": "예제 폴더(없을 수 있다).",
    "keys": "yaml 설정 칸 목록 [{path, type, required, desc}](yaml 오퍼레이션만).",
    "presets": "미리 정한 설정(없으면 null).",
    "alternative_invocations": "다른 호출 꼴(일부 오퍼레이션만).",
})
WhoamiOut = _shape("WhoamiOut", {
    "id": "사용자 번호.",
    "email": "이메일.",
    "display_name": "표시 이름(없으면 null).",
    "is_active": "활성 계정인가.",
    "is_system_admin": "시스템 관리자인가.",
    "created_at": "가입 시각(ISO 8601).",
})
SystemStatusOut = _shape("SystemStatusOut", {
    "version": "API 판.",
    "env": "실행 환경 이름(app_env).",
    "api": "{ok, port}.",
    "database": "{ok, port} — ok 가 false 면 DB 에 닿지 못했다(port 는 늘 null).",
    "worker": "{concurrency, queued, running} — 동시 실행 자리 · 대기 · 실행 중 잡 수(전체 사용자).",
    "binary": "{present} — KooRemapper 바이너리가 있는가.",
    "gmsh": "{available, note} — gmsh 를 쓸 수 있는가.",
    "mcp": "{port, url, url_note} — 공개 주소가 설정에 없으면 url 은 null 이고 url_note 가 까닭을 말한다.",
    "rate_limit": "{enabled} — 속도 제한이 켜져 있는가.",
    "signup": "{enabled} — 가입을 받는가.",
    "operations": "오퍼레이션 수.",
    "postprocess_versions": "최근 반입 리포트가 실어 온 후처리 판 [{name, adapter, version, n, last_at}](최근 것부터 10줄 · "
                            "null = 못 셌다 · [] = 그 기간에 없다).",
    "postprocess_versions_window_days": "postprocess_versions · observed_images 가 보는 기간(일).",
    "observed_images": "매니페스트가 관측한 SIF {post: [...], manifest_node_pre: [...]}(칸마다 10줄 · null = 못 셌다).",
})
ListSessionsRow = _shape("ListSessionsRow", _CORE_SESSION_FIELDS)
CreateSessionOut = _shape("CreateSessionOut", _CORE_SESSION_FIELDS)
GetSessionOut = _shape("GetSessionOut", {
    **_CORE_SESSION_FIELDS,
    "files": "파일 목록(id 순) [{id, session_id, filename, kind, origin_job_id, size_bytes, sha256, meta, created_at}].",
})
CoreSessionFileRow = _shape("CoreSessionFileRow", _CORE_FILE_FIELDS)
SaveResultToPathOut = _shape("SaveResultToPathOut", {
    "saved": "쓴 경로(dest_path 그대로).",
    "bytes": "쓴 바이트 수.",
})
SessionIncludesOut = _shape("SessionIncludesOut", {
    "ok": "빠진 *INCLUDE 가 없으면 true.",
    "missing_by_file": "{덱 파일명: {missing: [...], satisfied: [...]}} — 빠진 것이 있는 덱만 싣는다.",
})
InspectFileOut = _shape("InspectFileOut", {
    "filename": "세션 안 파일 이름.",
    "sha256": "내용 지문(덱 판을 가린다).",
    "meta": "업로드 때 잰 메타(캐시 — 다시 재지 않는다).",
})
RunOperationOut = _shape("RunOperationOut", _CORE_JOB_FIELDS)
GetJobOut = _shape("GetJobOut", {
    **_CORE_JOB_FIELDS,
    "logs": "include_logs=true 일 때만 — stdout · stderr 의 마지막 4000자(못 읽으면 까닭 글).",
    "logs_truncated": "include_logs=true 이고 로그를 읽었을 때만 — 4000자를 넘어 앞이 잘렸으면 true.",
    "logs_total_chars": "include_logs=true 이고 로그를 읽었을 때만 — 자르기 전 로그 전체 글자 수.",
})
CancelJobOut = _shape("CancelJobOut", _CORE_MESSAGE_FIELD)
UpdateSessionOut = _shape("UpdateSessionOut", _CORE_SESSION_FIELDS)
DeleteSessionOut = _shape("DeleteSessionOut", _CORE_MESSAGE_FIELD)
DeleteFileOut = _shape("DeleteFileOut", _CORE_MESSAGE_FIELD)


@mcp.tool(annotations=_READ)
async def list_operations(ctx: Context) -> list[ListOperationsRow]:
    """사용 가능한 오퍼레이션 전체의 요약 목록을 돌려준다 — 무엇을 할 수 있는지 처음 볼 때 쓴다.

    한 오퍼레이션의 인자 · 예제 · 주의 사항은 describe_operation, 실제 실행은 run_operation 으로 한다. 오퍼레이션은 세션 파일에 거는
    메쉬 · 덱 작업(map · contact · info 등)과 다른 클러스터와 주고받는 작업(stcx_fullangle_drop · postprocess)이다.

    반환: 행 목록(분류 · 이름 순 · 자르지 않는다) — 행마다 name · category · summary · invocation(positional · yaml 은 이 서버의
    바이너리, external 은 다른 클러스터) · takes_kfile · requires_gmsh · requires_tetgen. 개수는 카탈로그가 정한다(system_status 의
    operations 와 같다)."""
    return await _get(ctx, "/operations")


@mcp.tool(annotations=_READ)
async def describe_operation(
    operation: Annotated[str, Field(description="오퍼레이션 이름 — list_operations 의 name(예 info · map · contact). "
                                                "없는 이름이면 404 로 실패한다.")],
    ctx: Context,
) -> DescribeOperationOut:
    """오퍼레이션 하나의 상세(설명 · 인자 정의 · args JSON Schema · 예제 · 주의 사항)를 돌려준다 — run_operation 의 args 를 짜기 전에 쓴다.

    전체 목록과 이름은 list_operations 로 본다. 실행은 run_operation(session_id, operation, args) — args 는 여기 args_schema 를
    따르고, 파일 인자(x-kind session_file)는 그 세션의 파일 이름(get_session 의 files[].filename)이다.

    반환: name · category · summary · description · invocation · config_style · takes_kfile · requires_gmsh · requires_tetgen ·
    params(인자 정의 — name · type · role · required · description · enum · default · pattern · group) · args_schema(type object ·
    properties · required · additionalProperties — freeform yaml 오퍼레이션만 모르는 칸을 받는다) · example{args, note} · notes(주의
    사항) · example_folder · keys(yaml 설정 칸) · presets · alternative_invocations. 덜 쓰는 칸은 오퍼레이션마다 없을 수 있다."""
    return await _get(ctx, f"/operations/{_seg(operation)}")


# ── 세션 / 파일 ──────────────────────────────────────────────────────
@mcp.tool(annotations=_READ)
async def whoami(ctx: Context) -> WhoamiOut:
    """이 MCP 호출에 실린 토큰의 사용자 정보를 돌려준다 — 누구 권한으로 도는지 확인할 때 쓴다.

    모든 도구는 이 사용자 권한으로 백엔드를 부른다(세션 · 잡은 이 사용자 것만 고치고 지울 수 있다). 플랫폼 상태는 system_status,
    기능 범위는 system_capabilities.

    반환: id · email · display_name · is_active · is_system_admin · created_at."""
    return await _get(ctx, "/me")


@mcp.tool(annotations=_READ)
async def system_status(ctx: Context) -> SystemStatusOut:
    """플랫폼 상태(API · DB · 워커 큐 · gmsh · 바이너리 · 오퍼레이션 수)와 운영에서 도는 후처리 판 · 이미지를 돌려준다.

    장애를 의심하거나 잡이 큐에서 안 움직일 때 먼저 본다. 웹 · MCP 기능 범위와 스위치는 system_capabilities, 내 정보는 whoami.

    반환: version · env · api{ok, port} · database{ok} · worker{concurrency, queued, running} · binary{present} · gmsh{available,
    note} · mcp{port, url, url_note} · rate_limit{enabled} · signup{enabled} · operations · postprocess_versions ·
    postprocess_versions_window_days(90) · observed_images.
    · postprocess_versions — 최근 90일 외부 잡으로 반입된(external_job_key 가 있는) 리포트가 실어 온 후처리 판
      [{name(producer.tool), adapter, version, n, last_at}] — 어댑터가 다르면 다른 줄, 빈 판은 안 센다, 글은 한 줄 80자, 최근 것부터
      10줄까지. stcx 에 닿지 않고도 운영에서 어느 후처리 판이 도는지 본다(None = 못 셌다, [] = 그 기간에 그런 리포트가 없다).
    · observed_images — 같은 기간 그 리포트들의 매니페스트가 관측한 SIF(칸마다 10줄) `{post: [{sha256, version, n, nodes,
      last_at}], manifest_node_pre: [{sha256, version, kooremapper_commit, n, nodes, last_at}]}` — post 는 리포트를 만든 노드의
      후처리 SIF, manifest_node_pre 는 매니페스트를 쓴 노드에 깔려 있던 전처리 SIF(배포 상태 — 전처리가 실제로 쓴 판의 증거가
      아니다). 같은 칸에 sha256 이 여럿이면 노드마다 SIF 사본이 다르다(None = 못 셌다)."""
    return await _get(ctx, "/system/status")


@mcp.tool(annotations=_READ)
async def list_sessions(ctx: Context) -> list[ListSessionsRow]:
    """내가 볼 수 있는 세션 목록을 돌려준다 — 내 세션과 조직에 공개된(company · department · team) 남의 세션이다.

    기존 작업을 이어갈 때 먼저 찾는다. 새 작업 공간은 create_session, 세션 하나의 파일까지 보려면 get_session. 빈 목록이어도 전사에
    없다는 뜻은 아니다 — 전사 집계는 corpus_summary.

    반환: 행 목록(최근 수정 순) — 행마다 id · name · description · status(active · archived) · visibility · deck_revision_label ·
    linked_cad · created_at · updated_at · file_count · environment · revision_warning. 남의 공개 세션은 읽기만 된다(올리기 ·
    실행 · 고치기 · 지우기는 주인만).

    한계: 최근 수정 순 앞 200개만 온다(백엔드 기본 상한 — 이 도구는 쪽 넘김을 주지 않는다). 200개가 꽉 차 오면 뒤가 잘렸을 수 있다."""
    return await _get(ctx, "/sessions")


@mcp.tool(annotations=_ADD)
async def create_session(
    name: Annotated[str, Field(description=f"세션 이름(1~{SESSION_NAME_MAX}자) — 사람이 알아보는 이름.")],
    ctx: Context,
    description: Annotated[str | None, Field(description="세션 설명(선택) — 무엇을 하는 세션인지 한 줄.")] = None,
) -> CreateSessionOut:
    """새 세션(작업 공간)을 만든다 — K파일 업로드 · 오퍼레이션 실행을 담는 그릇이라 새 작업의 첫 도구다.

    기존 작업을 이어가려면 list_sessions 로 먼저 찾는다(같은 이름으로 또 만들면 세션이 하나 더 생긴다). 만든 뒤 upload_kfile ·
    upload_local_path 로 덱을 올리고 run_operation 으로 돌린다. 이름 · 설명은 update_session 으로 바꾼다.

    반환: 만든 세션 — id(이후 도구의 session_id) · name · description · status(active) · visibility(private — 나만 본다) ·
    deck_revision_label · linked_cad · created_at · updated_at · environment · revision_warning."""
    return await _post(ctx, "/sessions", {"name": name, "description": description})


@mcp.tool(annotations=_READ)
async def get_session(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
) -> GetSessionOut:
    """세션 하나의 상세와 그 안의 파일 목록(파일마다 meta)을 돌려준다 — 「이 세션에 무엇이 들어 있나」 의 입구다.

    파일 목록만 필요하면 list_session_files(같은 행), 파일 하나의 meta · sha256 은 inspect_file, 잡 이력은 list_session_jobs,
    빠진 *INCLUDE 는 session_includes. 파트 제목 바꾸기는 rename_session_part, 이름 · 설명 바꾸기는 update_session. 내 세션과
    조직에 공개된 남의 세션을 볼 수 있다(없거나 볼 수 없으면 404).

    반환: id · name · description · status · visibility · deck_revision_label(덱 판 라벨) · linked_cad(연결된 StepForge 과제 · 판
    {project_id, revision}) · revision_warning(둘이 다르면 경고 글) · environment(dev · prod · unknown) · created_at · updated_at ·
    file_count · files[{id, session_id, filename, kind, origin_job_id, size_bytes, sha256, meta, created_at}](id 순 · 자르지 않는다).
    라벨 · 연결은 이 MCP 로 바꿀 수 없다 — REST PATCH /sessions/{id} 로 둔다.

    파일이 많고 meta 가 크면 응답이 커진다 — 파일 하나만 볼 때는 inspect_file 이 가볍다."""
    return await _get(ctx, f"/sessions/{_seg(session_id)}")


@mcp.tool(annotations=_ADD)
async def upload_kfile(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    filename: Annotated[str, Field(description="세션 안에 둘 파일 이름 — 하위 경로를 그대로 쓴다(예 sub/part.k · 덱의 *INCLUDE 줄과 "
                                               "같은 경로). `..` · 절대 경로는 서버가 지운다. 같은 이름이 있으면 `_1` 이 붙는다.")],
    content: Annotated[str, Field(description="파일 내용 — 글 파일(LS-DYNA .k 등)은 내용 그대로(UTF-8 로 올린다), 바이너리는 base64 "
                                              "문자열로 주고 base64_encoded=true.")],
    ctx: Context,
    base64_encoded: Annotated[bool, Field(description="true 면 content 를 base64 로 풀어 그 바이트를 올린다(바이너리 파일). "
                                                      "false(기본)면 content 를 UTF-8 글로 올린다.")] = False,
) -> list[CoreSessionFileRow]:
    """파일 하나를 세션에 올린다(내용을 인자로 싣는다) — LS-DYNA 덱(.k 등) · 인클루드 · 설정 파일을 넣을 때 쓴다.

    MCP 서버와 같은 머신의 큰 파일은 upload_local_path(내용을 대화로 나르지 않는다)가 낫다. 세션 주인만 올릴 수 있다.

    올리면 백엔드가 덱(.k · .key · .dyn · .dynain · .inc)을 `info` 로 재어 meta(절점 · 요소 · 파트 · bbox · *INCLUDE · 키워드 ·
    modelmeta)에 둔다. ⚠ `filename` 에 하위 경로를 그대로 써야 한다 — 덱이 `*INCLUDE sub/part.k` 를 가리키면 그 파일도
    `filename="sub/part.k"` 로 올려라. 덱을 고쳐 쓰는 오퍼레이션은 주 덱만 고치고 출력 덱에 그 줄을 보존하므로, 경로가 어긋나면
    산출물을 LS-DYNA 에 넣을 때 깨진다. 올리는 순서는 상관없다 — meta 는 그때 세션에 있는 인클루드 닫힘까지 재고, 인클루드가 나중에
    들어오면 그것을 가리키는 덱의 meta 를 다시 잰다(큰 마스터면 그 인클루드 업로드가 그만큼 더 걸린다). 같은 이름으로 또 올리면 `_1` 이
    붙은 새 파일이 된다(덮어쓰지 않는다). 올린 뒤 session_includes 로 빠진 것이 없는지 확인하라.

    반환: 올린 파일 행 목록(한 행) — id(이후 file_id) · session_id · filename(실제로 둔 이름) · kind(input) · origin_job_id ·
    size_bytes · sha256 · meta · created_at. 한계: 파일당 서버 상한(기본 512 MB — 넘으면 413), 속도 제한이 켜져 있으면 분당 업로드
    횟수 상한(기본 60)."""
    raw = base64.b64decode(content) if base64_encoded else content.encode("utf-8")
    files = {"files": (filename, raw, "application/octet-stream")}
    async with _client() as c:
        return _unwrap(
            await c.post(
                f"/sessions/{_seg(session_id)}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool(annotations=_ADD_OUT)
async def upload_local_path(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    path: Annotated[str, Field(description="MCP 서버가 도는 머신의 파일 경로(절대 경로 권장) — 그 머신에서 읽을 수 있어야 한다.")],
    ctx: Context,
    filename: Annotated[str | None, Field(description="세션 안에 둘 이름(하위 경로 가능 — 예 sub/part.k). null(기본)이면 path 의 "
                                                      "파일 이름.")] = None,
) -> list[CoreSessionFileRow]:
    """MCP 서버가 도는 머신의 로컬 파일을 그대로 세션에 올린다 — 수십 MB 가 넘는 큰 메쉬처럼 내용을 대화로 나르기 어려울 때 쓴다.

    MCP 서버가 path 를 읽을 수 있을 때만 된다(같은 머신에서 도는 MCP — 예 Claude Desktop 과 로컬 실행). 원격 MCP 라면 path 는 그
    서버의 디스크를 가리키므로 보통 쓸 수 없다 — 그때는 upload_kfile 로 내용을 싣는다. 파일이 없으면 실패한다.

    나머지는 upload_kfile 과 같다 — 백엔드가 meta 를 재고, 인클루드는 어느 순서로 올려도 되며, 같은 이름이면 `_1` 이 붙는다. 덱이 하위
    경로의 *INCLUDE 를 가리키면 filename 에 그 경로(예 sub/part.k)를 준다. 올린 뒤 session_includes 로 확인하라. 세션 주인만 올릴
    수 있다.

    반환: 올린 파일 행 목록(한 행) — id(이후 file_id) · session_id · filename · kind(input) · origin_job_id · size_bytes · sha256 ·
    meta · created_at. 한계: 파일당 서버 상한(기본 512 MB — 넘으면 413) · 파일을 통째로 메모리에 읽어 보낸다."""
    import os as _os
    if not _os.path.isfile(path):
        raise RuntimeError(f"file not found on the MCP host: {path}")
    name = filename or _os.path.basename(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    files = {"files": (name, raw, "application/octet-stream")}
    async with _client() as c:
        return _unwrap(
            await c.post(
                f"/sessions/{_seg(session_id)}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool(annotations=_SET_OUT)
async def save_result_to_path(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_CORE_FILE_ID)],
    dest_path: Annotated[str, Field(description="저장할 MCP 서버 머신의 파일 경로 — 없는 상위 폴더는 만들고, 같은 경로에 파일이 "
                                                "있으면 묻지 않고 덮어쓴다.")],
    ctx: Context,
) -> SaveResultToPathOut:
    """세션 파일(오퍼레이션 산출물 등)을 MCP 서버가 도는 머신의 로컬 경로에 저장한다 — 큰 산출물을 대화로 나르지 않고 받을 때 쓴다.

    MCP 서버가 dest_path 에 쓸 수 있을 때만 쓸모가 있다(같은 머신에서 도는 MCP). 원격 MCP 라면 그 서버의 디스크에 쓰인다. 내용을
    대화로 보려면 download_result(기본 5 MB 까지), 무엇이 나왔는지는 get_job_outputs · list_session_files.

    ⚠ dest_path 에 파일이 있으면 묻지 않고 덮어쓴다. 없는 상위 폴더는 만든다. 내 세션과 조직에 공개된 세션의 파일을 받을 수 있다.

    반환: saved(쓴 경로) · bytes(쓴 바이트 수)."""
    import os as _os
    async with _client() as c:
        r = await c.get(
            f"/sessions/{_seg(session_id)}/files/{_seg(file_id)}/download", headers=_forward_headers(ctx)
        )
    if r.status_code >= 400:
        raise RuntimeError(f"download failed: HTTP {r.status_code}")
    d = _os.path.dirname(dest_path)
    if d:
        _os.makedirs(d, exist_ok=True)
    with open(dest_path, "wb") as fh:
        fh.write(r.content)
    return {"saved": dest_path, "bytes": len(r.content)}


@mcp.tool(annotations=_READ)
async def list_session_files(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
) -> list[CoreSessionFileRow]:
    """세션 안의 파일 목록을 파일마다 meta 와 함께 돌려준다 — 「이 K파일 안에 무엇이 들었나」 를 한 번에 볼 때 쓴다.

    세션 정보까지 함께 보려면 get_session(같은 files), 파일 하나의 meta · sha256 은 inspect_file, 잡 하나의 산출물만은
    get_job_outputs, 내용은 download_result. 내 세션과 조직에 공개된 세션을 볼 수 있다(없거나 볼 수 없으면 404).

    반환: 행 목록(id 순 · 자르지 않는다) — id(file_id) · session_id · filename · kind(input 올린 것 · output 잡 산출물 · generated) ·
    origin_job_id · size_bytes · sha256 · meta. meta 는 덱이면 nodes · elements · parts · bbox_min · bbox_max · includes ·
    part_titles(앞 50개) · keyword_counts · modelmeta 이고, 키워드 훑기가 앞 8 MB 에서 멈췄으면 truncated_scan 이 true 다.
    파일이 많으면 응답이 크다."""
    return await _get(ctx, f"/sessions/{_seg(session_id)}/files")


@mcp.tool(annotations=_READ)
async def session_includes(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
) -> SessionIncludesOut:
    """이 세션의 덱들이 참조하는 `*INCLUDE` 가 세션에 다 올라와 있는지 돌려준다 — 오퍼레이션을 돌리기 전에 확인하라.

    덱을 고쳐 쓰는 오퍼레이션은 주 덱만 고치므로 인클루드가 빠져도 성공할 수 있다. 대신 산출물에 그 `*INCLUDE` 줄이 그대로 남고,
    LS-DYNA 는 인클루드를 따라가므로 해석 단계에서 깨진다(분석 오퍼레이션 — info · modelmeta · 그림 셋 — 은 인클루드를 함께 읽고,
    빠진 파일은 못 읽었다고 말한다). 빠진 게 있으면 run_operation 이 422 로 막는다 — 그 파일을 upload_kfile · upload_local_path 로
    올려라(하위 폴더면 경로째로). 대상 파트가 인클루드 안에만 있으면 오퍼레이션이 rc 1 로 멈추고 `flatten_includes` 를 안내한다 —
    사용자가 원하면 config 에 `flatten_includes: true` 를 넣어 다시 돌린다(닫힘을 펼쳐 `*INCLUDE` 없는 한 덱으로 고친다). 넘김값
    `allow_missing_includes` 는 REST(`POST /sessions/{id}/jobs` 본문)에만 있고 이 MCP 도구로는 줄 수 없다.

    반환: ok(빠진 것이 없으면 true) · missing_by_file{덱 파일명: {missing: [...], satisfied: [...]}} — 빠진 것이 있는 덱만 싣는다.
    맞춤은 하위 경로째로, 또는 파일 이름만으로 한다(옛 세션은 경로 없이 올라와 있다)."""
    return await _get(ctx, f"/sessions/{_seg(session_id)}/includes")


@mcp.tool(annotations=_READ)
async def inspect_file(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_CORE_FILE_ID)],
    ctx: Context,
) -> InspectFileOut:
    """세션 파일 하나의 캐시된 메타와 sha256 을 돌려준다 — 덱 하나의 구조 · 포함 관계 · 판 지문을 볼 때 쓴다.

    meta 는 업로드 때(또는 그 덱이 가리키는 인클루드가 나중에 들어온 때) 잰 값이고 이 도구가 다시 재지 않는다. 세션의 모든 파일은
    list_session_files, 내용은 download_result. 파트 메트릭 · 재질 · 접촉 연결은 meta.modelmeta 에 있고, 더 깊은 분석은
    run_operation(info · modelmeta) 으로 한다. 내 세션과 조직에 공개된 세션의 파일을 볼 수 있다(없으면 404).

    반환: filename · sha256(덱 판 지문) · meta — 덱(.k · .key · .dyn · .dynain · .inc)이면 nodes · elements · parts · bbox_min ·
    bbox_max · size · valid · ref_dangling · newline · includes · part_titles(앞 50개) · keyword_counts · truncated_scan(키워드
    훑기가 앞 8 MB 에서 멈췄으면 true) · modelmeta(실패하면 {error}) · info_error(바이너리 실패 때), 덱이 아니면 {filename} 만."""
    return await _get(ctx, f"/sessions/{_seg(session_id)}/files/{_seg(file_id)}/inspect")


# ── 실행 / 결과 ──────────────────────────────────────────────────────
@mcp.tool(annotations=_ADD_OUT)
async def run_operation(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    operation: Annotated[str, Field(description="오퍼레이션 이름 — list_operations 의 name(예 info · map · contact).")],
    args: Annotated[dict, Field(description="오퍼레이션 인자 — describe_operation(operation) 의 args_schema 를 따르는 객체. "
                                            "파일 인자는 이 세션의 파일 이름(get_session 의 files[].filename).")],
    ctx: Context,
) -> RunOperationOut:
    """세션 파일에 오퍼레이션을 거는 비동기 잡을 낸다 — 큐에 넣고 바로 잡 정보를 돌려준다(끝날 때까지 기다리지 않는다).

    먼저 list_operations 로 이름을, describe_operation 으로 args_schema 를 본다. 낸 뒤에는 get_job 으로 상태를 보고(끝날 때까지
    되풀이), 끝나면 get_job_outputs 로 산출 파일을, download_result · save_result_to_path 로 내용을 받는다. 취소는 cancel_job.
    세션 주인만 낼 수 있다. invocation 이 external 인 오퍼레이션(stcx_fullangle_drop · postprocess)은 워커가 다른 클러스터
    (stcx · KooSlurm)에 잡을 내거나 그쪽 결과를 기다린다.

    제출 때 막는 것(도구 오류로 돌아온다): 없는 오퍼레이션(400) · args 검증 실패(422) · gmsh 가 필요한데 서버에 없음(422) · 파일 인자가
    세션에 없음(422) · 덱이 가리키는 `*INCLUDE` 가 세션에 없음(422 — session_includes 로 미리 본다, 넘김값은 REST 전용). 덱이 정의되지
    않은 세트 · 파트 · 재질 · 절점을 가리키면 막지 않고 잡의 warnings 에 남긴다.

    반환: 잡 — id(이후 도구의 job_id) · session_id · operation · args · status(queued) · warnings · created_at · external 등
    get_job 과 같은 칸."""
    return await _post(
        ctx, f"/sessions/{_seg(session_id)}/jobs", {"operation": operation, "args": args}
    )


@mcp.tool(annotations=_READ)
async def get_job(
    job_id: Annotated[str, Field(description=_A_CORE_JOB_ID)],
    ctx: Context,
    include_logs: Annotated[bool, Field(description="true 면 잡 로그(stdout · stderr)의 마지막 4000자를 logs 칸에 싣는다. "
                                                    "false(기본)면 로그를 읽지 않는다.")] = False,
) -> GetJobOut:
    """잡 하나의 상태 · 진행률 · 종료 코드 · 산출 파일 id · 경고를 돌려준다 — run_operation 뒤 끝났는지 볼 때 되풀이해 부른다.

    산출 파일의 이름 · meta 는 get_job_outputs, 세션의 잡 이력은 list_session_jobs, 취소는 cancel_job. 내 잡만 볼 수 있다.

    반환: id · session_id · operation · args · resolved_cmd · status(queued · running · succeeded · failed · canceled) ·
    progress(0~100) · exit_code · input_file_ids · output_file_ids · error_summary · warnings · created_at · started_at ·
    finished_at · external.
    · `warnings` 가 있으면 읽어라 — 입력 덱이 정의되지 않은 세트 · 파트 · 섹션 · 재질 · 절점을 가리킨다는 경고 등이다(막지 않고
      남긴다 · LS-DYNA 는 키워드 단계에서 멈춘다).
    · `external` — 외부 잡(stcx 제출 · 후처리 예약)의 요약 `{kind, cluster_state, ontology: {state, why?}}`(경로 · 토큰은 가린 꼴),
      로컬 잡은 null. 반입된 리포트는 `find_reports(external_job_key='stcx:<Slurm 잡 id>')` 로 찾는다. 매니페스트가 이미지 출처를
      실어 온 후처리 예약이면 `external.images` 도 온다 — `post`(리포트를 만든 노드의 후처리 SIF `{from, node, present, size,
      sha256, version}` · 리포트 노드를 모르면 `{from: null, node, why}`) · `manifest_node_pre`(매니페스트를 쓴 노드에 깔려 있던
      전처리 SIF `{node, present, size, sha256, version, kooremapper_commit}` — 배포 상태이고 전처리가 실제로 쓴 판의 증거가
      아니다). 없으면 칸이 없다(모르는 것 ≠ 없음).
    · include_logs=true 면 logs(마지막 4000자) · logs_truncated(앞이 잘렸으면 true) · logs_total_chars 가 붙는다."""
    job = await _get(ctx, f"/jobs/{_seg(job_id)}")
    if include_logs and isinstance(job, dict):
        async with _client() as c:
            r = await c.get(f"/jobs/{_seg(job_id)}/logs", headers=_forward_headers(ctx))
            job = {**job, "logs": r.text[-4000:] if r.status_code < 400 else f"(logs unavailable: HTTP {r.status_code})"}
            if r.status_code < 400:   # 앞을 잘랐는지 말한다(계약 C8)
                job.update(logs_truncated=len(r.text) > 4000, logs_total_chars=len(r.text))
    return job


@mcp.tool(annotations=_SET)
async def cancel_job(
    job_id: Annotated[str, Field(description=_A_CORE_JOB_ID)],
    ctx: Context,
) -> CancelJobOut:
    """대기 중이거나 도는 잡을 취소한다 — 잘못 낸 잡이나 매달린 잡을 멈출 때 쓴다.

    상태는 get_job 으로 보고, 다시 돌리려면 run_operation 으로 새 잡을 낸다(취소한 잡은 되살리지 않는다). 내 잡만 취소할 수 있다.
    로컬 잡은 프로세스에 멈춤 신호를 보낸다 — 곧바로 canceled 가 되지 않을 수 있으니 get_job 으로 확인한다. 후처리 예약은 기다림만
    멈추고 클러스터 잡은 그대로 둔다. 다른 클러스터에서 도는 외부 잡(stcx 제출)은 여기서 취소할 수 없다(501 — 제출한 클러스터에서
    취소한다). 이미 끝난 잡(succeeded · failed · canceled)은 409 로 실패한다.

    반환: message(취소 요청됨 · 취소됨 등 백엔드 문구)."""
    return await _post(ctx, f"/jobs/{_seg(job_id)}/cancel", None)


@mcp.tool(annotations=_SET)
async def update_session(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
    name: Annotated[str | None, Field(description=f"새 세션 이름(1~{SESSION_NAME_MAX}자). null(기본)이면 그대로 둔다.")] = None,
    description: Annotated[str | None, Field(description="새 설명. null(기본)이면 그대로 둔다 — 빈 문자열을 주면 설명을 비운다.")] = None,
    task_key: Annotated[str | None, Field(description=(
        "허브 과제 — 과제명 · 과제코드 · 옛 과제명 · 별칭 무엇이든 받아 판 확정과 같은 규칙으로 풀고 과제명을 남긴다(못 풀면 거절과 "
        "후보 — 이름은 list_tasks 로 찾는다). 빈 글이면 지운다 · null(기본)이면 그대로."))] = None,
    dev_rev: Annotated[Literal[DEV_REV_CODES] | Literal[""] | None, Field(description=(
        f"개발 단계 — {_one_of(DEV_REV_CODES)}. 빈 글이면 지운다 · null(기본)이면 그대로."))] = None,
) -> UpdateSessionOut:
    """세션의 이름 · 설명 · 허브 과제 · 개발 단계를 바꾼다 — 작업이 바뀌어 이름이 안 맞을 때, 또는 자동 파이프라인이 읽을 과제를 둘 때.

    준 칸만 바꾸고 null 인 칸은 그대로 둔다. 세션 주인만 바꿀 수 있다(아니면 404). task_key · dev_rev 는 자동 파이프라인이 이 세션의
    과제 · 차수로 읽는다(auto_changes 의 subject). 과제를 못 풀면 400 task_unresolved 와 후보, 단계가 틀리면 400 bad_dev_rev 이고 그때는
    다른 칸도 바꾸지 않는다. 공개 범위 · 상태 · 덱 판 라벨 · CAD 연결은 이 도구로 바꿀 수 없다(REST PATCH /sessions/{id}). 파트 제목은
    rename_session_part.

    반환: 바뀐 세션 — id · name · description · status · visibility · task_key · dev_rev · deck_revision_label · linked_cad · created_at ·
    updated_at · environment · revision_warning."""
    body = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
    for k, v in (("task_key", task_key), ("dev_rev", dev_rev)):
        if v is not None:
            body[k] = v.strip() or None          # 빈 글 = 지운다(REST 는 null 을 지움으로 읽는다)
    async with _client() as c:
        return _unwrap(await c.patch(f"/sessions/{_seg(session_id)}", json=body, headers=_forward_headers(ctx)))


@mcp.tool(annotations=_DELETE)
async def delete_session(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
) -> DeleteSessionOut:
    """세션과 그 안의 모든 파일 · 잡 기록을 지운다(되돌릴 수 없다) — 다 쓴 작업 공간을 정리할 때 쓴다.

    파일 하나만 지우려면 delete_file. 세션 주인만 지울 수 있다(아니면 404). 이 세션에서 도는 로컬 잡은 먼저 취소하고 잠깐(약 8초까지)
    기다린 뒤 지운다. 다른 클러스터에서 도는 외부 잡은 기다리지도 멈추지도 않는다.

    반환: message(백엔드 문구)."""
    return await _delete(ctx, f"/sessions/{_seg(session_id)}")


@mcp.tool(annotations=_DELETE)
async def delete_file(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_CORE_FILE_ID)],
    ctx: Context,
) -> DeleteFileOut:
    """세션에서 파일 하나를 지운다(되돌릴 수 없다) — 잘못 올린 파일이나 필요 없는 산출물을 정리할 때 쓴다.

    어떤 파일이 있는지는 get_session · list_session_files 로 먼저 본다. 세션 전체는 delete_session. 세션 주인만 지울 수 있다(아니면
    404). 지운 파일을 *INCLUDE 하는 덱이 있으면 그 인클루드가 빠진 상태가 된다 — session_includes 로 본다.

    반환: message(백엔드 문구)."""
    return await _delete(ctx, f"/sessions/{_seg(session_id)}/files/{_seg(file_id)}")


@mcp.tool(annotations=_READ)
async def get_job_outputs(
    job_id: Annotated[str, Field(description=_A_CORE_JOB_ID)],
    ctx: Context,
) -> list[CoreSessionFileRow]:
    """잡이 만든 산출 파일 목록을 파일마다 meta 와 함께 돌려준다 — 잡이 끝난 뒤 「무엇이 나왔나」 를 볼 때 쓴다.

    내용은 download_result(대화로 · 기본 5 MB 까지) · save_result_to_path(같은 머신 디스크로), 잡 상태와 로그는
    get_job(include_logs=true), 세션 전체 파일은 list_session_files. 내 잡만 볼 수 있다.

    반환: 행 목록(산출이 없으면 빈 목록) — id(file_id) · session_id · filename · kind(output · generated) · origin_job_id ·
    size_bytes · sha256 · meta · created_at."""
    return await _get(ctx, f"/jobs/{_seg(job_id)}/outputs")


@mcp.tool(annotations=_READ)
async def download_result(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_CORE_FILE_ID)],
    ctx: Context,
    as_base64: Annotated[bool, Field(description="true 면 내용을 base64 로 돌려준다(바이너리). false(기본)면 UTF-8 글로 돌려주고, "
                                                 "글로 못 풀면 저절로 base64 로 돌려준다.")] = False,
) -> dict:
    """세션 파일 하나의 내용을 대화로 가져온다 — 오퍼레이션 산출물 · 올린 덱을 읽을 때 쓴다.

    큰 파일은 save_result_to_path(MCP 서버와 같은 머신의 디스크로)가 낫다. 무엇이 있는지는 get_job_outputs · list_session_files 로
    본다. 내 세션과 조직에 공개된 세션의 파일을 받을 수 있다.

    반환: filename_id(받은 file_id) · bytes(크기)와 content(UTF-8 글) 또는 base64. as_base64=false 여도 UTF-8 로 못 풀면 base64 ·
    note 로 돌려준다. 한계: 서버 상한(기본 5 MB · 손잡이 KOORM_MCP_MAX_DOWNLOAD_BYTES)을 넘으면 내용 대신 error · bytes ·
    preview(앞 2000바이트를 글로 푼 것)만 온다 — base64 로 받아도 상한은 같다."""
    async with _client() as c:
        r = await c.get(
            f"/sessions/{_seg(session_id)}/files/{_seg(file_id)}/download",
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


async def _run_figure_job(ctx: Context, session_id: str, operation: str,
                          args: dict, timeout_s: int) -> tuple:
    """그림 잡을 돌리고 끝날 때까지 기다린 뒤 `(job_id, outputs)` 를 준다.

    실패를 성공처럼 보이는 dict 로 돌려주지 않는다 — 다른 도구와 같은 규율이다. 다만
    **로그 꼬리를 에러에 붙인다.** 그림 op 의 rc=1 은 고장이 아니라 **판정**인 경우가 있다 —
    `stackdiagram` 은 솔리드 축 범위가 포개지면 일부러 거절하고 `section` 을 쓰라고 말한다.
    그 까닭이 로그에만 있으므로, 붙이지 않으면 호출자는 "실패" 만 보고 **왜** 를 못 본다.
    """
    import asyncio

    job = await _post(ctx, f"/sessions/{_seg(session_id)}/jobs", {"operation": operation, "args": args})
    job_id = job.get("id") or job.get("job_id")
    if not job_id:
        raise RuntimeError(f"잡을 만들지 못했습니다: {job}")

    # 기다림은 벽시계로 잰다 — 잠만 세면 상태 조회에 든 시간이 빠진다. 그리고 이 도구 호출의 기한 안으로 죈다(끝난 뒤 산출 목록을
    # 받을 틈을 남긴다). 기한까지 안 끝나면 잡은 그대로 두고 job_id 와 손잡이를 말한다 — 잡을 끄지 않는다.
    left = _left()
    end = time.monotonic() + min(float(timeout_s), left - min(5.0, left / 10))
    last = job
    try:
        while time.monotonic() < end:
            await asyncio.sleep(max(0.0, min(1.0, end - time.monotonic())))
            last = await _get(ctx, f"/jobs/{_seg(job_id)}")
            # 백엔드는 `canceled`(l 하나)로 쓴다 — `cancelled` 만 보면 취소된 잡을 끝난 것으로
            # 알아보지 못해 `timeout_s`(최대 300초)를 꽉 채운 뒤에야 에러가 된다. 둘 다 본다.
            if last.get("status") in ("succeeded", "failed", "canceled", "cancelled"):
                break
    except (_Late, httpx.TimeoutException):
        pass        # 상태 조회가 기한에 걸렸다 — 잡은 그대로 둔다(아래에서 마지막으로 본 상태 · job_id 와 함께 말한다)
    if last.get("status") in ("queued", "running"):
        raise RuntimeError(
            f"{operation} 잡이 기다린 시간 안에 끝나지 않았다(timeout_s={timeout_s} · 이 도구 호출의 기한 {API_TIMEOUT_S:g}초 "
            f"{API_TIMEOUT_KNOB}) — 잡은 계속 돈다: job_id={job_id}. get_job 으로 지켜보고 끝나면 download_result 로 받는다")
    if last.get("status") != "succeeded":
        raise RuntimeError(
            "%s 잡이 끝나지 않았거나 실패했습니다: status=%s exit_code=%s job_id=%s\n--- 로그 ---\n%s"
            % (operation, last.get("status"), last.get("exit_code"), job_id,
               await _job_log_tail(ctx, job_id)))
    return job_id, await _get(ctx, f"/jobs/{_seg(job_id)}/outputs")


async def _job_log_tail(ctx: Context, job_id: str, limit: int = 2500) -> str:
    """잡 로그의 꼬리. `surfview`·`stackdiagram` 은 JSON 매니페스트가 없고 **그림의 요지 숫자가
    콘솔에만** 있으므로(자유면 비율·등진 삼각형 수·ink_ratio·바닥 처리한 층 수·겹침 쌍 수)
    이것이 그 둘의 매니페스트 노릇을 한다."""
    try:
        async with _client() as c:
            r = await c.get(f"/jobs/{_seg(job_id)}/logs", headers=_forward_headers(ctx))
        return r.text[-limit:] if r.status_code < 400 else f"(로그를 읽지 못했습니다: HTTP {r.status_code})"
    except Exception as e:  # 로그를 못 읽는 것이 그림을 못 쓴 것은 아니다
        return f"(로그를 읽지 못했습니다: {e})"


def fit_to_budget(build, n_rows: int, budget: int, reserve: int = 1200):
    """**나갈 그 꼴 그대로 재서** 표의 행을 뒤에서부터 뺀다. `build(cap)` 이 응답 dict 를 준다.

    왜 고정 캡이 아닌가. 챗은 텍스트를 이어 붙인 **뒤** 통째로 자르므로, 응답이 길면
    **URL 줄이 잘려 그림이 사라진다**. 고정 캡은 그 길이를 **재지 않는다** — 제목이 긴 덱은
    행이 적어도 넘고, 짧은 덱은 더 실을 수 있는데 못 싣는다. 실측(61파트 배터리 덱) —
    고정 캡 20 은 3,702바이트에 20행, 재서 빼면 같은 예산에 **25행**(4,413바이트)이 들어간다.

    `reserve` 는 본문 뒤에 붙는 안내·URL 자리다. 그 줄이 잘리면 그림이 사라지므로 남겨 둔다.
    돌려주는 것은 `(응답, 실은 행 수)` 이고, 뺀 수는 호출자가 `parts_omitted` 로 말한다.
    """
    import json as _j
    cap = max(int(n_rows), 1)
    res = build(cap)
    limit = max(budget - reserve, 256)
    while cap > 1 and len(_j.dumps(res, ensure_ascii=False)) > limit:
        cap -= max(1, cap // 8)
        cap = max(cap, 1)
        res = build(cap)
    return res, cap


async def _figure_numbers(ctx: Context, job_id: str, limit: int = 900) -> str:
    """로그에서 **그림의 요지 숫자 줄만** 뽑는다.

    왜 전체 로그가 아닌가. `mesh_section_figure` 는 매니페스트(파트 표)를 이미 싣는다. 거기에
    로그 2,500자를 더하면 응답이 불어 **챗이 URL 을 잘라 그림이 사라진다**(`TOOL_RESULT_MAX`).
    실측으로 compare 를 준 61파트 덱 응답이 이미 9,273바이트였다.

    왜 필요한가. **확대 배율과 최소피처 px 는 매니페스트에 없다** — 둘은 SVG 배치 단계에서
    정해지므로 JSON 을 쓴 **뒤에** 계산되고 콘솔에만 찍힌다. 그런데 이 도구의 설명·TOOLS.md·
    매뉴얼 §45.6 이 그 숫자를 응답에 준다고 적는다. 그 약속을 이 함수가 지킨다.
    """
    want = ("Magnified axis", "Min feature in px", "Axis chosen", "Section aspect")
    log = await _job_log_tail(ctx, job_id, limit=6000)
    keep = [l.strip() for l in log.splitlines() if any(w in l for w in want)]
    out = "\n".join(keep)
    return out[:limit] if out else "(로그에서 그림 숫자 줄을 찾지 못했습니다)"


def _pick_svg(outs: list) -> tuple:
    """산출물에서 `.svg` 를 찾아 `(file_id, size_bytes)`. 없으면 에러를 던진다."""
    for f in outs:
        if (f.get("filename") or "").lower().endswith(".svg"):
            return int(f["id"]), int(f.get("size_bytes") or 0)
    raise RuntimeError("그림(SVG)이 산출물에 없습니다: %s" % [f.get("filename") for f in outs])


async def _with_png(ctx: Context, session_id: str, svg_id: int | None, res: dict) -> list:
    """`res` 뒤에 그림의 **이미지 블록**을 붙여 `[res, Image]` 로 돌려준다(2026-11-02, 포털 요청).

    게이트웨이는 이미지 블록을 저장해 `figure_to_report` 로 리포트에 넣는다 — SVG 는 거기 못 간다.
    `res` 의 텍스트 블록은 그대로 나가고(FastMCP 가 dict 를 같은 꼴로 직렬화한다) 키 하나만 는다 —
    `figure_png`(꼴·크기) 또는 못 만든 까닭 `figure_png_error`. 못 만들면 `[res]` 만 간다.
    """
    if svg_id is None:
        res["figure_png_error"] = "render_failed: 산출물에 SVG 가 없다"
        return [res]
    try:
        svg = await _download_bytes(ctx, session_id, svg_id)
        data, fmt, w, h = await rasterize(svg)
    except FigurePngError as e:
        res["figure_png_error"] = str(e)
        return [res]
    except RuntimeError as e:
        res["figure_png_error"] = f"download_failed: {e}"[:200]
        return [res]
    res["figure_png"] = {"format": fmt, "width": w, "height": h, "bytes": len(data)}
    return [res, Image(data=data, format=fmt)]


# ── 메시 그림 · 세션 잡 · 시스템 기능 · 전사 코퍼스 도구의 계약 상수 ──────────────────────────────────────────────
# 허용값 · 하한은 받는 쪽과 같게 둔다 — 축 · 모드는 아래 그림 도구 본문의 검사, 그림 크기 하한은 그림 op 셋(C++ section · surfview ·
# stackdiagram)이 rc 1 로 거절하는 값, limit 상한은 백엔드 corpus 라우트의 Query(ge · le) 다.
MESH_SECTION_AXES = ("auto", "x", "y", "z")
MESH_SECTION_MODES = ("panels", "overlay")
MESH_STACK_AXES = ("x", "y", "z")
MESH_FIG_MIN_WIDTH_PX = 430
MESH_FIG_MIN_HEIGHT_PX = 240
CORPUS_LIMIT_MAX = 200

_A_MESH_FILE_ID = ("그릴 덱의 세션 파일 id — list_session_files 의 id · get_session 의 files[].id. 이 세션에 없으면 거절한다. "
                   "마스터 덱이면 *INCLUDE 닫힘까지 읽으므로 인클루드도 같은 세션에 올려 둔다.")
_A_MESH_WIDTH = f"SVG 폭(px) — {MESH_FIG_MIN_WIDTH_PX} 이상(여백 · 범례 · 그림 자리). 이미지 블록은 이와 별개로 폭 1500px 안팎으로 그린다."
_A_MESH_HEIGHT = f"SVG 높이(px) — {MESH_FIG_MIN_HEIGHT_PX} 이상."
_A_MESH_TIMEOUT = (f"잡이 끝나기를 기다릴 최대 초. 이 도구 호출의 기한({API_TIMEOUT_S:g}초 · {API_TIMEOUT_KNOB})보다 길게 줘도 그 기한까지만 "
                   "기다린다. 그 안에 안 끝나면 잡은 계속 돌고 job_id 가 든 오류가 난다 — get_job 으로 지켜본다.")

_O_SESSION_JOB = _shape("SessionJobRow", {
    "id": "잡 id — get_job · get_job_outputs · cancel_job 에 준다.",
    "session_id": "세션 id.",
    "operation": "오퍼레이션 이름(list_operations 의 name).",
    "args": "잡에 준 인자 객체.",
    "resolved_cmd": "백엔드가 풀어 쓴 실행 정보(argv · 쓴 파일 · 외부 잡 표지 · 인자 오류 — 없으면 null).",
    "status": "queued · running · succeeded · failed · canceled.",
    "progress": "진행률(%, 모르면 null).",
    "exit_code": "종료 코드(끝나지 않았으면 null).",
    "input_file_ids": "입력 세션 파일 id 목록.",
    "output_file_ids": "산출 세션 파일 id 목록 — 내용은 get_job_outputs · download_result.",
    "error_summary": "실패 요약 글(없으면 null).",
    "warnings": "입력 덱 경고 글 목록(정의되지 않은 세트 · 파트 · 섹션 · 재질 · 절점을 가리킴 등 — 없으면 null).",
    "created_at": "만든 시각(ISO 8601) — 목록은 이것의 내림차순.",
    "started_at": "시작 시각(없으면 null).",
    "finished_at": "끝난 시각(없으면 null).",
    "external": "외부 잡(stcx 제출 · 후처리 예약) 요약 {kind, cluster_state, ontology, images?} — 로컬 잡이면 null.",
})
_O_SYSTEM_CAPABILITIES = _shape("SystemCapabilitiesOut", {
    "operations": "오퍼레이션 수.",
    "mcp_tools": "MCP 도구 수(서버 소스를 세지 못하면 null).",
    "ontology": "과제 · 개정 기능 스위치 {enabled, source(option · inferred), reason, missing(빠진 설정 이름 목록)}.",
    "parity": "기능별 웹 · MCP 지원 표 — [{feature, web, mcp, note?}].",
    "mcp_url": "MCP 공개 주소(운영자가 설정하지 않았으면 null).",
    "mcp_add_hint": "붙여넣을 `claude mcp add` 명령 — 주소를 모르면 무엇을 설정할지 알리는 글.",
    "mcp_desktop_hint": "Claude Desktop 연결 안내 글.",
    "intake": "외부 적재 규격 {method, path, public_url(모르면 null), mcp_url, token, portal_auth_required, max_upload_mb, "
              "max_report_mb, batch, reports_per_call, rate_limit_per_min(꺼졌으면 null), campaign{REST 경로들 · form_fields · states}}.",
})
_O_CORPUS_SUMMARY = _shape("CorpusSummaryOut", {
    "sessions": "전사 세션 수.",
    "files": "전사 세션 파일 수.",
    "jobs": "전사 잡 수.",
    "mesh_scale": "{nodes, elements, parts} 마다 {n, min, median, max, total} — 메타에 그 값이 있는 파일만 센다(하나도 없으면 {n: 0}).",
    "note": "집계 범위 안내 글.",
})
_O_MATERIAL_USAGE = _shape("MaterialUsageOut", {
    "n_files_scanned": "메타가 있는 세션 파일 수(모집단).",
    "n_files_with_material": "*MAT_ 카드가 하나라도 있는 파일 수.",
    "materials": "파일 수 상위 limit 개 — [{card, files(그 카드가 나온 파일 수), occurrences(카드 개수 합)}].",
    "note": "읽는 법 안내 글.",
})
_O_OPERATION_USAGE = _shape("OperationUsageOut", {
    "n_jobs": "전사 잡 수.",
    "operations": "실행 횟수 순 — [{operation, total, succeeded, failed(canceled 포함), other(끝나지 않은 잡 등)}].",
    "note": "읽는 법 안내 글.",
})
_O_SECTION_CONTACT_USAGE = _shape("SectionContactUsageOut", {
    "n_files_scanned": "메타가 있는 세션 파일 수(모집단).",
    "sections": "*SECTION_ 카드의 파일 수 상위 limit 개 — [{card, files}].",
    "contacts": "*CONTACT_ 카드의 파일 수 상위 limit 개 — [{card, files}].",
})
_O_REPORT_CORPUS = _shape("ReportCorpusOut", {
    "reports": "전사 리포트 수.",
    "cases": "전사 케이스 수.",
    "by_kind": "종류별 리포트 수 — [{kind, reports}].",
    "findings_by_severity": "심각도별 소견 수 {CRITICAL: n, …} — 심각도가 없는 소견은 UNKNOWN.",
    "frequent_findings": "같은 제목이 많은 소견 상위 10개 — [{title(80자까지), count}].",
    "note": "리포트가 아직 없는지 알리는 글.",
})
_O_REPORT_UPLOAD_INSTRUCTIONS = _shape("ReportUploadInstructionsOut", {
    "권장(스크립트)": "kr_ PAT 로 REST intake 를 한 호출에 — {방법, 엔드포인트, 명령(curl), 폼필드, 대용량(상한)}.",
    "캠페인 묶음 적재": "런 수백 ~ 천 개를 캠페인으로 올리는 차례.",
    "웹 UI": "웹 화면에서 올리는 길.",
    "토큰 발급": "kr_ PAT 를 받는 길.",
    "note": "401 까닭 가르기 · 공개 주소를 모를 때의 안내.",
})


@mcp.tool(annotations=_ADD)
async def mesh_section_figure(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_MESH_FILE_ID)],
    ctx: Context,
    axis: Annotated[Literal[MESH_SECTION_AXES], Field(
        description=f"자르는 평면의 법선 축 — {_one_of(MESH_SECTION_AXES)}. 기본 auto(단면이 선으로 접히는 축을 빼고 파트를 가장 "
                    "많이 만나는 축 · 동점이면 단면 넓이가 큰 축).")] = "auto",
    at: Annotated[float | None, Field(
        description="평면 위치 — 고른 축의 좌표값(덱의 길이 단위 그대로). 비우면 bbox 중심. 절점층에 딱 걸리면 ε 비키고 응답에 "
                    "그렇다고 적는다.")] = None,
    compare_file_id: Annotated[int | None, Field(
        description="같은 그림에 올릴 두 번째 덱의 세션 파일 id(선택) — 이 세션에 없으면 거절한다. 비우면 한 덱만 그린다.")] = None,
    mode: Annotated[Literal[MESH_SECTION_MODES], Field(
        description=f"두 덱을 그리는 꼴 — {_one_of(MESH_SECTION_MODES)}. panels 는 칸마다 축 · 축척을 따로(접힘 전/후 비교에 맞다), "
                    "overlay 는 같은 평면으로 잘라 겹친다(두 번째 덱이 점선). compare_file_id 를 줄 때만 쓰인다. 기본 panels.")] = "panels",
    isotropic: Annotated[bool, Field(
        description="true 면 두 축을 같은 축척으로 그린다 — 얇은 층은 보이지 않을 수 있다(최소 피처 1.5px 미만이면 그렇다고 말한다). "
                    "기본 false(비등방 — 확대 축 · 배율을 그림에 적는다).")] = False,
    width: Annotated[int, Field(ge=MESH_FIG_MIN_WIDTH_PX, description=_A_MESH_WIDTH + " 기본 1200.")] = 1200,
    height: Annotated[int, Field(ge=MESH_FIG_MIN_HEIGHT_PX, description=_A_MESH_HEIGHT + " 기본 900.")] = 900,
    timeout_s: Annotated[int, Field(description=_A_MESH_TIMEOUT + " 기본 180.")] = 180,
) -> list:
    """메시를 평면 하나로 잘라 단면 그림(이미지 + SVG)과 그 요지 숫자를 한 번에 돌려준다.

    적층 덱의 층 경계 · 두께 · 재질을 눈으로 확인할 때 쓴다. 겉모습은 `mesh_surface_figure`, 층 순서와 중립축 모식도는
    `mesh_stack_diagram` 이 답한다. 안에서 `section` op 잡을 내고 끝날 때까지 기다린다(잡 · 산출 파일이 세션에 남는다).

    축 — `axis="auto"` 는 ① 단면이 선으로 접히는 축을 빼고 ② 파트를 가장 많이 만나는 축 ③ 동점이면 단면 넓이가 큰 축을 고른다.
    「적층 방향에 수직」 이 규칙이 아니다 — 고른 까닭이 응답에 온다. 축척 — 기본은 비등방이고 확대 축 · 배율을 그림에 적는다(얇은 층은
    등축이면 보이지 않는다). 두 덱 — `compare_file_id` 를 주면 `mode` 에 따라 나란히 또는 같은 평면으로 겹쳐 그린다(절점 번호로 짝짓는다).

    돌려주는 것 — `[결과 dict, 이미지]`. 이미지는 PNG(크면 JPEG · 폭 1500px 안팎 · 256KB 목표)이고 게이트웨이가 저장해
    `figure_to_report` 로 리포트에 넣는다. 꼴은 `figure_png`, 못 만들면 까닭이 `figure_png_error` 에 온다. dict 칸은 `job_id` · `svg_file_id`(벡터 원본 — `download_result` · `save_result_to_path`) ·
    `manifest_file_id` · `section`(자른 축과 까닭 · 맞은 파트 수/전체 · ε 비킴 · 최소 피처 · 파트별 pid · 제목 · 두께와 그 출처 · E —
    다각형은 싣지 않는다) · `compare_section` · `figure_numbers`(확대 배율 · 최소 피처 px — 매니페스트에 없는 숫자) · `read_this_first`.
    응답이 길면 파트 행을 뒤에서 빼고 `parts_omitted` 로 뺀 수를 말한다 — 전체 표는 매니페스트 파일에 있다. 잡이 실패하면 로그 꼬리가
    든 오류가 난다. 단위는 주장하지 않는다(LS-DYNA 덱은 단위를 담지 않는다).
    """
    import json as _json

    if mode not in ("panels", "overlay"):
        raise RuntimeError("mode 는 panels 또는 overlay 여야 합니다 (받은 값: %s)" % mode)
    if axis not in ("auto", "x", "y", "z"):
        raise RuntimeError("axis 는 auto, x, y, z 중 하나여야 합니다 (받은 값: %s)" % axis)

    files = await _get(ctx, f"/sessions/{_seg(session_id)}/files")
    byid = {int(f["id"]): f for f in files}
    if file_id not in byid:
        raise RuntimeError(f"세션에 file_id={file_id} 가 없습니다. list_session_files 로 확인하세요.")
    args: dict = {"model": byid[file_id]["filename"], "output": "section", "axis": axis,
                  "isotropic": isotropic, "width": width, "height": height}
    if at is not None:
        args["at"] = at
    if compare_file_id is not None:
        if compare_file_id not in byid:
            raise RuntimeError(f"세션에 compare_file_id={compare_file_id} 가 없습니다.")
        args["compare"] = byid[compare_file_id]["filename"]
        args["mode"] = mode

    job_id, outs = await _run_figure_job(ctx, session_id, "section", args, timeout_s)
    svg_id = json_id = None
    for f in outs:
        n = (f.get("filename") or "").lower()
        if n.endswith(".svg"):
            svg_id = int(f["id"])
        elif n.endswith(".json"):
            json_id = int(f["id"])
    if json_id is None:
        raise RuntimeError(f"단면 매니페스트(JSON)가 산출물에 없습니다: {[f.get('filename') for f in outs]}")

    async with _client() as c:
        r = await c.get(f"/sessions/{_seg(session_id)}/files/{_seg(json_id)}/download",
                        headers=_forward_headers(ctx))
    if r.status_code >= 400:
        raise RuntimeError(f"매니페스트를 내려받지 못했습니다: HTTP {r.status_code}")
    man = _json.loads(r.content.decode("utf-8"))

    # ⚠ **다각형은 돌려주지 않는다.** 실측으로 286k 요소 덱의 단면 JSON 이 455KB 다 — 대화에
    #   실으면 텍스트가 그림을 밀어낸다(챗은 텍스트를 이어 붙인 뒤 통째로 자른다).
    def strip(m: dict, part_cap: int = 20) -> dict:
        parts = m.get("parts") or []
        out = {k: v for k, v in m.items() if k not in ("polys", "parts", "compare")}
        out["parts"] = [
            {"pid": p.get("pid"), "title": p.get("title"), "polys": p.get("polys"),
             "shell": p.get("shell"), "thickness": p.get("thickness"),
             "thickness_note": p.get("thickness_note"), "E": p.get("E"),
             "thin": p.get("thin")}
            for p in parts[:part_cap]
        ]
        if len(parts) > part_cap:
            out["parts_omitted"] = len(parts) - part_cap
        return out

    # ★**나갈 그 꼴 그대로 재서** 파트 행을 뒤에서부터 뺀다 — 고정 캡이 아니다.
    #
    # 왜. 챗은 텍스트를 이어 붙인 **뒤** 통째로 자르므로, 응답이 길면 **URL 줄이 잘려 그림이
    # 사라진다**(`TOOL_RESULT_MAX`, URL 줄 81자). 고정 캡은 그 길이를 **재지 않는다** — 실측으로
    # 61파트 덱에 compare 를 주면 캡 20 에서 응답이 9,273바이트였다. 제목이 긴 덱이면 파트 수가
    # 적어도 넘을 수 있고, 짧으면 20개보다 더 실을 수 있는데 못 싣는다. 그래서 **직렬화해 재고**
    # 맞을 때까지 뒤에서 행을 뺀다. 뺀 수는 `parts_omitted` 로 **말한다**(조용히 자르지 않는다).
    def fit(cap: int) -> dict:
        r = {"job_id": job_id, "svg_file_id": svg_id, "manifest_file_id": json_id,
             "section": strip(man, cap)}
        if "compare" in man:
            r["compare_section"] = strip(man["compare"], cap)
        return r

    nparts = max(len(man.get("parts") or []),
                 len((man.get("compare") or {}).get("parts") or []))
    res, _cap = fit_to_budget(fit, nparts,
                              int(os.environ.get("KOORM_MCP_RESULT_BUDGET", "6000")))
    # ★확대 배율·최소피처 px 는 매니페스트에 없다(SVG 배치 때 정해진다) — 로그에서 뽑아 싣는다.
    res["figure_numbers"] = await _figure_numbers(ctx, job_id)
    res["how_to_see_the_figure"] = (
        "그림은 이 응답의 이미지 블록으로 옵니다(꼴·크기 `figure_png`, 없으면 까닭 "
        "`figure_png_error`). 벡터 원본 SVG 는 `download_result(session_id, svg_file_id)` 로 "
        "텍스트로 받거나 `save_result_to_path` 로 저장해 엽니다."
    )
    res["read_this_first"] = (
        "그림이 거짓말하지 않게 하는 숫자들입니다. `axis_chosen_because` 로 축이 맞는지, "
        "`parts_hit`/`parts_total` 로 층을 다 봤는지, `nudge`>0 이면 평면이 절점층에 걸려 ε "
        "비킨 것, `min_feature` 가 작으면 그 층은 그림에서 보이지 않을 수 있습니다. "
        "**확대 배율과 최소피처 px 는 `figure_numbers`** 에 있습니다 — 그 둘은 그림을 배치할 때 "
        "정해지므로 매니페스트에는 없습니다. "
        "단위는 없습니다(LS-DYNA 덱)."
    )
    return await _with_png(ctx, session_id, svg_id, res)


@mcp.tool(annotations=_ADD)
async def mesh_surface_figure(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_MESH_FILE_ID)],
    ctx: Context,
    azimuth: Annotated[float, Field(
        description="보는 방위각(도) — xy 평면에서 +x 축부터 +y 쪽으로 잰 각. 0 이면 +x 쪽에서, 90 이면 +y 쪽에서 본다. 범위를 "
                    "거르지 않는다(360 주기). 기본 35.")] = 35.0,
    elevation: Annotated[float, Field(
        description="보는 앙각(도) — xy 평면에서 +z 쪽으로 잰 각. 90 이면 위(+z)에서 내려다본다(그때 화면 위쪽은 +y, 아니면 +z). "
                    "범위를 거르지 않는다(보통 -90 ~ 90). 기본 25.")] = 25.0,
    wire: Annotated[bool, Field(
        description="true 면 면 음영 대신 모서리 선만 그린다. 기본 false(음영 면).")] = False,
    width: Annotated[int, Field(ge=MESH_FIG_MIN_WIDTH_PX, description=_A_MESH_WIDTH + " 기본 1200.")] = 1200,
    height: Annotated[int, Field(ge=MESH_FIG_MIN_HEIGHT_PX, description=_A_MESH_HEIGHT + " 기본 900.")] = 900,
    timeout_s: Annotated[int, Field(description=_A_MESH_TIMEOUT + " 기본 300.")] = 300,
) -> list:
    """메시의 자유면만 뽑아 직교투영 · 깊이정렬로 그린 3D 겉모습 그림(이미지 + SVG)을 돌려준다.

    「이 덱이 어떻게 생겼나」 를 볼 때 쓴다. 층 두께는 `mesh_section_figure`(비등방 · 배율을 적는다) 또는 `mesh_stack_diagram`(모식도)이
    답한다. 안에서 `surfview` op 잡을 내고 끝날 때까지 기다린다(잡 · SVG 가 세션에 남는다).

    자유면만 그리는 것이 그림의 요지다 — 묻힌 면은 보이지 않는다. 이 그림은 등축이다 — 3D 형상을 비등방으로 늘이면 모양이 거짓이
    되므로 적층이 얇게 보이는 것이 사실이다. 깊이정렬은 삼각형 무게중심 기준이라 서로 관통하는 삼각형은 순서가 틀릴 수 있다.

    돌려주는 것 — `[결과 dict, 이미지]`. 이미지는 PNG(크면 JPEG)이고 꼴은 `figure_png`, 못 만들면 까닭이 `figure_png_error` 에 온다.
    dict 칸은 `job_id` · `svg_file_id` · `svg_bytes` · `report`(콘솔 꼬리 2,500자 — 자유면 수/전체 면 수 · 등진 삼각형 수 · ink_ratio ·
    SVG 크기, 이 op 은 JSON 매니페스트가 없다) · `read_this_first`. ⚠ 삼각형을 솎지 않으므로(솎으면 구멍이 뚫려 그림이 거짓이 된다) 큰
    덱의 SVG 는 `download_result` 상한(기본 5MB · KOORM_MCP_MAX_DOWNLOAD_BYTES)을 넘을 수 있다 — 그때 `download_warning` 이 오고,
    `save_result_to_path` 로 저장하거나 `wire=true` 로 좁힌다. 이미지 블록은 이 상한과 무관하게 온다(서버가 그려 줄인다). 잡이 실패하면
    로그 꼬리가 든 오류가 난다. 단위는 주장하지 않는다(LS-DYNA 덱).
    """
    files = await _get(ctx, f"/sessions/{_seg(session_id)}/files")
    byid = {int(f["id"]): f for f in files}
    if file_id not in byid:
        raise RuntimeError(f"세션에 file_id={file_id} 가 없습니다. list_session_files 로 확인하세요.")

    args = {"model": byid[file_id]["filename"], "output": "surface",
            "azimuth": azimuth, "elevation": elevation, "wire": wire,
            "width": width, "height": height}
    job_id, outs = await _run_figure_job(ctx, session_id, "surfview", args, timeout_s)
    svg_id, svg_bytes = _pick_svg(outs)

    res = {"job_id": job_id, "svg_file_id": svg_id, "svg_bytes": svg_bytes,
           "report": await _job_log_tail(ctx, job_id)}
    MAX = int(os.environ.get("KOORM_MCP_MAX_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
    if svg_bytes > MAX:
        res["download_warning"] = (
            "SVG 가 %d bytes 로 다운로드 상한(%d)을 넘습니다 — `download_result` 가 거절합니다. "
            "`save_result_to_path` 로 디스크에 저장하거나 `wire=true` 로 좁히세요. 삼각형을 "
            "솎아서 줄이지는 않습니다(구멍이 뚫리면 그림이 거짓이 됩니다)." % (svg_bytes, MAX))
    res["read_this_first"] = (
        "`report` 가 그림이 거짓말하지 않게 하는 숫자들입니다. 자유면 비율이 그림에 무엇이 "
        "담겼는지, **등진 삼각형 수**가 뒤집힌 요소를 말합니다(닫힌 볼록체면 정확히 절반이어야 "
        "합니다). ink_ratio 가 1.0 을 넘으면 선이 포화돼 더 그려도 안 보입니다. "
        "깊이정렬은 삼각형 무게중심 기준이므로 서로 관통하는 삼각형은 순서가 틀릴 수 있습니다. "
        "단위는 없습니다(LS-DYNA 덱)."
    )
    return await _with_png(ctx, session_id, svg_id, res)


@mcp.tool(annotations=_ADD)
async def mesh_stack_diagram(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    file_id: Annotated[int, Field(description=_A_MESH_FILE_ID)],
    ctx: Context,
    axis: Annotated[Literal[MESH_STACK_AXES], Field(
        description=f"층을 재는 적층 축 — {_one_of(MESH_STACK_AXES)}(`neutralaxis` op 과 같은 축). 기본 z.")] = "z",
    force: Annotated[bool, Field(
        description="true 면 솔리드 파트의 축 범위가 포개져도 그린다 — 그림에 층 순서를 믿지 말라는 경고가 붙는다. "
                    "기본 false(포개지면 거절).")] = False,
    width: Annotated[int, Field(ge=MESH_FIG_MIN_WIDTH_PX, description=_A_MESH_WIDTH + " 기본 900.")] = 900,
    height: Annotated[int, Field(ge=MESH_FIG_MIN_HEIGHT_PX, description=_A_MESH_HEIGHT + " 기본 700.")] = 700,
    timeout_s: Annotated[int, Field(description=_A_MESH_TIMEOUT + " 기본 180.")] = 180,
) -> list:
    """적층을 층 모식도(이미지 + SVG)로 그리고 중립축 · 기하 중심면 · 굽힘강성을 같은 그림에 긋는다.

    「층이 몇 개이고 중립축이 어디냐」 를 한 그림으로 볼 때 쓴다. 격자를 자르지 않고 파트별 축 방향 범위(사실상 AABB)만 쓰는 모식도라
    평면을 고를 필요가 없다. 정확한 기하는 `mesh_section_figure`, 겉모습은 `mesh_surface_figure` 를 쓴다. 안에서 `stackdiagram` op
    잡을 내고 끝날 때까지 기다린다(잡 · SVG 가 세션에 남는다).

    ⚠ 감긴 · 접힌 적층은 솔리드 파트의 축 범위가 포개져 층 순서가 없으므로 이 도구가 거절한다 — 포갠 것을 층처럼 쌓은 그림은 그럴듯해
    보여 가장 나쁜 거짓이다. 거절 오류에 까닭(로그 꼬리)이 붙고, 그때는 `mesh_section_figure` 로 잘라 본다. `force=true` 면 그려 주되
    그림에 「믿지 말라」 가 적힌다. `*MAT` 을 못 읽으면(인클루드가 세션에 없을 때 등) 층은 그리고 중립축만 생략한다. 중립축 · 굽힘강성은
    `neutralaxis` op 과 같은 계산이다 — 숫자가 다르면 결함이다.

    돌려주는 것 — `[결과 dict, 이미지]`. 이미지는 PNG(크면 JPEG)이고 꼴은 `figure_png`, 못 만들면 까닭이 `figure_png_error` 에 온다.
    dict 칸은 `job_id` · `svg_file_id` · `svg_bytes` · `report`(콘솔 꼬리 2,500자 — 층 수(E 읽음/두께만) · 감싸는 파트 · 겹침 쌍 수 ·
    바닥 처리한 층 수 · 중립축 · 기하 중심면 · 굽힘강성, JSON 매니페스트는 없다) · `read_this_first`. 단위는 주장하지 않는다(LS-DYNA 덱).
    """
    if axis not in ("x", "y", "z"):
        raise RuntimeError("axis 는 x, y, z 중 하나여야 합니다 (받은 값: %s)" % axis)

    files = await _get(ctx, f"/sessions/{_seg(session_id)}/files")
    byid = {int(f["id"]): f for f in files}
    if file_id not in byid:
        raise RuntimeError(f"세션에 file_id={file_id} 가 없습니다. list_session_files 로 확인하세요.")

    args = {"model": byid[file_id]["filename"], "output": "stack", "axis": axis,
            "force": force, "width": width, "height": height}
    job_id, outs = await _run_figure_job(ctx, session_id, "stackdiagram", args, timeout_s)
    svg_id, svg_bytes = _pick_svg(outs)

    res = {
        "job_id": job_id, "svg_file_id": svg_id, "svg_bytes": svg_bytes,
        "report": await _job_log_tail(ctx, job_id),
        "read_this_first": (
            "`report` 가 그림이 거짓말하지 않게 하는 숫자들입니다. `Layers drawn` 의 '두께만' 은 "
            "E 를 못 읽어 중립축 계산에서 뺀 층이고, `Enclosing parts` 는 층이 아니라 적층을 "
            "품는 것(케이스·탭)이어서 점선 외곽으로만 그린 파트이며, `Floored layers` 가 0 이 "
            "아니면 **그 층의 두께는 그림이 아니라 옆에 적힌 숫자가 참**입니다. "
            "`Overlapping (shell band)` 는 정상입니다 — 셸은 두께 띠를 가진 중간면입니다. "
            "단위는 없습니다(LS-DYNA 덱)."
        ),
    }
    return await _with_png(ctx, session_id, svg_id, res)


@mcp.tool(annotations=_READ)
async def list_session_jobs(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
) -> list[_O_SESSION_JOB]:
    """세션에서 실행된 잡 이력을 최신순으로 돌려준다.

    「이 세션에서 무엇을 돌렸나 · 어느 잡이 실패했나」 를 볼 때 쓴다. 잡 하나의 자세한 상태 · 로그는 `get_job`(include_logs), 잡의
    산출 파일은 `get_job_outputs`, 새 잡은 `run_operation`. 내 세션만 보인다(남의 세션 id 면 찾을 수 없다는 오류).

    돌려주는 것 — 잡 행의 목록. 행마다 `id` · `operation` · `args` · `status`(queued · running · succeeded · failed · canceled) ·
    `progress` · `exit_code` · `error_summary` · `warnings` · `input_file_ids` · `output_file_ids` · `created_at` · `started_at` ·
    `finished_at` · `external`(외부 잡 요약, 로컬 잡이면 null). ⚠ 최신 100건까지만 온다 — 더 오래된 잡은 빠지고 잘렸다는 표시가 없다
    (이 도구는 페이지를 넘기지 못한다). 100건이 꽉 차 왔으면 더 있을 수 있다.
    """
    return await _get(ctx, f"/sessions/{_seg(session_id)}/jobs")


@mcp.tool(annotations=_READ)
async def system_capabilities(ctx: Context) -> _O_SYSTEM_CAPABILITIES:
    """플랫폼 기능 카탈로그 — 오퍼레이션 수 · MCP 도구 수 · 웹/MCP 패리티 표 · 연결 방법 · 외부 적재(intake) 규격을 돌려준다.

    「이 플랫폼이 무엇을 할 수 있고 파일을 어디로 올리나」 를 볼 때 쓴다. 건강 상태(DB · 워커 큐 · 바이너리)는 `system_status`,
    오퍼레이션 목록 · 인자는 `list_operations` · `describe_operation`, 리포트 파일을 올리는 명령은 `report_upload_instructions`.

    돌려주는 칸 — `operations`(오퍼레이션 수) · `mcp_tools`(MCP 도구 수, 못 세면 null) · `ontology`(과제 · 개정 기능 스위치
    `{enabled, source, reason, missing}` — 꺼짐은 까닭과 함께 온다) · `parity`(기능마다 `{feature, web, mcp, note?}`) · `mcp_url` ·
    `mcp_add_hint`(붙여넣을 `claude mcp add` 명령 — 공개 주소를 모르면 무엇을 설정할지 알리는 글) · `mcp_desktop_hint` ·
    `intake`(외부 적재의 공식 답 — `method` · `path` · `public_url`(운영자가 KOORM_PUBLIC_BASE 를 넣지 않았으면 null) · `token`(kr_pat) ·
    `portal_auth_required` · `max_upload_mb` · `max_report_mb` · `batch`(캠페인 묶음 적재가 있다) · `reports_per_call` ·
    `rate_limit_per_min`(토큰 하나의 분당 한도, 꺼졌으면 null) · `campaign`(캠페인 REST 경로들 · `form_fields` · `states`)).
    """
    return await _get(ctx, "/system/capabilities")


# ── 전사 코퍼스 통계 ──────────────────────────────────────────────────
# 개인 식별 없는 집계다. 세션·파일·잡·리포트는 user_id 스코프라 남의 모델을 열 수 없지만,
# '조직이 무엇을 어떻게 모델링해 왔는가' 라는 분포는 공개해도 된다. 심의(HWAX 시뮬심의·
# 시험계획)가 "일반적으로" 대신 "우리 조직은 이렇게" 를 말하려면 이 층이 필요하다.
# 전부 무인자 읽기 전용 — MCP 스모크의 실호출 검사 대상이 된다.
@mcp.tool(annotations=_READ)
async def corpus_summary(ctx: Context) -> _O_CORPUS_SUMMARY:
    """전사 모델 규모를 돌려준다 — 세션 · 파일 · 잡 수와 메시 규모 분포(개인 식별 없음).

    「우리 조직은 어느 크기의 모델을 얼마나 다루나」 를 근거로 말할 때 쓴다. 모든 사용자의 것을 세지만 소유자 · 세션명 · 파일명은 담지
    않는다. 내 세션 목록은 `list_sessions`(user_id 스코프 — 빈 배열이 전사에 없다는 뜻이 아니다). 물성 · 요소 정식 · 접촉 · 오퍼레이션 ·
    해석 결과 분포는 `material_usage` · `section_contact_usage` · `operation_usage` · `report_corpus`.

    돌려주는 칸 — `sessions` · `files` · `jobs`(전사 건수) · `mesh_scale`(`nodes` · `elements` · `parts` 마다 `{n, min, median, max,
    total}` — 업로드 때 잰 메타에 그 값이 있는 파일만 센다, 하나도 없으면 `{n: 0}`) · `note`. 표본이 적으면 분포가 오해를 부르므로 `n` 을
    함께 읽는다. 자르지 않는다.
    """
    return await _get(ctx, "/corpus/summary")


@mcp.tool(annotations=_READ)
async def material_usage(
    ctx: Context,
    limit: Annotated[int, Field(ge=1, le=CORPUS_LIMIT_MAX, description=f"돌려줄 물성 카드 수 — 파일 수 상위 N개, 1~{CORPUS_LIMIT_MAX}. "
                                                                     "기본 30.")] = 30,
) -> _O_MATERIAL_USAGE:
    """물성 카드(`*MAT_…`)마다 그것을 쓴 K파일 수를 전사로 센다(개인 식별 없음).

    시험 계획의 우선순위를 「민감도 추정」 이 아니라 「실사용 빈도」 로 근거화할 때 쓴다. 요소 정식 · 접촉 카드는 `section_contact_usage`,
    전사 규모는 `corpus_summary`. 업로드 때 잰 세션 파일 메타의 키워드 수로 센다(모든 사용자의 파일).

    돌려주는 칸 — `n_files_scanned`(메타가 있는 파일 수) · `n_files_with_material`(물성 카드가 하나라도 있는 파일 수) · `materials`(파일
    수가 많은 순 — 행마다 `{card, files, occurrences}`, files 는 그 카드가 나온 파일 수 · occurrences 는 카드 개수 합) · `note`.
    ⚠ 상위 `limit` 개만 온다 — 전체 카드 종류 수는 오지 않으므로 목록이 `limit` 개로 꽉 차면 더 있을 수 있다(limit 를 올려 다시 부른다).
    """
    return await _get(ctx, "/corpus/materials", params={"limit": limit})


@mcp.tool(annotations=_READ)
async def operation_usage(ctx: Context) -> _O_OPERATION_USAGE:
    """오퍼레이션마다 전사 실행 횟수와 성공 · 실패 수를 돌려준다(개인 식별 없음).

    조직이 실제로 쓰는 전처리 관행과 성공률을 볼 때 쓴다. 카탈로그 전체는 `list_operations`, 내 세션의 잡 이력은 `list_session_jobs`,
    물성 · 요소 정식 · 접촉 카드 분포는 `material_usage` · `section_contact_usage`.

    돌려주는 칸 — `n_jobs`(전사 잡 수) · `operations`(실행 횟수가 많은 순 — 행마다 `{operation, total, succeeded, failed, other}`, failed
    에 canceled 가 들고 other 는 아직 끝나지 않은 잡 등) · `note`. 실행 이력 기준이라 한 번도 안 돌린 오퍼레이션은 목록에 없다. 자르지
    않는다(실행된 오퍼레이션 전부).
    """
    return await _get(ctx, "/corpus/operations")


@mcp.tool(annotations=_READ)
async def section_contact_usage(
    ctx: Context,
    limit: Annotated[int, Field(ge=1, le=CORPUS_LIMIT_MAX, description=f"목록마다 돌려줄 카드 수 — 파일 수 상위 N개, 1~{CORPUS_LIMIT_MAX}"
                                                                     "(sections · contacts 에 따로). 기본 20.")] = 20,
) -> _O_SECTION_CONTACT_USAGE:
    """요소 정식(`*SECTION_…`) · 접촉(`*CONTACT_…`) 카드마다 그것을 쓴 K파일 수를 전사로 센다(개인 식별 없음).

    해석 설계 관행(어떤 요소 정식 · 접촉을 쓰나)을 근거로 말할 때 쓴다. 물성 카드는 `material_usage`, 전사 규모는 `corpus_summary`,
    오퍼레이션 관행은 `operation_usage`. 업로드 때 잰 세션 파일 메타의 키워드로 센다(모든 사용자의 파일).

    돌려주는 칸 — `n_files_scanned`(메타가 있는 파일 수) · `sections` · `contacts`(각각 파일 수가 많은 순 — 행마다 `{card, files}`).
    ⚠ 목록마다 상위 `limit` 개만 온다 — 전체 종류 수는 오지 않으므로 목록이 `limit` 개로 꽉 차면 더 있을 수 있다(limit 를 올려 다시 부른다).
    """
    return await _get(ctx, "/corpus/sections-contacts", params={"limit": limit})


@mcp.tool(annotations=_READ)
async def report_corpus(ctx: Context) -> _O_REPORT_CORPUS:
    """해석 결과 리포트의 전사 분포 — 리포트 · 케이스 수, 종류별 수, 심각도별 소견 수, 자주 나오는 소견을 돌려준다(개인 식별 없음).

    「우리 조직에서 어떤 실패 모드가 되풀이되나(설계 규칙 후보)」 를 볼 때 쓴다. 내 리포트 찾기는 `find_reports` · `list_reports`
    (user_id 스코프 — 빈 결과가 전사에 없다는 뜻이 아니다), 리포트 하나의 소견은 `report_findings`, 검색 칸 값은 `report_facets`.

    돌려주는 칸 — `reports` · `cases`(전사 건수) · `by_kind`(`[{kind, reports}]`) · `findings_by_severity`(`{CRITICAL: n, …}`, 심각도가
    없는 소견은 UNKNOWN) · `frequent_findings`(같은 제목이 많은 순 상위 10개 — `[{title, count}]`, 제목은 80자로 자른다) · `note`.
    리포트가 없으면 0 을 그대로 낸다 — 「없다」 와 「못 셌다」 는 다르다(못 세면 오류가 난다).
    """
    return await _get(ctx, "/corpus/reports")

# ── 낙하/충격 리포트 분석 ────────────────────────────────────────────
# SmartTwin 파이프라인이 만든 deep(단건 심층)·sphere(전각도 낙하)·impact(전위치
# 부분충격) 리포트 HTML 을 받아 구조화하고, 최악 케이스/파트 리스크/소견을 질의한다.
_WORST_METRICS = {"max_stress", "max_g", "max_disp", "min_safety_factor"}


@mcp.tool(annotations=_READ)
async def report_upload_instructions(
    project: Annotated[str, Field(description="명령에 넣을 과제명(intake 의 project 폼 칸). 비우면 `<과제명>` 자리를 남긴다.")] = "",
    filename: Annotated[str, Field(description="명령에 넣을 리포트 파일 경로(.html 또는 .html.gz). 비우면 `<리포트.html[.gz]>` "
                                               "자리를 남긴다.")] = "",
) -> _O_REPORT_UPLOAD_INSTRUCTIONS:
    """PC · 서버에 있는 리포트 파일을 올리는 REST intake 명령(curl)과 올리는 길을 돌려준다.

    MCP 로는 파일 본문을 나르지 않는다 — 전각도 낙하 리포트는 압축해도 수십 ~ 수백 MB, GB 급도 있어 JSON-RPC 에 못 싣는다. 대신 REST
    intake 가 리포트 + K파일(+ scenario)을 한 호출로 올린다(세션도 만든다 · .gz 면 서버가 푼다). 작은 HTML 을 이미 대화에 갖고 있으면
    `ingest_report`, 런 수백 개는 캠페인(`create_campaign` → `ingest_campaign_manifest` → 런마다 intake → `campaign_ingest_status`),
    intake 규격 값(상한 · 분당 한도)은 `system_capabilities` 의 `intake`. 이 도구는 백엔드를 부르지 않는다.

    돌려주는 칸 — `권장(스크립트)`(방법 · 엔드포인트 · 명령 · 폼필드 · 대용량 상한) · `캠페인 묶음 적재` · `웹 UI` · `토큰 발급` ·
    `note`(401 까닭 가르기). 명령의 kind 는 sphere 다 — 다른 종류면 바꿔 쓴다. ⚠ 토큰을 만들지도 담지도 않는다 — 명령의 `$KR_PAT` 는
    부르는 쪽 환경변수(kr_ PAT)다. 서버가 공개 주소를 모르면(KOORM_PUBLIC_BASE 미설정) `<포탈오리진>` 자리를 남기고 note 가 채우는 법을 말한다.
    """
    import shlex
    base = os.environ.get("KOORM_PUBLIC_BASE", "").rstrip("/")
    origin = base or "<포탈오리진>"          # 예: https://hwax.sec.samsung.net
    api = f"{origin}/apps/kooremapper_api/api/v1"
    rep = filename or "<리포트.html[.gz]>"
    curl = (f"curl -sS -X POST {shlex.quote(api + '/reports/intake')} "
            f'-H "Authorization: Bearer $KR_PAT" '
            f"-F file=@{shlex.quote(rep)} -F kfile=@<모델.k[.gz]> "
            f"-F project={shlex.quote(project or '<과제명>')} -F kind=sphere")
    return {
        "권장(스크립트)": {
            "방법": "kr_ PAT + REST intake — 리포트+K파일+scenario 를 한 호출로 반입",
            "엔드포인트": f"POST {api}/reports/intake",
            "명령": curl,
            "폼필드": "file(리포트,필수) · kfile(원본 K) · scenario(scenario.json) · "
                     "kind(deep|sphere|impact) · project · dev_rev · variation · doe · focus · "
                     "session_id(기존)/session_name(새 세션) · campaign_id + run_key(캠페인 런의 것으로 받을 때 — 둘 다)",
            "대용량": ".gz 로 올리면 서버가 해제. 전송 상한 512MB(압축 크기), 해제 상한 "
                     "2048MB(KOORM_MAX_REPORT_MB). 베어러 경로(/apps/kooremapper_api)는 portal_auth 없이 kr_ PAT 검증.",
        },
        "캠페인 묶음 적재": ("런 수백 ~ 천 개는 캠페인으로 — create_campaign → ingest_campaign_manifest(런 목록) → 런마다 위 명령에 "
                      "-F campaign_id=<id> -F run_key=<열쇠> 를 붙여 보낸다(한 호출에 리포트 하나). 같은 런에 같은 내용이 다시 "
                      "오면 건너뛰고(200 · ingest_state skipped) 다른 내용이면 거절한다(409). 올리기 길은 토큰 하나에 분당 "
                      "한도가 있다(system_capabilities 의 intake.rate_limit_per_min — 넘으면 429 와 Retry-After 초). "
                      "다시 올릴 때는 campaign_ingest_status 로 pending · rejected 런만 걸러 보낸다."),
        "웹 UI": f"포탈 로그인 후 {origin}/apps/kooremapper/ 에서 세션을 열고 '리포트 업로드'.",
        "토큰 발급": f"웹 UI 로그인→MCP 토큰 화면에서 kr_ PAT, 또는 REST POST {api}/auth/login→JWT→"
                    f"POST {api}/me/tokens. 환경변수 KR_PAT 에 둔다.",
        "note": ("MCP 로 파일 본문을 나르지 않는다(GB 급 불가) — REST intake 를 쓴다."
                 " 401 이면 응답 detail 글로 까닭을 가른다 — 「인증 토큰이 필요합니다.」 는 Authorization 헤더가 API 에 닿지 않았다"
                 "(경로 · 게이트웨이가 헤더를 넘기는지 본다) · 「토큰이 유효하지 않거나 취소·만료되었습니다.」 는 kr_ 토큰인데 이 서버가"
                 " 발급하지 않았거나(다른 인스턴스 — dev · 운영 — 에서 받은 토큰) 취소 · 만료됐다 · 「토큰이 유효하지 않거나"
                 " 만료되었습니다.」(「취소」 없음)는 kr_ 로 시작하지 않는 토큰이다(포털 자체 토큰은 받지 않는다 — 이 서버의 kr_ PAT"
                 " 를 쓴다) · detail 이 없는 401(이 서버의 JSON 꼴이 아니다)은 게이트웨이가 앞에서 막았다."
                 + ("" if base else " ⚠ 이 서버는 공개 주소를 모른다(KOORM_PUBLIC_BASE 미설정) — "
                    "<포탈오리진> 자리엔 포탈을 연 브라우저 주소창 오리진을 넣는다")),
    }


# ── 리포트 들이기 · 캠페인 · 묶음 도구의 허용값 · 경계 · 결과 꼴(공통 계약 C3 · C4 · C7) ───────────────────────────────────────
# 허용값 · 경계는 백엔드가 받는 것과 같아야 한다 — 거절 자리가 백엔드에서 MCP 로 옮길 뿐 받는 집합은 같다. 개발단계는 백엔드
# reports/datahub.py `parse_stage` 가 받는 열한 개다(dv · pv 는 차수 1 · 2 · 3 · r 필수, pre · pra · mp 는 차수 없음). 빈 글은 따로
# 받는다 — intake 폼에선 비운 칸(FastAPI 가 None 으로 읽는다), 메타 고침에선 지우기, 캠페인에선 검사 없이 그대로 둔다.
CAMPAIGN_THICKNESS_INPUTS = ("X", "Y", "Z", "x", "y", "z")   # 백엔드 CampaignBody.thickness_axis — 소문자는 대문자로 저장한다
REQUIRED_EXTRACTIONS_MAX = 200                                 # 백엔드 campaigns/routes.py `_REQUIRED_MAX`
BUNDLE_CAMPAIGNS_MAX = 20                                      # 백엔드 campaigns/routes.py `_BUNDLE_CAMPAIGNS_MAX`
_REPORT_META_ROW_OUT = {
    "id": "리포트 id — 다른 report_* 도구의 report_id.",
    "session_id": "리포트가 든 세션 id.",
    "kind": "리포트 종류 — deep · sphere · impact.",
    "label": "이름표.",
    "focus": "초점 라벨(camera-detail 등).",
    "n_cases": "케이스(각도 · 위치) 수.",
    "project_name": "리포트에 박힌 과제 이름.",
    "eng_meta": "수동 메타 — {project, dev_revision{phase, round?, code}, design_variation, doe{study, case?}}. 없으면 null.",
    "source_kfile_id": "원본 K파일의 세션 파일 id.",
    "scenario": "시뮬 조건 요약(scenario.json 을 준 때).",
    "drop_height": "낙하 높이 mm.",
    "worst_stress": "가장 큰 응력 MPa.",
    "worst_g": "가장 큰 가속도 G.",
    "max_severity": "가장 높은 소견 심각도 — CRITICAL · WARNING · INFO.",
    "created_at": "들인 시각(ISO 8601).",
    "environment": "응답을 낸 서버 환경 — dev · prod · unknown.",
}
IngestReportOut = _shape("IngestReportOut", {
    **_REPORT_META_ROW_OUT,
    "task_links": ("반입 뒤 과제 잇기의 수 — {linked, already, candidates, unmatched, kept_manual, refused, …}. 깨졌으면 {error}, "
                   "과제 · 개정 기능이 꺼져 있으면 {skipped: off}, 잠금을 다른 일이 쥐었으면 {skipped: busy}."),
})
UpdateReportMetaOut = _shape("UpdateReportMetaOut", _REPORT_META_ROW_OUT)
AttachRenderOut = _shape("AttachRenderOut", {
    "render_id": "렌더 id(render_result.json 의 것).",
    "ok": "렌더가 성공한 결과인가 — false 면 그림 없이 기록만 남았다.",
    "already": "true 면 같은 렌더 · 같은 출력이 이미 있어 바꾼 것이 없다.",
    "stored": "이번에 붙인 출력 파일 수.",
    "media_total": "붙인 뒤 리포트의 미디어 수.",
    "warnings": "렌더 결과의 경고 · 대조하지 못한 입력(목록).",
})
_CAMPAIGN_CREATED_OUT = {
    "campaign_id": "캠페인 id — 다른 캠페인 도구의 campaign_id.",
    "name": "캠페인 이름.",
    "project": "과제명.", "dev_rev": "개발단계.", "analysis_method": "해석 방법.", "analysis_target": "해석 대상.",
    "doe_strategy": "DOE 전략.", "drop_height_mm": "낙하 높이 mm.", "duration_ms": "해석 지속 시간 ms.",
    "thickness_axis": "두께 축 — X · Y · Z.", "impactor": "충격자 — {mass_g, height_mm, ke_mj}.",
    "health_thresholds": "건강 판정 문턱 묶음 — {values(다섯 값), ref(이름표), changed(기본값에서 바뀐 열쇠), defaults}.",
    "required_extractions": "필수 추출 목록 — [{field, parts, states}]. 없으면 null(모든 런의 삭제 보류).",
    "created_at": "만든 시각(ISO 8601).",
}
CreateCampaignOut = _shape("CreateCampaignOut", {**_CAMPAIGN_CREATED_OUT, "environment": "응답을 낸 서버 환경."})
IngestCampaignManifestOut = _shape("IngestCampaignManifestOut", {
    "campaign_id": "캠페인 id.",
    "added": "새로 더한 런 수(pending 으로 들어간다).",
    "updated": "보낸 칸이 바뀐 런 수.",
    "unchanged": "보냈지만 바뀐 칸이 없는 런 수.",
    "listed": "올린 뒤 목록 전체의 런 수.",
    "environment": "응답을 낸 서버 환경.",
})
CampaignIngestStatusOut = _shape("CampaignIngestStatusOut", {
    "campaign": "캠페인 칸 — create_campaign 응답과 같은 꼴.",
    "counts": "캠페인 전체의 수 — {listed, pending, received, skipped, rejected, with_report}. listed = 넷의 합.",
    "matched": "state 로 거른 런 수(쪽과 무관한 전체).",
    "runs": ("이 쪽의 런 — [{run_key, doe, pitch, roll, ingest_state, report_id, content_sha256, ingested_at, reject_reason}]. "
             "reject_reason 은 2000자에서 잘린다."),
    "limit": "이 쪽의 limit.", "offset": "이 쪽의 offset.",
    "environment": "응답을 낸 서버 환경.",
})
_HEALTH_THRESHOLDS_OUT = ("문턱 묶음 — {values(지금 쓰는 다섯 값), ref(묶음 이름표 — 런의 health.thresholds_ref), changed(기본값에서 바뀐 열쇠), "
                   "defaults(기본값)}.")
SetCampaignHealthThresholdsOut = _shape("SetCampaignHealthThresholdsOut", {
    "campaign_id": "캠페인 id.", "thresholds": _HEALTH_THRESHOLDS_OUT, "environment": "응답을 낸 서버 환경.",
})
CampaignProvenanceOut = _shape("CampaignProvenanceOut", {
    "campaign_id": "캠페인 id.",
    "generations": "설정 세대별 런 수 — [{config_generation, runs}]. 이름표 없는 런은 config_generation null.",
    "mixed_config": "이름표가 붙은 세대가 둘 이상이면 true.",
    "counts": "캠페인 전체의 수 — {listed, with_provenance, provenance_missing, superseded}.",
    "matched": "config_generation 으로 거른 런 수(쪽과 무관한 전체).",
    "runs": "이 쪽의 런 — [{run_key, doe, report_id, config_generation, superseded_by, provenance}].",
    "limit": "이 쪽의 limit.", "offset": "이 쪽의 offset.",
    "environment": "응답을 낸 서버 환경.",
})
CampaignHealthTableOut = _shape("CampaignHealthTableOut", {
    "campaign_id": "캠페인 id.",
    "header": ("머리 줄 — {total, included, excluded, excluded_by{까닭: 수}, valid, warn, invalid, line}. line 은 「유효 n / 전체 N · "
               "제외 까닭별 건수」 다. 캠페인 전체를 센다."),
    "thresholds": _HEALTH_THRESHOLDS_OUT,
    "include_invalid": "제외 까닭이 있는 런도 실었는가.",
    "matched": "실을 런 수(쪽과 무관한 전체).",
    "runs": ("이 쪽의 런 — [{run_key, doe, pitch, roll, report_id, config_generation, superseded_by, validity{status, reasons}, "
             "health, excluded_by}]."),
    "limit": "이 쪽의 limit.", "offset": "이 쪽의 offset.",
    "environment": "응답을 낸 서버 환경.",
})
ReportHealthOut = _shape("ReportHealthOut", {
    "report_id": "리포트 id.",
    "campaign": "그 런의 캠페인 — {campaign_id, name, run_key}. 캠페인 밖이거나 주인이 아니면 null.",
    "run_key": "런 열쇠. 캠페인 밖이거나 주인이 아니면 null.",
    "validity": "판정 — {status: valid | warn | invalid, reasons}.",
    "health": "건강 수치(ingest_campaign_manifest 의 health 칸) + thresholds_ref. 없으면 null.",
    "excluded_by": "기본 통계에서 빼는 까닭 목록 — invalid 까닭 · superseded · provenance_missing.",
    "config_generation": "설정 세대(캠페인 런일 때만).",
    "superseded_by": "이 런을 대체한 run_key(캠페인 런일 때만).",
    "thresholds": _HEALTH_THRESHOLDS_OUT + " 캠페인 밖이면 null.",
    "environment": "응답을 낸 서버 환경.",
})
SetCampaignRequiredExtractionsOut = _shape("SetCampaignRequiredExtractionsOut", {
    "campaign_id": "캠페인 id.",
    "required_extractions": "저장한 목록 — [{field, parts(정렬 · 겹침 없이, null = 모든 파트), states}]. 지웠으면 null.",
    "environment": "응답을 낸 서버 환경.",
})
CampaignDeletionClearanceOut = _shape("CampaignDeletionClearanceOut", {
    "campaign_id": "캠페인 id.",
    "header": ("머리 줄 — {total, allow, hold, deleted, reasons{까닭: 수}, line}. line 은 「삭제 허가 a / 전체 N · 보류 h · 이미 지움 d」"
               " 와 까닭별 수다. 캠페인 전체를 센다."),
    "required_extractions": "캠페인의 필수 추출 목록(없으면 null).",
    "matched": "status 로 거른 런 수(쪽과 무관한 전체).",
    "runs": ("이 쪽의 런 — [{run_key, doe, report_id, extraction, peak_provenance, clearance{status, reasons, missing}}]."),
    "limit": "이 쪽의 limit.", "offset": "이 쪽의 offset.",
    "environment": "응답을 낸 서버 환경.",
})
ReportExtractionOut = _shape("ReportExtractionOut", {
    "report_id": "리포트 id.",
    "campaign": "그 런의 캠페인 — {campaign_id, name, run_key}. 캠페인 밖이거나 주인이 아니면 null.",
    "run_key": "런 열쇠. 캠페인 밖이거나 주인이 아니면 null.",
    "extraction": "런의 추출 목록(ingest_campaign_manifest 의 extraction 칸). 캠페인 밖이면 null.",
    "peak_provenance": "피크 출처 표지 — {known, peak_source, states_read, states_total, peak_may_be_missed}.",
    "clearance": "그 런의 d3plot 삭제 허가 — {status: allow | hold | deleted, reasons, missing}. 캠페인 밖이거나 주인이 아니면 null.",
    "environment": "응답을 낸 서버 환경.",
})
_BUNDLE_HEAD_OUT = {
    "bundle_id": "묶음 주소 — 다음 판을 지을 때 · 읽을 때 쓴다.",
    "version": "판 번호(1 부터).",
    "label": "이름표.",
    "campaign_ids": "담은 캠페인 id 목록.",
    "as_of": "기준 시각 — 그때까지 받은 리포트만 넣었다.",
    "created_at": "판을 지은 시각.",
    "basis": ("수치 기준 — {campaigns[{campaign_id, total, included, valid_runs, excluded_by, thresholds_ref, generations, line}], "
              "include_invalid, units, items, line}. line 이 캠페인마다 「유효 n / 전체 N · 제외 까닭」 이다."),
    "citation": "인용 꼴 — {source_platform, source_kind, source_id, source_version, scope}.",
    "changes_counts": "앞 판 대비 바뀐 숫자 수 — {added, removed, changed}. 첫 판이면 null.",
}
BuildReportBundleOut = _shape("BuildReportBundleOut", {
    **_BUNDLE_HEAD_OUT,
    "unchanged": "true 면 숫자가 마지막 판과 같아 판을 올리지 않고 그 판을 돌려줬다.",
    "counts": "이 판의 크기 — {items(숫자 항목 수), tables, figures}.",
    "environment": "응답을 낸 서버 환경.",
})
ReportBundleOut = _shape("ReportBundleOut", {
    **_BUNDLE_HEAD_OUT,
    "spec": "기본값을 채운 명세 — {tables[{kind, metrics, parts}], figures{roles, exts}, include_invalid}.",
    "tables": "표 — [{kind, columns, rows, units}]. 쪽으로 나누지 않고 통째로 싣는다.",
    "figures": "인용한 그림 — [{campaign_id, run_key, report_id, file_id, path, ext, case_key, role, bytes, sha256}].",
    "sources": "출처 — {reports[{campaign_id, run_key, report_id, cases}], figures, thresholds_refs, …}.",
    "changes": "앞 판 대비 바뀐 숫자 — {added, removed, changed, counts}. 첫 판이면 null.",
    "versions": "이 주소의 판 목록 — [{version, created_at}].",
    "latest_version": "이 주소의 마지막 판 번호.",
    "items": ("items=true 일 때만 — {total, offset, limit, rows[{item_key, value, unit, source_path, source}]}. "
              "offset + limit < total 이면 이어 받는다."),
    "environment": "응답을 낸 서버 환경.",
})
ReportBundleDiffOut = _shape("ReportBundleDiffOut", {
    "bundle_id": "묶음 주소.",
    "from_version": "앞 판.", "to_version": "뒤 판.",
    "added": "더해진 숫자 — [{item_key, value, unit, source_path}]. 통째로 싣는다.",
    "removed": "빠진 숫자 — [{item_key, value, unit, source_path}]. 통째로 싣는다.",
    "changed": "값 · 단위가 바뀐 숫자 — [{item_key, old, new, unit, old_unit, source_path}]. 통째로 싣는다.",
    "counts": "수 — {added, removed, changed}.",
    "environment": "응답을 낸 서버 환경.",
})


@mcp.tool(annotations=_ADD)
async def ingest_report(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    filename: Annotated[str, Field(description=(
        "리포트 파일 이름(예 drop_sphere.html) — 저장 이름이 된다. .gz 로 끝나거나 바이트가 gzip 이면 서버가 푼다."))],
    html_content: Annotated[str, Field(description=(
        "리포트 HTML 전체 — koo_deep_report · koo_sphere_report · koo_impact_report 가 만든 것(데이터가 임베드돼 있다). "
        "base64_encoded 가 true 면 그 바이트(gzip 도 된다)의 base64 글."))],
    ctx: Context,
    kind: Annotated[Literal[REPORT_KINDS] | Literal[""] | None, Field(description=(
        f"리포트 종류(선택) — {_one_of(REPORT_KINDS)}. 주면 자동 판별을 덮어쓴다. 비우거나 빈 글이면 자동 판별."))] = None,
    label: Annotated[str | None, Field(description="이름표(선택 · 자유 글) — 목록에 보일 이름. 비우면 없음.")] = None,
    base64_encoded: Annotated[bool, Field(description=(
        "true 면 html_content 를 base64 로 풀어 쓴다(큰 HTML · gzip 바이트). 기본 false — UTF-8 글 그대로."))] = False,
    scenario_content: Annotated[str | dict | None, Field(description=(
        "시뮬 조건 scenario.json 글 또는 그 JSON 객체(선택) — 조건 요약을 붙이고 template 으로 세션 안 K파일을 자동으로 맞춘다(한 K파일에 결과 "
        "여럿). 비우면 없음."))] = None,
    kfile_id: Annotated[int | None, Field(description=(
        "원본 K파일의 세션 파일 id(선택) — list_session_files 의 id. 같은 세션의 파일이어야 한다. 비우면 scenario 로 자동으로 "
        "맞추고, scenario 도 없으면 잇지 않는다."))] = None,
    project: Annotated[str | None, Field(description=(
        "과제명(선택) — 비우면 리포트에 박힌 과제 이름. dev_rev 와 함께 있으면 반입 때 개정에 잇는다."))] = None,
    dev_rev: Annotated[Literal[DEV_REV_CODES] | Literal[""] | None, Field(description=(
        f"개발단계(선택) — {_one_of(DEV_REV_CODES)}. 빈 글은 주지 않은 것과 같다."))] = None,
    variation: Annotated[str | None, Field(description="설계안(선택 · 자유 글).")] = None,
    doe: Annotated[str | None, Field(description="DOE 참조(선택) — `study` 또는 `study:case`.")] = None,
) -> IngestReportOut:
    """낙하 · 충격 리포트 HTML 한 건을 세션에 들여와 구조화한다(deep · sphere · impact 자동 판별).

    html_content 를 글로 나르므로 수십 MB 넘는 리포트(전각도 낙하 등)는 이 도구가 아니다 — REST intake 로 올린다
    (`report_upload_instructions` 가 리포트 + K파일 한 호출 명령을 준다). 런 수백 개는 캠페인 길(`create_campaign` →
    `ingest_campaign_manifest` → intake)이다. 들인 뒤 메타 고침은 `update_report_meta`, 렌더 붙이기는 `attach_render`.

    project(없으면 리포트에 박힌 과제 이름)와 dev_rev 가 있으면 반입 때 개정에 잇는다 — 허브 받기 뒤 자동 잇기와 같은 판정이다.
    이름(과제명 · 과제코드 · 옛 과제명 · 별칭)이 허브 과제 하나로 풀리면 그 과제의 판에, 여러 과제에 걸리거나 이름(label)만 같으면
    잇지 않고 후보로 남기며(`plan_task_links` · `report_revision` 의 `task_candidates`), 허브가 모르는 이름은 글자 그대로의 판
    (`<project>@<dev_rev>`)에 잇는다. 과제 · 개정 기능이 꺼져 있으면 판정 없이 글자 그대로의 판에 잇고(허브가 바꾼 옛 과제명만 지금
    이름으로 푼다) `report_revision` · `plan_task_links` 는 거절된다. 선은 `report_revision` 의 `linked` 로 본다.

    돌려주는 것 — 리포트 행(id · kind · n_cases · eng_meta · 가장 큰 응력 · 가속도 …)과 `task_links`(반입 뒤 잇기의 수). 반입 때
    이어졌으면 `already` 1 이고 `linked` 는 그 뒤 새로 잇거나 옮긴 수다. `candidates` · `unmatched` 는 하나로 풀리지 않은 이름의
    수로 선이 있는지와 따로다. 깨졌으면 `error`(반입은 그대로) · 기능이 꺼져 있으면 `skipped: off`. 업로드는 분당 한도가 있다(429)."""
    raw = base64.b64decode(html_content) if base64_encoded else html_content.encode("utf-8")
    data = {}
    for k, v in (("kind", kind), ("label", label), ("kfile_id", kfile_id),
                 ("project", project), ("dev_rev", dev_rev),
                 ("variation", variation), ("doe", doe)):
        if v is not None:
            data[k] = str(v)
    files = {"file": (filename, raw, "text/html")}
    if isinstance(scenario_content, dict):
        # SDK 는 str 가 아닌 칸에 온 JSON 꼴 글을 객체로 먼저 푼다 — scenario.json 글이 「Input should be a valid string」 으로 막혔었다
        import json as _json
        scenario_content = _json.dumps(scenario_content, ensure_ascii=False, indent=2)
    if scenario_content:
        files["scenario"] = ("scenario.json", scenario_content.encode("utf-8"), "application/json")
    async with _client() as c:
        return _unwrap(await c.post(
            f"/sessions/{_seg(session_id)}/reports",
            files=files, data=data, headers=_forward_headers(ctx),
        ))


@mcp.tool(annotations=_SET)
async def update_report_meta(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    label: Annotated[str | None, Field(description="이름표(선택 · 255자까지). 빈 글이면 지운다 · 비우면 그대로.")] = None,
    project: Annotated[str | None, Field(description=(
        "과제명(선택 · 64자까지). 빈 글이면 지운다(그때 잇기는 리포트에 박힌 과제 이름을 쓴다) · 비우면 그대로."))] = None,
    dev_rev: Annotated[Literal[DEV_REV_CODES] | Literal[""] | None, Field(description=(
        f"개발단계(선택) — {_one_of(DEV_REV_CODES)}. 빈 글이면 지운다 · 비우면 그대로."))] = None,
    variation: Annotated[str | None, Field(description="설계안(선택 · 64자까지). 빈 글이면 지운다 · 비우면 그대로.")] = None,
    doe: Annotated[str | None, Field(description=(
        "DOE 참조(선택 · 128자까지) — `study` 또는 `study:case`. 빈 글이면 지운다 · 비우면 그대로."))] = None,
    kfile_id: Annotated[int | None, Field(description=(
        "원본 K파일의 세션 파일 id(선택) — list_session_files 의 id. 리포트와 같은 세션의 파일이어야 한다. 비우면 그대로(지우는 "
        "값은 없다)."))] = None,
    focus: Annotated[str | None, Field(description=(
        "초점 라벨(선택 · 64자까지 · 예 camera-detail). 빈 글이면 지운다 · 비우면 그대로."))] = None,
) -> UpdateReportMetaOut:
    """리포트의 수동 메타(이름표 · 과제명 · 개발단계 · 설계안 · DOE · 초점 · 원본 K파일)를 부분 갱신한다.

    안 준 칸은 그대로, 빈 글은 그 칸을 지운다. 적어 두면 DataHub 등재 때 과제 · 단계를 다시 넣지 않는다. 리포트 소유자만 고친다.
    새 리포트를 들이는 것은 `ingest_report`, 개정 선을 손으로 정하거나 끊는 것은 `set_report_revision` · `unlink_report_revision`.

    project 나 dev_rev 를 주면 기계가 이은 개정 선이 따라간다 — 허브 받기 뒤 자동 잇기와 같은 판정이다. 이름(과제명 · 과제코드 ·
    옛 과제명 · 별칭)이 허브 과제 하나로 풀리면 그 과제의 판으로 가고(이미 거기면 그대로), 여러 과제에 걸리거나 이름(label)만 같으면
    어디로도 가지 않는다 — 있던 선은 그대로고 메타와 다르면 `report_revision` 의 `mismatch` 가 말한다(후보는 그 `task_candidates` ·
    `plan_task_links`). 허브가 모르는 이름이면 글자 그대로의 판(`<project>@<dev_rev>`)으로 간다. 과제 이름이나 dev_rev 가 없으면
    선은 그대로다. 사람이 손으로 정한 선(`set_report_revision`)과 사람이 끊은 리포트(`report_revision` 의 `unlinked`)는 메타만
    저장하고 다시 잇지 않는다 — 다시 잇게 하려면 `set_report_revision` 또는 `clear_report_unlink`. 설계안 · DOE 만 고치면 선을 보지
    않는다. 과제 · 개정 기능이 꺼져 있으면 판정 없이 글자 그대로의 판으로 간다(허브가 바꾼 옛 과제명만 지금 이름으로 푼다 · 사람이
    정한 선과 끊은 리포트는 그때도 그대로 · `report_revision` 은 거절된다).

    돌려주는 것 — 고친 리포트 행(id · label · focus · eng_meta · source_kfile_id …). 선이 어떻게 됐는지는 싣지 않는다 —
    `report_revision` 으로 본다."""
    body = {k: v for k, v in {
        "label": label, "project": project, "dev_rev": dev_rev,
        "variation": variation, "doe": doe, "kfile_id": kfile_id, "focus": focus,
    }.items() if v is not None}
    async with _client() as c:
        return _unwrap(await c.patch(
            f"/reports/{_seg(report_id)}", json=body, headers=_forward_headers(ctx)))


@mcp.tool(annotations=_ADD_OUT)
async def attach_render(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    path: Annotated[str, Field(description=(
        "MCP 서버 박스의 경로 — SceneForge 결과 폴더(render_result.json + mp4 · 정지 화면 PNG, 맨 위 파일만 싣는다) 또는 그 "
        "폴더를 묶은 zip. 묶음 전송 상한은 업로드 상한(기본 512 MB)이다."))],
    ctx: Context,
) -> AttachRenderOut:
    """SceneForge 렌더 결과(결과 폴더 또는 zip)를 리포트의 미디어로 더한다.

    MCP 서버가 그 경로를 읽을 수 있는 같은 머신에서만 된다(`upload_local_path` 와 같다). 폴더면 맨 위 파일만 묶어 보내고 하위
    폴더는 빠진다. 리포트 소유자만 붙인다. StepForge CAD 묶음은 `attach_cad`, 해석 온톨로지 꾸러미는 `attach_cae_package`,
    붙은 그림 보기는 `report_media`.

    기존 미디어를 지우지 않고 더한다. 같은 render_id 를 같은 출력으로 다시 붙이면 바꾸는 것이 없고(`already: true`), 출력이 다르면
    그 렌더의 옛 파일 · 항목만 바꾼다. 같은 render_id 가 성공 · 실패를 바꿔 오면 거절한다. 결과의 run.report_id 가 이 리포트,
    run.case_key 가 이 리포트의 케이스여야 하고, 파일마다 sha256 · 크기가 결과에 적힌 값과 맞아야 한다 — 하나라도 다르거나 적히지
    않은 파일이 끼면 통째로 거절한다(전부 아니면 전무 — 아무것도 저장하지 않는다). 실패한 렌더(`ok: false`)는 그림 없이 기록만
    남는다.

    돌려주는 것 — render_id · ok · already · stored(이번에 붙인 파일 수) · media_total(리포트의 미디어 수) · warnings."""
    import io as _io
    import os as _os
    import zipfile as _zf
    if _os.path.isdir(path):
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, "w", _zf.ZIP_STORED) as z:
            for name in sorted(_os.listdir(path)):
                full = _os.path.join(path, name)
                if _os.path.isfile(full):            # 결과 폴더는 평평하다 — 하위 폴더는 싣지 않는다
                    z.write(full, arcname=name)
        raw = buf.getvalue()
    elif _os.path.isfile(path):
        with open(path, "rb") as fh:
            raw = fh.read()
    else:
        raise RuntimeError(f"path not found on the MCP host: {path}")
    files = {"file": ("render_result.zip", raw, "application/zip")}
    async with _client() as c:
        return _unwrap(await c.post(f"/reports/{_seg(report_id)}/renders", files=files, headers=_forward_headers(ctx)))


# ── 캠페인 묶음 적재(DF-01 · 계획 df-campaign-intake-1120) ───────────────────────────────────────────────────────────────
# 한 과제 · 한 판의 런 수백 ~ 천 개를 캠페인 하나로 묶어 받는다. ★파일 본문은 이 도구들로 오지 않는다 — 런마다 REST intake 에
# campaign_id · run_key 를 붙여 보낸다(report_upload_instructions). 상태 단어 · 건수 상한은 백엔드와 같아야 한다
# (test_mcp_tools_contract 가 대조한다).
CAMPAIGN_STATES = ("pending", "received", "skipped", "rejected")
CAMPAIGN_RUNS_MAX = 5000
CLEARANCE_STATUSES = ("allow", "hold", "deleted")   # 백엔드 GET /campaigns/{id}/deletion-clearance 의 status 와 같아야 한다
_A_REQUIRED = ("필수 추출 목록 — 항목마다 field(자유 글 128자까지 · 대소문자 · 앞뒤 공백은 가리지 않는다) · parts(정수 목록 · 없으면 모든 파트) · "
               "states(all · sampled — 기본 all, 모든 상태를 읽은 추출이어야 채워진다). 같은 항목이 둘이면 거절된다.")
_A_CAMPAIGN_ID = "캠페인 id — create_campaign 응답의 campaign_id(같은 이름으로 다시 만들면 오류 글에 그 id 가 있다)."
# 건강 판정 문턱(DF-03) — 열쇠 · 기본값은 백엔드 campaigns/health.py `DEFAULTS` 와 같아야 한다(test_mcp_tools_contract 가 대조한다)
HEALTH_THRESHOLD_DEFAULTS = {"energy_ratio_max": 1.05, "hg_over_ie_max": 0.10, "added_mass_pct_max": 0.5, "ke0_rel_tol": 0.10,
                             "contact_energy_min_mJ": -100.0}
_A_THRESHOLDS = ("건강 판정 문턱(선택) — 바꿀 열쇠만: energy_ratio_max(1.05 — 에너지비가 넘으면 warn) · hg_over_ie_max(0.10 — "
                 "HG/IE 비가 이 값 이상이면 warn) · added_mass_pct_max(0.5 — 추가 질량 % 기기 값, 없으면 전체 값) · "
                 "ke0_rel_tol(0.10 — 첫 KE 와 ½mv² 의 상대 차이) · contact_energy_min_mJ(-100 — 자체 접촉 에너지가 이보다 낮으면 "
                 "warn). 미끄럼 에너지는 문턱이 없다. 다른 열쇠는 거절된다.")


@mcp.tool(annotations=_ADD)
async def create_campaign(
    name: Annotated[str, Field(description=(
        "캠페인 이름(1~255자 · 앞뒤 공백은 떼고 저장한다) — 내 캠페인 안에서 하나뿐이어야 한다."))],
    ctx: Context,
    project: Annotated[str | None, Field(
        description="과제명(선택 · 64자까지) — 적어 두는 값이다. 리포트 메타는 intake 폼의 project 가 정한다.")] = None,
    dev_rev: Annotated[Literal[DEV_REV_CODES] | Literal[""] | None, Field(description=(
        f"개발단계(선택) — {_one_of(DEV_REV_CODES)}. 적어 두는 값이다(리포트 메타는 intake 폼의 dev_rev). 빈 글은 검사 없이 "
        "그대로 둔다."))] = None,
    analysis_method: Annotated[str | None, Field(description="해석 방법(선택 · 64자까지) — 온 글 그대로 둔다.")] = None,
    analysis_target: Annotated[str | None, Field(description="해석 대상(선택 · 64자까지) — 온 글 그대로 둔다.")] = None,
    doe_strategy: Annotated[str | None, Field(description="DOE 전략(선택 · 64자까지) — 온 글 그대로 둔다.")] = None,
    drop_height_mm: Annotated[float | None, Field(ge=0, description="낙하 높이 mm(선택 · 0 이상).")] = None,
    duration_ms: Annotated[float | None, Field(ge=0, description="해석 지속 시간 ms(선택 · 0 이상).")] = None,
    thickness_axis: Annotated[Literal[CAMPAIGN_THICKNESS_INPUTS] | None, Field(description=(
        "두께 축(선택) — X · Y · Z(소문자도 받아 대문자로 저장한다). 캠페인 분석 도구가 두께축을 안 받으면 이 값을 쓴다(없으면 "
        "Z)."))] = None,
    impactor: Annotated[dict | None, Field(description=(
        "충격자(선택) — {mass_g(g), height_mm(mm), ke_mj(mJ)} 가운데 아는 것만(모두 0 이상). 예 {\"mass_g\": 32.5, "
        "\"height_mm\": 1000}. 다른 열쇠는 거절된다."))] = None,
    health_thresholds: Annotated[dict | None, Field(description=(
        _A_THRESHOLDS + " energy_ratio_max · hg_over_ie_max 는 0 보다 크고 added_mass_pct_max · ke0_rel_tol 은 0 이상. "
        "예 {\"energy_ratio_max\": 1.1}. 비우면 모두 기본값 · 나중엔 set_campaign_health_thresholds."))] = None,
    required_extractions: Annotated[list[dict] | None, Field(max_length=REQUIRED_EXTRACTIONS_MAX, description=(
        _A_REQUIRED + f" {REQUIRED_EXTRACTIONS_MAX}항목까지. 예 [{{\"field\": \"stress\", \"parts\": [12, 15]}}]. 선택이다 — 비우면 "
        "목록이 없어 모든 런의 d3plot 삭제가 보류된다(required_extractions_unset). 나중엔 set_campaign_required_extractions."))] = None,
) -> CreateCampaignOut:
    """캠페인(한 과제 · 한 판의 런 묶음)을 만든다 — 응답의 `campaign_id` 로 런 목록을 올리고 리포트를 받는다.

    차례 — `create_campaign` → `ingest_campaign_manifest`(런 목록) → 런마다 REST intake 에 `campaign_id` · `run_key` 를 붙여
    리포트를 보낸다(`report_upload_instructions`) → `campaign_ingest_status` 로 수를 맞춘다. 리포트 한 건을 세션에 바로 들이는 것은
    `ingest_report` 다.

    같은 이름을 이미 썼으면 오류고 그 글에 있던 캠페인의 id 가 있다(id 를 잊었을 때도 이렇게 찾는다 — 캠페인 목록 · 고침 · 지우기
    도구는 없다). 문턱 · 필수 추출은 나중에 `set_campaign_health_thresholds` · `set_campaign_required_extractions` 로 통째로 바꾼다.
    필수 추출은 선택이지만 없으면 모든 런의 d3plot 삭제가 보류된다(`campaign_deletion_clearance`). 캠페인은 만든 사람만 본다.

    돌려주는 것 — campaign_id · 적은 칸 그대로 · health_thresholds(문턱 묶음 — values · ref · changed · defaults) ·
    required_extractions · created_at."""
    body = {k: v for k, v in {
        "name": name, "project": project, "dev_rev": dev_rev, "analysis_method": analysis_method,
        "analysis_target": analysis_target, "doe_strategy": doe_strategy, "drop_height_mm": drop_height_mm,
        "duration_ms": duration_ms, "thickness_axis": thickness_axis, "impactor": impactor,
        "health_thresholds": health_thresholds, "required_extractions": required_extractions,
    }.items() if v is not None}
    return await _post(ctx, "/campaigns", body)


@mcp.tool(annotations=_SET)
async def ingest_campaign_manifest(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    runs: Annotated[list[dict], Field(min_length=1, max_length=CAMPAIGN_RUNS_MAX, description=(
        f"런 목록(1~{CAMPAIGN_RUNS_MAX}건) — 항목마다 run_key(필수 · 빈칸 없는 글 128자까지 · `stcx:<잡 id>:<DOE>` 꼴을 권한다) · "
        "doe · pitch · roll(선택) · provenance(출처 — wrapper_name · wrapper_version · prescription_set · scenario_sha256 · "
        "runner_config_sha256 · deck_sha256 · include_sha256[] · solver{} · sif_version · deep_report_tool_commit · "
        "deep_report_flags · submitted_at) · config_generation(설정 세대 이름표 64자) · superseded_by(이 런을 대체한 같은 캠페인 "
        "런의 run_key) · health(건강 수치 — normal_termination · scheduler_state · energy_ratio_max · hg_over_ie_max(비) · "
        "added_mass_pct_device · added_mass_pct_total · ke0_measured · ke0_expected · contact_energy_min_mJ · nan_onset_ms · "
        "json_complete) · extraction(추출 목록 — d3plot_states_total · d3plot_states_read(total 이하) · peak_source(binout · elout · "
        "d3plot_full · d3plot_sampled) · fields_extracted[](글 또는 {field, parts[], states: all | sampled}) · d3plot_retained · "
        "d3plot_deleted_at) · impacts(충격 구간 50 개까지 — 항목 {index(1 부터 · 겹치면 거절), t_start_ms, t_end_ms?, ke_frac?, "
        "peaks?{무리 키: 그 충격의 피크}} — 각도 표 · 피크 표의 충격 수 · 차수가 이것으로 센다). 다른 열쇠는 거절된다. "
        "예 [{\"run_key\": \"stcx:4512:p030r045\", \"pitch\": 30, \"roll\": 45, \"health\": {\"normal_termination\": true}}]."))],
    ctx: Context,
) -> IngestCampaignManifestOut:
    """캠페인의 런 목록(매니페스트)을 올린다 — 리포트를 받기 전에 「무엇이 올 것인가」 를 먼저 적는다.

    `create_campaign` 다음, 런마다 리포트를 intake 로 보내기 전에 부른다. 목록에 없는 `run_key` 로 온 리포트는 거절된다.
    새 `run_key` 는 pending 으로 더하고, 있는 것은 상태 · 리포트를 둔 채 보낸 칸(doe · pitch · roll · provenance ·
    config_generation · superseded_by · health · extraction · impacts)만 맞춘다 — 객체 칸은 통째로 바뀌고, 안 보낸 칸은 그대로고
    null 을 보내면 비운다. `superseded_by` 는 같은 캠페인의 다른 run_key 여야 한다(같은 요청에서 더하는 런도 된다 · 자기 자신 ·
    고리는 거절 — 그때는 아무것도 바뀌지 않는다). 같은 목록을 다시 올려도 된다. 한 요청 안에 같은 `run_key` 가 둘이면 거절이고,
    목록에서 런을 빼는 길은 없다.

    건강 문턱 · 필수 추출은 캠페인 쪽(`set_campaign_health_thresholds` · `set_campaign_required_extractions`)이다. 올린 뒤에는
    `campaign_ingest_status`(적재) · `campaign_provenance`(출처) · `campaign_health_table`(건강) ·
    `campaign_deletion_clearance`(삭제 허가)로 본다.

    돌려주는 것 — campaign_id · added(새 런) · updated(보낸 칸이 바뀐 런) · unchanged · listed(올린 뒤 목록 전체 런 수)."""
    return await _post(ctx, f"/campaigns/{_seg(campaign_id)}/runs", {"runs": runs})


@mcp.tool(annotations=_READ)
async def campaign_ingest_status(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    state: Annotated[Literal[CAMPAIGN_STATES] | None, Field(
        description=f"이 상태의 런만(선택) — {_one_of(CAMPAIGN_STATES)}. 비우면 모두.")] = None,
    limit: Annotated[int, Field(ge=1, le=CAMPAIGN_RUNS_MAX, description=(
        f"한 번에 받을 런 수(1~{CAMPAIGN_RUNS_MAX} · 기본 200). 수(`counts`)는 이 값과 무관하게 캠페인 전체다."))] = 200,
    offset: Annotated[int, Field(ge=0, description=(
        "건너뛸 런 수(0 이상 · 목록 순서) — offset + limit 이 `matched` 보다 작으면 offset 을 늘려 이어 받는다."))] = 0,
) -> CampaignIngestStatusOut:
    """캠페인의 적재 상태 — 목록 수 · 상태별 수 · 런마다 상태 · report_id · 지문(sha256) · 거절 까닭을 본다.

    리포트를 다시 올리기 전에 `state` 를 pending · rejected 로 걸러 그 런만 보낸다 — 건너뛰는 런도 파일을 통째로 보내야 건너뛴다.
    출처는 `campaign_provenance`, 건강 판정은 `campaign_health_table`, d3plot 삭제 허가는 `campaign_deletion_clearance`.

    `counts.listed = pending + received + skipped + rejected` 가 늘 맞는다. `ingest_state` 는 그 런의 마지막 시도 결과고
    `report_id` 는 그 런이 가진 리포트다 — 가진 리포트가 있는데 뒤에 다른 내용이 와 거절된 런은 rejected 이면서 report_id 가
    있다(`counts.with_report` 가 리포트를 가진 런 수). pending = 목록에만 있다(또는 가졌던 리포트가 지워졌다) · received = 받았다 ·
    skipped = 같은 내용이 다시 와 건너뛰었다 · rejected = 거절(`reject_reason` — 2000자에서 잘린다). 런에 적히지 않는 실패 —
    401(토큰) · 429(분당 한도) · 요청 꼴 오류(file 칸 없음) · 게이트웨이가 앞에서 막은 요청 · 5xx 는 런 상태를 바꾸지 않는다.

    돌려주는 것 — campaign(캠페인 칸) · counts · matched(거른 런 수) · runs(이 쪽 — run_key · doe · pitch · roll · ingest_state ·
    report_id · content_sha256 · ingested_at · reject_reason) · limit · offset."""
    params = {"limit": limit, "offset": offset}
    if state is not None:
        params["state"] = state
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/ingest-status", params)



@mcp.tool(annotations=_SET)
async def set_campaign_health_thresholds(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    energy_ratio_max: Annotated[float | None, Field(gt=0, description=(
        "에너지비 문턱(0 초과 · 비우면 기본 1.05) — 런의 energy_ratio_max 가 넘으면 warn(energy_ratio)."))] = None,
    hg_over_ie_max: Annotated[float | None, Field(gt=0, description=(
        "HG/IE 비 문턱(0 초과 · 비우면 기본 0.10 = 10 %) — 이 값 이상이면 warn(hourglass)."))] = None,
    added_mass_pct_max: Annotated[float | None, Field(ge=0, description=(
        "추가 질량 문턱 %(0 이상 · 비우면 기본 0.5) — 기기 값(added_mass_pct_device, 없으면 added_mass_pct_total)이 넘으면 "
        "warn(added_mass)."))] = None,
    ke0_rel_tol: Annotated[float | None, Field(ge=0, description=(
        "첫 KE 와 ½mv² 의 상대 차이 문턱(0 이상 · 비우면 기본 0.10 = 10 %) — 넘으면 warn(ke0_mismatch)."))] = None,
    contact_energy_min_mJ: Annotated[float | None, Field(description=(
        "자체 접촉 에너지 문턱 mJ(비우면 기본 -100) — 런의 값이 이보다 낮으면 warn(contact_energy)."))] = None,
) -> SetCampaignHealthThresholdsOut:
    """캠페인의 건강 판정 문턱 다섯을 통째로 바꾼다 — 안 준 열쇠는 기본값이다(아무것도 안 주면 모두 기본값으로 돌린다).

    판정은 읽을 때 세므로 바꾼 문턱이 곧바로 `campaign_health_table` · `report_health` 와 다음에 짓는 묶음
    (`build_report_bundle`)에 든다. 캠페인을 만들 때 함께 주려면 `create_campaign` 의 health_thresholds. 런의 건강 수치는
    `ingest_campaign_manifest` 의 health 칸으로 올린다. 정상 종료 아님 · NaN · 잘린 JSON · 첫 KE 0 이하는 문턱 없이 invalid 다.
    미끄럼 에너지는 문턱이 없다. 캠페인 주인만 바꾼다.

    돌려주는 것 — campaign_id · thresholds(values — 지금 쓰는 다섯 값 · ref — 묶음 이름표로 런의 `health.thresholds_ref` 와 같다 ·
    changed — 기본값에서 바뀐 열쇠 · defaults)."""
    body = {k: v for k, v in {
        "energy_ratio_max": energy_ratio_max, "hg_over_ie_max": hg_over_ie_max, "added_mass_pct_max": added_mass_pct_max,
        "ke0_rel_tol": ke0_rel_tol, "contact_energy_min_mJ": contact_energy_min_mJ,
    }.items() if v is not None}
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/health-thresholds", body)


@mcp.tool(annotations=_READ)
async def campaign_provenance(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    config_generation: Annotated[str | None, Field(description=(
        "이 설정 세대의 런만(선택 · 64자까지 · 같은 글만) — 세대 이름은 이 도구의 generations 에 있다. 비우면 모두."))] = None,
    limit: Annotated[int, Field(ge=1, le=CAMPAIGN_RUNS_MAX, description=(
        f"한 번에 받을 런 수(1~{CAMPAIGN_RUNS_MAX} · 기본 200). 분포 · 수는 이 값과 무관하게 전체다."))] = 200,
    offset: Annotated[int, Field(ge=0, description=(
        "건너뛸 런 수(0 이상 · 목록 순서) — offset + limit 이 `matched` 보다 작으면 offset 을 늘려 이어 받는다."))] = 0,
) -> CampaignProvenanceOut:
    """캠페인의 런 출처 — 설정 세대별 런 수 · 세대가 섞였는지 · 출처가 빈 런 · 대체된 런과 런마다 출처를 본다.

    출처는 `ingest_campaign_manifest` 의 provenance · config_generation · superseded_by 칸으로 올린다. 출처가 빈 런과 대체된 런은
    기본 통계에서 빠진다(`campaign_health_table` 의 excluded_by — provenance_missing · superseded). 적재 상태는
    `campaign_ingest_status`, 설정 세대끼리 견주기는 `compare_config_pairs`.

    돌려주는 것 — campaign_id · generations([{config_generation, runs}] — 이름표 없는 런은 config_generation null) ·
    mixed_config(이름표가 붙은 세대가 둘 이상이면 true) · counts(listed · with_provenance · provenance_missing · superseded — 캠페인
    전체) · matched(거른 런 수) · runs(이 쪽 — run_key · doe · report_id · config_generation · superseded_by · provenance) · limit ·
    offset."""
    params: dict = {"limit": limit, "offset": offset}
    if config_generation is not None:
        params["config_generation"] = config_generation
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/provenance", params)


@mcp.tool(annotations=_READ)
async def campaign_health_table(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    include_invalid: Annotated[bool, Field(description="true 면 invalid · 대체된 런 · 출처가 빈 런도 싣는다(기본 false — "
                                                       "통계에 넣는 런만).")] = False,
    limit: Annotated[int, Field(ge=1, le=CAMPAIGN_RUNS_MAX, description=(
        f"한 번에 받을 런 수(1~{CAMPAIGN_RUNS_MAX} · 기본 200). 머리 줄은 이 값과 무관하게 전체다."))] = 200,
    offset: Annotated[int, Field(ge=0, description=(
        "건너뛸 런 수(0 이상) — offset + limit 이 `matched` 보다 작으면 offset 을 늘려 이어 받는다."))] = 0,
) -> CampaignHealthTableOut:
    """캠페인의 런 건강 표 — 머리 줄 · 판정에 쓴 문턱 묶음 · 런마다 건강 수치 · 판정 · 제외 까닭을 본다.

    통계에 넣는 런을 고르는 기준이다 — 캠페인 분석 도구와 묶음(`build_report_bundle`)이 같은 제외 까닭을 쓴다. 문턱 바꾸기는
    `set_campaign_health_thresholds`, 리포트 하나는 `report_health`, 출처 분포는 `campaign_provenance`. 건강 수치는
    `ingest_campaign_manifest` 의 health 칸으로 올린다.

    invalid 까닭 — no_report(리포트 없음) · health_missing(건강 수치 없음 — 스케줄러 상태만으로 valid 로 보지 않는다) ·
    termination_unknown · abnormal_termination · json_incomplete · nan · ke0_zero. warn 까닭 — energy_ratio · hourglass ·
    added_mass · ke0_mismatch · contact_energy. 기본 제외 — invalid · superseded(대체된 런) · provenance_missing. warn 은 넣는다.

    돌려주는 것 — header(`line` 「유효 n / 전체 N · 제외 까닭별 건수」 · total · included · excluded · excluded_by · valid · warn ·
    invalid — 캠페인 전체) · thresholds(values · ref · changed · defaults) · include_invalid · matched(실을 런 수) · runs(이 쪽 —
    run_key · doe · pitch · roll · report_id · config_generation · superseded_by · validity{status, reasons} · health ·
    excluded_by) · limit · offset."""
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/health",
                      {"include_invalid": "true" if include_invalid else "false", "limit": limit, "offset": offset})


@mcp.tool(annotations=_READ)
async def report_health(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
) -> ReportHealthOut:
    """리포트 하나(런 하나)의 건강 수치 · 판정 · 제외 까닭 · 판정에 쓴 문턱 묶음을 본다.

    캠페인 런에 묶인 리포트면 그 캠페인의 문턱으로 판정한다. 캠페인 전체 표는 `campaign_health_table`, 같은 런의 추출 · 삭제
    허가는 `report_extraction`, 문턱 바꾸기는 `set_campaign_health_thresholds`. 캠페인 주인이 아니면(같은 소속 공유로 읽는 사람)
    campaign · run_key 를 비우고 판정 · 수치만 준다. 캠페인 밖 리포트는 campaign null · validity invalid(health_missing) ·
    thresholds null 이다.

    돌려주는 것 — report_id · campaign({campaign_id, name, run_key}) · run_key · validity({status: valid | warn | invalid, reasons}) ·
    health(건강 수치 + thresholds_ref) · excluded_by · config_generation · superseded_by · thresholds(values · ref · changed ·
    defaults)."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/health")


@mcp.tool(annotations=_SET)
async def set_campaign_required_extractions(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    required_extractions: Annotated[list[dict], Field(max_length=REQUIRED_EXTRACTIONS_MAX, description=(
        _A_REQUIRED + f" {REQUIRED_EXTRACTIONS_MAX}항목까지. 예 [{{\"field\": \"stress\", \"parts\": [12, 15]}}, "
        "{\"field\": \"plastic_strain\", \"states\": \"sampled\"}]. 빈 목록이면 지운다."))],
    ctx: Context,
) -> SetCampaignRequiredExtractionsOut:
    """캠페인의 필수 추출 목록을 통째로 바꾼다 — d3plot 을 지우기 전에 DynaForge 에 들어와 있어야 할 추출이다.

    목록이 없는 캠페인은 모든 런의 삭제가 보류다(`required_extractions_unset`). 허가는 읽을 때 세므로 바꾼 목록이 곧바로
    `campaign_deletion_clearance` · `report_extraction` 에 든다. 런마다 뽑은 것은 `ingest_campaign_manifest` 의 extraction 칸으로
    올린다. 캠페인을 만들 때 함께 주려면 `create_campaign` 의 required_extractions. 빈 목록이면 지운다. 캠페인 주인만 바꾼다.

    돌려주는 것 — campaign_id · required_extractions(저장한 목록 — 파트는 정렬 · 겹침 없이, 지웠으면 null)."""
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/required-extractions",
                      {"required_extractions": required_extractions})


@mcp.tool(annotations=_READ)
async def campaign_deletion_clearance(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    status: Annotated[Literal[CLEARANCE_STATUSES] | None, Field(
        description=f"이 허가 상태의 런만(선택) — {_one_of(CLEARANCE_STATUSES)}. 비우면 모두.")] = None,
    limit: Annotated[int, Field(ge=1, le=CAMPAIGN_RUNS_MAX, description=(
        f"한 번에 받을 런 수(1~{CAMPAIGN_RUNS_MAX} · 기본 200). 머리 줄은 이 값과 무관하게 전체다."))] = 200,
    offset: Annotated[int, Field(ge=0, description=(
        "건너뛸 런 수(0 이상) — offset + limit 이 `matched` 보다 작으면 offset 을 늘려 이어 받는다."))] = 0,
) -> CampaignDeletionClearanceOut:
    """캠페인 런마다 d3plot 을 지워도 되는지(삭제 허가)를 본다 — 조회만 한다(지우기는 KooChainRun 이 한다).

    허가는 캠페인의 필수 추출 목록(`set_campaign_required_extractions`)과 런의 추출 목록(`ingest_campaign_manifest` 의 extraction
    칸)을 읽을 때 견줘 센다. 런 하나는 `report_extraction`.

    보류 까닭 — required_extractions_unset(필수 목록 없음) · no_report · extraction_missing(추출 목록 없음) · extraction_incomplete
    (`missing` 의 항목마다 field_missing · parts_missing(`parts_missing` 에 빠진 파트) · states_sampled(필수는 모든 상태인데 표본) ·
    states_unknown). 이미 지운 런은 deleted(already_deleted)이고, 빠진 항목이 있으면 extraction_lost(다시 못 뽑는다)를 단다.

    돌려주는 것 — header(`line` 「삭제 허가 a / 전체 N · 보류 h · 이미 지움 d」 와 까닭별 수 · total · allow · hold · deleted ·
    reasons — 캠페인 전체) · required_extractions · matched(거른 런 수) · runs(이 쪽 — run_key · doe · report_id · extraction ·
    peak_provenance · clearance{status: allow | hold | deleted, reasons, missing}) · limit · offset."""
    params: dict = {"limit": limit, "offset": offset}
    if status is not None:
        if status not in CLEARANCE_STATUSES:
            raise RuntimeError(f"status 는 {list(CLEARANCE_STATUSES)} 중 하나여야 합니다.")
        params["status"] = status
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/deletion-clearance", params)


@mcp.tool(annotations=_READ)
async def report_extraction(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
) -> ReportExtractionOut:
    """리포트 하나(런 하나)의 추출 목록 · 피크 출처 표지 · 그 런의 d3plot 삭제 허가를 본다.

    캠페인 런에 묶인 리포트면 그 캠페인의 필수 목록으로 허가를 센다. 캠페인 전체는 `campaign_deletion_clearance`, 같은 런의 건강
    판정은 `report_health`. 캠페인 주인이 아니면 campaign · run_key · clearance 를 비우고 추출 · 표지만 준다. 캠페인 밖 리포트는
    extraction null · 표지 known false 다.

    피크 표지(`peak_provenance`) — peak_source · states_read · states_total · peak_may_be_missed(d3plot 표본 상태에서 나온 피크면
    true · binout · elout 이면 false · 모르면 null). 같은 표지가 피크를 돌려주는 리포트 도구(report_summary · report_query ·
    report_worst_cases · report_case · report_part_risk · report_directional · report_scatter · report_angle_stats ·
    report_hotspots · report_findings)의 응답에도 실린다.

    돌려주는 것 — report_id · campaign({campaign_id, name, run_key}) · run_key · extraction · peak_provenance · clearance({status:
    allow | hold | deleted, reasons, missing})."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/extraction")


# ── 보고서용 묶음(DF-13 · 계획 df-report-bundles-1122) — 캠페인 숫자 · 그림 재료를 판으로 ─────────────
BUNDLE_TABLE_KINDS = ("runs", "case_metrics", "part_peaks")   # 백엔드 TableSpec.kind 와 같아야 한다
BUNDLE_ITEMS_PAGE_MAX = 20000                                  # 백엔드 GET /bundles/{id} 의 limit 상한과 같아야 한다
_A_BUNDLE_ID = "묶음 주소 — build_report_bundle 응답의 bundle_id."


@mcp.tool(annotations=_ADD)
async def build_report_bundle(
    campaign_ids: Annotated[list[str], Field(min_length=1, max_length=BUNDLE_CAMPAIGNS_MAX, description=(
        f"담을 캠페인 id 목록(1~{BUNDLE_CAMPAIGNS_MAX} · id 는 26자까지) — 모두 내 캠페인이어야 한다. 겹친 id 는 하나로 센다."))],
    spec: Annotated[dict, Field(description=(
        "묶음 명세 — {tables: [{kind, metrics?, parts?}], figures?: {roles?, exts?}, include_invalid?}. "
        f"kind 는 {_one_of(BUNDLE_TABLE_KINDS)} — runs(런 목록 · 지표 pitch · roll), case_metrics(케이스 롤업 · 지표 max_stress · "
        "max_g · max_disp · min_safety_factor — 기본 넷), part_peaks(파트 피크 · 지표 peak_stress · peak_strain · peak_g · peak_disp · "
        "peak_principal · min_principal · peak_vm_strain — 기본 peak_stress · peak_g · parts 로 파트를 고른다). 같은 종류는 하나. "
        "figures 는 넣은 런의 리포트 그림 가운데 역할(roles — 없으면 모두) · 확장자(exts — 기본 png · svg)인 것을 인용한다(영상은 싣지 "
        "않는다). include_invalid 가 참이면 제외 까닭이 있는 런도 넣는다(기본 거짓 — 건강 표와 같다). 모르는 열쇠 · 지표는 거절된다. "
        "표는 1~10 개 · 지표는 표마다 50 개까지. 예 {\"tables\": [{\"kind\": \"case_metrics\"}, {\"kind\": \"part_peaks\", "
        "\"parts\": [12, 15]}], \"figures\": {\"exts\": [\"png\"]}}."))],
    ctx: Context,
    as_of: Annotated[str | None, Field(description=(
        "기준 시각(선택 · ISO 8601 · 시간대가 없으면 UTC) — 그때까지 받은 리포트만 넣는다. 비우면 지금."))] = None,
    bundle_id: Annotated[str | None, Field(description=(
        "있는 주소의 다음 판을 지을 때(선택) — 캠페인 · 명세가 그 주소와 같아야 한다. 숫자가 같으면 판을 올리지 않는다. 비우면 새 "
        "주소."))] = None,
    label: Annotated[str | None, Field(description="이름표(선택 · 255자까지) — 비우면 앞 판의 것을 잇는다.")] = None,
) -> BuildReportBundleOut:
    """보고서 · 영상 생성기가 읽을 묶음(캠페인 숫자 · 그림 인용 · 숫자마다 출처)을 짓는다 — 주소(`bundle_id`) 하나에 판을 쌓는다.

    넣는 런은 건강 표와 같다(`campaign_health_table` 의 제외 까닭이 없는 런 · include_invalid 면 리포트가 있는 런 모두). 지은 판은
    `report_bundle` 로 읽고, 두 판 사이 바뀐 숫자는 `report_bundle_diff`. bundle_id 를 주면 그 주소의 다음 판이다 — 캠페인 · 명세가
    그 주소와 같아야 하고(다르면 거절 — 명세를 바꾸려면 bundle_id 없이 새 주소로), 숫자 · 그림 · 기준 줄이 마지막 판과 같으면 판을
    올리지 않고 그 판을 `unchanged: true` 로 돌려준다. 같은 주소의 판을 동시에 지으면 한쪽은 다시 지으라는 오류다.

    숫자는 항목 하나가 한 줄이고 `report_bundle(items=true)` 로 받는다 — 숫자마다 `source_path` 가 리포트 · 케이스 · (파트) ·
    지표까지 거슬러 간다. 한 판의 숫자는 200,000 개까지 — 넘으면 거절되니 표 종류 · 지표 · 파트를 좁힌다. 묶음은 만든 사람만
    본다.

    돌려주는 것 — bundle_id · version · label · campaign_ids · as_of · created_at · basis(수치 기준 — `basis.line` 이 캠페인마다
    「유효 n / 전체 N · 제외 까닭」, 설정 세대 · 문턱 이름표 · 단위) · citation(ReportArchive 가 인용하는 꼴) · changes_counts(앞 판
    대비 added · removed · changed, 첫 판이면 null) · unchanged · counts(items · tables · figures)."""
    body = {k: v for k, v in {"campaign_ids": campaign_ids, "spec": spec, "as_of": as_of, "bundle_id": bundle_id,
                              "label": label}.items() if v is not None}
    return await _post(ctx, "/bundles", body)


@mcp.tool(annotations=_READ)
async def report_bundle(
    ctx: Context,
    bundle_id: Annotated[str | None, Field(description=_A_BUNDLE_ID + " bundle_id · campaign_id 가운데 하나만 준다.")] = None,
    campaign_id: Annotated[str | None, Field(description=(
        "캠페인 id — 주면 그 캠페인을 담은 묶음 가운데 가장 늦게 지은 판(REST /campaigns/{id}/bundles/latest).") )] = None,
    version: Annotated[int | None, Field(ge=1, description=(
        "판(선택 · 1 이상 · bundle_id 와 함께만) — 비우면 마지막 판."))] = None,
    items: Annotated[bool, Field(description=(
        "참이면 숫자 항목(item_key · value · unit · source_path · source)을 쪽으로 싣는다. 기본 거짓 — 항목 없이 머리 · 표 · 그림만."))] = False,
    limit: Annotated[int, Field(ge=1, le=BUNDLE_ITEMS_PAGE_MAX, description=(
        f"한 쪽의 항목 수(1~{BUNDLE_ITEMS_PAGE_MAX} · 기본 1000) — items 가 참일 때만 쓴다."))] = 1000,
    offset: Annotated[int, Field(ge=0, description=(
        "건너뛸 항목 수(0 이상) — offset + limit 이 items.total 보다 작으면 offset 을 늘려 이어 받는다."))] = 0,
) -> ReportBundleOut:
    """묶음의 판 하나를 읽는다 — bundle_id 의 판(기본 마지막 판) 또는 campaign_id 를 담은 묶음 가운데 가장 늦게 지은 판.

    짓기는 `build_report_bundle`, 두 판 사이 바뀐 숫자만 보려면 `report_bundle_diff`. bundle_id · campaign_id 가운데 하나만 주고,
    version 은 bundle_id 와 함께만 준다.

    돌려주는 것 — 머리(bundle_id · version · label · campaign_ids · as_of · created_at · basis · citation · changes_counts) · spec ·
    tables(표마다 columns · rows · units — 쪽으로 나누지 않고 통째로 싣는다) · figures(파일 id · sha256) · sources · changes(앞 판
    대비 바뀐 숫자 목록과 counts) · versions(판 목록) · latest_version. items 가 참이면 items({total, offset, limit, rows}) — 행마다
    item_key · value · unit · source_path · source(source_path 를 푼 것 — report_id · case_key · part_id · metric, 런 표는
    campaign_id · run_key · metric)."""
    if (bundle_id is None) == (campaign_id is None):
        raise RuntimeError("bundle_id · campaign_id 가운데 하나만 주세요.")
    params: dict = {"items": items, "limit": limit, "offset": offset}
    if campaign_id is not None:
        if version is not None:
            raise RuntimeError("version 은 bundle_id 와 함께만 줍니다.")
        return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/bundles/latest", params)
    if version is not None:
        params["version"] = version
    return await _get(ctx, f"/bundles/{_seg(bundle_id)}", params)


@mcp.tool(annotations=_READ)
async def report_bundle_diff(
    bundle_id: Annotated[str, Field(description=_A_BUNDLE_ID)],
    ctx: Context,
    from_version: Annotated[int | None, Field(ge=1, description="앞 판(선택 · 1 이상) — 비우면 뒤 판의 바로 앞 판.")] = None,
    to_version: Annotated[int | None, Field(ge=1, description="뒤 판(선택 · 1 이상) — 비우면 마지막 판.")] = None,
) -> ReportBundleDiffOut:
    """묶음의 두 판 사이 바뀐 숫자를 본다 — 더해짐 · 빠짐 · 값(또는 단위) 바뀜(옛 값 → 새 값 · 출처 경로)과 그 수.

    기본은 마지막 판과 그 바로 앞 판이다. 판 하나의 전체 내용은 `report_bundle`, 새 판 짓기는 `build_report_bundle`. 판이 하나뿐이면
    (견줄 앞 판이 없으면) 오류다. 목록은 쪽으로 나누지 않고 통째로 싣는다 — 숫자가 많이 바뀐 판끼리는 응답이 크니
    `build_report_bundle` · `report_bundle` 의 changes_counts 를 먼저 본다.

    돌려주는 것 — bundle_id · from_version · to_version · added · removed(항목마다 item_key · value · unit · source_path) ·
    changed(item_key · old · new · unit · old_unit · source_path) · counts(added · removed · changed)."""
    params: dict = {}
    if from_version is not None:
        params["from"] = from_version
    if to_version is not None:
        params["to"] = to_version
    return await _get(ctx, f"/bundles/{_seg(bundle_id)}/diff", params)


# ── 캠페인 분석(DF-05 · 06 · 08 ~ 12 · 계획 df-campaign-analysis-1122) — 각도 표 · 통계 · 피크 · 여유 · 구면 지도 · 자리 · 비교 · 설정 쌍 ─────────
ANGLE_METRICS = ("peak_stress", "peak_strain", "peak_g", "peak_disp", "peak_principal", "min_principal", "peak_vm_strain",
                 "peak_principal_stress", "min_principal_stress", "peak_plastic_strain", "peak_principal_strain", "min_principal_strain")
METRIC_ALIASES = ("MET-STRESS", "MET-STRAIN", "MET-ACCEL", "MET-DISP")       # 백엔드 angles.METRIC_ALIASES 와 같아야 한다
MARGIN_AXES = ("tension_principal_stress", "von_mises", "compressive_strain", "board_strain_ue", "effective_plastic_strain")
THICKNESS_AXES = ("X", "Y", "Z")
ANALYSIS_ROWS_MAX = 5000                                                      # 백엔드 각도 표 · 피크 표의 limit 상한과 같아야 한다
_A_METRIC = (f"지표 — {_one_of(ANGLE_METRICS)} 또는 별칭 {_one_of(METRIC_ALIASES)}(MET-STRESS → peak_stress · MET-STRAIN → "
             "peak_strain · MET-ACCEL → peak_g · MET-DISP → peak_disp).")
_A_GROUPS = "무리 키(쉼표로 여럿 · 선택) — 비우면 정한 무리 전부(무리를 안 정했으면 all = 모든 파트)."
_A_THICK = f"두께축(선택) — {_one_of(THICKNESS_AXES)}. 비우면 캠페인의 thickness_axis, 그것도 없으면 Z. 라벨은 덱 축으로 나온다."
_A_INVALID = "참이면 제외 까닭이 있는 런도 넣는다(리포트가 있는 런 모두). 기본 거짓 — 건강 표와 같다."
_A_KEJUMP = "참이면 첫 KE 가 ½mv² 와 어긋난 런(ke0_mismatch — KE 튐)도 넣는다. 기본 거짓 — 빼고 excluded_ke_jump 로 센다."
_A_GEN = "이 설정 세대(config_generation)의 런만(선택)."


def _filters(include_invalid, include_ke_jump, config_generation) -> dict:
    p = {"include_invalid": include_invalid, "include_ke_jump": include_ke_jump}
    if config_generation is not None:
        p["config_generation"] = config_generation
    return p


async def _get_raw(ctx, path, params=None) -> bytes:
    """그림(svg · png)을 바이트로 — 오류면 백엔드 글을 그대로 올린다."""
    async with _client() as c:
        r = await c.get(path, params=params, headers=_forward_headers(ctx))
    if r.status_code >= 400:
        _unwrap(r)
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.content


async def _figure(ctx, path, params, res: dict) -> list:
    """`res` 뒤에 SVG 를 래스터로 바꾼 이미지 블록을 붙인다(못 만들면 `figure_png_error`)."""
    try:
        svg = await _get_raw(ctx, path, {**params, "format": "svg"})
        data, fmt, w, h = await rasterize(svg)
    except FigurePngError as e:
        res["figure_png_error"] = str(e)
        return [res]
    except RuntimeError as e:
        res["figure_png_error"] = f"download_failed: {e}"[:200]
        return [res]
    res["figure_png"] = {"format": fmt, "width": w, "height": h, "bytes": len(data)}
    return [res, Image(data=data, format=fmt)]


# 캠페인 분석 도구의 닫힌 어휘 · 경계 · 결과 꼴(공통 계약 C3 · C4 · C7) — 값은 백엔드 campaigns/analysis_routes.py · sessions 와 같아야 한다
ANALYSIS_METRIC_NAMES = ANGLE_METRICS + METRIC_ALIASES   # 지표 하나 칸 — 백엔드 _metric(angles.resolve_metric)이 받는 이름 · 별칭
ANALYSIS_MATCH_MODES = ("doe", "angle")                  # GET /campaigns/compare 의 match
ANALYSIS_TOP_MAX = 100                                   # GET /campaigns/{id}/angle-stats 의 top 상한
ANALYSIS_GROUPS_MAX = 200                                # PUT part-groups 의 무리 수 상한
ANALYSIS_CRITERIA_MAX = 1000                             # PUT criteria 의 항목 수 상한
ANALYSIS_SITES_MAX = 5000                                # PUT sites 의 자리 수 상한
ANALYSIS_PART_MAP_ROWS_MAX = 20000                       # POST /part-maps 의 행 수 상한
ANALYSIS_PAIR_METRICS_MAX = 50                           # PUT pair-rule 의 규칙 항목 수 상한
ANALYSIS_RADIUS_MAX_MM = 1000                            # GET hotspot-sites 의 radius_mm 상한(0 초과)
ANALYSIS_KEY_MAX = 64                                    # 세대 · 무리 · 지표 · 부품 · 기준 글 칸의 길이 상한(Query max_length)
ANALYSIS_ID_MAX = 26                                     # GET /campaigns/compare 의 a · b · part_map 길이 상한
RENAME_PART_TITLE_MAX = 70                               # PATCH /sessions/{id}/parts/{pid} 의 title 상한(*PART 제목 칸 A70)
_A_ANALYSIS_GEN = (f"이 설정 세대(config_generation)의 런만(선택 · {ANALYSIS_KEY_MAX}자까지) — 비우면 모든 세대. 응답 "
                   "header.generations 에 세대별 런 수가 있다.")
_CA_ENV = "백엔드 환경 — dev · prod · unknown."
_CA_HEADER = ("넣은 런 머리 — total · included · excluded_by{까닭: 수} · excluded_ke_jump · include_invalid · include_ke_jump · "
              "config_generation · generations[{config_generation, runs}] · thresholds_ref · line(한 줄 요약).")
_CA_GROUPS = "센 무리 [{group_key, label, part_ids(null = 모든 파트), part_key}]."
_SetCampaignPartGroupsOut = _shape("SetCampaignPartGroupsOut", {
    "campaign_id": "캠페인 id.",
    "groups": "저장된 무리 [{group_key, label, part_ids(겹친 번호를 빼고 정렬), part_key}] — 빈 목록이면 지운 것(모든 파트를 무리 all 로 센다).",
    "environment": _CA_ENV})
_CampaignAngleTableOut = _shape("CampaignAngleTableOut", {
    "campaign_id": "캠페인 id.", "header": _CA_HEADER, "thickness_axis": "쓴 두께축(X · Y · Z).",
    "metrics": "쓴 지표(별칭은 리포트 지표 이름으로 고친 것).", "units": "{지표: 단위} — MPa · G · mm · 빈 글(변형률).",
    "groups": _CA_GROUPS, "matched": "조건에 맞는 전체 행 수 — rows 는 그 가운데 offset 부터 limit 개.",
    "rows": ("각도 행 [{run_key, case_key, doe, report_id, pitch, roll, direction(덱 틀 단위 벡터), lon, lat, label(26 방향), "
             "category(face · edge · corner), ke0, n_impacts, second_impact_ms, peak_source, peaks{무리: {지표: {value, part_id, t_peak_ms, "
             "peak_impact, ke_frac_at_impact}}}}]."),
    "limit": "받은 limit.", "offset": "받은 offset.", "environment": _CA_ENV})
_CampaignAngleStatsOut = _shape("CampaignAngleStatsOut", {
    "campaign_id": "캠페인 id.", "header": _CA_HEADER, "thickness_axis": "쓴 두께축.", "metric": "쓴 지표(리포트 지표 이름).",
    "unit": "지표 단위.", "groups": _CA_GROUPS,
    "stats": ("통계 — n · impacts_known · multi_impact · multi_impact_ratio · groups{무리: {distribution{n, min, p10, median, p90, max, "
              "mean}, top, bottom, by_category, by_label, peak_impact_counts}} · coverage{labels_hit, labels_total, missing_labels}."),
    "environment": _CA_ENV})
_CampaignPeakTableOut = _shape("CampaignPeakTableOut", {
    "campaign_id": "캠페인 id.", "header": _CA_HEADER, "metric": "쓴 지표.", "unit": "지표 단위.", "groups": _CA_GROUPS,
    "matched": "피크 행 전체 수 — peaks 는 그 가운데 offset 부터 limit 개.",
    "peaks": ("피크 행 [{run_key, case_key, doe, group_key, value, part_id, t_peak_ms, peak_impact, ke_frac_at_impact, n_impacts, "
              "peak_source}]."),
    "impacts": "충격별 행 [{run_key, doe, impact, t_start_ms, t_end_ms, ke_frac, group_key, value}] — 쪽 넘기기 없이 전부.",
    "limit": "받은 limit.", "offset": "받은 offset.", "environment": _CA_ENV})
_SetCampaignCriteriaOut = _shape("SetCampaignCriteriaOut", {
    "campaign_id": "캠페인 id.",
    "criteria": ("저장된 기준값 [{part_id, group_key, failure_mode, metric_axis, criterion_value, unit(축의 표준 단위), source_platform, "
                 "source_record_id, version}]."),
    "environment": _CA_ENV})
_CampaignPartMarginOut = _shape("CampaignPartMarginOut", {
    "campaign_id": "캠페인 id.", "header": _CA_HEADER, "axes": "센 지표 축.", "criteria": "캠페인의 기준값 묶음(set_campaign_criteria 의 것).",
    "rows": ("여유 행 [{target{part_id 또는 group_key}, label, failure_mode, metric_axis, unit, status(ok · criterion_unset · group_unknown), "
             "criterion_source, n, value, median, criterion, ratio, median_ratio, exceed_ratio, top_angles}]."),
    "environment": _CA_ENV})
_SetCampaignSitesOut = _shape("SetCampaignSitesOut", {
    "campaign_id": "캠페인 id.", "sites": "저장한 자리 수(정수).", "environment": _CA_ENV})
_CampaignSiteTableOut = _shape("CampaignSiteTableOut", {
    "campaign_id": "캠페인 id.",
    "coverage": "덮임 — sites · with_results · missing(결과 없는 자리) · by_face · footprints_are_measured · warning(합성 footprint 경고).",
    "rows": ("자리 행 [{site_id, face, col, row, x_mm, y_mm, under_category, impactor, run_key, footprint_measured, "
             "source(site_metrics · run_report · null), metrics[{part, metric, value, time_ms, elem_id, ratio, criterion}], max_ratio}]."),
    "environment": _CA_ENV})
_ImportPartMapOut = _shape("ImportPartMapOut", {
    "map_id": "새 파트 짝 표 id — compare_campaigns 의 part_map.", "label": "이름표.", "from_model": "앞 모델 이름.",
    "to_model": "뒤 모델 이름.", "rows": "저장된 짝 행.", "n_rows": "행 수.", "created_at": "만든 때(ISO 8601).", "environment": _CA_ENV})
_CompareCampaignsOut = _shape("CompareCampaignsOut", {
    "header": ("머리 — common_angles · match · tol_deg · metric · pairs_compared · size_counts{high, mid, low} · top5 · name_only_skipped · "
               "unmatched_pairs · a · b{campaign_id, header}."),
    "pairs": "짝 결과 [{a_pid, b_pid, basis, role, n, median_ratio, top5_sum_a, top5_sum_b, top5_ratio, size}].",
    "unmatched": "공통 각도에서 값을 못 맞춘 짝 [{a_pid, b_pid, basis}].",
    "disappeared_parts": "앞 캠페인에만 있는 파트 번호(믿는 짝이 없다).", "new_parts": "뒤 캠페인에만 있는 파트 번호.",
    "part_map": "쓴 짝 표 {map_id, from_model, to_model}.", "environment": _CA_ENV})
_SetCampaignPairRuleOut = _shape("SetCampaignPairRuleOut", {
    "campaign_id": "캠페인 id.",
    "pair_rule": "저장된 규칙 {metrics[{metric(리포트 지표 이름), group_key, max_diff_pct}], rank_corr_min, max_failed_pairs}.",
    "environment": _CA_ENV})
_CompareConfigPairsOut = _shape("CompareConfigPairsOut", {
    "campaign_id": "캠페인 id.", "old": "옛 세대 {config_generation, header}.", "new": "새 세대 {config_generation, header}.",
    "pair_rule": "쓴 쌍 규칙.", "common_doe": "옛 · 새에 다 있는 DOE 수.", "only_old": "옛 세대에만 있는 DOE.",
    "only_new": "새 세대에만 있는 DOE.",
    "pairs": "쌍 행 [{doe, group_key, metric, old, new, diff_pct, max_diff_pct, over, old_run_key, new_run_key}].",
    "rank_correlation": "지표 · 무리마다 [{group_key, metric, n, rank_corr, below_min}].",
    "failed_pairs": "넘은 쌍(DOE) 수.", "failed_doe": "넘은 DOE 목록.", "max_failed_pairs": "넘은 쌍 상한.",
    "rank_corr_min": "순위 상관 하한.", "verdict": "판정 — pass · rerun_required · no_pairs.",
    "reasons": "판정 까닭 — failed_pairs · rank_corr · no_common_doe.", "environment": _CA_ENV})
_SetCampaignFrameOffsetOut = _shape("SetCampaignFrameOffsetOut", {
    "campaign_id": "캠페인 id.", "frame_offset": "저장된 이동값 {dx, dy, dz(mm), source}.", "environment": _CA_ENV})
_CampaignHotspotSitesOut = _shape("CampaignHotspotSitesOut", {
    "campaign_id": "캠페인 id.", "header": _CA_HEADER, "part_id": "파트 번호.", "criterion": "쓴 판정 기준(없으면 null).",
    "criteria_seen": "그 파트에서 본 판정 기준 목록.", "frame_offset": "쓴 이동값 {dx, dy, dz, source(query · campaign · none)}.",
    "radius_mm": "쓴 묶음 반경(mm).", "n_clusters": "묶은 군집 수.",
    "sites": ("자리 [{site, center_deck, n_clusters, n_angles, stress_max_distribution, representative{run_key, case_key, doe, report_id, "
              "stress_max, center_deck}, angles}]."),
    "bbox": "원본 K 파일 메타의 파트 bbox {bbox_min, bbox_max, report_id, file_id, title} — 없으면 null.",
    "bbox_containment": "옮긴 군집 중심의 bbox 포함 {ratio, inside, total, tol_mm} · 못 쟀으면 note.",
    "merged_part": "늘 null(가릴 칸이 없다).", "warnings": "경고 글 목록(이동값 없음 · 포함률 99 % 아래).", "environment": _CA_ENV})
_RenameSessionPartOut = _shape("RenameSessionPartOut", {
    "session_id": "세션 id.", "file_id": "고친 파일 id.", "part_id": "파트 번호.", "title": "새 제목.", "old_title": "옛 제목.",
    "line_no": "바꾼 줄 번호(1 부터).", "sha256": "고친 파일의 새 sha256.", "environment": _CA_ENV})


@mcp.tool(annotations=_SET)
async def set_campaign_part_groups(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    groups: Annotated[list[dict], Field(max_length=ANALYSIS_GROUPS_MAX, description=(
        f"부품 무리 목록(0~{ANALYSIS_GROUPS_MAX} 개) — 항목 {{group_key(빈칸 없는 글 · 64자까지), label?(255자까지), part_ids(양의 정수 목록 · "
        "1~10000 개), part_key?(표준 부품 키 PRT-*)}. 통째로 바꾸고, 빈 목록이면 지운다(그러면 무리 하나 all = 모든 파트로 센다). "
        "같은 group_key 가 둘이면 거절된다. 예: [{\"group_key\": \"display\", \"label\": \"디스플레이\", \"part_ids\": [101, 102]}]."))],
    ctx: Context,
) -> _SetCampaignPartGroupsOut:
    """캠페인의 부품 무리(이름 붙인 파트 묶음)를 통째로 바꾼다.

    각도 표 · 통계 · 피크 표 · 여유 · 구면 지도(campaign_angle_table · campaign_angle_stats · campaign_peak_table · campaign_part_margin ·
    campaign_sphere_map)와 설정 쌍 비교(compare_config_pairs)가 무리마다 그 파트들 가운데 지표 최댓값(min_ 지표는 최솟값)을 센다. 무리를
    정하지 않은 캠페인은 무리 하나 all(모든 파트)로 센다. 기준값의 group_key(set_campaign_criteria)가 여기 없는 무리면 여유에서
    group_unknown 이 되고, 쌍 규칙(set_campaign_pair_rule)의 무리가 없으면 compare_config_pairs 가 거절한다. 목록은 덮어쓴다 — 빈 목록이면
    지우고, 같은 목록을 다시 보내도 결과가 같다. 같은 group_key 가 둘이면 거절된다. 캠페인 주인만 쓸 수 있다.

    돌려주는 것 — campaign_id · groups(저장된 무리 — part_ids 는 겹친 번호를 빼고 정렬) · environment.
    """
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/part-groups", {"groups": groups})


@mcp.tool(annotations=_READ)
async def campaign_angle_table(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metrics: Annotated[str, Field(description=_A_METRIC + " 쉼표로 여럿을 준다(기본 peak_stress) — 모르는 이름이 하나라도 "
                                              "있으면 거절된다.")] = "peak_stress",
    groups: Annotated[str | None, Field(description=_A_GROUPS + " 모르는 무리 키는 거절된다.")] = None,
    thickness_axis: Annotated[Literal[THICKNESS_AXES] | None, Field(description=_A_THICK)] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
    limit: Annotated[int, Field(ge=1, le=ANALYSIS_ROWS_MAX,
                                description=f"한 번에 받을 행 수(1~{ANALYSIS_ROWS_MAX} · 기본 1000).")] = 1000,
    offset: Annotated[int, Field(ge=0, description="건너뛸 행 수(0 이상 · 기본 0) — matched 가 offset + limit 보다 크면 offset 을 "
                                                   "늘려 이어 받는다.")] = 0,
) -> _CampaignAngleTableOut:
    """캠페인의 각도 표 — 넣은 런(전각도 리포트면 케이스)마다 한 행으로 방향 · 범주 · 라벨 · 충격 · 무리별 피크를 준다.

    각도 하나하나를 보거나 표로 내릴 때 쓴다. 분포 · 상위 · 범주별 요약은 campaign_angle_stats, 지표 하나의 피크와 충격별 피크는
    campaign_peak_table, 구면 그림은 campaign_sphere_map. 넣는 런은 건강 표(campaign_health_table)와 같은 규칙이다 — 제외 까닭이 있는 런 ·
    첫 KE 가 ½mv² 와 어긋난 런(KE 튐)은 기본으로 뺀다. 런 하나의 리포트가 전각도 리포트면 케이스마다 한 각도다.

    행 — run_key · case_key · doe · report_id · pitch · roll · direction(덱 틀 단위 벡터 — 두께 틀 d = (sin p·cos r, −sin r, −cos p·cos r)을
    두께축으로 돌린 것) · lon · lat · label(가장 가까운 26 방향, 예 -Z · +X-Z) · category(face · edge · corner) · ke0 · n_impacts ·
    second_impact_ms · peak_source · peaks{무리: {지표: {value, part_id, t_peak_ms, peak_impact, ke_frac_at_impact}}}. 충격 구간은 런 목록의
    impacts 에서 온다(없으면 null).

    돌려주는 것 — header(유효 n · 전체 · 제외 까닭 · excluded_ke_jump · 세대 · line) · thickness_axis · metrics · units · groups ·
    matched(조건에 맞는 전체 행 수) · rows(이 쪽) · limit · offset · environment. 쪽 넘기기 — matched 가 offset + limit 보다 크면 offset 을
    늘려 다시 부른다.
    """
    params = {"metrics": metrics, "limit": limit, "offset": offset, **_filters(include_invalid, include_ke_jump, config_generation)}
    if groups is not None:
        params["groups"] = groups
    if thickness_axis is not None:
        params["thickness_axis"] = thickness_axis
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/angle-table", params)


@mcp.tool(annotations=_READ)
async def campaign_angle_stats(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metric: Annotated[Literal[ANALYSIS_METRIC_NAMES], Field(description=_A_METRIC + " 하나만 준다(기본 peak_stress).")] = "peak_stress",
    groups: Annotated[str | None, Field(description=_A_GROUPS + " 모르는 무리 키는 거절된다.")] = None,
    thickness_axis: Annotated[Literal[THICKNESS_AXES] | None, Field(description=_A_THICK)] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
    top: Annotated[int, Field(ge=1, le=ANALYSIS_TOP_MAX,
                              description=f"상위 · 하위로 낼 각도 수(1~{ANALYSIS_TOP_MAX} · 기본 10).")] = 10,
) -> _CampaignAngleStatsOut:
    """캠페인 각도 값의 요약 통계 — 무리별 분포 · 상위 · 하위 각도 · 범주별 · 라벨별 · 다회 충격 비율 · 26 방향 덮임을 준다.

    캠페인 전체의 경향(어느 방향이 센가 · 어느 방향이 비었나)을 볼 때 쓴다. 각도마다의 값은 campaign_angle_table, 구면 그림은
    campaign_sphere_map, 리포트 하나 안의 각도 통계는 report_angle_stats. 넣는 런 규칙 · 무리 · 두께축은 campaign_angle_table 과 같다.

    돌려주는 것 — header(유효 n · 제외 까닭 · excluded_ke_jump · line) · thickness_axis · metric · unit · groups · stats{n · impacts_known ·
    multi_impact · multi_impact_ratio(충격 구간을 받은 각도 가운데 2 회 이상인 비율) · groups{무리: {distribution{n, min, p10, median, p90,
    max, mean} · top · bottom(각 top 개 — run_key · case_key · doe · label · value · peak_impact) · by_category · by_label ·
    peak_impact_counts}} · coverage{labels_hit · labels_total(26) · missing_labels}} · environment.
    """
    params = {"metric": metric, "top": top, **_filters(include_invalid, include_ke_jump, config_generation)}
    if groups is not None:
        params["groups"] = groups
    if thickness_axis is not None:
        params["thickness_axis"] = thickness_axis
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/angle-stats", params)


@mcp.tool(annotations=_READ)
async def campaign_peak_table(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metric: Annotated[Literal[ANALYSIS_METRIC_NAMES], Field(description=_A_METRIC + " 하나만 준다(기본 peak_stress).")] = "peak_stress",
    groups: Annotated[str | None, Field(description=_A_GROUPS + " 모르는 무리 키는 거절된다.")] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
    limit: Annotated[int, Field(ge=1, le=ANALYSIS_ROWS_MAX,
                                description=f"한 번에 받을 피크 행 수(1~{ANALYSIS_ROWS_MAX} · 기본 1000).")] = 1000,
    offset: Annotated[int, Field(ge=0, description="건너뛸 피크 행 수(0 이상 · 기본 0).")] = 0,
) -> _CampaignPeakTableOut:
    """캠페인 각도 × 무리마다 지표 하나의 피크 행과, 런의 충격 구간마다의 충격별 행을 한 번에 준다.

    피크가 몇 번째 충격에서 났는지 · 그 충격의 KE 비를 볼 때 쓴다 — report_part_series 를 각도마다 부르지 않아도 된다. 여러 지표 · 방향 ·
    라벨이 함께 든 표는 campaign_angle_table, 분포 요약은 campaign_angle_stats. 넣는 런 규칙 · 무리는 campaign_angle_table 과 같고, 두께축은
    캠페인의 것(없으면 Z)이다.

    돌려주는 것 — header · metric · unit · groups · matched(피크 행 전체 수) · peaks(이 쪽 — run_key · case_key · doe · group_key · value ·
    part_id · t_peak_ms · peak_impact · ke_frac_at_impact · n_impacts · peak_source) · impacts(런의 충격 구간마다 run_key · doe · impact ·
    t_start_ms · t_end_ms · ke_frac · group_key · value — value 는 만드는 쪽이 충격별 피크를 보냈을 때만) · limit · offset · environment.
    쪽 넘기기는 peaks 에만 걸린다 — impacts 는 매번 전부 온다.
    """
    params = {"metric": metric, "limit": limit, "offset": offset, **_filters(include_invalid, include_ke_jump, config_generation)}
    if groups is not None:
        params["groups"] = groups
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/peaks", params)


@mcp.tool(annotations=_SET)
async def set_campaign_criteria(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    criteria: Annotated[list[dict], Field(max_length=ANALYSIS_CRITERIA_MAX, description=(
        f"기준값 목록(0~{ANALYSIS_CRITERIA_MAX} 개) — 항목 {{part_id 또는 group_key(하나만), failure_mode?, metric_axis("
        + _one_of(MARGIN_AXES) + "), criterion_value(0 초과), unit(응력 축 MPa · board_strain_ue 는 µε · 변형률 축은 빈 글 또는 -), "
        "source_platform?, source_record_id?, version?}. 통째로 바꾸고 빈 목록이면 지운다. 예: [{\"group_key\": \"display\", "
        "\"metric_axis\": \"von_mises\", \"criterion_value\": 250, \"unit\": \"MPa\"}]."))],
    ctx: Context,
) -> _SetCampaignCriteriaOut:
    """캠페인의 기준값 묶음(부품 · 무리마다 지표 축별 허용치)을 통째로 바꾼다.

    campaign_part_margin 은 이 묶음으로만 비를 센다 — 리포트의 항복값은 쓰지 않는다. 자리 표(campaign_site_table)도 자리 지표의 metric 이
    지표 축 이름이고 그 부품(part_id)의 기준값이 있으면 기준 대비 비를 센다. group_key 는 set_campaign_part_groups 로 정한 무리 키(무리를 안
    정했으면 all). 출처 칸(source_platform · source_record_id · version)은 MatNexus 기준 id · 판을 적는 자리다. 목록은 덮어쓴다 — 빈 목록이면
    지운다(그러면 여유는 모두 criterion_unset). 같은 대상 · 지표 축 · 고장모드가 둘이거나 단위가 축과 맞지 않으면 거절된다. 캠페인 주인만
    쓸 수 있다.

    돌려주는 것 — campaign_id · criteria(저장된 항목 — unit 은 축의 표준 단위 MPa · µε · 빈 글로 고쳐 적힌다) · environment.
    """
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/criteria", {"criteria": criteria})


@mcp.tool(annotations=_READ)
async def campaign_part_margin(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metric_axis: Annotated[Literal[MARGIN_AXES] | None, Field(
        description=f"지표 축(선택) — {_one_of(MARGIN_AXES)}. 비우면 기준값에 있는 축 전부.")] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
) -> _CampaignPartMarginOut:
    """캠페인 부품 · 무리마다 각도 최댓값을 기준값과 견준 위험 · 허용치 여유 표를 준다.

    기준값은 set_campaign_criteria 로 둔 묶음의 것만 쓴다(리포트의 항복값은 쓰지 않는다). 기준이 없는 무리 · 축도 값 · 가운데값은 센다
    (status criterion_unset — 비 null). 각도별 값 자체는 campaign_angle_table. 지표 축 — tension_principal_stress(인장 주응력 MPa) ·
    von_mises(MPa) · compressive_strain(압축 변형률 절댓값) · board_strain_ue(보드 변형률 µε = 변형률 × 10⁶) · effective_plastic_strain(유효
    소성 변형률). 넣는 런 규칙은 campaign_angle_table 과 같다. 기준값이 없고 metric_axis 도 비우면 axes · rows 가 빈다 — 기준을 두거나
    metric_axis 를 고른다.

    돌려주는 것 — header · axes(센 축) · criteria(묶음) · rows[{target{part_id 또는 group_key} · label · failure_mode · metric_axis · unit ·
    status(ok · criterion_unset · group_unknown — 기준의 무리 키가 캠페인에 없다) · criterion_source · n · value(각도 최댓값) · median ·
    criterion · ratio(value / criterion) · median_ratio · exceed_ratio(기준 이상인 각도 비율) · top_angles(상위 10 % 각도)}] · environment.
    """
    params = _filters(include_invalid, include_ke_jump, config_generation)
    if metric_axis is not None:
        params["metric_axis"] = metric_axis
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/part-margin", params)


@mcp.tool(annotations=_READ)
async def campaign_sphere_map(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metric: Annotated[Literal[ANALYSIS_METRIC_NAMES], Field(description=_A_METRIC + " 하나만 준다(기본 peak_stress).")] = "peak_stress",
    group: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=(
        f"무리 키 하나(선택 · {ANALYSIS_KEY_MAX}자까지) — 비우면 첫 무리(무리가 없으면 all). 모르는 키는 거절된다."))] = None,
    center: Annotated[bool, Field(description="참이면 센 띠를 경도 0° 로 돌린다(기본 참 — 돌린 양은 shift_deg). 거짓이면 돌리지 않는다.")] = True,
    thickness_axis: Annotated[Literal[THICKNESS_AXES] | None, Field(description=_A_THICK)] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
    include_grid: Annotated[bool, Field(description="참이면 격자 값(위도 181 × 경도 361)을 응답에 싣는다(크다). 기본 거짓 — grid 에 "
                                                    "크기 · 최소 · 최대만 싣고 values 자리에 안내 글을 둔다.")] = False,
    figure: Annotated[bool, Field(description="참이면 Mollweide 그림을 이미지 블록(PNG)으로 붙인다(기본 참). 거짓이면 결과만.")] = True,
) -> list:
    """캠페인 각도 값을 구면 위험도 지도로 — 경위도 격자로 보간하고 Mollweide 컨투어 그림(PNG 이미지 블록)을 붙여 준다.

    어느 방향 둘레가 위험한지 한눈에 볼 때 쓴다. 숫자 표는 campaign_angle_table, 요약은 campaign_angle_stats. 보간 — 두께 틀 경위도 격자
    (경도 361 × 위도 181 · 1° 간격)에 가까운 8 방향 · 가중 1 / max(θ, 0.5°)². center 가 참이면 센 띠(cos 위도 가중 경도 열 평균이 가장 큰
    열)를 경도 0° 로 돌린다. 무리는 하나만 그린다. 넣는 런 규칙은 campaign_angle_table 과 같다. 방향과 값이 있는 각도가 없으면 오류다.

    돌려주는 것 — [결과, 이미지] 목록. 결과 — header · metric · unit · group · thickness_axis · grid{lon0 · lat0 · step_deg · n_lon · n_lat ·
    min · max · values(include_grid 가 거짓이면 값 대신 안내 글)} · interpolation · shift_deg(돌린 경도) · points(방향 점 lon · lat · value ·
    run_key · case_key · doe) · provenance(출처 줄 — 유효 n · 제외 · 세대) · environment · figure_png{format, width, height, bytes}(그림을 못
    만들면 figure_png_error). figure 가 거짓이면 결과만 온다.
    """
    params = {"metric": metric, "center": center, **_filters(include_invalid, include_ke_jump, config_generation)}
    if group is not None:
        params["group"] = group
    if thickness_axis is not None:
        params["thickness_axis"] = thickness_axis
    path = f"/campaigns/{_seg(campaign_id)}/sphere-map"
    res = await _get(ctx, path, {**params, "format": "json"})
    if not include_grid and isinstance(res, dict) and isinstance(res.get("grid"), dict):
        res["grid"] = {k: v for k, v in res["grid"].items() if k != "values"} | {"values": "include_grid=true 로 받는다"}
    return await _figure(ctx, path, params, res) if figure else [res]


@mcp.tool(annotations=_SET)
async def set_campaign_sites(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    sites: Annotated[list[dict], Field(max_length=ANALYSIS_SITES_MAX, description=(
        f"자리 표(0~{ANALYSIS_SITES_MAX} 개) — 항목 {{site_id, face?(TOP · BOT), col?, row?, x_mm?, y_mm?, under_category?(받침 분류), "
        "impactor?{mass_g, height_mm, ke_mj}, run_key?(그 자리를 친 런 — 자리 지표가 없으면 그 런의 리포트 피크 · 건강 에너지비로 "
        "채운다), footprint?{measured: 참이어야 실제 측정, …}, metrics?[{part, metric, value?, time_ms?, elem_id?, ratio?}]}. 통째로 바꾸고 "
        "빈 목록이면 지운다. 같은 site_id 는 거절. 예: [{\"site_id\": \"S01\", \"face\": \"TOP\", \"x_mm\": 10, \"y_mm\": 20, "
        "\"run_key\": \"r001\"}]."))],
    ctx: Context,
) -> _SetCampaignSitesOut:
    """캠페인의 부분충격 자리 표(자리 위치 · 충격추 · 친 런 · 자리 지표)를 통째로 바꾼다.

    campaign_site_table · campaign_site_map 이 이 표를 읽는다. 자리 지표를 주지 않고 run_key 만 묶으면 그 런의 리포트 피크(peak_stress ·
    peak_principal_strain · peak_g · peak_disp) · 건강 에너지비로 채운다. 자리 지표의 metric 이 여유의 지표 축 이름(예 board_strain_ue)이고
    part 가 기준값을 둔 파트 번호면 기준 대비 비를 센다(set_campaign_criteria). footprint 는 measured 가 참이어야 실제 측정으로 본다 — 아니면
    자리 표 · 지도가 합성이라고 경고한다. 목록은 덮어쓴다 — 빈 목록이면 지운다. 같은 site_id 가 둘이면 거절된다. 캠페인 주인만 쓸 수 있다.

    돌려주는 것 — campaign_id · sites(저장한 자리 수) · environment.
    """
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/sites", {"sites": sites})


@mcp.tool(annotations=_READ)
async def campaign_site_table(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
) -> _CampaignSiteTableOut:
    """캠페인의 부분충격 자리 표를 자리마다 지표 · 기준 대비 비 · 덮임과 함께 준다.

    자리를 둔 뒤(set_campaign_sites) 결과를 숫자로 볼 때 쓴다. 면별 그림은 campaign_site_map. 지표는 받은 자리 지표(부품 피크 · 접촉력 ·
    이탈 시각 · 되튐 · 에너지비 등)이고, 없으면 묶인 런의 리포트 첫 케이스 피크 · 건강 에너지비로 채운다(source 칸이 어느 쪽인지 말한다).
    기준 대비 비는 그 부품(파트 번호)에 같은 이름의 지표 축 기준값(set_campaign_criteria)이 있을 때 센다.

    돌려주는 것 — coverage{sites · with_results · missing(결과 없는 자리) · by_face · footprints_are_measured · warning(footprint 가 실제
    측정이 아니면 — 그때 footprint 는 합성이다)} · rows[{site_id · face · col · row · x_mm · y_mm · under_category · impactor · run_key ·
    footprint_measured · source(site_metrics · run_report · null) · metrics[{part, metric, value, time_ms, elem_id, ratio, criterion?}] ·
    max_ratio}] · campaign_id · environment. 쪽 넘기기 없이 자리 전부를 준다.
    """
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/sites")


@mcp.tool(annotations=_READ)
async def campaign_site_map(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    ctx: Context,
    metric: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=(
        f"칠할 자리 지표(선택 · {ANALYSIS_KEY_MAX}자까지) — campaign_site_table 의 rows[].metrics[].metric 값. 비우면 자리의 가장 큰 "
        "기준 대비 비(max_ratio)."))] = None,
    part: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=(
        f"그 지표의 부품(선택 · {ANALYSIS_KEY_MAX}자까지) — rows[].metrics[].part 값. 비우면 자리의 그 지표 최댓값."))] = None,
    figure: Annotated[bool, Field(description="참이면 자리 지도 그림을 이미지 블록(PNG)으로 붙인다(기본 참). 거짓이면 결과만.")] = True,
) -> list:
    """캠페인의 부분충격 자리 지도 — 면(TOP · BOT)마다 자리 점을 값으로 칠한 그림(PNG 이미지 블록)과 점 목록을 준다.

    자리 분포 · 빠진 자리를 눈으로 볼 때 쓴다. 숫자 표는 campaign_site_table. 칠하는 값 — metric 을 비우면 자리의 가장 큰 기준 대비 비
    (max_ratio), 주면 그 자리 지표의 값(part 를 주면 그 부품 것만, 아니면 최댓값). 결과 없는 자리는 빈 빨간 원이다. footprint 가 실제 측정이
    아니면 그림 아래에 경고가 있다. 좌표(x_mm · y_mm)가 없는 자리와, 면을 적은 자리가 있을 때 면이 없는 자리는 그림에 점이 없다.

    돌려주는 것 — [결과, 이미지] 목록. 결과 — campaign_id · coverage(campaign_site_table 과 같다) · metric · part · points[{site_id, face,
    x_mm, y_mm, value}] · environment · figure_png{format, width, height, bytes}(그림을 못 만들면 figure_png_error). figure 가 거짓이면
    결과만 온다.
    """
    params: dict = {}
    if metric is not None:
        params["metric"] = metric
    if part is not None:
        params["part"] = part
    path = f"/campaigns/{_seg(campaign_id)}/site-map"
    res = await _get(ctx, path, {**params, "format": "json"})
    return await _figure(ctx, path, params, res) if figure else [res]


@mcp.tool(annotations=_ADD)
async def import_part_map(
    from_model: Annotated[str, Field(description="앞 모델(리비전) 이름(1~255자 · 앞뒤 공백은 뗀다) — 적어 두는 값이다.")],
    to_model: Annotated[str, Field(description="뒤 모델(리비전) 이름(1~255자 · 앞뒤 공백은 뗀다).")],
    rows: Annotated[list[dict], Field(min_length=1, max_length=ANALYSIS_PART_MAP_ROWS_MAX, description=(
        f"짝 행 목록(1~{ANALYSIS_PART_MAP_ROWS_MAX}) — 항목 {{a_pid?, b_pid?(양의 정수 · 둘 가운데 하나는 있어야 · 한쪽만이면 사라진 · "
        "새로 생긴 파트), basis(짝 근거 · 필수 · 64자까지 — name 뿐인 짝은 비교에 쓰지 않는다), center_dist_mm?(0 이상), "
        "size_rel_diff?, title_token_jaccard?(0~1), role?}. 예: [{\"a_pid\": 101, \"b_pid\": 201, \"basis\": \"geometry\", "
        "\"center_dist_mm\": 0.4}]."))],
    ctx: Context,
    label: Annotated[str | None, Field(description="이름표(선택 · 255자까지) — 비우면 없음.")] = None,
) -> _ImportPartMapOut:
    """두 모델 리비전 사이의 파트 짝 표를 새로 올리고 map_id 를 받는다.

    리비전 비교(compare_campaigns)의 part_map 인자로 쓴다. 부를 때마다 새 표가 생긴다 — 덮어쓰지 않으므로 고치려면 새로 올려 새 map_id 를
    쓴다. 행마다 짝 근거 basis 가 필수이고, basis 가 name 뿐인 짝은 비교에서 빼고 센다. 한쪽 pid 만 있는 행은 사라진 · 새로 생긴 파트다.
    표는 올린 사람만 읽을 수 있다(REST GET /part-maps/{map_id} — MCP 읽기 도구는 없다).

    돌려주는 것 — map_id · label · from_model · to_model · rows(저장된 행) · n_rows · created_at · environment.
    """
    body = {"from_model": from_model, "to_model": to_model, "rows": rows}
    if label is not None:
        body["label"] = label
    return await _post(ctx, "/part-maps", body)


@mcp.tool(annotations=_READ)
async def compare_campaigns(
    a: Annotated[str, Field(min_length=1, max_length=ANALYSIS_ID_MAX,
                            description=f"앞 리비전 캠페인 id(1~{ANALYSIS_ID_MAX}자) — create_campaign 의 campaign_id.")],
    b: Annotated[str, Field(min_length=1, max_length=ANALYSIS_ID_MAX,
                            description=f"뒤 리비전 캠페인 id(1~{ANALYSIS_ID_MAX}자).")],
    part_map: Annotated[str, Field(min_length=1, max_length=ANALYSIS_ID_MAX,
                                   description=f"파트 짝 표 id(1~{ANALYSIS_ID_MAX}자) — import_part_map 의 map_id.")],
    ctx: Context,
    metric: Annotated[Literal[ANALYSIS_METRIC_NAMES], Field(description=_A_METRIC + " 하나만 준다(기본 peak_stress).")] = "peak_stress",
    match: Annotated[Literal[ANALYSIS_MATCH_MODES], Field(
        description="각도 맞춤 — doe(같은 DOE · 기본) · angle(덱 틀 방향의 각거리 tol_deg 안에서 가장 가까운 짝).")] = "doe",
    tol_deg: Annotated[float, Field(gt=0, le=90, description="angle 맞춤의 각거리 허용치(도 · 0 초과 90 이하 · 기본 5). doe 맞춤에서는 "
                                                             "쓰지 않는다.")] = 5.0,
) -> _CompareCampaignsOut:
    """두 리비전 캠페인을 파트 짝 표로 이어 공통 각도에서 지표 하나를 비교한다(짝마다 b / a 비).

    모델이 바뀐 앞 · 뒤 리비전에서 어느 파트가 세졌는지 볼 때 쓴다. 짝 표는 import_part_map 으로 먼저 올린다. 같은 캠페인 안 옛 · 새 설정
    세대의 비교는 compare_config_pairs. 공통 각도만 쓰고, 두 캠페인 모두 제외 까닭 · KE 튐 런은 뺀다(넣는 칸이 없다). 짝마다 각도별 비
    b / a 의 가운데값 · 상위 5 합(각 캠페인의 가장 큰 다섯 값 합)과 그 비 · 크기(high · mid · low — |log₂ 가운데 비| 0.5 이상 · 0.25 이상 ·
    그 아래). 두 캠페인 · 짝 표는 내 것만 된다.

    돌려주는 것 — header{common_angles · match · tol_deg · metric · pairs_compared · size_counts · top5(|log₂ 비|가 큰 다섯 짝) ·
    name_only_skipped · unmatched_pairs · a · b(캠페인 id · 머리)} · pairs[{a_pid, b_pid, basis, role, n, median_ratio, top5_sum_a,
    top5_sum_b, top5_ratio, size}] · unmatched(값을 못 맞춘 짝) · disappeared_parts · new_parts(믿는 짝이 없는 파트) · part_map · environment.
    """
    if match not in ("doe", "angle"):
        raise RuntimeError("match 는 doe · angle 가운데 하나입니다.")
    return await _get(ctx, "/campaigns/compare", {"a": a, "b": b, "part_map": part_map, "metric": metric, "match": match,
                                                  "tol_deg": tol_deg})


@mcp.tool(annotations=_SET)
async def set_campaign_pair_rule(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    metrics: Annotated[list[dict], Field(min_length=1, max_length=ANALYSIS_PAIR_METRICS_MAX, description=(
        f"규칙 항목(1~{ANALYSIS_PAIR_METRICS_MAX}) — {{metric(" + _A_METRIC + "), group_key?(비우면 all), max_diff_pct(% · 0 초과 — "
        "|차 %| 가 넘으면 그 쌍이 넘은 쌍)}. 예: [{\"metric\": \"peak_stress\", \"max_diff_pct\": 5}]."))],
    ctx: Context,
    rank_corr_min: Annotated[float, Field(ge=-1, le=1, description="순위 상관(스피어먼) 하한(−1~1 · 기본 0.9) — 지표 · 무리 하나라도 "
                                                                   "이보다 낮으면 재실행 필요.")] = 0.9,
    max_failed_pairs: Annotated[int, Field(ge=0, description="넘은 쌍 상한(0 이상 · 기본 2) — 넘은 쌍(DOE)이 이보다 많으면 전량 재실행 "
                                                             "필요.")] = 2,
) -> _SetCampaignPairRuleOut:
    """캠페인의 설정 쌍 합격 규칙(지표 · 무리마다 최대 차 % · 순위 상관 하한 · 넘은 쌍 상한)을 통째로 바꾼다.

    compare_config_pairs 가 이 규칙으로 옛 · 새 설정 세대를 판정한다 — 규칙이 없으면 그 도구가 거절한다. 지표는 별칭(MET-*)을 받아 리포트
    지표 이름으로 고쳐 저장하고, 모르는 지표는 거절한다. group_key 는 set_campaign_part_groups 의 무리 키(비우면 all)이고, 캠페인에 없는
    무리는 비교 때 거절된다. 덮어쓰기라 같은 규칙을 다시 보내도 결과가 같다. 캠페인 주인만 쓸 수 있다.

    돌려주는 것 — campaign_id · pair_rule{metrics[{metric, group_key, max_diff_pct}], rank_corr_min, max_failed_pairs} · environment.
    """
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/pair-rule",
                      {"metrics": metrics, "rank_corr_min": rank_corr_min, "max_failed_pairs": max_failed_pairs})


@mcp.tool(annotations=_READ)
async def compare_config_pairs(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    old: Annotated[str, Field(min_length=1, max_length=ANALYSIS_KEY_MAX,
                              description=f"옛 설정 세대(config_generation · 1~{ANALYSIS_KEY_MAX}자).")],
    new: Annotated[str, Field(min_length=1, max_length=ANALYSIS_KEY_MAX,
                              description=f"새 설정 세대(config_generation · 1~{ANALYSIS_KEY_MAX}자).")],
    ctx: Context,
) -> _CompareConfigPairsOut:
    """같은 캠페인에서 같은 DOE 를 옛 · 새 설정 세대로 돌린 쌍을 견줘 쌍 규칙으로 합격 · 재실행을 판정한다.

    해석 설정(config_generation)을 바꾼 뒤 결과가 같은지 볼 때 쓴다. 규칙은 set_campaign_pair_rule 로 먼저 둔다(없으면 거절). 다른 리비전 ·
    모델 사이의 비교는 compare_campaigns. 쌍마다 규칙의 지표 · 무리별 차 % = (새 − 옛) / |옛| × 100, 지표 · 무리마다 순위 상관(스피어먼),
    넘은 쌍(어느 항목이든 |차 %| 가 max_diff_pct 를 넘은 DOE) 수를 센다. 판정 — pass · rerun_required(넘은 쌍이 상한보다 많거나 순위 상관이
    하한 아래) · no_pairs(공통 DOE 없음). 옛 세대 런이 새 세대로 대체돼 있어도 넣고, 제외 까닭 · KE 튐 런은 뺀다.

    돌려주는 것 — old · new{config_generation, header} · pair_rule · common_doe · only_old · only_new · pairs[{doe, group_key, metric, old,
    new, diff_pct, max_diff_pct, over, old_run_key, new_run_key}] · rank_correlation[{group_key, metric, n, rank_corr, below_min}] ·
    failed_pairs · failed_doe · max_failed_pairs · rank_corr_min · verdict · reasons(failed_pairs · rank_corr · no_common_doe) ·
    campaign_id · environment.
    """
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/config-pairs", {"old": old, "new": new})


# ── 핫스팟 자리 · 덱 세션 관리(DF-07 · DF-15 · 계획 df-hotspot-session-1122) ─────────────

@mcp.tool(annotations=_SET)
async def set_campaign_frame_offset(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    dx: Annotated[float, Field(description="이동값 x(mm) — 덱 좌표 = 결과(d3plot) 좌표 + (dx, dy, dz).")],
    dy: Annotated[float, Field(description="이동값 y(mm).")],
    dz: Annotated[float, Field(description="이동값 z(mm).")],
    ctx: Context,
    source: Annotated[str | None, Field(description="근거(선택 · 255자까지) — 예: 덱 원점 메모 · 재집계 문서. 비우면 없음.")] = None,
) -> _SetCampaignFrameOffsetOut:
    """캠페인의 결과(d3plot) 틀 → 덱 틀 이동값(dx, dy, dz mm)을 둔다 — 덱 좌표 = 결과 좌표 + (dx, dy, dz).

    campaign_hotspot_sites 가 핫스팟 군집 중심을 덱 좌표로 옮길 때, 그 도구에 dx · dy · dz 를 주지 않으면 이 값을 쓴다. 그 도구가 bbox 포함률
    경고(99 % 아래)를 내면 이동값을 의심하고 여기서 고친다. source 에 근거를 적어 둔다. 덮어쓰기라 같은 값을 다시 보내도 결과가 같다.
    캠페인 주인만 쓸 수 있다.

    돌려주는 것 — campaign_id · frame_offset{dx, dy, dz, source} · environment.
    """
    body = {"dx": dx, "dy": dy, "dz": dz}
    if source is not None:
        body["source"] = source
    return await _put(ctx, f"/campaigns/{_seg(campaign_id)}/frame-offset", body)


@mcp.tool(annotations=_READ)
async def campaign_hotspot_sites(
    campaign_id: Annotated[str, Field(description=_A_CAMPAIGN_ID)],
    part_id: Annotated[int, Field(gt=0, description="파트 번호(LS-DYNA PID · 1 이상).")],
    ctx: Context,
    criterion: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=(
        f"판정 기준(선택 · {ANALYSIS_KEY_MAX}자까지) — 리포트 핫스팟의 criterion 값(report_hotspots · 응답 criteria_seen). 비우면 그 "
        "파트의 기준이 하나일 때만 된다(여럿이면 오류 글에 목록)."))] = None,
    radius_mm: Annotated[float | None, Field(gt=0, le=ANALYSIS_RADIUS_MAX_MM, description=(
        f"묶음 반경 mm(선택 · 0 초과 {ANALYSIS_RADIUS_MAX_MM} 이하) — 비우면 군집 반경 가운데값의 2 배(없으면 5)."))] = None,
    dx: Annotated[float | None, Field(description="이동값 x(mm · 선택) — dx · dy · dz 를 셋 다 주면 캠페인의 이동값 대신 쓴다(일부만 "
                                                  "주면 거절).")] = None,
    dy: Annotated[float | None, Field(description="이동값 y(mm · 선택).")] = None,
    dz: Annotated[float | None, Field(description="이동값 z(mm · 선택).")] = None,
    include_invalid: Annotated[bool, Field(description=_A_INVALID)] = False,
    include_ke_jump: Annotated[bool, Field(description=_A_KEJUMP)] = False,
    config_generation: Annotated[str | None, Field(max_length=ANALYSIS_KEY_MAX, description=_A_ANALYSIS_GEN)] = None,
) -> _CampaignHotspotSitesOut:
    """캠페인 각도들의 핫스팟 군집(파트 하나 · 판정 기준 하나)을 덱 좌표로 옮겨 반경 안에서 자리로 묶는다.

    여러 낙하 각도에서 같은 자리가 되풀이해 위험한지 볼 때 쓴다. 리포트 하나의 군집은 report_hotspots. 이동값 — dx · dy · dz 를 셋 다 주면
    그것, 아니면 set_campaign_frame_offset 으로 둔 캠페인 값, 둘 다 없으면 결과 틀 좌표 그대로 읽고 warnings 에 적는다. 묶기는 최대
    응력(절댓값)이 큰 군집부터 반경 안의 첫 자리에 넣는다. 넣는 런 규칙은 campaign_angle_table 과 같다.

    돌려주는 것 — header · part_id · criterion · criteria_seen · frame_offset{dx, dy, dz, source(query · campaign · none)} · radius_mm ·
    n_clusters · sites[{site · center_deck · n_clusters · n_angles · stress_max_distribution · representative · angles}] · bbox(원본 K 파일
    메타의 파트 bbox — 없으면 null) · bbox_containment{ratio, inside, total, tol_mm} · merged_part(늘 null) · warnings(bbox 포함률이 99 %
    아래면 이동값을 의심하라는 경고) · campaign_id · environment.
    """
    params = {"part_id": part_id, **_filters(include_invalid, include_ke_jump, config_generation)}
    for k, v in (("criterion", criterion), ("radius_mm", radius_mm), ("dx", dx), ("dy", dy), ("dz", dz)):
        if v is not None:
            params[k] = v
    return await _get(ctx, f"/campaigns/{_seg(campaign_id)}/hotspot-sites", params)


@mcp.tool(annotations=_SET)
async def rename_session_part(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    part_id: Annotated[int, Field(gt=0, description="파트 번호(*PART 의 PID · 1 이상).")],
    file_id: Annotated[int, Field(gt=0, description=(
        "그 파트의 *PART 가 있는 세션 K 파일 id(1 이상 · get_session 의 files[].id) — 인클루드 안이면 그 인클루드 파일의 id."))],
    title: Annotated[str, Field(max_length=RENAME_PART_TITLE_MAX, description=(
        f"새 제목 — {RENAME_PART_TITLE_MAX}자까지 · 출력 가능한 ASCII 만 · `*` · `$` 로 시작하지 않는다."))],
    ctx: Context,
) -> _RenameSessionPartOut:
    """세션 덱 파일의 *PART 제목 한 줄을 제자리에서 바꾼다(줄 끝 꼴 · 다른 바이트는 그대로).

    파트 제목을 사람이 읽는 이름으로 고칠 때 쓴다. 그 파일의 주 덱에서 제목 줄 + PID 가 맞는 카드를 찾는다 — 파트가 인클루드 안에 있으면
    그 인클루드 파일의 id 를 준다(list_session_files · inspect_file 로 찾는다). 자리가 없거나 둘 이상이면 바꾸지 않고 오류다. 제목은 70 자까지 ·
    출력 가능한 ASCII 만 · `*` · `$` 로 시작할 수 없다. 파일의 sha256 · 메타의 파트 제목도 고친다. 같은 제목을 다시 보내도 결과가 같다.
    세션 주인만 쓸 수 있다.

    돌려주는 것 — session_id · file_id · part_id · title · old_title · line_no(바꾼 줄 번호 · 1 부터) · sha256(새 값) · environment.
    """
    async with _client() as c:
        return _unwrap(await c.patch(f"/sessions/{_seg(session_id)}/parts/{_seg(part_id)}",
                                     json={"file_id": file_id, "title": title}, headers=_forward_headers(ctx)))

# ── 해석 온톨로지(cae_*) — 후처리 꾸러미를 리포트에 싣고 묻는다(사용자 결정 10-31 (가), 계획 cae-ontology-1031) ─────────────
# 허용값은 백엔드 GET /cae/parts · /cae/load-paths 의 Query 패턴과 같아야 한다(test_mcp_tools_contract 가 대조한다).
CAE_SEVERITIES = ("CRITICAL", "WARNING", "UNKNOWN", "OK")         # 높은 것부터
CAE_PATH_SORTS = ("impulse_max", "engage_ratio", "peak_force_max", "work_max")
CAE_LIMIT_MAX = 500

# ── 리포트 조회 · 해석 온톨로지 도구의 허용값 · 경계 · 결과 꼴(공통 계약 C3 · C4 · C7) ─────────────────────────────────────────
# 경계 · 허용값은 백엔드 GET /reports/{id}/contact_profile · hotspots · blocks/{name} 의 Query 제약과 같아야 한다. 정렬 칸 · 분석 블록 이름은
# 백엔드가 모르는 값을 거절하지 않고 받으므로(정렬은 stress_max 로 · 블록은 available=false) enum 으로 두지 않고 설명에만 쓴다(파서 상수와 같다).
CONTACT_METRICS = ("pf", "ti", "tw")              # peak_force · total_impulse · total_work
CONTACT_TOP_MAX = 1000
CONTACT_AXIS_TOP_MAX = 5000
HOTSPOT_TOP_MAX = 500
BLOCK_MAX_BYTES_MIN = 1_000
BLOCK_MAX_BYTES_MAX = 4_000_000
HOTSPOT_ORDERS_DEEP = ("stress_max", "stress_mean", "volume", "element_count", "radius_enclosing", "rank")
HOTSPOT_ORDERS_SPHERE = ("stress_max", "element_count", "radius_enclosing", "rank", "strain_max", "energy_total", "energy_max")
REPORT_ANALYTICS_BLOCKS = ("doe_analysis", "deep_analytics", "insights", "physics", "solver_quality", "contact_profile", "set_report")
_A_CAE_PROJECT = "과제 — 수동 메타의 과제 또는 리포트에 박힌 project_name. " + _A_FACET + " 비우면 모두."
_A_CAE_KIND = f"리포트 종류 — {_one_of(REPORT_KINDS)} 중 하나. 비우면 모두."

AttachCaePackageOut = _shape("AttachCaePackageOut", {
    "already": "true 면 같은 꾸러미(sha256 같음)라 행은 그대로 두고 코어 다리만 다시 지었다",
    "vocabulary": "받아들인 어휘 판 {version, sha256}",
    "sha256": "꾸러미 바이트의 sha256",
    "file_id": "리포트 세션에 저장한 꾸러미 파일 id",
    "file": "그 파일 이름",
    "producer": "꾸러미를 낸 후처리(꾸러미의 producer 그대로)",
    "source_html": "꾸러미가 적은 짝 HTML",
    "units": "단위계 이름",
    "counts": "건수 {objects: 꾸러미 타입별, loaded: 실은 타입별, edges: 관계 수}",
    "runs": "런 키 대조 {package, matched, missing(앞 20 개)}",
    "warnings": "받는 쪽 경고 글 목록",
    "loaded_at": "실은 시각(UTC ISO 꼴)",
    "bridges": "코어 다리 셈 {rule, human, stale, renamed, candidates, unmatched, unnamed, by_type, mirror, notes, computed_at} — "
               "다리 짓기만 깨지면 {error}",
})
ReportCaeOut = _shape("ReportCaeOut", {
    "report_id": "리포트 id",
    "loaded": "꾸러미를 실었나 — false 면 why 만 온다",
    "why": "실은 적이 없을 때 까닭과 붙이는 길",
    "summary": "적재 요약(어휘 판 · sha256 · 파일 · 단위계 · counts · runs · warnings · loaded_at · 다리 셈)",
    "campaign": "캠페인 {key, label, 단위계 · 낙하 높이 · 충돌 속도 · scenario_kind …} — 없으면 null",
    "parts": "파트 판정, 위험한 것부터 — key · label · severity · min_safety_factor · worst_von_mises(MPa) · worst_*_run_case · "
             "worst_*_run_identity …",
    "load_paths": "하중 경로, 충격량 큰 것부터 — part_a · part_b(+ _name) · engage_ratio · impulse_max(N·s) · peak_force_max(N) · work_max(mJ) …",
    "contacts": "접촉 — 칸들과 sides[{part, name …}]",
    "findings": "소견, 심각한 것부터 — 칸들과 about[파트 key]",
    "hotspots": "응력 집중 행",
    "bridges": "코어 다리 {rule, counts, lines, stale, candidates, unmatched, unnamed, drift(있을 때)} — 보기만 깨지면 {error}",
})
FindCaePartsOut = _shape("FindCaePartsOut", {
    "items": "파트 판정, 위험한 것부터 — report_id · report_label · kind · project · key · label · part_id · name · material_name · "
             "severity · min_safety_factor · worst_von_mises(MPa) · worst_von_mises_run_case · worst_g · worst_g_run_case …",
    "total": "돌려준 건수(items 길이) — 전체 건수가 아니다",
    "truncated": "limit 만큼 찼으면 true — 더 있을 수 있다(limit 을 올리거나 거름을 좁힌다)",
})
FindCaeLoadPathsOut = _shape("FindCaeLoadPathsOut", {
    "items": "하중 경로, sort 가 큰 것부터 — report_id · report_label · kind · project · key · label · part_a · part_b · n_runs_engaged · "
             "engage_ratio · impulse_max(N·s) · impulse_max_run_case · impulse_median · impulse_p90 · peak_force_max(N) · work_max(mJ)",
    "total": "돌려준 건수(items 길이) — 전체 건수가 아니다",
    "truncated": "limit 만큼 찼으면 true — 더 있을 수 있다(limit 을 올리거나 거름을 좁힌다)",
})
AttachCadOut = _shape("AttachCadOut", {
    "key": "묶음 열쇠",
    "already": "true 면 같은 묶음이 이미 붙어 있어 바꾼 것이 없다",
    "stored": "이번에 저장한 파일 수(already 면 0)",
    "n_parts": "묶음의 파트 수",
    "replaced": "갈아 끼운 옛 묶음 열쇠 — 처음 붙였으면 null(already 면 칸이 없다)",
    "warnings": "받는 쪽 경고 글 목록",
})
AttachReportScenarioOut = _shape("AttachReportScenarioOut", {
    "id": "리포트 id",
    "kind": "리포트 종류",
    "label": "라벨",
    "scenario": "조건 요약 {project_name, sim_params{drop_height, t_final, dt}, scenarios[name · template · source_type · angle_source · "
                "tolerance · n_base_directions · expected_runs …], templates}",
    "scenario_type": "방향 조건 종류(첫 시나리오의 source_type)",
    "scenario_file_id": "이번에 저장한 scenario.json 세션 파일 id",
    "source_kfile_id": "이어진 원본 K파일 id — 이번에 template 로 찾아 이었을 수 있다",
    "n_cases": "케이스 수",
    "environment": "응답을 낸 서버 환경(dev · prod · unknown)",
})
ReportListRow = _shape("ReportListRow", {
    "id": "리포트 id",
    "kind": "리포트 종류(deep · sphere · impact)",
    "label": "라벨",
    "focus": "초점 라벨",
    "project_name": "리포트에 박힌 과제 이름",
    "doe_strategy": "방향 컨셉(cuboid_26 등)",
    "scenario_type": "방향 조건 종류",
    "drop_height": "낙하 높이(mm)",
    "worst_stress": "전역 최악 응력(MPa)",
    "max_severity": "가장 높은 소견 심각도",
    "source_kfile_id": "이어진 원본 K파일 id",
    "eng_meta": "과제 · rev · 설계안 수동 메타",
    "n_cases": "케이스 수",
    "created_at": "반입 시각",
    "environment": "응답을 낸 서버 환경(dev · prod · unknown)",
})
ReportBlocksOut = _shape("ReportBlocksOut", {
    "n_blocks": "블록 수",
    "n_unread": "read_by_parser=false 인 블록 수",
    "blocks": "블록마다 {name, type(object · array · …), count, sub_keys(앞 40 개), item_type, bytes(직렬화 크기 어림), read_by_parser}",
})
ReportBlockOut = _shape("ReportBlockOut", {
    "name": "블록 이름",
    "found": "블록 · 경로를 찾았나 — false 면 note 가 쓸 수 있는 키 · 인덱스를 말한다",
    "path": "준 하위 경로",
    "value": "꺼낸 값(잘렸으면 앞부분, too_big 이면 null)",
    "shape": "값의 형태 {type, count, sub_keys}",
    "bytes": "값의 직렬화 크기 어림(바이트)",
    "read_by_parser": "전용 도구가 이 블록을 읽나",
    "truncated": "잘랐으면 {kind: limit · bytes · too_big, returned, total, bytes, max_bytes} — 안 잘랐으면 칸이 없다",
    "note": "잘림 · 끊긴 경로 · 없는 블록의 안내 글",
    "available": "없는 블록일 때 블록 이름 목록(앞 80 개)",
    "walked": "경로가 끊겼을 때 거기까지 지난 경로",
})
ReportHotspotsOut = _shape("ReportHotspotsOut", {
    "available": "군집이 실렸나 — false 면 note 가 까닭",
    "kind": "sphere 일 때만 온다",
    "n_records": "파트 × 기준 레코드 수",
    "n_clusters": "거른 뒤 군집 수(top 으로 자르기 전)",
    "n_clusters_all": "sphere — 거르기 전 전 각도 군집 수",
    "criteria": "이 리포트의 판정 기준 목록",
    "parts": "군집이 있는 파트 id 목록",
    "order": "실제로 쓴 정렬 칸",
    "filter": "적용한 거름",
    "clusters": "군집 — part_id · part_name · criterion · center(mm) · radius_enclosing · element_count · stress_max(MPa) · peak_time … "
                "(sphere 는 case_key · angle, deep 은 uniform · volume · stress_mean · peak_element_id 까지)",
    "truncated": "top 에서 잘랐으면 {returned, total}",
    "envelope": "sphere — 파트 × 기준마다 전 각도에서 가장 센 군집(worst_case_key · worst_angle · stress_max · n_angles …)",
    "envelope_truncated": "sphere — envelope 를 top 에서 잘랐으면 {returned, total}",
    "n_angles_total": "sphere — 각도 런 수",
    "n_angles_with_clusters": "sphere — 군집이 실린 각도 런 수",
    "uniform_records": "deep — 값이 고른 레코드 수(uniform_note 참고)",
    "cap_note": "생성기 군집 상한에 걸렸을 때의 글",
    "compact_note": "sphere 압축본에 없는 칸 안내",
    "note": "군집이 없을 때 까닭",
    "peak_provenance": "피크 출처 표지 — 캠페인 런의 추출에서, 모르면 known=false",
})
ReportContactProfileOut = _shape("ReportContactProfileOut", {
    "available": "프로파일이 있나 — false 면 note(또는 error)가 까닭",
    "kind": "리포트 종류",
    "metric": "쓴 지표",
    "metric_name": "지표 이름(peak_force · total_impulse · total_work)",
    "axis_kind": "축 — angle(sphere) · position(impact)",
    "n_pairs": "파트쌍 수",
    "n_resolved": "파트로 분해된 쌍 수",
    "n_axis": "축(각도 · 위치) 수",
    "pairs": "쌍마다 key · src · dst · src_name · dst_name · contact_id · name · resolved · n_engaged · peak(최대 |값|) · peak_case_key · "
             "peak_label",
    "pairs_truncated": "top 에서 잘랐으면 {returned, total}",
    "axis_summary": "축마다 case_key · label · 각도(위치) · n_engaged · top_pair · top_value — 가장 센 것부터 axis_top 개",
    "axis_summary_note": "「상위 n/N」 글",
    "at": "case_key 를 줬을 때 — {case_key, found, 축 칸, edges[쌍마다 peak_force · total_impulse · total_work]}",
    "trust": "전 각도 Newton-3 접촉력 신뢰 요약(있을 때)",
    "note": "None · resolved 뜻 안내, 또는 프로파일이 없을 때 까닭",
})
ReportBehaviorClustersOut = _shape("ReportBehaviorClustersOut", {
    "available": "군집이 있나 — false 면 note",
    "n_clusters": "선언한 군집 수",
    "archetypes": "아키타입 이름 목록",
    "features_used": "군집에 쓴 특징",
    "n_positions_labeled": "라벨이 붙은 위치 수",
    "groups": "아키타입마다 {archetype, index, n_positions, positions}, 큰 것부터",
    "n_archetypes_used": "실제로 쓰인 아키타입 수",
    "degenerate": "true 면 선언 수보다 적게 쓰였다 — 거동이 갈리지 않았다(degenerate_note)",
    "is_mock": "true 면 합성 군집이다 — 근거로 쓰지 말 것(mock_note)",
    "note": "군집이 없을 때 까닭",
})
ReportAnalyticsOut = _shape("ReportAnalyticsOut", {
    "requested": "준 block(없으면 null)",
    "n_blocks": "요약한 블록 수",
    "blocks": "블록마다 {name, available, bytes, n_subs, subs[{name, summary, values, detail_shape, not_computed, not_computed_note}]} — "
              "없는 블록은 available=false 와 note",
    "raw_access_note": "원본을 꺼내는 길 안내",
})
ReportMediaOut = _shape("ReportMediaOut", {
    "report_id": "리포트 id",
    "kind": "리포트 종류",
    "n_total": "거르기 전 전체 수",
    "n_returned": "돌려준 수",
    "n_images": "돌려준 것 중 볼 수 있는 그림 수",
    "n_videos": "돌려준 것 중 볼 수 없는 것(영상) 수",
    "cases_with_media": "그림이 붙은 case_key 목록",
    "filter": "적용한 거름",
    "media": "항목마다 path · stored_as · file_id · bytes · kind(image · video) · can_llm_view · case_key · set_name · set_title · role · "
             "face · declared",
    "note": "붙은 그림이 없을 때 까닭과 올리는 길",
})


@mcp.tool(annotations=_SET_OUT)
async def attach_cae_package(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    path: Annotated[str, Field(description="꾸러미 파일 경로(<리포트 이름>.ontology.json — 후처리가 리포트 HTML 옆에 낸다). "
                                           "MCP 서버가 읽을 수 있는 같은 머신 경로.")],
    ctx: Context,
) -> AttachCaePackageOut:
    """후처리 해석 온톨로지 꾸러미(`dynaforge.onto_package`, <리포트 이름>.ontology.json)를 리포트에 싣는다 — 캠페인 수준만 행으로.

    리포트를 꾸러미 없이 올렸거나 후처리를 다시 돌려 새 꾸러미가 생겼을 때 쓴다. 리포트를 번들(.zip)로 올리면 같은 폴더 · 같은 이름 줄기의
    꾸러미가, 후처리 예약 반입은 귀환 매니페스트에 꾸러미가 있으면 저절로 실린다(get_job 의 `external.ontology.state` — null 인 성공 잡도
    있다). 실렸는지 · 내용은 report_cae, 리포트를 건너 찾기는 find_cae_parts · find_cae_load_paths. MCP 서버가 `path` 를 읽을 수 있는
    같은 머신에서만 된다. 리포트 소유자만.

    싣는 것은 캠페인 · 파트 판정 · 접촉 · 하중 경로 · 소견 · 응력 집중이다(런 · 파트 응답은 리포트의 케이스가 정본이라 행으로 싣지 않는다).
    어휘 판 · 짝 HTML 지문(꾸러미의 source.html 이 이 리포트 원본 HTML 과 같아야 한다) · 종류 · 런 키 중 하나라도 어긋나거나 같은
    관계(이름 · 양 끝)가 두 번 나오면(`duplicate_relation`) 통째로 거절하고 아무것도 바꾸지 않는다. 같은 꾸러미는 행을 그대로 두고
    (already=true), 다른 꾸러미면 그 리포트의 행을 통째로 바꾼다. 어느 쪽이든 코어 다리(해석 파트 → 코어 부품 maps_to · 소견 → 고장모드
    indicates · 캠페인 → 해석 방법 follows_method)를 지금 거울로 다시 짓는다 — 사람이 이은 선은 남는다(규칙은 report_cae 의 bridges.rule).

    돌려주는 것 — already · vocabulary · counts · runs · warnings · bridges(선 · 후보 · 못 붙인 객체 수, 거울에 타입이 없으면 notes).
    다리 짓기만 깨지면 꾸러미는 실리고 bridges 는 {"error": …} — 같은 꾸러미를 다시 붙이면 다시 짓는다. 리포트가 그사이 지워졌으면
    「찾을 수 없습니다」, 쓰기가 깨지면 까닭과 함께 오류이고 바뀐 것이 없다 — 다만 오류 글이 「실렸는지 모른다」 고 하면 실렸을 수 있다
    (report_cae 로 확인하거나 같은 꾸러미를 다시 붙인다)."""
    import os as _os
    if not _os.path.isfile(path):
        raise RuntimeError(f"path not found on the MCP host: {path}")
    with open(path, "rb") as fh:
        raw = fh.read()
    files = {"file": (_os.path.basename(path), raw, "application/json")}
    async with _client() as c:
        return _unwrap(await c.post(f"/reports/{_seg(report_id)}/cae", files=files, headers=_forward_headers(ctx)))


@mcp.tool(annotations=_READ)
async def report_cae(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context) -> ReportCaeOut:
    """리포트 하나에 실린 해석 온톨로지(캠페인 · 파트 판정 · 하중 경로 · 접촉 · 소견 · 응력 집중)와 코어 다리를 본다.

    한 리포트를 캠페인 수준으로 볼 때, 꾸러미가 실렸는지 확인할 때 쓴다. 여러 리포트를 건너 찾기는 find_cae_parts · find_cae_load_paths,
    런마다의 값은 report_case · report_part_series, 꾸러미 싣기는 attach_cae_package. 리포트를 읽을 수 있는 사람(소유 · 같은 소속)만.

    돌려주는 것 — campaign(단위계 · 낙하 높이 · 충돌 속도 …) · parts(위험한 것부터 — 판정 · 최소 안전율 · 최악 응력과 그 런의 case_key ·
    identity) · load_paths(충격량 큰 것부터 — 파트 쌍 · 맞닿은 비율) · contacts(sides — 양쪽 파트) · findings(about) · hotspots · summary
    · bridges. 키는 꾸러미의 상대 키(part/3 · finding/2 · campaign)다. 실은 적이 없으면 loaded=false 와 붙이는 길(why).

    bridges — 해석 파트 → 코어 부품(maps_to) · 소견 → 고장모드(indicates) · 캠페인 → 해석 방법(follows_method). lines(basis 가 rule ·
    human — 코어 끝 key · 이름 · dst_active · dst_deprecated, 부르는 글이 확정 때와 달라진 사람 선은 renamed_from) · stale(가리키던 해석
    객체가 다시 반입에서 사라진 사람 선 — 지우지 않는다) · candidates(정확히 하나로 안 맞은 것 — 후보 key · 까닭, 선이 아니다) · unmatched
    · unnamed(타입별 key) · counts · rule(맞추는 규칙 전문) · drift(있을 때만 — 붙인 뒤 거울이 바뀌어 저장된 규칙 선이 지금 셈과 다르면
    add · drop, 사람 선 객체를 부르는 글이 바뀌었으면 renamed). 규칙 선은 부르는 칸(파트 name · 소견 title · 캠페인 scenario_kind)의 글이
    살아 있는 코어 객체 하나와 글자 그대로 맞을 때만 선다. 사람 선은 다시 붙여도 남고 다대일(파트 · 캠페인)에서는 규칙을 이긴다. 후보를
    사람 선으로 확정하거나 지우는 것은 MCP 도구가 아니라 REST POST · DELETE /reports/{id}/cae/bridges 다(리포트 주인 · 시스템 관리자).
    다리 보기만 깨지면 bridges 는 {"error": …} 이고 나머지는 그대로 온다."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/cae")


@mcp.tool(annotations=_READ)
async def find_cae_parts(
    ctx: Context,
    min_severity: Annotated[Literal[CAE_SEVERITIES] | None,
                            Field(description=f"판정 하한 — {_one_of(CAE_SEVERITIES)} 중 하나(높은 것부터). 이 판정 **이상**"
                                              "(CRITICAL 이면 CRITICAL 만, WARNING 이면 CRITICAL 도). 비우면 거르지 않는다.")] = None,
    max_safety_factor: Annotated[float | None, Field(ge=0, description="최소 안전율 상한(무차원, 0 이상) — 최소 안전율이 이 값 이하인 "
                                                                       "파트만(안전율이 없는 파트는 빠진다). 1 미만이면 항복이다. "
                                                                       "비우면 거르지 않는다.")] = None,
    project: Annotated[str | None, Field(description=_A_CAE_PROJECT)] = None,
    kind: Annotated[Literal[REPORT_KINDS] | None, Field(description=_A_CAE_KIND)] = None,
    limit: Annotated[int, Field(ge=1, le=CAE_LIMIT_MAX,
                                description=f"최대 건수(1~{CAE_LIMIT_MAX}) — 위험한 순으로 매긴 뒤 자른다. 기본 100.")] = 100,
) -> FindCaePartsOut:
    """리포트를 건너 파트 판정(cae_part)을 위험한 것부터 찾는다 — 판정 · 최소 안전율 · 최악 응력 순으로 매긴 뒤 limit 에서 자른다.

    「어느 리포트의 어느 파트가 항복에 가깝나」 처럼 여러 캠페인을 견줄 때 쓴다. 한 리포트 안을 다 볼 때는 report_cae, 리포트 자체를
    조건으로 거르기는 find_reports. 해석 온톨로지 꾸러미를 실은 리포트만 나온다(attach_cae_package). 읽을 수 있는 리포트(소유 · 같은
    소속, 관리자는 전사)의 것만. 거름은 모두 함께 걸린다(AND).

    돌려주는 것 — items(항목마다 report_id · report_label · kind · project · key(part/3 꼴) · label 과 파트 칸 — part_id · name ·
    material_name · yield_limit · severity · min_safety_factor · worst_von_mises(MPa) · worst_von_mises_run_case · worst_g ·
    worst_g_run_case …) · total(돌려준 건수 — 전체 건수가 아니다) · truncated(limit 만큼 찼으면 true — 더 있을 수 있으니 limit 을
    올리거나 거름을 좁힌다)."""
    params: dict = {"limit": limit}
    for k, v in {"min_severity": min_severity, "max_safety_factor": max_safety_factor,
                 "project": project, "kind": kind}.items():
        if v is not None:
            params[k] = v
    return await _get(ctx, "/cae/parts", params)


@mcp.tool(annotations=_READ)
async def find_cae_load_paths(
    ctx: Context,
    sort: Annotated[Literal[CAE_PATH_SORTS],
                    Field(description=f"정렬 기준(큰 것부터) — {_one_of(CAE_PATH_SORTS)} 중 하나"
                                      "(충격량 N·s · 맞닿은 비율 · 최대 힘 N · 일 mJ). 기본 impulse_max.")] = "impulse_max",
    min_engage_ratio: Annotated[float | None, Field(ge=0, le=1, description="맞닿은 런의 비율 하한(0~1) — 이 쌍이 맞닿은 런 수 ÷ 런 수가 "
                                                                            "이 값 이상인 경로만. 비우면 거르지 않는다.")] = None,
    project: Annotated[str | None, Field(description=_A_CAE_PROJECT)] = None,
    kind: Annotated[Literal[REPORT_KINDS] | None, Field(description=_A_CAE_KIND)] = None,
    limit: Annotated[int, Field(ge=1, le=CAE_LIMIT_MAX,
                                description=f"최대 건수(1~{CAE_LIMIT_MAX}) — 정렬 기준으로 매긴 뒤 자른다. 기본 100.")] = 100,
) -> FindCaeLoadPathsOut:
    """리포트를 건너 하중 경로(하중을 주고받은 파트 쌍, cae_load_path)를 sort 칸이 큰 것부터 찾는다.

    「충격이 어디로 흘렀나」 를 캠페인끼리 견줄 때 쓴다. 한 리포트의 경로 전부는 report_cae 의 load_paths, 각도(위치)마다의 접촉 스칼라는
    report_contact_profile, 하중경로 그래프 상세는 report_energy_flow. 해석 온톨로지 꾸러미를 실은 리포트만 나온다(attach_cae_package).
    읽을 수 있는 리포트(소유 · 같은 소속, 관리자는 전사)의 것만. 거름은 모두 함께 걸린다(AND).

    돌려주는 것 — items(항목마다 report_id · report_label · kind · project · key · label 과 경로 칸 — part_a · part_b(파트 key) ·
    n_runs_engaged · engage_ratio · impulse_max(N·s) · impulse_max_run_case · impulse_median · impulse_p90 · peak_force_max(N) ·
    work_max(mJ)) · total(돌려준 건수 — 전체 건수가 아니다) · truncated(limit 만큼 찼으면 true — 더 있을 수 있다). sort 칸이 빈 경로는
    뒤로 간다."""
    params: dict = {"sort": sort, "limit": limit}
    for k, v in {"min_engage_ratio": min_engage_ratio, "project": project, "kind": kind}.items():
        if v is not None:
            params[k] = v
    return await _get(ctx, "/cae/load-paths", params)


@mcp.tool(annotations=_SET_OUT)
async def attach_cad(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    path: Annotated[str, Field(description="fe_cad 묶음 폴더 또는 그 폴더를 묶은 zip 의 경로 — MCP 서버가 도는 머신에서 읽을 수 있는 "
                                           "경로. 폴더면 맨 위 파일만 싣는다(하위 폴더는 뺀다).")],
    ctx: Context,
) -> AttachCadOut:
    """StepForge fe_cad 묶음(가중치 · glb — 묶음 폴더 또는 그 폴더를 묶은 zip)을 리포트의 기기 형상으로 붙인다.

    묶음 폴더에는 manifest.json · glb · weights.json · weights.bin · parts.json · pairs.json 이 있다. 리포트 화면의 구면 위험도 맵에서
    각도를 골라 「형상 보기」 로 그 기기를 열려면 붙인다. MCP 서버가 `path` 를 읽을 수 있는 같은 머신에서만 된다(upload_local_path 와
    같다). 해석 온톨로지 꾸러미는 attach_cae_package, 시뮬 조건은 attach_report_scenario, 렌더 결과는
    attach_render. 리포트 소유자만. 전송 크기 상한은 백엔드 업로드 상한(max_upload_mb)이다.

    리포트 하나에 묶음 하나다. 같은 묶음(열쇠 · 파일 sha256 같음)을 다시 붙이면 바꾸는 것이 없고(already=true), 다른 열쇠의 묶음이면
    갈아 끼우고 옛 파일을 지운다. 같은 열쇠인데 파일이 다르면 거절한다. 받는 쪽 검사(파일마다 sha256 · 크기, 열쇠, 가중치 배열, glb 정점
    수, 묶음 파트가 리포트 파트와 겹치는가)에 하나라도 걸리면 통째로 거절한다(전부 아니면 전무).

    돌려주는 것 — key(묶음 열쇠) · already · stored(저장한 파일 수) · n_parts · replaced(갈아 끼운 옛 열쇠, 처음이면 null) · warnings."""
    import io as _io
    import os as _os
    import zipfile as _zf
    if _os.path.isdir(path):
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, "w", _zf.ZIP_STORED) as z:
            for name in sorted(_os.listdir(path)):
                full = _os.path.join(path, name)
                if _os.path.isfile(full):            # 묶음 폴더는 평평하다 — 하위 폴더는 싣지 않는다
                    z.write(full, arcname=name)
        raw = buf.getvalue()
    elif _os.path.isfile(path):
        with open(path, "rb") as fh:
            raw = fh.read()
    else:
        raise RuntimeError(f"path not found on the MCP host: {path}")
    files = {"file": ("fe_cad.zip", raw, "application/zip")}
    async with _client() as c:
        return _unwrap(await c.post(f"/reports/{_seg(report_id)}/cad", files=files, headers=_forward_headers(ctx)))


@mcp.tool(annotations=_REPLACE)
async def attach_report_scenario(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    scenario_content: Annotated[str, Field(description="scenario.json 텍스트 그대로 — KooChainRun 의 scenario.json(scenarios 배열이 있는 "
                                                       "JSON 객체). 크기 상한은 백엔드 업로드 상한(max_upload_mb).")],
    ctx: Context,
) -> AttachReportScenarioOut:
    """이미 반입한 리포트에 시뮬 조건(scenario.json)을 붙인다 — 조건 요약을 캐시하고, 원본 K파일이 비어 있으면 template 으로 찾아 잇는다.

    template(.k 파일명)으로 같은 세션의 K파일을 찾는다. 리포트를 조건 없이 반입한 뒤 각도 출처 · 허용차 · 예상 런 수를 달 때 쓴다.
    반입하면서 함께 주려면 ingest_report 의 scenario_content, 과제 · rev · K파일 링크 같은 메타는 update_report_meta. 리포트 소유자만.

    다시 붙이면 리포트의 조건 요약 · scenario_type 을 새 것으로 바꾼다 — 옛 scenario 파일은 세션에 남고 새 파일이 `_1` 꼴 이름으로 하나
    더 생긴다. JSON 이 아니거나 scenarios 배열이 없으면 오류이고 바뀐 것이 없다.

    돌려주는 것 — 갱신된 리포트(id · kind · label · scenario(조건 요약 — sim_params · scenarios[각도 출처 · 허용차 · expected_runs] ·
    templates) · scenario_type · scenario_file_id · source_kfile_id · n_cases · environment …)."""
    files = {"file": ("scenario.json", scenario_content.encode("utf-8"), "application/json")}
    async with _client() as c:
        return _unwrap(await c.post(
            f"/reports/{_seg(report_id)}/scenario", files=files, headers=_forward_headers(ctx)))


@mcp.tool(annotations=_READ)
async def list_reports(
    session_id: Annotated[str, Field(description=_A_SESSION_ID)],
    ctx: Context,
    kfile_id: Annotated[int | None, Field(description="원본 K파일 id(세션 파일 id — get_session 의 files[].id) — 그 K파일에 매달린 "
                                                      "리포트만. 비우면 세션의 모든 리포트.")] = None,
) -> list[ReportListRow]:
    """세션 하나에 반입된 리포트 목록을 최신 것부터 돌려준다 — kfile_id 를 주면 그 K파일에 매달린 리포트만(K파일 하나 ↔ 해석 결과 여럿).

    내 세션의 리포트 id 를 찾을 때 쓴다. 세션을 건너 조건으로 찾기는 find_reports, 리포트 하나의 내용은 report_summary. 세션 주인만
    부를 수 있다.

    ⚠ 세션 주인 스코프다 — 빈 배열은 「전사에 리포트가 없다」 가 아니라 「이 호출자 계정의 이 세션에 없다」 는 뜻이다. 빈 배열을 부재
    증거로 읽지 말라. 전사 규모의 유사 해석 유무는 corpus_summary · report_corpus(개인 식별 없는 집계)로 물어라.

    돌려주는 것 — 행마다 id · kind · label · focus · project_name · doe_strategy · scenario_type · drop_height(mm) · worst_stress(MPa) ·
    max_severity · source_kfile_id · eng_meta(과제 · rev 수동 메타) · n_cases · created_at · environment. 자르지 않고 전부 준다."""
    params = {"kfile_id": kfile_id} if kfile_id is not None else None
    return await _get(ctx, f"/sessions/{_seg(session_id)}/reports", params=params)


@mcp.tool(annotations=_READ)
async def report_blocks(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context) -> ReportBlocksOut:
    """리포트 원본에 임베드된 데이터 블록 전수 목록을 돌려준다 — 이름 · 형태 · 크기 · read_by_parser.

    리포트에 무엇이 들어 있는지부터 볼 때 쓴다 — 리포트 종류(deep · sphere · impact)마다 블록 구성이 다르다. 정규화가 해석하지 않는
    블록도 다 뜬다(read_by_parser=false — 못 쓴다는 뜻이 아니라 전용 도구가 읽지 않는다는 뜻이다). 블록 하나를 꺼내기는 report_block,
    큰 분석 블록 요약은 report_analytics, 정규화된 요약은 report_summary.

    돌려주는 것 — n_blocks · n_unread(read_by_parser=false 수) · blocks[](name · type(object · array · …) · count · sub_keys(앞 40 개까지
    — count 가 전체 수) · item_type · bytes(직렬화 크기 어림, sphere 의 results 는 각도 시계열 포함) · read_by_parser)."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/blocks")


@mcp.tool(annotations=_READ)
async def report_block(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    name: Annotated[str, Field(description="블록 이름 — report_blocks 의 blocks[].name(예 results · hotspot · set_report).")],
    ctx: Context,
    path: Annotated[str, Field(description="하위 경로(선택) — `a.b.0.c` 꼴(dict 키와 list 인덱스를 점으로, 음수 인덱스 가능). "
                                           "비우면 블록 통째.")] = "",
    limit: Annotated[int, Field(ge=0, description="배열을 앞에서 몇 개만(0 이상) — 0(기본)이면 개수로 자르지 않는다. 값이 배열이 "
                                                  "아니면 무시된다.")] = 0,
    max_bytes: Annotated[int, Field(ge=BLOCK_MAX_BYTES_MIN, le=BLOCK_MAX_BYTES_MAX,
                                    description=f"응답 값의 크기 상한(바이트, {BLOCK_MAX_BYTES_MIN}~{BLOCK_MAX_BYTES_MAX}) — 넘는 배열은 "
                                                "앞에서 잘라 truncated 로 말하고, 배열이 아닌 값은 value=null 과 too_big 이다. "
                                                "기본 60000.")] = 60000,
) -> ReportBlockOut:
    """리포트 임베드 블록 하나(또는 그 하위 경로)를 원본 그대로 꺼낸다 — 전용 도구가 읽지 않는 값도 끝까지 되짚는다.

    report_blocks 로 이름을 본 뒤, 또는 report_analytics · report_hotspots 같은 요약의 원본을 확인할 때 쓴다. 요약으로 충분하면 전용
    도구(report_summary · report_case · report_hotspots …)가 가볍다. sphere 의 results 는 `path` 를 `results.<순번>…` 으로 주면 그
    각도만 시계열까지 읽는다(results 통째면 원본 전체를 읽어 무겁다).

    경로가 끊기면 found=false 와 그 자리에서 쓸 수 있는 키 · 인덱스(note — 키는 앞 30 개)를, 없는 블록이면 found=false 와 블록 이름
    목록(available — 앞 80 개)을 준다. 큰 값은 `limit` · `max_bytes` 로 좁혀라 — 넘으면 잘라서 truncated({kind: limit · bytes ·
    too_big, returned, total})로 말한다(조용히 자르지 않는다).

    돌려주는 것 — name · found · path · value · shape(type · count · sub_keys) · bytes · read_by_parser · truncated · note."""
    q = {"max_bytes": max_bytes}
    if path:
        q["path"] = path
    if limit:
        q["limit"] = limit
    return await _get(ctx, f"/reports/{_seg(report_id)}/blocks/{_seg(name)}", q)


@mcp.tool(annotations=_READ)
async def report_hotspots(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    criterion: Annotated[str, Field(description="판정 기준(선택) — von_mises · max_principal · min_principal 등. 이 리포트의 기준은 "
                                                "응답의 criteria. 같은 것만 걸린다. 비우면 전부.")] = "",
    part_id: Annotated[int | None, Field(description=_A_PART_ID_OPT)] = None,
    top: Annotated[int, Field(ge=1, le=HOTSPOT_TOP_MAX,
                              description=f"군집 상위 몇 개(1~{HOTSPOT_TOP_MAX}) — order 로 매긴 뒤 자른다. sphere 의 envelope 도 같은 "
                                          "수로 자른다. 기본 20.")] = 20,
    order: Annotated[str, Field(description=f"정렬 칸 — deep 은 {_one_of(HOTSPOT_ORDERS_DEEP)}, sphere 는 "
                                            f"{_one_of(HOTSPOT_ORDERS_SPHERE)} 중 하나. stress_* 는 절대값 큰 것부터, 나머지는 큰 것부터"
                                            "(sphere 의 rank 만 작은 것부터). 그 종류에 없는 값이면 오류 없이 stress_max 로 매긴다"
                                            "(응답 order 가 실제로 쓴 값). 기본 stress_max.")] = "stress_max",
    case_key: Annotated[str, Field(description="각도 런(폴더) 하나만(sphere, 선택) — clusters[].case_key · envelope[].worst_case_key "
                                               "의 값. envelope 는 이 값과 상관없이 전 각도로 센다. 비우면 전 각도.")] = "",
) -> ReportHotspotsOut:
    """핫스팟 군집(deep · sphere)을 돌려준다 — 파트 × 판정 기준마다 응력이 높은 요소가 모인 곳, sphere 는 각도별 군집과 포락까지.

    군집마다 중심 좌표(mm) · 둘러싼 반경 · 요소 수 · 최대 응력(MPa) · 피크 시각이 온다(deep 은 부피 · 평균 응력 · 피크 요소 ID 까지).
    「어디가 뜨거운가」 를 볼 때 쓴다. sphere(전각도 낙하)는 각도 런마다 실린 군집을 각도와 함께 내고, envelope 에 파트 × 기준마다 전
    각도에서 가장 센 군집(그 각도 · |응력| · 군집이 난 각도 수 n_angles)을 붙인다 — 「어느 각도에서 어느 파트가 뜨거운가」 는 이것부터.
    캠페인의 여러 런을 덱 좌표로 묶기는 campaign_hotspot_sites, 파트 판정은 report_part_risk, 원본 레코드는 report_block(deep 은
    name='hotspot').

    주의 — stress_* 정렬은 절대값이다(min_principal 값은 음수다). deep 의 uniform=true 레코드의 군집은 「가장 뜨거운 곳」 이 아니다
    (uniform_note). sphere 압축본에는 uniform 표시 · 부피 · 평균 응력이 없다(compact_note). 생성기 상한에 걸렸으면 cap_note 가 말한다.
    군집이 없는 리포트는 available=false 와 까닭(note).

    돌려주는 것 — available · n_records · n_clusters(거른 뒤 수) · criteria · parts · order · filter · clusters[] · truncated({returned,
    total} — top 에서 잘랐을 때) · peak_provenance, sphere 는 더해 envelope[] · envelope_truncated · n_clusters_all · n_angles_total ·
    n_angles_with_clusters."""
    q = {"top": top, "order": order}
    if criterion:
        q["criterion"] = criterion
    if part_id is not None:
        q["part_id"] = part_id
    if case_key:
        q["case_key"] = case_key
    return await _get(ctx, f"/reports/{_seg(report_id)}/hotspots", q)


@mcp.tool(annotations=_READ)
async def report_contact_profile(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    metric: Annotated[Literal[CONTACT_METRICS],
                      Field(description=f"지표 — {_one_of(CONTACT_METRICS)}(pf=최대 접촉력 peak_force · ti=총 충격량 total_impulse · "
                                        "tw=총 일 total_work). 크기 비교는 |값|. 기본 pf.")] = "pf",
    top: Annotated[int, Field(ge=1, le=CONTACT_TOP_MAX,
                              description=f"pairs 상위 몇 쌍(1~{CONTACT_TOP_MAX}) — 파트로 분해된 쌍 · 큰 |값| 순으로 매긴 뒤 자른다. "
                                          "기본 10.")] = 10,
    case_key: Annotated[str, Field(description="각도(sphere) · 위치(impact) 하나(선택) — 주면 그 축의 파트쌍 엣지 전부(at.edges — 세 "
                                               "지표)를 함께 준다. 값은 pairs[].peak_case_key · axis_summary[].case_key. 비우면 at 이 "
                                               "없다.")] = "",
    axis_top: Annotated[int, Field(ge=1, le=CONTACT_AXIS_TOP_MAX,
                                   description=f"axis_summary 를 가장 센 접촉이 큰 각도(위치) 상위 몇 개로(1~{CONTACT_AXIS_TOP_MAX}). "
                                               "기본 10.")] = 10,
) -> ReportContactProfileOut:
    """파트쌍 접촉 프로파일(sphere · impact)을 돌려준다 — 어느 파트가 어느 파트를 어느 각도(위치)에서 세게 미는가.

    각도(위치)마다의 접촉 스칼라를 전 각도로 견줄 때 쓴다. 전 각도가 실린다 — 시계열 · 하중경로 그래프 상세는 report_energy_flow 이고 그것은
    상위 각도에만 있다. 여러 리포트를 건너 하중 경로를 찾기는 find_cae_load_paths(꾸러미를 실은 리포트), deep 리포트의 접촉력은
    report_energy_flow.

    돌려주는 것 — metric · metric_name · axis_kind(angle · position) · n_pairs · n_resolved · n_axis · pairs[](쌍마다 src · dst · 이름 ·
    contact_id · resolved · n_engaged · peak(최대 |값|) · peak_case_key · peak_label) · pairs_truncated({returned, total} — top 에서
    잘랐을 때) · axis_summary[](축마다 n_engaged · top_pair · top_value, axis_summary_note 가 「상위 n/N」) · at(case_key 를 줬을 때 —
    found · edges[] 에 peak_force · total_impulse · total_work) · trust(전 각도 Newton-3 접촉력 신뢰 요약, 있을 때). 값의 단위는 리포트
    단위계를 따른다(ton-mm-s 면 N · N·s · mJ).

    주의 — None 은 「그 각도에 그 접촉이 없다」 이다(0 이 아니다). resolved=false 는 파트로 분해되지 않은 접촉이다. 프로파일이 없는
    리포트(deep 등)는 available=false 와 까닭(note)."""
    q = {"metric": metric, "top": top, "axis_top": axis_top}
    if case_key:
        q["case_key"] = case_key
    return await _get(ctx, f"/reports/{_seg(report_id)}/contact_profile", q)


@mcp.tool(annotations=_READ)
async def report_behavior_clusters(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context) -> ReportBehaviorClustersOut:
    """거동 아키타입 군집(impact)을 돌려준다 — 낙하 · 충격 위치를 몇 가지 거동으로 묶은 결과.

    impact 리포트에서 위치마다 거동이 몇 갈래로 갈리나를 볼 때 쓴다. 위치마다의 지표는 report_case · report_worst_cases, 위치별 그림은
    report_media · report_image. deep · sphere 리포트에는 보통 없다(available=false 와 note).

    돌려주는 것 — n_clusters(선언한 군집 수) · archetypes · features_used · n_positions_labeled · groups[](archetype · index ·
    n_positions · positions, 큰 것부터) · n_archetypes_used · degenerate · is_mock(+ degenerate_note · mock_note).

    주의 — degenerate=true 면 선언한 군집 수와 실제로 쓰인 수가 다르다 — 거동이 갈리지 않은 것이고, 그때 「N 가지 거동」 으로 읽으면 안
    된다. is_mock=true 면 합성이다 — 결론의 근거로 쓰지 말라."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/clusters")


@mcp.tool(annotations=_READ)
async def report_analytics(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    block: Annotated[str, Field(description=f"한 블록만(선택) — {_one_of(REPORT_ANALYTICS_BLOCKS)}. 비우면 전부. 이 리포트에 없는 "
                                            "이름이면 오류 없이 그 블록이 available=false 로 온다.")] = "",
) -> ReportAnalyticsOut:
    """큰 분석 블록의 요약을 돌려준다 — 하위 분석마다 생성기가 계산한 summary 그대로와 상세의 형태.

    doe_analysis · deep_analytics · insights · physics · solver_quality · contact_profile · set_report 처럼 그대로는 크고 읽기 어려운
    블록의 결론을 볼 때 쓴다. 원본 값은 report_block(name, path=…)으로 끝까지 되짚고, 블록 전수 목록은 report_blocks.

    summary 는 생성기가 계산한 값 그대로다(여기서 다시 계산하지 않는다 — 다시 계산하면 리포트 화면의 숫자와 조용히 갈린다). not_computed 가
    붙은 하위(empty=true · available=false · ok=false · is_mock=true)는 「값이 0」 이 아니라 계산되지 않았다는 뜻이다.

    돌려주는 것 — requested · n_blocks · blocks[](name · available · bytes · n_subs · subs[](name · summary · values(작은 스칼라와 1.2 KB
    이하 값) · detail_shape(큰 값의 형태만) · not_computed · not_computed_note)) · raw_access_note."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/analytics", {"block": block} if block else None)


@mcp.tool(annotations=_READ)
async def report_media(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    case_key: Annotated[str, Field(description="케이스 하나만(선택) — 응답 cases_with_media 의 값(impact 는 위치 id). 비우면 "
                                               "전부.")] = "",
    kind: Annotated[str, Field(description="image · video 로 거르기(선택) — 같은 것만 걸린다(모르는 값이면 빈 목록). 비우면 "
                                           "둘 다.")] = "",
    role: Annotated[str, Field(description="역할로 거르기(선택) — peak(정점 그림) · view(영상) · render(렌더 결과). 같은 것만 "
                                           "걸린다. 비우면 전부.")] = "",
    images_only: Annotated[bool, Field(description="true 면 모델이 볼 수 있는 그림(can_llm_view — png · jpeg · gif · webp)만. 비교 "
                                                   "전에 켠다. 기본 false.")] = False,
) -> ReportMediaOut:
    """리포트에 붙은 결과 이미지 · 영상 목록을 돌려준다 — 내용은 report_image 로 본다.

    케이스 그림을 보거나 비교하기 전에 무엇이 있는지 볼 때 쓴다. 그림 한 장을 실제로 보기는 report_image, 케이스 여러 개를 그림 + 지표로
    견주기는 report_compare.

    결과 이미지는 리포트 HTML 안에 없고 옆에 딸린 파일이다 — 리포트를 번들(.zip · .tar.gz)로 올려야 함께 들어온다(렌더 결과는
    attach_render). 붙은 그림이 없으면 note 가 그렇게 말한다. can_llm_view 가 네가 볼 수 있는지를 가른다 — png · jpeg · gif · webp 는
    보고 mp4 는 못 본다. 비교에는 images_only=true 를 써라.

    돌려주는 것 — report_id · kind · n_total(거르기 전 전체) · n_returned · n_images · n_videos · cases_with_media · filter · media[](path ·
    stored_as · file_id · bytes · kind · can_llm_view · case_key · set_name · set_title · role · face · declared) · note. 자르지 않는다."""
    q = {}
    for k, v in (("case_key", case_key), ("kind", kind), ("role", role)):
        if v:
            q[k] = v
    if images_only:
        q["images_only"] = True
    return await _get(ctx, f"/reports/{_seg(report_id)}/media", q or None)


# ── 결과 이미지 — **네가 볼 수 있게** 돌려준다 ────────────────────────────────
#
# ★왜 따로 있나 (2026-10-13). `download_result` 는 base64 를 **dict 안에** 넣어 돌려준다.
# 그러면 모델에게는 **글자**로 온다 — 그림을 본 것이 아니다. 이미지를 실제로 보려면
# `Image` 로 돌려줘서 이미지 콘텐츠 블록이 되어야 한다. 그 길이 이 서버에 한 곳도 없었다.
#
# ★mp4 는 모델이 못 본다. `can_llm_view=false` 인 것을 이미지로 내려 하면 아무것도 못 보고
# 응답만 불어난다 — 그래서 **거절하고 대안(peak png)을 말한다.**

_IMAGE_MIME = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
               ".gif": "gif", ".webp": "webp"}
#: 비교 한 번에 보낼 이미지 장수 상한. 넘으면 **뺀 수를 말한다**(조용히 자르지 않는다).
#: 상한이 있는 이유 — 이미지는 응답을 금방 불린다(`TOOL_RESULT_MAX`). 실측 png 한 장 ≈ 15KB.
MAX_COMPARE_IMAGES = 8


async def _fetch_media(ctx: Context, report_id: str, *, case_key: str = "",
                       role: str = "", images_only: bool = True) -> list:
    q = {"images_only": True} if images_only else {}
    for k, v in (("case_key", case_key), ("role", role)):
        if v:
            q[k] = v
    got = await _get(ctx, f"/reports/{_seg(report_id)}/media", q or None)
    return (got or {}).get("media") or []


async def _download_bytes(ctx: Context, session_id: str, file_id: int) -> bytes:
    async with _client() as c:
        r = await c.get(f"/sessions/{_seg(session_id)}/files/{_seg(file_id)}/download",
                        headers=_forward_headers(ctx))
    if r.status_code >= 400:
        raise RuntimeError(f"미디어 다운로드 실패: HTTP {r.status_code}")
    return r.content


def _provenance(report_id: str, case_key: str | None, row: dict, data: bytes) -> str:
    """이미지 한 장의 출처 한 줄 — 게이트웨이가 그림을 리포트로 옮겨도 어디서 왔는지 남게(2026-11-02, 포털 요청)."""
    return "출처 — report=%s case=%s file_id=%s sha256=%s path=%s" % (
        report_id, case_key or "-", row.get("file_id"), hashlib.sha256(data).hexdigest(),
        row.get("path") or "-")


# ── 리포트 조회 도구의 닫힌 어휘 · 경계 · 결과 꼴(공통 계약 C3 · C4 · C7) ─────────────────────────────────────────────────
# 최악 케이스 지표 — 백엔드 GET /reports/{id}/cases 의 sort 가 정렬하는 열(services._SORT_COLS 의 열쇠)이고 report_worst_cases 가 받는
# 집합(_WORST_METRICS)과 같다. 백엔드는 모르는 값을 조용히 max_stress 로 바꾸므로 MCP 가 먼저 거절한다. 상한은 같은 라우트의 limit(1~2000).
WORST_CASE_METRICS = ("max_stress", "max_g", "max_disp", "min_safety_factor")
REPORT_CASES_LIMIT_MAX = 2000
_OUT_PEAK_PROVENANCE = ("피크 출처 표지 — known · peak_source · states_read · states_total · peak_may_be_missed(true 면 d3plot 표본 "
                        "상태에서 읽은 피크라 실제 피크를 놓쳤을 수 있다 · 캠페인 밖 리포트는 known=false)")
_ReportSummaryOut = _shape("ReportSummaryOut", {
    "id": "리포트 id",
    "session_id": "리포트가 든 세션 id",
    "kind": f"리포트 종류 — {_one_of(REPORT_KINDS)}",
    "label": "표시 이름",
    "project_name": "리포트에 박힌 과제 이름",
    "eng_meta": "과제 · 개발 단계 · 설계안 수동 메타",
    "doe_strategy": "방향 컨셉(예 cuboid_26)",
    "scenario_type": "방향 조건 종류",
    "scenario": "시뮬 조건 요약",
    "drop_height": f"낙하 높이({UNIT_LENGTH})",
    "sim_params": "해석 조건",
    "parts": "파트 목록 — part_id · name · group",
    "findings": f"위험 소견 목록({_one_of(SEVERITIES)})",
    "summary": "전역 최악 롤업 — 값 · 케이스 · 파트",
    "worst_stress": f"전역 최악 응력({UNIT_STRESS})",
    "worst_g": f"전역 최악 가속({UNIT_ACCEL})",
    "max_severity": f"가장 높은 소견 심각도 — {_one_of(SEVERITIES)}",
    "n_cases": "케이스 수",
    "reservation": "후처리 예약 원장 — 예약으로 들어온 리포트만",
    "created_at": "반입 시각",
    "environment": "응답을 낸 서버 환경 — dev · prod · unknown",
    "peak_provenance": _OUT_PEAK_PROVENANCE,
})
_ReportCaseOut = _shape("ReportCaseOut", {
    "id": "케이스 행 번호",
    "report_id": "리포트 id",
    "case_key": "케이스 키 — sphere 는 각도 런 폴더, impact 는 위치 id(pos_id), deep 은 single",
    "identity": "케이스 정체 — sphere 는 angle(name · roll · pitch · yaw · category · lon · lat), impact 는 face · pos_id · pos_x · pos_y",
    "num_states": "결과 상태(state) 수",
    "success": "정상 종료 여부",
    "parts_metrics": f"파트 번호 → 지표(peak_stress {UNIT_STRESS} · peak_g {UNIT_ACCEL} · peak_disp {UNIT_LENGTH} · safety_factor …)",
    "max_stress": f"케이스 안 파트 최악 응력({UNIT_STRESS})",
    "max_g": f"케이스 안 파트 최악 가속({UNIT_ACCEL})",
    "max_disp": f"케이스 안 파트 최악 변위({UNIT_LENGTH})",
    "min_safety_factor": "케이스 안 파트 최소 안전율 — 작을수록 위험",
    "peak_provenance": _OUT_PEAK_PROVENANCE,
})
_ReportPartRiskOut = _shape("ReportPartRiskOut", {
    "report_id": "리포트 id",
    "kind": f"리포트 종류 — {_one_of(REPORT_KINDS)}",
    "parts": (f"파트별 최악(최악 응력 큰 것부터) — part_id · part_name · worst_stress(value {UNIT_STRESS} · case_key) · "
              f"worst_g(value {UNIT_ACCEL} · case_key) · worst_disp(value {UNIT_LENGTH} · case_key) · min_safety_factor"),
    "peak_provenance": _OUT_PEAK_PROVENANCE,
})
_ReportDirectionalOut = _shape("ReportDirectionalOut", {
    "report_id": "리포트 id",
    "kind": f"리포트 종류 — {_one_of(REPORT_KINDS)}",
    "part_id": "준 파트 번호 — null 이면 모든 파트",
    "directions": (f"범주별 최악(최악 응력 큰 것부터) — category · n_cases · worst_stress(value {UNIT_STRESS} · part_id · part_name · "
                   f"case_key) · worst_g(value {UNIT_ACCEL} · part_id · part_name · case_key)"),
    "peak_provenance": _OUT_PEAK_PROVENANCE,
})
_ReportFacetsOut = _shape("ReportFacetsOut", {
    "kind": "리포트 종류별 건수 — [{value, count}]",
    "project": "과제(수동 메타 과제, 없으면 project_name)별 건수",
    "dev_rev": "개발 단계 코드별 건수",
    "design_variation": "설계안별 건수(find_reports 의 variation)",
    "doe_strategy": "방향 컨셉별 건수",
    "scenario_type": "조건 종류별 건수",
    "focus": "초점 라벨별 건수",
    "max_severity": "리포트 최고 심각도별 건수",
    "drop_height": f"낙하 높이({UNIT_LENGTH})별 건수",
})


@mcp.tool(annotations=_READ)
async def report_image(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    case_key: Annotated[str, Field(description="케이스 키 — report_media 의 media[].case_key · cases_with_media(report_worst_cases 의 "
                                               "case_key 와 같은 키). 비우면 모든 케이스에서 고른다.")] = "",
    path: Annotated[str, Field(description="그림 한 장의 경로 — report_media 의 media[].path(또는 stored_as) 그대로. 주면 role 은 "
                                           "쓰지 않는다. 비우면 case_key · role 로 고른다.")] = "",
    role: Annotated[str, Field(description="그림 역할 — report_media 의 media[].role 값으로 peak(피크 상태 png) · view(영상 mp4 — "
                                           "모델이 못 본다) · render(attach_render 로 붙인 렌더) 따위다. 기본 peak, 빈 문자열이면 "
                                           "역할을 가리지 않는다. path 를 주면 쓰지 않는다.")] = "peak",
):
    """결과 이미지 한 장을 그림(이미지 콘텐츠)으로 돌려준다 — 글자가 아니라 모델이 직접 보고 판단할 수 있다.

    언제 — 피크 렌더 같은 그림 한 장을 볼 때. 무엇이 붙어 있는지(경로 · 역할 · 케이스 · 볼 수 있는지)는 먼저 report_media 로 본다.
    여러 케이스를 지표와 그림으로 나란히 놓으려면 report_compare, 숫자만 필요하면 report_case · report_worst_cases 다.

    고르는 법 — `path` 를 주면 그 한 장이다(`role` 은 쓰지 않고 `case_key` 만 함께 건다). 안 주면 `case_key` · `role` 로 거른 것
    가운데 모델이 볼 수 있는 첫 장이다. 번들 그림을 케이스 · 역할에 묶는 것은 impact 리포트뿐이다 — sphere · deep 번들 그림은
    case_key · role 이 비어 있으니 `path` 로 고르거나 `role` 을 비워라. attach_render 로 붙인 렌더는 종류와 상관없이 case_key ·
    role=render 가 있다.

    돌려주는 것 — 출처 한 줄(report · case · file_id · sha256 · path)과 이미지 한 장. 그림이 없으면 {error, hint}, 고른 것이 영상(mp4)
    뿐이면 {error, videos(경로 앞 5개), hint} 다 — 모델은 mp4 를 못 보므로 거절하고 같은 케이스의 peak png 를 권한다. `path` 에
    맞는 그림이 없으면 오류다. 결과 이미지는 리포트 HTML 안에 없고 옆에 딸린 파일이라 리포트를 번들(.zip/.tar.gz)로 올렸을 때만
    있다."""
    # ⚠ `path` 로 한 장을 지정했으면 `role` 로 **걸러서는 안 된다** — 예컨대 mp4(role=view)를
    #   지정했는데 기본 `role=peak` 가 먼저 걸러 버리면 "그림이 없다" 라는 **엉뚱한 까닭**을
    #   대고, 정작 "영상은 못 본다" 를 말하지 못한다(실측으로 그랬다).
    rows = await _fetch_media(ctx, report_id, case_key=case_key,
                              role=("" if path else role), images_only=False)
    if not rows:
        return {"error": "그림이 없다",
                "hint": "결과 이미지는 리포트 HTML 안에 없고 **옆에 딸린 파일**이다 — "
                        "리포트를 번들(.zip/.tar.gz)로 올려야 함께 들어온다. "
                        "`report_media` 로 무엇이 붙어 있는지 먼저 보라"}
    if path:
        rows = [r for r in rows if r.get("path") == path or r.get("stored_as") == path]
        if not rows:
            raise RuntimeError(f"그 경로의 그림이 없다: {path} — `report_media` 로 경로를 확인하라")
    pick = next((r for r in rows if r.get("can_llm_view")), None)
    if pick is None:
        vids = [r.get("path") for r in rows][:5]
        return {"error": "고른 것이 영상(mp4)이라 **모델이 볼 수 없다**",
                "videos": vids,
                "hint": "같은 케이스의 `role=peak` png 를 써라 — `report_media(role='peak')`"}
    sess = (await _get(ctx, f"/reports/{_seg(report_id)}")) or {}
    session_id = sess.get("session_id")
    if not session_id:
        raise RuntimeError("리포트의 세션을 알 수 없다")
    data = await _download_bytes(ctx, session_id, pick["file_id"])
    ext = "." + (pick.get("path") or "").rsplit(".", 1)[-1].lower()
    return [_provenance(report_id, pick.get("case_key") or case_key, pick, data),
            Image(data=data, format=_IMAGE_MIME.get(ext, "png"))]



# 케이스 응답(CaseRead)의 롤업 칸 — 파트 피크의 최댓값(안전율은 최솟값)이 맨 위 칸에 있다(백엔드 parser._case_rollup).
_CASE_ROLLUP = {"peak_stress": "max_stress", "peak_g": "max_g", "peak_disp": "max_disp", "safety_factor": "min_safety_factor"}


def _case_metric(case: dict, m: str):
    """report_compare 표 한 칸 — 맨 위 칸(max_stress 등) → 롤업 이름(peak_stress → max_stress) → 파트 지표의 최댓값(min_* · 안전율은
    최솟값). 예전에는 케이스 응답에 없는 rollup · summary 칸만 봐서 표가 늘 「—」 였다."""
    v = case.get(m)
    if v is None and m in _CASE_ROLLUP:
        v = case.get(_CASE_ROLLUP[m])
    if v is None:
        vals = [p[m] for p in (case.get("parts_metrics") or {}).values() if isinstance(p, dict) and isinstance(p.get(m), (int, float))]
        if vals:
            v = min(vals) if m.startswith("min_") or m == "safety_factor" else max(vals)
    return v


@mcp.tool(annotations=_READ)
async def report_compare(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    case_keys: Annotated[list[str], Field(description="견줄 케이스 키 목록 — report_worst_cases 결과의 case_key. 준 순서대로 표 행 · "
                                                      "그림이 놓인다. 없는 키가 하나라도 있으면 오류다.")],
    ctx: Context,
    metrics: Annotated[list[str] | None, Field(description=(
        "표에 놓을 지표 이름 목록 — 비우면(null · 빈 목록) peak_stress · peak_g · peak_disp. 케이스 롤업 칸(max_stress · max_g · "
        "max_disp · min_safety_factor — peak_stress · peak_g · peak_disp · safety_factor 도 그 칸)이나 파트 지표 이름(peak_strain · "
        "peak_vel 등 — 파트 중 최댓값, min_* 은 최솟값). 값이 없는 칸은 「—」 다."))] = None,
    max_images: Annotated[int, Field(description=f"보낼 이미지 장수 상한 — 기본 {MAX_COMPARE_IMAGES}. 그림이 있는 케이스가 이보다 "
                                                 "많으면 뒤 케이스의 그림을 빼고 뺀 장수를 표 아래에 말한다. 0 이면 표만 온다.")
                          ] = MAX_COMPARE_IMAGES,
) -> list:
    """케이스 여러 개를 지표 표와 피크 렌더 그림으로 한 번에 견준다 — 그림을 보면서 「어느 방향이 왜 더 나쁜가」 를 쓸 때.

    언제 — report_worst_cases 로 좁힌 몇 케이스를 그림과 함께 나란히 볼 때. 그림 한 장만이면 report_image, 숫자 순위는
    report_worst_cases, 한 케이스의 파트별 숫자는 report_case, 다른 리포트(개정 · 조건)끼리 파트별 최악을 견주려면 compare_reports 다.

    돌려주는 것 — ① 글 한 덩이 — 케이스마다 한 행인 지표 표와 경고(그림 없는 케이스 · 뺀 그림 수). 칸은 케이스 롤업
    (max_stress 등)이나 파트 지표의 최댓값이고 값이 없으면 「—」 — 파트별 숫자는 report_case 로 본다. ② 케이스마다 출처 한 줄(report · case · file_id · sha256 · path)과
    피크 렌더 이미지(그 케이스 role=peak 의 볼 수 있는 첫 장). 케이스에 묶인 peak 그림은 impact 번들 리포트에만 있어 sphere · deep
    은 보통 표만 온다(그때는 report_media 로 경로를 찾아 report_image(path) 로 본다). 내려받지 못한 그림은 말없이 빠진다.

    한도 — 이미지는 `max_images` 장까지이고 넘으면 몇 장을 뺐는지 말한다. 그림은 응답을 금방 불리므로 많은 케이스는 지표로 먼저
    좁혀 몇 개만 넣어라."""
    metrics = metrics or ["peak_stress", "peak_g", "peak_disp"]
    rep = (await _get(ctx, f"/reports/{_seg(report_id)}")) or {}
    session_id = rep.get("session_id")
    lines = ["# 비교 — report %s (%s)" % (report_id, rep.get("kind")),
             "",
             "| case | " + " | ".join(metrics) + " |",
             "|---" * (len(metrics) + 1) + "|"]
    for ck in case_keys:
        case = (await _get(ctx, f"/reports/{_seg(report_id)}/cases/{_seg(ck)}")) or {}
        cells = []
        for m in metrics:
            v = _case_metric(case, m)
            cells.append("—" if v is None else ("%g" % v if isinstance(v, (int, float)) else str(v)))
        lines.append("| %s | %s |" % (ck, " | ".join(cells)))

    out: list = []
    picks: list[tuple[str, dict]] = []
    missing: list[str] = []
    for ck in case_keys:
        rows = await _fetch_media(ctx, report_id, case_key=ck, role="peak", images_only=True)
        if rows:
            picks.append((ck, rows[0]))
        else:
            missing.append(ck)
    dropped = 0
    if len(picks) > max_images:
        dropped = len(picks) - max_images
        picks = picks[:max_images]
    if missing:
        lines += ["", "⚠ 그림이 없는 케이스: %s" % ", ".join(missing[:12])
                  + (" 외 %d 개" % (len(missing) - 12) if len(missing) > 12 else ""),
                  "   (결과 이미지는 번들로 올려야 들어온다 — `report_media` 로 확인하라)"]
    if dropped:
        lines += ["", "⚠ 이미지 %d 장을 **뺐다**(상한 %d) — 케이스를 줄여 다시 부르거나 "
                      "`max_images` 를 올려라" % (dropped, max_images)]
    if not picks:
        lines += ["", "그림이 하나도 없어 **표만** 돌려준다."]
    out.append("\n".join(lines))
    for ck, row in picks:
        if not session_id:
            break
        try:
            data = await _download_bytes(ctx, session_id, row["file_id"])
        except RuntimeError:
            continue
        ext = "." + (row.get("path") or "").rsplit(".", 1)[-1].lower()
        out.append("## %s — %s\n%s" % (ck, row.get("path", "").rsplit("/", 1)[-1],
                                         _provenance(report_id, ck, row, data)))
        out.append(Image(data=data, format=_IMAGE_MIME.get(ext, "png")))
    return out


@mcp.tool(annotations=_READ)
async def report_summary(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context) -> _ReportSummaryOut:
    """리포트 하나의 머리 정보와 전역 요약을 돌려준다 — 종류 · 과제 · 조건 · 파트 목록 · 소견 · 전역 최악값.

    언제 — 리포트를 처음 열 때 무엇을 분석할 수 있는지(kind · parts · n_cases)부터 여기서 본다. 여기서 얻은 part_id 로
    report_part_risk · report_directional 을, 케이스 순위는 report_worst_cases 를, 소견을 심각도로 거르려면 report_findings 를,
    리포트에 실린 원본 블록 목록은 report_blocks 를 쓴다. 리포트를 찾는 것은 find_reports 다.

    돌려주는 것 — id · session_id · kind(deep · sphere · impact) · label · project_name · eng_meta(과제 · 개발 단계 · 설계안 수동
    메타) · doe_strategy · scenario_type · scenario · drop_height(mm) · sim_params · parts[](part_id · name · group) · findings[] ·
    summary(전역 최악 롤업) · worst_stress(MPa) · worst_g(G) · max_severity · n_cases · created_at · environment ·
    peak_provenance(피크 출처 — report_extraction 참고). 후처리 예약으로 들어온 리포트면 `reservation` 에 예약 원장 — 잡 키 ·
    해석 조건 · 매니페스트 요약(이미지 출처가 실려 왔으면 `manifest.images` 원본 칸과 `manifest.images_observed` 관측 — get_job 의
    `external.images` 와 같은 꼴). 붙인 렌더 기록은 `renders`, CAD 형상 묶음은 `cad`, 해석 온톨로지 적재 요약은 `ontology` 다.
    소유자이거나 같은 소속으로 공유된 리포트만 읽힌다(아니면 「찾을 수 없다」)."""
    return await _get(ctx, f"/reports/{_seg(report_id)}")


@mcp.tool(annotations=_READ)
async def report_worst_cases(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    metric: Annotated[Literal[WORST_CASE_METRICS], Field(
        description=f"줄 세울 지표 — {_one_of(WORST_CASE_METRICS)}. max_stress(케이스 최악 응력 {UNIT_STRESS}) · max_g(최악 가속 "
                    f"{UNIT_ACCEL}) · max_disp(최악 변위 {UNIT_LENGTH}) 는 큰 것부터, min_safety_factor(최소 안전율)는 작은 것부터"
                    "(작을수록 위험). 기본 max_stress.")] = "max_stress",
    top_n: Annotated[int, Field(ge=1, le=REPORT_CASES_LIMIT_MAX,
                                description=f"돌려줄 케이스 수 — 1~{REPORT_CASES_LIMIT_MAX}, 기본 10. 늘 맨 위부터다.")] = 10,
) -> list[_ReportCaseOut]:
    """한 리포트의 케이스를 지표 하나로 줄 세워 위험한 것부터 돌려준다 — sphere 는 최악 낙하 방향, impact 는 최악 충격 위치(deep 은 케이스 하나).

    언제 — 「어느 방향(위치)이 가장 나쁜가」 를 케이스 단위로 볼 때. 파트별 최악과 그 케이스는 report_part_risk, 방향 범주(면 · 엣지 ·
    코너 · F1~F6)별 묶음은 report_directional, 파트 · 각도 · 임계로 거른 낱값은 report_query, 한 케이스의 파트별 상세는
    report_case, 고른 케이스를 그림과 함께 견주려면 report_compare 다.

    돌려주는 것 — 케이스 목록(최대 top_n 개, 값 없는 케이스는 맨 뒤). 항목마다 case_key · identity(sphere 는 angle — name · roll ·
    pitch · yaw · category · lon · lat, impact 는 face · pos_id · pos_x · pos_y) · num_states · success · max_stress(MPa) · max_g(G) ·
    max_disp(mm) · min_safety_factor · parts_metrics(파트 번호 → peak_stress · peak_g · peak_disp · safety_factor …) ·
    peak_provenance. 건너뛰기(페이지)는 없다 — 늘 맨 위 top_n 개이고, 전체 케이스 수는 report_summary 의 n_cases 다."""
    if metric not in _WORST_METRICS:
        raise RuntimeError(f"metric 은 {sorted(_WORST_METRICS)} 중 하나여야 합니다.")
    order = "asc" if metric == "min_safety_factor" else "desc"
    return await _get(
        ctx, f"/reports/{_seg(report_id)}/cases",
        params={"sort": metric, "order": order, "limit": top_n},
    )


@mcp.tool(annotations=_READ)
async def report_part_risk(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
                           part_id: Annotated[int | None, Field(description=_A_PART_ID_OPT)] = None) -> _ReportPartRiskOut:
    """파트마다 최악 응력 · G · 변위와 그 값이 난 케이스(각도 · 위치), 최소 안전율을 돌려준다 — 「어느 파트가 어느 방향(위치)에서 가장 위험한가」.

    언제 — 파트 단위 위험 순위가 필요할 때. part_id 를 주면 그 파트만. 케이스 단위 순위는 report_worst_cases, 방향 범주별 최악은
    report_directional, 여러 리포트(개정 · 조건)의 파트별 최악을 나란히 놓으려면 compare_reports, 한 파트의 시간이력은
    report_part_series, 핫스팟 위치는 report_hotspots 다.

    돌려주는 것 — report_id · kind · parts[] · peak_provenance. parts 는 최악 응력이 큰 것부터(값 없는 파트는 뒤)이고 항목마다
    part_id · part_name · worst_stress{value(MPa) · case_key} · worst_g{value(G) · case_key} · worst_disp{value(mm) · case_key} ·
    min_safety_factor(없으면 null). 케이스를 모두 훑어 계산하고 자르지 않는다 — 파트가 많으면 응답이 길다. 없는 part_id 면
    parts 가 빈 목록이다."""
    params = {"part_id": part_id} if part_id is not None else None
    return await _get(ctx, f"/reports/{_seg(report_id)}/parts", params=params)


@mcp.tool(annotations=_READ)
async def report_case(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    case_key: Annotated[str, Field(description="케이스 키 — report_worst_cases 결과의 case_key(sphere 는 각도 런 폴더 이름 · 없으면 "
                                               "각도 이름, impact 는 위치 id(pos_id), deep 은 single). 같은 키만 걸린다.")],
    ctx: Context,
) -> _ReportCaseOut:
    """케이스(각도 · 위치) 하나의 상세를 돌려준다 — identity 와 파트별 지표.

    언제 — report_worst_cases · report_part_risk · report_directional 이 가리킨 case_key 하나를 파고들 때. 그 케이스 · 파트의
    시간이력은 report_part_series, 하중 경로 · 에너지는 report_energy_flow, 그 케이스의 핫스팟은 report_hotspots(case_key), 그림은
    report_image(case_key), 여러 케이스를 그림과 함께 견주려면 report_compare 다.

    돌려주는 것 — case_key · identity(sphere 는 angle — name · roll · pitch · yaw · category · lon · lat, impact 는 face · pos_id ·
    pos_x · pos_y, deep 은 빈 객체) · num_states · success · parts_metrics(파트 번호 → peak_stress(MPa) · peak_g(G) · peak_disp(mm) ·
    safety_factor 등 리포트가 실은 지표) · 케이스 최악 max_stress · max_g · max_disp · min_safety_factor · peak_provenance.
    없는 case_key 면 오류다(「케이스를 찾을 수 없습니다」)."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/cases/{_seg(case_key)}")


@mcp.tool(annotations=_READ)
async def report_directional(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
                             part_id: Annotated[int | None, Field(description=_A_PART_ID_OPT)] = None) -> _ReportDirectionalOut:
    """방향 범주별 최악 응력 · G 를 돌려준다 — sphere 는 face · edge · corner(면 · 엣지 · 코너), impact 는 충격 면 F1~F6, deep 은 single 하나.

    언제 — 「어느 방향 범주가 가장 위험한가」. part_id 를 주면 그 파트만 따진 범주별 취약도다. 낱낱의 케이스 순위는
    report_worst_cases, 파트별 최악은 report_part_risk, 범주 · 각도군의 분포 통계(평균 · 산포 · 부품별 분해)는 report_angle_stats,
    sphere 방향 섭동 산포는 report_scatter, 범주로 거른 낱값은 report_query(category) 다.

    돌려주는 것 — report_id · kind · part_id(준 값, 없으면 null) · directions[] · peak_provenance. directions 는 최악 응력이 큰
    것부터이고 항목마다 category · n_cases(그 범주의 케이스 수) · worst_stress{value(MPa) · part_id · part_name · case_key} ·
    worst_g{value(G) · part_id · part_name · case_key}. 범주가 없는 케이스는 unknown 으로 묶인다. 자르지 않는다."""
    params = {"part_id": part_id} if part_id is not None else None
    return await _get(ctx, f"/reports/{_seg(report_id)}/directional", params=params)


@mcp.tool(annotations=_READ)
async def report_facets(ctx: Context) -> _ReportFacetsOut:
    """읽을 수 있는 리포트 전체에서 검색 칸마다 어떤 값이 몇 건 있는지 돌려준다 — find_reports 로 좁히기 전에 「무엇이 있나」 를 본다.

    언제 — find_reports 의 project · dev_rev · variation · doe_strategy · scenario_type · focus 에 넣을 값을 모를 때(그 칸들은
    여기 값과 같은 것만 걸린다). 리포트 하나의 내용은 report_summary, 해석 결과 전체 분포(종류 · 케이스 수 · 반복 소견)는
    report_corpus 다.

    돌려주는 것 — 칸마다 [{value, count}] 목록이다 — kind · project(수동 메타 과제, 없으면 리포트의 project_name) · dev_rev(개발
    단계 코드) · design_variation(설계안 — find_reports 의 variation) · doe_strategy(방향 컨셉) · scenario_type(조건 종류) ·
    focus(초점 라벨) · max_severity(리포트 최고 심각도) · drop_height(낙하 높이 mm). 값이 null 인 리포트는 세지 않는다. 범위는
    소유분과 같은 소속으로 공유된 리포트(관리자는 전부)다. 인자도 페이지도 없다."""
    return await _get(ctx, "/reports/facets")


# ── 리포트 찾기 · 조회 · 비교 · 등재 · 지우기(계약 C1 ~ C8) — 허용값 · 경계는 백엔드가 받는 집합 · 경계를 그대로 옮겼다 ──────────────────
# 질의 지표 = GET /reports/{id}/query 의 metric(services._QUERY_METRICS 의 열쇠). 질의 상한 · 각도 허용 · 부품 상위 수 = 그 라우트들의 Query
# 경계. 개발 단계 = datahub.parse_stage 가 받는 코드 + 빈 글(백엔드가 리포트 메타로 갈음해 받는다). 산포 지표(parser._SCATTER_METRICS)는
# sphere 가 아닌 리포트에서 지표를 보지 않고 note 만 주므로 enum 으로 막지 않고 설명에만 쓴다.
REPORT_QUERY_METRICS = ("peak_stress", "peak_strain", "peak_g", "peak_disp", "peak_vel", "peak_plastic_strain",
                        "peak_principal", "min_principal", "peak_principal_stress", "min_principal_stress",
                        "peak_principal_strain", "min_principal_strain", "peak_vm_strain", "safety_factor",
                        "peak_ie", "peak_ke", "final_ie", "final_ke")
REPORT_QUERY_LIMIT_MAX = 5000
REPORT_ANGLE_TOL_MAX_DEG = 180
REPORT_TOP_PARTS_MAX = 50
REPORT_SCATTER_METRICS = ("peak_stress", "peak_strain", "peak_plastic_strain", "peak_g", "peak_disp", "peak_vel",
                          "peak_ie", "peak_ke")
DATAHUB_STAGES = ("pre", "dv1", "dv2", "dv3", "dvr", "pv1", "pv2", "pv3", "pvr", "pra", "mp", "")

_A_VALUE_UNIT = (f"단위는 물리량의 단위(응력 {UNIT_STRESS} · 가속 {UNIT_ACCEL} · 변위 {UNIT_LENGTH} · 변형률 무차원, 그 밖은 "
                 "리포트에 실린 단위 그대로)")
_A_PEAK_PROV = "피크 출처 표지 — 캠페인 런에서 온 리포트만 값이 있다(모르면 known:false)"

FindReportsOut = _shape("FindReportsOut", {
    "items": "리포트 행 — id · kind · label · focus · project_name · doe_strategy · scenario_type · drop_height(mm) · "
             "worst_stress(MPa) · max_severity · source_kfile_id · eng_meta · n_cases · created_at · environment",
    "total": "돌려준 행 수(items 의 길이) — 조건에 맞는 전체 수가 아니다",
    "reason": "0 건일 때 까닭 글(도구 실패가 아니라 맞는 리포트가 없다는 뜻). 있으면 null",
    "truncated": "true 면 limit 에서 잘렸을 수 있다 — 다음 쪽은 없으니 조건을 좁혀 다시 부른다",
})
ReportQueryOut = _shape("ReportQueryOut", {
    "report_id": "리포트 id", "kind": "deep · sphere · impact", "metric": "물은 물리량",
    "n_matched": "조건에 맞은 행 수(자르기 전 · 훑기 상한에 걸렸으면 그때까지 센 수)",
    "returned": "facts 에 실은 행 수",
    "truncated": "limit 또는 훑기 상한(케이스 × 파트 20000)에서 잘렸으면 true",
    "facts": "[case_key · identity(각도 · 위치) · part_id · part_name · quantity · value · at_time(피크 시각 s, 있으면)] — value 순",
    "peak_provenance": _A_PEAK_PROV,
})
ReportScatterOut = _shape("ReportScatterOut", {
    "kind": "리포트 종류(sphere 가 아니면 note 만 온다)", "metric": "지표", "part_id": "고른 파트(null 이면 케이스마다 파트 최댓값)",
    "n_cases": "묶은 케이스 수", "n_bases": "표본이 있는 정준 방향 수",
    "degenerate": "방향당 표본이 하나뿐이라 산포가 0 이면 true",
    "note": "까닭 글(degenerate · sphere 가 아님)",
    "most_severe": "평균이 가장 큰 방향(groups 의 한 행)", "most_scattered": "CoV 가 가장 큰 방향(표본 2 이상)",
    "groups": "[base · category · representative · n · mean · std · cov · min · max · worst_value · worst_case_key] — 평균 큰 순",
    "peak_provenance": _A_PEAK_PROV,
})
ReportPartEnergyOut = _shape("ReportPartEnergyOut", {
    "kind": "리포트 종류", "part_id": "고른 파트(있으면)", "t": "시간 축(s) — matsum 이 있을 때",
    "parts": "[part_id · part_name · internal_energy · kinetic_energy · peak_internal_energy · peak_kinetic_energy · "
             "hourglass_energy(있으면)]",
    "note": "값이 없을 때 까닭(matsum 없음 · deep 이 아님 · 파트 없음)",
})
ReportAngleStatsOut = _shape("ReportAngleStatsOut", {
    "kind": "리포트 종류", "metric": "지표", "part_id": "고른 파트(null 이면 케이스마다 파트 대표값)",
    "available_metrics": "이 리포트에 실린 파트 물리량 이름",
    "selection": "고른 방식 — mode(near · base · category · all_bases · all_categories)와 그 인자",
    "n_cases_total": "지표 값이 있는 케이스 수", "n_groups": "그룹 수",
    "groups": "[group_key · category · representative · stats · worst · parts(part_id 를 비웠을 때)]",
    "note": "까닭 글(지표 없음 · sphere 전용 고르기 · 맞는 케이스 없음)",
    "peak_provenance": _A_PEAK_PROV,
})
ReportEnergyFlowOut = _shape("ReportEnergyFlowOut", {
    "kind": "리포트 종류",
    "energy_balance": "deep — energy_ratio_min · energy_ratio_max · has_mass_added · normal_termination",
    "energy_series": "deep — t · total_energy · kinetic_energy · internal_energy · hourglass_energy · energy_ratio",
    "contacts": "deep — rcforc 접촉별 [id · name · side · peak_fmag] 큰 순",
    "contact_metrics": "deep — 리포트에 실린 접촉 계측(있으면)", "has_matsum": "deep — 파트별 에너지(matsum)가 실렸나",
    "case_key": "sphere · impact — 물은 케이스", "flow_case_key": "sphere · impact — 실제로 쓴 케이스(없으면 null)",
    "n_flows": "sphere · impact — 하중경로 상세가 실린 케이스 수",
    "energy_flow": "sphere · impact — 하중경로 그래프(form · impactor_ke_* · energy_dissipated · propagation_order · nodes · "
                   "edges · form_note)",
    "detail_note": "생성기가 상세를 일부 케이스에만 실었다는 글", "available_case_keys": "상세가 있는 케이스(200 개까지)",
    "note": "값이 없을 때 까닭",
})
ReportGeometryOut = _shape("ReportGeometryOut", {
    "kind": "리포트 종류", "device_outline": "impact — 디바이스 외곽선(XY)", "device_bbox": "impact — 디바이스 경계 상자",
    "parts": "impact — [part_id · name · group · footprint(XY 다각형) · synthetic_footprint · zmin · zmax]",
    "synthetic_footprints": "지어낸 footprint 를 가진 파트 수", "footprints_are_measured": "모든 footprint 가 실제 형상이면 true",
    "footprint_warning": "지어낸 footprint 가 있을 때 경고 글",
})
ReportPartSeriesOut = _shape("ReportPartSeriesOut", {
    "kind": "리포트 종류", "case_key": "케이스(sphere · impact)", "part_id": "파트 번호",
    "series_blocks": "deep — 실린 시계열 블록 이름",
    "stress": "deep — {물리량: {t · max · avg · global_max · global_min · time_of_max · unit}}(다른 블록도 같은 꼴로 온다)",
    "motion": "deep — t · disp_mag · vel_mag · acc_mag",
    "stress_ts": "sphere · impact — 응력 시계열", "strain_ts": "sphere — 변형률 시계열", "g_ts": "sphere — 가속 시계열(max 별칭)",
    "disp_ts": "sphere — 변위 시계열(max 별칭)", "acc_ts": "sphere — 가속도 시계열",
    "note": "케이스 · 파트를 못 찾았을 때 글",
})
ReportFindingRow = _shape("ReportFindingRow", {
    "severity": "CRITICAL · WARNING · INFO", "title": "소견 제목", "detail": "내용", "recommendation": "권고",
    "peak_provenance": _A_PEAK_PROV,
})
CompareReportsOut = _shape("CompareReportsOut", {
    "kinds": "{리포트 id: kind}", "note": "kind 가 섞였을 때 경고(아니면 null)",
    "parts": "[part_id · part_name · by_report{리포트 id: {worst_stress(MPa) · worst_stress_case · min_safety_factor}}] — "
             "part_id 글자 순",
})
PublishReportToDatahubOut = _shape("PublishReportToDatahubOut", {
    "record_id": "DataHub 레코드 id(SIM-…)", "data_type": "SIM", "doc_type": "sim_report", "sim_domain": "시뮬 도메인",
    "report_kind": "리포트 종류", "view": "레코드 주소(DataHub /api/records/<id>)",
})
DeleteReportOut = _shape("DeleteReportOut", {"message": "지웠다는 글"})


@mcp.tool(annotations=_READ)
async def find_reports(
    ctx: Context,
    kind: Annotated[Literal[REPORT_KINDS] | None, Field(description=f"리포트 종류 — {_one_of(REPORT_KINDS)} 중 하나"
                                                  "(sphere 전각도 낙하 · impact 부분 충격 · deep 단건). 비우면 모두.")] = None,
    project: Annotated[str | None, Field(description="과제 — 수동 메타의 과제(eng_meta.project) 또는 리포트에 박힌 "
                                                     "project_name 과 같은 것. " + _A_FACET + " 비우면 거르지 않는다.")] = None,
    dev_rev: Annotated[str | None, Field(description="개발 단계 코드(예 dv1 · pv2 · mp) — " + _A_FACET
                                                     + " 비우면 거르지 않는다.")] = None,
    variation: Annotated[str | None, Field(description="설계안 — " + _A_FACET + " 비우면 거르지 않는다.")] = None,
    doe: Annotated[str | None, Field(description="DOE 캠페인(study) — " + _A_FACET + " 비우면 거르지 않는다.")] = None,
    focus: Annotated[str | None, Field(description="초점 라벨(예 camera-detail) — " + _A_FACET + " 비우면 거르지 않는다.")] = None,
    doe_strategy: Annotated[str | None, Field(description="방향 컨셉(예 cuboid_26 · fibonacci_162) — " + _A_FACET
                                                          + " 비우면 거르지 않는다.")] = None,
    scenario_type: Annotated[str | None, Field(description="조건 종류(scenario source_type) — " + _A_FACET
                                                           + " 비우면 거르지 않는다.")] = None,
    drop_height: Annotated[float | None, Field(description=f"낙하 높이({UNIT_LENGTH}) — 이 높이 ±{HEIGHT_TOL_MM:g} "
                                                           f"{UNIT_LENGTH} 의 리포트. 비우면 거르지 않는다.")] = None,
    severity: Annotated[Literal[SEVERITIES] | None, Field(description=f"심각도 — {_one_of(SEVERITIES)} 중 하나. 리포트의 최고 "
                                                      "소견 심각도가 이 심각도 **이상**인 리포트(WARNING 이면 CRITICAL 도 걸린다). "
                                                      "단 INFO 는 최고 심각도가 INFO 인 리포트만 건다. 비우면 거르지 않는다.")] = None,
    min_worst_stress: Annotated[float | None, Field(description=f"최악 응력 하한({UNIT_STRESS}) — 리포트의 전역 최악 "
                                                                "응력이 이 값 이상. 비우면 하한 없음.")] = None,
    min_worst_g: Annotated[float | None, Field(description=f"최악 가속 하한({UNIT_ACCEL}) — 리포트의 전역 최악 가속이 "
                                                           "이 값 이상. 비우면 하한 없음.")] = None,
    has_part: Annotated[str | None, Field(description="파트 이름 — 이 이름(정확히 같은 것)의 파트를 가진 리포트"
                                                      "(report_summary 의 parts[].name). 비우면 거르지 않는다.")] = None,
    q: Annotated[str | None, Field(description="글자 검색 — 라벨 · 과제(박힌 이름 · 수동 메타)에 이 글자가 든 리포트"
                                               "(대소문자 무시). 비우면 거르지 않는다.")] = None,
    since: Annotated[str | None, Field(description="만든 때 하한 — ISO 8601(예 2026-10-01 또는 "
                                                   "2026-10-01T09:00:00+09:00). 이 시각 이후. 꼴이 틀리면 오류. 비우면 하한 없음.")] = None,
    until: Annotated[str | None, Field(description="만든 때 상한 — ISO 8601(since 와 같은 꼴). 이 시각 이전. "
                                                   "비우면 상한 없음.")] = None,
    session_id: Annotated[str | None, Field(description="세션 id — 이 세션의 리포트만(list_sessions 의 id). "
                                                        "비우면 모든 세션.")] = None,
    kfile_id: Annotated[int | None, Field(description="K파일 id — 이 K파일(세션 파일)에서 나온 리포트만"
                                                      "(get_session 의 files[].id). 비우면 거르지 않는다.")] = None,
    external_job_key: Annotated[str | None, Field(description="외부 잡 키(64자까지) — 후처리 예약이 반입한 리포트의 잡 키 "
                                                              "`stcx:<Slurm 잡 id>`(정확히 같음). get_job 의 external 과 짝. "
                                                              "비우면 거르지 않는다.")] = None,
    config_generation: Annotated[str | None, Field(description="설정 세대(64자까지) — 내 캠페인에서 이 세대 이름표가 붙은 "
                                                               "런에 묶인 리포트만(campaign_provenance 의 generations). "
                                                               "비우면 거르지 않는다.")] = None,
    sort: Annotated[Literal[FIND_SORTS], Field(description=f"정렬 기준 — {_one_of(FIND_SORTS)} 중 하나. 기본 created_at"
                                                           "(만든 때). 그 값이 없는 리포트는 뒤로 간다.")] = "created_at",
    order: Annotated[Literal[SORT_ORDERS], Field(description=f"정렬 방향 — {_one_of(SORT_ORDERS)}. 기본 desc"
                                                             "(큰 것 · 최근 것부터).")] = "desc",
    limit: Annotated[int, Field(ge=1, le=FIND_LIMIT_MAX,
                                description=f"최대 건수(1~{FIND_LIMIT_MAX}) · 기본 100. 결과가 이만큼이면 truncated:true — "
                                            "더 있을 수 있다(다음 쪽은 없다 — 조건을 좁혀라).")] = 100,
) -> FindReportsOut:
    """조건으로 리포트를 찾는다 — 전 세션에서 내 것 + 같은 소속으로 공유된 것(관리자는 전사)을 서버(SQL)가 걸러 한 쪽만 준다.

    리포트 id 를 모를 때 맨 먼저 쓴다. 어떤 과제 · 개발 단계 · 설계안 · 방향 컨셉 · 초점 · 조건 종류 · 높이가 있는지는 report_facets 로
    먼저 훑고 그 값을 그대로 넣는다(같은 것만 걸린다). 같은 전각도라도 방향 컨셉 · 초점 · 조건 · 높이로 따로 골라낸다. 한 세션의 리포트를
    차례로 보려면 list_reports, 찾은 리포트 안은 report_summary(무엇이 있나) · report_query(부품 × 각도 × 물리량 값) ·
    report_findings(소견)로 간다.

    돌려주는 것 — `{items, total, reason, truncated}`. items 는 리포트 행(id · kind · label · project_name · drop_height ·
    worst_stress · max_severity · n_cases · eng_meta · created_at …)이고 total 은 돌려준 행 수다(조건에 맞는 전체 수가 아니다).
    0 건이어도 빈 봉투(`items:[]` · `total:0` · `reason`)를 준다 — 도구 실패가 아니라 「이 조건에 맞는 리포트가 없다」 는 뜻이다.
    한 번에 limit 건까지이고 다음 쪽은 없다 — `truncated:true` 면 잘렸을 수 있으니 조건을 좁히거나 sort · order 를 바꿔 다시 부른다."""
    params: dict = {"sort": sort, "order": order, "limit": limit}
    for k, v in {
        "kind": kind, "project": project, "dev_rev": dev_rev, "variation": variation, "doe": doe,
        "focus": focus, "doe_strategy": doe_strategy, "scenario_type": scenario_type,
        "drop_height": drop_height, "severity": severity,
        "min_worst_stress": min_worst_stress, "min_worst_g": min_worst_g,
        "has_part": has_part, "q": q, "since": since, "until": until,
        "session_id": session_id, "kfile_id": kfile_id, "external_job_key": external_job_key,
        "config_generation": config_generation,
    }.items():
        if v is not None:
            params[k] = v
    items = await _get(ctx, "/reports", params=params)
    items = items if isinstance(items, list) else []
    return {"items": items, "total": len(items),
            "reason": None if items else "리포트 없음 — 이 조건에 맞는 리포트가 없다(도구 실패가 아니다)",
            "truncated": len(items) >= limit}


@mcp.tool(annotations=_READ)
async def report_query(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    part_id: Annotated[int | None, Field(description=_A_PART_ID_OPT)] = None,
    category: Annotated[str | None, Field(description="방향 범주 — sphere 는 각도 범주(예 face · edge · corner), impact 는 "
                                                      "충격 면(F1 ~ F6), deep 은 single. 정확히 같은 것만"
                                                      "(report_directional 의 directions[].category). 비우면 모두.")] = None,
    angle_name: Annotated[str | None, Field(description="각도 이름 — 정확히 같은 것(예 F1_Back · P0001). report_worst_cases · "
                                                        "report_case 의 identity.angle.name. 비우면 모두.")] = None,
    near_roll: Annotated[float | None, Field(description="근접 기준 roll(도) — near_pitch 와 함께 그 방향 둘레(angle_tol_deg) "
                                                         "의 케이스만. 근접 거르기를 켰는데 비우면 0 으로 친다.")] = None,
    near_pitch: Annotated[float | None, Field(description="근접 기준 pitch(도) — near_roll 과 같다. 근접 거르기를 켰는데 "
                                                          "비우면 0 으로 친다.")] = None,
    near_yaw: Annotated[float | None, Field(description="근접 기준 yaw(도) — 보내기만 하고 서버가 쓰지 않는다(yaw 는 낙하 "
                                                        "방향을 바꾸지 않는다). 이것만으로는 근접 거르기가 켜지지 않는다.")] = None,
    angle_tol_deg: Annotated[float | None, Field(ge=0, le=REPORT_ANGLE_TOL_MAX_DEG,
                                                 description=f"근접 허용 대원거리(도, 0~{REPORT_ANGLE_TOL_MAX_DEG}). "
                                                             "near_roll · near_pitch · 이것 중 하나라도 주면 근접 거르기가 "
                                                             "켜진다. 비우면 15 도.")] = None,
    metric: Annotated[Literal[REPORT_QUERY_METRICS], Field(description=f"물리량 — {_one_of(REPORT_QUERY_METRICS)} 중 하나. "
                                                                       "기본 peak_stress. 리포트에 없는 물리량이면 맞는 행이 0 "
                                                                       "이다(실린 것은 report_angle_stats 의 "
                                                                       "available_metrics).")] = "peak_stress",
    min_value: Annotated[float | None, Field(description="값 하한 — 이 값 이상만. " + _A_VALUE_UNIT
                                                         + ". 비우면 하한 없음.")] = None,
    max_value: Annotated[float | None, Field(description="값 상한 — 이 값 이하만. " + _A_VALUE_UNIT
                                                         + ". 비우면 상한 없음.")] = None,
    sort: Annotated[Literal[SORT_ORDERS], Field(description=f"값 정렬 — {_one_of(SORT_ORDERS)}. 기본 desc(큰 것부터). "
                                                            "safety_factor · min_* 처럼 작을수록 나쁜 물리량은 asc.")] = "desc",
    limit: Annotated[int, Field(ge=1, le=REPORT_QUERY_LIMIT_MAX,
                                description=f"돌려줄 최대 행 수(1~{REPORT_QUERY_LIMIT_MAX}) · 기본 200. 넘으면 "
                                            "truncated:true 이고 n_matched 가 자르기 전 수다.")] = 200,
) -> ReportQueryOut:
    """리포트 하나 안의 값(fact)을 부품 · 각도 · 물리량 · 값 범위로 걸러 평탄한 행으로 준다 — 거르기 · 정렬 · 자르기는 서버가 한다.

    「이 부품이 이 각도(근처)에서 응력이 얼마인가」 · 「응력 상위 N 개 (케이스, 부품)」 처럼 값을 바로 묻는 질문에 쓴다. 케이스가 수천인
    sphere 도 전 케이스를 훑지 않고 답한다. 각도군의 분포 통계(평균 · 표준편차 · 백분위)는 report_angle_stats, 26 정준 방향별 산포는
    report_scatter, 케이스 순위만은 report_worst_cases, 파트별 최악 한 줄은 report_part_risk, 한 케이스의 시간이력은
    report_part_series 다.

    각도 근접 — near_roll · near_pitch 를 리포트의 각도 규약(swap 포함)대로 방향으로 바꿔 대원거리 angle_tol_deg 안의 케이스를 고른다.
    near_yaw 는 서버가 보지 않는다.

    돌려주는 것 — `facts`[case_key · identity · part_id · part_name · quantity · value · at_time(피크 시각, 있으면)](value 순,
    limit 개까지) + `n_matched`(자르기 전 맞은 수) · `returned` · `truncated`. 한 질의가 훑는 케이스 × 파트는 20000 까지다 — 넘으면
    거기서 멈추고 truncated:true 다(n_matched 도 그때까지 센 수). 그때는 조건을 좁혀 다시 부른다. 캠페인 런에서 온 리포트면
    `peak_provenance` 에 피크 출처가 있다."""
    params: dict = {"metric": metric, "sort": sort, "limit": limit}
    for k, v in {
        "part_id": part_id, "category": category, "angle_name": angle_name,
        "near_roll": near_roll, "near_pitch": near_pitch, "near_yaw": near_yaw,
        "angle_tol_deg": angle_tol_deg, "min_value": min_value, "max_value": max_value,
    }.items():
        if v is not None:
            params[k] = v
    return await _get(ctx, f"/reports/{_seg(report_id)}/query", params=params)


@mcp.tool(annotations=_READ)
async def report_scatter(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    metric: Annotated[str, Field(description=f"지표 — {_one_of(REPORT_SCATTER_METRICS)} 중 하나(sphere 리포트에서 이 밖이면 "
                                             "오류). 기본 peak_stress.")] = "peak_stress",
    part_id: Annotated[int | None, Field(description="파트 번호(LS-DYNA PID) — report_summary 의 parts[].part_id. 비우면 "
                                                     "케이스마다 모든 파트의 최댓값.")] = None,
) -> ReportScatterOut:
    """방향 섭동 산포를 낸다(sphere 전용) — 케이스를 가장 가까운 26 정준 방향(면 6 · 엣지 12 · 코너 8)으로 묶어 방향별 지표 산포를 잰다.

    「같은 낙하 방향을 조금 틀면 결과가 얼마나 흔들리나」(방향 민감도)를 물을 때 쓴다. 방향마다 여러 런이 있는 섭동 DOE 라야 뜻이 있다 —
    방향당 표본이 하나뿐(순수 26면)이면 `degenerate:true`(산포 0)다. 고른 각도군(범주 · 기준 방향 · 원하는 방향의 콘)의 분포 통계는
    report_angle_stats, 개별 값은 report_query, 범주별 최악만은 report_directional 이다.

    돌려주는 것 — `groups`[base(정준 방향 x,y,z) · category(face · edge · corner) · representative(가장 가까운 각도 이름) · n · mean ·
    std(표본) · cov · min · max · worst_value · worst_case_key](평균 큰 순) + `most_severe`(평균이 가장 큰 방향) ·
    `most_scattered`(CoV 가 가장 큰 방향, 표본 2 이상) · n_cases · n_bases · degenerate · note. 지표가 리포트에 없으면 groups 가 빈다.
    sphere 가 아닌 리포트는 `note` 만 온다(지표를 보지 않는다)."""
    params = {"metric": metric}
    if part_id is not None:
        params["part_id"] = part_id
    return await _get(ctx, f"/reports/{_seg(report_id)}/scatter", params=params)


@mcp.tool(annotations=_READ)
async def report_part_energy(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    part_id: Annotated[int | None, Field(description="파트 번호(LS-DYNA PID) — report_summary 의 parts[].part_id. 비우면 "
                                                     "matsum 의 모든 파트.")] = None,
) -> ReportPartEnergyOut:
    """파트별 에너지(내부 IE · 운동 KE · 있으면 hourglass) 시간이력을 준다 — deep 리포트에 LS-DYNA matsum 이 실렸을 때만 값이 있다.

    「어느 파트가 에너지를 얼마나 흡수했나 · 언제 최대였나」 를 물을 때 쓴다. 원본 리포트를 다시 읽는다. 전체 에너지 밸런스
    (hourglass · energy_ratio) · 접촉력 · 하중경로는 report_energy_flow, 응력 · 변형률 · G 시간이력은 report_part_series 다.

    돌려주는 것 — `t`(시간 축) + `parts`[part_id · part_name · internal_energy · kinetic_energy · peak_internal_energy ·
    peak_kinetic_energy · hourglass_energy(있으면)] · `note`. part_id 를 주면 그 파트만. matsum 이 없는 deep(런이 덤프하지 않았다)과
    sphere · impact 는 parts 가 비고 `note` 가 까닭을 말한다(오류가 아니다). 시계열을 통째로 주므로 파트가 많으면 응답이 크다 —
    필요한 파트만 골라 부른다."""
    params = {"part_id": part_id} if part_id is not None else None
    return await _get(ctx, f"/reports/{_seg(report_id)}/part-energy", params=params)


@mcp.tool(annotations=_READ)
async def report_angle_stats(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    metric: Annotated[str, Field(description="지표 — 리포트에 실린 파트 물리량 이름(예 peak_stress · peak_strain · peak_g · "
                                             "peak_disp). 기본 peak_stress. 실린 것은 응답의 available_metrics — 없는 것을 "
                                             "주면 groups 가 비고 note 가 말한다.")] = "peak_stress",
    part_id: Annotated[int | None, Field(description="파트 번호(LS-DYNA PID) — report_summary 의 parts[].part_id. 비우면 "
                                                     "케이스마다 파트 최댓값(작을수록 나쁜 지표는 최솟값)을 대표값으로 쓰고 "
                                                     "부품별 분해(parts)를 붙인다.")] = None,
    category: Annotated[str | None, Field(description="방향 범주로 고른다 — sphere 는 각도 범주(예 face · edge · corner), "
                                                      "impact 는 충격 면(F1 ~ F6). 정확히 같은 것만(report_directional 의 "
                                                      "directions[].category). near · angle_name 이 있으면 무시된다. "
                                                      "비우면 고르지 않는다.")] = None,
    angle_name: Annotated[str | None, Field(description="각도 이름(sphere) — 그 각도와 같은 26 정준 방향에 묶인 케이스들을 "
                                                        "고른다(report_case 의 identity.angle.name). near_lon · near_lat 이 "
                                                        "있으면 무시된다. 비우면 고르지 않는다.")] = None,
    near_lon: Annotated[float | None, Field(description="콘 중심 경도(도, sphere) — 리포트 각도의 등장방형 투영 경도"
                                                        "(-180 ~ 180). near_lat 과 둘 다 있어야 콘으로 고른다.")] = None,
    near_lat: Annotated[float | None, Field(description="콘 중심 위도(도, sphere, -90 ~ 90). near_lon 과 둘 다 있어야 "
                                                        "콘으로 고른다.")] = None,
    tol_deg: Annotated[float, Field(ge=0, le=REPORT_ANGLE_TOL_MAX_DEG,
                                    description=f"콘 반경(대원거리, 도, 0~{REPORT_ANGLE_TOL_MAX_DEG}) · 기본 15. near_lon · "
                                                "near_lat 을 줄 때만 쓴다.")] = 15.0,
    top_parts: Annotated[int, Field(ge=1, le=REPORT_TOP_PARTS_MAX,
                                    description=f"부품별 분해(parts.top_risk · most_sensitive)의 상위 몇 개"
                                                f"(1~{REPORT_TOP_PARTS_MAX}) · 기본 5. part_id 를 주면 쓰지 않는다.")] = 5,
) -> ReportAngleStatsOut:
    """고른 각도군의 표준 통계(분포 + 부품별 분해)를 낸다 — 모든 그룹이 같은 꼴이라 그룹끼리 견줄 수 있다.

    각도군 고르기(앞이 이긴다): near_lon + near_lat(그 방향 둘레 tol_deg 콘, sphere) > angle_name(그 각도와 같은 26 정준 방향에 묶인
    섭동 구름, sphere) > category(sphere 면 · 엣지 · 코너 / impact 면) > 비우면 전체(sphere 는 정준 방향별, 그 밖은 범주별).
    「이 방향 근처의 평균 · 산포는」 「이 각도군에서 어느 부품이 가장 위험 · 민감한가」 에 쓴다. 개별 값은 report_query, 26 방향 산포만은
    report_scatter, 캠페인의 런을 모은 각도 통계는 campaign_angle_stats 다.

    돌려주는 것 — `groups`[group_key · category · representative · stats{n · mean · std(표본) · cov · min · p05 · p25 · median · p75 ·
    p95 · max · iqr · range} · worst{value · angle_name · part_id · part_name · case_key} · (part_id 를 비웠을 때) parts{top_risk ·
    most_sensitive}] + selection · n_cases_total · n_groups · available_metrics · note. 작을수록 나쁜 지표(safety_factor · min_*)는
    worst 가 최솟값이다. sphere 전용 고르기를 다른 리포트에 주면 groups 가 비고 note 가 말한다."""
    params: dict = {"metric": metric, "tol_deg": tol_deg, "top_parts": top_parts}
    for k, v in (("part_id", part_id), ("category", category), ("angle_name", angle_name),
                 ("near_lon", near_lon), ("near_lat", near_lat)):
        if v is not None:
            params[k] = v
    return await _get(ctx, f"/reports/{_seg(report_id)}/angle-stats", params=params)


@mcp.tool(annotations=_READ)
async def report_energy_flow(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context,
    case_key: Annotated[str | None, Field(description="케이스 열쇠(sphere 는 각도 폴더 · impact 는 위치 id) — "
                                                      "report_worst_cases 의 case_key. 비우면(빈 글 포함) 상세가 실린 첫 "
                                                      "케이스. deep 은 보지 않는다.")] = None,
) -> ReportEnergyFlowOut:
    """에너지 · 접촉 상세를 원본 리포트에서 다시 읽어 준다 — deep 은 에너지 밸런스 · 접촉력, sphere · impact 는 한 케이스의 하중경로 그래프다.

    deep — `energy_balance`(energy_ratio 최소 · 최대 · 질량 추가 · 정상 종료) · `energy_series`(t · total · kinetic · internal ·
    hourglass · energy_ratio) · `contacts`(rcforc 접촉별 최대 힘, 큰 순) · `contact_metrics` · `has_matsum`. case_key 는 보지 않는다.
    sphere · impact — `energy_flow`(nodes 파트별 에너지 · edges 접촉마다 peak_force · total_work · total_impulse · confidence ·
    propagation_order) · `flow_case_key`(실제로 쓴 케이스) · `n_flows`. case_key 를 비우면 첫 케이스를 쓰고 flow_case_key 로 알린다.
    상세는 생성기가 상위 각도(위치)에만 싣는다 — 없는 케이스를 물으면 다른 케이스로 떨어지지 않고 energy_flow:null 과
    `detail_note` · `available_case_keys`(200 개까지) · `note` 가 온다. HTML 압축본이면 빠진 칸(원해상도 피크 등)을
    `energy_flow.form_note` 가 말한다.

    전 각도의 파트쌍 접촉력은 report_contact_profile, 파트별 에너지 시간이력은 report_part_energy 다."""
    params = {"case_key": case_key} if case_key else None
    return await _get(ctx, f"/reports/{_seg(report_id)}/energy", params=params)


@mcp.tool(annotations=_READ)
async def report_geometry(report_id: Annotated[str, Field(description=_A_REPORT_ID)], ctx: Context) -> ReportGeometryOut:
    """부품의 공간 배치를 준다 — impact 리포트의 디바이스 외곽선 · 파트별 XY footprint 다각형 · z 범위다.

    「부품이 어디 있나」 「충격 위치가 어느 부품 위인가」 를 좌표로 볼 때 쓴다. sphere · deep 은 각도 기반이라 부품 형상이 원본 렌더에만
    있어 device_outline · device_bbox 가 null 이고 parts 가 빈다. 그림으로 보려면 report_media · report_image, 뜨거운 자리의 좌표는
    report_hotspots 다.

    ⚠ footprint 가 지어낸 것일 수 있다. 상류 생성기는 실제 형상이 없는 파트에 파트 id 해시로 사각형을 지어내고 표시를 단다. 응답의
    `footprints_are_measured`(모두 실제 형상이면 true) · `synthetic_footprints`(지어낸 파트 수) · 파트별 `synthetic_footprint` ·
    `footprint_warning` 을 먼저 보라 — 지어낸 footprint 를 부품 위치 · 크기로 쓰면 안 된다. zmin · zmax 도 비어 있을 수 있다.

    돌려주는 것 — kind · device_outline · device_bbox · parts[part_id · name · group · footprint · synthetic_footprint · zmin · zmax]
    · 위 요약 칸."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/geometry")


@mcp.tool(annotations=_READ)
async def report_part_series(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    case_key: Annotated[str, Field(description="케이스 열쇠 — report_worst_cases 의 case_key"
                                               "(sphere 는 각도 폴더 · impact 는 위치 id · deep 은 그 한 건 — deep 은 "
                                               "값을 보지 않는다).")],
    part_id: Annotated[int, Field(description="파트 번호(LS-DYNA PID) — report_summary 의 parts[].part_id.")],
    ctx: Context,
) -> ReportPartSeriesOut:
    """한 케이스 · 한 파트의 시간이력을 준다 — 원본 리포트를 다시 읽어, 생성기가 솎아 실은 응력 · 변형률 · G · 변위 시계열이다.

    「최악 케이스에서 이 파트의 응력이 언제 · 어떻게 올라갔나」 를 볼 때 쓴다. case_key 는 report_worst_cases · report_query 에서,
    part_id 는 report_summary · report_part_risk 에서 얻는다. 피크 값만 필요하면 report_case · report_query, 파트별 에너지 시간이력은
    report_part_energy 다.

    돌려주는 것(kind 마다 다르다) —
    - deep: 실린 블록(stress · strain · vm_strain · max_principal · min_principal · max_principal_strain · min_principal_strain)마다
      {물리량: {t · max · avg · global_max · global_min · time_of_max · unit}}, `series_blocks`(실린 블록 이름),
      `motion`(t · disp_mag · vel_mag · acc_mag). deep 은 단건이라 case_key 를 보지 않는다.
    - sphere: stress_ts · strain_ts · g_ts · disp_ts · acc_ts(g_ts · disp_ts 에는 max 별칭을 얹는다).
    - impact: stress_ts.
    케이스 · 파트를 못 찾으면 `note` 가 온다(오류가 아니다)."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/cases/{_seg(case_key)}/series", params={"part_id": part_id})


@mcp.tool(annotations=_READ)
async def report_findings(
    report_id: Annotated[str, Field(description=_A_REPORT_ID)],
    ctx: Context,
    severity: Annotated[str | None, Field(description=f"심각도 — {_one_of(SEVERITIES)} 중 하나. 그 심각도와 **같은** "
                                                      "소견만(대소문자 무시). 비우면 모두.")] = None,
) -> list[ReportFindingRow]:
    """리포트의 위험 소견(자동 판정 — 항복 초과 · 과도한 G 등)을 목록으로 준다. severity 로 그 심각도만 고를 수 있다.

    리포트 하나의 소견을 읽을 때 쓴다(sphere · impact — deep 리포트는 소견이 없어 빈 목록이다). 여러 리포트에서 「CRITICAL 소견이 있는
    리포트」 를 찾으려면 find_reports 의 severity, 소견이 가리키는 파트 · 케이스의 값은 report_part_risk · report_query, 해석
    온톨로지(CAE) 꾸러미의 판정은 report_cae 다.

    돌려주는 것 — 행 목록 [severity(CRITICAL · WARNING · INFO) · title · detail · recommendation · peak_provenance]. 생성기가 실은
    순서 그대로이고 자르지 않는다. 0 건이면 빈 목록이다. 캠페인 런에서 온 리포트면 행마다 peak_provenance 에 피크 출처가 있다."""
    params = {"severity": severity} if severity else None
    return await _get(ctx, f"/reports/{_seg(report_id)}/findings", params=params)


@mcp.tool(annotations=_READ)
async def compare_reports(
    report_ids: Annotated[list, Field(description="비교할 리포트 id 목록(둘 이상) — find_reports 의 items[].id. 같은 kind "
                                                  "끼리라야 뜻이 있다.")],
    ctx: Context,
    part_id: Annotated[int | None, Field(description=_A_PART_ID_OPT)] = None,
) -> CompareReportsOut:
    """여러 리포트(개정 · 조건)를 파트별 최악 응력 · 최소 안전율로 나란히 놓는다 — 리포트마다 report_part_risk 를 불러 파트 번호로 맞춘다.

    「개정 A 와 B 에서 같은 파트의 최악 응력이 어떻게 달라졌나」 를 물을 때 쓴다. 같은 kind 끼리라야 뜻이 있다(sphere ↔ sphere,
    impact ↔ impact) — kind 가 섞이면 `note` 가 경고한다. 한 리포트 안의 케이스를 그림과 함께 견주려면 report_compare, 캠페인끼리는
    compare_campaigns, 한 과제의 개정끼리는 compare_task_revisions 다.

    돌려주는 것 — `kinds`{리포트 id: kind} · `note` · `parts`[part_id · part_name · by_report{리포트 id: {worst_stress(MPa) ·
    worst_stress_case · min_safety_factor}}](part_id 글자 순). 어느 리포트에 없는 파트는 그 리포트 칸이 없다. report_ids 는 둘
    이상이어야 한다 — 상한은 없지만 리포트마다 백엔드를 두 번 부르고 모두 도구 호출 한 번의 시간 한도 안이어야 한다."""
    if not report_ids or len(report_ids) < 2:
        raise RuntimeError("비교하려면 report_ids 가 2개 이상이어야 합니다.")
    rows = {}
    kinds = {}
    for rid in report_ids:
        summ = await _get(ctx, f"/reports/{_seg(rid)}")
        kinds[rid] = summ.get("kind")
        pr = await _get(ctx, f"/reports/{_seg(rid)}/parts",
                        params={"part_id": part_id} if part_id is not None else None)
        for p in pr.get("parts", []):
            key = p.get("part_id")
            slot = rows.setdefault(key, {"part_id": key, "part_name": p.get("part_name"), "by_report": {}})
            slot["by_report"][rid] = {
                "worst_stress": p.get("worst_stress", {}).get("value"),
                "worst_stress_case": p.get("worst_stress", {}).get("case_key"),
                "min_safety_factor": p.get("min_safety_factor"),
            }
    if len(set(kinds.values())) > 1:
        note = f"⚠ 서로 다른 kind 비교({kinds}) — 물리적으로 다른 시험일 수 있습니다."
    else:
        note = None
    return {"kinds": kinds, "note": note, "parts": sorted(rows.values(), key=lambda r: str(r["part_id"]))}


@mcp.tool(annotations=_ADD_OUT)
async def publish_report_to_datahub(
    report_id: Annotated[str, Field(description=_A_REPORT_ID + " 내가 소유한 리포트만.")],
    project: Annotated[str, Field(description="과제코드(64자까지) — 레코드의 project. 빈 글이면 리포트 메타의 과제"
                                              "(update_report_meta 로 적은 값)를 쓰고, 그것도 없으면 오류.")],
    stage: Annotated[Literal[DATAHUB_STAGES], Field(description="개발 단계 코드 — " + _one_of(s for s in DATAHUB_STAGES if s)
                                                                + " 중 하나(dv · pv 는 차수 1 · 2 · 3 · r 필수, pre · pra · mp "
                                                                "는 차수 없음). 빈 글이면 리포트 메타의 개발 단계를 쓰고, 그것도 "
                                                                "없으면 오류.")],
    ctx: Context,
    variation: Annotated[str | None, Field(description="설계안 — 비우면 리포트 메타의 설계안.")] = None,
    doe: Annotated[str | None, Field(description="DOE 참조 — `study` 또는 `study:case`. 비우면 리포트 메타의 DOE.")] = None,
    unit: Annotated[str, Field(description="단위계 표지(자유 글) — 첨부 설명 · 첨부 extra 의 unit_system 에 그대로 싣는다"
                                           "(값을 바꾸지 않는다). 기본 mm-t-s.")] = "mm-t-s",
    title: Annotated[str | None, Field(description="레코드 제목 — 비우면 `<과제> <단계> — <리포트 과제명 또는 kind> <kind> "
                                                   "리포트`.")] = None,
) -> PublishReportToDatahubOut:
    """리포트를 AI Data Hub 에 범용 sim_report 레코드로 등재한다 — DynaForge 밖(DataHub)에 새 레코드를 만든다.

    리포트를 과제 · 개발 단계에 엮어 사내 검색 · 개정 비교에 올릴 때 쓴다. 리포트 소유자만 부를 수 있다(공유로 읽는 리포트는 404).
    ★부를 때마다 새 레코드 id(SIM-…)를 받는다 — 같은 리포트를 다시 등재하면 덮지 않고 레코드가 하나 더 생긴다. 과제 · 개발 단계를
    리포트 메타에 먼저 적어 두려면 update_report_meta(그러면 project · stage 를 빈 글로 줘도 그 값을 쓴다).

    싣는 것 — 리포트 요약 · 소견 · 최악 케이스 상위 5 · 파트 · sim_params 를 content 로, 원본 리포트 HTML 을 첨부로. deep · sphere
    리포트에 핫스팟이 있으면 그 요약(sphere=포락 상위 10 · deep=군집 상위 10 — report_hotspots 와 같은 계산)도
    content.outputs.hotspots 에 싣는다(저장만 — 검색 칸은 아니다). 원본 HTML 이 없거나 DataHub 주소가 설정되지 않았거나 과제 ·
    단계를 못 정하면 오류(400), DataHub 가 거절하면 502 다.

    돌려주는 것 — record_id · data_type(SIM) · doc_type(sim_report) · sim_domain · report_kind · view(레코드 주소)."""
    body = {"project": project, "stage": stage, "unit": unit}
    if variation:
        body["variation"] = variation
    if doe:
        body["doe"] = doe
    if title:
        body["title"] = title
    return await _post(ctx, f"/reports/{_seg(report_id)}/publish-datahub", body)


@mcp.tool(annotations=_DELETE)
async def delete_report(
    report_id: Annotated[str, Field(description="지울 리포트 id — find_reports 의 items[].id(내가 소유한 것만).")],
    ctx: Context,
) -> DeleteReportOut:
    """인제스트된 리포트를 지운다 — 되돌릴 수 없다.

    리포트 행과 그 케이스 · 원본 리포트 HTML · 조건(scenario) 파일 · 해석 온톨로지 꾸러미 파일을 함께 지운다. K파일은 모델 자산이라
    남긴다(다른 리포트가 쓸 수 있다). DataHub 에 등재한 레코드는 지우지 않는다. 리포트 소유자만 지울 수 있다(공유로 읽는 리포트는
    404). 개정 연결만 끊으려면 unlink_report_revision, 메타만 고치려면 update_report_meta 다.

    돌려주는 것 — message(지웠다는 글). 이미 지운 리포트를 다시 부르면 404 오류다."""
    return await _delete(ctx, f"/reports/{_seg(report_id)}")


# ── 과제 · 개발 개정 (온톨로지) ──────────────────────────────────────
# 과제의 정본은 **허브**다 — 여기에 과제를 만들거나 고치는 도구는 **없다**(있으면 다음 받기가
# 덮어쓰고 그 사실이 고친 사람에게 안 보인다). 쓰는 것은 **우리 것**(개정)뿐이다.

# 과제 · 개정 · 레시피 도구(list_tasks ~ recipe_deprecate)의 허용값 · 상한 · 결과 꼴(계약 C3 · C4 · C7) — 허용값 · 상한은 백엔드 라우트의 제약과 같다.
ONTO_STATES = ("all", "active", "deprecated", "inactive")       # GET /ontology/objects 의 state — 이 밖은 백엔드가 422 로 거절한다
TASK_LIMIT_MAX = 1000                                           # GET /ontology/tasks 의 limit(ge=1)
ONTO_FIND_LIMIT_MAX = 1000                                      # GET /ontology/objects 의 limit(ge=1) · offset(ge=0)
TASK_LINKS_LIMIT_MAX = 2000                                     # GET /ontology/task-links 의 limit(ge=1 — 0 이하는 MCP 가 싣지 않는다)
RECIPE_SEARCH_LIMIT_MAX = 200                                   # GET /recipes 의 limit(ge=1)
RECIPE_RUN_REPORTS_MAX = 32                                     # POST /recipes/{name}/run 의 report_ids(1개 이상)
RECIPE_NOTE_MIN = 20                                            # 등록 근거가 되는 평가 글의 최소 글자 수
# 개정 코드 — 설명에만 쓴다(enum 이 아니다 — 백엔드는 앞뒤 공백을 떼고 받는다). dv · pv 는 차수(1 · 2 · 3 · r) 필수, pre · pra · mp 는 차수 없음.
REVISION_CODES = ("pre", "dv1", "dv2", "dv3", "dvr", "pv1", "pv2", "pv3", "pvr", "pra", "mp")

_A_TASK_KEY = ("과제명(허브 plm_task 의 key) — list_tasks 의 items[].key. 과제코드가 아니다(과제코드면 list_tasks 의 q 로 과제명을 "
               "먼저 찾는다). '/' 가 들어도 된다.")
_A_OWN_REPORT_ID = _A_REPORT_ID + " 내 리포트여야 한다(남의 리포트는 404)."
_A_RECIPE_NAME = "레시피 이름(소문자 · 숫자 · 밑줄) — recipe_search 의 name."

ListTasksOut = _shape("ListTasksOut", {
    "items": "과제 — key(과제명) · label · status(deprecated 면 그만 씀) · deleted · properties(task_code · project · aliases …) · "
             "updated_at, 검색했으면 matched_by · match_kind, 별칭으로 걸렸으면 matched_alias · alias_source",
    "total": "q 로 걸린 전체 수 — q 가 있을 때만 온다",
    "truncated": "limit 에서 잘렸으면 true",
    "sync_enabled": "허브 수신이 켜져 있나",
    "last_status": "과제 타입의 마지막 받기 상태",
    "last_error": "허브가 준 오류 원문 — 시스템 관리자에게만(그 밖에는 null)",
    "last_run_at": "과제 타입을 마지막으로 받은 때",
    "reason": "목록이 비었을 때의 까닭(수신 꺼짐 · 받았지만 없음) — 비지 않았으면 null",
})
TaskRevisionsOut = _shape("TaskRevisionsOut", {
    "task": "물은 과제명",
    "task_found": "거울에 있는 과제거나 개정이 있으면 true — false 면 모르는 과제",
    "revisions": "판(rev_seq 순) — key(<과제명>@<code>) · code · phase · round · rev_seq · rev_source · status · decided_by · "
                 "decided_at · model · supersedes(앞 판 key) · reports(읽을 수 있는 리포트 id)",
    "scope": "all(시스템 관리자 — 리포트 전부) · readable(읽을 수 있는 리포트만)",
    "reason": "unknown_task — task_found 가 false 일 때만",
    "hint": "모르는 과제일 때 다음 할 일",
})
ReportRevisionOut = _shape("ReportRevisionOut", {
    "report_id": "리포트 id",
    "eng_meta": "수동 메타(project · dev_revision …)",
    "free_task": "리포트가 말하는 과제 이름(수동 메타의 project, 없으면 리포트에 박힌 이름)",
    "resolved_task": "그 이름이 지금 풀리는 과제명 — 못 풀면 null",
    "resolved_how": "어떻게 풀렸나 — exact · task_code · previous_key · alias · hub_alias",
    "linked": "이어진 판 {key, task, code, source(manual · rule · eng_meta · null)} — 없으면 null",
    "unlinked": "사람이 끊은 기록 {by, at, was} — 없으면 null",
    "task_state": "그 과제의 허브 처지 {key, state(active · deprecated · merged · gone · hidden · renamed · unknown), into …} — 과제가 "
                  "없으면 null",
    "mismatch": "수동 메타와 이어진 판의 어긋남 {kind(differs · renamed · merged · eng_meta_missing), linked, eng_meta, said} — 없으면 null",
    "candidates": "개정 코드 후보 — code · source · evidence · valid(false 면 why) · phase · round · rev_seq",
    "task_candidates": "과제가 하나로 안 풀렸을 때의 과제 후보와 근거",
    "ambiguous": "글자 그대로 맞는 과제가 둘 이상이면 true(잇지 않았다)",
    "alias_missing": "끝(과제)이 거울에 없는 사람의 별칭이 가리키는 key — 없으면 null",
})
SetReportRevisionOut = _shape("SetReportRevisionOut", {
    "ok": "확정했으면 true",
    "key": "확정한 판 key(<과제명>@<code>)",
    "rev_seq": "판 차례 번호(단계 × 10 + 차수)",
    "task_unverified": "과제 거울에 그 과제가 없어 확인하지 못했으면 true",
    "detail": "덧붙임 글",
    "task_resolved": "적은 과제를 어떻게 풀었나 {input, key, how(exact · task_code · previous_key · alias · hub_alias · verbatim)}",
})
OntologySyncStateOut = _shape("OntologySyncStateOut", {
    "enabled": "허브 수신이 켜져 있나",
    "receive_types": "받을 타입 — null 이면 공개된 것 전부",
    "types": "타입 줄 — type_slug · objects_as_of · relations_as_of · catalog_revision · last_run_at · last_status · last_error(관리자만) · "
             "objects · stopped · stopped_why",
    "stopped_types": "멈춘 타입 slug",
    "problems": "지금 상태에서 본 문제(멈춘 타입 등) — 사람이 읽는 줄",
    "objects_by_type": "타입별 객체 수",
    "object_states": "타입별 {total, active, deprecated, inactive, hidden}",
    "last_run": "마지막 받기 실행 — id · started_at · finished_at · mode · trigger · result · revision · counts · problem_count · notes · "
                "problems · error — 없으면 null",
    "catalog": "마지막 허브 카탈로그 {revision, received_at, system, types(타입 수)} — 없으면 null",
    "full_every_days": "처음부터 다시 받는 주기(일)",
    "merged_waiting": "관리자가 옮기기를 기다리는 합쳐진 과제 수",
})
OntologyTypesOut = _shape("OntologyTypesOut", {
    "types": "타입 — slug · label · description · source(hub · dynaforge · null) · catalog_revision · properties(칸) · relations · "
             "counts{total, active, deprecated, inactive, hidden}",
    "relation_types": "관계 종류 — slug · label · inverse_label · src · dst · source",
})
OntologyFindOut = _shape("OntologyFindOut", {
    "type": "물은 타입 slug",
    "total": "거른 전체 수(페이지와 무관)",
    "offset": "이 페이지의 시작 위치",
    "items": "객체(key 순) — type · key · label · status · active(false 면 사라짐) · hidden · merged_into · source · updated_at · synced_at",
})
OntologyObjectOut = _shape("OntologyObjectOut", {
    "object": "객체 — type · key · label · status · active · hidden · merged_into · source · properties(칸) · previous_keys. 옛 식별자로 "
              "물었으면 null",
    "renamed_to": "옛 식별자로 물었을 때만 — 지금 key",
    "merged_into_now": "합쳐진 객체면 바뀜 · 합침을 끝까지 푼 지금 key — 아니면 null",
    "out": "나가는 선(지금 이어진 것) — relation · type · key · label · source · evidence_note · updated_at",
    "in": "들어오는 선(지금 이어진 것) — out 과 같은 꼴",
    "previous": "옛 식별자",
    "scope": "all(시스템 관리자) · readable(끝이 리포트인 선은 읽을 수 있는 것만)",
})
PlanTaskLinksOut = _shape("PlanTaskLinksOut", {
    "scope": "all(시스템 관리자 — 리포트 전부) · readable(읽을 수 있는 리포트만)",
    "counts": "reports · reports_without_a_name · strings(자유 문자열 전체 수) · links · proposal · unmatched(판정한 문자열 기준) · unlinked",
    "plan": "자유 문자열별 판정(문자열 정렬 순) — free · reports · n_reports · codes · task_key · how · verdict(links · proposal · "
            "unmatched) · candidates · ambiguous · alias_missing · unlinked",
    "reports_without_a_name": "과제 이름조차 없는 리포트 id",
})
CompareTaskRevisionsOut = _shape("CompareTaskRevisionsOut", {
    "task": "물은 과제명",
    "task_found": "거울에 있는 과제거나 개정이 있으면 true",
    "revisions": "판(rev_seq 순) — 개정 줄 칸 + n_reports · worst_stress(MPa) · worst_g(G) · max_severity · n_cases · measured_from · "
                 "missing_reports · d_worst_stress(앞 판 대비 — 한쪽이라도 없으면 null)",
    "scope": "all(시스템 관리자) · readable(읽을 수 있는 리포트만으로 셌다)",
    "note": "과제는 있으나 개정이 없을 때의 글",
    "reason": "unknown_task — 모르는 과제일 때만",
    "hint": "모르는 과제일 때 다음 할 일",
})
UnlinkReportRevisionOut = _shape("UnlinkReportRevisionOut", {
    "ok": "끊었으면 true",
    "was": "끊은 개정 key",
    "unlinked_by": "끊은 사람",
    "unlinked_at": "끊은 때",
    "detail": "덧붙임 글",
})
ClearReportUnlinkOut = _shape("ClearReportUnlinkOut", {
    "ok": "지웠으면 true",
    "was": "기록에 있던 개정 key",
    "detail": "덧붙임 글",
    "task_links": "지운 뒤 이 리포트 하나에 돈 자동 잇기 결과 — 기능 꺼짐 · 잠금이면 skipped(off · busy), 실패면 error",
})
ConfirmTaskAliasOut = _shape("ConfirmTaskAliasOut", {
    "ok": "붙였으면 true",
    "alias": "붙인 자유 문자열(앞뒤 공백을 뗀 것)",
    "key": "가리키는 과제명",
})
RemoveTaskAliasOut = _shape("RemoveTaskAliasOut", {
    "ok": "뗐으면 true",
    "alias": "뗀 자유 문자열",
    "was": "가리키던 과제명",
    "detail": "덧붙임 글",
})
RecipeSearchRow = _shape("RecipeSearchRow", {
    "name": "레시피 이름",
    "domain": "영역(report)",
    "registered": "등록 판이 있으면 true",
    "current_version": "등록 판 번호 — 없으면 null",
    "meta": "title · question · when_to_use · kinds · needs · inputs · params · tags",
    "useful_count": "등록 판에 붙은 '쓸모 있었다' 평가 수",
    "has_draft": "내가 올린 초안 · 후보가 있으면 true",
})
RecipeGetOut = _shape("RecipeGetOut", {
    "name": "레시피 이름",
    "domain": "영역(report)",
    "origin": "platform(이 플랫폼에서 올림) · git(씨앗 · 내보낸 파일에서 읽음)",
    "current_version": "등록 판 번호 — 없으면 null",
    "deprecated_at": "내린 때 — 안 내렸으면 null",
    "deprecated_reason": "내린 까닭",
    "versions": "판(새 것부터) — version · status(draft · candidate · registered · superseded) · meta · checks · gate · code(볼 수 없으면 "
                "null) · created_at · registered_at",
})
RecipeRunOut = _shape("RecipeRunOut", {
    "run_id": "실행 id — recipe_evaluate 에 넣는다",
    "job_id": "플랫폼 잡 id — get_job 으로 본다",
    "status": "queued · running · succeeded · failed",
    "result": "run() 이 돌려준 값 — 크면 안내만",
    "result_truncated": "결과가 커서 result 에 싣지 않았으면 true(전체는 산출 파일)",
    "output_file_id": "결과 전체가 든 세션 산출 파일 id(download_result)",
    "error": "실패 까닭 — 성공이면 null",
    "sandbox": "샌드박스 층 정보",
    "elapsed_ms": "실행 시간(ms)",
    "hint": "다음 할 일",
})
RecipeProposeOut = _shape("RecipeProposeOut", {
    "name": "레시피 이름",
    "version": "새 판 번호",
    "status": "candidate(자기 시험 통과) · draft(실패)",
    "checks": "static_ok · tests · selftest_ok · tests_passed · compat_base · compat_ok · layers · error · stdout_tail",
    "message": "다음 할 일 · 실패 까닭",
    "similar": "비슷한 레시피 이름(최대 5)",
})
RecipeEvaluateOut = _shape("RecipeEvaluateOut", {
    "run_id": "실행 id",
    "useful": "남긴 평가",
    "note": "남긴 글(최대 2000자)",
})
RecipeRegisterOut = _shape("RecipeRegisterOut", {
    "name": "레시피 이름",
    "version": "등록한 판 번호",
    "status": "registered",
    "superseded": "물러난 앞 등록 판 번호 — 없으면 null",
    "exported": "내보낸 recipe.json 경로 — 내보내기에 실패했으면 null",
    "message": "덧붙임 글",
})
RecipeDeprecateOut = _shape("RecipeDeprecateOut", {
    "name": "레시피 이름",
    "deprecated": "내렸으면 true",
    "reason": "남긴 까닭",
})


@mcp.tool(annotations=_READ)
async def list_tasks(
    ctx: Context,
    q: Annotated[str, Field(description="검색어 — 과제명(key) · 과제코드(properties.task_code) · 별칭(허브 · 이 플랫폼) · 이름(label)의 "
                                        "일부(대소문자 무시). 비우면 거르지 않고 과제명 순이다.")] = "",
    limit: Annotated[int, Field(ge=1, le=TASK_LIMIT_MAX,
                                description=f"돌려줄 최대 과제 수(1~{TASK_LIMIT_MAX}). 기본 100. 넘치면 순위대로 앞에서 자르고 "
                                            "truncated:true.")] = 100,
    project: Annotated[str, Field(description="프로젝트 — 허브 칸 properties.project 와 글자 그대로 같은 과제만. "
                                              "비우면 모든 프로젝트.")] = "",
) -> ListTasksOut:
    """허브에서 받은 과제(plm_task) 거울을 과제명 · 과제코드 · 별칭 · 이름으로 찾는다.

    과제명(key)을 모를 때 먼저 쓴다 — task_revisions · compare_task_revisions · set_report_revision · confirm_task_alias 에 넣을
    과제명을 여기서 얻는다. 과제가 아닌 받은 타입은 ontology_find.
    검색은 순위를 매긴 뒤 자른다 — 앞부분(prefix) · 낱말 경계(word) · 부분(substring) 순이고, 같은 꼴이면 과제명 · 과제코드 · 별칭 ·
    이름 순이다. 항목마다 `matched_by`(task_name · task_code · alias · label) · `match_kind` 가 오고, 별칭으로 걸렸으면
    `matched_alias` · `alias_source`(hub · dynaforge)도 온다. 허브에서 사라진 과제는 빠진다.
    돌려주는 것 — `items` · `truncated`(limit 에서 잘렸나) · `total`(q 가 있을 때 걸린 전체 수) · 수신 상태(`sync_enabled` ·
    `last_status` · `last_run_at`). 페이지는 없다 — 잘렸으면 q · project 로 좁힌다.
    ★`status:"deprecated"` 는 허브가 그만 쓰라고 한 과제다 — 새로 붙일 때 고르지 마라(이미 이은 것은 그대로다).
    ★목록이 비면 `reason` 을 본다 — 수신이 꺼진 것과 받았지만 없는 것은 다르다. `last_error`(허브 오류 원문)는 시스템 관리자에게만
    오고 그 밖에는 null 이다. 과제·개정 기능이 꺼진 박스는 거절한다(HTTP 409 — 까닭이 문구에 있다)."""
    params: dict = {"limit": limit}
    if q:
        params["q"] = q      # ★빈 값을 None 으로 실으면 httpx 가 `q=` 를 보낸다 — 키를 뺀다
    if project:
        params["project"] = project
    return await _get(ctx, "/ontology/tasks", params)


@mcp.tool(annotations=_READ)
async def task_revisions(task_key: Annotated[str, Field(description=_A_TASK_KEY)], ctx: Context) -> TaskRevisionsOut:
    """한 과제의 개발 개정 줄을 rev_seq 순으로 준다 — 판마다 달린 리포트 id 와 앞 판(supersedes).

    판마다 리포트 id 를 얻을 때 쓴다. 판끼리 수치(최악 응력 · G · 심각도)를 나란히 보려면 compare_task_revisions, 리포트 하나가
    어느 판인지는 report_revision 이다. 판끼리 리포트를 파트별로 견주려면 여기서 얻은 id 를 compare_reports 로 넘긴다.
    돌려주는 것 — `task` · `task_found` · `revisions[]`(key `<과제명>@<code>` · code · phase · round · rev_seq · rev_source(manual 이면
    사람이 확정한 판) · decided_by · decided_at · model · supersedes · reports) · `scope`. 상한 · 페이지 없이 전부 온다.
    ★`task_found:false`(reason `unknown_task`)면 정본에 그 과제가 없다 — 개정이 0 인 것과 다르다. 과제코드를 넣었을 수 있으니
    list_tasks 로 과제명을 먼저 찾는다.
    ★판은 다 보이지만 판마다 리포트는 읽을 수 있는 것(소유 · 같은 소속)만 온다 — `scope` 가 readable 이면 전사 수가 아니다(시스템
    관리자는 all)."""
    return await _get(ctx, f"/ontology/tasks/{_seg_key(task_key)}/revisions")


@mcp.tool(annotations=_READ)
async def report_revision(
    report_id: Annotated[str, Field(description=_A_OWN_REPORT_ID)],
    ctx: Context,
    task_key: Annotated[str, Field(description="개정 코드 후보를 볼 과제명 — 주면 그 과제의 허브 개발모델(plm_model) model_revision 도 "
                                               "후보 근거에 넣는다. 비우면 리포트의 이름이 풀리는 과제로 본다.")] = "",
) -> ReportRevisionOut:
    """리포트 하나가 어느 과제 · 개정에 이어져 있는지와 어긋남 · 후보와 근거 · 그 과제의 허브 처지를 함께 준다(리포트 소유자만).

    set_report_revision 으로 확정하기 전에 부른다 — 후보와 근거를 사람에게 보여 주고 고르게 한다. 과제의 판 줄 전체는 task_revisions.
    - `linked` — 이어진 판 `{key, task, code, source}`. source 는 선을 누가 이었나다 — `manual` 사람 · `rule` 기계(이름이 허브 과제
      하나로 풀림) · `eng_meta` 기계(허브가 모르는 이름을 수동 메타 글자 그대로) · null(누가 이었는지 적지 않던 옛 선). 이을 때 찍은
      표시라 지금 풀리는 과제와 다를 수 있다 — 지금 풀림은 `resolved_task` · `resolved_how`. 사람이 이은 선은 기계가 옮기지 않는다.
    - `mismatch` — 비어 있지 않으면 수동 메타(eng_meta)와 이어진 판이 다르다. 관계가 정본이지만 서버는 조용히 맞추지 않는다 — 사람에게
      보여 주고 고르게 한다. kind `renamed` · `merged` 는 잘못이 아니다(허브가 과제명을 바꿨거나 합쳤고 판이 옮겨졌다). 수동 메타의
      이름이 과제코드 · 별칭이어도 같은 판으로 풀리면 어긋남이 아니다.
    - `task_state.state` — active · deprecated(그만 씀) · merged(`into` 로 합쳐짐 — 옮기기는 시스템 관리자가 화면에서 누른다, 저절로
      옮기지 않는다) · gone(허브에서 사라짐) · hidden · renamed · unknown.
    - `candidates` — 개정 코드 후보와 근거(`valid:false` 도 버리지 않고 보인다). `ambiguous:true` 면 글자 그대로 맞는 과제가 둘 이상이라
      잇지 않았다(`task_candidates`). 그만 쓴 과제는 살아 있는 과제가 하나도 안 맞을 때만 센다.
    - `alias_missing` — 사람이 붙인 별칭의 끝(과제)이 거울에 없어 그 별칭으로는 잇지 않았다(remove_task_alias 로 떼고 다시 붙인다).
    - `unlinked` — 사람이 연결을 끊은 기록 `{by, at, was}` — 자동 잇기가 다시 잇지 않는다."""
    return await _get(ctx, f"/reports/{_seg(report_id)}/revision",
                      {"task_key": task_key} if task_key else None)


@mcp.tool(annotations=_SET)
async def set_report_revision(
    report_id: Annotated[str, Field(description=_A_OWN_REPORT_ID)],
    task_key: Annotated[str, Field(description="과제 — 과제명 · 과제코드 · 옛 과제명 · 별칭 어느 것이든(list_tasks 로 찾는다). 과제 "
                                               "하나로 풀려야 한다. 1~300자.")],
    code: Annotated[str, Field(description=f"개정 코드 — {_one_of(REVISION_CODES)} 가운데 하나(dv · pv 는 차수 1 · 2 · 3 · r 필수, "
                                           "pre · pra · mp 는 차수 없음).")],
    ctx: Context,
    model_key: Annotated[str, Field(description="허브 개발모델(plm_model) key — 판에 적는다. 비우면 바꾸지 않는다. 최대 300자.")] = "",
    supersedes: Annotated[str, Field(description="앞 판의 개정 key(<과제명>@<code> — task_revisions 의 revisions[].key). 비우면 앞 판을 "
                                                 "잇지 않는다. 자기 자신 · 순환은 거절된다. 최대 300자.")] = "",
    note: Annotated[str, Field(description="판에 남길 메모 — 비우면 바꾸지 않는다. 최대 2000자.")] = "",
) -> SetReportRevisionOut:
    """리포트를 과제의 한 개정에 확정한다 — 사람의 판정으로 기록되고 재인제스트에도 지워지지 않는다(리포트 소유자만).

    ★짐작으로 부르지 마라 — report_revision 의 후보와 근거를 사람에게 보여 주고 고른 값을 넣는다. 잘못 확정했으면
    unlink_report_revision 으로 끊는다. 이 리포트에 사람이 끊은 기록이 있으면 지운다.
    과제는 과제명 · 과제코드 · 옛 과제명 · 별칭 어느 것이든 된다 — 자동 잇기와 같은 규칙으로 과제 하나로 풀리면 그 과제명으로
    잇고(응답 `task_resolved`), 없거나 둘 이상이면 `task_unresolved` 로 거절한다(HTTP 400 · 후보를 함께 준다 · 아무것도 바꾸지
    않았다). 허브 거울에 과제가 하나도 없는 박스는 글자 그대로 잇는다(how `verbatim`).
    이미 다른 판에 이어져 있으면 이 판으로 옮긴다(리포트 하나에 판 하나). 그 판이 기계가 지은 판이면 거기 얹힌 다른 리포트의 옛
    선에 기계가 이었다고 먼저 적는다 — 그 리포트를 누가 고치는 중이면 `busy` 로 거절한다(HTTP 409 · 아무것도 바꾸지 않았다 · 잠시
    뒤 다시 부른다).
    돌려주는 것 — `key`(<과제명>@<code>) · `rev_seq` · `task_unverified`(과제 거울에 없어 확인 못 함) · `task_resolved`."""
    return await _put(ctx, f"/reports/{_seg(report_id)}/revision", {
        "task_key": task_key, "code": code, "model_key": model_key,
        "supersedes": supersedes, "note": note})


@mcp.tool(annotations=_READ)
async def ontology_sync_state(ctx: Context) -> OntologySyncStateOut:
    """허브 수신(받기) 상태를 준다 — 타입별 시계 · 마지막 실행 결과 · 정의 판 · 타입별 건수(로그인한 누구나 읽는다).

    '받기가 됐나' 는 여기서 본다. 받은 타입 정의는 ontology_types, 받은 과제는 list_tasks. 받기 실행 · 처음부터 · 강제 정리 · 합친
    과제 옮기기는 관리자 화면에만 있다(도구 없음).
    - `last_run.result` — `ok` 정상 · `needs_check` 확인 필요 · `failed` 실패. 사유 수는 `last_run.problem_count`, 알림 줄
      `last_run.notes` 는 누구나 본다(이름 바뀐 과제의 개정 옮기기를 미뤘으면 그 수).
    - 타입 줄 `types[]` — `last_status` 가 `skipped` 면 허브가 그 타입을 공개하지 않았다(고칠 곳은 허브 관리자). `stopped:true` 는
      멈춘 타입이다 — 받을 타입(`receive_types`, null 이면 공개된 것 전부) 밖이거나(`stopped_why` `not_in_list`) 허브 카탈로그에
      없어서(`not_published`) 더 받지 않는다. 그 줄의 상태 · 건수는 마지막으로 받았을 때 그대로다.
    - 맨 위 `problems` 는 지금 상태에서 본 문제다 — 비어 있지 않으면 `last_run.result` 가 `ok` 여도 다 받고 있는 것이 아니다. 받을
      타입을 넓히는 것은 박스 설정 KOORM_SP_CORE_TYPES 다.
    - `object_states` 는 타입별 활성 · 그만 씀 · 사용 안 함 건수, `merged_waiting` 은 관리자가 옮길 합쳐진 과제 수다.
    ★시스템 관리자에게만 오는 것 — 오류 원문(`last_run.problems` · `last_run.error` · 타입 줄의 `last_error`), 받기 뒤 과제 잇기
    결과 `last_run.counts.task_links`(리포트 전부를 센 것 — `skipped: off` 면 그때 과제·개정 기능이 꺼져 잇지 않았다), 층 2 반영의
    예외 · 못 옮긴 앞 판 줄 · 옮긴 리포트 수. 일반 사용자에게는 빈 목록 · null 이고 `last_run.counts.reflected` 에는 반영 수(renamed ·
    revisions · collapsed · aliases · models · merged_waiting · deferred)만 온다."""
    return await _get(ctx, "/ontology/sync")


@mcp.tool(annotations=_READ)
async def ontology_types(ctx: Context) -> OntologyTypesOut:
    """허브에서 받은 타입 정의(칸 · 관계)와 타입별 건수를 준다 — 우리 것(dev_revision)도 같은 표에 있다.

    ontology_find · ontology_object 의 type_slug 를 여기서 고른다(`types[].slug`). 과제(plm_task)를 찾을 때는 list_tasks 가 낫다.
    돌려주는 것 — `types[]`(slug · label · description · source(hub 허브 · dynaforge 우리 것 · null 정의 없이 행만 받은 타입) ·
    catalog_revision · properties(칸) · relations · counts) · `relation_types[]`(slug · label · inverse_label · src · dst · source).
    counts 는 total · active(활성) · deprecated(그만 씀) · inactive(사용 안 함 — 사라짐 · 합쳐짐) · hidden(그중 안 보이게 됨)이고,
    리포트에서 나온 행(cae_*)은 세지 않는다.
    ★읽기 전용이다 — 정본은 허브라 고치는 도구는 없다. 상한 · 페이지 없이 전부 온다."""
    return await _get(ctx, "/ontology/types")


@mcp.tool(annotations=_READ)
async def ontology_find(
    type_slug: Annotated[str, Field(description="타입 slug — ontology_types 의 types[].slug(예 plm_task · plm_model · dev_revision). "
                                                "모르는 타입이면 거절하지 않고 빈 목록이다. 1~80자.")],
    ctx: Context,
    q: Annotated[str, Field(description="key · 이름(label)의 일부(대소문자 무시). 비우면 거르지 않는다. 최대 200자.")] = "",
    state: Annotated[Literal[ONTO_STATES], Field(description="상태 거르개 — all(기본 · 전부) · active(활성) · deprecated(그만 씀) · "
                                                             "inactive(사용 안 함 — 사라짐 · 합쳐짐).")] = "all",
    limit: Annotated[int, Field(ge=1, le=ONTO_FIND_LIMIT_MAX,
                                description=f"한 페이지의 최대 객체 수(1~{ONTO_FIND_LIMIT_MAX}). 기본 100.")] = 100,
    offset: Annotated[int, Field(ge=0, description="건너뛸 객체 수(0 이상) — 다음 페이지는 앞 offset + 받은 수. 기본 0(처음부터).")] = 0,
) -> OntologyFindOut:
    """받은 한 타입의 객체를 key · 이름 일부로 찾는다 — 페이지(limit · offset)로 넘긴다.

    type_slug 는 ontology_types 의 slug 다. 과제는 list_tasks 가 낫다(과제코드 · 별칭 · 순위). 객체 하나의 칸 · 선은 ontology_object.
    돌려주는 것 — `type` · `total`(거른 전체 수) · `offset` · `items[]`(type · key · label · status · active · hidden · merged_into ·
    source · updated_at · synced_at). key 순이다.
    ★사라진 것도 지우지 않았다 — `active:false` 로 함께 온다(합쳐졌으면 `merged_into`). `state` 로 거른다.
    ★`offset + items 수` 가 `total` 보다 작으면 더 있다 — 다음 페이지를 부른다. 리포트에서 나온 행(cae_*)은 여기 오지 않는다."""
    params: dict = {"type": type_slug, "state": state, "limit": limit, "offset": offset}
    if q:
        params["q"] = q      # 빈 값을 실으면 `q=` 가 간다 — 키를 뺀다
    return await _get(ctx, "/ontology/objects", params)


@mcp.tool(annotations=_READ)
async def ontology_object(
    type_slug: Annotated[str, Field(description="타입 slug — ontology_types 의 types[].slug(예 plm_task). '/' 는 쓸 수 없다.")],
    key: Annotated[str, Field(description="객체 key — ontology_find 의 items[].key(과제면 과제명). '/' 가 들어도 된다. 허브가 바꾼 "
                                          "옛 식별자도 받는다(renamed_to 로 답한다).")],
    ctx: Context,
) -> OntologyObjectOut:
    """받은 객체 하나를 칸 · 상태 · 옛 식별자 · 지금 이어진 선과 함께 준다.

    key 는 ontology_find 의 items[].key(과제면 list_tasks 의 key)다. 목록 · 검색은 ontology_find, 과제의 판 줄은 task_revisions.
    돌려주는 것 — `object`(type · key · label · status · active · hidden · merged_into · source · properties(칸) · previous_keys) ·
    `merged_into_now`(바뀜 · 합침을 끝까지 푼 지금 key — 합쳐진 객체만) · `previous`(옛 식별자) · `out` · `in`(나가는 · 들어오는 선 —
    relation · type · key · label · source · evidence_note(근거 메모) · updated_at, 지금 이어진 것만) · `scope`.
    ★허브가 바꾼 옛 식별자로 물으면 `object:null` 과 `renamed_to`(지금 key)가 온다 — 「없다」 가 아니다. 받은 적이 없는 key 는
    거절된다(HTTP 404).
    ★끝이 리포트인 선(개정에 달린 리포트)은 읽을 수 있는 리포트만 보인다 — `scope` 가 readable 이면 전부가 아니다(시스템 관리자는
    all). 선 수에 상한 · 페이지는 없다."""
    return await _get(ctx, f"/ontology/objects/{_seg(type_slug)}/{_seg_key(key)}")


@mcp.tool(annotations=_READ)
async def plan_task_links(
    ctx: Context,
    limit: Annotated[int, Field(le=TASK_LINKS_LIMIT_MAX,
                                description=f"판정할 자유 문자열 수 상한(1~{TASK_LINKS_LIMIT_MAX}) — 문자열 정렬 순으로 앞에서부터. "
                                            "0 이하(기본 0)면 전부. 자르면 counts 의 links · proposal · unmatched 도 판정한 것만 "
                                            "센다(counts.strings 가 전체 문자열 수).")] = 0,
) -> PlanTaskLinksOut:
    """과거 리포트의 자유 문자열 과제를 정본 과제에 붙이는 계획을 미리 본다 — 아무것도 쓰지 않는다(로그인한 누구나).

    후보 · 못 붙임을 사람에게 보여 주고 confirm_task_alias 로 별칭을 붙이게 할 때 쓴다. 리포트 하나의 판은 report_revision, 확정은
    set_report_revision. 적용(붙는 것을 실제로 잇기)은 이 도구가 아니다(시스템 관리자 REST).
    돌려주는 것 — `plan[]`(자유 문자열마다 free · reports · n_reports · codes · task_key · how · verdict · candidates · ambiguous ·
    alias_missing · unlinked) · `counts` · `reports_without_a_name`(과제 이름조차 없는 리포트 id) · `scope`.
    - verdict `links`(붙는다)는 글자 그대로 맞는 원천(과제명 · 과제코드 · 옛 과제명 · 사람이 붙인 별칭 · 허브 별칭)이 과제 하나로
      모일 때만이다. 엇갈리면(`ambiguous:true`) `proposal`(후보 있음), 없으면 `unmatched`. 그만 쓴(deprecated) 과제는 살아 있는
      과제가 하나도 안 맞을 때만 센다 — 하나면 잇고 여럿이면 못 붙임이다. 짐작으로 붙이지 마라.
    - `links` 는 허브 받기 뒤 · 리포트 반입 뒤 스스로 이어진다(사람이 손으로 확정한 리포트는 옮기지 않는다) — 그래서 대개 이미
      이어져 있다. 반입 · 수동 메타 고침(update_report_meta)도 같은 판정을 따르고, 허브가 모르는 이름만 글자 그대로의 판에
      이어져 있다가 허브가 그 과제를 내거나 사람이 별칭을 붙인 뒤 자동 잇기가 옮긴다.
    - `alias_missing` — 사람이 붙인 별칭의 끝(과제)이 거울에 없어(지워짐 · 합쳐짐 · 받은 적 없음) 그 별칭으로는 잇지 않았다.
      `unlinked` · `counts.unlinked` — 사람이 연결을 끊은 리포트(자동 잇기 · 일괄 적용이 건너뛴다).
    ★일반 사용자는 읽을 수 있는 리포트(소유 · 같은 소속)만 들고 수도 그것으로 센다(`scope: readable` — 전사 수가 아니다). 시스템
    관리자는 전부다(`all`)."""
    # ⚠`{"limit": None}` 을 넘기면 httpx 가 `limit=` 를 빈 값으로 보내고 `int` 쿼리가
    #   **422 로 거절한다**(실측 — 기본 호출이 그래서 깨져 있었다). 키를 아예 뺀다.
    return await _get(ctx, "/ontology/task-links", {"limit": limit} if limit > 0 else None)


@mcp.tool(annotations=_READ)
async def compare_task_revisions(task_key: Annotated[str, Field(description=_A_TASK_KEY)],
                                 ctx: Context) -> CompareTaskRevisionsOut:
    """한 과제의 개정을 나란히 놓는다 — 판마다 최악 응력 · 최악 G · 심각도 · 케이스 수와 앞 판 대비 변화.

    같은 과제의 판끼리 결과를 견줄 때 쓴다. 판 줄만 필요하면 task_revisions 다. 판끼리 리포트를 파트별로 견주려면
    `revisions[].reports` 의 id 를 compare_reports 로, 리포트 하나의 케이스를 그림으로 보려면 report_compare 로 넘긴다.
    돌려주는 것 — `task` · `task_found` · `revisions[]`(개정 줄 칸 + n_reports · worst_stress(MPa) · worst_g(G) · max_severity ·
    n_cases · measured_from · missing_reports · d_worst_stress) · `scope`. 숫자는 리포트에 이미 승격된 칸을 그대로 쓴다(다시 계산하지
    않는다). 상한 · 페이지 없이 전부 온다.
    ★안 잰 것은 `null` 이고 0 이 아니다 — 0 으로 읽으면 「쟀는데 0」 이 된다. `d_worst_stress` 는 앞 판과 양쪽에 값이 있을 때만
    수이고 아니면 null 이다.
    ★`measured_from` 은 그 판의 몇 건에서 최악값을 모았는지다 — 한 건과 열 건의 최악값은 같은 뜻이 아니다.
    ★리포트 줄 · 수치는 읽을 수 있는 리포트(소유 · 같은 소속)만으로 센다 — 판은 다 보인다(`scope`: all 시스템 관리자 · readable).
    `task_found:false`(reason `unknown_task`)면 정본에 없는 과제다 — list_tasks 로 과제명을 찾는다."""
    return await _get(ctx, f"/ontology/tasks/{_seg_key(task_key)}/compare")


@mcp.tool(annotations=_SET)
async def unlink_report_revision(report_id: Annotated[str, Field(description=_A_OWN_REPORT_ID)],
                                 ctx: Context) -> UnlinkReportRevisionOut:
    """리포트와 개정 사이의 연결을 끊고 끊은 기록을 남긴다 — 개정 객체는 남는다(리포트 소유자만).

    잘못 확정했을 때 쓴다. 다른 판으로 옮기려면 끊지 말고 set_report_revision 으로 바로 다시 확정한다(옛 선은 그때 떨어진다).
    개정 객체를 지우지 않는 까닭 — 그 판에 다른 리포트가 달려 있거나 `supersedes` 줄의 가운데일 수 있어 지우면 되돌릴 수 없다.
    ★끊은 사람 · 때를 기록한다 — 그 뒤로는 자동 잇기(허브 받기 뒤 · 리포트 반입 뒤 · 관리자 일괄 적용)도 수동 메타 고침
    (update_report_meta)도 이 리포트를 다시 잇지 않는다. 다시 잇게 하려면 set_report_revision(손으로) 또는 clear_report_unlink(기록
    지우기). 기록은 report_revision 의 `unlinked` 로 본다.
    돌려주는 것 — `was`(끊은 개정 key) · `unlinked_by` · `unlinked_at` · `detail`. 이어진 개정이 없으면 거절된다(HTTP 409
    `not_linked`)."""
    return await _delete(ctx, f"/reports/{_seg(report_id)}/revision")


@mcp.tool(annotations=_SET)
async def clear_report_unlink(report_id: Annotated[str, Field(description=_A_OWN_REPORT_ID)],
                              ctx: Context) -> ClearReportUnlinkOut:
    """사람이 끊은 기록을 지워 그 리포트를 자동 잇기가 다시 보게 한다(리포트 소유자만).

    unlink_report_revision 을 되돌릴 때 쓴다. 특정 판에 바로 이으려면 set_report_revision 이 낫다(기록도 함께 지운다).
    지운 뒤 그 리포트 하나의 자동 잇기를 바로 한 번 돈다 — 과제명 · 과제코드 · 별칭이 글자 그대로 과제 하나로 풀리고 개정 코드가
    있으면 지금 이어진다(`task_links`). 허브가 모르는 이름은 지금 이어지지 않는다(세기만 한다) — 글자 그대로의 선은 project 나
    dev_rev 를 주는 다음 메타 저장(update_report_meta) 때 다시 생긴다.
    돌려주는 것 — `was`(기록에 있던 개정 key) · `detail` · `task_links`(이 리포트의 자동 잇기 결과 — 기능 꺼짐 · 잠금이면 `skipped`,
    실패면 `error`). 기록이 없으면 거절된다(HTTP 409 `not_unlinked` — 조용히 성공하지 않는다). 기록은 report_revision 의
    `unlinked` 로 본다."""
    return await _delete(ctx, f"/reports/{_seg(report_id)}/revision/unlinked")


@mcp.tool(annotations=_SET)
async def confirm_task_alias(
    alias: Annotated[str, Field(description="붙일 자유 문자열 — 과거 리포트에 적힌 과제 이름 그대로(plan_task_links 의 plan[].free). "
                                            "앞뒤 공백은 뗀다. 1~500자.")],
    task_key: Annotated[str, Field(description="가리킬 과제명 — list_tasks 의 items[].key(과제코드가 아니다 — 풀지 않고 글자 그대로 "
                                               "적는다). 1~300자.")],
    ctx: Context,
    note: Annotated[str, Field(description="근거 메모 — 비우면 적지 않는다(같은 과제에 다시 붙일 때 비우면 앞 메모를 둔다). "
                                           "최대 2000자.")] = "",
) -> ConfirmTaskAliasOut:
    """자유 문자열(과거 리포트의 과제 이름)을 정본 과제에 별칭으로 붙인다(시스템 관리자).

    ★짐작으로 부르지 마라 — plan_task_links 의 후보와 근거를 사람에게 보여 주고 고른 값을 넣는다. 떼기는 remove_task_alias.
    한 번 붙이면 다음 자동 잇기(허브 받기 뒤 · 리포트 반입 뒤)부터 그 이름의 리포트가 그 과제에 이어진다. 단 다른 정확 일치(과제명 ·
    과제코드 · 옛 과제명 · 허브 별칭 · 같은 이름)가 다른 과제를 가리키면 엇갈림이라 잇지 않고 후보로 남는다(`ambiguous` — 그만 쓴
    과제는 살아 있는 과제를 막지 못한다).
    붙인 과제가 거울에 없으면(받기 전 · 허브에서 지워짐) 그 별칭으로는 잇지 않는다(`alias_missing`) — 그 과제가 거울에 오면 자동
    잇기가 옮긴다. 허브가 이름을 바꾼 옛 과제명에 붙였으면 지금 이름의 과제로 본다(합쳐 없어진 과제는 따라가지 않는다).
    한 문자열은 한 과제만 가리킨다 — 다른 과제에 붙어 있으면 거절된다(HTTP 409 `already_bound` — 먼저 뗀다). 같은 과제에 다시
    붙이면 새 행 없이 붙인 사람 · 메모만 고친다.
    돌려주는 것 — `ok` · `alias` · `key`."""
    return await _post(ctx, "/ontology/aliases",
                       {"alias": alias, "key": task_key, "note": note})


@mcp.tool(annotations=_DELETE)
async def remove_task_alias(
    alias: Annotated[str, Field(description="뗄 자유 문자열 — 붙일 때 적은 그대로(앞뒤 공백은 뗀다). 1~500자.")],
    ctx: Context,
) -> RemoveTaskAliasOut:
    """붙여 둔 별칭을 뗀다(시스템 관리자) — 이미 이어 둔 개정은 건드리지 않는다.

    별칭을 잘못 붙였거나 다른 과제로 옮겨 붙이기 전에 쓴다(한 문자열은 한 과제만 가리키므로 먼저 뗀다 — 다시 붙이기는
    confirm_task_alias). 별칭은 「다음부터 이렇게 붙여라」 는 규칙이고 과거에 붙인 것은 사람이 확정한 사실이라, 이미 이어진 리포트의
    판은 그대로다 — 끊으려면 리포트마다 unlink_report_revision.
    돌려주는 것 — `alias` · `was`(가리키던 과제명) · `detail`. 붙은 것이 없으면 거절된다(HTTP 404 `not_found`)."""
    return await _delete(ctx, "/ontology/aliases", {"alias": alias})


# ── 레시피 — 빌드 없이 쌓이는 분석 함수(docs/01-plan/features/recipes-1026) ────────────
# ★ 규칙 둘(SKILL.md 와 같다):
#   1) 새 비교·분석 코드를 쓰기 전에 `recipe_search` 로 이미 있는지 먼저 보라.
#   2) 즉석으로 짠 분석이 효과를 봤으면 `recipe_propose` 로 올려라 — 다음부터 남도 쓴다.
@mcp.tool(annotations=_READ)
async def recipe_search(
    ctx: Context,
    q: Annotated[str, Field(description="검색어 — 이름과 meta 의 title · question · when_to_use · tags 에 든 부분 문자열(대소문자 "
                                        "무시). 비우면 거르지 않는다.")] = "",
    kind: Annotated[str, Field(description=f"리포트 종류 — {_one_of(REPORT_KINDS)} 가운데 하나를 받는 레시피만(meta.kinds). 비우면 "
                                           "모두. 다른 값은 거절되지 않고 빈 목록이 된다.")] = "",
    tag: Annotated[str, Field(description="태그 — meta.tags 에 글자 그대로 든 레시피만. 비우면 모두.")] = "",
    limit: Annotated[int, Field(ge=1, le=RECIPE_SEARCH_LIMIT_MAX,
                                description=f"돌려줄 최대 레시피 수(1~{RECIPE_SEARCH_LIMIT_MAX}). 기본 50.")] = 50,
) -> list[RecipeSearchRow]:
    """쌓인 레시피(빌드 없이 쌓이는 분석 함수)를 검색어 · 종류 · 태그로 찾는다 — 분석 · 비교 코드를 쓰기 전에 먼저 본다.

    등록된 레시피와 내가 올린 초안 · 후보가 온다(내려진 것은 빠진다). 등록 판이 먼저, 그 안에서 '쓸모 있었다' 평가가 많은
    것부터다. 쓸 만한 게 있으면 recipe_get 으로 코드 · 인자를 보고 recipe_run, 없으면 직접 분석하고 효과를 보면 recipe_propose 로
    올린다.
    돌려주는 것 — 목록(name · domain · registered · current_version · meta(title · question · when_to_use · kinds · tags · inputs ·
    params) · useful_count · has_draft).
    ★limit 에서 조용히 잘린다 — 전체 수 · 잘림 표시가 없다. 받은 수가 limit 과 같으면 더 있을 수 있으니 q · kind · tag 로
    좁히거나 limit 을 올린다."""
    params = {"q": q, "kind": kind, "tag": tag, "limit": limit}
    return await _get(ctx, "/recipes", params={k: v for k, v in params.items() if v != ""})


@mcp.tool(annotations=_READ)
async def recipe_get(name: Annotated[str, Field(description=_A_RECIPE_NAME)], ctx: Context) -> RecipeGetOut:
    """레시피 하나의 상세를 준다 — 판 목록 · 상태 · 메타 · 관문 결과 · 코드.

    recipe_run 전에 무엇을 하는지, 어떤 params 를 받는지 본다(`versions[].meta.params` 와 코드의 `params.get(...)`). 찾기는
    recipe_search.
    돌려주는 것 — `name` · `domain` · `origin`(platform 이 플랫폼에서 올림 · git 씨앗 · 내보낸 파일) · `current_version`(등록 판 —
    없으면 null) · `deprecated_at` · `deprecated_reason` · `versions[]`(새 판부터 — version · status(draft 자기 시험 실패 · candidate
    후보 · registered 등록 · superseded 물러남) · meta · checks(정적 검사 · 자기 시험 · 앞 판 호환) · gate(등록 근거) · code ·
    created_at · registered_at).
    ★코드는 등록 · 물러난 판과 내가 올린 판만 보인다 — 남의 초안 · 후보는 `code:null`. 없는 이름이면 거절된다(HTTP 404)."""
    return await _get(ctx, f"/recipes/{_seg(name)}")


@mcp.tool(annotations=_ADD)
async def recipe_run(
    name: Annotated[str, Field(description=_A_RECIPE_NAME)],
    session_id: Annotated[str, Field(description="잡을 돌릴 내 세션 id — create_session 응답 · list_sessions 의 id. 결과 파일이 이 "
                                                 "세션에 남는다.")],
    report_ids: Annotated[list[str], Field(min_length=1, max_length=RECIPE_RUN_REPORTS_MAX,
                                           description=f"돌릴 리포트 id(1~{RECIPE_RUN_REPORTS_MAX}개) — find_reports 의 items[].id. "
                                                       "읽을 수 있는 리포트여야 하고, 개수 · 종류는 레시피의 meta.inputs "
                                                       "(min_reports · max_reports) · meta.kinds 를 따른다.")],
    ctx: Context,
    params: Annotated[dict | None, Field(description='레시피 인자 — 키는 그 레시피가 읽는 것이다(recipe_get 의 versions[].meta.params '
                                                     '와 코드의 params.get(...)). 예 angles_over_threshold 는 {"metric": '
                                                     '"max_stress", "threshold": 300}. 비우면 {}(레시피의 기본값).')] = None,
    version: Annotated[int | None, Field(description="돌릴 판 번호 — 비우면 등록 판(current_version). 등록 전 판(초안 · 후보)은 "
                                                     "올린 사람만 돌린다.")] = None,
    wait_sec: Annotated[int, Field(description="결과를 기다릴 최대 초(약 1초마다 확인 — 0 이하는 한 번만 본다). 기본 200. 도구 호출 "
                                               "기한(기본 540초)을 넘기면 오류로 끊기고 run_id 를 못 받으니 그보다 작게 둔다.")] = 200,
) -> RecipeRunOut:
    """레시피를 실데이터 리포트로 돌리고 끝날 때까지(최대 wait_sec 초) 기다려 결과를 준다 — 격리 샌드박스 · 플랫폼 잡.

    recipe_search · recipe_get 으로 고른 레시피를 돌릴 때 쓴다. 결과가 쓸모 있었으면 recipe_evaluate 로 평가를 남겨라 — 그래야 그
    판이 등록 관문(recipe_register)에 걸린다. 부를 때마다 새 실행 · 새 잡이 생긴다.
    돌려주는 것 — `run_id` · `job_id` · `status`(queued · running · succeeded · failed) · `result` · `result_truncated` ·
    `output_file_id` · `error` · `sandbox` · `elapsed_ms` · `hint`. 결과 전체는 세션 산출 파일(output_file_id — download_result)에 있고,
    크면(기본 256 KB 넘음) `result` 에는 안내만 오고 `result_truncated:true` 다.
    ★wait_sec 안에 안 끝나면 그때 상태(queued · running)로 돌아온다 — 잡은 계속 돈다. get_job(job_id) 로 상태를, 끝난 뒤
    get_job_outputs · download_result 로 결과 파일을 본다. 도구 호출 기한에 걸려 run_id 를 못 받았으면 list_session_jobs 로 잡을 찾는다.
    실행 하나는 샌드박스에서 기본 180초까지다. 리포트 수 · 종류가 레시피의 meta.inputs · meta.kinds 를 벗어나면 거절된다(HTTP 400)."""
    import asyncio
    body = {"session_id": session_id, "report_ids": report_ids, "params": params or {}}
    if version is not None:
        body["version"] = version
    sub = await _post(ctx, f"/recipes/{_seg(name)}/run", body)
    run_id, job_id = sub.get("run_id"), sub.get("job_id")
    last = sub
    for _ in range(max(1, wait_sec)):
        last = await _get(ctx, f"/recipes/runs/{_seg(run_id)}")
        if last.get("status") in ("succeeded", "failed", "canceled"):
            break
        await asyncio.sleep(1)
    return {
        "run_id": run_id, "job_id": job_id, "status": last.get("status"),
        "result": last.get("result"), "result_truncated": last.get("result_truncated"),
        "output_file_id": last.get("output_file_id"), "error": last.get("error"),
        "sandbox": last.get("sandbox"), "elapsed_ms": last.get("elapsed_ms"),
        "hint": "쓸모 있었으면 recipe_evaluate(run_id, useful=true, note=...) 로 근거를 남겨라",
    }


@mcp.tool(annotations=_ADD)
async def recipe_propose(
    name: Annotated[str, Field(description="레시피 이름 — 소문자로 시작하는 소문자 · 숫자 · 밑줄 3~64자(예 angles_over_threshold). "
                                           "있는 이름이면 그 레시피의 다음 판이 된다.")],
    code: Annotated[str, Field(description="파이썬 소스 — run(reports, params) 와 test_*() 하나 이상을 정의한다. 최대 200000자.")],
    ctx: Context,
    meta: Annotated[dict | None, Field(description="레시피 메타 — {title, question, when_to_use, kinds:[sphere|impact|deep], "
                                                   "needs:['data']?, inputs:{min_reports, max_reports}, params:{인자: 설명}, tags:[...]}. "
                                                   "비우면 kinds 는 셋 모두 · inputs 는 1~8 · 나머지는 빈 값. 적지 않은 키는 버린다. "
                                                   "needs 에 data 를 넣으면 리포트 원본 데이터(data.json)도 받는다.")] = None,
) -> RecipeProposeOut:
    """즉석 분석이 효과를 봤을 때 그 코드를 레시피 새 판으로 올린다 — 정적 검사 → 자기 시험(+앞 판 호환 시험) → 후보.

    recipe_search 로 같은 것이 없는지 먼저 본다. 같은 이름이 있으면 다음 판 번호로 올라간다(누구나 새 판을 올릴 수 있다). 부를
    때마다 새 판이 생긴다. 후보가 되면 recipe_run → recipe_evaluate → recipe_register 로 등록까지 간다.
    code 는 `run(reports, params)` 와 하나 이상의 `test_*()` 를 정의해야 한다. 리포트는 `recipe_kit.Report`(meta · parts · cases ·
    part_worst() · hotspots() · contact_profile() · case_energy() …)로 받고, 시험은 `recipe_kit.make_report(...)` 로 작은 리포트를
    만든다. 허용 import 는 stdlib 일부 · numpy · scipy · recipe_kit 뿐이고 파일 열기 · os · 던더 속성은 막힌다.
    돌려주는 것 — `name` · `version` · `status`(candidate 자기 시험 통과 · draft 실패) · `checks` · `message` · `similar`(비슷한
    레시피 이름). 정적 검사에 걸리거나 이름 · meta 가 틀리면 판을 만들지 않고 거절된다(HTTP 400)."""
    return await _post(ctx, "/recipes/propose",
                       {"name": name, "code": code, "meta": meta or {}})


@mcp.tool(annotations=_SET)
async def recipe_evaluate(
    run_id: Annotated[str, Field(description="실행 id — recipe_run 응답의 run_id.")],
    useful: Annotated[bool, Field(description="쓸모 있었으면 true — true 이고 글이 충분해야 등록 근거로 센다.")],
    note: Annotated[str, Field(description=f"까닭 — 무엇을 보여 줬는지 구체적으로. 등록 근거가 되려면 앞뒤 공백을 뺀 "
                                           f"{RECIPE_NOTE_MIN}자 이상, 최대 2000자.")],
    ctx: Context,
) -> RecipeEvaluateOut:
    """레시피 실행 하나가 쓸모 있었는지와 그 까닭을 남긴다 — useful=true 와 20자 이상의 글이 등록 관문의 근거다.

    recipe_run 결과를 본 뒤 쓴다. 근거가 갖춰지면 recipe_register 로 등록한다. 성공(succeeded)한 실행의 평가만 근거로 센다.
    같은 실행에 다시 부르면 앞 평가를 덮는다. 자기 실행만 평가할 수 있다(시스템 관리자는 전부).
    무엇을 보여 줬는지 구체적으로 적어라(예 '전 각도에서 파트 7 이 항복을 넘는 방향을 한 번에 집어냈다').
    돌려주는 것 — `run_id` · `useful` · `note`."""
    return await _post(ctx, f"/recipes/runs/{_seg(run_id)}/evaluate",
                       {"useful": useful, "note": note})


@mcp.tool(annotations=_SET)
async def recipe_register(
    name: Annotated[str, Field(description=_A_RECIPE_NAME)],
    ctx: Context,
    version: Annotated[int | None, Field(description="등록할 판 번호 — 비우면 지금 등록 판(current_version)이라, 새 후보를 등록하려면 "
                                                     "꼭 넣는다(recipe_propose 응답의 version). 내가 올린 후보만 등록할 수 있다.")] = None,
) -> RecipeRegisterOut:
    """후보 판을 등록한다 — 사람 승인 없이 자동 관문만 넘으면 바로 모두가 검색 · 실행한다.

    recipe_propose → recipe_run → recipe_evaluate 뒤에 부른다. 관문 — 정적 검사 · 자기 시험 · (있으면)앞 판 호환 시험 통과, 이 판으로
    성공한 실데이터 실행 1건 이상, 그 실행에 「쓸모 있었다」 평가(글 20자 이상) 1건 이상. 못 넘으면 무엇이 빠졌는지 알려 준다
    (HTTP 400 — 보통 실행이나 평가가 아직 없다).
    등록하면 앞 등록 판은 물러나고(superseded) 이 판이 current_version 이 된다. 코드는 격리 샌드박스에서만 돈다(허용 import 만 —
    recipe_propose). 잘못 올라간 것은 recipe_deprecate 로 내린다(올린 사람 · 관리자 — 판 기록은 남는다).
    통과하면 데이터 뿌리(…/svc/kooremapper/recipes/<이름>/)로 recipe.py · recipe.json 을 내보낸다 — git 반영은 사람이 그 폴더를
    platform/recipes/ 로 옮겨 커밋한다(서버는 커밋 · 푸시하지 않는다).
    돌려주는 것 — `name` · `version` · `status` · `superseded`(물러난 앞 판 번호) · `exported`(내보낸 recipe.json 경로 — 실패면 null) ·
    `message`."""
    body = {"version": version} if version is not None else {}
    return await _post(ctx, f"/recipes/{_seg(name)}/register", body)


@mcp.tool(annotations=_DELETE)
async def recipe_deprecate(
    name: Annotated[str, Field(description=_A_RECIPE_NAME)],
    reason: Annotated[str, Field(description="내리는 까닭(틀린 결과 · 더 나은 레시피로 대체 등) — recipe_get 의 deprecated_reason 으로 "
                                             "남는다. 최대 1000자.")],
    ctx: Context,
) -> RecipeDeprecateOut:
    """레시피를 내린다(올린 사람 · 시스템 관리자) — recipe_search 에서 빠지고 판 기록은 남는다.

    틀린 결과를 내거나 더 나은 레시피로 바뀌었을 때 쓴다. 판 하나가 아니라 레시피 전체를 내린다 — 코드만 고치려면 recipe_propose 로
    새 판을 올려 recipe_register 로 등록한다(앞 판은 물러난다). 왜 내리는지 reason 에 남긴다. 되살리는 도구는 없다.
    ★검색에서만 빠진다 — 이름을 아는 사람의 recipe_get · recipe_run 은 막지 않는다.
    돌려주는 것 — `name` · `deprecated` · `reason`."""
    return await _post(ctx, f"/recipes/{_seg(name)}/deprecate", {"reason": reason})




# ── 자동 파이프라인(포털 계약 v1.1 — 계획 docs/01-plan/features/auto-pipeline-1127.plan.md) ─────────────────────
# 포털이 서비스 신원으로 부른다. 계약 §0.3 — 실패는 isError true 와 본문 {"error", "detail"(, "missing")} JSON, 성공은 isError false 이고
# error 칸이 없다(포털이 isError 와 칸으로 판정한다 — 예외로 올리면 「Error executing tool …」 머리가 붙어 JSON 이 아니다).
# 표지(계약 §3) — auto_submit · auto_cancel 은 readOnlyHint 없음(destructiveHint false), 나머지는 readOnlyHint true.
# 공통 계약 C6 — 거듭해도 같음 · 바깥 세계 표지까지. auto_submit 은 idem_key 로 거듭해도 같은 실행이고 stcx 클러스터에 닿는다.
_AUTO_RO = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
_AUTO_SUBMIT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
_AUTO_RW = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _auto_out(data: dict, *, error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
                          structuredContent=data, isError=error)


async def _auto_call(ctx, method: str, path: str, *, params=None, body=None) -> CallToolResult:
    try:
        async with _client() as c:
            r = await c.request(method, path, params=params, json=body, headers=_forward_headers(ctx))
        doc = r.json()
    except httpx.TimeoutException:
        return _auto_out({"error": "timeout", "detail": f"DynaForge API 가 {API_TIMEOUT_S}초 안에 답하지 않았다"}, error=True)
    except Exception as exc:  # noqa: BLE001 — 닿지 않음 · JSON 아님 모두 계약 꼴의 실패로
        return _auto_out({"error": "unreachable", "detail": f"DynaForge API 에 닿지 못했다({type(exc).__name__})"}, error=True)
    if r.status_code >= 400 or not (isinstance(doc, dict) and doc.get("success", True)):
        data = doc.get("data") if isinstance(doc, dict) and isinstance(doc.get("data"), dict) else {}
        err = {"error": data.get("error") or f"http_{r.status_code}",
               "detail": data.get("detail") or (doc.get("message") if isinstance(doc, dict) else "") or ""}
        if data.get("missing") is not None:
            err["missing"] = data["missing"]
        return _auto_out(err, error=True)
    data = doc.get("data") if isinstance(doc, dict) else None
    data = data if isinstance(data, dict) else {"data": data}
    data.pop("error", None)                # 성공에 error 칸을 싣지 않는다(계약 §4-3)
    return _auto_out(data)


@mcp.tool(annotations=_AUTO_RO)
async def auto_changes(
    ctx: Context,
    since: Annotated[str | None, Field(description="앞 호출의 next_since 를 그대로(불투명 커서). 비우면 처음부터.")] = None,
    limit: Annotated[int, Field(description="한 쪽의 최대 세션 수(1~500). complete 가 false 면 같은 next_since 로 다시 부른다.")] = 200,
) -> CallToolResult:
    """자동 파이프라인의 원천 — 마지막으로 본 뒤 바뀐 세션(덱)을 쪽 커서로 끝까지 돌려준다.

    언제 — 포털 자동 파이프라인이 무엇을 다시 해석할지 고를 때 주기적으로 부른다. 첫 호출은 since 없이, 다음은 앞 응답의 next_since 를
    그대로 준다. 낼 수 있는지는 auto_check, 내기는 auto_submit.

    돌려주는 것 — items[] · next_since · complete. 항목마다 subject{project: 세션의 허브 과제명 | null, revision: 개발 단계 | null, refs:
    {dynaforge: 세션 id}} · links{step_forge?} · inputs[세션 입력 파일 — kind(deck · file) · ref(파일 id) · sha256 · at] ·
    ready{deck_ready: 낼 덱이 정확히 하나} · updated_at(세션 수정과 마지막 파일 가운데 늦은 때). 과제 · 단계는 update_session 의 task_key ·
    dev_rev 로 넣고, 비면 null 이다(짐작하지 않는다).

    한도 — 한 쪽은 limit(1~500 · 기본 200) 세션. complete 가 false 면 같은 next_since 로 다시 부른다. 게이트웨이 서비스 계정(설정)으로
    부르면 모든 세션, 그 밖은 볼 수 있는 세션만. 실패는 isError 와 {error, detail} JSON(틀린 커서는 bad_cursor). 읽기만 한다."""
    params = {"limit": limit}
    if since:
        params["since"] = since
    return await _auto_call(ctx, "GET", "/auto/changes", params=params)

_A_SUBJECT = ("무엇에 대한 일인가 — auto_changes 가 준 subject 그대로 {project: 허브 과제명, revision: 개발 단계, refs: {dynaforge: "
              "세션 id}}. project · revision 이 비면 확인이 project_key · revision 으로 막는다.")
_A_PROFILE = "auto_profiles 의 profile id(예 fullangle_162 · fullangle_26)."
_A_UPSTREAM = "앞 해석 단계의 결과 봉투 {단계 id: 봉투}(선택) — 전각도 낙하는 쓰지 않는다."
_A_RUN_REF = "auto_submit 이 돌려준 run_ref."


@mcp.tool(annotations=_AUTO_RO)
async def auto_profiles(ctx: Context) -> CallToolResult:
    """자동 파이프라인이 낼 수 있는 해석 묶음(profile)과 제출 준비 여부를 돌려준다 — 지금은 전각도 낙하 둘.

    언제 — auto_check · auto_submit 에 줄 profile id 를 고르기 전에, 또는 제출 계정이 정해졌는지 볼 때.

    돌려주는 것 — app_version · service_identity(제출 계정이 정해졌나 — false 면 포털이 막힘으로 세운다) · profiles[] — id
    (fullangle_162 · fullangle_26 — Fibonacci 162 · 26 방향, 높이 · 바닥 · 시간은 stcx 제출 op 기본값) · title · inputs(덱 하나 필수) ·
    cost{cores(방향 수 × 각도당 코어 — 대략치), minutes(null), cluster: stcx} · sync(false — 늘 비동기) · criteria_source(null — 판정 기준이
    아직 없어 auto_result 의 verdict 는 늘 unknown) · outputs(metrics · artifacts).

    실패는 isError 와 {error, detail} JSON. 읽기만 한다."""
    return await _auto_call(ctx, "GET", "/auto/profiles")


@mcp.tool(annotations=_AUTO_RO)
async def auto_check(
    ctx: Context,
    subject: Annotated[dict, Field(description=_A_SUBJECT)],
    profile: Annotated[str, Field(description=_A_PROFILE)],
    upstream: Annotated[dict | None, Field(description=_A_UPSTREAM)] = None,
) -> CallToolResult:
    """자동 파이프라인으로 이 세션을 지금 낼 수 있는지 본다 — 아무것도 바꾸지 않는다.

    언제 — auto_submit 전에 막히는 까닭을 미리 볼 때. subject 는 auto_changes 항목의 것 그대로, profile 은 auto_profiles 의 id.

    돌려주는 것 — ready · missing[{kind, name?, why}] · inputs. kind 는 project_key · revision(세션의 과제 · 단계 칸이 비었다 —
    update_session 으로 넣는다) · input(세션 없음 · 덱이 정확히 하나가 아님 · 덱에 *INCLUDE) · infra(stcx 꺼짐 · 클러스터 공유 폴더가 아직
    준비 전) · permission(제출 계정 없음). ready 면 inputs 가 이번에 낼 덱(이름 · sha256)이다.

    실패는 isError 와 {error, detail} JSON(모르는 profile 은 bad_profile). 본문이 커서 POST 로 보내지만 읽기만 한다."""
    return await _auto_call(ctx, "POST", "/auto/check", body={"subject": subject, "profile": profile, "upstream": upstream})


@mcp.tool(annotations=_AUTO_SUBMIT)
async def auto_submit(
    ctx: Context,
    subject: Annotated[dict, Field(description=_A_SUBJECT)],
    profile: Annotated[str, Field(description=_A_PROFILE)],
    idem_key: Annotated[str, Field(description="포털이 만든 64자 소문자 16진수 — 같은 값으로 다시 부르면 새로 내지 않고 같은 run_ref 를 "
                                               "created false 로 돌려준다.")],
    upstream: Annotated[dict | None, Field(description=_A_UPSTREAM)] = None,
) -> CallToolResult:
    """자동 파이프라인으로 전각도 낙하 해석을 낸다 — 세션 덱을 stcx 클러스터에 제출하고 결과 리포트까지 run_ref 하나로 묶는다.

    언제 — auto_check 가 ready 일 때. 세션 덱을 실행 세션(제출 계정 소유)에 복사해 stcx 에 내고, Slurm 잡 번호가 서면 후처리 예약을 걸어
    sphere 리포트 반입까지 이어 간다. 진행은 auto_status, 끝난 결과는 auto_result, 아직 내기 전이면 auto_cancel.

    돌려주는 것 — run_ref · state(queued) · created. 같은 idem_key 로 다시 부르면 새로 내지 않고 같은 run_ref 를 created false 로 준다.
    갖춰지지 않았으면 내지 않고 isError 와 {error: not_ready, detail, missing}(auto_check 의 missing 과 같다). 그 밖의 실패도 isError 와
    {error, detail} JSON."""
    return await _auto_call(ctx, "POST", "/auto/submit",
                            body={"subject": subject, "profile": profile, "idem_key": idem_key, "upstream": upstream})


@mcp.tool(annotations=_AUTO_RO)
async def auto_status(ctx: Context, run_ref: Annotated[str, Field(description=_A_RUN_REF)]) -> CallToolResult:
    """자동 파이프라인 실행 하나의 상태를 돌려준다 — 다섯 낱말 가운데 하나.

    언제 — auto_submit 뒤 끝날 때까지 가끔 부른다. done 이면 auto_result 로 결과 봉투를 받는다.

    돌려주는 것 — state(queued · running · done · failed · cancelled) · detail(지금 단계나 실패 까닭 — 예 「stcx 해석 중(Slurm 123)」) ·
    progress(null) · updated_at. 부를 때 실행의 다음 단계를 잇는다(stcx 잡이 Slurm 번호를 얻으면 후처리 예약을 걸고, 리포트가 반입되면
    done) — 같은 상태에서 거듭 불러도 결과는 같다. 남의 실행 · 없는 run_ref 는 isError 와 {error: not_found, detail}."""
    return await _auto_call(ctx, "GET", f"/auto/runs/{_seg(run_ref)}/status")


@mcp.tool(annotations=_AUTO_RO)
async def auto_result(ctx: Context, run_ref: Annotated[str, Field(description=_A_RUN_REF)]) -> CallToolResult:
    """끝난 자동 파이프라인 실행의 결과 봉투를 돌려준다 — 수치 · 산출물 · 리포트 id.

    언제 — auto_status 가 done 일 때. 숫자를 더 깊이 볼 때는 report_id 로 report_summary · report_part_risk 를 연다.

    돌려주는 것 — run_ref · subject · profile · app_version · verdict(늘 unknown — 판정 기준이 아직 없다) · metrics(sphere 리포트의 최대
    응력 MPa · 최대 가속도 G — 단위계를 알 때만, 모르면 빼고 notes 에 까닭 · 끝난 각도 수 · 실패한 각도 수) · figures([]) · artifacts(결과
    폴더 · 리포트) · inputs(낸 덱 · sha256) · notes · finished_at · report_id. done 이 아니면 isError 와 {error: not_done, detail}."""
    return await _auto_call(ctx, "GET", f"/auto/runs/{_seg(run_ref)}/result")


@mcp.tool(annotations=_AUTO_RW)
async def auto_cancel(ctx: Context, run_ref: Annotated[str, Field(description=_A_RUN_REF)]) -> CallToolResult:
    """아직 stcx 에 내지 않은 자동 파이프라인 실행을 취소한다 — 이미 낸 실행은 여기서 멈추지 않는다.

    언제 — auto_submit 직후 잘못 낸 것을 알았을 때(stcx 제출 전 몇 초 · 대기 중). 이미 클러스터에 낸 잡은 KooSlurm 에서 멈춘다.

    돌려주는 것 — run_ref · state(cancelled). 이미 냈거나 끝났으면(취소된 것을 다시 불러도) isError 와 {error: not_cancellable, detail}
    이고 상태는 그대로다. 없는 run_ref 는 not_found."""
    return await _auto_call(ctx, "POST", f"/auto/runs/{_seg(run_ref)}/cancel")

if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("KOORM_MCP_PORT", os.environ.get("MCP_PORT", "8701")))

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
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
        allowed_origins=[],
    )

    if SDK2:
        mcp.run(transport="streamable-http", host=host, port=port, **http_options(security))
    else:
        mcp.settings.host, mcp.settings.port, mcp.settings.transport_security = host, port, security
        mcp.run(transport="streamable-http")
