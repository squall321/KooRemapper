# StandardPlatform 을 받아 DynaForge 를 보강하는 계획 — 과제 정보 수신 · 온톨로지 · 개정

> 상태 — **계획(확정 전)**. 2026-10-14. 사람이 정할 것(§7)이 정해지면 단계마다 번호를 붙여 진행한다.
> 받은 것 — `vendor/StandardPlatform`(GitHub `4leaf321-nox321/StandardPlatform` · 커밋 `f7485c0` ·
> 버전 0.4.52 · 얕은 클론 916파일 18MB). 추적하지 않는다(§7 ①).
> 조사 — **읽기만 했다**(코드 실행 0 · 그 리포 안의 URL 접속 0).
>
> ★**StepForge 와 결을 맞춘다.** StepForge 가 같은 요청으로 먼저 계획을 세웠다
> (`StepForge/docs/STANDARD_PLATFORM.md` · 커밋 `bea7485`, D-525). 그 문서의 짜임새 · 용어 ·
> 수신 규칙 · 저장 표 꼴 · 단계 번호(S0~S6)를 **그대로 따른다.** 두 쌍둥이가 같은 허브에서 같은
> 것을 받는데 설계가 갈리면, 갈린 쪽은 한쪽만 고쳐진다.

## 0. 요청

1. SP 를 하위 디렉터리로 받는다.
2. **과제 정보를 받아오는 부분**과 **온톨로지 부분**을 DynaForge 에 심는다.
3. DynaForge **자체 온톨로지**로 **같은 과제라도 개정(revision) 정보**를 갖게 한다.
4. SP 전체를 읽고 우리 플랫폼을 보강할 길을 정한다.

## 1. 조사 요약 — 실측

### 1-1. SP 는 도메인이 빈 공통 틀이다

FastAPI + SQLAlchemy + **PostgreSQL 필수** + React. 도메인은 **온톨로지 메타모델**(타입·속성·
관계를 데이터로 정의)로 얹는다. 이미 다섯이 이 틀로 섰다 — MatNexus(8010/11/12) ·
TestScope(8020/21/22) · StandardPlatform(8040/41/42) · AutoJigGenerator(8060~) · SimEngBay(8070~).
MCP 서버는 별도 프로세스이고 백엔드를 **REST 로만** 부른다(`mcp_server/server.py:44` 의
`PLATFORM_API_BASE`) — DynaForge MCP 와 같은 짜임새다.

### 1-2. 온톨로지 엔진은 통째로 옮길 수 없다

| | 백엔드 py | 프런트 tsx |
|---|---|---|
| `ontology` | 11,222 | — |
| `objects` | 22,958 | — |
| `modules/ontology`+`modules/objects` | — | 22,158 (97 파일) |
| **합** | **34,180** | **22,158** |

바깥 의존(실측) — `accounts.models`(31회) · `shared.errors`(29) · `shared.permissions`(20) ·
`shared.batches`(10) · `workspaces.models`(6) · `metrics`·`files`·`jobs`·`datasources`·`audit`·
`review` + `shared` 11개. **온톨로지가 부서 소유를 전제로 짜여 있는데**
(`visible_owner_clause`·`require_owner_edit`) **DynaForge 에는 부서가 없다.**

→ StepForge 와 같은 결론이다. **엔진이 아니라 꼴을 가져온다.**

### 1-3. SP 에 개정 모델링은 **없다**

객체 한 줄이 곧 현재 상태다. SP 의 규칙은 "고친 판은 새 문서 — 이전 판의 key 를 메모에 적는다" 다.
데이터 안의 개정은 `plm_model.model_revision`(모델명에서 자른 조각 · `model_revision_kind` =
OS 버전·차수·기호) 정도다. 시간 축은 **연도**뿐이다(`temporal_kind` evergreen\|lifecycle\|
yearly\|derived, 필터가 `year=Y`). **개정 축은 우리가 만드는 것이다.**

### 1-4. 과제는 온톨로지 타입 `plm_task` 다

정본 — `pipeline/core/plm-core.json`(실측: `groups`·`types`·`relation_types`).

| 타입 | key | 비고 |
|---|---|---|
| `plm_project` 프로젝트 | 필수 | |
| `plm_task` **과제** | **과제명**(= plm_task.key) · 과제코드는 `properties.task_code` | `project`(→`plm_project`, 필수) · `task_status` · `sra_on` · `sra_kind` · `test_site` · `test_kind` · `test_plan_status` |
| `plm_model` 개발모델 | 모델명 원문 | `task`(→`plm_task`, 필수) · 모델명 해석(`region`·**`model_revision`**·`carrier` …) |
| `plm_test_site` 시험 주체 | 필수 | |
| 관계 `plm_derived_from` | 파생 모델 → 원 모델 | many_to_one · 순환 금지 |

