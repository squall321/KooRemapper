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

파트의 **면을 선택**해 RBE2/RBE3 강체 요소 구속을 만듭니다. RBE2 는 `*CONSTRAINED_NODAL_RIGID_BODY`, RBE3 는 `*CONSTRAINED_INTERPOLATION` 을 삽입합니다.

```yaml
model: mesh.k
output: mesh_rbe.k
rbe:
  - part: 9
    select: direction        # direction | all
    direction: [0, 0, -1]    # 면 선택 방향 벡터
    angle: 45.0              # 면 선택 각도 허용치(°)
    type: rbe3               # rbe2 | rbe3
    mode: spider             # spider (centroid 마스터 노드 1개) | face (면마다 centroid)
```

### 파라미터


**표 28-1. rbe 파라미터 — 대상 파트, 면 선택, RBE 유형·모드.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 대상 파트 ID |
| `select` | `direction`(방향 면) / `all`(파트 노출면 전체) — **`set` 은 없습니다** |
| `direction` | 면 선택 방향 벡터 |
| `angle` | 면 선택 각도 허용치(°) |
| `type` | `rbe2`(강체: 슬레이브가 마스터와 정확히 동일 이동) / `rbe3`(보간: 마스터 이동이 슬레이브 가중 평균) |
| `mode` | `spider`(centroid 마스터 노드 1개) / `face`(면마다 centroid 노드) |

> **허용값 (2026-09-18 실행 확인)**: `select` 는 **`direction` / `all`** 둘뿐입니다.
> `select: set` 이나 오타는 `[ERROR] rbe: constraints[0]: unsupported select 'set' (allowed: direction, all)` 와 함께
> **종료 코드 1** 입니다(예전에는 조용히 `all` 로 떨어져 면 전체를 잡았습니다).
> **`boundary` 에는 `set` 이 있고 `rbe` 에는 없습니다** — 두 op 의 help 가 오랫동안 같은 `direction | all` 을 찍어 혼동을 키웠으니 주의하세요.
> 이 검증은 단독 `rbe` 와 `assemble` 양쪽에 걸립니다.
>
> **v1.8.0 정정**: 구버전이 보이던 `type: rbe2/rbe3` + `master_nid`/`slave_nids`/`dof`/`weights` 노드 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`select`/`mode` **면-선택 스키마**를 씁니다(help·`examples/boundary` 의 rbe_spider/rbe_face). 최상위 키는 `rbe:` 입니다.

---

<!-- END MANUAL EXCERPT -->
