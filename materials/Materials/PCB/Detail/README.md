# PCB Detail — MAT_086 Equivalent Laminate Generator

스마트폰/전자기기 PCB를 **단일 등가 orthotropic viscoelastic 재료** (*MAT_086*)로 변환하는 툴.

## 목적

다층 PCB는 PPG(prepreg) 수지 + Cu 박의 교대 라미네이트이다. 실제 해석에서는:

- **모든 층을 따로 메쉬** → 메쉬 폭발, 대규모 해석 불가
- **Cu 패턴까지 고려** → 사실상 불가능

따라서 **smeared (homogenized) orthotropic equivalent**를 쓴다. 이 툴은:

1. 적층 구성(layup)을 읽어서
2. 각 층의 PPG/Cu 물성을 조회하고
3. **Rule of Mixture** + **Classical Lamination Theory**로 등가 물성 계산
4. LS-DYNA `*MAT_ORTHOTROPIC_VISCOELASTIC` (MAT_086) 카드로 출력

## MAT_086 선택 이유

| 카드 | Orthotropic | Viscoelastic | 적합도 |
|------|-----------|--------------|-------|
| MAT_002 | ✅ Full | ❌ | 탄성만 |
| MAT_006 | ❌ Isotropic | ✅ | 이방성 표현 불가 |
| **MAT_086** | ✅ Transversely isotropic | ✅ Single Maxwell (deviatoric) | **최적** |
| MAT_076 | ❌ Isotropic | ✅ Prony multi-term | 이방성 표현 불가 |

PCB는 본질적으로 **transversely isotropic**:
- **면내 (XY)**: 유리섬유 직조 + Cu 패턴 → 강함, 같음
- **면외 (Z)**: PPG 수지만 지배 → 약함

MAT_086은 EA=EB (면내 같음) + EC (면외 다름) + 편차응력(deviatoric) 점탄성 이완을 동시에 표현한다.

## MAT_086 카드 구조

```
*MAT_ORTHOTROPIC_VISCOELASTIC
Card 1: MID, RO, EA, EB, (nu_ba), GAB, GBC, GCA, AOPT
Card 2: K (bulk), G0, GINF, BETA, ...
Card 3-5: AOPT coordinate system definition
```

- **EA, EB, EC**: Young's modulus (a=x, b=y, c=z). PCB: EA=EB ≠ EC
- **nu_ba**: Poisson ratio (면내)
- **GAB, GBC, GCA**: 전단 탄성계수. PCB: GAB는 면내, GBC=GCA는 면외
- **K**: 체적 탄성계수 (시간 무관)
- **G0, GINF, BETA**: deviatoric 전단 이완 (단일 Maxwell)

## 등가 물성 계산 방법

### 1. 면내 (XY) — **Rule of Mixture (Voigt 근사)**

평행한 층들이 같은 변형을 받음:

```
E_xy_eq = Σ(t_i × E_xy_i × η_i) / Σ(t_i)
CTE_xy_eq = Σ(t_i × E_xy_i × η_i × α_xy_i) / Σ(t_i × E_xy_i × η_i)
```

- Cu 층의 `η_i` = Cu 면적률 (0.3~0.95)
- PPG 층의 `η_i` = 1.0

### 2. 면외 (Z) — **Reuss 근사 (직렬 연결)**

직렬 연결이므로 compliance 평균:

```
1/E_z_eq = Σ(t_i / E_z_i × η_i) / Σ(t_i)
CTE_z_eq = Σ(t_i × α_z_i × η_i) / Σ(t_i)  (자유 팽창 가정)
```

### 3. 전단 탄성계수

- **G_xy_eq** (면내): `E_xy_eq / (2*(1+nu_xy_eq))` 또는 VF 평균
- **G_xz_eq = G_yz_eq** (면외): Reuss 평균 (PPG 수지 지배)

### 4. 밀도

```
rho_eq = Σ(t_i × rho_i × η_i) / Σ(t_i)
```

### 5. 점탄성 (deviatoric)

PCB의 점탄성 거동은 **PPG 수지의 편차응력 이완**에서 온다. Cu는 탄성으로 간주:

```
G0_eq, GI_eq, BETA_eq = PPG 층의 두께 가중 평균
```

단, Cu 층이 너무 많으면 PPG의 이완 효과가 희석됨을 반영하여 **volume fraction of PPG**로 스케일링:

```
G0_dev = G0_ppg × vf_ppg + G_cu_eq × (1 - vf_ppg)
```

## 입력 파일 형식

### layup.yaml (적층 정의)

```yaml
material_name: "PCB_4Layer_HDI_Standard"
material_id: 200001
description: "4층 스마트폰 HDI (DS-8402H + ED Cu)"

# 재료 K-file 참조
ppg_library: "../pcb_prepreg_materials.k"
cu_library: "cu.k"

# 적층 (top → bottom)
layers:
  - {type: cu,  material: "Cu_ED_Standard", thickness_um: 18, cu_ratio: 0.40}  # Signal L1
  - {type: ppg, material: "Doosan DS-8402H", thickness_um: 100}               # PPG1
  - {type: cu,  material: "Cu_ED_Standard", thickness_um: 35, cu_ratio: 0.90}  # GND L2
  - {type: ppg, material: "Doosan DS-7402LC", thickness_um: 200}              # Core
  - {type: cu,  material: "Cu_ED_Standard", thickness_um: 35, cu_ratio: 0.90}  # PWR L3
  - {type: ppg, material: "Doosan DS-8402H", thickness_um: 100}               # PPG2
  - {type: cu,  material: "Cu_ED_Standard", thickness_um: 18, cu_ratio: 0.40}  # Signal L4
```

### 출력

`{material_name}.k` — MAT_086 카드 + MAT_ADD_THERMAL_EXPANSION

