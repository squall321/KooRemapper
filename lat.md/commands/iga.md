# iga — IGA NURBS box generation (§20)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#20-iga--등기하해석-nurbs-박스-생성](../../docs/KooRemapper_Manual.md#20-iga--등기하해석-nurbs-박스-생성)


## Synopsis

```
KooRemapper iga <args>
```

## What it does

Generates `*ELEMENT_SOLID_NURBS_PATCH` into a per-PID include file `<output>_iga_p<pid>.k`. IGA and FE parts MUST use different MID. New PID/SECID/MID allocated from `++maxPartId_`/`++maxMaterialId_`.

## Key references

- [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]]
- [`IGA.txt`](../../docs/LSDyna/IGA.txt)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §20. iga — 등기하해석 NURBS 박스 생성._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
FE solid 파트를 **3D NURBS B-Spline 박스(trivariate)**로 래핑하여
LS-DYNA IGA(Isogeometric Analysis) 해석 가능하게 변환합니다.

### 사용법

```bash
KooRemapper.exe iga <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: iga_result
targets:
  - target_pid: 1
    element_size: 4.0       # NURBS 복셀 크기 (rr=rs=rt 공통)
    element_size_r: 2.0     # r방향 개별 지정 (0=element_size 사용)
    element_size_s: 2.0
    element_size_t: 4.0
    offset: -1.0            # bbox 확장량 (-1=auto)
    bbox_scale: 1.5         # 균일 배율
    bbox_scale_r: 2.0       # 축별 배율
    bbox_scale_s: 1.3
    bbox_scale_t: 1.0
    ir: 0                   # 0=reduced Gauss, 1=full Gauss
    styp: 4                 # LCP stabilization type
    tollg: 1.0e-3           # LCP threshold
    pr: 1                   # polynomial order (r/s/t)
    ps: 1
    pt: 1
    nisr: 1                 # 적분점 수 (r/s/t)
    niss: 1
    nist: 1
```

### offset 우선순위 (높→낮)

1. `bbox_scale_r/s/t` — 축별 배율
2. `bbox_scale` — 균일 배율
3. `offset ≥ 0` — 고정값
4. 기본값 — element_size per axis

### 생성 파일

- 메인 출력: `<output>.k` (원본 FE 유지 + `*INCLUDE`)
- IGA 파일: `<output>_iga_p{pid}.k` (파트별 별도)

> **MID 격리 규칙**: IGA 파트와 일반 FE 파트는 반드시 다른 MID를 사용해야 합니다.

---

<!-- END MANUAL EXCERPT -->
