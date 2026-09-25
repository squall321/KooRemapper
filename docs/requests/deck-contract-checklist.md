# 덱 편집 계약 — 1차 구현 체크리스트 (2026-09-24)

요청서 `deck-contract-request-2026-09-24.md`, 실측 계획 `deck-contract-plan-2026-09-24.md`.
**공통 선행 관문** — LF 덱은 바이트가 안 바뀌어야 한다. `examples/*/small/*.k` 전 op 출력 sha256 을
수정 전에 떠 두고 매 단계 대조한다. 여기서 깨지면 개행 재적용이 틀린 것이다.

## P1-6 · D — 버그 2건 (선행 없음, 가장 작음)
- [x] `histElem` 에 `_SET` 제외 추가 (`ModelAssembler.cpp:2938`) — `histPart`(:2896)에는 이미 있다
      → 검증: `*DATABASE_HISTORY_SOLID_SET 7` 심고 merge → rc=1 오탐 사라짐
- [x] `*PART` 고정폭 폴백 8 → 10 (`KFileReader.cpp` parsePartSection)
      → 검증: 폴백 경로 덱에서 PID/SECID/MID 가 10칸으로 읽힘

## P1-5 · B — 넘침/잘림 금지
- [x] `fmt10d`(`ModelAssembler.cpp:15239`) 앞을 버리는 `substr` 제거 → 10칸에 맞는 표기 재포맷, 안 되면 raise
      → 검증: `dt2ms: -1.0e-7` 출력에 **음수 부호 보존**(지금 `1.0000E-07` — 물리가 뒤바뀐다)
- [x] `fmt10i`(:15243)·`setField`(`kw_util.h:54`) 같은 규약
- [x] 넘치면 rc=1 + errorMessage_, 입력 덱부터 어긋난 것은 WARN(`5581-5598` 규약 따름)

## P1-4 · C — `ContactDef.hasId` (읽기 + **쓰기 4곳**)
- [x] `contact_helpers.cpp:49-56` 판정을 endswith 전용 → `_ID` 끝 또는 `_ID_` 포함
- [x] `ContactDef` 에 `hasId` 추가, 편집 4곳(`contact_helpers.cpp:1203`·`1224`, `contact.cpp:955`·`989`)이 그것을 볼 것
      → 검증: `modify friction:0.33` 후 **fs 칸**에 0.33 · **ssid 칸 불변**(지금 SSID 를 덮어쓴다)
      → 검증: `modify soft:2 depth:35` 후 **필수 Card 3 잔존**(지금 사라진다)
      → ⚠ 회귀에서 **개수를 단언하지 말 것** — 개수만 보면 이 버그가 전부 통과한다
- [x] `_ID` 회귀 3종 추가(예제 덱 대신 회귀가 직접 만든다)(`examples/contact/model.k` 는 `_TITLE` 만 써서 이 경로를 안 밟는다)

## P1-1 · A — 개행 보존 (치명)
- [x] 읽을 때 개행 종류를 기억하고 쓸 때 되붙인다. **줄 문자열에 `\r` 을 남기지 말 것**
      (78곳의 `stoi`/`substr`/`back()` 분기가 전부 깨진다)
- [x] 진입점: `ModelAssembler.cpp:62-67`(loadBaseModel)·`132-135`(loadRawOnly), `KFileReader`
- [~] 출력: `ModelAssembler` 는 완료 / `KFileWriter`·`strip`·`relax`·`database` 는 다음 커밋, `KFileWriter:111,229`, `strip:177,225`, `relax:175,271`, `database`
      → 검증: CRLF 578 덱 → indent·database·relax·strip **4개 전부 CRLF=578**
        (지금 0 / 0 / **578 혼재** / 578 — relax 가 한 파일 안에서 개행이 갈린다)
      → 검증: LF 덱 전 op sha256 불변
      → 검증: CRLF 덱을 restack/refine 으로 돌려 엄격 재독(`5517`)이 rc=1 오판하지 않을 것 (**같은 커밋**)

## P1-2 · F — 무편집 진입점 + SYS-02 바이트 왕복 회귀
- [ ] 무편집 진입점. **각 op 의 read 경로를 태우고 write 경로로 낼 것** — cat 복사식은 아무것도 못 잡는다
- [ ] `tools/regress/test_roundtrip_bytes.py` — 픽스처 5종(LF / CRLF / 무-말미개행 / `I10=Y LONG=S` / 2줄 혼재)
      → 검증: sha256 + n_bytes + n_lines + n_crlf **4개 동시 일치**

