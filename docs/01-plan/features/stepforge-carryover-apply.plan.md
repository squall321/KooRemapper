# StepForge 이월 계획 적용 `apply_carryover_plan` — 계획 (2026-11-07)

StepForge `docs/REQUEST-2026-11-06-carryover.md`(`47cd7a1`)의 세 파일(계획 · 변위장 · 조각)을 받아 덱 PID 마다 처리를 적용하는 새 연산.
답신 `docs/requests/stepforge-carryover-reply-2026-11-07.md` 가 꼴 · 처리 · 질문 여덟의 답을 정한다.

## 사용자 결정 (11-07, 권장안 그대로)
- 답신 먼저 — 짓기는 StepForge 계획 파일 v2(PID 마다 덱 범위 · `snapshot.basis`/`project_id`)의 꼴이 정해진 뒤. 새 연산 이름은 지을 때 확인받는다.
- 나눠 쓰는 절점 — 거절하고 목록.
- 바꿔 넣기 · 지우기 PID 를 절점 · 세그먼트 · 요소로 가리키는 접촉 · 세트 — 거절하고 목록(PID 로 건 참조는 산다).
- 셸 두께가 바뀐 모프 — StepForge 가 새 섹션 카드를 낸다(우리는 그 PID 의 SECID 만 잇는다).

## 지금 있는 것 (11-07 소스)
`update`(*NODE 로 좌표 덮기) · `applyfold`(군별 강체 변환 — 나눈 절점 거절 · 되읽어 대조) · `id_floor`(덱 바닥) · `cad_solid_merge_to_deck`(새 파트 계약 — 이월
조각은 그대로 못 받음) · `rebind_entities_after_remesh`(정확히 같은 좌표만 — 새 메시에는 못 씀) · `info`(품질 지표).

## 다시 정한 것 (11-07 늦게)
- **지금 짓는다** — 사용자 「필요하면 서브에이전트 나눠서 빨리해」. StepForge 가 v2 에 더할 칸을 정확히 알려 왔다(v1 그대로 + 줄마다 덱 범위 ·
  `contiguous` · SECID · MID · `snapshot.basis`/`project_id` · `deck.includes`(늘 있음, 없으면 빈 목록) · `field.new_section` + `section_<PID>.k` ·
  transform 은 그쪽이 강체를 확인하고 아니면 review · 요소마다 셸 두께가 있으면 줄에 표시 · `version` 2). 그 목록으로 짓고 v2 실물이 오면 대조한다.
- **이름 `apply_carryover_plan`** — 사용자 확인(11-07).
- **판 2 받기(11-07 저녁 — StepForge `60f8969` · 코드 `4295f7d` · 라이브 9525)** — 정본은 그쪽 요청서 §10. 사용자 결정 둘 —
  ① 인클루드가 있는 덱은 `deck.includes` 를 대조해 받되 **주 덱만 고친다** — 고칠 자리(바꿀 PID 의 요소 · 절점 · `*PART` · 섹션)가 인클루드 파일에 있으면
  거절하고 목록(인클루드 파일은 쓰지 않는다). ② 줄마다 실린 덱 자리(절점 · 요소 범위와 수 · 이어짐 · SECID · MID)가 우리 셈과 다르면 **손대는 줄은 거절**,
  keep · review 줄은 경고. 실물 둘(바깥 덱 `fc160119a36e` · 메시 덱 `f8ff42845904`)은 받은 바이트 지문이 계획과 같고, 지금 배포 판(`752fa2b`)은 둘 다
  `version 2` · 모르는 칸으로 거절한다(엄격 읽기가 설계대로).

## 체크리스트
- [x] 새 연산 이름 사용자 확인 — `apply_carryover_plan`
- [x] v2 실물 받기(11-07 — 실물 둘 · 지문 대조 · 지금 판은 거절함을 확인)
- [x] v2 짓기 — 칸은 `src/parser/CarryoverPlan.cpp` 머리의 `kKeys` **한 표**에(줄마다 판 1 칸 · 판 2 가 더한 칸) · 인클루드 대조(주 덱만 고침) ·
      줄마다 덱 자리 대조 · 새 섹션 · refused_transform · summary 대조(아래 「판 2 받기 — 지으며 정한 것」)
