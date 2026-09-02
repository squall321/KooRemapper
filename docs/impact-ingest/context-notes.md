# Context Notes — 충격 리포트 인제스트

작업 중 내려진 결정과 근거를 계속 덧붙인다.

## 2026-08-15 — 착수 결정
- **호스팅=DynaForge**: FastAPI/MCP/PAT(HEAX SSO)/Postgres(JSONB)/sessions·files/DataHub 업로더가
  이미 있어 "업로드→파싱→저장→MCP 질의"가 기존 K파일 inspect/modelmeta 흐름과 동형. SmartTwinMCP 는
  script.sh 카탈로그형이라 DB·HTML 인제스트 API·웹을 새로 얹어야 해 중복. → SmartTwin=생성, DynaForge=수용.
- **저장소=Postgres+DataHub**: 사용자 "레포트가 데이터로 올라갈 수 있을거야" + 이번 세션에 만든 cae
  attachment/eng_meta/kr2datahub 재사용. Postgres 는 작업/랭킹 질의/ MCP 분석용, DataHub 는 durable 데이터 자산.
- **HTML-only 성립**: deep/sphere HTML 이 `const DATA={…}` 순수 JSON 임베드. json.loads 가능.
  → 사이드카(result.json/report.json/impact_payload.json)는 선택적 고해상도 보강으로만.

## 왜 케이스를 별도 테이블로 두나
- sphere 는 각도 N개(최대 1146), impact 는 면×위치 다수. MCP "최악 방향/위치 top_n" 질의를 SQL 정렬로
  싸게 하려면 케이스별 승격컬럼(max_stress/min_safety_factor/max_g)이 필요. JSONB 만이면 랭킹이 비쌈.
- 고해상도 시계열은 DB 부적합 → 정규화 JSON 파일(SessionFile)로 빼고 DB엔 요약+케이스 메트릭만.

## 파서 방어 항목 (에이전트 분석 근거)
- schema 문자열 2종: `single_analyzer/1.0` ∨ `koo_deep_report/1.0` (batch_report 는 후자만 허용).
- parts 키=문자열 파트ID, 비연속. 이름 리터럴 백슬래시/공백 → 폴백 `Part_<id>`.
- analysis_result.json 의 *_history 는 디스크서 잘림(head10+tail10). 완전 시계열은 HTML DATA(≤500pt) 또는
  peak_element_tensors/motion CSV. → 인제스트는 HTML DATA 우선.
- null=미측정(≠0) 보존: normal_termination/energy_ratio_min/safety_factor/glstat 등.
- unit_system: sphere loader 는 deck *MAT density 로 단위 감지(ton-mm-s 기본), G_FACTOR=9810. HTML DATA 엔
  이미 반영된 값이 들어옴(peak_g 등). 재계산 말고 임베드값 사용.

## 키 시그니처 (kind 자동판별)
- deep 마커 `const DATA = {…}`. keys: sim, label, yield_stress, summary, parts, stress, strain,
  max/min_principal(_strain), peak_element_tensors, motion, glstat, binout, renders, element_quality, metadata.
  parts[pid]={name,peak_stress,time_of_peak_stress,peak_element_id,peak_strain,peak_max/min_principal,
  peak_max/min_principal_strain,peak_disp_mag,peak_vel_mag,peak_acc_mag,safety_factor}.
- sphere 마커 `const REPORT_DATA = {…}`. keys: project_name, doe_strategy, total_runs, successful_runs,
  failed_runs, angular_spacing_deg, sphere_coverage, yield_stress, sim_params, findings, parts, results.
  results[i]={folder,angle{name,roll,pitch,yaw,category,swap},num_states,parts}; parts[pid]에 peak_stress/
  peak_strain/peak_g/peak_disp + stress_ts/strain_ts/g_ts/disp_ts(다운샘플).
- impact 마커 `const DATA = {…}`(대형은 deferred `<script type=application/json id=koo-data>`, chunked 는 분할→불완전).
  keys: meta,kpi,faces,parts,positions,contact_profile,results,energy_flows,findings,doe_analysis,
  part_motion,trajectories,clusters,solver_quality,… 사이드카 impact_payload.json={schema_version,generated_by,payload}
  이고 payload==const DATA. results[]는 평탄행 {face,pos_id,x,y,part_id,g,s,e,d[,s1,s3,e1,e3,evm],part_name}.
  케이스=pos_id(충격위치). 메트릭 약어 g/s/e/d=peak_g/stress/strain/disp.
