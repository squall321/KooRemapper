# DF 2차 ③ — 추출 완전성 표시 · d3plot 삭제 관문(DF-04) 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-04 이고 설계안 `df-request-1117.design.md` 의 ③ 단계다. 체크리스트
`df-extraction-clearance-1122.checklist.md` · 맥락 `df-extraction-clearance-1122.context-notes.md`. 요청서의 검증 사례(과제 이름 · PC 경로)는
옮기지 않는다 — 같은 꼴의 합성 사례로 잰다.

## 0. 받은 결정(사용자 11-21 · 11-22)
- 이름표 — 설계안 3절 그대로(11-21 「표 그대로 승인」). 이 단계의 이름은 MCP `report_extraction` · `campaign_deletion_clearance` ·
  `set_campaign_required_extractions`, REST `GET /reports/{id}/extraction` · `GET /campaigns/{id}/deletion-clearance` · `PUT
  /campaigns/{id}/required-extractions`. 칸 이름은 요청서 표 그대로다(`extraction` 의 `d3plot_states_total` · `d3plot_states_read` ·
  `peak_source` · `fields_extracted` · `d3plot_retained` · `d3plot_deleted_at`, 캠페인의 `required_extractions` = `[{field, parts, states}]`).
- 차례 · 확인(11-22 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」) — 단계마다 멈춰 칸 · 검증 사례를 확인받지 않고 짓는다. 짓고
  시험이 되면 main · dev · Drive 로 올리고, 검증은 사용자가 cae00 에서 돌린다. 이 계획에서 내가 고른 읽기는 7절에 모아 보고에서 알린다.
- 받는 꼴(11-21 「② 계획부터 쓴다」 와 같은 규칙) — 요청서 표대로 세우고 만드는 쪽의 실제 꼴(KooChainRun KC-01 귀환 목록 · KC-05 삭제)이 오면
  맞춘다. 모르는 열쇠는 버리지 않고 422 로 돌린다(② 와 같다).

## 1. 짓는 것
| 겉 | 이름 | 하는 일 |
|---|---|---|
| REST · MCP(고침) | `POST /campaigns/{id}/runs` · `ingest_campaign_manifest` | 런마다 `extraction` 을 더 받는다(보낸 칸만 맞춘다 — 지금 규칙 그대로) |
| REST · MCP(고침) | `POST /campaigns` · `create_campaign` | `required_extractions` 를 더 받는다 |
| REST · MCP(새) | `PUT /campaigns/{id}/required-extractions` · `set_campaign_required_extractions` | 캠페인의 필수 추출 목록을 통째로 바꾼다(빈 목록이면 지운다) |
| REST · MCP(새) | `GET /campaigns/{id}/deletion-clearance` · `campaign_deletion_clearance` | 머리 줄(허가 · 보류 · 이미 지움 수) · 런마다 허가 / 보류와 빠진 항목 |
| REST · MCP(새) | `GET /reports/{id}/extraction` · `report_extraction` | 리포트 하나의 런 추출 · 피크 출처 · 그 런의 삭제 허가 |
| REST(고침) | 피크를 돌려주는 리포트 응답 열 | `peak_provenance` 칸(`peak_source` · `states_read` · `states_total` · `peak_may_be_missed`)을 싣는다 — 5절 |
화면(콘솔)은 이 단계에 없다. 삭제 허가는 **조회만** 한다 — 지우는 것은 KooChainRun(KC-05)이다(요청서 수용 기준).

## 2. 표(마이그레이션 `0023_campaign_extraction`)
- `campaign_runs` 에 칸 하나 — `extraction`(JSONB · null 허용).
- `campaigns` 에 칸 하나 — `required_extractions`(JSONB · null 이면 정하지 않음).
- 허가 · 피크 표지는 저장하지 않고 읽을 때 센다(② 의 판정과 같다) — 필수 목록을 바꾸면 곧바로 다시 갈린다.

## 3. 받는 꼴(요청서 표 그대로 — 모르는 열쇠는 422)
- `extraction` — `d3plot_states_total`(0 이상 정수) · `d3plot_states_read`(0 이상 · total 이하) · `peak_source`(`binout` · `elout` ·
  `d3plot_full` · `d3plot_sampled`) · `fields_extracted`(목록 — 글 하나는 `{field: 그 글}` 과 같다, 객체는 `field`(글) · `parts`(정수 목록 ·
  없으면 「모든 파트」) · `states`(`all` · `sampled` · 없으면 런의 상태 수로 정한다 — read = total 이면 all)) · `d3plot_retained`(참 · 거짓) ·
  `d3plot_deleted_at`(ISO 시각 글).
- `required_extractions` — 목록, 항목은 `field`(글 · 필수) · `parts`(정수 목록 · 없으면 「모든 파트」) · `states`(`all` · `sampled` · 기본
  `all`). 같은 field · parts · states 가 둘이면 422.
- field 이름은 자유 글이다(요청서의 보기 「판 변형률장 · 부품 응력장」) — 견줄 때 앞뒤 공백을 떼고 대소문자를 가리지 않는다.

