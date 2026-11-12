# 스마트트윈 낙하 파이프라인 — DynaForge 몫 (2026-11-12)

**요청**: 포털(hwaxportal-a5), 사용자 지시 11-12. kooremapper-4a 가 `corelink-src08-11` 가지를 하는 중이라
이쪽은 가지 `dropline-1112`(작업 트리 `.claude/worktrees/dropline-1112`)에서 한다. **main 합치기는 판 고정 해제
알림 뒤**(HWAXPortal `docs/request-1111/checklist.md` — cae00 결과 보고 뒤 세션들에 알린다).

## 1. API 셋 — 덧붙이기만

| | 무엇 | 왜 |
|---|---|---|
| (a) | REST `/jobs/{id}`(→ MCP `get_job`)에 `external` 요약 — `{kind, cluster_state, ontology: {state, why?}}` | 가이드 §4·§5-1 이 보라는 칸인데 지금은 `/jobs/{id}/diagnostics` 에만 있다 |
| (b) | REST `/reports`·MCP `find_reports` 에 `external_job_key` 정확히 같음 거르기 | 후처리 예약이 반입한 리포트를 잡 키로 찾는다 |
| (c) | `/system/status` 에 `postprocess_versions` — 최근 리포트의 `ontology.producer` 서로 다른 판 · 수 · 마지막 시각 | stcx 접속 없이 운영에서 실제로 어느 후처리 판이 도는지 본다 |

- (a) 원본 `external_ref` 는 내보내지 않는다. 문자열은 진단 번들과 **같은** `redact`(경로 접기 · 이메일 · 토큰).
- (b) 저장 꼴은 `stcx:<slurm job id>`(`postprocess_return.py`). 요청서의 "stcx:<잡 id>" 뜻은 포털에 물었다.
- (c) 기간 90일 · 판 최대 10개. 리포트에 `ontology` 가 없으면 세지 않는다.

## 2. dev E2E 반입 쪽 — 설정 · 확인 차례

dev `platform/.env` 에 `KOORM_STCX_BACKEND_URL` · `KOORM_KOOSLURM_SSO_SECRET` · `KOORM_GATEWAY_PAT` 가 비어 있어
후처리 예약이 「설정 안 됨」 이다(11-12 확인 — 값은 보지 않았다). 준비하는 것 —
- 절차 문서: 어느 칸을 어디(dev 박스 파일)에 두나 · 확인 차례 `get_job` → `report_summary` → `report_cae`.
- 점검 스크립트: 값을 출력하지 않고 「어느 칸이 비었나 · 백엔드에 닿나」 만 본다.
- **값은 정하지도 다른 데서 옮기지도 않는다** — 누가 어디서 주나는 사용자 · 포털 결정.

## 받아들이는 기준

- (a)(b)(c) 시험 · backend 전체 녹색 · MCP 계약 시험(인자 고정본 갱신) 녹색.
- 기존 응답 칸은 그대로(덧붙이기만).
