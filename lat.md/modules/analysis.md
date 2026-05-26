# Module: src/analysis/

Continuum-mechanics primitives. See [[theory/index#Theory Index]] for theory.

| File | Role |
|------|------|
| [DeformationGradient.cpp](../../src/analysis/DeformationGradient.cpp) | `F = ∂x/∂X` from displacement gradients via HEX8 shape functions |
| [StrainCalculator.cpp](../../src/analysis/StrainCalculator.cpp) | engineering & Green-Lagrange strain |
| [StrainTensor.cpp](../../src/analysis/StrainTensor.cpp) | 3×3 tensor algebra (principal, von Mises) |
| [StressTensor.cpp](../../src/analysis/StressTensor.cpp) | Cauchy stress; `fromStrain()` Hooke law |
| [MaterialModel.cpp](../../src/analysis/MaterialModel.cpp) | isotropic elastic via Lamé λ, μ (factory `MaterialModel::isotropicElastic(E, nu)` — constructor is private) |
| [ElementAnalyzer.cpp](../../src/analysis/ElementAnalyzer.cpp) | per-element strain/stress orchestration |

## Verification reference

For `E=210000, ν=0.3, ε=0.02`:
- Lamé: `λ=121154, μ=80769`
- Result: `σ_xx=5654, σ_yy=σ_zz=2423`.

See [[theory/stress-tensor#Stress tensor]].

## Cross-references

- Used by [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] (main consumer).
- Material model also touched by [[commands/matdb#matdb — material DB lookup + replacement (§24)]].
- See [[theory/deformation-gradient#Deformation gradient F]], [[theory/strain-tensor#Strain tensor]], [[theory/stress-tensor#Stress tensor]].
