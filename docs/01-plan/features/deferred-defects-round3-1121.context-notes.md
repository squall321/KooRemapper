# 미룬 결함 3차 — 맥락 · 결정 기록

계획 `deferred-defects-round3-1121.plan.md` · 체크리스트 `deferred-defects-round3-1121.checklist.md`.

## 1. 시작(2026-11-21)
- 사용자 결정은 계획 0절에 문장째 옮겼다. 갈래 `corelink-int` 는 `ee210f0`(main 과 같다). SP main · 키트 판은 작업 시작 때 확인했다(바뀐 것 없음
  — 고정 `3196156` · 키트 `2026-11-06`).
- 설치된 판은 `f20d5d5b`(Drive `dist-20261121-120311Z`). 재기는 이 바이너리로, 고침은 작업 트리의 `build/dev` 로 한다.
- pykoocae-53 과 주고받은 것 — 그쪽이 matswap 번들 BOM 을 v141 에 넣으려고 기다린다. 답으로 아직 안 고쳤다는 것 · 그때까지의 길(번들을 BOM 없이
  저장) · 고치면 보낼 것(커밋 · 바이너리 sha256 · 판정 꾸러미)을 보냈고, 무거운 빌드 전에 알리겠다고 했다. `build/linux/bin` 은 알리기 전까지
  `f20d5d5b` 그대로 둔다.

## 2. 판을 나눈 까닭
- 뿌리가 같은 것끼리 묶었다 — 덱 머리(BOM · 빈 메시) · 칸 폭과 번호 한계 · 쌓인 카드와 재료 · 파일과 메모리 · battery. rc 0 으로 틀린 덱을 내는
  줄이 든 묶음을 앞에 뒀고, matswap 번들은 다른 팀이 기다려 맨 앞이다.
- 스무 줄을 한꺼번에 다시 재지 않는다 — 판을 열 때 그 판의 줄을 잰다. 목록의 여러 줄은 11-07 · 11-08 검토가 적은 것이라 지금 판에서 같은지
  모른다(검토가 적은 것은 소스에서 확인한 뒤에 고친다).

## 3. 1판을 재면서 정한 것
- **BOM 규칙은 새로 정하지 않았다** — 2차 H-2 · H-4 에서 사용자가 고른 것(extract-parts · cleanup-nodes 는 뗀다 · 산출에 싣지 않는다)을 남은 op
  에 그대로 편다. LS-DYNA 가 BOM 덱을 받는지는 못 쟀지만, BOM 없는 산출은 어느 쪽이든 받는 꼴이다.
- **cad_solid_merge_to_deck 조각의 BOM 은 표의 「줄 하나」 보다 나쁘다** — 다시 재 보니 조각의 `\ufeff*KEYWORD` 줄이 덱의 `*MAT_ELASTIC` 블록
  뒤(주석 두 줄 다음 · 산출 42째 줄)에 데이터 줄로 실린다. op 은 rc 0 에 되읽기 검증 통과를 말한다. 2차 H-6 표는 줄 수만 셌다.
- **조각은 rc 를 뒤집지 않는다** — cad_solid_merge_to_deck 은 떼고(rc 0 그대로 · 덱이 바로 선다), apply_carryover_plan 은 거절 그대로에 까닭
  글만 고친다. 둘을 같은 쪽으로 맞추면 한쪽은 다른 팀이 보는 rc 가 바뀐다. apply_carryover_plan 의 조각 검사는 제어 문자도 「고치지 않고
  거절한다」 고 적어 둔 자리다.
- **`strain` · `squeeze` 는 거절** — 같은 주 덱을 unfold · map · extract-surface · neutralaxis · prestress 가 이미 rc 1 로 멈춘다. 인클루드를
  읽게 하는 것은 기능을 넓히는 일이라 이번 범위가 아니다.

## 4. 2판에 넘긴 실측(L-04a — 1판을 재다 같이 쟀다)
- 줄 맞춘 표준 덱 · `LONG=Y` · `I10=Y` 세 꼴을 만들어 돌렸다(`examples/cnrb2solid/bolt_simple.k` 는 절점 줄이 칸에 맞지 않아 공백으로 끊어 다시
  썼다 — 처음에 칸으로 잘라 만든 `LONG=Y` 덱은 깨진 덱이라 그 결과는 버렸다).
- `I10=Y` — 둘 다 rc 0 이고 산출의 절점을 선언 폭(번호 10 · 좌표 16)으로 읽으면 표준 판과 좌표가 같다(cnrb2solid 75 절점 · cnrb2spring 20 절점).
  결함이 아니다.
- `LONG=Y` — cnrb2solid 는 rc 0 에 「WARNING: NSID=0 not found or empty, skipping PID=0」 을 찍고 솔리드를 하나도 만들지 않는다(표준 판은 24 개
  · CNRB 카드를 10 칸으로 읽어 NSID 가 0). cnrb2spring 은 rc 1 「덱에 *CONSTRAINED_NODAL_RIGID_BODY 가 없습니다」(있다). 목록이 적은 「좌표 칸」
  보다 앞의 문제다 — 두 op 은 `LONG=Y` 카드를 읽지 못한다. 읽게 할지 거절할지는 2판에서 선택지로 묻는다.

## 5. 1판 결과(2026-11-21 · 코드 `cd52b79`)
### 5-1. 지은 것
- 커밋 다섯 — 시험 `353d92c` · BOM 떼기 `bbc3513` · 빈 메시 거절 `09a57a7` · 남은 자리 넷 `5242abe` · 격자 파일 `cd52b79`.
- 시험 — `test_deck_bom.py` 는 고치기 전 빨강 59 → 9 → 0(151 항), 화면 대조 · ale · BOM 덱 계획을 더해 빨강 5 → 0(237 항), 격자 쌍둥이를 더해
  빨강 10 → 0(259 항). `test_include_only_main.py` 는 빨강 12 → 0(15 항). 단위 246 그대로(`scalarNodeMaxIdFile` 의 BOM + I10 항은 그 안).
- BOM 을 건너뛰는 줄이 든 소스는 스물다섯 파일이다(`git diff ee210f0 cd52b79 -- src include` 는 29 파일 · +83 −4) — 쓰는 쪽
  `writeFileWithSource` · 조립기의 기본 모델 읽기 둘 · prestress 의 변형 메시 복사 · op 마다의 덱 읽기 · matswap 번들 **둘**(YAML 꼴은 조립기
  `mw_parseBundle`, 옛 자리 인자 꼴은 `matswap.cpp` 의 `msw_parseBundle` — 옛 꼴은 모델 덱도 제 손으로 읽는다) · cad_solid_merge_to_deck 조각 ·
  ale 재료 파일 · `scalarNodeMaxIdFile` · 격자 리더 둘. 새 함수는 없다 — 있던 `yamlSkipBOM` · `yamlStripBOM` 을 여는 자리에서 부른다.
- 빈 메시 판정은 `Mesh::getElementCount()` 로 한다 — 솔리드 · 셸 · 두께 셸을 다 센다. 솔리드만 세면 셸뿐인 덱의 squeeze 가 빨개진다(시험 F 항).
  까닭 글은 `include_scan::emptyMeshWhy` 한 자리에서 짓는다.

### 5-2. 재서 확인한 것(바이너리 sha `2a4604f0` — `cd52b79` 를 지은 dev 판)
- **BOM 없는 덱은 그대로다** — 도움말 사례 64 를 설치된 판(`f20d5d5b`)과 새 판으로 돌려 rc · 화면 · 산출이 64 / 64 같다. 처음엔 `modelmeta`
  화면 하나가 달랐는데 코드가 아니라 자리 탓이었다(dev 바이너리 곁의 `materials/material_db.json` — 이웃 없는 폴더에 복사해 다시 재니 같다).
- **BOM 훑기 다시**(58 op × 꼴 넷) — 덱 맨 앞 BOM 은 57 / 58 같음(지난 판은 달라지는 op 이 44 · 이번 1). 남은 하나 apply_carryover_plan 은
  설계대로다(덱 → `deck_sha` · 조각 셋 → `fragment` 의 BOM 까닭). 인클루드 BOM(쪼갠 꼴 58 op · 펼친 꼴 50 op) · 설정 YAML BOM(55 op)은 차이 0.
  지난 훑기와 달라진 다른 줄은 일곱 — strain 셋 · squeeze 둘이 쪼갠 덱을 rc 1 로 거절하는 것(L-03 · 설계)과 `modelmeta` 둘(위의 이웃 탓).
