# DF 2차 ③ 맥락 노트 — 추출 완전성 · 삭제 관문

계획 `df-extraction-clearance-1122.plan.md` · 체크리스트 `df-extraction-clearance-1122.checklist.md`.

## 1. 시작(2026-11-22)
- 미룬 결함 3차 3판을 올리는 동안 썼다(차례 — 결함 판과 번갈아). 요청서 DF-04 원문은 스크래치에만 있다(리포에 두지 않는다).
- 입력 둘(KooChainRun KC-01 귀환 목록의 추출 목록 · KC-05 삭제)의 꼴을 이 박스에서 보지 못했다 — ② 처럼 요청서 표대로 받고 모르는 열쇠는 422.
- 리포트 생성기는 `peak_source` · 상태 수를 아직 내지 않는다 — 피크 표지의 값은 캠페인 런의 `extraction` 에서만 온다.

## 2. 지은 것 · 잰 것(2026-11-22)
- **지은 것(`9614bb8`)** — 마이그레이션 0023 · 순수 함수 `campaigns/extraction.py`(허가 · 피크 표지 · 머리 줄) · 받는 꼴(`ExtractionBody` ·
  `FieldItem` · `RequiredItem`) · 서비스 셋 · REST 셋 · 피크 표지 열 경로 · MCP 셋(97 → 100) · capabilities · 글.
- **목록 응답의 표지** — `/cases` · `/findings` 는 목록을 돌려준다. 꼴을 바꾸면 MCP(`report_worst_cases -> list`)와 화면이 깨져, 항목마다
  `peak_provenance` 를 싣는다(같은 값이 되풀이된다).
- **`status` 쿼리 이름** — 라우트 파일이 `fastapi.status` 를 쓰고 있어 매개변수를 `status_`(별칭 `status`)로 받았다. 계약 시험의 `_query` 가
  별칭으로도 찾게 고쳤다.
- **잰 것** — 시험 12 항(규칙 여덟 · 앱 넷 — 검증 사례 둘은 합성: 201 상태 중 40 상태의 `d3plot_sampled` 피크 · 판 변형률장이 빠진 런) · 피크
  경로 일곱이 sphere 표본에서 모두 200 과 표지를 돌려준다(400 으로 건너뛴 경로 0) · MCP 계약 13 / 13 · 선언 시험 · 변이 21 / 21 빨강 · 작업 트리
  백엔드 1090 통과 · 4 실패(`.env` 없는 supervisor_log). scratch DB 를 0023 으로 올렸다.
