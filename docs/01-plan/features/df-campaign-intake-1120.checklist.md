# DF 2차 ① — 캠페인 일괄 적재(DF-01) 체크리스트

계획 `df-campaign-intake-1120.plan.md` · 맥락 `df-campaign-intake-1120.context-notes.md`.

## A. 준비
- [x] A-1 작업 시작 확인 — SP main · 키트 판 그대로(3196156 · 2026-11-06) · 갈래 = main = d069d87
- [x] A-2 계획 · 체크리스트 · 맥락 문서(「진행해줘」 를 읽은 범위를 계획 0절에 적는다)
- [x] A-3 큰 리포트 해석 메모리 실측(설계안 정할 것 3) — 숫자와 선택지를 맥락 문서에

## B. 짓기(임시 DB 에서 — dev DB 는 건드리지 않는다)
- [x] B-1 마이그레이션 `0021_campaigns` · 모델 `Campaign` · `CampaignRun`(임시 DB 에서 내렸다 올리기 왕복)
- [x] B-2 `app/modules/campaigns/`(서비스 · 라우트 셋) · 라우터 등록
- [x] B-3 intake 폼 칸 `campaign_id` · `run_key` · `ingest_report(campaign_run_id=…)` — 건너뜀 · 거절 · 잠금
- [x] B-4 MCP 도구 셋 · `report_upload_instructions` 글 · `capabilities.intake`(새 칸 이름은 계획 4절) · parity 줄
- [x] B-5 문서 쓸기 — 도구 수 90 → 93(README · TOOLS.md · CLAUDE_DESKTOP.md) · TOOLS.md 표 · SKILL.md

## C. 재기
- [x] C-1 새 시험 `tests/test_campaign_intake.py`(계획 6절 1 ~ 9 · 11) — 10 항 · 변이 넷을 잡는다
- [x] C-2 닿는 기존 시험 — intake · 선언 · parity · 리포트 적재(전체 pytest 안에서 통과)
- [x] C-3 MCP 계약 시험 13 통과 · 임시 스택에서 MCP 도구 셋을 값으로 재기(28 항) · 441 MB 를 실제 HTTP intake 로(19.1 초 · 3,671 MB)
- [x] C-4 백엔드 전체 pytest — 1,051 통과 · 4 실패(감독자 로그 시험 — 작업 트리에 `platform/.env` 없음) · 12 건너뜀

## D. 올리기
- [x] D-1 갈래에 커밋 · 푸시(`corelink-int`)
- [ ] D-2 사용자 확인 — 계획 0절의 읽기 · 4절의 고른 읽기 · 이름 넷 · 상태 단어
- [ ] D-3 main 합치기 → dev DB 마이그레이션 → 재기동(살아 있는 잡 확인 뒤) → 스모크
- [ ] D-4 Drive 게시 · cae00 점검 문서 · 요청 쪽에 알릴 것
