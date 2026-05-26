# Coordinate systems

Stub mirroring `docs/KooRemapper_Theory_Document.md` §1.2.

Source code: (see See-also)

## Summary

Reference (X) vs deformed (x) configuration; arc/width/thickness axis convention for closed-loop meshes.

## See also

- [[project_unfold_axis_perm]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §1.2 — 좌표계 정의._

<!-- BEGIN EXCERPT -->



프로그램은 다음 좌표계를 사용합니다:

- **물리 좌표계 (Physical Coordinates)**: (x, y, z) - 실제 공간 좌표
- **매개변수 좌표계 (Parametric Coordinates)**: (u, v, w) ∈ [0,1]³ - 정규화된 좌표
- **자연 좌표계 (Natural Coordinates)**: (ξ, η, ζ) ∈ [-1,1]³ - 요소 내부 좌표

---

# 2. 메시 매핑 알고리즘

> **KooRemapper 실제 구현 요약**
>
> 본 프로그램은 **호장 길이 기반 Edge-Based 보간법**을 사용합니다:
> 1. 12개 모서리에서 **호장 길이(Arc-length) 매개변수화** 적용 (`EdgeInterpolator`)
> 2. i-축 4개 모서리에서 점을 선택 후 **(v, w) 평면에서 쌍선형 보간** (`ParametricMapper::edgeBasedInterpolate`)
>
> Gordon-Hall 트랜스파이닛 보간과 삼선형 보간은 코드에 구현되어 있으나 현재 비활성화 상태입니다.

---

<!-- END EXCERPT -->
