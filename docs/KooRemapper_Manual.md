# KooRemapper 기능 설명서

> **버전 1.1.0** | LS-DYNA 메시 전처리 도구
> 빌드: `cmake --build build --config Release`
> 실행: `KooRemapper.exe <command> [options] ...`

---

## 목차

1. [개요](#1-개요)
2. [시스템 요구사항 및 빌드](#2-시스템-요구사항-및-빌드)
3. [명령어 목록](#3-명령어-목록)
4. [map — HEX8 구조화 메시 매핑](#4-map--hex8-구조화-메시-매핑)
5. [shellmap — QUAD4 셸 기반 매핑](#5-shellmap--quad4-셸-기반-매핑)
6. [prestress — 초기 응력/변형률 계산](#6-prestress--초기-응력변형률-계산)
7. [squeeze — 간섭 끼워맞춤](#7-squeeze--간섭-끼워맞춤)
8. [generate / generate-var — 메시 생성](#8-generate--generate-var--메시-생성)
9. [assemble — 통합 어셈블리 명령](#9-assemble--통합-어셈블리-명령)
   - 9.1 [replace](#91-replace--상세-메시-교체)
   - 9.2 [squeeze (assemble 내)](#92-squeeze-assemble-내)
   - 9.3 [restack](#93-restack--레이어-재적층)
   - 9.4 [bend](#94-bend--굽힘-변형--초기-응력)
   - 9.5 [indent](#95-indent--압입--엠보싱)
   - 9.6 [formstrain](#96-formstrain--성형-소성-변형률)
   - 9.7 [tet10 / hex20 / quad8 / tria6](#97-tet10--hex20--quad8--tria6--2차-요소-변환)
   - 9.8 [refine](#98-refine--메시-세분화)
   - 9.9 [elform](#99-elform--요소-공식-변경)
   - 9.10 [disconnect](#910-disconnect--노드-분리)
   - 9.11 [iga](#911-iga--등기하해석-nurbs-박스-생성)
10. [matswap — 재료 번들 교체](#10-matswap--재료-번들-교체)
11. [implicit — Explicit→Implicit 변환](#11-implicit--explicitimplicit-변환)
12. [수학 이론](#12-수학-이론)
13. [출력 파일 형식](#13-출력-파일-형식)

---

## 1. 개요

KooRemapper는 LS-DYNA FEA 해석을 위한 **메시 전처리 도구**입니다.
주요 목적은 개략 메시(coarse mesh)로 구성된 전체 모델에 **상세 메시(detail mesh)**를 매핑하고,
조립 공정에 수반되는 **초기 응력 상태(prestress)**를 재현하는 것입니다.

### 핵심 기능 범위

| 범주 | 기능 |
|------|------|
| **메시 매핑** | HEX8 등매개변수 매핑, QUAD4 셸 기반 매핑 |
| **초기 응력** | 기준-변형 형상 간 변형률/응력 계산, dynain 출력 |
| **간섭 조립** | 부품 압축(squeeze) + 역방향 prestress |
| **형상 변형** | 굽힘(bend), 압입(indent), 엠보싱(emboss) |
| **적층 구조** | 레이어별 두께·재료 재정의(restack) |
| **성형 변형** | 이면각 기반 소성 변형률(formstrain) |
| **메시 변환** | 2차 요소 변환(TET10/HEX20 등), 세분화(refine), ELFORM 변경 |
| **토폴로지** | 노드 분리(disconnect), CZM·MEFEM 인터페이스 생성 |
| **등기하해석** | FE solid → IGA NURBS box 래핑(IGA) |
| **메시 생성** | 변밀도 메시 생성(generate-var) |

---

## 2. 시스템 요구사항 및 빌드

### 요구사항
- Windows 10/11 x64
- CMake 3.16 이상
- MSVC 2019/2022 (Visual Studio)
- C++17

### 빌드

```bash
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

실행 파일: `build\bin\Release\KooRemapper.exe`

---

## 3. 명령어 목록

```
KooRemapper.exe <command> [options] ...

Commands:
  map            HEX8 구조화 메시를 굽힘 참조 형상에 매핑
  shellmap       QUAD4 셸 참조 기반 상세 메시 매핑
  unfold         굽힘 구조화 메시로부터 평면 메시 생성
  generate       테스트용 예제 메시 생성
  generate-var   YAML 설정 기반 변밀도 메시 생성
  strain         두 메시 간 변형률 계산
  prestress      변형 형상 기반 초기 응력 계산 + dynain 출력
  squeeze        간섭 끼워맞춤 초기 변형 계산
  assemble       다중 오퍼레이션 통합 어셈블리
  matswap        재료 번들 교체 (MAT/SECTION/HGID/CURVE)
  implicit       Explicit K 파일 → Implicit 해석 변환
  info           메시 파일 정보 출력
  help           도움말
  version        버전 정보
```

---

## 4. map — HEX8 구조화 메시 매핑

### 용도
평면(flat) 상세 메시(HEX8)를 굽힘(bent) 참조 구조화 메시에 등매개변수 방법으로 매핑.
참조 메시는 **구조화된 HEX8**이어야 하며, 상세 메시는 임의 형상이어도 무방합니다.

### 사용법

```bash
KooRemapper.exe map [--single] <bent_mesh.k> <flat_mesh.k> <output.k>

Options:
  --single, -s    단일 스레드 모드 (기본: 병렬)
```

### 동작 원리

각 상세 메시 노드 **p**에 대해:

1. 참조 메시에서 포함하는 요소 검색
2. 자연 좌표 **(ξ, η, ζ)** 역계산 (Newton-Raphson)
3. 굽힘 참조 형상의 같은 자연 좌표로 위치 변환

$$\mathbf{x}(\xi, \eta, \zeta) = \sum_{i=1}^{8} N_i(\xi, \eta, \zeta) \, \mathbf{x}_i$$

여기서 HEX8 형상 함수:

$$N_i = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

### 출력
- `output.k`: 매핑된 위치의 상세 메시

### 주의사항
- 참조 메시는 반드시 **규칙적 HEX8 구조** 필요
- 상세 메시 노드가 참조 요소 외부에 있으면 경고 출력
- `info` 명령으로 Jacobian 통계 확인 가능

---

## 5. shellmap — QUAD4 셸 기반 매핑

### 용도
QUAD4 셸 참조 형상을 기반으로 **평면 상세 고체 메시(solid detail mesh)**를
굽힘 형상으로 매핑. 두께 방향 위치는 자동 또는 명시적으로 지정.

### 사용법

```bash
KooRemapper.exe shellmap [--thickness <t>] <bent_shell.k> <flat_detail.k> <output.k>

Options:
  --thickness <t>   두께 명시적 지정 (기본: Z-범위 자동 감지)
```

### 동작 원리

1. 셸 참조 메시로부터 **법선 벡터 n̂** 계산
2. 평면 노드의 면내 위치 (u, v)를 셸 면에 투영
3. 두께 방향 위치 z를 셸 면에서 **±t/2** 범위로 맵핑

$$\mathbf{x}' = \mathbf{x}_{shell}(u,v) + \frac{z}{t/2} \cdot \frac{t}{2} \hat{\mathbf{n}}(u,v)$$

### 출력
- `output.k`: 매핑된 상세 고체 메시

### 주의사항
- 가전개(developable) 면에 최적화; 비가전개 면에서 왜곡 경고 출력
- QUAD4 전용 (TRIA3 미지원)

---

## 6. prestress — 초기 응력/변형률 계산

### 용도
**기준 형상(reference)**과 **변형 형상(deformed)** 메시 쌍으로부터
각 요소의 초기 응력을 계산하여 LS-DYNA `*INITIAL_STRESS_SOLID` 형식으로 출력.

### 사용법

```bash
KooRemapper.exe prestress [options] <ref_mesh.k> <def_mesh.k> <output_prefix>

Options:
  --E <value>          영률 (K-파일 재료 카드 대체)
  --nu <value>         푸아송 비
  --strain engineering|green|log   변형률 계산 방식 (기본: engineering)
  --csv                CSV 형식 추가 출력
```

### 변형률 계산

#### 공학 변형률 (Engineering Strain)

$$\varepsilon_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial x_j} + \frac{\partial u_j}{\partial x_i}\right)$$

#### Green-Lagrange 변형률

$$E_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial X_j} + \frac{\partial u_j}{\partial X_i} + \frac{\partial u_k}{\partial X_i}\frac{\partial u_k}{\partial X_j}\right)$$

#### 로그 변형률 (Logarithmic / True Strain)

$$\varepsilon_{log} = \ln\left(\frac{L}{L_0}\right)$$

### 응력 계산 (선형 탄성, Hooke의 법칙)

라메 상수:

$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}, \quad \mu = \frac{E}{2(1+\nu)}$$

Cauchy 응력:

$$\sigma_{ij} = \lambda \varepsilon_{kk} \delta_{ij} + 2\mu \varepsilon_{ij}$$

### 출력
- `<prefix>_dynain.dat`: `*INITIAL_STRESS_SOLID` 카드
- `<prefix>.csv` (옵션): 요소별 변형률/응력 CSV

### 재료 우선순위
1. 명령행 `--E`, `--nu` 인자 (전체 오버라이드)
2. K-파일 내 `*MAT_ELASTIC` (파트별 자동 인식)

---

## 7. squeeze — 간섭 끼워맞춤

### 용도
간섭(interference fit) 조립 시뮬레이션을 위해 대상 파트를 지정 변형률로
**압축(compress)**하고, 그 역방향 응력을 dynain으로 출력.

### 사용법

```bash
KooRemapper.exe squeeze <mesh.k> <config.yaml> <output_prefix>
```

### YAML 설정

```yaml
parts:
  - pid: 3
    eps_x: -0.02    # x방향 2% 압축
    eps_y: -0.02
    eps_z:  0.0

material:           # 전역 재료 (K-파일 재료 없을 때)
  E: 210000
  nu: 0.3
```

### 동작 원리

파트 바운딩 박스 중심 $\mathbf{c}$에 대해 각 노드 위치:

$$\mathbf{x}' = \mathbf{c} + \begin{pmatrix} 1+\varepsilon_x & 0 & 0 \\ 0 & 1+\varepsilon_y & 0 \\ 0 & 0 & 1+\varepsilon_z \end{pmatrix} (\mathbf{x} - \mathbf{c})$$

초기 응력 (압축에 대한 역방향):

$$\sigma_{xx} = -(\lambda + 2\mu)\varepsilon_x - \lambda(\varepsilon_y + \varepsilon_z)$$

### 출력
- `<prefix>.k`: 압축된 메시
- `<prefix>_dynain.dat`: `*INITIAL_STRESS_SOLID`

---

## 8. generate / generate-var — 메시 생성

### generate — 예제 메시 생성

```bash
KooRemapper.exe generate <type> [options] <output.k>

Types: teardrop, arc, scurve, helix, torus, twist, wave,
       bulge, taper, waterdrop
```

테스트 및 데모용 다양한 기하학적 형상 HEX8 메시 생성.

### generate-var — 변밀도 메시 생성

```bash
KooRemapper.exe generate-var [--ref <ref.k>] [--no-scale] <config.yaml> <output.k>
```

#### YAML 설정 (평면 타입)

```yaml
type: flat
zones:
  - id: 1
    nx: 10
    ny: 8
    nz: 2
    x_min: 0.0
    x_max: 50.0
    y_min: 0.0
    y_max: 40.0
```

#### YAML 설정 (곡선 타입)

```yaml
type: curved
centerline: centerline.dat   # 중심선 좌표 파일
reference: ref_mesh.k        # 참조 두께용
zones:
  - ...
```

---

## 9. assemble — 통합 어셈블리 명령

### 개요

여러 오퍼레이션을 **순차적으로 적용**하는 통합 명령.
기본 모델을 로드하고 각 오퍼레이션을 순서대로 실행하며,
누적된 초기 응력을 단일 dynain 파일로 출력합니다.

```bash
KooRemapper.exe assemble <config.yaml>
```

### 공통 YAML 구조

```yaml
base_model: model.k             # 기본 모델 (필수)
output: result                  # 출력 접두어 (필수)

material:                       # 전역 재료 (선택)
  E: 210000
  nu: 0.3

dynamic_relaxation: true        # *CONTROL_DYNAMIC_RELAXATION 자동 삽입
dynain_embed: false             # true: dynain을 메인 파일에 인라인 삽입

operations:
  - type: <op_type>
    ...
```

### 공통 특성
- **원본 키워드 보존**: `*CONTACT`, `*BOUNDARY`, `*LOAD` 등 미파싱 키워드 그대로 유지
- **응력 누적**: 동일 요소에 여러 오퍼레이션 적용 시 응력 합산(`std::map` 기반)
- **ID 자동 관리**: 파트/섹션/노드/요소 ID 자동 발급 (충돌 방지)

---

### 9.1 replace — 상세 메시 교체

#### 용도
모델 내 특정 파트(coarse)를 상세 메시(detail)로 교체.
선택적으로 굽힘 초기 응력(prestress) 자동 계산.

#### YAML

```yaml
- type: replace
  target_pid: 3           # 교체 대상 파트 ID
  detail_flat: detail.k   # 평면 상세 메시
  shell_bent: bent.k      # 굽힘 QUAD4 셸 참조 (필수)
  prestress: true         # 굽힘 초기 응력 계산 (기본: false)
```

#### 동작
1. `target_pid` 파트 제거
2. `detail_flat` 메시를 `shell_bent` 기준으로 shellmap 매핑
3. 새 노드/요소 ID 발급 (기존 최대 ID + offset)
4. `prestress: true` 시 평면→굽힘 변형률/응력 계산 → dynain 축적

#### ID 재번호화
- 노드: `new_id = old_id + max_node_id`
- 요소: `new_id = old_id + max_elem_id`

---

### 9.2 squeeze (assemble 내)

#### YAML

```yaml
- type: squeeze
  target_pid: 5
  eps_x: -0.015
  eps_y: -0.015
  eps_z:  0.0
```

독립형 `squeeze` 명령과 동일 알고리즘.
`assemble` 파이프라인 내에서 다른 오퍼레이션과 순차 결합 가능.

---

### 9.3 restack — 레이어 재적층

#### 용도
기존 파트를 두께 방향으로 제거하고,
**각기 다른 두께와 재료**를 가진 레이어 스택으로 재생성.

#### YAML

```yaml
- type: restack
  target_pid: 2
  direction: z          # auto | x | y | z
  element_type: solid   # solid | tshell | shell
  layers:
    - thickness: 0.3
      material_card: |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
          MID001  7.85E-09    210000       0.3
    - thickness: 0.5
      material_card: |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
          MID001  2.50E-09     70000       0.33
```

> **참고**: `MID001`, `MID002` 등의 플레이스홀더가 자동으로 실제 MID로 치환됩니다.

#### 동작
1. `target_pid` 파트의 요소 분석 → 두께 방향 결정
2. 표면 메시(QUAD4) 추출
3. 각 레이어를 누적 두께로 압출(extrude)
4. 재료 카드 등록 + 새 파트/섹션/재료 ID 발급

---

### 9.4 bend — 굽힘 변형 + 초기 응력

#### 용도
처짐 함수 w(x₁, x₂)로 기술되는 굽힘을 파트에 적용.
변형(deform) 또는 응력(stress) 모드 선택 가능.

#### YAML

```yaml
- type: bend
  target_pid: 1
  plane: xy           # xy | yz | zx
  mode: deform        # deform (노드 이동) | stress (응력만)
  source: formula     # formula | dat | dat_pair

  # source: formula
  expression: "0.5 * sin(pi * x1 / L1) * sin(pi * x2 / L2)"

  # source: dat
  # dat_file: deflection.dat

  # source: dat_pair
  # dat_top: top.dat
  # dat_bottom: bottom.dat
```

#### 수식 변수

| 변수 | 의미 |
|------|------|
| `x1` | 면내 좌표 1 (바운딩 박스 최소값 기준 상대값) |
| `x2` | 면내 좌표 2 |
| `L1` | x1 방향 바운딩 박스 길이 |
| `L2` | x2 방향 바운딩 박스 길이 |
| `pi` | 원주율 π |

지원 함수: `sin`, `cos`, `tan`, `sqrt`, `exp`, `log`, `abs`, `pow`

#### 굽힘 이론

처짐 함수 w(x₁, x₂)로부터 **곡률**:

$$\kappa_1 = -\frac{\partial^2 w}{\partial x_1^2}, \quad \kappa_2 = -\frac{\partial^2 w}{\partial x_2^2}, \quad \kappa_{12} = -\frac{\partial^2 w}{\partial x_1 \partial x_2}$$

수치 미분 (유한 차분, dat 소스의 경우):

$$\kappa \approx -\frac{w(x+h) - 2w(x) + w(x-h)}{h^2}$$

중립면에서 거리 d인 지점의 굽힘 변형률:

$$\varepsilon_{11} = d \cdot \kappa_1, \quad \varepsilon_{22} = d \cdot \kappa_2, \quad \varepsilon_{12} = d \cdot \kappa_{12}$$

평면응력 가정 하 응력:

$$\sigma_{11} = \frac{E}{1-\nu^2}(\varepsilon_{11} + \nu\varepsilon_{22})$$
$$\sigma_{22} = \frac{E}{1-\nu^2}(\varepsilon_{22} + \nu\varepsilon_{11})$$
$$\sigma_{12} = \frac{E}{1+\nu}\varepsilon_{12}$$

> **주의**: 응력은 노드 변위 적용 **전에** 계산 (중립면 위치 보존).

#### dat 파일 형식

```
# 행: x2_max → x2_min (위→아래), 열: x1_min → x1_max
0.0  0.1  0.3  0.5  0.6
0.1  0.2  0.4  0.6  0.7
...
```

---

### 9.5 indent — 압입 / 엠보싱

#### 용도
폐곡선 경계(다각형 또는 스플라인) 안쪽 영역에 **quarter-arc 필렛 프로파일**로
압입(depth > 0) 또는 엠보싱(depth < 0)을 적용.

#### YAML

```yaml
- type: indent
  target_pid: 2
  plane: xy
  direction: -z
  depth: 2.0          # 양수=압입, 음수=엠보싱
  r1: 1.5             # 펀치 측 필렛 반경
  r2: 1.0             # 다이 측 필렛 반경
  bottom_ratio: 0.5   # 두께 방향 관통 비율 (0~1)
  stress: true        # 굽힘 응력 계산 여부

  shape:
    type: polygon     # polygon | spline
    points:
      - [0.0, 0.0]
      - [10.0, 0.0]
      - [10.0, 8.0]
      - [0.0, 8.0]
```

#### 압입 프로파일 h(d)

부호 있는 거리 d (경계까지의 거리; 양수=내부):

$$k = \frac{\text{depth}}{r_1 + r_2}$$

**r₁ 구역** (0 ≤ d ≤ r₁, 펀치 측 필렛):

$$h(d) = -\text{depth} + k \cdot r_1 \left(1 - \sqrt{1 - \left(\frac{d}{r_1}\right)^2}\right)$$

$$h''(d) = \frac{k r_1 / r_1^2}{\left(1 - (d/r_1)^2\right)^{3/2}} = \frac{k/r_1}{\left(1 - (d/r_1)^2\right)^{3/2}}$$

**평탄 구역** (r₁ < d ≤ D - r₂, D = SDF 최대값):

$$h(d) = -\text{depth}, \quad h''(d) = 0$$

**r₂ 구역** (D - r₂ < d ≤ D, 다이 측 필렛):

$$h(d) = -\text{depth} \left[1 - k \cdot r_2 \left(\frac{1}{k} - \sqrt{1 - \left(\frac{D-d}{r_2}\right)^2}\right) / \text{depth}\right]$$

**엠보싱**: depth < 0 → 위 수식의 정확한 수학적 거울상 (부호만 반전)

#### 부호 있는 거리 함수 (SDF)

경계 다각형에 대한 SDF는 **와인딩 넘버(Winding Number)** 방법으로 계산:

$$w(\mathbf{p}) = \frac{1}{2\pi} \oint_C d\theta$$

내부(w ≠ 0)이면 양수, 외부면 음수.
SDF = 최근접 경계까지의 최소 거리 × 부호

#### 굽힘 응력 (stress: true 시)

구배 방향 (gₓ, gᵧ):

$$\kappa_x = -h''(d) \cdot g_x^2, \quad \kappa_y = -h''(d) \cdot g_y^2, \quad \kappa_{xy} = -h''(d) \cdot g_x g_y$$

> **주의**: 응력은 노드 변위 **전에** 계산.
> h''(d)의 특이점 (d = r₁에서 발산) → `strainLimit / (thickness/2)` 로 상한 제한.

---

### 9.6 formstrain — 성형 소성 변형률

#### 용도
셸 메시의 **이면각(dihedral angle)**으로부터 굽힘 곡률을 계산하여
등가 소성 변형률(EPS)을 `*INITIAL_STRESS_SHELL`로 출력.

#### YAML

```yaml
- type: formstrain
  target_pid: 0          # 0 = 전체 셸 파트 자동 감지
  shell_thickness: 0.0   # 0 = *SECTION_SHELL에서 자동
  min_curvature: 0.001   # 잡음 필터 임계값
```

#### 이론

인접 셸 요소 쌍의 이면각 θ, 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

두께 t인 셸의 표면 굽힘 변형률:

$$\varepsilon = \frac{t}{2} \kappa$$

등가 소성 변형률 (von Mises 기준):

$$\text{EPS} = \frac{2}{\sqrt{3}} \varepsilon = \frac{t}{\sqrt{3} L} \theta$$

항복응력 σᵧ (`*MAT_024` Card 1 Field 5):

$$\sigma = \min(\text{EPS} \cdot E, \sigma_y)$$

> **주의**: 동일 요소에 복수 이웃 곡률이 있을 경우 **최대값(max)** 적용 (합산 아님).

---

### 9.7 tet10 / hex20 / quad8 / tria6 — 2차 요소 변환

#### 용도
1차 요소(TET4, HEX8, QUAD4, TRIA3)를 **2차 요소**로 변환.
각 요소 엣지의 중간점 노드 자동 생성.

#### YAML

```yaml
- type: tet10          # tet10 | hex20 | quad8 | tria6
  target_pid: 0        # 0 = 전체 파트
  elform: 17           # ELFORM 지정 (0=자동)
```

#### 자동 ELFORM 매핑

| convertType | 원본 요소 | 변환 요소 | 기본 ELFORM |
|-------------|-----------|-----------|-------------|
| tet10 | TET4 | TET10 | 17 |
| hex20 | HEX8 | HEX20 | 23 |
| quad8 | QUAD4 | QUAD8 | 23 |
| tria6 | TRIA3 | TRIA6 | 24 |

#### 중간점 노드 생성

엣지 (n₁, n₂)의 중간점:

$$\mathbf{x}_{mid} = \frac{\mathbf{x}_{n_1} + \mathbf{x}_{n_2}}{2}$$

공유 엣지의 중간점은 **단일 노드**로 중복 제거 (`edgeMidNodeMap_` 캐싱).

---

### 9.8 refine — 메시 세분화

#### 용도
요소를 엣지 방향으로 **1:2 또는 1:3** 비율로 균일 세분화.

#### YAML

```yaml
- type: refine
  target_pid: 0    # 0 = 전체
  ratio: 2         # 2 또는 3
```

#### 지원 요소 유형

| 요소 | ratio=2 | ratio=3 |
|------|---------|---------|
| QUAD4 | 4개 서브 쿼드 | 9개 서브 쿼드 |
| TRIA3 | 4개 서브 삼각형 | 9개 서브 삼각형 |
| HEX8 | 8개 서브 헥스 | 27개 서브 헥스 |
| TET4 | 8개 서브 테트 | — |

#### HEX8 ratio=3: 면 내부 노드 중복 제거

인접 요소 간 공유 면의 내부 노드는 **정규 이중선형(canonical bilinear)** 순서로
`faceCenterNodeMap_`에서 중복 없이 공유:

$$\mathbf{x}(s, t) = (1-s)(1-t)\mathbf{x}_0 + s(1-t)\mathbf{x}_1 + st\mathbf{x}_2 + (1-s)t\mathbf{x}_3$$

---

### 9.9 elform — 요소 공식 변경

#### 용도
기존 요소의 **ELFORM** 번호를 변경 (업그레이드/다운그레이드/동일 차수).

#### YAML

```yaml
- type: elform
  target_pid: 0
  target_elform: "17"        # 숫자 또는 별칭
```

#### 고체 요소 별칭

| 별칭 | ELFORM | 설명 |
|------|--------|------|
| `constant_stress` | 1 | 상수 응력 (UR) |
| `fully_integrated` | 2 | 완전 적분 |
| `tet4` | 13 | 4절점 사면체 |
| `tet10` | 17 | 10절점 사면체 |
| `hex20` | 23 | 20절점 헥사 |

#### 셸 요소 별칭

| 별칭 | ELFORM |
|------|--------|
| `belytschko_tsay` | 2 |
| `hughes_liu` | 1 |
| `fully_integrated_shell` | 16 |
| `quad8` | 23 |
| `tria6` | 24 |

---

### 9.10 disconnect — 노드 분리

#### 용도
지정 파트의 경계면 노드를 **분리**하여 비연속 인터페이스 생성.
CZM(응집 구역) 또는 MEFEM(미세균열) 모드 지원.

#### YAML

```yaml
- type: disconnect
  target_pid: 3          # 0 = 전체 파트
  mode: full             # full | czm | mefem

  # mode: czm 추가 설정
  cohesive_part_id: 0    # 0 = 자동 발급

  # mode: mefem 추가 설정
  failure_strain: 0.05   # *MAT_ADD_EROSION EPPF 값
```

#### 모드별 동작

| 모드 | 동작 | LS-DYNA 출력 |
|------|------|-------------|
| `full` | 경계 노드 단순 분리 | 노드 복사만 |
| `czm` | 분리 면에 응집 요소 삽입 | `*ELEMENT_SOLID` (cohesive) + `*MAT_COHESIVE_*` |
| `mefem` | 미세균열 확장 파라미터 설정 | `*MAT_ADD_EROSION` (EPPF 값) |

#### 노드 분리 규칙
- 대상 파트와 인접 파트 간 **공유 노드**만 분리
- 대상 파트 내부 노드는 분리 안 함
- 분리된 노드 쌍은 같은 위치의 새 노드로 대체

---

### 9.11 iga — 등기하해석 NURBS 박스 생성

#### 용도
FE solid 파트를 **3D NURBS B-Spline 박스(trivariate)**로 래핑하여
LS-DYNA IGA(Isogeometric Analysis) 해석 가능하게 변환.
원본 FE 메시는 TETMSH=-1 임베딩으로 그대로 유지됩니다.

#### YAML

```yaml
- type: iga
  targets:
    - target_pid: 1
      element_size: 4.0       # NURBS 복셀 크기 (rr=rs=rt 공통, 필수)
      element_size_r: 2.0     # r방향 개별 지정 (0=element_size 사용)
      element_size_s: 2.0
      element_size_t: 4.0
      offset: -1.0            # bbox 고정 확장량 (-1=auto=element_size)
      bbox_scale: 1.5         # 균일 배율 (IGA박스=파트bbox×1.5)
      bbox_scale_r: 2.0       # r방향 배율 개별 지정
      bbox_scale_s: 1.3
      bbox_scale_t: 1.0
      ir: 0                   # 0=reduced Gauss, 1=full Gauss
      styp: 4                 # LCP stabilization type
      tollg: 1.0e-3           # LCP threshold
      pr: 1                   # r방향 polynomial order
      ps: 1
      pt: 1
      nisr: 1                 # r방향 적분점 수
      niss: 1
      nist: 1
```

#### offset 우선순위 (높→낮)

1. `bbox_scale_r/s/t` — 축별 배율: $\text{off} = \frac{\text{scale}-1}{2} \times \text{len}$
2. `bbox_scale` — 균일 배율 (axis scale이 0인 경우)
3. `offset ≥ 0` — 고정값 (전 방향 동일)
4. 기본값 — element_size per axis

#### bbox_scale 공식

파트 바운딩 박스 길이 $L_r, L_s, L_t$에 대해:

$$\text{off}_r = \frac{\text{scale}_r - 1}{2} \times L_r$$

예) `bbox_scale=1.5`, $L_r=20$ → $\text{off}_r = 0.25 \times 20 = 5.0$

#### 생성 파일

- 메인 출력: `<output>.k` (원본 FE 유지 + `*INCLUDE <output>_iga_p{pid}.k`)
- IGA 파일: `<output>_iga_p{pid}.k` (파트별 별도)

#### IGA 파일 내용

```
*PARAMETER_LOCAL          id, mid, fepid, xmin~zmax, rr~rt,
                          ofr/ofs/oft (실제 offset), ir, styp, tollg
*PARAMETER_EXPRESSION_LOCAL  rxminn=&xmin-&ofr, rxmaxx=&xmax+&ofr, ...
*MAT_*                    원본 재료 복사 (새 MID)
*IGA_DEV_STABILIZATION    LCP 안정화
*PART                     IGA 파트 (새 PID/SECID/MID)
*SECTION_IGA_SOLID        ELFORM=0
*IGA_DEV_VOLUME_XYZ       TETMSH=-1 (원본 FE 임베딩)
*IGA_SOLID                nisr/niss/nist, rid
*IGA_3D_NURBS_XYZ         2×2×2 knot, 8개 제어점, pr/ps/pt
*IGA_REFINE_SOLID         h-refinement (rtyp=2, rr/rs/rt 복셀 크기)
```

#### MID 격리 규칙

**IGA 파트와 일반 FE 파트는 반드시 다른 MID를 사용해야 합니다.**
동일 MID 공유 시 LS-DYNA 오류 발생.
→ `newMid = ++maxMaterialId_` (새 MID 자동 발급 + 재료 카드 복사)
→ 원본 MID는 메인 파일에서 절대 변경하지 않습니다.

#### NURBS 이론 기초

B-Spline 기저 함수 (차수 p, 매듭 벡터 Ξ = {ξ₀, ..., ξₘ}):

$$N_{i,0}(\xi) = \begin{cases} 1 & \text{if } \xi_i \leq \xi < \xi_{i+1} \\ 0 & \text{otherwise} \end{cases}$$

$$N_{i,p}(\xi) = \frac{\xi - \xi_i}{\xi_{i+p} - \xi_i} N_{i,p-1}(\xi) + \frac{\xi_{i+p+1} - \xi}{\xi_{i+p+1} - \xi_{i+1}} N_{i+1,p-1}(\xi)$$

NURBS 곡면 (가중치 wᵢⱼₖ):

$$\mathbf{S}(\xi, \eta, \zeta) = \frac{\sum_{i,j,k} N_{i,p}(\xi) N_{j,q}(\eta) N_{k,r}(\zeta) w_{ijk} \mathbf{P}_{ijk}}{\sum_{i,j,k} N_{i,p}(\xi) N_{j,q}(\eta) N_{k,r}(\zeta) w_{ijk}}$$

h-refinement: 매듭 삽입으로 추가 제어점 생성 (기하 변화 없음).
KooRemapper 생성 NURBS 박스: **2×2×2 knot + rr/rs/rt 균일 세분화**.

---

## 10. matswap — 재료 번들 교체

`*MAT_*`, `*HOURGLASS`, `*DEFINE_CURVE`, `*SECTION_*` 를 하나의 번들 파일로 묶어 특정 파트에 일괄 교체합니다.

### 사용법

```
KooRemapper matswap config.yaml
KooRemapper matswap <model.k> <bundle.k> <pid> <output.k>   # legacy
```

### YAML 포맷

```yaml
model: model.k
output: result.k
swaps:
  - bundle: rubber.k        # PID로 타겟
    pid: 1
  - bundle: foam.k
    pids: [2, 3, 5]         # 복수 PID
  - bundle: steel.k
    swap_all: true           # 모델 전체
  - bundle: mat_update.k
    mid: 5                   # MID로 타겟 (SECTION 교체 안 함)
    mids: [5, 6]             # 복수 MID
```

### 번들 파일 포맷 (`*.k`)

`*PARAMETER` 블록으로 ID를 파라미터화합니다.

```
*PARAMETER
I HGID1            1I LCID1            1
I MID1             1I SECID1           1
I PID1             1
*HOURGLASS_TITLE
Rubber_HG
    &HGID1         5    0.0500 ...
*DEFINE_CURVE_TITLE
...    &LCID1 ...
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
     &MID1 ...
*SECTION_SOLID_TITLE
   &SECID1 ...
*PART
...  &PID1   &SECID1   &MID1   0   &HGID1 ...
*END
```

### MID 타겟 모드 (`mid:` / `mids:`)

MID로 타겟 지정 시 **SECTION 교체를 건너뜁니다** (ELFORM 호환성 유지).
MAT + HOURGLASS + DEFINE_CURVE 만 교체됩니다.

### 파라미터 이름 접두사 규칙

| 접두사 | ID 종류 | 동작 |
|--------|---------|------|
| `HGID*` | Hourglass ID | 항상 새 ID (모델 최대+1) |
| `LCID*` | Curve ID | 항상 새 ID |
| `SECID*` | Section ID | 항상 새 ID |
| `MID*` | Material ID | 고아 ID 재사용 가능 |
| `PID*` | Part ID | 무시 (PART 카드 미삽입) |

---

## 11. implicit — Explicit→Implicit 변환

Explicit LS-DYNA K 파일을 Implicit 해석 설정으로 변환합니다.

### 사용법

```
KooRemapper implicit config.yaml
```

### YAML 포맷

```yaml
model: explicit.k
output: implicit.k
mode: static          # static(IMASS=0) | dynamic(IMASS=1)
level: 2              # 1(공격적) ~ 8(좌굴/스냅스루)
endtime: 1.0          # *CONTROL_TERMINATION endtim 갱신 + DT 기준값

# 세부 오버라이드 (생략 시 level 기본값)
# dctol:      0.001   # 변위 수렴 허용치
# ectol:      0.010   # 에너지 수렴 허용치
# dt0:        0.002   # 초기 시간 스텝
# dtmax:      0.010   # 최대 시간 스텝
# nsolvr:     12      # 비선형 솔버 (12=BFGS, -2=BFGS+LS)
# kfail:      3       # 연속 step bisection 후 강성 재구성 횟수
# rctol:      1.0e10  # 잔류력 수렴 허용치 (1e10=비활성)
# lsolvr:     7       # 선형 솔버 (7=기본, 30=MUMPS)
# stab:       false   # *CONTROL_IMPLICIT_STABILIZATION on/off
# stab_scale: 1.0     # Stabilization SCALE (1.0=일반, 0.001=스프링백)
# arc_length: false   # Arc-length (Crisfield), 좌굴/스냅스루 전용

# 정리 옵션
# fix_shell_elform: false   # ELFORM=16 → 2 자동 수정
# keep_dr_curves:   false   # SIDR=1 DEFINE_CURVE 유지
```

### 레벨 스펙트럼

#### Table 1 — 비선형 솔버 & 수렴 허용치

| Lv | 이름 | NSOLVR | ILIMIT | MAXREF | ITEOPT | KFAIL | DCTOL | ECTOL | LSTOL | RCTOL |
|----|------|--------|--------|--------|--------|-------|-------|-------|-------|-------|
| 1 | 공격적 | 12 | 11 | 10 | 11 | 0 | 0.0050 | 0.0500 | 0.90 | off |
| 2 | 표준 | 12 | 11 | 15 | 11 | 0 | 0.0010 | 0.0100 | 0.90 | off |
| 3 | 안정 | 12 | 15 | 20 | 11 | 0 | 0.0010 | 0.0100 | 0.95 | off |
| 4 | 수렴우선 | -2 | 20 | 25 | 11 | 3 | 0.0010 | 0.0100 | 0.95 | off |
| 5 | 강건 | -2 | 25 | 30 | 15 | 5 | 0.0010 | 0.0050 | 0.99 | off |
| 6 | 고강건 | -2 | 30 | 40 | 15 | 8 | 0.0005 | 0.0020 | 0.99 | 0.1 |
| 7 | 최대안정 | -2 | 40 | 50 | 20 | 15 | 0.0001 | 0.0010 | 0.99 | 0.01 |
| 8 | 좌굴/스냅스루 | 7* | 40 | 50 | 20 | 15 | 0.0001 | 0.0010 | 0.99 | 0.01 |

> NSOLVR=7: Full Newton — arc-length 기능은 NSOLVR 6~9 범위 필요

#### Table 2 — 시간 스텝 & 활성화 기능 (T = endtime)

| Lv | DT0 | DTMAX | DTMIN | LSOLVR | STAB | ARC-LENGTH |
|----|-----|-------|-------|--------|------|------------|
| 1 | T/100 | T/20 | −T/1000 | 7 (기본) | off | off |
| 2 | T/500 | T/100 | −T/10000 | 7 (기본) | off | off |
| 3 | T/1000 | T/200 | −T/10000 | 7 (기본) | off | off |
| 4 | T/2000 | T/500 | −T/100000 | 7 (기본) | off | off |
| 5 | T/5000 | T/1000 | −T/100000 | 7 (기본) | **ON** | off |
| 6 | T/10000 | T/2000 | −T/100000 | **30 (MUMPS)** | ON | off |
| 7 | T/50000 | T/10000 | −T/1000000 | 30 (MUMPS) | ON | off |
| 8 | T/50000 | T/10000 | −T/1000000 | 30 (MUMPS) | ON | **ON (Crisfield)** |

### 기능 설명

| 기능 | 키워드 | 설명 |
|------|--------|------|
| **KFAIL** | `*CONTROL_IMPLICIT_AUTO` | N회 연속 step bisection 후 접선 강성 행렬 재구성 |
| **LSTOL** | `*CONTROL_IMPLICIT_SOLUTION` | Line search 수렴 허용치 (NSOLVR=-2 전용) |
| **RCTOL** | `*CONTROL_IMPLICIT_SOLUTION` | 잔류력 노름 수렴 기준 (1e10=비활성, 활성화 시 DCTOL과 AND 조건) |
| **STAB** | `*CONTROL_IMPLICIT_STABILIZATION` | IAS=1: 인공 강성 추가. Rigid body mode, 스프링백 하중 경로, singular K 방지 |
| **MUMPS** | `*CONTROL_IMPLICIT_SOLVER` | LSOLVR=30: 병렬 직접 솔버. ill-conditioned 행렬, 복잡한 contact 모델에 강건 |
| **ARC-LENGTH** | `*CONTROL_IMPLICIT_SOLUTION` Card 3 | Crisfield arc-length: 하중-변위 곡선 음의 기울기 구간 추적 (좌굴, 스냅스루) |

### 처리 파이프라인

#### 제거 (항상)

- `*CONTROL_DYNAMIC_RELAXATION` — DR 사전 하중 (implicit 불필요)
- `*CONTROL_BULK_VISCOSITY` — 체적 점성 (explicit 전용)
- `*DATABASE_BINARY_D3DRLF` — DR 출력 DB

#### 제거 (선택적)

- `*DEFINE_CURVE` (SIDR=1) — DR 하중 곡선 (`keep_dr_curves: false` 시)

#### 수정

- `*CONTROL_TIMESTEP` → TSSFAC=0.90, DT2MS=0.0
- `*CONTROL_TERMINATION` → endtim 갱신 (`endtime:` 지정 시)

#### 삽입 (항상)

- `*CONTROL_IMPLICIT_GENERAL` — IMFLAG=1, IMFORM=2, IGS=2
- `*CONTROL_IMPLICIT_DYNAMICS` — IMASS, GAMMA, BETA
- `*CONTROL_IMPLICIT_SOLUTION` — NSOLVR, ILIMIT, MAXREF, 수렴 허용치
- `*CONTROL_IMPLICIT_AUTO` — IAUTO=1, ITEOPT, DTMIN/DTMAX, KFAIL

#### 삽입 (Level 5+)

- `*CONTROL_IMPLICIT_STABILIZATION` — `stab: true` 또는 Level 5+

#### 삽입 (Level 6+)

- `*CONTROL_IMPLICIT_SOLVER` — `lsolvr: 30` (MUMPS) 또는 Level 6+

#### 삽입 (Level 8)

- `*CONTROL_IMPLICIT_SOLUTION` Card 3 — arc-length 파라미터 (`arc_length: true` 또는 Level 8)

### mode: static vs dynamic

| 파라미터 | static (준정적) | dynamic (구조동역학) |
|----------|----------------|-------------------|
| IMASS | 0 | 1 |
| GAMMA | 0.5 | 0.6 |
| BETA | 0.25 | 0.30 |
| 비고 | Newmark 표준 | 수치 감쇠 있는 Newmark (고주파 불안정 억제) |

---

## 12. 수학 이론

### 12.1 등매개변수 매핑 (map)

HEX8 요소의 자연 좌표계 (ξ, η, ζ) ∈ [-1, 1]³:

$$\mathbf{x}(\xi,\eta,\zeta) = \sum_{i=1}^{8} N_i(\xi,\eta,\zeta)\,\mathbf{x}_i$$

역매핑 (Newton-Raphson):

$$\begin{pmatrix} \Delta\xi \\ \Delta\eta \\ \Delta\zeta \end{pmatrix} = \mathbf{J}^{-1} (\mathbf{x}_{target} - \mathbf{x}(\xi,\eta,\zeta))$$

야코비안 행렬:

$$J_{ij} = \frac{\partial x_i}{\partial \xi_j} = \sum_{k=1}^{8} \frac{\partial N_k}{\partial \xi_j} x_{ki}$$

### 12.2 선형 탄성 재료 모델

라메 상수:

$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}, \quad \mu = G = \frac{E}{2(1+\nu)}$$

구성 방정식 (Voigt 표기):

$$\begin{pmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \sigma_{zz} \\ \sigma_{xy} \\ \sigma_{yz} \\ \sigma_{xz} \end{pmatrix} = \begin{pmatrix} \lambda+2\mu & \lambda & \lambda & 0 & 0 & 0 \\ \lambda & \lambda+2\mu & \lambda & 0 & 0 & 0 \\ \lambda & \lambda & \lambda+2\mu & 0 & 0 & 0 \\ 0 & 0 & 0 & \mu & 0 & 0 \\ 0 & 0 & 0 & 0 & \mu & 0 \\ 0 & 0 & 0 & 0 & 0 & \mu \end{pmatrix} \begin{pmatrix} \varepsilon_{xx} \\ \varepsilon_{yy} \\ \varepsilon_{zz} \\ 2\varepsilon_{xy} \\ 2\varepsilon_{yz} \\ 2\varepsilon_{xz} \end{pmatrix}$$

### 12.3 Kirchhoff 판 이론 (bend/indent)

중립면에서 거리 z인 지점의 변형률:

$$\varepsilon_{11}(z) = -z \kappa_{11}, \quad \varepsilon_{22}(z) = -z \kappa_{22}, \quad 2\varepsilon_{12}(z) = -2z \kappa_{12}$$

모멘트-곡률 관계 (굽힘 강성 D):

$$D = \frac{E t^3}{12(1-\nu^2)}$$

$$M_{11} = D(\kappa_{11} + \nu \kappa_{22}), \quad M_{22} = D(\kappa_{22} + \nu \kappa_{11}), \quad M_{12} = D(1-\nu)\kappa_{12}$$

### 12.4 형성 변형률 이론 (formstrain)

이면각 θ, 인접 셸 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

면외 굽힘 변형률 (두께 방향 선형 분포):

$$\varepsilon_{top} = +\frac{t}{2}\kappa, \quad \varepsilon_{bot} = -\frac{t}{2}\kappa$$

등가 소성 변형률 (Von Mises 기준, 단축 가정):

$$\overline{\varepsilon}^p = \frac{2}{\sqrt{3}} |\varepsilon_{max}|$$

---

## 13. 출력 파일 형식

### dynain 파일 (`*INITIAL_STRESS_SOLID`)

```
*INITIAL_STRESS_SOLID
$#     eid    numint
   12345         1
$# hisv1 ~ hisv7 (미사용, 0)
         0         0         0         0         0         0         0
$#  sig-xx    sig-yy    sig-zz    sig-xy    sig-yz    sig-xz
  5654.00  2423.00  2423.00     0.00     0.00     0.00
```

### IGA 포함 메인 파일 구조

```
*KEYWORD
...원본 FE 키워드...
*INCLUDE
 result_iga_p1.k
*END
```

### dynain embed 모드 (`dynain_embed: true`)

별도 `.dynain` 파일 없이 `*INITIAL_STRESS_SOLID` 블록을 메인 `.k` 파일에 직접 삽입.

---

*KooRemapper v1.1.0 | 이 문서는 모든 구현 기능을 포함합니다.*
