# DF 2차 ④ — 보고서용 묶음 출력(DF-13) 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-13 이고 설계안 `df-request-1117.design.md` 의 ④ 단계다. 체크리스트 `df-report-bundles-1122.checklist.md`
· 맥락 `df-report-bundles-1122.context-notes.md`. 요청서의 검증 사례(과제 이름 · 영상 이름)는 옮기지 않는다 — 같은 꼴의 합성 사례로 잰다.

## 0. 받은 결정(사용자 11-21 · 11-22)
- 이름표 — 설계안 3절 그대로(11-21 「표 그대로 승인」). 이 단계의 이름은 MCP `build_report_bundle` · `report_bundle` · `report_bundle_diff`,
  REST `POST /bundles` · `GET /bundles/{id}` · `GET /campaigns/{id}/bundles/latest`. 표는 `report_bundles` · `report_bundle_items`, 항목 칸은
  요청서 표 그대로 `item_key` · `value` · `unit` · `source_path`.
- 차례 · 확인(11-22 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」) — 멈춰 확인받지 않고 짓는다. 내가 고른 읽기는 7절에
  모아 보고에서 알린다.
- 경계(요청서) — HTML · 영상 렌더는 ReportArchive · 웹 디자인 쪽 몫이다. DynaForge 는 값과 그림 재료만 낸다.

## 1. 짓는 것
| 겉 | 이름 | 하는 일 |
|---|---|---|
| REST · MCP(새) | `POST /bundles` · `build_report_bundle` | 캠페인 하나 이상 · 묶음 명세 · 기준 시각으로 묶음을 짓는다. `bundle_id` 를 주면 그 주소의 다음 판(숫자가 같으면 판을 올리지 않는다) |
| REST · MCP(새) | `GET /bundles/{id}` · `report_bundle` | 한 판(기본 마지막) — 머리 줄 · 표 · 그림 · 출처 · 앞 판 대비 바뀐 숫자. 항목(숫자마다 출처 경로)은 쪽으로 |
| REST(새) | `GET /campaigns/{id}/bundles/latest` | 그 캠페인을 담은 묶음 가운데 가장 늦게 지은 판. MCP 는 `report_bundle(campaign_id=…)` 로 같은 것을 부른다 |
| REST · MCP(새) | `GET /bundles/{id}/diff` · `report_bundle_diff` | 두 판 사이 바뀐 숫자(더해짐 · 빠짐 · 값 바뀜). 기본은 마지막 판과 그 앞 판 |
화면(콘솔)은 이 단계에 없다.

## 2. 표(마이그레이션 `0024_report_bundles`)
- `report_bundles` — 판 하나가 한 행. `id`(큰 정수) · `bundle_id`(ULID — 주소) · `version`(1 부터) · 유일(`bundle_id` · `version`) ·
  `created_by` · `created_at` · `label` · `campaign_ids`(JSONB) · `spec`(JSONB) · `as_of` · `basis`(JSONB — 수치 기준 줄) · `tables`(JSONB) ·
  `figures`(JSONB) · `sources`(JSONB) · `changes`(JSONB — 앞 판 대비) · `citation`(JSONB — C1 공용 꼴).
- `report_bundle_items` — 숫자 하나가 한 행. `id` · `bundle_row_id`(위 표 · 지우면 같이) · `item_key` · `value`(실수) · `unit` · `source_path`.
  색인(`bundle_row_id` · `item_key`).

## 3. 묶음 명세(`spec`)와 기준 시각
- `tables` — 목록, 항목은 `{kind, …}`. 이 단계의 종류 셋(⑤ 가 각도 통계 · 피크 표 · 여유 등을 더한다).
  - `runs` — 넣은 런마다 `run_key` · `doe` · `pitch` · `roll` · `config_generation` · 판정(`valid` · `warn`) · 리포트 id. 숫자 항목은 `pitch` ·
    `roll`.
  - `case_metrics` — 넣은 런의 케이스마다 `max_stress` · `max_g` · `max_disp` · `min_safety_factor`(`metrics` 로 고른다 · 기본 넷).
  - `part_peaks` — 넣은 런의 케이스 × 파트마다 피크(`metrics` 는 ReportArchive 내보내기와 같은 표 — `peak_stress` · `peak_strain` · `peak_g` ·
    `peak_disp` · `peak_principal` · `min_principal` · `peak_vm_strain`, 기본 `peak_stress` · `peak_g`) · `parts`(정수 목록 · 없으면 모든 파트).
- `figures` — `{roles: [...], kinds: ["svg", "png"]}`(없으면 그림을 싣지 않는다). 넣은 런의 리포트 매체 가운데 그 역할 · 종류인 것을 싣는다 —
  파일 id · 경로 · 케이스 · 바이트 · sha256(세션 파일의 값 · 없으면 그 자리에서 잰다).
- `include_invalid` — 참이면 제외 까닭이 있는 런도 넣는다(기본 거짓 — 건강 표와 같다).
- `as_of`(기준 시각) — 그 시각까지 받은 리포트만 넣는다(`ingested_at` ≤ `as_of`). 뒤에 받은 런은 제외 까닭 `after_as_of`. 없으면 지은 시각.
- 모르는 열쇠 · 모르는 종류 · 모르는 지표는 422(② · ③ 과 같다).

