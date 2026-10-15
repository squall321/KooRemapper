# 체크리스트 — 인클루드 닫힘 · `IdAllocator` 첫 채택

계획 `include-closure-ids.plan.md` · 맥락 `include-closure-ids.context-notes.md`

## U1 인클루드 닫힘 리더
- [ ] `readClosure(mainPath)` — 맨 `*INCLUDE` 의 이름 카드 여러 장 · `␣+` 이음(세 줄)
- [ ] 중첩 · 순환 감지 · 인클루드 파일 안의 `*END` 는 그 파일만 끝낸다
- [ ] 찾는 순서 — 주 덱 폴더 먼저, 경로 없는 이름만 `*INCLUDE_PATH`(+`_RELATIVE`)
- [ ] 맨 `*INCLUDE` 가 아닌 것은 `notFollowed[]` 로(`*INCLUDE_PATH*` 는 탐색 경로라 제외)
- [ ] 단위 시험 — 위 갈래 전부 + 없는 파일
- [ ] 실사용 88장에서 못 푼 이름 수를 잰다(기대 1 — 그 1 이 무엇인지 본다)

## U2 `UsedIds`
- [ ] SET 한 통 · CONTACT CID — 닫힘 전체 최대값
- [ ] contact 기존 스캐너와 **추적 덱 전수 차분 0**(같은 덱에서 같은 최대값)

## U3 `IdAllocator`
- [ ] 빈 대역표 → `max+1` · `issue(ns)` 가 커서를 올린다 · `verify`
- [ ] 단위 시험

## U4 contact 첫 채택
- [ ] 커서 둘을 `issue` 로 — 동작 불변
- [ ] contact 골든 10장 **바이트 동일**
- [ ] 새 픽스처 — 인클루드에 SET 5 가 있으면 6 을 낸다(고치기 전엔 5 — 재현 먼저)

## U5 주 덱 `--strict`
- [ ] `checkSetReferences` 를 닫힘 위에서
- [ ] 실사용 재측정 — 83장의 판정 · 조각 142장은 그대로
- [ ] 회귀 전수 · ctest · help

## 닫기
- [ ] 장부(`deck-contract-checklist.md`) P1-3·P1-5 갱신 · 매뉴얼/도움말에 바뀐 판정을 적는다
