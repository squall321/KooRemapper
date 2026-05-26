# Stress tensor

Stub mirroring `docs/KooRemapper_Theory_Document.md` §3.3.

Source code: (see See-also)

## Summary

Hooke law σ = λ·tr(ε)·I + 2μ·ε. Lamé parameters from E, ν. Verification: E=210000, ν=0.3, ε=0.02 → σ_xx=5654, σ_yy=σ_zz=2423.

## See also

- [StressTensor.cpp](../../src/analysis/StressTensor.cpp)
- [[theory/isotropic-elastic#Isotropic elastic material]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §3.3 — 응력 텐서 (Stress Tensor) - **실제 사용**._

<!-- BEGIN EXCERPT -->



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

<!-- END EXCERPT -->
