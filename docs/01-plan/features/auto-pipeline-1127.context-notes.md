# 자동 파이프라인 맥락 — DynaForge 원천 + 전각도 낙하 해석

계획 `auto-pipeline-1127.plan.md` · 체크리스트 `auto-pipeline-1127.checklist.md`.

## 1. 사용자 결정(2026-11-27) — 고른 선택지의 설명 문장이 규격이다
- 세션 잇기 「세션에 과제 · 개발 단계 칸」 — 세션에 허브 과제(과제명)와 개발 단계 칸을 새로 둔다. 사람이 콘솔 · MCP 로 넣고, 과제는 판 확정과
  같은 규칙(과제명 · 과제코드 · 옛 과제명 · 별칭 → 과제 하나, 못 풀면 거절)으로, 개발 단계는 dev_rev 꼴로 검사한다. 비어 있으면 auto_changes 가
  null 로 싣고 refs 에 세션 id 와 linked_cad 의 StepForge 과제 id 를 함께 싣는다.
- 판정 「기준 없이 수치만」 — profile 둘(전각도 Fibonacci 162 · 26 방향 — 높이 · 바닥 · 시간은 stcx 제출 op 의 기본값, 바꾸려면 profile 을
  고친다). verdict 는 늘 unknown 이고 metrics 에 최대 응력 · 최대 가속도 · 소성 핫스팟 수 등을 단위와 함께 싣는다(limit 없음). 기준과 출처가
  정해지면 그때 더한다.
- 신원 「auto_* 만 모두 읽기」 — 설정에 적은 게이트웨이 서비스 계정으로 부를 때 auto_* 도구에서만 모든 세션 · 리포트를 읽게 연다(다른 도구 ·
  사람 신원은 그대로). 제출 계정은 운영 답 전까지 auto_profiles 의 service_identity 를 false 로 두고 auto_submit 은 permission 으로 막는다.

## 2. 대 본 것(11-27)
- 세션 칸 · 파일 sha256 · `updated_at` 의 움직임 · 낙하 사슬의 op 인자 · 리포트의 단위계 · MCP 오류 꼴 · 신원 전달은 계획 1절.
- 덱 하나를 고르는 규칙은 계약에 없다 — v1 은 「세션 입력 파일 가운데 덱 꼴이 하나」 일 때만 준비로 본다(둘 이상이면 무엇을 낼지 모른다 —
  missing input 에 목록). 포털에 알린다.
- sphere 리포트의 수치 단위는 생성기가 검출한 단위계에서 읽는다. 단위계를 모르면(검출 안 됨) 그 수치는 싣지 않고 notes 에 까닭 — 계약 §4-4
  「단위가 비지 않는다」 와 「지어내지 않는다」 를 함께 지킨다.

## 3. 포털과 맞춘 것 · refs 결정(2026-11-27)
- hwaxportal-71 — 포털 검증기(contract.py)에 대 봤고 꼴이 맞다. 맞출 것 셋 — ① ready 키는 `deck_ready`(포털 규칙 `kooremapper_mcp.deck_ready`) ②
  inputs 의 sha256 은 채운다(포털 입력 지문은 원천 · kind · ref · sha256 — at 은 안 쓴다, sha 가 null 이면 같은 ref 의 새 덱이 새 실행이 안
  된다) ③ 같은 세션이면 refs 를 늘 같은 꼴로.
- ③ 은 고른 선택지 문장(「refs 에 세션 id 와 linked_cad 의 StepForge 과제 id 를 함께」)과 부딪혀 다시 물었다 — 사용자 「refs 는 세션 id 만」:
  refs 는 {dynaforge: 세션 id} 하나로 고정하고 StepForge 과제 id 는 refs 밖 `links.step_forge`(없으면 빠짐)로 따로 싣는다. 같은 세션은 칸을
  채우거나 CAD 를 잇거나 refs 가 같아 포털이 막힘 줄을 걷는다.
- 세션 파일의 sha256 은 올릴 때 채운다(`sessions/services.py`). 빈 옛 행은 auto_changes 가 처음 볼 때 한 번 재서 남긴다.

## 4. 2단계 짓기(2026-11-27)
- 실행 세션 — 원천 세션의 덱을 제출 계정(`KOORM_AUTO_SUBMIT_EMAIL`) 소유의 실행 세션에 복사해 그 안에서 돌린다. 원천 세션 주인과 제출자가 갈리면
  잡 · 리포트 주인이 둘이 되고, 후처리 예약의 KooSlurm 위임은 잡 주인 명의라서다. 실행 세션에도 과제 · 단계를 적는다.
