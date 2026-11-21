# DynaForge 개발 요청서 v1.0 답신 — 15건의 상태 · 올린 것을 쓰는 법 · 확정된 이름 · 청할 것 (2026-11-21)

**받는 곳** 요청서를 보낸 쪽(전달은 사용자가 한다) · **보내는 쪽** DynaForge(KooRemapper) · **원문** DynaForge 개발 요청서 v1.0(11-17). 원문에는
미출시 과제 이름과 PC 경로가 있어 이 리포에 두지 않았고, 이 답신도 그것을 적지 않는다. 요청서의 검증 사례는 번호(DF-nn)로만 가리킨다.

## 0. 요약
- 15건 가운데 **올린 것은 셋**이다 — DF-14(요소 번호 겹침 감지 · 쓰기 거절) · DF-01(적재 주소의 공식 답 · 캠페인 일괄 적재 · 중복 막기) · DF-15
  의 일부(응답의 환경 칸). 올린 판은 Drive `dist-20261121-120311Z` 이고, 이 답신이 재 본 곳은 개발 스택이다. 운영(cae00)은 운영자가 다음에
  갱신할 때 받는다.
- 나머지 12건은 다섯 단계(② ~ ⑥)로 짓는다. 도구 · 경로 이름은 11-21 에 사용자가 확정했다(3절). 단계마다 칸과 검증 사례를 사용자에게 확인받고
  짓는다.
- **차례가 하나 바뀌었다** — 사용자가 기존 덱 연산의 결함 스무 줄을 먼저 고치기로 했다(11-21). ② ~ ⑥ 은 그 판들이 올라간 뒤에 시작한다. 날짜는
  약속하지 못한다.
- ② ~ ④ 는 만드는 쪽의 꼴을 받아야 칸이 선다(4절). 꼴이 오기 전에는 요청서 표대로 받는 쪽을 세우고, 실제 꼴이 다르면 받는 쪽을 다시 손본다.
- 지금 올리기는 **동시 수를 낮게** 잡아야 한다 — 동시 40 건 시험에서 23 건이 500 이었다(2-2절). 고치는 일은 ② 단계에 넣었다.

## 1. 15건의 상태
「단계」 는 짓는 차례다 — ② 출처 · 유효성 → ③ 추출 완전성 · 삭제 관문 → ④ 보고서 묶음 → ⑤ 캠페인 집계 → ⑥ 핫스팟 · 세션. 이름은 3절의 확정된
이름이다.

| 항목 | 우선 | 상태 | 지금 있는 것 · 지을 것 | 기대는 것 |
|---|---|---|---|---|
| DF-01 적재 경로 · 캠페인 일괄 적재 | P0 | **올림**(11-17 · 11-21) | 적재 주소의 공식 답 · 401 세 갈래 안내 · 캠페인 만들기 · 런 목록 · 런마다 올리기 · 중복 건너뜀 · 적재 상태(2절) | 운영 주소는 운영자 설정 |
| DF-02 런 출처 칸 · 혼합 설정 표시 | P0 | ② | 없다 — `campaign_provenance` · 필터 `config_generation` | KC-01 의 꼴 |
| DF-03 런 유효성 · 건강 칸 | P0 | ② | 없다 — `report_health` · `campaign_health_table` · 통계 도구의 `include_invalid` | KC-02 의 꼴 · HG/IE 문장(4절 4) |
| DF-04 추출 완전성 · d3plot 삭제 관문 | P0 | ③ | 없다 — `report_extraction` · `campaign_deletion_clearance` · `set_campaign_required_extractions` | KC-05 의 꼴 · `peak_source` · `states_read/total` 을 내는 쪽 |
| DF-05 캠페인 각도 통계 | P1 | ⑤ | 없다 — `campaign_angle_stats` · `campaign_angle_table` · `set_campaign_part_groups` | ② 의 유효성 칸 |
| DF-06 각도별 피크 · 시각 · 충격 차수 표 | P1 | ⑤ | 없다 — `campaign_peak_table`. 지금 리포트의 `peak_time` 은 리포트에 적힌 값 그대로 초다 | — |
| DF-07 핫스팟 묶음 | P2 | ⑥ | 없다 — `campaign_hotspot_sites` | — |
| DF-08 파트 위험 · 허용치 여유 | P1 | ⑤ | 없다 — `campaign_part_margin`. 기본 항복 350 은 리포트를 만드는 쪽이 넣는 값이고 우리는 싣기만 한다 | 기준값(MN-01 · 자주검증 Datahub) |
| DF-09 구 지도 값 · 그림 출력 | P1 | ⑤ | 없다 — `campaign_sphere_map` | 격자값 표본(4절 5) |
| DF-10 부분충격 위치 지도 | P1 | ⑤ | 없다 — `campaign_site_table` · `campaign_site_map`. footprint 는 지금 합성 사각형이고 「합성」 표지와 경고가 붙는다 | 실측 footprint 를 내는 쪽(4절 8) |
| DF-11 리비전 비교 | P1 | ⑤ | 없다 — `import_part_map` · `compare_campaigns` | — |
| DF-12 설정 쌍 비교 | P1 | ⑤ | 없다 — `compare_config_pairs` · `set_campaign_pair_rule` | ② 의 설정 세대 칸 |
| DF-13 보고서용 묶음 출력 | P1 | ④ | 없다 — `build_report_bundle` · `report_bundle` · `report_bundle_diff` | 인용 kind 목록(4절 6) |
| DF-14 솔리드 · 셸 요소 번호 겹침 | P1 | **올림**(11-17) | modelmeta 칸 둘 · 덱을 다시 쓰는 연산의 거절(2-3절) | — |
| DF-15 세션 관리 — 환경 · 판 · 파트 이름 · 옛 파일 | P2 | **일부 올림**(11-17) · 나머지 ⑥ | 리포트 응답의 `environment` · inspect 응답의 `sha256`(2-4절). 세션 응답의 칸 · `rename_session_part` 는 ⑥ | — |

