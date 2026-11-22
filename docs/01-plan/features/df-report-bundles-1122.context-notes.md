# DF 2차 ④ 맥락 노트 — 보고서용 묶음 출력

계획 `df-report-bundles-1122.plan.md` · 체크리스트 `df-report-bundles-1122.checklist.md`.

## 1. 시작(2026-11-22)
- 미룬 결함 3차 4 · 5판을 재는 동안 썼다. 요청서 DF-13 원문은 스크래치에만 있다(리포에 두지 않는다).
- 묶음에 실을 사실은 지금 있는 것뿐이다 — 캠페인 런(판정 · 세대 · 추출), 리포트 케이스 롤업(`impact_cases` 의 최대 응력 · G · 변위 · 안전율),
  파트 피크(`parts_metrics`), 리포트 매체(그림). 각도 통계 · 피크 표 · 여유 · 자리 표는 ⑤ 에서 함수가 서면 표 종류로 더한다.
- 단위 표는 ReportArchive 내보내기(`analysis/ndjson.py` 의 `_UNITS` · `_FACTS`)에 이미 있다 — 묶음이 두 번째 소비자라 한 곳에 두고 같이
  쓴다(사본을 만들지 않는다).
- 이 박스에 ReportArchive(RA-02) · 심의 엔진(DL-01 `ref.kind` 목록)이 없어 인용 꼴은 요청서의 C1 공용 꼴대로 세운다.

## 2. 지은 것 · 잰 것(2026-11-22)
- **지은 것** — 마이그레이션 0024(`report_bundles` · `report_bundle_items`) · 순수 함수 `campaigns/bundles.py`(항목 · 표 · 그림 인용 · 기준 줄 ·
  같음 · 차이 · 출처 경로 풀기) · 서비스(입력 모으기 · 짓기 · 판 읽기 · 차이 · 캠페인의 마지막 판) · REST 넷 · MCP 셋(100 → 103) · capabilities
  경로 넷과 표 한 줄 · 글(TOOLS · SKILL · README · CLAUDE_DESKTOP). 단위 표는 `analysis/ndjson.py` 의 것을 공개 이름(`UNITS` · `FACTS`)으로 같이
  쓴다.
- **그림** — 리포트 매체는 번들로 올 때만 생긴다(확장자 png · jpg · jpeg · webp · gif 는 image, 나머지 영상). svg 는 지금 매체로 받지 않아 기본
  확장자(png · svg)의 svg 는 비어 있다. sha256 은 세션 파일 행의 값(올릴 때 잰다)이고 비었으면 그 자리에서 잰다.
- **잰 것** — 시험 `test_campaign_bundles.py` 7 항(순수 넷 · 앱 셋 — 검증 사례 합성: 묶음의 케이스 숫자 = `/reports/{id}/cases` 의 값 · 출처
  경로가 그 리포트 · 케이스 · 지표에 닿는다) · 선언 시험 · MCP 계약 13 / 13 · 변이 21 / 21 빨강 · scratch DB 0023 → 0024 → 0023 → 0024 · 작업
  트리 백엔드 1099 통과 · 4 실패(`.env` 없는 supervisor_log) · 건너뜀 12.
