# KooRemapper Platform — 상세 개발 계획서

> **목적**: KooRemapper(C++ CLI)의 모든 기능을 (1) FastAPI 백엔드 API로 노출하고,
> (2) MCP로 Claude에서 사용하며, (3) LLM 없이도 쓸 수 있는 React+TS+Vite 프론트엔드를 제공한다.
> 데이터베이스는 Apptainer + PostgreSQL(로컬), 배포는 Apptainer instance 기반.
>
> **절대 원칙**: 기존 C++ SW의 빌드/사용에 **지장을 주지 않는다**. 추가는 전부 *additive*(옵션 플래그, 별도 디렉토리).
>
> 작성일: 2026-06-14 · 상태: **계획(승인 대기)** · 작성자: Claude (Opus 4.8)

---

## 0. TL;DR — 한 장 요약

| 항목 | 결정 |
|---|---|
| **파일 관리 단위** | **세션(프로젝트)** — 업로드한 여러 `.k`/`.dynain`/`.csv`를 한 세션으로 묶어 관리 |
| **op 실행 방식** | **비동기 Job 큐** — `start → poll → fetch`(진행상황/성공여부 가시화) |
| **MCP 도구 입도** | **범용 도구 소수 + 카탈로그** (`list/describe_operation`, `run_operation`, `get_job`, `download_result` 등 ~10개) |
| **DB** | **Apptainer + PostgreSQL 15** (로컬, MXWhitePaper 패턴 차용) |
| **백엔드** | FastAPI + SQLAlchemy(async) + Alembic (ReportArchive 패턴) |
| **토큰** | Personal Access Token (`kr_` 접두사, sha256 해시, 1회 노출) — 대시보드에서 발급 |
| **바이너리 공급** | CMake `POST_BUILD`(옵션 플래그)로 빌드 결과물을 백엔드 `bin/`에 복사 |
| **프론트** | React 18 + TypeScript + Vite + Tailwind + Radix UI (ReportArchive 구조 차용, TS화) |
| **진행 순서** | 본 계획서 승인 → Phase 1~9 단계별 구현 |

---

## 1. 기존 KooRemapper 전체 기능 파악 (현황)

### 1.1 빌드 시스템
- **빌드**: `cmake -DCMAKE_BUILD_TYPE=Release -S . -B build/linux && cmake --build build/linux -j$(nproc)`
- **산출 바이너리**: `build/linux/bin/KooRemapper` (정적 링크, 단독 실행)
- **런타임 데이터**: `material_db.json` 1개 (matdb/battery 등에서 사용) — `dist/materials/material_db.json` (1.27MB)
- **선택 외부 바이너리**: `meshfix`는 `dist/gmsh/gmsh` 서브프로세스 필요, `tetremesh`는 TetGen(빌드 옵션) 사용
- **CMake**: 3.16+, C++17, 기존 `install(TARGETS KooRemapper DESTINATION bin)` 존재
- **third_party**: `tetgen/` (옵션, 기본 OFF: `-DKOOREMAPPER_BUILD_TETGEN=ON`)

### 1.2 CLI 명령 전체 목록 (40개)

> 모두 `src/main.cpp`에서 dispatch, 핸들러는 `src/commands/*.cpp`.
> 입력은 **positional 인자** 또는 **YAML config** (대부분 YAML 안에서 `.k` 파일 경로 참조).

#### A. 코어 메쉬 / 응력 (7)
| op | 용도 | 입력 | 출력 |
|---|---|---|---|
| `map` | flat→bent HEX8 정형 매핑(+prestress 체인) | bent.k, flat.k, out / 또는 config.yaml | mapped .k (+dynain/csv) |
| `shellmap` | QUAD4 쉘 레퍼런스 매핑(비정형 가능) | bent_shell.k, flat_detail.k, out `--thickness` | mapped .k |
| `unfold` | bent→flat (arc-length) | bent.k, out_flat | flat .k |
| `generate` | 예제 메쉬 생성(arc/torus/helix/…) / `box` | type, prefix / box config.yaml | .k들 |
| `generate-var` | 가변밀도/곡선 메쉬 YAML 생성 | config.yaml `--ref --no-scale` | .k |
| `strain` | 변형률 텐서 계산(eng/green/log) | ref.k, def.k, out.csv `--type` | csv |
| `prestress` | 초기응력(*INITIAL_STRESS_SOLID) | ref.k, def.k, out `--E --nu --strain --csv` | dynain/csv |
| `info` | 메쉬 정보 출력 | mesh.k | 콘솔 요약 |
| `extract-surface` | solid→shell 외피 추출 | solid.k, out.k `--pid --face --output-pid --mid-surface` | shell .k |

