# Phase 10 — 하드닝 · 사용자관리 · 웹/MCP 패리티 UX

> 목표: 미구현 6대 항목을 전부 구현하고, **"웹에서도 되고 MCP로도 된다"** 는 패리티를
> 프론트엔드에서 **가시화**한다. 전체 UX를 최상으로. 기존 C++ 빌드 무영향 원칙 유지.
> 작성 2026-06-19 · 브랜치 `feat/kooremapper-platform`

## 0. 설계 원칙

1. **웹/MCP 패리티**: 모든 핵심 동작은 REST(프론트) + MCP(Claude) 양쪽에서 가능. 각 기능 화면에
   "이 기능은 웹 + MCP 둘 다 지원" 배지/안내를 표시.
2. **가시화 우선**: 상태(스택 헬스·워커·gmsh·MCP), 능력(op 45 + 도구), 보안(토큰·rate limit),
   사용자/세션을 한눈에. "뭐가 되고 안 되는지" 사용자가 화면에서 확인 가능.
3. **UX**: 일관된 로딩/빈/에러 상태, 토스트 알림, 커맨드 팔레트(cmd+k), 페이지네이션,
   접근성, 다크/라이트. 위험 동작은 확인 모달.
4. **무영향/격리**: 전부 `platform/` 안. 기존 빌드/바이너리 불변.

## 1. 구현 항목 (6 + UX)

### A. 사용자 관리 / 인증 (backend + frontend + MCP)
- 백엔드:
  - `POST /api/v1/auth/signup` (옵션: `KOORM_ALLOW_SIGNUP` 플래그로 on/off) → 일반 user 생성
  - `POST /me/password` 비밀번호 변경(현재 비번 검증)
  - `GET /admin/users` 목록 / `POST /admin/users` 생성 / `PATCH /admin/users/{id}` 활성·관리자 토글 /
    `POST /admin/users/{id}/password` 리셋 — 모두 `require_system_admin`
  - 모델: `User`에 이미 is_active/is_system_admin 있음(재사용)
- 프론트:
  - **Account** 페이지(설정): 내 정보 + 비밀번호 변경
  - **Admin → Users** 페이지(관리자만): 사용자 목록/생성/활성토글/관리자토글/비번리셋
  - 로그인 화면에 (signup 켜져 있으면) "회원가입" 링크
- MCP: `whoami`(현재 사용자) 도구 추가. (사용자 관리까지 MCP로 줄지는 보안상 admin 한정 — `list_users` admin만)

### B. Rate limiting (backend)
- `app/shared/ratelimit.py` — 경량 인메모리 슬라이딩윈도우 리미터(외부 의존 없이) + 의존성 주입.
- 적용: `/auth/login`(예: 10/min/IP), `/auth/signup`, `/me/tokens`(발급 남용), 업로드(예: 60/min/user).
- 초과 시 429 + `Retry-After`. 응답에 `X-RateLimit-*` 헤더.
- 설정: `KOORM_RATELIMIT_ENABLED`(기본 true), 한도 env.

### C. 입력↔산출 비교 뷰 (frontend, 백엔드 메타 재사용)
- `ComparePanel`: 세션의 파일 2개 선택 → meta diff(노드/요소/파트/bbox/크기 변화 +/- 강조).
- 세션 상세에 "비교" 탭/패널. Job 산출물 ↔ 입력 자동 비교 바로가기.

### D. nginx + TLS + MCP 원격 (infra)
- `infra/nginx/nginx.conf` : `/` → SPA(api:8700), `/api` → api, `/mcp` → mcp(8701).
- `infra/apptainer/nginx.def` : nginx 인스턴스(또는 호스트 nginx 문서). 자체서명 TLS(dev) + 인증서 마운트.
- MCP: `MCP_HOST=0.0.0.0` + `MCP_ALLOWED_HOSTS` 지원(이미 코드 있음) — start.sh에서 nginx 뒤 도메인 전달.
- 포트: nginx 8443(https)/8080(http). start.sh에 nginx 인스턴스 추가(옵션 `KOORM_ENABLE_NGINX`).

### E. gmsh 이미지 번들 (infra, meshfix 이식성)
- `api.def`에 gmsh 바이너리 + 런타임 라이브러리 동봉(현재 라이브러리만 추가됨, 바이너리는 호스트 의존).
  - 옵션1: `%files`로 `dist/gmsh` → 이미지 내부 `/opt/gmsh` 복사 + `setup-gmsh.sh`가 그쪽을 링크.
  - 옵션2(권장): apt로 `gmsh` 설치(데비안 패키지) → 버전 일관 + 의존 자동. meshfix가 PATH의 gmsh도 찾게 확인.