- **변이** — 넣은 줄을 하나씩 되돌려 시험이 빨개지는지 봤다. 36 줄 가운데 34 빨강, 산 둘을 조이고 격자 리더 두 줄을 더해 38 / 38 빨강.
  · 산 것 ① 옛 꼴 matswap 의 모델 덱 BOM — 번들 쪽만 쟀다 ② apply_carryover_plan 조각 — 첫 `[ERROR]` 줄만 봐서, BOM 을 안 뗀 채 검사를 이어
  엉뚱한 까닭이 한 줄 더 붙는 변이가 살았다.
- **JSON 입력의 BOM**(재기만 · 안 고침) — 계획(`plan_json — 계획 JSON 문법 — 0째 바이트: 값이 아니다`) · 대응표(id_floor ·
  cad_solid_merge_to_deck) · `range_diff`(rebind) · 재료 DB(`Cannot load database from: …`) 모두 rc 1 이고 까닭 글이 BOM 을 말하지 않는다.
- `info` · `modelmeta` 는 `*INCLUDE` 뿐인 주 덱에서 인클루드를 읽는다 — 고칠 것 없음.

### 5-3. 재다 나온 것(목록 밖)
- **내가 들인 것 둘**(`bbc3513` → `5242abe` 에서 고침 · 판을 내기 전) — apply_carryover_plan 의 거짓 `deck_changed`(뗀 줄을 BOM 든 파일 바이트와
  견줬다) · applyfold 의 거짓 「바이트 크기가 달라졌다」 경고. 둘 다 rc 와 산출은 같아 회귀 시험이 못 봤고, 쌍둥이 훑기를 화면까지 견줘서
  나왔다. 그래서 `test_deck_bom.py` 가 이제 화면도 견준다(시각 · 걸린 시간은 가린다).
- **설치된 판에도 있던 것**(이번에 고침) — ale 재료 파일의 BOM(`*MAT_` 블록이 통째로 빠지고 `*EOS_` 만 실린다 · rc 0) · warpage · bend 격자
  파일의 BOM(첫 행이 조용히 빠진다 — 리더가 둘이고 열쇠가 셋이라 쌍둥이 여섯으로 쟀다 · 설치된 판 `f20d5d5b` 에서 같은 결과) · BOM 붙은 덱에서
  낸 이월 계획을 적용하면 BOM 이 실린 덱을 썼다(rc 0). `scalarNodeMaxIdFile` 은 BOM 붙은 `I10=Y` 덱의 `*NODE_SCALAR` 900000 을 8 칸(9000)으로
  읽어 meshfix 가 새 절점을 9001 부터 냈다 — 이것은 새 판을 재다 나왔고 설치된 바이너리로 따로 돌리지는 않았다(그 함수에 든 것은 BOM
  건너뛰기뿐이라 코드로는 같다).
- **이월 조각의 거절 — 앞서 읽은 것을 바로잡는다.** 「계획의 sha 가 달라 거절이 강제된다」 가 아니다. 조각은 sha 가 달라도 값 대조가 지나면
  경고(`fragment_bytes`)로 받는다. BOM 조각이 거절되는 것은 조각 검사(`fragment`)가 걸려서이고, 그때만 sha 차이가 `file_mismatch` 오류로 같이
  선다. 그러니 「BOM 을 떼고 받는다」 는 뒤집을 수 있는 선택지다 — 값은 같으니 경고와 함께 rc 0 이 된다. 다만 다른 팀이 보는 rc 가 바뀌므로
  이번엔 거절 그대로에 까닭 글만 고쳤다.
- **2판에 넘긴 것** — `info` 가 `LONG=Y` 덱에서 거짓 「섹션 1 / 재질 1 이 정의되지 않았습니다」 를 찍고 `--strict` 는 rc 1 · applyfold 경고의
  숫자(`%+lld` 에 double) · `LONG=Y` 쌍둥이에서 rc 0 이 아닌 op 열여섯(ale · apply_carryover_plan · cad_solid_merge_to_deck · cclip ·
  cnrb2spring · convert · disconnect · extract-parts · matswap · meshfix · neutralaxis · offset · rbe · refine · restack · stackwrap)과
  `I10=Y` 의 셋(apply_carryover_plan · cad_solid_merge_to_deck · extract-parts)의 까닭 · L-04a 는 고친 넓히기 도우미로 다시 잰다(4절의 수치는
  그때 견준다).
- **4판 후보** — meshfix 가 퇴화한 면에서 gmsh 를 7 분 돌려 로그 2.7 GB 를 썼다(시간 · 로그 상한이 없다 · 실패 때 남기는 `__mf.log` 가 그
  크기다). 그 뒤로 gmsh 를 부를 수 있는 훑기는 `prlimit --fsize` 와 시간 한도를 걸고 돌린다.
- **적기만 한 것** — tetremesh 가 `*NODE_SCALAR` 를 산출에 옮겨야 하는지(판정 안 함) · 셸뿐인 덱의 squeeze 가 셸 번호에
  `*INITIAL_STRESS_SOLID` 를 쓴다.

### 5-4. 도움말은 그대로 둔다
- 덱 BOM 의 옛 전제(「op 마다 다르다」)를 말하는 도움말 문장이 없다 — `ops_help.py` 의 BOM 은 두 군데뿐이다(apply_carryover_plan 의 계획 JSON
  BOM — 지금도 맞다 · squeeze **설정 YAML** 주의 — 9 월부터 뒤처진 줄이고 매뉴얼 1절 표가 이미 그렇게 적는다). 그래서 카탈로그를 다시 내지
  않았고 바이너리의 도움말 글은 설치된 판과 같다. 전제를 말하던 글은 매뉴얼 3.1(e) · 7 · 10 · 13 · 21 · 23 · 35 · 49 · 52 장과 미룬 목록이고
  같은 커밋에서 고쳤다.

### 5-5. 범위 추세(1판)
- 목록의 두 줄(L-02 · L-03)을 닫는 동안 목록 밖에서 나온 것이 열여덟이다 — 이번에 고친 것 일곱(cad_solid_merge_to_deck 조각 자리 · matswap
  둘째 번들 파서 · prestress 복사 · ale 재료 파일 · 스칼라 절점 바닥 · BOM 덱 계획 · 격자 첫 행), 내가 들였다가 판 전에 고친 것 둘, 시험을
  조인 것 둘, 뒤 판으로 넘긴 것 넷(info 거짓 미정의 · applyfold 숫자 · meshfix 상한 · L-04a 가 목록보다 넓다), 적기만 한 것 셋(JSON BOM 까닭 글
  · tetremesh `*NODE_SCALAR` · squeeze 셸 응력 카드 — 뒤 둘은 결함인지 판정하지 않았다).
- 2차까지의 추세는 목록 밖 기존 결함이 열 → 열셋 → 검토 아홉이었다. 판을 거듭해도 줄지 않는다 — 2판을 열 때 이 수치를 선택지에 같이 싣는다.
- 배운 것 — rc 와 산출만 견주는 회귀는 거짓 화면 줄을 못 본다 · 첫 오류 줄만 읽는 시험은 변이를 살린다 · 덱이 아닌 글 입력(격자)은 쌍둥이
  항을 따로 둬야 한다 · 옛 판 / 새 판 대조는 바이너리 이웃(`materials/`)까지 같은 자리에서 한다.

## 6. 올리기 기록(1판 — 2026-11-21 밤)
- **main** — `98f5ec6` 을 main 으로 앞당겼다(코드 끝은 `cd52b79` · 뒤 둘은 문서). `ee210f0` 부터 37 파일 · +1009 −30, 그 가운데 `src` ·
  `include` 29 파일 · +83 −4, `platform/` 은 0 파일이다. SP 는 올리기 앞에서 다시 봤다 — 고정 `3196156` 위로 앞선 커밋 0 · `KIT_VERSION`
  2026-11-06 양쪽 같다.
