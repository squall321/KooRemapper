# squeeze — interference-fit compression + reverse prestress (§7)

Source: [squeeze_assemble.cpp](../../src/commands/squeeze_assemble.cpp), [SqueezeConfigReader.cpp](../../src/squeeze/SqueezeConfigReader.cpp)
Manual: [`KooRemapper_Manual.md`#7-squeeze--간섭-끼워맞춤](../../docs/KooRemapper_Manual.md#7-squeeze--간섭-끼워맞춤)


## Synopsis

```
KooRemapper squeeze config.yaml
```

## What it does

Two modes: (1) direct strain spec — displace nodes inward and inject reverse prestress via dynain; (2) thermal swelling — insert `*MAT_ADD_THERMAL_EXPANSION` and let LS-DYNA solve the equilibrium.

## Key references

- [[modules/squeeze#Module: src/squeeze/]]
- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]
- [[commands/prestress#prestress — reference → deformed strain/stress + dynain (§6)]] (reverse stress)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §7. squeeze — 간섭 끼워맞춤._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
간섭(interference fit) 조립 시뮬레이션을 위해 대상 파트를 지정 변형률로
**압축(compress)**하고, 그 역방향 응력을 dynain으로 출력.

### 사용법

```bash
KooRemapper.exe squeeze <mesh.k> <config.yaml> <output_prefix>
```

### YAML 설정

```yaml
# 방법 1: 직접 변형률 지정 (노드 이동 + dynain)
parts:
  - pid: 3
    eps_x: -0.02    # x방향 2% 압축
    eps_y: -0.02
    eps_z:  0.0

# 방법 2: 등방 팽창(swelling) — 열팽창 카드 삽입
  - pid: 5
    swelling: 0.01  # 1% 등방 팽창

material:           # 전역 재료 (K-파일 재료 없을 때)
  E: 210000
  nu: 0.3
```

### 동작 원리

**방법 1 (eps_x/y/z):** 파트 바운딩 박스 중심 $\mathbf{c}$에 대해 각 노드 위치:

$$\mathbf{x}' = \mathbf{c} + \begin{pmatrix} 1+\varepsilon_x & 0 & 0 \\ 0 & 1+\varepsilon_y & 0 \\ 0 & 0 & 1+\varepsilon_z \end{pmatrix} (\mathbf{x} - \mathbf{c})$$

초기 응력 (압축에 대한 역방향):

$$\sigma_{xx} = -(\lambda + 2\mu)\varepsilon_x - \lambda(\varepsilon_y + \varepsilon_z)$$

**방법 2 (swelling):** 노드를 이동하지 않고 LS-DYNA 열팽창 카드를 삽입합니다.
- `*MAT_ADD_THERMAL_EXPANSION` (LCID=0, 등방 ALPHA = swelling)
- `*INITIAL_TEMPERATURE` (모든 노드, T=1.0)
- `*LOAD_THERMAL_VARIABLE` (LCID=온도 커브 ID)
- 해석 시 LS-DYNA가 자동으로 열팽창을 적용

swelling 파트는 dynain에 포함되지 않습니다.

### 출력
- `<prefix>.k`: 압축된 메시 + 열팽창 카드 (swelling 파트)
- `<prefix>_dynain.dat`: `*INITIAL_STRESS_SOLID` (eps 파트만)

---

<!-- END MANUAL EXCERPT -->
