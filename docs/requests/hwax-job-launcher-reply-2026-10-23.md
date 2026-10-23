<!-- 답신 — HWAX Portal 운영의 실행기(launcher) 요청(hwax-job-launcher-request-2026-10-23.md)에 대한 KooRemapper 쪽 답 -->
# 답신 — 실행기(launcher) 설정 (2026-10-23)

대상 HWAX Portal 운영(HWAXProd) · 요청 `docs/requests/hwax-job-launcher-request-2026-10-23.md`(기준 `559f582`) · 반영 **`a3e9636`**(origin/main)

**한 줄**

- K1–K7 을 모두 넣었다. **설정이 비면 지금과 똑같다.** 기존 시험 578 이 그대로 통과하고, V1 시험 셋이 그것을 고정한다.
- 이 박스(smarttwincluster) API 는 설정을 비운 새 판으로 다시 띄웠다(H7 ①). MCP → API → 워커 경로로 database · meshfix 가 succeeded 이고, 잡의 `env_snapshot.launcher` 는 null 이다.
- 열린 질문 — ① 바이너리는 125 로 끝나지 않는다(코드 감사). ② NFS 는 측정을 기다린다. 우리 관점과 선택지는 3장에 적었다. ③ 권장안은 A(`nodename` 은 그대로 두고 `job_node` 를 더한다)다. 아직 넣지 않았다.
- 요청서의 사실 주장은 전부 맞았다. `파일:줄` 은 `559f582` 기준 ±1줄이다. getenv 넷, `omp_set_num_threads` 없음, `ldd`(libpq · sqlite 없음), Job 에 pid 칸 없음, stdin `/dev/null` 까지 다시 확인했다.

---

## 1. 넣은 것

| # | 자리 | 동작 | 덧붙임 |
|---|---|---|---|
| K1 | `config.py` `job_launcher` · `runner_loop._run_blocking` | 값이 있으면 `[*shlex.split(실행기), --job-id, <id>, --kind, argv[0], --, <바이너리>, *argv]` 로 띄운다. cwd · `.job_<id>.out/.err` · `text` · `start_new_session` · `_running` 은 그대로다 | 접두를 붙이는 곳은 이 한 곳뿐이다. 업로드 검사 · 출력 검사 · `kooremapper_bin` 은 로컬 그대로다. `argv[0]` 은 늘 연산 이름이다(위치 인자 꼴 · yaml 꼴 모두 `[op, …]` 로 시작한다) |
| K2 | 시간 초과 | 실행기가 있을 때만 SIGTERM → `job_term_grace_sec`(`KOORM_JOB_TERM_GRACE_SEC`, 기본 5) → SIGKILL 순서다. rc 124 와 `[timeout exceeded]` 줄은 그대로다 | 벽시계는 최대 `job_timeout_sec + 유예` 다 |
| K3 | `stop_worker` | 실행기가 있을 때만 TERM 을 먼저 보내고 2초를 기다린다(`_STOP_TERM_GRACE_SEC`). 남은 것에 SIGKILL 을 보낸다 | 종료로 끊긴 잡은 지금 `exit -9` 로 남는다. 앞으로는 실행기의 종료 코드(예 `exit -15`)로 남는다 |
| K4 | `reconcile_orphans` | 실행기가 있으면 `SELECT id … status='running' AND external_kind IS NULL` 를 먼저 한다. 잡마다 `<실행기> --reap <id>` 를 **한꺼번에** 부르고, 그 뒤에 기존 UPDATE 를 한다 | 한 번에 15초 상한이다(`_REAP_TIMEOUT_SEC`). rc≠0 · 시간 초과 · 실행 실패는 경고 한 줄(`job <id>: 실행기 --reap …`)만 남기고 진행한다. stdin 은 `/dev/null` 이고, stderr 는 rc≠0 일 때 꼬리 300자만 로그에 남긴다 |
| K5 | 자식 환경 | 실행기가 있을 때만 허용 목록 `PATH LANG LC_* HOME TMPDIR OMP_* KOOREMAPPER_GMSH KOO_*_DEBUG` 를 준다. `--reap` 호출에도 같은 목록을 쓴다 | 요청서 목록 그대로다. 설정이 비면 `env=` 를 넘기지 않는다(지금처럼 물려준다) |
| K6 | `_env_snapshot` | `"launcher": settings.job_launcher or None` | ⚠ 아래 4장 — 이 줄은 DB 와 진단 번들에 그대로 남는다 |
| K7 | 세션 삭제 | `rmtree` 뒤에도 폴더가 남으면 1초 뒤 한 번 더 지운다. 그래도 남으면 경고 한 줄(`session <id> 삭제: 폴더가 남았다(항목 N개, 그중 .nfs* M개)`)을 남긴다 | **설정과 무관하게** 돈다. 폴더가 남을 때만 움직이고, 그 경우는 지금은 조용히 지나간다. 파일 이름은 로그에 적지 않는다 |

