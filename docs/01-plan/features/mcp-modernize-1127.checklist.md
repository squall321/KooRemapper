# MCP 현대화 1127 체크리스트 — DynaForge MCP

계획 `mcp-modernize-1127.plan.md` · 맥락 `mcp-modernize-1127.context-notes.md`.

- [x] 0 받음(hwaxportal-71 · 11-27 두 번) · 포털 계획 · 계약 · 감사 읽기 · 87 에 묶을지 물음
- [x] 1 P1 stateless — 채널 쓰임 0 확인 · `stateless_http=True` · 탐침 `stateless` · 계약 시험 15 / 15 · 변이 4 / 4 · 임시 MCP(mcp.sif 1.28.0)에
  스모크 넷 통과
- [x] 2 바탕 — 표지 묶음 · `_shape` · import(`2352697e`)
- [x] 3 C1 ~ C8 구역 여덟 — 작업 트리마다 에이전트 하나 · 겹침 없이 합침(이름 겹침 0) · 손질(`_REPLACE` · 인자 글 이력 둘)
- [x] 4 시험 — 전수 절(표지 · 몸통 대조 · 인자 설명 · 설명 꼴 · 결과 꼴 · 백엔드 대조) · 변이 6 / 6 · 2.x SIF 임시 MCP 에 스모크 여섯 PASS ·
  스모크가 안 부르는 목록 꼴 넷 실호출
- [x] 5 P2 SDK 2.x — 두 SDK 로 도는 server.py · mcp 2.3.0 고정판 · `PYTHONNOUSERSITE=1` · 본문 상한 1 GiB · 새 SIF 를 scratch 에
  구움(`8da8d1cd`)
- [x] 6 P3 ToolError — 감싸개 한 곳(몸통 밖) · SIF 시험
- [x] 6b 발견한 결함 둘 — report_compare 표 늘 「—」(`597ddbdc`) · ingest_report scenario.json 글 늘 거절(`0281f03e`)
- [ ] 7 올림(87 회차) · Drive · 71 · 87 알림 · cae00 점검 문서 절