> ⚠ **cae00 10-27 실측 — 위 표의 일부는 허브 공개 목록에 없다(KR-12).** key 는 **과제명**이고
> 과제코드는 `properties.task_code` 다(KR-01 — 예전 표의 「key=과제코드」는 틀렸다). 그리고 허브에는
> `plm_test_site` · `model_revision_kind` · `base_code` · `series` · `plm_derived_from` 이 **없었다**.
> `model_revision_kind` 대신 쓸 칸(예 `model_kind`·`rc_marker`)과 `plm_test_site` 취급(목록에서 빼기 vs
> '허브에 없음' 표시)은 **허브 공개 필드 확인 뒤 정한다** — 짐작으로 코드에 박지 않는다(미결, 요청서 §3 K-4).

담당 부서·담당자·참여는 칸이 아니라 **관계**다(`work-core.json` 의 `dept_in_charge`·
`responsible`·`participates`).

### 1-5. ★받아오는 길은 **허브 코어 API** 다 — 이전 판의 제 기술을 고친다

저장소에 PLM 실시간 커넥터는 **없다.** 길은 둘로 나뉜다.

① **허브** 설치가 PLM 표(CSV/Excel·OData)를 받아 둔다(`sp_table.py` → 묶음 가져오기, 또는 범용
데이터 소스 `datasources/`).
② **다른 설치(쌍둥이)는 허브의 코어 API 로 증분을 받는다.**

실측한 계약(`backend/app/modules/coreapi/`) —

```
GET /api/core                      → CoreCatalogOut {system, revision, as_of, types[]}
GET /api/core/{type}?since=&cursor= → CorePageOut   {type_slug, as_of, since, next, items[]}
GET /api/core/{type}/relations      → CoreRelationPageOut
토큰 범위 core:read
```

`CoreRowOut` 봉투는 **고정**이다 — `key` · `label` · `status`(active\|deprecated) · `updated_at` ·
`deleted` · `hidden` · `merged_into` · `renamed_from`.

★**받는 쪽 키트가 이미 있다** — `backend/app/modules/coreapi/kit/sp_core_pull.py`(실측 436줄,
`requests`+`sqlite3`+표준 라이브러리만, 증분·`next`·`reset`·삭제·`hidden` 처리 포함).
그리고 **수신 규칙 열하나**(`docs/외부-시스템-연동-지침서.md` §4.2 — 머리 186행 「길 ① 코어 API
— **주기 동기화는 이 길이다**」 · 받는 쪽 반복문 294행 · 규칙 **311~343행**, 11개 전부 실측) —

1. `as_of` 를 **그대로** 되돌려 준다(받는 쪽 시계를 쓰면 몇 초 차이로 행이 샌다)
2. **`next` 가 있으면 `as_of` 는 `null`** 이다 — 끝까지 받은 뒤에만 시계를 옮긴다
3. `key` 를 저장한다 — 안 하면 다음 동기화가 「고침」 이 아니라 「새로 만들기」 가 된다
4. `deleted` 를 처리한다(지우지 말고 비활성) · `merged_into` 가 있으면 참조를 옮긴다
5. **모르는 칸은 무시한다** — 허브가 칸을 늘려도 우리가 안 깨지는 이유
6. 같은 행이 **두 번** 올 수 있다(덮어쓰면 해가 없다)
7. `since` 없이 받으면 지워진 것은 **안 온다** → 재적재의 **부재 대조**가 필요하다
8. 지워졌던 것이 **되살아날** 수 있다(`deleted: false` 로 다시 오면 되살린다)
9. 합쳐진 쪽의 선은 「끊긴 선」 으로 오지 않는다 — 합치기가 선을 이긴 쪽으로 **옮긴다**
10. 참조 칸의 값은 **보낼 때의 `key`** 다(나중에 바뀌어도 이미 받은 참조는 옛 값)
11. **404 는 두 가지다** — `APP-CORE-0001`(공개 안 된 타입 → 그 타입 수신을 멈추고 알린다)과 그 외

> ⚠ **이전 판에서 제가 틀리게 적었다.** "받기는 묶음 가져오기에 `source` 를 적어서만 한다" 고
> 썼는데, 그것은 `managed.py` 머리말이 **허브 쪽**에서 하는 일을 말한 것이다. 쌍둥이가 받는 길은
> **코어 API** 이고 키트와 규칙이 이미 있다. `coreapi` 모듈을 안 보고 쓴 탓이다.

### 1-6. 쌍둥이는 받은 것을 **고칠 수 없다**