- **호환 빌드** — pykoocae-53 에 빌드 앞 알림(23:31 UTC) 뒤 debian:12 빌더에서 `-j8` · 프로세스마다 주소 공간 8 GB(23:32:38 끝). 바이너리 sha256
  `d1e2ce96d9b6a722bbcb944302f9893a0a14ab79840e46a1634d829f22855cfc` · 9,006,040 바이트 · glibc 상한 2.35 · `--version` 1.8.0.
- **호환 바이너리로 다시 잰 것** — 단위 246 / 246 · `test_deck_bom.py` 259 항 · `test_include_only_main.py` 15 항 · 회귀 136 / 136(파일 크기
  상한 없이).
- **판정 꾸러미** — 사례 아홉(matswap 번들 두 꼴 · merge 덱 · strain · squeeze 의 `*INCLUDE` 뿐인 덱 · warpage 격자 · ale 재료 파일 ·
  cad_solid_merge_to_deck 조각 · apply_carryover_plan 조각)을 호환 바이너리와 설치돼 있던 `f20d5d5b` 로 기록했다. 새 판 9 를 호환 바이너리 ·
  설치한 바이너리를 묶은 api.sif · 새 cli.sif 에서, 옛 판 9 를 `f20d5d5b` · 헤드 SIF v140 에서 봤다(종료 코드 0 · 3). 꾸러미는 scratch 에만 있다
  — pyKooCAE 쪽에 경로 · 쓰는 법 · 기대값을 알렸다.
- **설치 · 재기동** — 살아 있는 잡 0 을 보고 23:43:58Z 에 `build/linux/bin` · `platform/backend/bin` 에 깔았다. API 는 감독자 창(23:44:08)에서
  다시 띄우고 MCP 는 멈춘 뒤 `start.sh` 로(23:44:19 — `/data/svc/kooremapper` 바인드 있음). 스모크 — MCP PASS(도구 93 · 연산 65) · deckops 29 /
  29 · allops 64 / 64(건너뜀 1 — stcx 전각도) · reports 59 / 59. 캠페인 탐침은 돌리지 않았다(파이썬이 그대로이고 탐침은 지울 수 없는 캠페인 행을
  남긴다).
- **cli.sif** — 다시 구웠다(141,721,600 바이트 · 안의 바이너리 `d1e2ce96`).
- **Drive** — `dist-20261121-234834Z`(게시 23:48:37Z · BUILD_INFO 커밋 `98f5ec6` · describe `v1.7.0-1247-g98f5ec6`). 앞 판과 다른 파일은
  `BUILD_INFO.txt` · `cli.sif` · `koorm-bin.tar.gz` 셋이고 api · mcp · nginx · postgres SIF 와 콘솔 묶음은 sha256 이 같다(게시 앞 · 뒤
  `latest/SHA256SUMS` 대조). 가장 오래된 `dist-20261108-234149Z` 가 지워졌다(남은 판 — 11-15 · 11-17 · 11-21 낮 · 11-21 밤). 되돌릴 판은
  `dist-20261121-120311Z`(코드 `e7a6ef7` · 바이너리 `f20d5d5b`). 마이그레이션 없음.
- **게시 뒤** — 재기동 없이 health 가 `revision` `98f5ec6` · `revision_matches_binary` true 로 바뀌었다. 주 체크아웃 백엔드 pytest(scratch DB ·
  설치한 바이너리) 1069 통과 · 실패 0.
- **점검 문서** — `docs/requests/hwax-portal-cae00-checks-2026-10-30.md` 에 §1-8 을 더하고 §0 · §1 · §1-7 · §8 의 판 정보를 맞췄다. 새 동작이 든
  바이너리는 `grep -a -c 'UTF-8 BOM 으로 시작한다'` 가 1 이상인지로 가른다(옛 판 0 · 새 판 2).
- **알림** — 11-22 00:00 UTC 무렵 여섯 세션으로 — pykoocae-53(커밋 · 바이너리 sha256 · 판정 꾸러미 경로 · 쓰는 법 · 기대값) ·
  hwaxportal-71(전문) · hwaxportal-87(짧은 판) · stepforge-d4(조각 · 덱 BOM · SP 고정) · smarttwinmcp-c8 · kooremapper-fd. 포털 알림에는 DF
  2차가 멈춘 일정은 싣지 않았다(사용자에게 읽기를 확인받기 전이다) — 동시 올리기 500 은 아직 안 고쳤다는 것만 실었다.
- **못 잰 것** — LS-DYNA 실행(라이선스 만료 — BOM 덱을 솔버가 받는지) · 운영(cae00) 스택 · 헤드 SIF v141(아직 안 구웠다 — pyKooCAE 쪽 일).

## 7. 2판 다시 재기(2026-11-22 · 설치된 판 `d1e2ce96`)
- **바이너리 · 법** — 설치된 판 `d1e2ce96`(`platform/backend/bin` — 이웃 `materials` · `gmsh` 그대로)과 앞 판 `f20d5d5b`. 카탈로그 사례 덱을
  표준 · `LONG=Y` · `I10=Y` 로 다시 쓰는 도우미(`widen.py`)는 `*INCLUDE` 파일 이름 줄을 칸으로 잘라 이름을 끊었다 — 고쳐 다시 쟀다(extract-parts
  의 세 꼴 rc 1 은 그 탓이었다 · 이제 셋 다 rc 0). 조각(계약상 표준 폭)은 넓히지 않는다.
- **L-05 여섯 — 앞 판과 같다**(검토 탐침 `reprobe.py` 를 두 판으로) — 두께 셸뿐인 덱의 unfold 두께 방향(입력 1.0 · 2.0 → 0.25 · 48 요소 결합 0 /
  48 같음) · `JOBID=LONGRUN` · `memory=belong` 이 `LONG=Y` 로 · `*KEYWORD` 둘 · 들여쓴 꼴의 읽기 / 쓰기 폭 갈림 · `*KEYWORD_ID I10=Y` 의 엉뚱한
  까닭(「Element 1 has 0 neighbors」 · 「요소 번호가 겹쳐」) · `-1.5e-120` 을 17 자로(map · tetremesh 57 자 줄) · 상한을 넘는 절점 번호(squeeze
  · tetremesh 가 넘는 하나를 빼고 rc 0 · map · unfold 는 「non-existent node 0」). 달라진 것 하나 — 전부 넘는 덱에서 squeeze 는 이제 rc 1(1판의
  빈 메시 거절)인데 tetremesh 는 여전히 rc 0 으로 절점 0 인 덱을 쓴다.
- **L-04 `LONG=Y` — 카드 리더 여덟**(카탈로그 58 op × 세 꼴 · `widerc.py`) — `I10=Y` 는 판에 든 두 거절(cad_solid_merge_to_deck ·
  apply_carryover_plan — 계획 sha 가 덱 바이트에 묶였다)뿐이다. `LONG=Y` 에서 rc 가 0 이 아닌 열여섯 가운데 아홉은 설계된 거절이다(convert ·
  refine · disconnect · offset · restack · rbe · meshfix 의 「long 포맷 덱 — 20 칸 서식을 확정하지 못했다」 · cad_solid_merge_to_deck ·
  apply_carryover_plan). 나머지는 제 카드 리더가 20 칸을 못 읽는 것이다 — cnrb2spring(「*CONSTRAINED_NODAL_RIGID_BODY 가 없습니다」) ·
  cclip(「*PART line for pid 2 not found」) · matswap · ale(「PID 1 not found」) · stackwrap · neutralaxis(「MID 의 E 를 못 읽었다」).
  cnrb2solid 는 rc 0 에 경고 한 줄(「NSID=0 not found」)로 솔리드 0 개 · 절점 25(표준 판 75)인 덱을 쓴다. info 는 rc 0 에 거짓 「[ERROR]
  정의되지 않은 것을 가리키는 카드 2건」 을 찍는다(`--strict` 면 rc 1). extract-parts 는 셋 다 rc 0 이다(2차 F-2).
