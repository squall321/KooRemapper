# 미뤄 둔 결함 둘 — unfold 가 요소를 말없이 잃는다 · extract-parts 가 `LONG=Y` 덱을 못 읽는다 (2026-11-20)

체크리스트 `deferred-defects-1120.checklist.md` · 맥락 `deferred-defects-1120.context-notes.md`.

## 0. 범위(사용자 지시를 읽은 것)
- 11-20 「진행해줘」 — 남은 일 정리 끝에 권한 차례(설계안 확인 → cae00 update-all → 미뤄 둔 물성 결함 둘) 가운데 셋째 몫이다.
- 고치는 것은 `seatbelt-aux-walkers-1107.plan.md` 「다음 판으로 미룬 것」 ★ 줄의 다섯 가운데 둘이다 — **F-1** unfold 가 요소를 rc 0 으로
  버린다 · **F-2** extract-parts 가 `LONG=Y` 덱을 못 읽는다. 나머지 셋(tetremesh 의 같은 EID · 8절점 셸 · `_THICKNESS` 와 i10 · id_floor 의
  elem_start int 범위)은 이번에 손대지 않는다.
- 올리는 데까지 — 갈래 `corelink-int` 에 커밋 · 푸시. main 합치기 · 주 체크아웃 바이너리 설치 · cli.sif 굽기 · Drive 게시는 사용자 확인 뒤다
  (C++ 바이너리가 바뀌는 판이라 SmartTwinPreprocessor SIF 까지 닿는다).

## 1. F-1 unfold — 잰 것(설치된 바이너리 248ec9bc · dev 라이브러리)
- 잃는 수 = 구조 격자 색인기(`StructuredGridIndexer`)가 **같은 (i,j,k) 칸에 둘 이상을 놓은 수**다. 탐침으로 칸을 세면
  `examples/foldable_display/test_small_bent.k` 100 요소 → 서로 다른 칸 53(가려진 요소 47 · 색인기 차원 5×5×4 — 평판 짝 덱의 격자는 10×5×2) ·
  `examples/wave/wave_bent.k` 250 → 238(가려진 12 · 색인기 차원은 평판 짝 덱과 같은 10×5×5 인데 칸이 겹친다). unfold 는 그 칸 수만큼만 쓰고 rc 0
  이다.
- 까닭 — 전파(`propagateIndicesGeometry`)가 이웃마다 「중심 방향과 가장 가까운 축」 을 고르는데 **고른 칸이 비었는지 보지 않는다**. 뒤의 채움률
  검사는 50 % 아래만 막고, 칸 찾기 표(`buildIndexLookup`)는 같은 칸의 앞 요소를 덮어쓴다. 평판 생성 3단계는 칸마다 요소 하나만 짓고, 모서리
  절점이 없으면 말없이 건너뛴다(`rebuiltElementCount` 는 세기만 하고 버린다).
- `map` 은 같은 색인기를 쓰지만 이 두 덱을 rc 1 로 거절한다(「only 1/8 corner nodes found」 · 「only 7/8 …」) — 다만 색인 검사가 아니라 뒤의
  모서리 절점 검사에 걸린 것이다. 모서리에서 먼 충돌이 `map` 을 조용히 지나는 덱은 **찾지 못했다(안 잰 것)**.
- 리포 덱 훑기(examples · tests · platform/backend/tests · docs 의 40 MB 아래 `.k` 339 개) — 구조 격자가 아니거나 모서리 요소가 없어 건너뛴 것
  246 · 구조 격자 93. 그 93 가운데 지금 색인 = 위상 색인(시제품, 아래 B) **83**(요소 전부 같은 칸) · 다른 것 **3**(위 둘과
  `examples/teardrop/teardrop_mapped.k` — 2,000 요소에 서로 다른 칸 1,214) · 지금 색인이 채움률로 실패하고 위상 색인은 되는 것 **5**
  (`examples/arc30/arc30_{mapped,remapped,test_green,test_prestress}.k` · `examples/foldable_display/foldable_remapped.k`) · 둘 다 실패 **2**
  (`examples/offset/07_contact_result.k` · `tests/offset/regression/05_contact_mode.k` — 한 덩어리가 아니다).

