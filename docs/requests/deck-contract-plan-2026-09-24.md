# 덱 편집 계약 — 구현 계획 (실측 기반 종합)

검증 기준. 바이너리 `build/linux/bin/KooRemapper`, 브랜치 `main` @ 228bd9b. 실험은 전부 `/tmp` 아래, 작업 트리 무변경(`git status --porcelain` 16줄, 세션 시작과 동일 — 전부 `.bkit/*`·`platform/scratch/`).

---

## 0. 한 줄 결론

요청서의 **결론은 맞고 기전 진단은 여러 곳에서 틀렸다.** 결손의 실체는 "계약이 없다"가 아니라 **"계약이 한두 op 안에만 있고 공용이 아니다"** 다. `strip` 은 이미 바이트를 보존하고, `restack`·`refine` 은 이미 파트별 요소 수를 왕복 대조해 어긋나면 파일을 안 쓰며, `cnrb2spring` 은 이미 예약 대역 + 8 네임스페이스 충돌 재검사를 갖고 있다. 1차 작업은 신규 구축이 아니라 **한 op 에만 있는 동작을 전 write 경로로 끌어올리는 일**이다.

---

## 1. 진짜 결손 / 이미 있음

### 1.1 이미 있음 — 요청에서 뺀다

| 요청 항목 | 이미 있는 것 | 근거 |
|---|---|---|
| DF-20 ⑥ 요소 수 증감 일치 | 파트별 + 합계 왕복 대조, 관대 재독 + **엄격 재독**(섹션 선언 칸 폭) 2중, 어긋나면 **파일을 안 쓰고 rc=1** | `src/assembly/ModelAssembler.cpp:5483-5616`. restack 실행 로그에 `[요소 수 대조] … 왕복 검증: … 엄격 재독한 결과도 같습니다` 실제 출력. 회귀 `test_element_card_layout.py` G·H, `test_restack_tennode.py` C 가 지킴 |
| DF-06 일부 — 델타 dangling | PID·EID·NID 3축 스캐너. `*SET_PART/_NODE/_SEGMENT/_SOLID/_SHELL/_BEAM/_TSHELL`, `*CONTACT` SSTYP/MSTYP 2·3, `*CNRB NSID`, `*DATABASE_HISTORY_*`, `*BOUNDARY_SPC_NODE`, `*DAMPING_PART_MASS/STIFFNESS`, `*INITIAL_STRESS_*`, `_GENERATE/_ADD/_COLUMN` 칸 뜻 차이까지 | `ModelAssembler.cpp:2767 scanDeadReferences`. `tools/regress/test_pidref_detect.py` ALL OK(실행 확인) |
| DF-06 일부 — ELEMENT→NID | `Validator::validateMesh` + `Mesh.h:355`(중복 1벌) | `src/util/Validator.cpp:12`. 단 `info` 에서만 돈다 |
| DF-04 "섹션 헤더마다 개별 판정" | **이미 요구보다 세밀하다 — 요소 카드 줄마다 판정한다.** 꼬리글 `(ten nodes format)` 은 *의도적으로* 판정에 쓰지 않는다("매뉴얼에 없다") | `src/parser/ElementCardLayout.cpp:15-16`. 꼬리글 없는 2줄 섹션 + 꼬리글 있는 1줄 섹션이 섞인 덱을 restack·refine·convert·disconnect 4개 op 로 돌려 전부 정답 |
| DF-03 일부 — i10 덱 요소 카드 10칸 쓰기 | restack/refine 경로는 이미 맞게 쓴다 | `test_element_card_layout.py` H 항목이 단언. 결손은 tet10/hex20/quad8/tria6 라이터와 `parsePartIdFromLine` 에 국한 |
| DF-07 일부 — 예약 대역 + 발행 후 재검사 | `cnrb2spring` 기본 대역 `990001/9900001/90000001` + 8 네임스페이스 exact-match 재검사 + I8 상한(99999999) 검사. restack `layers[].pid`·`pid_start`, 충돌이면 rc=1 로 덱 안 씀 | `src/commands/cnrb2spring.h:22-24`, `cnrb2spring.cpp:938-990`, `ModelAssembler.cpp:3730-3771`. `test_restack_tennode.py` H |
| DF-03 — `rjust(max(9,W))` 폭 확대 제거 | **그런 코드가 없다.** 지울 것이 없음 | C++·파이썬 전역 grep 0건 |
| 파이썬 계층 전반 | 덱 바이트를 만지지 않는다. 고칠 것 없음(예외 1건, §3) | `argbuild.py`(YAML·인자만), `sessions/services.py:159 dest.write_bytes(raw)`, `shared/storage.py:119 open("rb")` |

### 1.2 재현 안 됨 — 결손 근거로 쓸 수 없다

| 요청서 주장 | 실측 |
|---|---|
| 7자리 EID `9900061` → `99000` 잘림 | **재현 안 됨.** NID/EID 를 9900001~9900363 으로 올려 indent 왕복 → EID·PID·NID 전부 보존. 7자리는 8칸에 들어간다. 리포에 `setw(5)`/`%5d` 0건. 실제 경계는 **9자리** |
| `*KEYWORD I10=Y LONG=S` 가 왕복에서 소실 | indent 경로에서 **재현 안 됨**(보존됨) |
| `_ID` 를 놓쳐 TIED 225개를 **0개로 오판** | **재현 안 됨.** `_OFFSET_ID`/`_ID`/`_ID_OFFSET`/`_ID_MPP` 4종 전부 `Found 225 contacts`. 개수는 키워드 줄만 보므로 0 이 될 경로가 없다 |
| bbox 세 축이 똑같이 99.000mm | 그 숫자는 재현 안 됨. 같은 **고장 부류**는 재현됨 — 방언 오판 시 노드 363→4, 요소 200→99, bbox `(991,5,2)-(991,5,2)` 로 붕괴하면서 **rc=0** |

### 1.3 진짜 결손 — 남긴다

