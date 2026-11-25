# 포털 요청 1125 맥락 — KooRemapper 몫

계획 `hwax-request-1125.plan.md` · 체크리스트 `hwax-request-1125.checklist.md`.

## 1. 받음 · 다시 대 보기(2026-11-25)
- R-04 — `dist-from-drive.sh` `_install_if_changed` 는 `cp -p` 로 대상을 제자리에 덮는다(SIF 고리 · BUILD_INFO). `stop.sh` 는 `instance stop …
  || true` 뒤 기다리지 않고, `restart-api-only.sh` 는 `sleep 1` 만 둔다. 포털 고침 `11874eb9`(HWAXPortal — 읽기만) 꼴을 따른다.
- 바이너리 · 화면 묶음의 `tar -x` 는 실측으로 안전하다 — GNU tar 1.34 가 먼저 지우고 새로 만든다(inode 49154170 → 49154171 · 열린 서술자는 OLD
  를 읽었다).
- R-09 — `RevisionPanel.tsx` 의 자리표시는 「과제코드」 인데 `PUT /reports/{id}/revision` 은 `set_revision` 에서 입력을 글자 그대로 `과제@판`
  열쇠로 쓴다. 허브 과제 key 는 과제명이다(`resolve_task` 머리 주석 — 과제코드는 `properties.task_code`). 자동 잇기에는 과제명 · 과제코드 · 옛
  과제명 · 별칭을 하나로 푸는 규칙(`exact_matches` · `_pick`)이 이미 있다.
- R-09 레시피 — `recipe_export_dir` 기본 `recipes`(platform/ 기준)는 씨앗 넷이 추적되는 자리다. 새로 등록한 레시피 폴더는 추적 밖이라 포털
  update 의 `git stash -u` 가 쓸어 간다(DB 에는 남는다 — 기동 때 git 에서 읽어 들이는 것은 DB 에 없는 것만). 씨앗의 새 판도 추적 파일을 고쳐
  같은 일을 당한다. 10-27 사용자가 고른 「DB 즉시 + 등록 시 git」 설계와 맞물려 사용자 결정이다.
- HP-71 — 우리 코어 클라이언트는 KR-14 로 `trust_env=False` 라 프록시 환경변수를 따르지 않는다(코어 받기는 NO_PROXY 와 무관). `_common.sh` 는
  루프백을 NO_PROXY 에 넣은 뒤(8행) .env 를 읽어(34행) .env 의 NO_PROXY 가 그것을 덮는다 — 예시에 루프백까지 적어야 한다.

## 2. R-04 같은 뿌리
- stop 바로 뒤 start(또는 지우기)가 기다리지 않는 자리는 요청한 둘 밖에 다섯이다 — `restart.sh:10`(stop · sleep 1 · start.sh) · `start.sh:94` ·
  `start.sh:157`(postgres stop → 곧바로 start_instance) · `reset-db.sh:15`(postgres stop → 곧바로 pgdata 지우기) · `supervisor.sh:201`(postgres
  stop → pg_start). `supervisor.sh:259` 의 mcp 는 사라진 것을 확인한 뒤에만 띄우므로(`gone_for_sure`) 다음 회차로 미뤄질 뿐이라 뺀다.

## 3. R-04 · HP-71 짓기(2026-11-25)
- `_install_if_changed` — 포털 `11874eb9` 꼴(심링크는 `readlink -f` 로 가리키는 파일 · 쓸 수 없는 대상은 먼저 보고 rc 2 · `mktemp` 를 대상 옆에
  · `cp -p` · `mv -fT`). 포털 시험 넷에 둘을 더했다 — 같은 내용이면 inode · mtime 그대로, 임시 파일을 만든 뒤 복사가 깨지면(원본을 못 읽음) 임시
  파일을 치운다.
- `wait_instance_gone` — 상한은 횟수가 아니라 `$SECONDS` 로 잰다. 모름(목록 실패)은 `instance_running` 이 조회마다 0.5초를 더 쉬어 횟수로 세면
  상한이 늘어난다.
