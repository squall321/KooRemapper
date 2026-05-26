# Kirchhoff plate theory

Stub mirroring `docs/KooRemapper_Theory_Document.md` §40.3.

Source code: (see See-also)

## Summary

Thin plate: normals remain normal. Bending strain ε = -z·κ where z is distance from neutral surface and κ is curvature from the deflection field.

**Order of operations**: compute stress BEFORE displacing nodes, otherwise the centroid z shifts and the distance from the neutral surface becomes inconsistent.

## See also

- [[commands/bend#bend — Kirchhoff plate bending (§13)]]
- [[commands/indent#indent — indent/emboss (§14)]]

## Theory text

_From [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §40.3 — Kirchhoff 판 이론 (bend/indent)._

<!-- BEGIN EXCERPT -->



중립면에서 거리 z인 지점의 변형률:

$$\varepsilon_{11}(z) = -z \kappa_{11}, \quad \varepsilon_{22}(z) = -z \kappa_{22}, \quad 2\varepsilon_{12}(z) = -2z \kappa_{12}$$

모멘트-곡률 관계 (굽힘 강성 D):

$$D = \frac{E t^3}{12(1-\nu^2)}$$

$$M_{11} = D(\kappa_{11} + \nu \kappa_{22}), \quad M_{22} = D(\kappa_{22} + \nu \kappa_{11}), \quad M_{12} = D(1-\nu)\kappa_{12}$$

<!-- END EXCERPT -->