| # | 결손 | 실측 증거 (핵심 한 줄) |
|---|---|---|
| **G1** | **개행 소실. 기전은 라이터가 아니라 리더다** | CRLF 578 덱 → indent 출력 CRLF **0** / LF 579. 파괴 지점은 `ModelAssembler.cpp:62-67`·`132-135` 의 `line.pop_back()`. 같은 패턴 **78곳**(확인: `KFileReader.cpp` 20, `ModelAssembler.cpp` 16, `standalone_ops.cpp` 14, `ShellReader.cpp` 7, 나머지 21) |
| **G1b** | **op 마다 개행 파괴가 다르다 — 계약 부재의 직접 증거** | 같은 CRLF 덱. `indent` 0/579(전멸), `database` 0/635(전멸), `relax` 578/585(**혼재** — 원본 줄 CRLF, 새 7줄 LF), `strip` 578/579(보존). 한 파일 안에서 개행이 갈리는 `relax` 가 최악 |
| **G1w** | **윈도우 텍스트 모드 결함(별개 항목)** | `src` 전체 `std::ofstream` 중 `ios::binary` 는 **7곳뿐**, `src/commands` 의 비-바이너리 라이터 **40곳**. CR 을 살려 넘기는 `strip.cpp:177` 은 MSVC 에서 `\r\r\n` 을 뱉는다. 리눅스 CRLF 소실과 **원인이 다르다** |
| **G2** | **쓰기 경로가 방언 판별 결과를 안 쓴다 — 편집이 통째로 증발하고 rc=0** | `parseNodeIdFromLine`(`ModelAssembler.cpp:5830`)이 폭 무시·"첫 숫자 연속"으로 NID 를 읽는다. 좌표가 `0.000…`(숫자 시작)인 packed 덱 → "147 nodes moved" 인데 **출력이 입력과 바이트 동일**(cmp rc=0). 좌표가 `+0.000…`이면 정상 변경 |
| **G3** | **방언 판별 커버리지가 `*NODE`+`*ELEMENT_*` 뿐이고, 값 10 이 8벌로 흩어져 있다** | `sectionFieldWidth()` 사용처 4곳 전부 NODE/SOLID/SHELL. 독립 구현 — `kw_util.h:37 kw_tok10`(contact·contact_helpers·matswap·ale·optimize·cclip 공유), `cnrb2spring.cpp:66`, `cnrb2solid.cpp:56`, `hfdamp.cpp:54`, `merge.cpp:67`, `ModelAssembler.cpp:11261`·`17220`, `KFileReader` prescanPartSections 람다. `setw(10)` 170곳 / `%10d` 157곳 |
| **G3b** | ***PART 고정폭 폴백만 10 이 아니라 8** | `KFileReader.cpp` parsePartSection `substr(0,8)/(8,8)/(16,8)`. 부록 A(*PART=10칸)와 정면 충돌. 요청서가 못 찾은 것 |
| **G4** | **넘칠 때 raise 가 없다. 그리고 실제로 "자르는" 코드는 요소 ID 가 아니라 `*CONTROL` 값 쪽에 있다** | `fmt10d`(`ModelAssembler.cpp:15239`) `return s.substr(s.size()-10)` — **앞을 버린다**. `dt2ms:-1.0e-7` → `%10.4E` 가 11자 → **음수 부호가 잘려 DT2MS=+1.0e-7**. 선택적 질량스케일링이 고정 dt 스케일링으로 뒤바뀐다, rc=0·경고 0. `fmt10i:15243` 뒤를 버림, `kw_setField`(`kw_util.h:54`) 앞을 버림 |
| **G4b** | convert(tet10/hex20) 라이터가 덱 폭을 무시한다 | I10 덱 → 출력 `*NODE` 는 10칸인데 요소 카드만 8칸. 8칸 덱 + 9자리 NID → `100000000` 을 8칸 덱에 씀, `info` 가 `Nodes 12`(기대 14) + `references non-existent node 1000000`, **rc=0**. 요소 수가 안 변해 `5514 if (!touched.empty())` 가드에 걸려 게이트를 통째로 건너뜀 |
| **G5** | **`_ID` 판정이 endswith 전용 — 매뉴얼 정규 철자에서 깨진다** | `contact_helpers.cpp:49-56 rfind("_ID")==size-3`. `_ID_OFFSET`·`_ID_MPP` → ID 줄을 Card 1 로 읽어 `Slave: SET_SEGMENT 1000(=CID)`, FS/FD/DC 전부 한 카드 밀림. rc=0 |
| **G5b** | **더 치명적인 것은 쓰기다. `ContactDef` 에 `hasId` 멤버가 없다** | 편집 4곳이 `!hasTitle` 만 본다(`contact_helpers.cpp:1203`·`1224`, `contact.cpp:955`·`989`). `modify friction:0.33` → **SSID 칸에 0.33** 을 써 파트 참조 파괴, FS 는 0.0 그대로. `modify soft:2 depth:35` → **필수 Card 3 가 사라지고** 그 자리에 Card A. 요청서가 안전하다 가정한 `_OFFSET_ID` 에서도 터진다 |
| **G6** | **참조 무결성이 "델타 검사"뿐이다 — 절대 검사가 없다** | `ModelAssembler.cpp:2775` early return: `if (deadPids.empty() && deadEids.empty() && deadNodes.empty()) return;`. `isDead` 는 "이번 op 이 지웠나"이고 "정의돼 있나"가 아니다. **TN4 사건이 정확히 후자** — 없는 set 을 가리키는 `*DATABASE_HISTORY_SOLID_SET 9999`, CONTACT ssid 8888/msid 7777(styp=2), CNRB NSID 6666, PART→SECID 555/MID 444, SPC 999999 를 심고 `info` → `[OK] Mesh is valid`, rc=0. merge(스캐너가 도는 op)에서도 한 줄도 안 나옴 |
| **G6b** | ELEMENT→PID dangling 무검사 | 첫 요소 PID 1→777 → `Parts: 1`, `[OK] Mesh is valid`, rc=0 |
| **G6c** | 재료를 나란히 찍고 교집합을 안 본다 | `contact analyze` 가 `Slave: SET_PART 8888` 과 `--- Sets(1) --- SET_SOLID 7001` 을 같은 화면에 출력하고 대조 0. rc=0 |
| **G7** | **게이트 발화 조건이 두 겹으로 좁다** | (a) `ModelAssembler.cpp:5514 if (!touched.empty())` — 요소 증감 0 인 op(indent·convert·matswap·contact)은 **한 줄도 안 나온다**(indent 실행 로그 확인). (b) `ModelAssembler::writeOutput` 하나에만 있다 — `src/commands` 독립 `ofstream` **25곳 이상**이 게이트를 안 거친다. 실측: cnrb2spring 이 discrete beam 요소를 **추가**하는데 요소 수 대조 없음 |
| **G8** | **Δbytes·ΔCRLF·키워드별 카드 수 원장이 없다** | 바이트 수를 세는 코드가 전 write 경로에 없음. `ecBuildIndex countByPid` 는 solid/shell/tshell **요소만** 센다 — `*SET_*`·`*CONTACT_*`·`*MAT_*` 카드 증감을 못 본다 |
| **G9** | **편집 범위 단언 전무. 단 동작은 이미 좁다** | `edit_scope/changedRange/changed_line` grep 0건. 실측 indent — 변경 147줄 전부 `*NODE` 블록 안, 블록 밖 0줄. 즉 "우연히 맞은 것을 못 박는 일". 단 좌표 표기가 `2.0000000e+000`→`2.000000000e+00` 로 바뀐다(둘 다 16칸이라 바이트 중립일 뿐) |
| **G10** | **바이트 동일 왕복 회귀가 없고, "편집 0회"를 시킬 op 도 없다** | `tools/regress/*.py` **37개**(확인) 중 `crlf`/`\r\n` grep **0건**, `sha256`/`bytes`/`identical` 0건(`test_standalone_guards.py:82 md5` 는 *입력 불변* 검사). 49 op(카탈로그 확인) 에 identity 모드 없음. 가장 가까운 `strip` 무매칭도 **끝 개행 유무 하나로** 깨진다(37236 → 37237) |
| **G11** | **사본이 조용히 틀린다 — ORTHO** | 매뉴얼 정본 `*ELEMENT_SOLID_ORTHO`(Card4 A / Card5 D) 2요소로 cnrb2spring → `PART 12 <-> PART 500`(**오답**), 대조군 1줄 덱은 `PART 500 <-> PART 700`(정답). rc=0, `[ERROR]` 없음. 원인 — 방향 카드 `0.0 1.0 0.0` 가 토큰 3개라 "ten nodes 첫 줄" 조건에 걸리고 `cg_toInt=std::stoi("1.0")=1`. 공용 `ElementCardLayout.cpp:166` 은 ORTHO 를 `extraCards+=2` 로 **이미 알고 있다** — 사본만 모른다 |
| **G12** | **현존 오탐 버그 2건** | ① `ModelAssembler.cpp:2938 histElem` 에 `_SET` 제외가 빠졌다(같은 함수 `:2896 histPart` 에는 `&& !rsHas(b.kw,"_SET")` 가 있다 — 확인). `*DATABASE_HISTORY_SOLID_SET` 의 SID 를 EID 로 읽어, 세트 ID 가 우연히 지워진 요소 번호와 같으면 **rc=1 오탐**. 없는 세트 9999 는 여전히 무반응 = 틀린 것은 놓치고 안 틀린 것으로 rc 를 올린다. ② G3b |
| **G13** | **`info` 가 validateMesh 실패에도 rc=0** | `core_ops.cpp:1257 runInfo` 마지막이 무조건 `return 0`. `[ERROR] Mesh has no elements` 를 찍은 뒤 `[OK] All elements have positive Jacobian` 을 ±1.79e308 야코비안과 함께 출력 |
| **G14** | **modelmeta 에 파트별 `n_node`·`mass` 가 없다** | parts[] 키 전수 — `pid,title,elem_class,n_elems,bbox_min,bbox_max,area_ext,volume,proj,material`. 셸은 `volume:0`이고 `*SECTION_SHELL T1` 을 안 내므로 rho 가 있어도 질량 유도 불가. **요청서 §2 의 "DF-42 충분하다" 판정이 틀렸다** |
| **G15** | **ID 발행이 `*INCLUDE` 를 안 본다** | 마스터에 `*SET_PART_LIST 5`, 인클루드에 `6`(+그걸 쓰는 `*DAMPING_PART_SET 6`) → `contact create` 가 `Created SET_PART 6` 재발행, 경고 0, rc=0. `contact.cpp:435-440` 이 마스터만 `ifstream`, `INCLUDE` grep 0건. matswap·cnrb2spring 동일. cclip 만 1단계 확장(`cclip.cpp:665-687`) |
| **G16** | 메모리 7x — 전체 적재, 출력 전문 복사 4회 | `mmap` grep 0건. 실측 peak RSS — big.k 56.7MB/indent **418MB(7.4x)**, big2.k 113MB/indent **796MB(7.0x)**, big.k/info 116MB(2.0x), big.k/**strip 5.3MB(0.09x)**. 외삽 1GB 덱 ≈ 7GB. `ostringstream`+`output.str()` 4회(`ModelAssembler.cpp:4816,5410,5438,5517,5624`). **목표 아키텍처가 이미 `strip` 한 파일 안에 있다** |

---

## 2. 의존 순서

```
L0  무전제 — 지금 바로
    A  DeckBuffer + CR 취급 단일화(78곳)          ← G1, G1b
    B  넘침/잘림 금지 헬퍼 (fmt10d/i·setField·kw_setField·tet10계 라이터)  ← G4, G4b
    C  ContactDef.hasId (읽기 판정 + 쓰기 4곳)    ← G5, G5b
    D  버그 2건 (histElem _SET, *PART 폴백 8→10)  ← G12
    E  카드 필드폭 표 질의 함수 신설(호출부 흡수는 L2)  ← G3

L1  A 전제
    F  무편집 진입점(passthru/--roundtrip-noop) + SYS-02 바이트 왕복 회귀  ← G10
    G  EditGate 골격 — Δbytes/Δlines/ΔCRLF 원장, 전 write 경로 경유(warn 기본)  ← G7, G8
    H  kfile_inspect.py rb+latin-1 → n_crlf 노출 (파이썬, 관측용)

L1' E 전제 (A 와 병렬)
    I  쓰기 경로 폭 인식 (parseNodeIdFromLine/parseElementIdFromLine/parsePartIdFromLine)  ← G2
    J  rs* 헬퍼 익명 네임스페이스 탈출 → include/parser/KeywordBlocks.h   ← G6 전제(요청서에 없는 항목)

L2  G + E 전제
    K  게이트 확대 — 5514 touched 가드 해제, countByKeyword 추가, 엄격 재독 예외 로직 동반 추출
    L  kw_tok10 등 8벌 → 표 흡수, long=y(20칸)
    M  output.str() 복사 4회 제거 (K 가 3패스를 더하므로 같은 유닛)
    N  ElemCardIndex 공용화(440줄) + 사본 철거(cnrb2spring·cclip·elform)   ← G11

L3  J + E + C 전제
    O  ReferenceIntegrityChecker — 절대 검사(별도 채널·warn 기본)  ← G6, G6b
    P  *INCLUDE 확장 (O 와 공유) → IdAllocator 공용화  ← G15
    Q  DF-21 편집 범위 단언 (G 위)

L4  A + N 전제 / 외부 입력 대기
    R  mmap · string_view 전환 (분리 권장)  ← G16
    S  modelmeta n_node/mass, 덱간 3자 대조(파이썬)  ← G14 (요청 측 "템플릿" 정의 필요)
    T  DF-07 예약 대역 등록표 (요청 측 실제 값 필요)
```

**분리 결정 2건.**
- **개행 보존과 mmap 을 묶지 말 것.** 독립이다. 치명 항목(A)이 대형 리팩터(R)에 인질로 잡힌다.
- **`_ID` 읽기 판정과 `_ID` 쓰기 수정을 묶을 것.** 읽기만 고치면 `modify` 가 계속 SSID 칸을 덮어쓴다.

**요청서 주장 반박 2건.**
- "DF-01 이 나머지 전부의 전제" — **DF-02/03/05/06 은 DF-01 없이 착수 가능하다.** 위 재현이 전부 DF-01 없이 됐다. DF-01 이 진짜로 막는 것은 SYS-02, DF-20 ①③, DF-21 뿐이다.
- "DF-03 은 별개 항목" — **DF-02 의 산출물 그 자체다.** 표는 "이 키워드는 몇 칸", DF-02 는 "이 덱에서 그 칸이 8인가 10인가". 한 유닛으로 합친다.

---

## 3. 계층 배치

판단 기준 — 덱 텍스트를 직접 만지는 계약은 바이너리가 강제해야 실효가 있다.

| 항목 | 계층 | 이유 |
|---|---|---|
| A·B·C·D·E·G·I·J·K·L·M·N·O·P·Q·R | **C++ 단독** | 덱 바이트를 만드는 것은 C++ 뿐이다. 실측 — `platform/core/kooremapper_core` 는 `catalog.py`+`argbuild.py`+`catalog_data.json` 437줄, `.k` 를 열지 않는다. `platform/backend` 는 업로드 `write_bytes(raw)`·읽기 `open("rb")`·`subprocess` 실행뿐. 파이썬에 게이트를 얹으면 **CLI 직접 호출·pyKooCAE REMAP 체인이 그대로 뚫린다** |
| F SYS-02 하네스 | **양쪽** | 무편집 진입점은 C++(`src/main.cpp`), 회귀 드라이버는 파이썬(`tools/regress/test_roundtrip_bytes.py`). 기존 37개와 같은 `python3 <파일> <바이너리경로>` 규약 유지 |
| H kfile_inspect | **파이썬 단독** | `platform/backend/app/runner/kfile_inspect.py:56 path.open("r", errors="ignore")`. 읽기 전용 메타 스캔이라 덱을 망가뜨리지 않지만 요청서가 금지한 `errors='ignore'` 이고 universal-newlines 라 **개행 종류를 보고할 수 없다**. `deck_open` 이 `n_crlf` 를 노출하려면 `"rb"`+latin-1 필요 |
| S 덱간 3자 대조 | **양쪽** | 재고 산출은 C++(modelmeta 에 `n_node`/`mass` 추가). 대조는 파이썬 — 덱 여러 개를 동시에 봐야 하고 데이터가 이미 DB 에 있다(`kfile_inspect.py:94-117` 업로드 meta, `worker/runner_loop.py:261-300` 산출물 meta + sha256, kind=input/output/generated). **신규 C++ op 불필요** |
| T 예약 대역 등록표 | **양쪽** | 값은 캠페인·조직마다 다르므로 바이너리에 박으면 안 된다. C++ 이 `*_id_start` YAML 키를 받고(지금 받는 것은 restack `pid_start`, cnrb2spring 3개뿐), 파이썬(`argbuild.py`)이 주입, 보관은 `platform/backend` 세션/캠페인 스코프. **C++ 이 선행** |
| 카탈로그 정합 | **파이썬 부수작업** | 새 op 을 추가하면 `catalog_data.json`(49→50) + `test_catalog_binary_parity.py` + `tools/help/ops_help.py` + `test_help_truth.py` 를 같이 맞춰야 통과 |

---

## 4. 1차 구현 집합

선정 기준 — §1 사건표 9건 중 **몇 건을 실제로 막는가**, 그리고 **조용히 틀리는 것을 시끄럽게 실패시키는가**.

### 4.1 고른 것 (P1)

| P1 | 항목 | 막는 사건 | 고른 이유 |
|---|---|---|---|
| 1 | **A. DeckBuffer + CR 취급 단일화 + 개행 되붙임** (`ModelAssembler.cpp:62-67`·`132-135`, `KFileReader` 20곳, 쓰기 `5619-5624`·`KFileWriter:111,229`·`strip:177,225`·`relax:175,271`·`database`) | CRLF 소실(−12MB·diff 2,433만줄) | 사건표 유일한 "구조 카운트 전부 정상" 사건. 그리고 `strip` 이 이미 LF·CRLF 양쪽 바이트 동일이므로 **0 에서 시작하지 않는다** — 한 op 의 동작을 계약으로 올리는 일 |
| 2 | **F. 무편집 진입점 + SYS-02** (저장소 픽스처 LF/CRLF/무-말미개행/`I10=Y LONG=S`/2줄 포맷 5종) | 도구 자체의 조용한 파괴 | 1번의 유일한 증명 수단. **코퍼스를 기다릴 이유가 없다** — 위 실험이 그대로 씨앗이다. 코퍼스 인자는 옵션(없으면 skip, fail 아님) |
| 3 | **G. EditGate 골격** — Δbytes/Δlines/ΔCRLF 원장을 전 write 경로(25곳+)가 경유. **경고 기본, strict opt-in** | CRLF, restack 무증상 붕괴의 일반형 | 가장 값싸고 가장 넓다. 지금 게이트가 `writeOutput` 한 곳·요소 증감 있는 op 에만 있다. 원장만 찍어도 "조용히"가 사라진다 |
| 4 | **C. `ContactDef.hasId` + 쓰기 4곳** | 유격 캠페인 무효(TIED 225) | effort medium, 피해 최대. `modify friction` 이 **SSID 칸을 덮어쓴다** — 접촉 개수는 225 로 멀쩡하고 내용만 파괴되는, 요청서 DF-20 "구조 카운트만으로 통과시키지 않는다"의 교과서 사례 |
| 5 | **B. 넘침/잘림 금지** — `fmt10d/fmt10i/setField/kw_setField` + tet10/hex20/quad8/tria6 라이터 fw 인식 | DT2MS 부호 소실(조용한 물리 오류), convert 넘침 | 자르는 코드가 **실재**하고 조용히 부호를 없앤다. DF-02 표 없이 지금 당장 가능 |
| 6 | **D. 버그 2건** — `histElem` `_SET` 제외, `*PART` 폴백 8→10 | rc=1 오탐 | 한 줄씩. 덤으로 정리 |
| 7 | **O-min. 절대 참조 검사 최소형** — 미정의 SID(`DATABASE_HISTORY_*_SET`/`DAMPING_PART_*_SET`/`BOUNDARY_SPC_SET`/CONTACT styp 0·2·4)·CNRB NSID·PART→SECID/MID. **별도 채널·warn 기본** | TN4 전멸(Error 10144 키워드 즉사) | 사건표에서 **유일하게 즉사한 사건**이고 검사가 정말로 0 이다. ELEMENT→PID/NID 는 폭 오독 오탐 위험이 있어 **제외**(L3 으로) |
| 8 | **H. `kfile_inspect.py` rb+latin-1 → `n_crlf` 노출** | — | 1번을 플랫폼에서 관측 가능하게. 파이썬 3줄 |
| 9 | **G11 가드만** — cnrb2spring·cclip 이 `_ORTHO`/추가 카드를 만나면 **unsupported 로 거절** | A27 요소 소실의 재발 경로 | 사본 철거(N)는 크지만, **조용히 틀리는 것을 시끄럽게 실패시키는 것**은 작다. `cnrb2spring.cpp:200,796` 이 이미 `_GENERATE`/`_COLUMN` 에 쓰는 패턴 그대로 |

### 4.2 뺀 것과 이유

| 뺀 것 | 이유 |
|---|---|
| **L. `kw_tok10` 등 8벌 → 표 흡수, long=y 20칸** | 파급 최대(contact·contact_helpers·matswap·ale·optimize·cclip). **지금 10 고정이 표준·i10 덱에서는 맞는 답**이라 "고치면 오히려 깨지는" 회귀가 쉽다. 표 질의 함수(E)는 1차에 만들되 호출부 흡수는 P1 게이트가 바이트 동일을 증명해 준 뒤. long=y 를 표에 넣는 순간 `ModelAssembler.cpp:4841` 이 거절하던 덱이 통과하기 시작하므로 **쓰기 경로가 맞기 전에 거절 가드를 풀지 말 것** |
| **N. ElemCardIndex 공용화(약 440줄) + KFileReader 교체** | `KFileReader` 는 op 49개 전부의 입구이고 지금 `ifstream` 스트리밍이다. `ecBuildIndex` 는 전체 줄 벡터를 요구 → 700MB 덱을 통째로 올려 **G16 과 정면 충돌**. 그리고 현 리더의 "고정폭 우선 → 자유형식 폴백" 순서는 packed 덱을 살리려고 일부러 그 순서다(`test_restack_tennode.py packed_deck()`, `test_tet4_format.py` 가 지킴). A 가 서고 R 이 결정된 뒤 |
| **I. 쓰기 경로 폭 인식(G2)** | 가장 유혹적이지만 위험하다. `examples` 덱 대부분이 자유형식이라 **고정폭 우선 + 자유형식 폴백 순서를 반드시 유지**해야 하고, 전후 바이트 동일 확인이 필요하다 — 그 확인 수단이 P1-2/3 이다. **P2 첫 항목** |
| **K. `5514 touched` 가드 해제** | 게이트가 출력 전문을 복사해 `ecBuildIndex` 를 3회 돈다(관대 out / 엄격 out / 엄격 in). 전 op 으로 넓히면 700MB 덱에서 비용이 곱으로 는다 → **M(복사 4회 제거)과 같은 유닛**이어야 한다 |
| **O 전체(ELEMENT→PID/NID 절대 검사)** | `rsCardFields`(`ModelAssembler.cpp:1058`)가 10칸 고정폭 + 공백 분해뿐이고 **8칸 모드가 없다**. 그 상태로 요소 축 절대 검사를 돌리면 정상 덱에서 대량 오탐. DF-02 선행 |
| **DF-07 예약 대역 등록표** | **리포에 근거가 없다.** `grep -rni "500323\|9000001"` 의 유일한 히트가 요청서 자신(`docs/requests/…:64`). 관례의 존재는 확인됨(`test_restack_tennode.py:13`, `docs/KooRemapper_Manual.md:869,885`, `AssemblyConfig.h:73`)이나 **값이 없으면 골격만 만들고 비워 둘 수밖에** 없다. `*INCLUDE` 확장(P)만 O 와 함께 P2 |
| **DF-08 덱간 3자 대조** | **"템플릿"의 정의가 비어 있다.** 지금 리포의 template 은 리포트용 파일명 매칭(`reports/services.py:130`)이라 기준 재고와 무관. 세 다리 중 가운데가 없으면 구현 불가 |
| **DF-21** | G 위에 얹으면 값싸지만 op 마다 "내가 건드릴 범위" 선언 API 를 심어야 한다. 범위만 단언하면 좌표 표기가 조용히 바뀌는 경우를 통과시키므로 **Δbytes 와 같이** 가야 뜻이 있다 → P2 |
| **DF-20 ⑤ dangling 게이트 승격** | 현재 dangling 은 `ModelAssembler.cpp:3087` `"못 옮긴 자리가 남아 rc=1 로 끝냅니다(덱은 씁니다)"` — rc=1 인데 **덱은 디스크에 나간다**. ⑥ 은 반대로 파일을 안 쓴다. 두 관문의 결말을 통일하는 것은 **동작 변경이라 별도 합의** |
| **G13 `runInfo` rc=0→1** | 상위 파이프라인(platform 잡 러너·CI·pyKooCAE REMAP 체인)이 rc=0 을 기대한다. 별도 커밋 + 호출부 확인 |
| **R. mmap / string_view** | DF-01 의 필수 조건이 아니다. `strip` 이 5.3MB 로 끝내는 것이 목표 아키텍처의 실증이므로, 1차는 M(복사 4회 제거, 7x→4x)만으로 끊는다 |
| **2차·3차 전부**(DF-25~30 마스킹, DF-31~39 갭·압착, DF-46/49 dt 가드, DF-52 제출 게이트) | 기반 계약 위에 쌓이는 신규 기능. 1차와 섞으면 기반의 회귀 신호가 묻힌다 |

---

## 5. 받아들일 조건 (항목별 시험)

공통 1차 게이트 — **LF 덱은 바이트가 안 바뀌어야 한다.** `examples/<op>/small/*.k` 는 전부 LF. 수정 전 전 op 출력을 `/tmp` 에 떠 두고, 수정 후 **sha256 이 전부 동일**한지가 모든 항목의 선행 관문이다. 여기서 깨지면 개행 재적용 로직이 틀린 것이다.

| 항목 | 받아들일 조건 |
|---|---|
| **A** | ① CRLF 578 덱 → `indent`·`database`·`relax`·`strip` 4개 op 전부 출력 `CRLF=578·LF=579`(지금 0/0/**578 혼재**/578). 특히 `relax` 에서 **한 파일 안에 개행이 섞이지 않을 것**. ② LF 덱 전 op 출력 sha256 불변. ③ 원본이 말미 개행 없이 끝나면 출력도 없이 끝날 것(현 `strip` 은 1바이트 붙인다 — **동작 변경**, 골든 파일 재생성 동반). ④ CRLF 덱을 `restack`/`refine` 으로 돌려 `ModelAssembler.cpp:5517` 엄격 재독이 **rc=1 로 오판하지 않을 것**(재파싱이 `'\n'` 으로 자르므로 줄 끝 `\r` 이 고정폭 재독을 어긋내는 회귀 — 개행 수정과 **같은 커밋**에 들어가야 한다) |
| **F** | `python3 tools/regress/test_roundtrip_bytes.py <bin>` 이 픽스처 5종(LF / CRLF / 무-말미개행 / `I10=Y LONG=S` / 2줄 포맷 혼재) × 전 op 에서 **sha256 + `n_bytes` + `n_lines` + `n_crlf` 4개 동시 일치**. 무편집 진입점은 **반드시 각 op 의 read 경로를 태우고 write 경로로 낼 것** — `cat` 복사식이면 아무것도 못 잡는다 |
| **G** | ① 모든 op 이 종료 시 `Δbytes/Δlines/ΔCRLF` 한 줄을 찍는다(warn 모드에서도). ② `indent` 실행에 원장이 나온다(지금 한 줄도 없음). ③ cnrb2spring·strip·database·contact 등 자체 라이터 op 에도 나온다. ④ `strict` 키를 켜면 선언과 불일치 시 rc=1 이고 **파일을 안 쓴다**. ⑤ 기존 `test_pidref_detect.py`·`test_element_card_layout.py`·`test_restack_tennode.py` rc 단언 전부 불변 |
| **C** | ① `_ID`/`_OFFSET_ID`/`_ID_OFFSET`/`_ID_MPP` 4종 전부 `analyze` 가 `Slave: PID 1 (SSTYP=3)`(지금 뒤 2종은 `SET_SEGMENT 1000`=CID 오독). ② `modify friction:0.33` 후 **Card 2 fs 칸**에 0.33, **`ssid` 칸 불변**(지금 SSID 칸을 덮어쓴다). ③ `modify soft:2 depth:35` 후 **필수 Card 3 잔존** + Card A 추가(지금 Card 3 소멸). ④ 회귀는 **개수를 단언하지 말 것** — 개수만 보면 이 버그가 전부 통과한다. `examples/contact/model.k` 는 `_TITLE` 만 써서 이 경로를 한 번도 안 밟으므로 `_ID` 예제 추가 |
| **B** | ① `dt2ms: -1.0e-7` → 출력 `*CONTROL_TIMESTEP` 에 **음수 부호 보존**(지금 `1.0000E-07`). 실패가 아니라 **10칸 안에 들어가는 표기로 다시 포맷**하고 그래도 안 되면 raise 하는 순서. ② 8칸 덱에 9자리 ID 를 쓰려 하면 rc=1 + "폭 넘침" 이라고 말할 것(지금 `[요소 수 대조]` 가 원인을 "요소 수"로만 말한다). ③ I10 덱 `convert tet10` 출력의 **요소 카드가 10칸**(지금 8칸). ④ **우리가 새로 쓰는 값이 넘칠 때만 rc=1** — 입력 덱부터 어긋난 것은 WARN(`5581-5598` 이 이미 쓰는 규약을 따를 것) |
| **D** | ① `*DATABASE_HISTORY_SOLID_SET 7` 을 심고 merge → rc=1 오탐 사라짐. ② `*PART` 폴백 경로를 타는 덱에서 PID/SECID/MID 가 10칸으로 읽힘 |
| **O-min** | ① `dangling.k`(없는 set 9999 · CONTACT 8888/7777 styp=2 · CNRB NSID 6666 · SECID 555/MID 444 · SPC 999999) → **5종 전부 보고**(지금 `[OK] Mesh is valid` rc=0). ② `*SET_*_GENERATE`(범위쌍)·`*SET_NODE_ADD`(멤버가 세트 ID)·`*SET_NODE_GENERAL`(칸1 이 문자)·`*PARAMETER`/`&name`·PID=0 에서 **오탐 0건** — 기존 `maybe` 등급제(`2:3013-3016`)를 물려받을 것. ③ `*INCLUDE` 를 못 읽었으면 **"0건이라고 말할 수 없다"를 한 줄 박을 것**(`2785-2801` 규약 복제, 선택 아님). ④ 기본 warn·별도 채널 — 기존 `pid_refs: strict` rc 계약(`5750`,`3085`)을 건드리지 않을 것 |
| **P1-9 가드** | `_ORTHO` 덱으로 cnrb2spring → 지금은 `PART 12 <-> PART 500` rc=0. 수정 후 **rc≠0 + "unsupported" 명시**. 조용한 오답보다 시끄러운 거절 |
| **H** | `deck_open` 류 메타에 `n_crlf`·`newline`·`final_newline` 이 실려 나오고, CRLF 덱 업로드 시 `n_crlf>0` 으로 보고 |

