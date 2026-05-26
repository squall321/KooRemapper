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
parts:
  - pid: 5
    preset: air           # 프리셋 이름 또는 bundle 경로
    lagrangian_pids: [1, 2, 3]   # FSI 라그랑지안 파트
  - pid: 6
    preset: water
    lagrangian_pids: [1]
```

### 재료 프리셋 (14종)


**표 35. (표 설명 — 해당 명령어/기능의 파라미터 또는 옵션 목록)**

| 분류 | 프리셋 | MAT | EOS |
|------|--------|-----|-----|
| 기체 | air, nitrogen, argon | MAT_NULL | EOS_LINEAR_POLYNOMIAL |
| 액체 | water, electrolyte, gasoline, oil, coolant, resin, tim, silicone | MAT_NULL | EOS_GRUNEISEN |
| 폭발물 | tnt, c4 | MAT_HE_BURN | EOS_JWL |
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
