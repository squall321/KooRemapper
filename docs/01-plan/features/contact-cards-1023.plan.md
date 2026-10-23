# contact 카드 결함 전부 고치기 + map 직렬 전처리 (2026-10-23 밤)

**요청** 「결함은 다 고쳐야지 그건 최우선이야. 그리고 c++작업이라도 고쳐야할건 고쳐야하고」(사용자 10-23)
**근거** `contact-card-defects-1023.findings.md`(11개) + 그 뒤 코드를 읽다 더 나온 것.

## 왜
contact op 과 그 카드를 읽고 고치는 op(optimize · stabilize · modelmeta · assemble)이 **덱을 조용히 틀리게** 쓴다.
매뉴얼(Vol_I R16)은 카드 순서를 「정확히 이 순서」로 정한다 — ID → MPP 1(·2) → Card 1·2·3 → Card 4(형마다) → THRM → ORFR → 선택 카드 A…

## 범위 — 결함
| # | 결함 | 고침 |
|---|---|---|
| D1 | Card C FLANGL · CID_RCF 를 6·7열로 읽고 쓴다(매뉴얼 7·8열, 6열 공란) | 읽기 · 쓰기 모두 7·8열 |
| D2 | TIEBREAK Card 4 · THRM 을 선택 카드 뒤에 쓴다 | Card 1-3 → Card 4 → THRM → 선택 카드 |
| D3 | THRM 6열(FTOSA) 생략 시 1.0 | 0(= 0.5) · `ftosa` 키(옛 `chlm` 은 별칭) |
| D4 | TIEBREAK OPTION 생략 시 1(파손 없음) — 매뉴얼은 OPTION · NFLS · SFLS **required** | option 을 요구 · 파손 OPTION 이면 nfls · sfls 도 요구 · 13/14 · DAMPING 은 추가 카드라 거절 |
| D5 | tied_mortar → 없는 키워드 `TIED_SURFACE_TO_SURFACE_MORTAR` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED` · 아는 목록도 |
| D6 | ERODING 에 필수 Card 4 없음 · 다른 Card 4 형도 불완전 | ERODING Card 4 를 쓴다 · 우리가 못 쓰는 Card 4 형은 **거절**(조용히 불완전한 덱 대신) |
| D7 | 선택 카드 modify 가 Card 4 · THRM 을 지운다(파서가 넷째 카드를 Card A 로) | 파서가 형마다 카드 자리를 안다 · 선택 카드 줄만 바꾼다 · 모르는 꼴이면 거절 |
| D8 | 빈 줄 자리표시 카드를 건너뛴다 | 빈 줄도 카드로 센다(LS-DYNA 와 같게) |
| D9 | `_MPP` 덱의 MPP 1 을 Card 1 로 읽는다 | MPP 1(·`&` 로 시작하는 MPP 2)을 건너뛴다 |
| D10 | Card A 를 쓰면 MAXPAR 1.025 · DEPTH 2 를 늘 적는다 | 안 준 칸은 0(= 형의 기본) |
| D11 | `>= 0` 문이 뜻 있는 음수를 버린다(-1 sentinel) | 키가 있는지로 판단(std::optional) — 음수도 쓴다 |
| D12 | detect 가 thermal · tiebreak 형에 THRM · Card 4 를 안 쓴다 | create 와 같은 카드 조립 |
| D13 | skip_existing · subtract_existing 가 SET_SEGMENT 접촉을 못 알아본다 | 세그먼트 → 파트로 풀어 비교 · 세그먼트는 그대로 뺀다 |
| D14 | notes 13(subtract_existing 와 auto_create) | 코드로 확정해 문장 · 동작을 맞춘다 |
| D15 | 값 반올림 — FS · FD · BT 등 `%10.2f`, THRM · Card 4 `%10.3g` | 그 형식이 값을 그대로 돌려주면 그대로, 아니면 10칸 안의 가장 정밀한 표기 |
| D16 | 숫자를 못 읽은 YAML 값을 조용히 버린다(`catch(...){}`) | rc 1 과 그 키 · 값 |
| D17 | modify 가 Card 1 확장 칸(sboxid · mboxid · spr · mpr)을 무시한다 | 적용한다 |
| D18 | stabilize Lv8+ 가 SOFT 2 와 함께 MAXPAR 1.15 를 쓴다(SOFT 2 는 MAXPAR 를 안 쓴다) | 쓰지 않는다 |
| D19 | (확인 후) 쉼표 자유 형식 카드를 10칸으로 자른다 | 확인되면 같이 |
| — | optimize 가 카드를 직접 센다 · assemble 쓰기 · merge/cclip 등 | 정본 카드 위치를 쓴다 · 같은 결함이 있으면 같이 |
| D20 | stabilize 가 range-for 로 접촉을 돌면서 그 목록을 다시 파싱해 덮어쓴다(반복자 무효 — 미정의 동작) · TIEBREAK 에 SOFT 2 를 쓴다(Remark 2 — 구현 안 됨) | 번호로 돈다 · TIEBREAK 는 SOFT 를 그대로 두고 알린다 |
| D21 | remove 뒤의 액션이 줄을 밀면 다른 접촉을 지운다 | 지울 번호를 모았다가 맨 끝에 다시 읽은 자리로 지운다 |
| D22 | info 참조 검사 · restack/merge 죽은 참조 스캐너 · cnrb2spring 이 `_MPP` 의 MPP 1 을 Card 1 로 읽는다 | 셋 다 `ct_parseContacts` 의 카드 자리 |

## 범위 — C++ 성능
map 의 직렬 전처리(연결성 · 격자 색인 · 경계 추출 — 1·2단계에서 두 번). **산출이 바이트까지 같아야** 한다(20만 HEX8 sha `39a6a2af` · 회귀).
contact 와 겹치지 않으므로 하위 에이전트가 worktree 에서 따로 한다 — 결과는 검토 뒤 들인다.

## 바꾸지 않는 것
결함이 없는 칸의 바이트(골든) — 반올림 고침은 「그 형식으로 값이 그대로면 그 형식」 이라 대부분 그대로다.

## 검증
결함마다 회귀(옛 바이너리 FAIL · 새 바이너리 PASS) · 단위 · contact 골든 · 관문 전부 · 카탈로그 · 도움말 · 매뉴얼 쓸기. 솔버로는 못 잰다(라이선스).

## 배포
C++ 가 바뀌므로 사슬 전부 — compat 빌드 · 관문 · Drive · API/MCP · SIF 굽기 · /opt · 스모크.
