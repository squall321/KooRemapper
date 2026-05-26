# Trilinear interpolation

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.4.

Source code: (see See-also)

## Summary

Implemented but currently unused; kept for reference.

## See also

- [[modules/mapper#Module: src/mapper/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.4 — 삼선형 보간 (Trilinear Interpolation) - *구현됨, 미사용*._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `ParametricMapper::trilinearInterpolate()` - 코드에 존재하나 현재 비활성화

8개 코너 노드만 사용하는 가장 단순한 형태:

$$P(u,v,w) = \sum_{i=0}^{7} N_i(u,v,w) \cdot C_i$$

형상함수:
$$N_i(u,v,w) = \frac{1}{8}(1 \pm u)(1 \pm v)(1 \pm w)$$

| 노드 | u | v | w |
|------|---|---|---|
| 0 | - | - | - |
| 1 | + | - | - |
| 2 | + | + | - |
| 3 | - | + | - |
| 4 | - | - | + |
| 5 | + | - | + |
| 6 | + | + | + |
| 7 | - | + | + |

### 2.4.1 미사용 이유

코너만 사용하므로 모서리 곡선 형상이 무시됩니다. 곡률이 큰 메시에서 정확도가 떨어집니다.

---

<!-- END EXCERPT -->