---

## 6. 요청서 회신 — 사실과 달랐던 점

### 치명 (그대로 고치면 한 바이트도 안 고쳐진다)

1. **CRLF 소실 기전 오진.** "`KFileWriter.cpp:111,229` 가 `std::ofstream out(filename)` — 텍스트 모드다" 를 원인으로 지목했다. **리눅스 glibc 에서 텍스트 모드 ofstream 은 개행을 변환하지 않는다** — `o << "a\r\n" << "b\n"` → `od -c` 가 `a \r \n b \n`. 실제 원인은 **리더가 `line.pop_back()` 으로 CR 을 떼고 원 개행을 기록하지 않는 것**이며 **78곳**에 흩어져 있다.
2. **경로 오지목.** `KFileWriter.cpp` 는 CRLF 를 잃은 op(`indent`)의 경로에 **없다**. indent 의 라이터는 `ModelAssembler.cpp:5619` 이고 **이미 `std::ios::binary` 다**(확인). 사건표의 "텍스트 모드 I/O 가 700MB 덱을 LF 로 변환"도 같은 오진. 반증 — 똑같이 텍스트 모드인 `strip.cpp:177` 이 CRLF 를 **보존**한다.
   - 다만 **지목이 헛것은 아니다.** MSVC 빌드가 살아 있고(`scripts/build_windows.bat`, `CMakeLists.txt:14,24,190,253,298`), `src` 전체 `ofstream` 중 `ios::binary` 는 7곳뿐·`src/commands` 비-바이너리 40곳이다. CR 을 살려 넘기는 `strip.cpp:177` 은 윈도우에서 `\r\r\n` 을 뱉는다. **리눅스 CRLF 소실과 별개의 윈도우 버그이고, 두 개를 한 항목으로 묶은 것이 실수다.**
