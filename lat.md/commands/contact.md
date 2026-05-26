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


**표 24-1. matdb 재료 매칭 규칙 — 제목(title)/이름(name)/태그(tag) 우선순위 기반 자동 매칭.**

| type (YAML) | LS-DYNA 키워드 |
|---|---|
| `automatic_surface_to_surface` | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` |
| `tied_surface_to_surface` | `*CONTACT_TIED_SURFACE_TO_SURFACE` |
| `automatic_single_surface` | `*CONTACT_AUTOMATIC_SINGLE_SURFACE` |
| `eroding_surface_to_surface` | `*CONTACT_ERODING_SURFACE_TO_SURFACE` |
| `forming_surface_to_surface` | `*CONTACT_FORMING_SURFACE_TO_SURFACE` |
| (기타 직접 입력) | `*CONTACT_<입력값>` (대문자 변환) |

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


**표 24-2. matdb 구조 카드 타입 — MAT_ELASTIC, MAT_024, MAT_RIGID 등 지원 카드 목록.**

| YAML 값 | LS-DYNA 키워드 | 용도 |
|---|---|---|
| `auto` | `AUTOMATIC_SURFACE_TO_SURFACE` | 범용 |
| `tied` | `TIED_SURFACE_TO_SURFACE` | 접합 |
| `mortar` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` | 고정밀 |
| `single` | `AUTOMATIC_SINGLE_SURFACE` | 자기접촉 |
| `eroding` | `ERODING_SURFACE_TO_SURFACE` | 요소 파괴 |
| `forming` | `FORMING_SURFACE_TO_SURFACE` | 성형 해석 |

#### detect 옵션


**표 25-1. contact 접촉 type 값 목록 — YAML type 키워드와 LS-DYNA *CONTACT_* 키워드 대응.**

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


**표 25-2. contact modify 수정 가능 필드 — Card 1/2/A/C 필드명과 대응하는 LS-DYNA 필드.**

| 키 | 필드 | 설명 |
|---|---|---|
| `soft` | SOFT | 소프트 제약 (0/1/2) |
| `sofscl` | SOFSCL | SOFT 스케일 |
| `depth` | DEPTH | 검색 깊이 (0~45) |
| `sbopt` | SBOPT | 세그먼트 기반 옵션 |

#### Card B (두께)


**표 25-3. contact Optional Card 지원 목록 — A~G 카드별 주요 파라미터와 기본값.**

| 키 | 필드 | 설명 |
|---|---|---|
| `penmax` | PENMAX | 최대 관통량 |
| `thkopt` | THKOPT | 두께 옵션 |
| `shlthk` | SHLTHK | 셸 두께 고려 |

#### Card C (간격/에지)


**표 26-1. load 유형 목록 — 지원하는 하중 종류와 각 하중의 적용 대상(노드/파트/세그먼트).**

| 키 | 필드 | 설명 |
|---|---|---|
| `igap` | IGAP | 간격 처리 |
| `ignore` | IGNORE | 관통 무시 |

> **카드 의존성**: Card G를 지정하면 A~F가 자동 포함 (LS-DYNA 고정폭 카드 순서 요구).

---

<!-- END MANUAL EXCERPT -->
