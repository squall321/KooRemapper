# bend — Kirchhoff plate bending (§13)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp), [DeflectionGrid.cpp](../../src/assembly/DeflectionGrid.cpp)
Manual: [`KooRemapper_Manual.md`#13-bend--굽힘-변형--초기-응력](../../docs/KooRemapper_Manual.md#13-bend--굽힘-변형--초기-응력)
Theory: [[theory/kirchhoff-plate#Kirchhoff plate theory]]

## Synopsis

```
KooRemapper bend <args>
```

## What it does

Applies a deflection field (formula, dat file, or dat pair) and computes bending strain/stress under Kirchhoff plate theory. Stress computed BEFORE node movement (centroid invariance).

## Key references

- [[theory/kirchhoff-plate#Kirchhoff plate theory]]
- [FormulaEvaluator.cpp](../../src/assembly/FormulaEvaluator.cpp)
- [[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §13. bend — 굽힘 변형 + 초기 응력._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
처짐 함수 w(x₁, x₂)로 기술되는 굽힘을 파트에 적용합니다.
변형(deform) 또는 응력(stress) 모드 선택 가능.

### 사용법

```bash
KooRemapper.exe bend <config.yaml>
```

### YAML 형식

```yaml
base_model: flat.k
output: bent
material:                   # 선택 — 생략하면 대상 파트의 *MAT_ELASTIC
  E: 210000
  nu: 0.3
operations:
  - type: bend
    target_pid: 1           # 0 또는 생략 = 모든 파트
    plane: xy               # xy | yz | zx  (x1,x2 = X,Y | Y,Z | Z,X)
    mode: deform            # deform(노드 이동 + 역응력) | stress(노드 그대로, 정응력)
    source: formula         # formula | dat | dat_pair
    expression: "0.5 * sin(pi * x1 / L1) * sin(pi * x2 / L2)"   # 처짐 w(x1,x2)

    # source: dat      → dat_file: deflection.dat
    # source: dat_pair → dat_top: top.dat  +  dat_bottom: bottom.dat (상·하면 처짐 격자)
```

> **v1.8.0 정정**: (1) 굽힘 평면 값은 `xy | yz | zx` 입니다. `xz` 는 거부됩니다(이전 help 와 이 문서의 `xz` 표기가 틀렸음). (2) config 는 최상위 `base_model`/`output` + `operations[].type: bend` 구조입니다. (3) `mode` 는 `deform | stress`, `source` 는 `formula | dat | dat_pair` 이고 모두 필수 검사 대상입니다(이전 help 의 `mode: formula` 는 거부). 단독 `bend` 명령도 assemble 과 같은 검사를 거칩니다(예전엔 검사 없이 source 누락 시 비정상 종료).

### 수식 변수


**표 13-1. bend 수식 변수 — 면내 좌표 x1·x2, 바운딩 박스 길이 L1·L2, π.**

| 변수 | 의미 |
|------|------|
| `x1` | 면내 좌표 1 (바운딩 박스 최소값 기준 상대값) |
| `x2` | 면내 좌표 2 |
| `L1` | x1 방향 바운딩 박스 길이 |
| `L2` | x2 방향 바운딩 박스 길이 |
| `pi` | 원주율 π |

지원 함수: `sin`, `cos`, `tan`, `sqrt`, `exp`, `log`, `abs`, `pow`

### 굽힘 이론

처짐 함수 w(x₁, x₂)로부터 **곡률**:

$$\kappa_1 = -\frac{\partial^2 w}{\partial x_1^2}, \quad \kappa_2 = -\frac{\partial^2 w}{\partial x_2^2}, \quad \kappa_{12} = -\frac{\partial^2 w}{\partial x_1 \partial x_2}$$

중립면에서 거리 d인 지점의 굽힘 변형률:

$$\varepsilon_{11} = d \cdot \kappa_1, \quad \varepsilon_{22} = d \cdot \kappa_2, \quad \varepsilon_{12} = d \cdot \kappa_{12}$$

> **주의**: 응력은 노드 변위 적용 **전에** 계산 (중립면 위치 보존).

### dat 파일 형식

```
# 행: x2_max → x2_min (위→아래), 열: x1_min → x1_max
0.0  0.1  0.3  0.5  0.6
0.1  0.2  0.4  0.6  0.7
...
```

값은 모델 길이 단위의 처짐이며, 격자는 대상 파트의 평면 바운딩 박스에 펼칩니다. warpage 의 dat 는 행 0 이 2축 **최소**라 방향이 반대입니다(§21).

---

<!-- END MANUAL EXCERPT -->