`managed_by`(String(40))가 `object_types`·`relation_types`·`object_interfaces` 에 있고
(`ontology/models.py:258`·`:344`·`:503`), 내 `source` 와 다르면
`objects/routes.py:2268` 이 **만들기까지 거절**한다(고치기 `:1531`·`:2327` · 지우기 `:1645` ·
별칭 `:2397` · 되돌리기 `:2700`). 막지 않는 것은 「이 설치의 관계가 그 객체를 **가리키는 것**」
하나다 — **DynaForge 가 설 자리가 거기다.**

### 1-7. ★DynaForge 쪽 — **이미 과제와 개정이 있다**(StepForge 와 다른 점)

StepForge 의 과제 표 `code` 는 "자유 텍스트이고 무엇과도 이어지지 않는다" 였다.
DynaForge 는 그보다 멀리 가 있다 — `ImpactReport.eng_meta`(JSONB, `app/models.py:162`) —

```
{project: str,
 dev_revision: {phase: pre|dv|pv|pra|mp, round?: 1|2|3|r, code: str},
 design_variation?: str,
 doe?: {study, case?}}
```

- 형식 검증이 **이미 있다** — `_STAGE_RE = (pre|dv|pv|pra|mp)([123r])?`,
  dv/pv 는 차수 필수, pre/pra/mp 는 금지(`app/reports/datahub.py:31`·`:38`)
- 생성은 `build_eng_meta()` 한자리(`modules/reports/services.py:92`)
- 필터·패싯·세기가 이미 붙어 있다(`services.py:826-910`)
- `eng_meta.project` 가 비면 리포트에 박힌 `project_name` 으로 **폴백**(`:232`)
- DataHub 등재가 **같은 모양**을 쓴다(`reports/datahub.py:89`·`:179`)

**그래서 빈 곳은 과제·개정이 아니다** — 셋이다.

| 빈 곳 | 지금 | 결과 |
|---|---|---|
| 정체성 | `project` 가 자유 문자열 | 오타 하나가 같은 과제를 둘로 쪼갠다. 정본 목록이 없다 |
| 관계 | 없음 | "이 과제의 개발모델은" · "같은 개정의 리포트는" 을 못 묻는다 |
| 플랫폼 간 동일성 | 각자 문자열 | DataHub·RA·SP·StepForge 가 같은 과제를 다른 말로 부른다 |

## 2. 원칙 — 무엇을 가져오고 무엇을 안 가져오나 (StepForge §2 와 같은 줄)

| 가져온다 | 꼴 | 이유 |
|---|---|---|
| 코어 API **수신 키트**와 **수신 규칙 열하나** | DynaForge 는 Postgres + httpx 다 — `requests`/`sqlite3` 를 **httpx + SQLAlchemy** 로 옮긴다(첫 줄에 출처 주석) | 증분·삭제·reset·개명 처리가 이미 실측으로 다듬어져 있다 |
| **정의의 꼴**(SP import JSON — `groups`·`types`·`relation_types`·`property_defs` 값 종류·카디널리티) | DynaForge 정의 파일의 형식으로 쓴다 · 작은 검증기만 새로 짓는다 | 허브의 `plm-core` 를 그대로 읽고, 우리 정의를 허브가 읽을 수 있게 |
| 허브가 공개하는 **plm-core 정의와 객체**(과제·모델·프로젝트·시험주체·관계) | **읽기 전용 거울**(`source=hub`) | 과제 정보의 정본은 허브다 — DynaForge 는 고치지 않는다 |
| 별칭·「채울 곳」 착상 | 필요한 것만 | 자유 문자열 `project` 를 정본에 붙이는 일이 바로 그 문제다(ADR 0025) |

| 안 가져온다 | 이유 |
|---|---|
| 온톨로지 **엔진 코드**(모델·서비스·bulk·RDF·인터페이스·지표) | 부서·계정·감사·파일·작업 모듈에 깊게 묶여 있다. **꼴만 맞추고 엔진은 작게 다시 짓는다** |
| 인증·계정·부서·권한·공지·프런트엔드 | DynaForge 는 HEAX 게이트웨이 forward_auth 뒤에 있고 신원을 헤더로 받는다([[heax-sso]]) |
| 작업 워커·웹훅·지표 모듈 | DynaForge 에 워커·잡·리포트가 이미 있다. 착상만 본다 |
| HWAX 포털 SSO·게이트웨이 위임 | 위와 같다 — 게이트웨이가 이미 해 준다 |

**하위 디렉터리는 실행 경로 밖이다** — `vendor/StandardPlatform` 은 읽는 참고본이고 DynaForge
런타임은 거기서 import 하지 않는다. 옮긴 코드는 DynaForge 안의 파일이 되고 첫 줄에 출처
(`StandardPlatform <경로>@f7485c0`)를 적는다.

## 2-b. 규격을 전체 플랫폼과 맞춘다 — **Postgres**

