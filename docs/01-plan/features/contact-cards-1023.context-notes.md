# 결정 노트 — contact 카드 결함 · map 전처리 (10-23 밤)

- **(10-23) TIEBREAK OPTION 은 「생략 시 1」 이 아니라 「요구」 로 고친다.** 매뉴얼 Card 4 의 OPTION · NFLS · SFLS 기본값은 「required」 다
  (V68117-68150). 생략하면 우리가 고르는 값이 없다 — 1(파손 없음)을 몰래 넣던 것이 결함이었다. 파손 OPTION 에 NFLS · SFLS 를 안 주면
  파손 응력 0 이라 곧바로 떨어진다 — 그것도 요구한다.
- **(10-23) 못 쓰는 Card 4 형은 거절한다.** TIEBREAK_USER · COMPOSITE · TIED_WELD · CONSTRAINT · DRAWBEAD · RIGID · INTERFERENCE ·
  TIEBREAK_NODES/SURFACE(AUTOMATIC 과 꼴이 다르다) · THERMAL_FRICTION(THRM 2) · ORTHO_FRICTION(ORFR) · TIEBREAK OPTION 13/14 · DAMPING.
  지금까지는 대문자로 그대로 써서 「경고만 하고 rc 0」 으로 **불완전한 키워드**를 냈다 — 조용히 틀린 산출이다.
- **(10-23) 빈 줄은 카드다.** 매뉴얼 「Optional Cards A and B may be blank lines」. 파서가 건너뛰면 그 뒤 카드가 한 칸씩 당겨진다.
- **(10-23) 반올림 고침은 골든을 지키는 쪽으로.** 예전 형식으로 쓴 글자를 다시 읽어 같은 값이면 그 글자를 쓴다 — 0.2 · 1.0 처럼 흔한
  값은 바이트가 그대로다. 값이 바뀌는 경우(0.125 → 0.13 · 0.0005 → 0.00)에만 10칸 안의 가장 정밀한 표기로 바꾼다.
- **(10-23) ct_getExistingTiedSegments 는 일치하는 TIED 접촉 전부의 면을 모은다.** 예전엔 첫 일치에서 멈췄고, 거꾸로 맞으면(슬레이브가
  pidB 쪽) **두 갈래 모두** 바꿔치기했다 — 파트 기반 갈래는 이미 pidA · pidB 순서로 모으므로 그 바꿔치기가 오히려 면을 뒤집었다(잠재 결함).
  새 판은 세그먼트 갈래만 거꾸로일 때 바꾼다.
- **(10-23) 시험 셋이 결함 거동을 기대값으로 적고 있었다.** catalog_binary_parity(tied_mortar → 없는 키워드 · option 없는 tiebreak rc 0) ·
  remaining_surfaces H6(assemble 이 THERMAL · TIEBREAK · ERODING 을 Card 1-3 만으로 「같은 키워드」 라 통과) · yaml_common_rules
  (option 없는 tiebreak). 새 거동으로 바꿨고, 바꾼 단언은 옛 바이너리에서 FAIL 이다(결함을 잡는다).
- **(10-23) assemble 은 필수 카드 형을 만들지 않고 거절한다.** assemble 의 contact 는 Card 1-3 만 쓰는 꼴이라 THRM · Card 4 를 붙이려면
  단독 contact 의 조립을 옮겨야 한다. 지금은 단독 contact 가 바르게 만드니 assemble 은 [ERROR] rc 1 로 그쪽을 가리킨다 — 조용히
  불완전한 덱을 내던 것보다 낫고, 옮기는 일은 따로 정할 수 있다.
- **(10-23) D22 — 접촉 카드를 따로 세던 셋을 정본으로 모은다.** info 참조 검사 · restack/merge 죽은 참조 스캐너 · cnrb2spring 이 각자
  `_TITLE` · `_ID` 만 세어 `_MPP` 의 MPP 1 을 Card 1 로 읽었다. 재현 — info 는 MPP 1 의 IGNORE 2 를 「세트 2 가 없다」(`--strict` rc 1),
  진짜 Card 1 의 없는 세트는 못 봄 · restack 은 `_MPP` 접촉의 죽은 PID 를 못 보고 rc 0, MPP 1 의 BCKT 가 죽은 PID 와 같으면
  MPP 1 줄(NS2TRK 3→2)을 고쳐 씀 · cnrb2spring 은 [manual] 이 [maybe] 로 낮아져 rc 0. 셋 다 `ct_parseContacts` 의 카드 자리를 쓴다
  (세 번째 소비자 — 사본을 늘리지 않는다). IdRefs 는 이미 `_MPP` · `&` 를 바르게 세고 있어 그대로 둔다.