## 2. 올린 것을 쓰는 법

### 2-1. 적재 주소(DF-01)
- `GET /api/v1/system/capabilities` 의 `intake` 묶음이 공식 답이다 — `method` · `path`(`/api/v1/reports/intake`) · `public_url` · `mcp_url` ·
  `token`(`kr_pat` — 이 서버가 발급한 kr_ 토큰을 `Authorization: Bearer` 로) · `portal_auth_required`(false) · `max_upload_mb` · `max_report_mb`
  · `batch` · `reports_per_call`(1) · `rate_limit_per_min` · `campaign`(아래 세 경로 · 폼 칸 · 상태 단어).
- `public_url` 은 운영자가 `KOORM_PUBLIC_BASE` 를 넣어야 채워진다. 비어 있으면 null 이다 — 주소를 추측하지 말고 운영자에게 청한다.
- 401 은 응답의 `detail` 글로 가른다(MCP `upload_instructions` 에 같은 글이 있다) — 「인증 토큰이 필요합니다.」 는 Authorization 헤더가 API 에
  닿지 않은 것(게이트웨이가 뗐다) · 「토큰이 유효하지 않거나 취소·만료되었습니다.」 는 kr_ 토큰인데 그 인스턴스에 없는 것(개발 스택에서 받은
  토큰을 운영에 쓴 경우) · 「토큰이 유효하지 않거나 만료되었습니다.」 는 kr_ 가 아닌 토큰 · `detail` 이 없는 401 은 게이트웨이가 앞에서 막은
  것이다. 운영 게이트웨이에 실제로 깔린 설정은 우리가 보지 못했다.

### 2-2. 캠페인 일괄 적재(DF-01)
1. **캠페인을 만든다** — `POST /api/v1/campaigns`(MCP `create_campaign`). 본문은 `name`(필수) · `project` · `dev_rev` · `analysis_method` ·
   `analysis_target` · `doe_strategy` · `drop_height_mm` · `duration_ms` · `thickness_axis`(X · Y · Z) · `impactor`(`mass_g` · `height_mm` ·
   `ke_mj`)다. 모르는 칸은 422 다. 같은 이름을 이미 썼으면 409 이고 `data.campaign_id` 가 그 캠페인이다.