- `stop.sh` 는 하나가 상한을 넘겨도 나머지를 끝까지 시도하고 rc 1. `restart-api-only.sh` 는 넘기면 start 없이 rc 1 — 모름이 이어지면 예전엔 stop
  뒤 1초 쉬고 start 를 걸었는데, 이제 사라졌다고 확인될 때까지 띄우지 않는다(감독자는 실패 rc 를 이미 로그에 남긴다 —
  `test_the_restart_failure_logs_the_real_exit_code`).
- 시험용 가짜 apptainer 는 stop 이 돌아온 뒤에도 목록에 몇 번 더 남고, 아직 있는 이름에 start 를 걸면 `already exists` 로 실패한다(실물과 같다).
  기존 배포 시험 둘(목록이 늘 실패하는 「모름」)은 상한을 1초로 줬다 — 안 주면 기본 60초를 기다린다.
- 변이 12 / 12 빨강(설치 다섯 · 기다리기 셋 · 두 자리 넷).
- HP-71 — 예시는 포털 경로 꼴(`https://<포털 도메인>/rootdesign/rootdesign/api`)을 쓰고 허브 직결 꼴은 괄호로 남겼다. `/core` 경고 줄은
  그대로다. NO_PROXY 자리표시에 루프백을 같이 적고 그 까닭(.env 가 스크립트의 루프백을 덮는다)과 코어 받기는 프록시를 안 따른다는 것(KR-14)을
  적었다.

## 4. 사용자 결정(2026-11-25) — 고른 선택지의 설명 문장이 규격이다
- R-04 범위 「다섯도 기다리게」 — restart.sh · start.sh 두 자리(postgres 재기동) · reset-db.sh(pgdata 지우기 전) · supervisor.sh(postgres
  재기동)에도 같은 wait_instance_gone 을 넣는다. 상한을 넘기면 그 걸음을 멈추고 rc≠0(감독자는 실패를 로그에 남기고 다음 회차에 다시 본다).
  자리마다 시험과 변이로 잰다.
- R-09 (가) 「풀고, 안 풀리면 거절」 — 확정 입력을 자동 잇기와 같은 규칙으로 풀어 그 과제명으로 잇는다. 없음 · 둘 이상이면 400 으로 거절하고
  후보를 보인다(허브 과제에 안 붙는 판을 만들지 않는다). 단 허브 거울에 과제가 하나도 없는 박스(코어 받기 꺼짐)는 지금처럼 글자 그대로 잇는다.
  자리표시는 「과제명 · 과제코드」.
- R-09 (나) 「데이터 뿌리 아래로」 — 내보내기를 데이터 뿌리(/data/svc/kooremapper/recipes — storage 와 같은 부모)로 옮긴다. 기동 때는 리포
  씨앗(platform/recipes, 추적)과 데이터 뿌리 둘 다 읽는다(DB 에 없는 것만 넣는 지금 규칙 그대로). 없는 publish 도구를 가리키는 문장 셋은 고쳐
  쓴다(git 반영은 사람이 데이터 뿌리에서 복사해 커밋). update 의 stash 와 무관해진다.

## 5. 함께 온 것(2026-11-25)
- hwaxportal-71 — 이번 묶음(R-04 · HP-71 · R-09 · ST-25-KR)은 로컬 커밋까지만 · 원격 가지에도 올리지 않는다. ⑥ 의 `origin/corelink-int` 는
  그대로 둬도 된다(main 아님 · 87 지시대로). 해제 뒤 main 에는 R-04 를 먼저.
- hwaxportal-71(SignalForge 가 찾음) — `_common.sh` 가 .env 를 bash 로 source 하므로 따옴표 없는 `<포털 도메인>` 은 리다이렉션으로 읽힌다.
  자리표시가 든 값은 따옴표로 감싼다(SignalForge `157a2e6`). 바꾸지 않은 자리표시 주소가 요청 전에 걸러지는지도 본다.
- smarttwinmcp-c8 — KooSlurm `feat/c1-job-status-runs` `e5cb6f41` 에 job_status `runs: true`(각도마다 doe · step · case_key · angle · run_dir ·
  d3plot(있을 때만) · status — KooChainRun 값 그대로 running/completed/failed/pending). 운영 반영은 그쪽 사용자 승인 대기. KR-19 결과 회수 때 쓸
  칸이다 — 지금은 받기만.

