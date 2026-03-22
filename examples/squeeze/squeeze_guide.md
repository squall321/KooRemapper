# Squeeze 커맨드 가이드

KooRemapper v1.3.1 기준

---

## 1. 개요

`squeeze` 커맨드는 간섭끼워맞춤(interference fit), 팽윤(swelling), 초기 변형 등으로 인해 파트가 변형된 상태를 LS-DYNA에 초기 조건으로 전달하는 도구다.

**핵심 아이디어:**

1. 파트를 이미 압착·팽창된 기하 형상으로 표현 (노드 이동)
2. 그 변형에 대응하는 초기 응력 또는 변형률을 dynain 파일로 기록
3. LS-DYNA가 해석 시 두 정보를 합산하여 올바른 평형 상태에서 시작

---

## 2. 실행 방법

```bash
KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>
```

| 인자 | 설명 |
|------|------|
| `mesh.k` | 원본 기하 K-파일 |
| `config.yaml` | 설정 파일 |
| `output_prefix` | 출력 파일명 접두어 |

**출력 파일:**

| 파일 | 내용 |
|------|------|
| `<prefix>.k` | 압착된 메시 + `*INCLUDE` (dynain 연결) |
| `<prefix>.dynain` | 초기 응력 또는 변형률 카드 |

---

## 3. 초기 조건 방식 3가지

### 방식 비교표

| 방식 | YAML 키 | 재료 필요 여부 | 노드 이동 | LS-DYNA 카드 |
|------|---------|--------------|-----------|-------------|
| **응력** (기본) | `eps_x/y/z` | 필수 | O | `*INITIAL_STRESS_SOLID` |
| **변형률** | `eps_x/y/z` + `strain_mode: true` | 불필요 | O | `*INITIAL_STRAIN_SOLID` |
| **열팽창** | `swelling` | K-파일 *MAT 필수 | X | `*MAT_ADD_THERMAL_EXPANSION` + `*INITIAL_TEMPERATURE_NODE` |

---

## 4. 방식별 상세

### 4.1 응력 모드 (기본)

**언제 사용:** 재료의 E, nu를 알고 있고 응력 값으로 초기 조건을 주고 싶을 때.

**동작 흐름:**
```
eps_x/y/z 입력
      │
      ▼  노드 좌표 스케일
   압착된 기하 형상
      │
      ▼  역변형률 (-eps) → Hooke's law
   *INITIAL_STRESS_SOLID
      │
      ▼  LS-DYNA 해석
   응력과 기하가 평형 상태로 수렴
```

**재료 지정 방법 (2가지):**

#### A. YAML에 재료 직접 지정 (`ex01`)

K-파일에 `*MAT` 카드가 없을 때. 모든 squeeze 파트에 동일 재료 적용.

```yaml
parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z:  0.0

material:
  E: 210000.0    # MPa
  nu: 0.3
```

#### B. K-파일 재료 사용 (`ex02`)

K-파일에 이미 `*MAT_ELASTIC` 등이 있을 때. `material:` 섹션 생략 가능. 파트별로 각자의 재료 자동 사용.

```yaml
parts:
  - pid: 1
    eps_x: -0.015
    eps_y: -0.015
    eps_z:  0.0
  - pid: 2
    eps_x: -0.010
    eps_y:  0.0
    eps_z:  0.0

# material: 섹션 없음 → K-파일 *MAT 자동 참조
```

> **우선순위:** YAML `material:` > K-파일 `*MAT`. YAML에 지정하면 K-파일 재료를 완전히 덮어씀.

---

### 4.2 변형률 모드 (`strain_mode: true`)

**언제 사용:**
- 재료를 모를 때
- 재료가 비선형(소성, 초탄성)이어서 Hooke's law를 쓸 수 없을 때
- LS-DYNA 재료 모델이 직접 응력을 계산하게 하고 싶을 때

**동작 흐름:**
```
eps_x/y/z 입력
      │
      ▼  노드 좌표 스케일
   압착된 기하 형상
      │
      ▼  역변형률 (-eps) 그대로 기록
   *INITIAL_STRAIN_SOLID
      │
      ▼  LS-DYNA 해석 (재료 모델이 응력 계산)
   응력과 기하가 평형 상태로 수렴
```

```yaml
strain_mode: true   # 최상위 키

parts:
  - pid: 1
    eps_x: -0.01
    eps_y: -0.01
    eps_z:  0.0

# material: 섹션 불필요
# K-파일에 *MAT 없어도 동작
```

**재료 지정과의 관계:**

| 재료 상태 | strain_mode 동작 |
|-----------|----------------|
| YAML material 있음 | dynain 생성에는 사용 안 함 (무시) |
| K-파일 *MAT 있음 | dynain 생성에는 사용 안 함 (해석에는 필요) |
| 재료 없음 | 정상 동작 — `*INITIAL_STRAIN_SOLID`만 생성 |

