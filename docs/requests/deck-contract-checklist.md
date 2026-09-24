# 덱 편집 계약 — 1차 구현 체크리스트 (2026-09-24)

요청서 `deck-contract-request-2026-09-24.md`, 실측 계획 `deck-contract-plan-2026-09-24.md`.
**공통 선행 관문** — LF 덱은 바이트가 안 바뀌어야 한다. `examples/*/small/*.k` 전 op 출력 sha256 을
수정 전에 떠 두고 매 단계 대조한다. 여기서 깨지면 개행 재적용이 틀린 것이다.

## P1-6 · D — 버그 2건 (선행 없음, 가장 작음)
- [x] `histElem` 에 `_SET` 제외 추가 (`ModelAssembler.cpp:2938`) — `histPart`(:2896)에는 이미 있다
      → 검증: `*DATABASE_HISTORY_SOLID_SET 7` 심고 merge → rc=1 오탐 사라짐
- [x] `*PART` 고정폭 폴백 8 → 10 (`KFileReader.cpp` parsePartSection)
      → 검증: 폴백 경로 덱에서 PID/SECID/MID 가 10칸으로 읽힘

## P1-5 · B — 넘침/잘림 금지
- [x] `fmt10d`(`ModelAssembler.cpp:15239`) 앞을 버리는 `substr` 제거 → 10칸에 맞는 표기 재포맷, 안 되면 raise
      → 검증: `dt2ms: -1.0e-7` 출력에 **음수 부호 보존**(지금 `1.0000E-07` — 물리가 뒤바뀐다)
- [x] `fmt10i`(:15243)·`setField`(`kw_util.h:54`) 같은 규약
- [x] 넘치면 rc=1 + errorMessage_, 입력 덱부터 어긋난 것은 WARN(`5581-5598` 규약 따름)

## P1-4 · C — `ContactDef.hasId` (읽기 + **쓰기 4곳**)
- [x] `contact_helpers.cpp:49-56` 판정을 endswith 전용 → `_ID` 끝 또는 `_ID_` 포함
- [x] `ContactDef` 에 `hasId` 추가, 편집 4곳(`contact_helpers.cpp:1203`·`1224`, `contact.cpp:955`·`989`)이 그것을 볼 것
      → 검증: `modify friction:0.33` 후 **fs 칸**에 0.33 · **ssid 칸 불변**(지금 SSID 를 덮어쓴다)
      → 검증: `modify soft:2 depth:35` 후 **필수 Card 3 잔존**(지금 사라진다)
      → ⚠ 회귀에서 **개수를 단언하지 말 것** — 개수만 보면 이 버그가 전부 통과한다
- [x] `_ID` 회귀 3종 추가(예제 덱 대신 회귀가 직접 만든다)(`examples/contact/model.k` 는 `_TITLE` 만 써서 이 경로를 안 밟는다)

## P1-1 · A — 개행 보존 (치명)
- [x] 읽을 때 개행 종류를 기억하고 쓸 때 되붙인다. **줄 문자열에 `\r` 을 남기지 말 것**
      (78곳의 `stoi`/`substr`/`back()` 분기가 전부 깨진다)
- [x] 진입점: `ModelAssembler.cpp:62-67`(loadBaseModel)·`132-135`(loadRawOnly), `KFileReader`
- [~] 출력: `ModelAssembler` 는 완료 / `KFileWriter`·`strip`·`relax`·`database` 는 다음 커밋, `KFileWriter:111,229`, `strip:177,225`, `relax:175,271`, `database`
      → 검증: CRLF 578 덱 → indent·database·relax·strip **4개 전부 CRLF=578**
        (지금 0 / 0 / **578 혼재** / 578 — relax 가 한 파일 안에서 개행이 갈린다)
      → 검증: LF 덱 전 op sha256 불변
      → 검증: CRLF 덱을 restack/refine 으로 돌려 엄격 재독(`5517`)이 rc=1 오판하지 않을 것 (**같은 커밋**)

## P1-2 · F — 무편집 진입점 + SYS-02 바이트 왕복 회귀
- [ ] 무편집 진입점. **각 op 의 read 경로를 태우고 write 경로로 낼 것** — cat 복사식은 아무것도 못 잡는다
- [ ] `tools/regress/test_roundtrip_bytes.py` — 픽스처 5종(LF / CRLF / 무-말미개행 / `I10=Y LONG=S` / 2줄 혼재)
      → 검증: sha256 + n_bytes + n_lines + n_crlf **4개 동시 일치**

## 남긴 것 (P2 이후)
- G EditGate 원장 / O-min 절대 참조 검사 / H kfile_inspect n_crlf / G11 ORTHO 거절 가드
- 이유는 계획서 §4.2. 특히 `kw_tok10` 8벌 흡수·ElemCardIndex 공용화는 회귀 신호가 묻힐 만큼 파급이 크다

## 실제 결과 (2026-09-24)

커밋 4건. 회귀 **37 → 40개**, 전부 통과. 매 항목 **무력화로 확인**했다.

| 커밋 | 무엇 | 무력화 |
|---|---|---|
| `4d22441` | `_SET` 오독 rc=1 오탐 · `*PART` 폴백 8→10 | 제외를 빼면 FAIL 2 |
| `e2281b3` | dt2ms 음수 부호 소실 | 옛 포매터로 되돌리면 FAIL 2 |
| `63f50a7` | `_ID` 편집이 SSID 칸 덮어씀 | 쓰기가 hasId 를 안 보면 FAIL 6 |
| `a25aa17` | CRLF 왕복 소실 | 되붙임을 빼면 FAIL 2 |

**셋은 요청서에 없던 것이다** — `_SET` 오독, dt2ms 부호, `_ID` 쓰기. 요청서가 든 근거
(7자리 EID 잘림 · TIED 225→0)는 재현되지 않았고, 대신 검증 중에 더 나쁜 것이 나왔다.

## 아직 남은 것

- **자체 ofstream op 들의 개행** — `strip`·`relax`·`database`·`KFileWriter` 등 25곳 이상.
  `relax` 는 한 파일 안에서 개행이 갈린다(최악). MSVC 텍스트 모드 결함도 같은 자리다.
- **무편집 진입점 + 픽스처 5종 바이트 왕복**(SYS-02 완전형) — 지금 회귀는 개행만 본다
- G EditGate 원장 / O-min 절대 참조 검사 / H kfile_inspect n_crlf / G11 ORTHO 거절 가드


## 2차 완료 (2026-09-24 이어서)

- [x] 자체 ofstream op 들의 개행 — `DeckWriter` 공용 계층으로 모음(d988740). **19개 op 보존, 깨짐 0**
- [x] 전 op 개행 매트릭스 `test_newline_matrix.py` — 카탈로그 예제를 구동기로 씀(op 이 늘어도 따라옴)
- [x] ORTHO/COMPOSITE 등 못 다루는 카드 배치 거절(d194c49)
- [x] 세트 참조 절대 검사(814ff72) — TN4 사건. 오탐 0건 확인, `*INCLUDE` 면 단정 안 함
- [x] `kfile_inspect` 개행 노출(f1b6d7d) — newline/n_crlf/n_lines/final_newline
- [x] **회신 요청서** `deck-contract-reply-2026-09-24.md`

회귀 **37 → 42개**, 전부 통과. 무력화 전 항목 확인.

### 다음(요청 측 답을 기다리는 것)
- DF-07 예약 대역 **실제 값** / DF-08 "템플릿" **정의** / 회귀 코퍼스 / dangling rc 정책 합의
- DF-20 편집 게이트 원장 — 출력 복사 4회 제거와 **같은 유닛**이어야 한다
