# Checklist — StandardPlatform 수신 · 온톨로지 · 개정

설계 `ontology-graft.plan.md` · 맥락 `ontology-graft.context-notes.md`
★결을 맞추는 짝 — `StepForge/docs/STANDARD_PLATFORM.md`(`bea7485`, D-525) 와 **같은 S0~S6** 이다.

> **S1 부터는 §7 의 답을 받고 시작한다.** 특히 ① 보관 방식과 ② 허브 주소·토큰이 없으면
> S1 은 가짜 서버 회귀까지만 간다.

## A. 조사 (끝)
- [x] **A-1 받기** `vendor/StandardPlatform` (`f7485c0` · 0.4.52 · 916파일 18MB) — **읽기만** 했다
      (코드 실행 0 · 그 리포 안 URL 접속 0)
- [x] **A-2 엔진 규모 실측** 백엔드 34,180줄(`ontology` 11,222 + `objects` 22,958) · 프런트 22,158줄(97 tsx)
- [x] **A-3 의존 폐쇄 실측** accounts(31회)·shared.errors(29)·shared.permissions(20)·batches(10)·
      workspaces·metrics·files·jobs·datasources·audit·review + shared 11개 → **부서를 전제한다.
      DynaForge 엔 부서가 없다**
- [x] **A-4 과제의 정본** `pipeline/core/plm-core.json` — `plm_project`·`plm_task`(key=과제코드)·
      `plm_model`(`model_revision` 보유)·`plm_test_site` + `plm_derived_from`
- [x] **A-5 받는 길** 허브 **코어 API**(`/api/core`·`/api/core/{type}`·`…/relations` · `core:read`)
      + **수신 키트**(`coreapi/kit/sp_core_pull.py` 436줄) + **수신 규칙 열하나**(§4.2 311~343행)
- [x] **A-6 쌍둥이는 못 고친다** `managed_by` 와 거절 지점(`objects/routes.py:2268` 이 **만들기**까지)
- [x] **A-7 SP 에 개정 모델링이 없다** — 객체 한 줄이 현재 상태. 시간 축은 **연도**뿐
- [x] **A-8 우리 쪽 실측** `eng_meta` 에 과제·개정이 **이미 있다**(형식 검증·필터·패싯·DataHub 등재)
- [x] **A-9 StepForge 와 대조** 용어(개정·허브·거울)·표 꼴·단계 번호·수신 규칙을 맞췄다.
      ★**축은 다르다** — StepForge `cad_revision`(CAD 판) vs DynaForge `dev_revision`(개발 단계)
- [x] **A-10 제 오기 수정** 이전 판에 "받기는 묶음 가져오기" 라고 적었다 → **코어 API** 다.
      `coreapi` 모듈을 안 보고 썼다
- [x] **A-11 줄번호 오기 수정** 수신 규칙을 126~157행으로 적었는데 그것은 `awk` 로 잘라낸 블록의
      **상대 번호**였다 → 실제 **311~343행**
- [x] **A-12 규격은 Postgres 다**(사용자 지시 · 계획서 §2-b) — SP 는 PG 필수, 포크 넷도 PG,
      DynaForge 도 PG(5436). **StepForge 만 SQLite** 이고 그 자기 계획서가 이미
      `SQLite(WAL) → 필요 시 PG`(`StepForge/docs/PLAN.md:51`) 라고 적어 뒀다
- [x] **A-13 옮기는 비용 실측** `sqlite3` 12파일(집중: `db.py` 10·`jobs.py` 5) · 스키마 620줄
      `CREATE TABLE` 18 · 전용 문법 ~44지점 · `?` 자리표시자 **256** · 포트는 **5437** 이 빈다
- [x] **A-14 지금이 흉내다** `db.py:604` 가 `BEGIN IMMEDIATE` 를 **`SKIP LOCKED` 대용**이라 적는다 ·
      `PRAGMA journal_mode=WAL` 잠금 충돌을 따로 다뤄야 했다(D-506)
- [x] **A-15 ★부서는 베끼지 않는다** DynaForge 는 `X-Heax-User-Affiliation`+`X-Heax-Aff-Proof`
      (HMAC)를 받고 `shared/affiliation.py`·`shared/visibility.py` 가 판정한다 — 정본은 포탈이다.
      SP 스스로 "부서를 `objects` 에 복제하면 두 벌이 되고 **반드시 갈린다**" 고 적었다(§3.6)
      → `kind_class=system` **거울**(행 복제 0)

