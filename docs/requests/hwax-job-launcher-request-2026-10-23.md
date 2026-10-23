<!-- 받은 요청서 원문(2026-10-23). 요청자 메일 주소만 역할 이름으로 바꾸고, 붙여 넣기로 생긴 코드 블록 안 빈 줄을 걷었다. 답신은 hwax-job-launcher-reply-2026-10-23.md -->
# KooRemapper(DynaForge) — job 을 다른 노드에서 돌릴 수 있게 '실행기(launcher)' 설정 하나 (2026-10-23)

요청일 2026-10-23 · 요청자 HWAX Portal 운영 · 대상 **KooRemapper(DynaForge)**(github.com/squall321/KooRemapper)

기준 — `559f582`(cae00 체크아웃 HEAD, 로컬 변경 없음, 지금 도는 API 가 이 판이다). 아래 `파일:줄` 은 이 판의 리포 루트 기준으로 다시 대조했다.

근거 — 코드 대조와 cae00 실측(10-23, 읽기 전용: 프로세스 · 환경변수 이름 · 마운트 · 네트워크 이름공간 · 컨테이너 안 도구 · DB 행 수). 같은 꼴의 요청을 StepForge 에도 따로 보낸다(`STEPFORGE-JOB-LAUNCHER-REQUEST.md`).

**한 줄**

- prod 를 CPU 노드 두 대(h02 · h03)에 올리고 job 을 두 노드에 나눠 돌리려 한다. 앱은 노드를 몰라도 된다. 운영 쪽(HWAXProd)이 만든 실행기가 노드를 고르고, 그 노드에서 **같은 SIF** 로 job 을 띄운다.

- 필수는 둘이다. 접두(K1)와 시간 초과 때 SIGTERM 먼저(K2). job 자식(C++ 바이너리)이 파일만 읽고 쓰기 때문이다. 자식 환경에서 비밀 값을 빼는 일은 실행기가 한다(L2).

- 설정이 비어 있으면 지금과 똑같다(V1 로 확인한다).

- 그 밖의 prod 이전(127.0.0.1 바인드, 웹 접두, 연동 끄기)은 코드 수정 없이 설정으로 한다(3장). 그 설정들이 지금처럼 동작하도록 유지해 달라.

우선 — **P1** 없으면 다른 노드에서 못 돈다 · **P2** 없어도 돌지만 종료 · 재기동 때 틈이 남는다 · **P3** 있으면 낫다(선택).

줄임: RL = `platform/backend/app/worker/runner_loop.py`, CFG = `platform/backend/app/config.py`, JR = `platform/backend/app/modules/jobs/routes.py`, SS = `platform/backend/app/modules/sessions/services.py`, BIN = `platform/backend/app/runner/binary.py`.

---

## 0. 배경

| 항목 | 운영 구조 |

|---|---|

| 노드 | CPU 노드 2대(h02 · h03). GPU 없음. 두 노드가 같은 NFS `/data3` 를 본다 |

| 앱 한 벌 | API · 러너 · DB 는 가동 노드 한 곳에서만 돈다. 노드마다 API 를 따로 띄우지 않는다(기동 때 running 행을 전부 failed 로 닫으므로 API 가 둘이면 서로의 job 을 죽인다, RL:702-720) |

| DB | 가동 노드 로컬 디스크의 Postgres. NFS 에 두지 않는다 |

| 파일 | job 이 읽고 쓰는 세션 폴더와 job 로그는 `/data3` 공유 루트(`KOORM_STORAGE_DIR`)에 둔다. 두 노드에서 같은 경로로 보인다 |

| 나누는 것 | job 자식 프로세스만 나눈다. 노드 선택 · 원격 실행 · 남은 프로세스 정리는 HWAXProd 실행기가 한다 |

