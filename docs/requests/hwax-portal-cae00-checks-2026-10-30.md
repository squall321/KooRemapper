# cae00 · icn401 · stcx 점검 — 2026-10-30 · 10-31 반영분(DynaForge 후처리 반입 · 낙하 트윈 P1 · P2 · P3 받는 쪽 · SP 받는 쪽 전부 · MCP 인자 설명 · 시간 한도 · 해석 온톨로지)

**누가 · 어디서** 사람이 cae00(실사용 서버)·icn401(KooSlurm 운영)·stcx 에서 돌리는 확인이다. 포털 `docs/cae00-deploy-guide.md` 의 「2026-10-30 반영분」 절로 옮긴다(포털 세션).
**정본** DynaForge 쪽 결정 · 계약은 KooRemapper `platform/docs/REQUEST-postprocess-operation.md` §10, `docs/01-plan/features/{postprocess-reservation-1028,sphere-risk-map-1029}.plan.md`, 총괄 `drop-twin-1028.checklist.md`. KooSlurm 쪽은 KooSlurm `docs/sso_enable_20261029/{icn401_apply_check,sso_enable_procedure}.md`(origin `46c647e4`).

## 0. 순서 — 한 줄씩
1. **cae00** — `git pull && update-all`(kooremapper 가 Drive 판 `dist-20261108-234149Z` 를 받는다) → §1 · §1-1 · §1-2 · §1-3 · §1-4 확인.
2. **icn401** — `git pull && sudo ./dashboard/start_production.sh` → §3 확인(KooSlurm 문서 §2).
3. **비밀 하나를 두 곳에** — icn401 `HEAX_GATEWAY_SECRET`(backend_5010/.env) = cae00 `KOORM_KOOSLURM_SSO_SECRET`(KooRemapper platform/.env) → §2 · §3-3.
4. **cae00** — `KOORM_STCX_BACKEND_URL` 확인 → DynaForge 재기동 → §2 확인.
5. 운영의 **첫 실제 전각도 잡** 뒤 → §4.
6. (사람 · 읽기만) stcx viz 노드 · 게이트웨이 감사 → §5 · §6.
7. (운영 측) stcx 후처리 이미지 **Post v51**(`226eca7`) 설치 — 단면 영상 응력 0 프레임 고침(v42 와 같음) · S1 추출 · 해석 온톨로지 꾸러미(어휘 0.5) ·
   셸 파트 응력 → §5-1. 꾸러미가 어휘 0.5 라 cae00 의 1번(update-all)을 먼저 하거나 같은 때에 한다.
SSO 켜기는 **이번에 하지 않는다**(§7 — 조건이 안 섰다).

