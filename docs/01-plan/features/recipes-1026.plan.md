# 레시피 — 빌드 없이 쌓이는 분석 함수 (2026-10-26)

**요청** 「경험으로 정한 비교·분석 스크립트가 경험으로 쌓이게 하려면 어떻게 해야 하나. 지금은 기능을 하나 더할 때마다
빌드해서 올려야 하니, 함수 레시피를 써서 효과가 있으면 LLM이 등록하게끔 했으면 좋겠는데」(사용자 10-26)

**사용자가 고른 것**
- 등록 문턱 — **LLM 자동 + 자동 관문**. 샌드박스에서 자기 시험 통과 + 실데이터 실행 성공 + 효과 평가가 붙으면 LLM 이 바로 등록한다. 사람은 내리거나 지울 수 있다.
- 저장 — **DB 즉시 + 등록 시 git**. 초안 · 후보 · 실행 기록은 DB 에, 등록되면 `platform/recipes/<이름>/` 에 코드 · 메타 · 시험을 파일로 내보낸다.
- 첫 판 — **리포트 분석 · 비교부터**(sphere · impact · deep).

## 레시피 한 개
파이썬 모듈 하나(`run(reports, params)` + `test_*()`)와 메타(무엇을 묻나 · 언제 쓰나 · 받는 리포트 종류 · 필요한 입력 · 인자 · 꼬리표).
판은 바뀌지 않는다(새 판을 올린다). 생명주기는 다음과 같다.

| 상태 | 뜻 | 누가 보나 |
|---|---|---|
| draft | 올렸지만 정적 검사나 자기 시험을 못 넘었다 | 올린 사람 · 관리자 |
| candidate | 정적 검사 + 자기 시험 + 앞 판 시험을 넘었다 | 올린 사람 · 관리자 |
| registered | 관문을 넘었다 — 누구나 검색 · 실행 | 모두 |
| superseded | 새 판이 등록돼 물러났다(기록으로 남는다) | 모두 |
| deprecated | 사람이 내렸다(까닭을 남긴다) | 올린 사람 · 관리자 |

## 등록 관문(자동)
1. 정적 검사 통과 · `test_` 함수가 하나 이상이고 각각 `run` 을 부르고 `assert` 가 있다.
2. 자기 시험 전부 통과(샌드박스).
3. **앞 등록 판의 시험을 새 판의 `run` 으로 다시 돌려 전부 통과** — 누구나 판을 올릴 수 있게 하는 대신 지키는 회귀 관문이다.
4. 그 판으로 실데이터 실행이 한 번 이상 성공(succeeded).
5. 그 판의 실행에 `useful=true` 평가가 하나 이상 있고, 평가 글이 20자 이상(무엇을 보였나).

## 실행 — 플랫폼 잡
설계에서 말한 대로 실데이터 실행은 플랫폼 잡(`operation="recipe"`)이다. 세션 소유 · 슬롯 4 · 로그 · `env_snapshot` 을 그대로 쓴다.
산출은 세션 파일(`recipe_<이름>_v<판>_<잡>.json`)과 실행 기록(`recipe_runs`)이다. 제안할 때의 자기 시험만 API 안에서 바로 돈다
(리포트를 안 읽는다 · 동시 2 · 60초).

## 샌드박스(겹)
| 겹 | 무엇을 막나 |
|---|---|
| AST 허용 목록 | import 는 표준 일부 · numpy · scipy 일부 · `recipe_kit` 만. `_` 로 시작하는 속성 · 위험한 이름(open · eval · getattr …) · 파일을 읽고 쓰는 numpy 함수 이름 |
| 제한 builtins | 위 이름을 뺀 builtins · import 관문 |
| 감사 훅 | 읽기 뿌리 밖 열기 · 모든 쓰기 · 프로세스 · 소켓 · ctypes · mmap · gc 탐색 · pickle · marshal |
| Landlock(커널) | 읽기는 파이썬 · 키트 · 입력 묶음만, 쓰기 · 지우기 · 만들기는 어디에도 없다 |
| seccomp(커널) | socket · connect · kill · ptrace · io_uring · mount · unshare · bpf … |
| rlimit | AS 2 GiB · CPU · NPROC 0(fork · 스레드) · FSIZE 0 · NOFILE |
| 환경 | 비밀 없는 최소 환경 · BLAS 스레드 1 · `python -I` |
| 상한 | 벽시계 · 출력 크기 · NaN 은 null 로 |

