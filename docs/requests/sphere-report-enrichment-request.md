# 스피어(전각도 낙하) 리포트 보강 요청서

**보내는 쪽**: DynaForge / KooRemapper 플랫폼 (리포트 소비·분석 계층)
**받는 쪽**: `koo_sphere_report` 후처리 모듈 (+ 상류 데이터원 `KooD3plotReader`)
**작성일**: 2026-09-04
**대상 산출물**: `koo_sphere_report` 가 생성하는 sphere 리포트 HTML 의 임베드 데이터(`results[].parts[<pid>]` 등)

---

## 1. 배경과 목적

DynaForge 는 sphere 리포트 HTML 을 인제스트해 방향군 통계·부품 리스크·산포/민감도·시계열
분석을 서버 표준으로 제공한다. 분석 도구는 이미 구현돼 있고, **리포트에 값이 있으면 자동으로
활성화**된다(예: `report_angle_stats` 는 `available_metrics` 를 자동 감지, `report_part_series` 는
`strain_ts/g_ts/disp_ts` 키를 이미 읽음, `report_part_energy` 는 matsum 스키마를 이미 읽음).

즉 아래 항목들은 **DynaForge 쪽 추가 개발이 거의 없이**, 리포트가 값을 담아주기만 하면 그 자리에서
분석이 열린다. 각 항목마다 "여는 분석"과 "DynaForge 후속(수용 시)"을 같이 적었다.

---

## 2. 현재 sphere 리포트가 담는 것 (실측 기준)

`Test_001_report.html`(cuboid_26) 기준으로 확인한 실제 내용이다.

- 최상위: `doe_strategy`, `angular_spacing_deg`, `sphere_coverage`, `total_runs`/`successful_runs`/`failed_runs`, `project_name`, `sim_params`, `yield_stress`, `parts`, `results`, `findings`
- `results[]`: `angle{name,roll,pitch,yaw,category,swap}`, `folder`, `num_states`, `parts`
- `results[].parts[<pid>]`: **`peak_stress`, `peak_strain`, `peak_disp`, `peak_g`, `stress_ts`**
  - `stress_ts` = `{t[], max[], avg[], min[], elem[]}` — 다운샘플된 폰미세스 응력 시간이력(파트 내 요소 max/avg/min + max 요소 id)
- `energy_flows`: **현재 `null`** (하중경로 그래프·파트 에너지 없음 — matsum 미덤프로 추정)

---

## 3. 보강 요청

### P1-A. 스트레인·변위·가속도 시계열 (`strain_ts` / `disp_ts` / `g_ts`)

- **현재**: 응력만 시계열(`stress_ts`)이 있고, 스트레인·변위·가속도는 **peak 스칼라뿐**이다.
- **요청**: `stress_ts` 와 **동일한 형태**로 파트별 시간이력을 추가한다. peak 값을 뽑을 때 이미
  시간이력을 갖고 있을 것이므로, 그 다운샘플 계열을 그대로 직렬화하면 된다.
  ```json
  "results[].parts[<pid>]": {
    "strain_ts": {"t": [...], "max": [...], "avg": [...], "min": [...], "elem": [...]},
    "disp_ts":   {"t": [...], "max": [...], "avg": [...], "min": [...]},
    "g_ts":      {"t": [...], "max": [...], "avg": [...], "min": [...]}
  }
  ```
- **여는 분석**: 파트별 스트레인/변위/가속도 시간이력(`report_part_series`) — 응력 외 3개 물리량의
  거동을 시간축으로.
- **DynaForge 후속**: **없음**. `parser.part_series` 가 이미 `strain_ts/g_ts/disp_ts` 키를 읽는다(현재는
  부재라 `None`). 담기면 즉시 노출된다.
- **난이도(추정)**: 낮음. peak 계산 경로에 이미 존재하는 계열의 직렬화.

### P1-B. 유효 소성 변형률 (effective plastic strain, EPS)

- **현재**: `peak_strain`(총/유효 변형률, 탄성·소성 미분리)만 있다. 소성 변형률은 **전무**하다.
- **요청**: 파트별 소성 변형률 peak(가능하면 시계열도)을 추가한다.
  ```json
  "results[].parts[<pid>]": {
    "peak_plastic_strain": <float>,
    "plastic_strain_ts": {"t": [...], "max": [...], "avg": [...], "min": [...]}   // 선택
  }
  ```
  - 소성 변형률은 낙하/충격에서 **영구 손상·항복 판정의 1차 지표**라 방향별로 보는 가치가 크다.
- **여는 분석**: 방향군별 소성 변형률 통계(`report_angle_stats`), 부품 소성 리스크 랭킹.
- **DynaForge 후속**: 한 줄. 쿼리 물리량 화이트리스트(`_QUERY_METRICS`)에 `peak_plastic_strain` 추가.
  나머지(방향별 통계·산포·부품 분해)는 `available_metrics` 자동 감지로 그대로 동작.
- **난이도(추정)**: 중. d3plot 에 소성 변형률(예: history variable / EPS)이 있으면 KooD3plotReader
  추출 → 리포트 직렬화. 없으면 solver 출력 요청부터.

### P2-A. 파트별 에너지 (matsum) — 내부/운동 에너지

