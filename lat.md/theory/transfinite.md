# Transfinite interpolation (Gordon-Hall)

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.3.

Source code: (see See-also)

## Summary

Implemented but currently unused; kept for reference.

## See also

- [[modules/mapper#Module: src/mapper/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.3 — 트랜스파이닛 보간법 (Transfinite Interpolation) - *구현됨, 미사용*._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `ParametricMapper::transfiniteInterpolate()` - 코드에 존재하나 현재 비활성화

### 2.3.1 이론적 배경

Gordon & Hall (1973)이 개발한 방법으로, 경계 조건을 정확히 만족하면서 내부 영역을 보간합니다.

### 2.3.2 3차원 Gordon-Hall 공식

$$P(u,v,w) = P_{faces} - P_{edges} + P_{corners}$$

**면 기여항:**
$$P_{faces} = (1-u)F_0(v,w) + uF_1(v,w) + (1-v)F_2(u,w) + vF_3(u,w) + (1-w)F_4(u,v) + wF_5(u,v)$$

**모서리 기여항 (빼기):**
$$P_{edges} = \sum_{i=0}^{11} w_i(u,v,w) \cdot E_i(t)$$

**코너 기여항 (더하기):**
$$P_{corners} = \sum_{i=0}^{7} w_i(u,v,w) \cdot C_i$$

### 2.3.3 미사용 이유

Edge-Based 보간이 구조화 Hex 메시에서 더 단순하고 정확한 결과를 제공하므로 현재 비활성화되어 있습니다.

---

<!-- END EXCERPT -->
