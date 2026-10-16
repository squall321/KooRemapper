# 체크리스트 — 10-16 마무리

- [x] C++ 문구·주석 — `section` 안내 · `info` 「읽지 못해」 · 그림 셋이 요소가 없을 때 리더의 닫힘 안내를 찍는다 · stackdiagram `*MAT` 힌트 · 주석 넷 · 도움말(그림 셋 · 재결속 v2) → 빌드 · 관련 회귀 6파일 FAIL 0 · 전체 회귀 97/97 · 단위 rc 0 · 도움말 ALL PASS
- [x] 카탈로그 — rebind(바꾸는 칸 · 재검사) · 그림 셋 `model` · stackdiagram `*MAT` · modelmeta(닫힘 · 2차 null) · info(닫힘 · 참조 · 2차) · hfdamp(닫힘 · 실측 rc 255) · ale(인클루드 한계 · 실측 rc 1) · id_floor(`check` 값) → 패리티 ALL PASS · 백엔드 562
- [x] ★(점검 중 발견) gmsh 게이트가 meshfix `preview: true` 도 막았다 — gmsh 가 없는 서버에서 「gmsh 없이」 약속이 깨진다 → 예외 한 줄 · 시험(돌연변이 FAIL 확인)
- [ ] `server.py` 도구 설명 — 업로드 · `session_includes`(읽는 op · 넘김값은 REST 만) · `get_job`(`warnings`) → 백엔드 시험
- [ ] 백엔드 주석·API 설명 — `sessions/routes.py` · `jobs/routes.py` · `jobs/schemas.py`
- [ ] SKILL.md — 조각 넣기 흐름 · 재결속 · meshfix 거절·재결속·preview · 인클루드 마스터 · 2차 null · 경고 · 자주 쓰는 op
- [ ] TOOLS.md — 도구 수 72 · 검증 관문 셋
- [ ] 매뉴얼 · platform README 낡은 자리
- [ ] API · MCP 재기동 → `describe_operation` 이 새 글을 내는지 살아 있는 스택으로 확인
- [ ] 보고서 `docs/04-report/deck-contract-1016.report.md` — 수치 재측정
- [ ] 관문 — 회귀 · 단위 · 도움말 · 플랫폼 pytest · 스모크 셋
