# Plan — 리포트에 있는데 플랫폼이 버리는 것을 전부 살린다

요청: 사용자 지시 2026-10-13 — "플랫폼 파서에 리포트에 있는 것 중 없는 것들 다 만들어야 해"
발단: "핫스팟 클러스터 관련은 들어있나" → 생성기에는 있고 **플랫폼이 버리고 있었다.**

---

## 1. 실측 — 무엇이 버려지는가 (짐작이 아니라 전수 조사)

실제 리포트 6개의 임베드 `DATA` 최상위 키를 뽑고, `parser.py` 가 **원본에서 읽는**
키(`data.get("…")` 전수)와 차집합을 냈다.

| kind | 최상위 키 | 읽는 키 | **버려지는 키** |
|---|---|---|---|
| `sphere` | 12 | 12 | **0** |
| `deep` | 21 | 10 | **11** |
| `impact` | 27 | 9 | **18** |

### deep 에서 버려지는 11

`hotspot`(★군집 102건) · `peak_element_tensors`(★응력 텐서 sxx..szx) ·
`max_principal` · `min_principal` · `max_principal_strain` · `min_principal_strain` ·
`strain` · `element_quality` · `vm_strain` · `renders` · `label`

⚠ `part_series` 가 `data.get("stress")` **하나만** 읽는다 — 그래서 주응력·주변형·변형 시계열이
전부 끊긴다. 피크값은 `parts[].peak_max_principal` 로 살아 있지만 **시계열이 없다.**

### impact 에서 버려지는 18

`clusters`(★거동 아키타입 군집) · `deep_analytics`(anomaly/fft/pca_modal/safe_drop_zone) ·
`doe_analysis`(grid·peak_g_matrix·behavior_class_counts…) ·
`insights`(ContactPulse·DamageIndex·ReboundField·Symmetry·Trajectory3D) ·
`physics`(RestitutionMap·StressWaveVelocity·worst_combinations…) ·
`part_motion` · `trajectories` · `positions` · `faces` · `contact_profile` ·
`impactor_mesh` · `device_geometry` · `set_report` · `solver_quality` ·
`energy_flow_max_ie` · `energy_flow_thresholds` · `energy_conservation_tolerance` · `risk_score`

## 2. 설계 — 29개를 하나씩 포팅하지 않는다

★원본 HTML 은 **이미 보관된다**(`ImpactReport.source_file_id` — "온디맨드 시계열 재파싱용").
`/energy`·`/geometry`·`/cases/{k}/series` 가 이미 그 길로 돈다. 그러면 할 일은 포팅이 아니라
**그 길을 일반화**하는 것이다.

### 2-1. 일반 블록 접근 — 버려지는 것이 **구조적으로 불가능**해진다

    GET /reports/{id}/blocks            → 임베드 블록 목록(이름·형태·크기·읽히는지)
    GET /reports/{id}/blocks/{name}     → 그 블록(`path=` 로 하위 선택, 크기 가드)

키를 하나 더 추가하는 생성기 변경이 있어도 **코드를 안 고쳐도 보인다.** 지금 방식(정규화가
아는 키만 통과)은 생성기가 늘 때마다 조용히 뒤처진다 — 이번 일이 정확히 그것이다.

### 2-2. 높은 값은 **일급**으로 — 핫스팟·군집

일반 접근만 두면 "있긴 한데 쓰기 어렵다" 가 된다. 둘은 정규화 형태와 전용 엔드포인트를 준다.

    GET /reports/{id}/hotspots          # deep — 파트·판정기준별 군집(bbox·반경·요소수·응력)
    GET /reports/{id}/clusters          # impact — 거동 아키타입(라벨·특징·대표)

### 2-3. 시계열 비대칭을 고친다

`part_series` 가 `stress` 만 읽는 것을 `stress`·`strain`·`max_principal`·`min_principal`·
`max_principal_strain`·`min_principal_strain`·`vm_strain` 전부로 넓힌다. 같은 모양의 배열이라
한 줄짜리 목록 변경이다.

## 2-4. 큰 분석 블록은 **해석해서** 낸다 (사용자 지시 2026-10-13)

