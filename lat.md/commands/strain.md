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


**표 8-1. generate-var 두께 분포 정의 — 영역(zone)별 lc와 두께를 지정하여 변밀도 메시를 생성한다.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `ref_mesh.k` | 기준 형상 메시 (입력) | — |
| `def_mesh.k` | 변형 형상 메시 (입력) | — |
| `output.csv` | 변형률 결과 CSV (출력) | — |
| `--type` | 변형률 계산 방식 | `engineering` |

### 변형률 유형


**표 9-1. unfold 파라미터 — 굽힘 메시 전개 시 호(arc), 너비(width), 두께(thickness) 축 방향 설정.**

| 유형 | 설명 |
|------|------|
| `engineering` | 공학 변형률 (소변형 가정) |
| `green` | Green-Lagrange 변형률 (대변형, 비선형 항 포함) |
| `log` | 로그 변형률 (진변형률, 대변형) |

### 출력

- `output.csv`: 요소별 6개 변형률 성분 (εxx, εyy, εzz, εxy, εyz, εxz)

---

<!-- END MANUAL EXCERPT -->
