# DF 2차 ⑤ — 캠페인 분석(DF-05 · 06 · 08 · 09 · 10 · 11 · 12) 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-05 · 06 · 08 ~ 12 이고 설계안 `df-request-1117.design.md` 의 ⑤ 단계다. 체크리스트
`df-campaign-analysis-1122.checklist.md` · 맥락 `df-campaign-analysis-1122.context-notes.md`. 요청서의 검증 사례(과제 이름 · 경로 · 각도 수)는
옮기지 않는다 — 같은 꼴의 합성 사례로 잰다. 요청서가 말하는 대조 파일(각도 표 · 피크 표 · 격자 스크립트 · 자리 결과 · 쌍 판정)은 이 박스에
없다 — 대조는 사용자가 cae00 에서 한다(11-22 「검증런을 cae00에서 돌릴게」).

## 0. 받은 결정(사용자 11-21 · 11-22)
- 이름표 — 설계안 3절 그대로(11-21 「표 그대로 승인」). 표에 없던 쓰기 길 둘(기준값 · 자리 표)과 읽기 경로 하나(파트 짝 표 읽기)는 7절에 적는다.
- 차례 · 확인(11-22 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」) — 멈춰 확인받지 않고 짓는다. 고른 읽기는 7절에 모아 보고에서
  알린다.
- 받는 꼴(②③ 과 같은 규칙) — 요청서 표대로 세우고 만드는 쪽의 실제 꼴이 오면 맞춘다. 모르는 열쇠는 422.
- footprint(11-21 「생성기에 청하고 기다린다」) — 자리 지도는 받은 footprint 가 실측이라고 말하지 않으면 「합성」 표지와 경고를 싣는다.

## 1. 짓는 것(MCP 100 → 117 · 마이그레이션 `0025_campaign_analysis` 하나)
| 겉 | 이름 | 하는 일 |
|---|---|---|
| ⑤-1 쓰기 | `PUT /campaigns/{id}/part-groups` · `set_campaign_part_groups` | 부품 무리(`group_key` · `label` · `part_ids` · `part_key`)를 통째로 바꾼다 |
| ⑤-1 받기(고침) | `POST /campaigns/{id}/runs` · `ingest_campaign_manifest` | 런마다 `impacts`(충격 구간 — `index` · `t_start_ms` · `t_end_ms` · `ke_frac` · 무리별 `peaks`)를 더 받는다 |
| ⑤-1 읽기 | `GET /campaigns/{id}/angle-table` · `campaign_angle_table` | 각도마다 방향 벡터 · 범주 · 라벨 · 충격 횟수 · 두 번째 충격 시각 · 첫 KE · 무리별 피크 · 피크 시각 · 충격 차수 |
| ⑤-1 읽기 | `GET /campaigns/{id}/angle-stats` · `campaign_angle_stats` | n · 제외 수(`excluded_ke_jump` 따로) · 다회 충격 비율 · 무리별 분포 · 상위 · 하위 10 · 범주별 · 라벨별 · 덮임 |
| ⑤-1 읽기 | `GET /campaigns/{id}/peaks` · `campaign_peak_table` | 피크 표(각도 × 무리 — 시각 ms · 충격 차수 · 그 충격의 KE 비 · 충격 수 · `peak_source`) · 충격별 표 |
| ⑤-2 쓰기 | `PUT /campaigns/{id}/criteria` · `set_campaign_criteria`(새 이름) | 기준값 묶음(파트 또는 무리 · 고장모드 · 지표 축 · 값 · 단위 · 출처 · 판)을 통째로 바꾼다 |
| ⑤-2 읽기 | `GET /campaigns/{id}/part-margin` · `campaign_part_margin` | 부품 · 무리 · 지표 축마다 값 · 기준값 · 출처 · 비 · 넘은 각도 비율 · 상위 10 % 각도. 기준이 없으면 「기준 미지정」 |
| ⑤-3 읽기 | `GET /campaigns/{id}/sphere-map` · `campaign_sphere_map` | 구면 격자(경도 361 × 위도 181 · 가까운 8 방향 역거리 제곱 · 하한 0.5°) · 센 띠 가운데 맞춤 · json · svg · png |
| ⑤-4 쓰기 | `PUT /campaigns/{id}/sites` · `set_campaign_sites`(새 이름) | 자리 표(자리 · 면 · 열 · 행 · x · y · 받침 · 충격추 · 런 · footprint · 자리별 지표)를 통째로 바꾼다 |
| ⑤-4 읽기 | `GET /campaigns/{id}/sites` · `campaign_site_table` | 자리마다 부품 피크 · 접촉력 · 이탈 시각 · 되튐 · 에너지비 · 기준 대비 비 · 덮임(빠진 자리) |
| ⑤-4 읽기 | `GET /campaigns/{id}/site-map` · `campaign_site_map` | 면마다 자리 지도(svg · png · json) · 빠진 자리 표시 · footprint 합성 경고 |
| ⑤-5 쓰기 · 읽기 | `POST /part-maps` · `import_part_map`, `GET /part-maps/{id}`(REST) | 파트 짝 표 — 행마다 짝 근거(`basis`) 필수 |
| ⑤-5 읽기 | `GET /campaigns/compare?a=&b=&part_map=` · `compare_campaigns` | 공통 각도(같은 DOE 또는 각거리 허용치)만 · 짝 파트별 비 · 크기별 상 / 중 / 하 · 상위 5 합 · 사라진 · 새로 생긴 파트 |
| ⑤-6 쓰기 | `PUT /campaigns/{id}/pair-rule` · `set_campaign_pair_rule` | 쌍 합격 규칙(지표 · 무리별 최대 차 % · 순위 상관 하한 · 넘은 쌍 상한) |
| ⑤-6 읽기 | `GET /campaigns/{id}/config-pairs?old=&new=` · `compare_config_pairs` | 같은 DOE 의 옛 · 새 세대 쌍 — 쌍별 차 % · 순위 상관 · 넘은 쌍 수 · 판정(통과 / 재실행 필요) |
화면(콘솔)은 이 단계에 없다.

