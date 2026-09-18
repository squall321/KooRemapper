# ale — Lagrangian → ALE converter (§35)

Source: [ale.cpp](../../src/commands/ale.cpp)
Manual: [`KooRemapper_Manual.md`#35-ale--ale-변환](../../docs/KooRemapper_Manual.md#35-ale--ale-변환)


## Synopsis

```
KooRemapper ale <args>
```

## What it does

14 presets: gas/liquid/explosive/vacuum. Auto-inserts `*SECTION_SOLID` ELFORM change, `*HOURGLASS` IHQ=3, `*CONTROL_ALE`, `*ALE_MULTI-MATERIAL_GROUP`, `*ALE_REFERENCE_SYSTEM_GROUP` (PRTYPE=4), `*CONSTRAINED_LAGRANGE_IN_SOLID` (FSI), `*INITIAL_DETONATION` (HE). Shared SECID detection → new section created. Unit: t/mm/s → MPa.

## Key references

- [[lsdyna/ale#ALE keywords in KooRemapper]]
- [[lsdyna/eos#LS-DYNA EOS (equation of state) in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §35. ale — ALE 변환._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
지정 solid 파트를 ALE(Arbitrary Lagrangian-Eulerian)로 변환합니다.
14종 재료 프리셋과 커스텀 번들 파일을 지원합니다.

### 사용법

```bash
KooRemapper.exe ale <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: ale_model.k
ale_parts:                 # 변환 대상 파트 (필수)
  - pid: 5
    material: air          # 프리셋 이름 또는 커스텀 .k 번들 경로
  - pid: 6
    material: water
fsi_pids: [1, 2, 3]        # FSI 라그랑지안 파트 (선택)
elform: 11                 # ALE ELFORM (11=multi-mat, 12=single, 기본 11)
# dct/nadv/meth (CONTROL_ALE), ctype/pfac (FSI), detonation (tnt/c4) 등 선택 옵션
```

> **v1.8.0 정정**: config 키는 `ale_parts`(각 항목 `{pid, material}`) / `fsi_pids` 입니다(help·`examples/ale`. 구버전의 `parts`/`preset`/`lagrangian_pids` 정정). `fsi_pids` 는 최상위 리스트이며(파트별 아님), 폭발물 기폭점은 최상위 `detonation: {pid, x, y, z, lt}` 로 지정합니다.

### 재료 프리셋 (14종)


**표 35-1. ale 재료 프리셋 — 분류별 프리셋과 MAT·EOS.**

| 분류 | 프리셋 | MAT | EOS |
|------|--------|-----|-----|
| 기체 | air, nitrogen, argon | MAT_NULL | EOS_LINEAR_POLYNOMIAL |
| 액체 | water, electrolyte, gasoline, oil, coolant, resin, tim, silicone | MAT_NULL | EOS_GRUNEISEN |
| 폭발물 | tnt, c4 | MAT_HIGH_EXPLOSIVE_BURN | EOS_JWL |
| 진공 | vacuum | MAT_VACUUM | — |

### 자동 삽입 카드

- `*SECTION_SOLID` ELFORM 변경
- `*HOURGLASS` (IHQ=3)
- `*CONTROL_ALE`
- `*ALE_MULTI-MATERIAL_GROUP`
- `*ALE_REFERENCE_SYSTEM_GROUP` (PRTYPE=4)
- `*CONSTRAINED_LAGRANGE_IN_SOLID` (FSI)
- `*INITIAL_DETONATION` (폭발물 전용)

### 단위 체계
t/mm/s → MPa

---

<!-- END MANUAL EXCERPT -->
