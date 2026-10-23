# 체크리스트 — contact 카드 결함 · map 전처리 (10-23 밤)

## 정본 카드 자리(파서)
- [x] ct_parseContacts 가 카드 줄 자리를 든다(ID · MPP · Card 1-3 · Card 4 · THRM · ORFR · 선택 A-G) · 빈 줄도 카드(D8) · `_MPP`(D9)
- [x] 형마다 Card 4 · THRM · ORFR 수 — 모르면 layoutKnown=false
- [x] Card C 7·8열 읽기(D1) · 쉼표 자유 형식(D19 — 확인했다)

## 쓰기
- [x] 순서 Card 1-3 → Card 4 → THRM → 선택(D2) · Card C 7·8열(D1)
- [x] 값 형식(D15) · Card A 안 준 칸 0(D10) · FTOSA 0(D3)
- [x] ERODING Card 4(D6) · tied_mortar(D5) · 못 쓰는 Card 4 형 거절

## contact 액션
- [x] std::optional 칸 · 엄격한 숫자 읽기(D11 · D16)
- [x] create — tiebreak option/nfls/sfls 요구 · 13/14 · DAMPING · THERMAL_FRICTION 거절(D4)
- [x] modify — 선택 카드만 바꾼다(D7) · Card 1 확장 칸(D17)
- [x] detect — THRM · Card 4(D12) · skip/subtract 가 SET_SEGMENT 를 안다(D13) · notes 13(D14)

## 다른 op
- [x] optimize 가 정본 카드 자리를 쓴다
- [x] stabilize SOFT 2 에 MAXPAR 안 씀(D18) · TIEBREAK 엔 SOFT 2 안 씀 · 번호로 돈다
- [x] assemble — 필수 카드 형은 [ERROR] rc 1
- [x] 접촉 카드를 따로 세던 곳 — info 참조 검사(ReferenceIntegrity) · restack/merge 죽은 참조 스캐너(rsFirstCard) ·
  cnrb2spring 지운 세트 검사가 `_MPP` 의 MPP 1 을 Card 1 로 읽었다(D22 — 재현 뒤 정본 `ct_parseContacts` 로). IdRefs 는 이미 맞다 ·
  modelmeta 는 정본을 써서 함께 고쳐졌다(실측) · cclip · merge 는 접촉 카드를 따로 읽지 않는다

## 시험
- [x] 회귀 test_contact_cards.py(결함마다 · 옛 FAIL / 새 PASS) · contact 골든 · 단위
- [x] 옛 결함 거동을 적던 시험 셋을 새 거동으로(catalog_binary_parity · remaining_surfaces H6 · yaml_common_rules)
- [x] D22 — test_reference_integrity E · test_cnrb2spring · test_pidref_detect B2(옛 FAIL / 새 PASS)

## 쓸기
- [x] 카탈로그(Known issue · cannot be written · -1 sentinel 문장) · 도움말 · 매뉴얼 · 예제 15·16 · ContactKeywords
- [x] assemble 의 contact type 설명 · notes 10 · MCP SKILL.md · 매뉴얼 「assemble 쪽 약칭 비대칭」 문단(09-18 부터 틀렸던 것)

## map 전처리(하위 에이전트 · worktree)
- [ ] 측정 · 고침 · 바이트 동일 · 회귀 → 검토 → 들임

## 관문 · 배포
- [ ] 단위 · 회귀 전부 · 도움말 · 대조 · 백엔드 · 덱 바이트
- [ ] compat · Drive · API/MCP · SIF · /opt · 스모크 · 커밋 · 메모리 · 보고
