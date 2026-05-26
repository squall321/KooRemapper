# wrap — winding-tension prestress (§33)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#33-wrap--와인딩-인장-프리스트레스](../../docs/KooRemapper_Manual.md#33-wrap--와인딩-인장-프리스트레스)


## Synopsis

```
KooRemapper wrap <args>
```

## What it does

Applies winding tension to jelly-roll layers — translates tension to hoop stress per layer.

## Key references

- [[modules/assembly#Module: src/assembly/]]
- [[modules/battery#Module: src/battery/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §33. wrap — 와인딩 인장 프리스트레스._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
와인딩 공정에서 발생하는 인장 프리스트레스를 시뮬레이션합니다.
원통 좌표계 기반으로 후프(hoop) 응력과 반경 방향 압축을 계산합니다.

### 사용법

```bash
KooRemapper.exe wrap <config.yaml>
```

### YAML 형식

```yaml
model: cylinder.k
output: wrapped
target_pid: 1
axis: z                 # 와인딩 축 (x/y/z)
axis_center: [0, 0]     # 축 중심 좌표 [c1, c2]
tension: 100.0          # 와인딩 인장력 (MPa)
material:
  E: 210000
  nu: 0.3
```

### 물리 모델

원통 좌표계 (r, θ, z)에서:
- **후프 응력** σ_θθ = tension (인장)
- **반경 압축** σ_rr = -tension × (r_outer/r - 1) / ln(r_outer/r_inner)

전역 좌표 변환:
$$\sigma_{xx} = \sigma_{rr}\cos^2\theta + \sigma_{\theta\theta}\sin^2\theta$$
$$\sigma_{yy} = \sigma_{rr}\sin^2\theta + \sigma_{\theta\theta}\cos^2\theta$$
$$\sigma_{xy} = (\sigma_{\theta\theta} - \sigma_{rr})\sin\theta\cos\theta$$

---

<!-- END MANUAL EXCERPT -->
