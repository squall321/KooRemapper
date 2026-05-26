# boundary — boundary conditions (§27)

Source: [load_boundary.cpp](../../src/commands/load_boundary.cpp)
Manual: [`KooRemapper_Manual.md`#27-boundary--경계-조건-적용](../../docs/KooRemapper_Manual.md#27-boundary--경계-조건-적용)


## Synopsis

```
KooRemapper boundary <args>
```

## What it does

Emits `*BOUNDARY_SPC_*` cards from YAML.

## Key references

- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §27. boundary — 경계 조건 적용._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
LS-DYNA 모델에 경계 조건(구속/변위) 키워드를 삽입합니다.

### 사용법

```bash
KooRemapper.exe boundary <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: constrained.k
boundaries:
  - type: spc
    nid: 100
    dofx: 1            # 0=자유, 1=구속
    dofy: 1
    dofz: 1
    dofrx: 0
    dofry: 0
    dofrz: 0
  - type: prescribed_motion
    nid: 200
    dof: 1
    value: 10.0
    lcid: 1
```

### 파라미터


**표 28-1. rbe 구속 유형 — RBE2/RBE3 구속 조건 생성 방법과 마스터/슬레이브 설정.**

| 파라미터 | 설명 |
|----------|------|
| `type` | 경계 유형 (spc/prescribed_motion) |
| `nid` | 노드 ID |
| `dofx~dofrz` | DOF 구속 (SPC: 0=자유, 1=구속) |
| `dof` | 자유도 방향 (prescribed_motion) |
| `value` | 변위값 |
| `lcid` | Load Curve ID |

---

<!-- END MANUAL EXCERPT -->