## 2. 표(`0025_campaign_analysis`)
- `campaign_runs` 칸 하나 — `impacts`(JSONB). `campaigns` 칸 하나 — `pair_rule`(JSONB).
- `campaign_part_groups`(campaign_id · group_key 유일 · label · part_ids · part_key) · `criteria_bindings`(campaign_id · part_id 또는 group_key
  하나 · failure_mode · metric_axis · criterion_value · unit · source_platform · source_record_id · version) · `part_maps`(map_id · 만든 사람 ·
  from_model · to_model · rows · label) · `campaign_sites`(campaign_id · site_id 유일 · face · col · row · x_mm · y_mm · under_category ·
  impactor · run_key · footprint) · `campaign_site_metrics`(자리 행 · part · metric · value · time_ms · elem_id · ratio).
- 판정 · 비 · 격자는 저장하지 않고 읽을 때 센다(②③ 과 같다). 각도 사실 표를 따로 굳히지 않는다 — 7절 읽기 3.

## 3. 각도 행(⑤ 의 공용 바탕 — 순수 함수 `campaigns/angles.py`)
- 넣는 런 — 건강 표와 같은 규칙(제외 까닭이 없는 런 · `include_invalid` 면 리포트가 있는 런 모두) · `config_generation` 거르기. 첫 KE 가 ½mv² 와
  어긋난 런(`ke0_mismatch` — 「KE 튐」)은 기본으로 빼고 `excluded_ke_jump` 로 따로 센다(`include_ke_jump` 로 넣는다).
- 행 — 런의 리포트 케이스가 하나면 그 런이 한 각도(런의 pitch · roll, 없으면 케이스의 각도), 케이스가 여럿이고 케이스마다 각도가 있으면(전각도
  리포트) 케이스마다 한 각도.
- 방향 — 요청서 식 그대로 두께 틀에서 d = (sin p·cos r, −sin r, −cos p·cos r)(도). 덱 틀로는 두께축이 Z 면 그대로, X 면 (d₃, d₁, d₂), Y 면 (d₂,
  d₃, d₁)(오른손 순환). 두께축은 인자 → 캠페인의 `thickness_axis` → Z.
- 범주 · 라벨 — 덱 틀에서 가장 가까운 26 방향(면 6 · 모서리 12 · 꼭짓점 8)의 이름(`-Z` · `+X-Z` · `+X+Y-Z`)과 그 범주. 라벨이 덱 축으로 나오므로
  두께축이 X 인 덱에서 Z 를 가정한 라벨이 어긋나지 않는다(요청서 함정 줄).
- 무리 피크 — 무리의 파트 가운데 지표 최댓값과 그 파트 · 시각(지표의 시각 칸 — `peak_stress` → `time_of_peak_stress` · `peak_g` →
  `time_of_peak_g`, 초 → ms). 무리를 정하지 않은 캠페인은 무리 하나 `all`(모든 파트).
- 지표 — 리포트 파트 지표 이름(`peak_stress` · `peak_strain` · `peak_g` · `peak_disp` · `peak_principal` · `peak_principal_stress` ·
  `peak_plastic_strain` · `peak_principal_strain` · `min_principal_strain` …)과 요청서 별칭(`MET-STRESS` → `peak_stress` · `MET-STRAIN` →
  `peak_strain` · `MET-ACCEL` → `peak_g` · `MET-DISP` → `peak_disp`).
- 충격 — 런의 `impacts`(만드는 쪽이 낸다 — 리포트에는 충격 구간이 없다). 충격 수 · 두 번째 충격 시작 · 피크 시각을 품은 충격의 차수와 KE 비.
  `impacts` 가 없는 런은 그 칸이 null 이고 다회 충격 비율의 분모에서 뺀다(`impacts_known`).

