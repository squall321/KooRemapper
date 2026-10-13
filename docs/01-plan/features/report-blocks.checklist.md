# Checklist — 리포트 블록 전수 노출

설계: `report-blocks.plan.md` · 맥락: `report-blocks.context-notes.md`

## A. 실측·기준
- [x] **A-1 차집합 전수 조사** — sphere 0 · deep 11 · impact 18 (실제 리포트 6개)
- [x] **A-2 차집합을 회귀로 고정** `backend/tests/test_report_blocks.py` 13항 —
      `EXPECTED_UNREAD` 를 **이름으로** 고정해, 생성기가 키를 늘리면 빨개진다

## B. 일반 블록 접근
- [x] **B-1 `list_blocks`** — 이름·형태·크기·`read_by_parser`
- [x] **B-2 `get_block`** — `path=a.b.0.c` 로 하위 선택, 끊기면 **쓸 수 있는 키를 알려준다**
- [x] **B-3 크기 가드** — 배열은 잘라서 **잘랐다고 말하고**, 스칼라/dict 가 너무 크면 거절하며 `path` 를 권한다
- [ ] B-4 API `GET /reports/{id}/blocks`, `/blocks/{name}`
- [ ] B-5 MCP `report_blocks`, `report_block`

## C. 일급 — 핫스팟·군집
- [x] **C-1 `hotspot_clusters`** — 실측 102 레코드 → 105 군집, 34파트 × 3기준.
      ★`stress_*` 정렬은 **절대값**이다(direction=min 기준은 음수다) · `uniform` 레코드를 적는다
- [x] **C-2 `behavior_clusters`** — ★선언 4 군집 중 **쓰인 것은 1**(실측)을 `degenerate` 로
      적는다. `is_mock` 도 그대로 올린다(합성을 실측으로 읽으면 결론이 거짓이다)
- [ ] C-3 API `/hotspots`, `/clusters` + MCP 도구 둘
- [ ] C-4 프런트 표(핫스팟 상위 군집 · 군집 아키타입)

## D. 시계열 비대칭
- [x] **D-1 시계열 7종** `DEEP_SERIES_BLOCKS` — 전에는 `stress` **하나만** 읽어 주응력·
      주변형·변형 시계열이 전부 끊겨 있었다(피크값만 살아 있었다). 하위 호환 유지
- [x] **D-2 회귀** — 시계열에 `unit`·`time_of_max`·`global_min` 도 같이 싣는다

## E. 관문
- [ ] E-1 backend 전수 · 회귀 전수
- [ ] E-2 라이브 스택에서 실제 리포트로 끝까지

## F. 큰 분석 블록 해석 (사용자 지시)
- [x] **F-1~F-5 `analytics_summary`** — 7 블록 전수. ★요약을 **다시 계산하지 않는다**:
      하위 분석이 들고 있는 생성기 `summary` 를 그대로 올린다(다시 계산하면 HTML 화면 숫자와
      조용히 갈린다). `available=false`·`empty=true`·`is_mock=true` 를 **미계산**으로 크게 적는다.
- [x] ~~F-1~~ `doe_analysis` 요약 — 격자·지표·`peak_g_matrix` 최악 셀·거동 분류 수
- [ ] F-2 `deep_analytics` 요약 — anomaly·fft·pca_modal·safe_drop_zone
- [ ] F-3 `insights` 요약 — DamageIndex·ReboundField·Symmetry·ContactPulse
- [ ] F-4 `physics` 요약 — RestitutionMap·StressWaveVelocity·worst_combinations
- [ ] F-5 `solver_quality`·`trajectories`·`part_motion` 요약
- [x] **F-6 요약이 원본을 가리지 않는다** — `raw_access_note` + `get_block(path=…)` 회귀

## G. ★결과 이미지 (사용자 지시 — LLM 이 보고 비교)
- [ ] G-1 `/reports/intake` 가 **번들**(.zip/.tar.gz) 반입 — HTML + 사이드카
- [ ] G-2 미디어를 SessionFile 로 저장하고 리포트·케이스에 연결(`set_report.media` 정본)
- [ ] G-3 `GET /reports/{id}/media` — 케이스·뷰·물리량·종류 필터
- [ ] G-4 ★MCP `report_image` 가 **ImageContent** 로 — 지금은 base64 를 dict 에 넣어
      Claude 에게 **글자**로 온다(실측). 이게 "이미지로 비교" 의 핵심 공백이다
- [ ] G-5 ★MCP `report_compare` — 이미지 N장 + 지표 표를 한 번에
- [ ] G-6 크기 규율 — 장수 상한·축소, 넘으면 **뺀 수를 말한다**
- [ ] G-7 프런트 이미지 갤러리(케이스별)
