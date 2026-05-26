# convert — TET10/HEX20/QUAD8/TRIA6 promotion (§16)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#16-convert--2차-요소-변환](../../docs/KooRemapper_Manual.md#16-convert--2차-요소-변환)


## Synopsis

```
KooRemapper convert <args>
```

## What it does

Dispatched by `convertType` field; mid-edge nodes interned in `edgeMidNodeMap_` (member — persists across calls so multi-op runs share mid-side nodes). Auto-updates SECID→ELFORM via `solidSectionElforms_` / `shellSectionElforms_`.

## Key references

- [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]]
- [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §16. convert — 2차 요소 변환._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
1차 요소(TET4, HEX8, QUAD4, TRIA3)를 **2차 요소**로 변환합니다.

### 사용법

```bash
KooRemapper.exe convert <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: converted
target_pid: 0            # 0 = 전체 파트
convert_type: tet10      # tet10 | hex20 | quad8 | tria6
elform: 0                # ELFORM 지정 (0=자동)
```

### 자동 ELFORM 매핑


**표 17-1. refine 세분화 비율 — 요소 유형별 1:2, 1:3 세분화 시 생성 요소 수 비교.**

| convertType | 원본 요소 | 변환 요소 | 기본 ELFORM |
|-------------|-----------|-----------|-------------|
| tet10 | TET4 | TET10 | 17 |
| hex20 | HEX8 | HEX20 | 23 |
| quad8 | QUAD4 | QUAD8 | 23 |
| tria6 | TRIA3 | TRIA6 | 24 |

---

<!-- END MANUAL EXCERPT -->
