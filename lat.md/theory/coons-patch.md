# Coons patch

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.5.

Source code: (see See-also)

## Summary

Bilinear blend of four boundary curves. Used by [FaceInterpolator.cpp](../../src/mapper/FaceInterpolator.cpp).

## See also

- [[modules/mapper#Module: src/mapper/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.5 — Coons 패치 (Coons Patch) - *면 보간에 사용*._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `FaceInterpolator::buildBilinear()` - 면 보간에 부분적 사용

### 2.5.1 이론적 배경

Coons (1967)가 제안한 곡면 보간법으로, 4개의 경계 곡선으로 정의된 곡면을 생성합니다.

### 2.5.2 수학적 정의

4개 경계 곡선:
- $C_0(t)$: s=0 경계 (아래)
- $C_1(t)$: s=1 경계 (위)
- $D_0(s)$: t=0 경계 (왼쪽)
- $D_1(s)$: t=1 경계 (오른쪽)

**Coons 패치 공식:**

$$P(s,t) = L_c(s,t) + L_d(s,t) - B(s,t)$$

여기서:

$$L_c(s,t) = (1-s) \cdot D_0(t) + s \cdot D_1(t)$$

$$L_d(s,t) = (1-t) \cdot C_0(s) + t \cdot C_1(s)$$

$$B(s,t) = (1-s)(1-t) \cdot P_{00} + s(1-t) \cdot P_{10} + (1-s)t \cdot P_{01} + st \cdot P_{11}$$

### 2.5.3 특성

- 4개 경계 곡선을 정확히 통과
- 4개 코너 점을 정확히 통과
- 내부는 부드럽게 보간됨

---

<!-- END EXCERPT -->