- 판별 순서: impact(generated_by==koo_impact_report ∨ positions+results ∨ faces+doe_analysis) →
  sphere(results+sphere_coverage/angular_spacing_deg) → deep(peak_element_tensors ∨ sim+glstat).
  impact 를 sphere 보다 먼저(둘 다 `results` 보유).

## Phase 1·2 완료 (검증)
- 파서 app/reports/parser.py: 실제 생성 HTML 3종 유닛테스트 5개 통과(test_report_parser.py).
- DB models.py: impact_reports/impact_cases + alembic 0002 적용(dev postgres). reports 모듈
  (services/routes/schemas) + /api/v1 등록. E2E 3종 통과(test_reports_ingest.py). 전체 52 passed.
- 원본 HTML 은 SessionFile(kind="report", meta={report:True}) 로 저장(kfile inspect 안 함) — 온디맨드
  시계열 재파싱 소스. 케이스 승격컬럼(max_stress/max_g/max_disp/min_safety_factor)로 SQL 랭킹.

## 미확정 / 후속
- impact chunked(tier D) 임베드: 단일 HTML만으론 시계열 분할 복원 불가 — 케이스 비면 400. 필요 시
  chunk .js 동반 업로드 지원 추가(현재 범위 밖).
- 고해상도 시계열(stress_ts/motion/glstat/peak_element_tensors)은 DB 미저장 — report_case/energy_flow
  도구가 원본 HTML(source_file_id)을 재파싱해 제공(Phase 3에서 parse_series 헬퍼 추가 예정).
- federate(리비전 비교)는 compare_reports MCP 로 v1 포함, 별도 kind 아님.

## Phase 4 완료 + 범용 forge 방향 (사용자 지침)
- 사용자: "여러 시뮬레이션에 대한 forge를 만들거야", "툴마다 포지를 만들거니까 데이터 허브에
  양식을 넣을 때 참고로 해" → DataHub 등재 양식을 **모든 forge 공용 sim_report 템플릿**으로 고정.
  표준 문서: docs/impact-ingest/datahub-sim-report-schema.md.
- 구현: app/reports/datahub.py (build_record/publish), POST /reports/{id}/publish-datahub,
  MCP publish_report_to_datahub. config.datahub_url(기본 127.0.0.1:8001, 호스트넷 공유라 도달 OK).
- AIDataHub 함정(실측):
  · /api/records limit 최대 100 (200→422). next_sim_id 는 (team,group,year) 접두 max+1.
  · bundle 은 record.id 필수(서버 자동부여 아님), 첨부 file_path 는 zip 내 경로와 일치해야.
  · SimContent.eng_meta.doe = DoeRef(extra 금지): study(필수)/case/factors 만. 전략은 factors 에.
  · SimContent 정의外 content 키(sim_domain/report_kind)는 정규화서 유실 → inputs/tags/첨부 extra 로 이중화.
- E2E 검증: sphere 리포트 publish → SIM-MX-CAE-... 생성, 판별자 3곳 생존, eng_meta.doe 정상,
  components 23·첨부 1·worst_cases. 스모크 레코드 정리 완료. 유닛 test_report_datahub 3개 + 전체 55 passed.

## Phase 6 — forge 심화 (사용자: "B. 현재 forge 심화")
- report_directional: 방향 범주별(sphere 면/엣지/코너, impact F1~F6) 최악 응력·G. DB(케이스)만으로 계산.
  실측: cuboid_26 → edge 12케이스 최악 1046.2 > face 6 최악 661.6 > corner 8 최악 579.5(엣지가 최악방향).
- report_energy_flow: 원본 HTML 재파싱. deep=glstat 에너지밸런스(energy_ratio_min/hourglass)+rcforc 접촉력+
  contact_metrics(Newton-3), sphere/impact=energy_flows[case] 하중경로 그래프(있으면; 샘플엔 비어 note).
- report_part_series: 케이스·파트 시계열(다운샘플) 재파싱 — 응력/변형률/G/변위.
- 파서 추가: case_energy/part_series (app/reports/parser.py). services: directional/case_energy/part_series
  + _load_html_data(원본 재파싱 헬퍼). routes: /directional /energy /cases/{key}/series.
- MCP 35종(신규 report_directional/report_energy_flow/report_part_series). 유닛+E2E 57 passed. 라이브 검증.
- 남은 후속: impact chunked(tier D, 데이터 분할→다중파일 필요) 미지원(문서화).

