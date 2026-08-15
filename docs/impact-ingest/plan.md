# DynaForge 충격 리포트 인제스트 & MCP 분석 — 계획

## 배경 / 목표
SmartTwin 파이프라인(`fullangle_drop_simulation` → KooChainRun → KooD3plotReader 후처리)이
생성하는 **낙하/충격 리포트**를 DynaForge 플랫폼이 수용해서, HTML 을 받아 구조화 저장하고
MCP 로 각종 분석을 할 수 있게 한다.

리포트 3종(v1 전부 지원):
- **deep** (`koo_deep_report`) — 단건 심층 (디테일 한 각도/위치)
- **sphere** (`koo_sphere_report`) — 전각도 낙하 집계 (Fibonacci/26방향)
- **impact** (`koo_impact_report`) — 전위치 부분충격 (F1~F6 × XY 그리드)

## 확정된 결정 (사용자 확인 완료)
1. **호스팅** — DynaForge(KooRemapper 플랫폼) 확장. SmartTwinMCP=생성, DynaForge=수용·분석.
2. **저장소** — DynaForge Postgres(작업/질의/MCP) + AIDataHub(sim-result 데이터 레코드, eng_meta 연계).
3. **v1 범위** — sphere + deep + impact 3종 동시, 공통 `kind` 스키마.
4. **인제스트 입력** — HTML(임베드 `const DATA` 블롭 파싱)이 1차. JSON 사이드카는 선택적 고해상도 보강.

## 근거 (실물 확인)
- deep/sphere HTML 은 데이터를 `const DATA = {…}` 순수 JSON 으로 인라인 임베드(외부 의존 Plotly CDN 뿐).
  마커~중괄호 매칭 구간만 뽑으면 `json.loads` 로 전량 복원. → "HTML 만 받는 API" 성립.
- HTML 임베드 DATA 는 `result.json`/`report.json` 사이드카의 superset(시계열 ≤500pt 다운샘플).
  피크·랭킹·안전율·최악방향엔 충분. 완전 해상도 필요 시 사이드카 동반.
- `koo_federate_report` 가 이미 sphere `report.json`·impact `impact_payload.json` 을 `kind` 로
  구분하는 사이드카 계약을 정의 → 정규화 스키마를 여기 맞추면 리비전 비교가 자연 연결.

### 스키마 함정 (파서가 방어)
- `parts` 키는 문자열 파트ID, 비연속(예제서 "23" 누락). 이름에 리터럴 백슬래시/공백 가능(폴백 `Part_<id>`).
- `schema` 문자열 2종 병존: `single_analyzer/1.0` ∨ `koo_deep_report/1.0`.
- `analysis_result.json` 의 `*_history` 는 디스크서 head10+tail10 로 잘림 — 완전 시계열은 HTML DATA
  (다운샘플) 또는 `peak_element_tensors`/motion CSV. → 디스크 analysis_result.json 은 신뢰 금지.
- null 다수: `metadata.normal_termination`, `summary.energy_ratio_min`, `parts[*].safety_factor`,
  `glstat` 블록 전체(Tier<2). "미측정"은 0 이 아니라 null 로 보존.

## 공통 정규화 스키마 (kind-tagged)
파서가 deep/sphere/impact HTML(또는 사이드카)을 아래 공통 형태로 정규화한다.

```
NormalizedStudy = {
  kind: "deep" | "sphere" | "impact",
  source: { generator, generator_version, schema, ingested_from: "html"|"json" },
  project: { name, doe_strategy?, test_dir? },
  sim_params: { t_final, dt, drop_height, density, youngs_modulus, poisson_ratio,
                yield_stress, unit_system },
  parts: [ { part_id:int, name:str, group:str } ],
  findings: [ { severity:"CRITICAL"|"WARNING"|"INFO", title, detail, recommendation } ],
  summary: { ...kind별 글로벌 최악값 롤업... },
  cases: [ Case ],          # deep=1건, sphere=각도별, impact=면×위치별
}

Case = {
  case_key: str,            # deep="single" / sphere=run_folder|angle_name / impact=face+pos
  identity: {               # kind별 케이스 식별
    # sphere: angle{ name, roll, pitch, yaw, category }
    # impact: { face, pos_x, pos_y }
    # deep:   {}  (단건)
  },
  meta: { num_states?, tier?, success? },
  parts_metrics: { "<pid>": {
      peak_stress, time_of_peak_stress?, peak_strain, peak_disp, peak_g?,
      safety_factor?, peak_principal?, min_principal?, peak_vm_strain?,
      energy?: { peak_ie, peak_ke, final_ie, final_ke },
  } },
  series?: { ... }          # 고해상도(선택) — DB 아닌 저장파일로
}
```