## S0. 받기와 고정 — **끝**
- [x] **S0-1 보관 = git submodule** `external/StandardPlatform` @ `f7485c0`(v0.4.52) ·
      브랜치 추적 없음 · StepForge 와 **같은 경로·주소·커밋**. `.gitignore` 의 `vendor/` 는 뺐다
- [x] **S0-2 출처 규약** 옮긴 파일 머리에 `StandardPlatform <경로>@f7485c0`
- [x] **S0-3 런타임 import 0 가드** `platform/backend/tests/test_external_boundary.py` **4항** —
      import · `sys.path` 우회 · **훑는 범위가 0이 아닌지** · submodule 이 그 커밋에 고정됐는지
- [x] **S0-4 관문이 무는지 증명** `tools/_boundary_probe.py` 에 `sys.path.insert(…external…)` 를
      심어 **빨개지는 것**을 보고 지웠다.
      ★처음엔 **안 물었다** — `git ls-files` 가 추적된 것만 봐서 방금 쓴 파일이 목록에 없었다.
      `--cached --others --exclude-standard` 로 고쳤다(`.gitignore` 가 `.venv` 를 막아 준다).
      **세는 관문이 0을 세면 언제나 초록이다**

## S1. 과제 정보 수신
- [x] **S1-1 키트 이식** `app/runner/sp_core.py` 413줄 — `requests`+`sqlite3` → **httpx + SQLAlchemy**.
      머리에 출처(`…/kit/sp_core_pull.py@f7485c0`)를 달았다
- [x] **S1-2 표 다섯** `onto_types`·`onto_relation_types`·`onto_objects`·`onto_relations`·
      `onto_sync_state` — StepForge 와 **같은 이름·칸**, `properties` 는 **JSONB**.
      마이그레이션 `0011_ontology`(개발 DB 에 올렸다)
- [x] **S1-7 부서는 행을 만들지 않는다** 받은 선의 **먼 끝**으로만 산다(SP `object_links` 와
      같은 자리). `test_a_relation_to_a_system_type_never_creates_an_object_row` 가 지킨다
- [x] **S1-3 `plm_sync`** `app/worker/plm_sync.py` — 잡이 아니라 **주기 작업**이다(잡은 세션에
      매달리고 기준정보는 세션의 일이 아니다). 외부 잡 스캔과 같은 자리·같은 모양.
      **기본 꺼짐**(`sp_core_sync_sec=0`) — 없는 허브를 두드리면 진짜 실패가 로그에 묻힌다.
      배선이 지워지지 않게 구조 시험까지(`test_the_worker_still_calls_it`)
- [x] **S1-4 설정** `sp_core_url`·`sp_core_token`·`sp_core_page_size` — 기본값 빈 문자열,
      주소나 토큰이 비면 **아무것도 부르지 않고** `unavailable` 로 실패한다
- [x] **S1-5 수신 규칙 열하나 전수 회귀** `tests/test_sp_core_rules.py` **23항**(가짜 허브) —
      규칙 1·2(시계 · 쪽이 남으면 안 옮긴다 · 중간에 끊기면 옛 시계 유지) · 3 · 4(deleted ·
      merged_into · **renamed_from** · hidden) · 5·10 · 6(행·**선** 둘 다) · 7(전량 쓸어내기 ·
      **0건이면 아무것도 안 한다** · 증분은 안 쓸어낸다) · 8 · 9 · 11(둘로 가른다)
      + reset · reset 루프 거절 · 토큰 없으면 호출 0 · 공개 안 된 타입 요청 거절 · 카탈로그 판 기록
- [x] **S1-5a ★키트의 구멍을 채웠다** `renamed_from` 을 키트가 **전혀 다루지 않는다**
      (`ENVELOPE` 에도 없다). 규칙 4 가 요구하므로 구현하고 회귀로 박았다 — 없으면 개명 뒤
      **같은 것이 둘이 된다**
- [x] **S1-5b 회귀가 결함 둘을 잡았다** ① 한 쪽에 같은 key 가 두 번 오면
      `CardinalityViolationError`(Postgres 는 한 문장에서 같은 행을 두 번 못 고친다) →
      보내기 전에 접는다(나중 것이 이긴다). 선도 같다. ② 규칙 11 의 사유에 **코드가 안
      들어갔다** → `[APP-CORE-0001]` 을 넣는다(고칠 곳을 가르는 값이다)
- [ ] **S1-6 실제 허브에서 한 번 받기**(§7 ② 뒤) — 관문이 초록인 것과 도는 것은 다르다

