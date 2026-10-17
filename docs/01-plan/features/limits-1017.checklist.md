# 체크리스트 — 한계 여섯 (10-17)

## 작은 셋
- [x] S1 hfdamp 거절 rc 255 → 1 — 시험(rc 1 단정 · C-1b 값 검사도) · 카탈로그 · SKILL · 매뉴얼 · pyKooCAE 문구(커밋은 문서 묶음에서) → `19c265d`
- [x] S3 목록 칸 → 정본 `noderefs::listCardOf`·`listCardFields` — 옮기기·치우기·보고 세 장치 · 실측 결함 둘(`_INTERSECT` 세트 ID 를 절점으로 · 맨 `*SET_NODE` 를 안 옮김) · `test_dead_node_list_cards`(배포본 FAIL 4) · 단위 2 → `f7ad8c0`
- [x] S2 cleanup-nodes → 정본 `include_closure::readPaths`(흘려 읽기 판) — 실측: 9단째 파일의 절점을 지웠다(rc 0) · F-10~14(배포본 FAIL 5) · 단위 2 → `5871e5d`

## 큰 셋
- [x] B1 2차 솔리드 — 리더(전체 절점 · TET10 코너) · Writer · bboxReport · modelmeta(`geometry_basis`) · info · 그림 셋 · rebind 소속
      · 25–28 과 모자란 카드는 그대로 거절 · test_secondorder_solid 다시 씀(배포본 FAIL 40) · 사면체 edge_len · 낡은 말 쓸기 → `0193459`
- [x] B2 재결속 — `tolerance` · 인클루드 덱 · 초기응력·파트 감쇠 카드 · 시험 E·F·G(배포본 FAIL 9) → `ea3e994`
- [x] B3 `flatten_includes` — 정본 펼치기 · 엔진 훅 · 줄 기반 op · 옵션 없을 때 거절 · test_flatten_includes 114항(배포본 FAIL 56) → `0b7daf8`

## 문서
- [x] 카탈로그 · ops_help(→ HelpCatalogData.inc) · SKILL.md · 매뉴얼 · 보고서 `limits-1017.report.md` · 장부 5차 · pyKooCAE `15e5e8f` · StepForge 답신 `44f16c9`
- [x] 메모리 — green-gates(백엔드 관문 바이너리) · absence(사례 × 쪼갬 탐침) · flip-premise(막음을 풀 때) · stepforge-boundary · pykoocae(REMAP 인클루드) · 색인

## 배포
- [x] compat 빌드 `cd07c327` · 관문 전부(회귀 99 · 단위 112 · 도움말 · 패리티 · backend 564 · 덱 바이트) · cli.sif `d8213999` · Drive `dist-20261017-082514Z` · API/MCP · 스모크 셋 · 설명 14/14 · 플랫폼 경유 3/3 · 스테이징
- [x] SIF(bake rc 0 · tar v119 · 메일) · /opt/apptainers · 세 사본 `eddd5783` · 네 자리 sha `cd07c327` · SIF 안 실행 · REMAP 배선 5/5
