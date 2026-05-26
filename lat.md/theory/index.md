# Theory Index

Mirrors [`docs/KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md).
Each anchor below links to a stub node; click through to follow into source.

## 1. Coordinate systems
- [[theory/coordinate-systems#Coordinate systems]] — reference vs deformed; arc/width/thickness convention.

## 2. Mesh mapping
- [[theory/arc-length-param#Arc-length parameterization]] — **actual algorithm** (§2.1, §2.2 in manual). Used in
  [ParametricMapper.cpp](../../src/mapper/ParametricMapper.cpp).
- [[theory/edge-interpolation#Edge-based interpolation]] — edge-based variant (§2.1) — [EdgeInterpolator.cpp](../../src/mapper/EdgeInterpolator.cpp).
- [[theory/coons-patch#Coons patch]] — face interpolation (§2.5) — [FaceInterpolator.cpp](../../src/mapper/FaceInterpolator.cpp).
- [[theory/structured-grid#Structured grid BFS indexing]] — BFS indexing (§2.6) — [[modules/grid#Module: src/grid/]].
- [[theory/transfinite#Transfinite interpolation (Gordon-Hall)]] / [[theory/trilinear#Trilinear interpolation]] — **implemented but unused**
  (§2.3, §2.4) — kept for reference.

## 3. Deformation analysis
- [[theory/deformation-gradient#Deformation gradient F]] — `F = ∂x/∂X` (§3.1) — [DeformationGradient.cpp](../../src/analysis/DeformationGradient.cpp).
- [[theory/strain-tensor#Strain tensor]] — engineering, Green-Lagrange, Voigt, principal, von Mises (§3.2).
- [[theory/stress-tensor#Stress tensor]] — Hooke, principal, von Mises, triaxiality, Tresca (§3.3).

## 4. Numerical methods
- [[theory/gauss-quadrature#Gauss quadrature]] — HEX8 (2×2×2), TET4 (1-pt / 4-pt) (§4.1).
- [[theory/shape-functions#Shape functions]] — HEX8 tri-linear + derivatives, TET4 (§4.2).
- [[theory/jacobian#Jacobian matrix]] — det/inv (§4.3).

## 5. Material models
- [[theory/isotropic-elastic#Isotropic elastic material]] — Lamé λ, μ; Hooke (§5.1).
- [[theory/viscoelastic#Viscoelastic (MATVISCOELASTIC)]] — MAT_VISCOELASTIC prestress relaxation (§5.2).

## 6. Operation-specific theory
- [[theory/kirchhoff-plate#Kirchhoff plate theory]] — bend/indent bending strain (§40.3).
- [[theory/indent-profile#Indent profile h(d), h''(d)]] — quarter-arc fillet `h(d), h''(d)`.
- [[theory/formstrain-theory#Formstrain (dihedral curvature)]] — dihedral curvature → plastic EPS (§40.4).
- [[theory/isoparametric-map#Isoparametric mapping]] — map command theory (§40.1).

## 7. Cross-references
- See [[../lsdyna/keywords#LS-DYNA Keyword Cross-Reference]] for keyword-level grounding.
- Linear elastic verification reference values: see [[modules/analysis#Module: src/analysis/]].

> Pages below are stubs; populate from `KooRemapper_Theory_Document.md` as each
> theory node becomes load-bearing for a specific change.
