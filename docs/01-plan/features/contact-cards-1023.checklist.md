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
- [x] D23 · D24 — test_contact_cards T(6 — 옛 전부 FAIL) · deckops_smoke 에 contact create

## 쓸기
- [x] 카탈로그(Known issue · cannot be written · -1 sentinel 문장) · 도움말 · 매뉴얼 · 예제 15·16 · ContactKeywords
- [x] assemble 의 contact type 설명 · notes 10 · MCP SKILL.md · 매뉴얼 「assemble 쪽 약칭 비대칭」 문단(09-18 부터 틀렸던 것)

## map 전처리(하위 에이전트 · worktree)
- [x] 측정 · 고침 · 바이트 동일 · 회귀 → 검토 → 들임(c1067b8..9f80bf1 — 큰 arc 매핑 6.1~6.7 → 1.3~1.4 초 · sha 39a6a2af 동일, 본 세션 재측정)

## 관문 · 배포
- [x] 단위 140 · 회귀 101/101(dev · compat 둘 다) · 도움말 사례 · 카탈로그 대조 · 백엔드 628 · 덱 지문(contact 만 의도대로 다름 — D23, 보고 JSON 둘은 같은 바이너리로도 매번 다르다)
- [x] compat 0e7db58c(GLIBC 2.35) · cli.sif · Drive 20261024-000227Z · API/MCP 재기동(살아 있는 잡 0 에 걸고) · health 2e8b9e4 일치
- [x] 스모크 73 tools · 리포트 35/35 · 그림 20/20 · 덱 op 25/25(contact 줄을 더했다) · 살아 있는 잡(option 없으면 실패 + 이유 · option 2 성공)
- [x] SIF v122 굽기(0e7db58c · 소스 2e8b9e4 · 검증 통과 · 업로드 · 메일) · compute-node-images · /opt 사본 같은 바이트
- [ ] 계산 노드 node001 · node002 — VM 이 꺼져 있다(10-19 부터). 켜는 것 · 깔기(`deploy_apptainers.sh --image`)는 사용자 결정
- [x] 커밋 · 메모리 · 보고
