# DynaForge 개발 요청서 v1.0(11-17) — 2차 설계안 · 이름표(11-21 사용자 확인)

계획 `df-request-1117.plan.md` · 맥락 `df-request-1117.context-notes.md`. 1차(DF-14 · DF-01 틈 · D4 · D5 · RK-06)는 11-17 에 올렸다.
이 문서는 나머지(DF-01 캠페인 적재 · DF-02 ~ 13 · DF-15 나머지)의 개체 · 이름 · 차례 · 기대는 것을 적는다. **이름표와 「정할 것」 은 11-21 에
사용자가 확인했다**(6절) — 단계 계획에서는 칸과 검증 사례만 확인받는다. 요청서의 검증 사례(과제 이름 · PC 경로)는 이 문서에 옮기지
않는다.

## 1. 놓을 자리(D1 · C5 — 사용자 결정 문서)
- 해석 결과 원본과 캠페인 조회 함수는 DynaForge 하나에 둔다. ReportArchive 는 묶음 id 만 인용한다(동기화 칸 없음).
- 차례 — ① DF-01 캠페인 적재 → ② DF-02 출처 · DF-03 유효성 → ③ DF-04 추출 완전성 · 삭제 관문 → ④ DF-13 묶음 → ⑤ DF-05 · 06 · 08 ~ 12 →
  ⑥ DF-07 · DF-15 나머지. 단계마다 계획 · 이름표 · 검증 사례를 따로 확인받고 올린다.

## 2. 개체(새 표 — 마이그레이션은 단계마다 하나)
| 표 | 칸(요청서 제안 바탕) | 단계 |
|---|---|---|
| `campaigns` | id · name · project · dev_rev · analysis_method · analysis_target · doe_strategy · drop_height_mm · duration_ms · thickness_axis · impactor(질량 g · 높이 mm · KE mJ) · created_by · created_at | ① |
| `campaign_runs` | campaign_id · run_key(캠페인 안 유일 — `stcx:<잡 id>:<DOE>`) · report_id(거절된 런은 null) · doe · pitch · roll · content_sha256 · ingest_state(받음 · 건너뜀 · 거절) · reject_reason · ingested_at | ① |
| 〃(칸 더함) | provenance(JSONB — 래퍼 · 처방 · 설정 sha · SIF · tool_commit …) · config_generation · superseded_by · validity · health(JSONB) | ② |
| 〃(칸 더함) | extraction(JSONB — d3plot 상태 수 · peak_source · fields_extracted · d3plot_retained · deleted_at) | ③ |
| `campaigns`(칸 더함) | required_extractions · health_thresholds · frame_offset · pair_rule(JSONB) | ② ~ ⑤ |
| `campaign_part_groups` | campaign_id · group_key · label · part_ids · part_key | ⑤ |
| `criteria_bindings` | part_id 또는 group_key · failure_mode · metric_axis · criterion_value · unit · source_platform · source_record_id · version(D7) | ⑤ |
| `part_maps` | map_id · from_model · to_model · rows(a_pid · b_pid · basis · center_dist_mm · size_rel_diff · title_token_jaccard · role) | ⑤ |
| `campaign_sites` · `campaign_site_metrics` | site_id · face · col · row · x_mm · y_mm · under_category · impactor / site_id · part · metric · value · time_ms · elem_id · ratio | ⑤ |
| `report_bundles` · `report_bundle_items` | bundle_id · 판 · 만든 시각 · 수치 기준 줄 · 출처(C1 공용 꼴 `{source_platform, source_kind, source_id, source_version, scope}`) / item_key · 값 · 단위 · 출처 경로 | ④ |

- 리포트 · 케이스 · 파트 사실 표는 지금 것을 그대로 쓴다 — 캠페인 집계는 그 위에서 셈하고, 각도 사실 표를 따로 굳힐지는 ⑤ 에서 실측(1,000 런
  셈 시간)으로 정한다.