- [x] v2 실물 둘 · 인클루드 꼴 · 셸 두께 모프 꼴로 시험 — `tools/regress/test_apply_carryover_plan_v2.py` 67 항 · 단위 시험 v2 5 · 실물 둘 rc 0(문제 0 · 경고 0)
- [ ] 적대적 검토 · 배포 · StepForge 에 알림(답신 부록)
- [x] 읽기 — 계획(엄격) · 변위장(이진) · 조각(덱 SECID · MID 참조 꼴) — `include/parser/CarryoverPlan.h`
- [x] 사전 검사 — 꼴 · 덱 지문 · 파일 지문 · 변위장 덮음 · 조각 범위 대 바닥 · 참조 · 나눈 절점(전부 아니면 전무) — v1 이라 includes 는 거절
- [x] 처리 — transform(강체 확인) · morph · remesh(같은 PID 로 바꿔 넣기 · new_section) · delete · add · keep/review(`touches_changed` 보고) —
      morph 의 new_section(두께)은 v2(지금은 `field.thickness` 가 있으면 거절)
- [x] 되읽어 대조 · 품질 관문(새로 뒤집힌 솔리드 · 뒤집힌 셸 법선이면 산출을 지운다) · 보고(PID 마다 · 적용 덱 sha256) — `src/assembly/CarryoverApply.cpp`
- [x] 시험 — 진리값 판(`examples/apply_carryover_plan`) · 12 파트 덱(`tools/regress/data/apply_carryover_plan/mesh12`) ·
      거절 16 · CRLF · 바닥 · 품질 · 리뷰 11-07 고침(H · I · J)(`tools/regress/test_apply_carryover_plan.py` 80 항) · 리더 단위 시험(`tests/test_CarryoverPlan.cpp` 10)
- [x] 리뷰 11-07 고침 — 아래 「리뷰 11-07 고침 — 정한 것」
- [x] 바닥 — `idMaxima()` 의 요소가 보 · 이산 · 질량 · 안전띠 · 플롯 요소까지(`id_floor` · `cad_solid_merge_to_deck` 같이, `test_id_floor` E)
- [x] help · 카탈로그 · 개행 행렬 제외 · ofstream 선언

## 지으며 정한 것 (11-07 — 다음 세션이 다시 따지지 않게)
- **보고는 거절해도 쓴다** — 저쪽이 걸린 것 전부를 읽고 계획을 고친다. YAML 이 틀려 보고 자리를 모를 때(모르는 키 · output 없음)만 콘솔뿐.
- **조각 바이트가 다를 때의 값 대조** = 조각 엄격 읽기 + 머리 대조(번호 구간 · 수 · PID · SECID · MID · 요소 꼴 · 새 섹션 카드 · 요소가 쓰는 절점이
  다 있고 안 쓰는 절점 없음). 좌표는 대조하지 않는다 — 그래서 받되 **경고**(`fragment_bytes`)다. 변위장은 지문이 다르면 거절
  (파일의 몫은 확장자가 아니라 줄이 정한다 — 리뷰 11-07).
- **remesh 조각의 SECID · MID** — new_section 이 없으면 덱 `*PART` 의 SECID 와 같아야 하고, MID 는 늘 덱 `*PART` 의 MID 와 같아야 한다
  (다르면 거절 — 섹션을 바꾸는 꼴은 new_section 뿐). 섹션 종류(셸 · 솔리드)가 조각 요소 꼴과 맞아야 한다.
- **`*PART` 변형**(`_INERTIA` 등)은 remesh · delete 만이 아니라 transform · morph 도 거절 — 무게중심 · 관성 칸을 함께 옮길 규칙이 없다.
  keep · review 줄은 변형 PID 도 받는다.
