# formstrain — shell forming plastic EPS (§15)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp), [ShellCurvature.cpp](../../src/assembly/ShellCurvature.cpp)
Manual: [`KooRemapper_Manual.md`#15-formstrain--성형-소성-변형률](../../docs/KooRemapper_Manual.md#15-formstrain--성형-소성-변형률)
Theory: [[theory/formstrain-theory#Formstrain (dihedral curvature)]]

## Synopsis

```
KooRemapper formstrain <args>
```

## What it does

Computes dihedral angle across shell edges via `ShellCurvature` (edge adjacency map). κ = θ/L where L is centroid distance. Bending strain → plastic EPS (sigy from MAT_024 Card 1 Field 5). Multiple ops merge EPS via max() (not sum).

## Key references

- [[theory/formstrain-theory#Formstrain (dihedral curvature)]]
- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]
- [[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §15. formstrain — 성형 소성 변형률._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
셸 메시의 **이면각(dihedral angle)**으로부터 굽힘 곡률을 계산하여
등가 소성 변형률(EPS)을 `*INITIAL_STRESS_SHELL`로 출력합니다.

### 사용법

```bash
KooRemapper.exe formstrain <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: formed
target_pid: 0            # 0 = 전체 셸 파트 자동 감지
shell_thickness: 0.0     # 0 = *SECTION_SHELL에서 자동
min_curvature: 0.001     # 잡음 필터 임계값
```

### 이론

인접 셸 요소 쌍의 이면각 θ, 중심 간 거리 L:

$$\kappa = \frac{\theta}{L}$$

등가 소성 변형률:

$$\text{EPS} = \frac{t}{\sqrt{3} L} \theta$$

> 동일 요소에 복수 이웃 곡률이 있을 경우 **최대값(max)** 적용 (합산 아님).

---

<!-- END MANUAL EXCERPT -->