## 4. 나머지 규칙
- 여유(DF-08) — 지표 축 다섯(`tension_principal_stress` · `von_mises` · `compressive_strain` · `board_strain_ue` · `effective_plastic_strain`)을
  리포트 지표로 읽는다(압축은 절댓값 · 보드는 ×10⁶ µε). 기준값은 묶음의 것만 쓴다 — 리포트의 항복값(350)은 쓰지 않는다. 기준이 없는 부품 ·
  무리는 「기준 미지정」(비 null). 값은 각도 최댓값, 같이 가운데값 · 기준 넘은 각도 비율 · 상위 10 % 각도.
- 구면 지도(DF-09) — 두께 틀의 위도 = asin(d₃) · 경도 = atan2(d₂, d₁). 격자 마디마다 각거리로 가까운 8 방향 · 가중 1 / max(θ, 0.5°)². 가운데
  맞춤 — 경도 열 평균이 가장 큰 열을 0° 로 돌린다(돌린 양을 싣는다). svg · png 는 Mollweide · 띠 칠(등급 10) · 등고선 · 방향 점. 응답에 유효 n ·
  제외 수 · 설정 세대 · 기준값 판. 순수 파이썬으로 센다(백엔드 venv 에 numpy 가 없다 — 같은 값이 어디서나 나온다).
- 자리(DF-10) — 자리 표는 캠페인에 통째로 둔다. 자리 지표가 없고 자리에 런이 묶였으면 그 런 리포트의 파트 피크 · 건강의 에너지비를 쓴다. 지표도
  런도 없는 자리는 덮임의 빠진 자리. footprint 가 실측(`measured: true`)이라고 받지 않은 자리가 하나라도 있으면 `footprints_are_measured: false`
  와 경고.
- 리비전 비교(DF-11) — 짝 근거가 `name` 뿐인 행은 쓰지 않고 센다(`name_only_skipped`). 공통 각도만 — 같은 DOE(기본) 또는 각거리 허용치. 짝마다
  각도별 비 b / a 의 가운데값 · 상위 5 합(각 캠페인의 가장 큰 다섯 값 합)과 그 비 · 크기(|log₂ 가운데값| 0.5 이상 상 · 0.25 이상 중 · 나머지
  하).
- 설정 쌍(DF-12) — 같은 DOE 의 옛 · 새 세대 런을 쌍으로. 규칙의 지표 · 무리마다 차 % = (새 − 옛) / 옛 × 100 · 순위 상관(스피어먼). 넘은 쌍이
  `max_failed_pairs` 를 넘거나 순위 상관이 하한 아래면 「재실행 필요」.

## 5. 시험
- 새 `tests/test_campaign_analysis.py` — 순수 함수(방향 · 라벨 · 두께축 · 무리 피크 · 충격 차수 · 여유 · 격자 · 짝 · 쌍) · 앱(받는 꼴 422 · 주인
  404 · 경로 열 넷 · 합성 캠페인의 값). 검증 사례(합성) — 각도 표의 다회 충격 비율 · 여유의 넘은 비율 · 격자가 손으로 센 IDW 값과 같다 · 쌍
  판정이 규칙대로 갈린다.
- MCP 계약(도구 103 → 117) · 선언 시험(capabilities 경로) · 변이.

## 6. 차례
- 마이그레이션 → 모델 → ⑤-1(각도 행 · 무리 · 충격) → ⑤-2 → ⑤-3 → ⑤-4 → ⑤-5 → ⑤-6 → MCP · 글 → 시험 · 변이 → 올리기(⑥ 과 한 판이어도 된다).

## 7. 고른 읽기(묻지 않았다 — 보고에서 알린다)
- 1 — 새 쓰기 길 둘(`set_campaign_criteria` · `PUT /campaigns/{id}/criteria`, `set_campaign_sites` · `PUT /campaigns/{id}/sites`)과 읽기 경로
  `GET /part-maps/{id}` 는 설계안 표에 없던 이름이다(기준값 · 자리 표를 받을 길이 표에 없었다).
- 2 — 충격 구간은 런 목록의 `impacts` 로 받는다(리포트에 충격 구간이 없다 — 만드는 쪽 KooChainRun 이 낸다고 읽었다). 없으면 그 칸이 null.
- 3 — 각도 사실 표를 굳히지 않고 읽을 때 리포트 케이스에서 센다(설계안 「⑤ 에서 실측으로 정한다」 — 1,000 런 셈 시간을 재서 맥락에 적는다).
- 4 — 두께축이 X · Y 인 덱의 틀 바꾸기는 오른손 순환이다(요청서는 두께축 선택만 말한다).
- 5 — 범주 · 라벨은 가장 가까운 26 방향으로 정한다(요청서는 범주 이름만 말한다).
- 6 — 가운데 맞춤은 경도 열 평균이 가장 큰 열을 0° 로(요청서 「센 띠를 가운데로」).
- 7 — 「상위 5 합」 은 각 캠페인의 가장 큰 다섯 각도 값의 합으로, 크기 상 / 중 / 하는 |log₂ 비| 0.5 · 0.25 로 가른다.
- 8 — KE 손실 지표는 싣지 않는다(리포트 파트 지표에 런 전체의 KE 손실이 없다 — 만드는 쪽이 건강 칸으로 내면 더한다).