- run 하나 = 리포트 하나가 기본이다. 지금 리포트 표에 칸을 넓히지 않고 `campaign_runs` 에 둔다 — 거절된 런(리포트 없음)도 행이 남아야 받음 +
  건너뜀 + 거절 = 목록 수가 맞는다.

## 3. 이름표 — 요청서 제안 → 우리 제안
우리 MCP 꼴 — 읽기는 명사가 앞(`report_*` · `campaign_*`), 쓰기는 동사가 앞(`create_` · `set_` · `attach_` · `ingest_`), 비교는 `compare_*`.
REST 는 kebab 이고 콜론 꼴이 없다. 「그대로」 가 아닌 줄만 까닭을 적는다.

| 항목 | 요청서 MCP | 우리 제안 | 요청서 REST | 우리 제안 |
|---|---|---|---|---|
| DF-01 | `campaign_create` | `create_campaign`(쓰기) | `POST /campaigns` | 그대로 |
| DF-01 | `campaign_ingest_manifest` | `ingest_campaign_manifest`(쓰기 — 런 목록을 먼저 올린다) | `POST /campaigns/{id}/runs:batchIntake` | `POST /campaigns/{id}/runs` |
| DF-01 | `campaign_ingest_status` | 그대로(C4 게이트웨이가 이 이름으로 읽는다) | `GET /campaigns/{id}/ingest-status` | 그대로 |
| DF-01 | intake 폼 `campaign_id` · `run_key` | 그대로 | — | — |
| DF-02 | `campaign_provenance` | 그대로 | `GET /campaigns/{id}/provenance` | 그대로 |
| DF-02 | 필터 `config_generation` | 그대로 | — | — |
| DF-03 | `run_health` | `report_health`(받는 것이 report_id — `report_*` 꼴) | `GET /reports/{id}/health` | 그대로 |
| DF-03 | `campaign_health_table` | 그대로 | `GET /campaigns/{id}/health` | 그대로 |
| DF-03 | 인자 `include_invalid` | 그대로 | — | — |
| DF-04 | `run_extraction_status` | `report_extraction` | `GET /reports/{id}/extraction` | 그대로 |
| DF-04 | `deletion_clearance` | `campaign_deletion_clearance`(캠페인 단위) | `GET /campaigns/{id}/deletion-clearance` | 그대로 |
| DF-04 | (설정) | `set_campaign_required_extractions` | `PUT /campaigns/{id}/required-extractions` | 그대로 |
| DF-05 | `campaign_angle_stats` · `campaign_angle_table` | 그대로 | `GET …/angle-stats` · `…/angle-table` | 그대로 |
| DF-05 | `part_group_define` | `set_campaign_part_groups`(쓰기) | `PUT /campaigns/{id}/part-groups` | 그대로 |
| DF-06 | `campaign_peak_table` | 그대로 | `GET /campaigns/{id}/peaks` | 그대로 |
| DF-07 | `campaign_hotspot_sites` | 그대로 | `GET /campaigns/{id}/hotspot-sites` | 그대로 |
| DF-08 | `campaign_part_margin` | 그대로 | `GET /campaigns/{id}/part-margin` | 그대로 |
| DF-09 | `campaign_sphere_map` | 그대로 | `GET /campaigns/{id}/sphere-map` | 그대로 |
| DF-10 | `impact_site_table` · `impact_site_map` | `campaign_site_table` · `campaign_site_map`(자리도 캠페인 단위) | `GET …/sites` · `…/site-map` | 그대로 |
| DF-11 | `part_map_import` | `import_part_map`(쓰기) | `POST /part-maps` · `GET /part-maps/{id}` | 그대로 |
| DF-11 | `campaign_compare_revisions` | `compare_campaigns`(`compare_reports` 와 같은 꼴) | `GET /campaign-compare?a=&b=&part_map=` | `GET /campaigns/compare?a=&b=&part_map=` |
| DF-12 | `config_pair_compare` | `compare_config_pairs` | `GET /campaigns/{id}/config-pairs` | 그대로 |
| DF-12 | `pair_rule_set` | `set_campaign_pair_rule` | `PUT /campaigns/{id}/pair-rule` | 그대로 |
| DF-13 | `report_bundle_build` · `_get` · `_diff` | `build_report_bundle` · `report_bundle` · `report_bundle_diff` | `POST /bundles` · `GET /bundles/{id}` · `GET /campaigns/{id}/bundles/latest` | 그대로 |
| DF-14 | `deck_eid_collision_check` | 만들지 않았다 — modelmeta 칸 둘(1차)로 갈음 | `GET …/files/{fid}/id-audit` | 만들지 않았다 — inspect `meta.modelmeta` |
| DF-15 | `session_describe` | 새 도구 없이 `get_session` 응답에 칸 | `GET /sessions/{id}/describe` | 새 경로 없이 세션 응답에 칸 |
| DF-15 | `part_rename` | `rename_session_part`(쓰기) | `PATCH /sessions/{id}/parts/{pid}` | 그대로 |

