# Strain tensor

Stub mirroring `docs/KooRemapper_Theory_Document.md` §3.2.

Source code: (see See-also)

## Summary

Engineering ε = (F+Fᵀ)/2 − I (default) and Green-Lagrange E = (FᵀF − I)/2 (option). Voigt, principal, von Mises, volumetric, and triaxiality forms all in [StrainTensor.cpp](../../src/analysis/StrainTensor.cpp).

## See also

- [[theory/stress-tensor#Stress tensor]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §3.2 — 변형률 텐서 (Strain Tensor) - **실제 사용**._

<!-- BEGIN EXCERPT -->



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

<!-- END EXCERPT -->
