# 체크리스트 — 인클루드 닫힘 · `IdAllocator` 첫 채택

계획 `include-closure-ids.plan.md` · 맥락 `include-closure-ids.context-notes.md`

## U1 인클루드 닫힘 리더
- [x] `readClosure` → `include_closure::read(mainPath, mainLines)` — 맨 `*INCLUDE` 의 이름 카드
      여러 장 · `␣+` 이음(세 줄). **주 덱 줄은 호출자 것을 받는다**(큰 덱에서 메모리 두 배 금지)
- [x] 중첩(깊이 우선) · 순환은 한 번만 읽고 `cycles` 로 · 인클루드 파일 안의 `*END` 는 그 파일만
- [x] 찾는 순서 — 주 덱 폴더 먼저, 경로 없는 이름만 `*INCLUDE_PATH`(+`_RELATIVE`)
- [x] 맨 `*INCLUDE` 가 아닌 것은 `notFollowed` 로 · `*INCLUDE_PATH*` 는 파일로 세지 않는다
- [x] 단위 시험 10개(`tests/test_IncludeClosure.cpp`) — 전체 78 → **88** 초록
      ★**무는 것을 증명했다** — 다른 구현들이 실제로 달랐던 세 자리를 그 구현처럼 바꿔 넣었다.
      M1 포함하는 파일의 폴더로 풀기(`cleanup_nodes`) → 「주 덱 폴더」 시험이 죽는다 ·
      M2 `_TRANSFORM` 을 맨 `*INCLUDE` 처럼 읽기(`modelmeta`) → TRANSFORM 시험이 죽는다 ·
      M3 카드마다 첫 이름만(`IncludeScan`) → 네 시험이 죽는다. 되돌리면 88/88.
- [x] 실사용 88장 — **이름 408 · 읽은 파일 407 · 못 푼 이름 1 · 따라가지 않은 카드 0 · 순환 0.**
      두 기준(주 덱 폴더 / 포함하는 파일 폴더)이 갈리는 덱은 실사용에 **없었다.** 못 푼 1 은
      `battery_study/debug_archive/case01_run70_normal_term/` — 보관하면서 `02_mesh` 를 **뺀** 폴더라
      LS-DYNA 도 못 돈다. 리더가 옳게 말한 것이다.

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
