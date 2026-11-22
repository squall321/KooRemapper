# DF 2차 ② — 런 출처 · 유효성(DF-02 · DF-03) · 동시 올리기의 DB 연결 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-02 · DF-03 이고 설계안 `df-request-1117.design.md` 의 ② 단계다. 체크리스트
`df-provenance-health-1122.checklist.md` · 맥락 `df-provenance-health-1122.context-notes.md`. 요청서의 검증 사례(과제 이름 · PC 경로)는 옮기지
않는다 — 같은 꼴의 합성 사례로 잰다.

## 0. 받은 결정(사용자 11-21 · 11-22)
- 이름표 — 설계안 3절 그대로(11-21 「표 그대로 승인」). 이 단계의 이름은 MCP `campaign_provenance` · `report_health` · `campaign_health_table`,
  REST `GET /campaigns/{id}/provenance` · `GET /reports/{id}/health` · `GET /campaigns/{id}/health`, 필터 `config_generation`, 인자
  `include_invalid`. 칸 이름은 요청서 표 그대로다.
- 문턱 쓰기 — `set_campaign_health_thresholds` · `PUT /campaigns/{id}/health-thresholds`(11-22). `create_campaign` 도 같은 칸
  `health_thresholds` 를 받는다.
- 기본 문턱(11-21 「요청서 값을 기본으로」) — 에너지비 ≤ 1.05 · HG/IE < 10 % · 추가 질량 0.5 % 넘으면 warn · 미끄럼 에너지는 문턱 없음.
  캠페인마다 바꿀 수 있고 응답에 판정에 쓴 문턱 묶음을 싣는다.
- 그 밖 판정(11-22) — 첫 KE 가 0 이하면 invalid · ½mv² 와 10 % 넘게 다르면 warn(우리가 정한 값) · 자체 접촉 에너지가 −100 mJ 아래면 warn(요청서
  함정 줄의 값) · 비정상 종료 · NaN · 잘린 JSON 은 invalid. 모두 캠페인마다 바꿀 수 있다.
- 건강 수치가 없는 런(11-22) — invalid(`health_missing`)로 보고 기본 제외한다. `include_invalid=true` 로는 보인다.
- 동시 올리기(11-21 「② 계획에 넣어 고친다」) — 줄에 서 있는 동안 DB 연결을 놓고, 워커의 후처리 반입 길은 트랜잭션이 갈리지 않게 따로 둔다.
- 차례(11-22 「② 계획을 지금 먼저」 · 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」) — 단계마다 멈춰 확인받지 않고 짓는다. 짓고
  시험이 되면 main · dev · Drive 로 올리고, 검증은 사용자가 cae00 에서 돌린다. 그래서 이 계획의 칸 · 검증 사례는 여기 적은 대로 짓고 보고에서
  알린다.

## 1. 짓는 것
| 겉 | 이름 | 하는 일 |
|---|---|---|
| REST · MCP(고침) | `POST /campaigns/{id}/runs` · `ingest_campaign_manifest` | 런마다 `provenance` · `config_generation` · `superseded_by` · `health` 를 더 받는다(보낸 칸만 맞춘다 — 지금 규칙 그대로) |
| REST · MCP(고침) | `POST /campaigns` · `create_campaign` | `health_thresholds` 를 더 받는다 |
| REST · MCP(새) | `PUT /campaigns/{id}/health-thresholds` · `set_campaign_health_thresholds` | 캠페인의 문턱을 바꾼다 — 안 보낸 열쇠는 기본값 |
| REST · MCP(새) | `GET /campaigns/{id}/provenance` · `campaign_provenance` | 설정 세대 분포 · `mixed_config` · 출처가 빈 런 수 · 대체된 런 수 · 런마다 출처 |
| REST · MCP(새) | `GET /campaigns/{id}/health` · `campaign_health_table` | 머리 줄(유효 n / 전체 N · 제외 까닭별 건수) · 문턱 묶음 · 런마다 건강 수치와 판정 |
| REST · MCP(새) | `GET /reports/{id}/health` · `report_health` | 리포트 하나의 런 건강 · 판정(캠페인 주인이 아니면 캠페인 칸은 비운다) |
| REST · MCP(고침) | `GET /reports` · `find_reports` 의 `config_generation` | 그 설정 세대의 캠페인 런에 묶인 리포트만 |
| 받기 길(고침) | `/reports/intake` · `/sessions/{id}/reports` | 리포트 받기 줄(`_PARSE_LOCK`)에 서기 전에 커밋해 DB 연결을 놓는다 |

화면(콘솔)은 이 단계에 없다. `report_angle_stats` · `report_query` 는 리포트 하나(런 하나)를 읽으므로 `config_generation` 필터를 붙이지 않는다 —
캠페인 통계 도구(⑤)가 같은 거르기를 쓴다.