3. **"DF-20/21 없다" 는 틀렸다.** DF-20 ⑥ 은 완전히 구현돼 있다(`ModelAssembler.cpp:5483-5616`, commit 890f68a, 2026-09-18). 요청서대로 읽고 신규 구현하면 **있는 것을 두 번 짓는다.** 실제 결손은 ①②③④ 와 **발화 범위**다.
4. **"DF-06 검사가 없다" 는 과장.** `scanDeadReferences`(`2767`)가 해당 키워드를 실제로 훑고 회귀(`test_pidref_detect.py`)도 ALL OK 다. 정확한 서술은 **"이번 op 이 지운 ID 만 보는 델타 검사이고 절대 검사가 없다"**. 이 구분이 중요한 이유 — 요청서 근거인 TN4 가 정확히 후자이고 **델타 스캐너를 아무리 키워도 TN4 는 안 잡힌다**(`2775` early return).

### 사실 오류

5. **7자리 EID 잘림 재현 안 됨.** 7자리는 8칸에 들어가고 indent 왕복에서 EID·PID·NID 전부 보존. `99000`(5자)이 나오려면 5칸 필드가 있어야 하는데 리포에 `setw(5)`/`%5d` 0건. 실제 경계는 9자리. 그쪽 손스크립트 사고로 보인다.
6. **"자른다"는 서술이 C++ 쓰기 경로에는 안 맞는다.** `std::setw`/`snprintf` 는 자르지 않고 **칸을 늘린다** — 증상은 잘림이 아니라 뒤 칸이 통째로 밀리는 것이고, 잘림은 그 덱을 고정폭으로 다시 읽는 쪽(`KFileReader.cpp:506`)에서 생긴다. **raise 요구는 유효하되 고칠 자리는 리더가 아니라 라이터다.**
   - **단, 문자 그대로 자르는 곳이 따로 있다** — 요청서가 못 짚은 `*CONTROL` 값 경로. `fmt10d`/`fmt10i`/`setField`/`kw_setField` 가 앞 또는 뒤를 잘라 **DT2MS 음수 부호를 조용히 없앤다**. DF-03 의 실제 피해는 여기가 더 크다.