10-26 탐침(api.sif · 커널 5.15) — Landlock ABI 1 과 seccomp 가 컨테이너 안에서 켜지고, 비밀 파일 · 부모 프로세스 environ ·
쓰기 · 지우기 · fork · 스레드 · 소켓 · kill 이 막혔다. 커널 층이 없는 박스에서는 파이썬 층만 남는다 — 실행 기록에 어느 층이 켜졌는지 남긴다.

## 입력
리포트 묶음 — API 가 리포트마다 `meta.json` · `cases.json`(승격 칸 + `parts_metrics`) · 필요하면 `data.json`(임베드 데이터)을 만든다.
레시피는 `recipe_kit.Report` 로 받는다(`meta` · `parts` · `cases` · `facts()` · `data` · `hotspots()` · `contact_profile()` · `case_energy()` ·
`part_series()` · `analytics()` · `block()` — 파서를 그대로 부른다). 시험은 `make_report(...)` 로 작은 리포트를 만든다.

## 저장과 퍼뜨리기
- DB(마이그레이션 0014) — `recipes` · `recipe_versions` · `recipe_runs`.
- 등록하면 `platform/recipes/<이름>/recipe.py` · `recipe.json`(메타 · 관문 결과 · 근거 · 코드 sha256)을 쓴다.
- API 가 뜰 때 `platform/recipes/` 를 읽어 DB 에 없는 판을 넣는다(sha 가 안 맞으면 건너뛰고 경고). 그래서 git 으로 옮겨 간 레시피가 prod 에서도 뜬다.
- **커밋 · 푸시는 API 가 하지 않는다** — `tools/recipes_publish.sh` 가 `platform/recipes/` 만 커밋하고 민다(결정 노트 3).

## MCP 도구 (고정 7)
`recipe_search` · `recipe_get` · `recipe_run` · `recipe_propose` · `recipe_evaluate` · `recipe_register` · `recipe_deprecate`.
레시피가 늘어도 서버를 다시 빌드하지 않는다. SKILL.md 에 두 규칙 — 분석 코드를 쓰기 전에 `recipe_search`, 즉석 분석이 효과를 보면 `recipe_propose`.

## numpy · scipy
api.sif 에는 **없다**(10-26 실측 — 앞서 본 numpy 2.4.5 는 호스트 `~/.local` 의 것이었다. 샌드박스는 `-I` 라 그것을 못 본다).
`api.def` 에 numpy · scipy 를 더하고 나머지 패키지는 지금 이미지 판으로 고정해(`api-constraints.txt`) 다시 굽는다. 그 전까지는 표준 라이브러리만.

## 씨앗(경험에서)
선택지 글에 적은 넷 — 판끼리 비교 · 각도별 문턱 넘는 파트 · 핫스팟 · 접촉 추세. LLM 과 같은 길(제안 → 실데이터 실행 → 평가 → 등록)로 올린다.

## 바꾸지 않는 것
C++ 바이너리 · 카탈로그 · 기존 리포트 끝점 · 덱 산출 · 다른 리포.

## 검증
정적 검사 단위 · 샌드박스 겹마다 탈출 시도(파이썬 층을 끈 판으로 커널 층을 따로) · DB 통합(제안 · 실행 · 평가 · 등록 · 내보내기 · 읽어 들이기) ·
도구 수 대조 · 백엔드 전체 · 스모크 다섯 + 레시피 스모크 · 살아 있는 플랫폼에서 씨앗 넷.

## 배포
코드는 /workspace 바인드라 API · MCP 재기동(살아 있는 잡 0)으로 실린다. 마이그레이션 0014. api.sif 다시 굽기(메모리 감시) → 바꿔 끼우기.
Drive 게시(SIF 가 바뀐다). C++ 가 안 바뀌므로 compat · cli.sif · SmartTwinPreprocessor.sif 는 그대로다.
