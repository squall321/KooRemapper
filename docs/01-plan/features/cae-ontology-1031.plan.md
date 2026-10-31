# 해석 어휘(cae_*) 채택 · 캠페인 수준 적재 · 질의 (2026-10-31)

후처리(KooD3plotReader)가 리포트 곁에 내는 온톨로지 꾸러미(`dynaforge.onto_package`)를 DynaForge 가 받아 싣고 묻게 한다.
상대 문서 — KooD3plotReader `docs/ontology_2026-10/package-contract.md`(계약 초안 2) · 정본 어휘의 출처 그쪽 `e6cce7f`.
우리 검토 답신 `docs/requests/kood3plotreader-ontology-review-2026-10-31.md`(`7e8252d`).

## 사용자 결정 (10-31)
- KooD3plotReader 세션에서 「넷 다 권장안」 — DynaForge 가 채택 · 적재 · 질의를 맡는다. 어휘 정본은 DynaForge `platform/core/ontology/dynaforge-cae.json`.
  적재는 **(가) 캠페인 수준만 행으로**. KooD3plotReader 는 push · SIF 배포.
- 이 세션에서 다시 확인(10-31 「지금 짓는다」).

## 무엇을
### 어휘
- 정본 `platform/core/ontology/dynaforge-cae.json` — 그쪽 판 0.3 **바이트 그대로**(sha256 `72ff9b49…`). 다른 바이트로 시작하면 배포된 생산 쪽 꾸러미가 처음부터 거절된다.
- **받아들인 판의 목록** — 꾸러미 머리의 `vocabulary.sha256` 이 목록 안이면 받고, **그 판의 어휘로** 검증한다. 정본을 올릴 때는 옛 바이트를
  `platform/core/ontology/history/` 로 옮겨 목록에 남긴다(아직 옛 판을 싣는 배포판 · 늦게 바뀌는 노드 SIF 를 막지 않게 — 그쪽 10-31 권고).
### 적재 (가)
- 행으로 — `cae_campaign` · `cae_part` · `cae_contact` · `cae_load_path` · `cae_finding` · `cae_hotspot`. 선은 꾸러미의 다대다(`contact_side` ·
  `path_between` · `finding_about`)와 우리가 긋는 `campaign_report`(→ `impact_report`).
- 행으로 하지 않는 것 — `cae_run` · `cae_part_response`(정본은 `impact_cases` — `case_key` 가 같다) · `cae_load_transfer`(꾸러미 파일). 꾸러미 파일은
  리포트의 세션 파일로 둔다.
- 키는 `<리포트 id>/<꾸러미 키>`, 참조 값도 같다. 행 · 선에 `report_id`(FK → `impact_reports` ON DELETE CASCADE) — 리포트를 지우면 함께 사라진다.
  다시 실으면 그 리포트의 행을 통째로 바꾼다(정본은 리포트이고 꾸러미는 거기서 다시 만든다).
- 짝 — 머리 `source.html.sha256` 이 리포트 원본 HTML 의 지문과 같아야 한다. 종류(sphere · impact · deep)가 맞아야 한다. 꾸러미의 런 키가 리포트의
  `case_key` 와 맞는지 본다(하나도 안 맞으면 거절, 일부면 경고).
- 들어오는 길 — REST `POST /reports/{id}/ontology`(꾸러미 JSON) · MCP `attach_ontology(report_id, path)` · 번들 반입이 같은 이름 줄기의 꾸러미를 저절로.
  후처리 예약(7-1) 길은 KooSlurm 귀환 매니페스트에 꾸러미 항목이 생긴 뒤(요청).
### 질의
- 리포트 하나 — `GET /reports/{id}/ontology`(캠페인 · 파트 판정 · 하중 경로 · 소견 · 경고). 리포트 가시성 그대로.
- 리포트를 건너 — `GET /cae/parts`(판정 · 안전율로) · `GET /cae/load-paths`(충격량 · 맞닿은 비율 순). **읽을 수 있는 리포트의 것만**(`_readable_scope`, 관리자는 전사).
- MCP — `attach_ontology` · `report_ontology` · `find_cae_parts` · `find_load_paths`.
- ★리포트에서 나온 행은 리포트 가시성을 따른다 — 전사 공개인 일반 보기(`/ontology/types` · `/ontology/objects`)에는 `cae_*` 를 내지 않는다.
- 화면 — 리포트 상세에 「해석 온톨로지」(파트 판정 · 하중 경로 상위 · 경고).

## 하지 않는 것
- 런 단위 행(사용자 결정 (가)) · `cae_*` 를 허브로 내보내기 · 어휘 0.4(`flow_scalars_only`)는 생산 쪽 표식이 배포될 때 함께(그쪽 제안 — 넣는 것은 동의).

## 체크리스트
- [ ] 정본 어휘 0.3 바이트 그대로 · 받아들인 판 목록 · 꾸러미 검사(순수 함수) + 시험
- [ ] 마이그레이션 0020 — `onto_objects.report_id` · `onto_relations.report_id`(FK CASCADE · 색인) · `impact_reports.ontology`
- [ ] 적재 서비스 · REST 붙이기 · 번들 반입 연결 + 시험(실물 표본 v14 · impA · deep)
- [ ] 질의 REST · MCP 넷 · 일반 보기에서 `cae_*` 빼기 + 시험 · 문서 쓸기(TOOLS · 개수 · 패리티)
- [ ] 화면 — 리포트 상세 「해석 온톨로지」
- [ ] 백엔드 전체 · 스모크 · 화면 확인 · dev 반영 · 커밋 · Drive 게시 · KooSlurm 매니페스트 요청 · KooD3plotReader 알림

## 결정 기록
- (10-31) 위 사용자 결정.
- (10-31) 받아들인 판 목록을 둔다 — 정본 하나와만 견주면 정본을 올리는 순간 옛 판을 싣는 배포판의 꾸러미가 모두 막힌다(그쪽 권고). 판마다 그 판 어휘로 검증.
- (10-31) 리포트 행은 `report_id` FK CASCADE 로 묶는다 — 키 접두 LIKE 로 지우면 색인을 못 타고, 가시성도 리포트와 이어야 한다.
- (10-31) 다시 실으면 그 리포트 행을 통째로 바꾼다 — 그쪽 계약 초안은 「삭제 표시」 를 권했지만 행의 정본이 리포트라 남길 것이 없다.
- (10-31) 일반 보기에서 `cae_*` 를 뺀다 — 일반 보기는 로그인한 누구나 읽는데 리포트는 소유 · 소속으로 갈린다(리포트 수치가 새어 나간다).
