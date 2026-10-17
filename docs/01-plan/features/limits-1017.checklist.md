# 체크리스트 — 한계 여섯 (10-17)

## 작은 셋
- [x] S1 hfdamp 거절 rc 255 → 1 — 시험(rc 1 단정 · C-1b 값 검사도) · 카탈로그 · SKILL · 매뉴얼 · pyKooCAE 문구(커밋은 문서 묶음에서) → `19c265d`
- [x] S3 목록 칸 → 정본 `noderefs::listCardOf`·`listCardFields` — 옮기기·치우기·보고 세 장치 · 실측 결함 둘(`_INTERSECT` 세트 ID 를 절점으로 · 맨 `*SET_NODE` 를 안 옮김) · `test_dead_node_list_cards`(배포본 FAIL 4) · 단위 2 → `f7ad8c0`
- [x] S2 cleanup-nodes → 정본 `include_closure::readPaths`(흘려 읽기 판) — 실측: 9단째 파일의 절점을 지웠다(rc 0) · F-10~14(배포본 FAIL 5) · 단위 2 → `5871e5d`

## 큰 셋
- [ ] B1 2차 솔리드 — 리더(전체 절점 · TET10 코너) · Writer · bboxReport · modelmeta(`geometry_basis`) · info · 그림 셋 · rebind 소속
      · 25–28 과 모자란 카드는 그대로 거절 · 시험(test_secondorder_solid 갈래 뒤집기 + 새 단정) · 낡은 말 쓸기
- [ ] B2 재결속 — `tolerance` · 인클루드 덱 · 초기응력·파트 감쇠 카드 · 시험
- [ ] B3 `flatten_includes` — 정본 펼치기 · 엔진 훅 · 줄 기반 op · 옵션 없을 때 거절 · 시험(쪼갠 덱 = 안 쪼갠 덱)

## 문서
- [ ] 카탈로그 · ops_help(→ HelpCatalogData.inc) · SKILL.md · 매뉴얼 · README · 보고서 5차 · 장부 · pyKooCAE · StepForge 답신 · 메모리

## 배포
- [ ] compat 빌드 · 관문 전부 · cli.sif · Drive · API/MCP · 스모크 셋 · 스테이징 · SIF · /opt/apptainers · 네 자리 sha
