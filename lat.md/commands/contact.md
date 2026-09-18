# contact — CONTACT analyze/create/convert/modify/remove/detect (§25)

Source: [contact.cpp](../../src/commands/contact.cpp), [contact_helpers.cpp](../../src/commands/contact_helpers.cpp)
Manual: [`KooRemapper_Manual.md`#25-contact--접촉-정의-관리](../../docs/KooRemapper_Manual.md#25-contact--접촉-정의-관리)


## Synopsis

```
KooRemapper contact <args>
```

## What it does

Six sub-actions on `*CONTACT_*` cards. Optional cards A-G are modeled via `ct_modifyOptionalCards()` with re-parse. Auto-detect scans for part adjacency.

## Key references

- [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §25. contact — 접촉 정의 관리._

<!-- BEGIN MANUAL EXCERPT -->



```
KooRemapper.exe contact <config.yaml>
```

LS-DYNA 모델의 `*CONTACT_*`, `*SET_SEGMENT`, `*SET_PART`, `*SET_NODE` 키워드를 일괄 관리한다.
하나의 YAML 설정으로 분석, 생성, 변환, 수정, 삭제, 자동 감지를 순차 실행할 수 있다.

### 기본 YAML 구조

```yaml
model:  model.k
output: model_contact.k

contacts:
  - action: analyze
    ...
  - action: create
    ...
```

---

### 25.1 analyze — 접촉 분석

모델의 기존 접촉 정의를 리포트한다. 수정 없이 읽기 전용.

```yaml
contacts:
  - action: analyze
```

`contact_index` 번호([0], [1], ...)를 convert/modify/remove에서 참조한다.

---

### 25.2 create — 접촉 생성

#### 모드 1: Part ID 직접 지정 (SSTYP=3)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1 }
    master: { pid: 2 }
    friction: 0.3
    soft: 2
    title: Case_to_Board
```

#### 모드 2: 복수 PID → SET_PART 자동 생성 (SSTYP=2)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pids: [1, 2, 3] }
    master: { pids: [4, 5] }
```

#### 모드 3: 표면 세그먼트 추출 → SET_SEGMENT (SSTYP=0)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1, as_segment: true }
    master: { pid: 2, as_segment: true }
```

#### 모드 4: 세그먼트 + facing 필터

```yaml
contacts:
  - action: create
    type: tied_surface_to_surface
    slave:  { pid: 1, as_segment: true, facing: true }
    master: { pid: 2, as_segment: true, facing: true }
    tolerance: 0.05
    normal_angle: 30
```

#### 모드 5: Single Surface 자기접촉

```yaml
contacts:
  - action: create
    type: automatic_single_surface
    slave:  { pids: [1, 2, 3, 4] }
    soft: 2
```

#### create에서 사용 가능한 type 값


약칭(short name)을 쓰면 전체 키워드로 풀립니다. `assemble` 의 `- type: contact` 도 **같은 표**를 씁니다(2026-09-18 확인).

**표 25-1. contact create 접촉 type 약칭 — YAML type 약칭과 LS-DYNA *CONTACT 키워드.**

| type (YAML 약칭) | LS-DYNA 키워드 |
|---|---|
| `auto` / `automatic` | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` |
| **키 생략** | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` |
| `tied` | `*CONTACT_TIED_SURFACE_TO_SURFACE` |
| `tied_thermal` / `thermal` | `*CONTACT_TIED_SURFACE_TO_SURFACE_THERMAL` |
| `tiebreak` | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK` |
| `mortar` | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` |
| `tied_mortar` | `*CONTACT_TIED_SURFACE_TO_SURFACE_MORTAR` |
| `single` | `*CONTACT_AUTOMATIC_SINGLE_SURFACE` |
| `eroding` | `*CONTACT_ERODING_SURFACE_TO_SURFACE` |
| `forming` | `*CONTACT_FORMING_SURFACE_TO_SURFACE` |

> 실제로 쓰이는 카드는 `_TITLE` 붙은 형태입니다(`*CONTACT_TIED_SURFACE_TO_SURFACE_TITLE`).

> **약칭은 대소문자를 가리지 않고, `-` 는 `_` 로 바꿔 읽습니다**(2026-09-18 실행 확인) —
> `tied-thermal`·`TIED_THERMAL`·`tied_thermal` 이 모두 `*CONTACT_TIED_SURFACE_TO_SURFACE_THERMAL_TITLE` 로 나옵니다.
> 이 표는 코드에서도 한 곳(`ct_getPreset`)에만 있어 **단독 `contact` 와 `assemble` 의 `- type: contact` 가 같은 결과**를 냅니다.
> 예전에는 `assemble` 쪽에 `tied_thermal`·`thermal`·`tiebreak` 별칭이 없어 같은 YAML 이
> LS-DYNA 에 없는 `*CONTACT_TIED_THERMAL` 로 나갔습니다.

**약칭이 아닌 값**은 그대로 대문자로 바꿔 `*CONTACT_<입력값>` 으로 씁니다.
즉 `automatic_nodes_to_surface`·`automatic_general`·`forming_one_way_surface_to_surface`·`tied_shell_edge_to_surface` 처럼
표에 없는 LS-DYNA 접촉 키워드도 **그대로 통과**합니다(`KooRemapper` 자신이 `cclip` 에서 `automatic_nodes_to_surface` 를 씁니다).

아래 27개 키워드는 KooRemapper 가 내는 카드 구성과 맞는다고 등록해 둔 목록이라 **조용히 통과**합니다.

```
SURFACE_TO_SURFACE                      ONE_WAY_SURFACE_TO_SURFACE
NODES_TO_SURFACE                        SINGLE_SURFACE
AUTOMATIC_SURFACE_TO_SURFACE            AUTOMATIC_SURFACE_TO_SURFACE_MORTAR
AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK   AUTOMATIC_ONE_WAY_SURFACE_TO_SURFACE
AUTOMATIC_SINGLE_SURFACE                AUTOMATIC_SINGLE_SURFACE_MORTAR
AUTOMATIC_NODES_TO_SURFACE              AUTOMATIC_GENERAL
TIED_SURFACE_TO_SURFACE                 TIED_SURFACE_TO_SURFACE_OFFSET
TIED_SURFACE_TO_SURFACE_FAILURE         TIED_SURFACE_TO_SURFACE_MORTAR
TIED_SURFACE_TO_SURFACE_THERMAL         TIED_NODES_TO_SURFACE
TIED_NODES_TO_SURFACE_OFFSET            TIED_SHELL_EDGE_TO_SURFACE
TIED_SHELL_EDGE_TO_SURFACE_OFFSET       ERODING_SURFACE_TO_SURFACE
ERODING_SINGLE_SURFACE                  ERODING_NODES_TO_SURFACE
FORMING_SURFACE_TO_SURFACE              FORMING_ONE_WAY_SURFACE_TO_SURFACE
FORMING_NODES_TO_SURFACE
```

이 목록에도 없는 값은 **막지 않고 경고만** 합니다(종료 코드 0, 덱은 그대로 생성).

```
[WARN] [contact] create: type 'bogus' is not a known contact keyword — writing *CONTACT_BOGUS as-is
       (LS-DYNA will reject it if the keyword does not exist). Short names: auto, automatic, tied,
       tied_thermal, thermal, tiebreak, mortar, tied_mortar, single, eroding, forming
```

`assemble` 도 같은 문구를 찍습니다(그 파일 관례대로 접두어는 `[WARNING] `). 즉 **오타는 LS-DYNA 가 잡습니다.**

> **`assemble` 쪽 약칭 비대칭**: `assemble` 의 약칭 표에는 `tied_thermal`/`thermal`/`tiebreak` 항목이 없어,
> `assemble` 안에서 `type: thermal` 은 `*CONTACT_THERMAL` 을 내며 위 경고를 받습니다.
> `assemble` 에서는 **전체 키워드(`tied_surface_to_surface_thermal`)를 적으세요.**

#### `slave` / `master` 의 `pids` 표기

인라인 목록과 블록 목록 **둘 다** 쓸 수 있고 **같은 덱**이 나옵니다(2026-09-18 확인 — 예전에는 블록 목록이 조용히 무시되어 `*SET_PART` 가 생기지 않았습니다).

```yaml
slave:
  pids: [1, 2]        # 인라인
slave:
  pids:               # 블록 목록 — 위와 같다
    - 1
    - 2
```

---

### 25.3 convert — 접촉 변환

기존 접촉의 SSTYP/MSTYP 방식을 변경한다.

```yaml
contacts:
  - action: convert
    contact_index: 0
    slave_to: segment
    master_to: segment
    facing: true
    tolerance: 0.05
    normal_angle: 30
```

---

### 25.4 modify — 접촉 수정

```yaml
contacts:
  - action: modify
    contact_index: 0
    friction: 0.5
    soft: 2
    depth: 35
    penmax: 0.5
```

---

### 25.5 remove — 접촉 삭제

```yaml
contacts:
  - action: remove
    contact_index: 0
```

---

### 25.6 detect — 접촉 자동 감지

**Spatial Hash Grid** 알고리즘으로 파트 간 맞닿는 영역을 고속 검출한다.

#### 명시적 PID 지정

```yaml
contacts:
  - action: detect
    slave:  { pid: 1 }
    master: { pid: 2 }
    tolerance: 0.1
    auto_create: true
    contact_type: auto
    friction: 0.20
```

#### 전체 파트 자동 감지

```yaml
contacts:
  - action: detect
    scope: all
    exclude: [rigid, null, air]
    tolerance: 0.1
    auto_create: true
    contact_type: auto
```

#### 키워드 기반 파트 선택

```yaml
contacts:
  - action: detect
    include: [bolt, plate, housing]
    exclude: [rigid]
    tolerance: 0.05
    auto_create: true
    contact_type: tied
```

#### contact_type 프리셋


**표 25-2. contact detect 접촉 type — YAML 값, LS-DYNA 키워드, 용도.**

| YAML 값 | LS-DYNA 키워드 | 용도 |
|---|---|---|
| `auto` | `AUTOMATIC_SURFACE_TO_SURFACE` | 범용 |
| `tied` | `TIED_SURFACE_TO_SURFACE` | 접합 |
| `mortar` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` | 고정밀 |
| `single` | `AUTOMATIC_SINGLE_SURFACE` | 자기접촉 |
| `eroding` | `ERODING_SURFACE_TO_SURFACE` | 요소 파괴 |
| `forming` | `FORMING_SURFACE_TO_SURFACE` | 성형 해석 |

#### detect 옵션


**표 25-3. contact detect 옵션 — 탐지 범위, 포함·제외, 허용치, 법선 각, 자동 생성.**

| 키 | 기본값 | 설명 |
|---|---|---|
| `scope` | — | `all`: 모든 파트 쌍 탐색 |
| `include` | — | 대상 파트 이름 키워드 리스트 |
| `exclude` | — | 제외 파트 이름 키워드 리스트 |
| `tolerance` | `0.1` | 접촉 간격 허용치 |
| `normal_angle` | `45.0` | 법선 방향 허용 각도(°) |
| `auto_create` | `false` | 검출 쌍마다 자동 생성 |
| `skip_existing` | — | `tied`/`all`: 기존 접촉 쌍 건너뜀 |
| `subtract_existing` | `false` | 기존 tied 세그먼트 차집합 제외 |

---

### 25.7 세부 옵션 (Optional Cards A~G)

create, modify, detect(auto_create) 모든 액션에서 동일하게 사용 가능.

#### Card A (소프트닝/깊이)


**표 25-4. contact 세부 옵션 (soft·sofscl·depth·sbopt) — 키와 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `soft` | SOFT | 소프트 제약 (0/1/2) |
| `sofscl` | SOFSCL | SOFT 스케일 |
| `depth` | DEPTH | 검색 깊이 (0~45) |
| `sbopt` | SBOPT | 세그먼트 기반 옵션 |

#### Card B (두께)


**표 25-5. contact 세부 옵션 (penmax·thkopt·shlthk) — 키와 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `penmax` | PENMAX | 최대 관통량 |
| `thkopt` | THKOPT | 두께 옵션 |
| `shlthk` | SHLTHK | 셸 두께 고려 |

#### Card C (간격/에지)


**표 25-6. contact 세부 옵션 (igap·ignore) — 키와 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `igap` | IGAP | 간격 처리 |
| `ignore` | IGNORE | 관통 무시 |

> **카드 의존성**: Card G를 지정하면 A~F가 자동 포함 (LS-DYNA 고정폭 카드 순서 요구).

---

<!-- END MANUAL EXCERPT -->
