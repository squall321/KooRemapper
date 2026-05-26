# Formstrain (dihedral curvature)

Stub mirroring `docs/KooRemapper_Theory_Document.md` §40.4.

Source code: (see See-also)

## Summary

Edge dihedral angle θ → bending strain ε_b = (t/2)·κ where κ = θ/L (L = centroid distance between adjacent shells). Plastic EPS = max(0, ε_b - ε_y). Merges across ops via max().

## See also

- [ShellCurvature.cpp](../../src/assembly/ShellCurvature.cpp)
- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]

## Theory text

_From [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §40.4 — 형성 변형률 이론 (formstrain)._

<!-- BEGIN EXCERPT -->



이면각 θ, 인접 셸 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

면외 굽힘 변형률 (두께 방향 선형 분포):

$$\varepsilon_{top} = +\frac{t}{2}\kappa, \quad \varepsilon_{bot} = -\frac{t}{2}\kappa$$

등가 소성 변형률 (Von Mises 기준, 단축 가정):

$$\overline{\varepsilon}^p = \frac{2}{\sqrt{3}} |\varepsilon_{max}|$$

---

<!-- END EXCERPT -->
