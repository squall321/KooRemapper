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

파트의 **면을 선택**해 압력/힘 하중을 부여합니다. `*LOAD_SEGMENT_SET`, `*DEFINE_CURVE`, `*SET_SEGMENT` 키워드를 삽입합니다.

```yaml
model: mesh.k
output: mesh_loaded.k
loads:
  - part: 10
    mode: pressure          # pressure | normal_pressure | force  (gravity 는 없다)
    value: 1.0              # 압력 [MPa], force 모드는 총 힘 [N]
    direction: [0, 0, 1]    # 하중 방향 벡터 (normal_pressure 외 필수)
    select: direction       # direction | tied | set  (all 은 없다)
    angle: 45.0             # 면 선택 각도 허용치(°)
    curve:                  # 선택. 시간-하중 곡선 → *DEFINE_CURVE
      - [0.0, 0.0]
      - [0.001, 1.0]
      - [0.01, 1.0]
```

### 파라미터


**표 26-1. load 파라미터 — 대상 파트, 하중 유형·크기·방향, 면 선택, 시간 곡선.**

| 파라미터 | 설명 |
|----------|------|
| `part` | 하중 대상 파트 ID |
| `mode` | 하중 유형 — `pressure`(값을 압력으로) / `normal_pressure`(방향 없이 노출면 전체에 법선 압력) / `force`(총 힘 [N] 을 투영면적으로 나눠 압력화) |
| `value` | 하중 크기 — `pressure`/`normal_pressure` 는 [MPa], `force` 는 총 힘 [N] |
| `direction` | 하중 방향 벡터 `[x, y, z]` (`normal_pressure` 외 필수) |
| `select` | 면 선택 방식 — `direction`(방향벡터 각도 내 법선 면, 기본) / `tied`(tied 접촉 참여 면, 모델에 해당 파트의 `*CONTACT_TIED…` 가 없으면 경고 후 파트 표면에서 고름) / `set`(기존 `*SET_SEGMENT`, `set_id` 필수) |
| `angle` | 면 선택 각도 허용치(°) |
| `curve` | 선택. `[[t, f], ...]` 시간-하중 곡선 |

> **허용값 (2026-09-18 실행 확인)**
> - `mode` 는 **`pressure` / `normal_pressure` / `force`** 셋뿐입니다. **`gravity` 는 없습니다** —
>   `[ERROR] [load] loads[0]: unsupported mode 'gravity' (allowed: pressure, force, normal_pressure)` 로 종료 코드 1 입니다.
>   중력 하중이 필요하면 `*LOAD_BODY_*` 를 직접 덱에 넣으세요.
> - `select` 는 **`direction` / `tied` / `set`** 셋뿐입니다. **`all` 은 없습니다**(종료 코드 1).
>   `boundary`·`rbe` 의 `select` 와 허용값이 다르니 주의하세요([§27](#27-boundary--경계-조건-적용)·[§28](#28-rbe--rbe-구속-조건)).
>
> **v1.8.0 정정**: 구버전이 보이던 `type`/`nid`/`pid`/`dof`/`lcid` 노드·파트 ID 직접지정 스키마 대신, v1.8.0 은 위 `part`/`mode`/`select`/`direction`/`angle` **면-선택 스키마**를 씁니다(help·`examples/load`).

---

<!-- END MANUAL EXCERPT -->
