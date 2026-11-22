# DF 2차 ② 체크리스트 — 런 출처 · 유효성(DF-02 · DF-03) · 동시 올리기의 DB 연결

계획 `df-provenance-health-1122.plan.md` · 맥락 `df-provenance-health-1122.context-notes.md`.

## A. 준비
- [x] A-1 결정 받기(문턱 쓰기 이름 · 그 밖 판정 · 수치 없는 런 · ② 먼저 · 다 짓고 cae00 검증)
- [x] A-2 계획 · 체크리스트 · 맥락 노트

## B. 짓기
- [ ] B-1 마이그레이션 `0022_campaign_health` · 모델 칸
- [ ] B-2 받는 꼴 — 런 목록의 `provenance` · `config_generation` · `superseded_by` · `health` · 캠페인의 `health_thresholds`
- [ ] B-3 판정 · 거르기 서비스(문턱 묶음 · `ref` · 까닭)
- [ ] B-4 REST 넷(문턱 쓰기 · 출처 · 캠페인 건강 · 리포트 건강) · `find_reports` 의 `config_generation`
- [ ] B-5 MCP 넷 · 두 도구의 인자 더함 · capabilities
- [ ] B-6 받기 줄 앞에서 연결 놓기 · 워커 길은 그대로
- [ ] B-7 글(TOOLS · SKILL · CLAUDE_DESKTOP · README · 매뉴얼에 닿는 곳)

## C. 시험
- [ ] C-1 시험 먼저 — `tests/test_campaign_health.py`(검증 사례 1 ~ 8) 빨강 확인
- [ ] C-2 연결 시험(`tests/test_report_parse_queue.py`) 빨강 확인
- [ ] C-3 짓고 초록 · 변이(판정 규칙 · 연결 놓기)
- [ ] C-4 MCP 계약 시험 · 백엔드 전체 · 임시 스택 실측(동시 40 건)

## D. 올리기
- [ ] D-1 main · dev DB 0022 · API · MCP 재기동 · 스모크(+ 캠페인 탐침)
- [ ] D-2 Drive · cae00 점검 문서 · 알림(포털 · smarttwinmcp · kooremapper-fd)
