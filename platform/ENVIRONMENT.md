# 환경변수 레퍼런스

`platform/.env` (예시: `platform/.env.example`). Apptainer 스크립트와 FastAPI 백엔드가 함께 읽는다.

## PostgreSQL
| 변수 | 기본값 | 설명 |
|---|---|---|
| `POSTGRES_USER` | `koorm` | DB 사용자 |
| `POSTGRES_PASSWORD` | (필수) | DB 비밀번호. `CHANGE_ME_*` placeholder면 기동 거부 |
| `POSTGRES_DB` | `koorm` | DB 이름 |
| `POSTGRES_PORT` | `5433` (이 호스트는 5436) | 호스트 노출 포트 — 충돌 시 빈 포트로 |

## 백엔드 (FastAPI) — `KOORM_` 접두사
| 변수 | 기본값 | 설명 |
|---|---|---|
| `KOORM_APP_ENV` | `development` | `production`이면 기본 시크릿으로 기동 거부 |
| `KOORM_API_PORT` | `8700` | API 포트 |
| `KOORM_MCP_PORT` | `8701` | MCP 포트(토큰 스니펫 생성에도 사용) |
| `KOORM_DATABASE_URL` | `postgresql+asyncpg://…` | asyncpg DSN (POSTGRES_* 와 일치시킬 것) |
| `KOORM_JWT_SECRET` | (필수) | JWT 서명 키. dev 기본값은 production에서 거부 |
| `KOORM_JWT_ACCESS_TTL_MIN` | `720` | access 토큰 수명(분) |
| `KOORM_PAT_DEFAULT_EXPIRES_DAYS` | `90` | PAT 기본 만료(일) |
| `KOORM_STORAGE_DIR` | `platform/storage` | 세션 파일 실물 경로 |
| `KOORM_KOOREMAPPER_BIN` | `platform/backend/bin/KooRemapper` | runner가 실행할 바이너리 |
| `KOORM_JOB_TIMEOUT_SEC` | `1800` | Job 1건 최대 실행시간 |
| `KOORM_WORKER_CONCURRENCY` | `4` | 동시 워커 수 |
| `KOORM_MAX_UPLOAD_MB` | `512` | 업로드 파일 1건 최대 크기 |
| `KOORM_CORS_ORIGINS` | `http://localhost:5273,…` | 허용 오리진(쉼표 구분) |
| `KOORM_SERVE_FRONTEND_DIST` | (빈값) | 설정 시 API가 SPA도 서빙(단일 오리진). start.sh가 dist 존재 시 자동 설정 |

## MCP
| 변수 | 기본값 | 설명 |
|---|---|---|
| `KOOREMAPPER_API_BASE` | `http://127.0.0.1:8700` | MCP가 호출할 REST 베이스 |
| `MCP_HOST` | `127.0.0.1` | MCP 바인드 호스트 |
| `MCP_ALLOWED_HOSTS` | (빈값) | 비-localhost 바인드 시 허용 Host(쉼표). 빈값이면 DNS-rebind 보호가 외부 Host를 거부 |
| `KOORM_MCP_MAX_DOWNLOAD_BYTES` | `5242880` | download_result가 인라인 반환할 최대 바이트 |

## Apptainer / 운영
| 변수 | 기본값 | 설명 |
|---|---|---|
| `KOORM_APPT_HOST_NET` | `0` | 1이면 인스턴스에 host 네트워크 강제(이 호스트는 rootless라 불가, 0 유지) |
| `KOORM_ADMIN_EMAIL` | `admin@kooremapper.local` | seed.sh 관리자 이메일 |
| `KOORM_ADMIN_PASSWORD` | `admin` | seed.sh 관리자 비밀번호(운영 시 변경) |
| `ALLOW_PLACEHOLDER_SECRETS` | `0` | 1이면 CHANGE_ME_ 가드 우회(throwaway 환경용) |

> **불일치 주의**: `POSTGRES_*` 와 `KOORM_DATABASE_URL` 의 사용자/비번/포트는 항상 일치해야 한다.
> 비번/포트를 바꾸면 `infra/data/postgres` 를 비우고(reset-db.sh) 재기동해야 새 initdb가 적용된다.