7. **`ElementCardLayout::optValue("I10")` 라는 API 는 없다.** `ElementCardLayout` 은 클래스가 아니라 자유함수 헤더이고 `optValue` 는 `keywordCardDeckWidth` 내부 지역 람다(`ElementCardLayout.cpp:85`). 밖에서 부를 수 없으니 "있는 부품"으로 세면 안 된다.
8. **`realFieldWidth(intFw)` 는 ID 폭 표가 아니다.** `intFw>=20 ? 20 : 16` — 정수 칸 폭 → 좌표 칸 폭 대응(Vol_I 19345/19348/19360)이다. 필드폭 표의 재료가 아니다.
9. **§2 표 "요소 카드에 국한된다" 가 `*NODE` 를 빠뜨렸다.** 실제 커버리지는 `*NODE` + `*ELEMENT_SOLID/_TSHELL/_SHELL`(`KFileReader.cpp:425` 는 parseNodeSection 안). §3.1 DF-02 본문은 제대로 적었으니 §2 표가 틀린 쪽이다.
10. **"`*PART`/`*SET_*`/`*MAT_*`/`*CONTACT_*` 의 그 표가 없다" 는 절반만 맞다.** 표(단일 출처)가 없는 건 사실이나 폭이 미정의라는 뜻이면 틀린다 — 값 10 이 **최소 8벌**에 하드코딩돼 있고 표준·i10 덱에서는 맞는 값이다. 진짜 결손은 (a) long=y(20칸)에서 저 10 들이 전부 틀리는데 막는 것이 없다 (b) **`*PART` 고정폭 폴백만 8칸이다**(요청서가 못 찾음).
11. **"`rjust(max(9,W))` 같은 폭 확대" 는 코드에 실재하지 않는다.** grep 0건. 지울 것이 없다. 금지해야 할 것은 `setw` 가 넘칠 때 **조용히 칸을 늘리는 것**(같은 행동의 C++ 판)이다.
12. **DF-04 "`(ten nodes format)` 을 섹션 헤더마다 개별 판정해야 하는데 규약이 없다" — 진단이 어긋났다.** 공용 계층은 꼬리글을 **일부러** 안 쓴다(`ElementCardLayout.cpp:15-16` 에 근거까지 적혀 있다). 판정 단위는 섹션이 아니라 **요소 카드 줄마다**라 요구보다 세밀하다. "T4 덱 5섹션 중 3개가 2줄"은 지금 코드로 **이미 안전하다**(꼬리글 유·무 × 1줄·2줄 4조합 혼재 덱을 restack·refine·convert·disconnect 로 돌려 전부 정답). 예외는 `elform` op 하나.
13. **DF-04 가 센 사본이 틀렸고 모자란다.** `ModelAssembler.cpp:4955` 는 사본이 아니다 — 그 `TEN NODE` 문자열 검사는 "새 요소를 어느 섹션에 붙일지" 힌트이고 `:5179` 에서 `eidx.span[i]>1` 로 덮어쓰인다. ModelAssembler 의 실제 판정(`ecBuildIndex:1400-1415`)은 **이미 `solidCardLines()`·`solidNodesFromElform()` 을 부르는 공용의 유일한 소비자다.** 못 짚은 진짜 사본 — `KFileReader.cpp:457-690`(리더 본체, `:666` 에서 `(nodes+9)/10-1` 로 공식을 손으로 다시 적었다), `cclip.cpp:802-853`, `ModelAssembler.cpp:7303`(elform, 유일하게 "파일 전체 1회 판정"이 일어나는 자리).
    - **그리고 사본의 진짜 위험은 1줄/2줄이 아니라 추가 카드(ORTHO Card4/5, DOF Card6)다.** 1줄/2줄은 사본들이 우연히 비슷하게 맞히지만 ORTHO 에서 갈린다 — cnrb2spring 이 `PART 12 <-> PART 500` 오답을 rc=0 으로 낸다. 공용 `ElementCardLayout.cpp:166` 은 ORTHO 를 `extraCards+=2` 로 **이미 알고 있다**.