새 설정 둘은 `platform/ENVIRONMENT.md` 와 `platform/.env.example` 에 적었다. 환경 변수로 줘도 되고 `platform/.env` 에 둬도 된다(컨테이너 안에서 앱이 `/workspace/platform/.env` 를 직접 읽는다). `start.sh` 는 고치지 않았다.

## 2. 확인 (요청서 5장)

`platform/backend/tests/test_job_launcher.py` 21개, backend 전체 **599 통과**(기존 578 + 21)다. 시험용 실행기는 `platform/backend/tests/data/launcher/` 에 있다. `passthrough.sh` · `childwrap.py` 는 요청서 1-4 원문이고, 실패(125) · 정리 기록 · TERM 무시 · 환경 이름 · 원격 흉내 · 느린 가짜 바이너리를 더했다.

| # | 결과 |
|---|---|
| V1 | 설정이 비면 Popen 은 `[bin, *argv]` 이고 `env=` 가 없다. 시간 초과는 `[SIGKILL]` 만, 종료도 `[SIGKILL]` 만 간다. 기존 시험 전부 통과 |
| V2 · V3 | 다섯 op 를 직접 · `passthrough.sh` · `childwrap.py` 세 가지로 돌렸다. op 는 generate → map(위치 인자 · OpenMP · 진행률 %) · database(yaml) · matdb(번들 DB) · meshfix(gmsh)다. 상태 · 종료 코드 · 오류 요약 · 산출 이름 · 내용 해시 · `_live_progress` 가 모두 같고, 등록한 sha256 은 디스크와 같다. 내용 해시는 실행 시각 줄(`$ Date:`)을 빼고 쟀다. 같은 op 를 두 번 돌려 diff 하면 다른 것은 그 줄뿐이다 |
| V4 | `childwrap.py` 를 취소하면 canceled 가 되고, 남은 프로세스는 0, 5초 안이다 |
| V5 | 실행기가 125 와 `[launcher] no node` 를 내면 failed 가 되고, `error_summary` 에 그 줄이 있으며 산출은 0이다 |
| V6 | 실행기에만 SIGKILL 을 보냈다. failed 가 되고 `error_summary` 는 `exit -9…` 로 시작한다. 같은 세션의 다음 잡은 succeeded |
| V7 | TERM 을 무시하는 실행기는 `[SIGTERM, SIGKILL]` 을 받고, 둘 사이는 유예만큼이다. TERM 을 따르는 실행기는 `[SIGTERM]` 만 받고 곧 나온다. 둘 다 rc 124 이고 `[timeout exceeded]` 가 남는다. 원격 흉내 실행기(실행기가 죽어도 자식은 산다)에서는 **등록한 해시가 끝난 파일과 같다.** 옛 순서(바로 SIGKILL)를 끼우면 이 셋이 실패한다. 마지막 것은 「등록한 뒤에 파일이 바뀌었다」로 잡힌다 |
| V8 | 고아 둘을 두고 돌렸다. 둘 다 `--reap` 를 받았고, 행은 failed(`worker restarted while job was running`)가 되며, `finished_at` 은 정리 시각보다 뒤다. 정리는 한꺼번에 돈다(1초짜리 둘이 1.8초 안). `--reap` 가 rc 3 으로 끝나거나 멈춰도(상한) 행은 닫힌다 |
| V9 | 동시 수 8, 잡 12개로 `_loop` 를 그대로 돌렸다. 최대 동시는 **8**이다. 클레임은 메모리 큐로 바꿨다(시험 DB 가 떠 있는 API 의 DB 라 queued 행을 그 워커가 집어 간다). 세션당 하나는 기존 시험 `test_a_running_local_job_still_blocks_the_session` 이 고정한다(SQL 은 바꾸지 않았다) |
| V10 | 실행기가 받은 환경에 `KOORM_*` 가 없다. 허용 목록 밖의 토큰 꼴 이름도 없다. `PATH HOME OMP_NUM_THREADS KOO_MAP_DEBUG KOOREMAPPER_GMSH LC_ALL` 은 있다 |
| 컨테이너 | `api.sif`(같은 이미지 · `/workspace` 바인드) 안에서 허용 목록 환경으로 다섯 op 모두 rc 0 이다. meshfix 는 번들 gmsh 를 찾았다. 자식 환경 이름은 `HOME LANG LC_* PATH PWD` 다(`PWD` 는 sh 가 넣는다) |