#### B. 변형 / 사전응력 (8)
| op | 용도 | 핵심 입력 |
|---|---|---|
| `squeeze` | 간섭끼움 압축 + 역인장 prestress | mesh.k, config.yaml(parts eps), prefix |
| `bend` | 굽힘 변형+prestress (formula/dat) | config.yaml(operations bend) |
| `indent` | 인덴트/엠보싱 변형+prestress | config.yaml(operations indent) |
| `formstrain` | 쉘 dihedral 기반 소성변형(*INITIAL_STRAIN_SHELL) | config.yaml |
| `warpage` | 측정 dat/CSV 휨 적용(bilinear) | config.yaml |
| `offset` | 표면→solid 압출(tied/czm/contact) | config.yaml |
| `wrap` | 권선장력 hoop/radial prestress | config.yaml(target_pid, axis, tension) |
| `cnrb2solid` | CNRB 강체볼트→solid 실린더 | config.yaml |

#### C. 메쉬 수정 / 재메쉬 (8)
| op | 용도 |
|---|---|
| `convert` | 2차요소화(tet10/hex20/quad8/tria6) |
| `refine` | 세분화(1:2/1:3 subdivision) |
| `elform` | SECTION ELFORM 변경 |
| `disconnect` | 계면 분리(full/czm/mefem) |
| `iga` | IGA NURBS 박스 임베드(*IGA_DEV_VOLUME_XYZ) |
| `tetremesh` | 국부 TET 재메쉬(localimprove/tetgen) |
| `meshfix` | 전체 파트 TET4 재메쉬(Gmsh 서브프로세스) |
| `matswap` | MAT 번들 원자적 교체(MAT+HG+CURVE+SECTION) |

#### D. 재료 / 감쇠 (3)
| op | 용도 |
|---|---|
| `matdb` | JSON DB에서 *MAT 교체 / `matdb list` |
| `hfdamp` | 고주파 감쇠(*DAMPING_FREQUENCY_RANGE_DEFORM) |
| `optimize` | 재료별 글로벌카드 최적화(rubber 등) |

#### E. 해석 셋업 (7)
| op | 용도 |
|---|---|
| `relax` | Dynamic Relaxation(5단계 프리셋) |
| `explicit` | implicit/DR/modal 제거→순수 explicit |
| `implicit` | explicit→implicit(7단계 프리셋) |
| `modal` | 고유진동(*CONTROL_IMPLICIT_EIGENVALUE) |
| `ale` | ALE 변환(air/water/explosive 프리셋, FSI) |
| `stabilize` | explicit 안정화(12단계 누적 프리셋) |
| `database` | *DATABASE_* 출력제어(프리셋/개별) |

#### F. 하중 / 경계 / 구속 (3)
| op | 용도 |
|---|---|
| `load` | 하중(force/pressure/gravity) |
| `boundary` | 경계조건(SPC/rigidwall) |
| `rbe` | RBE2/RBE3 구속 |

#### G. 모델 조작 / 오케스트레이션 (4)
| op | 용도 |
|---|---|
| `assemble` | 순차 op 파이프라인(replace/squeeze/bend/… 누적 prestress) |
| `merge` | 여러 .k 병합(ID remap) |
| `strip` | 키워드/카드 블록 제거 |
| `restack` | 쉘→적층 solid 압출 |
| `update` | dynain/.k에서 노드좌표 갱신 |
| `contact` | 접촉 분석/생성/변환/제거/탐지 |
| `battery` | 배터리 셀 생성(stacked/wound) |

> **합계 40개 op** (info/extract-surface/matdb-list 등 포함). 입력 형태별 분류:
> - **positional .k 직접**: map, shellmap, unfold, strain, prestress, info, extract-surface, generate
> - **YAML config (안에서 .k 참조)**: 나머지 ~30개 (대부분 `model`/`base_model`/`output` 키)
> - **YAML-only(파일 불필요 가능)**: generate(box), generate-var

### 1.3 문서 자산 (백엔드 op 설명에 재활용)
- `docs/KooRemapper_Manual.md` (38장, 500+ 파라미터) — op별 상세 설명 원천
- `README.md` — 워크플로우 개요
- `examples/*/` 45개 폴더 — op별 실전 예제(YAML+.k+로그) → **예제 카탈로그**로 변환

---

## 2. 목표 아키텍처

