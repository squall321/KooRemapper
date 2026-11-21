# 미룬 결함 2차 — 사용자 결정 넷을 짓고 main · Drive 까지 올린다 (2026-11-20)

체크리스트 `deferred-defects-round2-1120.checklist.md` · 맥락 `deferred-defects-round2-1120.context-notes.md`. 1차는
`deferred-defects-1120.plan.md`(F-1 unfold 관문 · F-2 extract-parts `LONG=Y`), 캠페인 적재는 `df-campaign-intake-1120.plan.md` 다.

## 0. 범위(사용자 지시를 읽은 것)
- 11-20 「필요하면 나한테 선택지를 줘 … 니가 다 수정하고 테스트까지 잘 되면 모두 리포지토리 합쳐서 빌드하고 설치하고 sif만들어서 드라이브로
  보내는거까지 해」. 선택지 넷을 냈고 답은 아래와 같다(고른 선택지의 설명 문장이 규격이다).
  1. 캠페인 이름 · 규칙 — 「지은 그대로」. 이름 여섯 · 상태 넷 · 목록에 없는 `run_key` 거절 · 같은 `run_key` 에 다른 내용 거절 · 만든 사람만
     본다. 고칠 것이 없다(`6c17926` 그대로).
  2. 리포트 상한 — 「줄만 세운다」. 상한은 그대로 두고 파싱만 한 번에 하나로 한다.
  3. 폭 섞인 덱(1차 C-4) — 「거절한다」. rc 1 과 까닭 글로 멈춘다.
  4. 결함 범위 — 「★ 셋 + 위상 전파 모두」. ★ 셋은 tetremesh 가 같은 EID 솔리드를 잃고 8절점 셸을 4절점으로 쓰는 것 · `_THICKNESS` 값을 버리고
     i10 을 8칸으로 쓰는 것 · id_floor 의 `elem_start` 가 int 범위를 넘는 것이다. 위상 전파는 1차 계획 2절의 B 다. 미룬 목록의 나머지 열 줄
     남짓은 이번 범위가 아니다.
- 올리는 데까지 — 고침과 시험이 끝나면 `corelink-int` 를 main 에 합치고, 호환 빌드 · 바이너리 설치 · dev DB 0021 · 재기동 · 스모크 · cli.sif ·
  Drive 게시까지 한다. 재기동과 설치는 살아 있는 잡을 확인한 뒤에 한다. SmartTwinPreprocessor SIF 는 pyKooCAE 쪽이 굽는다 — 새 바이너리
  지문을 알린다.
- **묻지 않고 함께 고치는 것**(최종 보고에 추세와 함께 적는다) — ★ 셋을 재다가 같은 쓰기 함수(`KFileWriter`)에서 목록에 없던 조용한 변질
  넷(N-1 ~ N-4 · 1절)이 나왔다. ★ 고침이 그 함수의 폭 규칙과 셸 처리를 바꾸므로 따로 떼면 틀린 덱을 새로 내게 된다(예 — tetremesh 가
  `*KEYWORD LONG=Y` 를 선언하면서 절점 좌표를 16칸으로 쓴다). C-4 관문은 long 뿐 아니라 I10 이 섞인 두 꼴(h · i)도 같은 규칙으로 거절한다.

