# KooRemapper 기능 설명서

> **버전 1.3.0** | LS-DYNA 메시 전처리 도구
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
9. [unfold — 굽힘 메시 전개](#9-unfold--굽힘-메시-전개)
10. [strain — 변형률 계산](#10-strain--변형률-계산)
11. [info — 메시 정보](#11-info--메시-정보)
12. [restack — 레이어 재적층](#12-restack--레이어-재적층)
13. [bend — 굽힘 변형 + 초기 응력](#13-bend--굽힘-변형--초기-응력)
14. [indent — 압입/엠보싱](#14-indent--압입엠보싱)
15. [formstrain — 성형 소성 변형률](#15-formstrain--성형-소성-변형률)
16. [convert — 2차 요소 변환](#16-convert--2차-요소-변환)
17. [refine — 메시 세분화](#17-refine--메시-세분화)
18. [elform — 요소 공식 변경](#18-elform--요소-공식-변경)
19. [disconnect — 노드 분리](#19-disconnect--노드-분리)
20. [iga — 등기하해석 NURBS 박스 생성](#20-iga--등기하해석-nurbs-박스-생성)
21. [warpage — 워피지 보정](#21-warpage--워피지-보정)
22. [offset — 셸 오프셋 솔리드 생성](#22-offset--셸-오프셋-솔리드-생성)
23. [matswap — 재료 번들 교체](#23-matswap--재료-번들-교체)
24. [matdb — 재료 DB 교체](#24-matdb--재료-db-교체)
25. [contact — 접촉 정의 관리](#25-contact--접촉-정의-관리)
    - 25.1 [analyze — 접촉 분석](#251-analyze--접촉-분석)
    - 25.2 [create — 접촉 생성](#252-create--접촉-생성)
    - 25.3 [convert — 접촉 변환](#253-convert--접촉-변환)
    - 25.4 [modify — 접촉 수정](#254-modify--접촉-수정)
    - 25.5 [remove — 접촉 삭제](#255-remove--접촉-삭제)
    - 25.6 [detect — 접촉 자동 감지](#256-detect--접촉-자동-감지)
    - 25.7 [세부 옵션 (Optional Cards A~G)](#257-세부-옵션-optional-cards-ag)
26. [load — 하중 적용](#26-load--하중-적용)
27. [boundary — 경계 조건 적용](#27-boundary--경계-조건-적용)
28. [rbe — RBE 구속 조건](#28-rbe--rbe-구속-조건)
29. [implicit — Explicit→Implicit 변환](#29-implicit--explicitimplicit-변환)
30. [modal — 고유진동수(모달) 해석 변환](#30-modal--고유진동수모달-해석-변환)
31. [relax — Dynamic Relaxation 설정](#31-relax--dynamic-relaxation-설정)
32. [explicit — 순수 Explicit 복원](#32-explicit--순수-explicit-복원)
33. [wrap — 와인딩 인장 프리스트레스](#33-wrap--와인딩-인장-프리스트레스)
34. [optimize — 재료별 해석 최적화](#34-optimize--재료별-해석-최적화)
35. [ale — ALE 변환](#35-ale--ale-변환)
36. [stabilize — Explicit 솔버 안정화](#36-stabilize--explicit-솔버-안정화)
37. [database — DATABASE 출력 제어](#37-database--database-출력-제어)
38. [키워드 제거(strip) 기능](#38-키워드-제거strip-기능)
39. [assemble — 통합 어셈블리](#39-assemble--통합-어셈블리)
    - 39.1 [replace](#391-replace--상세-메시-교체)
    - 39.2 [squeeze (assemble 내)](#392-squeeze-assemble-내)
    - 39.3 [restack](#393-restack--레이어-재적층)
    - 39.4 [bend](#394-bend--굽힘-변형--초기-응력)
    - 39.5 [indent](#395-indent--압입--엠보싱)
    - 39.6 [formstrain](#396-formstrain--성형-소성-변형률)
    - 39.7 [tet10 / hex20 / quad8 / tria6](#397-tet10--hex20--quad8--tria6--2차-요소-변환)
    - 39.8 [refine](#398-refine--메시-세분화)
    - 39.9 [elform](#399-elform--요소-공식-변경)
    - 39.10 [disconnect](#3910-disconnect--노드-분리)
    - 39.11 [iga](#3911-iga--등기하해석-nurbs-박스-생성)
    - 39.12 [warpage](#3912-warpage--워피지-보정)
    - 39.13 [offset](#3913-offset--셸-오프셋-솔리드-생성)
    - 39.14 [matswap](#3914-matswap--재료-번들-교체)
    - 39.15 [matdb](#3915-matdb--재료-db-교체)
    - 39.16 [wrap](#3916-wrap--와인딩-인장-프리스트레스)
40. [수학 이론](#40-수학-이론)
41. [출력 파일 형식](#41-출력-파일-형식)

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
| **형상 변형** | 굽힘(bend), 압입(indent), 엠보싱(emboss), 워피지(warpage) |
| **적층 구조** | 레이어별 두께·재료 재정의(restack) |
| **성형 변형** | 이면각 기반 소성 변형률(formstrain) |
| **메시 변환** | 2차 요소 변환(TET10/HEX20 등), 세분화(refine), ELFORM 변경 |
| **토폴로지** | 노드 분리(disconnect), CZM·MEFEM 인터페이스 생성 |
| **등기하해석** | FE solid → IGA NURBS box 래핑(IGA) |
| **셸 오프셋** | 셸 표면 추출 → 솔리드 압출(offset) |
| **재료 관리** | 재료 번들 교체(matswap), 재료 DB 교체(matdb) |
| **메시 생성** | 변밀도 메시 생성(generate-var) |
| **해석 설정** | Implicit/Modal/DR/ALE/Stabilize 변환 |
| **출력 관리** | DATABASE 출력 제어 키워드 삽입 (8종 프리셋) |

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
  # 메시 처리
  map            HEX8 구조화 메시를 굽힘 참조 형상에 매핑
  shellmap       QUAD4 셸 참조 기반 상세 메시 매핑
  unfold         굽힘 구조화 메시로부터 평면 메시 전개
  generate       테스트용 예제 메시 생성
  generate-var   YAML 설정 기반 변밀도 메시 생성

  # 분석
  strain         두 메시 간 변형률 계산
  prestress      변형 형상 기반 초기 응력 계산 + dynain 출력
  info           메시 파일 정보 출력

  # 형상 변형 (단독 실행)
  squeeze        간섭 끼워맞춤 초기 변형 계산
  restack        레이어 재적층
  bend           굽힘 변형 + 초기 응력
  indent         압입 / 엠보싱 변형
  formstrain     성형 소성 변형률 계산
  warpage        워피지(면외 변형) 보정
  offset         셸 오프셋 솔리드 생성
  wrap           와인딩 인장 프리스트레스

  # 메시 변환
  convert        2차 요소 변환 (TET10/HEX20/QUAD8/TRIA6)
  refine         메시 세분화 (1:2, 1:3)
  elform         요소 공식(ELFORM) 변경
  disconnect     파트 간 노드 분리 (full/czm/mefem)
  iga            등기하해석(IGA) NURBS 박스 생성

  # 재료/접촉 관리
  matswap        재료 번들 교체
  matdb          재료 DB 교체
  contact        접촉 정의 분석/생성/변환/수정/삭제/자동감지

  # 하중/경계 조건
  load           하중 적용
  boundary       경계 조건 적용
  rbe            RBE 구속 조건

  # 해석 설정
  implicit       Explicit → Implicit 해석 변환
  modal          고유진동수(모달) 해석 변환
  relax          Dynamic Relaxation 설정
  explicit       순수 Explicit 복원 (모든 비-Explicit 키워드 제거)
  optimize       재료별 해석 최적화
  ale            ALE(Arbitrary Lagrangian-Eulerian) 변환
  stabilize      Explicit 솔버 안정화 (12단계)
  database       DATABASE 출력 제어 키워드 삽입

  # 통합 실행
  assemble       다중 오퍼레이션 통합 어셈블리

  # 유틸리티
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
# 방법 1: 직접 변형률 지정 (노드 이동 + dynain)
parts:
  - pid: 3
    eps_x: -0.02    # x방향 2% 압축
    eps_y: -0.02
    eps_z:  0.0

# 방법 2: 등방 팽창(swelling) — 열팽창 카드 삽입
  - pid: 5
    swelling: 0.01  # 1% 등방 팽창

material:           # 전역 재료 (K-파일 재료 없을 때)
  E: 210000
  nu: 0.3
```

### 동작 원리

**방법 1 (eps_x/y/z):** 파트 바운딩 박스 중심 $\mathbf{c}$에 대해 각 노드 위치:

$$\mathbf{x}' = \mathbf{c} + \begin{pmatrix} 1+\varepsilon_x & 0 & 0 \\ 0 & 1+\varepsilon_y & 0 \\ 0 & 0 & 1+\varepsilon_z \end{pmatrix} (\mathbf{x} - \mathbf{c})$$

초기 응력 (압축에 대한 역방향):

$$\sigma_{xx} = -(\lambda + 2\mu)\varepsilon_x - \lambda(\varepsilon_y + \varepsilon_z)$$

**방법 2 (swelling):** 노드를 이동하지 않고 LS-DYNA 열팽창 카드를 삽입합니다.
- `*MAT_ADD_THERMAL_EXPANSION` (LCID=0, 등방 ALPHA = swelling)
- `*INITIAL_TEMPERATURE` (모든 노드, T=1.0)
- `*LOAD_THERMAL_VARIABLE` (LCID=온도 커브 ID)
- 해석 시 LS-DYNA가 자동으로 열팽창을 적용

swelling 파트는 dynain에 포함되지 않습니다.

### 출력
- `<prefix>.k`: 압축된 메시 + 열팽창 카드 (swelling 파트)
- `<prefix>_dynain.dat`: `*INITIAL_STRESS_SOLID` (eps 파트만)

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

## 9. unfold — 굽힘 메시 전개

### 용도
굽힘(bent) 구조화 HEX8 메시로부터 **평면(flat) 전개 메시**를 생성합니다.
`map` 명령의 역방향 연산으로, 굽힘 구조화 메시의 호 길이(arc-length) 매개변수화를 사용하여
평면 형상을 복원합니다.

### 사용법

```bash
KooRemapper.exe unfold <bent_mesh.k> <output_flat.k>
```

### 파라미터

| 파라미터 | 설명 |
|----------|------|
| `bent_mesh.k` | 굽힘 구조화 HEX8 메시 (입력) |
| `output_flat.k` | 전개된 평면 메시 (출력) |

### 동작 원리

1. 입력 메시의 구조화 격자 차원(I, J, K) 자동 감지
2. 각 축 방향으로 호 길이(arc-length) 계산
3. 호 길이를 기반으로 평면 좌표 재매핑

### 출력

- `output_flat.k`: 전개된 평면 메시
- 콘솔: 격자 차원(I, J, K) 및 평면 길이(I=호 길이, J, K) 출력

### 주의사항
- 입력 메시는 반드시 **규칙적 HEX8 구조화 메시**여야 합니다
- 비구조화 메시에는 사용할 수 없습니다

---

## 10. strain — 변형률 계산

### 용도
**기준 형상(reference)**과 **변형 형상(deformed)** 메시 쌍 간의 변형률을 계산하여
CSV 파일로 출력합니다.

### 사용법

```bash
KooRemapper.exe strain <ref_mesh.k> <def_mesh.k> <output.csv> [--type engineering|green|log]
```

### 파라미터

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `ref_mesh.k` | 기준 형상 메시 (입력) | — |
| `def_mesh.k` | 변형 형상 메시 (입력) | — |
| `output.csv` | 변형률 결과 CSV (출력) | — |
| `--type` | 변형률 계산 방식 | `engineering` |

### 변형률 유형

| 유형 | 설명 |
|------|------|
| `engineering` | 공학 변형률 (소변형 가정) |
| `green` | Green-Lagrange 변형률 (대변형, 비선형 항 포함) |
| `log` | 로그 변형률 (진변형률, 대변형) |

### 출력

- `output.csv`: 요소별 6개 변형률 성분 (εxx, εyy, εzz, εxy, εyz, εxz)

---

## 11. info — 메시 정보

### 용도
LS-DYNA K-파일의 메시 정보를 분석하여 콘솔에 출력합니다.

### 사용법

```bash
KooRemapper.exe info <mesh_file.k>
```

### 출력 정보

| 항목 | 설명 |
|------|------|
| 파일명 | 입력 K-파일 이름 |
| 노드 수 | 전체 노드 개수 |
| 요소 수 | 전체 요소 개수 |
| 파트 수 | 파트 개수 |
| 바운딩 박스 | X/Y/Z 최소~최대 범위 |
| 크기 | X/Y/Z 방향 길이 |
| 검증 결과 | 메시 유효성 검사 |
| 요소 품질 | Jacobian 최소/최대, 음수 Jacobian 요소 수 |

---

## 12. restack — 레이어 재적층

### 용도
기존 파트를 두께 방향으로 제거하고, **각기 다른 두께와 재료**를 가진 레이어 스택으로 재생성합니다.

### 사용법

```bash
KooRemapper.exe restack <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: restacked
target_pid: 1
direction: z              # auto | x | y | z (적층 방향)
element_type: solid       # solid | tshell | shell
material:
  E: 210000
  nu: 0.3
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

### 파라미터

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `model` | 입력 K-파일 | — |
| `output` | 출력 접두어 | — |
| `target_pid` | 대상 파트 ID | — |
| `direction` | 적층 방향 (auto/x/y/z) | `auto` |
| `element_type` | 요소 유형 | `solid` |
| `layers` | 레이어 리스트 (thickness + material_card) | — |

> **참고**: `MID001`, `MID002` 등의 플레이스홀더가 자동으로 실제 MID로 치환됩니다.

### 동작
1. `target_pid` 파트의 요소 분석 → 두께 방향 결정
2. 표면 메시(QUAD4) 추출
3. 각 레이어를 누적 두께로 압출(extrude)
4. 재료 카드 등록 + 새 파트/섹션/재료 ID 발급

---

## 13. bend — 굽힘 변형 + 초기 응력

### 용도
처짐 함수 w(x₁, x₂)로 기술되는 굽힘을 파트에 적용합니다.
변형(deform) 또는 응력(stress) 모드 선택 가능.

### 사용법

```bash
KooRemapper.exe bend <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: bent
target_pid: 1
plane: xy               # xy | yz | zx (굽힘 평면)
mode: deform            # deform (노드 이동) | stress (응력만)
source: formula         # formula | dat | dat_pair

# source: formula
expression: "0.5 * sin(pi * x1 / L1) * sin(pi * x2 / L2)"

# source: dat
# dat_file: deflection.dat

# source: dat_pair
# dat_top: top.dat
# dat_bottom: bottom.dat

material:
  E: 210000
  nu: 0.3
```

### 수식 변수

| 변수 | 의미 |
|------|------|
| `x1` | 면내 좌표 1 (바운딩 박스 최소값 기준 상대값) |
| `x2` | 면내 좌표 2 |
| `L1` | x1 방향 바운딩 박스 길이 |
| `L2` | x2 방향 바운딩 박스 길이 |
| `pi` | 원주율 π |

지원 함수: `sin`, `cos`, `tan`, `sqrt`, `exp`, `log`, `abs`, `pow`

### 굽힘 이론

처짐 함수 w(x₁, x₂)로부터 **곡률**:

$$\kappa_1 = -\frac{\partial^2 w}{\partial x_1^2}, \quad \kappa_2 = -\frac{\partial^2 w}{\partial x_2^2}, \quad \kappa_{12} = -\frac{\partial^2 w}{\partial x_1 \partial x_2}$$

중립면에서 거리 d인 지점의 굽힘 변형률:

$$\varepsilon_{11} = d \cdot \kappa_1, \quad \varepsilon_{22} = d \cdot \kappa_2, \quad \varepsilon_{12} = d \cdot \kappa_{12}$$

> **주의**: 응력은 노드 변위 적용 **전에** 계산 (중립면 위치 보존).

### dat 파일 형식

```
# 행: x2_max → x2_min (위→아래), 열: x1_min → x1_max
0.0  0.1  0.3  0.5  0.6
0.1  0.2  0.4  0.6  0.7
...
```

---

## 14. indent — 압입/엠보싱

### 용도
폐곡선 경계(다각형 또는 스플라인) 안쪽 영역에 **quarter-arc 필렛 프로파일**로
압입(depth > 0) 또는 엠보싱(depth < 0)을 적용합니다.

### 사용법

```bash
KooRemapper.exe indent <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: indented
target_pid: 1
plane: xy
direction: -z
depth: 2.0              # 양수=압입, 음수=엠보싱
r1: 1.5                 # 펀치 측 필렛 반경
r2: 1.0                 # 다이 측 필렛 반경
bottom_ratio: 0.5       # 두께 방향 관통 비율 (0~1)
stress: true            # 굽힘 응력 계산 여부
shell_thickness: 1.0    # 셸 두께 (셸 요소일 때)

shape:
  type: polygon         # polygon | spline
  points:
    - [0.0, 0.0]
    - [10.0, 0.0]
    - [10.0, 8.0]
    - [0.0, 8.0]

material:
  E: 210000
  nu: 0.3
```

### 파라미터

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `depth` | 압입 깊이 (양수=압입, 음수=엠보싱) | — |
| `r1` | 펀치 측(내부) 필렛 반경 | — |
| `r2` | 다이 측(외부) 필렛 반경 | — |
| `bottom_ratio` | 두께 방향 관통 비율 | `0.5` |
| `stress` | 굽힘 응력 계산 여부 | `false` |
| `shell_thickness` | 셸 요소 두께 | 자동 |

### 압입 프로파일

부호 있는 거리 d에서의 프로파일 함수 h(d):

$$k = \frac{\text{depth}}{r_1 + r_2}$$

**r₁ 구역** (0 ≤ d ≤ r₁): $h(d) = -\text{depth} + k \cdot r_1 (1 - \sqrt{1 - (d/r_1)^2})$

**평탄 구역** (r₁ < d ≤ D - r₂): $h(d) = -\text{depth}$

**r₂ 구역** (D - r₂ < d ≤ D): 역 quarter-arc 천이

> **주의**: 응력은 노드 변위 **전에** 계산. h''(d) 특이점 → `strainLimit / (thickness/2)` 상한 제한.

---

## 15. formstrain — 성형 소성 변형률

### 용도
셸 메시의 **이면각(dihedral angle)**으로부터 굽힘 곡률을 계산하여
등가 소성 변형률(EPS)을 `*INITIAL_STRESS_SHELL`로 출력합니다.

### 사용법

```bash
KooRemapper.exe formstrain <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: formed
target_pid: 0            # 0 = 전체 셸 파트 자동 감지
shell_thickness: 0.0     # 0 = *SECTION_SHELL에서 자동
min_curvature: 0.001     # 잡음 필터 임계값
```

### 이론

인접 셸 요소 쌍의 이면각 θ, 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

등가 소성 변형률:

$$\text{EPS} = \frac{t}{\sqrt{3} L} \theta$$

> 동일 요소에 복수 이웃 곡률이 있을 경우 **최대값(max)** 적용 (합산 아님).

---

## 16. convert — 2차 요소 변환

### 용도
1차 요소(TET4, HEX8, QUAD4, TRIA3)를 **2차 요소**로 변환합니다.

### 사용법

```bash
KooRemapper.exe convert <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: converted
target_pid: 0            # 0 = 전체 파트
convert_type: tet10      # tet10 | hex20 | quad8 | tria6
elform: 0                # ELFORM 지정 (0=자동)
```

### 자동 ELFORM 매핑

| convertType | 원본 요소 | 변환 요소 | 기본 ELFORM |
|-------------|-----------|-----------|-------------|
| tet10 | TET4 | TET10 | 17 |
| hex20 | HEX8 | HEX20 | 23 |
| quad8 | QUAD4 | QUAD8 | 23 |
| tria6 | TRIA3 | TRIA6 | 24 |

---

## 17. refine — 메시 세분화

### 용도
요소를 엣지 방향으로 **1:2 또는 1:3** 비율로 균일 세분화합니다.

### 사용법

```bash
KooRemapper.exe refine <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: refined
target_pid: 0            # 0 = 전체
ratio: 2                 # 2 또는 3
```

### 지원 요소 유형

| 요소 | ratio=2 | ratio=3 |
|------|---------|---------|
| QUAD4 | 4개 서브 쿼드 | 9개 서브 쿼드 |
| TRIA3 | 4개 서브 삼각형 | 9개 서브 삼각형 |
| HEX8 | 8개 서브 헥스 | 27개 서브 헥스 |
| TET4 | 8개 서브 테트 | — |

---

## 18. elform — 요소 공식 변경

### 용도
기존 요소의 **ELFORM** 번호를 변경합니다.

### 사용법

```bash
KooRemapper.exe elform <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: modified
target_pid: 0
target_elform: "2"       # 숫자 또는 별칭
```

### 고체 요소 별칭

| 별칭 | ELFORM | 설명 |
|------|--------|------|
| `constant_stress` | 1 | 상수 응력 (UR) |
| `fully_integrated` | 2 | 완전 적분 |
| `tet4` | 13 | 4절점 사면체 |
| `tet10` | 17 | 10절점 사면체 |
| `hex20` | 23 | 20절점 헥사 |

### 셸 요소 별칭

| 별칭 | ELFORM |
|------|--------|
| `belytschko_tsay` | 2 |
| `hughes_liu` | 1 |
| `fully_integrated_shell` | 16 |
| `quad8` | 23 |
| `tria6` | 24 |

---

## 19. disconnect — 노드 분리

### 용도
지정 파트의 경계면 노드를 **분리**하여 비연속 인터페이스를 생성합니다.

### 사용법

```bash
KooRemapper.exe disconnect <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: disconnected
target_pid: 1
mode: full               # full | czm | mefem
cohesive_part_id: 0      # CZM 모드 파트 ID (0=자동)
failure_strain: 0.05     # CZM 파괴 변형률
```

### 모드별 동작

| 모드 | 동작 | LS-DYNA 출력 |
|------|------|-------------|
| `full` | 경계 노드 단순 분리 + PERI 요소 | `*SECTION_SOLID_PERI` (ELFORM=48, DR=1.01) |
| `czm` | 분리 면에 응집 요소 삽입 | `*ELEMENT_SOLID` (cohesive) + `*MAT_COHESIVE_*` |
| `mefem` | 미세균열 확장 파라미터 설정 | `*MAT_ADD_EROSION` (EPPF 값) |

---

## 20. iga — 등기하해석 NURBS 박스 생성

### 용도
FE solid 파트를 **3D NURBS B-Spline 박스(trivariate)**로 래핑하여
LS-DYNA IGA(Isogeometric Analysis) 해석 가능하게 변환합니다.

### 사용법

```bash
KooRemapper.exe iga <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: iga_result
targets:
  - target_pid: 1
    element_size: 4.0       # NURBS 복셀 크기 (rr=rs=rt 공통)
    element_size_r: 2.0     # r방향 개별 지정 (0=element_size 사용)
    element_size_s: 2.0
    element_size_t: 4.0
    offset: -1.0            # bbox 확장량 (-1=auto)
    bbox_scale: 1.5         # 균일 배율
    bbox_scale_r: 2.0       # 축별 배율
    bbox_scale_s: 1.3
    bbox_scale_t: 1.0
    ir: 0                   # 0=reduced Gauss, 1=full Gauss
    styp: 4                 # LCP stabilization type
    tollg: 1.0e-3           # LCP threshold
    pr: 1                   # polynomial order (r/s/t)
    ps: 1
    pt: 1
    nisr: 1                 # 적분점 수 (r/s/t)
    niss: 1
    nist: 1
```

### offset 우선순위 (높→낮)

1. `bbox_scale_r/s/t` — 축별 배율
2. `bbox_scale` — 균일 배율
3. `offset ≥ 0` — 고정값
4. 기본값 — element_size per axis

### 생성 파일

- 메인 출력: `<output>.k` (원본 FE 유지 + `*INCLUDE`)
- IGA 파일: `<output>_iga_p{pid}.k` (파트별 별도)

> **MID 격리 규칙**: IGA 파트와 일반 FE 파트는 반드시 다른 MID를 사용해야 합니다.

---

## 21. warpage — 워피지 보정

### 용도
측정 데이터(.dat 파일)로부터 면외 변형(warpage)을 메시에 적용합니다.
곡률 기반 응력 계산 또는 직접 변위 모드를 지원합니다.

### 사용법

```bash
KooRemapper.exe warpage <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: warped
target_pid: 1
dat_file: warpage.dat      # 변형 데이터 파일
plane: xy                  # 투영 평면
deflection_axis: z         # 변형 축
unit: mm                   # 단위
mask_value: -9999          # 무효 데이터 마커
noise_threshold: 0.001     # 노이즈 임계값
morph_factor: 1.0          # 변형 배율
mode: curvature            # curvature | raw
finite_strain: false       # 유한 변형률 사용
outside_behavior: clamp    # 경계 외 처리
debug: false
debug_prefix: debug_
data_bbox:                 # 데이터 바운딩 박스 (선택)
  x_min: 0
  x_max: 100
  y_min: 0
  y_max: 100
material:
  E: 210000
  nu: 0.3
```

### 파라미터

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `dat_file` | 워피지 측정 데이터 파일 | — |
| `plane` | 투영 평면 (xy/yz/zx) | `xy` |
| `deflection_axis` | 변형 방향 축 | `z` |
| `mode` | curvature(곡률 응력) / raw(직접 변위) | `curvature` |
| `morph_factor` | 변형 배율 | `1.0` |
| `mask_value` | 무효 데이터 값 | — |
| `noise_threshold` | 노이즈 필터 임계값 | `0.001` |
| `finite_strain` | 유한 변형률 사용 여부 | `false` |
| `outside_behavior` | 경계 외 처리 (clamp/zero) | `clamp` |
| `data_bbox` | 데이터 영역 제한 | 자동 |

### 동작
1. .dat 파일에서 격자 데이터 로드
2. 바이리니어 보간으로 각 노드 위치의 변형량 계산
3. curvature 모드: 유한 차분으로 곡률 계산 → 굽힘 응력
4. raw 모드: 직접 노드 변위만 적용

---

## 22. offset — 셸 오프셋 솔리드 생성

### 용도
셸(shell) 파트의 표면을 추출하여 지정 두께/방향으로 **솔리드 요소를 압출** 생성합니다.
곡면 법선, 가변 두께, 영역 선택, CZM 접합을 지원합니다.

### 사용법

```bash
KooRemapper.exe offset <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: offset_result
source_pid: 1
offset_direction: +normal   # +normal|-normal|+x|-x|+y|-y|+z|-z
thickness: 2.0
thickness_formula: "1.0 + 0.01*x"   # 가변 두께 수식 (선택)
num_layers: 1
use_local_normals: true      # 곡면 법선 사용
element_type: hex            # hex | tet
connection_mode: shared      # shared | tied | czm
new_pid: 0                   # 0=자동
part_title: "Offset part"
material:
  E: 210000
  nu: 0.3

# CZM 연결 (connection_mode: czm)
czm_part_id: 100
czm_mid: 50
czm_material_card: |
  *MAT_COHESIVE_...

# 재료 카드 직접 지정 (선택)
material_card: |
  *MAT_ELASTIC
  ...

# 영역 선택 (선택)
bbox_xmin: 0
bbox_xmax: 100
bbox_ymin: 0
bbox_ymax: 100
bbox_zmin: 0
bbox_zmax: 100
node_id_min: 1
node_id_max: 999999
element_id_min: 1
element_id_max: 999999
```

### 주요 파라미터

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `source_pid` | 소스 파트 ID | — |
| `offset_direction` | 압출 방향 | — |
| `thickness` | 균일 두께 | — |
| `thickness_formula` | 가변 두께 수식 (x,y,z 변수) | — |
| `use_local_normals` | 곡면 노드별 법선 사용 | `false` |
| `connection_mode` | 연결 방식 (shared/tied/czm) | `shared` |

### 품질 검증
생성된 솔리드 요소의 품질을 자동 검증합니다:
- Aspect Ratio: warn > 10, error > 20
- Jacobian: warn < 0.1, error < -1e-10
- Warping: warn > 30°, error > 45°

---

## 23. matswap — 재료 번들 교체

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
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
     &MID1 ...
*SECTION_SOLID_TITLE
   &SECID1 ...
*PART
...  &PID1   &SECID1   &MID1   0   &HGID1 ...
*END
```

### 파라미터 이름 접두사 규칙

| 접두사 | ID 종류 | 동작 |
|--------|---------|------|
| `HGID*` | Hourglass ID | 항상 새 ID |
| `LCID*` | Curve ID | 항상 새 ID |
| `SECID*` | Section ID | 항상 새 ID |
| `MID*` | Material ID | 고아 ID 재사용 가능 |
| `PID*` | Part ID | 무시 |

---

## 24. matdb — 재료 DB 교체

### 용도
JSON 재료 데이터베이스(`material_db.json`)를 기반으로 모델의 `*MAT` 카드를 일괄 교체합니다.
파트 이름 자동 매칭 또는 직접 MID 지정을 지원합니다.

### 사용법

```bash
KooRemapper.exe matdb <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: result.k
database: materials/material_db.json
mat_type: MAT_024         # 구조 카드 유형 (기본)
thermal: false            # 열 재료 삽입 여부

materials:                # 개별 규칙 (선택)
  - match: "steel*"       # 파트 이름 패턴 매칭
    mat_type: MAT_ELASTIC
  - mid: 5                # 직접 MID 지정
    thermal: true
  - match: "*"            # catch-all 자동 매칭
```

### 매칭 규칙
- `match`: 파트 title과 DB의 name/tag 부분 문자열 매칭 (대소문자 무시)
- `mid`: 직접 재료 ID 지정
- `match: "*"`: 모든 미매칭 재료에 자동 매칭 시도

### 열 재료 삽입 (`thermal: true`)
- `*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` 자동 삽입
- TMID 링크 자동 연결

---

## 25. contact — 접촉 정의 관리

```
KooRemapper.exe contact <config.yaml>
```

LS-DYNA 모델의 `*CONTACT_*`, `*SET_SEGMENT`, `*SET_PART`, `*SET_NODE` 키워드를 일괄 관리한다.
하나의 YAML 설정으로 분석, 생성, 변환, 수정, 삭제, 자동 감지를 순차 실행할 수 있다.

### 기본 YAML 구조

```yaml
model:  model.k
output: model_contact.k

contacts:
  - action: analyze
    ...
  - action: create
    ...
```

---

### 25.1 analyze — 접촉 분석

모델의 기존 접촉 정의를 리포트한다. 수정 없이 읽기 전용.

```yaml
contacts:
  - action: analyze
```

`contact_index` 번호([0], [1], ...)를 convert/modify/remove에서 참조한다.

---

### 25.2 create — 접촉 생성

#### 모드 1: Part ID 직접 지정 (SSTYP=3)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1 }
    master: { pid: 2 }
    friction: 0.3
    soft: 2
    title: Case_to_Board
```

#### 모드 2: 복수 PID → SET_PART 자동 생성 (SSTYP=2)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pids: [1, 2, 3] }
    master: { pids: [4, 5] }
```

#### 모드 3: 표면 세그먼트 추출 → SET_SEGMENT (SSTYP=0)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1, as_segment: true }
    master: { pid: 2, as_segment: true }
```

#### 모드 4: 세그먼트 + facing 필터

```yaml
contacts:
  - action: create
    type: tied_surface_to_surface
    slave:  { pid: 1, as_segment: true, facing: true }
    master: { pid: 2, as_segment: true, facing: true }
    tolerance: 0.05
    normal_angle: 30
```

#### 모드 5: Single Surface 자기접촉

```yaml
contacts:
  - action: create
    type: automatic_single_surface
    slave:  { pids: [1, 2, 3, 4] }
    soft: 2
```

#### create에서 사용 가능한 type 값

| type (YAML) | LS-DYNA 키워드 |
|---|---|
| `automatic_surface_to_surface` | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` |
| `tied_surface_to_surface` | `*CONTACT_TIED_SURFACE_TO_SURFACE` |
| `automatic_single_surface` | `*CONTACT_AUTOMATIC_SINGLE_SURFACE` |
| `eroding_surface_to_surface` | `*CONTACT_ERODING_SURFACE_TO_SURFACE` |
| `forming_surface_to_surface` | `*CONTACT_FORMING_SURFACE_TO_SURFACE` |
| (기타 직접 입력) | `*CONTACT_<입력값>` (대문자 변환) |

---

### 25.3 convert — 접촉 변환

기존 접촉의 SSTYP/MSTYP 방식을 변경한다.

```yaml
contacts:
  - action: convert
    contact_index: 0
    slave_to: segment
    master_to: segment
    facing: true
    tolerance: 0.05
    normal_angle: 30
```

---

### 25.4 modify — 접촉 수정

```yaml
contacts:
  - action: modify
    contact_index: 0
    friction: 0.5
    soft: 2
    depth: 35
    penmax: 0.5
```

---

### 25.5 remove — 접촉 삭제

```yaml
contacts:
  - action: remove
    contact_index: 0
```

---

### 25.6 detect — 접촉 자동 감지

**Spatial Hash Grid** 알고리즘으로 파트 간 맞닿는 영역을 고속 검출한다.

#### 명시적 PID 지정

```yaml
contacts:
  - action: detect
    slave:  { pid: 1 }
    master: { pid: 2 }
    tolerance: 0.1
    auto_create: true
    contact_type: auto
    friction: 0.20
```

#### 전체 파트 자동 감지

```yaml
contacts:
  - action: detect
    scope: all
    exclude: [rigid, null, air]
    tolerance: 0.1
    auto_create: true
    contact_type: auto
```

#### 키워드 기반 파트 선택

```yaml
contacts:
  - action: detect
    include: [bolt, plate, housing]
    exclude: [rigid]
    tolerance: 0.05
    auto_create: true
    contact_type: tied
```

#### contact_type 프리셋

| YAML 값 | LS-DYNA 키워드 | 용도 |
|---|---|---|
| `auto` | `AUTOMATIC_SURFACE_TO_SURFACE` | 범용 |
| `tied` | `TIED_SURFACE_TO_SURFACE` | 접합 |
| `mortar` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` | 고정밀 |
| `single` | `AUTOMATIC_SINGLE_SURFACE` | 자기접촉 |
| `eroding` | `ERODING_SURFACE_TO_SURFACE` | 요소 파괴 |
| `forming` | `FORMING_SURFACE_TO_SURFACE` | 성형 해석 |

#### detect 옵션

| 키 | 기본값 | 설명 |
|---|---|---|
| `scope` | — | `all`: 모든 파트 쌍 탐색 |
| `include` | — | 대상 파트 이름 키워드 리스트 |
| `exclude` | — | 제외 파트 이름 키워드 리스트 |
| `tolerance` | `0.1` | 접촉 간격 허용치 |
| `normal_angle` | `45.0` | 법선 방향 허용 각도(°) |
| `auto_create` | `false` | 검출 쌍마다 자동 생성 |
| `skip_existing` | — | `tied`/`all`: 기존 접촉 쌍 건너뜀 |
| `subtract_existing` | `false` | 기존 tied 세그먼트 차집합 제외 |

---

### 25.7 세부 옵션 (Optional Cards A~G)

create, modify, detect(auto_create) 모든 액션에서 동일하게 사용 가능.

#### Card A (소프트닝/깊이)

| 키 | 필드 | 설명 |
|---|---|---|
| `soft` | SOFT | 소프트 제약 (0/1/2) |
| `sofscl` | SOFSCL | SOFT 스케일 |
| `depth` | DEPTH | 검색 깊이 (0~45) |
| `sbopt` | SBOPT | 세그먼트 기반 옵션 |

#### Card B (두께)

| 키 | 필드 | 설명 |
|---|---|---|
| `penmax` | PENMAX | 최대 관통량 |
| `thkopt` | THKOPT | 두께 옵션 |
| `shlthk` | SHLTHK | 셸 두께 고려 |

#### Card C (간격/에지)

| 키 | 필드 | 설명 |
|---|---|---|
| `igap` | IGAP | 간격 처리 |
| `ignore` | IGNORE | 관통 무시 |

> **카드 의존성**: Card G를 지정하면 A~F가 자동 포함 (LS-DYNA 고정폭 카드 순서 요구).

---

## 26. load — 하중 적용

### 용도
LS-DYNA 모델에 하중 키워드를 일괄 삽입합니다.

### 사용법

```bash
KooRemapper.exe load <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: loaded.k
loads:
  - type: force
    nid: 100
    dof: 3             # 1=x, 2=y, 3=z
    value: -1000.0
    lcid: 0            # Load Curve ID (0=상수)
  - type: pressure
    pid: 1
    value: 10.0
  - type: gravity
    direction: z
    value: -9810.0
```

### 파라미터

| 파라미터 | 설명 |
|----------|------|
| `type` | 하중 유형 (force/pressure/gravity) |
| `nid` | 노드 ID (force) |
| `pid` | 파트 ID (pressure) |
| `dof` | 자유도 방향 1=x, 2=y, 3=z (force) |
| `value` | 하중 크기 |
| `lcid` | Load Curve ID (0=상수) |
| `direction` | 중력 방향 (gravity) |

---

## 27. boundary — 경계 조건 적용

### 용도
LS-DYNA 모델에 경계 조건(구속/변위) 키워드를 삽입합니다.

### 사용법

```bash
KooRemapper.exe boundary <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: constrained.k
boundaries:
  - type: spc
    nid: 100
    dofx: 1            # 0=자유, 1=구속
    dofy: 1
    dofz: 1
    dofrx: 0
    dofry: 0
    dofrz: 0
  - type: prescribed_motion
    nid: 200
    dof: 1
    value: 10.0
    lcid: 1
```

### 파라미터

| 파라미터 | 설명 |
|----------|------|
| `type` | 경계 유형 (spc/prescribed_motion) |
| `nid` | 노드 ID |
| `dofx~dofrz` | DOF 구속 (SPC: 0=자유, 1=구속) |
| `dof` | 자유도 방향 (prescribed_motion) |
| `value` | 변위값 |
| `lcid` | Load Curve ID |

---

## 28. rbe — RBE 구속 조건

### 용도
RBE2(강체 연결) 또는 RBE3(분산 하중) 구속 조건을 삽입합니다.

### 사용법

```bash
KooRemapper.exe rbe <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: rbe_model.k
rbes:
  - type: rbe2
    master_nid: 100
    slave_nids: [101, 102, 103, 104]
    dof: 123456
  - type: rbe3
    master_nid: 200
    slave_nids: [201, 202, 203]
    dof: 123
    weights: [1.0, 1.0, 1.0]
```

### 파라미터

| 파라미터 | 설명 |
|----------|------|
| `type` | rbe2 (강체) / rbe3 (분산) |
| `master_nid` | 마스터 노드 ID |
| `slave_nids` | 슬레이브 노드 ID 리스트 |
| `dof` | 구속 자유도 (예: 123456) |
| `weights` | 가중치 (RBE3 전용) |

---

## 29. implicit — Explicit→Implicit 변환

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
endtime: 1.0
strip: false          # true: 키워드 제거만 (삽입 없음)

# 세부 오버라이드 (생략 시 level 기본값)
# dctol/ectol/dt0/dtmax/nsolvr/kfail/rctol/lsolvr/stab/stab_scale/arc_length
# fix_shell_elform/keep_dr_curves
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

### 처리 파이프라인

#### 제거 (항상)
- `*CONTROL_DYNAMIC_RELAXATION`
- `*CONTROL_BULK_VISCOSITY`
- `*DATABASE_BINARY_D3DRLF`

#### 수정
- `*CONTROL_TIMESTEP` → TSSFAC=0.90, DT2MS=0.0
- `*CONTROL_TERMINATION` → endtim 갱신

#### 삽입
- `*CONTROL_IMPLICIT_GENERAL` / `_DYNAMICS` / `_SOLUTION` / `_AUTO`
- Level 5+: `*CONTROL_IMPLICIT_STABILIZATION`
- Level 6+: `*CONTROL_IMPLICIT_SOLVER` (MUMPS)
- Level 8: Arc-length (Crisfield)

### mode: static vs dynamic

| 파라미터 | static (준정적) | dynamic (구조동역학) |
|----------|----------------|-------------------|
| IMASS | 0 | 1 |
| GAMMA | 0.5 | 0.6 |
| BETA | 0.25 | 0.30 |

### strip 모드 (`strip: true`)

`*CONTROL_IMPLICIT_*` 관련 키워드 10종을 모두 제거하고, 새 키워드는 삽입하지 않습니다.
level/mode 파라미터 검증을 건너뜁니다.

---

## 30. modal — 고유진동수(모달) 해석 변환

### 용도
LS-DYNA 모델을 모달 해석(고유진동수/고유모드) 설정으로 변환합니다.

### 사용법

```bash
KooRemapper.exe modal <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: modal.k
nmode: 10              # 추출 모드 수 (기본: 10)
fmin: 0.0              # 최소 주파수 (Hz)
fmax: 0.0              # 최대 주파수 (0=무제한)
center: 0.0            # 중심 주파수 (Lanczos shift)
eigmth: 2              # 고유치 방법
solver: 7              # 선형 솔버
fix_shell_elform: false
keep_dr_curves: false
strip: false           # true: 키워드 제거만
```

### 고유치 방법 (eigmth)

| 값 | 방법 | 설명 |
|----|------|------|
| 2 | Lanczos | 기본, 범용 |
| 101 | MCMS | Multi-Component Mode Synthesis |
| 102 | LOBPCG | Locally Optimal Block PCG |
| 103 | FastLanczos | 고속 Lanczos |

### 삽입 키워드

- `*CONTROL_IMPLICIT_EIGENVALUE` — nmode, fmin, fmax, center, eigmth
- `*CONTROL_IMPLICIT_GENERAL` — IMFLAG=1
- `*CONTROL_IMPLICIT_SOLUTION` — solver 설정

### strip 모드 (`strip: true`)

`*CONTROL_IMPLICIT_EIGENVALUE`, `_GENERAL`, `_SOLUTION`, `_SOLVER`를 제거합니다.

---

## 31. relax — Dynamic Relaxation 설정

### 용도
초기 응력이 적용된 모델을 Dynamic Relaxation으로 평형 상태까지 릴렉세이션합니다.

### 사용법

```bash
KooRemapper.exe relax <config.yaml>
```

### YAML 형식

```yaml
model: wrapped_model.k
output: relaxed_model.k
level: 2               # 1(빠름) ~ 5(보수적), 기본=2
mode: explicit          # explicit(IDRFLG=1) | implicit(IDRFLG=5)
drterm: 100.0           # DR 종료 시간 (0=무한대)
endtime: 1.0            # DR 후 실제 해석 종료 시간
d3drlf: true            # DATABASE_BINARY_D3DRLF 출력
fix_shell_elform: false
strip: false            # true: 키워드 제거만

# 세부 오버라이드
# nrcyck/drtol/drfctr/tssfdr/irelal/edttl
```

### 레벨 프리셋 (5단계)

| Lv | 이름 | NRCYCK | DRTOL | DRFCTR | TSSFDR | IRELAL | EDTTL |
|----|------|--------|-------|--------|--------|--------|-------|
| 1 | 빠름 | 500 | 0.010 | 0.990 | 0.95 | 0 | 0.04 |
| 2 | 표준 | 250 | 0.001 | 0.995 | 0.90 | 0 | 0.04 |
| 3 | 안정 | 100 | 0.001 | 0.998 | 0.80 | 0 | 0.04 |
| 4 | 보수 | 50 | 1e-4 | 0.999 | 0.67 | 1 | 0.01 |
| 5 | 최대 | 25 | 1e-5 | 0.999 | 0.50 | 1 | 0.001 |

### 모드

| mode | IDRFLG | 설명 |
|------|--------|------|
| explicit | 1 | 명시적 DR — 속도 감쇠로 운동에너지 소산 |
| implicit | 5 | 암시적 초기화 — 암시적 솔버로 평형 도달 |

### strip 모드 (`strip: true`)

`*CONTROL_DYNAMIC_RELAXATION`, `*DATABASE_BINARY_D3DRLF`를 제거합니다.

---

## 32. explicit — 순수 Explicit 복원

### 용도
모델에서 DR + Implicit + Modal 관련 키워드를 **모두 제거**하여 순수 Explicit 설정으로 복원합니다.

### 사용법

```bash
KooRemapper.exe explicit <config.yaml>
```

### YAML 형식

```yaml
model: implicit_model.k
output: explicit_model.k
keep_dr_curves: false    # true: SIDR=1 DEFINE_CURVE 유지
```

### 제거 대상

| 키워드 | 원래 소속 |
|--------|----------|
| `*CONTROL_DYNAMIC_RELAXATION` | relax |
| `*DATABASE_BINARY_D3DRLF` | relax |
| `*CONTROL_IMPLICIT_GENERAL` | implicit |
| `*CONTROL_IMPLICIT_DYNAMICS` | implicit |
| `*CONTROL_IMPLICIT_SOLUTION` | implicit |
| `*CONTROL_IMPLICIT_AUTO` | implicit |
| `*CONTROL_IMPLICIT_STABILIZATION` | implicit |
| `*CONTROL_IMPLICIT_SOLVER` | implicit |
| `*CONTROL_IMPLICIT_EIGENVALUE` | modal |
| `*CONTROL_IMPLICIT_MODAL_DYNAMIC` | modal |
| `*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS` | modal |
| `*CONTROL_IMPLICIT_INERTIA_RELIEF` | modal |
| `*DEFINE_CURVE` (SIDR=1) | relax (keep_dr_curves=false 시) |

---

## 33. wrap — 와인딩 인장 프리스트레스

### 용도
와인딩 공정에서 발생하는 인장 프리스트레스를 시뮬레이션합니다.
원통 좌표계 기반으로 후프(hoop) 응력과 반경 방향 압축을 계산합니다.

### 사용법

```bash
KooRemapper.exe wrap <config.yaml>
```

### YAML 형식

```yaml
model: cylinder.k
output: wrapped
target_pid: 1
axis: z                 # 와인딩 축 (x/y/z)
axis_center: [0, 0]     # 축 중심 좌표 [c1, c2]
tension: 100.0          # 와인딩 인장력 (MPa)
material:
  E: 210000
  nu: 0.3
```

### 물리 모델

원통 좌표계 (r, θ, z)에서:
- **후프 응력** σ_θθ = tension (인장)
- **반경 압축** σ_rr = -tension × (r_outer/r - 1) / ln(r_outer/r_inner)

전역 좌표 변환:
$$\sigma_{xx} = \sigma_{rr}\cos^2\theta + \sigma_{\theta\theta}\sin^2\theta$$
$$\sigma_{yy} = \sigma_{rr}\sin^2\theta + \sigma_{\theta\theta}\cos^2\theta$$
$$\sigma_{xy} = (\sigma_{\theta\theta} - \sigma_{rr})\sin\theta\cos\theta$$

---

## 34. optimize — 재료별 해석 최적화

`optimize` 명령은 특정 재료(예: 고무)에 최적화된 LS-DYNA 컨트롤 카드를 자동으로 적용합니다.

### 사용법

```bash
KooRemapper optimize config.yaml
```

### YAML 형식

```yaml
model: my_model.k
output: my_model_optimized.k
optimize: rubber          # 최적화 모드 (현재: rubber만 지원)
pids: [2, 5, 8]          # 최적화 대상 파트 ID
tssfac: 0.67             # TSSFAC 설정값 (기본: 0.67)
analysis_type: ""        # "explicit" / "implicit" / "" (자동 감지)
```

#### matswap 통합

```yaml
model: base_model.k
output: swapped_model.k
swaps:
  - bundle: rubber.k
    pid: 3
optimize: rubber
```

### rubber 모드 적용

#### 공통 (explicit + implicit)

| 카드 | 필드 | 목표값 |
|---|---|---|
| `*CONTROL_ACCURACY` | INN | `4` |
| `*CONTROL_ENERGY` | HGEN/RWEN/SLNTEN/RYLEN | `2/2/2/2` |
| `*CONTACT_*` (대상 PID) | SOFT | `0` |
| `*CONTACT_*` (대상 PID) | SBOPT | `2` |

#### Explicit 전용

| 카드 | 필드 | 동작 |
|---|---|---|
| `*CONTROL_TIMESTEP` | TSSFAC | 0.67 (강제) |
| `*CONTROL_TIMESTEP` | DT2MS | 양수이면 경고 |
| `*CONTROL_BULK_VISCOSITY` | Q1, Q2 | 비표준이면 경고 |

### 멱등성
이미 올바른 값은 수정하지 않습니다. 같은 모델에 두 번 실행해도 결과 동일.

---

## 35. ale — ALE 변환

### 용도
지정 solid 파트를 ALE(Arbitrary Lagrangian-Eulerian)로 변환합니다.
14종 재료 프리셋과 커스텀 번들 파일을 지원합니다.

### 사용법

```bash
KooRemapper.exe ale <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: ale_model.k
parts:
  - pid: 5
    preset: air           # 프리셋 이름 또는 bundle 경로
    lagrangian_pids: [1, 2, 3]   # FSI 라그랑지안 파트
  - pid: 6
    preset: water
    lagrangian_pids: [1]
```

### 재료 프리셋 (14종)

| 분류 | 프리셋 | MAT | EOS |
|------|--------|-----|-----|
| 기체 | air, nitrogen, argon | MAT_NULL | EOS_LINEAR_POLYNOMIAL |
| 액체 | water, electrolyte, gasoline, oil, coolant, resin, tim, silicone | MAT_NULL | EOS_GRUNEISEN |
| 폭발물 | tnt, c4 | MAT_HE_BURN | EOS_JWL |
| 진공 | vacuum | MAT_VACUUM | — |

### 자동 삽입 카드

- `*SECTION_SOLID` ELFORM 변경
- `*HOURGLASS` (IHQ=3)
- `*CONTROL_ALE`
- `*ALE_MULTI-MATERIAL_GROUP`
- `*ALE_REFERENCE_SYSTEM_GROUP` (PRTYPE=4)
- `*CONSTRAINED_LAGRANGE_IN_SOLID` (FSI)
- `*INITIAL_DETONATION` (폭발물 전용)

### 단위 체계
t/mm/s → MPa

---

## 36. stabilize — Explicit 솔버 안정화

### 용도
Explicit 솔버의 안정성을 단계적으로 강화하는 **12단계 누적 시스템**입니다.

### 사용법

```bash
KooRemapper.exe stabilize <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: stabilized.k
stabilize: explicit
level: 6               # 1 ~ 12
```

### 레벨 시스템

| Lv | 주요 변경 |
|----|----------|
| 1 | 에너지 추적 활성화 |
| 2 | 정확도 향상 (INN=4) |
| 3 | TSSFAC 0.80 |
| 4 | IHQ=4 (hourglass) |
| 5 | 셸 요소 설정 (자동 감지) |
| 6 | 접촉 soft stage 1 |
| 7 | TSSFAC 0.67 + bulk viscosity 강제 |
| 8 | 핀볼 SOFT=2 + Card C IGNORE |
| 9 | IHQ=6 Belytschko-Bindeman |
| 10 | TSSFAC 0.60 |
| 11 | ERODE (대화형) |
| 12 | 최대 보수적 설정 |

각 레벨은 **이전 레벨을 포함**합니다 (누적 적용).

---

## 37. database — DATABASE 출력 제어

### 용도

LS-DYNA K-파일에 `*DATABASE_*` 출력 제어 키워드를 자동 삽입합니다.
프리셋 또는 개별 키워드 토글 방식을 지원하며, 기존 키워드는 자동으로 건너뜁니다.

### 사용법

```bash
KooRemapper.exe database <config.yaml>
```

### YAML 형식 (프리셋)

```yaml
model:  model.k
output: model_db.k
preset: drop           # all/drop/crash/static/thermal/forming/modal/minimal
dt:     0.001          # ASCII 출력 간격 (기본 0.001)
dt_plot: 0.01          # D3PLOT 간격 (기본 dt×10)
```

### YAML 형식 (개별 지정)

```yaml
model:  model.k
output: model_db.k
ascii:
  glstat: true
  matsum: true
  nodout: true
  rcforc: true
binary:
  d3plot: true
  d3thdt: true
extent:
  neiph: 6             # 추가 적분점 히스토리 변수
  strflg: 1            # 변형률 텐서 출력
  sigflg: 1            # 응력 텐서 출력
  epsflg: 1            # 유효 소성 변형률 출력
```

### 프리셋 (8종)

| 프리셋 | ASCII 키워드 | Binary | EXTENT |
|--------|-------------|--------|--------|
| `all` | 20종 전체 (glstat~massout) | d3plot, d3thdt, d3dump, runrsf | O |
| `drop` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, rwforc, nodfor, secforc, bndout, ncforc | d3plot, d3thdt, d3dump | O |
| `crash` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, rwforc, nodfor, secforc, swforc, ncforc, abstat | d3plot, d3thdt, d3dump | O |
| `static` | glstat, matsum, nodout, elout, spcforc, nodfor, bndout, secforc | d3plot, d3thdt | O |
| `thermal` | glstat, matsum, nodout, elout, spcforc, tprint, bndout | d3plot, d3thdt | O |
| `forming` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, nodfor, secforc, ncforc, swforc | d3plot, d3thdt, d3dump | O |
| `modal` | glstat, matsum, nodout, elout, spcforc | d3plot | X |
| `minimal` | glstat, matsum | d3plot | X |

### 지원 키워드

**ASCII (20종):** glstat, matsum, nodout, elout, rcforc, sleout, spcforc, nodfor, rwforc, secforc, jntforc, bndout, abstat, swforc, ssstat, deforc, disbout, ncforc, tprint, massout

**Binary (6종):** d3plot, d3thdt, d3dump, runrsf, intfor, d3drlf

### 동작
- 기존 `*DATABASE_*` 키워드를 스캔하여 중복 건너뛰기 (`[SKIP]` 표시)
- `*END` 직전에 출력 블록 삽입
- 프리셋 미지정 + 개별 미지정 시 `all` 프리셋 자동 적용

---

## 38. 키워드 제거(strip) 기능

### 개요

`implicit`, `modal`, `relax` 명령에 `strip: true` 옵션을 추가하면,
해당 명령이 관리하는 키워드를 **제거만** 하고 새 키워드는 삽입하지 않습니다.

### 명령별 제거 범위

| 명령 | strip: true 시 제거 대상 |
|------|------------------------|
| `implicit` | `*CONTROL_IMPLICIT_*` 10종 |
| `modal` | `*CONTROL_IMPLICIT_EIGENVALUE`, `_GENERAL`, `_SOLUTION`, `_SOLVER` |
| `relax` | `*CONTROL_DYNAMIC_RELAXATION`, `*DATABASE_BINARY_D3DRLF` |
| `explicit` | 위 3개 명령의 제거 대상 전부 + SIDR=1 DEFINE_CURVE |

### strip vs explicit

| 구분 | strip: true | explicit 명령 |
|------|-------------|---------------|
| 범위 | 해당 명령 소속 키워드만 | 모든 비-Explicit 키워드 |
| 사용법 | 각 명령의 YAML에 `strip: true` | 별도 명령 |
| 용도 | 부분 정리 | 완전 초기화 |

---

## 39. assemble — 통합 어셈블리

### 개요

여러 오퍼레이션을 **순차적으로 적용**하는 통합 명령.
기본 모델을 로드하고 각 오퍼레이션을 순서대로 실행하며,
누적된 초기 응력을 단일 dynain 파일로 출력합니다.

```bash
KooRemapper.exe assemble <config.yaml>
```

### 공통 YAML 구조

```yaml
base_model: model.k
output: result
material:
  E: 210000
  nu: 0.3
dynamic_relaxation: true
dynain_embed: false

operations:
  - type: <op_type>
    ...
```

### 공통 특성
- **원본 키워드 보존**: `*CONTACT`, `*BOUNDARY`, `*LOAD` 등 미파싱 키워드 그대로 유지
- **응력 누적**: 동일 요소에 여러 오퍼레이션 적용 시 응력 합산(`std::map` 기반)
- **ID 자동 관리**: 파트/섹션/노드/요소 ID 자동 발급 (충돌 방지)

> **참고**: 아래 각 오퍼레이션은 동일 이름의 독립 명령어(12~22장)와 동일한 알고리즘을 사용합니다.
> assemble 내에서는 `- type: <이름>` 으로 지정하며, 여러 오퍼레이션을 순차 결합할 수 있습니다.

---

### 39.1 replace — 상세 메시 교체

```yaml
- type: replace
  target_pid: 3
  detail_flat: detail.k
  shell_bent: bent.k
  prestress: true
```

모델 내 특정 파트를 상세 메시로 교체. `prestress: true` 시 굽힘 초기 응력 자동 계산.

---

### 39.2 squeeze (assemble 내)

```yaml
- type: squeeze
  target_pid: 5
  eps_x: -0.015
  eps_y: -0.015
  eps_z:  0.0
```

독립형 `squeeze` 명령과 동일.

---

### 39.3 restack — 레이어 재적층

```yaml
- type: restack
  target_pid: 2
  direction: z
  element_type: solid
  layers:
    - thickness: 0.3
      material_card: |
        *MAT_ELASTIC
        ...
    - thickness: 0.5
      material_card: |
        *MAT_ELASTIC
        ...
```

→ 독립 명령 [12. restack](#12-restack--레이어-재적층) 참조

---

### 39.4 bend — 굽힘 변형 + 초기 응력

```yaml
- type: bend
  target_pid: 1
  plane: xy
  mode: deform
  source: formula
  expression: "0.5 * sin(pi * x1 / L1)"
```

→ 독립 명령 [13. bend](#13-bend--굽힘-변형--초기-응력) 참조

---

### 39.5 indent — 압입 / 엠보싱

```yaml
- type: indent
  target_pid: 2
  plane: xy
  direction: -z
  depth: 2.0
  r1: 1.5
  r2: 1.0
  stress: true
  shape:
    type: polygon
    points:
      - [0, 0]
      - [10, 0]
      - [10, 8]
      - [0, 8]
```

→ 독립 명령 [14. indent](#14-indent--압입엠보싱) 참조

---

### 39.6 formstrain — 성형 소성 변형률

```yaml
- type: formstrain
  target_pid: 0
  shell_thickness: 0.0
  min_curvature: 0.001
```

→ 독립 명령 [15. formstrain](#15-formstrain--성형-소성-변형률) 참조

---

### 39.7 tet10 / hex20 / quad8 / tria6 — 2차 요소 변환

```yaml
- type: tet10       # tet10 | hex20 | quad8 | tria6
  target_pid: 0
  elform: 17
```

→ 독립 명령 [16. convert](#16-convert--2차-요소-변환) 참조

---

### 39.8 refine — 메시 세분화

```yaml
- type: refine
  target_pid: 0
  ratio: 2
```

→ 독립 명령 [17. refine](#17-refine--메시-세분화) 참조

---

### 39.9 elform — 요소 공식 변경

```yaml
- type: elform
  target_pid: 0
  target_elform: "2"
```

→ 독립 명령 [18. elform](#18-elform--요소-공식-변경) 참조

---

### 39.10 disconnect — 노드 분리

```yaml
- type: disconnect
  target_pid: 3
  mode: full
```

→ 독립 명령 [19. disconnect](#19-disconnect--노드-분리) 참조

---

### 39.11 iga — 등기하해석 NURBS 박스 생성

```yaml
- type: iga
  targets:
    - target_pid: 1
      element_size: 4.0
      bbox_scale: 1.5
```

→ 독립 명령 [20. iga](#20-iga--등기하해석-nurbs-박스-생성) 참조

---

### 39.12 warpage — 워피지 보정

```yaml
- type: warpage
  target_pid: 1
  dat_file: warpage.dat
  plane: xy
  deflection_axis: z
  mode: curvature
  morph_factor: 1.0
```

→ 독립 명령 [21. warpage](#21-warpage--워피지-보정) 참조

---

### 39.13 offset — 셸 오프셋 솔리드 생성

```yaml
- type: offset
  source_pid: 1
  offset_direction: +normal
  thickness: 2.0
  use_local_normals: true
  element_type: hex
```

→ 독립 명령 [22. offset](#22-offset--셸-오프셋-솔리드-생성) 참조

---

### 39.14 matswap — 재료 번들 교체

```yaml
- type: matswap
  bundle: rubber.k
  pid: 3
```

→ 독립 명령 [23. matswap](#23-matswap--재료-번들-교체) 참조

---

### 39.15 matdb — 재료 DB 교체

```yaml
- type: matdb
  database: materials/material_db.json
  mat_type: MAT_024
  thermal: false
```

→ 독립 명령 [24. matdb](#24-matdb--재료-db-교체) 참조

---

### 39.16 wrap — 와인딩 인장 프리스트레스

```yaml
- type: wrap
  target_pid: 1
  axis: z
  axis_center: [0, 0]
  tension: 100.0
```

→ 독립 명령 [33. wrap](#33-wrap--와인딩-인장-프리스트레스) 참조

### 39.17 generate — 메시 인라인 생성

`base_model` 없이 assemble 시작 시 첫 번째 오퍼레이션으로 사용:

```yaml
# base_model 키 없음
output: my_model

operations:
  - type: generate
    shape: box
    lx: 100.0   # X 길이 [mm]
    ly:  20.0   # Y 길이 [mm]
    lz:  10.0   # Z 길이 [mm]
    nx: 10      # X 방향 요소 수
    ny:  4
    nz:  2
    rho: 7.85e-9
    E: 210000.0
    nu: 0.3
    mid: 1
    secid: 1
    pid: 1
    part_title: Steel Box
```

독립 명령으로도 사용 가능: `KooRemapper generate box config.yaml`

---

### 39.18 update — 노드 좌표 업데이트

dynain 또는 K 파일의 `*NODE` 블록에서 일치하는 NID만 좌표 갱신 (미정의 노드 유지):

```yaml
- type: update
  dynain: results/dynain
```

→ 독립 명령으로도 사용: `KooRemapper update config.yaml`

---

### 39.19 control — 해석 제어 카드 삽입

`*CONTROL_*` 카드를 삽입하거나 기존 카드 필드를 수정:

```yaml
- type: control
  endtime: 0.001    # *CONTROL_TERMINATION endtim (초)
  tssfac: 0.9       # *CONTROL_TIMESTEP tssfac
  dt2ms: -1.0e-7    # *CONTROL_TIMESTEP dt2ms (mass scaling, 음수)
  energy: true      # *CONTROL_ENERGY: hgen=2, rwen=2, slnten=1, rylen=1
  ihq: 4            # *CONTROL_HOURGLASS: stiffness-based
  qh: 0.05          # hourglass coefficient
  q1: 1.5           # *CONTROL_BULK_VISCOSITY quadratic
  q2: 0.06          # linear bulk viscosity
```

기존 카드가 있으면 해당 필드만 수정. 없으면 신규 삽입.

---

### 39.20 database — 출력 제어 카드 삽입

`*DATABASE_*` 출력 키워드 일괄 삽입 (assemble 내):

```yaml
- type: database
  preset: crash     # crash / drop / nve / all
  dt: 0.0001        # ASCII 출력 간격 (초)
  dt_plot: 0.001    # d3plot 출력 간격
```

→ 독립 명령 [37. database](#37-database--database-출력-제어) 참조

---

## 40. 수학 이론

### 40.1 등매개변수 매핑 (map)

HEX8 요소의 자연 좌표계 (ξ, η, ζ) ∈ [-1, 1]³:

$$\mathbf{x}(\xi,\eta,\zeta) = \sum_{i=1}^{8} N_i(\xi,\eta,\zeta)\,\mathbf{x}_i$$

역매핑 (Newton-Raphson):

$$\begin{pmatrix} \Delta\xi \\ \Delta\eta \\ \Delta\zeta \end{pmatrix} = \mathbf{J}^{-1} (\mathbf{x}_{target} - \mathbf{x}(\xi,\eta,\zeta))$$

야코비안 행렬:

$$J_{ij} = \frac{\partial x_i}{\partial \xi_j} = \sum_{k=1}^{8} \frac{\partial N_k}{\partial \xi_j} x_{ki}$$

### 40.2 선형 탄성 재료 모델

라메 상수:

$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}, \quad \mu = G = \frac{E}{2(1+\nu)}$$

구성 방정식 (Voigt 표기):

$$\begin{pmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \sigma_{zz} \\ \sigma_{xy} \\ \sigma_{yz} \\ \sigma_{xz} \end{pmatrix} = \begin{pmatrix} \lambda+2\mu & \lambda & \lambda & 0 & 0 & 0 \\ \lambda & \lambda+2\mu & \lambda & 0 & 0 & 0 \\ \lambda & \lambda & \lambda+2\mu & 0 & 0 & 0 \\ 0 & 0 & 0 & \mu & 0 & 0 \\ 0 & 0 & 0 & 0 & \mu & 0 \\ 0 & 0 & 0 & 0 & 0 & \mu \end{pmatrix} \begin{pmatrix} \varepsilon_{xx} \\ \varepsilon_{yy} \\ \varepsilon_{zz} \\ 2\varepsilon_{xy} \\ 2\varepsilon_{yz} \\ 2\varepsilon_{xz} \end{pmatrix}$$

### 40.3 Kirchhoff 판 이론 (bend/indent)

중립면에서 거리 z인 지점의 변형률:

$$\varepsilon_{11}(z) = -z \kappa_{11}, \quad \varepsilon_{22}(z) = -z \kappa_{22}, \quad 2\varepsilon_{12}(z) = -2z \kappa_{12}$$

모멘트-곡률 관계 (굽힘 강성 D):

$$D = \frac{E t^3}{12(1-\nu^2)}$$

$$M_{11} = D(\kappa_{11} + \nu \kappa_{22}), \quad M_{22} = D(\kappa_{22} + \nu \kappa_{11}), \quad M_{12} = D(1-\nu)\kappa_{12}$$

### 40.4 형성 변형률 이론 (formstrain)

이면각 θ, 인접 셸 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

면외 굽힘 변형률 (두께 방향 선형 분포):

$$\varepsilon_{top} = +\frac{t}{2}\kappa, \quad \varepsilon_{bot} = -\frac{t}{2}\kappa$$

등가 소성 변형률 (Von Mises 기준, 단축 가정):

$$\overline{\varepsilon}^p = \frac{2}{\sqrt{3}} |\varepsilon_{max}|$$

---

## 41. 출력 파일 형식

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

*KooRemapper v1.3.0 | 이 문서는 모든 구현 기능을 포함합니다.*
