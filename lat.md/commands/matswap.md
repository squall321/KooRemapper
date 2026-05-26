# matswap — material bundle parameter swap (§23)

Source: [matswap.cpp](../../src/commands/matswap.cpp), [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp) (mw_*)
Manual: [`KooRemapper_Manual.md`#23-matswap--재료-번들-교체](../../docs/KooRemapper_Manual.md#23-matswap--재료-번들-교체)


## Synopsis

```
KooRemapper matswap <args>
```

## What it does

Replaces a bundle of materials (with `*PARAMETER` definitions) by PID match. ID type auto-detected by name prefix (`HGID/LCID/SECID/MID/PID`). Output has resolved numbers — no `*PARAMETER` blocks remain.

## Key references

- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]
- bundle examples: `examples/matswap/`

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §23. matswap — 재료 번들 교체._

<!-- BEGIN MANUAL EXCERPT -->



`*MAT_*`, `*HOURGLASS`, `*DEFINE_CURVE`, `*SECTION_*` 를 하나의 번들 파일로 묶어 특정 파트에 일괄 교체합니다.

### 사용법

```
KooRemapper matswap config.yaml
KooRemapper matswap <model.k> <bundle.k> <pid> <output.k>   # legacy
```

### YAML 포맷

```yaml
model: model.k
output: result.k
swaps:
  - bundle: rubber.k        # PID로 타겟
    pid: 1
  - bundle: foam.k
    pids: [2, 3, 5]         # 복수 PID
  - bundle: steel.k
    swap_all: true           # 모델 전체
  - bundle: mat_update.k
    mid: 5                   # MID로 타겟 (SECTION 교체 안 함)
    mids: [5, 6]             # 복수 MID
```

### 번들 파일 포맷 (`*.k`)

`*PARAMETER` 블록으로 ID를 파라미터화합니다.

```
*PARAMETER
I HGID1            1I LCID1            1
I MID1             1I SECID1           1
I PID1             1
*HOURGLASS_TITLE
Rubber_HG
    &HGID1         5    0.0500 ...
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
     &MID1 ...
*SECTION_SOLID_TITLE
   &SECID1 ...
*PART
...  &PID1   &SECID1   &MID1   0   &HGID1 ...
*END
```

### 파라미터 이름 접두사 규칙


**표 23-1. matswap 번들 파라미터 타입 — ID 접두어(HGID/LCID/SECID/MID/PID)별 자동 인식 규칙.**

| 접두사 | ID 종류 | 동작 |
|--------|---------|------|
| `HGID*` | Hourglass ID | 항상 새 ID |
| `LCID*` | Curve ID | 항상 새 ID |
| `SECID*` | Section ID | 항상 새 ID |
| `MID*` | Material ID | 고아 ID 재사용 가능 |
| `PID*` | Part ID | 무시 |

---

<!-- END MANUAL EXCERPT -->
