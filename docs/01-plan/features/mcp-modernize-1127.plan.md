# MCP 현대화 1127 — DynaForge MCP 서버(stateless · 공통 계약 C1 ~ C9 · SDK 2.x)

체크리스트 `mcp-modernize-1127.checklist.md` · 맥락 `mcp-modernize-1127.context-notes.md`. 보낸 쪽 hwaxportal-71 — 사용자 결정 11-27 「여기
프로젝트는 모두 stateless 로 바꿔야 하고, cae00 도 이 비전을 따르게」 · 추가 지시 「다 잘 고치자. 남기지 말고 최대한 많이 고쳐.」. 정본은 포털
리포 `docs/mcp-modernize/`(PLAN · contract.md · audit/contract.md — 읽기만, 여기에 옮기지 않는다).

## 0. 조건
- 도구 · 인자 이름과 동작은 바꾸지 않는다. report_* · set_campaign_* 묶기는 이름이 바뀌므로 제안만 한다.
- 올리는 때는 판 고정 · 라운드 규칙 그대로 — auto-pipeline 착지와 한 판으로 묶을지는 hwaxportal-87 과 맞춘다. 그 전까지는 가지
  `mcp-stateless`(origin 에 올려 둔다 — 재부팅 reset).
- 알린 뒤에는 cae00 이 받았다고 답할 때까지 main · Drive 를 그대로 둔다.

## 1. 차례
| 차례 | 항목 | 할 것 | 비고 |
|---|---|---|---|
| 1 | P1 stateless | `FastMCP(..., stateless_http=True)` · 탐침 `stateless` · 시험 둘 · 스모크 넷 | 서버 → 클라이언트 채널 0 (맥락 1절) |
| 2 | 바탕 | 표지 묶음 · 결과 꼴 도우미 · import — 구역 작업이 맨 위를 건드리지 않게 먼저 | 한 커밋 |
| 3 | C1 ~ C8 | 도구 120 을 정의 줄 차례로 일곱 구역으로 나눠 작업 트리마다 한 에이전트 → 내가 합친다 | 구역이 겹치지 않아 git 이 합친다 |
| 4 | 시험 | 전역 불변식(표지 · 인자 설명 · 이력 낱말 · 길이 상한) · enum · 경계가 백엔드와 같은지 | 백엔드 상수와 대조 |
| 5 | P2 SDK 2.x | `MCPServer` 로 옮기고 mcp.sif 를 다시 굽는다 — 옛 세대 클라이언트(스모크의 1.x)로 확인 | 할 수 있으면(71) |
| 6 | P3 오류 꼴 | `ToolError` — 2.x 에서만 뜻이 있다(1.x 는 어차피 머리를 붙인다) | 5 와 함께 |
| 7 | 알림 | 71 · 87 에 커밋 · SIF 파일 sha256 · 항목별 한 줄(「됨 · 할 차례 · 안 함(까닭)」) | 허브 캐시 열쇠는 없다(자체 빌드) |

## 2. 설계
- C6 표지 — 묶음을 맨 위에 둔다. 읽기(`readOnlyHint` · 거듭해도 같음), 더하기(새 행 · 새 잡), 덮어쓰기(같은 값이면 같음 · 덮음), 지우기 (덮음 ·
  거듭해도 같음). 우리 백엔드만 부르면 `openWorldHint=False`, 바깥(DataHub · stcx · 외부 클러스터)을 부르면 True.
- C7 결과 꼴 — `_shape(이름, {칸: 뜻})` 가 TypedDict(total=False)를 만든다. 칸 형은 Any, 적지 않은 칸도 그대로 싣는다(extra allow). 출력 검증이
  실제 값에 걸리지 않고 structuredContent 가 글과 같은 내용이다. 1.x FastMCP 는 구조 결과가 있으면 같은 내용을 글(content)과 structuredContent
  둘로 낸다(응답 두 배 — 알린다).
- C3 · C4 — `Literal` · `ge`/`le` 는 백엔드가 받는 집합 · 경계와 같을 때만 단다. 거절 자리가 백엔드에서 MCP 로 옮길 뿐 받는 집합은 같다.
  백엔드가 자유 글을 받으면 enum 을 달지 않는다(설명에 찾는 도구 이름).
- C1 — 첫 줄 한 문장(무엇) → 언제 · 형제 도구(이름) → 돌려주는 꼴 · 한도 · 페이지. 결정 번호 · 날짜 · 실측 일화 · 판 이력은 TOOLS.md 의 「도구
  설명에서 옮긴 이력」 절로 옮긴다. 같은 뜻의 영어 문장은 뺀다.
- C8 — 자르는 자리에 `truncated` · `total`(조용히 끊지 않는다).
- C9 — 이름은 그대로(조건). 설명에 게이트웨이 접두 이름이 없는지만 본다.