## 2. 표(마이그레이션 `0022_campaign_health`)
- `campaign_runs` 에 칸 넷 — `provenance`(JSONB) · `config_generation`(64 자) · `superseded_by`(128 자 — 같은 캠페인의 run_key) ·
  `health`(JSONB). 모두 null 허용이다.
- `campaigns` 에 칸 하나 — `health_thresholds`(JSONB · null 이면 기본값).
- 판정(`validity`)은 저장하지 않고 읽을 때 지금 문턱으로 센다 — 문턱을 바꾸면 곧바로 다시 판정된다. 설계안 2절 표의 `validity` 칸은 응답 칸이다.

## 3. 받는 꼴(요청서 표 그대로 — 모르는 열쇠는 422)
- `provenance` — `wrapper_name` · `wrapper_version` · `prescription_set` · `scenario_sha256` · `runner_config_sha256` · `deck_sha256` ·
  `include_sha256`(글 목록) · `solver`(열쇠가 요청서에 없어 글 · 숫자 값의 객체를 그대로 받는다) · `sif_version` · `deep_report_tool_commit` ·
  `deep_report_flags`(글 또는 글 목록) · `submitted_at`(ISO 시각 글).
- `config_generation`(사람이 붙이는 세대 이름표 · 64 자) · `superseded_by`(이 런을 대체한 런의 run_key).
- `health` — `normal_termination`(참 · 거짓) · `scheduler_state`(참고 글) · `energy_ratio_max` · `hg_over_ie_max`(비 — 0.10 이 10 %) ·
  `added_mass_pct_device` · `added_mass_pct_total`(백분율) · `ke0_measured` · `ke0_expected` · `contact_energy_min_mJ` · `nan_onset_ms`(없으면
  null) · `json_complete`(참 · 거짓).
- `health_thresholds` — `energy_ratio_max`(1.05) · `hg_over_ie_max`(0.10) · `added_mass_pct_max`(0.5) · `ke0_rel_tol`(0.10) ·
  `contact_energy_min_mJ`(−100). 미끄럼 에너지 열쇠는 없다(문턱이 없다).
- 만드는 쪽의 실제 꼴(KooChainRun KC-01 · KC-02)을 아직 보지 못했다 — 꼴이 다르면 받는 쪽을 다시 손본다(11-21 결정 문장). 모르는 열쇠를 버리지
  않고 422 로 돌려 어긋남이 바로 보이게 한다.

## 4. 판정 규칙
1. 리포트가 없는 런(pending · 리포트 없는 rejected) — `no_report` 로 제외한다. 판정은 `invalid`.
2. `health` 가 없으면 `health_missing` 으로 invalid. 있는데 `normal_termination` 이 비면 `termination_unknown` 으로 invalid(「Slurm 상태만으로
valid 금지」). 거짓이면 `abnormal_termination` 으로 invalid.
3. `json_complete` 거짓 → `json_incomplete` invalid · `nan_onset_ms` 가 있으면 `nan` invalid · `ke0_measured` ≤ 0 → `ke0_zero` invalid.
4. warn — `energy_ratio_max` > 문턱(`energy_ratio`) · `hg_over_ie_max` ≥ 문턱(`hourglass`) · 추가 질량(기기 값, 없으면 전체 값) >
문턱(`added_mass`) · `ke0_measured` 가 `ke0_expected` 와 상대 차이 > 문턱(`ke0_mismatch`) · `contact_energy_min_mJ` < 문턱(`contact_energy`).
수치가 없는 항목은 판정하지 않는다.
5. 상태 — invalid 까닭이 하나라도 있으면 `invalid`, 아니면 warn 까닭이 있으면 `warn`, 아니면 `valid`. 까닭은 모두 `reasons[]` 에 싣는다.
6. 통계 기본 제외(`include_invalid=false`) — invalid · `superseded_by` 가 있는 런(`superseded`) · 출처가 빈 런(`provenance_missing`). warn 은
넣는다. 머리 줄의 제외 까닭별 건수는 런 하나가 까닭 여럿이면 여럿에 센다 — 「제외된 런 수」 는 따로 준다.
7. `superseded_by` — 같은 캠페인의 run_key 여야 하고(목록을 다 맞춘 뒤 대조) 자기 자신 · 고리는 422 다.
8. 문턱 묶음 — 응답에 `values` · `ref`(`thr-` + 정렬한 JSON 의 sha256 앞 12 자) · 기본값에서 바뀐 열쇠를 싣는다. 런의 `thresholds_ref` 가 이
`ref` 다.