- **L-04 정수 상한 — 넘친 번호를 rc 0 으로 쓰는 op 여덟**(`maxid.py` — `I10=Y` 덱에 번호가 2147483647 인 절점 넷 · 셸 · 파트 · 섹션 · 재질 ·
  세트를 더했다) — meshfix(새 절점 · 요소가 -2147483648 부터) · cnrb2solid(새 절점) · matswap(새 SECID) · boundary(새 세트) · ale(PID 2147483648
  · MID 음수) · iga(MID · `*PARAMETER_LOCAL`) · merge(새 MID — rc 1 이지만 덱은 쓴다) · cclip(보고의 `new_mid` · `new_secid`). 목록이 적은 자리
  가운데 cad_solid_merge_to_deck 은 칸 상한으로 막고, apply_carryover_plan 은 넓힌 덱이 계획 sha 와 달라 이 탐침으로는 재지 못했다. 앞서 고친
  tetremesh · id_floor 는 rc 1 이다. 처음 검사는 붙어 쓴 10 칸 셋을 큰 수 하나로 읽어 거짓으로 많이 셌다 — 칸 단위로 고쳐 다시 쟀다.
- **L-08 battery** — ① 주 덱이 `I10=Y` · `LONG=Y` 여도 use_include: true 는 rc 0 으로 맨 `*INCLUDE` 와 표준 폭 battery 덱(맨 `*KEYWORD` · 절점
  줄 56 자)을 붙인다. 우리 extract-parts 는 이 닫힘을 섞인 폭으로 거절한다. Vol_I 는 `*INCLUDE -` 가 인클루드 전체를 표준 폭으로 읽게 한다고
  적지만(LONG 덱일 때) I10 에는 인클루드 단위 되돌림이 없다 — LS-DYNA 가 맨 `*KEYWORD` 인클루드를 어떻게 읽는지는 못 쟀다(라이선스 만료). ②
  battery 뒤 extract_surface 의 `output_pid` 가 battery 파트 번호(11)면 셸 50 개가 battery 파트 11 에 rc 0 으로 들어간다. 주 덱 파트(솔리드 파트
  1)를 주어도 같다 — battery 만의 것이 아니다.
- **목록 밖** — assemble 의 extract_surface 는 새 `output_pid` 에 `*PART` 를 쓰지 않는다(정의 안 된 파트를 가리키는 셸 50 · rc 0). 단독
  extract-surface 는 `*PART` 를 쓰되 SECID 가 그 번호인 섹션이 없다. 매뉴얼 43.7 이 「옵션 세부 동작은 확인 필요」 라고 적은 자리다. applyfold
  경고의 숫자(`%+lld` 에 double)는 1판에서 넘긴 그대로다.
- **범위 추세** — 열 → 열셋 → 아홉 → 1판 열여덟 → 2판 다시 재기에서 새 묶음 둘(정수 상한 넘침 일곱 op · extract_surface 의 `*PART`). 1판에서
  넘긴 넷 가운데 셋(info 거짓 미정의 · applyfold 숫자 · `LONG=Y` 까닭 열여섯)이 이 판의 몫이다.
- **2판 결정(11-22)** — `LONG=Y` 카드 리더 여덟은 「여덟 다 읽게 고친다」(op 마다 카드 리더가 선언된 칸 폭으로 읽는다 · 합성 덱으로만 잰다).
  battery 인클루드 폭은 「battery 덱을 주 덱 폭으로 쓴다」. extract_surface `output_pid` 는 「셸 섹션까지 지어 넣는다」 — 있는 번호면 거절 · 새
  번호에 `*PART` 와 `*SECTION_SHELL`(ELFORM 2 · NIP 2 · 새 SECID · MID 는 셸을 뽑은 솔리드 파트의 것 · 다르면 rc 1)을 짓고, 두께 키는 assemble
  `thickness` · 단독 `--thickness` 로 새 번호면 필수(「thickness · --thickness · 새 번호면 필수」). 정수 상한 넘침 여덟 op 은 tetremesh ·
  id_floor 처럼 rc 1 로 거절한다(묻지 않았다 — 앞서 정한 꼴을 따른다).
- **차례(11-22)** — DF ② 계획을 먼저 쓰고 결함 판과 번갈아 짓는다(「② 계획을 지금 먼저」). 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서
  돌릴게」 — 판마다 멈추지 않고 짓고 올린다. 솔버로만 확인되는 줄은 cae00 검증런에 맡긴다.

## 8. 2판 짓기(2026-11-22)
- **묶음 1 — L-05 넷(`57f885c`)** — 폭 선언을 낱말로 · 첫 `*KEYWORD` 카드만(`*KEYWORD_ID` · `_JOBID` 포함) · 칸을 넘는 좌표를
  `formatRealField` 로 · 리더가 int 를 넘는 번호를 0 으로 읽던 것을 거절로 · applyfold 경고 숫자. 시험 `test_width_decl.py` 31 항(설치된 판
  빨강 23).
- **묶음 4 — L-04 정수 상한(`a0a494a`)** — 새 번호가 상한을 넘으면 쓰지 않는다(조립기 `bumpId` 84 곳 · `ids::IdAllocator` · 제 손으로 세는
  op 여섯). 시험 `test_id_cursor_limit.py` 74 항(설치된 판 빨강 17).
- **묶음 3 — L-04 `LONG=Y`** — 리더 여덟(cnrb2solid · cnrb2spring · cclip · matswap · ale · stackwrap · neutralaxis · info)이 선언된 폭으로
  읽는다. 고치며 쓰기 쪽 결함이 따라 나왔다 — 2판 탐침(카탈로그 58 op 을 표준 · LONG 으로 돌려 산출을 선언된 폭으로 읽기)이 rc 0 으로 LONG 덱에
  10 칸 카드를 끼우는 op 열다섯(elform · iga · merge · formstrain · matdb · load · boundary · contact · relax · stabilize · database · hfdamp ·
  implicit · modal · optimize)을 찾았다. 「여덟 다 읽게」 를 고르며 「새로 쓰는 카드도 덱의 폭으로」 를 같은 일로 보고 고쳤다(묻지 않았다 —
  리더만 고치면 그 덱을 다시 읽는 op 이 틀린 값을 읽는다). 새로 지은 카드는 표준 폭으로 지어 `widenGeneratedCards` 로 넓히고, 덱에서 베낀
  줄은 넓히지 않는다(붙어 쓴 표준 칸과 20 칸 값 하나를 글자로 가를 수 없어 「이미 넓혔나」 짐작은 뺐다).
- **곁 파일도 주 덱 폭으로(묻지 않았다 — battery 결정과 같은 꼴)** — Vol_I 「Long Format Input」 은 인클루드를 `*INCLUDE -` · `+` 가 없으면
  주 덱 폭으로 읽는다고 적는다. 맨 `*KEYWORD` 곁 파일(assemble 의 `.dynain` · 덱 내장 초기응력 · cclip dynain · squeeze · prestress 의 dynain ·
  IGA 인클루드 · 단독 extract-surface 의 셸 덱)은 LONG 덱이 물면 솔버가 20 칸으로 읽을 수 있다. 이제 주 덱이 LONG 이면 `*KEYWORD LONG=Y` 와
  20 칸으로 쓰고(`widenGeneratedDeck`), extract-surface 는 솔리드 덱의 폭(`I10=Y` 포함)을 밝힌다. IGA 파일이 베낀 재질 블록의 폭이 파일과
  다르면 키워드에 `+` · `-` 를 단다. 우리 리더는 파일마다 제 선언을 읽고 LS-DYNA 는 물려받든 제 선언을 읽든 같은 폭이 된다.
- **목록 밖 — `*INITIAL_STRESS_SHELL` 카드 1** — 덱 내장 · `.dynain` · cclip 셋이 `I10 + I8×7` 로 써서 여섯째 값(LARGE)이 다섯째 10 칸
  창(NTENSR)에 들어가 그 칸이 「0       0」 이었다(10-16 에 고친 `*INITIAL_STRESS_SOLID` 와 같은 결함 — 값이 모두 0 이라 뜻은 같았다). LONG 으로
  넓히면 그 칸이 그대로 옮겨져 드러났다. 10-16 꼴 그대로 `InitialStressCard.h` 의 `shellCard1` 하나로 쓴다(I10×8). 시험
  `test_initial_stress_card.py` 에 셸 자리 셋을 더했다(32 항 · 고치기 전 빨강 3).
