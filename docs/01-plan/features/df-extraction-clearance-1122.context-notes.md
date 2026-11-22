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

## 3. 올리기(2026-11-22 — 3차 3판과 같은 판)
- **올리기(11-22 06:0x ~ 06:3xZ — DF 2차 ③ 과 같은 판)** — main `6ac6e70` → `2cbdc84`(ff — 뒤에 cae00 문서 `ae8a62e`) · 주 체크아웃 ff ·
  pykoocae-53 에 빌드 앞 알림 · 호환 빌드(빌더 컨테이너 · -j8 · 프로세스 8 GB 상한) rc 0 · glibc 2.35 ·
  `4b8fe975202d9103c9c69c5530ea20c2d9bf72617139b26de9ed04368e86cc85`(9,131,568 바이트) · 호환 단위 246 / 246 · 호환 회귀 148 / 148 · 도는 잡 0 ·
  설치 06:20:57Z(`build/linux/bin` · `platform/backend/bin`) · dev DB 0022 → 0023 · API 06:21:10 · MCP 06:21:31(`start.sh` — `/data` 바인드
  있음) · 스모크 MCP PASS(도구 100 · 연산 65) · deckops 29 / 29 · allops 64 / 64(건너뜀 1) · reports 59 / 59 · DF ③ 탐침 18 / 18(만든 캠페인 ·
  세션 지움) · 주 체크아웃 백엔드 1106 통과 · 실패 0 · cli.sif 06:28(안 바이너리 `4b8fe975`) · Drive `dist-20261122-062855Z`(게시 06:28:59Z ·
  다른 파일은 BUILD_INFO · koorm-bin.tar.gz · cli.sif 셋 · 가장 오래된 `dist-20261117-212938Z` 정리 — 남은 판 11-21 낮 · 11-21 밤 · 11-22 새벽 ·
  11-22 낮) · 게시 뒤 health `revision` `2cbdc84` · `revision_matches_binary` true · cae00 문서 §1-10(`ae8a62e`). 되돌릴 판은
  `dist-20261122-042305Z`(코드 `a50bcc3` · 바이너리 `1106bef1`).