```
┌────────────────────────────────────────────────────────────────────┐
│  Claude (Claude Code / Desktop)                                      │
│     │  claude mcp add --transport http kooremapper http://host:PORT  │
│     │     --header "Authorization: Bearer kr_..."                    │
│     ▼                                                                │
│  ┌──────────────────────┐   REST(+PAT 헤더 전달)                    │
│  │ MCP 서버 (FastMCP,    │ ───────────────────────────┐            │
│  │ streamable-http)      │   범용도구 ~10개            │            │
│  │ 별도 venv/프로세스     │                             ▼            │
│  └──────────────────────┘                  ┌────────────────────┐   │
│                                            │  FastAPI 백엔드      │   │
│  ┌──────────────────────┐   REST(JWT/PAT) │  (app/modules/*)    │   │
│  │ React+TS+Vite 프론트   │ ──────────────▶│  - auth/PAT 발급     │   │
│  │ (LLM 없이 op 실행)     │                │  - sessions/files    │   │
│  └──────────────────────┘                  │  - operations(카탈로그)│ │
│                                            │  - jobs(큐/워커)      │   │
│                                            │  - runner(바이너리 실행)│ │
│                                            └─────────┬──────────┘   │
│                                                      │              │
│                          ┌───────────────────────────┼───────────┐ │
│                          ▼                            ▼           │ │
│                  ┌──────────────┐            ┌──────────────────┐ │ │
│                  │ PostgreSQL    │            │ KooRemapper 바이너리│ │ │
│                  │ (Apptainer)   │            │ + materials/ +gmsh │ │ │
│                  │ 메타데이터     │            │ (subprocess 실행)  │ │ │
│                  └──────────────┘            └──────────────────┘ │ │
│                          파일 실물: 호스트 storage/ (bind-mount)    │ │
│                          └──────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### 2.1 디렉토리 레이아웃 (신규, 기존 건드리지 않음)

```
KooRemapper/
├── CMakeLists.txt            # (수정: POST_BUILD 복사 블록 옵션 추가 — 유일한 기존파일 수정)
├── src/ include/ ...         # (그대로)
├── platform/                 # ★ 신규 — 플랫폼 전부 여기에 격리
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py            # pydantic-settings
│   │   │   ├── database.py          # async engine/session
│   │   │   ├── shared/
│   │   │   │   ├── auth.py          # JWT + PAT resolver
│   │   │   │   ├── responses.py     # {success,data,message} 엔벨로프
│   │   │   │   ├── errors.py
│   │   │   │   └── storage.py       # 세션 파일 경로/입출력
│   │   │   ├── runner/
│   │   │   │   ├── binary.py        # KooRemapper 바이너리 subprocess 래퍼
│   │   │   │   ├── catalog.py       # 40개 op 카탈로그(메타+인자스키마)
│   │   │   │   └── argbuild.py      # op+args → CLI argv / YAML 생성
│   │   │   ├── worker/
│   │   │   │   └── runner_loop.py   # job 큐 소비 워커(asyncio)
│   │   │   └── modules/
│   │   │       ├── auth/            # 로그인, JWT 발급
│   │   │       ├── users/           # PAT 발급/조회/취소(kr_)
│   │   │       ├── sessions/        # 세션 CRUD + 파일 업로드/목록/다운로드
│   │   │       ├── operations/      # 카탈로그 조회 API
│   │   │       └── jobs/            # job 생성/상태/결과/로그/취소
│   │   ├── alembic/                 # 마이그레이션
│   │   ├── alembic.ini
│   │   ├── requirements.txt
│   │   ├── bin/                     # ★ CMake POST_BUILD 복사 대상 (gitignore)
│   │   │   ├── KooRemapper          # (빌드시 자동 복사)
│   │   │   └── materials/material_db.json
│   │   └── tests/
│   ├── mcp_server/
│   │   ├── server.py                # FastMCP, streamable-http, PAT 헤더 전달
│   │   ├── requirements.txt
│   │   └── skill/kooremapper/SKILL.md
│   ├── frontend/                    # React + TS + Vite
│   │   ├── src/{modules,shared}/...
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── package.json
│   ├── infra/
│   │   ├── apptainer/
│   │   │   ├── postgres.def         # pgvector/pg15 base 래핑(불필요시 postgres:15)
│   │   │   ├── api.def              # python:3.12-slim + deps
│   │   │   ├── mcp.def              # (또는 api와 공유)
│   │   │   └── web.def              # 빌드된 SPA serve
│   │   ├── scripts/
│   │   │   ├── _common.sh           # .env 로드, 인스턴스명/포트
│   │   │   ├── build.sh             # .sif 빌드/풀
│   │   │   ├── start.sh             # postgres→api→mcp→web 순차 기동
│   │   │   ├── stop.sh / restart.sh
│   │   │   ├── migrate.sh / seed.sh
│   │   │   └── reset-db.sh
│   │   └── data/                    # postgres 데이터(bind-mount, gitignore)
│   ├── storage/                     # 세션 파일 실물(bind-mount, gitignore)
│   ├── .env.example
│   └── README.md
```

> **기존 파일 수정은 `CMakeLists.txt` 끝의 옵션 블록 1곳뿐.** 나머지는 전부 `platform/` 신규.
> `.gitignore`에 `platform/backend/bin/`, `platform/infra/data/`, `platform/storage/` 추가.

---

## 3. 데이터 모델 (PostgreSQL)

> 세션 단위 파일 관리 + 비동기 Job + PAT.

```
users
  id PK, email UNIQUE, password_hash, display_name,
  is_active, is_system_admin, created_at