- **죽은 참조 옮기기 · info** — merge 의 죽은 PID 옮기기(assemble 과 같은 `migrateDeadReferences` · `cleanupDeadNodeRefs` ·
  `scanDeadReferences`)가 10 칸으로만 잘라 LONG 덱에서 죽은 참조를 하나도 못 보고 rc 0 으로 두었다(`*MAT_ADD_THERMAL_EXPANSION` 의 PID 1 · 3).
  들머리에서 덱 폭을 정하고(`RsCardWidth`) 고쳐 쓰는 자리도 그 폭으로. info 의 섹션 · 재질 번호 모으기도 블록 폭으로 잘라 거짓 「정의되지 않은
  카드」 가 없어졌다(`--strict` rc 0).
- **시험** — `test_long_readers.py` 159 항(A 여섯 · B 둘 · C · D 나머지 사례 전부 — 거절 아홉은 rc ≠ 0, 그 밖은 산출 덱 · dynain · IGA 를 선언된
  폭으로 읽은 값이 표준과 같고 `LONG=Y` 를 싣는다) · `test_initial_stress_card.py` 32 항 · 단위 246.
- **커밋** — 묶음 3 `f01d10d`(회귀 139 / 139 · 단위 246).
- **묶음 5 — L-08 battery(`bd28bc4`)** — 「battery 덱을 주 덱 폭으로 쓴다」 그대로. 표준 폭으로 지은 battery 덱(번호를 옮긴 뒤)을 `toDeckWidth`
  로 주 덱 폭에 옮긴다 — I10 은 8 칸 칸(절점 번호 · TC · RC · 격자 요소 줄)만 10 칸, LONG 은 좌표 · 10 칸 카드까지 20 칸, 머리는 `I10=Y` ·
  `LONG=Y`. battery 가 쓰는 꼴(맨 `*NODE` · 한 줄 꼴 격자 요소 셋)만 알고 모르는 `*ELEMENT_` · `*NODE_` 꼴이면 rc 1(짐작해 넓히지 않는다). 펼침
  (use_include: false)의 거절을 뺐다 — 펼친 카드는 이미 주 덱 폭이라 다시 넓히지 않는다(처음 판은 `insertBeforeFirstEnd` 의 넓히기가 한 번 더
  돌아 40 칸이 됐다 — 시험이 잡았다). 시험 `test_battery_deck_width.py` 108 항(적층 기본 · dent · pouch 예압 · TSHELL · 에어백 · 권취 × 인클루드
  · 펼침 × I10 · LONG · 고치기 전 빨강 16).
- **묶음 6 — extract_surface `output_pid`(`04cd476`)** — 「셸 섹션까지 지어 넣는다」 · 「thickness · --thickness · 새 번호면 필수」 그대로.
  고르며 문장에 없던 셋은 결정 문장을 글자 그대로 읽었다(묻지 않았다 — 끝 보고에 적는다). ① 단독 extract-surface 의 기본값 `--output-pid 1` 은
  그대로 두었다 — 덱에 PID 1 이 있으면 거절된다(시험 넷 · 도움말 사례 둘이 새 번호 · 두께를 준다). 기본값을 「최대값 위 새 번호」(assemble 과
  같은 꼴)로 바꿀지는 사용자 몫이다. ② `*PART` 가 없는 메시(`generate arc` 의 덱)는 셸을 뽑은 파트의 MID 가 0 이라 0 을 옮기고 경고한다 —
  「파트의 MID 를 옮긴다」 를 그대로 읽었다. 멈추면 `generate arc → extract-surface → shellmap` 길(도움말 사례 · 시험 넷)이 막힌다. ③ assemble
  의 `LONG=Y` 덱은 요소를 더하는 assemble op 의 설계된 거절 그대로다. 고치며 찾은 것 — assemble 의 저절로 고른 번호가 `*PART` 없는 메시에서 요소
  PID 1 과 겹쳤다(파트 커서가 `*PART` 카드만 센다) — 쓰는 번호를 건너뛰게 했다. 시험 `test_extract_surface_part.py` 51 항(설치된 판 빨강 18).
  카탈로그 예제(볼트 덱)는 PID 1 이 셸 파트라 `pid: 200` 을 주었다.
- **묶음 2 — L-05 unfold 두께 셸(`1b67f87`)** — 격자로 다시 지을 때 입력이 두께 셸이던 요소는 모서리마다 굽은 절점을 짝지어 입력 차례로
  다시 놓고, 평판에서 뒤집히면 면 안의 감김만 되돌린다. z 축 상자도 아랫면 · 윗면이 뒤바뀌어 있었다. 시험 `test_unfold_tshell_axis.py`
  27 항(상자 · 원호 × 두께 축 셋 · 고치기 전 빨강 8). L-05 의 정수 상한 꼬리(tetremesh 가 절점 0 인 덱을 rc 0)는 묶음 1 의 리더 거절로 rc 1
  이 됐다(검토 탐침 덱 셋으로 다시 쟀다).
- **목록 밖(고치지 않음)** — 단독 extract-surface 의 셸 EID 는 1 부터다(매뉴얼 3.1(h) 가 「별도 덱 — 원 덱에 들이면 겹친다」 로 적은 그대로).
- **변이(`$S/g3/mut/mutate4.py` · `mutate4b.py`)** — 2판 고침 39 자리를 하나씩 되돌려 다시 짓고 그 자리를 지키는 시험을 돌렸다. 1차 빨강 28.
  살아남은 열하나 가운데 아홉은 시험이 그 길을 타지 않았다 — 덱 내장 초기응력 · DR 카드 · cclip 곁 dynain · 표준 인클루드의 IGA 재질 · IGA 칸
  자리(낱말로 견주어 못 봤다) · matswap 옛 꼴 · battery I10(낱말로 되돌려 어긋난 칸이 같아 보였다) · 공용 발행자 상한(사례 덱에 접촉이 없다) ·
  폭 선언 낱말(변이가 옛 결함을 그대로 되살리지 않았다 — 고쳐 다시). 시험을 더해(`bea26db`) 2차 10 / 10 빨강. 둘은 같은 뜻 · 닿지 않는 길이다 —
  인클루드를 펼칠 때 뒤 `*KEYWORD` 를 빼는 줄(리더가 이제 첫 카드만 읽는다) · merge 의 새 세트 블록 넓히기(merge 는 새 세트를 짓지 않는다 — tied
  소비자는 보고만). 시험을 더하다 하나를 더 찾아 고쳤다 — 죽은 PID 옮기기의 열 꼴 세트 줄을 10 칸으로 고쳐 써 LONG 덱의 PID 칸이 어긋났다.
- **전체 재기(dev 판 `1e73e714` · `bea26db`)** — 단위 246 / 246 · 백엔드 1078 통과 · 4 실패(작업 트리에 `.env` 가 없어 supervisor_log 넷 — 앞
  판과 같다) · MCP 계약 13 / 13 · 회귀 142 / 142(파일 크기 상한 없이 — 새 시험 일곱 포함).

## 9. 올리기 기록(2판 — 2026-11-22)
- **올리기(11-22 04:06 ~ 04:28Z — DF 2차 ② 와 같은 판)** — main `a50bcc3`(ff — 뒤에 cae00 문서 `cc480c7`) · 주 체크아웃 ff · 도는 잡 0(04:06 ·
  04:15 두 번) · pykoocae-53 에 빌드 앞 알림 · 호환 빌드 (빌더 컨테이너 · -j8 · 프로세스 8 GB 상한) rc 0 · glibc 2.35 ·
  `1106bef1d4ef0e4dca215f62247359962120dae9147f92e7901c75aba52ad62a`(9,095,464 바이트) · 호환 단위 246 / 246 · 호환 회귀 142 / 142 · 설치
  04:15:46Z(`build/linux/bin` · `platform/backend/bin`) · migrate 0022 그대로(dev 는 ② 때 올렸다) · API 04:16:08 · MCP 04:16:17(`start.sh` —
  `/data` 바인드 있음) · 스모크 MCP PASS(도구 97 · 연산 65) · deckops 29 / 29 · allops 64 / 64(건너뜀 1) · reports 59 / 59 · 주 체크아웃 백엔드
  1094 통과 · 실패 0 · cli.sif 04:22:32(안 바이너리 `1106bef1`) · Drive `dist-20261122-042305Z`(게시 04:23:08Z · 다른 파일은 BUILD_INFO ·
  koorm-bin.tar.gz · cli.sif 셋 — 나머지 SIF 와 콘솔 묶음은 sha256 같음 · 가장 오래된 `dist-20261115-093042Z` 정리 — 남은 판 11-17 · 11-21 낮 ·
  11-21 밤 · 11-22) · 게시 뒤 health `revision` `a50bcc3` · `revision_matches_binary` true · cae00 문서 §1-9(`cc480c7`) · 알림 여섯(pykoocae-53
  설치 뒤 · hwaxportal-71 전문 · hwaxportal-87 짧은 판 · smarttwinmcp-c8 · stepforge-d4 · kooremapper-fd). 되돌릴 판은
  `dist-20261121-234834Z`(코드 `98f5ec6` · 바이너리 `d1e2ce96`).

