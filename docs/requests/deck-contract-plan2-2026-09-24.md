# DynaForge(KooRemapper) 추가 개발 계획 — 2026-09-24

실사용 박스 피드백(`deck-contract-followup-2026-09-24.md`)과 갈래별 실측 후보 40여 건을 합성했다. **이 문서의 모든 수치는 아래 §0 에서 이 세션이 직접 재현한 것이거나, 파일:행으로 짚은 것이다.** 후보 보고에서 인용만 하고 이 세션이 재확인하지 않은 것은 그 자리에 `(미재확인)` 이라고 적었다.

---

## 0. 이 세션에서 직접 확인한 기준선

| 항목 | 실측값 | 근거 |
|---|---|---|
| HEAD | `3aed197`, origin/main 보다 **1커밋 앞(미푸시)** | `git rev-list --left-right --count origin/main...HEAD` → `0 1` |
| 게시본(Drive latest) | commit `cb4e208`, 바이너리 mtime `2026-09-21T15:08:05Z`, glibc_max 2.34 | `rclone cat ApptainerImages:KooRemapper/dist/latest/BUILD_INFO.txt` |
| 게시본과 코드 차 | **15커밋** — 09-24 덱 계약 9건이 실사용 어디에도 없다 | `git rev-list --count cb4e208..HEAD` → 15 |
| 현재 트리 바이너리 | **GLIBC_2.38 요구** (컨테이너 허용 ≤2.36) · `build/linux/bin` 과 `platform/backend/bin` 이 동일 파일(09-24 08:09) | `objdump -T platform/backend/bin/KooRemapper` |
| 개행 매트릭스(gmsh 고정) | **보존 19 · 깨짐 1 · 건너뜀 29**, FAIL = `meshfix_out.k(CRLF 0 / LF단독 2754)` — 저쪽 답신의 2754 와 같은 수 | `KOOREMAPPER_GMSH=$PWD/dist/gmsh/gmsh python3 tools/regress/test_newline_matrix.py build/linux/bin/KooRemapper --verbose` |
| 덱을 쓰는 op | **42개**(카탈로그 49 − info·modelmeta·strain·generate·generate-var·battery·stcx 7) → 그중 판정된 것 19개 | 위 실행의 skip 사유 전수 |
| 카탈로그 예제 | **17개 op 의 입력 덱이 자기 `example_folder` 에 없다**(출력 파일 부재는 제외한 수) | 카탈로그 전수 대조 스크립트 |
| `takes_kfile` 오기 | **3개** — `indent`·`restack`·**`update`**(config 로 덱을 먹는다). `generate`·`battery` 는 false 가 맞다 | 카탈로그 덤프 |
| meshfix 2줄 카드 | **재현** — 2파트 2줄 포맷 덱에 `meshfix pid:1` → PID 2 요소 5개의 **노드 줄만 삭제**, 요소 1913→**1908**, 그런데 `info` 가 `[OK] Mesh is valid` **rc=0** | `/tmp/.../scratchpad/mf2/` (`fixed.k` 91~95행이 헤더만 5줄) |
| 예제 덱 자체가 2줄 포맷 | `examples/mesh/tetramesh.k` 8827행 `[       1       1]` + 8828행 노드 줄 — WB-LSDYNA 2025 R2 산출 | 파일 직접 확인 |
| 개행 아직 깨지는 op | **재현** — `database` CRLF 0 / LF 116(전멸), `implicit` CRLF 86 / LF **15 혼재**(한 파일 안) | `/tmp/.../scratchpad/nl/` |
| DeckWriter 채택 | 8개 파일뿐(ale·cnrb2solid·cnrb2spring·contact·core_ops·merge·relax·surface_extract + KFileWriter) | `grep -rln DeckWriter src/ include/` |
| 비바이너리 ofstream | `src/commands`·`src/assembly` 에 **34곳** | `grep -rn std::ofstream \| grep -v ios::binary \| wc -l` |
| ID 발행 | `IdAllocator`/`IdBand` **0건**. 발행자 8개 파일(hfdamp·contact·contact_helpers·matswap·merge·cnrb2solid·ale·surface_extract) 모두 `INCLUDE` grep **0건**. 인클루드를 보는 것은 `cclip`(5건)·`modelmeta`(1건)뿐이고 `KFileReader` 는 0건 | grep 전수 |
| DF-07 의 실제 범위 | StepForge `ID_BANDS.md` §5 — PID 축은 사내 관례 공식이 정하고, **DF-07 은 SET id 축으로 좁혀진다**. 즉 "예약 대역표 값을 기다려 막힌 항목" 은 이제 **없다** | `/home/koopark/claude/StepForge/docs/ID_BANDS.md:57-62` |
| modelmeta 재고 | `n_node`·`mass`·`thickness` **0건** | `grep -n "n_node\|\"mass\"\|thickness" src/commands/modelmeta.cpp` |
| 플랫폼 | `newline` 메타 소비자 **0건**, 절대 참조 검사 노출 **0건**, `/api/health` 는 `status·env·name·binary_present` 4칸, `token_version` 은 문서에만 | grep + `main.py:69-80` |
| 운영 | `platform/infra/data/backups` **없음**, 크론 koorm 줄 **1개(감독자뿐)**, `PYTHONNOUSERSITE` **0건**, `dist-to-drive.sh` 는 glibc 를 **기록만** 하고 거절 분기 없음 | ls·crontab·grep·`dist-to-drive.sh:144` |
| 시험 재고 | `tools/regress/*.py` **42개**, 바이트 왕복 시험 **0개**, 체크리스트 미완 **2칸**(P1-2 무편집 진입점 + `test_roundtrip_bytes.py`) | ls + checklist |

**아직 모르는 것(추측하지 않는다).** ① 실사용 캠페인 덱이 `I10=Y` 인지, 좌표가 칸을 꽉 채우는 packed 인지 — 폭 결함의 실사용 빈도를 우리는 모른다. ② `rc=1` 인데 파일이 나오던 동작에 기대는 캠페인 손스크립트가 있는지. ③ 발행 SID 를 고정으로 못박은 하류 스크립트가 있는지. ④ 세션 공유 `team/department` 가 실사용 박스에서도 전부 NULL 인지(dev 실측은 후보 보고 — 미재확인).

---

## 1. 중복 합침 — 40 후보 → 21 작업 단위