- 결과: 다른 호스트에서도 meshfix 동작(호스트 dist/gmsh 의존 제거).

### F. 시스템 상태 / 패리티 가시화 (backend + frontend) ★가시화 핵심
- 백엔드 `GET /api/v1/system/status`(인증): api/db/worker(큐 길이·실행중)/gmsh(존재)/mcp(포트)/바이너리/버전.
- 백엔드 `GET /api/v1/system/capabilities`: op 수, MCP 도구 수, 각 기능의 web/mcp 지원 매트릭스.
- 프론트 **System** 페이지: 헬스 카드(초록/빨강) + 워커 큐 라이브 + **웹↔MCP 패리티 매트릭스 표**
  (기능 | 웹 | MCP) + MCP 연결 안내(`claude mcp add ...` 스니펫, Desktop은 mcp-remote).
- 대시보드 상단에 미니 상태 위젯.

### G. 전체 UX 폴리시 (frontend)
- 토스트 시스템(성공/에러), 확인 모달(삭제/취소/비번리셋), 커맨드 팔레트(cmd+k: op/세션 점프),
  세션/Job/토큰/유저 목록 페이지네이션 컨트롤, 일관된 로딩/빈/에러 컴포넌트,
  각 기능 화면에 "웹+MCP" 배지.

## 2. 웹/MCP 패리티 매트릭스 (목표)

| 기능 | 웹 | MCP |
|---|---|---|
| 세션 CRUD | ✓ | ✓ |
| 파일 업로드/조회/다운로드 | ✓ | ✓ (+로컬경로) |
| op 카탈로그/옵션 | ✓ | ✓ |
| op 실행/Job/로그/취소 | ✓ | ✓ |
| 토큰 발급 | ✓ | (웹 전용) |
| 내 정보(whoami) | ✓ | ✓(신규) |
| 시스템 상태 | ✓(신규) | ✓(신규 도구) |
| 사용자 관리 | ✓(admin) | (admin 한정 list만) |

## 3. 작업 분할 (서브에이전트 병렬)

> 충돌 방지: 에이전트는 **새 파일**만 생성, 공유 파일(modules/__init__.py, App.tsx, AppShell.tsx,
> server.py, api.def, start.sh) 배선은 **메인(나)** 이 직접. API 계약은 본 계획서로 고정 → 프론트/백 병렬 가능.

- **WS1 백엔드 인증/유저** (메인): users 라우트 확장 + signup + password + admin/users.
- **WS2 백엔드 ratelimit + system** (에이전트 가능, 새 파일): `shared/ratelimit.py`, `modules/system/routes.py`.
- **WS3 MCP 패리티** (메인): whoami/system 도구.
- **WS4 프론트 페이지들** (에이전트 분할, 새 파일): AccountPage, admin/UsersPage, ComparePanel, system/SystemPage, api 클라이언트(users.ts/system.ts).
- **WS5 프론트 UX 코어** (에이전트, 새 파일): toast, ConfirmDialog, CommandPalette, Pagination, WebMcpBadge.
- **WS6 인프라 nginx/TLS** (에이전트, 새 파일): nginx.conf, nginx.def, 인증서 스크립트.
- **WS7 인프라 gmsh 번들** (메인, api.def 편집 + setup).
- **배선/통합** (메인): 라우터 등록, App.tsx 라우트, AppShell 내비, start.sh.

## 4. 검증 기준

- 백엔드 pytest 추가(유저 mgmt, password, ratelimit 429, system status). 기존 28 + 신규 유지.
- 라이브 API: signup→login→password change→admin user toggle; rate limit 429 재현; system/status 필드.
- 프론트 `pnpm build` 0 에러; Playwright로 신규 화면(Account/Users/System/Compare) 렌더 + 동작.
- meshfix: gmsh 번들 후 깨끗한 컨테이너에서 동작(이식성).
- nginx: https로 SPA+API+MCP 프록시 동작.
- 회귀: 45/45 op 라이브 검증 유지.

## 5. 진행 순서

1. (이 계획) 작성 ✓
2. WS1+WS3+WS7 (메인 백엔드/MCP/gmsh) + WS2 동시
3. WS4/WS5/WS6 프론트·인프라 에이전트 병렬 → 메인이 배선
4. 통합 검증(pytest + 라이브 + Playwright + 45/45 회귀) → 커밋/푸시
