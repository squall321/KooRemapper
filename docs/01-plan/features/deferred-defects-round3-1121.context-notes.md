# 미룬 결함 3차 — 맥락 · 결정 기록

계획 `deferred-defects-round3-1121.plan.md` · 체크리스트 `deferred-defects-round3-1121.checklist.md`.

## 1. 시작(2026-11-21)
- 사용자 결정은 계획 0절에 문장째 옮겼다. 갈래 `corelink-int` 는 `ee210f0`(main 과 같다). SP main · 키트 판은 작업 시작 때 확인했다(바뀐 것 없음
  — 고정 `3196156` · 키트 `2026-11-06`).
- 설치된 판은 `f20d5d5b`(Drive `dist-20261121-120311Z`). 재기는 이 바이너리로, 고침은 작업 트리의 `build/dev` 로 한다.
- pykoocae-53 과 주고받은 것 — 그쪽이 matswap 번들 BOM 을 v141 에 넣으려고 기다린다. 답으로 아직 안 고쳤다는 것 · 그때까지의 길(번들을 BOM 없이
  저장) · 고치면 보낼 것(커밋 · 바이너리 sha256 · 판정 꾸러미)을 보냈고, 무거운 빌드 전에 알리겠다고 했다. `build/linux/bin` 은 알리기 전까지
  `f20d5d5b` 그대로 둔다.

## 2. 판을 나눈 까닭
- 뿌리가 같은 것끼리 묶었다 — 덱 머리(BOM · 빈 메시) · 칸 폭과 번호 한계 · 쌓인 카드와 재료 · 파일과 메모리 · battery. rc 0 으로 틀린 덱을 내는
  줄이 든 묶음을 앞에 뒀고, matswap 번들은 다른 팀이 기다려 맨 앞이다.
- 스무 줄을 한꺼번에 다시 재지 않는다 — 판을 열 때 그 판의 줄을 잰다. 목록의 여러 줄은 11-07 · 11-08 검토가 적은 것이라 지금 판에서 같은지
  모른다(검토가 적은 것은 소스에서 확인한 뒤에 고친다).

## 3. 1판을 재면서 정한 것
- **BOM 규칙은 새로 정하지 않았다** — 2차 H-2 · H-4 에서 사용자가 고른 것(extract-parts · cleanup-nodes 는 뗀다 · 산출에 싣지 않는다)을 남은 op
  에 그대로 편다. LS-DYNA 가 BOM 덱을 받는지는 못 쟀지만, BOM 없는 산출은 어느 쪽이든 받는 꼴이다.
- **cad_solid_merge_to_deck 조각의 BOM 은 표의 「줄 하나」 보다 나쁘다** — 다시 재 보니 조각의 `\ufeff*KEYWORD` 줄이 덱의 `*MAT_ELASTIC` 블록
  뒤(주석 두 줄 다음 · 산출 42째 줄)에 데이터 줄로 실린다. op 은 rc 0 에 되읽기 검증 통과를 말한다. 2차 H-6 표는 줄 수만 셌다.
- **조각은 rc 를 뒤집지 않는다** — cad_solid_merge_to_deck 은 떼고(rc 0 그대로 · 덱이 바로 선다), apply_carryover_plan 은 거절 그대로에 까닭
  글만 고친다. 둘을 같은 쪽으로 맞추면 한쪽은 다른 팀이 보는 rc 가 바뀐다. apply_carryover_plan 의 조각 검사는 제어 문자도 「고치지 않고
  거절한다」 고 적어 둔 자리다.
- **`strain` · `squeeze` 는 거절** — 같은 주 덱을 unfold · map · extract-surface · neutralaxis · prestress 가 이미 rc 1 로 멈춘다. 인클루드를
  읽게 하는 것은 기능을 넓히는 일이라 이번 범위가 아니다.

## 4. 2판에 넘긴 실측(L-04a — 1판을 재다 같이 쟀다)
- 줄 맞춘 표준 덱 · `LONG=Y` · `I10=Y` 세 꼴을 만들어 돌렸다(`examples/cnrb2solid/bolt_simple.k` 는 절점 줄이 칸에 맞지 않아 공백으로 끊어 다시
  썼다 — 처음에 칸으로 잘라 만든 `LONG=Y` 덱은 깨진 덱이라 그 결과는 버렸다).
- `I10=Y` — 둘 다 rc 0 이고 산출의 절점을 선언 폭(번호 10 · 좌표 16)으로 읽으면 표준 판과 좌표가 같다(cnrb2solid 75 절점 · cnrb2spring 20 절점).
  결함이 아니다.
- `LONG=Y` — cnrb2solid 는 rc 0 에 「WARNING: NSID=0 not found or empty, skipping PID=0」 을 찍고 솔리드를 하나도 만들지 않는다(표준 판은 24 개
  · CNRB 카드를 10 칸으로 읽어 NSID 가 0). cnrb2spring 은 rc 1 「덱에 *CONSTRAINED_NODAL_RIGID_BODY 가 없습니다」(있다). 목록이 적은 「좌표 칸」
  보다 앞의 문제다 — 두 op 은 `LONG=Y` 카드를 읽지 못한다. 읽게 할지 거절할지는 2판에서 선택지로 묻는다.