## 4. 삭제 허가 규칙(런마다 · 읽을 때)
- 캠페인에 필수 목록이 없으면(null · 빈 목록) 모든 런이 `hold`(`required_extractions_unset`) — 무엇을 지켜야 할지 모르면 지워도 된다고 하지
  않는다(7절 읽기 1).
- 리포트가 없는 런 — `hold`(`no_report`). `extraction` 이 없는 런 — `hold`(`extraction_missing`).
- 이미 지운 런(`d3plot_retained` 가 거짓이거나 `d3plot_deleted_at` 이 있다) — `deleted`. 빠진 필수 항목이 있으면 같이 싣는다(지운 뒤 다시 못
  뽑는다 — 요청서 함정 줄).
- 필수 항목 하나는 같은 field 의 추출이 있고, 추출의 파트가 필수의 파트를 덮고(「모든 파트」 는 무엇이든 덮는다 · 필수가 「모든 파트」 면 추출도
  「모든 파트」 여야 한다), 필수가 `all` 이면 추출도 `all` 일 때 채워진다. 하나라도 비면 `hold` 와 빠진 항목 목록(`missing` — 항목마다 까닭
  `field_missing` · `parts_missing`(빠진 파트) · `states_sampled`).
- 다 채워지면 `allow`. 머리 줄 — 전체 · allow · hold · deleted 수와 까닭별 수.

## 5. 피크 출처 표지(`peak_provenance`)
- 값의 출처는 그 리포트를 가진 캠페인 런의 `extraction` 뿐이다 — 리포트 생성기가 아직 내지 않는다(설계안 4절). 캠페인 밖 리포트 · 추출이 없는
  런은 네 칸이 null 이고 `known: false`.
- `peak_may_be_missed` — `peak_source` 가 `d3plot_sampled` 거나, `d3plot_*` 인데 `states_read < states_total` 이면 참. `binout` · `elout` 은
  시간 이력 출력이라 거짓. 출처를 모르면 null.
- 싣는 응답 — `GET /reports/{id}`(요약 · 최악 경우) · `/query` · `/cases` · `/cases/{key}` · `/parts` · `/directional` · `/angle-stats` ·
  `/hotspots` · `/findings` · `/scatter`(7절 읽기 3). MCP 는 REST 응답을 그대로 넘기므로 같은 칸이 보인다.

## 6. 시험
- 새 `tests/test_campaign_extraction.py` — 받는 꼴(모르는 열쇠 · 범위 · peak_source 값 · 글 / 객체 fields) · 필수 목록 PUT(통째 · 빈 목록 지움 ·
  겹침 422) · 허가 규칙 넷(unset · no_report · extraction_missing · deleted) · 필드 · 파트 · 상태 빠짐 · allow · 주인 대조(남의 캠페인 404).
- 검증 사례 둘(합성) — ① 201 상태 중 40 상태만 읽은 `d3plot_sampled` 런의 `report_extraction` 과 피크 응답에 `peak_may_be_missed: true` ·
  `states_read 40` · `states_total 201`. ② 필수 「판 변형률장」(states all)이 빠진 런은 `hold` · 빠진 목록에 그 field.
- MCP 계약(도구 97 → 100 · 인자 계약 고정 파일) · 선언 시험(capabilities 경로) · 변이(받기 · 규칙 · 표지 줄마다).

## 7. 고른 읽기(묻지 않았다 — 보고에서 알린다)
- 1 — 필수 목록을 정하지 않은 캠페인은 모든 런 `hold`(`required_extractions_unset`). 「허가」 를 기본으로 두면 목록을 안 쓴 캠페인에서 다시 못
  뽑는 d3plot 을 지우게 된다(요청서의 목적과 반대).
- 2 — `fields_extracted` 항목은 글 · 객체를 다 받는다. 요청서 표는 글 목록(「판 변형률장 · 부품 응력장」)인데 필수 목록은 parts · states 를
  갖는다 — 글이면 「모든 파트 · 런의 상태 수」 로 읽는다.
- 3 — 「피크를 돌려주는 모든 응답」 을 리포트 하나를 읽어 응력 · 변형률 · 힘의 최댓값을 내는 경로 열로 읽었다. 리포트 목록 · 파일 · 매체 · CAE
  경로에는 싣지 않는다.
- 4 — `peak_source` 가 `binout` · `elout` 이면 놓칠 수 있음이 거짓이다(시간 이력은 출력 주기마다 쓴다 — 요청서 함정 줄 `D3PART_LCDT_WINDOW_SKIP`
  은 d3part 창의 것이다).

## 8. 차례
- 마이그레이션 → 모델 → 받는 꼴 · 서비스(허가 규칙은 순수 함수 `campaigns/extraction.py`) → REST 셋 · 피크 표지 → MCP 셋 · 고침 둘 → 글(TOOLS ·
  SKILL · CLAUDE_DESKTOP · README · capabilities) → 시험 · 변이 → 올리기(dev DB 0023 · 스모크 · Drive 는 다음 바이너리 판과 함께).
