# Arc-length parameterization

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.2.

Source code: (see See-also)

## Summary

Normalize node positions to u ∈ [0,1] along the arc axis. The actual mapping algorithm in production. See [ParametricMapper.cpp](../../src/mapper/ParametricMapper.cpp).

## See also

- [[theory/edge-interpolation#Edge-based interpolation]]
- [[modules/mapper#Module: src/mapper/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.2 — 호장 길이 기반 매개변수화 (Arc-length Parameterization) - **실제 사용**._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `EdgeInterpolator::build()`, `EdgeInterpolator::interpolate()`

### 2.2.1 이론

곡선을 따라 균일한 매개변수 분포를 보장하기 위해 호장 길이를 사용합니다. 이 방법은 평면 메시의 X 좌표가 곡면 메시의 곡선 길이에 정확히 대응되도록 합니다.

### 2.2.2 알고리즘 (실제 구현)

**Step 1: 누적 호장 계산** (`EdgeInterpolator::build()`)

```cpp
arcLengths_.push_back(0.0);  // s₀ = 0
for (size_t i = 1; i < points_.size(); ++i) {
    double segmentLength = points_[i].distanceTo(points_[i - 1]);
    totalLength_ += segmentLength;
    arcLengths_.push_back(totalLength_);  // sᵢ = sᵢ₋₁ + |Pᵢ - Pᵢ₋₁|
}
```

수학적 표현:
$$s_0 = 0, \quad s_i = s_{i-1} + \|P_i - P_{i-1}\|, \quad L_{total} = s_n$$

**Step 2: 매개변수 t에 대한 위치 계산** (`EdgeInterpolator::interpolate()`)

```cpp
double targetLength = t * totalLength_;  // 목표 호장

// 해당 선분 검색
for (size_t i = 0; i + 1 < arcLengths_.size(); ++i) {
    if (targetLength >= arcLengths_[i] && targetLength <= arcLengths_[i + 1]) {
        idx = i;
        break;
    }
}

// 국소 매개변수 계산
double segmentLength = arcLengths_[idx + 1] - arcLengths_[idx];
double localT = (targetLength - arcLengths_[idx]) / segmentLength;

// 선형 보간
return Vector3D::lerp(points_[idx], points_[idx + 1], localT);
```

수학적 표현:

목표 호장: $s_{target} = t \cdot L_{total}$

선분 검색: $s_i \leq s_{target} < s_{i+1}$인 i 찾기

국소 매개변수:
$$t_{local} = \frac{s_{target} - s_i}{s_{i+1} - s_i}$$

보간 결과:
$$P(t) = (1 - t_{local}) \cdot P_i + t_{local} \cdot P_{i+1}$$

### 2.2.3 장점

- 곡선 길이에 비례한 균일한 점 분포
- 물리적 대응성 보장 (평면 X좌표 ↔ 곡면 호장 길이)
- 곡률 변화에 자연스럽게 적응
- U-fold 등 복잡한 형상에서도 일관된 매핑

---

<!-- END EXCERPT -->