deep 전용 확장: `case.glstat`(에너지 시계열), `case.contact_metrics`(Newton-3/timing/sliding),
`case.energy_flow`(load path 그래프). sphere 전용: `summary.angular_spacing_deg`, `sphere_coverage`.
impact 전용: (분석 확인 후 확정) face×position transfer map, severity/verdict.

## DB 스키마 (Postgres, models.py 에 additive)
- **impact_reports** (스터디 1건)
  id(ULID) · session_id(FK) · user_id(FK) · kind · label · source_file_id(업로드 HTML의 SessionFile)
  · generator · generator_version · schema_str · project_name · doe_strategy · test_dir
  · sim_params(JSONB) · parts(JSONB) · findings(JSONB) · summary(JSONB) · payload_ref(정규화 JSON 저장경로)
  · created_at
- **impact_cases** (케이스 N)
  id · report_id(FK) · case_key · kind · identity(JSONB) · num_states · tier · success
  · parts_metrics(JSONB) · 랭킹용 승격컬럼: max_stress · min_safety_factor · max_g · max_disp
  (승격컬럼으로 SQL 정렬/필터 → MCP 최악케이스 질의가 싸다)

전체 정규화 payload(고해상도 시계열 포함)는 SessionFile(kind="report-json")로 저장, DB엔 요약+케이스만.

## API (신규 reports 모듈, /api/v1)
- `POST /sessions/{sid}/reports` — multipart(HTML 필수, 사이드카 JSON 선택, kind 힌트 선택)
  → 파싱·정규화·저장 → 스터디 요약 반환. **"HTML 을 받는 API".**
- `GET  /sessions/{sid}/reports` — 목록
- `GET  /reports/{rid}` — 스터디 요약(kind·project·sim_params·글로벌 최악·findings·parts)
- `GET  /reports/{rid}/cases?sort=max_stress&order=desc&limit=` — 랭킹된 케이스
- `GET  /reports/{rid}/cases/{case_key}` — 케이스 상세(+선택 시계열)
- `GET  /reports/{rid}/parts/{pid}` — 파트 관통 분석(최악 각도/위치·안전율·시계열)
- `GET  /reports/{rid}/findings?severity=` — 위험 소견
- `POST /reports/{rid}/publish-datahub` — 구조화 요약을 AIDataHub sim-result 로 등재(eng_meta 연계)
- `DELETE /reports/{rid}`

## MCP 분석 도구 (비카탈로그 신규 도구; inspect_file 과 동급)
- `ingest_report(html, kind?)` → report_id + 요약
- `list_reports(session?)`
- `report_summary(report_id)` → kind·project·sim_params·글로벌 최악·findings 요약
- `report_worst_cases(report_id, metric=peak_stress|peak_g|safety_factor, top_n)`
  → sphere: 최악 방향, impact: 최악 위치, deep: 최악 파트
- `report_part_risk(report_id, part_id?)` → 파트별 최악값 + 발생 각도/위치 + 안전율
- `report_findings(report_id, severity?)`
- `report_case(report_id, case_key)`
- `report_energy_flow(report_id, case_key?)` — load path(deep/contact)
- `compare_reports(report_ids[], part_id?)` — federate 식 리비전 비교
- `report_directional(report_id, part_id)` — 방향 취약도(sphere)

## 단계 / 검증
1. **파서 라이브러리** — HTML 에서 `const DATA` 추출 + deep/sphere/impact 정규화.
   → verify: 실제 샘플(single_report/report.html, Test_001/005/006_report.html, impact 골든)로 유닛테스트.
2. **DB + reports 모듈** — 테이블 2종 + 인제스트 엔드포인트 + 목록/상세/케이스/파트/findings.
   → verify: 실제 HTML 업로드 → 케이스 수·최악값이 리포트 원본과 일치.
3. **MCP 분석 도구** — 위 도구군.
   → verify: MCP tools/list 노출 + 실제 report_id 로 최악케이스/파트리스크 호출.
4. **AIDataHub 등재** — sim-result 레코드 + eng_meta(과제/개발단계/BOM) 연계.
   → verify: 업로드 후 DataHub 검색에 노출.
5. **(선택) 웹 UI** — 리포트 목록·요약·최악케이스 표 + 원본 HTML iframe.

## 절대 제약
- 기준 C++ 빌드/Windows CLI 에 지장 없음(이 작업은 platform/ 백엔드·MCP·프론트에만; C++ 무관).
- SmartTwinPostprocessor 리포트 생성기는 **읽기 전용 참조만**, 수정 안 함.
- 개수/스키마 하드코딩 금지(파서는 schema 문자열 2종·null·비연속 파트ID 방어).
