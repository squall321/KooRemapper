# 레시피 체크리스트 (2026-10-26 · 갱신 10-27)

계획 — `recipes-1026.plan.md` · 결정 — `recipes-1026.context-notes.md`

## 1. 저장
- [x] 모델 `Recipe` · `RecipeVersion` · `RecipeRun` (`app/models.py`)
- [x] 마이그레이션 `0014_recipes.py` → dev DB 적용

## 2. 샌드박스
- [x] 정적 검사(`app/recipes/check.py`) — 허용 import · 금지 이름 · 던더 속성 · run · test_ 규칙
- [x] 부트스트랩(`app/recipes/sandbox_main.py`) — rlimit · 사전 import · Landlock · seccomp · 감사 훅 · 제한 builtins · 봉투 출력
- [x] 실행기(`app/recipes/sandbox.py`) — 최소 환경 · 벽시계 · 출력 상한 · 프로세스 그룹 죽이기
- [x] 키트(`app/recipes/recipe_kit.py`) — Report · make_report · 파서 감싸기
- [x] 단위 시험(`test_recipe_sandbox.py`) — 겹마다 탈출 · 시간 · 메모리 · NaN · Landlock(15항)

## 3. 서비스 · 라우트
- [x] 제안(정적 검사 → 판 저장 → 자기 시험 · 앞 판 호환 → candidate/draft · 비슷한 레시피)
- [x] 실행 = 잡(`operation="recipe"`) — 번들 · 워커 갈래 · 산출 파일 · 실행 기록
- [x] 평가 · 등록 관문 · 내리기
- [x] 내보내기(`platform/recipes/<이름>/`) · 기동 때 git-load
- [x] 검색 · 상세 · 판
- [x] DB 통합 시험(`test_recipe_db.py`, 2항 — 전 수명주기 · running 으로 넣어 워커 레이스 회피)

## 4. MCP
- [x] 도구 7 · 설명에 규칙 둘
- [x] 도구 수 문서(README · CLAUDE_DESKTOP · TOOLS 73→80) · SKILL.md 규칙
- [x] `recipe_smoke.py` — 값으로(hotspot ≥1 · contact ≥1 · 샌드박스 상한 · 금지 거절, 19/19)

## 5. numpy · scipy
- [x] `api-constraints.txt`(현재 48판 고정) · `api.def` 에 numpy · scipy + %files
- [x] 굽기(taskset, 피크 ~1 GB) → numpy 레시피 다섯 층 검증 → api.sif 바꿔 끼움(옛 것 백업) → koorm_api 재기동 · numpy 2.4.5/scipy 1.17.1 라이브

## 6. 씨앗
- [x] 파트 최악값 비교 · 각도 문턱 · 핫스팟 포락 · 접촉 피크 — 제안 → 실행 → 평가 → 등록 → 내보내기(platform/recipes/)

## 7. 배포 · 마무리
- [x] 백엔드 전체(651 통과) · 도구 수(parity) · 스모크 다섯 + 레시피(80 · 35 · 25 · 20 · 62 · 19)
- [x] 커밋 · 푸시(의미 단위 7) · API/MCP 재기동(살아 있는 잡 0)
- [ ] Drive 게시 — SIF 가 바뀌었으니 **prod 반영 때 필요**(아티팩트 + prod alembic + 재기동, 사용자 타이밍)
- [x] 매뉴얼/플랫폼 문서(SKILL · TOOLS · README · CLAUDE_DESKTOP) · 메모리 · 완료 보고서