| 단위 | 흡수한 후보 id | 한 덩어리인 이유 |
|---|---|---|
**U1 meshfix 덱 쓰기** | MESHFIX-SPLICE2L, MESHFIX-CRLF, MESHFIX-WIDTH | 덱을 쓰는 경로가 `spliceMesh` **하나**다. 세 번 열지 말고 한 번 연다 |
**U2 개행 일원화** | NEWLINE-REST10, NL-REST-9OPS, NL-WRITERS-10, WIN-BINARY-MODE | 같은 10~11개 라이터. 윈도 `\r\r\n` 은 DeckWriter 로 옮기면 공짜로 막힌다 |
**U3 시험 눈뜨기** | MATRIX-EYESOPEN, MATRIX-HONEST, NL-MATRIX-BLIND(2건), MATRIX-FIXTURES, CATALOG-EXAMPLES, CATALOG-TAKESKFILE, GMSH-PIN | 한 스크립트와 한 데이터 파일(카탈로그). 따로 고치면 서로를 되돌린다 |
**U4 게시 정합** | RELEASE-STALE, DIST-GLIBC-GATE, PLATFORM-REV-HEALTH | "무엇이 돌고 있나" 를 못 보는 문제 하나 |
**U5 바이트 왕복** | SYS02-BYTES, SYS02-RELATIVE, SYS02-NOOP, SYS02-FIXTURES | 픽스처 5종을 공유하는 한 하네스. 상대 대조(LF↔CRLF)와 절대 대조(원본 동일)는 같은 파일의 두 단언 |
**U6 쓰기 폭** | G2-WRITE-WIDTH, G4B-CONV-WIDTH | 같은 `ModelAssembler` 파싱/포맷 자리. 한 커밋이 싸다 |
**U7 ID 발행** | INCLUDE-SCAN-SHARED, IDALLOC-CORE, IDALLOC-BANDS, IDALLOC-BANDS-IO, IDALLOC-ADOPT-SET, G15-SETID, IDISSUE-ONE-PATH, DF07-CENSUS-REPLY | 전부 "발행자가 표와 인클루드를 본다" 한 줄기. 조사 결과는 회신에 실린다 |
**U8 재고(modelmeta)** | MODELMETA-NODE-MASS, INV-FIELDS, MODELMETA-INVENTORY, INV-BEAM-BLIND, INV-BBOX-BASIS | DF-08·마스킹 관문·3자 대조가 전부 같은 결손에 막혀 있다 |
**U9 3자 대조** | TEMPLATE-3WAY, DF08-THREEWAY, INV-3WAY-PLATFORM, INV-STREAM-CLI | 앞다리는 플랫폼(DB), 뒤다리는 CLI 관문 — 두 조각이지만 한 계약 |
**U10 dangling rc** | DANGLING-NOWRITE, DF20-DANGLING-RC, RC-UNIFY-DANGLING, DF08-DANGLING-RC-ASK | 같은 결정 하나 + 같은 승인 하나 |
**U11 관문/노출** | G13-PREFLIGHT, REF-SURFACE, O-EXT-PIDREF, CONTACT-SSID-SCAN | `info` rc 를 못 건드린다는 제약을 공유하는 새 관문 채널 |
**U12 gmsh 운용** | GMSH-PREFLIGHT (+U3 의 GMSH-PIN) | 시험 쪽은 U3, 실행 쪽은 U12 |
**U13 운영 위생** | MCP-USERSITE, SUPERVISOR-LOG, DB-BACKUP-CRON, USAGE-READOUT, DATAHUB-SIMID, TOKEN-VERSION, SESSION-SHARE-DEAD | 전부 작고 서로 무관 — 한 스프린트로 묶는다 |
**U14 회신** | REPLY-FOLLOWUP, NOTIFY-CORRECTION, PYKOOCAE-SNAPSHOT, POSTPROCESS-REPLY, SF-GAP-CONVENTION, BOUNDARY-OWNERSHIP, OUT-OF-SCOPE-NOTED | 문서. 다만 수신자별로 쪼갠다(캠페인 / StepForge / 포털·KooSlurm / pyKooCAE) |
**U15~U21** | PLATFORM-NEWLINE-DIFF, SETDIALECT-GENERATE, CNRB2SOLID-MAXSCAN, RESTACK-SECID-BAND, GATE-LEDGER-MEM, EDIT-SCOPE, WIDTH-TABLE, MESHFIX-REBIND, ASSESS-EDIT-IMPACT, MASKFEAS-GATE, POSTPROC-OP, STCX-LIVE, IDALLOC-ADOPT-REST, PUSH-HEAD | 독립 단위로 유지 |

크기 표기 — **S** ≤0.5일, **M** 1~3일, **L** 4~10일, **XL** >10일.

---

## 2. P0 — 실사용에서 지금 틀린 산출물이 나오고, 하류 합의 없이 고칠 수 있는 것

### P0-1. meshfix 가 2줄 포맷 덱에서 **다른 파트의 요소를 조용히 없앤다** · U1a · M
개행보다 이것이 먼저다. `spliceMesh` 가 줄마다 `parseFirstInt`(`meshfix.cpp:1517`)로 첫 정수를 읽어 삭제를 정하는데, 2줄 카드의 둘째 줄 첫 정수는 **노드 번호**다. 그 값이 `removeElems`(= 그 PID 의 전 eid, `:2168-2177`)에 있으면 건드리지 말아야 할 파트의 노드 줄만 지워진다. **셋이 겹쳐 최악이다** — ① 리포의 meshfix 예제 덱(`examples/mesh/tetramesh.k`)이 이미 2줄 포맷이다 ② meshfix 는 자체 라이터라 요소 수 대조 게이트(`ModelAssembler.cpp:5483-5616`)를 안 거친다 ③ `info` 가 그 덱을 `[OK] Mesh is valid` rc=0 으로 통과시킨다. 캠페인 사건 1(A27 요소 소실)과 같은 모양이다. **올바른 구현은 같은 리포에 이미 있다** — `cclip.cpp:798-853 cc_removeSolidElements` 가 `toks.size()==2` 로 2줄 헤더를 알아보고 두 줄을 함께 소비한다.

받아들일 조건 — ① 위 재현 덱(`scratchpad/mf2/two_part_2line.k`)을 회귀 픽스처로 넣고, meshfix 후 PID 2 의 `900001 2` + 노드 줄이 **두 줄 그대로** 남고 `info` 의 요소 수가 1913. ② 1줄 포맷 덱 출력 sha256 불변. ③ tet10(10노드) 섹션은 판정에서 제외(meshfix 는 tet4 만 다룬다). ④ 무력화 — 카드 스팬 판정을 빼면 그 회귀가 FAIL. ⑤ `cclip` 쪽 동작은 건드리지 않는다(공용화가 아니라 meshfix 안에 같은 판정을 둔다 — 파급이 작다).

