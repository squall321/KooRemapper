# KooRemapper 프로젝트 개발 총정리

## 1. 프로젝트 개요

**KooRemapper**는 LS-DYNA K-file 기반의 메쉬 매핑 및 프리스트레스 계산 도구이다.
폴더블 디스플레이와 같은 다층 적층 구조물에서, 평면(flat) 상태의 상세 메쉬를
굽힘(bent) 형상으로 매핑하고, 변형에 의한 초기응력(prestress)을 계산하여
LS-DYNA dynain 파일로 출력한다.

- **버전**: 1.1.0
- **언어**: C++17
- **빌드**: CMake 3.15+, 완전 정적 링크 (DLL 의존성 없음)
- **병렬화**: OpenMP
- **라이센스**: MIT

---

## 2. 주요 기능 (Commands)

| 명령어 | 기능 | 핵심 알고리즘 |
|--------|------|---------------|
| `map` | 평면 메쉬를 굽힘 형상으로 매핑 | Edge-based arc-length 보간 + BFS 인덱싱 |
| `unfold` | 굽힘 메쉬를 평면으로 전개 | Arc-length 파라미터화 |
| `prestress` | 변형에 의한 초기응력 계산 | 변형 구배 텐서 → 변형률 → Hooke's Law |
| `generate-var` | YAML 기반 가변 밀도 메쉬 생성 | Zone 기반 밀도 제어, 곡선 보간 |
| `generate` | 11종 예제 메쉬 생성 | Arc, S-curve, Helix, Torus 등 |
| `strain` | 변형률 필드 계산 | Engineering / Green-Lagrange / Log strain |
| `info` | 메쉬 정보 표시 | Jacobian 품질 검사 |

---

## 3. 전체 워크플로우

```
[1단계] 굽힘 메쉬 준비
   - LS-DYNA K-file (bent mesh)
   - HyperMesh 등에서 생성

[2단계] 평면 메쉬 생성
   KooRemapper generate-var config.yaml flat.k
   - YAML로 Zone별 요소 밀도 제어
   - 곡선 중심선 기반 메쉬도 가능 (Catmull-Rom, B-Spline)

[3단계] 매핑
   KooRemapper map bent.k flat.k remapped.k
   - BFS로 구조 격자 인덱싱
   - Edge 기반 arc-length 보간으로 노드 매핑
   - OpenMP 병렬 처리

[4단계] 프리스트레스 계산
   KooRemapper prestress flat.k bent.k output.dynain
   - 변형 구배 F = J_def · J_ref⁻¹
   - Green-Lagrange 변형률 E = ½(F^T·F − I)
   - Hooke's Law: σ = λ·tr(ε)·I + 2μ·ε
   - *INITIAL_STRESS_SOLID 카드로 출력
```

---

## 4. 핵심 알고리즘

### 4.1 BFS 기반 구조 격자 인덱싱

비구조 메쉬(unstructured mesh)에 (i, j, k) 구조 격자 인덱스를 부여하는 알고리즘.

1. 요소 간 인접성(connectivity) 분석
2. 임의의 시작 요소에서 BFS(너비 우선 탐색) 수행
3. 기하학적 방향(요소 중심 좌표)으로 i, j, k 축 결정
4. dimK ≤ dimJ ≤ dimI 순으로 축 재배열
5. 노드 순서를 LS-DYNA 표준(하면 반시계, 상면 반시계)에 맞게 재배열

### 4.2 Edge 기반 Arc-length 보간 (실제 사용)

```
P(u,v,w) = (1-w)·[(1-v)·p₀₀(u) + v·p₁₀(u)] + w·[(1-v)·p₀₁(u) + v·p₁₁(u)]
```

- 메쉬의 4개 i축 Edge에 대해 arc-length 룩업 테이블 구축
- 매개변수 u ∈ [0,1]을 arc-length 위치로 매핑
- (v, w) 평면에서 bilinear 블렌딩
- 굽힘 메쉬의 기하학적 형상을 정확히 보존

### 4.3 Transfinite 보간 (구현됨, 미사용)

12개 Edge + 6개 Face를 활용한 Gordon-Hall 보간. 구현은 되었으나 Edge 기반 방법이
충분히 정확하여 실제로는 사용하지 않음.

### 4.4 변형 구배 텐서 (Deformation Gradient)

```
F = J_deformed · J_reference⁻¹
```

- HEX8: Gauss 적분점(1점 또는 2×2×2=8점)에서 평가
- TET4: 상수 구배 (선형 형상함수)
- Shape function: N_i(ξ,η,ζ) = ⅛(1±ξ)(1±η)(1±ζ)

### 4.5 변형률-응력 관계 (Hooke's Law)

