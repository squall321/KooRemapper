# cae00 요청 — 높음 전부(KR-01~05·09) + KR-17 (완료 보고 2026-10-27)

**요청** cae00 운영 요청서(사용자 10-27). 범위 결정 — 높음 전부 + KR-09 + KR-17(읽기 열기). 계획 `docs/01-plan/features/hwax-request-1027.*`.
근거는 저쪽 장부를 그대로 믿지 않고 **현재 코드에서 짚었다**.

## 고친 것
| # | 무엇 | 커밋 | 검증 |
|---|---|---|---|
| KR-03 | prestress 주응력 퇴행 고유값 버그 — `else` 한 실근 가지 제거(변형률 매개화) | `b8eb309` | C++ 단위 5항·145/0 · prestress probe ALL PASS · compat 바이너리에서도 |
| KR-01 | 과제코드 매칭 — key=과제명, 과제코드는 properties.task_code. resolve·후보·검색·matched_by | `ca47363` | DB·ASGI 시험 |
| KR-02 | '/' 든 key — `tasks/{task_key:path}` + MCP quote | `ca47363` | ASGI 200(404 아님) |
| KR-17 | sync 읽기 개방 — GET /ontology/sync 를 로그인 사용자에게(쓰기·수신은 admin) | `ca47363` | 비관리자 200 |
| KR-04 | 감시가 배포 표지 보면 건너뜀 | `c2a124b`·`f1ab307` | supervisor 시험(pid 포털 꼴·실제 flock) |
| KR-05 | 크론 세션 버스 자동 채움 | `c2a124b` | _common 시험 |
| KR-09 | crontab -l 실패 안전 | `c2a124b` | install 시험 |

## KR-03 — "진단을 뒤집지 말라"
요청서 짐작(acos 범위)도, 소스의 '부호 고침'(`22c7f9e`·10-01, 배포본 `44f16c9`·10-17 에 **이미 있음**)도 원인이 아니었다.
진짜는 퇴행 고유값(겹침)+미세 전단에서 판별식이 미세 양수로 떠 `else` 한 실근 가지로 빠져 세 주응력을 같게 만든 것(min=max).
재현으로 가리고 변형률 매개화(한 실근 가지 없음)로 고쳤다. 기존 probe 회귀는 전단 0 깨끗한 케이스만 봐서 배포본에서 초록이었다(빈틈 — C++ 단위로 메움).

## KR-04 — 피어(kooremapper-fd)가 잡은 두 버그
첫 구현(`c2a124b`)에 두 결함이 있었고 다른 세션이 코드·실측으로 잡아 `f1ab307` 로 고쳤다.
① 포털 pid 파일은 `"pid epoch deploy-all"`(deploy-all-from-drive.sh:476) 꼴인데 `tr -dc '0-9'` 가 pid·epoch 를 한 숫자로 붙여 늘 실패 → `read` 로 첫 칸만.
② `flock -n` 엿보기가 잠금을 쥐어 때마침 뜨는 update-all 을 오작동(exit 3)시킬 수 있음 → `/proc/locks` 로 inode FLOCK 유무만(안 잡음).
포털 짝 HP-01 은 HWAXPortal main `35c5dde` 에 이미 있어, 표지는 **다음 deploy-all 부터 실제로 뜬다** — 그래서 ① 수정이 바로 필요했다.

## 검증 · 배포
- 백엔드 전체 **662 통과** · C++ 단위 **145/0** · 스크립트/ASGI 시험 · prestress probe ALL PASS.
- compat 빌드(GLIBC_2.35, taskset 가드) → `platform/backend/bin` 갱신 → dev API/MCP 재기동(잡 0) → 스모크 **기본 80도구 · allops 62/62**.
- 커밋 전부 origin/main.

## 남은 것 — prod(사용자 타이밍)
- 코드(KR-01·02·04·05·09·17) — origin/main. prod 는 update-all 이 가져간다.
- KR-03 바이너리 — **Drive 게시 완료**(dist-20261027-220420Z). cli.sif 도 새 바이너리로 다시 구워 올렸다(배치/HPC·REMAP 체인까지 KR-03). api.sif(numpy — 레시피)·나머지 SIF 도 같은 세트로 올라갔다. prod 반영은 `dist-from-drive.sh`(ops/update-all).

## 배포 완료(10-27)
dev 전부 라이브 · Drive 게시(dist-20261027-220420Z)까지. prod 는 ops 가 dist-from-drive + update-all 로 가져간다(노드·타이밍은 사용자/ops).


## 확장 — 남은 요청 항목도 끝냄(사용자 「다 끝내야지」, 10-27)
높음 뒤 **할 수 있는 것 전부**를 이어서 고쳤다(커밋 e2075f4·0012f97·80312af·e533be8·54304cd).

| # | 무엇 | 비고 |
|---|---|---|
| KR-06 | 받을 타입 선택(KOORM_SP_CORE_TYPES, 기본 셋) · 미공개는 거절 말고 건너뜀(skipped) | 전제 뒤집힌 시험 둘 갱신 |
| KR-07 | 모르는 과제 vs 개정 없음 — task_found·unknown_task(단, 개정 있으면 '아는' 과제) | |
| KR-08 | find_reports 빈 봉투 {items,total,reason} (MCP) | 0자 출력 → 사유 있는 빈 결과 |
| KR-13 | 부분 수신은 409 아니라 성공 상태 + per-type | |
| KR-14 | sp_core trust_env=False(토큰 프록시 우회) | |
| KR-15 | plm_sync 머리말·.env.example(SP_CORE, /core 금지) | |
| KR-16 | list_tasks 앞부분·낱말경계 순위 · project 거르개 · matched_by | |
| KR-18 | /auth/sso/verify(204/401/404) · X-Heax-Client 에 gateway | |
| KR-12 | 계획서 표를 실측으로(문서) — 대체 필드·plm_test_site 취급은 **허브 확인 뒤 결정(미결)** | 짐작으로 코드에 안 박음 |

백엔드 **670 통과** · dev 재기동 · 기본 스모크 80도구. 코드는 origin/main(update-all). **바이너리 안 바뀜 → 이 묶음은 Drive 불필요.**

## 아직 못 하는 것(이유)
- **KR-10 · KR-19(stcx)** — stcx 첫 실제 제출의 `job_status` 응답 원문이 있어야 종료 판정을 고정한다(KR-10). 나머지 옵션·결과 회수(KR-19)는 다음 판 + 저쪽 대기. 우리 첫 제출이 먼저다.
- **KR-20(질문)** — CSV 주응력을 쓴 기존 결과 재실행 여부. **권장**: von Mises·성분은 두 판 다 맞았으니, **주응력(min/maxPrincipalStress)을 소비한** 결과 중 퇴행 고유값 요소가 있던 것만 다시 돌리면 된다(prestress 재실행은 싸다). 다만 어디까지 재실행할지는 사용자/요청자 결정.
- **KR-21(질문)** — stcx 잡 소유자(제출자 기록 vs stcx 인증). 저쪽(stcx)과 합의할 일 — 우리 코드 몫 아님.
- **KR-22(질문)** — NFS 출력 누락 대비. 측정 뒤 결정(저쪽). 앱 쪽 선택지: 짧은 재시도 · 실행기가 남긴 출력 목록 읽기 — 측정 결과 보고 정한다.

## 범위 밖
KR-06~08·10·12~16·18·19 · stcx 전부(첫 제출·저쪽 대기) · 6절 저쪽 몫. KR-11 은 불변 조건으로 지켰다.