★2026-10-14 사용자 지시. 처음 판에서 저는 저장소를 「맞추면 안 되는 것」 에 넣었다 —
StepForge 의 SQLite 를 **주어진 것**으로 놓은 탓이다. 그것 자체가 선택이었다.

### 왜 맞춰야 하나

| | 저장소 |
|---|---|
| StandardPlatform | **PostgreSQL 필수** |
| 그 포크 넷(MatNexus·TestScope·AutoJig·SimEngBay) | Postgres |
| DynaForge | Postgres (5436) |
| StepForge | **SQLite** ← 혼자 다르다 |

그리고 **StepForge 자기 계획서가 이미 그렇게 적어 뒀다** —
`StepForge/docs/PLAN.md:51` `| DB | SQLite(WAL) → **필요 시 PG** | 초기 규모에 충분 |`.
PG 는 처음부터 예정된 종착지였고, **규격을 맞출 필요가 생긴 지금이 그 「필요 시」** 다.

### 지금 구조가 Postgres 가 주는 것을 흉내 내고 있다

`StepForge/app/db.py` 머리말 — "**WAL 단일 라이터**가 원자성을 준다" ·
`:604` — "`BEGIN IMMEDIATE` 트랜잭션 — 잡 원자 클레임에 쓴다(**`SKIP LOCKED` 대용**)".

DynaForge 는 그 자리에서 `FOR UPDATE SKIP LOCKED` 를 쓴다(진짜를 쓴다). 그리고 StepForge 는
`PRAGMA journal_mode=WAL` 이 잠금과 부딪혀 `database is locked` 가 나는 자리를 따로 다뤄야 했다
(D-506, `db.py:295-310`). **없는 것을 흉내 내는 비용**이다.

### 옮기는 비용 — 실측

| 무엇 | 실측 | 비고 |
|---|---|---|
| `sqlite3` 를 부르는 자리 | 12파일, 집중 — `app/db.py`(10)·`app/jobs.py`(5)·`core/sidecar.py`(1) | ORM 이 없다(생 SQL) |
| 스키마 | `app/db.py` 620줄 · `CREATE TABLE` **18** | 한 파일 |
| SQLite 전용 문법 | `PRAGMA` 14(3파일) · `json_extract` 11(3) · `AUTOINCREMENT` 8(1) · `rowid` 7(5) · `strftime` 3(3) · `INSERT OR IGNORE` 1 | ~44 지점 |
| 자리표시자 | `?` **256회** → `%s` 또는 이름 인자 | 기계적이지만 많다 |
| 운영 | 인스턴스(5432~5436 사용 중 → **5437**) 또는 5436 에 DB 분리 · SIF 에 PG 클라이언트 · 기존 `.db` 이관 · 백업/복구 | **DynaForge 에 그대로 쓸 수 있는 선례가 있다**(`platform/infra/scripts/start.sh` → postgres → migrate → api · `backup-db.sh`) |

### 맞추면 생기는 것

1. **표가 이름만 같은 게 아니라 DDL 이 같아진다** — `properties` 가 양쪽 다 **JSONB**(SQLite 의
   JSON 텍스트가 아니다). 같은 색인, 같은 타입. 그래야 **두 쌍둥이 사이에 데이터가 실제로 옮겨진다.**
2. SP 의 수신 키트가 전제하는 것과 가까워진다 — 키트는 `sqlite3` 로 쓰여 있지만 **허브는 Postgres**다.
3. ★**StepForge 쪽에서는 「엔진이 아니라 꼴만」 결정을 다시 봐야 한다.** 그 결정의 근거가
   "StepForge 는 SQLite 다" 였다(그 문서 §2). Postgres 가 되면 SP 의 온톨로지 엔진(JSONB·pg_trgm·
   재귀 CTE·advisory lock·`SKIP LOCKED`·`COPY` 에 묶인)이 **쓸 수 있는 것**이 된다.
   **그것은 StepForge 의 판단이다** — 여기서는 그 사실만 적는다.

### ★DynaForge 쪽은 Postgres 가 되어도 엔진이 안 풀린다 — 막는 것이 DB 가 아니다

막는 것은 **부서(`workspaces`)** 다. `objects` 는 부서 소유를 전제로 짜여 있다
(`visible_owner_clause`·`require_owner_edit`·`resolve_owner_workspace` · import 실측 workspaces 6회,
accounts 31회, permissions 20회). 그런데 —

**DynaForge 는 부서 표를 들이면 안 된다. 이미 있다.** 게이트웨이가 **서명해서** 보낸다 —
`X-Heax-User-Affiliation` + `X-Heax-Aff-Proof`(`v1.<exp>.<hmac>`), 검증은
`app/shared/affiliation.py`, 가시성 판정은 `app/shared/visibility.py`. 정본은 **포탈**이다.