```
σ = λ·tr(ε)·I + 2μ·ε

λ = E·ν / ((1+ν)(1−2ν))   [Lamé 제1 매개변수]
μ = E / (2(1+ν))           [전단 탄성계수]
```

---

## 5. 지원 재료 모델

| 재료 키워드 | MAT 번호 | 처리 방식 |
|-------------|----------|-----------|
| `MAT_ELASTIC` | 001 | E, ν 직접 사용 |
| `MAT_PIECEWISE_LINEAR_PLASTICITY` | 024 | E, ν 추출 (탄성 영역) |
| `MAT_RIGID` | 020 | E, ν 추출 |
| `MAT_VISCOELASTIC` | 006 | 장기 전단 계수로 E 추정 |
| `MAT_MOONEY-RIVLIN_RUBBER` | 027 | G₀=2(A+B), E=2G₀(1+ν)로 변환 |

미지원 재료 사용 시 에러 메시지 출력 + 영향받는 파트 리스트 표시 후 종료.

---

## 6. 개발 과정에서 만난 예상치 못한 문제들

이 프로젝트에서 가장 가치 있는 부분은 **처음에 예상하지 못했던 문제들을 발견하고
해결한 과정**이다. 아래에 주요 사례를 정리한다.

### 6.1 Engineering Strain의 강체 회전 오염 (가장 큰 발견)

**문제**: 스티프한 재료(Ti, Glass 등)가 대변형(굽힘)을 겪을 때 응력이 **5배 이상
과평가**되었다.

**원인**: Engineering strain ε = ½(F + F^T) − I 는 강체 회전(rigid body rotation)을
변형으로 오인한다.

```
30° 순수 회전의 경우:
  F = R (회전 행렬)

  Engineering: ε = ½(R + R^T) − I
    → ε_xx = ε_yy = cos(30°) − 1 = −0.134  (가짜 13.4% 압축!)

  Green-Lagrange: E = ½(R^T·R − I) = 0  (정확히 0)
```

**실측 비교** (Ti, E=105,000 MPa, 30° 굽힘):

| | Engineering | Green-Lagrange | 비율 |
|---|---|---|---|
| 평균 von Mises strain | 0.682 | 0.125 | 5.5배 |
| 최대 von Mises stress | 114,202 MPa | 22,720 MPa | 5.0배 |

**해결**: 기본 strain type을 `GREEN_LAGRANGE`로 변경. Green-Lagrange 변형률은
강체 회전에 불변(invariant)이므로 대변형에서도 정확하다.

**교훈**: 소변형 가정의 이론식을 대변형 문제에 적용하면 안 된다. 특히 굽힘처럼
회전이 큰 경우, Engineering strain은 물리적으로 무의미한 결과를 만든다.

---

### 6.2 Fixed-Width 요소 파싱 순서 문제

**문제**: Bent 메쉬에서 **~5,000개 요소가 누락**되었다. Flat 메쉬는 정상.

**원인**: LS-DYNA의 fixed-width 포맷에서 노드 ID가 공백 없이 붙어있는 경우:
```
1098724       51100417511004174110043571100435611036996110369951103717711037176
```

`tokenize()`가 먼저 호출되면 이 라인에서 토큰이 2개만 나와서 "2줄 포맷"으로
오인했다. 실제로는 8자리씩 잘라야 하는 fixed-width 포맷.

**해결**: `parseElementSolidSection()`에서 **fixed-width 포맷을 먼저 체크**하고,
실패 시 free-format tokenize를 시도하도록 순서 변경.

```cpp
// 80자 이상이면 fixed-width 먼저 시도
if (line.length() >= 80) {
    int eid = parseInt(line.substr(0, 8));
    int pid = parseInt(line.substr(8, 8));
    // ...
}
// 실패 시 free format
auto tokens = tokenize(line);
```

**교훈**: 파서에서 포맷 감지 순서가 중요하다. 더 제한적인 조건(fixed-width)을
먼저 체크해야 오탐을 방지할 수 있다.

---

### 6.3 하이픈이 포함된 LS-DYNA 키워드

**문제**: `*MAT_MOONEY-RIVLIN_RUBBER`가 `*MAT_MOONEY`로만 읽혔다.
"unsupported material" 에러 발생.

**원인**: `extractKeyword()` 함수가 알파벳, 숫자, 밑줄(`_`)만 유효 문자로 인식.
하이픈(`-`)에서 키워드 추출이 중단됨.

```cpp
// 수정 전
if (std::isalnum(c) || c == '_') { ... }

// 수정 후
if (std::isalnum(c) || c == '_' || c == '-') { ... }
```

**교훈**: LS-DYNA 키워드 명명 규칙이 일관적이지 않다. 대부분 밑줄을 사용하지만,
일부 재료(MAT_MOONEY-RIVLIN_RUBBER 등)는 하이픈을 포함한다.

