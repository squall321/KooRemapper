# 코어와 잇기 — DynaForge 몫 SRC-08 ~ 11 (2026-11-10)

## 무엇을 · 왜
cae00 운영의 11-09 제안서 「플랫폼 데이터 온톨로지화 · 코어와 잇기」 가운데 KooRemapper(DynaForge) 몫이다. 원문은 HWAXPortal 리포
`docs/core-link/request.md` 3-2절, 계약은 같은 리포 `docs/core-link/design.md` §8(포털 main `5f28bf36`)이다. 운영 실측(요청서 1-1) — 정의는
있으나 객체 0 · 코어로 가는 선 0 · 거울 받기가 기본 세 타입만 돌고 나머지는 10-28 에 멈춘 채 상태가 `ok` 로 보였다.

## 사용자 결정
- Q-5(11-09, 포털 결정 기록 CK-2) — 다리 **셋 다 · 정확 일치만**: `cae_part` → 코어 `part` · `cae_finding` → `failure_mode` · `cae_campaign` →
  `analysis_method`. 이름 · 별칭이 하나로 맞을 때만 `rule` 선, 나머지는 후보. 다시 반입해도 사람 선은 남는다. 다리는 자체 정의
  `dynaforge-core.json` 에 두고 바이트 사본인 정본 어휘 `dynaforge-cae.json` 은 고치지 않는다.
- 관계 이름(11-10) — `maps_to`(cae_part → part · StepForge SRC-02 와 같은 이름 — 한 질의로 두 앱을 묻는다) · `indicates`(cae_finding →
  failure_mode) · `follows_method`(cae_campaign → analysis_method).
- 후보를 사람 선으로 확정 · 지우는 권한(11-10) — 리포트 주인 + 시스템 관리자(꾸러미 붙이기와 같다).
- 보류(계약 §10 · 포털 11-09) — 가지(`corelink-src08-11`)에서 짓고 시험한다. main 에는 cae00 이 11-08 · 11-09 라운드 update-all 을 끝냈다고
  사용자가 알린 뒤(포털이 전한다)에 올린다 — deploy-all 이 코드와 Drive 바이너리를 함께 받기 때문이다.

## 지을 것
- **SRC-08 다리** — `dynaforge-core.json` 에 관계 셋. 꾸러미를 붙일 때(REST · 번들 · 7-1 반입 모두) 거울의 코어 객체 이름 · 별칭과 정확히 하나로
  맞으면 `rule` 선을 잇고, 여럿이 맞거나 부분만 맞으면 후보로 낸다. 결과에 선 수 · 후보 수 · 못 붙인 수를 싣는다(붙이기 응답 · 리포트의
  `ontology` 요약). 다시 붙이면 `rule` 선만 다시 짓고 **사람 선은 남긴다** — 리포트 행의 FK CASCADE 에 묶이지 않게 따로 두고, 가리키던 `cae_*` 가
  사라지면 지우지 않고 「끊긴 사람 선」 으로 보인다. 후보 확정 · 사람 선 지우기 길(REST, 리포트 주인 + 시스템 관리자). `report_cae` 가 선 · 후보를 보인다.
- **SRC-09 과제 잇기 자동** — `apply_task_links` 의 「붙는 것」(정확 · 별칭)만 받기(`plm_sync`) 뒤와 리포트 반입 뒤에 스스로 돈다. 받기 결과 줄에
  붙인 수 · 후보 수 · 못 붙인 수 · 이름 없는 리포트 수.
- **SRC-10 미리 보기 열기** — `GET /ontology/task-links`(MCP `plan_task_links`)를 일반 사용자 읽기로. 적용 `POST /ontology/task-links/apply` 는
  시스템 관리자 그대로(403). ★일반 사용자에게는 **자기가 읽을 수 있는 리포트(소유 · 같은 소속)만** 계획에 든다 — 일반 보기에서 `cae_*` 를 뺀
  10-31 결정과 같은 까닭(리포트 수치가 새어 나간다).
