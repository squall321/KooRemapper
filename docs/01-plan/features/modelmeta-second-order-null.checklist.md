# 체크리스트 — modelmeta 2차 솔리드 null + reason

- [x] 옛 바이너리를 기준선으로 복사
- [x] `modelmeta.cpp` — 파트 기하 다섯 칸 null + `geometry_reason` · mass null + `mass_reason` · orphan 상한 처리 · 규약·경고 문구
- [x] 회귀 `test_secondorder_solid.py` F·G 절 — 옛 바이너리 FAIL 7, 새 바이너리 PASS
- [x] 1차 덱 산출 불변 — 저장소 덱 500장 옛/새 대조: 498장 동일(새 null 칸 둘 빼고), 다른 둘은 2차 덱의 그 칸뿐
- [x] 소비자 — 프런트 `types.ts`(tsc rc 0) · `kr2datahub.py` 사유 전달(시험) · `kfile_modelmeta.py` 사유 통과(시험 · 변이 FAIL)
- [x] 매뉴얼 §45.5a · 원장 · 도움말 · StepForge 답신 §4 한 줄
- [x] 관문 — 단위 104 · 회귀 92/92 · help ALL PASS · 플랫폼 562
- [ ] 실사용 덱(6,053장) 옛/새 대조 — 돌리는 중(결과는 결정 노트에 적는다)