personal_access_tokens          # MCP/외부 클라이언트용 (kr_ 접두사)
  id PK, user_id FK,
  name, token_prefix(표시용 kr_+8자), token_hash(sha256 UNIQUE),
  created_at, expires_at(NULL=무기한), last_used_at, revoked_at

sessions                        # "프로젝트" = 업로드 K파일 묶음
  id PK(ulid), user_id FK,
  name, description,
  created_at, updated_at,
  storage_path(상대경로),       # storage/{user}/{session}/
  status(active|archived)

session_files                   # 세션 안의 개별 파일(.k/.dynain/.csv/...)
  id PK, session_id FK,
  filename, rel_path,           # 세션 storage 내 상대경로
  kind(input|output|generated),
  origin_job_id FK NULL,        # output이면 어느 job 산출물인지
  size_bytes, sha256,
  meta JSONB,                   # info op 캐시: node/elem 수, parts, bbox, *INCLUDE 목록
  created_at

jobs                            # op 실행 단위
  id PK(ulid), session_id FK, user_id FK,
  operation(varchar),           # 'map','shellmap',...
  args JSONB,                   # 사용자 입력 인자(정규화 전)
  resolved_cmd JSONB,           # 실제 argv + 생성 YAML(감사/재현용)
  status(queued|running|succeeded|failed|canceled),
  progress SMALLINT,            # 0~100(가능한 op만, 아니면 NULL)
  exit_code INT NULL,
  stdout_path, stderr_path,     # 로그 파일 경로(스트리밍/다운로드)
  input_file_ids JSONB,         # 입력으로 쓴 session_file id들
  output_file_ids JSONB,        # 산출 등록된 session_file id들
  error_summary TEXT NULL,
  created_at, started_at, finished_at