| 실행 경계 | 앱은 apptainer 컨테이너 안에서 돈다. 실행기는 앱의 자식이므로 **앱 컨테이너 안**에서 뜬다. 그래서 컨테이너 안에서 보이는 경로(바인드)에 있어야 하고, 컨테이너 안에는 ssh · apptainer 가 없다(10-23 실측). 실행기는 같은 노드의 호스트 쪽 도우미에 루프백으로 붙는다(컨테이너가 호스트 네트워크 이름공간을 쓴다, 같은 실측). 원격 노드의 도우미가 **같은 이미지 · 같은 바인드 · 같은 cwd** 로 바이너리를 띄운다. 이 경계 너머는 전부 HWAXProd 몫이고 앱은 모른다 |

| 왜 앱 수정이 드나 | job 을 API 프로세스의 로컬 자식으로 띄운다(RL:166-184). 실행 명령을 바꿀 자리가 없다 |

---

## 1. 실행기 계약

### 1-1. 설정

| 설정 | 비었을 때 | 값 |

|---|---|---|

| `KOORM_JOB_LAUNCHER`(설정 `job_launcher`) | 지금과 같다 | 명령 한 줄. `shlex.split` 으로 나눈다. 고정 인자를 넣을 수 있다(예 `/usr/local/bin/python3 /opt/hwaxprod/bin/forge-launch --app kooremapper` — 컨테이너 안 경로이고, 그 폴더는 HWAXProd 가 바인드한다) |

### 1-2. 앱이 하는 것

설정이 있으면 job 자식의 argv 를 아래 꼴로 바꾼다. 다른 것은 바꾸지 않는다.

```
<실행기 설정을 shlex.split 한 것…> --job-id <job id> --kind <연산 이름> -- <원래 argv…>
```

| 항목 | 앱이 주는 것 |

|---|---|

| `--kind` | 연산 이름(`argv[0]`) |

| 원래 argv | `[kooremapper_bin, *argv]` |

| cwd · 환경 · stdout/stderr · stdin | 지금 자식에 주던 그대로 실행기에 준다(`.job_<id>.out/.err` 파일, stdin 은 10-23 실측으로 `/dev/null`). 환경을 줄이는 것은 실행기다(L2). K5(선택)를 넣으면 앱에서도 줄어든다 |

| 프로세스 그룹 | 지금처럼 `start_new_session=True`. 실행기가 그룹 리더가 된다 |

| 종료 코드 · 신호 | 실행기의 것을 지금 자식의 것처럼 읽는다 |

스레드 수 · 노드 · 슬롯은 앱이 넘기지 않는다. 실행기가 정한다.

### 1-3. 실행기가 지키는 것(HWAXProd 책임)

| # | 항목 | 내용 |

|---|---|---|

| L1 | argv 유지 | 자기 argv 를 바꾸지 않는다 |

| L2 | 환경 · cwd | 받은 cwd 를 원격에 그대로 쓴다. 환경은 바이너리가 읽는 이름만 넘긴다: `PATH LANG LC_* HOME TMPDIR OMP_* KOOREMAPPER_GMSH KOO_*_DEBUG`(바이너리의 `getenv` 는 `src/commands/meshfix.cpp:254, 306` · `src/mapper/MeshRemapper.cpp:1033` · `src/remesh/TetGenRemesher.cpp:158` 뿐이다). API 환경의 `KOORM_DATABASE_URL` · `KOORM_JWT_SECRET` · `KOORM_GATEWAY_PAT` · `KOORM_ADMIN_PASSWORD` · `KOORM_HEAX_GATEWAY_SECRET`(이름만 확인했다)가 다른 노드로 가지 않게 한다. 노드에 맞춰 덮어쓰는 것은 `OMP_NUM_THREADS` 뿐이다. 실행기 자신의 설정은 환경이 아니라 설정 값의 인자나 파일로 받는다. 환경 값은 어디에도 적지 않는다 |

| L3 | 출력 | 원격 stdout · stderr 를 각각 받은 파일로 바로 흘린다. 성공 길에서는 자기 줄을 한 줄도 더하지 않는다. `error_summary` 는 stderr 꼬리를 쓰고, stderr 가 비었을 때만 stdout 의 `[ERROR]` 줄로 간다(RL:661-675) |

