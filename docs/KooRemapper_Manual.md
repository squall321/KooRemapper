# KooRemapper 기능 설명서

> **버전 1.8.0** | LS-DYNA 메시 전처리 도구
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
40. [meshfix — TET4 재메시 (Gmsh 기반)](#40-meshfix--tet4-재메시-gmsh-기반)
41. [수학 이론](#41-수학-이론)
42. [출력 파일 형식](#42-출력-파일-형식)
43. [추가 op 레퍼런스 (v1.8.0 대조 추가)](#43-추가-op-레퍼런스-v180-대조-추가)

---

## 1. 개요

KooRemapper는 LS-DYNA FEA 해석을 위한 **메시 전처리 도구**입니다.
주요 목적은 개략 메시(coarse mesh)로 구성된 전체 모델에 **상세 메시(detail mesh)**를 매핑하고,
조립 공정에 수반되는 **초기 응력 상태(prestress)**를 재현하는 것입니다.

> **v1.8.0 바이너리 대조 반영(2026-09-16)** — 이 문서는 실제 v1.8.0 바이너리의 `help` 덤프와 shipped 예제 YAML(`examples/`)에 대조하여 호출형태·config 키·기본값·스키마를 정정했습니다. 이론·동작원리 서술은 보존했습니다.

### 핵심 기능 범위


**표 1-1. KooRemapper 핵심 기능 범주 — 각 범주별 주요 기능과 해당 명령어를 요약한다.**

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
| **TET4 재메시** | Gmsh 기반 완전 재메시, 스케일드 자코비안 품질 개선(meshfix) |

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
KooRemapper <command> [options] ...

Commands:
  # 메시 처리
  map            HEX8 구조화 메시를 굽힘 참조 형상에 매핑
  shellmap       QUAD4 셸 참조 기반 상세 메시 매핑
  unfold         굽힘 구조화 메시로부터 평면 메시 전개
  generate       테스트용 예제 메시 생성 (box 하위명령 포함)
  generate-var   YAML 설정 기반 변밀도 메시 생성
  battery        배터리 셀(stacked/wound) K파일 생성 + 스웰링 DR 데크

  # 분석 / 메타
  strain         두 메시 간 변형률 계산
  prestress      변형 형상 기반 초기 응력 계산 + dynain 출력
  info           메시 파일 정보 출력
  modelmeta      파트별 기하·재료·연결성 메타 JSON 추출
  version        버전 정보

  # 형상 변형 (단독 실행)
  squeeze        간섭 끼워맞춤 초기 변형 계산
  restack        레이어 재적층
  bend           굽힘 변형 + 초기 응력
  indent         압입 / 엠보싱 변형
  formstrain     성형 소성 변형률 계산
  warpage        워피지(면외 변형) 보정
  offset         셸 오프셋 솔리드 생성
  wrap           와인딩 인장 프리스트레스
  cclip          육면체 파트를 F-δ 캘리브레이션된 C형 스프링 클립으로 치환 (눌린 상태+초기응력)

  # 메시 변환 / 편집
  convert        2차 요소 변환 (TET10/HEX20/QUAD8/TRIA6)
  refine         메시 세분화 (1:2, 1:3)
  elform         요소 공식(ELFORM) 변경
  disconnect     파트 간 노드 분리 (full/czm/mefem)
  iga            등기하해석(IGA) NURBS 박스 생성
  cnrb2solid     CNRB 강체 볼트를 HEX8 솔리드 실린더로 변환
  update         dynain/K파일 *NODE 블록으로 노드 좌표 갱신

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
  hfdamp         고주파(스퓨리어스) 진동 댐핑 (*DAMPING_FREQUENCY_RANGE_DEFORM)

  # 통합 실행
  assemble       다중 오퍼레이션 통합 어셈블리

  # 표면·재메시 (숨은 op — --help 목록에는 없으나 정상 동작)
  extract-surface  솔리드에서 표면 셸 추출
  tetremesh        TET4 로컬 재메시 (패치 기반, localimprove/tetgen 백엔드)
  meshfix          TET4 파트 전체 재메시 (Gmsh 기반)
  merge            적층 파트를 균질화(Voigt-Reuss-Hill) 단일 레이어로 병합
  strip            지정 키워드(keywords 리스트)를 K파일에서 제거

  # 유틸리티
  help           도움말
```

> **명령 개수**: v1.8.0 바이너리는 총 47개 op(유틸리티 `help`/`version` 제외)을 제공합니다. 이 중 `extract-surface`·`tetremesh`·`meshfix`·`merge`·`strip` 5종은 `KooRemapper --help` 최상위 목록에는 표시되지 않는 **숨은 op**이지만 정상 동작합니다(op 이름으로 실행하면 고유 Usage/YAML 스키마 출력). 실제 v1.8.0 리눅스 바이너리 경로는 `/opt/kooremapper/bin/KooRemapper` 이며, 아래 사용법의 `KooRemapper.exe` 표기는 Windows 빌드 기준입니다.

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
  --strain engineering|green   변형률 계산 방식 (기본: green)
  --csv                CSV 형식 추가 출력
```

> **v1.8.0 정정**: `--strain` 기본값은 `green`(Green-Lagrange)입니다(help `Usage:` 기준). prestress 의 help 는 `engineering`/`green` 두 가지만 지원하며 `log` 는 없습니다(두 메시 변형률만 필요할 때는 `strain` 명령이 `log` 도 지원, §10). `--E`/`--nu` 를 생략하면 K-파일 재료값이 쓰입니다.

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
세 번째 인자 `<output>` 은 dynain 파일 경로입니다.
- `<output>`: `*INITIAL_STRESS_SOLID` 카드(dynain). `pre.k` 처럼 `.k` 로 끝나면 아래 메시 사본과 겹치지 않게 `pre.dynain` 으로 씁니다.
- `<output 에서 확장자를 뗀 이름>.k`: 변형 메시 사본 + 위 dynain `*INCLUDE`
- `<output 에서 확장자를 뗀 이름>.csv` (`--csv`): 요소별 변형률/응력 CSV. 재료(E·ν)를 찾지 못하면 dynain 대신 `<output>` 에 CSV 만 씁니다.

예: `KooRemapper prestress --E 210000 --nu 0.3 flat.k bent.k pre.dynain` → `pre.dynain` + `pre.k`

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
- `<prefix>.k`: 압축된 메시 + 열팽창 카드 (swelling 파트) + dynain `*INCLUDE`
- `<prefix>.dynain`: `*INITIAL_STRESS_SOLID` (eps 파트만)

접두어 끝의 `.k` 는 떼고 씁니다(`out.k` 를 줘도 `out.k`·`out.dynain`).

---

## 8. generate / generate-var — 메시 생성

### generate — 예제 메시 생성

호출형태는 두 가지입니다(help `Usage:`).

```bash
KooRemapper generate [options] <type> <output_prefix>
KooRemapper generate box <config.yaml>

Types: teardrop, arc, scurve, helix, torus, twist, bendtwist,
       wave, bulge, taper, waterdrop

Options:
  --dim-i <n>   I 방향 요소 수 (기본 10)
  --dim-j <n>   J 방향 요소 수 (기본 5)
  --dim-k <n>   K 방향 요소 수 (기본 5)
```

테스트 및 데모용 다양한 기하학적 형상 HEX8 메시 생성. `box` 하위명령은 YAML(`lx/ly/lz`, `nx/ny/nz`, `rho/E/nu`, `mid/secid/pid`, `part_title`)로 직육면체 메시를 만듭니다.

### generate-var — 변밀도 메시 생성

호출형태는 positional 입니다(`--ref`, `--no-scale` 는 옵션).

```bash
KooRemapper generate-var [options] <config.yaml> <output.k>

Options:
  --ref <file>   스케일링용 참조 평면 메시
  --no-scale     참조로 스케일하지 않고 YAML 길이를 그대로 사용
```

#### YAML 설정 (평면 타입, `type: flat`)

help 기준 스키마는 `variable_density` + `elements_j/k` 구조입니다(존별 `length`/`num_elements`).

```yaml
type: flat                     # 생략 시 기본 flat
reference:
  flat_mesh: "ref_flat.k"      # 자동 스케일용 참조 메시
elements_j: 50                 # J 방향 요소 수
elements_k: 10                 # K 방향 요소 수
variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 50
  # zone2_... 존을 이어서 정의
```

#### YAML 설정 (곡선 타입, `type: curved`)

중심선 좌표(`centerline_points`)를 보간해 단면을 스윕합니다.

```yaml
type: curved
reference:
  flat_mesh: "ref_flat.k"      # 스케일용(선택)
centerline_points:
  - [0, 0]
  - [50, 0]
  - [100, 50]
  - [150, 50]
interpolation: catmull_rom     # linear | catmull_rom | bspline
cross_section:                 # 참조가 없을 때만
  width: 10.0
  thickness: 2.0
elements_along_curve: 100
elements_j: 20
elements_k: 5
```

> **v1.8.0 정정**: 구버전 정본이 보이던 `zones:`(id/nx/ny/nz/x_min/x_max…) 형식은 v1.8.0 바이너리가 파싱하는 스키마와 다릅니다. help 기준은 위 `variable_density`/`centerline_points` 구조입니다(zones 형식 병행 지원 여부는 확인 필요).

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


**표 9-1. unfold 인자 — 입력 굽힘 메시와 출력 평면 메시.**

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


**표 10-1. strain 인자 — 기준·변형 메시, 출력 CSV, 변형률 유형 옵션.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `ref_mesh.k` | 기준 형상 메시 (입력) | — |
| `def_mesh.k` | 변형 형상 메시 (입력) | — |
| `output.csv` | 변형률 결과 CSV (출력) | — |
| `--type` | 변형률 계산 방식 | `engineering` |

### 변형률 유형


**표 10-2. strain 변형률 유형 — engineering·green·log 정의.**

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


**표 11-1. info 출력 항목 — 노드·요소·파트 수, 바운딩 박스, 검증 결과, 요소 품질.**

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


**표 12-1. restack YAML 파라미터 — 대상 파트, 적층 방향, 요소 유형, 레이어 목록.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `model` | 입력 K-파일 | — |
| `output` | 출력 접두어 | — |
| `target_pid` | 대상 파트 ID | — |
| `direction` | 적층 방향 (auto/x/y/z) | `auto` |
| `element_type` | 요소 유형 | `solid` |
| `layers` | 레이어 리스트 (thickness + material_card) | — |

> **재질 카드 MID 칸**: 각 층 `material_card` 의 첫 `*MAT` 카드 MID 칸(1~10열, `*MAT_…_TITLE` 이면 제목 다음 줄)에 쓴 값은 라벨입니다. `MID001`·`MAT01`·`@MID@`·`14` 무엇이든 층마다 새로 발급한 MID 로 바뀌고, 같은 MID 를 가리키는 `*MAT_ADD_…` 카드도 함께 바뀝니다.
> - 라벨과 카드 내용(MID 칸 제외)이 같은 층끼리만 MID 하나를 공유합니다. 라벨이 같아도 물성이 다르면 따로 발급하고 `material label 'X' reused with a different card -> separate MID N` 을 안내합니다(위 예시의 두 층은 라벨은 같고 물성이 달라 MID 가 둘).
> - 값은 LS-DYNA 고정 폭 10열 칸 안에 두세요(블록 들여쓰기를 뺀 뒤 기준). 쉼표 자유 형식도 됩니다.
> - YAML `|` 블록은 키보다 깊게 들여쓴 줄까지이며 끝 빈 줄은 버립니다. 제목에 `:` 나 `-` 가 있어도 됩니다.

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
base_model: flat.k
output: bent
material:                   # 선택 — 생략하면 대상 파트의 *MAT_ELASTIC
  E: 210000
  nu: 0.3
operations:
  - type: bend
    target_pid: 1           # 0 또는 생략 = 모든 파트
    plane: xy               # xy | yz | zx  (x1,x2 = X,Y | Y,Z | Z,X)
    mode: deform            # deform(노드 이동 + 역응력) | stress(노드 그대로, 정응력)
    source: formula         # formula | dat | dat_pair
    expression: "0.5 * sin(pi * x1 / L1) * sin(pi * x2 / L2)"   # 처짐 w(x1,x2)

    # source: dat      → dat_file: deflection.dat
    # source: dat_pair → dat_top: top.dat  +  dat_bottom: bottom.dat (상·하면 처짐 격자)
```

> **v1.8.0 정정**: (1) 굽힘 평면 값은 `xy | yz | zx` 입니다. `xz` 는 거부됩니다(이전 help 와 이 문서의 `xz` 표기가 틀렸음). (2) config 는 최상위 `base_model`/`output` + `operations[].type: bend` 구조입니다. (3) `mode` 는 `deform | stress`, `source` 는 `formula | dat | dat_pair` 이고 모두 필수 검사 대상입니다(이전 help 의 `mode: formula` 는 거부). 단독 `bend` 명령도 assemble 과 같은 검사를 거칩니다(예전엔 검사 없이 source 누락 시 비정상 종료).

### 수식 변수


**표 13-1. bend 수식 변수 — 면내 좌표 x1·x2, 바운딩 박스 길이 L1·L2, π.**

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

값은 모델 길이 단위의 처짐이며, 격자는 대상 파트의 평면 바운딩 박스에 펼칩니다. warpage 의 dat 는 행 0 이 2축 **최소**라 방향이 반대입니다(§21).

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
base_model: flat.k
output: indented
material:
  E: 210000
  nu: 0.3
operations:
  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 2.0              # 양수=압입, 음수=엠보싱 (0 불가)
    r1: 1.5                 # 바닥 쪽 전이 호 반경 (> 0)
    r2: 1.0                 # 표면 쪽 전이 호 반경 (> 0)
    bottom_ratio: 0.5       # 반대 면 변위 비율 (0 = 반대 면 고정, 기본 0)
    stress: true            # 굽힘 응력 계산 여부
    shell_thickness: 1.0    # 셸 응력 두께 (0 = *SECTION_SHELL)
    shape:
      type: polygon         # polygon | spline (3점 이상)
      points:               # 평평한 바닥 윤곽 — 평면 좌표계의 모델 좌표
        - [0.0, 0.0]
        - [10.0, 0.0]
        - [10.0, 8.0]
        - [0.0, 8.0]
```

> **v1.8.0 정정**: config 는 최상위 `base_model`/`output` + `operations[].type: indent` 구조입니다. `shape.type` 은 `polygon | spline` 이고 `points` 는 3점 이상이어야 합니다(`circle` 은 없음 — 이전 help 표기가 틀렸음). `depth ≠ 0`, `r1·r2 > 0`, `direction` 은 `+x|-x|+y|-y|+z|-z` 를 검사하며 단독 `indent` 도 같습니다(예전엔 points·r1/r2 누락 시 비정상 종료).

### 파라미터


**표 14-1. indent 파라미터 — 깊이, 전이 호 반경 r1·r2, 반대 면 변위 비율, 응력·셸 두께.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `depth` | 압입 깊이 (양수=압입, 음수=엠보싱) | — |
| `r1` | 바닥 쪽 전이 호 반경 (윤곽 바깥 0~r1) | — |
| `r2` | 표면 쪽 전이 호 반경 (윤곽 바깥 r1~r1+r2) | — |
| `bottom_ratio` | 반대 면 변위 비율 (눌리는 면 1 → 반대 면 bottom_ratio 로 선형) | `0.0` |
| `stress` | 굽힘 응력 계산 여부 | `false` |
| `shell_thickness` | 셸 응력 두께 | `0` (= `*SECTION_SHELL`) |

### 압입 프로파일

윤곽(shape)으로부터의 부호 있는 거리 d(안쪽 < 0)에서 표면 변위 h(d):

$$k = \frac{\text{depth}}{r_1 + r_2}$$

- **윤곽 안** (d < 0): $h = -\text{depth}$ (평평한 바닥)
- **r₁ 구역** (0 ≤ d < r₁, 바닥 쪽 호): $h(d) = -\text{depth} + k\, r_1 \left(1 - \sqrt{1 - (d/r_1)^2}\right)$
- **r₂ 구역** (r₁ ≤ d < r₁+r₂, 표면 쪽 호): $h(d) = -k\, r_2 \left(1 - \sqrt{1 - \left((r_1 + r_2 - d)/r_2\right)^2}\right)$
- **바깥** (d ≥ r₁+r₂): $h = 0$

두께 방향으로는 눌리는 면에서 h, 반대 면에서 `bottom_ratio`·h 로 선형 보간합니다.

> **주의**: 응력은 노드 변위 **전에** 계산. h''(d) 특이점은 변형률 0.05 기준 `0.05 / (thickness/2)` 로 상한 제한.

---

## 15. formstrain — 성형 소성 변형률

### 용도
셸 메시의 **이면각(dihedral angle)**으로부터 굽힘 곡률을 계산하여
등가 소성 변형률(EPS)을 `*INITIAL_STRAIN_SHELL`(초기 변형률)로 출력합니다.
재료 항복응력 sigy 는 `*MAT_024` 에서 읽어 EPS 스케일에 씁니다.

### 사용법

```bash
KooRemapper.exe formstrain <config.yaml>
```

### YAML 형식

```yaml
base_model: bent_shell.k
output: formstrain_result
dynain_embed: true           # 출력에 초기 변형률 셸 카드 임베드
operations:
  - type: formstrain
    target_pid: 0            # 생략/0 = 전체 셸 파트 자동 감지
    shell_thickness: 0.0     # 0 = *SECTION_SHELL에서 자동
    min_curvature: 0.001     # 잡음 필터 임계값
```

> **v1.8.0 정정**: 출력 카드는 `*INITIAL_STRAIN_SHELL`(초기 변형률)입니다(help 기준. 구버전의 `*INITIAL_STRESS_SHELL` 표기 정정). config 는 최상위 `base_model`/`output`/`dynain_embed` + `operations[].type: formstrain` 구조입니다.

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


**표 16-1. convert 변환 유형 — 원본·변환 요소와 기본 ELFORM.**

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


**표 17-1. refine 세분화 결과 — 요소 유형별 ratio=2·3 서브 요소.**

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


**표 18-1. elform 고체 요소 별칭 — 별칭과 LS-DYNA ELFORM 번호.**

| 별칭 | ELFORM | 설명 |
|------|--------|------|
| `constant_stress` | 1 | 상수 응력 (UR) |
| `fully_integrated` | 2 | 완전 적분 |
| `tet4` | 13 | 4절점 사면체 |
| `tet10` | 17 | 10절점 사면체 |
| `hex20` | 23 | 20절점 헥사 |

### 셸 요소 별칭


**표 18-2. elform 셸 요소 별칭 — 별칭과 LS-DYNA ELFORM 번호.**

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


**표 19-1. disconnect 모드 — full·czm·mefem 동작과 LS-DYNA 출력.**

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
  # 대상 지정: target_pid 하나 | target_pids: [2, 3] (같은 설정, PID 마다 따로 감쌈)
  #           | target_name: "Lower*" (파트 제목 와일드카드 * ?, 0개 매칭이면 오류) + exclude_name
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
base_model: flat.k
output: warped
material:
  E: 210000
  nu: 0.3
operations:
  - type: warpage
    target_pid: 1
    dat_file: warpage.dat      # 처짐값 격자 (YAML 폴더 기준 상대 경로)
    plane: xy                  # xy | yz | zx
    deflection_axis: +z        # +z | -z | +x | -x | +y | -y
    unit: um                   # um(기본) | mm | m — 격자 값 단위
    mode: prestress            # prestress(기본, 초기응력) | deform(노드 이동)
    morph_factor: 1.0          # 처짐 배율 (> 0)
    finite_strain: true        # true: von Kármán 대변형(기본) | false: Kirchhoff
    outside_behavior: zero     # zero(기본) | clamp | extrapolate — 격자 범위 밖 노드
    mask_value: 9999           # 결측으로 보고 주변에서 보간할 값
    noise_threshold: 1.0e-10   # 노이즈 임계값
    # data_bbox:               # 격자가 덮는 평면 좌표 범위 (생략 시 파트 bbox)
    #   x_min: 0.0
    #   x_max: 100.0
    #   y_min: 0.0
    #   y_max: 100.0
```

> **v1.8.0 정정**: config 는 최상위 `base_model`/`output` + `operations[].type: warpage` 구조입니다. 이전 help 와 이 문서가 적었던 `source`·`dat_top`·`dat_bottom`·op 바로 아래 `x_min~y_max` 는 warpage 파서가 읽지 않는 키였습니다(오류 없이 무시). 격자 범위는 `data_bbox:` 아래에 두고, `mode` 는 `prestress | deform` 입니다(`curvature | raw` 아님). YAML 이 현재 폴더에 있을 때 `dat_file` 을 루트(`/파일`)에서 찾던 문제는 고쳐졌습니다.

### 파라미터


**표 21-1. warpage 파라미터 — 격자 파일·평면·단위·모드·범위 처리와 기본값.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `dat_file` | 처짐값 격자 파일 (필수) | — |
| `plane` | 투영 평면 (xy/yz/zx) | `xy` |
| `deflection_axis` | 처짐 방향 축 (±x/±y/±z) | `z` |
| `unit` | 격자 값 단위 (um/mm/m) | `um` |
| `mode` | prestress(초기응력만) / deform(노드 이동) | `prestress` |
| `morph_factor` | 처짐 배율 (> 0, 10 초과 시 경고) | `1.0` |
| `mask_value` | 결측 값 (주변 보간) | `9999` |
| `noise_threshold` | 노이즈 임계값 | `1e-10` |
| `finite_strain` | von Kármán 대변형(true) / Kirchhoff 소변형(false) | `true` |
| `outside_behavior` | 격자 범위 밖 노드 처리 (zero/clamp/extrapolate) | `zero` |
| `data_bbox` | 격자가 덮는 평면 범위 (`x_min`·`x_max`·`y_min`·`y_max`) | 파트 bbox |
| `debug` / `debug_prefix` | 격자·곡률 VTK 등 디버그 출력 | `false` / `debug/warp` |

### dat 파일 형식

공백(탭) 구분 처짐값 행렬입니다. `data_bbox`(생략 시 파트 bbox)에 펼치며 **열 0 = 평면 1축 최소, 행 0 = 2축 최소**입니다(bend 의 dat 는 행 0 = x2 최대로 반대). 값 단위는 `unit` 입니다.

```
0  0   0   0  0
0 50 100  50  0      # 가운데가 최대 100 um
0  0   0   0  0
```

### 동작
1. .dat 격자 로드 (`mask_value` 결측은 주변 보간)
2. 바이리니어 보간으로 각 노드 위치의 처짐 계산
3. prestress 모드: 유한 차분 곡률 → Kirchhoff/von Kármán 굽힘 변형률 → 초기응력 (노드 그대로)
4. deform 모드: 노드를 처짐만큼 이동

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
base_model: model.k
output: offset_result
operations:
  - type: offset
    source_pid: 1
    element_type: solid          # solid | tshell | shell
    thickness: 2.0
    thickness_formula: "1.0 + 0.01*x"   # 가변 두께 수식 (선택, x/y/z 변수)
    num_layers: 1
    offset_direction: +normal    # +normal|-normal|+x|-x|+y|-y|+z|-z
    use_local_normals: true      # 곡면 노드별 법선 사용
    connection_mode: tied        # tied | czm | contact | none (기본 tied)
    new_pid: 10                  # 새 파트 ID
    part_title: "Offset part"
    material_card: |             # MID 칸(@MID@·숫자·라벨)은 새 MID 로 바뀜
      *MAT_ELASTIC
      $#     mid        ro         e        pr
           @MID@       2.0     12000      0.25

    # CZM 연결 (connection_mode: czm)
    czm_material_card: |         # MID 칸(@CZM_MID@ 등)은 새 CZM MID 로 바뀜
      *MAT_COHESIVE_MIXED_MODE
      $#     mid        ro     roflg   intfail        en        et       gic      giic
       @CZM_MID@       2.0         0       1.0     20000     10000       0.5       0.5
      $#     xmu         t         s       und       utd     gamma
             2.0       1.0       1.0

    # 영역(region) 필터 (선택): 소스 표면의 일부만 처리
    # bbox_xmin/xmax/ymin/ymax/zmin/zmax
    # node_id_min/max, element_id_min/max
```

> **v1.8.0 정정**: (1) `connection_mode` 값 집합은 `tied | czm | contact | none` 이며 **기본값은 `tied`** 입니다(help·examples. 구버전의 `shared | tied | czm`/기본 `shared` 정정). `contact` 는 인터페이스 노드를 복제해 별도 표면을 만들고 사용자가 이후 `*CONTACT` 를 정의합니다. (2) `element_type` 값은 `solid | tshell | shell` 입니다(구버전의 `hex | tet` 정정). (3) config 는 최상위 `base_model`/`output` + `operations[].type: offset` 구조입니다. 재료는 `material_card` 로 지정하고, 층마다 다르면 `material_cards:` 목록(`- |` 항목)을 씁니다(단독·assemble 모두). (4) 카드 MID 칸의 값(`@MID@`·`@CZM_MID@`·숫자·라벨)은 새 MID 로 바뀌며, 값은 LS-DYNA 고정 폭 10열 칸 안에 두세요. (5) `new_pid`·`new_secid`·`new_mid` 를 지정해도 뒤이어 자동 발급되는 ID 와 겹치지 않습니다. (6) `connection_mode: none` 은 assemble 경로에서도 허용됩니다. 단독 `offset` 도 assemble 과 같은 값 검사를 거칩니다.

### 주요 파라미터


**표 22-1. offset 주요 파라미터 — 소스 파트, 방향·두께, 요소 유형, 연결 방식.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `source_pid` | 소스 파트 ID | — |
| `offset_direction` | 압출 방향 | — |
| `thickness` | 균일 두께 | — |
| `thickness_formula` | 가변 두께 수식 (x,y,z 변수) | — |
| `use_local_normals` | 곡면 노드별 법선 사용 | `false` |
| `element_type` | 요소 유형 (solid/tshell/shell) | `solid` |
| `connection_mode` | 연결 방식 (tied/czm/contact/none) | `tied` |

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

> **대상 PART 카드**: `*PART` 데이터 줄이 PID·SECID·MID 3칸뿐인 모델(예: `generate box` 출력)도 인식합니다(예전엔 `PID not found`).

### 파라미터 이름 접두사 규칙


**표 23-1. matswap 번들 파라미터 타입 — ID 접두어(HGID/LCID/SECID/MID/PID)별 자동 인식 규칙.**

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


**표 25-1. contact create 접촉 type — YAML type 값과 LS-DYNA *CONTACT 키워드.**

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


**표 25-2. contact detect 접촉 type — YAML 값, LS-DYNA 키워드, 용도.**

| YAML 값 | LS-DYNA 키워드 | 용도 |
|---|---|---|
| `auto` | `AUTOMATIC_SURFACE_TO_SURFACE` | 범용 |
| `tied` | `TIED_SURFACE_TO_SURFACE` | 접합 |
| `mortar` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` | 고정밀 |
| `single` | `AUTOMATIC_SINGLE_SURFACE` | 자기접촉 |
| `eroding` | `ERODING_SURFACE_TO_SURFACE` | 요소 파괴 |
| `forming` | `FORMING_SURFACE_TO_SURFACE` | 성형 해석 |

#### detect 옵션


**표 25-3. contact detect 옵션 — 탐지 범위, 포함·제외, 허용치, 법선 각, 자동 생성.**

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


**표 25-4. contact 세부 옵션 (soft·sofscl·depth·sbopt) — 키와 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `soft` | SOFT | 소프트 제약 (0/1/2) |
| `sofscl` | SOFSCL | SOFT 스케일 |
| `depth` | DEPTH | 검색 깊이 (0~45) |
| `sbopt` | SBOPT | 세그먼트 기반 옵션 |

#### Card B (두께)


**표 25-5. contact 세부 옵션 (penmax·thkopt·shlthk) — 키와 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `penmax` | PENMAX | 최대 관통량 |
| `thkopt` | THKOPT | 두께 옵션 |
| `shlthk` | SHLTHK | 셸 두께 고려 |

#### Card C (간격/에지)


**표 25-6. contact 세부 옵션 (igap·ignore) — 키와 LS-DYNA 필드.**

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

파트의 **면을 선택**해 압력/힘/중력 하중을 부여합니다. `*LOAD_*`, `*DEFINE_CURVE`, `*SET_*` 키워드를 삽입합니다.

```yaml
model: mesh.k
output: mesh_loaded.k
loads:
  - part: 10
    mode: pressure          # pressure | force | gravity
    value: 1.0              # 하중 크기
    direction: [0, 0, 1]    # 하중 방향 벡터
    select: direction       # direction | tied | all
    angle: 45.0             # 면 선택 각도 허용치(°)
    curve:                  # 선택. 시간-하중 곡선 → *DEFINE_CURVE
      - [0.0, 0.0]
      - [0.001, 1.0]
      - [0.01, 1.0]
```

### 파라미터


**표 26-1. load 파라미터 — 대상 파트, 하중 유형·크기·방향, 면 선택, 시간 곡선.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 하중 대상 파트 ID |
| `mode` | 하중 유형 (`pressure` / `force` / `gravity`) |
| `value` | 하중 크기 |
| `direction` | 하중 방향 벡터 `[x, y, z]` |
| `select` | 면 선택 방식 — `direction`(방향벡터 각도 내 법선 면) / `tied`(tied 접촉 참여 면, 모델에 해당 파트의 `*CONTACT_TIED…` 가 없으면 경고 후 파트 표면에서 고름) / `all`(파트 노출면 전체) |
| `angle` | 면 선택 각도 허용치(°) |
| `curve` | 선택. `[[t, f], ...]` 시간-하중 곡선 |

> **v1.8.0 정정**: 구버전이 보이던 `type`/`nid`/`pid`/`dof`/`lcid` 노드·파트 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`mode`/`select`/`direction`/`angle` **면-선택 스키마**를 씁니다(help·`examples/load`).

---

## 27. boundary — 경계 조건 적용

### 용도
LS-DYNA 모델에 경계 조건(구속/변위) 키워드를 삽입합니다.

### 사용법

```bash
KooRemapper.exe boundary <config.yaml>
```

### YAML 형식

파트의 **면을 선택**해 자유도 구속(SPC) 또는 강체벽 경계를 부여합니다. `*BOUNDARY_SPC_NODE`, `*RIGIDWALL_PLANAR` 키워드를 삽입합니다.

```yaml
model: mesh.k
output: mesh_bc.k
boundaries:
  - part: 9
    dof: all                 # all | x | y | z | xy | xz | yz | xyz
    direction: [0, 0, -1]    # 면 선택 방향 벡터
    select: direction        # direction | all
    angle: 45.0              # 면 선택 각도 허용치(°)
```

### 파라미터


**표 27-1. boundary 파라미터 — 대상 파트, 구속 자유도, 면 선택.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 경계 대상 파트 ID |
| `dof` | 구속 자유도 — `all`(6 DOF 전체) / `x`·`y`·`z`(단일 병진) / `xy`·`xz`·`yz`·`xyz`(다중 병진) |
| `direction` | 면 선택 방향 벡터 |
| `select` | `direction`(방향 면) / `all`(파트 노출면 전체) |
| `angle` | 면 선택 각도 허용치(°) |

> **v1.8.0 정정**: 구버전이 보이던 `type: spc/prescribed_motion` + `nid` + `dofx~dofrz` 노드 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`dof`/`select`/`direction` **면-선택 스키마**를 씁니다(help·`examples/boundary`). help 의 `dof` 목록은 `all|x|y|z|xy|xz|yz` 이나 예제는 3방향 병진 구속에 `xyz` 도 사용합니다.

---

## 28. rbe — RBE 구속 조건

### 용도
RBE2(강체 연결) 또는 RBE3(분산 하중) 구속 조건을 삽입합니다.

### 사용법

```bash
KooRemapper.exe rbe <config.yaml>
```

### YAML 형식

파트의 **면을 선택**해 RBE2/RBE3 강체 요소 구속을 만듭니다. RBE2 는 `*CONSTRAINED_NODAL_RIGID_BODY`, RBE3 는 `*CONSTRAINED_INTERPOLATION` 을 삽입합니다.

```yaml
model: mesh.k
output: mesh_rbe.k
rbe:
  - part: 9
    select: direction        # direction | all
    direction: [0, 0, -1]    # 면 선택 방향 벡터
    angle: 45.0              # 면 선택 각도 허용치(°)
    type: rbe3               # rbe2 | rbe3
    mode: spider             # spider (centroid 마스터 노드 1개) | face (면마다 centroid)
```

### 파라미터


**표 28-1. rbe 파라미터 — 대상 파트, 면 선택, RBE 유형·모드.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 대상 파트 ID |
| `select` | `direction`(방향 면) / `all`(파트 노출면 전체) |
| `direction` | 면 선택 방향 벡터 |
| `angle` | 면 선택 각도 허용치(°) |
| `type` | `rbe2`(강체: 슬레이브가 마스터와 정확히 동일 이동) / `rbe3`(보간: 마스터 이동이 슬레이브 가중 평균) |
| `mode` | `spider`(centroid 마스터 노드 1개) / `face`(면마다 centroid 노드) |

> **v1.8.0 정정**: 구버전이 보이던 `type: rbe2/rbe3` + `master_nid`/`slave_nids`/`dof`/`weights` 노드 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`select`/`mode` **면-선택 스키마**를 씁니다(help·`examples/boundary` 의 rbe_spider/rbe_face). 최상위 키는 `rbe:` 입니다.

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


**표 29-1. implicit 레벨별 비선형 솔버 설정 — NSOLVR·ILIMIT·MAXREF·수렴 허용치.**

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


**표 29-2. implicit 레벨별 시간 증분·선형 솔버·안정화 설정.**

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


**표 29-3. implicit mode: static 과 dynamic 의 IMASS·GAMMA·BETA.**

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


**표 30-1. modal 고유치 방법(eigmth) — 값별 방법과 용도.**

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


**표 31-1. relax 레벨 프리셋 — NRCYCK·DRTOL·DRFCTR 등 DR 설정.**

| Lv | 이름 | NRCYCK | DRTOL | DRFCTR | TSSFDR | IRELAL | EDTTL |
|----|------|--------|-------|--------|--------|--------|-------|
| 1 | 빠름 | 500 | 0.010 | 0.990 | 0.95 | 0 | 0.04 |
| 2 | 표준 | 250 | 0.001 | 0.995 | 0.90 | 0 | 0.04 |
| 3 | 안정 | 100 | 0.001 | 0.998 | 0.80 | 0 | 0.04 |
| 4 | 보수 | 50 | 1e-4 | 0.999 | 0.67 | 1 | 0.01 |
| 5 | 최대 | 25 | 1e-5 | 0.999 | 0.50 | 1 | 0.001 |

### 모드


**표 31-2. relax 모드 — explicit·implicit DR 과 IDRFLG.**

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

> **v1.8.0 정정**: explicit 복원 op 에는 **level 체계가 없습니다**. `model`/`output`/`keep_dr_curves` 세 키만 받습니다(help). `examples/explicit/level01.yaml`~`level12.yaml` 는 이 explicit 복원 op 이 아니라 별도 op 인 **`stabilize`**(파일 내용이 `stabilize: explicit` + `level: 1~12`, 호출 `KooRemapper stabilize levelNN.yaml`)용 예제이므로 혼동에 주의합니다(§36 stabilize 참조).

### 제거 대상


**표 32-1. explicit 제거 대상 키워드 — 키워드와 원래 소속 명령.**

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
output: cylinder_wrapped
target_pid: [1, 2]      # 하나 이상의 파트 ID (리스트)
axis: z                 # 와인딩 축 (x/y/z)
tension: 100.0          # 와인딩 인장력 [force/length]
center: [0.0, 0.0]      # 축 중심 좌표 [c1, c2] (선택, 자동 감지)
material:
  E: 210000
  nu: 0.3
```

> **v1.8.0 정정**: (1) `tension` 단위는 `[force/length]` 입니다(help. 구버전의 `MPa` 표기 정정 — 모델 단위계에 맞춰 해석). (2) 축 중심 필드명은 `center` 입니다(help·example. 구버전의 `axis_center` 정정). (3) `target_pid` 는 하나 이상의 파트 ID 리스트를 받습니다. 생성된 프리스트레스는 `relax` 또는 `dynamic_relaxation: true` 로 평형화한 뒤 본 해석에 넘깁니다.

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


**표 34-1. optimize rubber 모드가 맞추는 카드 — 카드·필드·목표값.**

| 카드 | 필드 | 목표값 |
|---|---|---|
| `*CONTROL_ACCURACY` | INN | `4` |
| `*CONTROL_ENERGY` | HGEN/RWEN/SLNTEN/RYLEN | `2/2/2/2` |
| `*CONTACT_*` (대상 PID) | SOFT | `0` |
| `*CONTACT_*` (대상 PID) | SBOPT | `2` |

#### Explicit 전용


**표 34-2. optimize rubber 모드가 조정하는 카드 — 카드·필드·동작.**

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
ale_parts:                 # 변환 대상 파트 (필수)
  - pid: 5
    material: air          # 프리셋 이름 또는 커스텀 .k 번들 경로
  - pid: 6
    material: water
fsi_pids: [1, 2, 3]        # FSI 라그랑지안 파트 (선택)
elform: 11                 # ALE ELFORM (11=multi-mat, 12=single, 기본 11)
# dct/nadv/meth (CONTROL_ALE), ctype/pfac (FSI), detonation (tnt/c4) 등 선택 옵션
```

> **v1.8.0 정정**: config 키는 `ale_parts`(각 항목 `{pid, material}`) / `fsi_pids` 입니다(help·`examples/ale`. 구버전의 `parts`/`preset`/`lagrangian_pids` 정정). `fsi_pids` 는 최상위 리스트이며(파트별 아님), 폭발물 기폭점은 최상위 `detonation: {pid, x, y, z, lt}` 로 지정합니다.

### 재료 프리셋 (14종)


**표 35-1. ale 재료 프리셋 — 분류별 프리셋과 MAT·EOS.**

| 분류 | 프리셋 | MAT | EOS |
|------|--------|-----|-----|
| 기체 | air, nitrogen, argon | MAT_NULL | EOS_LINEAR_POLYNOMIAL |
| 액체 | water, electrolyte, gasoline, oil, coolant, resin, tim, silicone | MAT_NULL | EOS_GRUNEISEN |
| 폭발물 | tnt, c4 | MAT_HIGH_EXPLOSIVE_BURN | EOS_JWL |
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


**표 36-1. stabilize 레벨 — 레벨별 주요 변경.**

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


**표 37-1. database 프리셋 — ASCII·Binary 키워드와 EXTENT.**

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

> **참고 — 독립 `strip` op 과 구분**: 여기서 다루는 `strip: true` 는 `implicit`/`modal`/`relax`/`explicit` 명령에 붙는 옵션으로, 해당 명령 소속 키워드만 제거합니다. 이와 별개로 v1.8.0 에는 **독립 `strip` op**(숨은 op)이 있어 `keywords` 리스트에 나열한 임의 키워드를 K파일에서 제거합니다(§43 추가 op 레퍼런스 참조). 둘 다 "제거만 하고 새 키워드는 삽입하지 않는다"는 점은 같습니다.

### 명령별 제거 범위


**표 38-1. 명령별 strip: true 제거 범위.**

| 명령 | strip: true 시 제거 대상 |
|------|------------------------|
| `implicit` | `*CONTROL_IMPLICIT_*` 10종 |
| `modal` | `*CONTROL_IMPLICIT_EIGENVALUE`, `_GENERAL`, `_SOLUTION`, `_SOLVER` |
| `relax` | `*CONTROL_DYNAMIC_RELAXATION`, `*DATABASE_BINARY_D3DRLF` |
| `explicit` | 위 3개 명령의 제거 대상 전부 + SIDR=1 DEFINE_CURVE |

### strip vs explicit


**표 38-2. strip: true 와 explicit 명령 비교.**

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
- **출력 이름**: `output` 끝의 `.k` 는 있어도 없어도 같습니다(`result`·`result.k` → `result.k`, dynain 은 `result.dynain`).
- **상대 경로**: `base_model`·`dat_file`·`bundle`·`dynain` 등은 YAML 파일이 있는 폴더 기준입니다(YAML 이 현재 폴더에 있어도 같음).
- **인라인 주석**: 값 뒤에 공백 + `#` 로 주석을 달 수 있습니다(따옴표 안의 `#` 는 값). 단독 YAML 명령도 같습니다.
- **값 검사**: 각 op 값을 읽을 때 검사하며, 단독 `bend`·`indent`·`offset`·`restack`·`iga` 도 같은 규칙을 씁니다.

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
  deflection_axis: +z
  unit: um
  mode: prestress
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
  element_type: solid
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
  center: [0, 0]
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


## 40. meshfix — TET4 재메시 (Gmsh 기반)

### 용도
기존 TET4 파트를 Gmsh를 통해 **완전 재메시**하여 요소 품질을 개선하는 명령.
STL 경계 추출 → Gmsh 실행 → MSH2 파싱 → 원본 K파일에 스플라이스하는 파이프라인으로 동작하며,
Gmsh 실행 파일(`gmsh.exe`)이 `dist/gmsh/` 또는 `dist/gmsh-<ver>/` 디렉터리에 있어야 한다.

### 사용법

```bash
KooRemapper.exe meshfix <config.yaml>
```

### YAML 설정 전체

```yaml
model:   input.k      # 입력 K파일
output:  output.k     # 출력 K파일
pid:     1            # 재메시할 파트 ID (TET4)

# ─── 요소 크기 제어 ────────────────────────────────────────────────────────
lc_target:    5.0     # 목표 평균 요소 크기 (기본: 1.0, 단위: 모델 단위)
lc_min:      -1.0     # 최소 요소 크기 (-1 = 자동: edge_min×0.8 또는 dt 기반)
lc_max:      -1.0     # 최대 요소 크기 (-1 = lc_target × 2)

# ─── dt 기반 lc_min (lc_min 대신 사용 가능) ───────────────────────────────
min_dt:       1.0e-6  # LS-DYNA explicit 시간 증분 하한 (초)
density:      2.7e-9  # 밀도 (t/mm³)
E:            70000.0 # 탄성계수 (MPa)
nu:           0.33    # 포아송 비

# ─── 얇은 형상 처리 ────────────────────────────────────────────────────────
min_layers_thin: 2    # 얇은 방향 최소 요소 레이어 수 (기본: 2)

# ─── 적응형 사이즈 필드 ────────────────────────────────────────────────────
adaptive:     true    # bbox 코너 거리 기반 MathEval 필드 활성화 (기본: true)
decay_factor: 8.0     # 코너 세밀 영역 크기 = lc_min × decay_factor

# ─── Gmsh 메셔 설정 ────────────────────────────────────────────────────────
algorithm:       hxt  # 3D 메셔: hxt (병렬, 기본) | frontal3d | del3d
optimize_netgen: true # Gmsh 내장 Netgen 최적화 활성화
optimize_passes: 3    # Mesh 3 이후 추가 OptimizeMesh "Netgen" 호출 횟수

# ─── 표면 STL 전처리 ───────────────────────────────────────────────────────
refine_surface:  auto # auto | 0(off) | 1~3 (conforming feature-edge 세분화)
smooth_surface:  0    # feature-edge Laplacian 스무딩 스텝 수 (0=off)

# ─── 경계 노드 처리 ────────────────────────────────────────────────────────
boundary_nodes: free  # free | fixed | snap
snap_tolerance: 0.001 # snap 모드 탐색 반경

# ─── 품질 보고 ─────────────────────────────────────────────────────────────
quality_check:  true  # 재메시 후 스케일드 자코비안 보고 활성화
warn_min_jac:   0.15  # 이 값 미만 요소에 경고 출력

# ─── 패치 폴리싱 (실험적) ─────────────────────────────────────────────────
polish:          false # 나쁜 요소 클러스터 로컬 재메시 (기본: off)
polish_jac:      0.10  # polish 대상 임계값 (J < polish_jac)
polish_max_iter: 2     # 최대 반복 횟수
```

**표 40-1. meshfix YAML 옵션 요약**

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `lc_target` | 1.0 | 목표 평균 요소 크기 |
| `lc_min` | auto | 최솟값 (-1=자동, dt 기반 또는 edge_min×0.8) |
| `lc_max` | auto | 최댓값 (-1=lc_target×2) |
| `adaptive` | true | MathEval bbox 코너 거리 필드 |
| `algorithm` | hxt | Gmsh 3D 메셔 선택 |
| `optimize_passes` | 3 | 추가 Netgen 최적화 횟수 |
| `refine_surface` | auto | STL feature-edge 세분화 레벨 |
| `warn_min_jac` | 0.15 | 품질 경고 임계값 |
| `polish` | false | 나쁜 요소 로컬 재메시 |

### 동작 파이프라인

```
[1] K파일 로드 → TET4 파트 추출
        ↓
[2] 메시 분석
    - lc_min/max 자동 계산
    - geomThin 감지 (min_bbox < avg_bbox × 0.3)
    - autoRefineSurface 레벨 결정
        ↓
[3] 경계 STL 추출
    - 비다양체 에지 필터 (Stage 1: 점수 기반)
    - bbox 표면 노드 필터 (Stage 2: 레이캐스팅)
    - 최대 연결 컴포넌트만 유지
        ↓
[4] STL 전처리
    - refine_surface: conforming feature-edge 세분화 (dihedral > 40°)
    - smooth_surface: feature-edge Laplacian 스무딩
        ↓
[5] Gmsh .geo 스크립트 생성
    - ClassifySurfaces{40°} → CreateGeometry → Volume
    - MathEval 적응형 사이즈 필드 (또는 인플레인 4코너 필드)
        ↓
[6] Gmsh 실행 (HXT 알고리즘)
    Mesh 2 → Mesh 3 → OptimizeMesh "Netgen" × N
        ↓
[7] MSH2 파싱 → 스케일드 자코비안 품질 검사
        ↓
[8] (polish=true) 나쁜 클러스터 로컬 재메시
        ↓
[9] K파일 스플라이스 (기존 노드/요소 교체, 다른 파트 보존)
```

> **그림 40-1. meshfix 처리 파이프라인 — 입력 K파일에서 재메시된 출력 K파일까지의 전체 데이터 흐름을 단계별로 나타낸다. [2]~[4]는 전처리, [5]~[6]은 Gmsh 처리, [7]~[9]는 후처리에 해당한다.**

### 적응형 사이즈 필드

MathEval 거리 필드: Gmsh 임베디드 Point 엔티티 없이 순수 수식으로 구현 (HXT 호환).

```
Field[1] = MathEval;
Field[1].F = "Sqrt(Min(Min(d000,d001),Min(...,d111)))";
    ← bbox 8개 코너까지의 최솟값 거리 (수식)

Field[2] = Threshold;
    SizeMin = lc_min     ← 코너 근처: 세밀
    SizeMax = lc_max     ← 내부: 큰 요소

Field[3] = MathEval; F = "lc_target";
    ← 균일 배경 필드

Background Field = Min(Field[2], Field[3]);
```

> **그림 40-2. MathEval 적응형 사이즈 필드 구성 — 8개 bbox 코너까지의 최솟값 거리를 기준으로 코너 근처에서는 lc_min, 내부에서는 lc_target의 요소 크기를 유도한다.**

**얇은 형상 (geomThin) 처리:**
min_bbox < avg_bbox × 0.3인 경우 자동 감지하여 다음을 전환한다.

**표 40-2. geomThin 감지 시 동작 변경**

| 항목 | 일반 형상 | 얇은 형상 (geomThin) |
|---|---|---|
| Mesh 2 (표면 메시) | 실행 | **스킵** |
| 사이즈 필드 | 8코너 3D 필드 | **4코너 인플레인 필드** |
| Netgen OptimizePasses | 실행 | **스킵** |
| autoRefineSurface | 0 (Mesh 2가 대신함) | 1 (필요 시) |

### 스케일드 자코비안 (Scaled Jacobian)

TET4 요소의 형상 품질을 나타내는 무차원 지표.

$$J_s = \frac{6\sqrt{2} \cdot V}{L_{max}^3}$$

여기서 V = TET4 체적, $L_{max}$ = 가장 긴 엣지 길이. 정규 TET4에서 $J_s = 1.0$.

**표 40-3. 스케일드 자코비안 판정 기준**

| 범위 | 판정 | 설명 |
|---|---|---|
| $J_s \geq 0.5$ | **우수** | LS-DYNA 권장 범위 |
| $0.2 \leq J_s < 0.5$ | 양호 | 실용적으로 허용 |
| $0.15 \leq J_s < 0.2$ | 주의 | warn_min_jac 경고 기준 |
| $0.0 < J_s < 0.15$ | **불량** | 재메시 또는 개선 필요 |
| $J_s \leq 0$ | 역전 | 음의 체적 — 해석 불가 |

### 기하학적 품질 한계

90° 직각 코너에 인접한 TET4는 기하 구속으로 인해 이론적 최솟값이 존재한다.

$$J_{s,min}^{corner} \approx 0.03 \sim 0.07 \quad \text{(기하 구속, 요소 크기와 무관)}$$

이 한계는 기하학 수정(코너 라운딩, 필렛 추가) 없이는 개선할 수 없다.

### 패치 폴리싱 (polish)

`polish: true` 설정 시 재메시 후 추가 국소 개선을 시도한다.

**표 40-4. 패치 폴리싱 이중 품질 게이트**

| 조건 | 식 | 의미 |
|---|---|---|
| 최솟값 Jac 유지 | $J_{min,new} \geq J_{min,orig} \times 0.95$ | 최솟값 5% 이상 회귀 시 거부 |
| 불량 수 감소 | $N_{bad,new} < N_{bad,orig}$ | 불량 요소 수가 줄어야 수락 |

두 조건을 모두 만족한 패치만 메시에 머지한다. 하나라도 불만족이면 해당 클러스터는 원본 유지.

### 경계 노드 처리 모드

**표 40-5. boundary_nodes 모드별 동작**

| 모드 | 동작 | 사용 예 |
|---|---|---|
| `free` (기본) | 모든 Gmsh 노드에 새 ID 부여 | 독립 파트 재메시 |
| `fixed` | 경계 노드를 원본 ID에 고정 (좌표 매칭) | 인접 파트와 공유 노드 |
| `snap` | 인접 파트 노드에 snap_tolerance 이내이면 병합 | 파트 간 접합 재메시 |

### 실행 예시

```yaml
# 예시: arc30 평면 TET4 메시 재메시
model:      examples/arc30/arc30_flat_tet.k
output:     output/remeshed.k
pid:        1
lc_target:  5.0
adaptive:   true
warn_min_jac: 0.15
```

실행 출력:
```
PID 1 TET4:              3000
  lc_min=1  lc_max=10
Gmsh TET4:               34695
Min scaled Jacobian:     0.0675
Avg scaled Jacobian:     0.405
[WARN] 847 elements below warn_min_jac=0.15
Total time: 13.6 s
```

> **그림 40-3. meshfix 실행 출력 예 — 입력 3,000개 TET4가 34,695개로 재메시됨. 스케일드 자코비안 통계와 품질 경고가 출력된다. 847개 불량 요소는 박스 90° 코너의 기하 구속에 의한 것으로, 기하학 수정 없이는 개선 불가하다.**

### 주의사항

- **Gmsh 필수**: `dist/gmsh/gmsh.exe` 또는 `dist/gmsh-<ver>/gmsh.exe` 위치에 배치 필요
- **TET4 전용**: 입력 파트는 TET4 (또는 퇴화 HEX8) 형식이어야 함
- **처리 시간**: 10만 요소 이상에서 수 분 소요 가능
- **polish 제한**: `polish: true`는 실험적 기능. 90° 코너 구속 형상에서는 불량 수 감소 불가로 자동 스킵

---

## 41. 수학 이론

### 41.1 등매개변수 매핑 (map)

HEX8 요소의 자연 좌표계 (ξ, η, ζ) ∈ [-1, 1]³:

$$\mathbf{x}(\xi,\eta,\zeta) = \sum_{i=1}^{8} N_i(\xi,\eta,\zeta)\,\mathbf{x}_i$$

역매핑 (Newton-Raphson):

$$\begin{pmatrix} \Delta\xi \\ \Delta\eta \\ \Delta\zeta \end{pmatrix} = \mathbf{J}^{-1} (\mathbf{x}_{target} - \mathbf{x}(\xi,\eta,\zeta))$$

야코비안 행렬:

$$J_{ij} = \frac{\partial x_i}{\partial \xi_j} = \sum_{k=1}^{8} \frac{\partial N_k}{\partial \xi_j} x_{ki}$$

### 41.2 선형 탄성 재료 모델

라메 상수:

$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}, \quad \mu = G = \frac{E}{2(1+\nu)}$$

구성 방정식 (Voigt 표기):

$$\begin{pmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \sigma_{zz} \\ \sigma_{xy} \\ \sigma_{yz} \\ \sigma_{xz} \end{pmatrix} = \begin{pmatrix} \lambda+2\mu & \lambda & \lambda & 0 & 0 & 0 \\ \lambda & \lambda+2\mu & \lambda & 0 & 0 & 0 \\ \lambda & \lambda & \lambda+2\mu & 0 & 0 & 0 \\ 0 & 0 & 0 & \mu & 0 & 0 \\ 0 & 0 & 0 & 0 & \mu & 0 \\ 0 & 0 & 0 & 0 & 0 & \mu \end{pmatrix} \begin{pmatrix} \varepsilon_{xx} \\ \varepsilon_{yy} \\ \varepsilon_{zz} \\ 2\varepsilon_{xy} \\ 2\varepsilon_{yz} \\ 2\varepsilon_{xz} \end{pmatrix}$$

### 41.3 Kirchhoff 판 이론 (bend/indent)

중립면에서 거리 z인 지점의 변형률:

$$\varepsilon_{11}(z) = -z \kappa_{11}, \quad \varepsilon_{22}(z) = -z \kappa_{22}, \quad 2\varepsilon_{12}(z) = -2z \kappa_{12}$$

모멘트-곡률 관계 (굽힘 강성 D):

$$D = \frac{E t^3}{12(1-\nu^2)}$$

$$M_{11} = D(\kappa_{11} + \nu \kappa_{22}), \quad M_{22} = D(\kappa_{22} + \nu \kappa_{11}), \quad M_{12} = D(1-\nu)\kappa_{12}$$

### 41.4 형성 변형률 이론 (formstrain)

이면각 θ, 인접 셸 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

면외 굽힘 변형률 (두께 방향 선형 분포):

$$\varepsilon_{top} = +\frac{t}{2}\kappa, \quad \varepsilon_{bot} = -\frac{t}{2}\kappa$$

등가 소성 변형률 (Von Mises 기준, 단축 가정):

$$\overline{\varepsilon}^p = \frac{2}{\sqrt{3}} |\varepsilon_{max}|$$

---

## 42. 출력 파일 형식

### dynain 파일 (`*INITIAL_STRESS_SOLID`)

파일 이름은 `<output>.dynain` 입니다(assemble·squeeze·restack 등, prestress 는 §6). 머리 `$` 주석 뒤 요소마다 두 줄을 씁니다.

```
*INITIAL_STRESS_SOLID
$#    eid    nint   nhisv   large     ics   ncomp
         3       1       0       0       0       0
$#  sigxx     sigyy     sigzz     sigxy     sigyz     sigxz       eps
 5.654e+03 2.423e+03 2.423e+03 0.000e+00 0.000e+00 0.000e+00 0.000e+00
```

### 사면체 요소 연결 순서

TET4 는 `*ELEMENT_SOLID` 8절점 칸에 LS-DYNA 규정대로 **N1, N2, N3, N4, N4, N4, N4, N4** 로 씁니다(elform 하향, split_fillet 분할 등). LS-DYNA R16 Vol I 는 이 순서를 어기면 초기화에서 negative volume 으로 종료한다고 적고 있고, KooRemapper 도 이 순서만 TET4 로 다시 읽습니다.

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

## 43. 추가 op 레퍼런스 (v1.8.0 대조 추가)

정본에 전용 섹션이 없던 op 들을 v1.8.0 바이너리 기준으로 간결히 정리한다. 각 op 의 근거(help / examples / pyKooCAE 페이지)를 함께 표기한다. 이 중 `extract-surface`·`tetremesh`·`merge`·`strip` 4종과 `meshfix`(§40)는 `KooRemapper --help` 최상위 목록에 없는 **숨은 op** 이지만 정상 동작한다.

### 43.1 battery — 배터리 셀 생성

**용도**: 배터리 셀(적층 `stacked` / 권취 `wound`) 모델을 YAML 설정에서 생성하고, 스웰링(swelling) 상태 평형을 `*CONTROL_DYNAMIC_RELAXATION` 데크로 잡는다.

**호출형태**: yaml-config op.

```bash
KooRemapper battery <config.yaml>
```

**주요 config 키** (예제 관찰 기반 — `examples/battery/swell/*`; help 는 필드 문서를 출력하지 않음):

| 키 | 설명 |
|---|---|
| `output` | 출력 접두사/경로 |
| `model_type` | `stacked` 또는 `wound` |
| `tier` / `phase` / `mode` | 티어·페이즈 지정, `mode: swell` |
| `solid_electrode` / `solid_elform` | 전극층 solid 화, (wound) 1=reduced/2=full |
| `geometry.cell_width` / `.cell_height` / `.n_unit_cells` | 셀 치수·(stacked) 단위셀 수 |
| `layer_thickness.*` | al_cc·cathode·separator·anode·cu_cc·pouch·electrolyte_buffer 두께 [mm] |
| `pouch.*` | 필렛·버퍼·돔캡 파라미터 |
| `wound.flat` / `.flat_ratio` / `.n_winds` | (wound) 편평·비율·권취 수 |
| `swelling.soc` / `.nmc_cte` / `.graphite_cte` | SOC·양극/음극 팽창률 |
| `dr_endtim` / `dr_tolerance` / `dr_factor` / `dr_nrcyck` | DR 파라미터 |

**근거**: pyKooCAE `mesh_generate.md`, `examples/battery/swell/{stacked,wound}/*.yaml`. 정본에 없던 op 이라 필드는 예제 관찰 기반이며, 미등장 필드·기본값은 확인 필요.

---

### 43.2 cclip — C형 스프링 클립 치환

**용도**: 스마트폰 스프링 접점 등 hex box 파트를 측정 힘-변위(F-δ) 데이터에 캘리브레이션한 C형 쉘 스트립 클립으로 치환하고, 눌린(pressed) 상태로 `*INITIAL_STRESS_SHELL` 을 넣어 출력한다.

**호출형태**: yaml-config op.

```bash
KooRemapper cclip <config.yaml>
```

**주요 config 키** (help + `examples/cclip/*.yaml`):

| 키 | 값/설명 |
|---|---|
| `model` / `output` | 입력 .k / 출력 접두(`.k` + `_cclip_report.json` 생성) |
| `mode` | `analytic` 또는 `deck`(LS-DYNA press deck) |
| `attach` | `none` 또는 `cnrb`(foot tied to board) |
| `stress_output` | `embed` 또는 `include`(.dynain + `*INCLUDE`) |
| `free_output` | true 시 `<output>_free.k`(눌리지 않은 원안)도 출력 |
| `element` | `shell` 또는 `solid`(through-thickness HEX8) |
| `axis` | `auto` 또는 `[+\|-]x\|y\|z`(press-from side) |
| `open` | C 벌징 방향(길이축 기준, 예: `"+"`) |
| `calibration.point` | `{deflection, force}` 단일 작동점(analytic) |
| `calibration.curve` | `[[d,F], ...]` F-δ 곡선(deck) |
| `calibration.operating_deflection` | 곡선 모드 필수(설치 눌림량) |
| `calibration.tolerance` | 캘리브레이션 허용오차 |
| `clips[].pid` | 대상 파트 ID(또는 `match_part: "CCLIP_*"`, `auto: true`) |
| `clips[].overtravel` | free height = installed + overtravel |

**근거**: help(`Usage:`), pyKooCAE `mesh_generate.md`, `examples/cclip/cclip.yaml`(analytic)·`cclip_deck.yaml`(deck). 원본 PID 를 유지해 기존 SET/CONTACT 참조가 살아남으며, 출력 검증은 `tools/cclip_check.py` 로 한다(솔버 불필요).

---

### 43.3 cnrb2solid — CNRB 볼트를 솔리드로 변환

**용도**: `*CONSTRAINED_NODAL_RIGID_BODY`(CNRB, 강체 볼트 구속)를 O-grid(butterfly) 토폴로지의 HEX8 솔리드 실린더로 변환하고, 원본 노드와 신규 솔리드 사이에 `*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET` 를 생성한다. 볼트 헤드(플랜지)도 자동 생성할 수 있다.

**호출형태**: yaml-config op (모든 키를 최상위 flat 에 둠).

```bash
KooRemapper cnrb2solid <config.yaml>
```

**주요 config 키** (`examples/cnrb2solid/{basic,with_head}.yaml`):

| 키 | 기본값 | 설명 |
|---|---|---|
| `model` / `output` | (필수) | 입출력 K파일 |
| `E` / `PR` / `RHO` | (필수) | 탄성계수[MPa] / 포아송비 / 밀도[t/mm³] |
| `radius_scale` | 0.999 | 링 노드 반경 = 볼트홀 R × scale |
| `num_circum_nodes` | 0(자동) | 원주 노드 수(4의 배수) |
| `inner_radius_ratio` | 0.3 | 코어 사각형 반변 / R 비율 |
| `axis_direction` | auto | 실린더 축(PCA 자동 감지) |
| `z_tolerance` / `r_tolerance` | 0.1 / 0.5 | Z-레벨 그룹핑 / 다중 반경 클러스터링 허용오차 [mm] |
| `head_offset_r` / `head_thickness` / `head_position` | 0.0 / 2.0 / auto | 헤드 반경 오프셋(0=미생성) / 두께 / 위치 |

**근거**: pyKooCAE `surface_remesh.md`, `docs/cnrb2solid_concept.md`, `examples/cnrb2solid/*.yaml`. 재료값(E/PR/RHO)은 변환 없이 그대로 쓰이므로 모델 단위계와 일치시켜야 한다.

---

### 43.4 hfdamp — 고주파 댐핑

**용도**: 소형 요소가 만드는 고주파(스퓨리어스) 진동을 억제한다. `*DAMPING_FREQUENCY_RANGE_DEFORM` 을 삽입한다(selective 모드에서는 대상 파트의 `*SET_PART_LIST` 도 생성).

**호출형태**: yaml-config op.

```bash
KooRemapper hfdamp <config.yaml>
```

**주요 config 키** (`examples/hfdamp/*.yaml`, README):

| 키 | 기본값 | 설명 |
|---|---|---|
| `model` / `output` | (필수) | 입출력 K파일 |
| `dt_target` | (필수) | 댐핑 타겟 dt. `FLOW = 1/(2×dt_target)` |
| `cdamp` | 0.99 | 임계 감쇠비(0 < cdamp ≤ 1), 대역 [FLOW, FHIGH]에 적용 |
| `fhigh_ratio` | 100.0 | `FHIGH = FLOW × ratio`(권장 10~300) |
| `mode` | global | `global`(PSID=0 전 파트) / `selective`(요소 dt ≤ dt_target 파트만, 재료 E·PR·RHO 필요) |
| `tssfac` | 0.9 | selective 전용. 요소 dt 추정 안전계수 |

**근거**: pyKooCAE `load_bc_contact.md`, `examples/hfdamp/{basic,selective,hfdamp_full}.yaml`. DEFORM 옵션은 요소 응력/힘을 감쇠하고 강체 운동은 감쇠하지 않으며 동적 강성을 약 CDAMP% 높인다. `--help` 는 인자를 config 경로로 해석해 에러를 내므로 근거는 예제·README.

---

### 43.5 modelmeta — 파트별 메타 JSON 추출

**용도**: K파일을 읽어 파트별 기하 메트릭·재료·연결성(connectivity)을 구조화된 JSON 으로 추출한다. 모델을 변형하지 않는 읽기 전용 op 로, `*CONTACT` 카드가 없어도 기하학적으로 닿는 파트쌍을 탐지할 수 있다.

**호출형태**: yaml-config op.

```bash
KooRemapper modelmeta <config.yaml>
```

**주요 config 키** (`examples/modelmeta/modelmeta.yaml`):

| 키 | 예제값/기본 | 설명 |
|---|---|---|
| `model` | (필수) | 분석 대상 K파일(읽기 전용, `*INCLUDE` 1단계 추적) |
| `detect` | true | `*CONTACT` 없이도 기하학적으로 닿는 파트쌍 탐지 |
| `gap_tol` | 0.2 | 탐지 갭 허용치(모델 길이 단위) |
| `output` | (생략 시 `<model>_modelmeta.json`) | 출력 JSON 이름 |
| `material_db` | (생략 시 실행파일 옆 번들 DB) | 재료 DB 경로 |
| `db_mid_fallback` | false | MID 일치 폴백(로컬 MID 충돌 위험 — opt-in) |

**근거**: pyKooCAE `info_meta.md`, `examples/modelmeta/modelmeta.yaml`. 정본에 없던 op 이라 필드는 help 동작과 단일 예제 유추이며, JSON 스키마 상세 필드·기본값은 확인 필요.

---

### 43.6 update — 노드 좌표 갱신

**용도**: dynain 또는 K파일의 `*NODE` 블록을 읽어 모델의 일치 노드 좌표를 덮어쓴다. 불일치 노드는 그대로 둔다. (assemble §39.18 에 operations 형태로도 기술)

**호출형태**: yaml-config op (flat 스키마).

```bash
KooRemapper update <config.yaml>
```

```yaml
model:  original.k
output: updated.k
dynain: dr_result.dynain   # *NODE 블록을 가진 임의 파일(dynain/K-file 등)
```

assemble/체인에서는 operations 항목으로도 쓴다.

```yaml
operations:
  - type: update
    dynain: dr_result.dynain
```

**근거**: help(`Usage:`), pyKooCAE `mesh_edit.md`. model 과 소스 양쪽에 있는 노드만 갱신되고 나머지는 유지된다.

---

### 43.7 extract-surface — 표면 셸 추출 (숨은 op)

**용도**: 솔리드 K파일에서 표면 셸을 추출한다.

**호출형태**: positional op (help `Usage:` 와 정확히 일치).

```bash
KooRemapper extract-surface <solid.k> <output_shell.k> [--pid N] [--face top|bottom|all] [--output-pid N]
```

| 인자/옵션 | 설명 |
|---|---|
| `<solid.k>` | 입력 솔리드 K파일 (positional 1) |
| `<output_shell.k>` | 출력 셸 K파일 (positional 2) |
| `--pid N` | 대상 파트 ID |
| `--face top\|bottom\|all` | 추출할 면 선택 |
| `--output-pid N` | 출력 셸에 부여할 파트 ID |

**근거**: help(`Usage:`), pyKooCAE `surface_remesh.md`. 옵션 세부 동작·기본값은 정본 예제가 없어 플래그 이름 기준이며 확인 필요.

---

### 43.8 tetremesh — TET4 로컬 재메시 (숨은 op)

**용도**: 기존 TET4 파트를 품질 게이트(스케일드 자코비안·종횡비)로 스캔하고, 불량 요소 패치를 국소 재메시한다. `localimprove`(외부 라이브러리 불필요, 항상 사용 가능)와 `tetgen`(빌드 플래그 `KOOREMAPPER_BUILD_TETGEN` 필요, AGPL v3) 두 백엔드를 지원한다. (§40 meshfix 의 Gmsh 전체 재메시와 별개)

**호출형태**: yaml-config op.

```bash
KooRemapper tetremesh <config.yaml>
```

**주요 config 키** (help YAML 스키마):

| 키 | 기본값 | 설명 |
|---|---|---|
| `model` / `output` | (필수) | 입출력 K파일 |
| `backend` | localimprove | `localimprove` \| `tetgen` |
| `fallback` | (없음) | 주 백엔드 실패 시 대체 백엔드 |
| `report_only` | false | true 면 스캔·보고만 |
| `target_pids` | [](전체) | 대상 파트 ID 리스트 |
| `quality.min_jacobian` | 0.2 | 스케일드 자코비안 하한 |
| `quality.max_aspect_ratio` | 8.0 | 종횡비 상한 |
| `patch.ring_expand` / `.surface_flatness_deg` / `.surface_move_tolerance` / `.preserve_multi_material` | 2 / 5.0 / 0.0 / true | 패치 확장·평면 판정·이동·다중재료 보존 |
| `improve.laplacian_iters` / `.max_outer_iters` / `.allow_subdivide` | 5 / 3 / true | (Phase A) 스무딩·반복·세분화 |
| `tetgen.quality_ratio` / `.min_dihedral_deg` | 1.4 / 10.0 | (Phase B) `-q` 반경/에지 비·최소 이면각 |

**근거**: help(`Usage:` + YAML 스키마), pyKooCAE `surface_remesh.md`. `report_only: true` 로 먼저 품질 스캔 후 재메시가 안전하다.

---

### 43.9 merge — 적층 파트 균질화 병합 (숨은 op)

**용도**: 적층된 여러 파트(PID)를 하나의 균질화(homogenized) 재료 레이어로 병합한다.

**호출형태**: yaml-config op.

```bash
KooRemapper merge <config.yaml>
```

```yaml
model: three_layer.k
output: merged_output.k
direction: z
method: vrh        # voigt | reuss | vrh (Voigt-Reuss-Hill 평균)
merge:
  - pids: [1, 2, 3]
    name: "Homogenized_Stack"
```

| 키 | 설명 |
|---|---|
| `model` / `output` | 입출력 K파일 |
| `direction` | 적층 방향 |
| `method` | `voigt` / `reuss` / `vrh` |
| `merge[]` | 병합 그룹(`pids` 합칠 리스트 + `name` 결과 파트 이름) |

**근거**: help(`Usage:` 한 줄), pyKooCAE `surface_remesh.md`, `examples/merge/merge_test.yaml`. 정본 섹션이 없어 `direction` 의 다른 값·추가 키 여부는 확인 필요.

---

### 43.10 strip — 키워드 제거 (숨은 op)

**용도**: `keywords` 리스트로 지정한 LS-DYNA 키워드를 K파일에서 제거한다(부피 큰 메시 데이터 제거 등). §38 의 `strip: true` 옵션과는 별개의 독립 op 다.

**호출형태**: yaml-config op.

```bash
KooRemapper strip <config.yaml>
```

```yaml
model: al_box.k
output: stripped_output.k
keywords:
  - "*NODE"
  - "*ELEMENT_SOLID"
  - "*ELEMENT_SHELL"
  - "*INITIAL_STRESS_SOLID"
  - "*INITIAL_STRESS_SHELL"
```

**근거**: help(`Usage:` 한 줄), pyKooCAE `surface_remesh.md`, `examples/strip/strip_test.yaml`.

---

*KooRemapper v1.8.0 | 이 문서는 모든 구현 기능을 포함합니다.*
