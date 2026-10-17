# 체크리스트 — 한계 여섯 (10-17)

## 작은 셋
- [ ] S1 hfdamp 거절 rc 255 → 1 — 시험(rc 1 단정) · 카탈로그 · 매뉴얼 · pyKooCAE 문구
- [ ] S3 `cleanupDeadNodeRefs` 목록 칸 → 정본 표 · 세트 분류 정본 — `_INTERSECT` 실측(돌려서) · 시험 · 단위 시험
- [ ] S2 cleanup-nodes 인클루드 → 정본 닫힘 — `␣+` 이음 · 인클루드 안 `*END` · 깊이 상한을 「못 봤다」로 · 시험

## 큰 셋
- [ ] B1 2차 솔리드 — 리더(전체 절점 · TET10 코너) · Writer · bboxReport · modelmeta(`geometry_basis`) · info · 그림 셋 · rebind 소속
      · 25–28 과 모자란 카드는 그대로 거절 · 시험(test_secondorder_solid 갈래 뒤집기 + 새 단정) · 낡은 말 쓸기
- [ ] B2 재결속 — `tolerance` · 인클루드 덱 · 초기응력·파트 감쇠 카드 · 시험
- [ ] B3 `flatten_includes` — 정본 펼치기 · 엔진 훅 · 줄 기반 op · 옵션 없을 때 거절 · 시험(쪼갠 덱 = 안 쪼갠 덱)

## 문서
- [ ] 카탈로그 · ops_help(→ HelpCatalogData.inc) · SKILL.md · 매뉴얼 · README · 보고서 5차 · 장부 · pyKooCAE · StepForge 답신 · 메모리

## 배포
- [ ] compat 빌드 · 관문 전부 · cli.sif · Drive · API/MCP · 스모크 셋 · 스테이징 · SIF · /opt/apptainers · 네 자리 sha