## 3. 열린 질문

**① 종료 코드 125 — 나오지 않는다.** run 함수의 반환을 모두 셌다. 리터럴은 `return 0` 79곳, `return 1` 669곳, `std::exit(1)` 1곳이다. 계산된 반환(매핑 · 뒤집기 · 초기응력 · stackwrap · rebind · meshfix 미리보기 · help)은 이 값을 그대로 넘긴다. `main` 은 `std::exception` 을 잡아 1 로 바꾼다. 그 밖의 끝은 신호(표준 밖 예외의 abort −6, segfault −11)와 로더 실패(127)뿐이다. 그래서 L5 가 125 를 써도 겹치지 않는다. `passthrough.sh` 의 `exec` 가 실패하면 sh 가 126 · 127 을 내는데, 그것도 125 가 아니다.

**② NFS 위 판정 — 측정을 기다린다.** 우리가 보는 것은 다음과 같다.
- 출력 판정은 API 노드에서 `rglob` + `stat().st_mtime` 을 앞뒤로 떠서 비교한다(RL:586-591 · 623-627). 두 mtime 모두 API 노드의 클라이언트로 서버 값을 읽은 것이라 노드 사이 시계 차이는 끼지 않는다. 위험은 **API 노드의 캐시**다. 원격이 막 만든 파일이 목록에 안 보이거나, 덮어쓴 파일의 mtime 이 옛 값으로 보이면 출력을 놓친다.
- `.job_<id>.out/.err` 는 실행기가 **API 노드에서** 쓴다. 그래서 진행률 · `error_summary` 는 노드 사이 가시성에 달리지 않고, 원격이 직접 쓰는 산출만 달린다.
- 마운트로 푸는 쪽을 권한다(API 노드의 저장 루트, 잴 후보는 `lookupcache=positive|none` · `actimeo=0` · `noac`). 앱은 이 파일을 워커 밖에서도 읽는다(다운로드, 등록 때 `info`·`modelmeta` 검사, MCP 내려받기, 미리보기). 앱 쪽 대기는 워커만 덮는다.
- 마운트로 못 풀면 고를 길은 둘이다. (a) 실행기가 끝난 뒤 목록 · mtime 이 멈출 때까지 짧게 다시 뜬다(상한을 둔다). 간단하지만 짐작이다. (b) 실행기가 cwd 에 `.job_<id>.outputs`(상대 이름 목록)를 남기고, 앱이 그것을 자기 목록과 합친 뒤 파일마다 열어 본다(열 때 다시 확인된다). 정확하지만 계약이 하나 는다. 우리는 (b) 쪽으로 기우는데, 측정을 본 뒤 정하겠다.
- 덧붙임 — 판정 시점에 `.nfs*` 가 있으면 출력으로 등록된다(빼는 것은 `.job_*` 뿐이다). `.nfs*` 를 빼는 것은 한 줄 고침이다. 요청 밖이라 아직 넣지 않았고, 원하면 넣겠다.

**③ 실제 노드 기록 — 권장 A. 아직 넣지 않았다.**

| 안 | 내용 | 득실 |
|---|---|---|
| **A (권장)** | `host.nodename` 은 그대로 둔다(API 노드 — 등록 · 검사가 돈 곳). 잡이 끝난 뒤 cwd 의 `.job_<id>.node` 첫 줄을 읽어 `host.job_node` 에 적는다. 파일이 없으면 null | 기존 칸의 뜻이 바뀌지 않는다. 번들 · 요약에 두 노드가 함께 보인다 |
| B | 실행기가 남긴 노드가 있으면 `host.nodename` 을 그것으로 바꾼다 | 칸 하나로 끝나지만 같은 칸이 잡마다 다른 뜻이 된다 |
| C | K6 만(지금 상태) | 노드는 실행기 기록에만 있고 진단 번들에는 안 보인다 |