| L4 | 종료 코드 | 원격 종료 코드를 그대로 낸다. 원격이 신호 N 으로 죽었으면 같은 신호를 자기에게 다시 걸어 끝난다(부모가 `-N` 을 본다. 자기 코어 덤프는 끈다) |

| L5 | 실행기 자신의 실패 | 노드 없음 · 통로 끊김 · 원격 시작 실패는 종료 코드 **125** 와 stderr 한 줄 `[launcher] <까닭>` 으로 끝낸다. 원격에서 시작하지 못했으면 아무것도 남기지 않는다 |

| L6 | 신호 | SIGTERM · SIGINT 를 받으면 원격 job 의 프로세스 그룹에 SIGTERM 을 보내고, 3초 뒤 남았으면 SIGKILL 을 보낸다. 원격이 끝난 것을 확인하고 L4 대로 나온다. 받은 뒤 5초 안에 나온다(취소는 5초 뒤 그룹에 SIGKILL 을 보낸다, RL:683-698) |

| L7 | 실행기가 죽을 때 | 실행기가 SIGKILL 등으로 죽거나, 자기를 띄운 앱 프로세스를 잃으면(부모 pid 가 바뀌면) 원격 job 의 그룹도 끝난다. 원격 쪽 임대(연결이 끊기면 그룹 종료)로 지킨다. 앱이 실행기에 SIGKILL 을 보내는 자리가 지금 있다: 시간 초과(RL:179) · 종료(RL:828) |

| L8 | 기다리지 않는다 | 빈 자리를 기다리며 줄 서지 않는다. 바로 올리거나 L5 로 끝낸다. 시간 제한 시계는 띄운 순간부터 돈다(RL:177) |

| L9 | 시작 지연 | 몇 초 안에 원격을 띄운다. 그림 도구는 job 을 낸 뒤 기본 180초를 기다린다(`platform/mcp_server/server.py:443`) |

| L10 | 정리 하위 명령 | `<실행기> --reap <job id>`. 그 job 의 원격 프로세스가 남았으면 끝내고, 끝남을 확인한 뒤 0 으로 나온다. 여러 번 불러도 결과가 같고, 10초 안에 끝난다 |

| L11 | 노드 기록 | 어느 노드에서 돌았는지는 실행기 자기 기록에 남긴다. cwd 에 `.job_<id>.node` 를 써도 된다(RL:631 이 `.job_*` 를 출력에서 뺀다) |

### 1-4. 시험용 실행기

앱 쪽 시험은 아래 둘로 한다. 둘 다 노드를 고르지 않는다.

`passthrough.sh` — 그 자리에서 원래 명령이 된다(`exec`). pid · cmdline · 신호 · 종료 코드가 지금과 같다.

```sh
#!/bin/sh
# 시험용 실행기 — 노드를 고르지 않고 이 자리에서 원래 명령이 된다.
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--reap" ] && exit 0
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
exec "$@"
```

`childwrap.py` — 원래 명령을 **다른 그룹의 자식**으로 띄운다. 앱의 killpg 가 자식에 바로 닿지 않으므로 원격과 같은 조건이 된다.

```python
#!/usr/bin/env python3
# 시험용 실행기(별도 프로세스판) — 신호를 넘기고, 자식이 끝난 모양을 그대로 흉내 낸다.
import ctypes, os, resource, signal, subprocess, sys
a = sys.argv[1:]
head = a[:a.index("--")] if "--" in a else a
if "--reap" in head:
    sys.exit(0)
if "--" not in a:
    print("[launcher] no '--'", file=sys.stderr)
    sys.exit(125)
libc = ctypes.CDLL(None)
def die_with_parent():
    libc.prctl(1, signal.SIGKILL)   # PR_SET_PDEATHSIG — 실행기가 죽으면 직계 자식도 죽는다(L7 의 일부만 흉내 낸다)
p = subprocess.Popen(a[a.index("--") + 1:], start_new_session=True, preexec_fn=die_with_parent)
def fwd(sig, _):
    try:
        os.killpg(p.pid, sig)
    except ProcessLookupError:
        pass
for s in (signal.SIGTERM, signal.SIGINT):
    signal.signal(s, fwd)
rc = p.wait()
if rc < 0:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if -rc != signal.SIGKILL:
        signal.signal(-rc, signal.SIG_DFL)
    os.kill(os.getpid(), -rc)
sys.exit(rc)
```

