# relax — Dynamic Relaxation setup (§31)

Source: [relax.cpp](../../src/commands/relax.cpp)
Manual: [`KooRemapper_Manual.md`#31-relax--dynamic-relaxation-설정](../../docs/KooRemapper_Manual.md#31-relax--dynamic-relaxation-설정)


## Synopsis

```
KooRemapper relax <args>
```

## What it does

5-level preset. Overrides: nrcyck/drtol/drfctr/tssfdr/irelal/edttl. Inserts `*CONTROL_DYNAMIC_RELAXATION`.

## Key references

- [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §31. relax — Dynamic Relaxation 설정._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
초기 응력이 적용된 모델을 Dynamic Relaxation으로 평형 상태까지 릴렉세이션합니다.

### 사용법

```bash
KooRemapper.exe relax <config.yaml>
```

### YAML 형식

```yaml
model: wrapped_model.k
output: relaxed_model.k
level: 2               # 1(빠름) ~ 5(보수적), 기본=2
mode: explicit          # explicit(IDRFLG=1) | implicit(IDRFLG=5)
drterm: 100.0           # DR 종료 시간 (0=무한대)
endtime: 1.0            # DR 후 실제 해석 종료 시간
d3drlf: true            # DATABASE_BINARY_D3DRLF 출력
fix_shell_elform: false
strip: false            # true: 키워드 제거만

# 세부 오버라이드
# nrcyck/drtol/drfctr/tssfdr/irelal/edttl
```

### 레벨 프리셋 (5단계)


**표 37-1. database 프리셋 종류 — crash/drop/nve/all 프리셋별 출력 키워드 목록.**

| Lv | 이름 | NRCYCK | DRTOL | DRFCTR | TSSFDR | IRELAL | EDTTL |
|----|------|--------|-------|--------|--------|--------|-------|
| 1 | 빠름 | 500 | 0.010 | 0.990 | 0.95 | 0 | 0.04 |
| 2 | 표준 | 250 | 0.001 | 0.995 | 0.90 | 0 | 0.04 |
| 3 | 안정 | 100 | 0.001 | 0.998 | 0.80 | 0 | 0.04 |
| 4 | 보수 | 50 | 1e-4 | 0.999 | 0.67 | 1 | 0.01 |
| 5 | 최대 | 25 | 1e-5 | 0.999 | 0.50 | 1 | 0.001 |

### 모드


**표 39-1. assemble 오퍼레이션 목록 — type 필드로 지정 가능한 전체 오퍼레이션과 주요 파라미터.**

| mode | IDRFLG | 설명 |
|------|--------|------|
| explicit | 1 | 명시적 DR — 속도 감쇠로 운동에너지 소산 |
| implicit | 5 | 암시적 초기화 — 암시적 솔버로 평형 도달 |

### strip 모드 (`strip: true`)

`*CONTROL_DYNAMIC_RELAXATION`, `*DATABASE_BINARY_D3DRLF`를 제거합니다.

---

<!-- END MANUAL EXCERPT -->