일반 접근만으로는 `doe_analysis`(하위 203키)·`deep_analytics`(142)·`insights`(93)·
`physics`(87) 를 "꺼낼 수는 있지만 쓸 수는 없는" 상태로 둔다. 그래서 블록마다 **요약 + 질의**를
얹는다 — 원본은 그대로 꺼낼 수 있게 두고, 그 위에 '무엇이 들어 있나/무엇이 최악인가' 를 낸다.

| 블록 | 요약해서 낼 것 |
|---|---|
| `doe_analysis` | 격자 모양·지표 목록 · `peak_g_matrix` 최악 셀 · `behavior_class_counts` |
| `deep_analytics` | `anomaly_detection` 이상치 목록 · `fft` 주요 주파수 · `pca_modal` 기여율 · `safe_drop_zone` 경계 |
| `insights` | `DamageIndex`·`ReboundField`·`Symmetry`·`ContactPulse` 지표와 상위/하위 |
| `physics` | `RestitutionMap`·`StressWaveVelocity`·`RecoveryDamping`·`worst_combinations` |
| `solver_quality` | 위치별 품질 + 요약(수렴·에너지) |
| `trajectories`·`part_motion` | 케이스별 궤적 유무와 길이(원본은 블록으로) |

★원칙 — **요약이 원본을 가리지 않는다.** 요약은 `summary` 로, 원본은 같은 엔드포인트의
`raw=true` 또는 `/blocks/{name}` 으로. 요약이 틀렸을 때 원본으로 되짚을 수 있어야 한다.

## 2-5. ★결과 이미지 — LLM 이 **보고** 비교할 수 있게 (사용자 지시 2026-10-13)

실측: 결과 이미지는 임베드가 아니라 **사이드카 파일**이다.

  · impact : `impact_report_data/set_media/pos_<POS>_s0_peak.png` + `_view.mp4` (8+8, 200K)
  · deep   : `custom_report/set_reports/<zone>/peak_<view>_<field>.png` + `view_*.mp4`

그래서 **HTML 하나만 올리면 이미지는 애초에 플랫폼에 들어오지 않는다.** 그리고 들어와도
지금 MCP 는 base64 를 **dict 안에** 넣어 돌려주므로 Claude 에게는 **글자**로 온다 —
`ImageContent` 로 내는 길이 한 곳도 없다(실측). 둘 다 고쳐야 "이미지로 비교" 가 된다.

    1) 반입   : `/reports/intake` 가 **번들**(.zip/.tar.gz)을 받아 HTML + 사이드카를 함께 푼다.
                미디어는 SessionFile 로 저장하고 리포트·케이스에 **연결**한다.
                `set_report.media` 의 상대경로가 그 연결의 정본이다.
    2) 목록   : `GET /reports/{id}/media` — 케이스·뷰·물리량·종류(png/mp4)로 걸러 본다
    3) 보기   : MCP `report_image(report_id, case_key, …)` 가 **ImageContent** 로 돌려준다
                (Claude 가 png/jpeg/gif/webp 를 본다. SVG 는 못 본다 — 그래서 png 를 쓴다)
    4) 비교   : MCP `report_compare(report_id, case_keys[], metrics[])` 가 **이미지 N장 +
                지표 표**를 한 번에 돌려준다. 그러면 LLM 이 그림을 보면서 리포트를 쓸 수 있다.

★크기 규율 — 이미지는 응답을 금방 불린다(`TOOL_RESULT_MAX=6000`). 비교 도구는 **장수 상한**과
**축소**를 두고, 넘으면 '몇 장을 뺐다' 를 말한다(조용히 자르지 않는다).

## 3. 범위 밖(지금 안 한다)

- 생성기(SmartTwinPostprocessor) 변경 — 이미지를 **만드는** 쪽은 그대로 두고 **나르는** 길만 만든다
- 프런트 3D 뷰어 — 핫스팟·군집 표와 이미지 **갤러리**까지만
- mp4 를 LLM 에게 보여 주는 것(모델이 영상을 못 본다) — 대표 프레임 png 로 대신한다

## 4. 검증 기준

1. 실제 리포트 3종에서 **버려지는 키 0** (차집합 스크립트를 회귀로 고정)
2. 핫스팟 102군집·impact 군집이 엔드포인트로 **같은 수** 나온다
3. 시계열 7종이 다 나온다
4. 큰 블록(625행 `results`·49MB 리포트)에서 응답 크기 가드가 돈다