```

- **파일 실물**: `platform/storage/{user_id}/{session_id}/...` (DB엔 메타만)
- **다운로드**: `session_files`의 output kind를 Claude/프론트에서 받아감
- **`*INCLUDE` 인지**: 업로드/생성 시 `info`로 파싱해 `session_files.meta`에 내부 파일·파트 목록 저장 → "안에 어떤 파일이 들어있는지 조회" 요구 충족

---

## 4. 백엔드 API 설계 (REST)

> 응답 엔벨로프 `{success, data, message, errors}` (ReportArchive 패턴).
> 인증: `Authorization: Bearer <JWT 또는 kr_PAT>`. JWT는 프론트, PAT는 MCP.
> prefix `/api/v1`.

### 4.1 인증 / 토큰
| Method | Path | 설명 |
|---|---|---|
| POST | `/auth/login` | email/pw → JWT(access) |
| GET | `/me` | 현재 사용자 |
| GET | `/me/tokens` | 내 PAT 목록(상태 포함) |
| POST | `/me/tokens` | PAT 발급 → **평문 1회 노출** + `claude mcp add` 스니펫 |
| DELETE | `/me/tokens/{id}` | PAT 취소 |

### 4.2 세션 / 파일
| Method | Path | 설명 |
|---|---|---|
| GET | `/sessions` | 내 세션 목록 |
| POST | `/sessions` | 세션 생성(name/desc) |
| GET | `/sessions/{id}` | 세션 상세 + 파일 목록 |
| PATCH | `/sessions/{id}` | 이름/상태 변경 |
| DELETE | `/sessions/{id}` | 세션 삭제(파일 포함) |
| POST | `/sessions/{id}/files` | 파일 업로드(multipart, 다중 가능) → `info` 자동 파싱 |
| GET | `/sessions/{id}/files` | 파일 목록(kind/meta 포함) |
| GET | `/sessions/{id}/files/{fid}` | 파일 메타 |
| GET | `/sessions/{id}/files/{fid}/download` | 파일 다운로드 |
| GET | `/sessions/{id}/files/{fid}/inspect` | 내부 파일/파트/`*INCLUDE`/bbox 조회(캐시된 meta) |
| DELETE | `/sessions/{id}/files/{fid}` | 파일 삭제 |

### 4.3 op 카탈로그
| Method | Path | 설명 |
|---|---|---|
| GET | `/operations` | 40개 op 요약(name, category, summary, takes_kfile) |
| GET | `/operations/{op}` | op 상세: 인자 스키마(JSON Schema), 입출력, 예제 YAML, 매뉴얼 발췌 |

> 카탈로그 원천 = `runner/catalog.py`의 정적 정의 + `docs/KooRemapper_Manual.md`/`examples/` 발췌.
> 각 op은 **JSON Schema**로 인자를 기술 → 프론트는 자동 폼 생성, MCP는 LLM에 스키마 제공.

### 4.4 Job (비동기 실행)
| Method | Path | 설명 |
|---|---|---|
| POST | `/sessions/{id}/jobs` | op 실행 요청 `{operation, args}` → job 생성(queued), job_id 반환 |
| GET | `/jobs/{jid}` | job 상태/진행/exit_code/요약 |
| GET | `/jobs/{jid}/logs` | stdout/stderr (tail/stream, `?follow=1` SSE) |
| GET | `/jobs/{jid}/outputs` | 산출 파일 목록(session_files) |
| POST | `/jobs/{jid}/cancel` | 실행 취소(워커 SIGTERM) |
| GET | `/sessions/{id}/jobs` | 세션의 job 히스토리 |

### 4.5 실행 파이프라인 (runner)
1. `POST jobs` → `args`를 `catalog`의 JSON Schema로 **검증** → `jobs(queued)` insert.
2. 워커(`worker/runner_loop.py`)가 queued를 집어 `running` 전환.
3. `argbuild.py`: op에 따라
   - positional op → `argv = [bin, op, file1, file2, out, ...flags]`
   - YAML op → 세션 파일 경로를 채운 임시 `config.yaml` 생성 → `argv = [bin, op, config.yaml]`
4. `binary.py`: `subprocess` 실행, cwd=세션 storage, stdout/stderr 파일로, 타임아웃, SIGTERM 취소 지원.
   - `meshfix`는 `bin/gmsh` 필요 → 없으면 명확한 에러.
5. 종료 후 세션 storage의 **새 파일**(out.k, *.dynain, *.csv 등)을 `session_files(output)`로 등록 + `info` 파싱.
6. `jobs(succeeded|failed)` + exit_code + 산출 file_ids 기록.
7. **진행률**: KooRemapper stdout의 진행 로그를 정규식으로 파싱해 `progress` 갱신(가능한 op만; 불가하면 NULL 유지).

> **동시성**: 워커 N개(설정), CPU 바운드라 기본 `min(4, cores-1)`. 큐는 DB `status=queued` 폴링(단순·견고) 또는 `asyncio.Queue`.

---

## 5. MCP 서버 설계 (FastMCP, streamable-http)

> ReportArchive `mcp_server/server.py` 패턴: **별도 venv·프로세스**, REST로만 통신, PAT 헤더 전달.
> 등록: `claude mcp add --transport http kooremapper http://<host>:PORT/mcp --header "Authorization: Bearer kr_..."`

### 5.1 도구 (범용 ~10개 + 카탈로그)
| 도구 | 설명 |
|---|---|
| `list_operations()` | 40개 op 요약(카테고리/요약/입력유형). 무엇을 할 수 있나 먼저 조회 |
| `describe_operation(op)` | op 인자 JSON Schema + 입출력 + 예제. `run_operation` 전 호출 |
| `list_sessions()` | 내 세션 목록 |
| `create_session(name, description?)` | 새 세션 생성 |
| `upload_kfile(session_id, ...)` | 파일 업로드(경로/내용). **"K파일 전송"** 충족 |
| `list_session_files(session_id)` | 세션 내 파일 + 내부 *INCLUDE/파트/bbox. **"안에 뭐 들었는지 조회"** 충족 |
| `inspect_file(session_id, file_id)` | 단일 파일 상세(info 결과) |
| `run_operation(session_id, operation, args)` | op 실행 → job_id. **"오퍼레이션 적용"** 충족 |
| `get_job(job_id)` | 상태/진행/로그요약 폴링 |
| `download_result(job_id 또는 file_id)` | 산출물 내용/링크 반환. **"변경된 파일 다시 가져오기"** 충족 |

> 스마트 로직(검증/argv 생성/실행)은 전부 백엔드에 있고 MCP는 thin proxy.
> DNS rebinding 보호: 비-localhost 바인딩이면 `MCP_ALLOWED_HOSTS`로 제어(ReportArchive 패턴).