---

### 6.4 *PART 키워드 하나에 여러 파트 정의

**문제**: K-file에 10개 파트가 있는데 **Part-Material 매핑이 1개만** 출력됨.

**원인**: HyperMesh가 생성한 K-file에서는 `*PART` 키워드 하나 아래에 여러 파트가
연속으로 정의된다:
```
*PART
$NAME
Lattice
     5   8001     19  ...
$NAME
PSA0
    16   8001     44  ...
```

`parsePartSection()`이 첫 번째 파트를 읽은 후 **`break`로 루프를 빠져나갔다**.

**해결**: `break` 제거, 파트 읽은 후 상태 변수를 리셋하고 다음 파트를 계속 읽도록 수정.

**교훈**: LS-DYNA K-file 표준을 엄밀히 따르는 것과, 실제 상용 소프트웨어가
생성하는 파일을 처리하는 것은 다르다. HyperMesh, LS-PrePost 등 각 전처리기마다
파일 생성 방식이 다를 수 있다.

---

### 6.5 Mooney-Rivlin 고무의 선택적 필드

**문제**: `*MAT_MOONEY-RIVLIN_RUBBER` 파싱 시 "4 tokens (need 6)" 에러.

**원인**: 실제 K-file에서 B와 REF 필드가 비어있을 수 있다:
```
$      MID       RHO        PR         A         B       REF
        441.1000E-09     0.499      31.7
```
라인 길이가 40자 정도여서 10자씩 6개 필드를 채우지 못함.

**해결**: 최소 필수 필드를 4개(MID, RHO, PR, A)로 변경. B와 REF는 있으면 파싱,
없으면 0.0 기본값 사용.

```cpp
// 최소 4개 토큰만 필요 (B, REF는 선택적)
if (tokens.size() >= 4) {
    // ...
    b = (tokens.size() >= 5) ? parseDouble(tokens[4]) : 0.0;
}
```

**교훈**: LS-DYNA fixed-width 포맷에서 trailing 공백 필드는 라인 자체가 짧아질 수
있다. 항상 선택적 필드를 고려한 방어적 파싱이 필요하다.

---

### 6.6 Prestress 출력 시 기준 메쉬 복사 오류

**문제**: Prestress 결과 K-file이 **flat(기준) 메쉬**의 노드를 포함하고 있었다.

**원인**: Dynain은 응력 데이터만 담고 있고, 이것을 **변형(bent) 메쉬**에
`*INCLUDE`로 포함시켜야 한다. 그런데 코드가 기준(flat) 메쉬를 복사하고 있었다.

```cpp
// 수정 전 (잘못됨)
std::ifstream srcFile(refFile, std::ios::binary);

// 수정 후 (올바름)
std::ifstream srcFile(defFile, std::ios::binary);
```

**교훈**: Prestress 워크플로우에서 "기준"과 "변형"의 역할을 명확히 구분해야 한다.
Dynain의 응력은 변형 상태에서의 초기값이므로, 변형 메쉬와 함께 사용해야 한다.

---

### 6.7 ν ≈ 0.5 재료의 체적 응력 폭발

**분석 과정에서 발견** (실제 버그는 아님):

Mooney-Rivlin 고무 (ν=0.499)에서 Lamé 파라미터 λ가 폭발적으로 커진다:
```
λ = E·ν / ((1+ν)(1−2ν))
(1−2ν) = 0.002 → λ ≈ 500·μ
```

미세한 체적 변형률(메쉬 매핑 오차)만으로도 거대한 hydrostatic stress가 발생할 수
있다. 다행히 고무의 E 자체가 매우 작아(~190 MPa) 실질적 문제는 없었지만,
스티프한 거의 비압축성 재료에서는 주의가 필요하다.

**교훈**: 거의 비압축성 재료(ν → 0.5)에서는 deviatoric/volumetric 분리 처리나
혼합 변분법(mixed formulation)이 필요할 수 있다.

---

## 7. 아키텍처 구조

```
src/
├── main.cpp                    [커맨드 디스패처, 1300+ lines]
├── core/                       [기본 자료구조: Node, Element, Mesh, Vector3D]
├── parser/                     [K-file 읽기/쓰기, Dynain 출력]
├── mapper/                     [매핑 핵심: BFS, Edge 보간, 전개]
├── grid/                       [구조 격자: 인덱싱, Edge 계산, 경계 추출]
├── analysis/                   [변형률/응력: 변형구배, 텐서, 재료모델]
├── generator/                  [메쉬 생성: YAML, 가변밀도, 곡선]
├── example/                    [11종 예제 메쉬]
├── cli/                        [인자 파싱, 콘솔 출력]
└── util/                       [로거, 타이머, 검증]

include/                        [43개 헤더, 동일 구조]
docs/                           [이론 문서, 계획서]
```

