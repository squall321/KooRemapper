# Isotropic elastic material

Stub mirroring `docs/KooRemapper_Theory_Document.md` §5.1.

Source code: (see See-also)

## Summary

λ = Eν / ((1+ν)(1-2ν)), μ = E / (2(1+ν)). Constraint: -1 < ν < 0.5. Factory `MaterialModel::isotropicElastic(E, ν)`.

## See also

- [MaterialModel.cpp](../../src/analysis/MaterialModel.cpp)
- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §5.1 — 등방성 선형 탄성._

<!-- BEGIN EXCERPT -->



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

<!-- END EXCERPT -->