## 방향 섭동 산포(scatter) 분석 — sphere 도출 (사용자: "26면 주변 퍼터베이션")
- 외부 scatter 리포트 생성기는 없음(리포트 4종뿐). DynaForge 가 sphere 케이스에서 도출(경로 B).
- report_scatter: 케이스를 최근접 26 정준방향(면6·엣지12·코너8)으로 묶어 방향별 metric
  산포(n·mean·std·CoV·min·max·최악) + most_severe/most_scattered. metric∈peak_stress/g/disp.
- 프레임 정합 실측 검증: cuboid_26 26케이스 → 26 정준방향 1:1, 카테고리 100% 일치(면 0°, 최대 9.7°).
  euler→벡터는 sphere 리포트 규약 그대로(lon=pitch,lat=roll[+swap], v=(coslat·coslon,coslat·sinlon,sinlat)).
  swap 필요 → scatter 는 원본 재파싱(authoritative angle).
- degenerate: 방향당 표본 1개(순수 26면)면 산포 0 → note. 조밀/섭동 DOE 라야 의미.
  실측 Test_006(1146): non-degenerate, peak_g 최악 corner mean 304k, 최대산포 face CoV 1.15(75k→1.34M).
- MCP 36종. REST /reports/{id}/scatter?metric=&part_id=. 파서 scatter_analysis(순수함수).

## 26방향 스캐터 — 생성 경로 확인 + 런처 (사용자 "다 되게 하자")
- scenario.json 에 이미 존재: angle_source.cuboid_geometry(6F+12E+8C=26방향) + tolerance
  (roll/pitch/yaw ±범위, doe_count, doe_type lhs/full_factorial/random). **방향마다** 적용.
- 실측(KooChainRun prepare, LS-DYNA 불필요): cuboid+tolerance(doe_count=5) → doe_angles=130=26×5.
  각 기준방향 F1_Back_DOE001~005 처럼 ±2° 흩뿌림. 사용자 주장(26방향 스캐터 옵션 있음)이 맞음.
- 런처 공백 해소: SmartTwinMCP 에 cuboid_scatter_drop_simulation 툴 신규(feat/cuboid-scatter-drop).
  scenario_builder.build_cuboid_scatter_scenario. dry-run 130run 검증, 카탈로그 0-issue 등록.
- 전체 루프: cuboid_scatter_drop_simulation(런치) → KooChainRun → sphere_report → DynaForge
  인제스트 → report_scatter(26방향 산포/민감도). 실제 LS-DYNA run 만 남음(수 시간, 별도 승인).
- report_scatter 프레임은 sphere 리포트(후처리) 각도 기준 검증됨(Test_001/006). runner_config raw
  각도는 리포트 이전 규약이라 다름 — report_scatter 는 리포트를 소비하므로 무관.

## 공간 시각화(2dfcb23) — 부품 위치·낙하방향 맵
- 요구: 리스크 부품이 어디인지 이미지로 보여주고, 전각도 낙하/충격위치를 찍고 값을 표시. 확정 범위=웹 리포트 상세 SVG + bbox 개략도.
- 백엔드: parser.extract_geometry(impact 만 outline·bbox·파트 footprint 반환, sphere/deep 는 빈 지오메트리), services.geometry, GET /reports/{id}/geometry, MCP report_geometry. 순수 additive 57줄.
- 프런트: ReportVisuals.tsx. sphere=등장방형 pitch×roll 방향맵(각 방향 값 히트·최악 링+라벨), impact=디바이스맵(외곽선+선택 파트 footprint 초록+충격위치 값 마커). 값은 report_query(part_id×metric fact) 서버필터로 채움. deep 은 단건이라 마커 없음(원본 렌더 안내).
- 실측 검증: impact 샘플 ingest → geometry(bbox -50..50/-40..40, outline 4pt, 12파트 전부 footprint 4pt), query(peak_stress 50 fact, identity=face/pos_x/pos_y). 합성샘플은 pos 가 전부 0,0 이라 impact 점이 원점에 겹침(데이터 아티팩트, 코드 아님). 실제 리포트는 위치 분산됨.
- 테스트 78 passed(+2 geometry). 프런트 tsc+vite 빌드 clean. dev 인스턴스 api/mcp 재기동으로 라우트·툴(47개) 반영. Drive 배포는 아직(다음 build-all-to-drive 필요).
