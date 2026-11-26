# cae00 · icn401 · stcx 점검 — 2026-10-30 · 10-31 반영분(DynaForge 후처리 반입 · 낙하 트윈 P1 · P2 · P3 받는 쪽 · SP 받는 쪽 전부 · MCP 인자 설명 · 시간 한도 · 해석 온톨로지)

**누가 · 어디서** 사람이 cae00(실사용 서버)·icn401(KooSlurm 운영)·stcx 에서 돌리는 확인이다. 포털 `docs/cae00-deploy-guide.md` 의 「2026-10-30 반영분」 절로 옮긴다(포털 세션).
**정본** DynaForge 쪽 결정 · 계약은 KooRemapper `platform/docs/REQUEST-postprocess-operation.md` §10, `docs/01-plan/features/{postprocess-reservation-1028,sphere-risk-map-1029}.plan.md`, 총괄 `drop-twin-1028.checklist.md`. KooSlurm 쪽은 KooSlurm `docs/sso_enable_20261029/{icn401_apply_check,sso_enable_procedure}.md`(origin `46c647e4`).

## 0. 순서 — 한 줄씩
1. **cae00** — `git pull && update-all`(kooremapper 가 Drive 판 `dist-20261125-161932Z` 를 받는다) →
   §1 · §1-1 · §1-2 · §1-3 · §1-4 · §1-5 · §1-6 · §1-7 · §1-8 · §1-9 · §1-10 · §1-11 · §1-12 · §1-13 · §1-14 · §1-15 · §1-16 · §1-17 확인.
2. **icn401** — `git pull && sudo ./dashboard/start_production.sh` → §3 확인(KooSlurm 문서 §2).
3. **비밀 하나를 두 곳에** — icn401 `HEAX_GATEWAY_SECRET`(backend_5010/.env) = cae00 `KOORM_KOOSLURM_SSO_SECRET`(KooRemapper platform/.env) → §2 · §3-3.
4. **cae00** — `KOORM_STCX_BACKEND_URL` 확인 → DynaForge 재기동 → §2 확인.
5. 운영의 **첫 실제 전각도 잡** 뒤 → §4.
6. (사람 · 읽기만) stcx viz 노드 · 게이트웨이 감사 → §5 · §6.
7. (운영 측) stcx 후처리 이미지 **Post v51**(`226eca7`) 설치 — 단면 영상 응력 0 프레임 고침(v42 와 같음) · S1 추출 · 해석 온톨로지 꾸러미(어휘 0.5) ·
   셸 파트 응력 → §5-1. 꾸러미가 어휘 0.5 라 cae00 의 1번(update-all)을 먼저 하거나 같은 때에 한다.
SSO 켜기는 **이번에 하지 않는다**(§7 — 조건이 안 섰다).

## 1. cae00 — DynaForge 받기(update-all 뒤)
10-30 판에 든 것 — 반입 속도(raw_decode `288afb7` · sphere 블록 분리 `c7970dc`) · 후처리 예약 `postprocess`(`4ff9a79` → 위임 창구 `e62f601` · rc 3 경고) · 구면 위험도 맵(3D · 허용비 · 상위 N, `f366816`) · 렌더 결과 반입 C-11(`85ba2f0`) · postprocess 의 비운 선택 칸 null 을 없는 칸으로(`07679d7`) · `dev_rev` 를 예약 때 반입 규칙으로(`3574342`) · **변형 뷰어 1단계** — 리포트에 StepForge fe_cad 묶음 붙이기(REST `POST /reports/{id}/cad` · MCP `attach_cad`, `aa63e2a`) · 맵에서 각도를 고르면 「형상 보기」(`d37fcbb`). 그 판의 **마이그레이션 셋**(0015 · 0016 · 0017 — 모두 null 허용 칸 · 유일 제약, 옛 코드에 영향 없음) — 그 뒤 0018 · 0019 · 0020 · 0021 이 더해져
지금은 0015 ~ 0026 열둘이다(아래 표 · §8). 바이너리는 그 판까지 그대로(`8c7c4f87`)였고 **11-07 판에서 바뀌었고**(`15d013ec` — §1-3) **11-08 판에서 또 바뀌었다**(`c5f74c18` — §1-4). 11-15 판에서는 그대로였고(§1-5) **11-17 판에서 다시 바뀌었다**(`248ec9bc` — §1-6). **11-21 판에서 또 바뀌었다**(`f20d5d5b` — §1-7). **11-21 밤 판에서 다시 바뀌었다**(`d1e2ce96` — §1-8). **11-22 판에서 또 바뀌었다**(`1106bef1` — §1-9). **11-22 낮 판에서 다시 바뀌었다**(`4b8fe975` — §1-10). **11-22 오후 판에서 또 바뀌었다**(`066e21a3` — §1-11).