14. **DF-05 "TIED 225 → 0개 오판" 재현 안 됨.** `_ID` 철자 4종 전부 225 를 225 로 센다. 개수가 0 이 되는 경로 자체가 없다. 도구 밖 손수 스크립트 사고로 보이며 리포의 결손 근거로는 쓸 수 없다.
15. **DF-05 예시 키워드의 옵션 순서가 매뉴얼과 역순이다.** Vol_I 67029-67040 — OPTION3=`ID` 가 OPTION4=`OFFSET` 보다 앞이므로 정규 철자는 `*CONTACT_TIED_SURFACE_TO_SURFACE_ID_OFFSET`. **얄궂게도 요청서가 쓴 `_OFFSET_ID` 는 현재 코드가 읽기에서 유일하게 성공하는 철자이고, 매뉴얼 정규 철자가 깨지는 철자다.** 요청서 철자대로만 코퍼스를 만들면 결손을 못 잡는다.
16. **DF-05 를 읽기 문제로만 규정한 것이 좁다.** 더 비싼 것은 쓰기다 — `ContactDef` 에 `hasId` 가 없어 `modify` 가 Card 2 값을 **Card 1 SSID 칸에 쓰고**(파트 참조 파괴), Optional Card 추가가 **필수 Card 3 를 지운다**. 요청서가 안전하다 가정한 `_OFFSET_ID` 에서도 터진다.
17. **부록 A 가 `_TITLE` 과 `_ID` 를 대등하게 적었다.** `*CONTACT` 페이지 OPTION3 허용값은 `ID` 하나뿐(Vol_I 67029). `_TITLE` 은 다른 페이지(Vol_I 239351)의 사실상 별칭이다. 코드가 둘 다 받는 건 실무적으로 옳으니 유지할 것. 판정식 `endswith("_ID") or "_ID_" in kw` 는 **매뉴얼 키워드 1,830개 전수 스캔에서 오탐 0**(`*EOS_IDEAL_GAS` 는 안 잡힌다) — 현재 코드보다 정확하다. 단 ID 옵션을 갖는 카드군(매뉴얼 14개)으로 **한정**해 쓸 것.
18. **§2 표 "DF-42 부피·질량 | info, modelmeta | 충분하다" 는 틀렸다.** modelmeta 는 **질량을 내지 않는다.** 셸은 `volume:0` 이고 두께도 안 내므로 rho 가 있어도 유도 불가. 이 판정을 두면 DF-08 의 `mass` 항이 "이미 있는 것"으로 잘못 정리된다. 파트별 `n_node` 도 없다.
19. **DF-07 "`max+1` 금지" 전제가 과장.** restack 은 이미 `layers[].pid`/`pid_start` 로 대역을 옮기고 충돌이면 rc=1, cnrb2spring 은 예약 대역 기본값 + 8 네임스페이스 재검사 + I8 상한을 이미 갖고 있다. 결손은 "대역 개념이 없다"가 아니라 **"두 op 에만 있고 공용·외부 등록표가 아니다"**.
20. **KMM 낙하판 PID 500323 / `sid 9000001` 은 리포 안에서 확인되지 않는다.** 두 번호의 유일한 출현이 요청서 자신(`docs/requests/…:64`). 관례의 존재는 확인됨(`test_restack_tennode.py:13` "사내 ID 관례(예약 대역)와 부딪혔다", 매뉴얼 869·885). **등록표를 도구에 넣으려면 실제 값을 주셔야 한다.**
21. **요청서가 안 적은 결손 5건.**
    - **쓰기 경로가 폭을 무시해 편집이 통째로 증발한다**(`parseNodeIdFromLine:5830`) — 좌표가 숫자로 시작하는 packed 덱에서 "147 nodes moved" 인데 출력이 입력과 **바이트 동일**, rc=0. DF-02 를 "읽기 판별을 넓히는 일"로만 잡으면 안 고쳐진다.
    - **`*INCLUDE` 를 안 보고 `max+1` 한다** — 인클루드가 감쇠용으로 점유한 `sid 6` 을 `contact create` 가 경고 없이 재발행, rc=0. 요청서가 든 사고 형태 그대로.
    - `histElem` `_SET` 제외 누락 → **rc=1 오탐**.
    - `*PART` 폴백 8칸(부록 A 위반).
    - `info` 가 validateMesh 실패에도 **rc=0**.
