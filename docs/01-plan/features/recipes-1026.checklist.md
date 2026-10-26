# 레시피 체크리스트 (2026-10-26)

계획 — `recipes-1026.plan.md` · 결정 — `recipes-1026.context-notes.md`

## 1. 저장
- [ ] 모델 `Recipe` · `RecipeVersion` · `RecipeRun` (`app/models.py`)
- [ ] 마이그레이션 `0014_recipes.py` → dev DB 에 올리기(`infra/scripts/migrate.sh`)

## 2. 샌드박스
- [ ] 정적 검사(`app/recipes/check.py`) — 허용 import · 금지 이름 · 금지 속성 · `run` · `test_` 규칙
- [ ] 부트스트랩(`app/recipes/sandbox_main.py`) — rlimit · 미리 import · Landlock · seccomp · 감사 훅 · 제한 builtins · 봉투 출력
- [ ] 실행기(`app/recipes/sandbox.py`) — 최소 환경 · 벽시계 · 출력 상한 · 프로세스 그룹 죽이기 · 취소
- [ ] 키트(`app/recipes/recipe_kit.py`) — `Report` · `make_report` · 파서 감싸기
- [ ] 단위 시험 — 겹마다 탈출 시도(파이썬 층을 끈 판으로 커널 층 따로) · 시간 · 메모리 · 출력 · NaN

## 3. 서비스 · 라우트
- [ ] 제안(정적 검사 → 판 저장 → 자기 시험 · 앞 판 시험 → candidate/draft · 비슷한 레시피)
- [ ] 실행 = 잡(`operation="recipe"`) — 묶음 만들기 · 워커 갈래 · 산출 파일 · 실행 기록
- [ ] 평가 · 등록 관문 · 내리기 · 지우기(등록된 적 없는 것만)
- [ ] 내보내기(`platform/recipes/<이름>/`) · 기동 때 읽어 들이기
- [ ] 검색 · 상세 · 판 · 실행 조회
- [ ] DB 통합 시험(queued 잡을 넣지 않는다 — 떠 있는 워커가 집는다)

## 4. MCP
- [ ] 도구 7 · 설명에 사용 규칙
- [ ] 도구 수 문서(README · CLAUDE_DESKTOP · TOOLS.md) · SKILL.md 규칙 둘
- [ ] `recipes_smoke.py` — 제안 · 실행 · 평가 · 등록 · 검색을 값으로

## 5. numpy · scipy
- [ ] `api-constraints.txt`(지금 이미지 판) · `api.def` 에 numpy · scipy
- [ ] 굽기(taskset · cgroup · 가용 감시) → 새 이미지에서 백엔드 시험 → 바꿔 끼우기(앞 판 보관)

## 6. 씨앗
- [ ] 판끼리 비교 · 각도별 문턱 · 핫스팟 · 접촉 추세 — 제안 → 실데이터 실행 → 평가 → 등록 → 내보내기

## 7. 배포 · 마무리
- [ ] 백엔드 전체 · 도구 수 대조 · 스모크 다섯 + 레시피 스모크
- [ ] 커밋 · 푸시(의미 단위) · API/MCP 재기동(살아 있는 잡 0) · Drive 게시
- [ ] 매뉴얼 · 플랫폼 문서 · 메모리 · 완료 보고서
