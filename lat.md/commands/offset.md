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
model: base.k
output: offset_result
source_pid: 1
offset_direction: +normal   # +normal|-normal|+x|-x|+y|-y|+z|-z
thickness: 2.0
thickness_formula: "1.0 + 0.01*x"   # 가변 두께 수식 (선택)
num_layers: 1
use_local_normals: true      # 곡면 법선 사용
element_type: hex            # hex | tet
connection_mode: shared      # shared | tied | czm
new_pid: 0                   # 0=자동
part_title: "Offset part"
material:
  E: 210000
  nu: 0.3

# CZM 연결 (connection_mode: czm)
czm_part_id: 100
czm_mid: 50
czm_material_card: |
  *MAT_COHESIVE_...

# 재료 카드 직접 지정 (선택)
material_card: |
  *MAT_ELASTIC
  ...

# 영역 선택 (선택)
bbox_xmin: 0
bbox_xmax: 100
bbox_ymin: 0
bbox_ymax: 100
bbox_zmin: 0
bbox_zmax: 100
node_id_min: 1
node_id_max: 999999
element_id_min: 1
element_id_max: 999999
```

### 주요 파라미터


**표 22-2. offset local_normals 효과 — 전역 평균 법선 대비 로컬 법선 사용 시 품질 개선.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `source_pid` | 소스 파트 ID | — |
| `offset_direction` | 압출 방향 | — |
| `thickness` | 균일 두께 | — |
| `thickness_formula` | 가변 두께 수식 (x,y,z 변수) | — |
| `use_local_normals` | 곡면 노드별 법선 사용 | `false` |
| `connection_mode` | 연결 방식 (shared/tied/czm) | `shared` |

### 품질 검증
생성된 솔리드 요소의 품질을 자동 검증합니다:
- Aspect Ratio: warn > 10, error > 20
- Jacobian: warn < 0.1, error < -1e-10
- Warping: warn > 30°, error > 45°

---

<!-- END MANUAL EXCERPT -->