## 1. cae00 — DynaForge 받기(update-all 뒤)
10-30 판에 든 것 — 반입 속도(raw_decode `288afb7` · sphere 블록 분리 `c7970dc`) · 후처리 예약 `postprocess`(`4ff9a79` → 위임 창구 `e62f601` · rc 3 경고) · 구면 위험도 맵(3D · 허용비 · 상위 N, `f366816`) · 렌더 결과 반입 C-11(`85ba2f0`) · postprocess 의 비운 선택 칸 null 을 없는 칸으로(`07679d7`) · `dev_rev` 를 예약 때 반입 규칙으로(`3574342`) · **변형 뷰어 1단계** — 리포트에 StepForge fe_cad 묶음 붙이기(REST `POST /reports/{id}/cad` · MCP `attach_cad`, `aa63e2a`) · 맵에서 각도를 고르면 「형상 보기」(`d37fcbb`). 그 판의 **마이그레이션 셋**(0015 · 0016 · 0017 — 모두 null 허용 칸 · 유일 제약, 옛 코드에 영향 없음) — 그 뒤 0018 · 0019 · 0020 이 더해져
지금은 0015 ~ 0020 여섯이다(아래 표 · §8). 바이너리는 그 판까지 그대로(`8c7c4f87`)였고 **11-07 판에서 바뀌었고**(`15d013ec` — §1-3) **11-08 판에서 또 바뀌었다**(`c5f74c18` — §1-4).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `"status":"ok"` · `revision` 이 이번 게시 BUILD_INFO 의 커밋(`e6407dc`) · `revision_matches_binary` true |
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `e6407dc` 이거나 그 뒤 — 위 `revision` 은 Drive 판의 커밋이라 그 뒤에 파이썬만 바뀐 커밋은 여기서만 보인다. 앞이면 null 을 보내는 손님(MCP 직접 호출 — Claude 등)이 비운 선택 칸에서 422 를 받고(포털 R2a 는 칸째 빼고 보내 영향 없음), 틀린 `dev_rev` 가 예약은 되고 잡이 끝난 뒤 반입에서야 실패한다 |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 「Running upgrade」 줄 없이 「✓ migrations applied」 = 이미 0020 까지 올라 있다(빠졌으면 이 명령이 그 자리에서 올린다 — 0015 · 0016 · 0017 · 0018 · 0019 · 0020). ★0019 는 **지운 리포트의 개정 선**을 한 번 지운다 — 개정 비교의 「리포트」 수가 지운 리포트만큼 줄 수 있다(정상, 사용자 결정 10-30) |
| MCP 도구 | 게이트웨이 tools/list 에서 kooremapper 도구 수, 또는 `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 89개(`attach_render` · `attach_cad` · `ontology_types` · `ontology_find` · `ontology_object` · `attach_cae_package` · `report_cae` · `find_cae_parts` · `find_cae_load_paths` 가 새로 있다) · `MCP SMOKE: PASS` |
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
리포트만 반입되고 잡 `external_ref.ontology.state` 가 `no_field`(옛 작성기) · `absent`(꾸러미 없음)다 — 둘 다 정상이고 경고가 아니다.
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
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `revision` `e6407dc` · `revision_matches_binary` true |
| 바이너리 | `sha256sum platform/backend/bin/KooRemapper` | `c5f74c18…` |
| 연산 수 | 시스템 상태의 `operations` | 65(그대로) |
| 스모크(dev 실측 11-08) | `mcp_server/deckops_smoke.py` · `mcp_server/allops_smoke.py` | 29/29 · 64/64(외부 잡 하나 건너뜀) |

클러스터 전처리 이미지(SmartTwinPreprocessor.sif)의 스테이징 사본도 `c5f74c18` 로 바꿨다(`scripts/stage-to-appt313.sh`) — 구워야 클러스터의 연산이
이번 고침을 쓴다. 굽기는 sudo 가 드는 사람 몫이다(`docs/infra/appt313-bake-hook.md`). 다음 판으로 미룬 기존 결함 목록은 KooRemapper
`docs/01-plan/features/seatbelt-aux-walkers-1107.plan.md` 「다음 판으로 미룬 것」.

## 2. cae00 — 후처리 예약(7-1) 설정
`platform/.env`(KooRemapper)에 둘. **값은 화면 · 로그 · 채팅에 붙이지 않는다.**
```
KOORM_STCX_BACKEND_URL=<cae00 에서 닿는 stcx 대시보드 주소 — 덱 업로드에 쓰는 것과 같은 값>
KOORM_KOOSLURM_SSO_SECRET=<icn401 backend_5010/.env 의 HEAX_GATEWAY_SECRET 과 같은 값>
```
선택 — `KOORM_POSTPROCESS_WAIT_DAYS`(기본 7) · `KOORM_KOOSLURM_TIMEOUT_SEC`(기본 30). 넣은 뒤 재기동(도는 잡 0 확인 → `restart-api-only.sh`, 또는 다음 `update-all` 이 .env 지문으로 재기동).

**확인 — 없는 잡으로 예약해 본다**(운영 잡을 건드리지 않는다). 콘솔에서 세션 하나 → 오퍼레이션 `postprocess` → `job_key=stcx:0`, `sim_type=fullangle_drop` → 실행. 또는 `platform/mcp_server/venv/bin/python platform/mcp_server/allops_smoke.py` 의 postprocess 줄.
| 잡의 오류 문구 | 뜻 |
|---|---|
| 「구성 안 됨 — KOORM_… 이(가) 비었다」 | 설정이 아직 안 들어갔다(또는 재기동 전) |
| 「위임 창구가 잡 소유자의 토큰을 내주지 않았다(sso_401)」 | 비밀이 icn401 과 다르다 |
| 「…(sso_404)」 | icn401 에 비밀이 아직 없다(§3-3) — 창구가 닫혀 있다 |
| 「…(sso_400)」 | 이메일이 사용자 이름 규칙에 안 맞는다(`@` 앞이 `[a-z0-9._-]` 1~32 · admin · root · anonymous 거절) |
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
- 파일 — Drive `ApptainerImages:SmartTwinPreprocessor/SmartTwinPostprocessor_20261108_v51.tar.gz`(575,361,435 바이트), sha256 헤드리스
  `32997e9b6efb1fdc36737a1f9706a3156bee0a7256a6fe9382135495182ada24`(1,156,505,600 바이트) · GUI `a3f06a56…`. dev 헤드 `/opt/apptainers` ·
  `/data/SmartTwinPostprocessor` 가 이 판이다(지문 확인 — dev 노드 node001 · 002 는 VM 이 꺼져 있어 아직 v47). 이 박스에서 stcx 로 밀어 넣는 절차는
  없고 **설치는 운영 측 몫**이다. 리포트 잡이 도는 노드 쪽 사본까지 같은 판으로 둔다
  (헤드와 노드의 판이 다르면 리포트 셸이 경고한다).
- 설치 뒤 — `apptainer exec <설치한 SmartTwinPostprocessor.sif> head -3 /opt/kood3plot/VERSION` → `Version: 226eca7`.
- 순서 — 이 판의 꾸러미는 어휘 0.5 다. cae00 DynaForge 가 `32cc364` 이상이어야 받는다(§0 의 1번 update-all 을 먼저 하거나 같은 때에 — `752fa2b` 판이
  이미 그 뒤다). 늦으면 그 사이 반입된 리포트는 꾸러미 없이 들어오고 잡 `external_ref.ontology.state` 가 `failed`(「받아들이지 않은 어휘 판이다」 — 잡
  경고 한 줄)다. 리포트는 정상이고, 꾸러미는 나중에 리포트 화면 「꾸러미 붙이기」로 붙인다. 노드 쪽 사본이 아직 옛 판(v46 이하)이면 그 잡의 꾸러미는
  어휘 0.4 로 오고 그대로 받는다(v47 ~ v49 이면 0.5 — 같다).
- 운영에서 볼 것 — 전각도 잡 하나 뒤 (1) 단면 영상 마지막 프레임 범례가 `max = 0, at node# 0` 이 아니다 (2) 결과 폴더에
  `<출력>/sphere_report.ontology.json` 이 있다 (3) icn401 반영 뒤 제출한 잡이면 귀환 매니페스트의 `reports[].ontology.present` 가 true 이고,
  그 잡을 받은 DynaForge 후처리 예약의 `external_ref.ontology.state` 가 `loaded` (4) 그 리포트 화면의 해석 온톨로지 칸에 노란 경고 줄이 없다 — 있으면
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
- **DynaForge** — 아티팩트: `rclone copy ApptainerImages:KooRemapper/dist/dist-<이전 판>/ ApptainerImages:KooRemapper/dist/latest/`(이번 판 바로 앞은 `dist-20261107-083706Z`) 뒤 `update-all`(또는 `dist-from-drive.sh --restart`). 코드: 이전 커밋으로. 마이그레이션 0015 · 0016 · 0017 은 null 허용 칸 · 유일 제약, 0018 은 새 표 셋과 null 허용 칸 둘, 0019 는 트리거, 0020 은 null 허용 칸 셋(FK 둘 · JSONB 하나)이라 옛 코드가 그대로 돈다 — 되돌리지 않아도 된다(0019 가 지운 「지운 리포트의 선」 은 되살리지 않는다 — 리포트가 없다).
- **KooSlurm** — 그쪽 문서의 되돌리기 절.

## 9. 남은 사람 결정(참고)
SP 허브 주소 · `core:read` 토큰(받기를 켜는 조건 — 넣으면 시간마다 받고 7일마다 처음부터) · CAD 묶음을 리포트에 붙일 주체(포털 절차의 한 단계 · 사용자 MCP — MCP `attach_cad` 는 MCP 컨테이너가 읽는 경로만 되고 StepForge 산출 자리는 안 보인다(dev 실측), REST 는 어디서든) · 옛 결과 리포트 셸 다시 만들기 `--regen-sh`(pyKooCAE — 옛 부분충격 결과는 이것 없이 7-1 로 못 받는다) · SSO 켤 시각(§7) · 렌더 결과를 붙이는 명의(소유자만 / 같은 소속) · 보고 영상 「접촉 앞」 해석 밖 구간 · 과제 키 검증(7-4) · pyKooCAE F 예제.
