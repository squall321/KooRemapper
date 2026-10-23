# 컨택 그래프 · 전각도 핫스팟 · 세트 합치기 — 1·2·3 (2026-10-23)

**날짜** 2026-10-23 · **요청** 「파트간의 컨택 관계로 그래프를 그리는게 가능한지와 전각도 낙하 데이터가 핫스팟 클러스터 기능까지도
다 올라오고 조회도 되는지」 → 조사 답의 선택지 1·2·3 을 「꼼꼼히」(사용자 10-23)

## 왜 — 실측
- **sphere 생성기가 플랫폼보다 앞서 있다.** 운영 이미지(`/opt/apptainers/SmartTwinPostprocessor.sif`, 10-18)로 실제 런
  (`/data/koopark/Test_HotspotKeys_v118`, analyzer be9d2b0)을 돌린 새 판 리포트는 최상위 23키 중 9개를 플랫폼이 안 읽는다
  (`contact_profile`·`contact_trust`·`device_mesh`·`energy_flows_note`·`hotspot_mesh_note`·`hotspot_parts`·`set_report`·
  `tool_builds`·`unit_system`). 이 박스의 sphere 고정본은 전부 옛 판(12키)이라 관문이 초록이다.
- **하중경로 값이 null 이다** — sphere·impact 모두. HTML 은 압축 꼴(`pf`·`tw`·`ti`·`ke_init`·노드 `id`)인데 `case_energy` 는
  중립 꼴 이름(`peak_force`·`impactor_ke_initial`·`node_id`)만 읽는다. 게다가 요청한 각도에 상세가 없으면 **다른 각도의 흐름을
  그 각도 이름으로** 돌려준다(첫 흐름으로 떨어진다).
- **sphere 핫스팟을 조회할 수 없다** — `/hotspots` 는 deep 꼴(최상위 `hotspot`)만 안다. sphere 는 각도 런마다 `results[i].hotspot`
  (압축 키 p·cr·et·cl[c,r,k,n,s,e,w,wd,t])에 싣는다.
- **세트 합치기가 조용히 틀린다**(C++ 공용 세트 파서). `*SET_PART_ADD` 를 가리키는 접촉 → 0쌍 · unresolved 0.
  `*SET_SEGMENT_ADD` 는 멤버 세트 id 를 **절점 번호로** 읽어 엉뚱한 파트쌍을 낸다(재현: 정답 (1,3) 대신 (2,3)).
  같은 조회를 contact(면 모으기·세그먼트 펼치기)·optimize(대상 파트 판정)도 한다.

## 범위
### 1 — 조용히 틀린 값
- **1-A 하중경로 읽기** — `case_energy` 가 중립·압축 두 꼴을 다 읽는다(sphere·impact). 압축 꼴에 없는 값(원해상도 피크 ·
  confidence · first_engage_t · 전파 순서)은 **다시 재지 않고** null + 까닭. 요청한 케이스에 상세가 없으면 null + 까닭(다른 각도로
  떨어지지 않는다) · 실제로 쓴 케이스 키를 적는다 · `energy_flows_note` 를 싣는다.
- **1-B 세트 합치기(C++)** — 파서가 `_ADD`·`_INTERSECT` 멤버를 **세트 id 목록으로 따로** 든다(`ids` 는 비운 채 — 닫히는 쪽 유지) ·
  SEGMENT 방언이 멤버를 세그먼트로 읽지 않는다 · 정본 해석기 하나(`_ADD` 합집합 · PSID 음수 범위 · 없는 세트 무시 · 재귀 ·
  순환 가드 · `_INTERSECT` 교집합 · `_GENERAL`/`_ADVANCED` 는 미해석으로 센다) → modelmeta · contact · optimize 가 쓴다.
- **1-C 회귀 고정본** — 운영 이미지로 만든 새 판 sphere 리포트를 고정본으로(출처 기록). `EXPECTED_UNREAD` 를 의식해서 고친다.

### 2 — sphere 핫스팟 일급 조회
- `hotspot_clusters` 가 sphere 꼴을 읽는다 — deep 과 같은 평탄 목록 + 각도(case_key · 이름 · roll/pitch/yaw) ·
  **포락**(파트 × 기준마다 가장 센 각도 · 그 값 · 군집이 난 각도 수) · 각도 필터 · 생성기 상한 문구(`hotspot_cap_note`) ·
  압축본에 없는 값(부피·평균응력·피크요소)은 지어내지 않는다.
- 새 키 읽기 — `unit_system`·`tool_builds`(정규화 요약) · `contact_profile`·`contact_trust`(전용 함수) · `hotspot_parts`·
  `hotspot_mesh_note`(핫스팟 응답) · `energy_flows_note`(하중경로 응답). 화면 전용 `device_mesh` 와 `set_report` 는 까닭을 적고 남긴다.
- API(`/hotspots?case_key=` · `/contact_profile`) · MCP(`report_hotspots` 설명 · `report_contact_profile`) · 문서 쓸기.

### 3 — 그림
- **결과 기준 접촉 그래프** — 「에너지·접촉」 탭이 sphere·impact 의 하중경로를 그린다(층 배치 · 엣지 굵기 = 피크 접촉력) ·
  새 탭 「접촉 전개」 — 파트쌍 × 각도(위치) 히트맵(pf/ti/tw) · 칸을 누르면 그 각도의 그래프.
- **덱 연결도 행렬 보기** — ConnectivityView 에 그래프/행렬 전환(엣지가 많으면 행렬이 기본) · 미해석 접촉 면 수를 보인다.
- 핫스팟 탭이 sphere 를 그린다(포락 표 + 각도 칸).

## 바꾸지 않는 것
deep 핫스팟 응답 꼴 · 옛 판 sphere 리포트의 결과 · DB 스키마(원본 HTML 재파싱으로 푼다) · 생성기.

## 검증
- C++ — 단위(해석기: ADD · 범위 · 재귀 · 순환 · INTERSECT · 미해석) · 회귀(modelmeta·contact·optimize 에 ADD 덱 · 옛 결과 불변 ·
  contact 골든) · 관문 전부.
- backend — 압축/중립 하중경로 · 다른 각도로 안 떨어짐 · sphere 핫스팟 실데이터(13항목 · 58군집) · 포락 · contact_profile
  (sphere 22쌍 · impact) · 새 키 0 안 읽힘 · API(실 DB 반입) · MCP 스모크.
- 프런트 — 빌드 0 오류 · Playwright 로 네 화면을 실제로 본다.

## 배포
C++ 가 바뀌므로 사슬 전부 — compat 빌드 · 관문 · Drive · API/MCP · 프런트 빌드 · SmartTwinPreprocessor.sif 굽기와 사본.