## 10. 3판 짓기(2026-11-22)
- **차례** — 판마다 멈추지 않는다(「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」). 항목마다 설치된 판(`1106bef1`)에서 빨간 시험을
  먼저 짓고 고쳤다(아래 「빨강」 은 설치된 판에서 실패한 항 수). 사용자에게 물을 갈림길은 TMID 하나(아래)이고, 결정 문장 없이 고른 것은 「고른
  것」 에 적는다.
- **L-10(`65e9af4`)** — 섹션 묶음 가르기를 블록 · 묶음 단위(`cur_cardSetBlocks`)로 펴서 섹션 훑기 · 모래시계 훑기 · 묶음째 지우기가 같이 쓴다.
  matswap(YAML · 옛 자리 인자) · cclip 은 그 번호의 묶음만 지우고(블록이 비면 블록째 · 줄 수를 모르는 묶음은 두고 알린다) 새 SECID · HGID 는
  쌓인 묶음까지 센 최대값 위로(ale 도). 시험 `test_stacked_cards.py` 16 항(빨강 7).
- **L-11(`9997051`)** — matdb 의 재질 훑기를 공용 재질 훑기(`matids::scan`) 위로 — 쌓인 둘째 재질도 제목 · `mid:` 로 고른다. 지우기만 하는 고아
  재질의 MID 꼴 덧붙임을 지운다. 시험 `test_matdb_stacked.py` 10 항(빨강 3).
- **L-12(`70aa955`)** — 리더가 `*MAT_ELASTIC` · `_PIECEWISE_LINEAR_PLASTICITY` · `_RIGID` 의 쌓인 묶음을 다 읽는다(빈 카드 · 빈 제목 줄도 카드 ·
  제목). iga 는 꼴을 모르는 재질 뒤에 다른 재질이 쌓였으면 rc 1(`stackedNeighborAfter`). ale 사용자 재료 파일은 첫 구조 재질 묶음 하나를 베낀다.
  LONG 덱의 2차 솔리드를 미리 훑기 · 요소 색인이 블록 폭 · 쌓인 섹션 묶음까지 본다. 시험 `test_material_sets.py` 9 항(빨강 5).
- **L-16(`e087c42`)** — rbe 의 CNRB PID 는 공용 파트 커서로, matdb 의 감쇠 세트는 공용 세트 커서로 낸다. 세트 훑기 사본 둘을 `cur_setIdsIn`
  하나로. 시험 `test_shared_cursors.py` 6 항(빨강 3).
- **L-15(`6590fa8`)** — `*MAT_T` 뒤에 숫자가 오는 철자를 다 열 재질로(`T1` · `T19` · `T001`). extract-parts 는 PID 꼴 `*MAT_ADD_*` 를 고른 PID
  와 견준다. `*PART +`(칸폭 표지)를 맨 파트로 — 참조 검사가 변형으로 보아 섹션 · 재질을 안 봤고, 요소 색인이 ELFORM 23 을 몰라 20 절점 솔리드의
  셋째 줄을 새 요소로 읽었다(「파트 12 미정의」 · 목록 밖이지만 같은 자리라 같이). info 가 *PART 의 TMID 를 본다. 시험
  `test_thermal_spelling.py` 18 항(빨강 12).
- **TMID 는 의심 줄로(`75eb65e` — 처음 판을 바로잡음)** — 처음 판은 없는 TMID 를 미정의(`--strict` rc 1)로 막았다. `/data` 표본에 대 보니
  battery 덱 11 장이 새로 막혔고, 그 가운데 열 재질 101 ~ 106 · 108 만 있고 *PART 가 TMID 107 을 가리키는 덱(`case_01_phase1_stacked_tier-1`)의
  d3hsp 가 정상 종료다. 열 재질이 하나도 없는 덱(TMID 106)도 키워드 단계를 지나 1 주기까지 돌았다(다른 까닭 — 음의 부피로 멈춤). Vol I *PART
  TMID 도 「열 · 열-구조 연성 해석이면」 모든 파트의 열 물성을 요구한다. 그래서 rc · `--strict` 와 무관한 의심 줄로 낮췄다. 열 해석
  덱(`*CONTROL_SOLUTION` SOLN 1 · 2)에서만 미정의로 올릴지는 솔버로 재지 못해(라이선스 만료) 사용자에게 묻는다.
- **섹션 묶음 셈의 메모리(L-15 넷째)** — 읽은 근거가 미룬 목록 한 줄뿐이라 코드에서 찾았다. `cur_cardSetBlocks` 가 모든 블록(수백만 줄의 `*NODE`
  포함)의 줄 번호 목록을 만든 뒤 고르지 않은 블록을 버렸다 — 고른 블록만 만든다. 300 만 절점 덱(171 MB)의 info --strict 를 glibc memusage 로
  재면 힙 누계 4,458 → 4,324 MB, 힙 최고치 803 MB · 최대 RSS 854 MB 는 그대로다(그 목록은 최고치 아래에서 났다 사라졌다).
- **L-09(`e548a1b` · `72a5c9a` · `907b7dc`)** — `--strict` 의 SECID · MID 겹침을 공용 묶음 셈(`sectionDefinitionLines` · `matids::scan`)으로 —
  쌓인 묶음의 겹침을 잡고, `_TITLE` 의 빈 제목 줄을 건너뛰어 둘째 카드를 번호로 읽던 거짓 겹침이 없어졌다. `*SET_*_TITLE` 의 빈 · 들여 쓴 제목
  줄도 제목. 섹션 훑기 둘(카드 묶음 셈 · 옛 첫 카드 셈)과 세트 정의 수집이 1열의 `*` · `$` 만 키워드 · 주석으로 본다. 시험
  `test_strict_stacked_duplicates.py` 12 항(빨강 8) · 이월 적용 L-4f(빨강 1 — 옛 첫 카드 셈은 이월 적용의 「섹션이 있나」 가 쓴다).
- **고른 것(묻지 않았다)** — ① PID 꼴 덧붙임은 `isMidKeyedAddOn` 밖의 `*MAT_ADD_*` 전부다(matswap · cclip 의 지우기와 같은 목록 — 새 MID 꼴
  덧붙임이 나오면 그 목록에 더한다). ② `*MAT_T` + 숫자 철자를 LS-DYNA 가 받는지는 못 쟀다 — 우리 판정만 넓혔다. ③ `*MAT_NONLOCAL` 은 겹침에서
  예전처럼 뺀다(제 번호 체계).
- **세트 커서도 1열 규칙(`469962e`)** — 공용 세트 커서 `cur_setIdsIn`(L-16 에서 둘을 모았다)이 첫 비공백 `*` · `$` 를 키워드 · 주석으로 보아
  제목이 「  *rim」 · 「  $rim」 인 세트의 SID 를 못 세었다 — matdb 감쇠의 새 세트가 그 번호를 다시 냈다(L-09 와 같은 꼴이라 이 판에서 고쳤다).
  설치된 판은 감쇠 세트를 옛 관례(800000 대)로 내 이 자리를 안 타서 변이 둘로 잰다.
