# 체크리스트 — 컨택 그래프 · 전각도 핫스팟 · 세트 합치기 (10-23)

## 실측
- [x] 새 판 sphere 리포트를 운영 이미지로 만들었다(23키 · 안 읽힘 9 · 핫스팟 13항목/58군집 · 하중경로 24노드/22엣지 · contact_profile 22쌍)
- [x] 하중경로 압축 꼴 → 값 null(sphere · impact 둘 다 압축 꼴)
- [x] `*SET_PART_ADD` → 0쌍 · `*SET_SEGMENT_ADD` → 틀린 쌍 (2,3)(정답 (1,3)) — 대조 `*SET_PART_LIST` 는 맞다

## 1 — 조용히 틀린 값
- [x] 1-A `case_energy` 세 꼴(중립 · sphere 압축 · impact 압축 — impact 는 엣지 이름이 또 달랐다) · 다른 각도로 안 떨어짐 · flow_case_key · note → `f1520ba`
- [x] 1-B 세트 파서(memberSets · SEGMENT 방언 · _ADVANCED) + 정본 해석기 `set_members.h` → `234ad04`
- [x] 1-B modelmeta · contact(면 모으기 · 펼치기 · TIED 판정 · 목록 · 커버리지) · optimize 가 정본 해석기를 쓴다 · unresolved_detail
- [x] 1-B 단위 16(128) · 회귀 test_set_add_resolution · test_set_dialect B-1/B-3 뜻을 고쳤다 · contact 골든 불변
- [x] 1-C 새 판 sphere 고정본 `/data/koopark/report_fixtures/sphere_hotspot_v1018`(운영 이미지 · README) · `EXPECTED_UNREAD`(sphere_new={device_mesh, set_report} · impact 에서 contact_profile·positions 뺌)

## 2 — sphere 핫스팟
- [x] `hotspot_clusters` sphere 꼴 · 포락 · 각도 필터 · cap_note · compact_note → `f1520ba`
- [x] 새 키 읽기(unit_system · tool_builds · contact_profile · contact_trust · hotspot_parts · hotspot_mesh(_note) · hotspot_cap_note · energy_flows_note · positions) · pulse_* 평탄화
- [x] `contact_profile()` 전용 함수(sphere · impact)
- [x] API(/hotspots?case_key · /contact_profile) · MCP(report_contact_profile · 설명 셋) · TOOLS.md · SKILL.md · 도구 수 73(`d70ccc7`)

## 3 — 그림
- [x] 에너지·접촉 탭 — 하중경로 그래프(sphere · impact) → `9e8999f`
- [x] 접촉 전개 탭 — 히트맵 + 각도 그래프
- [x] 핫스팟 탭 sphere(포락 · 각도 칸)
- [x] ConnectivityView 행렬 보기(엣지 150↑ 기본) · 미해석 면 목록 · CID
- [x] 프런트 빌드 · Playwright 로 네 화면(새 판 sphere · impact · 61파트 덱 · ADD 세트 덱)

## 하다 나온 것(같은 접촉 경로)
- [x] optimize — `_ID` 접촉의 Card 3 SFSA 칸에 SOFT=0 을 쓰던 것(접촉 강성 0) · modelmeta `_ID` 제목/cid → `fe82dd3`
- [x] MCP 문서의 도구 수 72 → 73(카탈로그 대조 관문이 잡았다) → `d70ccc7`
- [x] `reports_smoke` 가 새 도구를 한 번도 안 불렀다(24/24 초록) — 값으로 재는 11항을 더했다(35/35) → `ab19ef9`

## 관문 · 배포
- [x] 관문(릴리스 바이너리 `252bd444`) — 단위 128 · 회귀 100/100 · 도움말 예제 · 카탈로그 대조 · 백엔드 619 · 덱 바이트(다른 것 둘은 리포트 JSON 의 임시 폴더 경로뿐)
- [x] compat 빌드(GLIBC_2.35) · `cli.sif` · API 재기동 · MCP(도구 73) · 프런트 빌드
- [x] Drive `dist-20261023-115800Z` · health `revision_matches_binary=True`(소스 `9e8999f`)
- [x] 스모크 — smoke(op 63 · 도구 73) · reports 35/35 · figures 20/20 · deckops 21/21
- [x] 화면 확인용 임시 사용자 · 세션 · 리포트 둘 · 파일 넷 · 저장 폴더 지움(남은 것 0)
- [ ] SmartTwinPreprocessor.sif 굽기 — 자동 모드 분류기가 「Production Deploy」로 막았다 → 사용자 실행 대기
- [ ] 그 뒤 `/opt/apptainers` 사본 · 계산노드(`deploy_apptainers.sh --image`) · 노드에서 sha · SmartTwinMCP 에 알림