- **추가 줄의 조각이 ok false** — remesh 줄처럼 거절(새 파트가 조용히 빠진 덱을 내지 않는다). 조각이 null 이면 보고만(`skipped` · why).
- **정본이 단정하지 못한 자리(notChecked)** 는 고칠 덱 전체의 문제로 거절하되, 칸 자리를 아는 격자 밖 요소 블록(보 · 이산 · 안전띠 · 질량)이
  낸 몫은 뺀다 — 그 요소의 절점은 나눠 쓴 절점 검사가 정확히 셌다.
- **방언 세트**(`_GENERATE` · `_ADD` · `_INTERSECT`)는 정본 칸 표가 조용히 건너뛴다 — 정본 해석기(`ct_setMembers`)로 풀어 바꿔 넣기 · 지우기 PID 를
  담으면 거절(`set_member`). 접촉 면(STYP 0 · 1 · 4, 지우기는 2 · 6 도)은 풀 수 없으면 거절(`contact_side`).
- **셸 중간절점(N5-N8)** — 리더가 담지 않아 이월 적용이 직접 읽어 PID 절점에 넣는다(옮기기 · 지우기 · 나눠 쓴 절점).
- **품질 잣대** — 사면체 6V(`Validator`) · 육면체 · 쐐기 2×2×2 가우스점 최소 야코비안(`ElementQualityChecker`) ≤ 0 = 뒤집힘. 셸은 두 대각선 외적이
  앞뒤로 반대(또는 0)면 뒤집힘(모프만 — 옮기기는 det +1 강체라 뒤집을 수 없고 새 셸은 앞이 없다 · 리뷰 11-07). 바꿔 넣기 · 새 파트는
  새 요소가 하나라도 뒤집히면 거절.
- **바닥** — 새 counter `maxAuxElementId_` 를 `idMaxima()` 에만 넣었다. 다른 op 의 새 요소 번호(`maxElementId_`)는 그대로다(LS-DYNA 번호는 요소
  종류마다 따로다 — 바꾸면 30곳 op 의 번호가 움직인다).
- **남은 것** — `auxElementCard` 의 `*ELEMENT_MASS` PID 칸이 3(8칸 자르기)인데 매뉴얼 꼴은 EID I8 · NID I8 · MASS E16 · PID I8 이라 8칸으로는 칸 4 다
  (`IdRefs` 도 같은 자리). 이월 적용은 그 PID 를 「PID 에 질량 요소가 있다」(aux_in_part) 판정에만 쓴다 — 정본을 고치는 일은 따로(리뷰 11-07 —
  공용 코드 갈래가 고친다. 그 전까지는 지우는 PID 를 가리키는 질량 요소를 이 op 이 못 잡는다 — 재현 `MASS1_pid_deleted`).

## 판 2 받기 — 지으며 정한 것 (11-07 저녁 — 다음 세션이 다시 따지지 않게)
정본은 StepForge 요청서 §10(그쪽 main `60f8969` · 코드 `4295f7d` — `core/carryover_build.py` · `core/kfile.py`). 사용자 결정 둘은 위 「다시 정한 것」.
- **칸 표** — `kKeys` 한 표에 줄마다 판 1 칸과 판 2 가 더한 칸(`required2` · `optional2`)을 함께 적는다. 판 2 에만 있는 묶음(줄의 `deck` ·
  `includes` 한 줄 · 모프 `new_section` · `element_thickness` · `refused_transform` · `summary`)은 앞 두 칸이 비었다. 모르는 판(3 …)은 가장 새
  판의 표로 나머지를 보고 판은 따로 거절한다. `deck.max` 의 secid · mid 는 판 1 부터 있다(판 2 는 「닫힘 전체에서 센다」로 뜻만 넓혔다).
- **summary 대조** — 판 2 만. actions(줄의 처리 수 · 강체 아닌 옮김은 review) · sections(새 섹션 파일을 실은 모프 줄) · failed(그쪽 `_failed`
  그대로 — 조각 · instead 의 ok false · 파일이 없거나 check.ok 가 참이 아닌 변위장 · 파일 없는 new_section)를 다시 세어 다르면
  `plan_inconsistent`. added · fields · fragments 는 판 1 과 뜻이 같아 대조하지 않는다(판 1 은 summary 를 꼴만 본다 — 그대로).
