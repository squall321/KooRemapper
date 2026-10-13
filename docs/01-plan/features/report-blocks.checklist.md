# Checklist — 리포트 블록 전수 노출

설계: `report-blocks.plan.md` · 맥락: `report-blocks.context-notes.md`

## A. 실측·기준
- [x] **A-1 차집합 전수 조사** — sphere 0 · deep 11 · impact 18 (실제 리포트 6개)
- [ ] A-2 그 차집합을 **회귀로 고정** — 새 키가 생기면 빨개진다

## B. 일반 블록 접근
- [ ] B-1 `parser.list_blocks(data)` — 이름·형태·크기·`read_by_normalizer` 여부
- [ ] B-2 `parser.get_block(data, name, path=None)` — 하위 경로 선택
- [ ] B-3 크기 가드 — 49MB 리포트의 `results`(625행) 같은 블록
- [ ] B-4 API `GET /reports/{id}/blocks`, `/blocks/{name}`
- [ ] B-5 MCP `report_blocks`, `report_block`

## C. 일급 — 핫스팟·군집
- [ ] C-1 `parser.hotspot_clusters(data)` (deep) — 파트·criterion 별 군집
- [ ] C-2 `parser.behavior_clusters(data)` (impact) — 아키타입·라벨·특징
- [ ] C-3 API `/hotspots`, `/clusters` + MCP 도구 둘
- [ ] C-4 프런트 표(핫스팟 상위 군집 · 군집 아키타입)

## D. 시계열 비대칭
- [ ] D-1 `part_series` 의 deep 계열을 7종으로 넓힌다
- [ ] D-2 회귀 — 7종이 다 나오고 없는 것은 빈 dict 다

## E. 관문
- [ ] E-1 backend 전수 · 회귀 전수
- [ ] E-2 라이브 스택에서 실제 리포트로 끝까지
