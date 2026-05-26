# explicit — pure explicit restoration (§32)

Source: [strip.cpp](../../src/commands/strip.cpp)
Manual: [`KooRemapper_Manual.md`#32-explicit--순수-explicit-복원](../../docs/KooRemapper_Manual.md#32-explicit--순수-explicit-복원)


## Synopsis

```
KooRemapper explicit <args>
```

## What it does

Removes all `*CONTROL_IMPLICIT_*`, `*CONTROL_DYNAMIC_RELAXATION` etc., restoring a pure explicit `.k`. Counterpart to `strip`.

## Key references

- [[commands/strip#strip — keyword removal (§38)]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §32. explicit — 순수 Explicit 복원._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
모델에서 DR + Implicit + Modal 관련 키워드를 **모두 제거**하여 순수 Explicit 설정으로 복원합니다.

### 사용법

```bash
KooRemapper.exe explicit <config.yaml>
```

### YAML 형식

```yaml
model: implicit_model.k
output: explicit_model.k
keep_dr_curves: false    # true: SIDR=1 DEFINE_CURVE 유지
```

### 제거 대상


**표 32. (표 설명 — 해당 명령어/기능의 파라미터 또는 옵션 목록)**

| 키워드 | 원래 소속 |
|--------|----------|
| `*CONTROL_DYNAMIC_RELAXATION` | relax |
| `*DATABASE_BINARY_D3DRLF` | relax |
| `*CONTROL_IMPLICIT_GENERAL` | implicit |
| `*CONTROL_IMPLICIT_DYNAMICS` | implicit |
| `*CONTROL_IMPLICIT_SOLUTION` | implicit |
| `*CONTROL_IMPLICIT_AUTO` | implicit |
| `*CONTROL_IMPLICIT_STABILIZATION` | implicit |
| `*CONTROL_IMPLICIT_SOLVER` | implicit |
| `*CONTROL_IMPLICIT_EIGENVALUE` | modal |
| `*CONTROL_IMPLICIT_MODAL_DYNAMIC` | modal |
| `*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS` | modal |
| `*CONTROL_IMPLICIT_INERTIA_RELIEF` | modal |
| `*DEFINE_CURVE` (SIDR=1) | relax (keep_dr_curves=false 시) |

---

<!-- END MANUAL EXCERPT -->