- 칸 이름은 요청서 표의 것을 그대로 쓴다(D7 의 `source_platform` · `source_record_id` · `version`, C1 의 인용 꼴, D5 의 `environment` 포함).
  예외는 DF-14 처럼 이미 있는 칸이 같은 뜻을 내는 경우다.

## 4. 다른 곳에 기대는 것(꼴을 받아야 칸이 선다)
- DF-02 · 03 · 04 입력 — KooChainRun KC-01(`return_manifest.jsonl`) · KC-02(건강 요약) · KC-05(삭제). 이 박스에 그 리포가 없어 꼴을 보지 못했다.
- DF-04 `peak_source` · `states_read/states_total` — 리포트 생성기가 내야 한다(지금 리포트에 없다).
- DF-08 기준값 — MatNexus MN-01(재질 강도) · 자주검증 Datahub(부품 시험 합격선, D7).
- DF-09 격자 대조 — 요청 쪽 스크립트의 격자값 표본(같은 입력 · 같은 보간 규칙)을 받아야 「일치」 를 잰다.
- DF-10 실측 footprint — 생성기가 내거나, 우리가 가진 K 파일로 덱에서 잰다(새 기능 — 아래 정할 것 6).
- DF-13 인용 kind — 심의 엔진 DL-01 `ref.kind` 목록(C1 — DynaForge 리포트는 `dynaforge_report`).

## 5. 정할 것(사용자)
1. 캠페인 개체 — 새 표 `campaigns` · `campaign_runs`(권고 — 거절된 런도 행이 남고 런 칸이 리포트 표를 넓히지 않는다) 대 지금 리포트 칸
   (`project` · `dev_rev` · `variation`)으로만 묶기.
2. 같은 `run_key` 에 다른 sha256 이 오면 — 거절(권고 — 판을 바꾸려면 새 설정 세대로) · 새 판으로 받고 옛 것에 `superseded_by` · 덮어쓰기.
3. 큰 리포트(수백 MB JSON) 파싱 메모리 — 실측하지 않았다. ① 에서 재고, 상한(RF-A-3 와 같은 갈래)을 정한다.
4. 건강 문턱 기본값 — 요청서 제안(에너지비 ≤ 1.05 · HG/IE < 10 % · 추가 질량 0.5 % 넘으면 warn · 미끄럼 에너지는 문턱 없음)을 캠페인 기본으로
   둘지.
5. 이름표(위 3절) — 27 줄 가운데 요청서 이름을 바꾸거나 새로 둔 줄 열여섯(그 가운데 둘 — DF-14 와 DF-15 의 describe — 은 새 도구 · 경로를 만들지 않는 줄).
6. DF-10 footprint — 우리가 K 파일로 잴지(덱이 있는 리포트만) · 생성기를 기다릴지.
7. 묶음 적재의 길 — 런마다 intake(올리는 쪽이 파일을 보낸다 — 권고, 지금 길 그대로) 대 서버가 경로에서 당겨 오기(7-1 귀환을 넓힌다).