## 남긴 것 (P2 이후)
- G EditGate 원장 / O-min 절대 참조 검사 / H kfile_inspect n_crlf / G11 ORTHO 거절 가드
- 이유는 계획서 §4.2. 특히 `kw_tok10` 8벌 흡수·ElemCardIndex 공용화는 회귀 신호가 묻힐 만큼 파급이 크다

## 실제 결과 (2026-09-24)

커밋 4건. 회귀 **37 → 40개**, 전부 통과. 매 항목 **무력화로 확인**했다.

| 커밋 | 무엇 | 무력화 |
|---|---|---|
| `4d22441` | `_SET` 오독 rc=1 오탐 · `*PART` 폴백 8→10 | 제외를 빼면 FAIL 2 |
| `e2281b3` | dt2ms 음수 부호 소실 | 옛 포매터로 되돌리면 FAIL 2 |
| `63f50a7` | `_ID` 편집이 SSID 칸 덮어씀 | 쓰기가 hasId 를 안 보면 FAIL 6 |
| `a25aa17` | CRLF 왕복 소실 | 되붙임을 빼면 FAIL 2 |

**셋은 요청서에 없던 것이다** — `_SET` 오독, dt2ms 부호, `_ID` 쓰기. 요청서가 든 근거
(7자리 EID 잘림 · TIED 225→0)는 재현되지 않았고, 대신 검증 중에 더 나쁜 것이 나왔다.

## 아직 남은 것

- **자체 ofstream op 들의 개행** — `strip`·`relax`·`database`·`KFileWriter` 등 25곳 이상.
  `relax` 는 한 파일 안에서 개행이 갈린다(최악). MSVC 텍스트 모드 결함도 같은 자리다.
- **무편집 진입점 + 픽스처 5종 바이트 왕복**(SYS-02 완전형) — 지금 회귀는 개행만 본다
- G EditGate 원장 / O-min 절대 참조 검사 / H kfile_inspect n_crlf / G11 ORTHO 거절 가드


## 2차 완료 (2026-09-24 이어서)

- [x] 자체 ofstream op 들의 개행 — `DeckWriter` 공용 계층으로 모음(d988740). **19개 op 보존, 깨짐 0**
- [x] 전 op 개행 매트릭스 `test_newline_matrix.py` — 카탈로그 예제를 구동기로 씀(op 이 늘어도 따라옴)
- [x] ORTHO/COMPOSITE 등 못 다루는 카드 배치 거절(d194c49)
- [x] 세트 참조 절대 검사(814ff72) — TN4 사건. 오탐 0건 확인, `*INCLUDE` 면 단정 안 함
- [x] `kfile_inspect` 개행 노출(f1b6d7d) — newline/n_crlf/n_lines/final_newline
- [x] **회신 요청서** `deck-contract-reply-2026-09-24.md`

회귀 **37 → 42개**, 전부 통과. 무력화 전 항목 확인.

### 다음(요청 측 답을 기다리는 것)
- DF-07 예약 대역 **실제 값** / DF-08 "템플릿" **정의** / 회귀 코퍼스 / dangling rc 정책 합의
- DF-20 편집 게이트 원장 — 출력 복사 4회 제거와 **같은 유닛**이어야 한다

## 3차 — 덱 계약 2차 계획(plan2) 착수 (2026-09-25)

M1 · 시험이 눈을 뜬다 · **완료**

- [x] **P0-3** 매트릭스가 건너뛰지 않는다(0704b79) — 49 op = **판정 42 + 선언된 제외 7 · 건너뜀 0**
  - 건너뜀 29의 정체는 셋이었다. ① 예제 폴더에 입력 덱이 없다(16) ② **판정이 틀렸다**(6 —
    바이트 동일 보존이 "안 바뀐 입력" 으로 걸러졌다) ③ 정말 덱을 안 쓴다(7)
  - `FIXTURES`(어느 덱을 왜 갖다 놓나) · `PREP`(cclip 은 입력이 생성물) · mtime 기준선 + 내용 해시
    **둘 다** · 리포 `materials/` 스테이징(`matdb` 가 바이너리 위치로 갈렸다) · 선언 드리프트 FAIL
  - `requires_gmsh` 인데 gmsh 가 없으면 **skip 이 아니라 FAIL**. 실사용이 찾아 준 바로 그 구멍이다
  - 카탈로그는 고치지 않았다 — `example.args` 는 프런트 폼 자리표시자다(SessionDetailPage.tsx:54)

