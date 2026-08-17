# DynaForge 가시성 3단 모델 — 계획

> 심의(HWAX 시뮬심의·시험계획)가 실제 모델·해석 결과를 근거로 쓰게 하려면 조회 시야를
> 정해야 한다. 사용자 요구: **전체 통계는 공개 / 구체 내용은 내 계정 / 내 모델도 원하면
> 전체 공개 지정**. 공개 범위는 회사·부서·팀 단위(HEAX Hub 와 동일 4단).

## 1. 왜 필요한가

지금 DynaForge 의 세션·파일·잡·리포트는 전부 `user_id` 스코프다. 그래서 게이트웨이
서비스 계정(hwax-gateway@heax.local)으로 조회하는 심의는 **0건**을 본다 — 실제로는
세션 12개·K파일 25개·잡 8건이 있는데도(2026-08-17 실측).

심의가 "일반적으로 얇으면" 대신 **"우리 조직이 이 부품을 이렇게 모델링해 왔다"** 를
말하려면 조회 경로가 있어야 한다.

## 2. 3단 구조

| 층 | 도구 | 시야 | 심의에서의 쓸모 |
|---|---|---|---|
| **전체 통계** | corpus_summary · material_usage · operation_usage · report_corpus | 인증된 누구나(집계만) | "이 물성이 12개 모델에서 쓰인다" → 시험 우선순위 |
| **개인 상세** | 기존 list_sessions · inspect_file · report_* | 내 계정 | "내 모델 3번 파트" → 구체 진단 |
| **공개 지정** | set_session_visibility | 지정 범위(회사·부서·팀) | 조직 레퍼런스 모델 |

집계는 **개인 식별 정보를 담지 않는다** — 세션명·파일명·소유자를 빼고 수치와 물성·
오퍼레이션 이름만 낸다. 그래야 시야 배선(신원 전달) 없이도 지금 바로 붙는다.

## 3. 스키마 변경

현재 `users` 에 조직 정보가 없고(id·email·password_hash·display_name·is_active·
is_system_admin·created_at), `sessions` 에 가시성 개념이 없다. 둘 다 추가한다.

```sql
-- 0003_visibility

-- 조직 — 부서·팀 단위 공개를 하려면 사용자에 소속이 있어야 한다.
-- 자유 문자열로 둔다: 포털/SSO 가 주는 값을 그대로 받아 적고, 정규화는 나중에.
ALTER TABLE users ADD COLUMN department VARCHAR(120);
ALTER TABLE users ADD COLUMN team       VARCHAR(120);

-- 가시성 — HEAX Hub 와 같은 4단(company|department|team|private).
-- 기본 private: 기존 세션의 노출 범위를 마이그레이션이 넓히지 않는다.
ALTER TABLE sessions ADD COLUMN visibility VARCHAR(16) NOT NULL DEFAULT 'private';
CREATE INDEX ix_sessions_visibility ON sessions (visibility);
```

판정 규칙(단순·명시적).

```
private     → 소유자만
team        → 소유자 + 같은 team(둘 다 비어있지 않을 때만 매칭)
department  → 소유자 + 같은 department
company     → 인증된 사용자 전부
```

빈 department·team 은 **매칭되지 않는다**. 미설정끼리 서로 보이면 사고다.

## 4. 도구

### 4.1 전체 통계 (신규 — 집계만, 개인 식별 없음)

| 도구 | 내용 | 근거로서의 값어치 |
|---|---|---|
| `corpus_summary` | 모델 수·파트/요소 규모 분포·최근 활동 | 조직 규모 감각 |
| `material_usage` | **물성 카드별 사용 모델 수** | 시험 우선순위를 '민감도 추정' → **'실사용 빈도'** 로 |
| `operation_usage` | 오퍼레이션별 실행 횟수·성공률 | 해석 설계의 관행 근거 |
| `report_corpus` | 리포트 종류·케이스 수·findings 심각도 분포 | 어떤 실패모드가 반복되는가 |

집계 대상은 **전 사용자**다(공개 지정과 무관) — 개인을 식별하지 않으므로.
다만 표본이 적으면 오해를 부르니 각 응답에 `n`(모집단 크기)을 함께 낸다.

### 4.2 공개 지정

- `set_session_visibility(session_id, visibility)` — 소유자만 변경 가능.
- 기존 조회 도구(`list_sessions`·`get_session`·`list_session_files`·리포트류)는
  '내 것 + 내가 볼 수 있는 공개 세션' 으로 확장한다.

## 5. 단계

| 단계 | 내용 | 리포 | 상태 |
|---|---|---|---|
| **S1** | 스키마 + 가시성 판정 유틸 + 통계 4종(REST+MCP) | KooRemapper | ✅ `840acec` |
| S2 | 공개 지정 + 기존 조회 확장 | KooRemapper | ✅ `b51de3b` |
| S3 | 심의 스냅샷에 통계 연결 | HWAXAgentServer | ✅ `f22072c` |
| S4 | 개인 시야 배선(포털→에이전트→게이트웨이→DynaForge 사용자별 kr_ PAT) | 4개 리포 | ✅ 아래 |

S1~S3 은 신원 배선 없이 값을 낸다 — 게이트웨이 서비스 계정도 통계는 볼 수 있다.

### S4 결과 (2026-08-17)

| 홉 | 무엇을 했나 | 커밋 |
|---|---|---|
| 선행 | SSO PAT 이름을 클라이언트별로 분리(`X-Heax-Client`) | KooRemapper `8721d56` |
| 포털→에이전트 | 검증된 principal.email 을 `user_email` 로 전달 | HWAXPortal `41f91c5` |
| 에이전트→게이트웨이 | MCP 연결 헤더 `X-HWAX-User` + 에이전트 캐시 키에 신원 포함 | HWAXAgentServer `432c196` |
| 게이트웨이→DynaForge | `per_user_sso` 백엔드는 단발 세션 + 사용자 PAT(캐시·락) | HWAXMcpGateway `ad9bcfb` |

선행 분리가 필요했던 이유 — SSO PAT 이름이 하나뿐이면 심의가 사용자 신원으로 발급하는
순간 그 사람의 웹 세션 토큰이 회수된다(작업 중 실제로 두 번 겪었다).

실측: `list_sessions` 를 신원 없이 / admin / insp 로 → **0 · 10 · 2 건**, DB 와 일치.
발급 불가 시엔 0건이 아니라 `isError`(서비스 계정으로 강등하지 않는다 — 강등하면
'내 모델이 없다'는 틀린 답이 나가고 실패가 정상 응답과 구분되지 않는다).
insp PAT 로 admin 을 사칭한 헤더는 무시(검증된 PAT 의 email 만 싣는다).

## 6. 지켜야 할 것

- `system_capabilities.mcp_tools` 는 소스의 `@mcp.tool(` 카운트로 산출된다 —
  도구를 추가하면 그 값이 자동으로 오른다. 게이트웨이 드리프트 검사가 이 값과
  노출 수를 대조하므로, **MCP 재기동을 빠뜨리면 배포 직후 exit 3 이 뜬다**(정상 동작).
- 통계 도구는 **무인자·읽기 전용**으로 만든다 — mcp-smoke 가 실호출 검사에 쓴다.
- 마이그레이션 기본값은 `private` — 기존 데이터의 노출을 넓히지 않는다.
