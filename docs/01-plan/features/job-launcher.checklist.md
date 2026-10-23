# 체크리스트 — 실행기(launcher) 설정 (10-23)

## 사실 대조
- [x] 요청서의 `파일:줄` 전부 대조(±1줄) · getenv 넷 · `omp_set_num_threads` 없음 · `ldd`(libpq·sqlite 없음) · Job 에 pid 칸 없음
- [x] `argv[0]` = 연산 이름(core argbuild positional 235 · yaml 260)
- [x] 종료 코드 감사 — 125 가 나오는 길이 있나
- [x] 기준선 backend pytest 578 통과

## 코드
- [x] K1 설정 + 접두(`_run_blocking`)
- [x] K2 시간 초과 TERM → 유예 → KILL(실행기 있을 때만)
- [x] K3 `stop_worker` TERM 먼저(유예 2초)
- [x] K4 `reconcile_orphans` 앞에 `--reap`
- [x] K5 자식 환경 허용 목록
- [x] K6 `_env_snapshot.launcher`
- [x] K7 세션 삭제 뒤 남은 폴더

## 시험
- [x] V1 설정 비움 — Popen 인자 · env= 없음 · 시간 초과 바로 KILL · 기존 시험 전부(578 → 599, 새 21)
- [x] V2 passthrough — 위치 인자 · yaml · matdb · meshfix(gmsh)
- [x] V3 childwrap — 진행률 · 출력 등록이 V2 와 같다
- [x] V4 취소(childwrap) — canceled · 남은 프로세스 0 · 5초 안
- [x] V5 실행기 실패 125 + `[launcher]` 줄
- [x] V6 실행기 SIGKILL — failed · `exit -9` · 다음 job
- [x] V7 시간 초과 — TERM → 유예 → KILL · rc 124 · 등록 뒤 바뀐 파일 0
- [x] V8 재기동 — `--reap` 뒤 failed · 다음 job 은 그 뒤
- [x] V9 동시 수 8
- [x] V10 K5 — 자식 환경에 `KOORM_` 없음
- [x] 컨테이너 안(api.sif)에서 K5 환경으로 실제 op 이 도나 — 다섯 모두 rc 0 · 자식 환경 `HOME LANG LC_* PATH PWD`

## 문서 · 배포
- [x] 설정 문서(`.env.example` 등)에 새 설정 둘
- [x] 답신 `docs/requests/hwax-job-launcher-reply-2026-10-23.md`
- [x] 커밋 · 푸시 · API 재기동 · 헬스 · 스모크 — `a3e9636` · 재기동 전 queued/running 0 · MCP 경유 database · meshfix succeeded · `env_snapshot.launcher` null

## 남은 것(사용자 결정)
- [ ] Q3 실제 노드 기록 — 권장 A(`host.job_node` ← `.job_<id>.node`) 확정 뒤 넣는다
- [ ] `.nfs*` 를 출력 등록에서 뺄지(한 줄) — 요청 밖 · 제안만 했다
- [ ] Q2 NFS 판정 — HWAXProd 측정(H5) 대기
