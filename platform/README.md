# KooRemapper Platform

KooRemapper(C++ CLI)의 모든 기능을 **FastAPI 백엔드 + MCP + React 프론트엔드**로 제공하는 플랫폼.
DB는 **Apptainer + PostgreSQL**(로컬). 자세한 설계는 상위 [`KOOREMAPPER_PLATFORM_PLAN.md`](../KOOREMAPPER_PLATFORM_PLAN.md).

> **기존 C++ 빌드/사용에 무영향.** 모든 코드는 `platform/`에 격리되어 있고,
> 빌드 연동은 `CMakeLists.txt`의 옵션 플래그(`KOOREMAPPER_PLATFORM_BIN`) 1곳뿐이다(미지정 시 무동작).

## 구성

| 구성요소 | 위치 | 비고 |
|---|---|---|
| FastAPI 백엔드 | `backend/` | async SQLAlchemy + Alembic + asyncpg |
| MCP 서버 | `mcp_server/` | (Phase 7) FastMCP streamable-http |
| 프론트엔드 | `frontend/` | (Phase 8) React + TS + Vite |
| 인프라 | `infra/apptainer/`, `infra/scripts/` | postgres/api .def + 기동 스크립트 |
| 세션 파일 | `storage/` | 업로드/산출물 실물 (gitignore) |
| 바이너리 | `backend/bin/` | CMake POST_BUILD 복사 대상 (gitignore) |

## 1) 바이너리 공급 (빌드 연동)

기존 빌드는 그대로. 백엔드용 바이너리를 받으려면 플래그만 추가:

```bash
# KooRemapper 루트에서
cmake -DCMAKE_BUILD_TYPE=Release \
      -DKOOREMAPPER_PLATFORM_BIN="$PWD/platform/backend/bin" \
      -S . -B build/linux
cmake --build build/linux -j$(nproc)
# → platform/backend/bin/KooRemapper (+ materials/) 자동 복사
```

플래그를 빼면 기존과 100% 동일하게 빌드된다.

## 2) 스택 기동 (Apptainer + Postgres + API)

```bash
cp platform/.env.example platform/.env
# .env 의 CHANGE_ME_* (POSTGRES_PASSWORD / KOORM_JWT_SECRET / DATABASE_URL 비번) 교체
#   예: openssl rand -hex 16

platform/infra/scripts/start.sh     # build → postgres → migrate → api
platform/infra/scripts/seed.sh      # 관리자 계정 1개 시드 (admin@local / admin)
```

- API 문서: http://127.0.0.1:8700/api/docs
- 헬스체크: `curl http://127.0.0.1:8700/api/health`
- 중지: `platform/infra/scripts/stop.sh`
- DB 초기화(파괴적): `platform/infra/scripts/reset-db.sh`

## 3) 로컬 개발 (컨테이너 없이 백엔드만)

```bash
cd platform/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# postgres 는 Apptainer instance(start.sh)로 띄워두고
alembic upgrade head
uvicorn app.main:app --reload --port 8700
```

## 포트 (기본, .env로 변경)

| 서비스 | 포트 |
|---|---|
| postgres | 5433 |
| api | 8700 |
| mcp | 8701 |
| web | 5273 |

환경변수 전체는 [ENVIRONMENT.md](ENVIRONMENT.md) 참조.

## 운영 스크립트 (infra/scripts)

| 스크립트 | 용도 |
|---|---|
| `start.sh` | build → postgres → migrate → api(+SPA) → mcp 일괄 기동 |
| `stop.sh` | api + postgres 중지 |
| `restart.sh` | api 재기동(이미지 확인 포함) |
| `restart-api-only.sh` | api만 빠르게 재기동(코드 변경 반영, SIF/마이그레이션 생략) |
| `status.sh` | 인스턴스 + 헬스 점검 |
| `migrate.sh` / `seed.sh` | 마이그레이션 / 관리자 시드 |
| `build-frontend.sh` | SPA 빌드(dist) |
| `backup-db.sh` | postgres 덤프(infra/data/backups, 최근 14개 보관) |
| `reset-db.sh` | (파괴적) postgres 데이터 초기화 |

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `/api/health` 에 `binary_present:false` | 바이너리 미복사 → 루트에서 `cmake -DKOOREMAPPER_PLATFORM_BIN=$PWD/platform/backend/bin … && cmake --build …` |
| 로그인/API `connection refused` | api 인스턴스 미기동 → `status.sh` 확인 후 `restart-api-only.sh` |
| `password authentication failed` | `POSTGRES_PORT` 가 다른 postgres와 충돌(이 호스트는 5436 사용). `.env` 포트/비번 일치 + `reset-db.sh` 후 재기동 |
| `/` 는 404, `/api/docs` 는 정상 | SPA dist 없음 → `build-frontend.sh` 후 `restart-api-only.sh` |
| Job이 `running`에 멈춤 | api 재기동 시 워커가 startup에서 자동으로 `failed` 처리(reconcile). 재기동만 하면 됨 |
| 업로드 413 | 파일이 `KOORM_MAX_UPLOAD_MB`(기본 512MB) 초과 |
| op 실행 422 "세션에 없는 입력 파일" | 파일 인자가 세션에 업로드되지 않음 → 먼저 업로드 |
| `meshfix` 실패 | gmsh 바이너리 필요(`requires_gmsh`) — `dist/gmsh/` 배치 필요 |
| api가 `--reload`로 계속 죽음 | 의도적으로 비활성(번들 마운트 .pyc churn). 코드 변경은 `restart-api-only.sh` |

## 진행 상태

- ✅ Phase 0 — 스캐폴딩 + 빌드 무영향 확인 + POST_BUILD 복사
- ✅ Phase 1 — Apptainer Postgres + FastAPI 뼈대 + 마이그레이션 + /health
- ✅ Phase 2 — 인증(JWT) & PAT(`kr_`) 발급/조회/취소 (`/api/v1/auth/login`, `/me`, `/me/tokens`)
- ✅ Phase 3 — 세션 CRUD + 파일 업로드/목록/다운로드/삭제 + `info` 파싱(nodes/elems/parts/bbox/`*INCLUDE`/keyword) (`/api/v1/sessions/...`)
- ✅ Phase 4 — op 카탈로그 **45개** (JSON Schema 인자, 예제, 매뉴얼) (`/api/v1/operations`, `/operations/{op}`)
- ✅ Phase 5 — 비동기 Job 큐 & runner (`/sessions/{id}/jobs`, `/jobs/{id}`/logs/outputs/cancel) — 업로드→op 실행→산출물 자동등록·다운로드 e2e 9/9
- ✅ Phase 6 — 전 op 통합 테스트 (45-agent 병렬). 초기 37/45 → argbuild 2건 수정(YAML flow/indent 스타일 + positional 플래그 순서) 후 **45/45**
- ✅ Phase 7 — MCP 서버 (`mcp_server/server.py`, FastMCP streamable-http, 12개 도구, PAT 전달) — Claude 전체 사이클 e2e 통과
- ✅ Phase 8 — 프론트엔드 (React+TS+Vite+Tailwind+TanStack Query) — 로그인/대시보드/세션/세션상세(파일·op 자동폼·job 실시간)/카탈로그/토큰. `pnpm build` 0 에러, Playwright로 실제 동작 확인
- ✅ Phase 9 — 배포: postgres+api(+SPA serving)+mcp 3 인스턴스, `start.sh` 일괄 기동, `build-frontend.sh`
