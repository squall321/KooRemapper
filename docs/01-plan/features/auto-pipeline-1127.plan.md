# 자동 파이프라인 — DynaForge 원천 + 전각도 낙하 해석(KR-AP1 ~ 4, 2026-11-27)

체크리스트 `auto-pipeline-1127.checklist.md` · 맥락 `auto-pipeline-1127.context-notes.md`. 보낸 쪽 hwaxportal-71(사용자 결정 11-27 「미리 개발할
수 있는 것은 다」). 정본 계약은 포털 리포 `docs/auto-pipeline/contract.md` v1.1, 요청서는 같은 폴더 `requests/dynaforge.md`(main `afb751fc`) —
여기 옮기지 않는다.

## 0. 조건
- 포털은 기본 꺼짐으로 짓는다. 우리는 가지 `auto-pipeline` 에서 짓고 main · Drive 는 87 운영 회차에 맞춰 착지 값으로 준다.
- 낙하 실주행은 KooSlurm 공유 폴더 SH-01 · 02 뒤다. 그 전에는 `auto_check` 가 `missing kind=infra` 로 막는 것까지가 받아들이기다.
- 사용자 결정(11-27) — 세션 잇기 「세션에 과제 · 개발 단계 칸」 · 판정 「기준 없이 수치만」 · 신원 「auto_* 만 모두 읽기」(맥락 1절 — 설명
  문장이 규격).

## 1. 지금 꼴(대 본 것)
- 세션에는 허브 과제 · 개발 단계 칸이 없다 — `linked_cad`(StepForge 과제 id · 자유 판 이름) · `deck_revision_label`(자유)만. 과제 · 개발 단계는
  리포트(eng_meta · 과제·개정 잇기)와 후처리 예약 인자에만 있다.
- 세션 `updated_at` 은 세션 행이 바뀔 때만 움직인다(파일이 와도 그대로). 세션 파일에는 sha256 이 있다.
- 낙하 사슬 — op `stcx_fullangle_drop`(model · num_directions · height · t_final · drop_surface · ncpu · yield_stress_mpa …) → op
  `postprocess`(job_key · sim_type · project · dev_rev …) → sphere 리포트. 리포트에는 `worst_stress` · `worst_g` · `max_severity` 와 생성기가
  검출한 단위계(`unit_system` · `unit_labels`)가 있고 출처가 적힌 합부 기준은 없다.
- MCP 도구가 예외를 올리면 `isError` 다. 신원은 받은 `Authorization`(kr_ 토큰 · JWT)을 그대로 나른다 — 서비스 계정은 우리 쪽 사용자 하나로
  보인다.

## 2. 설계
- **세션 칸 둘**(마이그레이션 0027 — null 허용) — `task_key`(허브 과제명) · `dev_rev`(개발 단계 코드). 넣는 길은 세션 고치기(REST · MCP · 콘솔).
  과제는 판 확정과 같은 규칙(`resolve_confirm_task` — 못 풀면 400 + 후보, 허브 거울이 빈 박스는 글자 그대로), 개발 단계는 `parse_stage` 꼴.
  비우면 null.
- **KR-AP1 `auto_changes(since, limit)`** — 「바뀐 때」 = 세션 수정 시각과 마지막 파일 시각 가운데 늦은 것. 차례 (바뀐 때, 세션 id) · 불투명
  커서(그 둘) · 쪽마다 `complete`. `subject` = `{project: task_key | null, revision: dev_rev | null, refs: {dynaforge: 세션 id}}` — refs 는 세션
  id 하나로 고정한다(사용자 결정 — 포털이 같은 refs 로 막힘 줄을 걷는다). StepForge 과제 id 는 refs 밖 `links.step_forge`(linked_cad 가 있을
  때만). `inputs` = 세션 입력 파일(kind · ref=파일 id · sha256 · at) — sha256 이 빈 옛 행은 처음 볼 때 한 번 재서 남긴다(포털 입력 지문은 sha 를
  쓴다). `ready.deck_ready` = 덱 후보가 하나(입력 파일 가운데 덱 꼴 하나 — 둘 이상이면 거짓, 무엇을 낼지 모른다 · 포털 규칙은
  `kooremapper_mcp.deck_ready` 로 본다).
- **KR-AP2 해석 다섯** — 실행 원장 표 `auto_runs`(0028 — run_ref · idem_key 유일 · subject · profile · 세션 · 덱 파일 · stcx 잡 · 후처리 잡 ·
  리포트 · 상태 · 까닭 · 시각).
  - `auto_profiles` — profile 둘 `fullangle_162` · `fullangle_26`(Fibonacci 방향 수 · 높이 · 바닥 · 시간은 stcx op 기본값) · `cost.cores` = 방향
    × 2(ncpu 기본) · `minutes` null · `criteria_source` null · `service_identity`(제출 신원이 설정됐는지).
  - `auto_check` — 읽기만. missing 낱말 — `project_key` · `revision` · `input`(덱 없음 · 여럿) · `infra`(stcx 설정 없음 · 공유 폴더 SH-01 · 02
    전 — 설정 `KOORM_AUTO_DROP_INFRA_READY` 가 참이 아니면) · `permission`(제출 신원 없음).
  - `auto_submit` — 같은 idem_key 면 같은 run_ref(`created: false`). 갖춰지지 않았으면 `not_ready` + missing. 내면 stcx 잡을 만들고 run 원장에
    잇는다.
  - 사슬 나아가기 — `auto_status` · `auto_result` 를 부를 때(그리고 워커 주기에) run 을 앞으로 민다: stcx 잡이 Slurm 잡 id 를 얻으면 후처리 예약
    잡을 만들고, 예약이 리포트를 반입하면 done. 상태 다섯 낱말로 바꾼다.
  - `auto_result` — sphere 리포트의 수치(이름 · 단위 · 값 — 단위는 리포트 단위계에서, 모르면 그 수치를 빼고 notes) · verdict 는 늘
    `unknown`(사용자 결정) · artifacts 는 결과 폴더 · inputs 는 낸 덱. done 이 아니면 `not_done`.
  - `auto_cancel` — 아직 stcx 에 안 낸 run 만 취소(낸 뒤는 거절하고 까닭).
- **KR-AP3 신원** — 설정 `KOORM_AUTO_SERVICE_EMAILS`(쉼표)의 사용자가 부르면 auto_* 에서만 모든 세션 · 리포트를 본다(다른 도구는 그대로). 제출
  신원(서비스 계정 · KooSlurm 위임)은 운영 답 뒤 — 그 전엔 `service_identity: false` · `auto_submit` 은 `permission`.
- **KR-AP4 표지** — `auto_submit` · `auto_cancel` 은 readOnlyHint 없음(destructiveHint false), 나머지는 readOnlyHint true.
- **오류 꼴** — auto_* 의 실패는 MCP `isError` 와 글 본문 `{"error", "detail", "missing"?}` JSON(계약 §0.3 — isError false 로 오류를 싣지
  않는다).

## 3. 차례
1. 세션 칸 둘 + `auto_changes` + 신원 시야 + 표지 — 시험(쪽 끝까지 · null · 서비스 계정 시야).
2. `auto_runs` + 다섯(+cancel) — 가짜 stcx · 가짜 반입으로 사슬 끝까지 · idem · 상태 바꾸기 · 결과 봉투 · infra 막기.
3. 콘솔(세션 칸 둘) · MCP 설명 · 카탈로그 · 계약 §4 시험 전부 · 백엔드 전체 · MCP 계약 · 가지 push · 알림.
