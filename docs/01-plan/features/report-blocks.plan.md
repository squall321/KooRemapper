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

## 3. 범위 밖(지금 안 한다)

- 블록 **내용의 의미**를 해석하는 분석(예: `pca_modal` 의 모드를 그려 주는 화면)
- 생성기(SmartTwinPostprocessor) 변경
- 프런트는 핫스팟·군집 **표**까지만 — 3D 그림은 별건

## 4. 검증 기준

1. 실제 리포트 3종에서 **버려지는 키 0** (차집합 스크립트를 회귀로 고정)
2. 핫스팟 102군집·impact 군집이 엔드포인트로 **같은 수** 나온다
3. 시계열 7종이 다 나온다
4. 큰 블록(625행 `results`·49MB 리포트)에서 응답 크기 가드가 돈다