- **인클루드** — `deck.includes` 와 우리 닫힘을 relpath(주 덱 폴더 기준 · `lexically_relative` · `/`) · sha256(파일 바이트 전부) · 차례로 견준다.
  닫힘은 `include_closure::inlined` 가 다 읽어야 한다 — 그쪽은 같은 파일을 두 번 끌어오면 건너뛰지만(불완전 아님) 우리는 순환 ·
  두 번 끌어옴도 거절한다(LS-DYNA 는 다시 읽어 번호가 겹친다 — 안전한 쪽). 펼친 줄(줄마다 온 파일 · 줄 — `LineOrigin`)과
  `readFileWithIncludes` 메시로 모든 검사를 하고 주 덱(`rawLines_`)만 고친다. 고칠 자리 = 바꿀 PID 의 `*PART`(`partFile`) · 요소(닫힘 메시와
  주 덱 메시의 차) · 그 절점(인클루드 `*NODE` 를 훑는다) · 새 섹션이 옮길 옛 섹션 카드 — 하나라도 인클루드면 `include_edit`.
- **산출 자리(스펙이 열어 둔 것)** — 인클루드 덱의 산출은 **덱과 같은 폴더에만** 쓴다(`include_output`). 산출은 `*INCLUDE` 줄을 그대로 두고
  LS-DYNA · 우리 리더는 그 이름을 산출 덱 폴더에서 찾는다 — 다른 폴더면 그 덱은 다른(없는) 파일을 끌어와 되읽기를 덱 폴더 기준으로 풀어도
  쓴 덱이 틀린다. 그래서 「덱 폴더 기준으로 풀어 대조」 대신 거절을 골랐다(더 단순하고 산출이 그 자리에서 옳다). 되읽기는 산출의 닫힘이
  대조한 닫힘과 같은지 보고 닫힘째 읽는다. output · report 가 닫힘 파일과 같으면 러너가 아무것도 쓰기 전에 거절한다(`clobberPair`).
- **덱 자리** — 그쪽 `part_ranges()` 정의를 닫힘 메시로(격자 요소 · `forEachElementNode` + 셸 N5-N8 · 0 제외 · PID 하나씩 정렬 · 고유). SECID ·
  MID 는 닫힘의 맨 `*PART`(`*PART_TITLE` 도) — 그쪽 리더는 `*PART_TITLE` 을 모르는 카드로 건너뛴다(그런 덱이면 우리 값이 null 이 아니라
  손대는 줄은 거절된다 — 안전한 쪽). 다르면 손대는 줄 `deck_range` 거절 · keep/review 경고. 실물 둘은 줄 20 개 모두 같았다(경고 0).
- **새 셸 섹션** — 파일은 지문이 정확해야 한다(값 대조로 받지 않는다 — 바이트가 곧 카드다). 엄격 읽기는 「카드 하나」를 LS-DYNA 처럼 센다
  (빈 줄도 카드 · 끝의 빈 줄만 여백 · `_TITLE` 제목 · Card 1 · Card 2 · ICOMP 1 이면 각도 카드 ceil(NIP/8) — NIP 0 은 2 · ELFORM 101~105 는
  딸린 카드 묶음이라 거절). 옛 카드와는 블록째(키워드 줄부터 다음 키워드 앞까지 — 그쪽 `section_card` 가 옮기는 자리) 줄마다 견주고
  Card 1 앞 10칸 · Card 2 앞 40칸만 다를 수 있다. 쌓인 둘째 카드가 든 블록은 카드 하나가 아니라 거절된다. T1~T4 는 계획 thickness 와
  상대 1e-9(그쪽은 카드에 쓴 값을 되읽어 싣는다). SECID 차례 — 조각의 새 섹션(remesh · 새 파트 줄)을 먼저, 모프 줄은 그 뒤 줄 차례.
  판 2 조각의 새 SECID 도 deck.max.secid 위인지 본다(`secid_order`).
