# optimize — material-specific solver presets (§34)

Source: [optimize.cpp](../../src/commands/optimize.cpp)
Manual: [`KooRemapper_Manual.md`#34-optimize--재료별-해석-최적화](../../docs/KooRemapper_Manual.md#34-optimize--재료별-해석-최적화)


## Synopsis

```
KooRemapper optimize <args>
```

## What it does

Per-material solver presets (rubber etc.). Idempotent.

## Key references

- [[modules/commands#Module: src/commands/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §34. optimize — 재료별 해석 최적화._

<!-- BEGIN MANUAL EXCERPT -->



`optimize` 명령은 특정 재료(예: 고무)에 최적화된 LS-DYNA 컨트롤 카드를 자동으로 적용합니다.

### 사용법

```bash
KooRemapper optimize config.yaml
```

### YAML 형식

```yaml
model: my_model.k
output: my_model_optimized.k
optimize: rubber          # 최적화 모드 (현재: rubber만 지원)
pids: [2, 5, 8]          # 최적화 대상 파트 ID
tssfac: 0.67             # TSSFAC 설정값 (기본: 0.67)
analysis_type: ""        # "explicit" / "implicit" / "" (자동 감지)
```

#### matswap 통합

```yaml
model: base_model.k
output: swapped_model.k
swaps:
  - bundle: rubber.k
    pid: 3
optimize: rubber
```

### rubber 모드 적용

#### 공통 (explicit + implicit)


**표 34-1. optimize rubber 모드가 맞추는 카드 — 카드·필드·목표값.**

| 카드 | 필드 | 목표값 |
|---|---|---|
| `*CONTROL_ACCURACY` | INN | `4` |
| `*CONTROL_ENERGY` | HGEN/RWEN/SLNTEN/RYLEN | `2/2/2/2` |
| `*CONTACT_*` (대상 PID) | SOFT | `0` |
| `*CONTACT_*` (대상 PID) | SBOPT | `2` |

#### Explicit 전용


**표 34-2. optimize rubber 모드가 조정하는 카드 — 카드·필드·동작.**

| 카드 | 필드 | 동작 |
|---|---|---|
| `*CONTROL_TIMESTEP` | TSSFAC | 0.67 (강제) |
| `*CONTROL_TIMESTEP` | DT2MS | 양수이면 경고 |
| `*CONTROL_BULK_VISCOSITY` | Q1, Q2 | 비표준이면 경고 |

### 멱등성
이미 올바른 값은 수정하지 않습니다. 같은 모델에 두 번 실행해도 결과 동일.

---

<!-- END MANUAL EXCERPT -->