## 6. 받은 결정(사용자 — 11-20 · 11-21)
- 1 · 2 · 7(11-20) — 새 표 `campaigns` · `campaign_runs` · 같은 `run_key` 에 다른 sha256 은 거절 · 런마다 intake. ① 로 지어 11-21 에
  올렸다(`df-campaign-intake-1120.plan.md`).
- 3(11-20) — 「줄만 세운다」. 상한 숫자는 그대로 두고 리포트 받기를 한 번에 하나씩 줄 세운다.
- 4(11-21) — 「요청서 값을 기본으로」. 에너지비 ≤ 1.05 · HG/IE < 10 % · 추가 질량 0.5 % 넘으면 warn · 미끄럼 에너지는 문턱 없음을 캠페인
  기본으로 두고, 캠페인마다 바꿀 수 있게 한다. 응답에는 판정에 쓴 문턱 묶음을 같이 싣는다. 요청서 안에서 HG/IE 문턱을 「폐기된 값」 이라 적은
  줄과 어긋나 보이는 것은 답신에서 요청 쪽에 묻는다(`docs/requests/df-request-reply-2026-11-21.md` 4절 4).
- 5(11-21) — 「표 그대로 승인」. 남은 단계(② ~ ⑥)의 도구 · 경로 · 칸 이름을 3절 그대로 확정한다. 단계 계획에서는 칸과 검증 사례만 확인받는다.
- 6(11-21) — 「생성기에 청하고 기다린다」. footprint 는 리포트를 만드는 쪽이 재서 내는 값으로 두고, 우리는 지금처럼 「합성」 표지와 경고를
  그대로 싣는다. 덱에서 재는 기능은 짓지 않는다. 그때까지 자리 지도는 합성 사각형에 경고가 붙은 채다.
- 진행(11-21) — 「② 계획부터 쓴다」. 받는 꼴은 요청서 표대로 세우고, 만드는 쪽의 실제 꼴(KC-01 · KC-02)이 오면 맞춘다. 꼴이 다르면 받는 쪽을
  다시 손봐야 한다.
- 동시 올리기(11-21) — 「② 계획에 넣어 고친다」. 줄에 서 있는 동안 연결을 놓도록 고치고, 워커의 후처리 반입 길은 트랜잭션이 갈리지 않게 따로
  손본다. 고칠 자리와 시험은 ② 계획에 실어 확인받는다.
- 차례(11-21 — 위 둘보다 뒤에 받았다) — 미룬 결함 목록의 열린 줄 스물을 여러 판에 나눠 먼저 고친다(「열린 줄 스물 전부」 —
  `deferred-defects-round3-1121.plan.md`). 고른 문장이 「DF ② ~ ⑥ 은 그동안 멈춥니다」 라, ② 계획 쓰기와 동시 올리기 고침도 그 판들 뒤로 간다.
- 요청 쪽 답신(D-3 · 11-21 「답신 문서를 쓴다」) — `docs/requests/df-request-reply-2026-11-21.md`. 전달은 사용자가 한다.
- 차례 고침(11-22) — 「② 계획을 지금 먼저」 를 골랐다. 2판 고침 전에 ② 계획을 쓰고 결함 판과 번갈아 진행한다(위 「차례」 줄을 갈음한다). 같은 날
  받은 글 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」 — 단계마다 멈춰 확인받지 않고 지어 올리고, 검증은 사용자가 cae00 에서
  한다. ② 계획은 `df-provenance-health-1122.plan.md`.
- ② 이름 · 판정(11-22) — 문턱 쓰기는 `set_campaign_health_thresholds` · `PUT /campaigns/{id}/health-thresholds`. 첫 KE 0 이하 invalid · ½mv² 와
  10 % 넘게 다르면 warn · 자체 접촉 에너지 −100 mJ 아래 warn. 건강 수치가 없는 런은 invalid(`health_missing`)로 기본 제외.