## 1. 잰 것(바이너리 = `6285f42` 로 지은 `build/dev`)
| 꼴 | 지금 |
|---|---|
| T-1 tetremesh — 셸이 솔리드와 같은 EID | rc 1 · 산출 없음(DF-14 거절이 이미 막는다 — 닫힘) |
| T-2 tetremesh — 8절점 `*ELEMENT_SHELL` | rc 0 · 산출은 4절점 셸 |
| T-3 tetremesh — `*ELEMENT_SHELL_THICKNESS` | rc 0 · 산출은 맨 `*ELEMENT_SHELL`(두께 값 없음) |
| T-4a tetremesh — `*KEYWORD I10=Y` 작은 번호 | rc 0 · 산출은 맨 `*KEYWORD` 8칸(선언이 사라진다) |
| T-4b tetremesh — I10 큰 번호 | rc 0 · 8칸에 9자리가 붙은 깨진 덱 |
| I-1 id_floor — 요소 번호 2147483647 | rc 0 · `elem_start` 2147483648 |
| unfold — I10 · long 입력 | rc 0 · 산출은 맨 `*KEYWORD` 8칸(같은 `writeFile` 길) |
| N-1 map · squeeze — `*KEYWORD LONG=Y` | rc 0 · 절점 줄 68자(I20 + E16 셋 — 규격은 I20 + F20 셋 = 80) |
| N-2 squeeze — I10 덱 + 10칸 셸 1001 ~ 1005 | rc 0 · 솔리드 10 이 빠진다(셸 EID 를 8칸으로 잘라 「10」) |
| N-3 squeeze — 표준 덱 + `*ELEMENT_SHELL_THICKNESS` | rc 0 · 두께 줄 앞 8자가 수로 읽히면 그 번호 솔리드가 빠진다(1.0 → 1 · 2.5 → 2 · 37.0 → 3) |
| N-4a squeeze — 리더가 안 읽는 `*ELEMENT_TSHELL_BETA` 가 솔리드와 같은 EID 1 ~ 5 | rc 0 · 솔리드 1 ~ 5 가 빠진다 |
| N-4b squeeze — 같은 블록 · 먼 EID · BETA 45.0 | rc 0 · 솔리드 45 가 빠진다 |
| N-4c squeeze — `*ELEMENT_SHELL_COMPOSITE` 가 솔리드와 같은 EID | rc 0 · 솔리드 1 ~ 5 가 빠진다 |
| extract-parts h — 표준 주 덱 + 제 `*KEYWORD I10=Y` 인클루드 | rc 0 · 폭이 섞인 산출 |
| extract-parts i — I10 주 덱 + 제 맨 `*KEYWORD` 인클루드 | rc 0 · 폭이 섞인 산출 |
| extract-parts j · k · l · m(폭이 맞는 넷) | rc 0 · 폭 일치 |
| tetremesh — `*ELEMENT_SOLID_ORTHO` · `*ELEMENT_BEAM` 블록 | rc 0 · 산출에 없다(메시만 쓰는 계약 그대로 — 결함이 아니라 한계) |

- 추세 — ★ 셋 가운데 T-1 은 이미 닫혀 있었고, 재는 동안 목록 밖 결함이 넷(N-1 ~ N-4) · C-4 쪽에서 둘(h · i)이 더 나왔다. 여섯 다 이번
  커밋들이 들인 것이 아니라 전부터 있던 것이고(`248ec9bc` 와 같은 동작), 여섯 다 「폭을 한 자리에서 정하지 않는다」 · 「원본 글을 두 번째
  해석기로 다시 읽는다」 는 두 뿌리에서 나온다.
- 코드로만 읽은 것(돌려 보지 않았다 · 이번에 고치지 않는다) — `cnrb2solid` · `cnrb2spring` 의 절점 쓰기도 번호만 덱 폭을 따르고 좌표는 16칸으로
  못 박혀 있다(`cnrb2solid.cpp:401` · `cnrb2spring.cpp:632`). long 덱에서 N-1 과 같은 꼴일 수 있다. 미룬 목록에 적는다.

## 2. 설계
### 2-1. 파싱 줄 세우기(「줄만 세운다」)
`df-campaign-intake-1120.plan.md` 9절에 적는다.

### 2-2. 폭 섞인 인클루드 거절(C-4)
- 규칙은 고쳐 쓰는 op 의 `flatten_includes` 가 이미 쓰는 것(`include_closure::inlined`)과 같다 — 어느 파일에든 `*INCLUDE +` · `*INCLUDE -` 가
  있거나, 인클루드가 제 `*KEYWORD` 를 갖고 그 폭이 주 덱과 다르면 「한 폭으로 펼칠 수 없다」 로 거절한다.
- 그 판정을 파일 하나의 줄을 받아 답하는 함수 하나로 뽑아 `inlined`(메모리의 줄)와 extract-parts(파일을 흘려 읽는 앞 훑기)가 같이 쓴다 —
  두 번째 소비자가 생기는 자리라 사본을 만들지 않는다. extract-parts 는 산출을 열기 전에 rc 1 과 까닭 글로 멈춘다.
