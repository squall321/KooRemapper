# Edge-based interpolation

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.1.

Source code: (see See-also)

## Summary

Per-edge piecewise-linear field reconstruction along arc length.

## See also

- [EdgeInterpolator.cpp](../../src/mapper/EdgeInterpolator.cpp)

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.1 — 호장 길이 기반 Edge-Based 보간 - **실제 사용**._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `ParametricMapper::edgeBasedInterpolate()`, `EdgeInterpolator::interpolate()`

### 2.1.1 개요

KooRemapper는 구조화 Hex 메시의 매핑을 위해 Edge-Based 보간법을 사용합니다. 이 방법은:
- 12개 모서리의 실제 곡선 형상을 보존
- 호장 길이 기반 매개변수화로 물리적 대응성 보장
- bent → unfold → remap 왕복 시 원래 위치로 정확히 복귀

### 2.1.2 알고리즘

**Step 1: i-축 4개 모서리에서 호장 길이 기반 점 선택**

```cpp
// ParametricMapper::edgeBasedInterpolate() 구현
Vector3D p00 = edges_[0].interpolate(u);  // j=0, k=0 모서리
Vector3D p10 = edges_[1].interpolate(u);  // j=N, k=0 모서리
Vector3D p01 = edges_[2].interpolate(u);  // j=0, k=P 모서리
Vector3D p11 = edges_[3].interpolate(u);  // j=N, k=P 모서리
```

여기서 `edges_[i].interpolate(u)`는 호장 길이 기반 보간을 수행합니다 (2.2절 참조).

**Step 2: (v, w) 평면에서 쌍선형 보간**

```cpp
Vector3D bottom = p00 * (1-v) + p10 * v;  // k=0 선
Vector3D top    = p01 * (1-v) + p11 * v;  // k=P 선
Vector3D result = bottom * (1-w) + top * w;
```

수학적 표현:

$$P(u,v,w) = (1-w) \cdot [(1-v) \cdot p_{00}(u) + v \cdot p_{10}(u)] + w \cdot [(1-v) \cdot p_{01}(u) + v \cdot p_{11}(u)]$$

### 2.1.3 장점

- 구조화 그리드의 격자점에서 정확한 결과
- 모서리 곡선 형상 보존
- 계산 효율성 (단순 쌍선형 보간)

---

<!-- END EXCERPT -->