### P0-2. 덱 개행을 아직 잃는 op 11개 · U1b+U2 · M~L
저쪽이 `meshfix` 하나를 돌려줬지만 전수로 재면 더 있다. 이 세션 재현 2건(`database` 0/116 전멸, `implicit` 86/15 **혼재**) + 후보 실측 9건(`hfdamp`·`explicit`·`stabilize`·`modal`·`cclip`·`optimize`·`squeeze`·`meshfix`, 그리고 `database`·`implicit`). 라이터 위치 — `database.cpp:403`, `hfdamp.cpp:639`, `implicit.cpp:209/322/454`, `modal.cpp:161/252`, `stabilize.cpp:544`, `optimize`(`matswap.cpp:667`), `cclip.cpp:1478/1695`, `squeeze_assemble.cpp:452`, `meshfix.cpp:1556`. 덤으로 `matswap`(:403)·`strip`(:177/:189)은 리더가 CR 을 안 떼서 **우연히** 보존한다 — MSVC 텍스트 모드에서 `\r\r\n` 이 나는 자리(G1w)다.

받아들일 조건 — ① 11개 op 전부 CRLF 덱 출력의 **홀로 선 LF 가 0**. `implicit`·`squeeze` 는 한 파일 안에 개행이 섞이지 않는다. ② LF 덱 출력 sha256 이 수정 전과 **바이트 동일**. ③ `cclip` 의 리포트 JSON 은 LF 유지 · `squeeze` 의 `.dynain` 은 기존 개행 유지 — 덱과 비덱을 구분한다. ④ `matswap`·`strip` 도 DeckWriter 로 옮긴다. ⑤ grep 시험 신설 — `src/commands` 에 덱 확장자(`.k/.key/.dyn/.dynain`)를 쓰는 비-DeckWriter `ofstream` 이 남아 있으면 FAIL(예외는 화이트리스트에 사유와 함께). ⑥ 무력화 — DeckWriter 를 걷어내면 op 별 FAIL.

### P0-3. 시험이 눈을 뜨게 한다 · U3 · M
"ALL OK" 가 "전부 돌았다" 를 뜻하지 않는다. 기전 셋을 전부 확인했다 — ① `test_newline_matrix.py:198` 의 `if rc != 0 or not produced: SKIPS.append(...)` 가 **의존성 실패·예제 부재·바이트 동일**을 한 칸에 몰아넣는다 ② 카탈로그 `example.args` 가 실제 예제 yaml 의 상대 경로를 잃어 **17개 op 의 입력 덱이 폴더에 없다**(시험은 최상위 파일만 복사한다) ③ `takes_kfile` 오기 3건과 `restack` 의 잘못된 `example_folder`(카탈로그는 `examples/assemble_display`, 파일은 `examples/replace_test`) ④ gmsh 해소가 불결정적이다 — `KOOREMAPPER_GMSH` 를 `dist/gmsh/gmsh` 로 주면 돌고, 안 주면 PATH 의 깨진 파이썬 래퍼(`~/.local/bin/gmsh`, `import gmsh` 실패)를 집어 skip 된다.

받아들일 조건 — ① 시험이 **덱을 쓰는 op 42개를 카탈로그에서 유도해 세고**, 판정 없이 끝난 것이 하나라도 있으면 rc=1 + op 이름과 사유. skip 허용은 `EXCLUDE` 에 사유가 적힌 것만. ② "바이트 동일" 은 `보존(바이트 동일)` 등급으로 분리해 보존 수에 넣는다. ③ 카탈로그 `example.args` 가 예제 yaml 과 같은 경로를 갖거나 시험이 상대 경로 의존 파일을 함께 복사한다. `al_box.k`(120MB, 저장소에 못 둔다)는 대체 덱을 지정한다. ④ `indent`·`restack`·`update` 의 `takes_kfile` 을 true 로, `restack` 의 `example_folder` 를 `examples/replace_test` 로. ⑤ 하네스가 gmsh 를 `KOOREMAPPER_GMSH` → `dist/gmsh/gmsh` → `platform/backend/bin/gmsh/gmsh.exe` 순으로 찾고 **한 번 실행해 rc=0 을 확인**한다. `requires_gmsh` op 이 gmsh 를 못 얻으면 SKIP 이 아니라 **FAIL**. ⑥ 지금 상태로 돌리면 미판정 다수로 FAIL 하고, 예제 정합 뒤에는 미판정 0. ⑦ 같은 커밋에서 `test_catalog_binary_parity.py`·`test_catalog.py`·`tools/help/ops_help.py`·`test_help_truth.py` 통과(카탈로그는 게이트웨이가 그대로 내보내는 데이터다 — UI·MCP 표시가 함께 바뀐다). ⑧ CI(`regress.yml`)에 gmsh 설치 단계. apt 4.8.4 로 meshfix hxt 가 도는지는 **실측해야 한다**(이 박스 4.14.1 로는 된다). 설치 실패 시 meshfix 항목은 FAIL.

> P0-2 는 P0-3 없이 못 박힌다. 순서는 **P0-3 → P0-2** 또는 같은 묶음이다(CI 가 며칠 빨간 채로 남지 않게).

### P0-4. 게시본이 15커밋 뒤에 멈춰 있고, 지금 트리 바이너리는 컨테이너에서 안 돈다 · U4 · M + 외부 대기
고쳤다고 회신한 9건이 실사용(pyKooCAE REMAP 체인 = SIF 안 바이너리)에 **하나도 안 갔다**. 그리고 지금 `platform/backend/bin/KooRemapper` 는 GLIBC_2.38 을 요구해 `cli.sif`(2.36)에서 실행 자체가 안 되는데, `dist-to-drive.sh` 는 glibc 를 **BUILD_INFO 에 적기만** 하고 거절하지 않는다(`:144`). `build_method: 알 수 없음` 도 그대로 게시된다. 게다가 저쪽은 `f1b6d7d` 가 안 실린 프로세스를 **사람 눈으로** 찾아냈다 — `/api/health` 에 리비전이 없다.

