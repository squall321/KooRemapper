# modelmeta — 2차 솔리드 파트의 틀린 기하 값을 `null + reason` 으로

**날짜** 2026-10-16 · **원장** `docs/requests/deck-contract-checklist.md` 「사용자 판단 — 2차 솔리드 파트의 `mass` …」

## 왜
2차 솔리드(ELFORM 16·17·25~28) 파트는 리더가 `*ELEMENT_SOLID` 절점 칸의 **앞 8개만** 저장해 기하가 틀린다.
지금 `modelmeta` 는 값을 숫자로 내고 `second_order: true` 로 표시만 한다. 그런데

- 플래그를 **안 읽는** 소비자가 둘 있다 — `tools/kr2datahub.py`(DataHub 적재)와 hwax-risk 어댑터
  (`backend/app/adapters/dyna.py`). 둘 다 그 부피를 그대로 싣는다.
- 이 파일 자신의 질량 규약이 「유도할 수 없으면 **0 이 아니라 null + reason**」이다. 틀린 줄 아는 숫자는 그 규약에 어긋난다.
- 틀리는 칸이 원장에 적힌 넷보다 많다(아래 실측).

## 실측 (이 박스, 현재 바이너리 `55e6d46`)
매뉴얼 꼴(카드 2 에 N1~N10 한 줄) TET10 둘 — 참값 부피 0.5 · 절점 14 · 고아 0 · 요소 2.

| 칸 | 낸 값 | 판정 |
|---|---|---|
| volume | 0.257812 | 틀림(−48.4%) |
| area_ext · proj · edge_len | 그럴듯한 숫자 | 틀림(같은 뿌리) |
| mass | volume×rho | 틀림 |
| n_node | 12 | 틀림(n9·n10 을 못 본다) |
| model.orphan_nodes | 2 | **거짓 고아** — 상한일 뿐이다 |
| n_elems | 2 | 맞음 |
| bbox | [0,0,0]~[1,1,1] | 맞음(코너는 앞 8칸에 다 있다 — 직선 변) |

8+2 로 쪼갠 덱은 요소가 1 로 읽히지만 그 꼴은 매뉴얼 꼴이 아니다(R16 `*ELEMENT_SOLID` 카드 2 = N1~N10).

## 무엇을
- 2차 솔리드 파트 — `volume`·`area_ext`·`proj`·`edge_len`·`n_node` 를 `null`, 새 칸 `geometry_reason` 에 까닭.
  `mass`·`mass_basis` 는 `null`, `mass_reason` 에 까닭. `n_elems`·`bbox`·`second_order` 는 그대로.
- `model.orphan_nodes` — 2차 솔리드 파트가 있고 센 값이 0 보다 크면 `null` + `orphan_nodes_reason`(센 값은 상한).
  센 값이 0 이면 0 이 참이다(잘라 읽기는 참조를 **줄일** 뿐이라 고아를 숨기지 못한다).
- 규약 문구·콘솔 경고·소비자(프런트 타입 · kr2datahub 사유 전달 · 플랫폼 주석)·매뉴얼·원장.

## 하지 않는 것
- 리더가 10절점을 저장하게 하기(진짜 2차 지원) — `Element` 의 절점 칸 고정 8 을 바꾸는 큰 일이다.
- 1차 덱의 값 — 한 바이트도 안 바뀌어야 한다(시험으로 본다).