실행기 실패 시험은 `echo "[launcher] no node" >&2; exit 125` 한 줄짜리로 한다. `--reap` 호출을 볼 때는 받은 id 를 파일에 적게 바꾼다.

---

## 2. 고칠 곳

**먼저 알 것.** job 자식은 C++ 바이너리 하나다. DB 연결 · 소켓 · HTTP · 부모 쪽 파이프가 없다(`ldd` 에 libpq · sqlite 없음, 10-23 실측). 결과는 종료 코드 · `.job_<id>.out/.err`(부모가 연 파일) · 세션 폴더의 파일로만 돌아온다. PID 를 저장하거나 살아 있는지 보는 코드도 없다(`platform/backend/app/models.py:219-275` 의 `Job` 에 pid 칸 없음). 그래서 접두와 신호 조정이면 원격에서 돈다.

| # | 우선 | 자리 | 할 일 |

|---|---|---|---|

| K1 | P1 | CFG:77-78 다음 · RL:168-174 | 설정 `job_launcher: str = ""`(`KOORM_JOB_LAUNCHER`)를 더한다. 값이 있으면 `cmd = [*shlex.split(job_launcher), "--job-id", job_id, "--kind", argv[0], "--", str(kooremapper_bin), *argv]` 로 띄운다. cwd · stdout/stderr 파일 · `text` · `start_new_session` · `_running` 등록은 그대로 둔다. 접두는 RL:168 한 곳에만 붙인다. 업로드 검사(BIN:31)와 출력 검사(RL:495-496)는 로컬 바이너리 그대로 둔다. `KOORM_KOOREMAPPER_BIN` 을 실행기로 바꾸는 길은 쓰지 않는다. 그 설정(CFG:69-70)은 헬스 해시 · gmsh 탐색 · matdb 기본 DB 경로(`platform/backend/app/runner/argbuild.py:22`) · 업로드 검사도 함께 움직인다 |

| K2 | P1 | RL:176-182(시간 초과) | 설정이 있을 때만 SIGTERM → 유예 `job_term_grace_sec`(새 설정, 기본 5) → SIGKILL 순서로 끝낸다. rc 124 와 `[timeout exceeded]` 줄은 그대로 둔다. 지금은 바로 SIGKILL 이다(RL:179). 로컬에서는 바이너리가 그룹 리더라 `proc.wait()` 가 돌아오면 바이너리도 이미 죽어 있다. 실행기를 거치면 실행기만 죽고 원격은 L7 이 끊을 때까지 돈다. 그 사이 `_execute` 가 출력 목록을 다시 떠(RL:623-636) 아직 쓰이는 파일을 출력으로 등록하고 sha256 을 적는다(RL:495). 행이 닫힌 뒤 같은 세션의 다음 job 이 같은 폴더에서 먼저 시작될 수도 있다 |

| K3 | P2 | RL:823-830(`stop_worker`, 827-828) | 설정이 있을 때만 같은 TERM 먼저 순서를 쓴다. 종료 때도 `_execute` 가 이어서 출력 목록을 뜨므로(RL:810-811 이 남은 job 을 기다린다) K2 와 같은 틈이 있다. lifespan 3.5초(`platform/backend/app/main.py:52-55`)와 uvicorn 5초(`platform/infra/apptainer/api.def:52-53`) 안에 들게 유예를 짧게(예 2초) 둔다 |

