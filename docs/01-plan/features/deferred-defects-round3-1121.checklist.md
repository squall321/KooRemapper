# 미룬 결함 3차 체크리스트 — 열린 줄 스물 · 판마다 main · Drive

계획 `deferred-defects-round3-1121.plan.md` · 맥락 `deferred-defects-round3-1121.context-notes.md`.

## A. 준비
- [x] A-1 사용자 선택(「열린 줄 스물 전부」 · 틈 덱 「거절 그대로」) · 줄 스물에 번호 · 판 다섯으로 나눔
- [x] A-2 계획 · 체크리스트 · 맥락 문서

## B. 1판 — 덱 머리 BOM · `*INCLUDE` 뿐인 주 덱(L-02 · L-03)
- [x] B-1 다시 재기 — matswap 번들 · cad_solid_merge_to_deck 조각 · `strain` · `squeeze` (설치된 판 `f20d5d5b`)
- [ ] B-2 회귀 시험 `test_deck_bom.py` — 고치기 전 빨강 확인
- [ ] B-3 덱 · 번들 읽기에 BOM 떼기(원본을 따라 쓰는 쓰기 · assemble 족 · op 마다의 덱 읽기 · matswap)
- [ ] B-4 조각 — cad_solid_merge_to_deck 은 뗀다 · apply_carryover_plan 은 까닭 글
- [ ] B-5 `strain` · `squeeze` 명령줄 꼴 — 빈 메시 거절 · 시험
- [ ] B-6 훑기 다시(58 op × 꼴 넷) · JSON 입력의 BOM 재기 · 변이
- [ ] B-7 매뉴얼 3.1(e) · 23 장 · 도움말 · 미룬 목록
- [ ] B-8 전체 재기(단위 · 회귀 · 백엔드 pytest · 계약)
- [ ] B-9 올리기 — main · pykoocae-53 에 빌드 알림 · 호환 빌드 · 잡 확인 뒤 설치 · 재기동 · 스모크 · SIF 확인 · Drive · 알림(커밋 · 바이너리
  sha256 · 판정 꾸러미)

## C. 2판 — 칸 폭 · 번호 한계(L-04 · L-05 · L-08)
- [ ] C-1 다시 재기(L-04a 는 쟀다 — 맥락 노트) · 선택지
- [ ] C-2 시험 먼저 · 고침 · 변이 · 전체 재기 · 올리기

## D. 3판 — 쌓인 카드 · 재료 · 번호 커서(L-09 · L-10 · L-11 · L-12 · L-15 · L-16)
- [ ] D-1 다시 재기 · 선택지
- [ ] D-2 시험 먼저 · 고침 · 변이 · 전체 재기 · 올리기

## E. 4판 — 파일 · 메모리(L-01 · L-06 · L-13 · L-18 · L-19 · L-20)
- [ ] E-1 다시 재기 · 선택지
- [ ] E-2 시험 먼저 · 고침 · 변이 · 전체 재기 · 올리기

## F. 5판 — battery(L-07 · L-14 · L-17)
- [ ] F-1 다시 재기 · 선택지
- [ ] F-2 시험 먼저 · 고침 · 변이 · 전체 재기 · 올리기(SBOPT 는 「고쳤다 · 솔버 확인 없음」)

## G. 닫기
- [ ] G-1 미룬 목록(`seatbelt-aux-walkers-1107.plan.md`) 줄마다 닫은 커밋 · 남긴 까닭
- [ ] G-2 DF ② 계획을 연다(`df-request-1117.checklist.md` E-2)
