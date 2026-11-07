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

## 체크리스트
- [x] 새 연산 이름 사용자 확인 — `apply_carryover_plan`
- [ ] v2 실물 받기 · 대조(그쪽이 커밋을 알려 준다) — 칸은 `src/parser/CarryoverPlan.cpp` 머리의 `kKeys` **한 표**에 더한다
- [x] 읽기 — 계획(엄격) · 변위장(이진) · 조각(덱 SECID · MID 참조 꼴) — `include/parser/CarryoverPlan.h`
- [x] 사전 검사 — 꼴 · 덱 지문 · 파일 지문 · 변위장 덮음 · 조각 범위 대 바닥 · 참조 · 나눈 절점(전부 아니면 전무) — v1 이라 includes 는 거절
- [x] 처리 — transform(강체 확인) · morph · remesh(같은 PID 로 바꿔 넣기 · new_section) · delete · add · keep/review(`touches_changed` 보고) —
      morph 의 new_section(두께)은 v2(지금은 `field.thickness` 가 있으면 거절)
- [x] 되읽어 대조 · 품질 관문(새로 뒤집힌 솔리드 · 뒤집힌 셸 법선이면 산출을 지운다) · 보고(PID 마다 · 적용 덱 sha256) — `src/assembly/CarryoverApply.cpp`
- [x] 시험 — 진리값 판(`examples/apply_carryover_plan`) · 12 파트 덱(`tools/regress/data/apply_carryover_plan/mesh12`) ·
      거절 16 · CRLF · 바닥 · 품질(`tools/regress/test_apply_carryover_plan.py` 44 항) · 리더 단위 시험(`tests/test_CarryoverPlan.cpp` 7)
- [x] 바닥 — `idMaxima()` 의 요소가 보 · 이산 · 질량 · 안전띠 · 플롯 요소까지(`id_floor` · `cad_solid_merge_to_deck` 같이, `test_id_floor` E)
- [x] help · 카탈로그 · 개행 행렬 제외 · ofstream 선언

## 지으며 정한 것 (11-07 — 다음 세션이 다시 따지지 않게)
- **보고는 거절해도 쓴다** — 저쪽이 걸린 것 전부를 읽고 계획을 고친다. YAML 이 틀려 보고 자리를 모를 때(모르는 키 · output 없음)만 콘솔뿐.
- **조각 바이트가 다를 때의 값 대조** = 조각 엄격 읽기 + 머리 대조(번호 구간 · 수 · PID · SECID · MID · 요소 꼴 · 새 섹션 카드 · 요소가 쓰는 절점이
  다 있고 안 쓰는 절점 없음). 좌표는 대조하지 않는다 — 그래서 받되 **경고**(`fragment_bytes`)다. `.bin` 은 지문이 다르면 거절.
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
  앞뒤로 반대(또는 0)면 뒤집힘(옮기기 · 모프만 — 새 셸은 앞이 없다). 바꿔 넣기 · 새 파트는 새 요소가 하나라도 뒤집히면 거절.
- **바닥** — 새 counter `maxAuxElementId_` 를 `idMaxima()` 에만 넣었다. 다른 op 의 새 요소 번호(`maxElementId_`)는 그대로다(LS-DYNA 번호는 요소
  종류마다 따로다 — 바꾸면 30곳 op 의 번호가 움직인다).
- **남은 것** — `auxElementCard` 의 `*ELEMENT_MASS` PID 칸이 3(8칸 자르기)인데 매뉴얼 꼴은 EID I8 · NID I8 · MASS E16 · PID I8 이라 8칸으로는 칸 4 다
  (`IdRefs` 도 같은 자리). 이월 적용은 그 PID 를 「PID 에 질량 요소가 있다」 판정에만 쓴다 — 정본을 고치는 일은 따로.
