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
- [ ] v2 실물 받기 · 대조(그쪽이 커밋을 알려 준다)
- [ ] 읽기 — 계획(엄격) · 변위장(이진) · 조각(덱 SECID · MID 참조 꼴)
- [ ] 사전 검사 — 꼴 · 덱 지문(+ includes) · 파일 지문 · 변위장 덮음 · 조각 범위 대 바닥 · 참조 · 나눈 절점(전부 아니면 전무)
- [ ] 처리 — transform(강체 확인) · morph(+ new_section) · remesh(같은 PID 로 바꿔 넣기 · new_section) · delete · add · keep/review(`touches_changed` 보고)
- [ ] 되읽어 대조 · 품질 관문(뒤집힘이 하나라도 생기면 쓰지 않음) · 보고(PID 마다 · 적용 덱 sha256)
- [ ] 시험 — StepForge 진리값 판(`fixtures/carryover`)의 계획 · 변위장 · 조각으로