**어디서 재나(11-24 바로잡음 — cae00 넘김)** — cae00 은 DynaForge 를 운영 노드로 넘겨 띄운다. 이 문서 표들의 `curl -s
http://127.0.0.1:8700/api/health` 는 **DynaForge API 가 도는 자리**의 health 다 — cae00 에서는 운영 노드의 것을 보고, cae00 박스의 8700 은
update-all §1b 사전 백업의 되돌림 사본(일부러 멈춰 둔다)이라 그 자리가 아니다(그 사본으로는 늘 「못 봄」 이 된다).
`platform/mcp_server/smoke.py` 는 세션을 만들고 지우는 쓰기 시험이라 운영에서는 돌리지 않는다 — 대신 읽기 전용으로 둘을 본다. (1) health 본문의
`revision` · `revision_matches_binary` · `binary_sha256` · `database.ok`(로그인 없이 읽힌다) (2) 게이트웨이 `curl -s --noproxy '*'
localhost:9110/tools-map` 의 `apps` 가운데 `heax-kooremapper_mcp` 의 `tool_count` · `reachable`(그 줄의 description 은 허브 매니페스트 글이라 op
수가 옛 값일 수 있다 — 허브에 고쳐 달라고 청했다). 옛 절(§1-1 ~ §1-12)의 표도 같은 뜻으로 읽는다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | 운영 노드의 DynaForge `/api/health`(위 「어디서 재나」) | `"status":"ok"` · `revision` 이 이번 게시 BUILD_INFO 의 커밋(`6a90a41`) · `revision_matches_binary` true · `binary_sha256` `139036f2…` |
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `4f8f73e` 이거나 그 뒤 — 위 `revision` 은 Drive 판의 커밋이라 그 뒤에 파이썬만 바뀐 커밋은 여기서만 보인다. `4f8f73e` 보다 앞이면 §1-17 의 것(maps_to 공통 블록 새 판)이 없고, `664a2f2` 보다 앞이면 §1-16 의 것(진행 중 올리기를 기다리는 재기동 · 레시피 마지막 자리)이 없고, `6a90a41` 보다 앞이면 §1-15 의 것(낙하 ⑥ 이미지 출처 · 배포 기다리기 · 판 확정 풀기 · 레시피 자리)이 없고, `6ac0f7e` 보다 앞이면 §1-14 의 바이너리(권취 강체 방향 · battery 카드 꼴 · ale EOS 제목 · 들여 쓴 `*` 줄 나머지)가 옛 판이고, `f0cc07d` 보다 앞이면 §1-13 의 바이너리(battery phase_modes · contact.depth · 나선 판 · 들여 쓴 `*` 줄)가 옛 판이고, `4cca82a` 보다 앞이면 §1-12 의 캠페인 분석 · 핫스팟 자리 · 세션 판(REST 열여덟 · MCP 열일곱)이 없고(Drive 판은 §1-11 그대로다), `87632b1` 보다도 앞이면 §1-11 의 보고서용 묶음(REST 넷 · MCP 셋)이 없고(`2cbdc84` 판은 파이썬이 `9614bb8` 과 같다 — §1-10 은 판 · 바이너리 줄로 본다), `9614bb8` 보다도 앞이면 §1-10 의 추출 완전성 · 삭제 허가(REST 셋 · MCP 셋 · 피크 표지)가 없고(`a50bcc3` 판은 파이썬이 `53028a2` 과 같다 — §1-9 는 판 · 바이너리 줄로 본다), `53028a2` 보다도 앞이면 §1-9 의 캠페인 출처 · 건강 판정(REST 넷 · MCP 넷)과 받기 줄의 연결 놓기가 없고(`98f5ec6` 판은 파이썬 · 콘솔이 `e7a6ef7` 과 같다 — §1-8 은 판 · 바이너리 줄로 본다), `e7a6ef7` 보다 앞이면 §1-7 의 것(캠페인 묶음 적재 · 리포트 받기 한 줄)이 없고, `c37bd03` 보다도 앞이면 §1-6 의 것(적재 공식 답 `intake` · `environment` · inspect `sha256`)이 없고, `8b49d2a` 보다도 앞이면 §1-5 의 것(MCP 도구 90 · 낙하 파이프라인 API 셋 · 핵심 잇기)이 없다. `3574342` 보다도 앞이면 null 을 보내는 손님(MCP 직접 호출 — Claude 등)이 비운 선택 칸에서 422 를 받고(포털 R2a 는 칸째 빼고 보내 영향 없음), 틀린 `dev_rev` 가 예약은 되고 잡이 끝난 뒤 반입에서야 실패한다 |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 「Running upgrade」 줄 없이 「✓ migrations applied」 = 이미 0026 까지 올라 있다(빠졌으면 이 명령이 그 자리에서 올린다 — 0015 · 0016 · 0017 · 0018 · 0019 · 0020 · 0021 · 0022 · 0023 · 0024 · 0025 · 0026). ★0019 는 **지운 리포트의 개정 선**을 한 번 지운다 — 개정 비교의 「리포트」 수가 지운 리포트만큼 줄 수 있다(정상, 사용자 결정 10-30) |
| MCP 도구 | 게이트웨이 `curl -s --noproxy '*' localhost:9110/tools-map` 의 `apps` 가운데 `heax-kooremapper_mcp`(읽기 전용 — 운영에서 smoke.py 는 돌리지 않는다) · 개발 박스에서는 `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | `tool_count` 120 · `reachable` true(smoke 는 120 · `MCP SMOKE: PASS` — 판마다 늘어난 도구 이름은 그 판의 §1-x 표) |
| 화면 | 세션 → 전각도 리포트 펼치기 → 「부품 위치·방향 시각화」 → 보기 「구(3D)」 | 3D 구가 뜬다(three.js 는 묶음 안에 있다 — 망 밖에 안 나간다) · 허용값을 넣으면 「초과 · 경고」 수가 보인다 |
| 형상 보기 | 같은 맵의 상위 표에서 각도 한 줄을 누른다 | 「고른 각도 …」 줄이 생긴다. CAD 묶음을 붙인 리포트면 「형상 보기」 로 glb 가 열리고 파트가 칠해진다(「속 보기」 로 속 파트). 안 붙였으면 붙이는 길(MCP `attach_cad` · REST)이 적힌다 — 운영에서 누가 붙일지는 §9 |

## 1-1. cae00 — SP 받는 쪽(이번 판에 더해진 것)
SP 키트 2026-10-21 판(규칙 16 · 시험장 8단계 자동 시험) 받기 · 잠금 · 실행 기록 · 주 1회 처음부터 · 식별자 바뀜 반영 · 합쳐진 과제 알림과 관리자 옮기기 ·
과제 검색(KR-01 다시 · KR-16 다시) · 받은 것 보기(화면 · API · MCP 셋) · 다시 확정하면 옛 리포트 선을 뗀다 · 지운 리포트의 개정 선은 DB 가 함께 지운다
(`f36270f` · `a3eff43` · `306346d` · `80a862a` · `24bca1c`). **실제 허브 주소 · `core:read` 토큰은 아직 없다** — 그래서 받기는 꺼진 채가 정상이다.

| 확인 | 어디서 | 기대값 |
|---|---|---|
| 과제·개정 스위치 | 시스템 상태 → 「과제·개정 (온톨로지)」 카드 | 켜짐/꺼짐과 **사유**. 꺼졌으면 왼쪽 메뉴에 「온톨로지」 가 **없는 것이 정상**이다(꺼지면 없어진다) |
| (켜진 박스만) 보기 | 왼쪽 메뉴 「온톨로지」 | 받은 타입 · 상태별 건수 · 객체(활성 · 그만 씀 · 사용 안 함 구별) — 아직 받은 적이 없으면 「받은 것이 없다」 |
| (켜진 박스 · 관리자만) 받기 카드 | 시스템 상태 → 「허브 받기 (관리자)」 | 주소 · 토큰이 없으면 「허브 주소 · 토큰이 없어 받기가 꺼져 있다」 · 단추가 잠긴다 — 정상. 토큰이 생기면 「지금 받기」 → 결과 「정상」 또는 「확인 필요」 + 사유 |
| 과제 검색 | MCP `list_tasks(q=…)` | 항목마다 `matched_by` · `match_kind`, 응답에 `truncated` · `total` (허브에서 받은 과제가 있을 때) |

⚠ 화면이 옛것이면 — dist 는 받았는데 API 가 옛 index 를 내는 것이다. `update-all` 이 재기동을 건너뛰었는지(§2 지문) 보고, 아니면 KooRemapper `platform/infra/scripts/restart-api-only.sh`(도는 잡 0 확인 뒤).

## 1-2. cae00 — 10-31 반영분(MCP 인자 설명 · 시간 한도 · 해석 온톨로지)
포털 10-31 요청 ①②(`3929a4e` — 도구 8 · 인자 36 에 설명, MCP → REST 시간 한도를 손잡이 하나와 호출별 기한으로) · 해석 어휘(`cae_*`)
채택 · 적재 · 질의(`0e9c9da` · `220df28` · `4ada7ba` · `57a41bf`, 사용자 결정 10-31 (가) — 후처리 꾸러미를 리포트에 캠페인 수준으로 싣는다).
**마이그레이션 0020**(행 · 선에 `report_id` FK, 리포트에 `ontology` 칸 — 모두 null 허용).

| 확인 | 어디서 | 기대값 |
|---|---|---|
| 인자 설명 | 게이트웨이 `/tools-map` 의 kooremapper `arg_scores` | 0 이 아니다(dev 10-31 — 0 → 36/248, cae 도구 넷 전) |
| 시간 한도 | `platform/.env` 의 `KOORM_MCP_API_TIMEOUT_S` | 비어 있으면 540초. 넣는다면 게이트웨이 600 **미만**(넘으면 게이트웨이가 먼저 끊어 손님이 까닭을 못 받는다) |
| 해석 온톨로지 — 없음 | 세션 → 리포트 펼치기 | 「원본 리포트 보기」 위에 「해석 온톨로지 없음 — …」 한 줄과 「꾸러미 붙이기」. 꾸러미를 안 붙인 리포트는 모두 이렇다(정상) |
| 해석 온톨로지 — 붙이기 | 후처리 산출 폴더의 `<리포트 이름>.ontology.json`(리포트 HTML 과 같은 줄기)을 「꾸러미 붙이기」 로 | 파트 판정(위험한 것부터) · 하중 경로(충격량 큰 것부터) 표. 남의 리포트 꾸러미면 「이 리포트의 꾸러미가 아니다」 로 거절되고 아무것도 안 바뀐다 |
| MCP | `report_cae(report_id)` · `find_cae_parts(min_severity="CRITICAL")` | 붙인 리포트면 `loaded: true` 와 파트 목록, 아니면 `loaded: false` 와 붙이는 길. 찾기는 읽을 수 있는 리포트(소유 · 같은 소속)의 것만 |

운영에서 꾸러미가 생기는 것은 꾸러미를 내는 후처리 이미지가 stcx 에 깔린 뒤다 — 그전에는 「없음」 이 정상이다. 후처리 예약(7-1) 반입은
귀환 매니페스트의 꾸러미(`reports[].ontology`)를 저절로 싣는다. 세 자리가 다 서야 실제로 실린다 — KooSlurm 작성기(`b6a3d75c`, icn401 반영 뒤
제출한 잡부터) · 리포트 도구가 `-o` HTML 곁에 꾸러미를 쓰는 후처리 이미지(KooD3plotReader (A) — **Post v43** `eccde7f` 부터, 지금 깔 판은 **v51** `226eca7`, §5-1) · 이 판의 DynaForge. 하나라도 없으면
리포트만 반입되고 잡 응답(`GET /jobs/{id}` · MCP `get_job`)의 `external.ontology.state` 가 `no_field`(옛 작성기) · `absent`(꾸러미 없음)다 —
둘 다 정상이고 경고가 아니다(원장 `external_ref` 는 응답에 나가지 않는다 — 11-12 판부터 그 요약 `external` 이 나간다).
이 싣기(`77c10a0`)와 어휘 0.4 판(0.3 꾸러미도 그대로 받는다)은 **파이썬 · 데이터만 바뀐 커밋**이라 Drive 판은 그대로다 —
`update-all` 의 git 갱신으로 들어간다(§1 「소스」 줄의 `git log -1` 로 본다).

## 1-3. cae00 — 11-07 반영분(StepForge 이월 적용 · 기존 결함 넷 · 어휘 0.5)
바이너리가 바뀐 판이다(`15d013ec` — GLIBC 2.35). 마이그레이션은 그대로(0020). MCP 도구 수도 그대로(89) — 새 연산은 `run_operation` 으로 부른다.
- **새 연산 `apply_carryover_plan`**(사용자 이름 확인 11-07) — StepForge 이월 계획(`plan.json` v1 + `field_<PID>.bin` + `fragment_<PID>.k`)을 그 덱에
  PID 마다 적용한다. 계약은 KooRemapper `docs/requests/stepforge-carryover-reply-2026-11-07.md`(§5 지었다). 덱 지문이 다르거나 사전 검사에 하나라도
  걸리면 덱을 쓰지 않고 보고 JSON 에 걸린 것을 모두 적는다.
- **기존 결함 넷**(모두 회귀 시험으로 잠갔다)
  - 절점을 옮기는 연산(`update` · `applyfold` · 평행이동)이 옮긴 절점 줄의 **TC · RC(구속) 칸을 지웠다** → 남긴다(`dcb6b74`).
  - 번호 바닥(`id_floor` · `cad_solid_merge_to_deck`)이 보 · 이산 · 질량 · 안전띠 · 플롯 요소와 리더가 안 읽는 솔리드 · 티쉘 변형의 EID 를 안 셌다 → 센다.
  - `*ELEMENT_MASS` 의 PID 를 질량 칸의 뒤 절반(25-32열)에서 읽었다 → 33-40열에서.
  - i10 덱에 조각을 넣으면(`cad_solid_merge_to_deck`) 쓰기 관문이 늘 멈췄다 → 덱 폭으로 대조.
- **해석 어휘 0.5**(`32cc364`, 파이썬 · 데이터) — 핫스팟 소성 기준 둘과 기준별 값 칸. 0.3 · 0.4 꾸러미도 그대로 받는다.

| 확인 | 어디서 | 기대값 |
|---|---|---|
| 새 연산 | 세션 → 연산 목록, 또는 `platform/backend/bin/KooRemapper apply_carryover_plan` | 목록에 있다 · 인자 없이 부르면 사용법이 나온다 |
| 연산 수 | 시스템 상태의 `operations` | 65(카탈로그 전부 · 외부 연산 둘 포함 — 이번에 하나 늘었다) |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `15d013ec…`(11-07 판 — 지금 판은 §1-4 의 `c5f74c18…`) |

클러스터 전처리 이미지(SmartTwinPreprocessor.sif)의 스테이징 사본도 `15d013ec` 로 바꿨다(`scripts/stage-to-appt313.sh`) — 구워야 클러스터의 `update` ·
`applyfold` 등이 TC · RC 를 지킨다. 굽기는 sudo 가 드는 사람 몫이다(`docs/infra/appt313-bake-hook.md`).

## 1-4. cae00 — 11-08 반영분(안전띠 칸 · 출력 관문 · 이월 판 2 받기 · 기존 결함 묶음)
바이너리가 바뀐 판이다(`c5f74c18` — GLIBC 2.35). 마이그레이션은 그대로(0020). MCP 도구 수(89) · 연산 수(65)도 그대로다. 백엔드는 러너가 `*.kr_tmp_*`
임시 파일을 잡 산출로 올리지 않게 된 것 하나다. SP 서브모듈은 `de5ecf5`(v0.4.76 — 키트 판 2026-11-03 그대로, coreapi diff 0).
- **이월 계획 판 2 받기** — StepForge 이월 계획 version 2(인클루드 닫힘 대조 · 줄마다 덱 자리 · 모프의 새 셸 섹션 · `refused_transform`)를 받는다. 판 1 도
  그대로 받는다. 인클루드가 있는 덱은 주 덱만 고치고, 고칠 자리가 인클루드에 있으면 목록과 함께 거절한다(사용자 결정).
- **안전띠 · 보 족 카드 칸** — `*ELEMENT_SEATBELT` 의 N3 · N4(57-72열)와 보 ELBOW 의 MN · WARPAGE 의 SN 을 모든 걷기가 읽는다(cleanup-nodes 가 쓰는 절점을
  rc 0 으로 지우던 것). 두 가지로 읽히는 줄은 절점을 다 남기고 번호 다시 매기기는 거절한다(사용자 결정).
- **출력이 입력을 덮지 않는다** — 덱 · 보고를 쓰는 연산 전부가 쓰기 전에 설정 · 모델 · 인클루드 · 다른 입력과 견주고 같으면 rc 1(입력은 그대로).
- **임시 파일 + 바꿔 넣기** — extract-parts · apply_carryover_plan 은 임시 파일에 쓰고 성공해야 바꿔 넣는다. 쓰기 오류(디스크 참 등)는 확정하지 않는다.
- **기존 결함 묶음** — 첫 `*END` 앞에만 카드 넣기 · 스칼라 절점 번호 · 재질 번호 셈(열 재질 · `*MAT_ADD_*` · 쌓인 카드) · 섹션 번호 셈(쌓인 카드) ·
  assemble battery 의 번호 겹침 · tetremesh · unfold 가 셸을 솔리드로 쓰던 것 · hfdamp 재질 읽기 · battery 접촉 카드 · map 이 첫 `*END` 뒤를 읽던 것.

알고 받을 동작 변화(사용자 결정)
1. boundary · rbe 는 `output` 이 필수다 — 비우면 rc 1(카탈로그가 「비우면 model」 이라 적던 것을 고쳤다).
2. assemble 밖의 연산은 `output` 이 model · 그 인클루드 · 설정 · 다른 입력과 같은 파일이면 rc 1(assemble 의 문서화된 제자리 쓰기는 그대로).
3. YAML op 여덟(foldsurface · refshell · stackwrap · linkage-fit · applyfold · section · surfview · stackdiagram)과 battery output · warpage `debug_prefix` 는
   경로를 YAML 폴더 기준으로 푼다(플랫폼은 YAML 이 세션 폴더라 그대로).
4. extract-parts · apply_carryover_plan 은 실패 · 거절해도 앞 실행의 출력을 지우지 않는다 — 보고에 `ok` · `output_written`(· 드물게 `output_damaged`).
5. battery 배치에 `model_types` 가 둘 이상이면 파일 이름에 종류가 든다(`<output>_<type><tier>_phase{n}.k`). 조합 하나라도 실패하면 rc 1.
6. offset 은 `material_card(s)` 가 없으면 거절한다(rc 1) — 예전엔 없는 MID 를 가리키는 덱을 rc 0 으로 냈다.
7. extract-parts 는 고른 파트에 칸으로 못 읽는 보 족 줄(공백으로 띄운 줄)이 있으면 거절한다(`unreadable_aux`).
8. `info --strict` 가 주 덱 + 인클루드의 같은 종류 절점 · 요소 번호 중복을 망가진 카드로 짚는다(연산 동작은 그대로 — 사용자 결정).

해석 결과가 바뀌는 것(고친 결함)
- battery 덱의 접촉 — PENMAX 가 기본값으로 돌아가고 충격체 접촉(SOFT 1)에 IGNORE 가 실제로 걸린다(예전엔 Card C 가 Card B 자리에 있어 PENMAX 1.0).
- tetremesh · unfold — 셸 · 두꺼운 셸이 솔리드(부피 0)로 나가던 것이 제 꼴(`*ELEMENT_SHELL` · `*ELEMENT_TSHELL`)로 나간다.
- hfdamp — `*MAT_ADD_EROSION` 카드를 재질로 읽던 것이 구조 재질을 읽는다.
- 뒤집은(flip) map → prestress 체인이 재질을 싣는다 — E · nu 없이도 뒤집지 않은 체인처럼 응력을 센다(사용자 결정).

| 확인 | 어디서 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `e6407dc`(11-08 판 — 지금 판은 §1-5 의 `8b49d2a`) · `revision_matches_binary` true |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `c5f74c18…` |
| 연산 수 | 시스템 상태의 `operations` | 65(그대로) |
| 스모크(dev 실측 11-08) | `mcp_server/deckops_smoke.py` · `mcp_server/allops_smoke.py` | 29/29 · 64/64(외부 잡 하나 건너뜀) |

클러스터 전처리 이미지(SmartTwinPreprocessor.sif)의 스테이징 사본도 `c5f74c18` 로 바꿨다(`scripts/stage-to-appt313.sh`) — 구워야 클러스터의 연산이
이번 고침을 쓴다. **11-09 00:48 UTC 구웠다** — 구운 SIF `da892a35f730cc134a60a2b6e66fb4542572ae9a4f0fba766c8fdd6b674dd279`(1,615,933,440 B)가 빌드
자리 · KooSlurm `compute-node-images` · `/opt/apptainers` · Drive `ApptainerImages:SmartTwinPreprocessor/SmartTwinPreprocessor.sif` 넷 다 같고 그 안의
KooRemapper 가 `c5f74c18` 이다(실측). 같은 굽기의 Drive tar 는 `SmartTwinPreprocessor_20261109_v135.tar.gz`(1,379,306,561 B — pyKooCAE 묶음
`/opt/SmartTwinPreprocessor` 만 담고 KooRemapper 는 원래 안 든다). v134(11-08 23:01)는 스테이징 앞에 구운 판이라 옛 `15d013ec` 다. 계산 노드
(node001 · 002 · viz)는 down 이라 노드 사본은 아직이다 — 살아나면 `deploy_compute_images.sh`. 다음 판으로 미룬 기존 결함 목록은 KooRemapper
`docs/01-plan/features/seatbelt-aux-walkers-1107.plan.md` 「다음 판으로 미룬 것」.

## 1-5. cae00 — 11-15 반영분(핵심 잇기 SRC-08 ~ 11 · 낙하 파이프라인 API 셋)
바이너리 · 마이그레이션 · SIF 가 그대로인 판이다(바이너리 `c5f74c18` · 0020). Drive 판 `dist-20261115-093042Z`(소스 `8b49d2a`)에서 11-08 판과 다른
파일은 `BUILD_INFO.txt` 와 콘솔 묶음 `koorm-frontend-dist.tar.gz` 둘뿐이다 — SIF 다섯과 `koorm-bin.tar.gz` 는 sha256 이 같다(실측). 그 밖에 바뀐 것은
git 으로 들어오는 파이썬(백엔드 · MCP 서버) · 정의 파일 `platform/core/ontology/dynaforge-core.json` · 새 점검 스크립트 하나다. MCP 도구는 89 →
**90**(`clear_report_unlink`), 연산 수는 65 그대로다. SP 서브모듈 고정은 `13e6b02`(v0.4.85 — 키트 판 2026-11-06 그대로). 파이썬은 `update-all` 의 git
갱신으로 들어가므로 §1 「소스」 줄(`git log -1`)과 아래 표의 도구 수로 본다.
- **핵심 잇기 — 코어 다리(SRC-08)** — 해석 온톨로지 꾸러미를 붙일 때 그 객체를 허브에서 받은 코어 객체에 잇는 선(다리)을 함께 짓는다. 관계는
  셋이다(`maps_to` `cae_part` → `part` · `indicates` `cae_finding` → `failure_mode` · `follows_method` `cae_campaign` → `analysis_method`). 정확히
  하나로 맞는 것만 규칙 선으로 긋고 나머지는 후보나 못 붙인 것으로만 보인다. 사람이 확정 · 지우는 길은 REST 둘(`POST` ·
  `DELETE /reports/{id}/cae/bridges` — 리포트 주인과 시스템 관리자만)이고, 보기는 `report_cae` 의 `bridges` 다. 사람 선은 꾸러미를 다시 붙여도 남는다.
- **과제 잇기 · 개정(SRC-09 ~ 11)** — 리포트를 과제의 판에 잇는 판정이 한 곳으로 모였다(미리 보기 · 일괄 적용 · 받기 뒤 자동 잇기 · 반입 · 메타 고침).
  기계는 사람이 정한 선과 끊은 리포트를 바꾸지 않는다. 연결을 끊으면 끊은 기록(누가 · 언제)이 남아 자동 잇기가 그 리포트를 건너뛰고, 기록 지우기는
  리포트 주인만 한다(REST `DELETE /reports/{id}/revision/unlinked` · MCP `clear_report_unlink` · 콘솔 개정 줄의 「자동 잇기 다시 허용」).
- **낙하 파이프라인 API 셋(포털 요청 11-12)** — 잡 응답의 `external` 칸 · 리포트 찾기의 `external_job_key` 거르기 · 시스템 상태의
  `postprocess_versions` 다. 덧붙이기만 했고 기존 칸 · 인자는 그대로다. 점검 스크립트 `platform/infra/scripts/check-postprocess.py`(표준
  라이브러리만)는 §2 의 설정 칸이 비었는지와 KooSlurm 위임 창구에 닿는지만 보고 값은 출력하지 않는다.
- **정의 파일** — `dynaforge-core.json`(sha256 `9253578b…51f3`)에 관계 셋이 더해지고 `rev_source` 고름 목록에 `rule` 이 더해졌다(다섯 값). 허브에 다시
  넣는 것은 허브 관리자의 손 가져오기다(아래 6).

알고 받을 동작 변화
1. 과제·개정 스위치가 **꺼진 박스**(허브 주소 · 토큰이 없는 박스 — §1-1) — 온톨로지 길(`/ontology/*` · 개정 보기)은 예전처럼 409 이고, 반입 · 메타
   고침 · 7-1 반입은 예전처럼 과제명 글자 그대로의 판에 잇는다. 해석 온톨로지 꾸러미 붙이기는 스위치와 무관하게 되고, 거울이 비어 있으면 다리 셈이 0
   이고 `bridges.notes` 가 까닭을 말한다.
2. 스위치가 **켜진 박스**(허브 설정이 선 뒤) — 반입 · 메타 고침도 자동 잇기와 같은 판정을 따른다. 허브에서 하나로 풀리는 이름은 그 과제의 판에
   잇고(출처 `rule`), 하나로 안 정해지는 이름은 잇지 않고 후보로만 보이며, 허브가 모르는 이름만 글자 그대로 잇는다(`eng_meta`). 반입 응답의
   `task_links` 수만으로는 이어졌는지 가를 수 없다 — 선은 개정 보기(`GET /reports/{id}/revision` 의 `linked`)로 본다.
3. 미리 보기(`GET /ontology/task-links`)는 관리자만에서 로그인한 누구나(읽을 수 있는 리포트만 · `scope`)로 바뀌었다. 일괄
   적용(`POST /ontology/task-links/apply`)의 응답은 네 칸에서 열두 칸이 되었고, 선은 관리자 이름의 `manual` 이 아니라 출처 `rule` 로 적힌다. 과제의 판
   목록 · 비교 · 객체 보기는 읽을 수 있는 리포트로 좁혀졌다(새 칸 `scope`).
4. 잠금 — 일괄 적용 · 합친 과제 옮기기 · 개정 확정(`PUT /reports/{id}/revision`)은 다른 길이 잠금을 쥐고 있으면 기다리지 않고 409 `busy: …` 로 답하고
   아무것도 바꾸지 않는다(잠시 뒤 다시 한다). 반입은 그대로 되고 응답의 `task_links` 가 `{skipped: "busy", detail}` 로 온다.
5. 오류 글 — 반입 응답 · 7-1 원장 · 7-1 잡 `error_summary` · 받기 기록의 짧은 오류 글은 「클래스: 한 줄」(300자 안 — SQL 문 · 배경 링크는 빠진다)로
   온다. MCP 는 경로 id(리포트 · 세션 · 잡 · 파일 …)에 `/` · `\` 가 들면 보내지 않고 도구 오류를 낸다. 리포트를 지우면 붙였던 꾸러미 파일도 함께
   지운다.
6. 정의 파일을 허브에 다시 넣을 때 — 처음에 넣은 길 · 같은 출처로 넣는다. `dynaforge` 출처로 넣었던 허브에 손으로 넣으면 파일째 거절된다(오류 넷).
   `revision_of` · `supersedes` 는 StepForge 와 이름만 같고 정의가 달라, 한 허브에 두 앱 정의를 손으로 함께 넣으면 나중 것이 앞 것을 덮는다. 다리의 끝
   타입(`part` · `failure_mode` · `analysis_method`)은 받을 타입에 있어야 한다 — `KOORM_SP_CORE_TYPES=` 빈 값(전부)이면 된다. 넣는 차례와 재어 본 것은
   KooRemapper `docs/01-plan/features/corelink-src08-11.plan.md` 「허브에 올릴 때 알릴 것」.
7. 낙하 파이프라인 — 잡 응답(`GET /jobs/{id}` · MCP `get_job`)의 `external` 은 외부 잡(stcx 제출 · 후처리 예약)이면
   `{kind, cluster_state, ontology:{state, why?}}`, 로컬 잡이면 null 이다(원본 `external_ref` 는 내보내지 않는다). `postprocess_versions` 는 최근 90일
   7-1 반입 리포트의 후처리 판(`[{name, adapter, version, n, last_at}]` · 최대 10판)이고, 그 기간에 7-1 반입이 없으면 `[]`, 못 세면 null 이다.

| 확인 | 어디서 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `8b49d2a` · `revision_matches_binary` true · `published_utc` `2026-11-15T09:30:46Z`(11-15 판의 값 — 지금 판은 §1-7) |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `c5f74c18…`(11-08 판과 같다 — 지금 판은 §1-7 의 `f20d5d5b…`) |
| 마이그레이션 | `bash platform/infra/scripts/migrate.sh` | 「Running upgrade」 줄 없음(0020 그대로) |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | `[tools] 90 (expect 90)` · `MCP SMOKE: PASS` — `clear_report_unlink` 가 새로 있다 |
| 정의 파일 | `sha256sum platform/core/ontology/dynaforge-core.json` | `9253578b…51f3` |
| 시스템 상태 | MCP `system_status`(REST `/api/v1/system/status`) | `postprocess_versions`(7-1 반입이 없었으면 `[]`) · `postprocess_versions_window_days` 90 |
| 설정 점검 | `python3 platform/infra/scripts/check-postprocess.py` | §2 를 넣은 뒤면 끝 줄이 「후처리 예약 · 반입: 설정 칸과 위임 창구가 갖춰졌다…」 — 칸 이름 · 있음/비었음 · HTTP 상태만 나오고 값은 나오지 않는다 |
| (켜진 박스만 · 리포트 주인으로) 개정 줄 | 세션 → 리포트 펼치기 → 「개정」 줄 | 「연결 끊기」 를 누르면 「… 이 끊었다 — 자동 잇기가 다시 잇지 않는다」 와 「자동 잇기 다시 허용」 단추가 보인다 |
| 스모크(dev 실측 11-15) | `mcp_server/smoke.py` · `deckops_smoke.py` · `allops_smoke.py` · `reports_smoke.py` | PASS(도구 90) · 29/29 · 64/64(외부 잡 하나 건너뜀) · 59/59(스위치 꺼짐 — 스위치를 켠 임시 스택에서는 69/69) |

⚠ 도구 수가 89 로 남아 있으면 MCP 가 옛 코드로 떠 있는 것이다 — MCP 를 다시 띄운다(`apptainer instance stop koorm_mcp` 뒤 곧바로
`bash platform/infra/scripts/start.sh`). 분이 바뀌는 때는 피한다 — 감독자(cron 의 `supervisor.sh`)가 먼저 되살리면 MCP 가 데이터
바인드(`/data/svc/kooremapper`) 없이 뜬다(11-15 dev 실측 — 이번 판 앞부터 있던 것이고 아직 고치지 않았다). 바인드가 없으면 MCP 도구가 `/data` 아래
로컬 경로(`upload_local_path` · `save_result_to_path`)를 보지 못한다. 확인은 `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` —
폴더가 보이면 바인드가 있다.

## 1-6. cae00 — 11-17 반영분(요소 번호 겹침 DF-14 · 적재 공식 답 · environment · inspect sha256)
**바이너리가 바뀐 판이다**(`248ec9bc41c5c7a3…` · glibc 요구 2.35). Drive 판 `dist-20261117-212938Z`(소스 `c37bd03`)에서 11-15 판과 다른 파일은
`BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` · 콘솔 묶음 `koorm-frontend-dist.tar.gz` 넷이다 — api · mcp · nginx · postgres SIF 는 sha256
이 같다(실측). 마이그레이션은 없다(0020 그대로). MCP 도구 90 · 연산 65 그대로. SP 서브모듈 고정은 `068fd32`(v0.4.88 — 키트 판 2026-11-06 그대로,
`coreapi` · `ontology` diff 0).
-  **요소 번호 겹침(DF-14)** — 리더는 요소를 번호 하나로 한 표에 담아, 솔리드 1 과 셸 1 처럼 족을 건넌 번호(LS-DYNA 는 족마다 따로 받는다)도 앞
  정의를 잃는다. 예전엔 그 요소가 말없이 빠져 파트 목록이 줄고, 덱을 쓰는 op 은 그 요소가 빠진 덱을 냈다. 이제 덱을 쓰는 op(map · shellmap ·
  unfold · squeeze · tetremesh · prestress 의 뒤집기 임시 덱 등 `KFileWriter` 를 거치는 것)은 그런 덱을 **거절**한다(rc 1 · 「입력 덱의 요소
  번호가 겹쳐 리더가 앞 정의 N개를 잃었다 …」). 덱을 쓰지 않는 op(contact detect · surfview 등)은 그대로 돈다(앞 요소 없이). 파일
  메타(modelmeta)에 `element_id_collisions`(잃은 정의 수) · `parts_missing`(요소가 다 빠진 파트 수)이 생기고 inspect_file 의 `meta.modelmeta`
  에도 실린다 — 콘솔 파일 패널이 경고를 보인다. 겹친 덱으로 돌던 흐름은 이제 실패로 멈추니 번호를 옮긴 덱으로 다시 올린다(`info` 가 겹친 블록 ·
  범위를 짚는다).
-  **외부 적재의 공식 답(결정 문서 D4)** — `/system/capabilities`(MCP `system_capabilities`)에 `intake` 묶음(method · path · public_url ·
  mcp_url · token `kr_pat` · portal_auth_required false · max_upload_mb · max_report_mb · batch false)이 생긴다. `public_url` 은 `platform/.env`
  의 **`KOORM_PUBLIC_BASE`**(포털 오리진 — 끝 `/` 없이, 예 `https://<포털오리진:포트>`)가 있어야 채워진다(비면 null — 지어내지 않는다). 넣으면
  api · mcp 를 재기동한다. 같은 값이 MCP `upload_instructions` 의 명령 주소가 된다. 401 이 나면 그 도구의 note 가 detail 글로 까닭을 가른다.
-  **environment(결정 문서 D5)** — 리포트 응답(찾기 · 요약 · 세션 리포트 목록 · 메타 고침)과 원샷 intake 응답에 `environment` 가 생긴다.
  `KOORM_APP_ENV` 가 production 이면 `prod` · development 면 `dev` · 그 밖이면 `unknown`.
-  **inspect sha256(리스크 앱 RK-06)** — inspect_file 응답에 파일 행의 `sha256` 이 생긴다(덱 지문 — 그동안은 세션 파일 목록에만 있었다).
-  **알고 받을 것** — SmartTwinPreprocessor SIF v137 은 옛 바이너리 `c5f74c18` 을 담고 있어 그 SIF 로 도는 REMAP 체인은 아직 옛 동작이다(다시
  굽는 것은 pyKooCAE 쪽 몫 — 알렸다). 감독자가 되살린 MCP 의 `/data` 바인드 빠짐(§1-5)은 이번 판에도 그대로다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `c37bd03`(11-17 판 — 지금 판은 §1-7 의 `e7a6ef7`) · `revision_matches_binary` true |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `248ec9bc41c5c7a386d66ab56c9514ea7dd68fa3d077e04ce68f9b74a11c3ebf`(11-17 판 — 지금 판은 §1-7 의 `f20d5d5b…`) |
| 새 동작이 든 바이너리 | `platform/backend/bin/KooRemapper help modelmeta \| grep -c element_id_collisions` | 1 이상(옛 바이너리면 0) |
| 적재 공식 답 | MCP `system_capabilities` 의 `intake` | 묶음이 있다 · `public_url` 은 `KOORM_PUBLIC_BASE` 를 넣었으면 그 주소, 아니면 null |
| 환경 | MCP `find_reports` 의 항목 | `environment` 가 `prod` |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |

## 1-7. cae00 — 11-21 반영분(캠페인 묶음 적재 DF-01 · 받기 한 줄 · 덱 칸 폭 · 펼치기 위상 · BOM · tetremesh 경고)
**바이너리가 바뀐 판이다**(`f20d5d5bbdcb1a4a…` · glibc 요구 2.35). Drive 판 `dist-20261121-120311Z`(소스 `e7a6ef7`)에서 11-17 판과 다른 파일은
`BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋이다 — api · mcp · nginx · postgres SIF 와 콘솔 묶음은 sha256 이 같다(실측). **마이그레이션
0021 이 있다**(새 표 둘 `campaigns` · `campaign_runs` — 있던 표는 건드리지 않는다). MCP 도구 90 → **93** · 연산 65 그대로. SP 서브모듈 고정은
`3196156`(v0.4.98 — 키트 판 2026-11-06 그대로, `coreapi` 는 더하기뿐이라 받는 쪽은 그대로다). 이 판을 게시하면서 Drive 의 가장 오래된 판
`dist-20261107-083706Z` 가 지워졌다(넷만 남긴다 — 11-08 · 11-15 · 11-17 · 11-21).
-  **캠페인 묶음 적재(요청서 DF-01)** — 한 과제 · 한 판의 런 수백 ~ 천 개를 캠페인 하나로 묶어 받는다. REST `POST /campaigns`(만든다 — 같은
  이름을 이미 썼으면 409 · 답의 `data.campaign_id` 가 있던 캠페인) · `POST /campaigns/{id}/runs`(런 목록 — 한 요청 5,000 런까지 · 새 run_key 는
  pending) · `GET /campaigns/{id}/ingest-status`(상태별 수 · 런마다 상태), MCP `create_campaign` · `ingest_campaign_manifest` ·
  `campaign_ingest_status`. 파일은 MCP 로 오지 않는다 — 런마다 `POST /reports/intake` 에 `campaign_id` · `run_key` 를 붙여 보낸다(둘 다 — 하나만
  오면 400). 처음 온 내용은 201 `received`, 같은 내용이 다시 오면 200 `skipped`(같은 report_id), 다른 내용이면 409 `rejected`(가진 리포트는
  그대로), 목록에 없는 run_key 는 400 이다. 상태는 pending · received · skipped · rejected 넷이고 `ingest_state` 는 그 런의 마지막 시도 결과다.
  주인이 리포트를 지우면 그 런이 다시 열린다(받았거나 건너뛴 런이 pending 으로 보인다). **캠페인은 만든 사람만 본다** — 올리는 계정과 읽는
  계정이 다르면 읽는 쪽은 404 다. `/system/capabilities`(MCP `system_capabilities`)의 `intake.batch` 가 true 가 된다. 캠페인을 지우거나 런을
  빼는 길은 없다.
-  **리포트 받기는 한 번에 하나** — 상한(`max_upload_mb` 512 · `max_report_mb` 2,048)은 그대로 두고, API 프로세스 안에서 리포트 받기가 줄을
  선다(풀린 데이터가 파일의 약 8 배라 겹치면 메모리가 곱으로 든다 — 441 MB 리포트 한 건이 최고 RSS 3,671 MB · 19.1 초). ★줄에 선 올리기는 DB
  연결을 쥔 채 기다린다 — 임시 스택에 동시 40 건을 보내니 201 이 17 건 · **500 이 23 건**이었다(연결 풀 5 + 넘침 10 이 바닥났다 · 그동안 다른
  요청은 최장 30 초를 기다렸다). 고치지 않았다 — 올리는 쪽이 동시 수를 낮게 잡는다(잰 것은 동시 셋과 마흔뿐이고, 열다섯은 풀 크기로 한 셈이다).
  잡 워커의 후처리 반입은 다른 프로세스라 그 안에서 따로 줄을 선다.
-  **덱 칸 폭 — 섞이면 거절 · 읽은 폭으로 쓴다** — extract-parts 가 `flatten_includes` 와 같은 판정으로, 칸 폭이 주 덱과 섞이는 인클루드 닫힘을
  **거절**한다(rc 1 — `*INCLUDE +` · `*INCLUDE -` 가 있거나, 인클루드 파일의 `*KEYWORD` 폭 선언이 주 덱과 다를 때. 주 덱이 `LONG=Y` · `I10=Y`
  인데 인클루드가 맨 `*KEYWORD` 로 시작해도 거절한다). 예전엔 rc 0 으로 그 파일의 칸을 다른 폭으로 읽은 덱을 냈다. 덱을 쓰는 op(map · shellmap ·
  squeeze · unfold · tetremesh 등)은 읽은 덱의 칸 폭으로 쓴다(정수 8 · 10 · 20 칸 · 실수 16 · 16 · 20 칸) — unfold · tetremesh 산출의 첫 줄이 그
  폭을 선언하고(예전엔 `I10=Y` 덱도 8칸으로 썼다), shellmap 의 `LONG=Y` 절점 줄은 68 자 → 80 자다. 번호가 그 칸에 들어가지 않으면 쓰지 않고 rc 1
  이다(「N칸에 들어가지 않는 번호가 있다 …」 — 번호를 낮추거나 `*KEYWORD I10=Y` 로 선언한 덱으로 다시 돌린다). 예전엔 8칸 덱의 9자리 번호가 칸이
  붙은 덱으로 rc 0 에 나갔다. map 결과 메시가 두께 셸 번호를 옮긴다.
-  **펼치기(unfold) — 격자를 위상으로 읽는다** — 격자 색인기가 이웃을 거리로 찾지 않고 면 공유로 번지며, 절점 순서도 면으로 읽는다. 리포 덱 339
  장 가운데 unfold 가 되던 83 장에서 81 장은 산출 바이트가 같고, 2 장은 옛 판이 rc 0 으로 요소를 바꿔 끼우던 것이 맞게 나온다(250 요소 가운데 15
  · 88). 거절되던 8 장이 펼쳐진다. ★**11-21 전에 펼친 접힌 덱은 다시 펼쳐야 할 수 있다**(촘촘히 접혀 이웃이 아닌 요소가 가까이 놓인 덱 — 옛
  산출이 rc 0 인 채 틀렸을 수 있다). 독립된 평판 덱으로 돌린 map 산출은 그대로다. 틈(맞닿은 면의 절점을 따로 둔 자리)이 있는 굽은 덱은 unfold 가
  거절한다(「… are neighbours along <축> in the grid but share no face」 — 11-17 판까지는 말없이 틈을 붙여 256 절점을 252 로 냈다). map 은 틈
  덱을 굽은 기준으로 그대로 받는다.
-  **키워드 접미사** — 공백 없이 붙여 쓴 `*NODE-` · `*ELEMENT_SOLID-` 블록을 표준 폭으로 읽는다(예전엔 그 블록을 읽지 않아 unfold · map 은 rc 1
  로 멈췄지만 squeeze 는 rc 0 으로 아무것도 누르지 않았고 tetremesh 는 rc 0 으로 절점 · 솔리드가 빠진 덱을 썼다). `*NODE%` · `*ELEMENT_SOLID%`
  블록이 산출에 두 번 실리지 않는다. `*END-` 처럼 접미사가 붙은 끝 줄에서 쓰기도 끝낸다. LS-DYNA 가 붙여 쓴 꼴을 받는지는 재지 못했다(라이선스
  만료).
-  **BOM — 셋은 고쳤고 나머지는 재기만 했다** — extract-parts(덱 걸음 · 설정 YAML)와 cleanup-nodes(덱 걸음 · 설정 YAML)가 UTF-8 BOM 을
  뗀다(cleanup-nodes 는 `*PART` 로 시작하는 BOM 인클루드에서 쓰는 절점 둘을 rc 0 으로 지웠다). **고치지 않은 것** — 덱을 받는 58 op 을 BOM 붙은
  쌍둥이 덱으로 돌린 표(매뉴얼 3.1(e))에서 14 는 같고, 23 은 산출에 BOM 붙은 `*KEYWORD` 줄이 하나 더 실리고, 19 는 산출 맨 앞에 BOM 이
  실린다(모두 rc 0). ★**matswap 의 번들 덱이 BOM 으로 시작하면 rc 0 으로 틀린 덱이 나온다**(화면이 `params=5 cards=31` 에서 `params=0 cards=36`
  으로 — 파트가 지워진 옛 SECID · HGID 를 가리킨다). apply_carryover_plan 은 BOM 으로 시작하는 조각을 rc 1 로 거절하되 까닭 글이 BOM 을 말하지
  않는다(「조각 1째 줄 — 키워드 밖의 데이터 줄」). 11-17 판에도 있던 것이다 — **덱 · 번들 · 조각은 BOM 없이 저장해 올린다**.
-  **tetremesh · id_floor** — tetremesh 가 셸 · 두께 셸 블록을 읽은 덱에서 줄째 옮긴다(리메시 앞뒤 셸 지문이 다르면 rc 1). 리더가 안 읽는 솔리드
  · 셸 · 두께 셸 변형(`*ELEMENT_SOLID_ORTHO` · `*ELEMENT_SHELL_COMPOSITE` · `*ELEMENT_TSHELL_BETA` …)은 싣지 않고 `[WARN]` 으로 키워드마다 블록
  수 · 데이터 줄 수를 찍는다(산출은 그대로 — 보 · 질량 · `*PART` · `*SECTION` · `*MAT` 은 예전처럼 경고 없이 산출에 없다). 새로 내는 절점 · 요소
  번호가 정수 상한 2147483647 을 넘게 되면 쓰지 않고 rc 1 이다(예전엔 음수 번호가 rc 0 으로 나갔다). id_floor 는 네 번호 가운데 하나라도 그
  상한을 넘으면 rc 1 · JSON 없음이다.
-  **알고 받을 것** — SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 다시 굽기 전까지 옛 바이너리를 담고 있어, 그 SIF 로 도는 REMAP 체인은 옛
  동작이다(알렸다). 감독자가 되살린 MCP 의 `/data` 바인드 빠짐(§1-5)은 이번 판에도 그대로다. 검토 한 차례에서 찾고 고치지 않은 기존 결함
  여섯(전부 두께 셸인 덱의 unfold 두께 방향 · `*KEYWORD` 폭 선언을 부분 문자열로 읽는 것 · `*KEYWORD` 가 둘이거나 들여쓴 덱 · `*KEYWORD_ID
  I10=Y` · 음수 세 자리 지수 좌표 17 자 · 정수 상한을 넘는 절점 번호)은 `docs/01-plan/features/seatbelt-aux-walkers-1107.plan.md` 의 「다음
  판으로 미룬 것」 에 있다. LS-DYNA 로 돌려 본 것은 없다(라이선스 만료).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `e7a6ef7` · `revision_matches_binary` true · `published_utc` `2026-11-21T12:03:15Z`(11-21 낮 판 — 지금 판은 §1-8) |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `f20d5d5bbdcb1a4a7962b209542d17992cb15e7fc539d6d06a218e5e6b13fe97`(11-21 낮 판 — 지금 판은 §1-8 의 `d1e2ce96…`) |
| 새 동작이 든 바이너리 | `platform/backend/bin/KooRemapper help tetremesh \| grep -c 2147483647` | 1 이상(옛 바이너리면 0) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 처음엔 「Running upgrade 0020_cae_report_rows -> 0021_campaigns」 한 줄, 다시 돌리면 그 줄 없이 「✓ migrations applied」 |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 93개(`create_campaign` · `ingest_campaign_manifest` · `campaign_ingest_status` 가 새로 있다) · `MCP SMOKE: PASS` |
| 묶음 적재 | MCP `system_capabilities` 의 `intake.batch` | true(11-17 판은 false) |
| 캠페인 한 바퀴 | MCP `create_campaign` → `ingest_campaign_manifest`(run_key 하나) → `campaign_ingest_status` | `counts.listed` 1 · `counts.pending` 1. 지우는 길이 없으니 점검용임을 알아볼 이름으로 만든다(dev 에는 `dev-smoke-campaign-20261121T120207Z` 가 남아 있다) |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |

## 1-8. cae00 — 11-21 밤 반영분(덱 · 번들 BOM 떼기 · 빈 메시 거절 — 미룬 결함 3차 1판)
**바이너리가 바뀐 판이다**(`d1e2ce96d9b6a722…` · glibc 요구 2.35). Drive 판 `dist-20261121-234834Z`(소스 `98f5ec6` — 코드는 `cd52b79` · 뒤
커밋은 문서만)에서 11-21 낮 판(§1-7)과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋이다 — api · mcp · nginx · postgres SIF
와 콘솔 묶음은 sha256 이 같다(실측). **마이그레이션은 없다**(0021 그대로). 파이썬 · 콘솔 코드는 바뀌지 않았다. MCP 도구 93 · 연산 65 그대로. SP
서브모듈 고정은 `3196156` 그대로(키트 판 2026-11-06). 이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261108-234149Z` 가 지워졌다(넷만 남긴다
— 11-15 · 11-17 · 11-21 낮 · 11-21 밤).
-  **덱 · 번들 맨 앞의 UTF-8 BOM 을 떼고 읽는다** — 덱 · 번들 · 조각 · 격자 파일을 여는 자리에서 BOM 을 건너뛰고, 산출에는 싣지 않는다. 덱을
  받는 58 op 을 BOM 붙인 쌍둥이 덱으로 돌려 57 op 이 BOM 없는 쪽과 종료 코드 · 화면 · 산출이 같았다(§1-7 판에서는 44 op 이 달랐다 — 대개 산출에
  BOM 붙은 `*KEYWORD` 줄이 하나 더 실리거나 산출 맨 앞에 BOM 이 실렸다). ★§1-7 의 「matswap 의 번들 덱이 BOM 으로 시작하면 rc 0 으로 틀린 덱이
  나온다」 는 이 판에서 닫혔다(번들을 읽는 자리 둘 — YAML 꼴과 옛 자리 인자 꼴 — 을 다 고쳤다). ale 의 재료 파일(BOM 이면 `*MAT_` 블록이 통째로
  빠지고 `*EOS_` 만 실렸다) · warpage · bend 의 격자 파일(BOM 이면 첫 행이 조용히 빠졌다)도 뗀다 — 둘 다 §1-7 판에도 있던 것이다.
-  **조각** — `cad_solid_merge_to_deck` 은 조각의 BOM 을 떼고 넣는다(rc 0 그대로). `apply_carryover_plan` 은 BOM 으로 시작하는 조각을 그대로
  거절하되(rc 1) 까닭 글이 BOM 을 말한다(「UTF-8 BOM 으로 시작한다 — 조각은 BOM 없이 싣는다」 — §1-7 판은 「키워드 밖의 데이터 줄」 이라고
  했다). BOM 붙은 덱에서 낸 이월 계획은 그대로 적용하고 산출에 BOM 을 싣지 않는다(§1-7 판은 BOM 이 실린 덱을 썼다). 계획이 BOM 없는 덱에서
  나왔는데 BOM 붙은 덱에 적용하면 예전처럼 `deck_sha` 로 거절하고, 이제 그 줄이 BOM 을 말한다.
-  **`*INCLUDE` 뿐인 주 덱 — `strain` · `squeeze` 가 빈 메시를 거절한다** — 명령줄 꼴의 두 op 은 인클루드를 펼치지 않는다. 주 덱이 `*INCLUDE`
  뿐이면 예전엔 rc 0 으로 빈 산출(절점 0 · 솔리드 0)을 냈고, 이제 rc 1 로 멈춘다(「… 에서 절점을 하나도 읽지 못했다」). 셸뿐인 덱은 예전처럼
  돈다. 인클루드를 쓰는 덱은 미리 펼친 한 파일로 넘긴다.
-  **그대로인 것** — JSON 입력(이월 계획 · id_floor 와 cad_solid_merge_to_deck 의 대응표 · rebind 의 `range_diff` · 재료 DB)의 BOM 은 예전처럼
  rc 1 로 거절하고 까닭 글이 BOM 을 말하지 않는다 — JSON 은 BOM 없이 저장한다. BOM 없는 덱은 도움말 사례 64 를 §1-7 판과 새 판(같은 소스의 dev
  빌드)으로 돌려 rc · 화면 · 산출이 64 / 64 같다. 도움말 글은 바뀌지 않았다.
-  **알고 받을 것** — SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 다시 굽기 전까지 옛 바이너리를 담고 있어, 그 SIF 로 도는 REMAP 체인은 옛
  동작이다(알렸다 — 새 판인지 가르는 판정 꾸러미를 같이 넘겼다). 이 판은 미룬 결함 3차의 다섯 판 가운데 첫 판이다(나머지 — 칸 폭 · 번호 한계 ·
  쌓인 카드 · 재료 · 번호 커서 · 파일 · 메모리 · battery — 은 판마다 따로 올린다, `docs/01-plan/features/deferred-defects-round3-1121.plan.md`).
  LS-DYNA 로 돌려 본 것은 없다(라이선스 만료 — BOM 덱을 솔버가 받는지는 재지 못했다).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `98f5ec6` · `revision_matches_binary` true · `published_utc` `2026-11-21T23:48:37Z`(11-21 밤 판 — 지금 판은 §1-9) |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `d1e2ce96d9b6a722bbcb944302f9893a0a14ab79840e46a1634d829f22855cfc`(11-21 밤 판 — 지금 판은 §1-9 의 `1106bef1…`) |
| 새 동작이 든 바이너리 | `grep -a -c 'UTF-8 BOM 으로 시작한다' platform/backend/bin/KooRemapper` | 1 이상(§1-7 판 바이너리면 0) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 「Running upgrade」 줄 없이 「✓ migrations applied」(그 판은 0021 그대로 — 지금 판은 §1-9 의 0022) |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 93개 그대로(그 판 — 지금 판은 §1-9 의 97개) · `MCP SMOKE: PASS` |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |

## 1-9. cae00 — 11-22 반영분(DF 2차 ② 런 출처 · 유효성 · 미룬 결함 3차 2판 — 칸 폭 · 번호 한계)
**바이너리가 바뀌고 마이그레이션이 하나 있는 판이다**(바이너리 `1106bef1d4ef0e4d…` · glibc 요구 2.35 · 마이그레이션 0022). Drive 판
`dist-20261122-042305Z`(소스 `a50bcc3`)에서 §1-8 판과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋이다 — api · mcp · nginx ·
postgres SIF 와 콘솔 묶음은 sha256 이 같다(실측). MCP 도구 93 → 97 · 연산 65 그대로. SP 서브모듈 고정은 `3196156` 그대로(키트 판 2026-11-06).
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261115-093042Z` 가 지워졌다(넷만 남긴다 — 11-17 · 11-21 낮 · 11-21 밤 · 11-22).
-  **캠페인 런 출처 · 유효성(DF-02 · DF-03 · 2차 ②)** — 캠페인 런마다 출처(설정 세대 `config_generation` · 대체 `superseded_by` · 해석기)와 건강
  판정(valid · warn · invalid 와 까닭)을 본다. 판정은 저장하지 않고 읽을 때 문턱으로 다시 낸다. 기본 문턱은 요청서 값(에너지 비 1.05 ·
  모래시계/내부 0.10 · 추가 질량 0.5 % · KE0 ±10 % · 접촉 에너지 −100 mJ)이고 캠페인마다 바꿀 수 있다. 수치가 없는 런은 invalid(health_missing)
  이라 기본에서 빠진다. REST 넷 — `PUT /api/campaigns/{id}/health-thresholds` · `GET /api/campaigns/{id}/provenance` · `GET
  /api/campaigns/{id}/health` · `GET /api/reports/{id}/health`, MCP 넷 — `set_campaign_health_thresholds` · `campaign_provenance` ·
  `campaign_health_table` · `report_health`. `find_reports` 가 `config_generation` 으로 거른다. 마이그레이션 0022 는 캠페인 · 런 표에 null 허용
  칸을 더한다(있던 행은 그대로).
-  **동시 올리기** — 리포트 받기 줄에 서기 전에 DB 연결을 놓는다. 47 MB 리포트 동시 40 건이 201 40 이 됐다(11-20 측정은 201 17 · 500 23 · 그동안
  다른 요청 최장 30 초 → 이번 0.9 초).
-  **본문에 Infinity · NaN** — 422 대신 500 이 되던 것(검증 오류 글이 받은 값을 되돌려 싣다 JSON 으로 못 썼다)을 422 로.
-  **`LONG=Y` 덱(3차 2판)** — 제 카드 리더를 가진 op 여덟(cnrb2solid · cnrb2spring · cclip · matswap · ale · stackwrap · neutralaxis · info)이
  선언된 20 칸으로 읽는다(예전엔 rc 0 으로 바뀌지 않은 덱 · 거짓 「정의되지 않은 카드」 · 엉뚱한 까닭의 rc 1). 새로 쓰는 카드도 덱 폭으로 쓴다 —
  예전엔 op 열다섯(elform · iga · merge · formstrain · matdb · load · boundary · contact · relax · stabilize · database · hfdamp · implicit ·
  modal · optimize)이 LONG 덱에 10 칸 카드를 rc 0 으로 끼웠다. 곁 파일(dynain · IGA 인클루드 · 단독 extract-surface 의 셸 덱)도 주 덱이 LONG
  이면 `*KEYWORD LONG=Y` 로 쓴다(맨 `*KEYWORD` 인클루드는 LS-DYNA 가 주 덱 폭으로 읽을 수 있다). 요소 · 절점을 더하는 op 일곱의 LONG 거절은
  그대로다.
-  **정수 상한** — 덱의 최대 번호가 2147483647 이면 새 번호를 내는 op(meshfix · cnrb2solid · matswap · boundary · ale · iga · cclip · merge ·
  contact)이 넘친 음수 번호를 쓰던 것을 rc 1 로 멈춘다. 리더가 상한을 넘는 번호를 0 으로 읽어 그 절점 · 요소를 버리던 것도 거절로(예전엔 squeeze
  · tetremesh 가 rc 0 으로 하나 빠진 덱을 냈다). 덱 폭 선언은 `*KEYWORD` 첫 카드의 낱말만 읽는다(`JOBID=LONGRUN` 이 LONG 으로 읽히던 것).
-  **battery** — assemble 의 battery 덱을 주 덱 칸 폭으로 쓴다(`I10=Y` · `LONG=Y` 주 덱에 표준 폭 인클루드를 붙이던 것). `use_include: false` 의
  거절을 뺐다.
-  **extract_surface(바뀐 계약)** — `output_pid` 가 이미 있는 파트 번호면 아무것도 쓰지 않고 rc 1. 새 번호에는 `*PART` 와 `*SECTION_SHELL`
  (ELFORM 2 · NIP 2 · 새 SECID · MID 는 셸을 뽑은 솔리드 파트의 것)을 짓고, 두께 `thickness`(단독은 `--thickness`)가 **필수**다. 단독 명령의
  기본 `--output-pid 1` 은 그대로라 PID 1 이 있는 덱이면 거절된다 — 새 번호를 준다. 플랫폼 카탈로그(폼 · MCP 인자)에 `thickness` 가 더해졌다.
-  **unfold** — 두께 셸은 제 절점 차례(두께 방향)를 지킨다(예전엔 격자 k 축으로 두께를 바꿔 썼다).
-  **알고 받을 것** — SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 다시 굽기 전까지 옛 바이너리다(알렸다). LS-DYNA 로 돌려 본 것은 없다(라이선스
  만료 — LONG 곁 파일 · battery 주 덱 폭 · 새 셸 섹션은 솔버가 받는지 재지 못했다). 검증런은 사용자가 cae00 에서 돌린다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `a50bcc3` · `revision_matches_binary` true · `published_utc` `2026-11-22T04:23:08Z`(11-22 새벽 판 — 지금 판은 §1-10) |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `1106bef1d4ef0e4dca215f62247359962120dae9147f92e7901c75aba52ad62a`(11-22 새벽 판 — 지금 판은 §1-10 의 `4b8fe975`) |
| 새 동작이 든 바이너리 | `grep -a -c '새 셸 파트' platform/backend/bin/KooRemapper` | 1 이상(§1-8 판 바이너리면 0 · 지금 판에도 있다) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 처음 한 번 「Running upgrade 0021 -> 0022」 뒤 「✓ migrations applied」 · 다시 돌리면 그 줄 없이 |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 97개(`set_campaign_health_thresholds` · `campaign_provenance` · `campaign_health_table` · `report_health` 가 새로 있다 — 그 판 · 지금 판은 §1-10 의 100개) · `MCP SMOKE: PASS` |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |

## 1-10. cae00 — 11-22 낮 반영분(미룬 결함 3차 3판 — 쌓인 카드 · 재료 · 번호 커서 · DF 2차 ③ 추출 완전성 · 삭제 허가)
**바이너리가 바뀌고 마이그레이션이 하나 있는 판이다**(바이너리 `4b8fe975202d9103…` · glibc 요구 2.35 · 마이그레이션 0023). Drive 판
`dist-20261122-062855Z`(소스 `2cbdc84`)에서 §1-9 판과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋이다 — api · mcp · nginx ·
postgres SIF 와 콘솔 묶음은 sha256 이 같다(실측). MCP 도구 97 → 100 · 연산 65 그대로. SP 서브모듈 고정은 `3196156` 그대로(키트 판 2026-11-06).
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261117-212938Z` 가 지워졌다(넷만 남긴다 — 11-21 낮 · 11-21 밤 · 11-22 새벽 · 11-22 낮).
-  **쌓인 카드 묶음(3차 3판)** — 한 키워드 아래 정의가 여러 벌 쌓인 덱을 바로 다룬다. matswap(두 꼴) · cclip 은 바꾼 파트의 옛 섹션 · 모래시계
  **묶음만** 지우고(예전엔 블록째 지워 쌓인 이웃 파트의 것까지 잃었다) 새 SECID · HGID 는 쌓인 묶음까지 센 최대값 위로(ale 도). matdb 는 쌓인
  둘째 재질도 고르고 고아 재질의 `*MAT_ADD_*` 를 지운다. 리더가 `*MAT_ELASTIC` · `_PIECEWISE_LINEAR_PLASTICITY` · `_RIGID` 의 쌓인 묶음을 다
  읽는다(prestress 가 둘째 재질을 「NOT FOUND — stress 0」 으로 내던 것). rbe 의 CNRB PID · matdb 의 감쇠 세트는 공용 번호 커서로(파트 · 세트
  번호와 겹치던 것).
-  **열 재질 · `*PART +` · extract-parts** — `*MAT_T` 뒤에 숫자가 오는 철자(`*MAT_T1` · `T19` · `T001`)를 다 열 재질로 본다. info 가 *PART 의
  TMID 를 보고, 열 재질이 정의하지 않는 TMID 는 **의심 줄**(「열 재질(TMID) N 이 정의되지 않았습니다」 — rc · `--strict` 와 무관)이다 — 구조
  해석은 LS-DYNA 가 없는 TMID 를 받는다(TMID 107 이 없는 battery 덱이 정상 종료한 기록). 칸폭 표지 `*PART +` 를 맨 파트로 읽는다(20 절점
  솔리드를 요소 둘로 읽어 「파트 12 미정의」 를 내던 것). extract-parts 는 `*MAT_ADD_THERMAL_EXPANSION` 같은 PID 꼴 덧붙임을 고른 파트와 견준다.
-  **`--strict` 겹침** — SECID · MID 겹침을 쌓인 묶음까지 보고 `_TITLE` 의 빈 제목 줄을 제목으로 센다(`*MAT_RIGID_TITLE` 의 CMO `1` 을 MID 1
  겹침으로 막던 것 · 세트 제목의 거짓 SID 겹침). 들여 쓴 `*` · `$` 제목은 키워드 · 주석이 아니다(1열 규칙). 저장소 덱 339 장 · `/data` 표본 521
  장에서 `--strict` 의 rc · 확정 줄이 바뀐 덱은 0 이다. 쌓인 묶음에 진짜 겹침이 있는 덱은 이제 rc 1 이다.
-  **DF 2차 ③(DF-04)** — 런 목록이 `extraction`(d3plot 상태 수 · `peak_source` · 뽑은 장 · 지움)을 받고, 캠페인에 필수 추출 목록을 둔다. REST 셋
  — `PUT /api/campaigns/{id}/required-extractions` · `GET /api/campaigns/{id}/deletion-clearance` · `GET /api/reports/{id}/extraction`, MCP 셋 —
  `set_campaign_required_extractions` · `campaign_deletion_clearance` · `report_extraction`. 삭제 허가는 **조회만** 하고(지우기는 KooChainRun)
  필수 목록이 없는 캠페인은 모든 런이 보류다. 피크를 돌려주는 리포트 응답 열에 `peak_provenance`(peak_source · states_read · states_total ·
  peak_may_be_missed)가 실린다 — 값은 캠페인 런의 추출 목록에서만 온다. 마이그레이션 0023 은 null 허용 칸 둘(있던 행 그대로).
-  **알고 받을 것** — SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 다시 굽기 전까지 옛 바이너리다(알렸다). LS-DYNA 로 돌려 본 것은 없다(라이선스
  만료 — `*MAT_T1` 같은 철자를 솔버가 받는지 · 열 해석 덱에서 없는 TMID 가 멈추는지는 재지 못했다). 검증런은 사용자가 cae00 에서 돌린다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `2cbdc84` · `revision_matches_binary` true · `published_utc` `2026-11-22T06:28:59Z` |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `4b8fe975202d9103c9c69c5530ea20c2d9bf72617139b26de9ed04368e86cc85` |
| 새 동작이 든 바이너리 | `grep -a -c '열 재질(TMID)' platform/backend/bin/KooRemapper` | 1 이상(§1-9 판 바이너리면 0) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 처음 한 번 「Running upgrade 0022_campaign_health -> 0023_campaign_extraction」 뒤 「✓ migrations applied」 · 다시 돌리면 그 줄 없이 |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 100개(`set_campaign_required_extractions` · `campaign_deletion_clearance` · `report_extraction` 이 새로 있다) · `MCP SMOKE: PASS` |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |
| 되돌리기 | §8 | 앞 판 `dist-20261122-042305Z`(코드 `a50bcc3` · 바이너리 `1106bef1`) — 0023 의 칸 둘은 null 이라 옛 코드가 그대로 돈다 |

## 1-11. cae00 — 11-22 오후 반영분(미룬 결함 3차 4 · 5판 — 파일 · 메모리 · battery · 옵션 카드 · DF 2차 ④ 보고서용 묶음)
**바이너리가 바뀌고 마이그레이션이 하나 있는 판이다**(바이너리 `066e21a3508ac3fe…` · glibc 요구 2.35 · 마이그레이션 0024). Drive 판
`dist-20261122-085355Z`(소스 `87632b1`)에서 §1-10 판과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋이다 — api · mcp · nginx ·
postgres SIF 와 콘솔 묶음은 sha256 이 같다(실측). MCP 도구 100 → 103 · 연산 65 그대로. SP 서브모듈 고정은 `3196156` 그대로(키트 판 2026-11-06).
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261121-120311Z` 가 지워졌다(넷만 남긴다 — 11-21 밤 · 11-22 새벽 · 11-22 낮 · 11-22 오후).
-  **파일 · 메모리(3차 4판)** — 인클루드 닫힘을 펼치는 연산이 파일을 열기 전에 크기를 본다(474 바이트 주 덱이 40 GB 희소 인클루드를 끌면 예전엔
  주소 공간을 다 쓰도록 읽고 rc 0 — 이제 열기 전에 rc 1). 산출 이름이 주 덱의 `*INCLUDE` 이름 자리(`*INCLUDE_PATH` 로 찾던 것)와 같으면 쓰지 않는다
  (산출이 자기를 끌어오던 것). 디스크가 차면 덱 · 보고가 아닌 쓰기(CSV · JSON · SVG …)도 rc 1 이다. 되읽는 산출 자리가 장치 · FIFO 면 쓰기 전에
  거절한다. 플랫폼 실행기가 잡이 끝날 때 작업 폴더의 주인 없는 오래된 임시 파일(10 분 넘은 `*.kr_tmp_*`)을 치운다.
-  **battery · 읽기(3차 5판)** — battery 덱이 없는 재질 · 섹션 · 세트를 가리키던 것을 고쳤다(적층 기본 덱의 전해질 PART → 없는 MID 8 · side 의
  SPC → 없는 세트 3 · `no_impactor` 의 SPC → 없는 세트 2 · 3 · 권취 `core_fill` → 없는 섹션 33 — 모두 battery rc 0 에 LS-DYNA 가 키워드 단계에서
  멈추는 덱). **덱 바이트가 바뀐다** — 적층 side 덱에 바닥판이 생기고, Card A 의 SBOPT 가 `     3.000` 에서 `         3` 으로, 모르는
  `mode`(예: `nail` — 못 압입자는 `mode: side` 에 `indenter.type: nail`)는 rc 1 이다. 적층 탭이 셀 끝을 넘으면 `[WARN]` 이 지은 범위를 댄다. 보 옵션
  카드(`_WARPAGE` 의 SN · `_ELBOW` 의 MN) 절점을 Card 1 처럼 칸 읽기 · 다른 읽기로 가르고, cleanup-nodes 되읽기가 keep · 모르는 키워드로 지킨
  절점까지 잰다(보고 `verify.undefined_kept`). cnrb2solid 는 들여 쓴 `*` 줄(제목)을 키워드로 보지 않는다.
-  **DF 2차 ④(DF-13)** — 보고서 · 영상 생성기가 읽을 묶음을 짓는다. REST 넷 — `POST /api/bundles` · `GET /api/bundles/{id}` ·
  `GET /api/bundles/{id}/diff` · `GET /api/campaigns/{id}/bundles/latest`, MCP 셋 — `build_report_bundle` · `report_bundle` · `report_bundle_diff`. 주소
  (`bundle_id`) 하나에 판을 쌓고(숫자가 같으면 판을 올리지 않는다), 판마다 수치 기준 줄(유효 n / 전체 N · 제외 까닭) · 표(runs · case_metrics ·
  part_peaks) · 그림 인용(sha256) · 앞 판 대비 바뀐 숫자가 있으며, 숫자마다 `source_path` 가 리포트 · 케이스 · 지표까지 거슬러 간다. 마이그레이션
  0024 는 새 표 둘(있던 표는 그대로).
-  **알고 받을 것** — SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 다시 굽기 전까지 옛 바이너리다(알렸다 — battery 덱 sha 를 고정한 판정은 다시
  재야 한다). LS-DYNA 로 돌려 본 것은 없다(라이선스 만료 — 새 battery 덱 · SBOPT 정수가 솔버에서 도는지는 재지 못했다). 검증런은 사용자가
  cae00 에서 돌린다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `87632b1` · `revision_matches_binary` true · `published_utc` `2026-11-22T08:53:58Z` |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `066e21a3508ac3fe1fa549575b30c4359c466ac527cfe1ee88b637708a02372e` |
| 새 동작이 든 바이너리 | `grep -a -c '모르는 mode' platform/backend/bin/KooRemapper` | 1 이상(§1-10 판 바이너리면 0) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 처음 한 번 「Running upgrade 0023_campaign_extraction -> 0024_report_bundles」 뒤 「✓ migrations applied」 · 다시 돌리면 그 줄 없이 |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 103개(`build_report_bundle` · `report_bundle` · `report_bundle_diff` 가 새로 있다) · `MCP SMOKE: PASS` |
| MCP 바인드 | `apptainer exec instance://koorm_mcp ls -d /data/svc/kooremapper` | 폴더가 보인다(감독자가 되살린 MCP 면 안 보인다 — §1-5) |
| 되돌리기 | §8 | 앞 판 `dist-20261122-062855Z`(코드 `2cbdc84` · 바이너리 `4b8fe975`) — 0024 는 새 표 둘이라 옛 코드가 그대로 돈다 |

## 1-12. cae00 — 11-22 저녁 반영분(DF 2차 ⑤ 캠페인 분석 · ⑥ 핫스팟 자리 · 덱 세션 판 — 파이썬만)
**Drive 판은 §1-11 그대로다**(`dist-20261122-085355Z` · 바이너리 `066e21a3` — 다시 받을 아티팩트가 없다). 코드는 `git pull`(update-all 의 git 갱신)로
들어오고 **마이그레이션이 둘**(0025 · 0026 — null 허용 칸 넷과 새 표 다섯, 있던 행 그대로) · MCP 도구 103 → 120 이다. health 의 `revision` 은
`87632b1` 그대로라 이 반영은 §1 「소스」 줄의 `git log -1`(`4cca82a` 이거나 그 뒤)로 본다.
-  **⑤ 캠페인 분석(DF-05 · 06 · 08 ~ 12)** — 각도 표 · 통계(26 방향 라벨 · 범주 · 다회 충격 비율 · KE 튐 런 따로) · 피크 표(충격 차수 — 충격 구간은
  런 목록의 `impacts`) · 여유(기준값 묶음만 — 리포트 항복값을 쓰지 않음) · 구면 지도(경위도 격자 · Mollweide 그림) · 부분충격 자리 표 · 지도 ·
  리비전 비교(파트 짝 표 · 공통 각도만) · 설정 쌍 비교(쌍 규칙 · 판정). 쓰기 다섯 — `set_campaign_part_groups` · `set_campaign_criteria` ·
  `set_campaign_sites` · `import_part_map` · `set_campaign_pair_rule`.
-  **⑥ 핫스팟 자리(DF-07)** — 결과 틀 → 덱 틀 이동값(`set_campaign_frame_offset`)으로 핫스팟 군집을 덱 좌표에서 묶는다(되풀이 각도 · bbox 포함률).
   **덱 세션(DF-15 나머지)** — 세션 응답에 `environment` · `deck_revision_label` · `linked_cad` · `revision_warning`(REST PATCH 로 둔다) ·
  `rename_session_part`(*PART 제목 줄 제자리 바꾸기).
-  **알고 받을 것** — 요청서의 대조 파일(각도 표 · 피크 표 · 격자 스크립트 · 자리 결과 · 쌍 판정 · 핫스팟 재집계)은 이 박스에 없어 합성 사례로만 쟀다
  — 대조는 cae00 검증런에서 한다. 전각도 리포트 표본(26 방향)의 각도는 생성기 규약(`swap`)대로 읽어 범주가 생성기와 26 / 26 맞는다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `4cca82a` 이거나 그 뒤 |
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `87632b1` 그대로 · `revision_matches_binary` true(바이너리 `066e21a3` 그대로) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 처음 한 번 「Running upgrade 0024_report_bundles -> 0025_campaign_analysis」 · 「0025 … -> 0026_hotspot_session」 뒤 「✓ migrations applied」 |
| MCP 도구 | `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 120개 · `MCP SMOKE: PASS`(API · MCP 를 재기동한 뒤 — 파이썬만 바뀌어도 재기동해야 새 길이 선다) |
| 구면 지도 | 캠페인 하나로 `campaign_sphere_map(campaign_id)` | 글(격자 최소 · 최대 · 방향 점 · 출처 줄) + Mollweide 그림 이미지 블록 |
| 되돌리기 | §8 | 코드만 `87632b1` 로 — 0025 · 0026 은 null 칸과 새 표라 옛 코드가 그대로 돈다 |

## 1-13. cae00 — 11-22 밤 반영분(미룬 결함 3차 6판 — battery phase_modes · contact.depth · 권취 나선 판 · 들여 쓴 `*` 줄)
**지금 판은 §1-14(7판)다** — 이 절 표의 소스 · 판 · 바이너리 값은 6판(`f0cc07d` · `c1a274c4`)을 받았을 때의 것이다. 7판을 받았으면 그 셋은 §1-14
표로 보고, battery 사슬 줄은 7판에서도 그대로 맞다(11-24 바로잡음 — cae00 넘김).
**바이너리가 바뀐 판이다**(`c1a274c4ba6eabf0…` · glibc 요구 2.35). Drive 판 `dist-20261123-080850Z`(코드 `f0cc07d`)에서 §1-12 판과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋(api · mcp · nginx · postgres SIF 와 콘솔 묶음은 sha256 이 같다 — 실측) · **마이그레이션 없음** · MCP 도구 120
그대로. 사용자가 고른 넷(11-22 저녁) 가운데 셋을 지었다 — 열 해석 덱의 없는 TMID 는 고치지 않고 검증런에서 잰다.
- **battery phase_modes** — `batch.phase_modes` 의 swell · bare 판은 압입자 · 바닥판만 빼고 탭 · PCM 은 둔다(phase 1 의 셀 · 탭 · PCM 절점 ·
  요소 번호가 phase 2 에 같은 번호 · 같은 자리로 있다 — dynain 사슬). 단독 `mode: swell` · `bare` 는 그대로 넷 다 뺀다. 맨 위 `mode: swell` 의
  dent 판은 이제 압입자 · 처방 운동을 짓는다(전엔 고정구 없는 dent 덱 · rc 0). **권취는 탭 · PCM 을 압입자 · 바닥판보다 먼저 짓는다** — 고정구가
  있는 권취 덱(dent · side)은 그 넷의 번호가 바뀐다(좌표 · 세트 · 경계 · 접촉 카드는 좌표로 같다). 적층 단독 덱은 바이트가 같다.
- **contact.depth · soft** — `contact.depth` 가 모든 자동 접촉 Card A 의 DEPTH 에 쓰인다(기본 5 — 안 준 덱은 같다). 정수 0 이상만 받는다(음수 ·
  소수 · 글자 · 열 자리는 rc 1). `contact.soft` 는 읽기만 하고 적으면 [WARN].
- **권취 나선 판(`wound.flat: false`)** — 전해질 채움 PART 의 섹션 33 을 쓴다(전엔 나선 판 48 덱 가운데 36 이 없는 섹션을 가리켜 LS-DYNA 가
  키워드 단계에서 멈췄다 · rc 0). 적층 · 권취 평평 · 권취 나선 × mode 넷 × 선택 열둘 144 덱이 `info --strict` rc 0.
- **들여 쓴 `*` 줄** — contact · cclip · matswap(YAML 꼴 · 옛 위치 인자 꼴) · merge · optimize · modelmeta · ale 이 제목 · `*COMMENT` 글 속의
  `  *…` 를 키워드로 읽지 않는다(리더 · LS-DYNA 의 1열 규칙). 전엔 cclip · matswap · merge 가 rc 1 로 멈추거나 matswap 이 rc 0 으로 나눠 쓰는
  모래시계를 지웠고, optimize 가 implicit 으로 잘못 보았다.
- **알고 받을 것** — LS-DYNA(라이선스 만료)로 재지 못했다 — phase 2 가 phase 1 dynain 을 읽는지 · DEPTH 를 바꾼 접촉 · 나선 판 덱(검증런 §1).
  여섯 op 밖(assemble 의 다른 연산 · stabilize · standalone_ops · strip)에 같은 `*` 꼴이 남았다 — 최종 보고의 물음.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `f0cc07d` 이거나 그 뒤 |
| 판 | 운영 노드의 DynaForge `/api/health`(위 「어디서 재나」) | `revision` `f0cc07d` · `revision_matches_binary` true(6판 — 7판이면 §1-14) |
| 바이너리 | `sha256sum build/linux/bin/KooRemapper` | `c1a274c4ba6eabf03b8948e6bc72712fe5b7a080870f40d9685ba9b1c47a4a51` |
| battery 사슬 | `output: bt` · `model_type: wound` · `tier: -1` · `mode: dent` · `use_dynain: true` 에 `batch:` 아래 `phases: [1, 2]` · `phase_modes: [swell, dent]`(두 칸 들여 쓴 블록 꼴)로 `KooRemapper battery` | 덱 둘 · phase 1 에 PART 100 · 101(압입자 · 바닥판) 요소가 없고 2020 · 2021 · 2030(탭 · PCM)은 있다 |
| MCP 도구 | 게이트웨이 `curl -s --noproxy '*' localhost:9110/tools-map` 의 `apps` 가운데 `heax-kooremapper_mcp`(읽기 전용 — 운영에서 smoke.py 는 돌리지 않는다) | `tool_count` 120 · `reachable` true(API · MCP 를 재기동한 뒤 — 카탈로그 글이 바뀌었다) |
| 되돌리기 | §8 | 바이너리 · 코드를 `dist-20261122-085355Z`(코드 `87632b1` · 바이너리 `066e21a3`)로 — 마이그레이션이 없어 DB 는 그대로 |
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261121-234834Z` 가 지워졌다(넷만 남긴다 — 11-22 새벽 · 11-22 낮 · 11-22 오후 · 11-23).

## 1-14. cae00 — 11-23 반영분(미룬 결함 3차 7판 — 권취 강체 방향 · battery 카드 꼴 · ale EOS 제목 · 들여 쓴 `*` 줄 나머지)
**지금 판은 §1-15 다** — 이 절 표의 소스 · 판 값은 7판(`6ac0f7e`)을 받았을 때의 것이다(바이너리는 §1-15 도 같다). 11-25 판을 받았으면
그 둘은 §1-15 의 값으로 본다.
**바이너리가 바뀐 판이다**(`139036f27a554c87…` · glibc 요구 2.35). Drive 판 `dist-20261123-094507Z`(코드 `6ac0f7e`)에서 §1-13 판과 다른 파일은 `BUILD_INFO.txt` · `koorm-bin.tar.gz` · `cli.sif` 셋(api · mcp · nginx · postgres SIF 와 콘솔 묶음은 sha256 이 같다 — 실측) · **마이그레이션
없음** · MCP 도구 120 · 연산 65 그대로 · SP 서브모듈은 `5753257`(v0.4.99 · 키트 2026-11-06 그대로 — 받는 쪽 그대로). 6판에서 재다 나온 목록 밖
줄을 사용자가 고른 대로(11-23) 지었다.
- **battery** — 권취 dent · side 덱의 바닥판(PID 101 · 솔리드 16) · PCM(2030 · 9)을 바로 선 차례로 쓴다(전엔 모두 뒤집혀 `info` 가 「Negative
  Jacobian elements: 25」 — 절점 좌표 · 번호는 그대로, 요소 줄 25 개만 바뀐다). 적층 tied 접촉의 Card 3 은 실수꼴(`info` 의 「손상 의심」 둘이
  없어진다). 탭을 짓지 않는 적층 덱(no_pcm · 단독 swell · bare)은 탭 PART 20 · 21 카드와 셀 파트 세트 칸을 쓰지 않는다.
- **ale** — 사용자 재질 파일의 `*EOS_…_TITLE` 은 제목 줄을 그대로 두고 Card 1 의 EOSID 칸에 새 번호를 쓴다(전엔 제목 줄에 썼다).
- **들여 쓴 `*` 줄 나머지(58 자리)** — 리더의 미리 훑기(파트 · 섹션 ELFORM)와 인클루드 폭 바꿈 찾기, 공용 재질 번호 훑기, 재질 카드 검사기(줄
  어디든 「*MAT」 면 키워드로 보던 것), 요소 카드 걸음, assemble 의 matdb · elform · update · merge · restack 재질 카드, stabilize · modal · ale
  · iga · apply_carryover_plan · cad_solid_merge_to_deck · rebind 가 제목 · `*COMMENT` 글 속의 `  *…` 를 키워드로 읽지 않는다. 보통 덱의 산출은
  같다.
- **그 밖** — extract-parts 가 보고를 못 쓸 때 실패를 한 번만 찍는다 · 예제 `examples/matswap/two_cubes.k` 를 LS-DYNA 고정 칸으로 맞추고 결과 덱
  넷을 다시 만들었다.
- **알고 받을 것** — LS-DYNA(라이선스 만료)로 재지 못했다 — 권취 강체가 바로 선 덱을 솔버가 받는지(검증런 §1). `*` 자리 58 가운데 42 는 변이로
  못 잰 길이다(같은 한 줄 꼴 · 시험 사례가 그 길을 안 지난다 — 사용자 결정 「지금 판으로 올리기」).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `6ac0f7e` 이거나 그 뒤 |
| 판 | 운영 노드의 DynaForge `/api/health`(위 「어디서 재나」) | `revision` `6ac0f7e` · `revision_matches_binary` true · `binary_sha256` `139036f2…` |
| 바이너리 | `sha256sum build/linux/bin/KooRemapper` | `139036f27a554c87443af96af7fe3e4180ae241c0a1e135ca758aa477175aebd` |
| 권취 강체 | `output: bw` · `model_type: wound` · `tier: -1` · `mode: dent` 로 `KooRemapper battery` 뒤 `KooRemapper info bw_tier-1_phase1.k` | 「Negative Jacobian」 줄이 없다 |
| MCP 도구 | 게이트웨이 `curl -s --noproxy '*' localhost:9110/tools-map` 의 `apps` 가운데 `heax-kooremapper_mcp`(읽기 전용 — 운영에서 smoke.py 는 돌리지 않는다) | `tool_count` 120 · `reachable` true(API · MCP 를 재기동한 뒤 — 카탈로그 글이 바뀌었다) |
| 되돌리기 | §8 | 바이너리 · 코드를 `dist-20261123-080850Z`(코드 `f0cc07d` · 바이너리 `c1a274c4`)로 — 마이그레이션이 없어 DB 는 그대로 |
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261122-042305Z` 가 지워졌다(넷만 남긴다 — 11-22 낮 · 11-22 오후 · 11-23 아침 · 11-23).

## 1-15. cae00 — 11-25 반영분(낙하 ⑥ 이미지 출처 받기 · 포털 요청 1125 — R-04 배포 기다리기 · R-09 판 확정 · 레시피 자리 · HP-71)
**바이너리는 그대로다**(`139036f2…`). Drive 판 `dist-20261125-161932Z`(코드 `6a90a41`)에서 §1-14 판과 다른 파일은 `BUILD_INFO.txt` ·
`koorm-frontend-dist.tar.gz` 둘(SIF 넷 · cli.sif · 바이너리 묶음은 sha256 이 같다 — 실측) · **마이그레이션 없음** · MCP 도구 120 · 연산 65
그대로(도구 설명만 바뀌었다).
- **낙하 ⑥ 이미지 출처** — KooSlurm 귀환 매니페스트의 `images{}`(KooSlurm main `19eecafe`)를 7-1 반입이 아는 칸만 꼴을 보고 원장과 리포트
  `reservation.manifest` 에 옮긴다. get_job `external.images` — `post` 는 리포트를 만든 노드의 후처리 SIF, `manifest_node_pre` 는 매니페스트를
  쓴 노드에 그 시각 깔려 있던 전처리 SIF(배포 상태이지 전처리가 실제로 쓴 판의 증거가 아니다). system_status `observed_images`(90일 · 칸마다
  10줄). 매니페스트에 그 칸이 없으면 응답에도 칸이 없다 — KooSlurm 쪽 운영 반영은 icn401 `start_production` 뒤 제출한 잡부터다.
- **R-04 배포 기다리기** — `dist-from-drive.sh` 가 SIF · BUILD_INFO 를 임시 파일 + 이름 바꾸기로 깐다(도는 인스턴스 밑을 덮지 않는다). `stop.sh`
  · `restart-api-only.sh` · `restart.sh` · `start.sh`(postgres 재기동 둘) · `reset-db.sh` · `supervisor.sh`(postgres 무응답)는 stop 뒤
  인스턴스가 정말 사라질 때까지 기다리고, 상한(`KOORM_STOP_WAIT_S`, 기본 60초)을 넘기면 다음 걸음 없이 rc≠0 으로 끝난다. ★포털 deploy-all 의
  `_stop` 이 rc 를 삼키면 그 실패가 안 보인다(포털 몫).
- **R-09 판 확정** — 판 확정(콘솔 · MCP `set_report_revision`)의 과제 칸에 과제명 · 과제코드 · 옛 과제명 · 별칭 무엇을 넣어도 과제 하나로 풀리면
  그 과제명으로 잇는다. 못 풀거나 둘 이상이면 400 `task_unresolved` 와 후보를 내고 아무것도 바꾸지 않는다. 허브 거울에 과제가 없는 박스는 글자
  그대로. 콘솔 자리표시는 「과제명 · 과제코드」.
- **R-09 레시피 자리** — 등록 레시피를 `<데이터 뿌리>/svc/kooremapper/recipes` 에 내보낸다(리포 폴더에 쓰면 update 의 stash 가 쓸어 갔다). 기동
  때 리포 씨앗과 둘 다 읽는다. ★사람 몫 — 운영 노드에서 API 사용자가 `<데이터 뿌리>/svc/kooremapper` 에 새 폴더를 만들 수 있어야 한다(storage 와
  같은 소유자면 된다). 못 쓰면 등록은 되고 파일 내보내기만 경고(`exported: null`)다.
- **HP-71** — 예시 `.env` 의 코어 주소를 포털 경로 꼴로 · NO_PROXY 자리표시(루프백까지) · 자리표시 값에 따옴표(새 박스 대비 — 운영 `.env` 는
  손대지 않는다). 자리표시를 바꾸지 않은 코어 주소로 받으면 `bad_url` 로 멈춘다(예전엔 받기 전체가 예외로 터졌다).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `6a90a41` 이거나 그 뒤 |
| 판 | 운영 노드의 DynaForge `/api/health`(위 「어디서 재나」) | `revision` `6a90a41` · `revision_matches_binary` true · `binary_sha256` `139036f2…` |
| 시스템 상태 | MCP `system_status` | `observed_images` 칸이 있다 — 이미지 칸을 실은 7-1 반입 전에는 `{"manifest_node_pre": [], "post": []}` |
| 레시피 자리 | 운영 노드에서 API 사용자로 `test -w <데이터 뿌리>/svc/kooremapper && echo ok` | `ok` |
| MCP 도구 | 게이트웨이 `curl -s --noproxy '*' localhost:9110/tools-map` 의 `heax-kooremapper_mcp`(읽기 전용) | `tool_count` 120 · `reachable` true(API · MCP 를 재기동한 뒤 — 도구 설명이 바뀌었다) |
| 되돌리기 | §8 | 코드를 `6ac0f7e`(Drive 판 `dist-20261123-094507Z`)로 — 바이너리 · 마이그레이션이 같아 DB · 바이너리는 그대로 |
이 판을 게시하면서 Drive 의 가장 오래된 판 `dist-20261122-062855Z` 가 지워졌다(넷만 남긴다 — 11-22 오후 · 11-23 아침 · 11-23 · 11-25).

## 1-16. cae00 — 11-26 덧붙임(파이썬 · 스크립트만 — 레시피 마지막 자리 · 진행 중 올리기를 기다리는 재기동)
**새 Drive 판이 없다** — 바이너리 · SIF · 콘솔은 §1-15 그대로(`dist-20261125-161932Z`)이고 `git pull` 로만 간다. health `revision` 은 Drive 판
커밋이라 `6a90a41` 그대로다(소스 줄로 본다). 마이그레이션 없음 · MCP 도구 120 그대로.
- **레시피 마지막 자리**(`804a7acb`) — 데이터 뿌리 자리를 쓸 수 없으면 storage 아래 `.recipes` 에 내보낸다(예전 마지막 자리
  `platform/infra/data/recipes` 는 리포 묶음을 읽기 전용으로 띄우는 운영 노드에서 실패했다 — 11-26). 운영이 넣은 `KOORM_RECIPE_EXPORT_DIR`(같은
  자리)은 그대로 이기고, 빼도 같은 곳으로 간다.
- **진행 중 올리기를 기다리는 재기동**(`664a2f28`) — API 가 진행 중 올리기 수를 `/api/health` 의 `uploads_in_flight` 로 낸다. `stop.sh` ·
  `restart-api-only.sh` · `restart.sh` 는 그 수가 0 이 될 때까지 기다린 뒤 내리고, 상한을 넘기면 **내리지 않고 rc 1** 로 멈춘다(「진행 중 올리기
  N건이 …초 안에 끝나지 않았다」). 헬스가 안 닿으면(API 가 죽었다) 기다리지 않는다. 앞단 프록시가 본문을 다 받은 뒤 넘기는 전송 구간은 API 가
  모른다.
  - 환경값 — `KOORM_UPLOAD_DRAIN_S`(초, 기본 300 · 0 = 기다리지 않음) · `KOORM_STOP_WAIT_S`(초, 기본 60 — stop 뒤 인스턴스가 사라지기를 기다림).
    둘 다 비워 두면 기본값이다. `.env` 에 적으면 명령줄 값을 덮는다.
  - 멈췄을 때 — 올리기가 끝난 뒤 같은 명령을 다시 한다. 끊어도 되면 `KOORM_UPLOAD_DRAIN_S=0 bash
    platform/infra/scripts/restart-api-only.sh`(`.env` 에 그 값을 적어 두지 않았을 때).
  - ★포털 deploy-all 의 `_stop` 이 rc 를 삼키면 이 멈춤이 안 보인다(포털 몫 — R-04 와 같다).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `664a2f2` 이거나 그 뒤 |
| 판 | 운영 노드의 DynaForge `/api/health`(위 「어디서 재나」) | `revision` `6a90a41` 그대로 · `matches` true · `uploads_in_flight` 칸이 있다(API 를 재기동한 뒤 — 평소 0) |
| 레시피 자리 | `KOORM_RECIPE_EXPORT_DIR` 을 빼고 재기동했다면 등록 하나 뒤 storage 아래 `.recipes/<이름>/` | `recipe.py` · `recipe.json` 이 있다(뺄 필요는 없다 — 같은 자리) |
| 되돌리기 | §8 | 코드를 `6a90a41` 로 — Drive · DB 는 그대로 |

## 1-17. cae00 — 11-26 ST-25-KR(maps_to 공통 블록 새 판 — StepForge ST-25 와 같은 날)
**새 Drive 판이 없다** — 정의 파일 · 파이썬만이라 `git pull` 로 간다(바이너리 · SIF · 콘솔은 §1-15 그대로, health `revision` 은 `6a90a41`
그대로). 마이그레이션 없음 · MCP 도구 120 그대로. StepForge 도 같은 날 같은 바이트로 착지했다(그쪽 main `b7e937b6`).
- `platform/core/ontology/dynaforge-core.json` 의 `maps_to` 를 StepForge 가 보낸 블록 그대로로 — 출발 끝에 `cad_part`(StepForge 의 CAD 파트),
  맞은 칸에 `label_en`, 설명 · 도움말. 블록 지문(키 정렬 압축 sha256) `8cc5a705b0a0536f283fb1e2c023ebfd489523c5aa097cda5997148b437dc171` — 두
  앱이 같다. DynaForge 의 선 · 다리는 그대로다(우리는 `cae_part` 선만 짓는다).
- ★허브 사람 몫 — (1) 허브 관리자가 새 정의를 가져올 때 두 앱의 블록이 같은 바이트여야 한다(한 글자라도 다르면 허브가 둘째 것을 거절한다). (2)
  **허브 관리자는 `part_role` · `cae_part` · `cad_part` · `part` 를 다 코어 공개로** — SP 코어 API 는 적힌 끝 타입이 하나라도 코어 공개가 아니면
  그 관계를 안 연다(`_open_end`). 아니면 `maps_to` 가 두 앱 모두 통째로 닫힌다.

| 확인 | 명령 | 기대값 |
|---|---|---|
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `4f8f73e` 이거나 그 뒤 |
| 블록 지문 | `python3 -c "import json,hashlib;d=json.load(open('platform/core/ontology/dynaforge-core.json'));b=[r for r in d['relation_types'] if r['slug']=='maps_to'][0];print(hashlib.sha256(json.dumps(b,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())"` | `8cc5a705…c171`(StepForge 의 같은 블록과 같다) |
| 허브 | 허브 관리 화면에서 네 타입의 코어 공개 | `part_role` · `cae_part` · `cad_part` · `part` 모두 공개 |

## 2. cae00 — 후처리 예약(7-1) 설정
`platform/.env`(KooRemapper)에 둘. **값은 화면 · 로그 · 채팅에 붙이지 않는다.**
```
KOORM_STCX_BACKEND_URL=<cae00 에서 닿는 stcx 대시보드 주소 — 덱 업로드에 쓰는 것과 같은 값>
KOORM_KOOSLURM_SSO_SECRET=<icn401 backend_5010/.env 의 HEAX_GATEWAY_SECRET 과 같은 값>
```
선택 — `KOORM_POSTPROCESS_WAIT_DAYS`(기본 7) · `KOORM_KOOSLURM_TIMEOUT_SEC`(기본 30). 넣은 뒤 재기동(도는 잡 0 확인 → `restart-api-only.sh` — 11-26 부터 진행 중 올리기가 끝나기도 스스로 기다린다(§1-16), 또는 다음 `update-all` 이 .env 지문으로 재기동).

(11-15 덧붙임) 칸과 위임 창구만 먼저 보려면 `python3 platform/infra/scripts/check-postprocess.py`(§1-5) — 칸 이름 · 있음/비었음 · HTTP 상태만 나오고 값은 나오지 않는다. `--email <주소>` 를 주면 그 사람 명의로 토큰을 실제로 받아 본다(토큰은 출력하지 않는다).

**확인 — 없는 잡으로 예약해 본다**(운영 잡을 건드리지 않는다). 콘솔에서 세션 하나 → 오퍼레이션 `postprocess` → `job_key=stcx:0`, `sim_type=fullangle_drop` → 실행. 또는 `platform/mcp_server/venv/bin/python platform/mcp_server/allops_smoke.py` 의 postprocess 줄.
| 잡의 오류 문구 | 뜻 |
|---|---|
| 「구성 안 됨 — KOORM_… 이(가) 비었다」 | 설정이 아직 안 들어갔다(또는 재기동 전) |
| 「위임 창구가 잡 소유자의 토큰을 내주지 않았다(sso_401)」 | 비밀이 icn401 과 다르다 |
| 「…(sso_404)」 | icn401 에 비밀이 아직 없다(§3-3) — 창구가 닫혀 있다 |
| 「…(sso_400)」 | 이메일이 사용자 이름 규칙에 안 맞는다(`@` 앞이 `[a-z0-9._-]` 1~32 · admin · root · anonymous 거절), 또는 KooSlurm 의 클라이언트 허용 목록에 `dynaforge` 가 없다(`X-Heax-Client` — 11-15 덧붙임 · 두 까닭은 `check-postprocess.py --email` 이 보이는 까닭 글로 가른다) |
| 1~2분 뒤 「클러스터가 이 잡을 모른다(`/info` 404 …)」 | **정상** — 설정 · 위임 · 대시보드 REST 가 다 닿았다(잡 0 은 없다) |

## 3. icn401 — KooSlurm 반영(사람)
KooSlurm `docs/sso_enable_20261029/icn401_apply_check.md` 그대로. 요점 —
1. 반영 `git pull && sudo ./dashboard/start_production.sh`(로그를 /tmp 에 tee). 결과 귀환(`7c280000` 까지) · 위임 창구(`3f72f4c6`) · 문서(`46c647e4`)가 한 번에 들어간다.
2. 확인 10개 — 코드 판 · 템플릿 동기화 줄 · 드라이버 템플릿 `grep -c write_return_manifest` = 3 · LSTC 플레이스홀더 0 · 「→ SSO=false → 정본 conf: hpc-portal.conf」 · frontend_3010 재빌드 · 백엔드 active · C 라우트(새 코드면 400 · error_code 9001) · 다운로드 티켓 · 위임 창구 비밀 전 404.
3. `HEAX_GATEWAY_SECRET` 넣기(backend_5010/.env · chmod 600 · 재시작) → `curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Heax-Gateway-Secret: <비밀>" https://<대시보드>/api/auth/sso/verify` → **204**(틀리면 401). 같은 값을 cae00 §2 에.

## 4. 운영 첫 실제 전각도 잡 뒤 — 끝까지 한 번
1. **B(드라이버 매니페스트)** — KooSlurm 문서 §4: `sacct` · 드라이버 로그 끝 「=== 귀환 매니페스트 ===」 · `<RESULT_DIR>/output/return_manifest.json`. 정상이면 `COMPLETED 0:0` · `ok: true` · 리포트 sha256 이 파일과 같다. 없으면 `FAILED 3:0` · `reason` · `log_tail` — 그 줄을 KooSlurm 에 넘긴다(없으면 C 로 다시 거는 curl 이 문서에 있다).
2. **DynaForge 예약** — 그 잡을 제출한 절차(포털 R2a, `9ce09b6`)가 걸어 둔 `postprocess` 잡이 `succeeded` 가 되고 `resolved_cmd.report_ids` 에 리포트 id 가 생긴다. 리포트가 예약자 명의로 들어왔는지(제출 때 과제 메타 — `project` · `dev_rev` · `variation` · `doe` — 를 채웠으면 그 값도), 리포트 상세의 `external_job_key` = `stcx:<잡 id>` 인지 본다.
3. 실패면 잡의 `error_summary` 가 매니페스트 까닭을 그대로 싣는다 — 그 문구를 DynaForge 에 넘긴다.

## 5. stcx viz 노드 — 읽기만(SceneForge · S1)
GPU 는 노드마다 챗 LLM 과 함께 쓴다 — **읽기만**(MIG 전환 · GPU 재설정 · 설치 · 렌더 없음). 명령의 정본은 SceneForge `scripts/stcx_viz_readcheck.sh`(f46e835) — 결과를 텍스트 파일 하나로 모은다. 그 파일을 SceneForge 세션에 넘긴다.
```
bash stcx_viz_readcheck.sh                                    # 1단계 — 로그인 노드만, 노드에 잡을 걸지 않는다
bash stcx_viz_readcheck.sh <viz 파티션> <노드> <S1 결과 폴더>    # 2단계 — 고른 노드에 CPU 1 · 512M · 5분 · GPU 요청 없는 잡 하나
```
- 2단계 앞뒤로 cae00 에서 `~/stcx-llm/llmctl.sh status`(챗 LLM 이 그대로인지).
- **<S1 결과 폴더>** — S1 은 아직 나오지 않았다(KooD3plotReader 추출기 계약 대기). 둘 자리는 정해졌다 — 각도 run 폴더의 `Output/s1.h5`(KooD3plotReader 계약 초안 2, 10-30 — `<RESULT_DIR>/output` 아래). 추출기는 아직 운영 이미지에 없다(libhdf5 를 넣은 다음 판 대기). 그러니 지금은 운영 전각도 잡 하나의 `<RESULT_DIR>/output`(sphere_report.html 이 있는 곳 — 귀환 매니페스트의 `job.result_dir`)로 마운트를 본다.
- 스크립트를 못 옮기면 한 줄씩 — SceneForge `docs/requests/dynaforge-sceneforge-tasks-reply-2026-10-29.md` 「cae00 명령」 절(sinfo · squeue · 챗 LLM sbatch gres · scontrol config · `nvidia-smi` · `ldconfig -p` 로 GL/EGL/NVENC/Vulkan 라이브러리 · `apptainer --version` · `ls -la <폴더>`).
- 제어면 준비로 둘 더 — SceneForge 를 돌릴 cae00 계정에서 `ssh -o BatchMode=yes stcx true && echo ok`(sbatch 낼 길이 비밀번호 없이 열리나, C-13) · `ssh stcx df -h /data2`(렌더 작업자 SIF · 결과 자리 여유 — 자리는 노드 관리자와 정한다).
- GPU 를 쓰는 시험(T1 · T2)은 SceneForge `docs/research/stcx-gpu-test-plan-2026-10-29.md` — 읽기 점검 결과가 나온 뒤 챗 LLM 운영과 시간을 잡고.

## 5-1. stcx — 후처리 이미지 Post v51(운영 측 설치)
**v51**(KooD3plotReader `226eca7`, 11-08)을 깐다 — v50(운영에 넘길 판으로 정한 판, KooD3plotReader 사용자 결정 11-08)의 알려진 한계를 푼 판이다.
v43 · v47 · v50 을 이미 깔았으면 v51 로 바꾸고, 아직이면 v43 ~ v50 을 건너뛴다. 앞 판의 고침이 다 들어 있다(`eccde7f` · `f8f0e22` · `2780f20` 이 `226eca7` 의
조상 — 확인).
- 든 것 — v47 까지의 것과 v48 ~ v51 의 것. v43 의 것(단면 영상 **응력 0 프레임** 고침(K-1 — 운영 영상 24개 중 7개가 오류 없이 응력 0, v42 와 같음) · S1 경량 추출(계약 초안 4) ·
  리포트 곁의 **해석 온톨로지 꾸러미**(`<출력>/<kind>_report.ontology.json` — 리포트 도구가 스스로 쓴다) · 전각도 흐름 병렬(`--parallel-runs`))에 더해
  - 꾸러미 어휘가 **0.5** 다(`f8f0e22`). 핫스팟을 켠 실행은 기본 기준이 von_mises + plastic_strain 이고(`f218f49`), 소성 핫스팟은
    `plastic_strain_mean/max` 칸에 실린다.
  - 셸 · 두꺼운 셸 파트도 응력 · 변형률 값이 생긴다(적분점 층 극값, `cba5cf1`) — 꾸러미의 `cae_part_response` 에도 실린다.
  - 꾸러미 머리 **warnings**(`07d3e96`) — 캠페인 폴더(test_dir) · 덱 · DropSet 을 못 읽으면 사유를 싣는다(v43 은 같은 경우 경고 없이 덜 찬 꾸러미를 냈다).
  - 리포트 그림 꾸러미(최대 순간 스냅샷 · 차트 — HTML 「리포트 그림」 탭) · 캠페인 그림 · 영상 바닥 숨김 기본 · 분석기 메모리 안전장치(전 상태를 읽기
    전에 어림해 넘으면 숫자와 함께 멈춘다).
  - (v48 ~ v50) 소성역 요약(n_yield · vol_yield)이 ε_p ≤ 1e-6 잡음 요소를 뺀다 — 결과의 `yield_eps_threshold` 는 실제로 쓴 값(max(설정, 1e-6),
    `9db7f98`) · 리포트 그림의 파트 제목이 사용자 파트 ID 에 붙는다(`d0bc3fb`) · 부하가 높을 때 deep 이 VTK abort(rc 134)로 통째로 죽던 일이
    없어졌다(그림용 Xvfb `-noreset`, `7bc1f78`) · 파트별 LS-PrePost 단면 2차 패스가 늘 거절되던 결함을 고쳤다(`19e00e2` — v42 ~ v49 산출에는 파트별
    영상이 없고 갤러리에 「파트별 렌더 패스 실패」 가 남아 있다) · 파트별 단면 영상은 이름에 공통 키워드(기본 BGA, 대소문자 무시)가 든 파트만 찍는다
    (`6d6838e` — 모든 파트는 `--section-view-per-part`, 키워드는 `--section-view-part-keywords` 또는 YAML `section_view.part_keywords`) ·
    LS-PrePost 용 Xvfb 를 `-displayfd` 로 띄워 같은 노드의 동시 실행이 화면을 나눠 쓰지 않는다(`63a9594`). 꾸러미 어휘는 0.5 그대로(v47 과 같은 바이트).
  - (v51) 파트별 LS-PrePost 단면 폴더 이름이 덱 `*PART` 제목에서 지어진다(`part_1_Part1` → `part_1_PCB_FR4` — 키워드가 맞추는 이름과 같은 출처,
    영문 · 숫자 · `. _ -` 만 남기고 40자에서 자르며 남는 글자가 없거나 덱이 없으면 `Part<id>`) · 키워드에 맞는 파트가 없으면 안내에 그 런의 파트 이름이
    붙는다(앞 8개 · 외 N개, `7076b19`). 꾸러미 · 어휘 · 분석 수치는 v50 과 같다.
- **v52 가 나왔다(11-21 알림 — KooD3plotReader `d2f0d6b`)** — 적분점 응력이 있는 보 파트(BEAMIP > 0)에 응력 값이
  실린다(`cae_part.worst_von_mises` · `cae_part_response.peak_von_mises` 등). 어휘 0.5 · 꾸러미 꼴은 그대로다. DynaForge 검사(구운 api.sif 안
  `onto_package.check`)에 v51 · v52 의 deep 꾸러미를 넣어 둘 다 통과를 봤다(행 5 · 선 1 · 경고 0) — 받는 쪽은 고칠 것이 없다. 운영에 v51 과 v52
  가운데 어느 판을 깔지는 KooD3plotReader 쪽이 정한다 — 이 절의 파일 · 지문은 그 결정이 오기 전까지 v51 것이다.
- 파일 — Drive `ApptainerImages:SmartTwinPreprocessor/SmartTwinPostprocessor_20261108_v51.tar.gz`(575,361,435 바이트), sha256 헤드리스
  `32997e9b6efb1fdc36737a1f9706a3156bee0a7256a6fe9382135495182ada24`(1,156,505,600 바이트) · GUI `a3f06a56…`. dev 헤드 `/opt/apptainers` ·
  `/data/SmartTwinPostprocessor` 가 이 판이다(지문 확인 — dev 노드 node001 · 002 는 VM 이 꺼져 있어 아직 v47). 이 박스에서 stcx 로 밀어 넣는 절차는
  없고 **설치는 운영 측 몫**이다. 리포트 잡이 도는 노드 쪽 사본까지 같은 판으로 둔다
  (헤드와 노드의 판이 다르면 리포트 셸이 경고한다).
- 설치 뒤 — `apptainer exec <설치한 SmartTwinPostprocessor.sif> head -3 /opt/kood3plot/VERSION` → `Version: 226eca7`.
- 순서 — 이 판의 꾸러미는 어휘 0.5 다. cae00 DynaForge 가 `32cc364` 이상이어야 받는다(§0 의 1번 update-all 을 먼저 하거나 같은 때에 — `752fa2b` 판이
  이미 그 뒤다). 늦으면 그 사이 반입된 리포트는 꾸러미 없이 들어오고 잡 응답의 `external.ontology.state` 가 `failed`(「받아들이지 않은 어휘 판이다」 — 잡
  경고 한 줄)다. 리포트는 정상이고, 꾸러미는 나중에 리포트 화면 「꾸러미 붙이기」로 붙인다. 노드 쪽 사본이 아직 옛 판(v46 이하)이면 그 잡의 꾸러미는
  어휘 0.4 로 오고 그대로 받는다(v47 ~ v49 이면 0.5 — 같다).
- 운영에서 볼 것 — 전각도 잡 하나 뒤 (1) 단면 영상 마지막 프레임 범례가 `max = 0, at node# 0` 이 아니다 (2) 결과 폴더에
  `<출력>/sphere_report.ontology.json` 이 있다 (3) icn401 반영 뒤 제출한 잡이면 귀환 매니페스트의 `reports[].ontology.present` 가 true 이고,
  그 잡을 받은 DynaForge 후처리 예약 잡 응답의 `external.ontology.state` 가 `loaded` (4) 그 리포트 화면의 해석 온톨로지 칸에 노란 경고 줄이 없다 — 있으면
  꾸러미가 캠페인 폴더 · 덱을 못 읽고 지어진 것이다(접촉 양쪽 선 등이 빠진다) (5) 핫스팟을 켠 결과의 `hotspot.criteria` 가 9개 · `yield_eps_threshold`
  가 1e-6 이상 (6) deep 리포트에 그림이 있다(부하가 높아도 VTK abort 로 빠지지 않는다) (7) 파트별 단면 영상은 이름에 BGA 가 든 파트만 — 없으면
  갤러리에 「[설정] 파트별 단면: 이름에 BGA 가 든 파트가 없어 만들지 않았다(파트 이름: …)」 가 뜬다(개관 영상은 그대로) · 파트별 영상 폴더 이름이
  `part_<id>_<덱 파트 제목>` 이다.
- 확인한 것 — 배포된 v50 SIF 안에서(`python3 -s`, 캠페인 폴더 읽기 전용으로 묶음) v14 리포트로 꾸러미를 만들어 DynaForge 검사(구운 api.sif 안)에
  넣었다 — 어휘 0.5 · producer `226eca7` · 행 94 · 선 115 · 런 20/20 · 경고 0(v47 · v49 · v50 과 같은 수). 아래는 v47 판으로 잰 기록이다 — v47 도 같은 수였다. 캠페인 폴더를 안 묶으면 행 89 · 선 64 와 함께 머리 경고
  「test_dir … 를 찾지 못했다 — 덱 · DropSet · S1 정보(재질 · 접촉 · 초기 속도 · 낙하 높이) 없이 지었다」 가 검사 결과로 넘어와 리포트 화면에 보인다.
  이 판으로 만든 셸 파우치(에어백) 덱 deep 꾸러미도 같은 검사(api.sif 안)를 통과했다 — 행 144 · 선 1 · 런 1/1 · 경고 0. 핫스팟 79(von_mises 56 ·
  plastic_strain 23 — 소성 핫스팟은 `plastic_strain_mean/max` 만 차고 `stress_*` 는 비었다), 파트 응답 60 이 모두 응력 값을 가진다(셸 포함).
- 알려진 한계(KooD3plotReader) — 덱 파일 없이 도는 런은 키워드가 d3plot 제목과 맞춰지지만 폴더 이름은 `Part<id>` 다(드물어 기록만 — v50 의 폴더 이름
  한계는 v51 에서 풀렸다).
- v42 의 고침 확인 기록(dev 헤드, KooRemapper `7818cbc`)은 그대로다 — 결함을 매번 일으키는 설정(LS-PrePost 예산 20M)을 심어도 정상이고,
  옛 판(Post v41 `282630b`)은 같은 설정에서 0 을 내며 rc 0 으로 끝났다.

## 6. 게이트웨이 — 게이트웨이를 거친 stcx 제출이 지금 되는가(선택)
```
tail -3000 ~/Projects/HWAXMcpGateway/audit.jsonl | grep -a '"backend": "smart-twin' | tail -5
```
`ok` · `error` 칸만 본다. 게이트웨이는 smart-twin 백엔드에 Authorization 을 싣지 않아(사람별 위임은 미룸 — 사용자 「나로 일단」), smarttwin_mcp 가 서버 env `STMC_CLUSTER_TOKEN` 으로 넘어간다. 그것도 없으면 거부다.

## 7. SSO 켜기 — 이번엔 하지 않는다(조건)
KooSlurm `docs/sso_enable_20261029/sso_enable_procedure.md`. 켜기 전에 설 것 —
- **IdP 주소** — 저장소의 운영 YAML 사본은 `sso.saml.idp.sso_url` 이 비었다. 비었으면 켜는 순간 아무도 로그인 못 한다(icn401 실제 YAML 확인).
- **SSO 꺼진 동안 발급한 kst_ 는 전부 admin 으로 저장됐다** — 켠 뒤 그대로 두면 관리자 토큰이다. 절차서 §2 대로 지우고 다시 발급(`~/.claude.json` 의 smarttwin kst_ 포함). **smarttwin-mcp 유닛 env 의 `STMC_CLUSTER_TOKEN` 도** — 그대로 두면 게이트웨이 경유 제출이 전부 관리자 권한으로 간다. 다시 발급한 토큰의 주인이 그 뒤 제출 · 업로드의 명의가 된다(KooSlurm `a4734e7a`).
- **DynaForge 덱 업로드의 신원 = 제출 신원**(절차서 §0 조건 5) — 게이트웨이 경유 단일 신원이면 업로드도 그 토큰(`STMC_CLUSTER_TOKEN`), 사람별 위임이면 업로드도 위임 창구 토큰. 어긋나면 켜는 순간 거절된다. 어느 쪽인지는 켤 때 사용자 결정이고, DynaForge 업로더는 그 결정에 맞춰 짓는다(지금은 보류).
- 걸린 예약이 없을 때 켠다 — 켜는 순간 신원이 admin → 실제 사용자로 바뀌어 켜기 전 예약은 403 으로 닫힌다.

## 8. 되돌리기
- **DynaForge** — 아티팩트: `rclone copy ApptainerImages:KooRemapper/dist/dist-<이전 판>/ ApptainerImages:KooRemapper/dist/latest/`(이번 판 바로 앞은 `dist-20261123-094507Z` — 코드 `6ac0f7e` · 바이너리 `139036f2` · Drive 에는 11-22 오후 · 11-23 아침 · 11-23 · 11-25 넷이 있다) 뒤 `update-all`(또는 `dist-from-drive.sh --restart`). 코드: 이전 커밋으로. 마이그레이션 0015 · 0016 · 0017 은 null 허용 칸 · 유일 제약, 0018 은 새 표 셋과 null 허용 칸 둘, 0019 는 트리거, 0020 은 null 허용 칸 셋(FK 둘 · JSONB 하나), 0021 은 새 표 둘(있던 표는 그대로 · 리포트를 가리키는 FK 는 SET NULL), 0022 는 캠페인 · 런 표의 null 허용 칸 다섯, 0023 은 같은 표의 null 허용 칸 둘, 0024 는 새 표 둘이라 옛 코드가 그대로 돈다 — 되돌리지 않아도 된다(0019 가 지운 「지운 리포트의 선」 은 되살리지 않는다 — 리포트가 없다). 11-15 판은 마이그레이션이 없다 — 새 코드가 적은 다리 선 · 끊은 기록을 옛 코드로 읽는 것은 재지 않았다. 11-17 판도 마이그레이션이 없고 새 칸은 응답에만 있다(DB 에 남는 것이 없다) — 되돌리면 겹친 덱을 쓰는 op 이 다시 그 요소가 빠진 덱을 낸다. 11-21 판을 되돌리면 캠페인 길(REST 셋 · MCP 셋)이 없어지고(표 둘과 그 행은 남는다 — 옛 코드를 0021 DB 에 돌려 재지는 않았다 · 표 꼴로 본 것이다) 이번에 고친 조용한 틀림(펼치기의 바꿔 끼운 요소 · 칸이 붙은 덱 · BOM 인클루드에서 지워진 절점 — §1-7)이 돌아온다. 11-21 밤 판을 되돌리면 마이그레이션 없이 바이너리만 바뀐다 — 덱 · 번들 BOM 이 다시 산출에 실리고 matswap BOM 번들 · ale 재료 파일 · 격자 첫 행의 조용한 틀림과 strain · squeeze 의 빈 산출(§1-8)이 돌아온다. 11-22 판을 되돌리면 캠페인 출처 · 건강 판정 길(REST 넷 · MCP 넷)이 없어지고(0022 칸과 값은 남는다 — 옛 코드는 그 칸을 읽지 않는다 · 표 꼴로 본 것이다) 동시 올리기의 500 이 돌아오며, 바이너리는 LONG=Y 덱에 10 칸 카드 · 넘친 음수 번호 · extract_surface 의 정의 안 된 파트로 돌아간다(§1-9 — extract_surface 의 두께 필수 계약도 풀린다). 11-22 낮 판을 되돌리면 추출 완전성 · 삭제 허가 길(REST 셋 · MCP 셋)과 피크 표지가 없어지고(0023 칸과 값은 남는다 — 옛 코드는 그 칸을 읽지 않는다 · 표 꼴로 본 것이다), 바이너리는 쌓인 카드 묶음을 블록째 지우거나 그 번호를 다시 내는 판 · 첫 정의만 보는 `--strict` 겹침으로 돌아간다(§1-10). 11-22 저녁 반영(파이썬만)을 되돌리면 캠페인 분석 · 핫스팟 · 세션 판 길이 없어진다(0025 · 0026 의 칸과 표는 남는다 — 옛 코드는 읽지 않는다). 11-25 판(`dist-20261125-161932Z`)을 되돌리면 마이그레이션 · 바이너리 없이 파이썬 · 스크립트 · 콘솔만 바뀐다 — ⑥ 이미지 칸이 응답에서 빠지고(원장에 남은 칸은 옛 코드가 읽지 않는다), 판 확정이 다시 글자 그대로 잇고, 레시피를 다시 리포 폴더에 내보내며, stop 이 다시 기다리지 않는다(§1-15). 11-23 판(7판 · `dist-20261123-094507Z`)을 되돌리면 마이그레이션 없이 바이너리만 바뀐다 — 권취 바닥판 · PCM 이 다시 뒤집히고 tied Card 3 정수꼴 · 빈 탭 PART · ale EOS 제목 줄 · 들여 쓴 `*` 줄 나머지(§1-14)가 예전으로 돌아간다. 11-23 아침 판(6판)을 되돌리면 마이그레이션 없이 바이너리만 바뀐다 — phase_modes swell 판의 고정구 · 맨 위 swell 의 dent 판 · 권취 탭 · PCM 차례 · contact.depth · 나선 판 섹션 33 · 들여 쓴 `*` 줄(§1-13)이 예전으로 돌아간다. 11-22 오후 판을 되돌리면 보고서용 묶음 길(REST 넷 · MCP 셋)이 없어지고(0024 표와 행은 남는다 — 옛 코드는 그 표를 읽지 않는다), 바이너리는 없는 재질 · 세트를 가리키는 battery 덱 · 크기를 보지 않는 인클루드 펼치기 · 자기를 끌어오는 산출로 돌아간다(§1-11).
- **KooSlurm** — 그쪽 문서의 되돌리기 절.

## 9. 남은 사람 결정(참고)
SP 허브 주소 · `core:read` 토큰(받기를 켜는 조건 — 넣으면 시간마다 받고 7일마다 처음부터) · CAD 묶음을 리포트에 붙일 주체(포털 절차의 한 단계 · 사용자 MCP — MCP `attach_cad` 는 MCP 컨테이너가 읽는 경로만 되고 StepForge 산출 자리는 안 보인다(dev 실측), REST 는 어디서든) · 옛 결과 리포트 셸 다시 만들기 `--regen-sh`(pyKooCAE — 옛 부분충격 결과는 이것 없이 7-1 로 못 받는다) · SSO 켤 시각(§7) · 렌더 결과를 붙이는 명의(소유자만 / 같은 소속) · 보고 영상 「접촉 앞」 해석 밖 구간 · 과제 키 검증(7-4) · pyKooCAE F 예제.
