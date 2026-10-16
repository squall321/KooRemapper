# 없는 절점을 가리키는 카드 — `info --strict` 가 잡고, meshfix 가 만들지 않는다

**날짜** 2026-10-16 · **원장** plan2 P2-6(meshfix 참조 재결속) · StepForge 표 11행(재결속)의 공통 바닥

## 왜 (실측 — 이 박스)
`generate arc` 의 `demo_flat_tet.k` 에 PID 1 절점 379~382 를 가리키는 `*SET_NODE_LIST`·`*BOUNDARY_SPC_NODE`·
`*DATABASE_HISTORY_NODE` 를 붙이고 `meshfix pid: 1` 을 돌렸다.
- meshfix — rc 0 · 경고 없음. 산출 덱에 379~382 가 **없는데** 세 카드가 그 번호를 그대로 가리킨다.
- `info --strict` — 「참조 무결성 OK」 · rc 0. `--strict` 는 요소→절점만 보고 세트·경계조건→절점은 안 본다.
- LS-DYNA 는 세트가 없는 절점을 가리키면 키워드 단계에서 멈춘다(현장 실측 Error 10233 — `ModelAssembler.cpp`
  `cleanupDeadNodeRefs` 머리말). 나머지 카드는 같은 규율로 본다(라이선스 만료로 솔버 확인은 못 했다).

## 무엇을
1. **정본 하나** `parser/NodeRefs` — 절점을 가리키는 카드 칸(줄 · 칸 · 폭 · 값). 칸 자리는 `cleanupDeadNodeRefs`
   머리말의 매뉴얼 확정표를 그대로 옮긴다. 오탐을 막으려고 그 장치가 **확실히 아는 갈래만** 본다 —
   세트(LIST·LIST_SMOOTH·COLUMN·GENERAL 의 NODE/DNODE) · `*SET_SEGMENT` · SPC · 하중 · 초기속도 · 추가절점 ·
   집중질량 · 강제운동 · 이력 · CNRB 의 PNODE · 좌표계 절점. 조인트·스폿용접·보 족은 카드 꼴이 변종마다 달라
   **세어만 둔다**(예: `*CONSTRAINED_JOINT_STIFFNESS` 의 첫 칸은 절점이 아니다).
2. **`info`** — 그 칸의 값이 정의된 절점(주 덱 + 인클루드 닫힘의 `*NODE*` — 넘치게 모은다)에 없으면 미정의 참조.
   인클루드를 다 못 읽었으면 단정하지 않는다(기존 규율).
3. **meshfix** — 쓴 덱을 같은 함수로 다시 보고, 없는 절점을 가리키는 카드가 있으면 rc 1 · 목록 · 「`boundary_nodes:
   fixed` 면 표면 절점 번호를 지킨다」 안내. 틀린 덱을 남기지 않는다.

## 하지 않는 것(이번)
- 위치 기준 바꿔 쓰기(재결속) — 정본 함수가 칸 자리를 돌려주므로 다음에 그 위에 얹는다(meshfix `snap` · StepForge 재결속).
- `cleanupDeadNodeRefs` 를 정본으로 옮기기 — 고치기 동작(빼기·옮기기·보고)이 갈래마다 달라 따로 한다. 그동안은
  두 곳이 같은 칸 자리를 말해야 한다(시험으로 묶는다).

## 성공 기준
- 갈래마다 없는 절점 하나 → `--strict` rc 1 · 그 줄을 짚는다. 옛 바이너리 FAIL.
- 같은 덱에서 절점이 다 있으면 0건(거짓 경보 없음).
- **실사용 덱 전수에서 새로 뜬 절점 미정의를 하나하나 확인 — 오탐 0.**
- meshfix — 위 덱은 rc 1 · 덱을 남기지 않음, `fixed` + 표면 절점만 가리키면 rc 0.