| K4 | P2 | RL:702-720(`reconcile_orphans`, UPDATE 711-717) | 설정이 있으면 먼저 `SELECT id … WHERE status='running' AND external_kind IS NULL` 로 id 를 읽는다. 각 id 로 `<실행기> --reap <id>` 를 부른다(시간 제한, 실패해도 진행). 그 다음 지금의 UPDATE 를 한다. API 가 갑자기 죽으면 원격은 L7 로 끝나지만, 새 API 가 행을 failed 로 닫고 같은 세션의 다음 job 을 먼저 띄울 수 있다. 지금 로컬도 같은 틈이 있다(바이너리가 새 세션이라 API 와 함께 죽지 않는다) |

| K5 | P3 | RL:168-174(자식 환경) | 설정이 있을 때만 자식 환경을 허용 목록으로 준다(L2 와 같은 목록). 실행기가 이미 거르므로 겹 방어다. 지금 자식은 API 환경 전체를 물려받는다 |

| K6 | P3 | RL:58-81(`_env_snapshot`) | `"launcher": settings.job_launcher or None` 을 더한다. `host.nodename`(RL:80)은 API 노드다. 실제 노드는 실행기가 `.job_<id>.node` 로 남긴다(L11) |

| K7 | P3 | SS:316-357 · 383-386(세션 삭제) | 취소 뒤 8초 기다리고 `rmtree(ignore_errors=True)` 한다. 원격 job 이 아직 끝나는 중이면 NFS 의 `.nfs*` 파일이 남을 수 있다. 지운 뒤 폴더가 남으면 로그 한 줄을 남기거나 한 번 더 지운다 |

---

## 3. 코드 수정 없이 쓰는 설정(prod 이전 — 지금처럼 동작하도록 유지해 달라)

10-23 에 아래가 코드 수정 없이 되는 것을 확인했다. 이 동작이 바뀌면 prod 가 깨지므로 바꿀 때는 알려 달라.

| 항목 | prod 에서 쓰는 방법 | 근거 |

|---|---|---|

| API 바인드 | `api.def` 의 기동 스크립트는 `--host 0.0.0.0` 이다. prod 는 그 스크립트 대신 같은 이미지로 `uvicorn app.main:app --host 127.0.0.1 --port <포트> --no-proxy-headers` 를 직접 띄운다 | `platform/infra/apptainer/api.def` |

| Postgres 바인드 | 기동 스크립트(`docker-entrypoint.sh postgres`)에 `-c listen_addresses=127.0.0.1 -c port=<포트>` 를 붙여 직접 띄운다 | `platform/infra/apptainer/postgres.def` |

| MCP 바인드 | `MCP_HOST` 기본 127.0.0.1 을 그대로 쓰고 `MCP_ALLOWED_HOSTS` 에 cae00 쪽 주소를 넣는다 | `platform/infra/scripts/start.sh:224` |

| 웹 접두 | `KOORM_PORTAL_BASE=/apps/kooremapper_prod/` 로 프런트엔드를 빌드한다. API 는 게이트웨이 머리글이 있으면 `index.portal.html` 을 준다 | `platform/infra/scripts/build-frontend.sh:10, 20-24`, `platform/backend/app/main.py:197-214`, `platform/frontend/src/shared/api/client.ts:14-17` |

| 저장 위치 | `KOORM_STORAGE_DIR`(job 분배 때 `/data3` 아래). 옛 행의 `stdout_path` 가 풀리도록 `platform/storage` 링크도 같은 곳을 가리키게 한다 | CFG:68, JR:228-231 |

| 동시 수 | `KOORM_WORKER_CONCURRENCY` 를 두 노드 슬롯 합으로 둔다. 세마포어(RL:724 · 767)와 세션당 하나(RL:138-149)는 그대로 쓴다 | CFG:77-78 |

