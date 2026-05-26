# rbe — RBE constraint (§28)

Source: [load_boundary.cpp](../../src/commands/load_boundary.cpp)
Manual: [`KooRemapper_Manual.md`#28-rbe--rbe-구속-조건](../../docs/KooRemapper_Manual.md#28-rbe--rbe-구속-조건)


## Synopsis

```
KooRemapper rbe <args>
```

## What it does

Emits `*CONSTRAINED_NODAL_RIGID_BODY` or related cards.

## Key references

- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §28. rbe — RBE 구속 조건._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
RBE2(강체 연결) 또는 RBE3(분산 하중) 구속 조건을 삽입합니다.

### 사용법

```bash
KooRemapper.exe rbe <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: rbe_model.k
rbes:
  - type: rbe2
    master_nid: 100
    slave_nids: [101, 102, 103, 104]
    dof: 123456
  - type: rbe3
    master_nid: 200
    slave_nids: [201, 202, 203]
    dof: 123
    weights: [1.0, 1.0, 1.0]
```

### 파라미터


**표 29-1. implicit 변환 레벨 (1~8) — 공격적→보수적 순으로 정렬된 8단계 변환 레벨과 활성화 키워드.**

| 파라미터 | 설명 |
|----------|------|
| `type` | rbe2 (강체) / rbe3 (분산) |
| `master_nid` | 마스터 노드 ID |
| `slave_nids` | 슬레이브 노드 ID 리스트 |
| `dof` | 구속 자유도 (예: 123456) |
| `weights` | 가중치 (RBE3 전용) |

---

<!-- END MANUAL EXCERPT -->