- **SRC-11 멈춘 타입** — 받을 타입(`sp_core_types`) 밖인데 거울에 남은 타입을 `ontology_sync_state` 의 타입 줄에 「멈춘 타입」 으로 표시하고
  `problems` 에 싣는다(기본값 셋은 그대로 — 넓히는 것은 박스 설정 BOX-01).
- 포털 쪽 — 게이트웨이 읽기 목록에 `heax-kooremapper_mcp:plan_task_links`(이름 · 쓰지 않는 미리 보기 성격 그대로).

## 하지 않는 것
- 정본 어휘(`dynaforge-cae.json`) 바꾸기 · 다리 짐작(부분 일치)을 선으로 잇기 · 화면(CaePanel)의 확정 단추(이번엔 REST · MCP 읽기까지 —
  화면은 다음).

## 체크리스트
- [x] 원문 · 계약 읽기(포털 `5f28bf36`) · 사용자 결정 넷(Q-5 · 이름 · 권한 · 보류)
- [ ] SRC-08 — 정의 · 붙일 때 잇기 · 후보 · 사람 선 보존 · 확정 길 · `report_cae` · 시험(v14 실물 꾸러미 · 재반입)
- [x] SRC-09 — 받기 뒤 · 반입 뒤 자동 · 결과 줄 · 시험(`e7f8d35`, 앞 커밋 `614f3b6` 계획을 싸게)
- [x] SRC-10 — 미리 보기 읽기 열기(보이는 리포트만) · 적용 403 · MCP · 시험(`5ec314e`)
- [x] SRC-11 — 멈춘 타입 표시 · 시험(`ae27a32` — 관리 화면 「멈춤」 포함)
- [ ] 문서 쓸기(MCP 설명 · 카탈로그 · 매뉴얼 · 포털 계약에 닿는 말) · 백엔드 전체 시험 · 적대적 검토 — SRC-09 ~ 11 몫은
  커밋마다 쓸었다(MCP `plan_task_links` · `ontology_sync_state` · `ingest_report` 설명, TOOLS.md, 라우트 머리말, 스모크 값 항).
  매뉴얼 · 카탈로그에는 이 셋을 말하는 줄이 없었다. 적대적 검토는 아직.
- [ ] (보류 풀린 뒤) main · push · 배포 · 포털에 알림

## 결정 기록
- (11-10) 위 사용자 결정. 원문의 Q-5 는 포털 결정 기록 CK-2 로 확인했다(전해 들은 말만으로 짓지 않는다).
- (11-10) 미리 보기를 일반 사용자에게 열 때 보이는 리포트만 — 계획은 지금 모든 리포트를 읽는다(`select(ImpactReport)`).

### SRC-09 ~ 11 짓기(11-10, 갈래 작업 트리)
- (11-10) SRC-10 — 일반 사용자의 계획은 리포트 검색 · 상세와 **같은 술어**(`reports.services._readable_scope` — 소유 · 게이트웨이가
  서명한 같은 소속)로 좁히고 수도 그것으로 센다. 시스템 관리자는 전부. 응답에 `scope`(`all` · `readable`). MCP 는 소속 헤더 둘을
  그대로 나르므로 게이트웨이 경유도 같다. 적용(`POST …/apply`)은 관리자 라우터 그대로(일반 사용자 403). 도구 이름 · 인자 그대로.
- (11-10) SRC-09 「붙는 것」 — 계획의 `links` 판정 전부로 읽었다: 과제명(`exact`) · 과제코드(`task_code`) · 옛 과제명
  (`previous_key`) · 우리 별칭(`alias`) · 하나뿐인 허브 별칭(`hub_alias`). 모두 글자 그대로 같은 것이다(요청서 「정확 · 별칭」).
  후보(`proposal`) · 못 붙임은 세기만 한다. 자동으로 다진 판은 `rev_source=rule`(관리자 버튼의 적용은 지금처럼 `manual`).
