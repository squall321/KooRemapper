# Gauss quadrature

Stub mirroring `docs/KooRemapper_Theory_Document.md` §4.1.

Source code: (see See-also)

## Summary

HEX8: 2×2×2 (8 points) at ±1/√3. TET4: 1-pt or 4-pt at standard barycentric.

## See also

- [[modules/analysis#Module: src/analysis/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §4.1 — 가우스 적분 (Gauss Quadrature) - **실제 사용**._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `DeformationGradient::gaussPointsHex8()`
>
> KooRemapper는 **1점 적분(기본)** 또는 **8점 적분(옵션)** 을 지원합니다.
> `--gauss 1` 또는 `--gauss 8` 옵션으로 선택 가능.

### 4.1.1 이론

적분을 가중 합으로 근사:

$$\int_{-1}^{1} f(\xi) d\xi \approx \sum_{i=1}^{n} w_i f(\xi_i)$$

### 4.1.2 1D 가우스점

| 차수 n | 위치 ξᵢ | 가중치 wᵢ |
|--------|---------|-----------|
| 1 | 0 | 2 |
| 2 | ±1/√3 | 1 |
| 3 | 0, ±√(3/5) | 8/9, 5/9 |

### 4.1.3 3D HEX8 요소 (실제 구현)

**1-점 적분 (Reduced Integration) - 기본값:**

```cpp
// numPoints == 1
points.push_back({{0.0, 0.0, 0.0, 8.0}});  // {xi, eta, zeta, weight}
```

- 위치: (0, 0, 0)
- 가중치: 8
- 장점: 빠름, shear locking 방지
- 단점: hourglass 모드 가능

**2×2×2 = 8-점 적분 (Full Integration) - 옵션:**

```cpp
// numPoints == 8
const double g = 1.0 / std::sqrt(3.0);  // ≈ 0.577
for (i,j,k in {0,1}³) {
    xi   = (i == 0) ? -g : g;
    eta  = (j == 0) ? -g : g;
    zeta = (k == 0) ? -g : g;
    points.push_back({{xi, eta, zeta, 1.0}});
}
```

- 위치: (±1/√3, ±1/√3, ±1/√3)
- 가중치: 각 1
- 장점: 정확함
- 단점: shear locking 가능

### 4.1.4 요소 적분

$$\int_{\Omega} f(x,y,z) dV = \int_{-1}^{1}\int_{-1}^{1}\int_{-1}^{1} f(\xi,\eta,\zeta) |J| d\xi d\eta d\zeta$$

$$\approx \sum_i \sum_j \sum_k w_i w_j w_k f(\xi_i, \eta_j, \zeta_k) |J(\xi_i, \eta_j, \zeta_k)|$$

---

<!-- END EXCERPT -->
