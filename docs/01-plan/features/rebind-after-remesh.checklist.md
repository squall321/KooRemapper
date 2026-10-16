# 체크리스트 — 재결속 v1

- [x] `NodeRefs` — 맨 `*CONSTRAINED_NODAL_RIGID_BODY`·`*DEFINE_COORDINATE_NODES` 는 모든 줄(줄마다 정의 하나) · 그 카드가 든 덱 70장 재스윕 새 경보 0
- [x] `src/commands/rebind.cpp` — 읽기 · 짝 찾기(파트+좌표) · 허용 카드 · 충돌 · 구간 표 대조 · 제자리 바꿔 쓰기 · 쓰기 전 재검사
- [x] main 디스패치 · 도움말(62 op) · 플랫폼 카탈로그 · 예제 폴더
- [x] 회귀 `test_rebind_after_remesh.py` 20항 — 성공 6 · 못 풂 5 · 거절 9 · 변이 둘이 잡힘(옛 바이너리는 op 이 없어 FAIL)
- [x] 매뉴얼 §50 · 원장 · StepForge 답신에 한 줄
- [x] 관문 — 단위 104 · 회귀 94/94 · help · 플랫폼 562 → 커밋 · 푸시