22. **인접 결손(코드 인용만, 런타임 미재현).** `*SET_*_GENERATE`/`_COLUMN` 을 cnrb2spring 은 unsupported 로 막는데(`:200,796`) 공용 `ct_parseSets`(`contact_helpers.cpp:216`)는 `_TITLE`/`_LIST` 만 떼고 GENERATE 의 범위쌍을 **그냥 ID 목록으로 읽는다**. "방언 지식이 op 한 곳에만 있다"의 또 다른 실례.

### 요청서가 과소평가한 것 (좋은 쪽으로)

23. **`strip` 은 LF·CRLF 덱 **둘 다** 바이트 동일**하다(무매칭 strip 왕복, `cmp` rc=0). 계약이 아니라 **우연**이지만(`strip.cpp:189,225` 가 CR 을 안 뗀다), DF-01 은 0 에서 시작하지 않는다. 어긋남은 **말미 개행 1바이트**뿐.
24. **`strip` 경로는 peak RSS 5.3MB(0.09x)** 로 덱 크기와 무관하다. `indent` 는 7.4x. **목표 아키텍처가 이미 한 파일 안에 있다.**
25. **DF-08 "실패 판정" 은 요청서가 아는 것보다 앞서 있다.** 요청서가 든 "AP 파트가 통째로 빠졌는데 Normal termination" 사고는 **바로 그 코드의 주석에 근거로 적혀 있다**. 남은 일은 (a) 관문을 `writeOutput` 밖 op 로 넓히기 (b) 덱 간 대조로 끌어올리기 둘이다.
26. **재고 데이터는 이미 DB 에 쌓인다.** `kfile_inspect.py:94-117`(업로드마다 info+modelmeta) + `worker/runner_loop.py:261-300`(산출물 meta + sha256, kind=input/output/generated). "원본"과 "per-run" 두 다리는 있고 **가운데 다리("템플릿")의 정의만 비어 있다.**