## 6. 결정 뒤 짓기(2026-11-25) — 모두 로컬 커밋
- HP-71 따옴표(`0c08172`) — 예시의 자리표시 값(코어 주소 · NO_PROXY)을 따옴표로. 실측 — 따옴표 있으면 source 되고, 없으면 rc 1. 바꾸지 않은
  자리표시 주소는 httpx 가 보내기 전에 InvalidURL 을 던지는데 HTTPError 가 아니라 층 1(`SpCoreClient.get`) 밖으로 예외가 샜다 — `bad_url` 결과로
  멈추게 했다(다시 하지 않는다 · 아무 데도 안 닿았다). 키트(requests)는 `except Exception` 으로 잡아 이 틈이 없다.
- R-04 다섯(`3a7393d`) — restart.sh · start.sh 두 자리 · reset-db.sh · supervisor.sh. 감독자 pg 시험의 가짜 apptainer 는 stop 뒤에도 목록에 남게
  짜여 있어(기다리기가 없을 때는 상관없었다) 실물처럼 빠지게 고치고, 안 빠지는 경우 한 항을 더했다. start.sh 두 자리는 통째로 돌리기 어려워
  「모든 스크립트의 instance stop 뒤에 기다리기가 있는지」 훑는 항으로 지킨다(예외는 감독자 mcp 하나 — 까닭을 시험에 적었다). 변이 5 / 5.
- R-09 (가)(`654079d`) — `resolve_confirm_task`. 허브 거울은 `source=hub` 과제만 센다(우리가 만든 과제 행은 거울이 아니다). 처음 변이에서 그
  거르기가 살아남았다 — 시험 DB 에 과제 행이 하나도 없어 구분을 안 잰 것이라 우리 과제 행을 넣어 잰다. 거절은 400 `task_unresolved` — 후보를
  `data` 와 글 둘 다에 싣는다(화면 · MCP 는 글을 보인다).
- R-09 (나)(`1334095`) — 기본 내보내기는 `/data/svc/kooremapper/recipes`(dev 는 koopark 소유라 쓸 수 있음 확인). 그 자리가 없는 박스는
  `platform/infra/data/recipes` — 선택지 문장에 없는 자리라 보고에 적는다(git 밖 · postgres 데이터와 같은 자리). 운영 노드의
  `/data/svc/kooremapper` 에 API 사용자가 못 쓰면 등록은 되고 파일 내보내기만 경고(`exported: null`)다. 옛 자리(platform/recipes)에 쌓인 추적 밖
  폴더는 기동 때 씨앗으로 계속 읽힌다(DB 에도 있다).
- 백엔드 전체 1166 통과 · 4 실패는 작업 트리에 `.env` 가 없는 supervisor_log 넷(앞 판과 같다). 그 넷은 진짜 `supervisor.sh --once` 를 떠 있는
  dev 인스턴스에 돌리는 시험이라 작업 트리에서 억지로 돌리지 않는다(예시 .env 로 돌리면 dev API 를 작업 트리 코드로 재기동할 수 있다) — 올릴 때
  주 체크아웃에서 8 ~ 30 초 창에 돌린다. 바꾼 갈래(postgres 무응답)는 가짜 apptainer 시험(`test_supervisor_pg_liveness`)이 잰다. MCP 계약 13 /
  13.

## 7. C-1 운영 반영(2026-11-25)
- smarttwinmcp-c8 — job_status `runs: true` 가 운영(:5013)에 반영됐다(KooSlurm main `e5cb6f41` · 반영 기록 `0b46313f` — 리포 로컬 참조로 확인 ·
  smarttwin-mcp 11-25 02:50 UTC 재시작 · 실제 MCP 클라이언트로 스키마 통과 확인).
- ★부르는 꼴 — job_status 는 직접 도구라 MCP inputSchema 가 일반 `args` 객체 하나다. `runs` 는 그 `args` 안에 넣는다(게이트웨이를 거쳐도 같다).
  KR-19 결과 회수를 지을 때 이 꼴로 부른다.
- 읽는 법(우리가 적어 보낸 것과 그쪽 뜻이 같다고 답함) — status 는 KooChainRun 값 그대로 · d3plot null 은 「아직 없음 · 못 찾음」 · 재시도
  각도는 마지막 Run 만 · 각도 DOE 가 아니면 `runs: []` + `runs_note`.
