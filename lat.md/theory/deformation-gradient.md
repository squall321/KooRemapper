# Deformation gradient F

Stub mirroring `docs/KooRemapper_Theory_Document.md` §3.1.

Source code: (see See-also)

## Summary

F = ∂x/∂X. Computed via HEX8 shape function derivatives at the element centroid (single-point integration).

## See also

- [DeformationGradient.cpp](../../src/analysis/DeformationGradient.cpp)
- [[theory/shape-functions#Shape functions]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §3.1 — 변형 구배 텐서 (Deformation Gradient) - **실제 사용**._

<!-- BEGIN EXCERPT -->



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

<!-- END EXCERPT -->
