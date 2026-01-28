# KooRemapper 이론 문서
## 메시 매핑 및 응력/변형률 계산 알고리즘

**Version 1.0**
**Date: 2026-01-20**

---

# 목차

1. [개요](#1-개요)
2. [메시 매핑 알고리즘](#2-메시-매핑-알고리즘)
   - 2.1 [호장 길이 기반 Edge-Based 보간](#21-호장-길이-기반-edge-based-보간---실제-사용) **← 실제 사용**
   - 2.2 [호장 길이 기반 매개변수화](#22-호장-길이-기반-매개변수화-arc-length-parameterization---실제-사용) **← 실제 사용**
   - 2.3 [트랜스파이닛 보간법](#23-트랜스파이닛-보간법-transfinite-interpolation---구현됨-미사용) (구현됨, 미사용)
   - 2.4 [삼선형 보간](#24-삼선형-보간-trilinear-interpolation---구현됨-미사용) (구현됨, 미사용)
   - 2.5 [Coons 패치](#25-coons-패치-coons-patch---면-보간에-사용)
   - 2.6 [구조화 그리드 인덱싱](#26-구조화-그리드-인덱싱---실제-사용) **← 실제 사용**
3. [변형 해석 알고리즘](#3-변형-해석-알고리즘)
   - 3.1 [변형 구배 텐서](#31-변형-구배-텐서-deformation-gradient---실제-사용) **← 실제 사용**
   - 3.2 [변형률 텐서](#32-변형률-텐서-strain-tensor---실제-사용) **← 실제 사용**
   - 3.3 [응력 텐서](#33-응력-텐서-stress-tensor---실제-사용) **← 실제 사용**
4. [수치 해석 기법](#4-수치-해석-기법)
   - 4.1 [가우스 적분](#41-가우스-적분-gauss-quadrature---실제-사용) **← 실제 사용**
   - 4.2 [형상 함수](#42-형상-함수-shape-functions---실제-사용) **← 실제 사용**
   - 4.3 [야코비안 행렬](#43-야코비안-행렬-jacobian-matrix)
5. [재료 모델](#5-재료-모델)
6. [참고 문헌](#6-참고-문헌)

---

# 1. 개요

KooRemapper는 LS-DYNA 유한요소 해석을 위한 메시 매핑 및 프리스트레스 계산 도구입니다. 본 문서는 프로그램에서 사용된 핵심 수학적 알고리즘과 이론적 배경을 상세히 설명합니다.

## 1.1 주요 기능

- **메시 매핑**: 평면(flat) 메시를 곡면(bent) 참조 형상으로 변환
- **변형률 계산**: 기준 형상과 변형 형상 간의 변형률 계산
- **응력 계산**: 재료 물성을 이용한 Cauchy 응력 계산
- **DYNAIN 출력**: LS-DYNA 프리스트레스 입력 파일 생성

## 1.2 좌표계 정의

프로그램은 다음 좌표계를 사용합니다:

- **물리 좌표계 (Physical Coordinates)**: (x, y, z) - 실제 공간 좌표
- **매개변수 좌표계 (Parametric Coordinates)**: (u, v, w) ∈ [0,1]³ - 정규화된 좌표
- **자연 좌표계 (Natural Coordinates)**: (ξ, η, ζ) ∈ [-1,1]³ - 요소 내부 좌표

---

# 2. 메시 매핑 알고리즘

> **KooRemapper 실제 구현 요약**
>
> 본 프로그램은 **호장 길이 기반 Edge-Based 보간법**을 사용합니다:
> 1. 12개 모서리에서 **호장 길이(Arc-length) 매개변수화** 적용 (`EdgeInterpolator`)
> 2. i-축 4개 모서리에서 점을 선택 후 **(v, w) 평면에서 쌍선형 보간** (`ParametricMapper::edgeBasedInterpolate`)
>
> Gordon-Hall 트랜스파이닛 보간과 삼선형 보간은 코드에 구현되어 있으나 현재 비활성화 상태입니다.

---

## 2.1 호장 길이 기반 Edge-Based 보간 - **실제 사용**

> **구현 위치**: `ParametricMapper::edgeBasedInterpolate()`, `EdgeInterpolator::interpolate()`

### 2.1.1 개요

KooRemapper는 구조화 Hex 메시의 매핑을 위해 Edge-Based 보간법을 사용합니다. 이 방법은:
- 12개 모서리의 실제 곡선 형상을 보존
- 호장 길이 기반 매개변수화로 물리적 대응성 보장
- bent → unfold → remap 왕복 시 원래 위치로 정확히 복귀

### 2.1.2 알고리즘

**Step 1: i-축 4개 모서리에서 호장 길이 기반 점 선택**

```cpp
// ParametricMapper::edgeBasedInterpolate() 구현
Vector3D p00 = edges_[0].interpolate(u);  // j=0, k=0 모서리
Vector3D p10 = edges_[1].interpolate(u);  // j=N, k=0 모서리
Vector3D p01 = edges_[2].interpolate(u);  // j=0, k=P 모서리
Vector3D p11 = edges_[3].interpolate(u);  // j=N, k=P 모서리
```

여기서 `edges_[i].interpolate(u)`는 호장 길이 기반 보간을 수행합니다 (2.2절 참조).

**Step 2: (v, w) 평면에서 쌍선형 보간**

```cpp
Vector3D bottom = p00 * (1-v) + p10 * v;  // k=0 선
Vector3D top    = p01 * (1-v) + p11 * v;  // k=P 선
Vector3D result = bottom * (1-w) + top * w;
```

수학적 표현:

$$P(u,v,w) = (1-w) \cdot [(1-v) \cdot p_{00}(u) + v \cdot p_{10}(u)] + w \cdot [(1-v) \cdot p_{01}(u) + v \cdot p_{11}(u)]$$

### 2.1.3 장점

- 구조화 그리드의 격자점에서 정확한 결과
- 모서리 곡선 형상 보존
- 계산 효율성 (단순 쌍선형 보간)

---

## 2.2 호장 길이 기반 매개변수화 (Arc-length Parameterization) - **실제 사용**

> **구현 위치**: `EdgeInterpolator::build()`, `EdgeInterpolator::interpolate()`

### 2.2.1 이론

곡선을 따라 균일한 매개변수 분포를 보장하기 위해 호장 길이를 사용합니다. 이 방법은 평면 메시의 X 좌표가 곡면 메시의 곡선 길이에 정확히 대응되도록 합니다.

### 2.2.2 알고리즘 (실제 구현)

**Step 1: 누적 호장 계산** (`EdgeInterpolator::build()`)

```cpp
arcLengths_.push_back(0.0);  // s₀ = 0
for (size_t i = 1; i < points_.size(); ++i) {
    double segmentLength = points_[i].distanceTo(points_[i - 1]);
    totalLength_ += segmentLength;
    arcLengths_.push_back(totalLength_);  // sᵢ = sᵢ₋₁ + |Pᵢ - Pᵢ₋₁|
}
```

수학적 표현:
$$s_0 = 0, \quad s_i = s_{i-1} + \|P_i - P_{i-1}\|, \quad L_{total} = s_n$$

**Step 2: 매개변수 t에 대한 위치 계산** (`EdgeInterpolator::interpolate()`)

```cpp
double targetLength = t * totalLength_;  // 목표 호장

// 해당 선분 검색
for (size_t i = 0; i + 1 < arcLengths_.size(); ++i) {
    if (targetLength >= arcLengths_[i] && targetLength <= arcLengths_[i + 1]) {
        idx = i;
        break;
    }
}

// 국소 매개변수 계산
double segmentLength = arcLengths_[idx + 1] - arcLengths_[idx];
double localT = (targetLength - arcLengths_[idx]) / segmentLength;

// 선형 보간
return Vector3D::lerp(points_[idx], points_[idx + 1], localT);
```

수학적 표현:

목표 호장: $s_{target} = t \cdot L_{total}$

선분 검색: $s_i \leq s_{target} < s_{i+1}$인 i 찾기

국소 매개변수:
$$t_{local} = \frac{s_{target} - s_i}{s_{i+1} - s_i}$$

보간 결과:
$$P(t) = (1 - t_{local}) \cdot P_i + t_{local} \cdot P_{i+1}$$

### 2.2.3 장점

- 곡선 길이에 비례한 균일한 점 분포
- 물리적 대응성 보장 (평면 X좌표 ↔ 곡면 호장 길이)
- 곡률 변화에 자연스럽게 적응
- U-fold 등 복잡한 형상에서도 일관된 매핑

---

## 2.3 트랜스파이닛 보간법 (Transfinite Interpolation) - *구현됨, 미사용*

> **구현 위치**: `ParametricMapper::transfiniteInterpolate()` - 코드에 존재하나 현재 비활성화

### 2.3.1 이론적 배경

Gordon & Hall (1973)이 개발한 방법으로, 경계 조건을 정확히 만족하면서 내부 영역을 보간합니다.

### 2.3.2 3차원 Gordon-Hall 공식

$$P(u,v,w) = P_{faces} - P_{edges} + P_{corners}$$

**면 기여항:**
$$P_{faces} = (1-u)F_0(v,w) + uF_1(v,w) + (1-v)F_2(u,w) + vF_3(u,w) + (1-w)F_4(u,v) + wF_5(u,v)$$

**모서리 기여항 (빼기):**
$$P_{edges} = \sum_{i=0}^{11} w_i(u,v,w) \cdot E_i(t)$$

**코너 기여항 (더하기):**
$$P_{corners} = \sum_{i=0}^{7} w_i(u,v,w) \cdot C_i$$

### 2.3.3 미사용 이유

Edge-Based 보간이 구조화 Hex 메시에서 더 단순하고 정확한 결과를 제공하므로 현재 비활성화되어 있습니다.

---

## 2.4 삼선형 보간 (Trilinear Interpolation) - *구현됨, 미사용*

> **구현 위치**: `ParametricMapper::trilinearInterpolate()` - 코드에 존재하나 현재 비활성화

8개 코너 노드만 사용하는 가장 단순한 형태:

$$P(u,v,w) = \sum_{i=0}^{7} N_i(u,v,w) \cdot C_i$$

형상함수:
$$N_i(u,v,w) = \frac{1}{8}(1 \pm u)(1 \pm v)(1 \pm w)$$

| 노드 | u | v | w |
|------|---|---|---|
| 0 | - | - | - |
| 1 | + | - | - |
| 2 | + | + | - |
| 3 | - | + | - |
| 4 | - | - | + |
| 5 | + | - | + |
| 6 | + | + | + |
| 7 | - | + | + |

### 2.4.1 미사용 이유

코너만 사용하므로 모서리 곡선 형상이 무시됩니다. 곡률이 큰 메시에서 정확도가 떨어집니다.

---

## 2.5 Coons 패치 (Coons Patch) - *면 보간에 사용*

> **구현 위치**: `FaceInterpolator::buildBilinear()` - 면 보간에 부분적 사용

### 2.5.1 이론적 배경

Coons (1967)가 제안한 곡면 보간법으로, 4개의 경계 곡선으로 정의된 곡면을 생성합니다.

### 2.5.2 수학적 정의

4개 경계 곡선:
- $C_0(t)$: s=0 경계 (아래)
- $C_1(t)$: s=1 경계 (위)
- $D_0(s)$: t=0 경계 (왼쪽)
- $D_1(s)$: t=1 경계 (오른쪽)

**Coons 패치 공식:**

$$P(s,t) = L_c(s,t) + L_d(s,t) - B(s,t)$$

여기서:

$$L_c(s,t) = (1-s) \cdot D_0(t) + s \cdot D_1(t)$$

$$L_d(s,t) = (1-t) \cdot C_0(s) + t \cdot C_1(s)$$

$$B(s,t) = (1-s)(1-t) \cdot P_{00} + s(1-t) \cdot P_{10} + (1-s)t \cdot P_{01} + st \cdot P_{11}$$

### 2.5.3 특성

- 4개 경계 곡선을 정확히 통과
- 4개 코너 점을 정확히 통과
- 내부는 부드럽게 보간됨

---

## 2.6 구조화 그리드 인덱싱 - **실제 사용**

> **구현 위치**: `StructuredIndexer`, `MeshConnectivity`

### 2.6.1 목적

비정렬(unstructured) 메시 요소에 (i, j, k) 구조화 인덱스를 할당합니다.

### 2.6.2 BFS 기반 알고리즘

**Step 1: 코너 요소 탐색**

코너 요소 조건: 정확히 3개의 면 이웃을 가진 요소

```
for each element e:
    if neighbor_count(e) == 3:
        corner_elements.add(e)
```

**Step 2: 기하 기반 축 방향 결정**

요소 중심(centroid)의 상대 위치에서 축 방향 계산:

```
direction_i = average(neighbor_centroids) - element_centroid
direction_j = perpendicular_in_plane(direction_i)
direction_k = cross(direction_i, direction_j)
```

**Step 3: BFS 전파**

```python
def BFS_indexing(start_element):
    queue = [(start_element, 0, 0, 0)]
    visited = {}

    while queue:
        (elem, i, j, k) = queue.pop(0)
        if elem in visited:
            continue
        visited[elem] = (i, j, k)

        for (neighbor, direction) in get_face_neighbors(elem):
            if direction == +i: queue.add((neighbor, i+1, j, k))
            if direction == -i: queue.add((neighbor, i-1, j, k))
            if direction == +j: queue.add((neighbor, i, j+1, k))
            if direction == -j: queue.add((neighbor, i, j-1, k))
            if direction == +k: queue.add((neighbor, i, j, k+1))
            if direction == -k: queue.add((neighbor, i, j, k-1))
```

**Step 4: 축 순서 정렬**

조건: $dim_k \leq dim_j \leq dim_i$

필요시 축을 교환하여 조건 만족

**Step 5: 노드 순서 정규화**

LS-DYNA HEX8 표준 노드 순서:
- 하단면 (k=0): 반시계 방향 n₀, n₁, n₂, n₃
- 상단면 (k=1): 반시계 방향 n₄, n₅, n₆, n₇
- k-축: 하단 → 상단 방향

---

# 3. 변형 해석 알고리즘

> **KooRemapper 실제 구현 요약**
>
> 변형 해석은 다음 단계로 수행됩니다:
> 1. **변형 구배 계산**: `DeformationGradient::computeHex8()` - 야코비안 기반 계산
> 2. **변형률 계산**: `StrainTensor::fromDeformationGradient()` - 공학/Green-Lagrange 선택 가능
> 3. **응력 계산**: `StressTensor::fromStrain()` - Hooke 법칙 적용
> 4. **가우스 적분**: 1점 또는 8점 적분 선택 가능 (`setGaussPoints()`)

---

## 3.1 변형 구배 텐서 (Deformation Gradient) - **실제 사용**

> **구현 위치**: `DeformationGradient::computeHex8()`, `DeformationGradient::computeJacobianHex8()`

### 3.1.1 정의

변형 구배 텐서 **F**는 기준 형상에서 현재 형상으로의 국소 변형을 나타냅니다:

$$\mathbf{F} = \frac{\partial \mathbf{x}}{\partial \mathbf{X}}$$

여기서:
- $\mathbf{x}$: 현재(변형된) 좌표
- $\mathbf{X}$: 기준(미변형) 좌표

### 3.1.2 성분 표현

$$F_{ij} = \frac{\partial x_i}{\partial X_j}$$

$$\mathbf{F} = \begin{bmatrix}
\frac{\partial x}{\partial X} & \frac{\partial x}{\partial Y} & \frac{\partial x}{\partial Z} \\
\frac{\partial y}{\partial X} & \frac{\partial y}{\partial Y} & \frac{\partial y}{\partial Z} \\
\frac{\partial z}{\partial X} & \frac{\partial z}{\partial Y} & \frac{\partial z}{\partial Z}
\end{bmatrix}$$

### 3.1.3 유한요소 계산 (실제 구현)

자연 좌표계를 통한 계산:

$$\mathbf{F} = \mathbf{J}_{def} \cdot \mathbf{J}_{ref}^{-1}$$

```cpp
// DeformationGradient::computeHex8() 구현
Matrix3x3 J_ref = computeJacobianHex8(refNodes, xi, eta, zeta);
Matrix3x3 J_def = computeJacobianHex8(defNodes, xi, eta, zeta);
Matrix3x3 J_ref_inv = J_ref.inverse();
return J_def * J_ref_inv;
```

야코비안 행렬 계산:

$$J_{ij} = \frac{\partial x_i}{\partial \xi_j} = \sum_k \frac{\partial N_k}{\partial \xi_j} \cdot x_{k,i}$$

```cpp
// DeformationGradient::computeJacobianHex8() 구현
for (int i = 0; i < 3; ++i) {      // x, y, z
    for (int j = 0; j < 3; ++j) {  // xi, eta, zeta
        double sum = 0.0;
        for (int k = 0; k < 8; ++k) {
            sum += dN[k][j] * nodes[k][i];
        }
        J(i, j) = sum;
    }
}
```

### 3.1.4 물리적 의미

- $det(\mathbf{F}) > 0$: 요소 유효 (양의 체적)
- $det(\mathbf{F}) < 0$: 요소 뒤집힘 (음의 야코비안)
- $det(\mathbf{F}) = 1$: 비압축성 변형
- $\mathbf{F} = \mathbf{I}$: 변형 없음

---

## 3.2 변형률 텐서 (Strain Tensor) - **실제 사용**

> **구현 위치**: `StrainTensor::fromDeformationGradient()`

### 3.2.1 공학 변형률 (Engineering Strain) - **기본값**

작은 변형 가정 하에서:

$$\boldsymbol{\varepsilon} = \frac{1}{2}(\mathbf{F} + \mathbf{F}^T) - \mathbf{I}$$

```cpp
// StrainType::ENGINEERING 구현
Matrix3x3 sym = F.symmetric();  // (F + F^T) / 2
E = sym - Matrix3x3::identity();
```

성분 표현:

$$\varepsilon_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial X_j} + \frac{\partial u_j}{\partial X_i}\right)$$

여기서 변위 $\mathbf{u} = \mathbf{x} - \mathbf{X}$

### 3.2.2 Green-Lagrange 변형률 - **옵션으로 사용 가능**

큰 변형에 적합한 비선형 변형률:

$$\mathbf{E} = \frac{1}{2}(\mathbf{F}^T \cdot \mathbf{F} - \mathbf{I}) = \frac{1}{2}(\mathbf{C} - \mathbf{I})$$

```cpp
// StrainType::GREEN_LAGRANGE 구현
Matrix3x3 FtF = F.transpose() * F;
E = (FtF - Matrix3x3::identity()) * 0.5;
```

여기서 $\mathbf{C} = \mathbf{F}^T \cdot \mathbf{F}$는 우 Cauchy-Green 변형 텐서

성분 표현:

$$E_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial X_j} + \frac{\partial u_j}{\partial X_i} + \frac{\partial u_k}{\partial X_i}\frac{\partial u_k}{\partial X_j}\right)$$

### 3.2.3 Voigt 표기법

대칭 텐서를 6개 독립 성분으로 표현:

$$\{\varepsilon\} = \begin{bmatrix} \varepsilon_{xx} \\ \varepsilon_{yy} \\ \varepsilon_{zz} \\ \gamma_{xy} \\ \gamma_{yz} \\ \gamma_{xz} \end{bmatrix}$$

여기서 공학 전단변형률: $\gamma_{ij} = 2\varepsilon_{ij}$ (i ≠ j)

### 3.2.4 주변형률 (Principal Strains)

변형률 텐서의 고유값 문제:

$$det(\boldsymbol{\varepsilon} - \lambda \mathbf{I}) = 0$$

특성 방정식:

$$\lambda^3 - I_1\lambda^2 + I_2\lambda - I_3 = 0$$

불변량:
- $I_1 = tr(\boldsymbol{\varepsilon}) = \varepsilon_{xx} + \varepsilon_{yy} + \varepsilon_{zz}$
- $I_2 = \frac{1}{2}[I_1^2 - tr(\boldsymbol{\varepsilon}^2)]$
- $I_3 = det(\boldsymbol{\varepsilon})$

**Cardano 공식**을 이용한 해석해:

$$p = I_2 - \frac{I_1^2}{3}$$
$$q = \frac{2I_1^3}{27} - \frac{I_1 I_2}{3} + I_3$$

$$\lambda_k = \frac{I_1}{3} + 2\sqrt{-\frac{p}{3}} \cos\left(\frac{\theta + 2\pi k}{3}\right), \quad k = 0, 1, 2$$

여기서 $\theta = \arccos\left(\frac{3q}{2p}\sqrt{-\frac{3}{p}}\right)$

### 3.2.5 von Mises 등가 변형률 - **실제 사용**

> **구현 위치**: `StrainTensor::vonMisesStrain()`

$$\varepsilon_{eq} = \sqrt{\frac{2}{3} \boldsymbol{\varepsilon}' : \boldsymbol{\varepsilon}'}$$

여기서 편차 변형률:

$$\varepsilon'_{ij} = \varepsilon_{ij} - \frac{1}{3}\varepsilon_{kk}\delta_{ij}$$

```cpp
// StrainTensor::vonMisesStrain() 구현
StrainTensor dev = deviatoric();
double sum = dev.xx*dev.xx + dev.yy*dev.yy + dev.zz*dev.zz;
sum += 0.5 * (dev.xy*dev.xy + dev.yz*dev.yz + dev.xz*dev.xz);
return std::sqrt(2.0 / 3.0 * sum);
```

성분 형태:

$$\varepsilon_{eq} = \frac{\sqrt{2}}{3}\sqrt{(\varepsilon_{xx}-\varepsilon_{yy})^2 + (\varepsilon_{yy}-\varepsilon_{zz})^2 + (\varepsilon_{zz}-\varepsilon_{xx})^2 + 6(\varepsilon_{xy}^2 + \varepsilon_{yz}^2 + \varepsilon_{xz}^2)}$$

### 3.2.6 체적 변형률

$$\varepsilon_{vol} = \varepsilon_{xx} + \varepsilon_{yy} + \varepsilon_{zz} = tr(\boldsymbol{\varepsilon})$$

---

## 3.3 응력 텐서 (Stress Tensor) - **실제 사용**

> **구현 위치**: `StressTensor::fromStrain()`

### 3.3.1 Hooke 법칙 (등방성 선형 탄성)

$$\boldsymbol{\sigma} = \lambda \cdot tr(\boldsymbol{\varepsilon}) \cdot \mathbf{I} + 2\mu \cdot \boldsymbol{\varepsilon}$$

Lamé 상수:
- 제1 Lamé 상수: $\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}$
- 전단 계수 (제2 Lamé 상수): $\mu = G = \frac{E}{2(1+\nu)}$

### 3.3.2 탄성 강성 행렬

Voigt 표기법에서의 구성 행렬:

$$\{\sigma\} = [\mathbf{C}]\{\varepsilon\}$$

$$[\mathbf{C}] = \begin{bmatrix}
C_{11} & C_{12} & C_{12} & 0 & 0 & 0 \\
C_{12} & C_{11} & C_{12} & 0 & 0 & 0 \\
C_{12} & C_{12} & C_{11} & 0 & 0 & 0 \\
0 & 0 & 0 & C_{44} & 0 & 0 \\
0 & 0 & 0 & 0 & C_{44} & 0 \\
0 & 0 & 0 & 0 & 0 & C_{44}
\end{bmatrix}$$

여기서:
- $C_{11} = \lambda + 2\mu = \frac{E(1-\nu)}{(1+\nu)(1-2\nu)}$
- $C_{12} = \lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}$
- $C_{44} = \mu = \frac{E}{2(1+\nu)}$

### 3.3.3 주응력 (Principal Stresses)

변형률과 동일한 고유값 문제:

$$det(\boldsymbol{\sigma} - \sigma_p \mathbf{I}) = 0$$

주응력 순서: $\sigma_1 \geq \sigma_2 \geq \sigma_3$

### 3.3.4 von Mises 응력 (항복 기준)

$$\sigma_{vm} = \sqrt{\frac{3}{2} \mathbf{s} : \mathbf{s}}$$

여기서 편차 응력:

$$s_{ij} = \sigma_{ij} - \frac{1}{3}\sigma_{kk}\delta_{ij} = \sigma_{ij} - \sigma_m\delta_{ij}$$

평균 응력 (정수압):

$$\sigma_m = \frac{1}{3}(\sigma_{xx} + \sigma_{yy} + \sigma_{zz})$$

성분 형태:

$$\sigma_{vm} = \frac{1}{\sqrt{2}}\sqrt{(\sigma_{xx}-\sigma_{yy})^2 + (\sigma_{yy}-\sigma_{zz})^2 + (\sigma_{zz}-\sigma_{xx})^2 + 6(\tau_{xy}^2 + \tau_{yz}^2 + \tau_{xz}^2)}$$

주응력 형태:

$$\sigma_{vm} = \frac{1}{\sqrt{2}}\sqrt{(\sigma_1-\sigma_2)^2 + (\sigma_2-\sigma_3)^2 + (\sigma_3-\sigma_1)^2}$$

### 3.3.5 응력 삼축성 (Stress Triaxiality)

$$\eta = \frac{\sigma_m}{\sigma_{vm}}$$

물리적 의미:
- $\eta > 1/3$: 인장 지배 (취성 파괴 위험)
- $\eta \approx 0$: 순수 전단
- $\eta < 0$: 압축 지배

### 3.3.6 최대 전단응력 (Tresca)

$$\tau_{max} = \frac{\sigma_1 - \sigma_3}{2}$$

---

# 4. 수치 해석 기법

## 4.1 가우스 적분 (Gauss Quadrature) - **실제 사용**

> **구현 위치**: `DeformationGradient::gaussPointsHex8()`
>
> KooRemapper는 **1점 적분(기본)** 또는 **8점 적분(옵션)** 을 지원합니다.
> `--gauss 1` 또는 `--gauss 8` 옵션으로 선택 가능.

### 4.1.1 이론

적분을 가중 합으로 근사:

$$\int_{-1}^{1} f(\xi) d\xi \approx \sum_{i=1}^{n} w_i f(\xi_i)$$

### 4.1.2 1D 가우스점

| 차수 n | 위치 ξᵢ | 가중치 wᵢ |
|--------|---------|-----------|
| 1 | 0 | 2 |
| 2 | ±1/√3 | 1 |
| 3 | 0, ±√(3/5) | 8/9, 5/9 |

### 4.1.3 3D HEX8 요소 (실제 구현)

**1-점 적분 (Reduced Integration) - 기본값:**

```cpp
// numPoints == 1
points.push_back({{0.0, 0.0, 0.0, 8.0}});  // {xi, eta, zeta, weight}
```

- 위치: (0, 0, 0)
- 가중치: 8
- 장점: 빠름, shear locking 방지
- 단점: hourglass 모드 가능

**2×2×2 = 8-점 적분 (Full Integration) - 옵션:**

```cpp
// numPoints == 8
const double g = 1.0 / std::sqrt(3.0);  // ≈ 0.577
for (i,j,k in {0,1}³) {
    xi   = (i == 0) ? -g : g;
    eta  = (j == 0) ? -g : g;
    zeta = (k == 0) ? -g : g;
    points.push_back({{xi, eta, zeta, 1.0}});
}
```

- 위치: (±1/√3, ±1/√3, ±1/√3)
- 가중치: 각 1
- 장점: 정확함
- 단점: shear locking 가능

### 4.1.4 요소 적분

$$\int_{\Omega} f(x,y,z) dV = \int_{-1}^{1}\int_{-1}^{1}\int_{-1}^{1} f(\xi,\eta,\zeta) |J| d\xi d\eta d\zeta$$

$$\approx \sum_i \sum_j \sum_k w_i w_j w_k f(\xi_i, \eta_j, \zeta_k) |J(\xi_i, \eta_j, \zeta_k)|$$

---

## 4.2 형상 함수 (Shape Functions) - **실제 사용**

> **구현 위치**: `DeformationGradient::shapeFunctionsHex8()`, `DeformationGradient::shapeFunctionDerivativesHex8()`

### 4.2.1 HEX8 요소 (실제 구현)

8절점 육면체 요소의 형상함수:

$$N_i(\xi, \eta, \zeta) = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

```cpp
// DeformationGradient::shapeFunctionsHex8() 구현
for (int i = 0; i < 8; ++i) {
    double xi_i = HEX8_CORNERS[i].x;
    double eta_i = HEX8_CORNERS[i].y;
    double zeta_i = HEX8_CORNERS[i].z;
    N[i] = 0.125 * (1.0 + xi_i*xi) * (1.0 + eta_i*eta) * (1.0 + zeta_i*zeta);
}
```

LS-DYNA 노드 순서:

| 노드 i | ξᵢ | ηᵢ | ζᵢ |
|--------|-----|-----|-----|
| 0 | -1 | -1 | -1 |
| 1 | +1 | -1 | -1 |
| 2 | +1 | +1 | -1 |
| 3 | -1 | +1 | -1 |
| 4 | -1 | -1 | +1 |
| 5 | +1 | -1 | +1 |
| 6 | +1 | +1 | +1 |
| 7 | -1 | +1 | +1 |

### 4.2.2 형상함수 미분 (실제 구현)

```cpp
// DeformationGradient::shapeFunctionDerivativesHex8() 구현
dN[i].x = 0.125 * xi_i * (1.0 + eta_i*eta) * (1.0 + zeta_i*zeta);  // dN/dξ
dN[i].y = 0.125 * (1.0 + xi_i*xi) * eta_i * (1.0 + zeta_i*zeta);   // dN/dη
dN[i].z = 0.125 * (1.0 + xi_i*xi) * (1.0 + eta_i*eta) * zeta_i;    // dN/dζ
```

수학적 표현:

$$\frac{\partial N_i}{\partial \xi} = \frac{1}{8}\xi_i(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

$$\frac{\partial N_i}{\partial \eta} = \frac{1}{8}(1 + \xi_i\xi)\eta_i(1 + \zeta_i\zeta)$$

$$\frac{\partial N_i}{\partial \zeta} = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)\zeta_i$$

### 4.2.3 TET4 요소 - *구현됨, 제한적 지원*

> **참고**: TET4는 `DeformationGradient::computeTet4()`에 구현되어 있으나, 메시 매핑은 HEX8만 지원합니다.

4절점 사면체 요소:

$$N_1 = 1 - \xi - \eta - \zeta$$
$$N_2 = \xi$$
$$N_3 = \eta$$
$$N_4 = \zeta$$

좌표계: $(\xi, \eta, \zeta) \in [0,1]$, $\xi + \eta + \zeta \leq 1$

---

## 4.3 야코비안 행렬 (Jacobian Matrix)

### 4.3.1 정의

자연 좌표에서 물리 좌표로의 변환 야코비안:

$$[\mathbf{J}] = \begin{bmatrix}
\frac{\partial x}{\partial \xi} & \frac{\partial y}{\partial \xi} & \frac{\partial z}{\partial \xi} \\
\frac{\partial x}{\partial \eta} & \frac{\partial y}{\partial \eta} & \frac{\partial z}{\partial \eta} \\
\frac{\partial x}{\partial \zeta} & \frac{\partial y}{\partial \zeta} & \frac{\partial z}{\partial \zeta}
\end{bmatrix}$$

### 4.3.2 계산

$$J_{ij} = \sum_{k=1}^{n} \frac{\partial N_k}{\partial \xi_j} x_{ki}$$

여기서 $x_{ki}$는 노드 k의 좌표 성분 i

### 4.3.3 행렬식

$$|J| = det(\mathbf{J})$$

물리적 의미: 자연 좌표계 단위 체적에 대한 물리 좌표계 체적비

- $|J| > 0$: 유효한 요소
- $|J| \leq 0$: 뒤집힌 요소 (무효)

### 4.3.4 역행렬

물리 좌표에서 자연 좌표로의 미분 관계:

$$\frac{\partial}{\partial x} = [\mathbf{J}]^{-1} \frac{\partial}{\partial \xi}$$

---

# 5. 재료 모델

## 5.1 등방성 선형 탄성

### 5.1.1 입력 물성

| 물성 | 기호 | 단위 |
|------|------|------|
| 탄성 계수 | E | MPa |
| 포아송비 | ν | - |
| 밀도 | ρ | ton/mm³ |

### 5.1.2 유도 물성

**전단 계수:**
$$G = \frac{E}{2(1+\nu)}$$

**체적 탄성 계수:**
$$K = \frac{E}{3(1-2\nu)}$$

**Lamé 상수:**
$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)} = K - \frac{2G}{3}$$

### 5.1.3 물성 제한

- $E > 0$ (양의 탄성 계수)
- $-1 < \nu < 0.5$ (포아송비 범위)
  - $\nu = 0.5$: 비압축성 (수치적 문제)
  - $\nu < 0$: 음의 포아송비 (특수 재료)

## 5.2 점탄성 재료 (MAT_VISCOELASTIC)

### 5.2.1 입력 물성

| 물성 | 기호 | 의미 |
|------|------|------|
| 체적 탄성 계수 | K (BULK) | 부피 변형 저항 |
| 단시간 전단 계수 | G₀ | 즉시 전단 응답 |
| 장시간 전단 계수 | Gᵢ | 평형 전단 응답 |
| 감쇠 계수 | β | 이완 속도 |

### 5.2.2 프리스트레스 계산

장시간 거동(평형 상태)을 사용:

$$G = G_i$$

등가 탄성 계수 계산:

$$E = \frac{9KG}{3K + G}$$

$$\nu = \frac{3K - 2G}{2(3K + G)}$$

---

# 6. 참고 문헌

## 6.1 메시 매핑

1. Gordon, W.J., Hall, C.A. (1973). "Transfinite element methods: Blending-function interpolation over arbitrary curved element domains." *Numerische Mathematik*, 21(2), 109-129.

2. Coons, S.A. (1967). "Surfaces for computer-aided design of space forms." MIT Project MAC, TR-41.

3. Farin, G. (2002). *Curves and Surfaces for CAGD: A Practical Guide*, 5th Edition. Morgan Kaufmann.

## 6.2 연속체 역학

4. Malvern, L.E. (1969). *Introduction to the Mechanics of a Continuous Medium*. Prentice-Hall.

5. Holzapfel, G.A. (2000). *Nonlinear Solid Mechanics: A Continuum Approach for Engineering*. Wiley.

6. Bonet, J., Wood, R.D. (2008). *Nonlinear Continuum Mechanics for Finite Element Analysis*, 2nd Edition. Cambridge University Press.

## 6.3 유한요소법

7. Hughes, T.J.R. (2000). *The Finite Element Method: Linear Static and Dynamic Finite Element Analysis*. Dover Publications.

8. Zienkiewicz, O.C., Taylor, R.L. (2005). *The Finite Element Method*, 6th Edition. Butterworth-Heinemann.

9. Bathe, K.J. (2006). *Finite Element Procedures*. Prentice Hall.

## 6.4 LS-DYNA

10. Hallquist, J.O. (2006). *LS-DYNA Theory Manual*. Livermore Software Technology Corporation.

11. LS-DYNA Keyword User's Manual. LSTC.

---

# 부록

## A. 행렬 연산

### A.1 3×3 행렬 행렬식

$$det(\mathbf{A}) = a_{11}(a_{22}a_{33} - a_{23}a_{32}) - a_{12}(a_{21}a_{33} - a_{23}a_{31}) + a_{13}(a_{21}a_{32} - a_{22}a_{31})$$

### A.2 3×3 행렬 역행렬

$$\mathbf{A}^{-1} = \frac{1}{det(\mathbf{A})} adj(\mathbf{A})$$

여기서 $adj(\mathbf{A})$는 여인자 행렬의 전치

## B. 텐서 표기법

### B.1 인덱스 표기

Einstein 합 규약:

$$a_i b_i = \sum_{i=1}^{3} a_i b_i = a_1 b_1 + a_2 b_2 + a_3 b_3$$

### B.2 이중 축약 (Double Contraction)

$$\mathbf{A} : \mathbf{B} = A_{ij} B_{ij} = \sum_i \sum_j A_{ij} B_{ij}$$

### B.3 Kronecker Delta

$$\delta_{ij} = \begin{cases} 1 & i = j \\ 0 & i \neq j \end{cases}$$

---

**문서 끝**
