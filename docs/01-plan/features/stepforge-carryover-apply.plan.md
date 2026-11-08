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
- **11-07 밤 사용자 결정 둘** — ① 거절 · 실패 때 출력 자리의 앞 실행 덱을 지우던 규칙(`stale_output_removed`)을 extract-parts 와 맞춘다 —
  임시 파일에 쓰고 성공하면 바꿔 넣는다 · 거절 · 실패면 앞 파일은 그대로 · 보고는 늘 쓴다(플랫폼에서 앞 잡의 출력이 지워지지 않게).
  ② StepForge `591d5b5` 의 권고 셋 + 하나를 받는다 — 요소 `_TITLE` 블록은 읽지 않는 블록(그 PID 를 고치면 거절) · 정수 칸의 실수 꼴
  (`5.000e+00`)은 그 정수(LS-DYNA 실행 기록) · 열 재질 `*MAT_T01`~`T18` 은 MID 셈에서 뺀다(Vol II) · 손대는 PID 의 SECID · MID 가 두 번
  정의돼 있으면 거절(`part_duplicate` 처럼 — 두 앱이 같은 줄에서 멈춘다).
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
- [x] 적대적 검토 · 배포 · StepForge 에 알림(답신 부록 §6 — 11-08)
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
  → 11-07 밤 사용자가 정했다 — extract-parts 와 같게(아래 「11-07 밤 결정 고침」).
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
- **지문은 읽은 바이트의 것(그럴듯한 하나 — gdb 로 재현해 실제 결함이었다)** — 줄은 담을 때(`loadBaseModel` · `readIncludeClosure`),
  지문은 적용할 때(① · ②b) 읽었다. 잰 바이트를 담은 줄과 견준다(`carryover::bytesGiveLines` — 주 덱은 getline + CR 하나, 인클루드는
  닫힘 리더 `Walker::card` 꼴의 사본 · 단위 시험이 둘을 묶는다). 다르면 `deck_changed`. 바이트를 담을 때 함께 들고 있는 쪽(닫힘 · 리더를
  고쳐 바이트를 넘기는 것)은 공용 코드라 고르지 않았다. 남는 틈 — 메시 읽기(`readFile` · `readFileWithIncludes`)는 따로 연다: 주 덱 메시는
  줄보다 먼저(몇 ms), 닫힘 메시는 지문 뒤에 읽는다 — 인클루드는 쓴 뒤 닫힘 대조가 다시 재고, 주 덱은 되읽기 대조가 거의 잡는다.
  회귀 R-8 은 gdb 로 `applyCarryoverPlan` 에서 멈춰 파일을 바꾼다(검은 상자로는 한 프로세스 안의 두 읽기 사이를 못 끼운다 · 단위 시험은
  ModelAssembler 를 링크하지 못한다 — 명령 갈래 심볼). gdb 로 멈추지 못하면 SKIP.

