# prestress — reference → deformed strain/stress + dynain (§6)

Source: [main.cpp](../../src/main.cpp), [[modules/analysis#Module: src/analysis/]]
Manual: [`KooRemapper_Manual.md`#6-prestress--초기-응력변형률-계산](../../docs/KooRemapper_Manual.md#6-prestress--초기-응력변형률-계산)


## Synopsis

```
KooRemapper prestress reference.k deformed.k output.dynain
```

## What it does

Computes deformation gradient F per element, derives strain (engineering or Green-Lagrange), applies Hooke's law via [MaterialModel.cpp](../../src/analysis/MaterialModel.cpp), and emits `*INITIAL_STRESS_SOLID` to a dynain file via [DynainWriter.cpp](../../src/parser/DynainWriter.cpp).

Material priority: command-line `-mat` > K-file `*MAT_*` > built-in default.

## Key references

- [[theory/deformation-gradient#Deformation gradient F]]
- [[theory/stress-tensor#Stress tensor]]
- [[lsdyna/initial#LS-DYNA INITIAL cards in KooRemapper]]
- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §6. prestress — 초기 응력/변형률 계산._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
**기준 형상(reference)**과 **변형 형상(deformed)** 메시 쌍으로부터
각 요소의 초기 응력을 계산하여 LS-DYNA `*INITIAL_STRESS_SOLID` 형식으로 출력.

### 사용법

```bash
KooRemapper.exe prestress [options] <ref_mesh.k> <def_mesh.k> <output_prefix>

Options:
  --E <value>          영률 (K-파일 재료 카드 대체)
  --nu <value>         푸아송 비
  --strain engineering|green   변형률 계산 방식 (기본: green)
  --csv                CSV 형식 추가 출력
```

> **확인(2026-09-18)**: `--strain` 은 **`engineering` / `green` 두 값만** 받으며 기본값은 `green`(Green-Lagrange)입니다.
> `--strain log` 는 `[ERROR] Unknown --strain 'log' (allowed: engineering, green)` 와 함께 **종료 코드 1** 입니다.
> 로그(진) 변형률이 필요하면 `strain` 명령의 `--type log` 를 쓰세요([§10](#10-strain--변형률-계산)).
> `--E`/`--nu` 를 생략하면 K-파일 재료값이 쓰입니다.

### 변형률 계산

#### 공학 변형률 (Engineering Strain)

$$\varepsilon_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial x_j} + \frac{\partial u_j}{\partial x_i}\right)$$

#### Green-Lagrange 변형률

$$E_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial X_j} + \frac{\partial u_j}{\partial X_i} + \frac{\partial u_k}{\partial X_i}\frac{\partial u_k}{\partial X_j}\right)$$

#### 로그 변형률 (Logarithmic / True Strain) — `strain` 명령 전용

$$\varepsilon_{log} = \ln\left(\frac{L}{L_0}\right)$$

> **prestress 에서는 쓸 수 없습니다.** 이 정의는 `strain --type log`([§10](#10-strain--변형률-계산))에만 구현돼 있습니다.
> `prestress --strain log` 는 종료 코드 1 로 거절됩니다.

### 응력 계산 (선형 탄성, Hooke의 법칙)

라메 상수:

$$\lambda = \frac{E\nu}{(1+\nu)(1-2\nu)}, \quad \mu = \frac{E}{2(1+\nu)}$$

Cauchy 응력:

$$\sigma_{ij} = \lambda \varepsilon_{kk} \delta_{ij} + 2\mu \varepsilon_{ij}$$

### 출력
세 번째 인자 `<output>` 은 dynain 파일 경로입니다.
- `<output>`: `*INITIAL_STRESS_SOLID` 카드(dynain). `pre.k` 처럼 `.k` 로 끝나면 아래 메시 사본과 겹치지 않게 `pre.dynain` 으로 씁니다.
- `<output 에서 확장자를 뗀 이름>.k`: 변형 메시 사본 + 위 dynain `*INCLUDE`
- `<output 에서 확장자를 뗀 이름>.csv` (`--csv`): 요소별 변형률/응력 CSV. 재료(E·ν)를 찾지 못하면 dynain 대신 `<output>` 에 CSV 만 씁니다.

예: `KooRemapper prestress --E 210000 --nu 0.3 flat.k bent.k pre.dynain` → `pre.dynain` + `pre.k`

### 재료 우선순위
1. 명령행 `--E`, `--nu` 인자 (전체 오버라이드)
2. K-파일 내 `*MAT_ELASTIC` (파트별 자동 인식)

---

<!-- END MANUAL EXCERPT -->
