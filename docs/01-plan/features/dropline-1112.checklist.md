# 낙하 파이프라인 DynaForge 몫 — 체크리스트 (2026-11-12)

계획: `dropline-1112.plan.md` · 결정: `dropline-1112.context-notes.md` · 가지 `dropline-1112`

## 조사 (끝)
- [x] get_job 은 REST `/jobs/{id}` 를 그대로 넘긴다 · `JobRead` 에 external_ref 가 없다
- [x] 진단 번들이 `external_ref` 전체를 `_redact_deep` 로 가린다 — 같은 규칙을 쓴다
- [x] `external_ref.ontology.state` ∈ loaded · absent · no_field · failed(+why) · `cluster_state` 는 KooSlurm `/info` 의 state
- [x] `ImpactReport.external_job_key` = `stcx:<slurm id>` · `ImpactReport.ontology.producer`
- [x] dev `.env` 의 stcx 세 칸 비어 있음(값은 안 봄)

## (a) get_job 요약
- [x] `JobRead.external` — 원본 숨김(`exclude`) + redact 한 요약 · MCP get_job 설명
- [x] 시험 3

## (b) find_reports 거르기
- [x] REST `/reports?external_job_key=` · MCP 인자 · 계약 고정본(인자 36→37) · TOOLS.md
- [x] 시험 1(정확히 같음 · 앞부분만 같으면 안 걸림 · 안 주면 예전과 같음)

## (c) 시스템 상태
- [x] `/system/status.postprocess_versions`(90일 · 10판 · 못 세면 None) · MCP system_status 설명
- [x] 시험 1(판 없는 꾸러미 · 꾸러미 없는 리포트는 안 센다)

## 2. dev E2E
- [x] 절차 문서 `dropline-1112.dev-e2e.md`(값 없이) · 점검 스크립트 `platform/infra/scripts/check-postprocess.py` · 시험 3(값이 출력에 안 나온다)
- [x] 값 공급 — 사용자 결정(11-12): dev 전용으로 세션들이 맞춘다 · dev `.env` 두 칸 · e2etest 사용자 · 세션 · 점검 rc 0(e2etest 명의 토큰 받음)
- [ ] ④ 예약 · ⑤ 반입 확인 — **보류(11-12)**: ① 노드 이미지 배포 뒤 호스트 여유 메모리가 켜기 조건(30 GB) 아래라 사용자 결정으로 멈춤 ·
      node001 끔 · dev 설정 · e2etest 는 그대로 둔다 · 다시 돌릴 때 포털이 사용자에게 묻고 알린다(실행 스크립트는 스크래치 `e2e_reserve.py`)

## 마무리
- [x] backend 전체 829 녹색(작업 트리 환경 탓 5 — 결정 노트) · MCP 계약 9/9 · 가지 커밋 · 가지 푸시
- [x] 판 고정 해제(포털 11-14 — cae00 이 11-14 update-all 로 받음) 뒤 main 에 빨리 감기 `bc022d9..0d7ce64`(6 커밋)
- [ ] dist · API 재기동 · 스모크 · 포털 끝 알림 — **kooremapper-4a 가 corelink-int 를 합친 뒤 한 번에**(합의 11-14)