- 사슬 — stcx 잡이 Slurm 잡 번호를 얻으면 곧 후처리 예약을 건다(예약이 귀환 매니페스트를 스스로 기다린다 — 기한 7일). 예약 인자는 잡 만들기
  라우트와 같은 검사(인자 · `build_eng_meta`)를 지나고 소속은 비운다(서비스 계정은 소속 머리를 안 보낸다). 사슬은 auto_status · auto_result 를
  부를 때 민다 — 포털이 상태를 묻는다. 끝난 stcx 잡에 Slurm 번호가 없으면(응답을 잃고 work_dir 로 되찾은 잡) 까닭과 함께 failed.
- 확인은 아무것도 바꾸지 않는다 — 빈 sha 는 재서 답에 싣되 커밋하지 않는다(처음 짠 판은 커밋했다 · 변이가 잡았다). auto_changes 는 처음 잰 sha
  를 남긴다(캐시).
- 수치 단위 — KooD3plotReader 환산표(`koo_deep_report/ontology/package.py`)를 따른다: ton-mm-s · g-mm-ms 응력 MPa, SI 는 Pa → MPa, ton-mm-ms 는
  일관 단위계가 아니라 응력 단위를 안 정한다. G 는 생성기가 단위계로 환산한 값이라 「G」. 단위계가 없거나 검출 안 됐으면 응력 · G 를 빼고 notes.
  dev DB 의 sphere 리포트 14개에는 단위계 기록이 없다(10-17 이전 생성기) — 새 판은 실주행 뒤에 잰다.
- `updated_at` 은 onupdate 라 run 을 고친 뒤 읽으면 비동기 지연 읽기가 터진다 — advance 끝에 다시 읽는다.
- 시험 — 잡 행의 상태 · 외부 표지를 바꿔 워커가 한 일을 흉내 낸다(stcx · 예약은 돌리지 않는다). 변이 14 / 14(처음 살아남은 둘 — 확인의 sha 커밋
  · 번호 없는 끝 — 은 시험이 그 길을 안 지났다).

## 5. 3단계(2026-11-27)
- 콘솔에는 세션을 고치는 화면이 하나도 없었다(`updateSession` 은 있는데 아무도 안 썼다 — DF-15 의 덱 판 · CAD 연결도 REST · MCP 뿐). 고른
  선택지가 「콘솔 · MCP 로 넣는다」 라 세션 화면 왼쪽 위에 과제 · 단계 칸 하나를 더했다(판 확정과 같은 자리표시 · 거절 글에 후보). 작업 트리에는
  node_modules 가 없어 주 체크아웃 것을 잠깐 이어 tsc 를 돌리고 걷었다.
- 계약 §4 — ① 같은 idem_key 하나(`test_the_same_idem_key_submits_once`) ② 확인은 바꾸지 않음(DB 수 · sha) ③ isError false 에 error 없음(MCP
  탐침) ④ 단위가 비지 않음 ⑤ 모르는 과제 · 단계는 null ⑥ 서비스 계정은 모든 세션.
- ★깨진 시험 판이 행을 남기면 다른 시험이 조용히 건너뛴다 — 첫 auto_drop 판이 지연 읽기로 깨져 정리를 못 해 running 잡 둘이 scratch DB 에
  남았고, 「running 잡이 이미 있다 — reconcile_orphans 는 전역」 인 시험 다섯이 건너뛰었다(건너뜀 12 → 19). 남은 행을 지우고(시험 사용자 ad_* ·
  ap_* 만) 다시 돌려 14(모두 환경 — MCP venv · mcp.sif · gmsh)로 돌아왔다. 건너뜀 수가 바뀌면 까닭을 본다.

## 6. app_version 은 비지 않는다(2026-11-27 · 포털 계약 13c3ac3e)
- hwaxportal-71 이 b950bef0 의 답 꼴을 포털 검증기에 그대로 넣어 봤다 — 감지 · 프로파일 · 확인 · 제출 · 상태 · 취소 · 수치 없음 봉투는 받는다.
  걸린 것 하나 — auto_result 의 app_version 이 None 이면(바이너리 없음 · BUILD_INFO 커밋 없음) 포털이 봉투를 버린다(envelope_invalid). 포털이
  계약 §2 · §4-4 를 고쳤다(원본 확인).
- 고침 — app_version 은 배포 빌드 커밋(BUILD_INFO — health revision 과 같다) 앞 8자리, 모르면(읽기 실패 포함) "unknown". 런타임에 git 이 없어
  「앱 자신의 빌드 커밋」 은 따로 없다. profiles 도 같은 함수라 함께 맞는다. 시험 넷(판 없음 · 빈 사전 · None · 읽기 실패) · 변이 빨강.
