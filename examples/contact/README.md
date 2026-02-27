# contact 예제

LS-DYNA 접촉 정의를 분석, 생성, 변환, 수정, 삭제, 자동 감지하는 예제 모음.

---

## 파일 구성

| 파일 | 설명 |
|------|------|
| `model.k` | 3-파트 HEX8 모델 (Left/Center/Right, 2개 기존 접촉) |
| `01_analyze.yaml` | 접촉 분석 (읽기 전용 리포트) |
| `02_create_part.yaml` | Part ID로 접촉 생성 (SSTYP=3) |
| `03_create_segment.yaml` | 외곽면 추출 → SET_SEGMENT 접촉 (SSTYP=0) |
| `04_create_facing.yaml` | facing 필터 — 마주보는 면만 추출 (tied 안전) |
| `05_convert_facing.yaml` | 기존 접촉을 segment로 변환 + facing 필터 |
| `06_modify.yaml` | 기존 접촉 파라미터 수정 (마찰, SOFT 등) |
| `07_remove.yaml` | 접촉 삭제 |
| `08_detect_pid.yaml` | 명시적 PID 간 접촉 자동 감지 |
| `09_detect_all.yaml` | 전체 파트 간 자동 감지 (scope: all) |
| `10_detect_keyword.yaml` | 키워드 기반 파트 선택 감지 (include/exclude) |
| `11_detect_optcards.yaml` | detect + 세부 옵션 (Card A~C) |
| `12_multi_action.yaml` | 복합 워크플로우 (삭제→감지→수정) |
| `13_detect_skip.yaml` | skip_existing: 기존 tied 쌍 건너뛰기 |
| `14_detect_subtract.yaml` | subtract_existing: tied 세그먼트 차집합 |

---

## 실행 방법

```bash
KooRemapper contact 01_analyze.yaml
KooRemapper contact 02_create_part.yaml
KooRemapper contact 03_create_segment.yaml
KooRemapper contact 04_create_facing.yaml
KooRemapper contact 05_convert_facing.yaml
KooRemapper contact 06_modify.yaml
KooRemapper contact 07_remove.yaml
KooRemapper contact 08_detect_pid.yaml
KooRemapper contact 09_detect_all.yaml
KooRemapper contact 10_detect_keyword.yaml
KooRemapper contact 11_detect_optcards.yaml
KooRemapper contact 12_multi_action.yaml
KooRemapper contact 13_detect_skip.yaml
KooRemapper contact 14_detect_subtract.yaml
```

---

## 예제 설명

### 01 - analyze (접촉 분석)

```yaml
contacts:
  - action: analyze
```

기존 접촉 현황을 리포트한다. 수정 없이 contact_index 확인용.

---

### 02 - create (Part ID)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1 }
    master: { pid: 3 }
    friction: 0.3
    soft: 2
```

PID 직접 지정 (SSTYP=3). 가장 간단한 접촉 생성.

---

### 03 - create (segment 추출)

```yaml
contacts:
  - action: create
    type: automatic_surface_to_surface
    slave:  { pid: 1, as_segment: true }
    master: { pid: 2, as_segment: true }
```

파트의 전체 외곽면을 SET_SEGMENT로 추출 → SSTYP=0 접촉 생성.

---

### 04 - create (facing 필터)

```yaml
contacts:
  - action: create
    type: tied_surface_to_surface
    slave:  { pid: 1, as_segment: true, facing: true }
    master: { pid: 2, as_segment: true, facing: true }
    tolerance: 0.1
    normal_angle: 30
```

`facing: true` → detect 알고리즘으로 마주보는 면만 추출.
얇은 파트에서 반대면이 tied에 포함되는 문제를 방지한다.

- `normal_angle: 30` (보수적) → 정면 대향만
- `normal_angle: 45` (기본) → 약간 기울어진 면 포함
- `normal_angle: 80` (관대) → 비스듬히 닿는 면까지 포함

---

### 05 - convert (facing 필터)

```yaml
contacts:
  - action: convert
    contact_index: 0
    slave_to: segment
    master_to: segment
    facing: true
    tolerance: 0.1
```

기존 part→part 접촉을 segment→segment로 변환하되, 마주보는 면만 추출.
tied 변환에 필수.

---

### 06 - modify (파라미터 수정)

```yaml
contacts:
  - action: modify
    contact_index: 0
    friction: 0.5
    soft: 2
    depth: 35
    shlthk: 1