| AIDH 게시 끔 | `KOORM_DATAHUB_URL=`(빈 값). 게시 요청이 400 「datahub_url 이 설정되지 않았습니다」 로 끝난다. 노드에서 AIDH 에 닿지 않기 때문이다 | `platform/backend/app/modules/reports/routes.py:782-783` |

| stcx 전각도 낙하 끔 | `KOORM_STCX_BACKEND_URL=`(빈 값, 기본값). 제출이 「반입 주소가 설정되지 않았다」 로 끝난다. cae00 에서도 아직 제출된 적이 없다(jobs 1행, external 0행) | `platform/backend/app/runner/stcx_client.py:731`, CFG:93 |

| ReportArchive | RA 가 가져가는(pull) 방식이라 앱 쪽에서 끌 것이 없다 | `platform/backend/app/modules/analysis/` |

| OpenMP 스레드 | 바이너리는 스레드 수를 정하지 않는다(`src/` 에 `omp_set_num_threads` 없음). 실행기가 슬롯마다 `OMP_NUM_THREADS` 를 준다 | L2 |

---

## 4. 바꾸지 않는 것

- DB 는 가동 노드 로컬에 둔다. 원격 노드에는 DB 연결이 가지 않는다.

- 앱은 노드를 모른다. 노드 이름 · 주소 · 슬롯 · 전송 방법은 앱 코드와 설정에 들어가지 않는다. 앱 설정은 실행기 명령 한 줄뿐이다.

- **설정이 비면 지금과 똑같다.** argv · 신호 순서 · 환경 · 출력 · 종료 처리가 모두 그대로다. 위 표의 "설정이 있을 때만" 은 이 때문이다. V1 이 이것을 시험으로 고정한다.

- 새 의존성은 없다(표준 라이브러리만). `api.def` 에 ssh 를 넣어 달라는 요청도 아니다.

- 클레임 · 세션당 하나 직렬화 · 동시 수 계산 · 취소 API 는 그대로다.

- job 의 하위 프로세스(gmsh)에는 접두를 붙이지 않는다. 바이너리와 같은 원격 노드에서 돈다.

- API 프로세스 안에서 도는 일(업로드 검사 · 출력 검사 · 연결성 검사, SS:162-166, RL:495-496, SS:284-299)은 이번 요청 밖이다. 가동 노드에서 그대로 돈다.

---

## 5. 확인 방법

| # | 시험 | 기대 |

|---|---|---|

| V1 | 설정 비움(기본) | 기존 시험이 전부 그대로 통과한다. 단위 시험을 더한다: `_run_blocking` 이 `Popen([bin, *argv], …)` 를 `env=` 없이 부르고, 시간 초과에 SIGTERM 없이 바로 SIGKILL 을 보낸다 |

| V2 | `passthrough.sh` | 연산 꼴마다 하나 이상(위치 인자 · yaml · matdb · meshfix(gmsh))이 통과한다 |

| V3 | `childwrap.py` | `_live_progress` 진행률과 출력 등록이 V2 와 같다 |

| V4 | 취소(`childwrap.py`) | 실행기가 SIGTERM 을 받고 자식 그룹이 끝난다. 행은 canceled. 남은 프로세스 0. 5초 안 |

| V5 | 실행기 실패(exit 125 + `[launcher]` 줄) | 행 failed. `error_summary` 에 그 줄이 있다 |

| V6 | 실행기 강제 종료(SIGKILL) | 행이 failed 로 닫히고 다음 job 이 돈다. 신호 이름이 오류에 남는다(`exit -9`) |

| V7 | 시간 초과(설정 있음, 짧은 제한) | SIGTERM → 유예 → SIGKILL 순서다(K2). rc 124 와 `[timeout exceeded]` 는 그대로다. 출력 등록은 자식이 끝난 뒤에만 일어난다(등록 뒤에 바뀐 파일 0) |