A 로 정해지면 계약은 `.job_<id>.node` 한 줄(노드 이름만, 짧은 영숫자 · `.` · `-` · `_`)로 둔다. 앱은 길이와 글자를 잘라 읽는다.

## 4. 알릴 것

- **실행기 인자에 비밀을 넣지 말 것.** K6 로 실행기 명령 줄이 잡마다 DB(`env_snapshot`)에 남고 진단 번들에도 실린다. 번들은 저장소 · 홈 · `/workspace` 경로를 접고 토큰 꼴(`kr_…` · `Bearer …`)을 지울 뿐이다. 실행기 설정은 파일로 주라(L2 의 「설정 값의 인자나 파일」 중 파일).
- **OpenMP 를 쓰는 곳은 두 곳이다.** 요소 품질 분석(`ElementAnalyzer`)과 매핑(`MeshRemapper`)이다. 스레드 수를 코드에서 정하지 않으므로 실행기가 주는 `OMP_NUM_THREADS` 가 정한다. 주지 않으면 libgomp 가 affinity 안의 CPU 를 다 쓴다. 나머지 op 는 한 스레드다. gmsh 는 바이너리가 절대 경로로 띄우는 별도 프로세스이고, 그 스레드 수는 재지 않았다.
- **API 의 환경.** 이 박스의 API 프로세스 환경에는 `KOORM_*` 말고도 토큰 · API 키 꼴 이름이 여럿 있다(이름만 셌다). 인스턴스를 띄운 셸의 환경을 그대로 물려받기 때문이다(`--cleanenv` 없음). K5 는 실행기 쪽 자식에서 그것을 끊는다. prod 가 uvicorn 을 직접 띄울 때는 `apptainer exec --cleanenv` 에 필요한 값만 `--env`/`.env` 로 주기를 권한다.
- **로컬에도 같은 틈이 있다(바꾸지 않았다).** API 가 갑자기 죽으면 로컬 바이너리는 새 세션이라 남는다. 재기동이 행을 failed 로 닫으면 같은 세션의 다음 잡이 같은 폴더에서 먼저 시작될 수 있다(요청서 K4 의 지적 그대로다). 이번 변경은 실행기 길만 막는다.
- **3장 설정은 건드리지 않았다.** 바인드 · `KOORM_PORTAL_BASE` · `KOORM_STORAGE_DIR` · 동시 수 · `KOORM_DATAHUB_URL=` · `KOORM_STCX_BACKEND_URL=` 의 코드 길은 바뀌지 않았다. 전체 시험 통과로 확인했다.

## 5. 배포 · 되돌림

- `a3e9636` 은 Python 만 바꿨다. 바이너리 · SIF · Drive 아티팩트는 그대로다(바이너리 sha `cd07c327…`).
- 이 박스는 10-23 에 API 를 다시 띄웠다(설정은 비운 채). 재기동 전에 queued · running 잡이 0 인 것을 확인했다.
- 되돌림은 설정을 비우고 API 를 다시 띄우면 된다. 설정이 비었을 때 도는 길은 옛 길 그대로다.

## 6. 덧붙임 — 결정 반영 (2026-10-23 저녁)

- **③ 실제 노드 기록 — 안 A 를 넣었다.** 잡이 끝나면 cwd 의 `.job_<id>.node` 첫 줄을 읽어 `env_snapshot.host.job_node` 에 적는다.
  노드 이름만 받는다(영숫자 · `.` · `-` · `_`, 64자 이하). 꼴이 아니거나 파일이 없으면 null 이다. `host.nodename` 은 그대로 API 노드다.
  그 파일은 `.job_*` 라 출력으로 등록되지 않는다.
- **`.nfs*` 를 출력 등록에서 뺐다.** NFS 가 열린 채 지운 파일에 붙이는 이름이다. 판정 때 남아 있어도 산출로 올리지 않는다.
- **NFS 판정은 H5 측정을 그대로 기다린다.** 로컬 고아 틈도 바꾸지 않았다.