그리고 그렇게 하라고 **SP 가 스스로 적어 뒀다**(`온톨로지-메타모델-설계.md` §3.6) —

> `system` 이 핵심이다. 부서를 온톨로지에 넣겠다고 `objects` 에 행을 복제하면 두 벌이 되고
> **반드시 갈린다.** 행을 만들지 않고 `ObjectRef` 해석기가 원 표에서 라벨을 읽는다.

→ 부서는 `kind_class=system` **거울**로 둔다(행 복제 0). 끝단의 선은 `object_links` 자리에.
이것이 "규격을 맞춘다" 의 올바른 적용이다 — **표를 베끼는 것이 아니라 규칙을 따르는 것**이다.

## 3. 개정 모델 — DynaForge 자체 온톨로지

### 3-1. StepForge 와 **같은 꼴, 다른 축**이다 — 섞으면 안 된다

| | StepForge | DynaForge |
|---|---|---|
| 타입 slug | `cad_revision` | **`dev_revision`** |
| 뜻 | CAD 데이터 한 벌이 어느 과제·모델의 **몇 번째 판**인가 | 해석 결과가 어느 과제의 **어느 개발 단계·차수**인가 |
| 이름의 꼴 | `rev_label` 예 `C2`(`^[A-Z][0-9]$`) | `code` 예 `dv1`·`pv2`·`pre`·`mp`(`_STAGE_RE`) |
| 단위 | 과제 하나 = CAD 개정 하나 | 리포트 하나에 개정 하나(`eng_meta`) |

둘 다 **같은 `plm_task` 에 매달린다.** 그래서 허브에서 만나도 안 부딪히게 **slug 를 가른다.**
관계 이름은 뜻이 같은 것만 **똑같이** 쓴다.

### 3-2. 정의 (SP 정의 꼴)

| 정의 | 칸 / 끝점 | 뜻 |
|---|---|---|
| 타입 `dev_revision` | key = `<과제코드>@<code>` · `task`(→`plm_task`, 허브 거울) · `model`(→`plm_model`, 선택) · `code`(예 `dv1`) · `phase`(enum pre\|dv\|pv\|pra\|mp) · `round`(enum 1\|2\|3\|r) · `rev_seq`(그 과제 안 순서) · `rev_source`(`eng_meta`·`report_embed`·`hub_model_revision`·`manual`) · `status`(`draft`·`current`·`superseded`) · `decided_by` · `decided_at` | 해석 결과가 어느 과제의 몇 번째 개발 판인가 |
| 관계 `revision_of` | `dev_revision` → `plm_task` (many_to_one) | 같은 과제의 개정들 — **StepForge 와 같은 이름** |
| 관계 `supersedes` | `dev_revision` → `dev_revision` (many_to_one · 순환 금지) | 앞 판 — 줄의 순서. **StepForge 와 같은 이름** |
| 관계 `measured_at` | `impact_report` → `dev_revision` | 이 리포트가 어느 판을 쟀나 |

- ★**`rev_seq` 를 데이터로 둔다.** 지금 순서는 정규식의 나열 순서(`pre|dv|pv|pra|mp`)에
  **암묵**이다. SP 가 이 자리에서 배운 교훈이 문서에 적혀 있다 — "메타가 데이터에 있어야
  하는 이유: 코드에 암묵이면 화면도 MCP 도 그 의미를 알 방법이 없다. ReportArchive 가 `p55`
  에서 뒤늦게 깨달은 자리다"(`온톨로지-메타모델-설계.md` §3.4).
- **개정 이름은 사람이 정하고 기계는 후보를 낸다**(StepForge 와 같은 규율). DynaForge 의 근거 셋 —
  ① `eng_meta.dev_revision.code`(이미 있다 · 형식 검증까지) ② 리포트에 박힌 `project_name`
  ③ 허브 `plm_model.model_revision`. 후보와 근거를 보이고 사람이 확정한다.
- 허브에는 개정 개념이 없다 — 이 정의는 **DynaForge 의 것**이고(`source=dynaforge`),
  허브로 내보낼지는 §7 ⑤.

### 3-3. 지금 있는 `eng_meta` 를 어떻게 하나 — **지우지 않는다**

`eng_meta` 는 DataHub 등재 양식과 같은 모양이고 필터·패싯이 이미 물려 있다. 걷어내면 DataHub
쪽까지 같이 손대야 한다. 그래서 —

1. `eng_meta` 는 **그대로 둔다**(등재·검색이 계속 쓴다)
2. `impact_report` → `dev_revision` 관계를 **더한다**
3. 인제스트·PATCH 때 `eng_meta.project`+`dev_revision.code` 로 개정을 **찾거나 만들고** 잇는다
4. 둘이 어긋나면 **관계가 정본**이고, 어긋났다는 사실을 화면에 띄운다(**조용히 맞추지 않는다**)