## 5. 동시 올리기 — 줄에 서기 전에 연결을 놓는다
- 자리 — `reports/services.py` 의 `ingest_report` 가 줄에 서기 전에 `db.commit()` 한다(엔진 세션은 트랜잭션이 끝나면 연결을 풀에 돌려준다 ·
  `expire_on_commit=False` 라 객체는 살아 있다). 두 라우트가 그 앞에서 만든 세션 · K 파일은 이미 커밋돼 있다 — 새로 굳는 것은 없다.
- 워커(`worker/postprocess_return.py`) — 잡 원장 칸을 고친 채 부르고 리포트와 같은 커밋으로 굳힌다. 그 길은 `keep_transaction=True` 로 불러 줄
  앞 커밋을 건너뛴다(트랜잭션이 갈리지 않는다). 워커는 다른 프로세스라 그 안에서만 줄이 선다.
- 시험 — 줄을 쥔 채 다른 받기가 기다리는 동안 풀의 빌린 연결 수가 늘지 않는다 · 작은 풀(크기 1 · 넘침 0)에서 동시 올리기 여럿이 다 된다 · 워커
  길은 커밋을 건너뛴다. 임시 스택에서 동시 40 건을 다시 잰다(11-20 에 500 이 23 건).

## 6. 검증 사례(시험 `tests/test_campaign_health.py` · `tests/test_report_parse_queue.py`)
1. 혼합 설정 — 세대 셋(옛 · 옛 · 새)을 섞은 목록에서 `campaign_provenance` 의 세대별 런 수 · `mixed_config: true` 가 맞고, 한 세대만이면 `false`
다.
2. 대체 — 같은 DOE 의 옛 런에 `superseded_by` 를 주면 기본 표에서 빠지고(`superseded`) `include_invalid=true` 로 보인다 · 없는 run_key · 자기
자신 · 고리는 422.
3. 출처가 빈 런은 기본 제외(`provenance_missing`)되고 제외 수가 머리 줄에 실린다.
4. 판정 사례 — 스케줄러가 COMPLETED 인데 정상 종료가 아닌 런 → invalid · 첫 KE 0 → invalid · 몸통이 빠진 런(KE 가 기대의 60 %) → warn · NaN 시작
시각이 있는 런 → invalid · 잘린 JSON → invalid · 에너지비 1.018 이지만 접촉 에너지 −150 mJ → warn · 추가 질량 기기 0.66 % · 전체 0.01 % → warn ·
HG/IE 0.12 → warn · 미끄럼만 큰 런 → valid · 건강 수치가 없는 런 → invalid(`health_missing`).
5. 문턱 — 기본 묶음과 `ref` · `set_campaign_health_thresholds` 로 HG/IE 문턱을 0.15 로 바꾸면 0.12 런이 valid 로 돌아오고 `ref` 가 바뀐다 ·
모르는 열쇠 422 · 숫자가 아니면 422.
6. 받는 꼴 — 모르는 열쇠(`provenance` · `health` 안)는 422 · 목록 다시 올리기에서 보낸 칸만 바뀐다(`health` 만 보내면 `provenance` 는 그대로 ·
null 은 비운다).
7. `report_health` — 캠페인 런의 리포트는 판정이 오고, 캠페인 밖 리포트는 `campaign: null` · `health_missing`. 같은 소속이 읽는 리포트는 캠페인
칸을 비운다.
8. `find_reports(config_generation=…)` — 그 세대의 런에 묶인 리포트만 · 남의 캠페인 런은 세지 않는다.
9. MCP 계약 — 새 도구 넷의 인자가 REST 와 같고 도구 수가 93 → 97 이다(`tests/test_mcp_tools_contract.py`).
10. 동시 올리기 — 5절의 시험 셋과 임시 스택 실측(시험 밖 · 숫자는 맥락 노트).

## 7. 하지 않는 것
- KooChainRun 매니페스트 · 건강 요약 파일을 그대로 읽기 — 꼴을 보지 못했다. 런 목록 JSON 의 칸으로 받는다.
- d3hsp · glstat 를 우리가 읽어 건강 수치를 셈하기 — 만드는 쪽이 낸다(요청서 입력이 KC-02 다).
- 캠페인 각도 통계(⑤) — 이 단계는 거르기 규칙(6절)과 그 머리 줄을 짓고, 통계 도구가 그것을 쓴다.
- 줄이 길면 503 으로 돌려보내기 — 연결을 놓으면 풀이 마르지 않는다. 기다리는 올리기는 제 파일 바이트를 쥔 채다(11-20 그대로).

## 8. 재지 못한 것
- 요청서의 실제 런(검증 사례의 실물) — 이 박스에 없다. 사용자가 cae00 에서 검증런을 돌린다.
- KC-01 · KC-02 의 실제 꼴 · LS-DYNA 산출(d3hsp · glstat) — 받는 꼴은 요청서 표대로다.
