# 결정 노트 — 한계 여섯 (10-17)

- **(10-17) 결정 넷은 사용자 답(권장안)이다** — 범위 여섯 모두 · 2차는 코너 값 + `geometry_basis: corners` ·
  인클루드는 `flatten_includes: true` 일 때만 펼침 · 재결속 공차는 `tolerance` 를 줄 때만.
- **(10-17) 2차 솔리드 — 코너 차례를 아는 것은 TET10 뿐이다.** 매뉴얼 `*ELEMENT_SOLID` Remark 2 는 4·6·8·10·20절점을
  Fig 19-31 로, 27절점을 Fig 19-32 로 보이고, H27·H64·P21·P40·T15·T20 은 「그림을 보라」뿐이다(본문 표 없음).
  `*SECTION_SOLID` Remark 16 — 「ELFORM 24·25·26 · 27·28·29 는 개발 중」. 그래서 25·26·27·28 은 절점을 다 읽되 기하는
  지금처럼 거절·null 로 둔다(짐작한 코너로 그럴듯한 값을 내는 것이 가장 나쁘다).
- **(10-17) 노드를 8+2 로 쪼갠 TET10 덱은 매뉴얼 덱이 아니다.** Card 2 가 N1..N10 열 칸 한 장이다. LS-DYNA 도 둘째 줄을
  다음 요소의 Card 1 로 읽는다. 짐작해 붙이지 않고 「모자란 2차 카드」로 거절한다(지금과 같은 결과 · 까닭만 바르게).
- **(10-17) 전체 절점은 `Element` 가 아니라 `Mesh` 옆 표에 둔다.** `Element` 에 벡터를 넣으면 1차 덱도 요소마다 24바이트가
  는다(실사용 덱 수백만 요소). 2차 요소만 EID → 절점 표에 담는다.
- **(10-17) B3 실측 — 쪼갠 덱으로 사례를 다시 돌렸다**(`scratchpad/b3/incl_probe.py`).
  rc 0→1: cclip · disconnect · offset · restack · iga · merge · warpage · bend · indent · matswap · assemble · cnrb2spring · ale · applyfold.
  rc 0→0 인데 산출이 다르다: convert · refine · elform · wrap · update · tetremesh · cnrb2solid · strip · matdb(「No materials matched」) ·
  load · boundary · rbe(「No surface faces」) · explicit · cad_solid_merge_to_deck · cleanup-nodes(인클루드 정의는 안 지운다 — 설계).
  같다: contact · relax · stabilize · database · hfdamp · implicit · modal · optimize · 분석 op 전부 · id_floor · extract-parts.
- **(10-17) 정본이 하나 더 갈려 있다 — extract-parts 의 인클루드 펼치기**(`joinPath(baseDir, rel)` — 포함하는 파일의 폴더 기준).
  정본은 주 덱 폴더 기준이다. 이번 범위 밖이라 고치지 않고 알린다.
