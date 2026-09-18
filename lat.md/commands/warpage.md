# warpage — warpage correction (§21)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp), [WarpageGrid.cpp](../../src/assembly/WarpageGrid.cpp)
Manual: [`KooRemapper_Manual.md`#21-warpage--워피지-보정](../../docs/KooRemapper_Manual.md#21-warpage--워피지-보정)


## Synopsis

```
KooRemapper warpage <args>
```

## What it does

Applies an out-of-plane warpage field (typically from molding simulation) and recomputes stress.

## Key references

- [[modules/assembly#Module: src/assembly/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §21. warpage — 워피지 보정._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
측정 데이터(.dat 파일)로부터 면외 변형(warpage)을 메시에 적용합니다.
곡률 기반 응력 계산 또는 직접 변위 모드를 지원합니다.

### 사용법

```bash
KooRemapper.exe warpage <config.yaml>
```

### YAML 형식

```yaml
base_model: flat.k
output: warped
material:
  E: 210000
  nu: 0.3
operations:
  - type: warpage
    target_pid: 1
    dat_file: warpage.dat      # 처짐값 격자 (YAML 폴더 기준 상대 경로)
    plane: xy                  # xy | yz | zx
    deflection_axis: +z        # +z | -z | +x | -x | +y | -y
    unit: um                   # um(기본) | mm | m — 격자 값 단위
    mode: prestress            # prestress(기본, 초기응력) | deform(노드 이동)
    morph_factor: 1.0          # 처짐 배율 (> 0)
    finite_strain: true        # true: von Kármán 대변형(기본) | false: Kirchhoff
    outside_behavior: zero     # zero(기본) | clamp | extrapolate — 격자 범위 밖 노드
    mask_value: 9999           # 결측으로 보고 주변에서 보간할 값
    noise_threshold: 1.0e-10   # 노이즈 임계값
    # data_bbox:               # 격자가 덮는 평면 좌표 범위 (생략 시 파트 bbox)
    #   x_min: 0.0
    #   x_max: 100.0
    #   y_min: 0.0
    #   y_max: 100.0
```

> **v1.8.0 정정**: config 는 최상위 `base_model`/`output` + `operations[].type: warpage` 구조입니다. 이전 help 와 이 문서가 적었던 `source`·`dat_top`·`dat_bottom`·op 바로 아래 `x_min~y_max` 는 warpage 파서가 읽지 않는 키였습니다(오류 없이 무시). 격자 범위는 `data_bbox:` 아래에 두고, `mode` 는 `prestress | deform` 입니다(`curvature | raw` 아님). YAML 이 현재 폴더에 있을 때 `dat_file` 을 루트(`/파일`)에서 찾던 문제는 고쳐졌습니다.

### 파라미터


**표 21-1. warpage 파라미터 — 격자 파일·평면·단위·모드·범위 처리와 기본값.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `dat_file` | 처짐값 격자 파일 (필수) | — |
| `plane` | 투영 평면 (xy/yz/zx) | `xy` |
| `deflection_axis` | 처짐 방향 축 (±x/±y/±z) | `z` |
| `unit` | 격자 값 단위 (um/mm/m) | `um` |
| `mode` | prestress(초기응력만) / deform(노드 이동) | `prestress` |
| `morph_factor` | 처짐 배율 (> 0, 10 초과 시 경고) | `1.0` |
| `mask_value` | 결측 값 (주변 보간) | `9999` |
| `noise_threshold` | 노이즈 임계값 | `1e-10` |
| `finite_strain` | von Kármán 대변형(true) / Kirchhoff 소변형(false) | `true` |
| `outside_behavior` | 격자 범위 밖 노드 처리 (zero/clamp/extrapolate) | `zero` |
| `data_bbox` | 격자가 덮는 평면 범위 (`x_min`·`x_max`·`y_min`·`y_max`) | 파트 bbox |
| `debug` / `debug_prefix` | 격자·곡률 VTK 등 디버그 출력 | `false` / `debug/warp` |

### dat 파일 형식

공백(탭) 구분 처짐값 행렬입니다. `data_bbox`(생략 시 파트 bbox)에 펼치며 **열 0 = 평면 1축 최소, 행 0 = 2축 최소**입니다(bend 의 dat 는 행 0 = x2 최대로 반대). 값 단위는 `unit` 입니다.

```
0  0   0   0  0
0 50 100  50  0      # 가운데가 최대 100 um
0  0   0   0  0
```

### 동작
1. .dat 격자 로드 (`mask_value` 결측은 주변 보간)
2. 바이리니어 보간으로 각 노드 위치의 처짐 계산
3. prestress 모드: 유한 차분 곡률 → Kirchhoff/von Kármán 굽힘 변형률 → 초기응력 (노드 그대로)
4. deform 모드: 노드를 처짐만큼 이동

---

<!-- END MANUAL EXCERPT -->
