# Shape functions

Stub mirroring `docs/KooRemapper_Theory_Document.md` §4.2.

Source code: (see See-also)

## Summary

HEX8 trilinear N_i(ξ,η,ζ) = (1±ξ)(1±η)(1±ζ)/8. Derivatives evaluated at integration points feed F.

## See also

- [DeformationGradient.cpp](../../src/analysis/DeformationGradient.cpp)

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §4.2 — 형상 함수 (Shape Functions) - **실제 사용**._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `DeformationGradient::shapeFunctionsHex8()`, `DeformationGradient::shapeFunctionDerivativesHex8()`

### 4.2.1 HEX8 요소 (실제 구현)

8절점 육면체 요소의 형상함수:

$$N_i(\xi, \eta, \zeta) = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

```cpp
// DeformationGradient::shapeFunctionsHex8() 구현
for (int i = 0; i < 8; ++i) {
    double xi_i = HEX8_CORNERS[i].x;
    double eta_i = HEX8_CORNERS[i].y;
    double zeta_i = HEX8_CORNERS[i].z;
    N[i] = 0.125 * (1.0 + xi_i*xi) * (1.0 + eta_i*eta) * (1.0 + zeta_i*zeta);
}
```

LS-DYNA 노드 순서:

| 노드 i | ξᵢ | ηᵢ | ζᵢ |
|--------|-----|-----|-----|
| 0 | -1 | -1 | -1 |
| 1 | +1 | -1 | -1 |
| 2 | +1 | +1 | -1 |
| 3 | -1 | +1 | -1 |
| 4 | -1 | -1 | +1 |
| 5 | +1 | -1 | +1 |
| 6 | +1 | +1 | +1 |
| 7 | -1 | +1 | +1 |

### 4.2.2 형상함수 미분 (실제 구현)

```cpp
// DeformationGradient::shapeFunctionDerivativesHex8() 구현
dN[i].x = 0.125 * xi_i * (1.0 + eta_i*eta) * (1.0 + zeta_i*zeta);  // dN/dξ
dN[i].y = 0.125 * (1.0 + xi_i*xi) * eta_i * (1.0 + zeta_i*zeta);   // dN/dη
dN[i].z = 0.125 * (1.0 + xi_i*xi) * (1.0 + eta_i*eta) * zeta_i;    // dN/dζ
```

수학적 표현:

$$\frac{\partial N_i}{\partial \xi} = \frac{1}{8}\xi_i(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

$$\frac{\partial N_i}{\partial \eta} = \frac{1}{8}(1 + \xi_i\xi)\eta_i(1 + \zeta_i\zeta)$$

$$\frac{\partial N_i}{\partial \zeta} = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)\zeta_i$$

### 4.2.3 TET4 요소 - *구현됨, 제한적 지원*

> **참고**: TET4는 `DeformationGradient::computeTet4()`에 구현되어 있으나, 메시 매핑은 HEX8만 지원합니다.

4절점 사면체 요소:

$$N_1 = 1 - \xi - \eta - \zeta$$
$$N_2 = \xi$$
$$N_3 = \eta$$
$$N_4 = \zeta$$

좌표계: $(\xi, \eta, \zeta) \in [0,1]$, $\xi + \eta + \zeta \leq 1$

---

<!-- END EXCERPT -->