## 4. 수치 기준 줄(`basis`)과 출처
- `basis` — 캠페인마다 유효 n / 전체 N · 제외 까닭별 수(건강 표 머리 줄과 같은 셈 + `after_as_of`) · 설정 세대 분포 · 문턱 묶음 이름표 ·
  단위(아래)와 한 줄 글(`line`).
- 단위 — 지표마다 ReportArchive 내보내기 표(`analysis/ndjson.py` — ton-mm-s 관례: 응력 MPa · 가속 G · 변위 mm)를 쓴다(두 번째 소비자 —
  표를 한 곳에 둔다). 리포트가 밝힌 단위계 id 들을 `basis.units.unit_systems` 에 싣는다.
- 항목 — `item_key` 는 `<표 종류>/<캠페인 id>/<run_key>/<case_key>[/<파트>]/<지표>`, `source_path` 는
  `report:<id>/case:<case_key>[/part:<pid>]/<지표>` — 숫자마다 리포트 · 케이스 · 지표까지 거슬러 간다(요청서 수용 기준). 응답 항목에는
  `source_path` 를 푼 `source` 칸도 싣는다.
- `sources` — 넣은 리포트(report_id · run_key · case 수) · 그림 파일 · 문턱 묶음 이름표 · 파트 짝 표 · 기준값 판(이 단계는 null — ⑤).
- `citation` — C1 공용 꼴 `{source_platform: "dynaforge", source_kind: "dynaforge_bundle", source_id: <bundle_id>, source_version: <판>,
  scope: {campaign_ids}}`. ReportArchive 는 이 꼴로 인용한다(RA-02).

## 5. 판 규칙
- `bundle_id` 없이 지으면 새 주소의 1 판. 주면 그 주소의 마지막 판과 견준다 — 캠페인 · 명세가 다르면 422(주소는 한 질문이다), 항목 · 그림 ·
  기준 줄이 같으면 판을 올리지 않고 마지막 판을 `unchanged: true` 로 돌려준다, 다르면 다음 판과 `changes`(더해짐 · 빠짐 · 값 바뀜 — 바뀐 숫자
  목록)를 남긴다.
- 남의 캠페인 · 남의 묶음은 404(주인 대조 — 캠페인과 같다).

## 6. 시험
- 새 `tests/test_campaign_bundles.py` — 명세 받기(모르는 열쇠 · 종류 · 지표 422 · 남의 캠페인 404) · 1 판 짓기(표 셋 · 항목 수 · 기준 줄) ·
  같은 숫자로 다시 지으면 판 그대로 · 런 하나를 대체하면 2 판과 빠진 숫자 · 리포트 값을 바꾸면 값 바뀜 · diff · latest · 기준 시각 ·
  그림 sha256 · 남의 묶음 404 · 항목 상한.
- 검증 사례(합성 — 요청서 「영상이 읽던 숫자 JSON 과 같은 값」) — 런 둘의 캠페인에서 `case_metrics` 항목 값이 `/reports/{id}/cases` 의 값과
  같고, 항목의 `source_path` 를 따라가면 그 리포트 · 케이스 · 지표에 닿는다.
- MCP 계약(도구 100 → 103 · 인자 계약 고정 파일) · 선언 시험(capabilities 경로) · 변이(받기 · 판 규칙 · 항목 · 기준 줄 줄마다).

## 7. 고른 읽기(묻지 않았다 — 보고에서 알린다)
- 1 — 숫자가 같으면 판을 올리지 않는다(「결과가 바뀌면 같은 주소에서 새 판」). 다시 지은 시각은 남기지 않는다.
- 2 — 한 주소는 캠페인 · 명세가 같아야 한다. 명세를 바꾸려면 새 주소다(판의 바뀐 숫자가 명세 변화와 섞이지 않게).
- 3 — 표 종류는 지금 있는 사실(런 · 케이스 롤업 · 파트 피크)만. 각도 통계 · 피크 표 · 여유 · 자리 표는 ⑤ 의 함수가 서면 종류로 더한다.
- 4 — 단위는 ReportArchive 내보내기와 같은 ton-mm-s 표로 붙인다. 리포트가 다른 단위계를 밝혀도 값을 환산하지 않는다(단위계 id 를 싣는다).
- 5 — 그림은 리포트가 이미 가진 매체(svg · png)를 인용한다 — 새로 그리지 않는다(경계 줄). 영상(mp4)은 싣지 않는다(요청서 함정 줄 — 리포트의
  영상은 보고에 못 쓴다).
- 6 — 인용 꼴의 `source_kind` 는 `dynaforge_bundle`(리포트의 `dynaforge_report` 와 나란히 — 새 이름).
- 7 — 한 판의 항목은 200,000 개까지(넘으면 413 · 명세를 좁히라고 말한다). 지금 가장 큰 캠페인 셈은 ⑤ 에서 실측한다.
- 8 — `diff` 경로(`GET /bundles/{id}/diff`)는 설계안 표에 없던 경로다. MCP `report_bundle_diff` 가 부를 자리라 더했다.

## 8. 차례
- 마이그레이션 → 모델 → 명세 받기 · 순수 함수(`campaigns/bundles.py` — 항목 짓기 · 견주기 · 기준 줄) → 서비스 · REST 넷 → MCP 셋 →
  글(TOOLS · SKILL · CLAUDE_DESKTOP · README · capabilities) → 시험 · 변이 → 올리기(dev DB 0024 · 스모크 · Drive 는 다음 바이너리 판과 함께).