> **주의:** LS-DYNA 해석 자체에는 재료 모델이 필요하다. `strain_mode`는 KooRemapper가 응력 계산을 위해 재료를 요구하지 않는다는 의미다. K-파일에는 `*MAT` 카드가 있어야 LS-DYNA 해석이 가능하다.

**`*INITIAL_STRAIN_SOLID` 카드 구조:**
```
*INITIAL_STRAIN_SOLID
$#    eid    nint   nhisv   large
       101       1       0       0
$#       eps11        eps22        eps33        eps12        eps23        eps13
  -1.0000e-02  -1.0000e-02   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00
```

---

### 4.3 열팽창 모드 (swelling)

**언제 사용:** 배터리 전극, 고분자, 젤, 흡수재 등 재료가 등방적으로 팽창하는 경우.

**동작 흐름:**
```
swelling: 0.03 (3% 팽윤)
      │
      ▼  노드 이동 없음 (기하 유지)
   *MAT_ADD_THERMAL_EXPANSION (CTE = 0.03)
   *INITIAL_TEMPERATURE_NODE (T = 1.0)
      │
      ▼  LS-DYNA 해석
   ΔT=1 × CTE=0.03 → 3% 열팽창 자동 적용
```

```yaml
parts:
  - pid: 1
    swelling: 0.03    # 3% 등방 팽윤

  - pid: 2
    swelling: 0.05    # 5% 팽윤

# K-파일에 *MAT_* 카드 필수 (MID를 *PART에서 읽어 연결)
```

**삽입되는 카드 예시 (PID 1, MID 1):**
```
*MAT_ADD_THERMAL_EXPANSION
$#     mid      lcid     mult
         1         0   0.030
*INITIAL_TEMPERATURE_NODE
$#     nid      temp       loc
      1001       1.0         0
      1002       1.0         0
      ...
```

**제약사항:**
- 한 파트에 `swelling`과 `eps_x/y/z` 동시 사용 불가
- K-파일에 해당 파트의 `*MAT` 카드가 없으면 `*PART`에서 MID를 읽지 못해 PID를 MID로 대체 (경고 출력)
- `dynain` 파일에는 포함되지 않음 (카드가 직접 `.k` 파일에 삽입)

---

## 5. 재료 지정 분기 요약

```
squeeze 실행
      │
      ├─ swelling 파트? ─────────────────────────────────────── K-파일 *MAT 연결
      │
      └─ eps 파트?
            │
            ├─ strain_mode: true ───────────────────────────── 재료 불필요
            │                                                   *INITIAL_STRAIN_SOLID
            │
            └─ strain_mode: false (기본)
                  │
                  ├─ YAML material: 있음 ──────────────────── 전 파트 동일 재료
                  │                                            *INITIAL_STRESS_SOLID
                  │
                  ├─ K-파일 *MAT 있음 ──────────────────────── 파트별 재료 자동
                  │                                            *INITIAL_STRESS_SOLID
                  │
                  └─ 재료 없음 ────────────────────────────── ERROR
                                                               strain_mode: true 권장
```

---

## 6. Dynamic Relaxation 연동 (`relax:` 섹션)

squeeze 출력 파일에 DR 키워드를 자동 삽입하려면 `relax:` 섹션을 추가한다.
별도로 `KooRemapper relax` 커맨드를 실행하지 않아도 된다.

```yaml
relax:
  level: 2          # 1(빠름) ~ 5(최대 보수적)
  mode: explicit    # explicit(IDRFLG=1) | implicit(IDRFLG=5)
  drterm: 0.0       # DR 종료 시간 (0 = 수렴 판정까지)
  endtime: 1.0      # *CONTROL_TERMINATION 삽입 (생략 시 미삽입)
  d3drlf: true      # *DATABASE_BINARY_D3DRLF 출력
  # 개별 오버라이드 (선택)
  nrcyck: 250
  drtol: 0.001
  drfctr: 0.995
  tssfdr: 0.90
  irelal: 0
  edttl: 0.04
```

**레벨 프리셋:**

| 레벨 | 이름 | NRCYCK | DRTOL | DRFCTR | TSSFDR | IRELAL |
|------|------|--------|-------|--------|--------|--------|
| 1 | 빠름 | 500 | 0.010 | 0.990 | 0.95 | 0 |
| 2 | 표준 | 250 | 0.001 | 0.995 | 0.90 | 0 |
| 3 | 안정 | 100 | 0.001 | 0.998 | 0.80 | 0 |
| 4 | 보수 | 50 | 1e-4 | 0.999 | 0.67 | 1 |
| 5 | 최대 | 25 | 1e-5 | 0.999 | 0.50 | 1 |

