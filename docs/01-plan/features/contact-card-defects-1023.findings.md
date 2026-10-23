# contact 카드 쓰기 결함 — 카탈로그 대조에서 나온 것 (2026-10-23)

> **상태(10-23 밤) — 전부 고쳤다.** 사용자 「결함은 다 고쳐야지 그건 최우선이야」. 아래 11개와 detect · stabilize 항목은
> `e7a2bed`, 그 뒤 코드를 읽다 더 나온 것(D12-D21)도 같은 커밋, 접촉 카드를 따로 세던 셋(D22 — info 참조 검사 · restack/merge
> 죽은 참조 · cnrb2spring)은 `b20d1ad`. 번호와 고침은 `contact-cards-1023.plan.md`, 결정은 `contact-cards-1023.context-notes.md`.
> 아래 본문은 기록 당시 그대로 둔다. 솔버로는 여전히 못 쟀다(라이선스 만료).

**출처** 결정 3B(「contact 키 112개를 Vol_I 와 전부 대조」)를 하다가 나왔다. 설명 54개는 카탈로그에서 고쳤다(같은 날 커밋).
아래는 **설명만으로는 못 고치는 코드 결함**이다. 3B 범위 밖이라 손대지 않았고, 고칠지는 사용자가 정한다.
근거 — 매뉴얼 `docs/LSDyna/Vol_I.txt`(R16) 줄 번호(V) · 코드 `src/commands/contact_helpers.cpp`(CH) · `contact.cpp`(C) · `contact_defs.h`(CD).
「확인」은 이 세션에서 매뉴얼(일부는 PDF 원본 1210쪽)과 코드를 직접 본 것, 「프로브」는 대조 하위 에이전트가 바이너리(`252bd444`)로 돌려 본 것이다
(입력 · 출력은 세션 스크래치 `probe/` — 지워질 수 있다).

| # | 결함 | 영향 | 근거 |
|---|---|---|---|
| 1 | **Card C 의 FLANGL · CID_RCF 를 한 칸 앞에 쓴다** — 6 · 7열(매뉴얼은 6열 공란 · 7 FLANGL · 8 CID_RCF) | 준 FLANGL 은 사라지고 CID_RCF 가 FLANGL 로 읽힌다. 올바른 덱을 modify 로 왕복하면 둘이 옮겨진다 | 확인 — PDF 1210쪽 표 · `ct_formatCardC` CH:1212-1217(읽기는 공백 토큰이라 맞게 읽고 쓸 때 밀린다) |
| 2 | **TIEBREAK Card 4 · THERMAL 카드를 선택 카드 A–G 뒤에 쓴다** | 매뉴얼은 「정확히 이 순서」 — Card 1-3 → Card 4 → THRM → 선택 카드. 함께 쓰면 순서가 틀린 덱 | 확인 — V66596-66684 순서 목록 · CH:1306-1322 / 프로브 — tiebreak + `soft:1` 에서 Card A 줄이 Card 4 자리에 |
| 3 | **열 접촉의 6번째 칸(FTOSA)을 생략해도 1.0 으로 쓴다** | 마찰열을 전부 SURFA 쪽으로(매뉴얼 기본 0 = 0.5) | 확인 — CD `thChlm=1.0` · V70574-70582 · V70655-70662(CHLM 은 `*CONTACT_2D` 에만, V77964) |
| 4 | **TIEBREAK OPTION 기본이 1 = 영구 고착(파손 없음)** — 예제와 주석은 「quadratic 파손」 이라 적는다 | 파손을 기대한 덱이 파손 없이 붙어 있다 | 확인 — CD `tbOption=1` · V68286-68298 / 예제 `examples/contact/16_create_tiebreak.yaml:12` · C:786 주석 |
| 5 | **`tied_mortar` 가 없는 키워드를 쓴다** — `TIED_SURFACE_TO_SURFACE_MORTAR` | 매뉴얼에 0회 · 실제는 `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED`(V67003) | 확인 — Vol_I 검색 · CH:991-992 · `include/util/ContactKeywords.h:30` |
| 6 | **ERODING_* 에 필수 Card 4 를 안 쓴다** | 불완전한 키워드 | 확인 — V66596-66684 목록(Card 4 필요 형 중 ERODING_type) |
| 7 | **선택 카드 키를 modify 하면 Card 4 · THRM 1 이 지워진다** — 파서가 넷째 카드를 Card A 로 읽고, 다시 쓸 때 Card 3 뒤를 지운다 | TIEBREAK 줄 `1 10 50 …` 이 Card A `2 10.00 50 …` 로 | 프로브 · CH:142-153 · 1388-1396 |
| 8 | **빈 줄 자리표시 선택 카드를 건너뛴다**(매뉴얼은 허용 — V66661-66664) | 빈 Card B 뒤의 Card C 가 Card B 로 다시 쓰인다 | 프로브 · CH:88-90 |
| 9 | **`_MPP` 덱을 잘못 읽는다** — MPP 1 카드를 Card 1 로 | PID 1→2 접촉이 「SET_SEGMENT 1 / PID 200」 으로 분석된다 | 프로브 · CH:39-67 · V66604-66612 |
| 10 | **Card A 를 쓰면 MAXPAR 1.025 · DEPTH 2 를 늘 적는다** | 형마다 다른 기본(예 AUTOMATIC_GENERAL 의 DEPTH 3)을 덮는다 | 확인 — CD `maxpar=1.025 · depth=2` · V71541-71554 |
| 11 | **`>= 0` 문이 뜻 있는 음수를 모두 버린다** — FS −1/−2 · SFSA<0 · BT/DT<0 · −9999 · SABOXID<0 · DEPTH/BSORT<0 · IGAP<0 · DPRFAC/DTSTIF<0 등 | 그 기능(곡선 · 동적 이완 중 처리 · 접촉 부피)을 쓸 수 없다 — 조용히 빠진다 | 설명 문장에 「cannot be written」 으로 적었다 · 각 V 줄은 하위 에이전트 보고 |

**detect 쪽(설명에 적었다)** — `contact_type` 이 tied_thermal · thermal · tiebreak 여도 THERMAL · TIEBREAK 카드를 쓰지 않는다(C:1318-1438 · 1527-1649) ·
`skip_existing` · `subtract_existing` 는 part ID · SET_PART 쪽만 알아보아 detect 가 만든 SET_SEGMENT 접촉과 다시 맞지 않는다(CH:1032-1040 · 1073-1095 — 프로브).

**stabilize** — Lv8+ 가 SOFT 2 와 함께 MAXPAR 1.15 를 쓰는데 MAXPAR 는 SOFT 2 에 안 쓰인다(V71468-71478 · V71751) — 효과 없는 칸(해롭지는 않다).

**확인 못 한 것** — notes 13 「subtract_existing 는 auto_create 일 때만」 이 코드와 다르다는 보고(C:1273). 둘러싼 조건을 확정하지 못해 설명을 바꾸지 않았다.
솔버로는 하나도 안 쟀다(라이선스 만료). 2 · 7 의 솔버 쪽 결과는 매뉴얼 카드 순서에서 미루어 본 것이다.
