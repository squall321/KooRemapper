# Jacobian matrix

Stub mirroring `docs/KooRemapper_Theory_Document.md` §4.3.

Source code: (see See-also)

## Summary

J = ∂x/∂ξ. det(J) drives the integration weight; inv(J) maps natural derivatives to physical derivatives.

## See also

- [[modules/analysis#Module: src/analysis/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §4.3 — 야코비안 행렬 (Jacobian Matrix)._

<!-- BEGIN EXCERPT -->



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

<!-- END EXCERPT -->