**`relax:` 섹션 진입만으로 DR이 활성화된다.** `enabled: true` 명시 불필요.

---

## 7. 전체 YAML 옵션 레퍼런스

```yaml
# ── 최상위 키 ──────────────────────────────────────────────────
strain_mode: false        # true: *INITIAL_STRAIN_SOLID (재료 불필요)
                          # false: *INITIAL_STRESS_SOLID (기본, 재료 필수)

# ── 파트 정의 ──────────────────────────────────────────────────
parts:
  - pid: 1                # 파트 ID (필수)

    # [응력/변형률 모드] eps 지정 — swelling과 동시 사용 불가
    eps_x: -0.01          # x 방향 공학 변형률 (음수=압축, 양수=인장)
    eps_y: -0.01          # y 방향
    eps_z:  0.0           # z 방향

    # [열팽창 모드] swelling 지정 — eps와 동시 사용 불가
    # swelling: 0.03      # 등방 팽윤율 (3%)

# ── 재료 (응력 모드 전용, 선택) ─────────────────────────────────
material:
  E: 210000.0             # Young's modulus [MPa]
  nu: 0.3                 # Poisson's ratio
                          # 생략 시 K-파일 *MAT 자동 사용

# ── Dynamic Relaxation (선택) ───────────────────────────────────
relax:
  level: 2                # 1~5 (기본: 2)
  mode: explicit          # explicit | implicit
  drterm: 0.0             # DR 종료 시간 (0=수렴 판정)
  endtime: 1.0            # *CONTROL_TERMINATION (생략 가능)
  d3drlf: true            # D3DRLF 출력 (기본: true)
  nrcyck: 250             # 수렴 체크 간격 (오버라이드)
  drtol: 0.001            # 수렴 tolerance
  drfctr: 0.995           # 속도 감쇠 계수
  tssfdr: 0.90            # DR 중 timestep 스케일
  irelal: 0               # 자동 제어 (0=off, 1=on)
  edttl: 0.04             # 자동 제어 tolerance
```

---

## 8. 예제 파일 목록

| 파일 | 모드 | 재료 | DR |
|------|------|------|-----|
| `ex01_stress_yaml_material.yaml` | 응력 | YAML 직접 지정 | 없음 |
| `ex02_stress_kfile_material.yaml` | 응력 | K-파일 자동 | 없음 |
| `ex03_strain_no_material.yaml` | 변형률 | 불필요 | 없음 |
| `ex04_swelling.yaml` | 열팽창 | K-파일 필수 | 없음 |
| `ex05_mixed_with_dr.yaml` | 응력+열팽창 혼합 | YAML+K-파일 | 포함 |

---

## 9. 워크플로우별 사용 시나리오

### 시나리오 A: 볼베어링 간섭끼워맞춤

재료 알고 있음 → 응력 모드 + DR

```bash
KooRemapper squeeze bearing.k bearing_squeeze.yaml bearing_out
# → bearing_out.k (INITIAL_STRESS_SOLID + DR 카드)
# → bearing_out.dynain
# LS-DYNA로 bearing_out.k 실행 → DR 평형 후 접촉 해석
```

### 시나리오 B: 배터리 셀 팽윤

재료는 K-파일에 있고 등방 팽창 → 열팽창 모드

```bash
KooRemapper squeeze battery.k battery_swell.yaml battery_out
# → battery_out.k (MAT_ADD_THERMAL_EXPANSION + INITIAL_TEMPERATURE_NODE)
# LS-DYNA 해석 시 팽윤 자동 적용
```

### 시나리오 C: 비선형 재료 초기 변형

재료 모델이 복잡하거나 없음 → 변형률 모드

```bash
KooRemapper squeeze part.k squeeze_strain.yaml part_out
# → part_out.k (INITIAL_STRAIN_SOLID)
# LS-DYNA 재료 모델이 직접 응력 결정
```

---

## 10. 자주 하는 실수

| 증상 | 원인 | 해결 |
|------|------|------|
| `No material specified` 에러 | 응력 모드인데 재료 없음 | YAML `material:` 추가 또는 `strain_mode: true` |
| dynain 요소 수 = 0 | K-파일에 PID가 없음 | K-파일과 config YAML의 PID 일치 확인 |
| swelling 카드가 생성 안 됨 | `*PART` 카드가 없어 MID 탐색 실패 | K-파일에 `*PART` 카드 추가 |
| LS-DYNA가 초기 응력 무시 | dynain이 `*INCLUDE` 되지 않음 | `.k` 파일에 `*INCLUDE <prefix>.dynain` 확인 |
| DR이 수렴 안 됨 | 레벨이 낮거나 변형이 큼 | `relax: level` 값 높이기 (3~4) |
