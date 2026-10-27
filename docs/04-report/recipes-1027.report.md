# 레시피 — 빌드 없이 쌓이는 분석 함수 (완료 보고 2026-10-27)

**요청** 「경험으로 정한 비교·분석 스크립트가 쌓이게 — 함수 레시피를 써서 효과가 있으면 LLM 이 등록하게」(사용자 10-26~27).
고른 것 — LLM 자동 + 자동 관문 · DB 즉시 + 등록 시 git · 리포트 분석·비교부터.

## 무엇을 지었나
분석 함수 하나(`run(reports, params)` + `test_*`)를 **격리 샌드박스**에서 돌리고, 효과가 있으면 **자동 관문**을 통과시켜
등록해 쌓는다. C++·백엔드에 박아 빌드·배포하던 길을 대체한다. 코드는 /workspace 바인드라 **재기동만**으로 라이브다.

| 층 | 자리 |
|---|---|
| DB | `Recipe`·`RecipeVersion`·`RecipeRun` + 마이그레이션 0014 |
| 샌드박스 | `app/recipes/{check,recipe_kit,sandbox_main,sandbox,registry}.py` |
| 서비스·라우트 | `app/modules/recipes/` · 워커 `operation="recipe"` 갈래 · 기동 git-load |
| MCP | 7 도구(search·get·run·propose·evaluate·register·deprecate) · 73→80 |
| 씨앗 | `platform/recipes/` 넷(파트 최악값 비교 · 각도 문턱 · 핫스팟 포락 · 접촉 피크) |

## 샌드박스(겹) — 실측으로 막힌 것
정적 검사(import 허용목록·금지 이름·던더 속성) → 제한 builtins+import 관문 → 감사 훅 → **Landlock**(읽기 뿌리만) →
**seccomp**(소켓·kill·ptrace…) → rlimit(AS·CPU·FSIZE·NPROC=0). api.sif·호스트 커널 5.15 에서 **다섯 층 다 켜짐**.
막힌 것: 번들 밖 읽기 · 쓰기 · fork · 스레드 · 소켓 · kill · 메모리 폭탄(MemoryError) · 무한 루프(SIGXCPU). 비밀 없는 최소 환경.

## 등록 관문(자동)
정적·자기 시험·(있으면)앞 판 호환 통과 **+ 성공 실데이터 실행 ≥1 + '쓸모 있었다' 평가(글 20자↑) ≥1**.
통과하면 등록 · 앞 판은 물러나고 · `platform/recipes/<이름>/` 로 내보낸다. 기동 때 sha 가 맞으면 읽어 들인다(prod 도 이 길).
**커밋·푸시는 서버가 하지 않는다**(재부팅 reset · 타 세션 커밋 · 바깥 전송 — context-notes §3).

## 검증 · 배포
- 백엔드 전체 **651 통과**(샌드박스 15 · DB 통합 2 포함).
- 살아 있는 플랫폼(dev API/MCP 재기동, 잡 0 확인) 스모크 — 기본 **80 도구** · reports 35 · deckops 25 · figures 20 · allops 62 ·
  **레시피 19/19**(씨앗을 실데이터로 돌려 hotspot 포락 ≥1 · contact 쌍 ≥1 · 샌드박스 상한 켜짐 · 금지 import 거절을 **값으로**).
- 커밋 7(6c4b014 샌드박스 · 4c96bbe 서비스 · ecc71c9 MCP · 598d117 씨앗 · 8c2700b 스모크 · 1ffceba numpy 준비 · 그 밖 문서). 모두 origin/main.

## 아직 안 한 것
- **numpy·scipy 이미지 굽기.** `api.def` + `api-constraints.txt`(현재 48판 고정) 는 커밋했지만 **다시 굽지 않았다** —
  돌고 있는 api.sif 엔 numpy 가 없다(stdlib 레시피·씨앗은 영향 0). 수치 레시피를 쓰려면 굽기(taskset·cgroup·가용 감시) +
  바꿔 끼우기 + Drive 게시가 남았다. 메모리 때문에 사용자 결정으로 미룸(earlyoom).
- **prod 반영** — 코드는 origin/main 에 있다. prod 는 `alembic upgrade head`(0014) + 재기동이 필요하다(노드/배포는 사용자).
- `tools/recipes_publish.sh`(등록 레시피를 git 에 커밋·푸시하는 사람 트리거) 는 아직 안 지었다 — 지금은 손으로 `git add platform/recipes/`.

## 바꾸지 않은 것
C++ 바이너리 · 카탈로그 · 기존 리포트 끝점 · 덱 산출 · 다른 리포(소스 6a53f8a 그대로).
