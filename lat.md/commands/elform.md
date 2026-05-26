# elform — ELFORM remap (§18)

Source: [standalone_ops.cpp](../../src/commands/standalone_ops.cpp)
Manual: [`KooRemapper_Manual.md`#18-elform--요소-공식-변경](../../docs/KooRemapper_Manual.md#18-elform--요소-공식-변경)


## Synopsis

```
KooRemapper elform <args>
```

## What it does

Changes `*SECTION_*` ELFORM with alias support (solid: hex/tet/…; shell: belytschko/hughes-liu/…). Splits shared SECID if only some parts target it.

## Key references

- [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §18. elform — 요소 공식 변경._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
기존 요소의 **ELFORM** 번호를 변경합니다.

### 사용법

```bash
KooRemapper.exe elform <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: modified
target_pid: 0
target_elform: "2"       # 숫자 또는 별칭
```

### 고체 요소 별칭


**표 19-1. disconnect 모드 — full/czm/mefem 세 가지 노드 분리 모드와 생성 키워드.**

| 별칭 | ELFORM | 설명 |
|------|--------|------|
| `constant_stress` | 1 | 상수 응력 (UR) |
| `fully_integrated` | 2 | 완전 적분 |
| `tet4` | 13 | 4절점 사면체 |
| `tet10` | 17 | 10절점 사면체 |
| `hex20` | 23 | 20절점 헥사 |

### 셸 요소 별칭


**표 20-1. IGA 생성 파일 — 파트별 IGA NURBS 박스 파일과 메인 파일의 *INCLUDE 구조.**

| 별칭 | ELFORM |
|------|--------|
| `belytschko_tsay` | 2 |
| `hughes_liu` | 1 |
| `fully_integrated_shell` | 16 |
| `quad8` | 23 |
| `tria6` | 24 |

---

<!-- END MANUAL EXCERPT -->
