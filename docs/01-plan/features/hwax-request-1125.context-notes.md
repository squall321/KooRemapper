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