받아들일 조건 — ① `dist-to-drive.sh` 가 GLIBC_2.37 이상 요구 바이너리를 **업로드 전에** 거절한다. objdump 부재(폐쇄망)는 `알 수 없음` 이고 **기본은 거절**이며 `--allow-unknown-glibc` 로만 넘어간다(어느 쪽인지 문서에 적는다). `build_method: 알 수 없음` 도 같은 등급. ② 무력화 — 게이트를 지우면 빨개지는 시험 1건. ③ `/api/health` 가 코드 리비전(빌드/배포가 심은 값 — 컨테이너에 `.git` 이 없으므로 런타임 `git` 호출은 쓰지 않는다)과 바이너리 sha256·mtime 을 낸다. 배포 절차가 기동 후 그 값을 기대값과 대조해 다르면 실패로 끝난다. 일부러 옛 바이너리를 두면 실패한다. ④ `scripts/build_linux_compat.sh` 로 재빌드 → 매트릭스 깨짐 0 → `dist-to-drive.sh` → `BUILD_INFO.txt` 의 commit 이 그때의 origin/main 과 일치. ⑤ 순서 규칙을 지킨다 — **플랫폼 파이썬이 main 에 먼저** 올라간 뒤 바이너리(09-17 restack 전량 rc=1 사고가 이 순서를 어겨 났다). ⑥ SIF(`SmartTwinPreprocessor.sif`) 재굽기는 이 리포 밖이라 **외부 요청**으로 낸다(§6).

### P0-5. DB 백업이 한 번도 돈 적이 없다 · U13a · S
`backup-db.sh` 는 보관 정리까지 있는데 크론에 없고 백업 디렉터리가 생긴 적도 없다. 형제 스택(SignalForge·AIDataHub·MaterialTwinWeb)은 전부 매일 Drive 백업을 돈다. 되돌릴 수단이 없는 상태다.

받아들일 조건 — `install-autostart.sh` 가 감독자 줄과 같은 MARK 로 백업 크론 줄을 멱등하게 쓴다. 설치 직후 한 번 돌려 `platform/infra/data/backups/koorm_*.sql.gz` 가 생기고 `gunzip -t` 통과. 복원 리허설 1회를 문서에 남긴다. 시각은 형제 스택과 같은 새벽대.

### P0-6. ID 발행이 `*INCLUDE` 를 못 봤다는 사실을 **말하게** 한다(번호는 그대로) · U7a · S
발행자 8개 파일에 `INCLUDE` grep 0건이다. 인클루드가 점유한 번호를 재발행하는 사고는 후보 둘이 각각 재현했다(`contact create`·`hfdamp selective` 가 인클루드의 `*SET_PART 6` 을 경고 0·rc=0 으로 재발행). 번호를 바꾸는 것은 하류 바이트를 흔들어 고지가 필요하지만(→ P1-3), **"인클루드를 읽지 않았으므로 빈 번호를 단정할 수 없다" 고 말하는 것**은 오늘 공짜다. 규약 전례가 이미 있다 — `ReferenceIntegrity.cpp:93-96`, `core_ops.cpp:1326`.

받아들일 조건 — 마스터에 `*INCLUDE` 가 있는 덱에서 `hfdamp`·`contact`·`matswap`·`merge`·`cnrb2solid`·`ale` 이 ID 를 발행하면 경고 한 줄(`*INCLUDE N장을 읽지 않았습니다 — 발행 번호의 유일성을 단정할 수 없습니다`)이 난다. **발행 번호와 출력 바이트는 불변**(전 op sha256 대조). 인클루드가 없는 덱에서는 경고가 없다. 회귀 1건.

### P0-7. 답신에 회신한다 — 정정 2 · 새 결함 3 · 아직 안 알린 동작 변경 3 · U14a · S
저쪽 진단이 우리 시험의 구멍을 실제로 드러냈다는 것을 먼저 인정하고 시작한다. **정정 2** — ① `requires_gmsh: true` 는 **meshfix 하나**이고 `requires_tetgen` 은 49개 전부 false 다(카탈로그 전수 확인) ② `api.sif` 안에 gmsh 가 없다 — 컨테이너에서 `which gmsh` 가 잡히는 것은 홈 바인드로 호스트의 깨진 래퍼가 보이는 것이고 `--no-home --cleanenv` 면 없다. 그러니 "컨테이너에서 회귀를 돌린다" 로는 안 풀리고 해법은 `KOOREMAPPER_GMSH` 고정이다. **새 결함 3** — ③ 개행을 아직 잃는 op 이 10개 더 있다(§P0-2 표) ④ meshfix 가 2줄 포맷 덱에서 다른 파트 요소를 없애고 `[OK] rc=0` 을 낸다(§P0-1, 재현 수치 포함) ⑤ "옛 바이너리로 ALL OK" 의 정체는 **어느 복사본을 시험에 줬느냐**다(`platform/backend/bin` 에는 옆 gmsh 가 있고 `build/linux/bin` 에는 없다). **안 알린 동작 변경 3** — `e2281b3`(폭을 못 맞추면 자르지 않고 rc≠0), `d194c49`(ORTHO/COMPOSITE 거절), `814ff72`(`info` stdout 에 `[ERROR]` 가 나지만 rc 는 0). 앞의 둘은 그 조건을 밟던 파이프라인의 성공을 실패로 바꾼다 — pyKooCAE REMAP 스텝은 rc≠0 이면 체인을 멈춘다(`CumulativeScenarioRunner.py:2262`).

받아들일 조건 — `docs/requests/` 에 회신 한 장 + 원 회신 §3.1 자리에 `⚠정정`(원문을 지우지 않는다 — 저쪽이 우리에게 한 방식). 모든 주장에 파일:행 또는 실행 결과. 못 주는 것(대역표 값·실덱 코퍼스)은 못 준다고 적는다. 답신의 되물음 넷에 각각 결말(착수·보류·확인 대기) 한 줄. 동작 변경 셋에는 **어느 조건에서 rc 가 바뀌나 / 어느 하류가 영향인가** 를 붙여 저쪽이 "이 조건을 밟는 캠페인이 있나" 를 답할 수 있게 한다. 그리고 **`git push origin main`** — 재부팅 때 이 트리는 `reset --hard origin/main` 을 맞는다(현재 1커밋 미푸시).

---

## 3. P1 — 조용한 오답을 구조적으로 막는 것

