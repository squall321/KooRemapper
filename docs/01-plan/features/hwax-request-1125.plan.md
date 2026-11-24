# 포털 요청 1125 — KooRemapper 몫 (2026-11-25)

체크리스트 `hwax-request-1125.checklist.md` · 맥락 `hwax-request-1125.context-notes.md`. 보낸 쪽 hwaxportal-71 — 운영 박스(cae00)가 11-24 에
모은 요청의 1-11 절(여섯) · 1-12 절 HP-71. 원문은 포털 리포에 있다(여기에 옮기지 않는다).

## 0. 조건
- 5차 동결 — 커밋은 가지 · 로컬까지. push · Drive 는 동결 해제 알림 뒤(hwaxportal-71 이 전한다).
- dev 에서 포털 deploy-all 을 돌리지 않는다 — 함수만 떼어 시험한다.
- 적힌 자리는 지금 HEAD(main `7606736` + 가지 `corelink-int`)에서 다시 대 봤다 — 모두 그대로였다(맥락 1절).

## 1. 차례
| 차례 | ID | 할 것 | 결정 |
|---|---|---|---|
| 1 | R-04 | SIF · BUILD_INFO 설치를 같은 디렉터리 임시 파일 + 이름 바꾸기로(포털 `11874eb9` 꼴) · stop 뒤 인스턴스가 정말 사라질 때까지 기다리고 상한을 넘으면 rc≠0 | 범위(요청 둘 · 같은 뿌리 일곱) — 사용자 |
| 2 | HP-71 | `platform/.env.example` 코어 주소를 포털 경로 꼴로 · `/core` 경고 그대로 · NO_PROXY 자리표시(루프백까지) | 없음 |
| 3 | R-09 | 판 입력칸 「과제코드」 문구 · 등록 레시피 내보내기 자리 | 둘 다 사용자 |
| 4 | ST-25-KR | StepForge 가 확정한 maps_to 블록을 통째로 · `EXTERNAL_TYPES` 에 cad_part · 시험 두 자리 | StepForge ST-25 와 같은 판 |
| 5 | KR-12 | `EXTERNAL_TYPES` 의 plm_test_site · 개정 종류 괄호는 칸이 있을 때만 | DP-13(Datahub 플랫폼) 답 뒤 |
| 6 | KR-10 · KR-19 | 종료 판정을 실제 원문대로 · 옵션 · 결과 회수 | 운영 노드 첫 실제 제출 · `last_raw` 뒤 |

## 2. R-04 설계
- 설치 — `_install_if_changed` 가 내용이 다를 때 대상 옆 임시 파일(`.이름.XXXXXX`)에 `cp -p` 하고 `mv -fT` 로 바꾼다. 도는 인스턴스는 옛 inode
  를 쥔 채 돌고 다음 기동이 새 파일을 연다. 대상이 심링크면 가리키는 파일을 바꾸고(링크를 파일로 만들지 않는다), 쓸 수 없는 대상은 종전처럼 rc 2
  · 옛 파일 그대로 · 임시 파일을 남기지 않는다. mtime 은 원본 그대로(포털 재기동 판정 지문).
- 바이너리 · 화면 묶음은 `tar -x` 다 — GNU tar 1.34 는 먼저 지우고 새로 만든다(새 inode · 열린 서술자는 옛 내용, 실측). 바꾸지 않는다.
- 기다리기 — `_common.sh` 에 `wait_instance_gone 이름` — `instance_absent_for_sure` 가 참이 될 때까지 1초마다 본다. 상한
  `KOORM_STOP_WAIT_S`(기본 60초)를 넘으면 ✗ 를 찍고 1. 목록을 못 읽는 「모름」 도 사라졌다고 보지 않는다(기존 규율).
- 요청한 두 자리 — `stop.sh` 는 인스턴스마다 stop 뒤 기다리고(nginx → mcp → api → postgres 차례 그대로 — api 가 사라진 뒤 postgres) 하나라도
  상한을 넘으면 끝까지 시도한 뒤 rc 1. `restart-api-only.sh` 는 `sleep 1` 대신 기다리고 넘으면 rc 1(새 인스턴스를 띄우지 않는다 — 감독자는 실패
  rc 를 이미 로그에 남긴다).
- 같은 뿌리(stop 바로 뒤 start · 지우기) 다섯 — `restart.sh:10` · `start.sh:94` · `start.sh:157` · `reset-db.sh:15` · `supervisor.sh:201`.
  넣을지는 사용자 결정(맥락 2절).

## 3. 시험
- 설치 — 열린 서술자가 옛 내용을 읽는다 · 새 inode · mtime 그대로 · 임시 파일 없음 · 심링크 · 쓸 수 없는 디렉터리(포털 시험과 같은 넷) · 같은
  내용이면 손대지 않음.
- 기다리기 — 몇 번 뒤 사라지는 가짜 apptainer · 끝내 안 사라짐(상한 넘음 → rc 1 · 새 기동 없음) · 모름(목록 실패)도 상한 넘음.
- 기존 배포 시험(`test_deploy_defects_20260919.py`)은 상한을 짧게 줘 그대로 통과.