### 5.2 Agent Skill (`skill/kooremapper/SKILL.md`)
- op 선택 가이드, 워크플로(세션 생성→업로드→describe→run→poll→download), 자주 틀리는 인자, 재시도 노하우.
- 설치: `cp -r skill/kooremapper ~/.claude/skills/`.

---

## 6. 프론트엔드 설계 (React + TS + Vite) — UX 극상

> ReportArchive 구조(modules/shared, axios 클라이언트, Radix UI, Tailwind, useAsync) 차용 + **TypeScript화**.
> 상태관리: Context(Auth/Theme) + **TanStack Query**(job 폴링·캐시에 적합).

### 6.1 화면 구성
| 화면 | 내용 / UX 포인트 |
|---|---|
| **Login** | JWT 로그인 |
| **Dashboard** | 최근 세션·job 카드, 실행중 job 진행바, 성공/실패 통계 |
| **Sessions** | 세션 목록/생성/검색 |
| **Session Detail** | ① **파일 패널**(업로드 드래그앤드롭, 파일별 info 칩: node/elem/parts/bbox/*INCLUDE 트리) ② **Operation 패널**(카탈로그에서 op 선택 → **JSON Schema 자동 폼**, 파일 선택 드롭다운, 예제 YAML 미리채움) ③ **Job 패널**(히스토리, 실시간 진행바, 로그 스트림 뷰어, 산출물 다운로드/세션 재투입) |
| **Operation Catalog** | 40개 op 브라우저(카테고리 필터, 검색, 매뉴얼 발췌, 예제) — "뭘 하는 기능인지" 학습 |
| **MCP 토큰** (설정) | **토큰 발급 버튼 → 평문 1회 모달 + 복사 + `claude mcp add` 스니펫 자동완성**, 토큰 목록(상태/마지막사용/취소) |
| **Settings** | 테마(다크/라이트), 워커/타임아웃 등 표시 |

### 6.2 UX 디테일 (요구: "뭘 하는 기능인지 잘되어있는지 아닌지 볼 수 있게")
- **op 자동 폼**: JSON Schema → 라벨/툴팁/기본값/검증 메시지 인라인. 필수/선택 구분, enum은 셀렉트, 파일 인자는 세션 파일 드롭다운.
- **실행 가시화**: queued/running/succeeded/failed 색상 배지 + 진행바 + 경과시간 + exit_code + 실패 시 stderr 하이라이트.
- **로그 뷰어**: SSE follow, 자동스크롤 토글, 에러 줄 강조.
- **파일 인스펙터**: `*INCLUDE` 트리, 파트 테이블(pid/elem수/타입), bbox, "이 파일을 op 입력으로" 바로가기.
- **비교**: 입력 vs 산출 파일 메타 diff(노드/요소/파트 변화).
- **Empty/Error/Loading** 표준 상태, 토스트, ErrorBoundary(라우트별), 커맨드 팔레트(cmd+k).
- **반응형** + 접근성(Radix 기반).

### 6.3 API 클라이언트
- `src/shared/api/client.ts`: axios 인스턴스 + JWT 인터셉터 + 엔벨로프 unwrap + 401 핸들.
- 리소스별 모듈: `auth.ts, sessions.ts, files.ts, operations.ts, jobs.ts, tokens.ts` (타입 정의 포함).

---

## 7. 배포 (Apptainer + PostgreSQL) — MXWhitePaper 패턴

### 7.1 인스턴스 구성
| instance | .sif | 역할 | 포트(.env) |
|---|---|---|---|
| `koorm_postgres` | postgres.def(pg15) | 메타 DB | `5433`(충돌 회피) |
| `koorm_api` | api.def(py3.12-slim) | FastAPI + 워커 | `8700` |
| `koorm_mcp` | mcp.def(또는 api 공유) | MCP streamable-http | `8701` |
| `koorm_web` | web.def(serve dist) | SPA | `5273` |

- **postgres.def**: `Bootstrap: docker / From: postgres:15`(또는 pgvector 불필요) + `%startscript exec docker-entrypoint.sh postgres`. 데이터·소켓 bind-mount, `PGDATA`/`POSTGRES_*` env, `shared_memory_type=mmap` 패치(rootless 안정).
- **api.def**: python:3.12-slim + `fastapi uvicorn sqlalchemy[asyncio] asyncpg alembic pydantic pydantic-settings python-jose argon2-cffi python-multipart`. 소스는 `/workspace` bind-mount. **`platform/backend/bin/`도 컨테이너에서 보이도록 bind** → 바이너리 실행.
- **start.sh**: postgres 기동→`pg_isready` 대기→migrate→api→mcp→web. (MXWhitePaper start.sh의 stale-lock/mmap 패치 로직 차용)
- `.env`: `POSTGRES_*`, `DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:5433/koorm`, `JWT_SECRET`, `API_PORT`, `MCP_PORT`, `KOOREMAPPER_BIN=/workspace/platform/backend/bin/KooRemapper`, `STORAGE_DIR`, `CORS_ORIGINS`.

### 7.2 바이너리 공급 (요구: "빌드될 때마다 백엔드에 복사")
`CMakeLists.txt` 끝에 **옵션 블록** 추가(기존 빌드 무영향):
```cmake
# --- Platform backend integration (opt-in; zero impact when unset) ---
set(KOOREMAPPER_PLATFORM_BIN "" CACHE PATH "Copy built binary+materials here for the FastAPI backend")
if(KOOREMAPPER_PLATFORM_BIN)
  add_custom_command(TARGET KooRemapper POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:KooRemapper> "${KOOREMAPPER_PLATFORM_BIN}/$<TARGET_FILE_NAME:KooRemapper>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_SOURCE_DIR}/dist/materials" "${KOOREMAPPER_PLATFORM_BIN}/materials"
    COMMENT "Copying KooRemapper → platform backend bin")
endif()
```
- 사용: `cmake -DKOOREMAPPER_PLATFORM_BIN=$PWD/platform/backend/bin -S . -B build/linux && cmake --build build/linux`
- 플래그 미지정 시 **완전 무동작** → 기존 빌드/CI 그대로.
- 편의 스크립트 `platform/infra/scripts/sync-binary.sh`(이미 빌드된 결과를 수동 복사하는 대안)도 제공.

---

## 8. 단계별 구현 계획 (Phase)

> 각 Phase는 **검증 기준**을 가진다(목표지향 실행).

### Phase 0 — 스캐폴딩 & 무영향 확인
- `platform/` 디렉토리, `.gitignore` 갱신, `CMakeLists.txt` 옵션 블록 추가.
- **검증**: `cmake ... && cmake --build`(플래그 없이) → 기존과 동일 산출, 바이너리 정상. 플래그 지정 시 `platform/backend/bin/KooRemapper` 생성.

### Phase 1 — Apptainer Postgres + 백엔드 뼈대
- postgres.def/api.def, `_common.sh/build.sh/start.sh`, `.env.example`.
- FastAPI `main.py`+`config.py`+`database.py`+엔벨로프, `/health`.
- Alembic init + users/PAT/sessions/files/jobs 테이블 마이그레이션, seed(admin 1명).
- **검증**: `start.sh`로 postgres+api 기동, `GET /health` 200, `alembic upgrade head` 성공.

### Phase 2 — 인증 & PAT
- 로그인(JWT), `/me`, PAT 발급/조회/취소(`kr_`, sha256, 1회 노출), auth resolver(JWT|PAT prefix 구분).
- **검증**: 로그인→JWT로 `/me`; PAT 발급→그 PAT로 `/me` 통과; 취소 후 401.

### Phase 3 — 세션 & 파일 + info 파싱
- 세션 CRUD, 파일 업로드(multipart 다중)/목록/다운로드/삭제, storage 레이아웃.
- 업로드 시 `KooRemapper info` 실행해 meta(노드/요소/파트/bbox/*INCLUDE) 캐시 → `inspect`.
- **검증**: .k 업로드→파일 목록에 meta 표시, 다운로드 바이트 일치, `*INCLUDE` 포함 파일 내부목록 노출.

### Phase 4 — op 카탈로그 (40개)
- `runner/catalog.py`: 40개 op 각각 {name, category, summary, takes_kfile, args JSON Schema, io, example, manual 발췌}.
- `/operations`, `/operations/{op}`.
- **검증**: 40개 전부 조회, 스키마 유효(JSON Schema 검증), 예제 YAML 파싱 OK.

### Phase 5 — Job 큐 & runner (핵심)
- `argbuild.py`(positional/YAML 분기), `binary.py`(subprocess/타임아웃/취소/로그), `worker/runner_loop.py`.
- Job API 전체, 산출물 자동 등록, 진행률 파싱.
- **검증**: 대표 op들 end-to-end —
  - `info`(즉시), `generate`(파일 생성), `map`(arc30 예제), `unfold`, `prestress`(dynain), `matdb list`, `merge`, `assemble`(파이프라인), `meshfix`(gmsh 존재 시).
  - 각 job succeeded + 산출물이 세션에 등록 + 재다운로드.
  - 일부러 잘못된 인자 → failed + stderr 노출. 취소 동작.

### Phase 6 — 전 op 통합 테스트
- `examples/*` 폴더를 골든 케이스로 자동 검증(op별 최소 1개).
- **검증**: 40개 op 각 1개 이상 케이스 succeeded. 실패 op는 원인 문서화.

### Phase 7 — MCP 서버
- FastMCP streamable-http, 10개 범용 도구, PAT 헤더 전달, SKILL.md.
- `claude mcp add`로 등록 → Claude에서 세션 생성→업로드→describe→run→poll→download 시연.
- **검증**: 실제 Claude Code 등록 후 한 사이클 성공. 토큰 취소 시 거부.

### Phase 8 — 프론트엔드
- Vite+TS 스캐폴딩, 디자인시스템(ui 프리미티브), Auth/Theme, TanStack Query, API 클라이언트.
- 화면: Login/Dashboard/Sessions/Session Detail(파일·op·job 패널)/Catalog/토큰/Settings.
- **검증**: LLM 없이 브라우저에서 업로드→op 자동폼 실행→진행바/로그→산출물 다운로드. 토큰 발급 모달+스니펫. Playwright 스모크.

### Phase 9 — web.def 배포 & 문서
- web.def(빌드 dist serve), start.sh에 web 추가, nginx 예시(옵션), README/운영 문서.
- **검증**: 4개 인스턴스 기동, 브라우저 접속, MCP 동시 동작, 재부팅 후 stale-lock 복구.

---

## 9. 리스크 & 대응
| 리스크 | 대응 |
|---|---|
| `meshfix` gmsh 의존 | `bin/gmsh` 동봉 또는 미존재 시 명확한 에러+가이드. op 메타에 `requires_gmsh` 표기 |
| YAML op의 파일경로 매핑 복잡 | `argbuild.py`에서 세션 파일 id→실제 경로 치환, op별 단위테스트 |
| 대형 메쉬 메모리/시간 | 비동기 Job + 타임아웃 + 동시성 제한 + 진행바 |
| MCP↔FastAPI 의존성 충돌 | **별도 venv/프로세스**(ReportArchive 검증된 분리) |
| rootless postgres /dev/shm | `shared_memory_type=mmap` 패치(MXWhitePaper 검증) |
| 기존 빌드 영향 | POST_BUILD 옵션 플래그(기본 무동작) + 모든 신규는 `platform/` 격리 |
| 포트 충돌 | 비표준 포트(5433/8700/8701/5273), .env로 조정 |
| 보안(임의 파일경로/명령주입) | argv 화이트리스트(op는 enum), 경로는 세션 storage로 sandbox, 사용자 입력은 인자값만 |

## 10. 미해결/추후 결정 (구현 중 확인)
- 멀티유저 범위: 초기엔 단일/소수 사용자(시스템 admin seed) 가정, 조직/권한 트리는 후순위.
- 파일 보존정책(용량 한도, 오래된 세션 GC) — Phase 9 이후.
- gmsh 바이너리 동봉 여부(라이선스/용량).
- 진행률을 지원할 op 범위(stdout 패턴 확보된 op부터).

---

## 11. 요구사항 → 설계 매핑 (체크)
- ✅ "모든 기능을 백엔드 API로" → §4 (40 op = 카탈로그 + 단일 Job 실행 엔드포인트)
- ✅ "기존 빌드 그대로, 빌드 시 백엔드로 복사" → §7.2 POST_BUILD 옵션
- ✅ "바이너리를 argument와 함께 실행" → §4.5 runner(argbuild+binary)
- ✅ "각 역할 잘 설명 + MCP" → §4.3 카탈로그(JSON Schema+매뉴얼), §5 MCP
- ✅ "대시보드에서 토큰 발급 간단히" → §4.1, §6.1 MCP 토큰 화면(1회 노출+스니펫)
- ✅ "K파일 전송 + 내부 파일 조회/관리" → §3 sessions/files, §4.2 inspect, §5 upload/list/inspect
- ✅ "적용한 op 결과 다시 가져오기(다운로드)" → §4.2 download, §4.4 outputs, §5 download_result
- ✅ "ReportArchive MCP 참조" → §5(server.py 패턴), §4.1(PAT 패턴)
- ✅ "DB는 Apptainer + 로컬 PostgreSQL, MXWhitePaper 참조" → §7
- ✅ "LLM 없이 쓰는 React+TS+Vite, UX 극상" → §6
- ✅ "기준 코드 빌드/사용 무영향" → §2.1, §7.2, §9
```