★ 과거 리포트의 자유 문자열 `project` 를 `plm_task` 에 붙이는 일이 남는다. 추측해 붙이지 않고
**못 붙인 것을 목록으로 보여 준다**(틀려도 그럴듯한 것이 가장 나쁘다). SP 의 별칭·「채울 곳」
(ADR 0025)이 같은 문제를 이미 풀어 뒀다.

## 4. 저장 — Postgres (StepForge 의 표 꼴을 그대로)

**양쪽 다 Postgres 다**(§2-b). 표 이름·칸뿐 아니라 **타입까지** 같게 둔다 — `properties` 는
**JSONB** 다. 이름만 같고 타입이 다르면 맞대는 날 그 일부터 해야 한다.

| 표 | 칸 | 비고 |
|---|---|---|
| `onto_types` · `onto_relation_types` | 받은 정의(허브 카탈로그 스냅샷)와 자체 정의(`platform/core/ontology/dynaforge-core.json`) | 출처(`hub`·`dynaforge`)와 판(카탈로그 `revision` 지문) |
| `onto_objects` | `type`·`key`·`label`·`properties`(JSONB)·`previous_keys`·`deleted`·`hidden`·`merged_into`·`source`·`updated_at` | 허브 거울(`plm_project`·`plm_task`·`plm_model`·`plm_test_site`)과 자체 객체(`dev_revision`)를 **한 꼴로** |
| `onto_relations` | `relation`·`src_type`/`src_key`·`dst_type`/`dst_key`·`properties`·`deleted`·`source` | 받은 선과 자체 선 |
| `onto_sync_state` | 타입별 `objects_as_of`·`relations_as_of`·마지막 실행·상태 | **수신 규칙 1·2** — 서버가 준 `as_of` 를 **끝까지 받은 뒤에만** 옮긴다 |
| `impact_reports` | (그대로) `eng_meta` 는 입력·등재 칸으로 두고, 이어짐은 `measured_at` 관계가 정본 | 진입점 하나 |

**끝점은 `key` 로 잇는다**(uuid 가 아니다) — 받는 쪽의 id 는 허브 것과 다르다
(`CoreRelationOut` 이 그렇게 생겼다).

## 5. 단계 (StepForge 의 S0~S6 과 같은 번호)

| 단계 | 할 일 | 완료 기준 |
|---|---|---|
| **S0** 받기와 고정 | 보관 방식 결정(§7 ①) · 출처 메모 · **런타임 import 0 가드**(구조 시험) | `git status` 가 깨끗하다 · `platform/` 이 `vendor/` 를 import 하면 회귀가 깨진다 |
| **S1** 과제 정보 수신 | 수신 키트를 `platform/backend/app/runner/sp_core.py` 로 옮김(**httpx + SQLAlchemy**) · 표 넷(§4) · 잡 `plm_sync` · 설정(`KOORM_SP_CORE_URL` · 토큰) · MCP 는 기존 도구에 축을 더하는 쪽 먼저 | 가짜 코어 서버로 **수신 규칙 열하나 전부** 회귀(증분 · `next` 중 `as_of` 미저장 · `deleted` · `merged_into` · `renamed_from` · `hidden` · reset · 404 둘 · 부재 대조 · 되살림 · 같은 행 두 번) · 실제 허브에서 한 번 받기(§7 ②) |
| **S2** 자체 온톨로지 정의 | SP 정의 꼴의 `dynaforge-core.json`(`dev_revision`·`revision_of`·`supersedes`·`measured_at`) · 작은 검증기(값 종류·필수·카디널리티·참조 타입·순환 금지) · 허브 카탈로그와 한 표에 싣기 | 허브의 `plm-core` 를 그대로 읽어 검증기가 통과시킨다 · 자체 정의가 SP import 꼴로 **왕복**한다 |
| **S3** 개정 잇기 | `set_revision`(과제·모델·개정 코드·앞 판) · 후보 셋과 근거 · `eng_meta` ↔ 관계 어긋남 **표시** · `revision_history`(과제의 개정 줄) | 합성 리포트 셋으로 줄·후보·어긋남이 맞다 · **사람 판정이 재인제스트에 안 지워진다** |
| **S4** 과거 붙이기 | 자유 문자열 `project` → `plm_task` 별칭 · **못 붙인 목록** | 실측으로 붙은 수/못 붙은 수를 **보고한다**(추정 금지) |
| **S5** API·MCP·화면 | 과제·개정 목록, 개정 간 리포트 비교 · 리포트 목록의 과제·개정 필터 | `reports_smoke` 에 항 추가 · Playwright 로 실동작 |
| **S6** 허브로 내보내기(선택 · §7 ⑤) | `dev_revision` 을 허브에 올리기(허브에 그 타입 정의가 있어야 한다) | 허브 주인의 합의 뒤 |

