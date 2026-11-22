# 미룬 결함 3차 체크리스트 — 열린 줄 스물 · 판마다 main · Drive

계획 `deferred-defects-round3-1121.plan.md` · 맥락 `deferred-defects-round3-1121.context-notes.md`.

## A. 준비
- [x] A-1 사용자 선택(「열린 줄 스물 전부」 · 틈 덱 「거절 그대로」) · 줄 스물에 번호 · 판 다섯으로 나눔
- [x] A-2 계획 · 체크리스트 · 맥락 문서

## B. 1판 — 덱 머리 BOM · `*INCLUDE` 뿐인 주 덱(L-02 · L-03)
- [x] B-1 다시 재기 — matswap 번들 · cad_solid_merge_to_deck 조각 · `strain` · `squeeze` (설치된 판 `f20d5d5b`)
- [x] B-2 회귀 시험 `test_deck_bom.py` — 고치기 전 빨강 확인(`353d92c` — 빨강 59)
- [x] B-3 덱 · 번들 읽기에 BOM 떼기(원본을 따라 쓰는 쓰기 · assemble 족 · op 마다의 덱 읽기 · matswap) — `bbc3513` · 남은 자리 넷
  `5242abe` · 격자 파일 `cd52b79`(시험 259 항)
- [x] B-4 조각 — cad_solid_merge_to_deck 은 뗀다 · apply_carryover_plan 은 까닭 글(`bbc3513`)
- [x] B-5 `strain` · `squeeze` 명령줄 꼴 — 빈 메시 거절 · 시험(`09a57a7` — `test_include_only_main.py` 15 항)
- [x] B-6 훑기 다시(58 op × 꼴 넷) · JSON 입력의 BOM 재기 · 변이 — 덱 BOM 57 / 58 같음 · 인클루드 · 설정 YAML 차이 0 · 변이 38 / 38 빨강 ·
  BOM 없는 덱은 설치된 판과 64 / 64 같음
- [x] B-7 매뉴얼 3.1(e) · 23 장 · 도움말 · 미룬 목록 — 매뉴얼은 7 · 10 · 13 · 21 · 35 · 49 · 52 장까지 · 도움말은 바꿀 문장이 없다(맥락 노트
  5-4)
- [x] B-8 전체 재기(dev 판 `2a4604f0` · `cd52b79`) — 단위 246 / 246 · 회귀 136 / 136(파일 크기 상한을 건 채 135 — 200 MB 를 넘는 산출을
  내는 `test_remaining_surfaces.py` 는 상한 없이 다시 돌려 통과) · 백엔드 1049 통과 · 8 실패(작업 트리에 `.env` 가 없어 supervisor_log 넷 ·
  dev 바이너리에 이웃 `materials` · `gmsh` 가 없어 job_launcher 넷 — 이웃을 붙인 사본으로 32 통과 · 앞 판과 같은 여덟) · 계약(MCP venv 를
  잠깐 이어 전체) 1061 통과 · supervisor_log 넷
- [x] B-9 올리기 — main `98f5ec6` · 호환 빌드 `d1e2ce96` · 단위 246 · 회귀 136 · 설치 23:43Z · 스모크 넷 통과 · cli.sif · Drive
  `dist-20261121-234834Z` · 백엔드 1069 통과 · 알림(커밋 · 바이너리 sha256 · 판정 꾸러미) — 맥락 노트 6절

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