2. **런 목록을 올린다** — `POST /api/v1/campaigns/{campaign_id}/runs`(MCP `ingest_campaign_manifest`). 본문은 `{"runs": [{"run_key", "doe",
   "pitch", "roll"}, …]}` 이고 한 요청에 5,000 런까지다. 다시 올리면 새 `run_key` 만 더하고 있는 런은 보낸 칸만 맞춘다. 한 요청 안에 같은
   `run_key` 가 둘이면 422 다. `run_key` 는 빈칸 없는 글 128 자까지다(꼴은 검사하지 않는다 — 캠페인 안에서 유일하면 된다).
3. **런마다 리포트를 보낸다** — `POST /api/v1/reports/intake` 에 지금 쓰던 폼 그대로(`file` …) 폼 칸 `campaign_id` · `run_key` 를 더한다. 둘은
   함께 와야 한다. 한 호출에 리포트 하나다.
4. **적재 상태를 읽는다** — `GET /api/v1/campaigns/{campaign_id}/ingest-status`(MCP `campaign_ingest_status`). `counts` 는 `listed = pending +
   received + skipped + rejected` 이고 `with_report` 가 리포트를 가진 런 수다. 런마다 상태 · `report_id` · 지문 · 거절 까닭이 온다(`state` 로
   거르고 `limit` · `offset` 으로 넘긴다).

런마다 올릴 때의 답은 넷이다.

| 경우 | 답 | 런에 남는 것 |
|---|---|---|
| 그 런이 리포트를 갖지 않았다 | 201 · `ingest_state: "received"` · `content_sha256` | 리포트가 묶인다 |
| 가진 리포트와 내용이 같다 | 200 · `ingest_state: "skipped"` · 가진 리포트의 `report_id` | 아무것도 저장하지 않는다 |
| 가진 리포트와 내용이 다르다 | 409 · 까닭에 두 지문 · `data.offered_sha256` | 가진 리포트는 그대로 · 상태는 `rejected` |
| 목록에 없는 `run_key` | 400 | 런 행을 만들지 않는다(목록을 먼저 올린다) |

- **지문** — `content_sha256` 은 저장하는 리포트 HTML 바이트의 sha256 이다(.gz 는 푼 뒤 · 묶음은 그 안의 HTML). 같은 런을 다시 보내도 내용이
  같으면 건너뛰므로, 끊긴 일괄 적재는 처음부터 다시 돌려도 된다.
- **판을 바꾸려면** — 지금은 그 런의 리포트를 지운 뒤 다시 보내는 길뿐이다(지우면 런이 `pending` 으로 돌아온다). 설정 세대로 판을 가르는 것은 ②
  단계의 칸이다.
- **보이는 범위** — 캠페인은 만든 계정만 본다(다른 계정에는 404). 올리는 토큰과 읽는 토큰이 같은 계정이어야 한다.
- **그 밖의 4xx**(리포트 해석 실패 · 크기 상한 · 깨진 gzip …)는 그 글이 런의 거절 까닭으로 남는다. 5xx · 401 · 429 는 런에 적히지 않는다 — 런
  상태는 앞 그대로이고 다시 보내면 된다.
- **동시 수는 낮게** — 서버는 리포트 해석을 한 번에 하나씩 줄 세운다(메모리 때문이다 — 해석 중 메모리는 리포트 크기의 여덟 배쯤이다). 그런데
  줄에 선 요청이 DB 연결을 붙들고 있어, 동시 40 건 시험에서 17 건이 201 이고 23 건이 500 이었다(연결 15 개가 다 차고 30 초를 기다린 뒤다). 줄에
  열다섯 넘게 서면 이렇게 된다 — 연결은 다른 호출도 같이 쓴다. 잰 것은 동시 3(5.4 초에 끝났다)과 동시 40 둘뿐이고 그 사이는 재지 않았다. 고치기
  전에는 동시 3 ~ 4 로 올리기를 권한다. 분당 호출 한도(`rate_limit_per_min`)를 넘으면 429 와 `Retry-After` 가 온다.

```
curl -H "Authorization: Bearer kr_…" \
     -F file=@report.html.gz -F campaign_id=<campaign_id> -F run_key=<run_key> \
     <주소>/api/v1/reports/intake
```

### 2-3. 요소 번호 겹침(DF-14)
- 덱 메타(inspect 응답의 `meta.modelmeta`)의 `model.element_id_collisions`(뒤 정의에 덮인 요소 수) · `model.parts_missing`(요소가 하나도 남지
  않은 파트 수)이 0 이 아니면 그 덱은 요소 번호가 겹친 덱이다. 콘솔 파일 패널에도 경고가 보인다.
