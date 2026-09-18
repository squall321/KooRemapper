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
base_model: flat.k
output: indented
material:
  E: 210000
  nu: 0.3
operations:
  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 2.0              # 양수=압입, 음수=엠보싱 (0 불가)
    r1: 1.5                 # 바닥 쪽 전이 호 반경 (> 0)
    r2: 1.0                 # 표면 쪽 전이 호 반경 (> 0)
    bottom_ratio: 0.5       # 반대 면 변위 비율 (0 = 반대 면 고정, 기본 0)
    stress: true            # 굽힘 응력 계산 여부
    shell_thickness: 1.0    # 셸 응력 두께 (0 = *SECTION_SHELL)
    shape:
      type: polygon         # polygon | spline (3점 이상)
      points:               # 평평한 바닥 윤곽 — 평면 좌표계의 모델 좌표
        - [0.0, 0.0]
        - [10.0, 0.0]
        - [10.0, 8.0]
        - [0.0, 8.0]
```

> **v1.8.0 정정**: config 는 최상위 `base_model`/`output` + `operations[].type: indent` 구조입니다. `shape.type` 은 `polygon | spline` 이고 `points` 는 3점 이상이어야 합니다(`circle` 은 없음 — 이전 help 표기가 틀렸음). `depth ≠ 0`, `r1·r2 > 0`, `direction` 은 `+x|-x|+y|-y|+z|-z` 를 검사하며 단독 `indent` 도 같습니다(예전엔 points·r1/r2 누락 시 비정상 종료).

### 파라미터


**표 14-1. indent 파라미터 — 깊이, 전이 호 반경 r1·r2, 반대 면 변위 비율, 응력·셸 두께.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `depth` | 압입 깊이 (양수=압입, 음수=엠보싱) | — |
| `r1` | 바닥 쪽 전이 호 반경 (윤곽 바깥 0~r1) | — |
| `r2` | 표면 쪽 전이 호 반경 (윤곽 바깥 r1~r1+r2) | — |
| `bottom_ratio` | 반대 면 변위 비율 (눌리는 면 1 → 반대 면 bottom_ratio 로 선형) | `0.0` |
| `stress` | 굽힘 응력 계산 여부 | `false` |
| `shell_thickness` | 셸 응력 두께 | `0` (= `*SECTION_SHELL`) |

### 압입 프로파일

윤곽(shape)으로부터의 부호 있는 거리 d(안쪽 < 0)에서 표면 변위 h(d):

$$k = \frac{\text{depth}}{r_1 + r_2}$$

- **윤곽 안** (d < 0): $h = -\text{depth}$ (평평한 바닥)
- **r₁ 구역** (0 ≤ d < r₁, 바닥 쪽 호): $h(d) = -\text{depth} + k\, r_1 \left(1 - \sqrt{1 - (d/r_1)^2}\right)$
- **r₂ 구역** (r₁ ≤ d < r₁+r₂, 표면 쪽 호): $h(d) = -k\, r_2 \left(1 - \sqrt{1 - \left((r_1 + r_2 - d)/r_2\right)^2}\right)$
- **바깥** (d ≥ r₁+r₂): $h = 0$

두께 방향으로는 눌리는 면에서 h, 반대 면에서 `bottom_ratio`·h 로 선형 보간합니다.

> **주의**: 응력은 노드 변위 **전에** 계산. h''(d) 특이점은 변형률 0.05 기준 `0.05 / (thickness/2)` 로 상한 제한.

---

<!-- END MANUAL EXCERPT -->