| V8 | 실행기 job 이 도는 중 API 재기동 | `--reap <id>` 가 불린 뒤(시험 실행기가 파일에 적는다) 행이 failed("worker restarted…")로 닫힌다. 같은 세션의 다음 job 은 그 뒤에 시작된다(K4) |

| V9 | 동시 수 | `KOORM_WORKER_CONCURRENCY=8` 에서, 오래 자는 시험 실행기로 그 수까지 동시에 뜨고 넘지 않는다. 세션당 하나는 지킨다 |

| V10 | K5(넣은 경우) | 자식이 받은 환경에 `KOORM_` 로 시작하는 이름이 없다 |

---

## 6. 우리가(HWAXProd) 하는 것

| # | 할 일 | 내용 |

|---|---|---|

| H1 | 실행기 본체 | 표준 라이브러리 Python 한 파일이다. 앱 컨테이너 안에서 앱의 자식으로 뜬다(0장 '실행 경계'). 같은 노드의 호스트 쪽 도우미에 루프백으로 붙는다. 실행기 폴더를 앱 컨테이너에 바인드하고, 컨테이너를 별도 네트워크 이름공간 없이 띄운다(cae00 에서 지금 그렇다). 실행기는 컨테이너 안의 `/usr/local/bin/python3` 로 돈다 |

| H2 | 노드 선택 · 슬롯 | 노드별 슬롯과 CPU 몫, `OMP_NUM_THREADS` 를 정한다. 한 노드가 빠지면 남은 노드에 올린다. `KOORM_WORKER_CONCURRENCY` 를 슬롯 합에 맞춘다 |

| H3 | 같은 빌드 · 같은 경로 | 원격 도우미가 `apptainer exec` 로 같은 `api.sif` 와 같은 체크아웃 커밋을 같은 바인드(`/workspace` · 저장 루트)와 같은 cwd(세션 폴더)로 띄운다. argv 와 DB 에 남는 경로가 모두 컨테이너 안 경로이기 때문이다. 승격 관문에서 BUILD_INFO · sha256 을 비교한다 |

| H4 | 공유 루트 | `KOORM_STORAGE_DIR` 과 `platform/storage` 링크를 `/data3` 로 옮긴다 |

| H5 | NFS 측정 | `/data3` 마운트 옵션을 본다(지금 `soft` — job 파일을 두기 전에 `hard` 로 바꾼다). 가동 노드가 원격이 막 만든 파일을 바로 보는지 시험한다: 출력 판정(RL:586-591 · 623-627, 목록과 mtime 비교 — 새 파일과 덮어쓴 파일). 놓치면 마운트 옵션으로 먼저 푼다 |

| H6 | 원격 정리 | L6 · L7 · L10(신호 전달 · 임대 · `--reap`)을 만든다. 행과 원격 프로세스를 주기적으로 대조해 고아를 정리한다. 노드 사이는 용도 하나짜리 제한 ssh 키로 잇는다 |

| H7 | 도입 순서 | ① 설정을 비운 새 판 배포(V1) → ② 가동 노드 안에서 `passthrough` 로 며칠 → ③ 원격. 되돌림은 설정을 비우고 API 를 다시 띄우는 것이다 |

| H8 | 기록 | 실행기는 환경 값을 적지 않는다. job id · 노드 · 시작/끝 시각 · 종료 코드만 남긴다 |

---

## 열린 질문

1. **종료 코드 125.** 바이너리가 125 로 끝나는 경우가 없는지 확인해 달라. L5 가 실행기 실패에 125 를 쓴다.

2. **NFS 위 판정.** H5 에서 마운트 옵션으로 못 풀면 앱 쪽에서 판정 전에 무엇을 할지 정해야 한다(예 짧은 대기, 실행기가 남긴 출력 목록 읽기). 측정 뒤 다시 알린다.

3. **실제 노드 기록.** `env_snapshot.host.nodename` 을 실행기가 남긴 노드로 바꿔 적을지 정해 달라. K6 는 실행기 표시만 더하는 최소안이다.

---

담당: HWAX Portal 운영