```

기존 접촉의 Card 2 / Optional Card A~G 값을 in-place 수정.
SSTYP에 무관하게 동작 (segment든 part든 OK).

---

### 07 - remove (접촉 삭제)

```yaml
contacts:
  - action: remove
    contact_index: 1
```

해당 인덱스의 접촉 블록 전체를 삭제.

---

### 08 - detect (명시적 PID)

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

두 파트 사이의 맞닿는 세그먼트를 Spatial Hash Grid으로 고속 검출.
`auto_create: true` → SET_SEGMENT + CONTACT 자동 생성.

---

### 09 - detect (scope: all)

```yaml
contacts:
  - action: detect
    scope: all
    tolerance: 0.1
    auto_create: true
    friction: 0.15
```

모든 파트 쌍을 한 번에 검출. Global Grid로 O(N) 처리.

---

### 10 - detect (키워드 선택)

```yaml
contacts:
  - action: detect
    include: [Left]
    tolerance: 0.1
    auto_create: true
    contact_type: tied
```

파트 이름에 "Left"가 포함된 파트만 대상으로 감지.
`exclude` 키워드로 제외도 가능.

---

### 11 - detect + 세부 옵션

```yaml
contacts:
  - action: detect
    scope: all
    auto_create: true
    friction: 0.15
    fd: 0.10
    soft: 2
    depth: 35
    penmax: 0.5
    shlthk: 1
    igap: 2
```

detect의 auto_create에서도 Card A~G 전체 56개 필드를 지정할 수 있다.

---

### 12 - 복합 워크플로우

```yaml
contacts:
  - action: remove
    contact_index: 1
  - action: detect
    scope: all
    auto_create: true
    contact_type: mortar
  - action: modify
    contact_index: 0
    friction: 0.4
```

여러 액션을 순서대로 실행. 삭제 → 자동 감지 → 수정을 한 YAML에서 처리.

---

### 13 - detect + skip_existing (쌍 단위 중복 제거)

```yaml
contacts:
  - action: detect
    scope: all
    auto_create: true
    skip_existing: tied     # tied가 있는 쌍은 건너뜀
```

PID 2↔3은 기존 TIED가 있으므로 건너뛰고, PID 1↔2만 일반 접촉 생성.

- `skip_existing: tied` → TIED 접촉이 있는 쌍만 skip
- `skip_existing: all` → 어떤 접촉이든 있으면 skip

---

### 14 - detect + subtract_existing (세그먼트 차집합)

```yaml
contacts:
  - action: detect
    scope: all
    auto_create: true
    subtract_existing: true
```

PID 2↔3의 tied 세그먼트를 전체 접촉면에서 빼고 나머지만 일반 접촉으로 생성.
하나의 파트 쌍이 일부만 접착(tied)되고 나머지는 슬라이딩인 경우에 사용.
이 테스트 모델에서는 전체가 tied이므로 차집합이 0개 → skip.

---

## 테스트 모델 구조

```
model.k: 3 HEX8 parts (1×1×1 cubes), 공유 노드 접촉면
  PID 1 (Part_1_Left)   : x=[0,1]
  PID 2 (Part_2_Center) : x=[1,2]
  PID 3 (Part_3_Right)  : x=[2,3]

  기존 접촉:
    [0] *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (PID 1↔2, FS=0.2)
    [1] *CONTACT_TIED_SURFACE_TO_SURFACE      (PID 2↔3, FS=0)
```

---

## contact_type 프리셋

| 약칭 | LS-DYNA 키워드 |
|------|----------------|
| `auto` | `AUTOMATIC_SURFACE_TO_SURFACE` |
| `tied` | `TIED_SURFACE_TO_SURFACE` |
| `mortar` | `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR` |
| `tied_mortar` | `TIED_SURFACE_TO_SURFACE_MORTAR` |
| `single` | `AUTOMATIC_SINGLE_SURFACE` |
| `eroding` | `ERODING_SURFACE_TO_SURFACE` |
| `forming` | `FORMING_SURFACE_TO_SURFACE` |

약칭에 없는 값은 그대로 대문자 변환: `forming_one_way_surface_to_surface` → `*CONTACT_FORMING_ONE_WAY_SURFACE_TO_SURFACE`
