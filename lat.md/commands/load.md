# load — load application (§26)

Source: [load_boundary.cpp](../../src/commands/load_boundary.cpp)
Manual: [`KooRemapper_Manual.md`#26-load--하중-적용](../../docs/KooRemapper_Manual.md#26-load--하중-적용)


## Synopsis

```
KooRemapper load <args>
```

## What it does

Emits `*LOAD_BODY/NODE/SEGMENT/SHELL/THERMAL_*` cards from YAML.

## Key references

- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §26. load — 하중 적용._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
LS-DYNA 모델에 하중 키워드를 일괄 삽입합니다.

### 사용법

```bash
KooRemapper.exe load <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: loaded.k
loads:
  - type: force
    nid: 100
    dof: 3             # 1=x, 2=y, 3=z
    value: -1000.0
    lcid: 0            # Load Curve ID (0=상수)
  - type: pressure
    pid: 1
    value: 10.0
  - type: gravity
    direction: z
    value: -9810.0
```

### 파라미터


**표 27-1. boundary 조건 유형 — 지원하는 경계 조건 종류와 자유도(DOF) 구성.**

| 파라미터 | 설명 |
|----------|------|
| `type` | 하중 유형 (force/pressure/gravity) |
| `nid` | 노드 ID (force) |
| `pid` | 파트 ID (pressure) |
| `dof` | 자유도 방향 1=x, 2=y, 3=z (force) |
| `value` | 하중 크기 |
| `lcid` | Load Curve ID (0=상수) |
| `direction` | 중력 방향 (gravity) |

---

<!-- END MANUAL EXCERPT -->