- **요소마다 두께** — 계획의 `element_thickness` 만 믿지 않는다. 새 섹션을 넣을 모프 PID 의 셸 카드(THICKNESS · BETA · MCID 옵션)에서 THIC 가
  0 이 아니면(못 읽는 칸도) `element_thickness` 로 거절 — 그 두께가 섹션 두께를 덮어 새 섹션이 조용히 먹지 않는다.
- **instead(조각으로 물러선 줄)** — 판 1 처럼 받지 않는다(`morph_instead` — 우리는 변위장만 쓴다). new_section 이 못 지은 꼴이면 그 까닭을
  `new_section` 으로 함께 싣는다. element_thickness 가 있어도 두께가 그대로면(new_section null) 모프를 적용한다(그쪽 코드 — §10.2).
- **판 1 의 field.thickness 거절은 판 1 에만**. 판 2 는 thickness + new_section null = 섹션 그대로.
- **보고** — `plan.deck_from` · `deck.includes`(대조한 닫힘 · 아니면 null) · 줄의 `refused_transform` · 모프 줄 `new_section {secid, thickness}`.
  판(format version 1)은 그대로다 — 칸만 더했다(그쪽은 아직 보고를 읽지 않는다 — `git grep dynaforge-carryover-apply` 0).
- **`*PART` SECID 칸 폭** — 블록 키워드의 폭으로(표준 · i10 10칸 · long · `+` 20칸). 예전 `putField10` 은 키워드 `+` 덱에서 칸을 틀렸다.

