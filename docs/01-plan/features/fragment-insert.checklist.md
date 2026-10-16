# 체크리스트 — StepForge 조각 삽입

- [x] U1 `util::sha256Hex` + 표준 벡터
- [x] U2 `util::StrictJson` + 단위 시험(거절 꼴 · `\u` 이스케이프)
- [x] U3 `fragment::parseMap` — 칸 집합 그대로
- [x] U4 `fragment::coordSha` — 저쪽 식과 같은 값(파이썬 기댓값)
- [x] U5 `fragment::check` — 조각 ↔ 대응표 대조
- [x] 관문(단위 104 · 회귀 90 · help) · 커밋·푸시 — 여기까지는 사용자에게 보이는 이름이 없다
- [x] U6 삽입 본체 — `ModelAssembler::applyCadSolidMerge`(src/assembly/CadSolidMerge.cpp)
- [x] U7 CLI·카탈로그·도움말·매뉴얼(§49) — 이름은 경계 문서 그대로 `cad_solid_merge_to_deck`(사용자 「다 끝까지」 — 추천안)
- [x] 회귀 `test_cad_solid_merge.py` 30항 — 저쪽 실물 조각 · 표준/인클루드/i10 덱 · 거절 아홉
- [x] 관문 — 단위 104 · 회귀 91 · 도움말 · 플랫폼(카탈로그·패리티·dangling 28) · 42 op 산출 덱 동일
