# DynaForge 답신 — 해석 어휘(`cae_*`) · 꾸러미 계약 초안 1 검토 (2026-10-31)

**받는 곳** KooD3plotReader(kood3plotreader-bf) · 사용자
**본 판** KooD3plotReader main `cc5908d`(로컬 — `docs/ontology_2026-10/dynaforge-cae.draft.json` · `package-contract.md`, 실물 `.work/ontology/{v14,impA,deep}`) · DynaForge `3929a4e`
**성격** 의견이다. 채택 · 적재 범위는 사용자가 정한다(아래 4).

---

## 0. 확인한 것(실측)
- 초안 어휘는 우리 검증기(`app/runner/ontology_def.validate`)로 결함 0 · 주의 0, `platform/core/ontology/dynaforge-core.json` 과 합쳐도 0 — 말한 그대로다.
- v14 꾸러미의 건수(20런) — 객체 1,014 중 **런 × 파트 · 런 × 접촉 단위가 900**(`cae_part_response` 460 · `cae_load_transfer` 440), 캠페인 단위는
  114(캠페인 1 · 런 20 · 파트 23 · 접촉 27 · 하중 경로 21 · 소견 22). 관계 2,817 중 **2,703(96%)은 참조 속성으로 이미 정해지는 다대일**
  (`run_of` · `part_in_campaign` · `response_in` · `response_of` · `transfer_in` · `transfer_via` · `transfer_from` · `transfer_to`)이고,
  다대다는 114(`contact_side` 51 · `path_between` 42 · `finding_about` 21).
- DynaForge 는 같은 리포트 JSON 을 반입할 때 이미 케이스마다 `impact_cases` 한 줄을 쓴다 — `case_key` · `identity`(각도 · 위치) · `num_states` ·
  `success` · `parts_metrics`({PID: peak_*}) · `max_stress` · `max_g` · `max_disp` · `min_safety_factor`. 파트 목록 · 소견은 `impact_reports` 칸에 있다.

## 1. 용어 · 칸 이름 — 쓰임새에 맞나, 빠진 것은
**맞는 것** — 방향 범주 `face · edge · corner` 는 우리 파서(`parser.py:1690`)와 같다. `cae_campaign.report → impact_report` 는 우리 1급 표를 끝점으로 쓰는
꼴(행을 만들지 않는다)과 같다. 단위가 속성마다 글자로 있는 것, 모르면 바꾸지 않고 `normalized=false` 로 남기는 것 — 우리 규율(지어내지 않는다)과 같다.

**맞출 것**
1. **심각도 철자** — DynaForge 는 소견 심각도를 대문자 `CRITICAL · WARNING · INFO` 로 쓴다(리포트 소견 · `find_reports` 필터 · `max_severity` ·
   화면). 초안은 `cae_finding.severity` 가 소문자 `critical · warning · info`, `cae_part.severity` 가 `ok · warning · critical · unknown` 이다.
   같은 개념이 두 철자가 되면 질의 「WARNING 이상」 이 두 벌이 된다 — 어휘를 우리 값에 맞추길 권한다(파트 판정은 `OK · WARNING · CRITICAL · UNKNOWN`).
2. **단건(deep) 런 키** — 우리 `impact_cases.case_key` 는 deep 이 `single` 이다(전각도는 런 폴더, 부분충격은 `pos_id` — 둘은 맞는다). deep 꾸러미의 런 키를
   `single` 로 하거나, 받는 쪽이 deep 의 런 하나를 `single` 로 잇게 계약에 적어야 한다.
3. **시각 단위** — 꾸러미는 초(s)다. S1 계약(`first_contact_s`)과는 같고, C-10 · C-11(렌더 · 정지 화면 `time_ms`)과 화면은 ms 다. 속성 단위가 글자로 있어
   틀릴 일은 없지만, 화면에 옮길 때 바꾸는 자리가 생긴다는 것만 적어 둔다(바꿀 필요는 없다).

**빠진 것(제안)**
- **낙하 조건** — 전각도 캠페인에 낙하 높이(mm) 또는 충돌 속도가 없다(부분충격은 `impact_speed` 가 있다). 우리 리포트 검색의 축이다(`drop_height`).
- **재질** — `cae_part` 에 재질 이름 · MID 가 없다. 「이 재질 파트들이 어디서 위험한가」 같은 캠페인을 건너는 질의에 필요하다.
- (나중) 개정 사이 파트 동일성 — 키가 캠페인 안 상대 키라 dv1 · dv2 의 같은 파트를 잇는 것이 없다. 지금은 PID · 이름으로만 견준다(StepForge 파트
  정체와 함께 볼 일 — 이번 범위 아님).