- 바뀌는 것 — d · g · h · i 가 rc 0 → rc 1. e · f 는 rc 1 그대로고 글이 참 까닭(폭)으로 바뀐다. a · b · c · j · k · l · m 은 rc 0 그대로다.
- 값 — long · I10 주 덱 아래 맨 `*KEYWORD` 로 시작하는 인클루드는 본문이 주 덱 폭으로 쓰였어도 거절된다(글로는 가를 수 없다). 실사용 88 장에
  이 꼴은 0 장이었다.

### 2-3. 쓰기 함수(`KFileWriter`) — ★ 셋 가운데 둘과 N-1 ~ N-4
- **두 번째 해석기를 없앤다(N-2 · N-3 · N-4)** — `writeFileWithSource` 는 원본 글에서 `*ELEMENT_SHELL*` · `*ELEMENT_TSHELL*` 블록의 줄마다 앞
  8자를 EID 로 읽어 「솔리드 블록에서 뺄 번호」 를 모은다. 폭 · 둘째 카드 · 리더가 안 읽는 블록을 모른다. 뺄 번호는 메시가 이미 안다(셸은
  `QUAD4` · 두께 셸은 `Mesh::thickShellIds` — 쓰기가 이미 건너뛴다). 그 훑기가 아직 필요한 까닭은 `map` 의 결과 메시가 다시 지어지면서
  `thickShellIds` 를 잃기 때문 하나다 → `MeshRemapper::step5_CopyElements` 가 요소와 함께 그 번호를 옮기게 하고 훑기를 지운다.
- **폭을 한 자리에서(N-1 · T-4)** — 번호 폭(`idFieldWidth_`)이 정해지면 좌표 폭은 `realFieldWidth` 로 따른다(8 · 10 → 16, 20 → 20). 원본 없는
  쓰기(`writeFile`)는 폭을 `*KEYWORD` 줄에 선언한다(8 → 맨 줄 · 10 → `I10=Y` · 20 → `LONG=Y`). 생성기는 8 그대로라 바이트가 바뀌지 않는다.
- **번호가 칸에 안 들어가면 거절(T-4b 의 뒷문)** — 두 쓰기 길 모두 파일을 열기 전에 쓸 번호(절점 · 요소 · 파트 · 요소가 가리키는 절점)가 폭에
  들어가는지 본다. 넘으면 rc 1 이고 산출이 없다. 폭 10 · 20 은 int 범위라 걸리지 않고, 표준 덱에 `%` 접미사 블록으로 큰 번호가 든 꼴만 걸린다.
- **tetremesh(T-2 · T-3 · T-4)** — 메시만 쓰는 계약은 그대로 둔다. 폭은 읽은(펼친) 덱에서 가져오고, 셸 · 두께 셸은 메시로 다시 짓지 않고
  리더가 읽은 블록(`gridReaderReadsKeyword`)을 원본에서 글자 그대로 옮긴다(키워드 줄의 접미사 · 주석 · 두께 카드 · N5 ~ N8 까지). 셸이 없는
  표준 덱의 산출은 바이트가 바뀌지 않는다. 리더가 안 읽는 요소 키워드(솔리드 · 두께 셸의 선택 꼴 · 복합 셸 · 빔 …)는 지금처럼 산출에 없다 —
  매뉴얼 43.8 에 한계로 적는다.
- **unfold** — 산출 폭을 굽은 덱에서 가져온다(리더가 이미 읽은 덱 폭을 내어 준다). 셸이 있는 덱은 지금도 거절한다.
- **id_floor(I-1)** — 시작 번호 넷 가운데 하나라도 2147483647 을 넘으면 rc 1 과 까닭 글이고 JSON 을 내지 않는다(LS-DYNA 정수 상한 — Vol_I
  19325-19326).

