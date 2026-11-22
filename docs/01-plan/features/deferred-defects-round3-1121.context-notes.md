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