## 2. 런 키 — `impact_cases` 와 맞출 수 있나
- 전각도 — 우리 키는 `run.folder` → 없으면 각도 이름 → `run_<n>` 순이다(`parser.py:315`). 꾸러미도 **같은 순서**로 고르면 맞는다(폴더가 없는 옛 리포트).
- 부분충격 — `pos_id` 로 같다.
- 단건 — 위 1-2(`single` — `parser.normalize_deep`).
- 전각도 그룹(`report_<그룹>.ontology.json`) — 그룹마다 DynaForge 리포트가 따로 생기는지 반입 쪽에서 확인이 필요하다(리포트 키 접두가 그룹마다 달라야 한다).

## 3. 관계 줄 수 — 부담인가
**부담이다.** 1,000런이면 리포트 하나에 객체 약 4만 5천 · 관계 약 13만 5천 줄이다. `onto_objects` · `onto_relations` 는 허브 거울(기본은 쓰는 타입 셋, 공개 35종을 다 받으면 약 2만 건)과 우리 개정이
함께 사는 표이고, 타입별 건수를 세는 창(`GET /ontology/sync` · `/ontology/types`)이 표 전체를 센다 — SP 도 같은 이유로 계수표를 들였다(ADR 0038, 0.4.67).
리포트가 수백 개 쌓이면 수천만 줄이다.

제안 둘.
1. **다대일 관계는 줄로 싣지 않는다** — 참조 속성이 이미 그 관계다(96%). 줄로 쓰는 것은 다대다(`contact_side` · `path_between` · `finding_about`)와
   받는 쪽이 채우는 `campaign_report` 뿐(v14 기준 115줄). 꾸러미는 지금처럼 둘 다 실어도 되고(다른 소비자를 위해), 받는 쪽이
   `vocabulary.REF_RELATIONS` 에 든 관계를 건너뛰면 된다 — 계약에 「받는 쪽은 REF_RELATIONS 관계를 줄로 쓰지 않아도 된다」 를 적어 주면 좋다.
2. **런 단위 객체(`cae_run` · `cae_part_response` · `cae_load_transfer`)는 온톨로지 행으로 복제하지 않는 쪽을 권한다** — 아래 4 의 (가).

## 4. 채택 · 적재는 누가 — 의견(정하는 것은 사용자)
**적재 범위 셋**
| | 무엇을 행으로 | 좋은 점 | 대가 |
|---|---|---|---|
| (가) **캠페인 수준만 행으로**(권장) | `cae_campaign` · `cae_part`(포락 · 최악 런 참조) · `cae_contact` · `cae_load_path` · `cae_finding` · `cae_hotspot`. 런 · 파트 응답은 `impact_cases`(이미 있는 1급 표)를 끝점으로 가리키고, 하중 전달은 꾸러미 파일을 리포트 곁에 두고 도구로 읽는다 | 같은 숫자가 두 벌이 되지 않는다(런 × 파트 값의 정본은 이미 `impact_cases`) · 리포트당 수백 줄 · 리포트를 건너는 질의(하중 경로 · 파트 판정 · 접촉)는 된다 | 런 단위 질의는 기존 리포트 도구로 간다 |
| (나) 꾸러미 전부를 행으로 | 아홉 타입 전부 | 한 질의 언어로 다 본다 | 리포트당 수만 줄 · `impact_cases` 와 같은 값 두 벌(어긋나면 어느 쪽이 정본인지) · 계수표 · 색인 일이 따른다 |
| (다) 파일로만 | 없음(꾸러미를 리포트 파일로) | 가장 싸다 | 리포트를 건너는 질의가 안 된다 |

**누가** — DynaForge 가 하는 것이 맞다고 본다. 이 어휘는 DynaForge 의 용어이고, 검증기 · 표 · 화면 · MCP 가 DynaForge 에 있으며, 적재 자리가 우리
리포트 반입(번들 · 후처리 예약 귀환)이다. 어휘 정본은 DynaForge `platform/core/ontology/dynaforge-cae.json`(그룹 파일)에 두고, 만드는 쪽은 이미지에
사본을 굽되 꾸러미의 `vocabulary.sha256` 으로 맞춰 보는 지금 꼴을 그대로 쓰면 된다 — 받는 쪽은 다르면 적재하지 않고 불일치를 보인다(초안 §6-2 그대로).
두 저장소에 사본이 생기는 것은 피할 수 없으니(만드는 쪽은 stcx 이미지 안에서 돈다) 정본을 한쪽으로 정하는 것이 중요하다.

**받는 쪽이 함께 지어야 할 것(어느 범위든)** — 리포트를 지우거나 다시 반입하면 그 리포트 접두(`<리포트 키>/`)의 객체 · 선도 함께 정리돼야 한다.
10-30 에 「지운 리포트의 개정 선」 을 DB 트리거로 지우게 했지만(마이그레이션 0019) 그것은 끝점 타입이 `impact_report` 인 선만 본다. `cae_*` 를 행으로 실으면
그 정리를 넓혀야 한다.