M2 · 덱 쓰기 정합 · **개행 부분 완료**

- [x] **P0-1** meshfix 2줄 포맷 요소 소실 + CRLF(2e47878, 2차에서 이미 마침)
- [x] **P0-2** 개행을 아직 잃던 op — **계획의 10개가 아니라 12곳**이었다(afbc154, e841e5a)
  - `explicit`·`implicit`·`modal`·`stabilize`·`database`·`hfdamp`·`optimize`·`cclip`·`squeeze` 9개
    (`implicit`·`squeeze` 는 **한 파일 안에서 갈렸다**)
  - 예제가 **안 켜는 키** 뒤에 셋 더 — cclip `stress_output: include` 의 dynain ·
    cclip `free_output` 의 `_free.k` · squeeze `strain_mode` 의 dynain.
    dynain 이 갈리는 것이 특히 나쁘다 — `*INCLUDE` 로 **함께 풀리는 짝**이 어긋난다
  - `strip`·`matswap` 은 리눅스에서 우연히 보존됐다(리더가 `\r` 을 안 뗀다). MSVC `\r\r\n` 때문에
    옮겼다 — 우연에 기대는 자리를 계약으로 바꾼다
  - 새 관문 `test_deck_ofstream_allowlist.py` — `src/`·`include/` 의 `std::ofstream` 을 파일별로
    선언한다. 수가 달라지거나 선언에 없는 파일에서 나오면 FAIL. 분류는 덱(보존)·덱(신규)·덱 아님

회귀 **42 → 45개**, 전부 통과 · ctest 1/1. 변이는 커밋별로 이렇다(단위를 밝혀 둔다 —
합계만 적어 두면 어느 시험의 몇 건인지 되짚을 수 없다).

| 커밋 | 무엇을 되돌렸나 | 잡힘 |
|---|---|---|
| afbc154 | 개행 수정 소스 파일 하나씩 | 9/9 |
| 0704b79 | 매트릭스의 선언·관문(EXCLUDE·드리프트·gmsh·FIXTURES) | 4/4 |
| e841e5a | 동반 파일 개행 3곳 + `strip` | 3/4 |
| e841e5a | `std::ofstream` 선언 관문(수 증가·수 불일치) | 2/2 |

합계 19건 중 18건. 안 죽는 하나는 `strip` 이다 — 리눅스에서 리더가 `\r` 을 떼지 않아 우연히
보존되므로 되돌려도 산출물이 안 바뀐다(옮긴 이유는 MSVC 텍스트 모드의 `\r\r\n`). 잠금용으로 남겼다.

M0 · 신뢰 회복 · **백업 완료**

- [x] **P0-5** DB 백업 — 크론에 걸었고(매일 04:10) **첫 백업을 떴다**(3af5f0f)
  - 09-25 까지 `backup-db.sh` 는 한 번도 돈 적이 없었다. `infra/data/backups` 자체가 없었다
  - **부분 덤프를 백업으로 세지 않게** 고쳤다 — 옛 구현은 `pg_dump | gzip > OUT` 이라 중간에
    죽어도 파일이 남고, gzip 스트림은 정상 종료라 `gzip -t` 로도 안 걸려 **14개 보관 정책 아래서
    멀쩡한 백업을 밀어냈다.** `.part` + 완료 표식 확인 뒤 이름 바꾸기로 막았다
  - 시험이 기존 결함을 하나 찾았다 — 감독자가 안 돌고 있으면 `--remove` 가 크론을 이미 뗀 뒤에
    rc=1 로 끝났다(`pipefail` + 없는 잠금 파일). 기존 시험은 pid 파일이 **있는** 경로만 밟았다
  - 시험 6개 추가 · 변이 4/4 잡힘 · 백엔드 229 통과

M0 · 신뢰 회복 · **완료** / M3 · 게시 · **완료**