- 겹친 덱은 덱을 다시 쓰는 연산이 거절한다(산출 없음) — 파트가 조용히 빠진 덱이 나오지 않는다. `info` 도 같은 수를 알린다.
- 요청서의 `deck_eid_collision_check` · `…/id-audit` 는 따로 만들지 않았다 — 위 두 칸이 같은 답을 낸다. 셸 번호를 바꾼 사본을 만들어 주는 기능은
  짓지 않았다(사용자 결정 11-17 — 감지 · 경고 · 쓰기 거절까지).

### 2-4. 환경 칸(DF-15 일부)
- 리포트 응답(찾기 · 요약 · 목록 · 원샷 intake)과 캠페인 응답에 `environment`(dev · prod · unknown)가 실린다 — 개발 스택에 올린 것을 운영 것으로
  읽지 않게 한다.
- inspect 응답에 파일의 `sha256` 이 실린다.

## 3. 확정된 이름(사용자 확인 11-21)
우리 MCP 의 꼴에 맞췄다 — 쓰기는 동사가 앞(`create_` · `set_` · `import_` · `build_` · `ingest_` · `rename_`), 읽기는 명사가 앞(`report_*` ·
`campaign_*`), 비교는 `compare_*` 다. REST 는 kebab 이고 콜론 꼴(`:batchIntake`)이 없다. 아래 표에 없는 이름 · 경로 · 칸 이름은 **요청서 제안
그대로**다. 아직 짓지 않은 줄(② ~ ⑥)도 지을 때 이 이름으로 낸다.

| 항목 | 요청서 제안 | 확정 | 까닭 |
|---|---|---|---|
| DF-01 | `campaign_create` | `create_campaign` | 쓰기 |
| DF-01 | `campaign_ingest_manifest` | `ingest_campaign_manifest` | 쓰기 |
| DF-01 | `POST /campaigns/{id}/runs:batchIntake` | `POST /campaigns/{id}/runs` | 콜론 꼴 없음 · 런 목록만 받는다(파일은 런마다 intake) |
| DF-03 | `run_health` | `report_health` | 받는 것이 report_id |
| DF-04 | `run_extraction_status` | `report_extraction` | 받는 것이 report_id |
| DF-04 | `deletion_clearance` | `campaign_deletion_clearance` | 캠페인 단위 |
| DF-04 | (설정) | `set_campaign_required_extractions` · `PUT /campaigns/{id}/required-extractions` | 새로 둠 |
| DF-05 | `part_group_define` | `set_campaign_part_groups` | 쓰기 |
| DF-10 | `impact_site_table` · `impact_site_map` | `campaign_site_table` · `campaign_site_map` | 캠페인 단위 |
| DF-11 | `part_map_import` | `import_part_map` | 쓰기 |
| DF-11 | `campaign_compare_revisions` · `GET /campaign-compare?…` | `compare_campaigns` · `GET /campaigns/compare?a=&b=&part_map=` | `compare_reports` 와 같은 꼴 |
| DF-12 | `config_pair_compare` | `compare_config_pairs` | 비교 |
| DF-12 | `pair_rule_set` | `set_campaign_pair_rule` | 쓰기 |
| DF-13 | `report_bundle_build` · `_get` · `_diff` | `build_report_bundle` · `report_bundle` · `report_bundle_diff` | 쓰기는 동사가 앞 |
| DF-14 | `deck_eid_collision_check` · `…/id-audit` | 만들지 않음 | modelmeta 칸 둘이 같은 답 |
| DF-15 | `session_describe` · `GET /sessions/{id}/describe` | 새 도구 · 경로 없이 `get_session` 응답에 칸 | 같은 응답에 싣는다 |
| DF-15 | `part_rename` | `rename_session_part` | 쓰기 |

- 건강 문턱 기본값도 정해졌다(사용자 결정 11-21) — 에너지비 ≤ 1.05 · HG/IE < 10 % · 추가 질량 0.5 % 를 넘으면 warn · 미끄럼 에너지는 문턱 없음.
  캠페인마다 바꿀 수 있고, 응답에는 판정에 쓴 문턱 묶음을 같이 싣는다. HG/IE 는 4절 4 의 답에 따라 바뀔 수 있다.