---

## 7. 요청 측에 필요한 것

1. **예약 대역 등록표의 실제 값** — 없으면 DF-07 은 골격만 만들고 비워 둔다.
2. **"템플릿"의 정의** — DF-08 3자 대조의 가운데 다리. 현 리포의 template 은 리포트용 파일명 매칭이라 무관하다.
3. **부록 B 코퍼스** — 단 **대기하지 않는다.** 저장소 안 픽스처 5종으로 SYS-02 최소 집합을 먼저 세운다. 코퍼스는 인자로 받아 있으면 추가로 돈다(없으면 skip, fail 아님).
4. **말미 개행 없는 덱**을 LS-DYNA·하위 전처리기가 어떻게 먹는지 — 확인 전에는 "원본을 그대로 따르는 쪽"이 안전하다고 보고 그렇게 갈 예정이다(현 `strip` 동작 변경).
5. **동작 변경 2건 합의** — (a) dangling 시 "덱은 씁니다" → "안 씁니다" (b) `info` rc=0 → 1. 둘 다 상위 파이프라인을 뒤집는다.

---

## 8. 커밋 분리 규칙

- **개행 수정과 `5500-5613` 왕복 검증 수정은 같은 커밋에.** `5517` 재파싱이 `'\n'` 으로 자르므로, 출력이 CRLF 가 되면 멀쩡한 결과가 검증 실패로 거부된다.
- **`_ID` 읽기 판정과 쓰기 4곳은 같은 커밋에.** 읽기만 고치면 `modify` 가 계속 SSID 칸을 덮어쓴다.
- **`5514 touched` 가드 해제와 `output.str()` 복사 제거는 같은 커밋에.** 게이트 확대가 3패스를 더한다. 이때 `const std::string& body = output.str();` 는 임시 객체에 const-ref 를 묶어 수명을 늘린 코드이므로 `rdbuf()`/`view()` 로 바꿀 때 dangling 주의.
- **`relax`·`strip` 출력 바이트 변경은 하류 고지 대상.** 통일하면 `relax` 의 혼재 출력(원본 CRLF + 새 줄 LF)이 전부 CRLF 가 된다 — 의도한 개선이지만 diff 로 검증하던 파이프라인이 한 번 흔들린다.
- **골든 파일 재생성 목록** — `examples/contact/*_result.k`(02~08), `replace_test/restack_result.k`, `disconnect/restack_czm_result.k`, `examples/tet10/tet10_result.k`. 말미 개행 +1바이트와 I10 덱 요소 카드 폭이 원인.
- **회귀 필수 실행 세트**(rs\* 헬퍼나 `ecBuildIndex` 를 건드리면) — `test_pidref_detect`·`test_pidref_migrate`·`test_pidref_key`·`test_pidref_adversarial`·`test_merge_pidref_standalone` + `test_restack_tennode`·`test_restack_literal_mid`·`test_restack_mid_direction` + `test_element_card_layout`·`test_tet4_format`·`test_cnrb2spring`. 전부 현재 ALL PASS 로 기준선이 살아 있다.