# MCP 현대화 1127 맥락 — DynaForge MCP

계획 `mcp-modernize-1127.plan.md` · 체크리스트 `mcp-modernize-1127.checklist.md`.

## 1. stateless 전에 본 것(2026-11-27)
- 서버 → 클라이언트 채널 — `elicit` · `create_message` · `list_roots` · `send_*_list_changed` · `report_progress` · `ctx.info` 류 모두 0. 도구
  등록은 기동 때 한 번뿐(실행 중 `add_tool` 없음). `ctx` 는 `_forward_headers` 가 들어온 HTTP 요청의 머리(Authorization · 소속 둘)를 읽는 데만
  쓴다 — stateless 에서도 요청마다 실린다(탐침으로 확인).
- 같은 탐침, 바꾸기 전 · 뒤. initialize 의 `Mcp-Session-Id` 있음 → 없음. initialize 없이 부른 호출 400 「Missing session ID」 → 200. 옛 세션
  번호를 단 호출 404 「Session not found」 → 200(도구 120). 머리 나르기 그대로. 응답은 둘 다 SSE.
- GET(서버가 미는 줄)은 400 → 열어 둔 채 아무것도 오지 않는 SSE. DELETE 는 400 → 405 「Session termination not supported」. SDK 1.x 클라이언트는
  세션 번호가 없으면 GET 을 열지 않는다(`handle_get_stream`).
- 도는 판 — 운영 MCP 는 mcp.sif(`python:3.12-slim` · python 3.12.16 · mcp 1.28.0, `PYTHONNOUSERSITE=1`). dev 인스턴스는 그 SIF 에서 호스트
  `~/.local/lib/python3.12` 의 mcp 1.27.1 을 읽는다. 시험 · 스모크 venv(`platform/mcp_server/venv`)는 python 3.10 · mcp 1.27.2. 셋 다
  `stateless_http` 를 안다.
- 「허브가 지은 SIF · 캐시 열쇠」 — DynaForge 는 허브 등록 앱이 아니라 자체 빌드(Drive `dist-*` · 운영 노드)다. 포털 받은 편지함도 우리를 「운영
  노드」 로 적는다. 알릴 것은 Drive 판과 `SHA256SUMS` 의 mcp.sif 파일 sha256 이고, 허브 캐시 열쇠(`.sif.hash`)는 없다. server.py 는 코드
  체크아웃을 묶어 읽으므로 stateless 만으로는 mcp.sif 가 안 바뀐다.

## 2. 71 추가 지시(11-27) — 2단계를 지금 가지에서
- 「2단계는 읽고 계획만」 을 거두고 C1 ~ C9 을 최대한 고친다. 이름 · 동작은 그대로, 묶기는 제안만, SDK 2.x 는 할 수 있으면.
- 잰 값(main `e24ea649` 의 server.py, 감사와 같은 숫자) — 도구 120 · 인자 405 중 설명 193(47.7%) · enum 0 · 숫자 인자 107 중 경계 0 · 자유 객체
  14 · 표지 0 · outputSchema 0 · 설명 길이 400 미만 81 · 1,500 넘음 5 · 이력 낱말 33 · 같은 뜻 영어 31.

## 3. SDK 2.x 사실(PyPI 2.3.0 휠을 풀어 본 것)
- `Requires-Python: >=3.10` — 포털이 적은 「3.11 이상」 과 다르다(2.3.0 기준). mcp.sif 는 이미 3.12 다.
- `mcp.server.fastmcp` 는 지워졌다 — 들여오면 `ModuleNotFoundError` 로 `mcp.server.mcpserver.MCPServer` 를 가리킨다. `ToolError` 는
  `mcp.server.mcpserver.exceptions`. 새 의존 `httpx2` · `mcp-types` · `opentelemetry-api`.