- [x] **P0-4** 게시 정합(e5110b5·fb46468·c56bdfb) — **게시했다** `dist-20260925-040105Z`
  - glibc 관문. ⚠ 상한은 **2.35** 다 — 계획서의 "2.37 이상 거절" 은 두 칸 느슨했다.
    실사용 소비자 실측: SmartTwinPreprocessor.sif **2.35** · cli.sif 2.36 · api/mcp.sif 2.41
  - BUILD_INFO 가 받는 쪽에 **한 번도 안 내려앉고 있었다**(mktemp 스테이지째로 지워졌다).
    반입 readout 의 `sort -u`(사전순)도 고쳤다 — 2.38 을 받고도 "2.4" 라고 찍었다
  - `/api/health` 가 `revision`·`binary_sha256`·`revision_matches_binary` 를 낸다.
    실측으로 게시 → BUILD_INFO → 반입 → health 전 구간 확인
  - 게시본이 `cb4e208`(09-21) → `fb46468` 로 **26커밋 전진**
- [x] **P0-6** ID 발행이 `*INCLUDE` 를 못 봤다고 말한다(449bbf6) — 번호는 그대로
  - 조사가 후보 목록을 고쳤다 — `modelmeta` 는 발행자가 아니고, `cnrb2spring` 은 최대+1 이
    아니라 고정 대역+충돌검사다. 반대로 빠진 발행자가 9개 더 있어 전수 27곳
  - **헬퍼 1개 + 창구 2개**로 덮었다(18곳이 `loadBaseModel` 하나를 지난다)
  - `include/parser/IncludeScan.h` 가 판정을 한 자리로 모은다 — 같은 판정이 셋 있었고
    `ReferenceIntegrity` 는 `*INCLUDE_PATH` 를 파일로 세는 **오탐**이 있었다(`info` 가 거짓 경고)
  - 변이 5/5. ⚠ ④(번호 불변)를 처음엔 헛통과하게 써서 변이가 살아남았다 — '발급이 0건이면
    그 자체로 FAIL' 로 바꾸고 실제로 발급하는 레인(`ale`)으로 갈아 잡았다
- [x] **P0-7** 회신 `deck-contract-reply2-2026-09-25.md`
  - 사실 확인에서 **내 숫자 둘이 틀렸다** — 전진 커밋 수(21→26), meshfix 수정 후 값(실측 1911)
  - 인용 줄이 P0-6 편집으로 밀려 있어 **함수 이름과 함께** 다시 적었다
- [x] **P1-8** 플랫폼 개행 경고(45de81c) — P0-2 가 끝나 풀린 항목
  - ⚠ 판정 대조만으로는 **혼재 덱을 놓친다**(`count(CRLF)*2 > count(LF)` 규약). 혼재를 규칙으로 넣었다
  - 변이 시험이 제 가드 하나가 **거꾸로**임을 알려 줬다(덮어쓴 파일의 왕복 전 개행도 입력이다)
- [x] **CI 에 gmsh**(bc2eba2) — 내가 skip 을 FAIL 로 바꿔 CI 가 빨갰다. `.github/workflows/` 는
  HTTPS+PAT 로 못 미는데(`workflow` 스코프) **SSH 로는 된다** → `docs/requests/ci-gmsh-2026-09-25.md`

- [x] **SIF 재굽기**(외부라 적었으나 여기서 했다) — `SmartTwinPreprocessor.sif` 안 바이너리를
  `168cc9d4`(GLIBC_2.34, P0-6 포함)로 갈아 `/opt/apptainers` 와 compute-node-images 양쪽에 배포
  - 컨테이너(2.35) **안에서** 실행·P0-6 경고·CRLF 보존을 직접 확인했다
  - ⚠ `BuildSmartTwinPreprocessor.sh` 는 지금 koopark 으로 돌리면 **2/5 에서 죽는다** —
    샌드박스의 `KooDynaPostProcessor`(uid 100999)·`SmartTwinPreprocessor`(root)를 못 쓴다.
    이번에는 마지막 빌드 이후 바뀐 것이 kooremapper 한 파일뿐이라 그 트리만 갈아 구웠다.
    **그 스크립트 자체는 손대지 않았다**(다른 프로젝트다) — 소유권은 정리가 필요하다
  - 되돌리려면 `appt313/opt/kooremapper/bin-backups/KooRemapper.bak.1790326466` 로 되돌려 다시 굽는다
