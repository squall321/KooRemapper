# 낙하 파이프라인 DynaForge 몫 — 결정 노트 (2026-11-12)

### 왜 별도 가지인가

kooremapper-4a 가 `corelink-src08-11` 를 하는 중이고, 포털 11-11 요청 뒤 main 은 cae00 결과 보고까지 **판 고정**이다
(HWAXPortal `docs/request-1111/checklist.md` 22행). 그래서 가지 `dropline-1112` 를 작업 트리로 따로 두고 그 가지만
origin 에 올린다. 본 트리(main)는 건드리지 않는다.

### (a) 요약은 원본을 숨기고 계산해 낸다

`JobRead` 는 `from_attributes` 라 ORM 칸 이름을 따라간다. `external_kind` · `external_ref` 를 `exclude=True` 로 받아 두고
`computed_field` 로 요약만 낸다 — 원본(경로 · 레지스트리 id · 업로드 id 등)이 응답에 새지 않는다.
문자열은 진단 번들의 `redact` 를 그대로 쓴다(규칙이 두 벌이 되지 않게).

### 포털 답(11-12) — 잡 키 꼴 · 화면 · 값 묻기

- (b) 저장 꼴 `stcx:<Slurm 잡 id>` 가 맞다(가이드 §4 의 '잡 id' 도 stcx 드라이버의 Slurm 잡 id). DynaForge 잡 id 로 찾는 길은 두지 않는다.
- (a) 화면 표시는 범위 밖. MCP get_job 에서 보이면 포털 절차 R2c 가 쓴다.
- dev 값 셋은 포털이 사용자에게 한 번에 묻는다 — 같은 물음이 두 번 가지 않게 이쪽은 묻지 않는다.

### 해석기 없는 E2E 에 드는 칸은 둘이다

요청서는 셋(URL · SSO 비밀 · 게이트웨이 PAT)을 들었지만, 후처리 예약 · 반입 길(`postprocess_return.py`)이 보는 것은
`stcx_backend_url` · `kooslurm_sso_secret` 둘이다. `gateway_pat` 은 stcx **제출**(fullangle 도구를 게이트웨이로 부르기)에 쓴다.
절차 문서 0절에 갈라 적었다.

### 점검 스크립트는 토큰을 받지 않는 것이 기본이다

위임 창구는 비밀 없이 한 번 두드려 거절(401/403/400)이면 「있다」 로 본다 — 토큰이 발급되지 않는다. 실제 명의 확인(`--email`)은
그 사람 명의로 토큰이 **발급되는** 일이라 명시할 때만 한다. 표준 라이브러리만 써서 가상환경 없이 dev · cae00 어디서든 돈다.

### 작업 트리에서만 나는 실패 다섯 (이 변경과 무관)

`test_supervisor_log.py` 넷 — 작업 트리에 `platform/.env` 가 없다(git 밖). `test_gmsh_probe.py` 하나 — 심볼릭 링크로 이은
`platform/backend/bin` 의 gmsh 경로를 탐지기와 바이너리가 다르게 푼다. 본 트리(main)에서는 둘 다 통과(13/13).