## 11-08 적대적 검토(판 2 · 셋째 묶음 고침) 고침 — 정한 것
- **10진만(#5)** — `parseIntegral` 이 `strtod` 로 실수 꼴을 읽어 16진(`0x2`) · `0x1.8p0` 을 받았다(NIP `0x2` → 2). `isDecimalNumber`
  ([+-]? 숫자 [. 숫자] [e[+-]숫자])를 지난 글자만 `strtod` 에 넘긴다 — `parseReal`(T1~T4 같은 실수 칸)도 같은 문을 지난다. StepForge 리더의
  `int()` · `float()` 가 받는 10진 꼴과 같다(파이썬 `float` 도 16진을 안 받는다). 공용 SECID 훑기의 줄 셈이 쓰는 `carryover::integralField`
  가 이 규칙의 바깥 문이다.

- **SECID 는 카드 묶음으로(#2 · 8f6761a · 9298665 의 퇴행)** — 11-07 판의 「섹션 블록의 모든 행 첫 칸」 셈은 제목(`2024` · `12 mm plate`) ·
  정수 두께(`12`) · 정수 각도(`90`)를 SECID 로 세어 정상 판 2 계획의 새 섹션(조각 9 · 모프 10 — StepForge 591d5b5 가 deck.max.secid 8 을
  내는 덱)을 `secid_order` 로 거절했고 커서를 부풀렸다(2535716 은 받았다). `cur_scanSectionSets` 가 StepForge `card_sets` 와 같은 규칙으로
  가른다 — SOLID 1 · SHELL 2 + ICOMP 1 각도 ceil(NIP/8) · TSHELL 1 + 각도(ELFORM 101~105 · ICOMP 0 · 1 밖 · 못 읽은 칸이면 모름) · `_TITLE` 은
  묶음마다 제목 줄 · 빈 줄도 카드(끝의 빈 줄은 여백) · 묶음의 SECID 칸은 숫자만. 모르는 꼴과 못 가른 자리부터는 행마다 첫 칸 숫자(`loose` —
  StepForge `secid_bound`). 커서 · 이월 적용의 차례(`sectionIdTop`) · 겹침(`sectionIdsInUse`)이 이 셈 하나를 쓴다. 겹침도 넉넉한 셈을 거두었다 —
  ICOMP 1 덱에서 StepForge 가 새 SECID 를 각도 숫자(90)와 같게 매길 수 있어 그것을 겹침으로 거절하면 같은 거짓 거절이다(모르는 꼴만
  넉넉히). 커서가 옛 첫 카드 셈(공백 토큰 — `2.0` → 2) 밑으로 내려가지 않게 둘의 큰 쪽을 쓴다. 검토자의 21 회귀 산출 모으기(752fa2b 와
  견줌)를 다시 돌렸다 — 산출 256 개 중 SECID 가 752fa2b 와 다른 것은 둘이다: `test_section_cursor_stacked`(쌓인 카드 — 새 SECID 가 2 → 3,
  뜻한 것)와 `test_end_insert_once` 의 cnrb2solid PID 200(넷째 묶음의 `*END` 고침 — 35a35bb 에도 있다). 35a35bb 와는 SECID 가 다 같고
  바이트 차이는 `$ Date:` 줄뿐이다.

- **빈 `_TITLE` 제목 줄(#4)** — `cur_scanSectionDefs`(첫 카드 · 있나 · 종류 · 커서의 바닥)가 빈 줄을 제목보다 먼저 건너뛰어 SECID 카드를 제목으로
  버리고 두께 줄(`3.0`)을 SECID 3 으로 읽었다 — CAN 섹션의 제목을 비우면 BRACKET(SECID 3)의 옮기기가 `part_duplicate` 로 거짓 거절됐다.
  `_TITLE` 이면 키워드 뒤 첫 비주석 줄이 제목이다(비어 있어도 — LS-DYNA · StepForge 는 빈 줄도 카드). 두 번 정의 판정은 카드 묶음 셈
  (`cur_scanSectionSets` — 이미 빈 줄을 카드로 센다)으로 옮겨 쌓인 묶음끼리의 겹침도 센다(11-07 의 남는 틈을 닫았다). MID 의 두 번 정의는
  첫 카드 그대로(MID 훑기는 빈 제목 줄을 이미 바로 읽는다).

- **열 재질은 따로 센다(#3 · c50e54c 와 다른 훑기의 어긋남)** — c50e54c 가 공용 MID 커서에서 번호 이름 `*MAT_T01`~`T18` 도 뺐는데 다른 훑기는
  `*MAT_THERMAL_` 만 뺐다 — offset(재질 카드)이 `*MAT_T01 2` 옆에 낸 `*MAT_ELASTIC 2` 를 `info --strict` 가 「망가진 카드」로 막았다. 판정을
  `cards::isThermalMaterialKeyword`(CardFields.h — 번호 뒤는 끝 · `_` · 공백 · 폭 접미사) 하나로 모아 커서 · 겹침(ReferenceIntegrity) · `*PART`
  참조(`checkElementPartReferences`) · matdb 의 재질 블록(`md_scanMatBlocks`)과 옛 열 카드 지우기 · assemble merge 의 GENERIC · 조각 계약
  (CadSolidMerge) · hfdamp 가 쓴다. 참조 쪽은 `*MAT_ADD_` 만 빼서 **이름 꼴 열 재질도** `*PART` MID 를 정의한다고 보았다 — Vol I *PART 비고 7
  (MID 는 `*MAT` 의, TMID 는 `*MAT_THERMAL` 의 번호)대로 둘 다 뺐다. 재질 카드 없는 offset 이 쓰는 빈 MID(열 재질이 없어도 35a35bb 부터
  그렇다 — offset 몫이라 손대지 않음)를 같은 번호 TMID 가 가렸다. 회귀 `test_thermal_mat_ids.py` 9항(35a35bb 에서 9 실패).
  남긴 훑기 — 이름 꼴 열 재질도 MID 와 한 번호 공간으로 본다(35a35bb 그대로 · 우리 몫 밖). 지우거나 베끼는 것: matswap(단독
  `msw_removeBlock("*MAT_", mid)` · assemble `mw_removeBlock("*MAT_", mid)` — 바꾸는 MID 와 첫 칸이 같은 `*MAT_*` 블록을 다 지운다: 같은 번호
  TMID 의 열 카드 · 같은 번호 PID 의 `*MAT_ADD_*`), cclip(`cc_removeBlockById("*MAT", mid)` — 같다), offset IGA 의 `extractMaterialBlock`(첫 칸이
  origMid 인 첫 `*MAT` 블록을 베낀다 — 열 카드가 앞이면 그것), matdb(`thermal: false` 여도 같은 번호 열 카드를 지우고 `*PART` TMID 는 그대로
  둔다). 번호를 세기만 하는 것(커서가 높아질 뿐 · 겹침은 넉넉한 쪽): matswap · cclip 의 최대값, ale `ale_findMaxIds`, cnrb2solid 의 번호 공간 표
  (`Ns::Mat`), cnrb2spring 의 `MAT`. 단독 merge 는 모르는 재질을 알림에만 쓴다.

- **계획을 못 읽으면 동반 파일을 모른다(#1)** — `carryoverCompanionNames` 가 깨진 계획(끝 잘림 · 끝에 `x` · 앞의 BOM)에서 빈 목록을 내
  `report: field_2.bin` 이 rc 1 `plan_json` 으로 거절하며 field_2.bin 을 보고로 덮었다. 이제 「모른다」(false)를 돌려준다 — 열 수 없다 ·
  JSON 이 아니다 · 객체가 아니다 · `files` 객체(판 1 · 2 의 필수 칸 · 동반 파일의 표)가 없다. 그때는 계획 폴더의 파일(링크면 가리키는 것이
  파일인 것)을 다 읽는 파일로 본다 — 앞 실행의 이월 보고(첫 칸 `"format": "dynaforge-carryover-apply"` · 앞의 BOM · 공백 · CRLF 는 건너뛰고
  본다)만 빼서 같은 report 로 다시 돌릴 수 있게 했다. output 도 같은 목록을 본다 — 계획을 못 읽으면 덱은 어차피 쓰지 않지만 적용 쪽 읽기가
  나중에 BOM 을 받게 되어도 동반 파일을 덮지 않게(그때 거절 까닭은 `output_clobber` 이고 그 까닭에 「계획을 읽지 못해 동반 파일을 모른다」
  가 붙는다). 쓰기 · 바꿔 넣기(`CarryStagedFiles`)는 손대지 않았다(공용 도우미로 갈 몫). 회귀 v2 R-3e~i(35a35bb 에서 R-3e~h 실패).

- **조각 바닥은 절점 · 요소만(#6 · 문서)** — 이 문서(아래 「11-07 밤」 의 권고 ③ · 셋째 묶음 커서)와 그 커밋 글이 이월 적용의 조각 이동량
  바닥을 SECID · MID 커서의 소비자로 적었는데, 그 바닥(CarryoverApply ⑨)은 `idMaxima()` 의 절점 · 요소 최대값만 본다 — 줄을 고쳤다(커밋 글은
  그대로 남는다). 이월 적용이 SECID 셈을 쓰는 곳은 새 섹션의 차례 · 겹침, MID 셈은 「조각 MID 가 덱에 있나」 다. 도움말 · 카탈로그의 「조각
  번호는 덱 바닥 위」 도 절점 · 요소 번호라고 적었다(PID · SECID · MID 는 옮기지 않는다). 설명서 §3.1(h) 의 같은 말도 11-08 둘째에 고쳤다.

## 11-08 둘째 — 재질 번호(MID) 가족 고침(사용자 결정 「이번 판에 다 고친다」) — 정한 것
- **공용 재질 번호 훑기 하나(`parser/MaterialIds.h` · `matids`)** — 세기 · 있나 · 두 번 정의 · 정의 지우기 · 베끼기 · 고정 번호대 겹침이 같은
  셈을 쓴다(둘째 소비자 규칙 — op 마다 일곱 벌의 사본이 따로 셌다). 구조 재질 = `*MAT_*` 가운데 열 재질(`cards::isThermalMaterialKeyword` —
  TMID)과 `*MAT_ADD_*` 를 뺀 것. 섹션 카드 묶음 셈과 같은 꼴 — 빈 줄도 카드 · 끝의 빈 줄은 여백 · 1열의 `$` 는 건너뜀(11-08 셋째 — 들여쓴 `$`
  줄은 데이터) · 쉼표 줄은 모르는 꼴.
- **쌓인 재질 묶음((g))** — 묶음 한 벌의 줄 수를 Vol II R16 카드 요약이 정하는 꼴만 다 읽는다: `*MAT_ELASTIC`(001) 1 + Card 1.1(E < 0 ·
  StepForge 591d5b5 `card_set_rows` 와 같다) + Card 2(`_FLUID`) · `*MAT_PLASTIC_KINEMATIC`(003) 2 · `*MAT_VISCOELASTIC`(006) 1 · `*MAT_NULL`(009) 1
  · `*MAT_RIGID`(020) 3 · `*MAT_PIECEWISE_LINEAR_PLASTICITY`(024 · 옵션 없는 꼴) 4. 저장소 덱의 구조 재질 꼴 가운데 이 여섯이 대부분이다(ELASTIC
  531 · 024 283 · 006 215 · 003 205). E 칸이 수가 아니면(`&E`) 모름 — 지어내지 않는다. 그 밖의 꼴과 못 가른 자리부터는 행마다 첫 칸 숫자
  (`deckscan::digitsField` — 섹션과 공용)를 넉넉히 센다(커서 · 겹침만 — 「있나」 는 묶음의 Card 1). 커서(`cur_scanMaxMaterialId`)가 그
  최대 · 있나(`definedMaterialIds` · `materialsReachable`)가 정의 · 두 번 정의(`materialDefinitionLines` — 이월 적용 part_duplicate)가 묶음마다
  Card 1 줄을 쓴다(쌓인 묶음끼리도 센다 — StepForge `dup_mats` 와 같은 쪽). StepForge 는 `*MAT_ELASTIC` 만 쌓인 묶음을 읽고 다른 재질은 새
  번호를 매기지 않아 MID 위끝을 세지 않는다 — 우리 커서가 넉넉한 쪽이라 겹침은 없다.
- **MID 를 내는 op 마다 같은 셈((d))** — matswap(단독 · assemble) · cclip · ale · cnrb2solid · cnrb2spring · matdb match_part 가 각자 센
  `*MAT_` 첫 카드(또는 모든 행) 셈을 `matids` 로 바꿨다. assemble 의 matswap · matdb 는 공용 커서(`maxMaterialId_` · matswap 은
  `maxSectionId_` 도)와 견주고 낸 번호를 올린다 — 같은 실행의 앞 op(offset)이 덧붙인 재질 · 섹션은 아직 rawLines_ 에 없어 예전 훑기가
  못 보고 MID 2 · SECID 2 를 또 냈다(--strict 망가진 카드 2건 · 실측). 회귀 `test_material_id_family.py` G · D 17항(4dfe039 에서 17 실패).
- **옛 재질 지우기 — 구조 재질 정의만((a) matswap 단독 · assemble · (b) cclip)** — `matids::removeDefinition`: 길이를 아는 묶음은 그 묶음 줄만
  (블록의 묶음이 다 지워지면 키워드 줄째 — 빈 재질 키워드를 남기지 않는다), 길이를 모르는 첫 묶음은 블록째(예전 그대로 — 뒤에 쌓인 것이
  있는지 모른다), 길이를 모르는 쌓인 묶음은 그 자리부터 블록 끝까지. 같은 번호 TMID 의 열 재질 · PID 꼴 덧붙임 · 쌓인 다른 재질은 둔다.
  **MID 꼴 덧붙임(정한 것 · 조정자에게 물음)** — Vol II R16 카드 정의로 가른다: MID 꼴 12(EROSION · DAMAGE_GISSMO · DAMAGE_DIEM · FATIGUE ·
  GENERALIZED_DAMAGE · INELASTICITY · PERMEABILITY · PORE_AIR · PROPERTY_DEPENDENCE · PZELECTRIC · AIRBAG_POROSITY_LEAKAGE ·
  BASIC_INCREMENTAL_FAILURE) · PID 꼴 5(THERMAL_EXPANSION · COHESIVE · CHEM_SHRINKAGE · SOC_EXPANSION · EXTVAR_EXPANSION). 문자 그대로 「구조 정의만」
  지우면 재질이 덱에서 사라지는 경우(cclip — 새 MID · assemble matswap 여러 파트 — 번들은 새 번호) MID 꼴 덧붙임이 없는 재질을 가리킨다(예전엔
  같이 지워 그 결함이 없었다) — 그때만 `removeMidAddOns` 로 같이 지운다. 번호를 다시 쓰면(matswap 고아 MID) 둔다 — 새 재질에 붙는다(matdb 가
  같은 MID 에 덧붙임을 두는 것과 같다). 지운 뒤에도 그 번호가 쓰이면(`stillUsed` — 묶음을 못 가른 블록에 쌓였다 · 인클루드에도 있다) 번들에
  그 번호를 다시 주지 않는다(같은 MID 가 둘이 된다 — 예전엔 줬다). assemble matswap 은 재질 지우기를 번호 매기기 앞으로 옮겼다(다시 줄 수
  있는지 알아야 해서 — 산출 덱은 같다). 회귀 A · B 8항(4dfe039 에서 B-2 빼고 실패 — B-2 는 예전에도 덧붙임을 같이 지웠다).
- **IGA 재질 베끼기((c))** — `extractMaterialBlock` 을 `matids::copyDefinition` 으로: 그 MID 의 첫 구조 재질 정의(키워드 줄 · 그 묶음 줄 · 앞의
  주석)를 베끼고 Card 1 의 MID 칸만 바꾼다 — 고정폭 칸이 정수면 칸 폭 그대로 오른쪽 맞춤, 쉼표 줄이면 첫 값, 칸이 어긋난 줄이면 첫 토큰.
  예전 결함 셋을 같이 고쳤다 — 열 카드 · 덧붙임 카드가 앞이면 그것을 베꼈고, `_TITLE` 재질은 제목을 MID 로 읽어 못 찾아 0 물성 재질을 냈고,
  자리가 늘어난 MID(9 → 10)는 숫자 자리에 끼워 넣어 칸이 한 글자 밀렸다. 주 덱에 없으면 인클루드 파일에서 찾는다(새). 길이를 모르는 꼴은
  예전처럼 블록 끝까지 베낀다(그 뒤에 쌓인 재질이 있으면 같이 베껴진다 — 남은 틈). 회귀 C 4항(4dfe039 에서 4 실패).
- **matdb `thermal: false` 의 열 카드((e) · 가장 작은 바른 동작)** — 지우는 조건에 하나를 더했다: 그 재질의 thermal 이 꺼져 있고(새 열 카드를
  넣지 않는다) `*PART`(· `_TITLE`) TMID 가 그 열 카드를 가리키면(주 덱 · 인클루드) 남긴다 + 안내(`[matdb] kept thermal card TMID=n` — 바꾸기 전
  재질의 열 물성이다). 고른 까닭 — 지우고 TMID 를 0 으로 돌리기는 열 해석 덱을 깨고(LS-DYNA 는 열 · 연성 해석이면 셸 · 솔리드 파트마다 TMID
  를 요구한다 — Vol I *PART), 새 TMID 로 돌리기는 넣을 열 카드가 없다. 아무 파트도 가리키지 않는 열 카드는 예전처럼 지운다(해가 없다).
  `thermal: true` 는 그대로 — 그 번호의 열 카드를 DB 열 카드(TMID = MID)로 바꿔 넣고 그 MID 를 쓰는 파트의 TMID 를 잇는다(남은 틈 — 다른
  MID 의 파트가 같은 TMID 를 가리키면 그 파트도 새 열 물성을 받는다). 회귀 E 4항(4dfe039 에서 E-1 · E-1t 실패 · E-2 · E-3 은 지키는 항).
- **matdb 의 쌓인 재질(이번에 찾음 · (g) 의 같은 뿌리)** — matdb 는 맞춘 재질 블록을 `[startLine, endLine)` 째 지워, 블록의 첫 카드 MID 가 맞으면
  같은 키워드 아래 쌓인 둘째 재질까지 지웠다(그 재질을 쓰던 파트가 미정의 재질 · rc 0 · 실측). `matids::definitionMask`(removeDefinition 과
  같은 규칙 · 줄 차례를 바꾸지 않는 표시 — matdb 의 DEL 표지)로 맞춘 MID 의 묶음만 지운다. 묶음이 하나인 블록은 예전과 같은 줄을 지운다(산출
  같음). 매칭(`md_scanMatBlocks`)은 지금도 블록의 첫 카드만 본다 — 쌓인 둘째 재질은 `mid:` 규칙으로 고를 수 없다(남은 틈). 회귀 E-4(4dfe039 에서 실패).
- **offset 의 재질 카드는 필수((f) · 거절)** — 문서와 동작은 어긋나지 않았다: 카탈로그가 `material_card` 를 선택으로 두고 「If material_card is
  empty/missing, no material written (user adds manually or via matswap)」 라 적었고 그대로 동작했다(설명서는 말이 없고 도움말 예제가 재질
  카드 없이 돌았다 — `*PART` MID 2 에 재질 없음 · rc 0 · 35a35bb 부터). 조정자에게 셋을 물었다 — ① 거절 ② 원 파트 MID 를 같이 쓰기
  ③ 원 파트 구조 재질을 새 MID 로 베끼기. ①을 골랐다(답이 없어 알린 기본값) — ②③은 오늘 LS-DYNA 가 키워드 단계에서 멈추는 덱(시끄러운
  실패)을 「원 파트와 같은 재질」 로 조용히 바꾼다(지어내지 않는다). 대가 — 재질과 무관하게 offset 을 편의로 돌리던 설정이 rc 1 이 된다:
  도움말 예제(flatten_includes · output_guard_ops · help_truth 가 돌린다) · 회귀 다섯(catalog_binary_parity · element_topology ·
  id_width_overflow · section_cursor_stacked · standalone_yaml_parsing)에 재질 카드를 붙였다(시험 뜻은 그대로). 다층(material_cards)은 층마다
  같은 문을 지난다(빈 층 카드도 거절). 회귀 F 3항(4dfe039 에서 F-1 · F-2 실패).

## 11-08 셋째 — 여섯째 검토 고침(이월 · 번호 훑기 · matdb · hfdamp · 사용자 결정 「들인 결함 + 물성 바꾸는 기존 넷」) — 정한 것
- **번호 칸 읽기(S8)** — 카드 묶음 셈의 SECID 칸 · 넉넉한 셈(`deckscan::digitsField` — 섹션 · 재질 공용)이 숫자만 9 자리까지 받아(StepForge
  `isdigit` 꼴) 쌓인 묶음의 `+6` · `0000000006` · 10 자리를 놓쳤다 — offset 이 같은 SECID 를 다시 냈고 이월 적용이 「+9」 옆에 새 섹션 9 를
  썼다. 이제 정수 칸이 받는 꼴 그대로 — 부호 `+` · 앞의 0 · 칸 폭을 다 채운 수(int 안 · 0 보다 큼). 자리를 아는 번호 칸(묶음의 Card 1 —
  섹션 SECID `cur_setIdField` · 재질 MID `matids` 의 `midOf`)은 실수 꼴 정수(`6.0` · `6.000e+00`)도 그 정수로 읽는다 — 리더
  (`KFileReader::parseInt`)와 옛 첫 카드 셈이 그렇게 읽고, 정수 칸의 실수 꼴은 `carryover::integralField` 하나로 읽는다(D-681). 넉넉한 셈은
  실수 꼴을 세지 않는다 — 행 수를 모르는 꼴의 두께(`2.0` · `12.0`)와 가를 수 없어 세면 거짓 `secid_order` 가 돌아온다(11-08 #2 의 퇴행 꼴).
  그래서 행 수를 모르는 꼴(보 · 이산 …)에 쌓인 둘째 묶음의 실수 꼴 SECID 는 여전히 못 본다(남은 틈 · 그 블록의 첫 묶음은 옛 첫 카드 셈이
  읽는다). `withMid`(재질 베끼기)는 실수 꼴 MID 칸도 칸 폭 그대로 바꾼다(토큰 자리 바꾸기는 뒤 칸을 민다). 회귀 — 커서 D 6항 · 재질 G-7 · G-8
  3항 · 이월 S-3f~h 3항(4f550b3 에서 12 실패) · 단위 1.
- **모르는 꼴의 제목 줄(S10)** — 넉넉한 셈은 못 가른 묶음의 첫 줄(`rest`)부터 셌다. `rest` 는 늘 묶음의 첫 줄이고 `_TITLE` 이면 그 줄은 꼴을
  몰라도 제목이다(LS-DYNA · StepForge 리더) — `*SECTION_SEATBELT_TITLE` 의 제목 `2024`(쉼표 제목 `2024,beam` 도)가 가장 큰 SECID 가 되어 정상
  계획을 `secid_order` 로 거절하고 커서가 2025 로 뛰었다. 이제 제목 줄 다음부터 센다(섹션 · 재질 같은 규칙). 그 뒤에 쌓인 묶음의 제목은 자리를
  몰라 그대로 센다(넉넉한 쪽 — 남은 틈 · StepForge 도 보 · 이산의 제목을 센다: 검토 행렬의 `beam_title_2024` bound 2024). 회귀 — 커서 E 4항 ·
  재질 G-9 · 이월 S-3i(4f550b3 에서 6 실패).
- **주석은 1열의 `$` 뿐(S8 · S10 을 지으며 들인 퇴행을 고침)** — 섹션 묶음 셈과 `matids` 가 첫 비공백 글자가 `$` 인 줄을 주석으로 건넜다. 리더
  (`KFileReader::isCommentLine`)와 LS-DYNA(Vol_I 17862 「A dollar sign "$" in column one precedes a comment」)는 1열만 주석이다 — 들여쓴 `$`
  제목(「  $5 tube」)을 건너면 묶음이 한 줄 밀린다. 예전엔 밀린 둘째 카드의 `1.0` 을 SECID 로 못 읽어 넉넉한 셈으로 물러섰는데(우연히 맞았다 —
  검토 행렬 `shell_indented_dollar_title` 은 4f550b3 에서 2), S8 이 실수 꼴 정수를 받자 그 `1.0` 이 SECID 1 이 되어 진짜 SECID 2 를 놓쳤고(새
  섹션이 2 를 다시 냈다), S10 의 제목 건너기는 밀린 자리에서 진짜 Card 1 을 건넜다. 이제 둘 다 1열 규칙이다. 카드 한 장 꼴(`*SECTION_SOLID_TITLE`
  · `*MAT_ELASTIC_TITLE` 에 들여쓴 `$` 제목)은 4f550b3 에서도 Card 1 을 제목으로 삼켜 번호를 놓쳤다 — 같이 고쳐졌다. 들여쓴 `*` 제목 줄(블록이
  끝난 것으로 본다)은 다음 판 목록 그대로다(검토 행렬 `shell_indented_star_title` — 4f550b3 · 운영 판 모두 1). 옛 첫 카드 셈
  (`cur_scanSectionDefs` — 있나 · 종류 표)은 아직 첫 비공백 `$` 를 주석으로 본다(그 표만 들여쓴 `$` 제목에서 틀린다 — 남은 틈 · 커서는 두 셈의
  큰 쪽이라 맞다). 회귀 — 커서 F 2항(F-1 은 e27baed 에서 실패 · F-2 는 4f550b3 에서도) · 재질 G-11(e27baed 에서 새 MID 501 — 밀린 카드의
  `500.0` 을 MID 로) · G-10(지킴이 — 카드 한 장 `*MAT_ELASTIC_TITLE` 은 리더가 MID 를 읽어 커서가 맞았다) · 단위 1(`matids::defined` — 4f550b3
  에서는 그 MID 를 몰랐다).
- **열 카드를 가리키는 다른 파트(S5 — matdb `thermal: true`)** — b83b7bf 는 `thermal: false` 만 막았다(검토의 기본 재현은 그때 고쳐졌음을 확인).
  `thermal: true` 는 같은 번호(TMID = MID)의 열 카드를 늘 바꿔 넣어, 그 카드를 **다른 MID 의 파트**가 가리키면 그 파트의 열 물성이 조용히 DB 의
  것으로 바뀌었다(rc 0 · `--strict` 0). 정한 것 — 그때는 옛 카드를 두고 새 카드에 빈 TMID 를 준다(덱 · 인클루드의 열 카드 TMID · `*PART` TMID ·
  맞춘 MID 가운데 가장 큰 것 + 1, 맞춘 MID 차례로) · 그 MID 를 쓰는 주 덱 파트의 TMID 를 그 번호로 잇는다. 「다른 MID 의 파트」 는 이번에 TMID
  를 다시 매기지 않는 파트다 — 주 덱에서 thermal 이 켜진 다른 맞춘 MID 의 파트는 제 새 카드로 옮겨 가니 빼고, 인클루드의 파트는 고치지 않으니
  넣는다. 그 번호의 열 카드가 인클루드에 있어도 빈 TMID 다(예전엔 주 덱에 같은 TMID 를 하나 더 넣었다 — 인클루드는 고치지 않는다). 가리키는
  파트가 그 MID 의 것뿐이면 예전 그대로(TMID = MID — 산출 같음). 남은 틈 — 인클루드에 있는 그 MID 의 파트는 TMID 를 못 잇는다(예전부터 ·
  옛 카드를 둔 경우엔 옛 열 물성 그대로). matswap · cclip 은 열 카드를 지우지 않는다(11-08 (a) (b) — 구조 재질 정의만). 회귀 E-5 · E-5d
  (4f550b3 에서 E-5 실패 · E-5d 는 지키는 항).
- **깨진 계획을 다시 돌리면(S7)** — 계획을 못 읽으면(#1) 계획 폴더의 파일을 다 입력으로 보는데, 산출 자리도 그 목록과 견주어 앞 실행이 계획
  폴더에 남긴 `deck_applied.k` 가 걸렸다 — 보고는 `output_clobber`(「동반 파일을 모른다」)만 말하고 고칠 것(계획)은 말하지 않았다. 정한 것 —
  계획을 못 읽으면 보고 자리만 보고(콘솔 거절 그대로 — R-3e~g), 산출 자리는 **보지 않는다**(덱을 쓰지 않으니 덮을 일이 없다). 그 계획을 적용
  쪽과 같은 읽기(`parsePlan`)로 읽어 `plan_read` · `plan_json` · `plan_schema` 만 적고 거절한다(덱은 읽지 않는다 — 보고의 deck.sha256_in 은 null).
  위 #1 의 「output 도 같은 목록을 본다 — 적용 쪽 읽기가 나중에 BOM 을 받게 되어도」 는 이 갈래로 바뀌었다: 그 읽기가 BOM 을 받게 되면 계획은
  「읽은」 것이고 동반 파일 표가 생기니 산출 자리는 그 표와 견준다. 회귀 v2 R-3h(기대를 plan_json 으로) · R-3j(성공한 실행 뒤 깨진 계획 —
  4f550b3 에서 둘 다 output_clobber).
- **인클루드 덱의 되읽기 자리(S6)** — 쓴 덱의 대조(`verifyCarryoverOutput`)가 바꿔 넣기 전 임시 파일의 경로로 닫힘을 풀었다. 임시 파일은 공용
  `staged_write` 가 정한 자리 — output 이 링크면 따라간 파일 옆, 읽기 전용 폴더의 쓸 수 있는 output 이면 시스템 임시 폴더 — 라 `*INCLUDE` 이름이
  다른 폴더에서 풀려 「닫힘이 다르다」 로 맞는 산출을 거절했다. 이제 줄은 임시 파일에서 읽고 이름은 output 을 준 그대로의 폴더(§52.5 · 산출 규칙
  `include_output` 이 덱 폴더와 견주는 그 폴더)에서 푼다 — `verifyCarryoverOutput(tmp, rep, outPath)` · `KFileReader::readFileWithIncludes` 의
  `resolveAs`(줄은 그 파일 · 이름은 그 경로의 폴더). 쓰기 · 바꿔 넣기(공용 도우미)는 손대지 않았다. 회귀 v2 R-9a~c(4f550b3 에서 셋 다
  verify) · R-9d(다른 폴더 산출은 그대로 include_output — 지키는 항).
- **hfdamp 의 재질(P1 · 물성을 바꾸는 기존 결함)** — selective 가 `*MAT_` 블록마다 첫 데이터 줄을 Card 1(MID RO E PR)로 읽었다. 재질 뒤의
  `*MAT_ADD_EROSION`(첫 칸이 같은 MID)이 RO · E 를 EXCL · MXPRES 로 덮었고, 같은 뿌리로 `_TITLE` 재질은 제목 줄을 Card 1 로 읽었다(검토의
  `elastic_title` — 0 파트). 둘 다 그 파트의 dt 를 못 재 감쇠에서 빠진다. 줄마다 걷는 재질 읽기를 지우고 `matids::scan` 의 구조 재질 묶음마다
  Card 1 에서 RO · E · PR 를 읽는다(열 재질 · `*MAT_ADD_*` 는 그 훑기가 뺀다 · 쌓인 묶음도 읽는다). Card 1 에 RO · E · PR 가 없는 꼴(NULL · RIGID
  · SPRING · DAMPER · VACUUM · HE_BURN — 이름 꼴)은 예전처럼 건너뛴다(번호 이름 `*MAT_009` · `*MAT_020` 은 예전에도 읽었다 — 그대로). 칸은
  예전처럼 10칸 고정폭(long 덱은 예전부터 못 읽는다 — 남은 틈). 회귀 `test_material_id_family.py` H-1 · H-2(4f550b3 에서 실패) · H-0(지킴이).
- **extract-parts 되읽기의 재질 셈(다음 판 목록에서 — 조정자 「싸면」)** — `verifyOutput` 이 `*MAT` 블록의 모든 데이터 줄 첫 칸을 MID 로 세어
  열 재질 TMID · `*MAT_ADD_*` 의 첫 칸(MID · PID)이 미정의 재질을 가렸다. `*MAT` 블록 줄(빈 줄 · 주석까지)을 모아 `matids::inUse` 로 센다 —
  구조 재질만 · 줄 수를 모르는 꼴은 행마다 넉넉히(그 쌓인 둘째 재질을 미정의로 몰면 거짓 rc 1 — 예전 셈도 넉넉했다). 쓰기 쪽(`*MAT_T01` 블록을
  재질 2 로 싣는 고르기)은 손대지 않았다(더 싣는 쪽 · 무해). 스테이징 갈래의 extract-parts 고침(1565 줄 뒤 · 표준 헤더)과 겹치지 않는 자리다.
  회귀 `test_extract_parts.py` S-1 · S-2(4f550b3 에서 실패) · S-3(지킴이).

## 11-07 밤 결정 고침 — 정한 것
- **출력 규칙(사용자 결정 ①)** — extract-parts(`a33af2f`)와 같은 꼴: 덱 · 보고를 output 폴더의 임시 파일(`.<이름>.kr_tmp_…`)에 쓰고 되읽기 대조 ·
  품질 관문까지 지나면 덱 · 보고 차례로 바꿔 넣는다(11-08 부터 공용 도우미 `staged_write::StagedFiles` — `include/util/StagedWrite.h`, 사본 둘을 모았다).
  거절 · 실패면 이번 실행의 임시 파일만 지운다 — 앞 파일 · 폴더 · 남의 파일은 안 건드린다. 보고에 `output_written` 을 더했다(파일 목록은 원래
  싣지 않는다 — 덱 지문 `sha256_out` 은 바꿔 넣은 때만). `stale_output_removed` 는 없앴다. 읽는 파일 대조를 공용 관문 `output_guard::findClash`
  로 옮기며 **설정 YAML** 이 들었다 — 통합 판(`a62d7d2`)에서 실측: `report: a.yaml` 이 설정을 보고로 덮었고(rc 0) · 설정(c.k)과 같은 output 은
  쓰기 관문에 걸린 뒤 「옛 산출」로 지워졌고 · 빈 폴더 output 은 rmdir 됐다. 폴더 자리는 output 이면 `output_clobber`, report 면 콘솔 거절.
  쓰기 관문(`writeOutput` 의 `output_guard`)은 임시 이름을 보므로 output 자리의 겹침은 그 전에 runner 가 묻는다(아무것도 쓰기 전).
- **요소 `_TITLE` 블록(권고 ①)** — `gridTitleBlock`(리더가 담는 격자 블록 + 키워드 토큰에 TITLE). 그 블록의 데이터 줄마다 둘째 칸 정수를 PID 후보로
  넉넉히 모아(첫 줄이 제목이든 아니든 두 읽기를 다 덮는다 — 절점 줄 정수로 거짓 거절이 날 수 있다) 고치는 줄이면 `opaque_elements`(그 PID).
  덱 전체를 막는 「읽지 못하는 블록」 과 달리 PID 마다다(사용자 결정 「그 PID 를 고치면 거절」). 리더 자체의 오독(숫자꼴 제목 — 솔리드는 두 줄
  카드 머리, 셸은 요소 하나 · 11-07 밤 실측)은 고치지 않았다(공용 리더 · 이 갈래 밖) — 남는 틈: keep PID 가 그 블록에 있고 리더가 오독하면
  나눠 쓴 절점 · 번호 바닥이 그 오독을 본다.
- **정수 칸의 실수 꼴(권고 ②)** — `parseIntegral`(정수 글자 또는 실수 꼴의 정수 값 · |v| ≤ 2^53)을 `shellSectionRows` 의 ELFORM · NIP · ICOMP 와
  `scanSectionFile` 의 ELFORM 에. SECID(ID 칸)는 정수 글자만 — 실수 꼴 SECID 를 받으면 그 카드를 덱에 넣은 뒤 우리 번호 훑기(`iss >> int`)가
  `1.000e+01` 을 1 로 읽어 되읽기 대조가 갈린다. 다른 이월 칸 읽기(*PART · 요소)는 그대로다.
- **열 재질 번호 이름(권고 ③ · 공용 훑기)** — `cur_scanMaterialIds` 가 `*MAT_T01`~`*MAT_T18`(뒤가 끝 · `_`)도 뺀다(`cur_isThermalMaterial` —
  `*MAT_TABULATED_*` 같은 구조 재질은 센다). 부르는 곳 — ① `cur_scanMaxMaterialId` → `maxMaterialId_`(loadBaseModel · 인클루드 위로) →
  새 MID 를 내는 op: restack · disconnect(CZM) · IGA · offset · connection CZM · 다재료 offset · dual offset(prestress · CZM) · cnrb2solid ·
  merge, 그리고 `idMaxima().material` → `id_floor` 의 `pid_start` · `cad_solid_merge_to_deck` 의 PID·SECID·MID 바닥(~~이월 적용의 조각
  이동량 바닥~~ — 11-08 정정: 그 바닥은 `idMaxima()` 의 절점 · 요소만 본다 · CarryoverApply ⑨) ② `definedMaterialIds` → 이월 적용의
  「조각 MID 가 덱에 있나」 ③ `materialsReachable` → matswap · matdb 의 「MID 가
  인클루드에만 있나」. **번호가 바뀌는 덱** — `*MAT_T01`~`T18` 의 TMID 가 구조 MID(바닥이면 PID · SECID 도)의 최대값보다 큰 덱뿐이다 —
  그 op 들의 새 MID(· 바닥)가 TMID 위가 아니라 구조 번호 위로 내려온다(같은 수의 TMID 와 MID 는 Vol II 가 허락한다). 리포의 픽스처 ·
  회귀 덱에는 `*MAT_T01`~`T18` 이 없다(전수 grep) — 기존 회귀 산출은 그대로다.
- **두 번 정의된 SECID · MID(권고 ④)** — 공용 훑기 둘에 「번호마다 정의 전부」 꼴을 더하고(`cur_scanSectionDefs` · `cur_scanMaterialDefs` —
  옛 `cur_scanSectionIds` · `cur_scanMaterialIds` 는 그 첫 정의 · 번호 집합으로 같은 값을 낸다) `sectionDefinitionLines` · `materialDefinitionLines`
  로 이월 적용에 넘긴다. 손대는 줄의 `*PART` SECID · MID 정의가 둘 이상이면 `part_duplicate`(새 갈래를 만들지 않고 detail 에 「SECID n 의
  정의가 k 개(자리 …)」). 정의는 블록마다 첫 카드 — StepForge 리더도 쌓인 카드를 읽지 않으니 「같은 줄에서 멈춘다」 가 선다. 쌓인 둘째
  카드끼리의 겹침은 세지 않는다(남는 틈 — 새 SECID 의 겹침은 따로 넉넉히 센다).
  → 11-08: StepForge 591d5b5 리더는 SOLID · SHELL · TSHELL 의 쌓인 묶음을 다 읽고 `dup_sections` 로 센다 — SECID 정의는 카드 묶음 셈으로
  옮겼다(위 「11-08」 #4).
- **공용 SECID 커서(셋째 묶음 · 사용자 「이번 판」)** — `cur_scanMaxSectionId` 가 `cur_scanSectionIdsAnyCard`(섹션 블록의 모든 데이터 줄 첫 칸
  정수 · 블록 키워드 폭)로 센다 → `maxSectionId_`(loadBaseModel · 인클루드 위로) · `idMaxima().section`. 이월 적용의 `sectionIdsAnyCard` 를
  옮겨 둘이 하나의 규칙을 쓴다(둘째 소비자). 있나 · 종류(`cur_scanSectionIds` · `definedSectionIds`)는 첫 카드 그대로. **새 SECID 가 바뀔 수
  있는 op** — restack · disconnect(CZM 섹션 둘) · offset · 다재료 offset · dual offset prestress · merge · cnrb2solid(시작 번호) · IGA(커서를
  올리기만), 바닥 — `id_floor`(pid_start) · `cad_solid_merge_to_deck`(~~`apply_carryover_plan`(조각 이동량 바닥)~~ — 11-08 정정: 그 바닥은
  절점 · 요소 최대값만 본다. 이월 적용이 이 셈을 쓰는 곳은 새 섹션의 차례 · 겹침(`sectionIdTop` · `sectionIdsInUse`)이다). 바뀌는 덱은 섹션 블록에
  첫 카드보다 큰 정수가 첫 칸인 줄(쌓인 카드 · 정수 두께 · 숫자 제목)이 있는 덱뿐 — 커서는 오르기만 한다. **기존 회귀 산출** — 커서가
  옛 셈과 다를 때 적는 탐침 바이너리로 회귀 전체(111)를 돌렸다: 갈린 곳은 셋 — ① `examples/wrap/cylinder_2layer.k`(진짜 쌓인 카드 —
  `*SECTION_SOLID` 밑 SECID 1 · 2 · 1 → 2)를 쓰는 wrap 실행 스물여덟(wrap 은 절점만 옮기고 SECID 를 내지 않는다 — 산출 그대로) ② 이월 적용 R-1
  의 쌓인 카드 덱(8 → 9 · 10 — 거절 시험이라 산출 없음) ③ 새 회귀 `test_section_cursor_stacked.py`. 그러니 기존 회귀 산출은 바뀌지 않는다.
  → 11-08 적대적 검토가 이 「모든 행」 셈의 퇴행을 찾아 카드 묶음 셈으로 바꿨다(위 「11-08」 #2).
- **보 `_ELBOW` · `_WARPAGE`(셋째 묶음 4 — 다른 보처럼)** — 공용 걸음(`forEachNonGridElementCard`)이 MN(Card 10 · 92f50fe) · SN1 · SN2(Card 9 ·
  6341aac — 이 갈래에 그 커밋만 합쳤다)를 카드의 절점에 싣는다. 이월 적용이 그 절점을 쓰는 곳은 나눠 쓴 절점 하나(고치는 PID 의 절점과
  겹치면 `shared_nodes`)라 `elementBlockGap` 의 두 거절을 뺐다. SN 은 스칼라 절점 번호(`*NODE_SCALAR` — `*NODE` 와 겹치면 안 된다)라
  고치는 PID 의 절점과 겹치는 덱은 설명서 밖이다 — 겹치면 나눠 쓴 절점으로 거절된다(안전한 쪽). 조각의 절점 바닥은 6341aac 의
  `scalarNodeMaxId` 로 스칼라 절점 번호 위다.

## 리뷰 11-07 고침 — 정한 것
리뷰(11-07) 결함 11 + 그럴듯한 둘을 고쳤다. 공용 코드(i10 조각의 쓰기 관문 왕복 · 솔리드 · 티쉘 변형의 바닥 · `*ELEMENT_MASS` PID 칸)는 다른 갈래 몫.
- **요소 블록 판정(결함 1)** — 덱을 고치는 줄(옮기기 · 모프 · 바꿔 넣기 · 지우기 · 조각 있는 새 파트)이 하나라도 있으면, 절점 칸을 다 읽지 못하는
  `*ELEMENT_*` 블록이 있을 때 **전부** 거절(`opaque_elements` — 키워드마다 첫 줄 · 블록 수 · 까닭). 다 읽는 것은 둘뿐 —
  ① 리더가 메시에 그대로 담는 격자 블록(`KFileReader::parseFile` 의 갈래를 옮긴 `readerReadsGrid`: `*ELEMENT_SOLID` · `_SOLID_TITLE` · `*ELEMENT_TSHELL` ·
  `_TSHELL_TITLE` 은 이름이 같을 때만, `*ELEMENT_SHELL` 은 `parseElementKeyword` 가 받는 변형 — 단 `_DOF` 는 Card 5 의 NS1-NS4 를 아무도 읽지 않아 뺀다)
  ② 칸 자리를 아는 격자 밖 블록(`auxElementCard`) — 보는 옵션 카드에 절점이 있는 `_WARPAGE`(SN1 · SN2) · `_ELBOW`(MN)를 뺀다. Card 1 의 N3(방향 절점)은 읽는다.
  → 11-07 밤 공용 걸음이 MN(92f50fe) · SN(6341aac)을 읽게 되어 그 둘을 뺀 것을 거두었다(아래 「11-07 밤 결정 고침」).
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
  `stale_output_removed` 로 적는다. → 11-07 밤 사용자 결정으로 없앴다(앞 파일은 그대로 · 아래).
- (11-08) **판 2 받기 배포** — Drive `dist-20261108-234149Z`(revision `e6407dc`, 바이너리 `c5f74c18`). 배포 바이너리로 라이브 실물 둘을 다시 재 적용 덱
  sha256 raw `5066e271…` · mesh `842b0924…`(StepForge 에 알림). cae00 은 다음 update-all 로 받는다.