- [x] **재게시** — 첫 게시본(`dist-20260925-040105Z`)은 P0-6 이전이라 다시 올렸다.
  정본은 `dist-20260925-090215Z`(소스 `7aa1f3a`) — `revision_matches_binary: true` 로 확인
- [x] **`cli.sif` 가 09-21 바이너리를 굽고 있던 것** — 배치/HPC 잡용 자체완결 SIF 다.
  `--build` 없이 게시하면 아무도 다시 굽지 않아, 그 뒤 **모든 게시본이 옛 바이너리가 든
  cli.sif** 를 실어 날랐다. 게시물 안에서 `koorm-bin.tar.gz` 와 `cli.sif` 의 바이너리가 서로
  달랐고 받는 쪽은 알 방법이 없었다. 다시 굽고, **게시물 내부 정합 관문**을 붙였다
  - `api.sif`·`mcp.sif` 는 바인드로 쓰므로 무관하다(실측 확인). 굽는 것은 cli 와 STP 둘뿐이다

## 4차 — P1 착수 (2026-09-25)

- [x] **P1-1 바이트 왕복 회귀** `test_roundtrip_bytes.py` — 지금까지의 회귀는 산출 덱에
  **LF 단독 줄이 있나**만 봤다. 그것으로는 "입력 개행에 따라 **내용이** 달라지는" 결함을 못 잡는다
  - 같은 덱의 LF 판·CRLF 판에 같은 op 을 돌려 ① 정규화 sha256 일치 ② 줄 수 일치 ·
    `n_crlf(CRLF판)==줄 수` · `n_crlf(LF판)==0` · 말미 개행 일치 ·
    **바이트 차이 == 줄 수**(줄마다 CR 하나씩만) ③ 무-말미개행 판으로도 ①②
  - ②의 마지막 항이 `\r\r\n` 과 CR 누락을 잡는다 — 개행 **종류**만 보면 둘 다 "CRLF" 다
  - 42 op 전부 통과. 계획서가 지목한 무력화(리더의 `\r` 제거를 뺀다)로 **80건 FAIL** 확인.
    DeckWriter 하나 되돌리기로도 잡힌다
  - 픽스처 표는 매트릭스에서 **빌려 쓴다** — 베끼면 둘이 갈리고 한쪽이 틀린 채 초록이 된다

### ⚠ 그 과정에서 알아낸 사실 — 산출 덱은 바이트 단위로 재현되지 않는다

`map` 이 간헐적으로 실패해 비결정성으로 오진할 뻔했다. 파고 보니 **헤더에 시각이 박힌다** —
`KFileWriter::writeHeader` 와 `DynainWriter` 가 `$ Date: YYYY-MM-DD HH:MM:SS` 를 찍는다.
같은 입력에 같은 op 을 두 번 돌려도 **초가 넘어가면 sha256 이 달라진다**(실측).

시험은 비교 전에 그 값만 같은 길이로 가린다 — **감추는 것이 아니라 여기 적어 두는 것이다.**
3자 대조(원본↔템플릿↔per-run, P2-1)나 sha256 계보를 **바이트로** 하려면 이 줄을 끌 수 있어야
한다. 출력을 바꾸는 일이라 여기서 임의로 고치지 않았다 — 결정이 필요하다.

## 5차 — P1-2(쓰기 경로 폭) + P1-9(gmsh) (2026-09-25)

조사를 4갈래 워크플로로 돌리고 각 주장을 적대 검증했다. **재현된 결함 다섯을 고쳤고 전부
`rc=0` 으로 깨진 덱이 나가던 것**이다.

- [x] **`I10=Y` 요소 카드 8칸 + PID 오독**(201e0c8) — `parsePartIdFromLine` 이 `substr(8,8)` 이라
  I10 카드에서 **EID 의 꼬리**를 PID 로 읽었다(PID 77 → 1, 그 파트는 덱에 없다)
- [x] **packed `*NODE` 좌표 소실**(050e91e) — TC/RC 칸의 `0` 두 개가 토큰 수를 4로 만들어
  자유형식이 이기고 `y`·`z` 가 **둘 다 0** 이 됐다. **구속을 준 노드만** 좌표를 잃었다
- [x] **`generate` 재료 값 앞자리 버리기**(16850f5) — `e2281b3` 이 고친 코드가 다른 함수에
  **글자 그대로** 남아 `rho: -7.85e-9` 의 부호가 사라지고 `E: 12345678` 이 2,345,700 이 됐다
