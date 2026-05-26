# Isoparametric mapping

Stub mirroring `docs/KooRemapper_Theory_Document.md` §40.1.

Source code: (see See-also)

## Summary

Inverse-map a target point's physical coordinates back into the (ξ,η,ζ) natural space of the host element via Newton iteration, then sample the field via shape functions.

## See also

- [[commands/map#map — HEX8 structured mesh mapping (§4)]]
- [[theory/shape-functions#Shape functions]]

## Theory text

_From [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §40.1 — 등매개변수 매핑 (map)._

<!-- BEGIN EXCERPT -->



HEX8 요소의 자연 좌표계 (ξ, η, ζ) ∈ [-1, 1]³:

$$\mathbf{x}(\xi,\eta,\zeta) = \sum_{i=1}^{8} N_i(\xi,\eta,\zeta)\,\mathbf{x}_i$$

역매핑 (Newton-Raphson):

$$\begin{pmatrix} \Delta\xi \\ \Delta\eta \\ \Delta\zeta \end{pmatrix} = \mathbf{J}^{-1} (\mathbf{x}_{target} - \mathbf{x}(\xi,\eta,\zeta))$$

야코비안 행렬:

$$J_{ij} = \frac{\partial x_i}{\partial \xi_j} = \sum_{k=1}^{8} \frac{\partial N_k}{\partial \xi_j} x_{ki}$$

<!-- END EXCERPT -->
