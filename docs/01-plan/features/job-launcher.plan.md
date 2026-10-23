# 실행기(launcher) 설정 — job 을 다른 노드에서 (2026-10-23)

**날짜** 2026-10-23 · **요청** HWAX Portal 운영 요청서(`docs/requests/hwax-job-launcher-request-2026-10-23.md`, 기준 `559f582`)
· 답신 `docs/requests/hwax-job-launcher-reply-2026-10-23.md`

## 왜
prod 를 CPU 노드 두 대에 올리고 job 자식만 두 노드에 나눠 돌린다. 지금 러너는 바이너리를 API 프로세스의 로컬 자식으로
띄워(`runner_loop._run_blocking`) 실행 명령을 바꿀 자리가 없다. 운영 쪽이 만든 실행기가 노드를 고르고 같은 SIF 로 원격에서
띄우므로, 앱은 **명령 앞에 실행기를 붙이고 신호 순서만 맞추면** 된다. job 자식은 파일만 읽고 쓴다(DB·소켓 없음 — `ldd` 로 확인).

## 범위 (요청서 2장)
- **K1 (P1)** `job_launcher`(`KOORM_JOB_LAUNCHER`). 값이 있으면 `[*shlex.split(실행기), --job-id, id, --kind, argv[0], --, 바이너리, *argv]`.
  접두는 `_run_blocking` 한 곳뿐 — 업로드 검사·출력 검사·`kooremapper_bin` 은 그대로.
- **K2 (P1)** 시간 초과 — 실행기가 있을 때만 SIGTERM → `job_term_grace_sec`(새 설정, 기본 5) → SIGKILL. rc 124 · `[timeout exceeded]` 유지.
- **K3 (P2)** `stop_worker` — 실행기가 있을 때만 TERM 먼저, 유예 2초(lifespan 3.5초 · uvicorn 5초 안).
- **K4 (P2)** `reconcile_orphans` — 실행기가 있으면 running 로컬 잡마다 `<실행기> --reap <id>`(시간 제한 · 실패해도 진행) 뒤에 UPDATE.
- **K5 (P3)** 실행기가 있을 때만 자식 환경을 허용 목록으로(`PATH LANG LC_* HOME TMPDIR OMP_* KOOREMAPPER_GMSH KOO_*_DEBUG`).
- **K6 (P3)** `_env_snapshot` 에 `"launcher": settings.job_launcher or None`.
- **K7 (P3)** 세션 삭제 — `rmtree` 뒤 폴더가 남으면 한 번 더 지우고, 그래도 남으면 로그 한 줄.

## 바꾸지 않는 것
설정이 비면 argv · 신호 순서 · 환경 · 출력 · 종료 처리가 지금과 똑같다(V1 이 시험으로 고정). 클레임 · 세션당 하나 ·
동시 수 · 취소 API · gmsh 호출 · API 프로세스 안의 검사는 손대지 않는다. 새 의존성 없음(표준 라이브러리).

## 시험 (요청서 5장 V1–V10)
- 새 파일 `platform/backend/tests/test_job_launcher.py` + 시험용 실행기 `tests/data/launcher/`(요청서 1-4 의 둘 + 실패·reap 기록·원격 흉내).
- DB 시험은 행을 **running** 으로 넣고 `_execute` 를 직접 부른다 — queued 로 넣으면 떠 있는 API 워커가 같은 DB 에서 집어 간다.
- V9 는 `_loop` 를 그대로 돌리고 클레임만 메모리 큐로 바꾼다(같은 이유). 세션당 하나는 기존 `test_a_running_local_job_still_blocks_the_session` 이 고정한다.

## 배포
Python 만 바뀐다 — 커밋 · 푸시 → API 재기동(소스는 바인드). 바이너리 · SIF · Drive 아티팩트는 그대로다. 설정은 비운 채 둔다(도입 순서 H7 ①).

## 답할 질문
1. 바이너리 종료 코드 125 — 코드 경로 감사로 답한다.
2. NFS 위 출력 판정 — 측정을 기다리며 앱 쪽 관점을 적는다.
3. 실제 노드 기록 — 선택지와 권장안을 사용자에게 올린다(혼자 정하지 않는다).
