# modal — natural frequency / modal analysis (§30)

Source: [modal.cpp](../../src/commands/modal.cpp)
Manual: [`KooRemapper_Manual.md`#30-modal--고유진동수모달-해석-변환](../../docs/KooRemapper_Manual.md#30-modal--고유진동수모달-해석-변환)


## Synopsis

```
KooRemapper modal <args>
```

## What it does

Inserts `*CONTROL_IMPLICIT_EIGENVALUE` + GENERAL/SOLUTION. Options: nmode(10), fmin(0), fmax(0), center(0), eigmth (2=Lanczos/101=MCMS/102=LOBPCG/103=FastLanczos), solver(7/30=MUMPS), fix_shell_elform, keep_dr_curves. Existing `*CONTROL_IMPLICIT_*` → WARNING + replace.

## Key references

- [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §30. modal — 고유진동수(모달) 해석 변환._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
LS-DYNA 모델을 모달 해석(고유진동수/고유모드) 설정으로 변환합니다.

### 사용법

```bash
KooRemapper.exe modal <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: modal.k
nmode: 10              # 추출 모드 수 (기본: 10)
fmin: 0.0              # 최소 주파수 (Hz)
fmax: 0.0              # 최대 주파수 (0=무제한)
center: 0.0            # 중심 주파수 (Lanczos shift)
eigmth: 2              # 고유치 방법
solver: 7              # 선형 솔버
fix_shell_elform: false
keep_dr_curves: false
strip: false           # true: 키워드 제거만
```

### 고유치 방법 (eigmth)


**표 36-1. stabilize 12단계 설정 — 단계별 누적 적용 안정화 옵션과 활성화 조건.**

| 값 | 방법 | 설명 |
|----|------|------|
| 2 | Lanczos | 기본, 범용 |
| 101 | MCMS | Multi-Component Mode Synthesis |
| 102 | LOBPCG | Locally Optimal Block PCG |
| 103 | FastLanczos | 고속 Lanczos |

### 삽입 키워드

- `*CONTROL_IMPLICIT_EIGENVALUE` — nmode, fmin, fmax, center, eigmth
- `*CONTROL_IMPLICIT_GENERAL` — IMFLAG=1
- `*CONTROL_IMPLICIT_SOLUTION` — solver 설정

### strip 모드 (`strip: true`)

`*CONTROL_IMPLICIT_EIGENVALUE`, `_GENERAL`, `_SOLUTION`, `_SOLVER`를 제거합니다.

---

<!-- END MANUAL EXCERPT -->