## 사용법

```bash
cd PCB/Detail
python3 pcb_layup_generator.py examples/sample_4L_hdi.yaml
# 출력:
#   sample_4L_hdi_shell.k  ← Shell/TSHELL용 (MAT_086 점탄성)
#   sample_4L_hdi_solid.k  ← Solid용 (MAT_002 탄성 + Rayleigh damping)
```

## 두 가지 버전

생성기는 **항상 두 개의 K-file**을 출력한다:

### `_shell.k` — MAT_086 (Orthotropic Viscoelastic)
- **대상 요소**: Shell (ELFORM=2,16 등) 또는 TSHELL (ELFORM=1,2)
- **구성**: `*MAT_ORTHOTROPIC_VISCOELASTIC` + `*MAT_ADD_THERMAL_EXPANSION`
- **특징**: 점탄성 (deviatoric 이완) 내장. 추가 damping 불필요
- **장점**: 점탄성 거동이 material level에서 반영됨
- **제한**: Shell/TSHELL 전용. Solid 요소에는 쓸 수 없음
- **용도**: 전역 PCB 모델링, 빠른 낙하 해석

### `_solid.k` — MAT_002 + Rayleigh damping (PART_DAMPING)
- **대상 요소**: Solid (8-node hex, 4-node tet)
- **구성**:
  - `*MAT_ORTHOTROPIC_ELASTIC` (MAT_002)
  - `*MAT_ADD_THERMAL_EXPANSION` (x/y/z 별도 CTE)
  - `*SET_PART_LIST` (SID = MID + 800000, 빈 리스트 placeholder)
  - `*DAMPING_PART_MASS_SET` (alpha, mass-proportional)
  - `*DAMPING_PART_STIFFNESS_SET` (beta, stiffness-proportional)
- **특징**: 점탄성을 직접 표현 못 하므로 **Rayleigh damping**으로 등가 산일
- **장점**: Solid 요소 사용 가능 → 응력 집중, contact, 접착 더 정확
- **제한**: Rayleigh는 주파수 의존 특성 근사일 뿐
- **용도**: 국부 정밀 해석, BGA/Via 주변, 접착층 상세 모델

### Rayleigh damping 계수 유도

```
tan(delta)_peak = (G0 - GI) / (2 * sqrt(G0 * GI))       # 단일 Maxwell 손실 인자
zeta = tan(delta) / 2                                    # 등가 damping ratio
omega_ref = BETA                                         # 특성 각주파수 (rad/s)

alpha (mass)  = zeta * omega_ref
beta  (stiff) = zeta / omega_ref
```

이 방식은 MAT_086의 점탄성 피크 주파수 (omega = BETA)에서 **동일한 damping ratio**를 갖도록 한다.

### Part Set 설정 (solid 버전)

생성된 `_solid.k`에는 placeholder `*SET_PART_LIST`가 포함되어 있다:

```
*SET_PART_LIST_TITLE
PCB_8L_043T_DS7402_EM370Z_parts
$      SID       DA1       DA2       DA3       DA4
   1000008       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace the zero below with your actual PCB PART IDs
         0         0         0         0         0         0         0         0
```

**사용 방법**:
1. 풀 모델에서 PCB로 사용할 PART(s)의 MID를 생성된 material ID (예: 200008)로 설정
2. 그 PART의 PID를 위 SET_PART_LIST의 `0` 대신 입력
3. Rayleigh damping이 자동으로 해당 파트들에 적용됨

Part Set SID는 `MID + 800000`로 자동 할당되므로 다른 set과 충돌 없이 사용 가능하다.

## Cu 재료 (cu.k)

두 가지 Cu 박 (IPC-TM-650 + Rogers TDS 기반):

1. **Cu_RA (Rolled Annealed)** — 압연박
   - 유연, 높은 elongation (13% @ 1 oz)
   - FPC, flex PCB에 사용
   - E = 115 GPa, TS = 152 MPa, ρ = 8.93 g/cc

2. **Cu_ED (Electrodeposited)** — 전해박
   - 강한 tensile (276 MPa @ 1 oz), 낮은 elongation (3%)
   - 표준 rigid PCB에 사용
   - E = 117 GPa, TS = 276 MPa, ρ = 8.909 g/cc

3. **Cu_HTE (High Temperature Elongation)** — 고온 연신 ED
   - 낮은 temp 변형, 고신뢰성
   - E = 120 GPa, TS = 345 MPa

Cu는 **isotropic elastic**으로 처리 (MAT_001). 등가 라미네이트 계산 시 **Cu의 유효 기여**는 Cu 면적률로 할인한다 (빈 부분은 resin으로 채워짐).

## 디렉토리 구조

```
PCB/Detail/
├── README.md                     # 본 문서
├── cu.k                          # Cu 재료 라이브러리 (3종)
├── pcb_layup_generator.py        # 메인 변환 스크립트
├── examples/
│   ├── sample_2L_basic.yaml      # 2층 단순 PCB
│   ├── sample_4L_hdi.yaml        # 4층 HDI 표준
│   ├── sample_8L_smartphone.yaml # 8층 스마트폰 HDI
│   └── sample_flex_fpc.yaml      # FPC 플렉스
└── output/                        # 생성된 K-file 저장
```

## 참고

- MAT_086 제한: single Maxwell만 지원 (정밀 감쇠는 MAT_076 isotropic 권장)
- EA = EB 요구 (transversely isotropic). PCB 실제는 약간 다를 수 있지만 스마트폰 HDI는 등방에 가까움
- Cu 패턴의 실제 효율은 회로 설계에 따라 다름; 일반적으로 signal 30-50%, power/GND 80-95%
- 큰 via 영역은 등가 처리 어려움 → via 많은 영역은 국부 모델 권장