**엔진을 작게 다시 짓는 이유** — SP 처럼 `object_types` 를 데이터로 두면 화면 자동생성·권한·
`list_view`·인터페이스가 줄줄이 따라온다(그것이 34,180줄의 정체다). 우리가 지금 필요한 축은
허브 거울 넷 + 자체 하나다. **축이 늘어 화면 자동생성이 필요해지는 날**이 SP 인스턴스를
따로 띄울지 다시 보는 지점이다 — 그 기준을 지금 적어 둔다.

## 6. 위험 · 한계

- **허브가 있어야 S1 이 의미가 있다** — 저장소에 PLM 커넥터가 없다. 허브 주소와 `core:read`
  토큰이 없으면 S1 은 **가짜 서버 회귀까지만** 간다. 이 박스에는 SP 계열 백엔드가 안 떠 있다
  (8010~8072 중 열린 것은 `8013` 뿐이고 그것은 컨테이너의 MCP, `cwd=/mcp-server`, 게이트웨이
  설정에도 없다). 운영은 모른다 — 이 박스만 봤다.
- **`task_status` 값 목록은 저장소 밖**(허브의 사내 확장 정의)이다 — 받은 카탈로그를 정본으로
  쓰고 **코드에 박지 않는다**.
- **개정 이름은 원천마다 뜻이 다르다** — SP 스스로 `model_revision` 은 "BOM 부품 리비전과 다른
  것" 이라고 적었다. 후보의 근거를 함께 보이고 사람이 정한다.
- **SP 는 바뀐다**(10-13 에도 커밋). 수신 규칙은 판 `f7485c0` 에 고정하고 카탈로그의 `revision`
  지문이 바뀌면 **알린다**.
- SP 는 데이터 소스 자격증명을 DB 에 평문으로 두는 것으로 보인다 — StepForge 는 그 꼴을 따르지
  않기로 했다(토큰은 파일 경로로만). **DynaForge 는 지금 `.env`(`gateway_pat`)를 쓴다** —
  §7 ④ 에서 한 번에 정한다.
- **관문이 초록인 것과 플랫폼에서 도는 것은 다르다**([[kooremapper-green-gates-lie]]) —
  S1 의 완료 기준에 「실제 허브에서 한 번 받기」 를 넣은 이유다.

## 7. 사람이 정할 것 — **①②③④⑤⑥⑦ 닫힘 · ⑧⑨ 는 StepForge 소관**

> ③⑤⑥ 은 2026-10-14 "다 수정해" 에 따라 **제 판단으로 닫았다.** 각각 근거와 **다시 볼 조건**을
> 함께 적었다 — 다르게 보시면 그 줄만 고치면 된다.
> 남은 **실제 막힘은 하나**다 — ② 의 **허브 주소와 `core:read` 토큰**. 그것이 S1 을 라이브로
> 닫는 조건이고, 그 전까지 S1 은 가짜 코어 서버 회귀까지 간다.

1. ~~보관 방식~~ → **정해졌다(2026-10-14): git submodule.** StepForge 와 **같은 경로·같은 주소·
   같은 커밋** — `external/StandardPlatform` @ `f7485c0`(v0.4.52) · **브랜치 추적 없음**.
   런타임(`platform`·`tools`·`scripts`·`materials`)은 import 하지 않는다 —
   `platform/backend/tests/test_external_boundary.py` 4항이 지킨다.
2. **과제 정보의 원천** → StepForge 가 **운영 중인 SP 허브의 코어 API** 로 정했다(D-525 ②).
   같은 답으로 간다. **주소와 `core:read` 토큰은 아직 없다** — 그것이 S1 을 라이브로 닫는 조건이다.
3. **개정 단위** — 리포트 하나에 개정 하나(지금 `eng_meta` 그대로 · 권장) 대 세션/잡에도 매달기.
   세션에 매달면 **제출 화면이 바뀐다**(해석 전부터 과제를 알아야 한다).
4. ~~토큰을 어디 두나~~ → **정해졌다(2026-10-14): `.env`.** DynaForge 의 기존 관례를 유지한다
   (`gateway_pat` 과 같은 자리). `.gitignore` 의 `platform/**/.env` 가 리포 밖에 둔다 —
   StepForge 의 「비밀은 리포·DB 에 두지 않는다」 와 어긋나지 않는다.
   ⚠ StepForge 는 `/data/hwax/secrets` 아래 **파일 경로만** 앱에 준다(D-525 ②). 그쪽이
   규격을 `.env` 로 맞출지는 거기서 정한다 — 적어만 둔다.
