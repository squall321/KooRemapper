# offset — shell offset → solid extrusion (§22)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#22-offset--셸-오프셋-솔리드-생성](../../docs/KooRemapper_Manual.md#22-offset--셸-오프셋-솔리드-생성)


## Synopsis

```
KooRemapper offset <args>
```

## What it does

Extrudes a shell surface into a solid layer (with optional CZM connection). Variable thickness via `thickness_formula` (uses [FormulaEvaluator.cpp](../../src/assembly/FormulaEvaluator.cpp)). Local per-node averaged normals improve Jacobian on curved surfaces (+324% vs global avg).

Quality validation integrated: AspectRatio warn>10/err>20, Jacobian warn<0.1/err<-1e-10, Warping warn>30°/err>45°.

## Key references

- [[modules/validation#Module: src/validation/]]
- [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §22. offset — 셸 오프셋 솔리드 생성._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
셸(shell) 파트의 표면을 추출하여 지정 두께/방향으로 **솔리드 요소를 압출** 생성합니다.
곡면 법선, 가변 두께, 영역 선택, CZM 접합을 지원합니다.

### 사용법

```bash
KooRemapper.exe offset <config.yaml>
```

### YAML 형식

```yaml
base_model: model.k
output: offset_result
operations:
  - type: offset
    source_pid: 1
    element_type: solid          # solid | tshell | shell
    thickness: 2.0
    thickness_formula: "1.0 + 0.01*x"   # 가변 두께 수식 (선택, x/y/z 변수)
    num_layers: 1
    offset_direction: +normal    # +normal|-normal|+x|-x|+y|-y|+z|-z
    use_local_normals: true      # 곡면 노드별 법선 사용
    connection_mode: tied        # tied | czm | contact | none (기본 tied)
    new_pid: 10                  # 새 파트 ID
    part_title: "Offset part"
    material_card: |             # MID 칸(@MID@·숫자·라벨)은 새 MID 로 바뀜
      *MAT_ELASTIC
      $#     mid        ro         e        pr
           @MID@       2.0     12000      0.25

    # CZM 연결 (connection_mode: czm)
    czm_material_card: |         # MID 칸(@CZM_MID@ 등)은 새 CZM MID 로 바뀜
      *MAT_COHESIVE_MIXED_MODE
      $#     mid        ro     roflg   intfail        en        et       gic      giic
       @CZM_MID@       2.0         0       1.0     20000     10000       0.5       0.5
      $#     xmu         t         s       und       utd     gamma
             2.0       1.0       1.0

    # 영역(region) 필터 (선택): 소스 표면의 일부만 처리
    # bbox_xmin/xmax/ymin/ymax/zmin/zmax
    # node_id_min/max, element_id_min/max
```

> **v1.8.0 정정**: (1) `connection_mode` 값 집합은 `tied | czm | contact | none` 이며 **기본값은 `tied`** 입니다(help·examples. 구버전의 `shared | tied | czm`/기본 `shared` 정정). `contact` 는 인터페이스 노드를 복제해 별도 표면을 만들고 사용자가 이후 `*CONTACT` 를 정의합니다. (2) `element_type` 값은 `solid | tshell | shell` 입니다(구버전의 `hex | tet` 정정). (3) config 는 최상위 `base_model`/`output` + `operations[].type: offset` 구조입니다. 재료는 `material_card` 로 지정하고, 층마다 다르면 `material_cards:` 목록(`- |` 항목)을 씁니다(단독·assemble 모두). (4) 카드 MID 칸의 값(`@MID@`·`@CZM_MID@`·숫자·라벨)은 새 MID 로 바뀌며, 값은 LS-DYNA 고정 폭 10열 칸 안에 두세요. (5) `new_pid`·`new_secid`·`new_mid` 를 지정해도 뒤이어 자동 발급되는 ID 와 겹치지 않습니다. (6) `connection_mode: none` 은 assemble 경로에서도 허용됩니다. 단독 `offset` 도 assemble 과 같은 값 검사를 거칩니다.

### 주요 파라미터


**표 22-1. offset 주요 파라미터 — 소스 파트, 방향·두께, 요소 유형, 연결 방식.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `source_pid` | 소스 파트 ID | — |
| `offset_direction` | 압출 방향 | — |
| `thickness` | 균일 두께 | — |
| `thickness_formula` | 가변 두께 수식 (x,y,z 변수) | — |
| `use_local_normals` | 곡면 노드별 법선 사용 | `false` |
| `element_type` | 요소 유형 (solid/tshell/shell) | `solid` |
| `connection_mode` | 연결 방식 (tied/czm/contact/none) | `tied` |

### 품질 검증
생성된 솔리드 요소의 품질을 자동 검증합니다:
- Aspect Ratio: warn > 10, error > 20
- Jacobian: warn < 0.1, error < -1e-10
- Warping: warn > 30°, error > 45°

---

<!-- END MANUAL EXCERPT -->
