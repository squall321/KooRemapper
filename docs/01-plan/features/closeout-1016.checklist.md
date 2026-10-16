# 체크리스트 — 10-16 마무리

- [x] C++ 문구·주석 — `section` 안내 · `info` 「읽지 못해」 · 그림 셋이 요소가 없을 때 리더의 닫힘 안내를 찍는다 · stackdiagram `*MAT` 힌트 · 주석 넷 · 도움말(그림 셋 · 재결속 v2) → 빌드 · 관련 회귀 6파일 FAIL 0 · 전체 회귀 97/97 · 단위 rc 0 · 도움말 ALL PASS
- [x] 카탈로그 — rebind(바꾸는 칸 · 재검사) · 그림 셋 `model` · stackdiagram `*MAT` · modelmeta(닫힘 · 2차 null) · info(닫힘 · 참조 · 2차) · hfdamp(닫힘 · 실측 rc 255) · ale(인클루드 한계 · 실측 rc 1) · id_floor(`check` 값) → 패리티 ALL PASS · 백엔드 562
- [x] ★(점검 중 발견) gmsh 게이트가 meshfix `preview: true` 도 막았다 — gmsh 가 없는 서버에서 「gmsh 없이」 약속이 깨진다 → 예외 한 줄 · 시험(돌연변이 FAIL 확인)
- [x] `server.py` 도구 설명 — 업로드(★인클루드를 먼저 — 실측: 마스터를 먼저 올리면 meta 절점 0 으로 남는다) · `session_includes`(고쳐 쓰는 op 만 주 덱 · 넘김값은 REST 만) · `get_job`(`warnings` — 절점 참조도 실린다, 실측) → 백엔드 562 · 패리티
- [x] 백엔드 주석·API 설명 — `sessions/routes.py` · `jobs/routes.py`(422 문구에 「REST 전용」) · `jobs/schemas.py`
- [x] SKILL.md — 조각 넣기 흐름 · 재결속 · 멈추는 자리(meshfix · hfdamp · ale) · 인클루드 순서 · 2차 null · `warnings` · 모르는 키 422 · 자주 쓰는 op
- [x] TOOLS.md — 도구 수 54 → 72 · 검증에 그림·덱 op 스모크 · 패리티 ALL PASS
- [x] 매뉴얼(§50 재결속 두 줄 · §45.4 `*MAT` 닫힘 덧말 · §35 ale 인클루드 마스터 소절) · platform README(op 수 · meshfix preview)
- [ ] API · MCP 재기동 → `describe_operation` 이 새 글을 내는지 살아 있는 스택으로 확인
- [ ] 보고서 `docs/04-report/deck-contract-1016.report.md` — 수치 재측정
- [ ] 관문 — 회귀 · 단위 · 도움말 · 플랫폼 pytest · 스모크 셋
