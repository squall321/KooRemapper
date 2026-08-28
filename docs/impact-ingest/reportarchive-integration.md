# ReportArchive ← DynaForge 결과 pull 연동 (ra.analysis.v1)

ReportArchive 가 DynaForge 의 해석 결과를 **자동으로 당겨간다**(주기 동기화, 읽기 전용).
규격서 `ra.analysis.v1` 를 그대로 충족한다. 받는 쪽은 아래 값으로 소스를 설정하면 된다.

## 엔드포인트 (구현됨)

- **A. 목록** `GET /api/v1/analysis/runs?since=<ISO>&after=<커서>&limit=100`
  → `{success, data:{items:[{run_key, id, title, kind, analyzed_at, file_url, n_cases}], next_after?}}`
  - `run_key` = DynaForge 리포트 id(ULID, 안정·유일). 같은 리포트 재인제스트하면 새 id → 새 결과.
  - `since` = analyzed_at(created_at) 증분. `after`/`next_after` = id 커서(ULID 시각순).
- **B. 파일** `GET /api/v1/analysis/runs/{run_key}/export.ndjson`
  → `ra.analysis.v1` NDJSON 스트리밍(run 1줄 + fact N줄). `application/x-ndjson`.

인증: `Authorization: Bearer kr_...`(DynaForge PAT). 목록·파일 동일 헤더.

## ReportArchive `AnalysisSource.fetch_config` 값

```json
{
  "list_path": "api/v1/analysis/runs",
  "items_path": "data.items",
  "key_path": "run_key",
  "cursor_path": "data.next_after",
  "after_param": "after",
  "since_param": "since",
  "limit_param": "limit",
  "page_size": 100,
  "file_url_path": "file_url",
  "watermark_field": "analyzed_at",
  "cursor_field": "id"
}
```

`auth_config`: `{"bearer_token": "kr_<서비스 PAT>"}`.
- 서비스 계정으로 PAT 하나 발급 → 그 계정이 소유(또는 공유받은) 리포트만 보인다.
- 응답 봉투가 `{success, data:{...}}` 라 `items_path`·`cursor_path` 에 `data.` 접두를 붙인다(규격 §1.1 중첩 허용).

## NDJSON 형식 (실측 예)

```
{"type":"run","schema":"ra.analysis.v1","schema_version":1,"workflow":"full_angle_drop",
 "title":"Test_001_Full26_1Step","run_key":"01M156TD…","units":{"stress":"MPa","g":"G","disp":"mm",…},
 "parts":{"1":{"part_name":"Front\\Metal","group":"Front"},…},"findings":[…],"analyzed_at":"…Z",…}
{"type":"fact","axis_key":"Run_…","axis_meta":{"roll":0.0,"pitch":90.0,"yaw":0.0,"category":"face"},
 "part_key":"1","quantity":"stress","value":461.2}
```

- `workflow`: sphere→`full_angle_drop`, impact→`partial_impact_dwi`, deep→`single_deep`.
- `axis_meta`: sphere=`{roll,pitch,yaw,category}`(→ 구면 분포도 자동), impact=`{face,x,y}`.
- `quantity`: stress(MPa)·strain·g(G)·disp(mm)·max/min_principal_stress(MPa)·vm_strain.
- 값이 없으면(None) 그 fact 는 내지 않는다(숫자만). 단위는 항상 명시(§3.1 경고 준수).

## 범위 / 한계 (v1)

- **series(시간이력) 미포함** — v1 은 run + fact(피크값). series 는 원본 HTML 재파싱이라 후속.
  ReportArchive 도 §3.3 series 는 선택.
- **인증 범위** — 일반 PAT=소유자 리포트, **시스템 관리자 PAT=전 사용자 리포트(전사 수집)**.
  admin 이면 목록 item 에 `owner_user_id` 로 어느 계정 결과인지 표시된다. 같은 엔드포인트라
  ReportArchive fetch_config 변경 없이 PAT 권한만으로 범위가 결정된다.
- **file_url 외부 도달** — 포탈 서브패스 뒤라 내부 base 와 다르면 `KOORM_ANALYSIS_PUBLIC_BASE_URL`
  (config `analysis_public_base_url`)에 외부 URL 을 넣는다. 비우면 요청 base_url 을 쓴다.
- **sha256/bytes 미제공** — NDJSON 을 즉석 생성하므로 목록에 크기·해시를 안 싣는다(규격상 선택).
- Range/gzip 미지원(후속). 규격 §2 상 없어도 동작(끊기면 처음부터).

## 다대다(M:N) 토폴로지 — 여러 DynaForge ↔ 여러 ReportArchive

현재 설계로 **이미 성립**한다(읽기전용 pull + PAT 다중 공존). 추가 서버 로직 불필요.

**여러 DynaForge → 하나의 ReportArchive (fan-in)**
- ReportArchive 가 각 DynaForge 를 별도 소스(AnalysisSource)로 등록 — 인스턴스마다 base_url + PAT.
- 각 결과에 **`site`** 필드가 실려 어느 인스턴스에서 왔는지 구분된다(목록 item + NDJSON run 줄·provenance).
  `KOORM_ANALYSIS_SITE_ID`(config `analysis_site_id`, 예 "dynaforge-cae00")로 인스턴스마다 설정.
- `run_key` 는 ULID 라 인스턴스 간 전역 유일 → 충돌 없이 한 아카이브로 합쳐진다(site 는 표시·그룹핑용, dedup 은 run_key).

**하나의 DynaForge → 여러 ReportArchive (fan-out)**
- 읽기전용·멱등이라 N개가 동시에 폴링해도 무방. 각 ReportArchive 는 자기 이름의 PAT 를 쓴다
  (한 계정에 여러 named PAT 공존 가능, 또는 ReportArchive 마다 별도 계정).

**SSO PAT 와 ReportArchive PAT 공존 (맞는 설계)**
- SSO PAT 는 포탈 로그인 시 **같은 이름만** 회전(회수+재발급)한다. ReportArchive PAT 는 **다른 이름**
  (예 `ReportArchive`)이라 절대 안 건드려진다 → 한 계정에 SSO PAT + 서비스 PAT 가 안전하게 공존.
- 즉 사람(웹/Claude, SSO PAT)과 기계(ReportArchive, 고정 PAT)가 같은 계정을 써도 서로 안 끊는다.
