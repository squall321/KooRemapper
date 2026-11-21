# 미룬 결함 2차 체크리스트 — 사용자 결정 넷 · main · Drive

계획 `deferred-defects-round2-1120.plan.md` · 맥락 `deferred-defects-round2-1120.context-notes.md`.

## A. 재기 · 준비
- [x] A-1 ★ 셋 재현(T-1 ~ T-4 · I-1) · 같은 쓰기 함수의 N-1 ~ N-4 · extract-parts I10 섞임 h ~ m · tetremesh 가 안 읽는 키워드
- [x] A-2 사용자 선택 넷(이름 그대로 · 줄만 세운다 · 거절한다 · ★ 셋 + 위상 전파)
- [x] A-3 계획 · 체크리스트 · 맥락 문서

## B. 파싱 줄(파이썬)
- [ ] B-1 `_PARSE_LOCK` — `ingest_report` 전체 · `attach_media` 파싱
- [ ] B-2 시험(최대 겹침 1 · 잠금 안 파싱) · 변이 확인 · 닿는 기존 시험
- [ ] B-3 임시 스택에서 동시 올리기 둘의 최고 RSS

## C. 폭 섞인 인클루드 거절(C-4)
- [ ] C-1 판정 함수 하나(`include_closure`) — `inlined` 와 extract-parts 가 같이 쓴다
- [ ] C-2 시험 a ~ m(rc · 까닭 글 · 거절 때 산출 없음) · 변이 확인
- [ ] C-3 매뉴얼 48.2 · 도움말 문장

## D. 쓰기 함수 · tetremesh · unfold · id_floor
- [ ] D-1 회귀 시험 `test_writer_width_shells.py` — 고치기 전 빨강 확인
- [ ] D-2 원본 훑기 지움 + `map` 결과 메시가 두께 셸 번호를 옮긴다(N-2 · N-3 · N-4)
- [ ] D-3 좌표 폭 · `writeFile` 폭 선언 · 번호가 칸을 넘으면 거절(N-1 · T-4)
- [ ] D-4 tetremesh — 폭 · 셸 블록 그대로(T-2 · T-3) · unfold 폭
- [ ] D-5 id_floor int 상한 거절(I-1)
- [ ] D-6 새 시험 초록 · 변이마다 빨강 · 표준 덱 산출 바이트 동일
- [ ] D-7 전제를 말하는 글 쓸기(매뉴얼 43.8 · 도움말 · MCP 설명 · SKILL)

## E. 색인기 위상 전파
- [ ] E-1 고치기 전 산출 sha 기준선(`map` · `unfold` — 리포 덱 · 회귀 픽스처)
- [ ] E-2 전파 바꿈 · 기하 전파 지움
- [ ] E-3 83 덱 칸 동일 · 산출 sha 동일 · 새로 되는 3 + 5 덱 · 생성기 꼴 다섯 · 두 덩어리 2 는 거절
- [ ] E-4 1차 시험의 기대 바꿈 · 단위 시험 · 매뉴얼 9장 · 도움말

## F. 전체 재기
- [ ] F-1 단위 시험 · 회귀 전부(고치기 전 판과 실패 목록 대조)
- [ ] F-2 백엔드 pytest · MCP 계약 시험
- [ ] F-3 검토 한 차례(찾은 것은 소스에서 확인한 뒤 고친다)

## G. 올리기
- [ ] G-1 main 합치기 · 푸시
- [ ] G-2 호환 빌드 · GLIBC 확인 · 잡 확인 뒤 설치
- [ ] G-3 dev DB 0021 · 재기동 · health · 스모크
- [ ] G-4 cli.sif · api.sif 안에서 바이너리 확인 · Drive 게시 · `BUILD_INFO.txt` · `SHA256SUMS`
- [ ] G-5 알림 · cae00 점검 문서 · 1차 체크리스트 닫기 · 메모리