## S2. 자체 온톨로지 정의
- [x] **S2-1 `platform/core/ontology/dynaforge-core.json`** — `dev_revision`(속성 11) +
      `revision_of`·`supersedes`·`measured_at`. SP import 꼴 그대로.
      ★`code` 의 정규식이 리포트 쪽 `_STAGE_RE` 와 **같은지** 시험이 대조한다(두 벌이 되면
      한쪽만 고쳐진다). `rev_seq` 는 **데이터**다
- [x] **S2-2 검증기** `app/runner/ontology_def.py` — 값 종류 10 · 필수 · 카디널리티 4 ·
      참조 타입 · **순환 금지**(자기를 가리키면 `acyclic` 필수 · 끝이 안 겹치는데 `acyclic`
      이면 **막는 것이 없다**고 흠). 모르는 키는 **알림**이고 흠이 아니다(수신 규칙 5 자세).
      판별력 시험 12항 — 통과만 보는 검증기는 아무것도 안 보는 것과 구별되지 않는다
- [x] **S2-3 왕복** ★허브의 `plm-core.json`·`work-core.json` 을 **바꾸지 않고** 읽어 흠 0 ·
      알림 0(`section` 키까지 아는 것으로 올렸다). 그것이 「꼴을 맞췄다」 의 증거다
- [x] **S2-4 `rev_seq` 는 데이터다** — 정규식 나열 순서에 암묵이던 것을 꺼냈다

## S3. 개정 잇기
- [ ] **S3-1 `set_revision`** 과제·모델·개정 코드·앞 판
- [ ] **S3-2 후보 셋과 근거** ① `eng_meta.dev_revision.code` ② 리포트의 `project_name`
      ③ 허브 `plm_model.model_revision` — **사람이 확정한다**
- [ ] **S3-3 어긋남을 띄운다** `eng_meta` ↔ 관계가 다르면 **관계가 정본**이고 그 사실을 보인다
      (조용히 맞추지 않는다)
- [ ] **S3-4 사람 판정이 재인제스트에 안 지워진다** → 회귀
- [ ] **S3-5 `revision_history`** 과제의 개정 줄

## S4. 과거 붙이기
- [ ] **S4-1 별칭** 자유 문자열 `project` → `plm_task`
- [ ] **S4-2 못 붙인 목록** — 추측해 붙이지 않는다(틀려도 그럴듯한 것이 가장 나쁘다)
- [ ] **S4-3 실측 보고** 붙은 수 / 못 붙은 수. **추정 금지**

## S5. API · MCP · 화면
- [ ] **S5-1 API** 과제·개정 목록, 개정 간 리포트 비교
- [ ] **S5-2 MCP** 기존 도구에 축을 더하는 쪽 먼저
- [ ] **S5-3 화면** 리포트 목록의 과제·개정 필터
- [ ] **S5-4 관문** `reports_smoke` 에 항 추가 · Playwright 실동작

## S6. 허브로 내보내기 (선택 · §7 ⑤)
- [ ] **S6-1** `dev_revision` 을 허브에 — StepForge `cad_revision` 과 **나란히** 서야 한다

## 사람이 정할 것 (§7) — **남은 실제 막힘은 ② 의 허브 주소·토큰 하나**
- [x] ① 보관 방식 — **git submodule**(StepForge 와 같은 경로·주소·커밋)
- [x] ② 원천 — **운영 중인 SP 허브의 코어 API**(D-525 ②). ⚠ 주소·`core:read` 토큰은 **아직 없다**
- [x] ③ 개정 단위 — **리포트 하나에 개정 하나**(세션에 매달면 제출 화면이 함께 움직인다)
- [x] ④ 토큰 — **`.env`**(DynaForge 기존 관례 유지 · `platform/**/.env` 로 리포 밖)
- [x] ⑤ 허브로 내보내기 — **뒤로(S6)**. 올리는 날 StepForge `cad_revision` 과 **한 번에 같이**
- [x] ⑥ `design_variation`·`doe` — **이번 판은 축으로 안 올린다**. §5 끝의 문턱과 **함께** 간다
- [x] ⑦ 코드 복사 — **허락됐다**(D-525 ⑥). 출처를 머리 주석에 단다
- [x] ⑧ StepForge PG 이관 — **그쪽 소관**. 우리 전제만: 표를 **JSONB** 로 · 이름을 같게 · 5437 이 빈다
- [x] ⑨ 엔진 재검토 — **그쪽 소관 · 우리는 영향 없다**(막는 것이 DB 가 아니라 부서다)