| # | 단위 | 크기 | 전제 | 핵심 받아들일 조건 |
|---|---|---|---|---|
P1-1 | **바이트 왕복 회귀**(U5) | M~L | P0-3 | 픽스처 5종(LF / CRLF / 무-말미개행 / `I10=Y LONG=S` / 2줄 혼재) × 덱 쓰기 op 42개에서 ① `출력_CRLF` == `개행치환(출력_LF)` sha256 ② `n_bytes`·`n_lines`·`n_crlf`·`final_newline` 동시 일치 ③ 무편집 진입점 출력이 입력과 sha256 동일. 진입점은 `cat` 복사가 아니라 각 op 의 read→write 를 태운다(리더의 CR 되붙임을 빼면 FAIL 나는 무력화로 확인). `long=y` 픽스처는 요소·노드 편집 op 에 대해 **거절**을 기대한다(`ModelAssembler.cpp:4848-4857`). 2줄 혼재 픽스처가 P0-1 을 (수정 전에) 잡는다. 코퍼스는 인자로 받아 있으면 추가로 돌고 없으면 skip |
P1-2 | **쓰기 경로 폭 인식**(U6+U1c) | M | P1-1 | packed `*NODE` 덱에 `indent` → 출력이 **달라진다**(또는 폭 미확정이면 rc≠0 + "칸 폭을 확정할 수 없다" — 조용한 성공 보고 금지). `I10=Y` 덱에 `convert tet10/hex20/quad8/tria6`·`disconnect`·`meshfix` → 요소 카드가 **10칸**. 8칸 덱에 9자리 ID 는 자르지 않고 rc≠0. 8칸·자유형식 덱 전 op sha256 불변(**고정폭 우선 → 자유형식 폴백 순서 유지**). `parsePartIdFromLine` 의 `substr(8,8)` 하드코딩 제거. `test_restack_tennode`·`test_tet4_format`·`test_element_card_layout` 불변 |
P1-3 | **ID 발행 한 경로 — SET 축**(U7b) | L | P0-6 | `include/parser/IncludeScan.h` 하나를 cclip·modelmeta 가 함께 쓰고 두 op 출력 **바이트 동일**, 못 읽은 인클루드는 `unreadable[]` + 경고. `IdAllocator`(`UsedIds` + **빈 기본 대역표** + `issue` + `verify`)를 cnrb2spring(기존 8 네임스페이스 재검사 승격 원본)이 첫 채택자로 쓰고 출력 sha256 불변. 그 뒤 SET 축 4경로(hfdamp `++maxSetId` · contact `ct_findMaxSetId+1` · ModelAssembler `maxSetId_` 8곳 · disconnect `maxPartId_+1000`)가 공용 발행자를 지난다. 인클루드에 `*SET_PART 6` 이 있는 덱에서 6 을 **재발행하지 않는다**. 대역표가 비면 **오늘과 같은 번호**(무력화로 확인). `*SET_PART 6` 과 `*SET_NODE 6` 공존 덱에서 오탐 0. **네임스페이스 입도는 이 단계에서 바꾸지 않는다**(contact 의 '모든 SET 한 통' 유지) |
P1-4 | **대역표 입력 자리**(U7c) | M | P1-3 | 표 파일 하나(`id_bands.yaml`)를 (a) YAML 폴더 (b) `--id-bands` (c) 환경변수 순으로 찾고 없으면 빈 표로 오늘과 같이 돈다(matdb `database:` 키의 전례). 문법 오류는 조용히 무시하지 않고 rc=1. op 별 키를 늘리지 않는다(현재 6개 op 이 6가지 다른 이름을 쓴다). 스코프(세션/캠페인/조직)를 먼저 정한다 — CLI 만 보면 플랫폼이 뚫리고 플랫폼만 보면 pyKooCAE 체인이 뚫린다 |
P1-5 | **rc 를 올리는 새 관문 + 플랫폼 노출**(U11) | M | 없음 | **`info` 의 rc 는 0 그대로**(`test_reference_integrity.py:76` 이 일부러 단언하고 `kfile_inspect.py:118` 이 업로드마다 돈다). 새 관문(`check`/`preflight` 또는 `info --strict`)이 미정의 세트·미정의 PID·검증 실패에 rc≠0 + 한 줄 이유. 정상 예제 덱 40~60개에서 오탐 0. 업로드 메타에 `ref_dangling`(건수·상위 N·등급·안 본 인클루드 목록)이 실리고 세션 화면에 인클루드 경고와 같은 자리로 보인다. 잡 제출 시 `certain` 등급이면 422 + `allow_dangling_refs` 탈출구(`jobs/routes.py:67-84` 인클루드 게이트와 같은 패턴). 새 op 이면 카탈로그 정합 4종 통과 |
P1-6 | **절대 참조 검사 확장 + 손상 덱 탐지**(U11b) | M | P1-2 | `*ELEMENT→PID`, `*PART→SECID/MID` 를 보고한다(현재는 `[OK] Mesh is valid` rc=0). `*CONTACT_*` Card 1 의 SSID/MSID 칸에 소수점이 든 덱(= `contact modify` 가 마찰계수로 덮어쓴 이미 망가진 덱)과 `_ID` 카드인데 Card 3 가 없는 덱을 센다. 저장소 예제 40~60개 **오탐 0**(`_GENERATE`/`_ADD`/`_GENERAL`·`*PARAMETER &name`·PID=0·`*PART_INERTIA` 포함). 인클루드를 못 읽었으면 단정하지 않는다. 기존 `pid_refs` rc 계약 불변 |
P1-7 | **재고(modelmeta) 확장**(U8) | M~L | 없음 | parts[] 에 `n_node`·`thickness`(셸, 출처 SECID)·`mass` + `mass_basis`(`volume*rho`/`area*t*rho`/**null + 이유**)·`edge_len{min,p50,max}` 가 실린다. **mass 를 0 으로 채우지 않는다**(지금 셸 `volume: 0` 이 그 실수다). `*ELEMENT_BEAM`/`_DISCRETE`/`_TSHELL` 파트가 parts[] 에 **들어온다**(현재 `info` 는 파트 2개, modelmeta 는 1개로 같은 파일을 두고 다른 말을 한다). **`Mesh`/`Element` 에 새 요소류를 넣지 않는다** — 카드 색인 쪽에서 센다. `conventions` 에 bbox 기준을 적고 `bbox`(요소 참조 노드)와 `bbox_all_nodes` 를 구분해 낸다(`info` 와 modelmeta 가 지금 다른 정의를 쓴다). 기존 키 값 불변(하류 파서 보호) |
P1-8 | **플랫폼 개행 대조 경고**(U15) | S | P0-2 | 입력 덱 메타의 `newline` 과 산출물 메타의 `newline`(`final_newline` 포함)이 다르면 잡 기록에 경고가 남고 세션 화면에 보인다. CRLF 덱으로 수정 전 meshfix 잡을 걸면 뜨고, 수정 후에는 안 뜬다. **P0-2 뒤에 켠다**(먼저 켜면 실사용 잡에 경고가 대량으로 뜬다) |
P1-9 | **gmsh 실행 전 확인**(U12) | S | 없음 | `requires_gmsh` op 을 큐에 넣기 전(또는 시작 직후) gmsh 를 실제로 실행해 버전을 얻고 실패하면 사람이 읽을 한 줄로 거절한다. `/api/health` 에 가용 여부와 버전. 깨진 래퍼를 PATH 에 두면 탐색이 그것을 고르지 않거나 명확히 거절한다. 결과는 바이너리 mtime 기준으로 캐시 |
P1-10 | **운영 위생 5건**(U13b) | M(합) | 없음 | ① `start.sh`·`restart-api-only.sh`·`supervisor.sh` 에 `--env PYTHONNOUSERSITE=1` — 도는 인스턴스의 `import mcp` 가 `/usr/local/...`(1.28.0)을 가리킨다(지금은 호스트 `~/.local` 1.27.1). 스크립트 텍스트를 보는 회귀 + 적용 직후 MCP 도구 수 확인 ② 감독자 심장박동 줄에 `[%F %T]` + 로그 회전(지금 6,910줄이 시각 없이 같은 글자) ③ 관리자 전용 읽기 집계 `GET /api/v1/admin/usage?days=N`(op별 잡·실패·최근 실패 사유 상위, `newline` 분포, 인클루드 경고 수, 리포트·세션 수) + MCP 도구 한 칸, 비관리자 403, 빈 DB 에서 0 을 내고 죽지 않는다 ④ DataHub SIM id — 100건 초과 모의 응답에서 발행 id 가 기존과 겹치지 않고, 충돌 시 조용히 덮지 않는다(현재 `limit=100` 한 페이지에서 max+1) ⑤ `users.token_version` + JWT 클레임 + 재설정 시 증가 → 옛 JWT 401(PAT 회수 여부는 결정 사항, 회수하면 게이트웨이 세션이 끊긴다) |
P1-11 | **dangling 이면 덱을 아예 안 쓴다**(U10) | S | **캠페인 확인 대기** | strict 에서 dangling 이 남으면 출력 덱·dynain·iga 가 **하나도 생기지 않고** rc=1. warn 은 불변(rc=0·덱 씀). 알려진 소비자 셋은 안전하다고 확인했다(pyKooCAE `CumulativeScenarioRunner.py:2262`·`KooRemapperStep.py:153`, 플랫폼 `runner_loop.py:404`). `$ KOOREMAPPER-PIDREF` 목록이 사라지므로 콘솔이나 별도 파일로 내는 대안을 같이 넣는다. 확인 전에는 **플래그로만** 켤 수 있게 넣고 기본값은 오늘과 같게 |
P1-12 | **세트 방언 `_GENERATE`**(U16) | M | 없음 | `*SET_PART_GENERATE 7 / 1 5` 가 파트 1~5 로 읽힌다(지금은 `2 entries [1, 5]`, rc=0). `_ADD`·`_GENERAL` 은 **잘못 펼치지 않고 "뜻을 확정하지 못했다" 를 표시**한다(`cnrb2spring` 이 이미 거절하는 방식). `examples/contact` 골든과 `test_contact_id_option.py` 불변(또는 골든 재생성 근거를 커밋 메시지에) |
P1-13 | **cnrb2solid max 스캔 · restack SECID**(U17) | S×2 | P1-4(restack 쪽) | cnrb2solid 가 아무 데이터 줄 첫 10칸을 SECID·MID·SID·PID 넷에 동시에 밀어 넣는 것을 네임스페이스별로 좁힌다 — 노드 ID 9900001 대 덱에서 새 SECID 가 2 대가 되고 I8 초과면 rc=1. cnrb2solid 전용 회귀 신규 1개(오늘 0개). restack 은 `pid_start` 만 대역을 피하고 SECID 는 `++maxSectionId_` 다 — 대역표를 보게 하고 회귀에 SECID 단언 추가 |

---

## 4. P2 — 관문·재고·경계. 전제가 서기 전에는 손대지 않는다

| # | 단위 | 크기 | 전제 | 한 줄 |
|---|---|---|---|---|
P2-1 | **3자 대조**(U9) | L | P1-7 + 캠페인 정의 확인 | 앞다리(원본↔템플릿)는 플랫폼 — `session_files.meta`·sha256·잡 계보가 이미 있어 **DB 질의와 비교 로직만**. 뒤다리(템플릿↔per-run)는 CLI 스트리밍 재고 + `--expect ref.json` → 어긋난 PID 를 전부 이름 대고 rc=1. 재고를 뜬 시점의 sha256 과 현재가 다르면 "대조할 수 없다" 고 말한다(0건이라고 말하지 않는다). 신규 C++ op 은 최소로 |
P2-2 | **ID 발행 나머지 네임스페이스**(U7d) | XL | P1-3 | 노드·요소 / 파트·섹션·재질 / 곡선·좌표계·EOS·HGID 로 쪼개고 단계마다 전 op sha256 불변을 관문으로. `ModelAssembler` 발행 82곳 + commands. cclip 의 노드·요소도 인클루드를 보게 되어 한 op 안 규칙 불일치가 사라진다 |
P2-3 | **편집 원장 + 메모리**(GATE-LEDGER-MEM) | L | P1-1 | `Δbytes/Δlines/ΔCRLF/키워드별 카드 수` 를 전 op 이 찍고, strict 면 불일치 시 rc≠0 + 파일 안 씀. 100MB 덱 assemble peak RSS 를 7.4x → 3x 이하(`output.str()` 전문 복사 4회 제거, 마지막 자리는 스트리밍 DeckWriter 를 안 쓰고 문자열판 `deck_newline::apply` 를 부른다). 순서는 복사 제거 → 원장(warn) → 관문 확대 |
P2-4 | **편집 범위 단언**(EDIT-SCOPE) | M | P2-3 | `indent`·`boundary`·`contact modify` 3개로 먼저 증명. 선언 없는 op 은 원장에 "범위 미선언" 만 |
P2-5 | **카드 필드폭 표**(WIDTH-TABLE) | L | P1-1 + P1-2 | 지금 10 고정이 표준·i10 덱에서는 맞는 답이라 **미루는 것이 옳다**. `long=y` 거절 가드 해제는 쓰기 경로 20칸 지원 커밋과 **같은 커밋**이어야 한다 |
P2-6 | **meshfix 참조 재결속 + `assess_edit_impact`** | L | P0-1 | meshfix 는 노드·요소를 재번호하면서 `*SET_NODE`·`*SET_SEGMENT`·CNRB·`*DATABASE_HISTORY_*`·`*BOUNDARY_SPC_*` 를 **하나도 고치지 않는다**(소스에 문자열 0건). 재결속 건수와 못 푼 건수를 둘 다 내고 못 푼 것이 있으면 rc≠0. 사전 조회 `assess_edit_impact` 의 사전 예측 집합이 사후 `checkSetReferences` 실측과 **같아야** 한다 |
P2-7 | **경계 기능**(MASKFEAS-GATE, 갭 규약, 소유 확정) | 소유 확정 S · 구현 L~XL | P1-7 + StepForge 합의 | `check_mask_resolution_feasibility` 는 0.5mm 메시 + 0.6mm 줄무늬에 **불가** + 경계 요소 비율(계단 오차)을 수치로. 갭 모드 이름은 **저쪽 것을 그대로 받는다**(`raw|shell_half_t|shell_t`, 이미 배포됨) |
P2-8 | **후처리 연산 §7-1**(POSTPROC-OP) | XL | **외부 선행 3건에 막힘** | KooSlurm 대시보드 REST 인증·귀환 매니페스트·부분충격 리포트 생성이 서기 전에는 "지어내지 않는다" 를 지킬 방법이 없다. 착수 금지, 기록만 |
P2-9 | **stcx 등뼈 라이브 검증**(STCX-LIVE) | S | 게이트웨이 PAT 발급 | 외부 잡 원장·제출·폴링·고아 회수 제외가 구현돼 있는데 `gateway_pat` 이 비어 dev 에서 꺼져 있다(외부 잡 0건). §7-1 을 이 위에 얹기 전에 한 번 실제로 태운다 |

---

## 5. 의존 순서

```
[P0-3 시험 눈뜨기]  ──┬──> [P0-2 개행 11op] ──> [P1-8 플랫폼 개행 경고]
 (카탈로그 예제·gmsh)  │
                       └──> [P1-1 바이트 왕복] ──┬──> [P1-2 쓰기 폭] ──> [P1-6 참조검사 확장]
                                                 │                       └──> [P2-5 폭 표]
                                                 └──> [P2-3 원장+메모리] ──> [P2-4 편집범위]

[P0-1 meshfix 2줄]  ────────────────────────────────> [P2-6 재결속 + assess_edit_impact]
[P0-6 인클루드 침묵] ──> [P1-3 IdAllocator+SET축] ──> [P1-4 대역표 자리] ──┬──> [P1-13 restack SECID]
                                                                          └──> [P2-2 나머지 네임스페이스]
[P1-7 재고 확장] ──┬──> [P2-1 3자 대조]
                   └──> [P2-7 마스킹 관문]
[P0-4 게시 정합] ── 독립(단 P0-1·P0-2 를 담아 게시한다) ── [외부] SIF 재굽기
[P0-5 백업] [P0-7 회신] [P1-5 관문] [P1-9 gmsh] [P1-10 운영] [P1-12 방언] — 전제 없음
```

**외부 입력을 기다리는 것(따로 표시).** P1-11(dangling rc — 캠페인) · P2-1(템플릿 정의 확인 — 캠페인) · P2-7(소유·규약 — StepForge) · P2-8(선행 3건 — KooSlurm·pyKooCAE) · P2-9(게이트웨이 PAT — 운영) · P0-4 의 SIF 재굽기(pyKooCAE/SIF 소유자).
**이제 막혀 있지 않은 것.** 예약 대역표 **값**은 더 이상 차단 요인이 아니다 — StepForge `ID_BANDS.md` §5 가 PID 축을 관례 공식으로 걷어내 DF-07 이 SET id 축으로 좁혀졌고, 그 축은 값 없이 P1-3 으로 진행된다. 실덱 회귀 코퍼스도 차단 요인이 아니다 — P1-1 은 저장소 픽스처 5종으로 선다.

---

## 6. 외부에 요청할 것

| 수신 | 요청 | 없으면 막히는 것 |
|---|---|---|
캠페인 운영자 | ① dangling strict 에서 **파일을 아예 안 쓰는 것** 승인(우리 확인 — pyKooCAE·플랫폼 둘 다 rc 로만 판정해 안전, 남은 위험은 손스크립트) ② 인클루드를 못 읽었을 때 발행을 **거절**할지 ③ 발행 SID/PID 를 **고정으로 못박은 스크립트**가 있는지 ④ "템플릿" 정의 확인(원본→전처리 1회→템플릿→각도·DOE 파생) ⑤ 회귀 코퍼스(6face 19 + A27·M1/M3·TN·Cross) — 없어도 진행하지만 있으면 보강 ⑥ SET id 예약 대역의 실제 값 | P1-11, P1-3 의 기본값, P2-1 의 완성 |
캠페인 운영자 | ⑦ 실사용 덱이 `I10=Y` 인지 / 좌표가 칸을 꽉 채우는 packed 인지 — **폭 결함의 우선순위가 여기에 달렸다** | P1-2 의 P0 승격 여부 |
StepForge | ① 경계 기능 넷(+`region_mask_transfer`)의 **소유 확정**과 호출 방향 ② `PLAN.md` §9.2 의 "PID 는 작게·연속으로" 가 `ID_BANDS.md` 의 큰 계산값과 **모순**임 — 우리가 `id_floor` 를 받는 쪽으로 푼다 ③ 갭 규약(모드 이름은 저쪽 것 그대로, 분포+밀착 비율 출력, 두께는 `*SECTION_SHELL` 에서, 하드코딩 금지) 확인 ④ 마스킹 관문의 판정식·임계값 일치 | P2-7 전체 |
포털(HWAXPortal) | ① §7-4 의 **과제 코드 출처**(DataHub 에 목록 엔드포인트가 안 보인다) ② 게이트웨이가 **소속**을 전파해 줄 수 있는지(지금 `X-Heax-User-Email` 만) ③ §9 확인 셋(소속 id 길이·반입 시점·증명 수명) 재상정 | P2-8, 세션 소속 공유 결정 |
KooSlurm | ① 대시보드 파일 REST 의 **인증·소유 검사**(지금 `@optional_jwt`, 구분자 없는 `startswith`) ② `output/return_manifest.json` **귀환 매니페스트** — 없으면 후처리 실패가 `COMPLETED 0:0` 으로 성공처럼 보인다 | P2-8 |
pyKooCAE / SIF 소유자 | ① `SmartTwinPreprocessor.sif` 재굽기(현 SIF 안 바이너리 sha256 = Drive 09-21 것과 동일) ② 부분충격 `impact_report.sh` 미생성 ③ **통지** — `KooRemapperStep._snapshot` 이 파일 **이름 차집합**으로 산출을 세어, 같은 이름으로 덮어쓰는 op 은 "산출 없음" 이 된다(제안 — mtime 또는 내용 해시. 우리 매트릭스도 같은 함정을 밟았다는 근거를 함께) | P0-4 의 실사용 반영 |
운영 | 게이트웨이 PAT 발급(dev `.env`) | P2-9 |

---

## 7. 하지 말아야 할 것

| 하지 말 것 | 이유 |
|---|---|
`info` 의 rc 를 0→1 로 바꾸기 | `test_reference_integrity.py:76` 이 rc=0 을 **일부러** 단언하고 `kfile_inspect.py:118` 이 업로드마다 돈다. pyKooCAE 체인도 흔들린다. 새 관문을 따로 만든다(P1-5) |
`cc_removeSolidElements` 를 공용화해 meshfix 가 쓰게 하기 | cclip 동작이 함께 움직인다. meshfix 안에 같은 판정을 두는 쪽이 파급이 작다 |
`Mesh`/`Element` 에 BEAM·TSHELL 요소류 추가 | mapper·validator·writer 전반이 흔들린다(계획서 N 이 미룬 이유). 재고표는 카드 색인 쪽에서 센다 |
`kw_tok10` 8벌을 폭 표로 흡수 / `long=y` 거절 가드 해제 | 지금 10 고정이 표준·i10 덱에서는 맞는 답이다. 쓰기 경로가 20칸을 맞게 쓰기 전에 가드를 풀면 반쯤 맞는 덱이 나간다 |
ID 발행 12개 파일 80+곳을 한 번에 채택 | 회귀 신호가 묻힌다. 네임스페이스별로 쪼개고 단계마다 sha256 관문 |
발행 네임스페이스 **입도** 변경(contact 의 '모든 SET 한 통' → 타입별) | 번호가 확 달라져 하류가 흔들린다. P1-3 에서는 입도를 그대로 두고 대역·재검사만 얹는다 |
modelmeta 의 `mass` 를 0 이나 어림값으로 채우기 | 셸 파트가 통째로 빠져도 "0 → 0" 으로 대조가 통과한다. 유도 불가는 **null + 이유** |
`cnrb2spring`·`restack` 이 이미 가진 대역 로직 삭제 | 회신 §1.3 이 지적한 자리. 승격의 원본이다 |
P0-2 전에 P1-8(개행 경고) 켜기 | 실사용 잡에 경고가 대량으로 뜬다 |
지금 상태로 게시 | `platform/backend/bin/KooRemapper` 가 GLIBC_2.38 을 요구해 컨테이너에서 실행 자체가 안 된다 |
§7-1 후처리 본구현 착수 | 선행 3건이 없으면 "지어내지 않는다" 를 지킬 수 없다. 기록만 남긴다 |
예약 대역표 값·per-run 덱 내용을 추측해 채우기 | 답신이 "여기서는 못 준다" 고 확정했다. 골격만 비워 둔다 |
신규 C++ op 남발 | 카탈로그 정합 4종(`catalog_data.json`·`test_catalog_binary_parity`·`ops_help.py`·`test_help_truth`)을 매번 맞춰야 한다 |

---

## 8. 마일스톤

| 묶음 | 내용 | 끝나면 달라지는 것 |
|---|---|---|
**M0 · 신뢰 회복**(≈2일) | P0-7 회신 + push, P0-5 백업 크론, P0-4 의 glibc 게이트·health 리비전 | 실사용에 무엇이 돌고 있는지 밖에서 볼 수 있고, DB 를 되돌릴 수 있으며, 저쪽이 우리 정정과 새 결함 셋을 받는다 |
**M1 · 시험이 눈을 뜬다**(≈3일) | P0-3 | "보존 19 · ALL OK" 가 "덱 쓰는 42개 전부 판정" 으로 바뀌고, 미판정이 있으면 CI 가 빨개진다 |
**M2 · 덱 쓰기 정합**(≈4일) | P0-1, P0-2, P0-6 | 요소가 조용히 사라지는 경로가 닫히고, CRLF 덱이 42개 op 왕복에서 보존되며, 발행자가 인클루드를 못 봤다고 말한다 |
**M3 · 게시**(≈1일 + 외부) | P0-4 재빌드·게시, SIF 재굽기 의뢰 | 09-24 덱 계약 수정 11건이 pyKooCAE REMAP 체인과 클러스터에 실제로 도착한다 |
**M4 · 조용한 오답 사냥**(≈1.5주) | P1-1, P1-2, P1-9, P1-12, P1-13 | 좌표 표기·칸 폭·세트 방언이 바뀌면 바이트 왕복 시험이 먼저 잡는다 |
**M5 · 번호와 관문**(≈2주) | P1-3, P1-4, P1-5, P1-6, P1-8, P1-10 | 인클루드가 점유한 번호를 재발행하지 않고, 망가진 덱이 잡 제출에서 막히며, 개행이 갈리면 화면에 보인다 |
**M6 · 재고와 대조**(≈2~3주) | P1-7, P2-1, P2-3 | 파트가 사라지면 사람이 아니라 도구가 먼저 말한다. 700MB~1GB 덱이 메모리로 죽지 않는다 |
**M7 · 경계**(합의에 달림) | P2-6, P2-7, P2-2, P2-8, P2-9 | StepForge 와의 경계에서 정의가 두 벌이 되지 않는다 |

---

## 9. 착수 절차(첫 커밋에 들어갈 것)

1. `docs/requests/deck-contract-plan2-2026-09-25.md` — 이 계획을 정본으로 커밋(근거 표 §0 포함).
2. `docs/requests/deck-contract-checklist.md` — P0-1~P0-7 칸 추가. 기존 P1-2 두 칸(무편집 진입점·`test_roundtrip_bytes.py`)은 **P1-1 로 이관**하고 "코퍼스를 기다리지 않는다" 를 명시. "DF-07 때문에 막혔다" 는 더 이상 사실이 아니라는 것과 §7-1 이 막힌 외부 선행 셋·해제 조건을 적는다.
3. `docs/requests/` 회신 문서(P0-7) — 수신자별로 캠페인·StepForge·포털/KooSlurm·pyKooCAE 넷.
4. `context-notes.md` — 이번에 뒤집힌 전제 넷을 남긴다. ① `9000001` 은 예약 번호가 아니라 hfdamp 의 `*SET_PART` max+1 ② DF-07 은 SET id 축 ③ `requires_gmsh` 는 meshfix 하나이고 api.sif 에 gmsh 가 없다 ④ 매트릭스의 skip 은 통과가 아니다.
5. `git push origin main` — 재부팅 `reset --hard origin/main` 위험 때문에 커밋 즉시 푸시한다.