- **목록 밖(고치지 않음)** — offset 이 솔리드 파트의 바깥면 전부를 한 방향(+z)으로 밀어 옆면 요소가 뒤집힌다(상자 8 요소에서 새 28 · 음의
  야코비안 12 · 「warping 180°」 경고) — 시험 덱의 꼴이고 설치된 판도 같다. 설계 범위를 몰라 적어만 둔다.
- **대조** — 저장소 예제 · 시험 덱 339 장 · `/data` 표본 521 장(60 MB 아래 4,166 장에서 여덟 장마다 하나)을 설치된 판과 새 판의 info --strict 로
  — rc · 확정 줄(겹침 · 미정의)이 바뀐 덱 0. 새 의심 줄 「열 재질(TMID)」 은 저장소 0 장 · `/data` 11 장(외부 battery 생성기 덱).
- **변이(`$S/r3/e3/mut/mutate5.py`)** — 3판 고침 35 자리를 하나씩 되돌려 다시 짓고 그 자리를 지키는 시험을 돌렸다. 1차 빨강 28. 살아남은 일곱은
  시험이 그 길을 보지 않았다 — matswap 두 꼴 · cclip 이 바꾼 파트의 옛 섹션 · 모래시계 묶음을 지웠나(넷 — 남아도 덱은 서서 「겹침 없음」 만
  봤다), ale 가 새 SECID 를 내는 덱(섹션을 나눠 쓰지 않으면 제자리에서 고친다), 재료 파일에 구조 재질이 둘일 때 첫 것인가, 덱에 CNRB 가 있을
  때의 새 CNRB PID. 시험을 더해(`f8c2440` · `469962e`) 2차 9 / 9 빨강(세트 커서 둘 포함 — 모두 37 자리).
- **전체 재기(dev 판 `d470c920` · `30fb0b0`)** — 단위 246 / 246 · 회귀 148 / 148(새 시험 여섯 포함) · 백엔드 1078 통과 · 4 실패(작업 트리에
  `.env` 가 없어 supervisor_log 넷 — 앞 판과 같다) · MCP 계약 13 / 13.

## 11. 올리기 기록(3판 — 2026-11-22)
- **올리기(11-22 06:0x ~ 06:3xZ — DF 2차 ③ 과 같은 판)** — main `6ac6e70` → `2cbdc84`(ff — 뒤에 cae00 문서 `ae8a62e`) · 주 체크아웃 ff ·
  pykoocae-53 에 빌드 앞 알림 · 호환 빌드(빌더 컨테이너 · -j8 · 프로세스 8 GB 상한) rc 0 · glibc 2.35 ·
  `4b8fe975202d9103c9c69c5530ea20c2d9bf72617139b26de9ed04368e86cc85`(9,131,568 바이트) · 호환 단위 246 / 246 · 호환 회귀 148 / 148 · 도는 잡 0 ·
  설치 06:20:57Z(`build/linux/bin` · `platform/backend/bin`) · dev DB 0022 → 0023 · API 06:21:10 · MCP 06:21:31(`start.sh` — `/data` 바인드
  있음) · 스모크 MCP PASS(도구 100 · 연산 65) · deckops 29 / 29 · allops 64 / 64(건너뜀 1) · reports 59 / 59 · DF ③ 탐침 18 / 18(만든 캠페인 ·
  세션 지움) · 주 체크아웃 백엔드 1106 통과 · 실패 0 · cli.sif 06:28(안 바이너리 `4b8fe975`) · Drive `dist-20261122-062855Z`(게시 06:28:59Z ·
  다른 파일은 BUILD_INFO · koorm-bin.tar.gz · cli.sif 셋 · 가장 오래된 `dist-20261117-212938Z` 정리 — 남은 판 11-21 낮 · 11-21 밤 · 11-22 새벽 ·
  11-22 낮) · 게시 뒤 health `revision` `2cbdc84` · `revision_matches_binary` true · cae00 문서 §1-10(`ae8a62e`). 되돌릴 판은
  `dist-20261122-042305Z`(코드 `a50bcc3` · 바이너리 `1106bef1`).

## 12. 4판 짓기(2026-11-22)
- **차례** — 3판 · DF ③ 을 올린 뒤 바로 열었다(「계획한건 전부 만들고」). 판을 열 때 다시 재는 규칙대로 줄마다 카탈로그 사례 전부를 설치된
  판(`4b8fe975`)과 새 판으로 돌리는 탐침을 먼저 짰다 — 희소 인클루드(`l01_sweep`) · 산출 자리 /dev/full · /dev/zero · 폴더(`l18_sweep` ·
  `l19_sweep`).
- **L-01(`3e21444`)** — 474 바이트 꼴 주 덱이 40 GB 희소 인클루드를 끌면 카탈로그 op 59 가운데 덱을 읽는 57 이 주소 공간 상한(8 GB)이 허락하는
  4.1 GB 까지 읽고 rc 0 이었다(상한이 없으면 박스 메모리를 다 쓴다 — earlyoom 이 남을 죽인다). 닫힘 읽기가 파일을 열기 전에 크기를 보아
  `include_closure::TooLarge` 를 던지고 main 이 까닭을 찍고 rc 1. 고친 판으로 57 op 이 다 열기 전에 멈춘다(최대 RSS 500 MB 아래). 시험
  `test_include_size_gate.py` 6 항(빨강 5 · 주소 공간 2 GB 상한 안에서).
- **L-06(`459bbac` · `c9a12b1`)** — 주 덱이 `*INCLUDE_PATH` 로 찾던 `part.k` 를 산출 이름으로 주면(주 덱 폴더 · 다른 폴더) 산출 덱이 같은 카드를
  실어 자기 자신을 끌어오는데 rc 0 이었다. 공용 관문의 입력에 인클루드 이름(찾은 경로와 함께)을 싣고, 쓸 파일이 제 폴더에서 그 이름 자리인데
  원래 다른 파일을 가리켰거나 못 찾은 이름이면 거절한다. 조립기는 in-place 모델 몫에서 경로만 빼고 이름은 남긴다 · 펼친 산출은 이름을 비운다.
  매뉴얼 (j) 과 카탈로그 op 55 곳의 「다른 폴더의 같은 이름은 덮어쓴다」 에 예외를 붙였다. ★단위 시험 하나(「다른 폴더의 inc.k 는 거절하지
  않는다」)가 뒤집힌 전제였는데 `459bbac` 메시지에 「단위 246」 이라 적었다 — 실제 245 / 246 이었고 `c9a12b1` 에서 단언을 새 계약으로 고치며
  바로잡았다(결과를 보기 전에 커밋한 탓).
- **L-13(`570ca67` · `b42ce03`)** — 플랫폼 실행기가 잡이 끝날 때마다 세션 작업 폴더에서 10 분 넘게 건드리지 않은 `*.kr_tmp_*` 를 지운다(같은
  세션 로컬 잡은 한 줄로 돌지만 올리기 검사 modelmeta 가 같은 폴더에서 바이너리를 부른다 — 새 것은 둔다). Windows 두 자리(meshfix 관문에
  `__mf.log.bat` · 같은 파일 판정이 대소문자 무시 — `pre.K` · `pre.k`)는 이 박스에 툴체인이 없어 `-D_WIN32 -fsyntax-only` 로 문법만 봤다.
- **L-18(`2391a38` · `0e4d8da`)** — ① `batteryTakenSpans` 의 요소 번호 모으기가 색인(줄마다 18 바이트)을 짓지 않게 요소 카드 걸음(`ecWalk`)을
  떼었다 — 300 만 절점 덱 battery 의 힙 누계 7,058 → 7,004 MB · 최고치 1,306 MB 그대로 · 산출 sha 같음. ② 산출 자리를 /dev/full 로 바꾸면 75
  자리 가운데 12 자리가 rc 0 이었다 — `finishDeckFile` 을 `deck_write::finish` 로 옮기고(두 번째 소비자) 그 자리들과 meshfix STL · geo · CSV
  둘이 닫으며 본다. 읽어 대조하려는 임시 파일(펼친 덱 · 조각 블록 · polish 패치)은 견디고 물러선다. 시험 `test_write_errors.py`(빨강 12).
