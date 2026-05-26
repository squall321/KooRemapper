# implicit — Explicit → Implicit converter (§29)

Source: [implicit.cpp](../../src/commands/implicit.cpp)
Manual: [`KooRemapper_Manual.md`#29-implicit--explicitimplicit-변환](../../docs/KooRemapper_Manual.md#29-implicit--explicitimplicit-변환)


## Synopsis

```
KooRemapper implicit <args>
```

## What it does

8-level spectrum (1=aggressive → 8=buckling/snap-through). Removes DR/BULK/D3DRLF, modifies TIMESTEP/TERMINATION, inserts `*CONTROL_IMPLICIT_*`. Level 5+ adds STABILIZATION, 6+ MUMPS, 8 arc-length. Overrides: dctol/ectol/dt0/dtmax/nsolvr/kfail/rctol/lsolvr/stab/stab_scale/arc_length.

## Key references

- [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §29. implicit — Explicit→Implicit 변환._

<!-- BEGIN MANUAL EXCERPT -->



Explicit LS-DYNA K 파일을 Implicit 해석 설정으로 변환합니다.

### 사용법

```
KooRemapper implicit config.yaml
```

### YAML 포맷

```yaml
model: explicit.k
output: implicit.k
mode: static          # static(IMASS=0) | dynamic(IMASS=1)
level: 2              # 1(공격적) ~ 8(좌굴/스냅스루)
endtime: 1.0
strip: false          # true: 키워드 제거만 (삽입 없음)

# 세부 오버라이드 (생략 시 level 기본값)
# dctol/ectol/dt0/dtmax/nsolvr/kfail/rctol/lsolvr/stab/stab_scale/arc_length
# fix_shell_elform/keep_dr_curves
```

### 레벨 스펙트럼

#### Table 1 — 비선형 솔버 & 수렴 허용치


**표 29-2. implicit 오버라이드 파라미터 — dt0, dtmax, nsolvr 등 사용자 정의 시 기본값을 덮어쓰는 파라미터.**

| Lv | 이름 | NSOLVR | ILIMIT | MAXREF | ITEOPT | KFAIL | DCTOL | ECTOL | LSTOL | RCTOL |
|----|------|--------|--------|--------|--------|-------|-------|-------|-------|-------|
| 1 | 공격적 | 12 | 11 | 10 | 11 | 0 | 0.0050 | 0.0500 | 0.90 | off |
| 2 | 표준 | 12 | 11 | 15 | 11 | 0 | 0.0010 | 0.0100 | 0.90 | off |
| 3 | 안정 | 12 | 15 | 20 | 11 | 0 | 0.0010 | 0.0100 | 0.95 | off |
| 4 | 수렴우선 | -2 | 20 | 25 | 11 | 3 | 0.0010 | 0.0100 | 0.95 | off |
| 5 | 강건 | -2 | 25 | 30 | 15 | 5 | 0.0010 | 0.0050 | 0.99 | off |
| 6 | 고강건 | -2 | 30 | 40 | 15 | 8 | 0.0005 | 0.0020 | 0.99 | 0.1 |
| 7 | 최대안정 | -2 | 40 | 50 | 20 | 15 | 0.0001 | 0.0010 | 0.99 | 0.01 |
| 8 | 좌굴/스냅스루 | 7* | 40 | 50 | 20 | 15 | 0.0001 | 0.0010 | 0.99 | 0.01 |

#### Table 2 — 시간 스텝 & 활성화 기능 (T = endtime)


**표 30-1. modal 해석 파라미터 — 모드 수, 주파수 범위, 고유값 해석 방법(eigmth) 코드 목록.**

| Lv | DT0 | DTMAX | DTMIN | LSOLVR | STAB | ARC-LENGTH |
|----|-----|-------|-------|--------|------|------------|
| 1 | T/100 | T/20 | −T/1000 | 7 (기본) | off | off |
| 2 | T/500 | T/100 | −T/10000 | 7 (기본) | off | off |
| 3 | T/1000 | T/200 | −T/10000 | 7 (기본) | off | off |
| 4 | T/2000 | T/500 | −T/100000 | 7 (기본) | off | off |
| 5 | T/5000 | T/1000 | −T/100000 | 7 (기본) | **ON** | off |
| 6 | T/10000 | T/2000 | −T/100000 | **30 (MUMPS)** | ON | off |
| 7 | T/50000 | T/10000 | −T/1000000 | 30 (MUMPS) | ON | off |
| 8 | T/50000 | T/10000 | −T/1000000 | 30 (MUMPS) | ON | **ON (Crisfield)** |

### 처리 파이프라인

#### 제거 (항상)
- `*CONTROL_DYNAMIC_RELAXATION`
- `*CONTROL_BULK_VISCOSITY`
- `*DATABASE_BINARY_D3DRLF`

#### 수정
- `*CONTROL_TIMESTEP` → TSSFAC=0.90, DT2MS=0.0
- `*CONTROL_TERMINATION` → endtim 갱신

#### 삽입
- `*CONTROL_IMPLICIT_GENERAL` / `_DYNAMICS` / `_SOLUTION` / `_AUTO`
- Level 5+: `*CONTROL_IMPLICIT_STABILIZATION`
- Level 6+: `*CONTROL_IMPLICIT_SOLVER` (MUMPS)
- Level 8: Arc-length (Crisfield)

### mode: static vs dynamic


**표 35-1. ALE 프리셋 목록 (14종) — 기체/액체/폭약/진공 프리셋별 적용 재료 모델과 상태방정식.**

| 파라미터 | static (준정적) | dynamic (구조동역학) |
|----------|----------------|-------------------|
| IMASS | 0 | 1 |
| GAMMA | 0.5 | 0.6 |
| BETA | 0.25 | 0.30 |

### strip 모드 (`strip: true`)

`*CONTROL_IMPLICIT_*` 관련 키워드 10종을 모두 제거하고, 새 키워드는 삽입하지 않습니다.
level/mode 파라미터 검증을 건너뜁니다.

---

<!-- END MANUAL EXCERPT -->
