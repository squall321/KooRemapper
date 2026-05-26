# matdb — material DB lookup + replacement (§24)

Source: [matdb.cpp](../../src/commands/matdb.cpp)
Manual: [`KooRemapper_Manual.md`#24-matdb--재료-db-교체](../../docs/KooRemapper_Manual.md#24-matdb--재료-db-교체)


## Synopsis

```
KooRemapper matdb <args>
```

## What it does

Uses `materials/material_db.json` to replace `*MAT_*` cards. Auto-matches by title→name/tag substring (case-insensitive) or direct MID. Supports structural card type selection (MAT_ELASTIC/024/RIGID/…), optional thermal insertion (`*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` with TMID linkage). `match: "*"` is catch-all.

## Key references

- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]
- [[modules/commands#Module: src/commands/]] (stripQuotes)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §24. matdb — 재료 DB 교체._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
JSON 재료 데이터베이스(`material_db.json`)를 기반으로 모델의 `*MAT` 카드를 일괄 교체합니다.
파트 이름 자동 매칭 또는 직접 MID 지정을 지원합니다.

### 사용법

```bash
KooRemapper.exe matdb <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: result.k
database: materials/material_db.json
mat_type: MAT_024         # 구조 카드 유형 (기본)
thermal: false            # 열 재료 삽입 여부

materials:                # 개별 규칙 (선택)
  - match: "steel*"       # 파트 이름 패턴 매칭
    mat_type: MAT_ELASTIC
  - mid: 5                # 직접 MID 지정
    thermal: true
  - match: "*"            # catch-all 자동 매칭
```

### 매칭 규칙
- `match`: 파트 title과 DB의 name/tag 부분 문자열 매칭 (대소문자 무시)
- `mid`: 직접 재료 ID 지정
- `match: "*"`: 모든 미매칭 재료에 자동 매칭 시도

### 열 재료 삽입 (`thermal: true`)
- `*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` 자동 삽입
- TMID 링크 자동 연결

---

<!-- END MANUAL EXCERPT -->
