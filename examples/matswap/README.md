# matswap 예제

재료 번들(Material Bundle)을 LS-DYNA 모델의 특정 파트에 교환(Swap)하는 예제 모음.
MAT + HOURGLASS + DEFINE_CURVE + SECTION 전체 세트를 자동으로 교환하며,
ID 충돌 방지, 고아(orphan) 카드 자동 제거, 복수 파트 동시 교환을 지원한다.

---

## 파일 구성

| 파일 | 설명 |
|------|------|
| `two_cubes.k` | 2-파트 HEX8 모델 (Steel PID=1, Steel PID=2) |
| `rubber.k` | Rubber 재료 번들 (`*PARAMETER` + MAT_181 + HOURGLASS + DEFINE_CURVE + SECTION) |
| `01_single_pid.yaml` | 단일 PID 교환 |
| `02_multiple_pids.yaml` | 복수 PID 동시 교환 |
| `03_swap_all.yaml` | 전체 파트 교환 (`swap_all: true`) |
| `04_assemble_integration.yaml` | assemble 워크플로우 내 matswap 통합 |

---

## 실행 방법

```bash
# 독립 YAML 커맨드 (matswap)
KooRemapper matswap 01_single_pid.yaml
KooRemapper matswap 02_multiple_pids.yaml
KooRemapper matswap 03_swap_all.yaml

# assemble 워크플로우 통합
KooRemapper assemble 04_assemble_integration.yaml

# 레거시 positional 방식 (하위 호환)
KooRemapper matswap two_cubes.k rubber.k 1 legacy_result.k
```

---

## 예제 설명

### 01 - 단일 PID 교환

```yaml
model: two_cubes.k
output: 01_single_result.k
swaps:
  - bundle: rubber.k
    pid: 1
```

PID=1의 Steel 재료를 Rubber로 교환.
- PID=2는 기존 Steel 그대로 유지
- MID=1 (Steel_Top) orphan → 제거, Rubber MID 재사용
- 새 HOURGLASS, SECTION 자동 추가

---

### 02 - 복수 PID 동시 교환

```yaml
model: two_cubes.k
output: 02_multiple_result.k
swaps:
  - bundle: rubber.k
    pids: [1, 2]
```

PID=1, PID=2 모두 동일한 Rubber bundle로 교환.
- 두 파트의 기존 Steel 카드 모두 orphan 확인 후 제거
- Rubber 카드 **1세트만** 삽입, 두 PART가 동일 MID/SECID/HGID 공유
- 메모리/파일 크기 최적화

---

### 03 - 전체 파트 교환

```yaml
model: two_cubes.k
output: 03_swapall_result.k
swaps:
  - bundle: rubber.k
    swap_all: true
```

모델 내 모든 PART를 자동 검색하여 Rubber로 교환.
- PID 목록을 수동으로 지정할 필요 없음
- 파트 수가 많은 대형 모델에서 유용

---

### 04 - assemble 통합

```yaml
base_model: two_cubes.k
output: 04_assemble_result
operations:
  - type: matswap
    bundle: rubber.k
    pid: 1
  - type: matswap
    bundle: rubber.k
    pid: 2
```

`assemble` YAML 내에서 `type: matswap`으로 사용.
- 다른 operation(replace, bend, indent 등)과 순서대로 결합 가능
- 각 operation이 독립적으로 ID를 할당 → 두 파트가 별도 Rubber 인스턴스 보유

---

## 재료 번들 형식 (rubber.k)

```k
*PARAMETER
$# prmname   value
I HGID1            1I LCID1            1
I MID1             1I SECID1           1
I PID1             1
*HOURGLASS_TITLE
...
    &HGID1  ...
*DEFINE_CURVE_TITLE
...
    &LCID1  ...
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
...
     &MID1  ...  &LCID1  ...
*SECTION_SOLID_TITLE
...
   &SECID1  ...
*PART
...
     &PID1   &SECID1     &MID1  ...   &HGID1  ...
*END
```

**파라미터 명명 규칙** (ID 타입 자동 감지):

| 접두사 | ID 타입 | 재매핑 기준 |
|--------|---------|-------------|
| `HGID*` | Hourglass ID | 모델 max HGID + 1 |
| `LCID*` | Curve ID | 모델 max LCID + 1 |
| `SECID*` | Section ID | 모델 max SECID + 1 |
| `MID*` | Material ID | orphan이면 재사용, 아니면 max + 1 |
| `PID*` | Part ID | 재매핑 없음 (PART 카드 삽입 스킵) |

> **LS-DYNA 호환**: `*PARAMETER` 블록을 사용하므로 번들 파일을 LS-DYNA에서 직접 읽을 수 있음.
> matswap 출력 파일에는 `*PARAMETER` 없이 해결된 숫자값만 포함됨.

---

## ID 처리 로직

```
모델 로드
   ↓
타겟 PID 목록 확인 (pid/pids/swap_all)
   ↓
각 PART의 MID/SECID/HGID 조회
   ↓
Orphan 검사: 타겟 외 다른 PART가 사용하는지?
   ├─ Orphan → 기존 카드 제거
   └─ Shared → 기존 카드 유지 (다른 PART에서 계속 사용)
   ↓
번들 ID 재매핑 (모델 max ID + 1 기준)
   MID: orphan이고 단일 MID면 재사용
   ↓
번들 카드의 &VARNAME → 숫자로 resolve
   ↓
모든 타겟 PART 데이터 라인 업데이트
   ↓
resolve된 번들 카드 *END 앞에 삽입
```