- (11-10) SRC-09 범위 — **반입 뒤는 그 리포트만**(반입은 과제 · 별칭을 바꾸지 않아 다른 리포트의 판정이 그대로다), **받기 뒤는
  리포트 전부**(과제 · 별칭이 바뀌면 어느 리포트든 새로 풀린다. 「바뀐 과제만」 은 받기마다 바뀐 key 를 따로 들고 있어야 하고, 지난번에
  못 이은 것 — 잠금으로 건너뛴 반입 · 잇기 실패 · 수동 메타 PATCH 로 글자 그대로 돌아간 선 — 을 다시 보지 못한다). 싸게 두는 법:
  계획은 리포트 칸 셋(id · eng_meta · project_name)만 읽고 후보용 과제는 한 번만 읽는다(`614f3b6`), 쓰기는 판이 바뀔 리포트만 —
  두 번째 실행은 아무것도 쓰지 않는다(`already`).
- (11-10) SRC-09 사람 판 — `set_revision` 의 manual 보호(판 칸: rev_source · decided_by · decided_at · note)를 그대로 쓰고, ★사람이
  정한 판에 이어진 리포트는 **옮기지 않는다**(`kept_manual` — set_revision 은 판 칸만 지키고 리포트 선은 옮기므로 먼저 거른다). 사람
  판을 **가리키게** 하는 것은 막지 않는다(인제스트 때 잇기와 같다).
- (11-10) SRC-09 커밋 먼저 · 실패 — 받기는 받은 것을 커밋한 **뒤** 같은 잠금(`dynaforge.sp_core_sync` — 층 2 쓰기)을 다시 걸고 돈다.
  깨지면 받은 것은 그대로, 결과 `needs_check` + problems 한 줄(층 2 반영 실패와 같은 자세). 반입은 `ingest_report` 가 커밋한 뒤
  저장점 안에서 — 깨지면 응답 `task_links.error`, 7-1 은 잡 경고(잡은 성공 그대로). 잠금을 쥔 작업이 있으면 건너뛰고
  `skipped: busy`(다음 받기 뒤 전부를 본다).
- (11-10) SRC-09 결과 줄 — 실행 기록 `counts.task_links`(관리자 받기 응답 · `/ontology/sync/runs` · 로그 한 줄도). 칸 단위 —
  `linked` · `already` · `kept_manual` · `skipped_no_code` · `reports` · `reports_without_a_name` 은 리포트, `candidates` · `unmatched` 는
  자유 문자열(미리 보기 `counts` 의 `proposal` · `unmatched` 와 같은 단위). 반입 응답 · 7-1 원장도 같은 꼴(`scope: reports`).
  ★이 수는 리포트 전부를 센 것이라 GET /ontology/sync 의 `last_run` 에는 **시스템 관리자에게만** 싣는다(SRC-10 · 10-31 과 같은 까닭).
- (11-10) SRC-11 — 멈춘 타입 = 받기 상태의 타입 줄 가운데 받을 타입(`KOORM_SP_CORE_TYPES`) 밖(`not_in_list`), 받을 타입이
  비었으면(공개된 것 전부) 마지막 카탈로그에 없는 것(`not_published`). 타입 줄의 `last_status` 는 마지막 실행의 기록이라 그대로 두고
  `stopped` · `stopped_why` 를 더하고, 맨 위에 `receive_types` · `stopped_types` · `problems`(까닭별 한 줄 — 이름 · 마지막으로 받은 때 ·
  고칠 곳). 기본 받을 타입 셋은 그대로. 관리 화면(허브 받기 카드)은 바꾸는 것이 작아 「멈춤」 · problems 를 넣었다(tsc 통과).
