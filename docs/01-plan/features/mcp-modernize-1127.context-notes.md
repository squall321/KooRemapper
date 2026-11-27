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

## 4. 구역 여덟(2026-11-27)
- 도구 120 을 정의 줄 차례로 여덟 구역(21 · 11 · 16 · 17 · 14 · 8 · 12 · 21)에 나눠 작업 트리 `c9-g1` ~ `c9-g8` 에 에이전트 하나씩. 바탕 커밋이
  맨 위(표지 · `_shape` · import)를 먼저 두어 구역은 자기 도구의 데코레이터 · 서명 · docstring · 반환 표기와 첫 도구 위 상수 한 덩이만 고쳤다.
  몸통은 안 고쳤다(get_job 의 로그 잘림 표시 · report_compare 의 「외 N 개」 만 예외). 여덟 가지가 git 으로 겹침 없이 합쳐졌고 맨 위 이름 겹침
  0.
- 결과(전수 측정) — 인자 405 설명 100%(전 48%) · enum 33 · 숫자 경계 59 / 107(백엔드가 거는 것만) · 표지 120(읽기 78 · 더하기 15 · 덮기 26 ·
  바깥 세계 7) · outputSchema 112(그림 섞인 7 · download_result 제외) · 설명 225 ~ 1,354자(가운데 715 · 400 미만 11 — 단순 도구) · 이력 33 →
  TOOLS.md 「옮긴 이력」 절.
- 받는 집합 그대로 — Literal 은 백엔드가 받는 집합과 같을 때만. 어긋나는 가장자리 둘은 그대로 둔다 — 캠페인 지표(백엔드가 앞뒤 공백을 떼고 본다
  · 정식 이름 16 은 같다), 개정 코드(set_report_revision — 같은 까닭으로 enum 을 안 달았다). 문자열 길이 상한은 설명에만.
- 표지 `_REPLACE` 하나 더 — attach_report_scenario 는 덮되 부를 때마다 새 시나리오 파일을 남긴다(덮음 · 거듭하면 다름).

## 5. SDK 2.x 결정(2026-11-27)
- 두 SDK 로 돈다 — 시험 · 스모크 venv(1.x — 옛 세대 클라이언트)와 운영 SIF(2.x)가 같은 server.py 를 읽고, 되돌리기는 옛 SIF 로 충분하다.
- `PYTHONNOUSERSITE=1` 을 SIF 에 굽는다 — 11-02 에는 dev 판이 바뀌는 일이라 미뤘지만(사용자 결정 거리), 2.x 를 요청받은 지금은 이것 없이는 dev
  가 홈의 1.27.1 로 돌아 운영(2.x)과 갈린다.
- 본문 상한 1 GiB — 1.x 는 상한이 없었고 2.x 기본 4 MiB 면 upload_kfile 이 큰 덱에서 막힌다(5 MiB 탐침이 잰다).
- P3 — 2.x 는 ToolError 가 아닌 예외의 글을 서버에 남기고 모델엔 「Error executing tool <이름>」 만 보낸다(실측). 감싸개에서 바꾸면 1.x 글은
  바이트 그대로.
- 고정판 — 앞 판 고정을 그대로 두고 pip 가 2.x 의 새 의존 다섯만 더하게 했다(처음 풀어 받은 판은 httpx · pydantic 까지 모두 올라갔다).

## 6. 구조 결과는 응답이 두 배다
- 1.x · 2.x 모두 outputSchema 가 있으면 같은 내용을 글(content)과 structuredContent 둘로 낸다. 큰 결과(get_session · report_block 4 MB ·
  report_cae)는 두 배가 된다. download_result 는 그래서 꼴을 달지 않았다. 게이트웨이가 한쪽만 모델에 넘기면 된다 — 포털에 알린다.

## 7. 고치지 않고 알리는 것(백엔드 · 결정 거리)
- find_reports severity=INFO 가 「INFO 이상」 이 아니라 최고 심각도가 INFO 인 리포트만 걸린다(`services.py` `.get(sev, [sev])`) — 설명은
  「이상」 그대로.
- recipe_deprecate 는 찾기에서만 빠지고 이름으로 recipe_get · recipe_run 은 된다 — 의도인지(재현성) 결정 거리. 설명 · TOOLS.md 는 사실대로
  고쳤다.
- 조용한 백엔드 자르기 — list_sessions 200 · list_session_jobs 100 · recipe_search · find_cae 의 total(=건수) · report_energy_flow 의 case 키
  200 · system_status 10 줄. 설명에 적었다. 고치려면 인자(offset)나 백엔드 칸(total · truncated)을 더해야 한다(이름 · 동작 그대로 조건 밖).
- 묶기 제안(이름이 바뀌어 이번엔 안 함) — report_part_risk · report_directional · report_worst_cases 를 「파트 · 범주 · 케이스로 줄 세우기」
  하나로, report_scatter 를 report_angle_stats 의 갈래로, report_part_energy 를 report_part_series 의 물리량 선택으로, set_campaign_* 일곱을
  set_campaign_settings 하나로(구역마다 PUT 이라 원자적이지 않다 — 백엔드 PATCH /campaigns/{id} 가 필요).