---

## 8. 커밋 히스토리 (시간순)

| 커밋 | 내용 |
|------|------|
| `4f9fa13` | 최초 커밋: KooRemapper v1.0.0 |
| `21500cb` | Prestress 계산 기능 추가 |
| `96aa1f1` | 가변 밀도 메쉬 생성기 + 파트별 재료 지원 |
| `4c7d7c7` | 곡선 중심선 기반 메쉬 생성 (YAML) |
| `8d2ce75` ~ `cfb6399` | README 문서화 |
| `607e589` | 배포 가이드 + 패키징 스크립트 |
| `7f76bd6` | 레이어 방향 및 i-방향 매핑 수정 |
| `dbdfcd0` | Fixed-width 파싱 + OpenMP 병렬화 + 이론 문서 |
| `96cbdff` | Fixed-width 요소 파싱 순서 수정 (~5000개 누락 해결) |
| `a6c7ff1` | MAT_MOONEY-RIVLIN_RUBBER 지원 + 미지원 재료 감지 |
| `4cc7e12` | *PART 멀티 파트 파싱 수정 |
| `1574aec` | 버전 1.1.0 |
| `82f959a` | 이론 문서, 프레젠테이션, 테스트 데이터 |
| `90fb400` | 대용량 테스트 파일 gitignore |
| `c57ee10` | 기본 strain type을 Green-Lagrange로 변경 |

---

## 9. 수치 검증 요약

### 변형률 타입별 비교 (Ti, E=105,000, ν=0.3, 30° 굽힘)

| | Engineering | Green-Lagrange |
|---|---|---|
| 평균 von Mises strain | 0.682 | 0.125 |
| 최대 von Mises strain | 0.943 | 0.188 |
| 평균 von Mises stress | 82,646 MPa | 15,085 MPa |
| 최대 von Mises stress | 114,202 MPa | 22,720 MPa |

Engineering strain은 강체 회전에 의한 가짜 변형률(cos θ − 1)이 중첩되어
응력이 **5배 이상 과평가**된다.

### Mooney-Rivlin 등가 변환 검증 (MID=44)

```
입력: A=31.7, B=0, PR=0.499
계산: G₀ = 2(31.7 + 0) = 63.4
      E = 2 × 63.4 × (1 + 0.499) = 190.073 MPa
      ν = 0.499
```

---

## 10. 향후 개선 가능 사항

1. **비선형 재료 모델**: 현재 모든 재료를 선형 탄성으로 처리. 대변형 초탄성
   (Neo-Hookean, Mooney-Rivlin 자체 구성방정식)을 구현하면 고무 파트의
   정확도 향상 가능

2. **Deviatoric/Volumetric 분리**: ν → 0.5 재료에서 체적 잠금(volumetric
   locking) 방지를 위한 B-bar 방법이나 혼합 변분법

3. **Green-Lagrange + 2nd Piola-Kirchhoff**: 현재 Green-Lagrange 변형률에
   Cauchy 응력을 바로 계산하고 있으나, 에너지 공액쌍(conjugate pair)은
   2nd PK 응력. 엄밀한 대변형 해석에서는 이 구분이 필요

4. **Shell 요소 지원**: 현재 HEX8, TET4 솔리드만 지원. 쉘 요소 추가 시
   적용 범위 확대

5. **GUI**: 현재 CLI 전용. 간단한 GUI 또는 HyperMesh/LS-PrePost 플러그인
   연동 가능

---

## 11. 결론

KooRemapper는 "평면 메쉬를 굽힘 형상으로 매핑하고 초기응력을 계산한다"는
단순해 보이는 목표에서 출발했지만, 실제 개발 과정에서는 **연속체 역학의
근본적인 문제들**을 마주했다.

특히 **Engineering Strain의 강체 회전 오염 문제**는 이 프로젝트의 핵심 발견이다.
소변형 이론(engineering strain + Hooke's law)을 대변형 문제에 적용하면
물리적으로 무의미한 결과가 나온다는 것을 실측 데이터로 확인했으며,
Green-Lagrange 변형률로 전환함으로써 5배 이상의 과평가를 해소했다.

또한 LS-DYNA K-file 파싱에서도 **표준 문서와 실제 파일 사이의 괴리**를
여러 차례 경험했다. Fixed-width 포맷의 공백 없는 패킹, 하이픈이 포함된
키워드, 한 키워드 아래 여러 데이터 블록 등은 표준만으로는 예측할 수 없는
실무적 문제들이었다.

이러한 경험들은 단순한 코딩 이상의 **공학적 판단력**을 필요로 했으며,
프로젝트의 가장 큰 수확이었다.