- (11-10) ★열린 점(사용자 결정) — 사람이 개정 연결을 **끊은**(`unlink_report_revision`) 리포트도, 그 이름이 정확히 풀리고 개정 코드가
  있으면 다음 받기 뒤 자동 잇기가 **다시 잇는다** — 끊었다는 기록이 남지 않는다(선을 지운다). 지키려면 끊을 때 표시를 남기는 길
  (선을 지우지 않고 `deleted` + 끊은 사람)과 자동 잇기가 그것을 건너뛰는 것이 필요하다. 이번엔 짓지 않았다. 지금도 수동 메타
  PATCH 는 같은 까닭으로 끊은 리포트를 다시 잇는다(인제스트 때 잇기 — `_link_revision`).
- (11-10) 하지 않은 것 — 수동 메타 PATCH 뒤 자동 잇기(반입이 아니다 — 글자 그대로 돌아간 선은 다음 받기 뒤 맞춘다). 서비스 신원
  (SRC-13)으로 부른 `plan_task_links` 는 그 서비스 계정이 읽을 수 있는 리포트만 본다(관리자 계정이 아니면 전사 수가 아니다).
- (11-11) ★사용자 결정 — 위 열린 점에 「끊은 것을 기록해 자동이 건너뛴다」. 지었다(`5cffd8d`, 스모크 `8e9d74a`).
  - 기록 — 끊는 길은 `unlink_revision` 하나다(REST `DELETE /reports/{id}/revision` · MCP `unlink_report_revision`, 소유자). 선을
    지우지 않고 끊은 표시(`deleted` + `unlinked_by` 로그인한 소유자 · `unlinked_at`)로 남긴다 — 이 표의 규약(끊은 선은 표시만)이고,
    리포트를 지우면 0019 트리거가 함께 지운다.
  - 기록이 이긴다 — `set_revision` 한 자리에서 기계 경로(source 가 manual 아님: 인제스트 때 잇기 · 수동 메타 고침 · 자동 잇기)를
    `unlinked` 로 거절한다(앞으로 생길 자동 경로도 같은 자리를 지난다). 받기 뒤 · 반입 뒤 자동 잇기와 **관리자 일괄 적용**은 미리 거르고
    `skipped_unlinked` 로 센다 — 일괄 적용은 사람의 손이지만 그 리포트를 보고 내린 판단이 아니라서 끊음이 이긴다. 미리 보기는 항목마다
    `unlinked`(리포트 id) · `counts.unlinked`(범위 안의 끊은 리포트 전부). 개정 보기 `GET /reports/{id}/revision` 의 `unlinked`({by, at, was}).
  - 풀리는 길 둘 — 사람이 손으로 다시 이으면(PUT · `set_report_revision`, manual) 기록을 지우고 잇는다(되살린 선에 끊은 표시가 남지
    않게 먼저 지운다). 기록 지우기 `DELETE /reports/{id}/revision/unlinked` · MCP `clear_report_unlink` — **소유자만**(끊기 · 잇기와
    같은 자세, 관리자도 남의 것은 못 지운다) · 없으면 409 · 지운 뒤 그 리포트 하나의 자동 잇기를 바로 한 번 돈다(`task_links`).
  - 수동 메타 고침(열린 점 2) — 끊은 리포트는 메타만 저장하고 다시 잇지 않는다(로그에 거절 한 줄). 다시 잇게 하려면 위 두 길.
  - 그대로인 것 — 다시 반입은 새 리포트(새 id)라 기록이 따라가지 않는다(사람이 확정한 판 칸은 판 key 로 지금처럼 따라간다).
    끊은 기록이 남은 리포트의 판 key 가 허브 이름 바뀜으로 옮겨져도 기록은 리포트 단위라 그대로 막는다.
  - 화면 — 개정 패널에 「○○ 이 끊었다 — 자동 잇기가 다시 잇지 않는다」 와 「자동 잇기 다시 허용」(tsc 통과 · 배포 때 dist 다시 짓기).
