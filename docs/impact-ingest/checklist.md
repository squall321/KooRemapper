# 체크리스트 — 충격 리포트 인제스트 & MCP 분석

## Phase 0 — 현황 분석
- [x] 리포트 4종(deep/sphere/impact/federate) 정체·관계 파악
- [x] deep 데이터 모델(result.json / analysis_result.json / HTML DATA) 확정
- [x] sphere 데이터 모델(report.json / HTML DATA / loader 레이아웃) 확정
- [x] HTML 자기완결(임베드 const DATA) 확인 — HTML-only API 성립
- [x] 플랫폼 인제스트 지점(models.py·sessions·MCP·storage) 확인
- [x] 갈림길 3종 사용자 확인(DynaForge/Postgres+DataHub/3종동시)
- [x] impact 데이터 모델(impact_payload.json / HTML DATA / face×pos 레이아웃) 확정  ← 분석 중

## Phase 1 — 파서 라이브러리 (platform/backend/app/reports/parser.py + core)
- [x] HTML 에서 `const DATA = {…}` 블롭 추출기(중괄호 밸런싱, 두 마커 대응)
- [x] deep 정규화 → NormalizedStudy(kind=deep, cases=1)
- [x] sphere 정규화 → NormalizedStudy(kind=sphere, cases=각도별)
- [x] impact 정규화 → NormalizedStudy(kind=impact, cases=면×위치)
- [x] kind 자동판별(임베드 키 시그니처 기반) + 힌트 override
- [x] 스키마 함정 방어(문자열 파트ID·비연속·백슬래시 이름·null·schema 2종)
- [x] 유닛테스트: 실제 샘플로 케이스수·최악값 검증
      · deep: single_report/report.html
      · sphere: koo_sphere_report/examples/Test_001/005/006_report.html
      · impact: 골든 픽스처(generate_sample.py 산출)

## Phase 2 — DB + reports 모듈
- [x] models.py: impact_reports · impact_cases 테이블(additive)
- [x] 마이그레이션/스키마 생성 반영
- [x] reports/services.py: 인제스트(파싱→정규화→저장), 조회
- [x] reports/routes.py: POST reports · list · get · cases · parts · findings · delete
- [x] reports/schemas.py: Pydantic 응답 모델
- [x] modules/__init__.py 라우터 등록
- [x] 정규화 JSON 을 SessionFile(kind=report-json)로 저장, HTML 은 kind=report
- [x] verify: 실제 HTML 업로드 → 케이스수·최악값이 원본 일치

## Phase 3 — MCP 분석 도구
- [x] server.py 비카탈로그 도구: ingest_report·list_reports·report_summary
- [x] report_worst_cases·report_part_risk·report_findings·report_case
- [x] report_energy_flow·compare_reports·report_directional·report_part_series (Phase6 심화)
- [x] TOOLS.md/SKILL.md 갱신(개수 하드코딩 금지)
- [x] verify: MCP tools/list 노출 + 실제 report_id 로 호출

## Phase 4 — AIDataHub 등재
- [x] publish-datahub 엔드포인트(sim-result 레코드 + eng_meta 과제/개발단계/BOM)
- [x] kr2datahub 계열 업로더 확장 재사용
- [x] verify: DataHub 검색 노출

## Phase 5 — 웹 UI
- [x] 리포트 목록·요약·최악케이스 표 + 원본 HTML iframe + DataHub 등재 폼

## 배포/무회귀
- [x] 계약 테스트 통과 유지
- [x] C++ 빌드/Windows CLI 무영향(변경은 platform/ 한정)
- [x] build_linux_compat → SIF → restart-api-only/mcp 라이브 반영
- [ ] 커밋(feat)·main ff-merge·push
