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
- [x] **B-4 API** `/blocks` · `/blocks/{name}`(`path`·`limit`·`max_bytes`)
- [x] **B-5 MCP** `report_blocks` · `report_block`

## C. 일급 — 핫스팟·군집
- [x] **C-1 `hotspot_clusters`** — 실측 102 레코드 → 105 군집, 34파트 × 3기준.
      ★`stress_*` 정렬은 **절대값**이다(direction=min 기준은 음수다) · `uniform` 레코드를 적는다
- [x] **C-2 `behavior_clusters`** — ★선언 4 군집 중 **쓰인 것은 1**(실측)을 `degenerate` 로
      적는다. `is_mock` 도 그대로 올린다(합성을 실측으로 읽으면 결론이 거짓이다)
- [x] **C-3 API·MCP** `/hotspots` · `/clusters` · `/analytics` + 도구 셋
- [x] **C-4 프런트 표** `ReportAnalysis` 에 탭 둘 — 핫스팟 군집(파트·기준·순위·|응력|·요소·
      부피·반경·중심·피크시각, 기준 필터) · 거동 군집(아키타입별 위치, `degenerate`·`is_mock`
      을 **빨간 테두리로 먼저** 보인다)

## D. 시계열 비대칭
- [x] **D-1 시계열 7종** `DEEP_SERIES_BLOCKS` — 전에는 `stress` **하나만** 읽어 주응력·
      주변형·변형 시계열이 전부 끊겨 있었다(피크값만 살아 있었다). 하위 호환 유지
- [x] **D-2 회귀** — 시계열에 `unit`·`time_of_max`·`global_min` 도 같이 싣는다

## E. 관문
- [x] **E-1 backend 344** (회귀 `test_report_blocks.py` 13 + `test_report_media.py` 10)
- [x] **E-2 라이브 스택 관문** `platform/mcp_server/reports_smoke.py` **23항 PASS**.
      ★`ImageContent` **종류**를 본다 — 수를 세는 관문으로는 절대 안 잡힌다(dict 안의
      base64 도 '성공' 이다). `smoke`·`figures_smoke`·`deckops_smoke` 도 전부 초록

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
- [x] **G-1 번들 반입** `app/reports/bundle.py`(순수 함수). 가드: 트래버설·링크/장치·
      멤버 수·멤버 크기·합계 크기·확장자. 실측으로 탈출 2건·비미디어 1건을 **거부하고 셌다**
- [x] **G-2 저장·연결** 마이그레이션 `0010_report_media`(JSONB). `add_uploaded_file` 이
      하위 경로를 살려서 선언 경로와 **같은 문자열**로 조인된다.
      ⚠ `ingest_report` 가 이미 커밋하므로 뒤에서 **커밋해야** 한다(flush 만 하면 사라진다 —
      반입 응답은 16장인데 `/media` 가 0 을 냈다. 회귀가 다시 읽어 확인한다)
- [x] **G-3 `/media`** — `case_key`·`kind`·`role`·`images_only` 필터. 비면 **왜 비었는지** 말한다
- [x] **G-4 `report_image` → ImageContent** (실측 `mimeType=image/png`). mp4 는 모델이
      못 보므로 **거절하고 peak png 를 권한다**(`path` 를 주면 `role` 로 걸러선 안 된다 —
      그러면 '그림이 없다' 는 엉뚱한 까닭을 댄다. 실측으로 그랬다)
- [x] **G-5 `report_compare`** — 지표 표(TextContent) + 케이스별 **ImageContent**.
      실측: `['TextContent','TextContent','ImageContent',…]` 이미지 3장
- [x] **G-6 장수 상한 8** — 넘으면 **뺀 수를 말하고** 좁히는 법을 알려 준다
- [x] **G-7 프런트 이미지 갤러리** — 케이스 필터 + 격자. blob URL 을 **해제**한다(안 하면
      탭을 오래 열어 둘수록 샌다). `<img>` 로만 띄운다(`svgBlobUrl` 과 같은 규율).
      영상은 목록만(브라우저는 보지만 모델은 못 본다)
- [x] **분석 블록 탭** — 블록별 하위 `summary` 접기. `★미계산` 을 빨갛게 적는다
