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
- **(10-17) S3 에서 결함이 하나 더 나왔다 — 맨 `*SET_NODE`.** 옮기기 장치(`migrateDeadNodeSets`)가 이름이 `*SET_NODE_LIST` 로
  시작할 때만 봐서, 매뉴얼상 같은 카드인 맨 `*SET_NODE` 의 멤버는 같은 자리 새 절점으로 옮기지 않고 **지웠다**. 보고 장치
  (`scanDeadReferences`)도 세 번째 사본이었다 — `_INTERSECT` 를 「지운 중간면 노드」로 적었다. 셋 다 정본 표로 모았다.
- **(10-17) S2 — 정본 닫힘을 그대로 쓰면 큰 덱에서 메모리가 터진다.** `include_closure::read` 는 인클루드 파일의 줄을 담는다.
  2.32GB 급 덱은 메시가 인클루드 안에 있는 경우가 많아 그대로 쓰면 수 GB 를 담는다. 그래서 같은 걸음(`card`)을 쓰는
  **흘려 읽기 판**(`readPaths` — 차례와 경로만)을 정본 안에 더했다. 규칙이 둘로 갈리지 않는다(단위 시험이 두 판을 대조한다).
- **(10-17) 인클루드 안 `*END` 뒤의 카드는 이제 참조로 세지 않는다**(정본 규칙 — Vol_I 179654). 예전에는 세어서 절점을 더
  남겼다(보수적). LS-DYNA 가 읽지 않는 카드라 지워도 덱이 깨지지 않는다.
- **(10-17) B1 — TET10 만 새 종류를 달았다.** 육면체 2차(23·24·29)는 예전처럼 HEX8 로 둔다 — 종류를 바꾸면 `== HEX8` 을 보는
  소비자가 많아 동작이 갈린다(그 덱은 이미 맞게 읽혔다). TET10 은 TET4 꼴 코너 + 종류 TET10 이고, `Validator` 야코비안 · 그림 ·
  위상 표는 TET10 을 사면체로 본다. 2차 솔리드를 쓰는 쪽은 `Mesh::forEachElementNode` 로 중간절점까지 본다.
- **(10-17) B3 — 「모든 파트」 op 의 규칙을 한 번 고쳤다.** 처음에는 인클루드에 요소가 하나라도 있으면 멈췄는데, 회귀
  (`test_assembler_include_ids` 의 czm · tetremesh)가 「마스터 덱에 자기 파트 + 다른 파트 인클루드」 꼴을 깼다고 알렸다. 그래서
  주 덱에 요소가 없을 때만 멈추고, 있으면 고치되 인클루드 파트는 손대지 않았다고 [WARN] 한다. strip 은 남길 키워드가 인클루드에
  있을 때만 · tetremesh 는 주 덱에 메시가 없을 때만 멈춘다.
- **(10-17) 펼친 덱은 주 덱 옆 임시 파일이다**(`.<줄기>.kr_flat_<시각>_<주소>.k`). 줄을 읽는 op 이 경로만 바꿔 같은 코드로 읽게 하려는
  것이고, 상대 경로 기준(주 덱 폴더)이 그대로다. 기본 산출 이름은 펼치기 **전에** 원본 이름으로 정한다(merge · strip).
  ⚠ 엔진 로더가 펼치지 않을 때 `flat.path()`(빈 문자열)를 열어 **모든 엔진 op 이 멈춘** 적이 있다 — 실측 탐침이 잡았다.
- **(10-17) 백엔드 pytest 는 `platform/backend/bin/KooRemapper` 를 잰다.** 그 자리는 compat 빌드만 채운다 — dev 빌드로 돌린 563 은
  4차 바이너리를 쟀고, 릴리스 빌드 뒤에 옛 규약(「쓰지 말라」) 단정이 빨개졌다(564 로 고쳤다).