## 판 2 적대적 검토(11-07 저녁) 고침 — 정한 것
- **쌓인 카드의 SECID(#1)** — 겹침 · 차례는 `*SECTION_*` 블록의 데이터 줄마다 첫 칸 정수를 SECID 로 넉넉히 센 집합(`sectionIdsAnyCard`)으로
  본다(조각의 새 섹션 · 모프의 새 섹션 · 판 1 · 2). 있나 · 종류(셸 · 솔리드)는 예전처럼 첫 카드 표(`definedSectionIds`)로 — 넉넉한 집합을
  「있다」 로 쓰면 없는 SECID 를 받는 쪽으로 틀린다. 번호 커서(`cur_scanSectionIds` → `maxSectionId_` · `idMaxima().section`)도 같은
  틈이 있다(쌓인 카드 SECID 를 다른 op 이 새 섹션으로 다시 낼 수 있다) — 공용 커서라 이번에는 고치지 않았다(다른 op 의 번호가 움직인다).
- **덮어쓰기 · 지우기(#3)** — 읽는 파일 = 주 덱 · 계획 · 닫힘 · 계획의 동반 파일(`files` 키 + 줄의 field · new_section · fragment · instead 이름).
  report 가 겹치면 콘솔로만 거절(보고 자리가 없다), output 만 겹치면 보고에 `output_clobber`(예전 output == model 은 콘솔로만이었다 — 같은
  길로 모았다). 거절의 옛 산출 지우기(J-3 · 리뷰 11-07 결정)는 그대로 두되 입력이면 건너뛴다. extract-parts 갈래의 「임시 파일 + 성공 때
  이름 바꾸기 · 실패하면 옛 파일 그대로」 로는 옮기지 않았다 — 그러면 J-3(거절하면 옛 덱을 지운다)이 뒤집힌다(그 결정은 사람이 정할 일).
- **보고 UTF-8(#4)** — 둘 중 「실을 때 고친다」 를 골랐다 — 보고의 모든 글자(`q()`)를 바른 UTF-8 로(깨진 바이트 → U+FFFD), 줄 자르기는 글자
  경계에서. 계획 글자를 `plan_json` 으로 거절하는 쪽은 덱 · 경로에서 온 깨진 바이트를 못 막고, 한 글자 때문에 계획 전체의 문제 목록을 잃는다.
- **링크 덱의 폴더(#5)** — 산출 폴더 규칙은 「준 경로 그대로의 폴더」 를(폴더만 정규화) 쓴다 — 닫힘(`dirOf(model)`) · 되읽기(`dirOf(output)`)와
  같은 자리. 파일 경로를 정규화하면 덱 링크를 따라가 다른 폴더가 나왔다.
- **`*END` 둘(#6)** — 쓰기(`ModelAssembler::writeOutput`)의 `*END` 갈래에 깃발 하나(`endInsertsDone`) — 덧붙임은 주 덱의 **첫** `*END` 앞에만,
  둘째부터는 줄만 옮긴다. 그 갈래가 내는 것 전부(더한 절점 · 솔리드 · 티쉘 · 셸 요소 · 키워드 블록 · dynain · IGA `*INCLUDE` · DR 카드)가 같이
  고쳐진다. `addedKeywordBlocks_` 를 채우는 op — applyCarryoverPlan(조각 · 새 셸 섹션) · applyCadSolidMerge · applyRestack · applyOffset ·
  applyDisconnect · applyConnectionCZM · applyConnectionContact · createCzmElementsForDualOffset · addContactHint · migrateDeadReferences ·
  processDeadReferences · insertMaterialCard · createPartKeyword · createSectionSolid · createSectionShell · createSectionTShell · applyLoad ·
  applyControl · applyDatabase · applyMerge — 모두 「덱 끝(*END 앞)에 한 벌」 을 뜻했다(첫 *END 뒤 벌은 해석에 안 들어가고 같은 번호 카드만
  늘렸다). 쓰기 밖에서 rawLines_ 를 고쳐 넣는 갈래는 손대지 않았다 — applyMatswap · applyMatdb · applyLoad 의 끼움은 첫 *END 만(`inserted`),
  applyContact · applyBoundary · applyRbe 는 *END 마다(같은 틈) · applyBattery 의 `*INCLUDE` 는 마지막 *END 앞(첫 *END 뒤라 안 읽힌다) — 알렸다.
- **수의 끝자리(#7)** — 보고의 수(`num`)는 15 → 16 → 17 자리 중 다시 읽어 같은 double 이 되는 첫 꼴. `%.17g` 하나로 쓰면 왕복은 되지만
  0.6 이 `0.59999999999999998` 로 길어져 사람이 읽는 보고가 흐려지고 예전 보고와 글자가 갈린다 — 짧게 맞는 값은 예전 글자 그대로다.

## 리뷰 11-07 고침 — 정한 것
리뷰(11-07) 결함 11 + 그럴듯한 둘을 고쳤다. 공용 코드(i10 조각의 쓰기 관문 왕복 · 솔리드 · 티쉘 변형의 바닥 · `*ELEMENT_MASS` PID 칸)는 다른 갈래 몫.
- **요소 블록 판정(결함 1)** — 덱을 고치는 줄(옮기기 · 모프 · 바꿔 넣기 · 지우기 · 조각 있는 새 파트)이 하나라도 있으면, 절점 칸을 다 읽지 못하는
  `*ELEMENT_*` 블록이 있을 때 **전부** 거절(`opaque_elements` — 키워드마다 첫 줄 · 블록 수 · 까닭). 다 읽는 것은 둘뿐 —
  ① 리더가 메시에 그대로 담는 격자 블록(`KFileReader::parseFile` 의 갈래를 옮긴 `readerReadsGrid`: `*ELEMENT_SOLID` · `_SOLID_TITLE` · `*ELEMENT_TSHELL` ·
  `_TSHELL_TITLE` 은 이름이 같을 때만, `*ELEMENT_SHELL` 은 `parseElementKeyword` 가 받는 변형 — 단 `_DOF` 는 Card 5 의 NS1-NS4 를 아무도 읽지 않아 뺀다)
  ② 칸 자리를 아는 격자 밖 블록(`auxElementCard`) — 보는 옵션 카드에 절점이 있는 `_WARPAGE`(SN1 · SN2) · `_ELBOW`(MN)를 뺀다. Card 1 의 N3(방향 절점)은 읽는다.
  ⚠ `readerReadsGrid` 는 리더 갈래의 사본이다 — 공용 갈래가 「리더가 담는 키워드」 판정을 정본에 두면 그것으로 바꾼다.
- **참조 덮음 표(결함 2)** — 바꿔 넣기 · 지우기 줄이 있으면 덱의 키워드마다 `refCover`(CarryoverApply.cpp)로 가른다. 정본(NodeRefs · IdRefs · 접촉 면)이 읽거나 세는
  갈래 · 참조 없는 키워드 표 · 파트 칸만 아무도 안 읽는 갈래(지우기만 막는다) 밖은 **거절**(`ref_unscanned` — 키워드마다 한 번 · 첫 줄). 모르면 Free 가 아니다.
  - 참조 없는 표(매뉴얼 칸을 본 것만) — `*KEYWORD` · `*TITLE` · `*END` · `*COMMENT` · `*NODE` · `*PART`(+`_CONTACT`) · `*SECTION_SOLID/SHELL/TSHELL/BEAM/DISCRETE/SEATBELT` ·
    `*MAT_*`(빼는 것: `_ADD_*` · `_NONLOCAL` · 6DOF 스프링 093/095 — 파트 칸, `_WINFRITH_CONCRETE_REINFORCEMENT` — 요소 칸) · `*EOS_*` · `*HOURGLASS` · `*DAMPING_GLOBAL` ·
    `*DEFINE_CURVE` · `_CURVE_SMOOTH` · `_TABLE`(2D · 3D) · `_BOX` · `_VECTOR` · `_COORDINATE_SYSTEM`(`_CURVE_FUNCTION`(DX(n)) · `_CURVE_FEEDBACK`(PID) ·
    `_CURVE_TRIM`(NSEED) · `_COORDINATE_VECTOR`(NID) · `_VECTOR_NODES` 는 아니다) · `*PARAMETER*` · `*CONTROL_*`(빼는 것: `_FORMING_*` · `_IMPLICIT_SOLUTION`(ARCCTL 절점) ·
    `_COARSEN` · `_2D_REMESHING_REGION` · `_SPOTWELD_BEAM` · `_STAGED_CONSTRUCTION` · `_SEGMENTS_IN_ALE_COUPLING`, 파트 칸만: `_REFINE_*` · `_ADAPTIVE_CURVE` ·
    `_SUBCYCLE*` · `_MPP_DECOMPOSITION_*PART*`) · `*DATABASE_BINARY_*` · `_EXTENT_*` · `_FORMAT` · `_NODAL_FORCE_GROUP` · `_HISTORY_*_SET` · ASCII 출력(GLSTAT · MATSUM ·
    NODOUT · RCFORC …, `_RCFORC_MOMENT` 는 절점 칸이라 아니다) · `*BOUNDARY_SPC_SET*` · `*INITIAL_VELOCITY` · `*LOAD_BODY_X/Y/Z/RX/RY/RZ/VECTOR/PARTS` ·
    `*LOAD_SEGMENT_SET` · `*LOAD_SHELL_SET` · `*RIGIDWALL_PLANAR`(`_ID` · `_FINITE` · `_MOVING` 만 — `_ORTHO` · `_FORCES` 는 절점 칸). 세트 ID 만 가리키는 칸은 된다
    (세트 멤버는 정본 · 해석기가 본다).
  - 파트 칸만(지우기만 막는다) — `*INITIAL_VELOCITY_RIGID_BODY` · `*CONSTRAINED_RIGID_BODY_STOPPERS` · `*CONSTRAINED_EXTRA_NODES_NODE`(절점은 정본) · `_SET` ·
    `*DAMPING_RELATIVE` · `*DEFINE_FRICTION` · 위 `*MAT_*` · `*CONTROL_*` 파트 칸 · 보 `_PID` 옵션(PID1 · PID2).
  - 정본이 읽지만 덜 읽는 것 — `*LOAD_NODE_POINT` 의 M1-M3(DOF 4 · 8 의 따름 힘 절점)가 0 이 아니면 거절. 정본 접촉이라도 카드 1 꼴이 다른
    `*CONTACT_ENTITY` · `_GEBOD` · `_1D` · `_2D` · `_RIGID_SURFACE` · `_AUTO_MOVE` · `_COUPLING` · `_ADD_WEAR` · `_EXCLUDE_INTERACTION` · `_INTERIOR` · `_SPG` ·
    `_GUIDED_CABLE` 은 거절. CNRB · `*DEFINE_COORDINATE_NODES` 의 변형은 정본이 첫 정의만 읽어 거절.
  - 세트 — 종류를 모르는 세트(`*SET_DISCRETE` · `*SET_NODE_INTERVAL` …)는 `ref_unscanned`, 풀 수 없는 방언(`_GENERAL` · `_ADVANCED` · 없는 멤버 · 순환)은
    `set_unresolved`(파트 세트는 지우기 줄이 있을 때만). `_COLUMN` · 평범한 목록은 정본이 읽는다.
  - 표의 근거는 `docs/LSDyna/Vol_I.txt` · `Vol_II.txt` 칸 설명(「Node ID」 · 「Part ID」 · 「Element ID」 · 절점 칸 이름)이다. 흔한 낙하 덱 꼴(제어 · 출력 · 곡선 ·
    세트 구속 · 초기 속도 · PID 접촉)을 받는지 회귀 H-8 이 본다.
- **EID 겹침(결함 3)** — LS-DYNA 는 요소 종류마다 번호가 따로라 겹쳐도 된다. 그러나 리더는 요소를 번호 하나로 들고 쓰기는 지울 번호를 모든 요소 블록에서
  지운다 — 덱을 고치는 줄이 있으면 거절(`eid_collision` — EID · 키워드 · 줄). 큰 덱에서 EID 표를 짓지 않게 격자 카드 수 = 메시 EID 수 · 격자 밖 EID 가 안 겹치면 건너뛴다.
- **강체 허용(결함 4)** — max|RᵀR − I| · |det − 1| ≤ 1e-6(StepForge 의 round(x, 9) 가 RᵀR 에 ~2e-9 를 쌓는다), 보고는 `%.12g`.
- **셸 법선(결함 5)** — 모프만 견준다. **T1(결함 6)** — 상대 1e-4(StepForge `%10.5g`).
- **주입(결함 8)** — 덱에 쓰는 계획 글자(이름 · 파일 이름)의 제어 문자를 빈칸으로. 조각 줄의 제어 문자(탭 밖)는 거절 — 주석 · 제목 줄은 글자 그대로 들어간다.
- **동반 파일의 몫 · 예외(결함 9)** — 몫은 줄이 정한다(morph 의 field.file · remesh · 새 파트의 fragment.file). 어느 줄도 안 쓰는 파일은 확장자와 무관하게 경고만
  (`file_mismatch_unused` — 전에는 `.bin` 이면 거절). 이 op 안의 예외는 보고(`internal_error`)를 쓰고 덱을 남기지 않는다.
- **`*END` 없음(결함 10)** — 조각을 넣을 때만 `deck_no_end`(쓰기가 블록을 *END 자리에 낸다). 옮기기 · 모프만이면 받는다.
- **StepForge 실제 꼴(결함 11)** — 못 지은 조각은 `{ok, why}` · `{ok, why(null), notes}` · `{ok, 조각 칸, check{why · problems}}` — 까닭은 why → notes.why →
  check.why → check.problems 차례로 `fragment_failed` 에 싣는다. transform 의 `check` 는 선택이다.
- **그럴듯한 둘** — 돌리면(R ≠ I) `orientation_not_rotated` 경고(재질 축 · 좌표계 · MCID · 초기 응력은 돌리지 않는다). 거절하면 출력 자리의 옛 덱을 지우고
  `stale_output_removed` 로 적는다.
