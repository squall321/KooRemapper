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

> **v1.8.0 정정**: explicit 복원 op 에는 **level 체계가 없습니다**. `model`/`output`/`keep_dr_curves` 세 키만 받습니다(help). `examples/explicit/level01.yaml`~`level12.yaml` 는 이 explicit 복원 op 이 아니라 별도 op 인 **`stabilize`**(파일 내용이 `stabilize: explicit` + `level: 1~12`, 호출 `KooRemapper stabilize levelNN.yaml`)용 예제이므로 혼동에 주의합니다(§36 stabilize 참조).

### 제거 대상


**표 32-1. explicit 제거 대상 키워드 — 키워드와 원래 소속 명령.**

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
