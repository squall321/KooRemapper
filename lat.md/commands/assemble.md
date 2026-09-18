# assemble — multi-operation YAML composer (§39)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#39-assemble--통합-어셈블리](../../docs/KooRemapper_Manual.md#39-assemble--통합-어셈블리)


## Synopsis

```
KooRemapper assemble <args>
```

## What it does

Central composer. Operations: replace, squeeze, restack, bend, indent, formstrain, convert (tet10/hex20/quad8/tria6), refine, elform, disconnect, iga, warpage, offset, matswap, matdb, wrap, generate, update, control, database. Stresses from multiple ops on the same element sum; EPS uses max(). See [[modules/assembly#Module: src/assembly/]].

## Key references

- [[modules/assembly#Module: src/assembly/]]
- per-op nodes under [[commands/index#Commands]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §39. assemble — 통합 어셈블리._

<!-- BEGIN MANUAL EXCERPT -->



### 개요

여러 오퍼레이션을 **순차적으로 적용**하는 통합 명령.
기본 모델을 로드하고 각 오퍼레이션을 순서대로 실행하며,
누적된 초기 응력을 단일 dynain 파일로 출력합니다.

```bash
KooRemapper.exe assemble <config.yaml>
```

### 공통 YAML 구조

```yaml
base_model: model.k
output: result
material:
  E: 210000
  nu: 0.3
dynamic_relaxation: true
dynain_embed: false

operations:
  - type: <op_type>
    ...
```

### 공통 특성
- **원본 키워드 보존**: `*CONTACT`, `*BOUNDARY`, `*LOAD` 등 미파싱 키워드 그대로 유지
- **응력 누적**: 동일 요소에 여러 오퍼레이션 적용 시 응력 합산(`std::map` 기반)
- **ID 자동 관리**: 파트/섹션/노드/요소 ID 자동 발급 (충돌 방지)
- **출력 이름**: `output` 끝의 `.k` 는 있어도 없어도 같습니다(`result`·`result.k` → `result.k`, dynain 은 `result.dynain`).
- **상대 경로**: `base_model`·`output`·`dat_file`·`bundle`·`dynain` 등 YAML 안의 모든 파일 경로는
  **그 YAML 파일이 있는 폴더 기준**입니다 — 폴더가 붙은 `../data/box.k` 도 같고, 작업 폴더로 되돌아가지 않습니다
  (YAML 이 현재 폴더에 있어도 같음). 절대 경로는 그대로 씁니다.
  **`matdb` 의 `database` 도 같은 규칙입니다** — 값이 홑이름인데 그 자리에 없을 때만 번들 DB 로 한 번 더 찾아보고,
  폴더가 붙은 상대 경로는 번들로 넘어가지 않고 종료 코드 1 입니다([§24 표 24-1](#24-matdb--재료-db-교체)).
  **`assemble` 설정에 남은 경로 예외는 없습니다** — `map <config.yaml>` 만 단독 명령 쪽에서 예외로 남아 있습니다([§3.1(a)](#31-yaml-공통-규칙-모든-op)).
- **인라인 주석**: 값 뒤에 공백 + `#` 로 주석을 달 수 있습니다(따옴표 안의 `#` 는 값). 단독 YAML 명령도 같습니다.
- **탭 들여쓰기 거절 / UTF-8 BOM 허용**: [§3.1(d)(e)](#31-yaml-공통-규칙-모든-op) 와 같습니다.
- **값 검사**: 각 op 값을 읽을 때 검사하며, 단독 `bend`·`indent`·`offset`·`restack`·`iga` 도 같은 규칙을 씁니다.
  열거값 오타는 **종료 코드 1 + 출력 파일 없음** 이고, 이 검증은 `assemble` 과 단독 명령 양쪽에 똑같이 걸립니다
  (`restack` 의 `element_type`, `matdb` 의 `damping_preset`, `boundary`/`rbe` 의 `select` 등).
- **nan/inf 방어(2026-09-18)**: 결과 덱(`.k`·`.dynain`·IGA include)에 유한하지 않은 값이 하나라도 있으면
  **아무 파일도 쓰지 않고 종료 코드 1** 입니다. `assemble` 도 단독 명령과 같습니다(예전에는 `assemble` 만 조용히 nan 덱을 냈습니다).

  ```
  [ERROR] 출력 덱에 유한하지 않은 값(nan/inf)이 있습니다: out.k:17 '-nan' — 출력 파일을 쓰지 않았습니다: out.k, out.dynain
  ```

  **같은 경로에 있던 지난 실행 결과는 지우지 않습니다** — 실패해도 그 자리에 예전 파일이 그대로 남으니,
  새 결과로 오해하지 않도록 종료 코드를 반드시 확인하세요. in-place 출력(`output` == `base_model`)에서는 입력 메시가 보존됩니다.

> **참고**: 아래 각 오퍼레이션은 동일 이름의 독립 명령어(12~22장)와 동일한 알고리즘을 사용합니다.
> assemble 내에서는 `- type: <이름>` 으로 지정하며, 여러 오퍼레이션을 순차 결합할 수 있습니다.

---

### 39.1 replace — 상세 메시 교체

```yaml
- type: replace
  target_pid: 3
  detail_flat: detail.k
  shell_bent: bent.k
  prestress: true
```

모델 내 특정 파트를 상세 메시로 교체. `prestress: true` 시 굽힘 초기 응력 자동 계산.

---

### 39.2 squeeze (assemble 내)

```yaml
- type: squeeze
  target_pid: 5
  eps_x: -0.015
  eps_y: -0.015
  eps_z:  0.0
```

독립형 `squeeze` 명령과 동일.

---

### 39.3 restack — 레이어 재적층

```yaml
- type: restack
  target_pid: 2
  direction: z
  element_type: solid
  layers:
    - thickness: 0.3
      material_card: |
        *MAT_ELASTIC
        ...
    - thickness: 0.5
      material_card: |
        *MAT_ELASTIC
        ...
```

→ 독립 명령 [12. restack](#12-restack--레이어-재적층) 참조

---

### 39.4 bend — 굽힘 변형 + 초기 응력

```yaml
- type: bend
  target_pid: 1
  plane: xy
  mode: deform
  source: formula
  expression: "0.5 * sin(pi * x1 / L1)"
```

→ 독립 명령 [13. bend](#13-bend--굽힘-변형--초기-응력) 참조

---

### 39.5 indent — 압입 / 엠보싱

```yaml
- type: indent
  target_pid: 2
  plane: xy
  direction: -z
  depth: 2.0
  r1: 1.5
  r2: 1.0
  stress: true
  shape:
    type: polygon
    points:
      - [0, 0]
      - [10, 0]
      - [10, 8]
      - [0, 8]
```

→ 독립 명령 [14. indent](#14-indent--압입엠보싱) 참조

---

### 39.6 formstrain — 성형 소성 변형률

```yaml
- type: formstrain
  target_pid: 0
  shell_thickness: 0.0
  min_curvature: 0.001
```

→ 독립 명령 [15. formstrain](#15-formstrain--성형-소성-변형률) 참조

---

### 39.7 tet10 / hex20 / quad8 / tria6 — 2차 요소 변환

```yaml
- type: tet10       # tet10 | hex20 | quad8 | tria6
  target_pid: 0
  elform: 17
```

→ 독립 명령 [16. convert](#16-convert--2차-요소-변환) 참조

---

### 39.8 refine — 메시 세분화

```yaml
- type: refine
  target_pid: 0
  ratio: 2
```

→ 독립 명령 [17. refine](#17-refine--메시-세분화) 참조

---

### 39.9 elform — 요소 공식 변경

```yaml
- type: elform
  target_pid: 0
  target_elform: "2"
```

→ 독립 명령 [18. elform](#18-elform--요소-공식-변경) 참조

---

### 39.10 disconnect — 노드 분리

```yaml
- type: disconnect
  target_pid: 3
  mode: full
```

→ 독립 명령 [19. disconnect](#19-disconnect--노드-분리) 참조

---

### 39.11 iga — 등기하해석 NURBS 박스 생성

```yaml
- type: iga
  targets:
    - target_pid: 1
      element_size: 4.0
      bbox_scale: 1.5
```

→ 독립 명령 [20. iga](#20-iga--등기하해석-nurbs-박스-생성) 참조

---

### 39.12 warpage — 워피지 보정

```yaml
- type: warpage
  target_pid: 1
  dat_file: warpage.dat
  plane: xy
  deflection_axis: +z
  unit: um
  mode: prestress
  morph_factor: 1.0
```

→ 독립 명령 [21. warpage](#21-warpage--워피지-보정) 참조

---

### 39.13 offset — 셸 오프셋 솔리드 생성

```yaml
- type: offset
  source_pid: 1
  offset_direction: +normal
  thickness: 2.0
  use_local_normals: true
  element_type: solid
```

→ 독립 명령 [22. offset](#22-offset--셸-오프셋-솔리드-생성) 참조

---

### 39.14 matswap — 재료 번들 교체

```yaml
- type: matswap
  bundle: rubber.k
  pid: 3
```

→ 독립 명령 [23. matswap](#23-matswap--재료-번들-교체) 참조

---

### 39.15 matdb — 재료 DB 교체

```yaml
- type: matdb
  database: materials/material_db.json   # YAML 폴더 기준 (§3.1(a) 와 같음). 생략하면 번들 DB
  mat_type: MAT_024                      # 생략 시 기본값은 MAT_ELASTIC
  thermal: false
```

`damping_preset` 은 `smartphone_drop` / `smartphone_drop_aggressive` / `quasi_static` / `off` 만 받습니다(그 밖의 값은 종료 코드 1).

→ 독립 명령 [24. matdb](#24-matdb--재료-db-교체) 참조

---

### 39.16 wrap — 와인딩 인장 프리스트레스

```yaml
- type: wrap
  target_pid: 1
  axis: z
  center: [0, 0]
  tension: 100.0
```

→ 독립 명령 [33. wrap](#33-wrap--와인딩-인장-프리스트레스) 참조

### 39.17 generate — 메시 인라인 생성

`base_model` 없이 assemble 시작 시 첫 번째 오퍼레이션으로 사용:

```yaml
# base_model 키 없음
output: my_model

operations:
  - type: generate
    shape: box
    lx: 100.0   # X 길이 [mm]
    ly:  20.0   # Y 길이 [mm]
    lz:  10.0   # Z 길이 [mm]
    nx: 10      # X 방향 요소 수
    ny:  4
    nz:  2
    rho: 7.85e-9
    E: 210000.0
    nu: 0.3
    mid: 1
    secid: 1
    pid: 1
    part_title: Steel Box
```

독립 명령으로도 사용 가능: `KooRemapper generate box config.yaml`

---

### 39.18 update — 노드 좌표 업데이트

dynain 또는 K 파일의 `*NODE` 블록에서 일치하는 NID만 좌표 갱신 (미정의 노드 유지):

```yaml
- type: update
  dynain: results/dynain
```

→ 독립 명령으로도 사용: `KooRemapper update config.yaml`

---

### 39.19 control — 해석 제어 카드 삽입

`*CONTROL_*` 카드를 삽입하거나 기존 카드 필드를 수정:

```yaml
- type: control
  endtime: 0.001    # *CONTROL_TERMINATION endtim (초)
  tssfac: 0.9       # *CONTROL_TIMESTEP tssfac
  dt2ms: -1.0e-7    # *CONTROL_TIMESTEP dt2ms (mass scaling, 음수)
  energy: true      # *CONTROL_ENERGY: hgen=2, rwen=2, slnten=1, rylen=1
  ihq: 4            # *CONTROL_HOURGLASS: stiffness-based
  qh: 0.05          # hourglass coefficient
  q1: 1.5           # *CONTROL_BULK_VISCOSITY quadratic
  q2: 0.06          # linear bulk viscosity
```

기존 카드가 있으면 해당 필드만 수정. 없으면 신규 삽입.

---

### 39.20 database — 출력 제어 카드 삽입

`*DATABASE_*` 출력 키워드 일괄 삽입 (assemble 내):

```yaml
- type: database
  preset: crash     # all | drop | crash | static | thermal | forming | modal | minimal
  dt: 0.0001        # ASCII 출력 간격 (초)
  dt_plot: 0.001    # d3plot 출력 간격
```

> **프리셋은 위 8종뿐입니다.** 예전 판이 적었던 **`nve` 는 없는 프리셋**이고,
> 주면 `[ERROR] Unknown preset: nve` 와 함께 종료 코드 1 입니다(확인). 전체 목록은 [§37 표 37-1](#37-database--database-출력-제어) 참조.

→ 독립 명령 [37. database](#37-database--database-출력-제어) 참조

---

<!-- END MANUAL EXCERPT -->
