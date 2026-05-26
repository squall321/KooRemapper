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
model: base.k
output: bent
target_pid: 1
plane: xy               # xy | yz | zx (굽힘 평면)
mode: deform            # deform (노드 이동) | stress (응력만)
source: formula         # formula | dat | dat_pair

# source: formula
expression: "0.5 * sin(pi * x1 / L1) * sin(pi * x2 / L2)"

# source: dat
# dat_file: deflection.dat

# source: dat_pair
# dat_top: top.dat
# dat_bottom: bottom.dat

material:
  E: 210000
  nu: 0.3
```

### 수식 변수


**표 15-1. formstrain 출력 — 이면각 기반 소성 변형률 계산 결과 및 LS-DYNA *INITIAL_STRAIN_SOLID 출력.**

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

---

<!-- END MANUAL EXCERPT -->