## 4. 요청 쪽에 청할 것
1. **출처 매니페스트(KC-01)** — 실제로 나오는 한 줄의 표본. ② 는 요청서 표의 13 칸(래퍼 이름 · 판 · 처방 묶음 · 시나리오 · 러너 설정 · 덱 ·
   인클루드의 sha256 · 솔버 · SIF 판 · 리포트 도구 커밋 · 플래그 · 제출 시각 · 설정 세대)으로 받는 쪽을 세운다. KooChainRun 리포가 이 박스에
   없어 실제 꼴을 보지 못했다 — 칸 이름 · 형이 다르면 받는 쪽을 다시 손봐야 한다.
2. **건강 요약(KC-02)** — 같은 까닭으로 실제 표본. 요청서 표의 11 칸으로 세운다.
3. **삭제 기록(KC-05)** — d3plot 을 지웠다는 사실이 어떤 꼴로 오는지(런 열쇠 · 시각 · 지운 범위).
4. **HG/IE 문턱** — 요청서 안의 두 문장이 같은 값을 다르게 말하는 것으로 읽힌다. DF-03 의 기본값 제안은 「HG/IE < 10 %」 인데, 같은 항목의 함정
   목록에는 「'|HG|/IE ≤ 0.1' 문턱은 폐기된 값」 이라는 줄이 있다. 폐기가 특정 런 갈래에만 해당하는지, 기본값에서 빼야 하는지 알려 달라. 답이
   오기 전에는 제안값을 기본으로 둔다. 「에너지비만으로 판정하지 않는다」 는 줄은 그대로 지킨다.
5. **구 지도 격자값 표본(DF-09)** — 같은 입력 · 같은 보간 규칙으로 낸 격자값. 입력 리포트 묶음 · 격자 정의 · 보간 규칙 · 값이 함께 있어야
   「일치」 를 잰다.
6. **인용 kind 목록(DF-13)** — 심의 엔진 DL-01 의 `ref.kind` 목록. 우리 리포트는 `dynaforge_report` 로 낸다.
7. **`peak_source` · `states_read` · `states_total`(DF-04)** — 지금 리포트에 없는 값이다. 리포트를 만드는 쪽이 낼지, 래퍼(KC)가 낼지 정해 달라.
   우리는 온 값을 싣고 판정한다.
8. **실측 footprint(DF-10)** — 리포트를 만드는 쪽이 재서 내는 값으로 둔다(사용자 결정 11-21). 그때까지 자리 지도는 합성 사각형에 경고가 붙은
   채다. 우리가 덱에서 재는 길은 고르지 않았다.
9. **기준값(DF-08)** — 재질 강도(MN-01)와 부품 시험 합격선(자주검증 Datahub)을 `source_platform` · `source_record_id` · `version` 과 함께
   받는다. 기본 항복 350 은 리포트를 만드는 쪽이 넣는 값이라, 틀린 기준이 쓰이지 않게 하려면 그쪽에서 기본값을 빼거나 「기본값」 표지를 내야
   한다 — 표지가 오면 우리는 그것을 싣고 여유 계산에서 가른다.
10. **`peak_time` 단위(DF-06)** — 리포트에 적힌 값 그대로 초다. 캠페인 표에서 ms 로 낼지는 ⑤ 단계 계획에서 칸 이름과 함께 확인받는다.

## 5. 차례 · 운영
- 차례 — (기존 덱 연산 결함 판들) → ② DF-02 · DF-03 + 동시 올리기 고침 → ③ DF-04 → ④ DF-13 → ⑤ DF-05 · 06 · 08 ~ 12 → ⑥ DF-07 · DF-15 나머지.
  단계마다 올린 뒤 이런 답신을 다시 낸다.
- 운영(cae00) — 코드와 Drive 판은 올라가 있고, 운영 스택이 받는 것은 운영자의 갱신 때다. 운영에서 `capabilities.intake.public_url` 이 null 이면
  운영자 설정(`KOORM_PUBLIC_BASE`)이 아직 없는 것이다. 운영 스택의 지금 상태는 우리가 재지 못했다.
