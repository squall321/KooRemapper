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

## S0. 받기와 고정
- [ ] **S0-1 보관 방식 결정**(§7 ① — submodule \| gitignore \| 복사만). ★StepForge 와 **같은 답**
- [ ] **S0-2 출처 메모** 옮긴 파일 첫 줄에 `StandardPlatform <경로>@f7485c0`
- [ ] **S0-3 런타임 import 0 가드** — 구조 시험이 `platform/` → `vendor/` import 를 빨갛게 만든다

## S1. 과제 정보 수신
- [ ] **S1-1 키트 이식** `app/runner/sp_core.py` — `requests`+`sqlite3` → **httpx + SQLAlchemy**
- [ ] **S1-2 표 넷** `onto_types`·`onto_relation_types`·`onto_objects`·`onto_relations`·`onto_sync_state`
      (StepForge 와 **같은 이름·칸**)
- [ ] **S1-3 잡 `plm_sync`** 기존 워커에 — 네트워크만, 바이너리 없음
- [ ] **S1-4 설정** `KOORM_SP_CORE_URL` · 토큰(§7 ④) — **코드에 기본값을 박지 않는다**
- [ ] **S1-5 수신 규칙 열하나 전수 회귀** (가짜 코어 서버)
      → `as_of` 되돌림 · `next` 중 `as_of` 미저장 · `key` 저장 · `deleted`/`merged_into` ·
      모르는 칸 무시 · 같은 행 두 번 · `since` 없을 때 **부재 대조** · 되살림 ·
      합쳐진 쪽의 선 · 참조 칸의 옛 `key` · **404 두 가지**(`APP-CORE-0001` 과 그 외)
- [ ] **S1-6 실제 허브에서 한 번 받기**(§7 ② 뒤) — 관문이 초록인 것과 도는 것은 다르다

## S2. 자체 온톨로지 정의
- [ ] **S2-1 `platform/core/ontology/dynaforge-core.json`** — `dev_revision`·`revision_of`·
      `supersedes`·`measured_at`
- [ ] **S2-2 작은 검증기** 값 종류·필수·카디널리티·참조 타입·순환 금지
- [ ] **S2-3 왕복** 허브의 `plm-core` 를 그대로 읽어 통과 · 우리 정의가 SP import 꼴로 왕복
- [ ] **S2-4 `rev_seq` 는 데이터다** — 정규식 나열 순서에 암묵이던 것을 꺼낸다

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

## 사람이 정할 것 (§7)
- [ ] ① 보관 방식 (★StepForge 와 같은 답)
- [ ] ② 허브가 어느 인스턴스인가 · 주소 · `core:read` 토큰
- [ ] ③ 개정 단위 — 리포트에만 \| 세션·잡에도
- [ ] ④ 토큰을 어디 두나 — `.env` 유지 \| 파일 경로만(StepForge 쪽)
- [ ] ⑤ 허브로 내보내기
- [ ] ⑥ `design_variation`·`doe` 도 축으로
- [ ] ⑦ 코드 복사 허락(SP 에 라이선스 파일이 없다)