## 2. F-1 선택지
- **A 관문(이번에 짓는다 — DF-14 때 고른 「감지 · 경고 · 쓰기 거절」 과 같은 갈래)**
  - A-1 색인기 — 전파 뒤 서로 다른 칸 수 ≠ 요소 수면 실패(오류 글에 수를 싣는다). unfold 와 `map` 이 같은 까닭을 말한다.
  - A-2 unfold — 지은 요소 수 ≠ 읽은 요소 수면 rc 1, 산출을 쓰지 않는다(색인이 멀쩡해도 3단계가 건너뛴 요소를 잡는 뒷문).
  - 바뀌는 것 — 위 세 덱은 unfold 가 rc 1 로 거절한다(예전 rc 0 · 요소 빠진 덱). `map` 은 같은 rc 1 에 까닭만 달라진다. 나머지 83 덱은 그대로다.
- **B 뿌리 고침(제안 — 사용자 결정)** — 전파를 「중심 방향 어림」 에서 **면 위상**(이웃의 맞닿은 면 · 그 면과 두 절점을 나눠 가진 면으로 축 틀을
  옮긴다)으로 바꾼다. 시제품(scratch)으로 잰 것 — 충돌 0 · 83 덱은 지금과 같은 칸 · 3 + 5 = 8 덱이 새로 된다. `map` 의 뿌리를 바꾸는 일이라
  (산출 바이트 동일성 · 회귀 전부 · 실물 덱) 따로 계획 · 확인을 받고 짓는다. A 는 B 를 막지 않는다(B 가 들어와도 관문은 남는다).

## 3. F-2 extract-parts `LONG=Y` — 잰 것 · 고칠 자리
- 같은 모델(육면체 둘 · 셸 하나 · 파트 셋)을 두 폭으로 쓴 덱 — 표준 폭은 rc 0(파트 2/3 · 요소 카드 2 · 절점 12 · 되읽기 미정의 0),
  `*KEYWORD LONG=Y` 는 **rc 1 「No *PART definitions found (or only *PART_* variants we cannot chunk)」**. 조용한 변질이 아니라 큰 소리의
  거절이고, 글이 까닭(long 폭)을 말하지 않는다.
- 까닭 — 절점 · 요소 · 세트는 키워드마다 폭을 따르는데(`keywordFieldWidth`), 일반 카드 첫 칸을 **폭 10 으로 못 박아** 읽는 자리가 여섯이다.
  `indexDeck` 의 `*PART` 카드 2 · `*SECTION_SOLID`(ELFORM) · 패스 2 `flushBlock` 의 `*PART` · `*PART_*` 변형 · ID 블록(`*SECTION` · `*MAT` ·
  `*EOS` · `*HOURGLASS`) · 되읽기의 `*SECTION`.
- 고침 — 그 여섯 자리를 그 블록의 키워드 폭(`fw >= 20 ? 20 : 10` — 이미 세트가 쓰는 꼴)으로 읽는다. 쓰기는 줄을 그대로 옮기므로 바뀌지 않는다.
- 범위 — 덱 전체 `LONG=Y` 와 키워드 접미사 `+`. **인클루드마다 폭이 다른 덱은 이번 범위가 아니다**(인클루드 안 `*KEYWORD` 줄은 펼칠 때 빠지고
  덱 폭은 값 하나다 — 지금 동작은 재서 맥락 문서에 적는다). 솔버로는 못 잰다(라이선스 만료) — 연산의 되읽기와 표준 폭 대조로 잰다.

## 4. 검증
1. `tools/regress/test_unfold_element_loss.py` — 불변식 「unfold 는 rc ≠ 0 이거나 쓴 요소 수 = 읽은 요소 수」 를 충돌 덱 둘 · 대조 덱에서.
   고치기 전 바이너리에서 빨갛고 고친 뒤 초록. 거절 때 산출 파일이 없고 글에 수가 있다. `map` 은 같은 두 덱에서 rc 1 과 색인 글.
2. `tools/regress/test_extract_parts_long.py` — 같은 모델의 표준 · long 추출이 같은 수(고른 요소 · 절점 · 파트 · 필요한 단면 · 재질 ·
   되읽기 0)를 내고, long 산출이 `*KEYWORD LONG=Y` 와 160 칸 `*PART` 카드를 그대로 둔다. 고치기 전 빨강.
3. 단위 시험(`KooRemapper_tests`) · 회귀 전부(`tools/regress/*.py`)를 고친 바이너리로 — 고치기 전 판과 실패 목록을 견준다(환경 탓 실패를
   가른다).
4. 위 훑기 다시 — 83 덱의 색인이 그대로인지(관문이 멀쩡한 덱을 막지 않는지) 고친 라이브러리로 탐침.