5. ~~허브로 내보내기~~ → **닫았다: 뒤로(S6).** StepForge 와 같은 답이다(D-525 ⑤).
   허브에 `dev_revision` 타입 정의가 **먼저** 있어야 하고 그것은 허브 주인의 합의다.
   올리는 날 StepForge `cad_revision` 과 **나란히** 서야 하므로, 둘이 각자 올리면 안 된다 —
   한 번에 같이 올린다.
6. ~~`design_variation`·`doe` 를 축으로~~ → **닫았다: 이번 판은 올리지 않는다.**
   `eng_meta` 의 문자열로 둔다(필터·패싯이 이미 그 모양으로 돈다).
   **기준은 이미 적혀 있다**(§5 끝) — 축이 늘어 **화면 자동생성이 필요해지는 날** SP 엔진을
   다시 본다. `variation`·`doe` 를 축으로 올리면 거울 넷 + 자체 셋이 되어 그 문턱에 닿는다.
   그래서 이 둘은 **그 재검토와 함께** 간다. 따로 올리면 중간 상태가 가장 비싸다.
7. ~~코드 복사 허락~~ → **허락됐다**(D-525 ⑥ — 요청이 "심어" 였다). 출처를 머리 주석에
   `StandardPlatform <경로>@f7485c0` 로 단다.
8. **StepForge 를 Postgres 로 옮기는 시점과 방식**(§2-b) — ★**StepForge 소관이다.**
   여기서 닫을 수 없다. DynaForge 쪽 **전제만** 적는다 —
   ㉮ 우리 표를 처음부터 **JSONB** 로 세운다(§4). 그쪽이 PG 로 오는 날 DDL 이 이미 같다.
   ㉯ 표 이름·칸을 StepForge 의 것과 **같게** 둔다(이미 그렇게 했다).
   ㉰ 포트는 `5437` 이 빈다(5432~5436 사용 중) · `5436` 에 DB 를 나누는 길도 있다(SP 포크 지침은
   「DB 두 개 — 이름은 `APP_SLUG` 그대로」). **그 선택도 그쪽 것**이다.
9. **PG 뒤 「엔진이 아니라 꼴만」 재검토**(§2-b 3) — ★**StepForge 소관이고, DynaForge 는 영향이
   없다.** 우리를 막는 것은 DB 가 아니라 **부서**였고(§2-b 끝) 그것은 PG 가 되어도 그대로다.
   그쪽이 엔진을 받기로 하더라도 우리는 「작게 다시 짓는다」 를 유지한다 — 바뀌는 조건은 오직
   ⑥ 의 문턱(축이 늘어 화면 자동생성이 필요해지는 날)이다.

## 부록. 참조한 자리 (전부 `vendor/StandardPlatform@f7485c0`)

| 무엇 | 어디 |
|---|---|
| 과제 정의(정본) | `pipeline/core/plm-core.json` |
| 담당·참여 관계 | `pipeline/core/work-core.json` (관계 10 — `dept_in_charge`·`responsible`·`participates`·`part_of`·`produces`·`evidence`·`uses`·`involves_org`·`affiliated`·`about`) |
| 코어 API 계약 | `backend/app/modules/coreapi/routes.py`·`schemas.py` |
| **수신 키트** | `backend/app/modules/coreapi/kit/sp_core_pull.py` (436줄) |
| **수신 규칙 열하나** | `docs/외부-시스템-연동-지침서.md` §4.2 (머리 186행 · 규칙 311~343행) |
| 허브/쌍둥이 — 받기만 한다 | `backend/app/modules/ontology/managed.py` |
| `managed_by` 칸 | `backend/app/modules/ontology/models.py:258`·`:344`·`:503` |
| 쌍둥이의 거절 지점 | `backend/app/modules/objects/routes.py:2268`(만들기)·`:1531`·`:1645`·`:2397`·`:2700` |
| 온톨로지 메타모델 설계 | `docs/온톨로지-메타모델-설계.md` (1,039줄) · 배경 `docs/adr/0005-…` |
| 시간 축(연도) · 식별자 · 속성 일곱 | 같은 문서 §4.3 · §4.1 · §4.2 |
| 별칭·채울 곳 | `docs/adr/0025-채울-곳과-별칭-후보.md` |
| 포크 절차 · 포트 표 | `docs/새-플랫폼-만들기.md` (828줄) · §3.6 |
| MCP(얇은 프록시) | `mcp_server/server.py:44` |
| **StepForge 의 같은 계획** | `/home/koopark/claude/StepForge/docs/STANDARD_PLATFORM.md` (`bea7485`, D-525) |
