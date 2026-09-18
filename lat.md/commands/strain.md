# strain — strain reporting (§10)

Source: [main.cpp](../../src/main.cpp), [[modules/analysis#Module: src/analysis/]]
Manual: [`KooRemapper_Manual.md`#10-strain--변형률-계산](../../docs/KooRemapper_Manual.md#10-strain--변형률-계산)


## Synopsis

```
KooRemapper strain <args>
```

## What it does

Reports per-element strain (engineering, Green-Lagrange, principal, von Mises, volumetric). No K-file output by default; CSV/console.

## Key references

- [[theory/strain-tensor#Strain tensor]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §10. strain — 변형률 계산._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
**기준 형상(reference)**과 **변형 형상(deformed)** 메시 쌍 간의 변형률을 계산하여
CSV 파일로 출력합니다.

### 사용법

```bash
KooRemapper.exe strain <ref_mesh.k> <def_mesh.k> <output.csv> [--type engineering|green|log]
```

### 파라미터


**표 10-1. strain 인자 — 기준·변형 메시, 출력 CSV, 변형률 유형 옵션.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `ref_mesh.k` | 기준 형상 메시 (입력) | — |
| `def_mesh.k` | 변형 형상 메시 (입력) | — |
| `output.csv` | 변형률 결과 CSV (출력) | — |
| `--type` | 변형률 계산 방식 | `engineering` |

### 변형률 유형


**표 10-2. strain 변형률 유형 — engineering·green·log 정의.**

| 유형 | 설명 |
|------|------|
| `engineering` | 공학 변형률 (소변형 가정) |
| `green` | Green-Lagrange 변형률 (대변형, 비선형 항 포함) |
| `log` | 로그 변형률 (진변형률, 대변형) |

### 출력

`output.csv` 는 **헤더 1줄 + 요소당 1줄, 11열** 입니다(확인).

```
ElementID,exx,eyy,ezz,exy,eyz,exz,VonMises,Volumetric,MaxShear,Jacobian
```

**표 10-3. strain 출력 CSV 열 구성 — 11열의 각 열이 담는 값.**

| 열 | 내용 |
|---|---|
| `ElementID` | 요소 ID |
| `exx`·`eyy`·`ezz`·`exy`·`eyz`·`exz` | 변형률 6성분 |
| `VonMises` | 등가(von Mises) 변형률 |
| `Volumetric` | 체적 변형률 |
| `MaxShear` | 최대 전단 변형률 |
| `Jacobian` | 요소 자코비안 |

> **옵션 이름 주의**: `strain` 의 변형률 유형 옵션은 **`--type`** 입니다(`--strain` 은 `[ERROR] Unknown option: --strain`).
> 반대로 `prestress` 는 **`--strain`** 이고 `engineering`/`green` 두 값만 받습니다([§6](#6-prestress--초기-응력변형률-계산)).
> 모르는 값은 `[ERROR] Unknown --type 'xxx' (allowed: engineering, green, log)` 로 종료 코드 1 입니다.

---

<!-- END MANUAL EXCERPT -->