- **현재**: `energy_flows = null`. 파트별 에너지도, 하중경로 그래프도 없다(matsum 미덤프).
- **요청**: 각 케이스에서 파트별 내부에너지(IE)·운동에너지(KE) 시간이력을 담는다. deep 리포트가
  이미 쓰는 `matsum` 스키마와 **동형**이면 DynaForge 가 그대로 읽는다. 두 가지 담는 방식 중 택1.
  - (권장, deep 과 동형) 케이스별 `binout.matsum` 블록:
    ```json
    "results[].binout": {
      "matsum": {
        "part_ids": [...], "part_names": [...], "t": [...],
        "internal_energy": [[part-major 시계열], ...],
        "kinetic_energy":  [[...], ...],
        "hourglass_energy": [[...], ...]   // 선택
      }
    }
    ```
  - (대안, 파트에 직접) `results[].parts[<pid>].ie_ts` / `ke_ts` = `{t[], val[]}`.
- **여는 분석**: 파트별 에너지 시계열(`report_part_energy`) — 전각도 낙하에서 어느 방향·부품이
  에너지를 흡수/전달하는지. 방향별 에너지 통계도 확장 가능.
- **DynaForge 후속**: (권장안이면) 사실상 없음 — `parser.part_energy_series` 가 `binout.matsum` 을
  이미 읽고 배열 방향(part-major/time-major)까지 자동 처리한다. sphere 는 케이스 루프만 얹으면 됨.
- **선행 조건**: sphere DOE 런이 `*DATABASE_MATSUM` 을 덤프해야 한다.

### P2-B. 하중경로 그래프 (`energy_flows`) 채우기

- **현재**: `null`.
- **요청**: matsum 이 덤프되면 케이스별 `energy_flows[case_key]` 에 노드(파트/임팩터)·엣지(접촉
  일)·전파순서를 채운다. DynaForge 는 이미 `impactor_ke_initial/final`, `nodes[].peak_ie/peak_ke`,
  `edges[].total_work/confidence` 스키마를 읽는다(`report_energy_flow`).
- **개선 제안**: 노드를 `part_id` 로도 식별해 주면(현재 `node_id` 중심) 부품 리스크와 직접 연결된다.
- **DynaForge 후속**: 노드에 `part_id` 있으면 부품↔에너지 연계 강화(소규모).

### P3-A. 주응력/주변형률 (principal), 파트별 안전계수

- **현재**: `peak_stress`(폰미세스 추정)·`peak_strain` 만. principal·safety_factor 파트별 없음.
- **요청**: 있으면 파트별로 추가.
  ```json
  "results[].parts[<pid>]": {
    "peak_principal": <float>, "min_principal": <float>,
    "peak_vm_strain": <float>, "safety_factor": <float>
  }
  ```
  - `yield_stress` 는 이미 전역에 있으니 파트별 항복강도가 있으면 `safety_factor` 계산이 정확해진다.
- **여는 분석**: 주응력 기반 방향군 통계(취성/인장 파손 판정), 안전계수 방향 분포.
- **DynaForge 후속**: 없음 — `_QUERY_METRICS` 에 이미 4키 등록돼 있다(현재 리포트가 미채움).

---

## 4. 호환 부록 — DynaForge 가 기대하는 정확한 키

상류가 아래 키·형태로 담아주면 DynaForge 추가 개발이 최소화된다.

| 항목 | 위치 | 키 / 형태 | DynaForge 소비처 |
|---|---|---|---|
| 스트레인/변위/가속도 시계열 | `results[].parts[<pid>]` | `strain_ts`·`disp_ts`·`g_ts` = `{t,max,avg,min[,elem]}` | `part_series`(키 이미 읽음) |
| 소성 변형률 | `results[].parts[<pid>]` | `peak_plastic_strain`(+`plastic_strain_ts`) | `angle_group_stats`(자동감지) |
| 파트 에너지 | `results[].binout.matsum` | `part_ids,part_names,t,internal_energy,kinetic_energy` | `part_energy_series`(스키마 이미 읽음) |
| 하중경로 | `energy_flows[case_key]` | `nodes[].peak_ie/peak_ke`, `edges[].total_work/confidence`(+`part_id`) | `energy_flow` |
| 주응력/안전계수 | `results[].parts[<pid>]` | `peak_principal,min_principal,peak_vm_strain,safety_factor` | 쿼리/통계(키 이미 등록) |

**공통 규약**
- 결측값은 `null` 로(문자열 "nan"/Infinity 금지 — DynaForge 는 비유한수를 `null` 로 정규화하지만
  애초에 안 보내는 게 안전하다).
- 시계열은 지금처럼 다운샘플해서 담으면 된다(용량·전송 부담 최소).
- 파트 식별은 정수 `pid` 유지.

---

## 5. 우선순위 요약

| 우선 | 항목 | 여는 것 | 상류 난이도(추정) | DynaForge 후속 |
|---|---|---|---|---|
| **P1** | strain/disp/g 시계열 | 4개 물리량 시간이력 | 낮음(직렬화만) | 없음 |
| **P1** | 소성 변형률 | 소성 방향 분석·손상 판정 | 중(추출 필요) | 화이트리스트 1줄 |
| **P2** | 파트 에너지(matsum) | 에너지 흡수/전달 방향 분석 | 중(런이 matsum 덤프) | 거의 없음 |
| **P2** | energy_flows 채우기 | 하중경로 그래프 | 중(matsum 의존) | 소규모(part_id 연계) |
| **P3** | principal/safety_factor | 주응력·안전계수 방향 분석 | 낮음~중(있으면) | 없음 |

> 요지 — **P1(시계열·소성)이 가성비가 가장 높다.** 특히 `strain_ts/disp_ts/g_ts` 는 이미 있는 계열을
> 직렬화만 하면 되고 DynaForge 후속이 아예 없다. 소성 변형률은 낙하 손상 판정의 핵심이라 값어치가 크다.
