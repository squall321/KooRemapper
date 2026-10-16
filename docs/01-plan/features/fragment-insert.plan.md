# 계획 — StepForge 조각을 기존 덱에 넣는다 (`cad_solid_merge_to_deck`, 우리 몫)

체크리스트 `fragment-insert.checklist.md` · 맥락 `fragment-insert.context-notes.md`
장부 항 — `docs/requests/deck-contract-checklist.md` 「경계 합의로 새로 진 것」 ★삽입
저쪽 정본 — `StepForge/docs/BOUNDARY-DYNAFORGE.md` §3-3(확정본 `540f89f`) · 조각 내보내기 `1425fcf`

## 0. 왜 지금인가
2026-10-15 에는 저쪽 조각이 0건이라 「입력 꼴을 정하는 쪽이 저쪽」이었다. 10-16 에 저쪽이
`export_part_fragment` 를 지었다 — 조각 `.k` + 대응표 JSON 의 칸 집합이 **확정**됐다(「여러분이 모르는 칸을
거절하시므로 빠짐없이 적습니다」). 그래서 우리 삽입의 입력이 실재한다.

## 1. 계약(저쪽 §3-3 그대로)
- 조각 `.k` — `*KEYWORD` · 머리 주석 둘 · `*NODE` · `*ELEMENT_SOLID`·`*ELEMENT_SHELL` · `*PART` ·
  `*SECTION_SOLID_TITLE`·`*SECTION_SHELL_TITLE` · `*MAT_*` · `*END`. `*SET_*` 없음. 고정폭(8자리 번호는 옆 칸과 붙는다).
- 대응표 JSON — 맨 위 넷 `unit`(늘 `mm-t-s`)·`frame`(늘 `world`)·`ranges`·`parts`. `ranges` 넷 `node`·`elem`·`pid`·`sid`
  (값은 실제로 쓴 `[lo, hi]` 또는 `null`). `parts[]` 여덟 `path`·`name`·`pid`·`node_start`·`node_count`·`elem_start`·
  `elem_count`·`coord_sha`. **칸은 이것뿐** — 모르는 칸은 거절한다(우리가 그렇게 말했다).
- `coord_sha` — 파트 절점 좌표를 `%16.9e` 셋씩 이은 줄을 사전순 정렬해 `\n` 으로 잇고 SHA-256 앞 16자(번호·순서 무관).
- 과도기 번호 길 — 저쪽이 1부터 쓰고 **우리 삽입이 옮긴다**. `ranges` 가 정본. SECID·MID 는 PID 를 따른다.

## 2. 짓는 것 — 이름이 드러나지 않는 핵심부터
| 단위 | 하는 일 | 증명 |
|---|---|---|
| U1 `util::sha256Hex` | FIPS 180-4 | 표준 시험 벡터 셋 |
| U2 `util::StrictJson` | 엄격 파서 — 꼬리 쓰레기·중복 키·잘못된 이스케이프·제어 문자 거절, `\uXXXX`(서로게이트 포함)→UTF-8, 정수는 int64 | 단위 시험 |
| U3 `fragment::parseMap` | 칸 집합 그대로(모르는 칸·빠진 칸 거절) · `ranges` 의 `null` 받음 | 단위 시험 |
| U4 `fragment::coordSha` | 저쪽 함수와 같은 값 | 파이썬(저쪽 식 그대로)으로 구한 기댓값 |
| U5 `fragment::check` | 조각 `.k` 를 대응표와 대조 — 번호가 `ranges` 안 · 파트마다 요소 수·구간·절점 구간·`coord_sha` · 대응표에 없는 파트 0 · `sid: null` ↔ `*SET_*` 0 | 단위 시험(정상 · 절점 하나 옮김 · 요소 더함 · 범위 밖) |
| U6 삽입 본체 | 대상 덱(인클루드 닫힘까지 센 커서) 위로 번호를 옮겨 `*END` 앞에 넣는다 · 넣은 뒤 다시 읽어 파트마다 요소 수·참조 무결성 | 회귀 시험 |
| U7 CLI·카탈로그·도움말·매뉴얼 | **이름은 사용자 확인 뒤** | — |

## 3. 정하지 않은 것(사용자)
- op 이름(CLI·카탈로그 — 카탈로그 이름이 곧 CLI 이름이다). 경계 문서의 이름은 `cad_solid_merge_to_deck`.
- 저쪽 새 질문 다섯(변환 JSON 파트 지목 · `residual_mm: null` · `planar_region` 파일 · `ranges.sid: null` · unit/frame 을 대응표에서 읽기).