### 2-4. 색인기 위상 전파(1차 계획 2절 B)
- 첫 틀(시작 모서리 요소의 세 축)은 지금처럼 기하로 정한다(`determineInitialDirectionsGeometry`). 전파만 바꾼다 — 요소마다 「면 → (축, 부호)」
  틀을 들고, 이웃으로 넘어갈 때 맞닿은 면은 반대 부호로, 나머지 면은 맞닿은 면과 두 절점을 나눠 가진 면끼리 짝지어 옮긴다. 칸은 넘어간 면의
  축 · 부호만큼 한 칸 옮긴다. 끝나고 최솟값을 0 으로 맞춘다.
- 실패는 넷이다 — 이미 놓인 이웃의 칸이 계산한 칸과 다르다 · 면 짝이 네 절점을 나누지 않는다 · 이어 갈 면이 없다 · 닿지 못한 요소가 있다.
  **기하 전파로 되돌아가는 길은 두지 않는다** — 위상이 구조 격자가 아니라고 말하는 덱을 어림으로 다시 색인하면 1차에서 막은 겹침이 되돌아온다.
  채움률 관문 · 칸 유일성 관문(A-1) · 축 재배열 · 절점 재배열은 그대로 둔다.
- 기대(시제품으로 잰 것) — 리포의 구조 격자 93 덱 가운데 83 은 칸이 같다(→ `map` · `unfold` 산출 바이트가 같아야 한다) · 겹치던 3 과 채움률로
  거절되던 5 가 색인된다 · 두 덩어리인 2 는 계속 거절된다. generate 가 지은 꼴 다섯(helix 20×5×3 · wave 10×10×2 · scurve 40×8×4 ·
  scurve 10×10×2 · helix 10×10×2)이 색인된다.

## 3. 검증
1. 파싱 줄 — 동시 호출 셋의 최대 겹침 1 · `attach_media` 가 잠금 안에서 파싱 · 변이 확인 · 임시 스택에서 동시 올리기 둘의 최고 RSS.
2. C-4 — `test_extract_parts_long.py` 에 a ~ m 열세 꼴(rc 와 까닭 글 · 거절 때 산출 없음) · 변이 확인 · `inlined` 를 쓰는 기존 시험 그대로.
3. 쓰기 — 새 회귀 `test_writer_width_shells.py`(T-2 · T-3 · T-4a · T-4b · I-1 · N-1 ~ N-4 · unfold 폭 · 표준 덱 바이트 동일) · 변이마다 빨강.
4. 위상 — 고치기 전 바이너리(`6285f42`)와 `map` · `unfold` 산출 sha 대조(리포 덱 · 회귀 픽스처) · 새로 되는 덱의 요소 수 · 뒤집기 대칭 ·
   1차 시험(`test_unfold_element_loss.py`)의 기대를 새 동작으로 · 단위 시험.
5. 전체 — 단위 시험 · 회귀 전부 · 백엔드 pytest(새 표는 임시 DB) · MCP 계약 시험.

## 4. 올리기 차례
1. `corelink-int` → main 합치기 · 푸시(직전에 fetch).
2. 호환 빌드(`builder.sif` · `-j8`) → GLIBC 상한 확인 → 살아 있는 잡 확인 → `build/linux/bin` · `platform/backend/bin` 에 설치.
3. dev DB `alembic upgrade head`(0021) → API · MCP 재기동(잡 확인 뒤) → health · 스모크(바뀐 op 을 실제로 부르는 것까지).
4. cli.sif 다시 굽기 → 바이너리를 api.sif 안에서 돌려 확인 → `dist-to-drive.sh`(보관 4) → `BUILD_INFO.txt` · `SHA256SUMS` 확인.
5. 알림(pyKooCAE · SmartTwinMCP · 포털 · StepForge · 같은 리포 세션) · cae00 점검 문서 · 체크리스트 · 메모리.

## 5. 이번에 하지 않는 것
- 미룬 목록의 나머지 줄 · `cnrb2solid` · `cnrb2spring` 의 long 좌표 폭(1절 끝) · DF 2차 ② ~ ⑥ · 리포트 상한 값 바꾸기.
- 솔버 실행(라이선스 만료) · 실물 long 덱(리포에 없다) — 재지 못한 것으로 적는다.
