# indent — indent/emboss (§14)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp), [IndentProfile.cpp](../../src/assembly/IndentProfile.cpp)
Manual: [`KooRemapper_Manual.md`#14-indent--압입엠보싱](../../docs/KooRemapper_Manual.md#14-indent--압입엠보싱)
Theory: [[theory/indent-profile#Indent profile h(d), h''(d)]]

## Synopsis

```
KooRemapper indent <args>
```

## What it does

Quarter-arc fillet indent (depth < 0 for emboss). Profile `h(d), h''(d)` driven by r1/r2 radii; curvature decomposed by gradient direction: κ_x = -h''·gx², κ_y = -h''·gy², κ_xy = -h''·gx·gy. Singularity at d=r1 capped at strainLimit/(thickness/2).

## Key references

- [[theory/indent-profile#Indent profile h(d), h''(d)]]
- [[theory/kirchhoff-plate#Kirchhoff plate theory]]
- [ClosedLoop.cpp](../../src/assembly/ClosedLoop.cpp) (signed distance + gradient)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §14. indent — 압입/엠보싱._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
폐곡선 경계(다각형 또는 스플라인) 안쪽 영역에 **quarter-arc 필렛 프로파일**로
압입(depth > 0) 또는 엠보싱(depth < 0)을 적용합니다.

### 사용법

```bash
KooRemapper.exe indent <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: indented
target_pid: 1
plane: xy
direction: -z
depth: 2.0              # 양수=압입, 음수=엠보싱
r1: 1.5                 # 펀치 측 필렛 반경
r2: 1.0                 # 다이 측 필렛 반경
bottom_ratio: 0.5       # 두께 방향 관통 비율 (0~1)
stress: true            # 굽힘 응력 계산 여부
shell_thickness: 1.0    # 셸 두께 (셸 요소일 때)

shape:
  type: polygon         # polygon | spline
  points:
    - [0.0, 0.0]
    - [10.0, 0.0]
    - [10.0, 8.0]
    - [0.0, 8.0]

material:
  E: 210000
  nu: 0.3
```

### 파라미터


**표 16-1. convert 지원 변환 유형 — TET4→TET10, HEX8→HEX20, QUAD4→QUAD8, TRIA3→TRIA6 변환 지원.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `depth` | 압입 깊이 (양수=압입, 음수=엠보싱) | — |
| `r1` | 펀치 측(내부) 필렛 반경 | — |
| `r2` | 다이 측(외부) 필렛 반경 | — |
| `bottom_ratio` | 두께 방향 관통 비율 | `0.5` |
| `stress` | 굽힘 응력 계산 여부 | `false` |
| `shell_thickness` | 셸 요소 두께 | 자동 |

### 압입 프로파일

부호 있는 거리 d에서의 프로파일 함수 h(d):

$$k = \frac{\text{depth}}{r_1 + r_2}$$

**r₁ 구역** (0 ≤ d ≤ r₁): $h(d) = -\text{depth} + k \cdot r_1 (1 - \sqrt{1 - (d/r_1)^2})$

**평탄 구역** (r₁ < d ≤ D - r₂): $h(d) = -\text{depth}$

**r₂ 구역** (D - r₂ < d ≤ D): 역 quarter-arc 천이

> **주의**: 응력은 노드 변위 **전에** 계산. h''(d) 특이점 → `strainLimit / (thickness/2)` 상한 제한.

---

<!-- END MANUAL EXCERPT -->
