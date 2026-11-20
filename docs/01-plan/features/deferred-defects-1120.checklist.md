# 미뤄 둔 결함 둘(F-1 unfold · F-2 extract-parts `LONG=Y`) 체크리스트

계획 `deferred-defects-1120.plan.md` · 맥락 `deferred-defects-1120.context-notes.md`.

## A. 재기 · 준비
- [x] A-1 F-1 재현 · 까닭 실측(칸 충돌 탐침 · `map` rc · 339 덱 훑기)
- [x] A-2 F-2 재현(표준 rc 0 · long rc 1) · 폭 10 으로 못 박은 자리 여섯
- [x] A-3 계획 · 체크리스트 · 맥락 문서

## B. F-1 unfold
- [x] B-1 회귀 시험 `test_unfold_element_loss.py` — 고치기 전 빨강 확인
- [x] B-2 A-1 색인기 칸 유일성 관문 · A-2 unfold 요소 수 관문
- [x] B-3 dev 빌드(-j8 · prlimit) · 새 시험 초록 · 변이 확인(A-1 끄면 A-2 가 막는다) · 339 덱 다시 훑어 83 덱 그대로

## C. F-2 extract-parts `LONG=Y`
- [x] C-1 회귀 시험 `test_extract_parts_long.py` — 고치기 전 빨강 확인(21 항 가운데 12)
- [x] C-2 일곱 자리(계획의 여섯 + 되읽기 재질 훑기의 덱 폭)를 키워드 폭으로 · 새 시험 초록 · 변이 여덟 다 빨강
- [x] C-3 인클루드마다 폭이 다른 덱의 지금 동작을 재서 맥락 문서에(고치지 않는다) — 일곱 꼴 · 조용히 틀린 꼴 둘(전부터)
- [ ] C-4 사용자 결정 — long 주 덱 + 표준 폭 인클루드(`*INCLUDE -` · 제 `*KEYWORD`)를 거절할지(지금은 rc 0 · 폭이 섞인 산출)

## D. 전체 재기 · 올리기
- [x] D-1 단위 시험 · 회귀 전부(고치기 전 판과 실패 목록 대조)
- [x] D-2 전제를 말하는 글 쓸기(도움말 · 매뉴얼 · MCP 설명 — unfold 「요소를 잃지 않는다」 · extract-parts long)
- [x] D-3 갈래에 커밋 · 푸시(`corelink-int` — 결함마다 커밋 하나)
- [ ] D-4 사용자 확인 — F-1 선택지 B(위상 전파) · C-4 · main 합치기 · 바이너리 설치 · SIF · Drive