- [x] **8칸 초과를 조용히 넘김**(9150ee6) — `std::setw` 은 자르지 않고 **칸을 늘린다.**
  `*NODE` 16줄이 엄격 8칸 재독에서 **고유 9개**로 뭉쳤다. 이제 파일을 쓰지 않고 rc≠0
- [x] **`elform` 강등·`meshfix` 가 덱 폭을 안 따름**(9150ee6) — elform 은 **내가 201e0c8 에서
  이웃만 고치고 놓친 자리**, meshfix 는 덱 폭을 아예 안 읽었다(+ long 덱 거절 추가)
- [x] **P1-9 gmsh 를 실제로 돌려 확인**(21df344) — 탐색이 후보를 검증하지 않아 깨진 래퍼가
  진짜 gmsh 를 제치고 뽑혔다. 플랫폼도 큐에 넣기 전 422 거절 + `/api/health` 노출

**8칸 덱 불변**은 매번 옛 바이너리와 **42 op sha256 대조**로 증명했다(말로 끝내지 않았다).

### ⚠ 회귀 4개가 빨갰고, 원인이 둘이었다 — 둘 다 코드 결함이 아니었다

**(a) 내 가드가 정상 설정을 막았다.** gmsh 검증이 **사용자가 지목한 명령**(`KOOREMAPPER_GMSH`)을
시험 삼아 돌렸는데, 회귀가 거기에 gmsh **래퍼**를 준다(`cp "$1" saved.geo` 를 먼저 한다).
`--version` 이 `cp --version` 이 되어 `cp (GNU coreutils) 8.32` 를 냈고 "gmsh 아님" 으로 거절했다.
→ **명시 지정은 검증하지 않는다**(21df344). 탐색이 *우리 마음대로* 고른 후보에만 정당하다.

**(b) 리포 루트의 덱 픽스처 12개가 덮어쓰여 있었다.** `test_remaining_surfaces` 는 단언 실패가
아니라 **900초 시간 초과**였다. `arc30_flat_tet.k` 가 요소 1000 → 99 · Parts 0 으로 바뀌어 있었고
meshfix 가 그 덱에서 끝나지 않았다. `git checkout` 으로 되돌리니 **rc=0, 21초**.
→ **rc=124 를 단언 실패로 넘겨짚지 않은 것**이 갈랐다. 기억에 남겼다(test-env-traps).

**(c) 그리고 내 시험이 같은 함정에 두 번째로 걸렸다**(21fff27) — gmsh 탐색 시험이 바이너리를
**그 자리에서** 돌려, 옆에 번들 gmsh 가 있는 사본에서는 PATH 갈래에 도달하지 못했다.
시험은 바이너리의 **이웃**에 기대면 안 된다.

### 남은 것 (이 라운드에서 재현했지만 안 고침)
- `md_setField` 의 앞자리 버리기 — 8칸으로 부르는 자리가 `*ELEMENT_MASS` 하나뿐이고 그 탐지가
  따로 깨져 있어 **실제 잘림을 재현하지 못했다**. 지어내지 않고 남긴다
- `cnrb2spring` 의 `99999999` 상한이 덱 폭을 안 본다(i10 덱에서 9-10자리를 막는다)
- `*NODE` **가운데 칸이 빈** 고정형식 카드 오독 — 자유형식 덱과 구분할 판별식을 못 찾았다

### 아직 남은 것
- (없음 — plan2 의 P0 7건과 P1-8 완료)

### 이번에 우리가 우리를 잡은 것
빌드 덫 하나가 **오늘 실제로 발동했다.** `build/linux` 가 `-DKOOREMAPPER_PLATFORM_BIN` 으로
설정돼 있어 평범한 `cmake --build` 가 배포용 바이너리를 GLIBC_2.38 로 덮어썼다(09-24 에
"다른 세션이" 라고 적은 그 사건도 같은 기전일 가능성이 크다). **오늘 만든 관문 둘이 그것을
잡았다** — `/api/health` 의 `revision_matches_binary: false`, 그리고 `dist-to-drive.sh` 의 거절.
이제 빌드 때도 시끄럽게 말한다(`15fa18b`). 막지는 않는다 — 진짜 관문은 게시 쪽이다.