- **L-19(`0e810e3` · `626d9d5`)** — 산출 자리를 /dev/zero 로 바꾸면 되읽는 squeeze · stackwrap 이 60 초 한도에 걸렸다(한도가 없으면 끝없이) — 그
  둘만 쓰기 전에 거절한다(`/dev/null` 마른 실행 계약은 그대로라 장치를 통째로 막지 않는다). 폴더로 바꾸면 cclip 보고만 rc 0 이었다(못 열면
  조용히 건너뛰었다) — rc 1 · 75 / 75. 디스크 참 시험에 map 산출 · extract-parts 보고를 더했다(32 항). 시험 `test_output_slot_kinds.py`(빨강 3).
- **L-20(`7d8c7f3`)** — meshfix 가 gmsh 앞 단계(STL · 다듬기 · 쪼개기 · .geo)에서 멈추면 이 실행의 `.kr_tmp_mf.*` 를 지운다(`.geo` 자리를 폴더로
  막으면 설치된 판은 `.stl` · `.geo` 둘을 숨긴 채 남겼다). 시험 `test_meshfix_temp_cleanup.py`(빨강 1).
- **고른 것(묻지 않았다)** — ① L-01 문턱: 줄로 담으면 바이트 합 × 9(StepForge D-684 와 같은 값), 흘려 읽으면 파일 하나 × 4, 남은 메모리를 못
  읽으면 보지 않는다. ② L-06: 못 찾은 이름도 막는다 · `.dynain` 은 보지 않는다(map + prestress 고리) · 쓸 파일이 덱이 아닌데 이름이 인클루드
  이름과 같으면 거짓으로 걸릴 수 있다(드물다). ③ L-13: 10 분. ④ L-19: 되읽는 자리만 막는다. ⑤ L-20: 살펴보라고 남기지 않고 지운다(gmsh 앞에서
  멈춘 까닭은 글이 댄다).
- **목록 밖(고치지 않음)** — `exportStressDistribution` 은 부르는 곳이 없다(죽은 코드). 요소 카드 걸음(`ecWalk` · 옛 `ecBuildIndex`)은 첫 비공백
  `*` 를 키워드로 본다(1열 규칙과 어긋남 — 들여 쓴 `*` 줄이 요소 블록을 끊는다). extract-parts 는 보고 쓰기 실패를 두 번 찍는다.
- **변이(4판)** — 1차 19 가운데 빨강 14. 살아남은 셋(`.dynain` 제외 · 인클루드에만 있는 요소 · prestress `--csv` 의 쓰기 실패)과 변이 글이
  빌드를 깬 둘에 시험 · 글을 고쳐(`b16b3ec`) 2차 5 / 5.
- **전체 재기(4판)** — 회귀 153 / 154. 남은 하나는 ofstream 전수 선언이 `deck_write::finish` 의 매개변수를 새 자리로 센 것이라 선언 수만
  올렸다(`f165537` — 4판 고침의 빨강이 아니다). 올리기는 5판과 한 판으로 한다(14절).

## 13. 5판 짓기(2026-11-22)
- **차례** — 4판 전체 재기를 돌리는 동안 열었다. 판을 열 때 다시 재는 규칙대로 기본 설정 덱을 `info --strict` 로 먼저 쟀다.
- **L-07(`511a915`)** — 적층 기본 덱의 전해질 PART 13 이 공기주머니에서만 적는 MID 8 을, side 의 SPC 가 짓지 않은 바닥판 세트 3 을
  가리켰다(LS-DYNA 는 키워드 단계에서 멈춘다 · battery rc 0). 전해질은 Electrolyte_Solid, side 는 권취처럼 바닥판도 짓는다. 선택을 하나씩 바꿔
  (적층 · 권취 × 열둘 × mode 넷 + nail) 같은 꼴 셋을 더 찾아 같이 고쳤다 — no_impactor 의 SPC · 처방 운동이 없는 세트 2 · 3 · 권취 core_fill
  전해질이 없는 섹션 33 · 모르는 mode(`nail`)는 적층이 압입자 없이 세트를 묶고 권취는 움직이지 않는 압입자를 지었다(이제 rc 1). 96 덱 모두
  strict rc 0. 시험 `test_battery_deck_refs.py` 25 항(빨강 17).
- **L-14(`0a28ef3`)** — ① 보 옵션 카드(SN · MN) 절점을 Card 1 처럼 칸 읽기 · 다른 읽기(공백 토큰 · 못 읽은 줄의 정수)로 가른다 — cleanup-nodes
  는 둘 다 지키고 못 읽은 줄을 [WARN], extract-parts 는 다른 읽기만 말하는 절점을 덱(`*NODE` · 스칼라 절점)에 있으면 싣는다. ② cleanup-nodes
  되읽기가 keep · 모르는 키워드 · 못 읽는 세트 변종 · 못 읽은 보 족 줄로 지킨 절점도 잰다(`verify.undefined_kept`). ③ 적층 탭이 셀 끝을 넘으면
  [WARN] 이 지은 범위를 댄다. ④ cnrb2solid 아홉 자리를 1열 규칙으로. 시험 `test_option_card_readings.py` 8 항(빨강 6) ·
  `test_cnrb2solid_indented_star.py` 3 항(빨강 2).
- **L-17(`c9a8890`)** — Card A 의 SBOPT 를 정수 칸(Vol_I 형 I)에 `3.000` 으로 썼다 → `3`(LS-PrePost 는 둘 다 3 · LS-DYNA 로는 못 쟀다). 카탈로그
  `contact.soft` 「always 1」 · `contact.depth` 설명은 두 키가 읽기만 하고 덱에 쓰이지 않는다고 바로 적었다. 시험은
  `test_battery_contact_optional_cards.py` 에 SBOPT 칸 넷(빨강 4).
- **변이(5판)** — 1차 17 가운데 빨강 16. 살아남은 #15(cnrb2solid 절점 훑기)에 「  *NODES_bolt」 사례를 더해(`ff6899a`) 다시 1 / 1. 새
  되읽기(L-14 ②)는 두 겹 변이로 쟀다 — resolve 가 모르는 키워드를 지키지 않게 하면 rc 1 · `undefined_kept` 1, 새 되읽기까지 끄면 rc 0.
- **고른 것(묻지 않았다)** — ① 모르는 mode 는 rc 1(카탈로그 enum · rbe `mode: bogus` 와 같은 처리). ② no_impactor 면 SPC · 처방 운동을 쓰지
  않는다(셀을 묶는 경계를 지어 넣지 않는다). ③ core_fill 섹션은 `solid_elform` 을 따른다. ④ 옵션 카드의 다른 읽기는 공백 토큰 ∪ (못 읽은 줄이면)
  정수 전부 — Card 1 과 같은 넘치게 세기. ⑤ 탭 경고는 탭마다 한 번. ⑥ `contact.soft` · `depth` 는 글만 고쳤다(덱에 쓰게 할지는 물음).
- **목록 밖(고치지 않음)** — 권취 `batch.phase_modes` 의 swell 판이 압입자 · 바닥판 · PCM · 탭을 SPC 없이 싣는다(단독 `mode: swell` 은 뺀다 —
  고치면 phase 2 의 dynain 사슬이 읽는 phase 1 덱이 바뀌어 물음으로 남긴다) · 적층도 그 판에 PCM · 탭을 싣는다 · 다듬은 줄의 `*` 를 키워드로
  보는 꼴이 contact_helpers · cclip · matswap · merge · optimize · modelmeta 에 남았다 · battery tied 접촉의 Card 3 을 정수꼴로 써 `info` 가
  「손상 의심」 둘을 낸다 · `contact.soft` · `depth` 는 읽기만 한다.
- **범위 추세(5판)** — 목록 줄 셋을 고치며 같은 판에 들인 것 셋(no_impactor · core_fill · 모르는 mode — L-07 과 같은 꼴) · 남긴 것 다섯(위 줄).
- **재기(4 · 5판 한 판)** — dev 판 `d792e04f` 로 전체 회귀 157 / 157(4판 새 시험 여섯 · 5판 넷 포함) · 단위 246 / 246 · 작업 트리 백엔드 1092
  통과 · 4 실패(`.env` 없는 supervisor_log — 환경 탓) · 건너뜀 12 · MCP 계약 13 / 13(주 체크아웃 것으로).
