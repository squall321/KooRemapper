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

파트의 **면을 선택**해 자유도 구속(SPC)을 부여합니다.
삽입되는 키워드는 **`*SET_NODE_LIST_TITLE` + `*BOUNDARY_SPC_SET`** 입니다(확인).

```yaml
model: mesh.k
output: mesh_bc.k
boundaries:
  - part: 9
    dof: all                 # all | x | y | z | xy | xz | yz | xyz
    direction: [0, 0, -1]    # 면 선택 방향 벡터 (select: direction 일 때만 의미가 있다)
    select: direction        # direction | all | set
    set_id: 100              # select: set 일 때 필수 (기존 *SET_NODE)
    angle: 45.0              # 면 선택 각도 허용치(°)
```

> **`*RIGIDWALL` 은 나오지 않습니다.** 바이너리의 `boundary` help 가 아직
> `Inserts *BOUNDARY_SPC_NODE, *RIGIDWALL_PLANAR keywords.` 라고 찍지만, 소스에는 강체벽을 쓰는 코드가 없고
> 실제 출력 덱에도 `*RIGIDWALL` 이 0건입니다. 노드 구속도 `*BOUNDARY_SPC_NODE` 가 아니라
> **노드 세트 + `*BOUNDARY_SPC_SET`** 으로 나갑니다. 강체벽이 필요하면 `*RIGIDWALL_PLANAR` 를 직접 덱에 넣으세요.

### 파라미터


**표 27-1. boundary 파라미터 — 대상 파트, 구속 자유도, 면 선택.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 경계 대상 파트 ID |
| `dof` | 구속 자유도 — `all`(6 DOF 전체) / `x`·`y`·`z`(단일 병진) / `xy`·`xz`·`yz`·`xyz`(다중 병진) |
| `direction` | 면 선택 방향 벡터 (`select: direction` 에서만 쓰임) |
| `select` | `direction`(방향 면) / `all`(파트 노출면 전체) / `set`(기존 `*SET_NODE`, `set_id` 필수) |
| `angle` | 면 선택 각도 허용치(°) |

> **허용값 (2026-09-18 실행 확인)**
> - `select` 는 **`direction` / `all` / `set`** 셋입니다. 오타는
>   `[ERROR] boundary: boundaries[0]: unsupported select 'bogus' (allowed: direction, all, set)` 와 함께 **종료 코드 1, 출력 파일 없음** 입니다
>   (예전에는 조용히 `direction` 으로 떨어졌습니다).
> - **`select: all` 에 `direction` 키가 같이 있으면 `direction` 을 무시하고 파트 노출면 전체를 잡습니다.**
>   예전에는 이 조합에서 방향 필터가 걸렸으니, `all` 로 적어 둔 기존 YAML 은 구속 노드 수가 달라질 수 있습니다
>   (예: 20×10×2 박스 PID 1 → `direction` 132 노드 vs `all` 162 노드).
> - **`boundary` 와 `rbe` 의 `select` 허용값이 다릅니다** — `boundary` 는 `direction|all|set`, `rbe` 는 `direction|all`(`set` 없음),
>   `load` 는 `direction|tied|set`(`all` 없음). 바이너리의 `boundary` help 가 아직 `# direction | all` 만 찍는 것은 낡은 표기입니다.
>
> **v1.8.0 정정**: 구버전이 보이던 `type: spc/prescribed_motion` + `nid` + `dofx~dofrz` 노드 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`dof`/`select`/`direction` **면-선택 스키마**를 씁니다(help·`examples/boundary`). help 의 `dof` 목록은 `all|x|y|z|xy|xz|yz` 이나 예제는 3방향 병진 구속에 `xyz` 도 사용합니다.

---

<!-- END MANUAL EXCERPT -->
