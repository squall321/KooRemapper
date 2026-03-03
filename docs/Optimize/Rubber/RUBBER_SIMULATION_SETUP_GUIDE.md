# LS-DYNA Rubber Part Simulation Setup Guide

> **For AI Agents**: 고무 파트가 포함된 LS-DYNA 모델을 셋업할 때, 수렴 문제 없이 안정적으로 실행되도록 하는 실전 가이드.
> 300건 이상의 시뮬레이션(Ex03: 117건, Ex09: 143건, Ex10: 8건, Ex16: 56건)으로 검증됨.

---

## 0. 이 가이드를 적용하는 조건

아래 중 하나라도 해당되면 이 가이드의 규칙을 따라야 한다:

- 파트의 재료가 **고무, 엘라스토머, 실리콘, 가스켓, 부싱, O-ring** 등 초탄성 소재
- **Poisson비 > 0.49** (거의 비압축성)
- **예상 변형률 > 20%** (대변형)
- MAT_027, MAT_077, MAT_077_H, MAT_077_O, MAT_181 중 하나를 사용

---

## 1. Element Formulation 선택

### 1.1 규칙 (Tet4 메시 기준 — 실무 표준)

```
ELFORM=13  ← 유일한 권장값
```

| ELFORM | 이름 | 판정 | 근거 |
|--------|------|------|------|
| **13** | **1-point tet4** | **사용** | R²=0.90 (PR=0.49), 안정적, 빠름 |
| 10 | 1-point tet4 (legacy) | 가능 | EF13과 유사하나 EF13이 표준 |
| 15 | 4-point tet4 | 비권장 | mass scaling 3.7배 더 심함 (230% vs 62%) |
| 43 | ME-FEM tet4 | **금지** | locking ratio 28.8 (EF13의 3.2배 악화) |
| 41 | EFG-41 | **금지** | 60% 압축에서 timestep collapse |
| 60 | Cosserat tet4 | **금지** | NaN 즉시 발산 |

### 1.2 Hex8 메시가 가능한 경우 (단순 형상)

```
ELFORM=-1  ← fully integrated S/R hex8
또는
ELFORM=2   ← selective reduced hex8
```

- Hex8은 체적 잠김에 면역 → PR=0.4999도 안정적
- 단, 실무 복잡 형상에서는 hex 메싱이 불가능하므로 tet4가 기본

### 1.3 SECTION_SOLID 카드

```
*SECTION_SOLID
$    SECID    ELFORM       AET
         1        13         0
```

- SECTION_SOLID_EFG는 ELFORM=41/42 전용. Tet4(EF13)에서는 사용하지 않는다.

---

## 2. Poisson비 설정 — 가장 중요한 숫자

### 2.1 절대 규칙

```
PR ≤ 0.495  ← 반드시 지킬 것
```

| PR 값 | R² | Locking Ratio | 판정 |
|-------|-----|--------------|------|
| 0.490 | 0.90 | 1.0 (기준) | 안전 |
| **0.495** | **0.80** | **1.13** | **허용 가능** |
| 0.4999 | -24.7 | 8.87 | **절대 금지** |

### 2.2 왜 0.4999를 쓰면 안 되는가

- 실제 고무의 PR은 0.4995~0.49999이지만, FEA에서 PR=0.4999는 **수치적 재앙**
- 체적 탄성계수 K = 2G(1+ν)/3(1-2ν)에서 (1-2ν) → 0이므로 K → ∞
- Tet4의 1-point 적분은 이 무한대를 처리할 수 없음 (체적 잠김)
- **어떤 완화법(F-bar, TET13V, ME-FEM)도 PR=0.4999에서는 효과 없음** (56건 검증)

### 2.3 실무 대응

```
실제 고무 PR = 0.4995~0.49999
   ↓
시뮬레이션 PR = 0.490 ~ 0.495 로 설정
   ↓
비압축성은 BULK VISCOSITY가 보조적으로 처리
```

PR=0.490에서 0.495 사이의 차이는 결과에 미미 (Peak Fz 13% 차이).
PR=0.4999는 Peak Fz가 8.9배 폭증 → 완전히 비물리적.

---

## 3. Material Model 선택

### 3.1 의사결정 트리

```
실험 데이터(응력-변형률 곡선)가 있는가?
├── Yes → MAT_181 (tabulated) 또는 MAT_077/077_H (Yeoh/MR fitting)
└── No  → 전단 계수 G와 PR만 알고 있는가?
    ├── Yes → MAT_027 (Mooney-Rivlin)
    │         A = G/4, B = G/4 (균등 분배)
    └── No  → 영률 E만 알고 있는가?
        └── Yes → MAT_027, A = E/8, B = E/8 (ν≈0.5이면 G≈E/3)
```

### 3.2 MAT_027 (Mooney-Rivlin) — 물성 상수만 있을 때

```
*MAT_MOONEY-RIVLIN_RUBBER
$      MID       RHO        PR         N        NV         G      SIGF
         1  1.10E-09     0.495
$      C10       C01       C11       C20       C02       C30
    {A}       {B}
```

- A = C10 = G/4 (MPa), B = C01 = G/4 (MPa)
- RHO: ton/mm³ 단위 (고무 ≈ 1.0~1.3 × 10⁻⁹)
- PR: 0.490~0.495
- N=0 (Mooney-Rivlin 2항), G/SIGF = 0.0 (자동)

### 3.3 MAT_077_H (Hysteresis) — COR 제어 필요 시

#### 카드 순서 (반드시 이 순서)

```
Card 1: 기본 물성
Card 2: 시험 데이터 또는 TBHYS (PR < 0일 때만)
Card 3b: Mooney-Rivlin 계수 (N=0일 때)
Card 4: Prony 급수 (선택)
```

#### 완전한 예시

```
*MAT_HYPERELASTIC_RUBBER_TITLE
Rubber_077H
$ Card 1: 기본 물성
$      MID       RHO        PR         N        NV         G      SIGF       REF
         1  1.10E-09   -0.4950         0         0       0.0       0.0       0.0
$ Card 2: TBHYS (PR < 0이므로 이 카드 활성화)
$      SGL        SW        ST      LCID     TBHYS
       0.0       0.0       0.0         0       100
$ Card 3b: Mooney-Rivlin (N=0)
$        N       C10       C01
         0     {C10}     {C01}
$ Card 4: Prony (선택사항)
$       GI     BETAI
    {G_i}  {beta_i}
```

#### PR 부호 규칙

| PR 값 | 의미 |
|-------|------|
| +0.495 | 표준 Mooney-Rivlin (hysteresis 없음) |
| **-0.495** | **hysteresis 활성화** (Card 2의 TBHYS 읽음) |
| -0.4999 | hysteresis 활성화 + PR=0.4999 (locking 위험!) |

**실전 값**: PR = **-0.4950** (hysteresis ON + 안전한 PR)

#### TBHYS 테이블 설정 (DEFINE_TABLE + DEFINE_CURVE)

```
*DEFINE_TABLE
$    TBID
       100
$    VALUE
       0.0
       1.0
$
*DEFINE_CURVE
$ 곡선 1: strain_rate = 0.0에 대응 (DEFINE_TABLE의 첫 번째 VALUE)
$     LCID      SIDR       SFA       SFO      OFFA      OFFO     DATTYP
       101         0       1.0       1.0       0.0       0.0         0
$                 A1                  O1
               0.000               0.000
               0.200               {D1}
               0.400               {D2}
               ...                 ...
               1.000               {Dn}
*DEFINE_CURVE
$ 곡선 2: strain_rate = 1.0에 대응 (DEFINE_TABLE의 두 번째 VALUE)
       102         0       1.0       1.0       0.0       0.0         0
               0.000               0.000
               0.200               {D1}
               ...                 ...
```

**핵심 규칙**:
- DEFINE_TABLE의 VALUE 개수 = DEFINE_CURVE 개수 (위치 기반 매칭, LCID 무관!)
- TBHYS power-law 생성: `D = (W_dev / W̄_dev)^alpha`
- **n_points ≥ 100** (해상도 부족 시 곡선 불연속)
- alpha=0.0 → D=1.0 (감쇠 없음), alpha=0.50 → 최대 감쇠

#### COR 예측 공식

```
COR ≈ 0.890 - 0.295 × alpha              (hysteresis 단독)
COR ≈ 0.810 - 0.297 × alpha              (+ Prony 35%)
최저 달성: COR = 0.66 (alpha=0.50 + Prony 35%)
```

### 3.4 MAT_181 (Tabulated) — 실험 곡선 직접 입력

#### 카드 순서

```
Card 1: MID, RO, KM, MU, G, SIGF
Card 2: LCID, TRAMP, TEFAC
Card 3: *** WITH_FAILURE 옵션일 때만 읽음 → 일반적으로 SKIP ***
Card 4: VISCO, VFLAG  (점탄성 사용 시)
Card 5: GI, BETAI     (Prony 급수)
```

#### 완전한 예시 (점탄성 포함)

```
*MAT_SIMPLIFIED_RUBBER_TITLE
Rubber_181
$ Card 1: 기본 물성
$      MID        RO        KM        MU         G      SIGF
         1  1.10E-09   {KM}       0.0       0.0       0.0
$ Card 2: 곡선 참조
$     LCID     TRAMP      TEFAC
      {LC}       0.0       0.0
$ *** Card 3는 생략 (WITH_FAILURE 아닐 때 Card 4로 직행) ***
$ Card 4: 점탄성 활성화
$    VISCO     VFLAG
         1         0
$ Card 5: Prony 급수
$       GI     BETAI
    {G_i}  {beta_i}
```

#### 필드별 상세

| 필드 | 값 | 규칙 |
|------|-----|------|
| KM | 2G(1+ν)/3(1-2ν) | PR=0.495 → KM ≈ 100×G. 직접 계산 필수 |
| MU | **0.0** | G=0, SIGF=0이면 MU는 무시됨 (아무 효과 없음) |
| LCID | 곡선 ID | 엔지니어링 응력-변형률. 첫 점 반드시 (0.0, 0.0) |
| VISCO | 1 | Prony 급수 사용 시 **필수**. 0이면 Card 4-5 무시 |
| VFLAG | **0** | **절대 1 금지** — VFLAG=1은 대변형에서 negative volume |

#### Multi-term Prony 함정

```
⚠️ 같은 총 이완율(%)이라도 항 수가 많으면 COR이 높아진다 (감쇠 약해짐)
예: 35% 이완 × 1항 → COR=0.860
    35% 이완 × 3항 → COR=0.883 (더 높음 = 감쇠 부족)
→ 단일 항이 가장 효과적. 다항은 실험 fitting 목적으로만 사용
```

#### KM 계산 예시

```python
# PR=0.495, G=1.0 MPa (C10+C01=G/2)
G = 2 * (C10 + C01)  # MPa
KM = 2 * G * (1 + 0.495) / (3 * (1 - 2*0.495))  # = 99.3 × G
```

**주의**: MAT_181은 다축 하중에서 MR/Yeoh 대비 **56% 낮은 반력**을 보인다 (Phase 4 검증).
단축 시험 데이터만으로 보정한 MAT_181을 다축 하중에 적용할 때는 주의 필요.

### 3.5 Prony 급수 (점탄성 감쇠)

MAT_077_H 또는 MAT_181에 추가 가능:

```
$ MAT_077_H Card 4 (Prony series)
$       GI        BETAI
    {G_i}     {beta_i}
```

```
$ MAT_181 Card 4-5 (VISCO=1 필수)
$    VISCO     VFLAG
         1         0       ← VFLAG=0 필수 (1이면 대변형에서 negative volume)
$       GI        BETAI
    {G_i}     {beta_i}
```

- Relaxation % = G_i / G_total × 100
- COR 감소 효과: ~35% relaxation → COR 0.08 감소

---

## 4. Control Cards — 정확한 값

### 4.1 CONTROL_SOLID (Tet4 전용 설정)

```
*CONTROL_SOLID
$    ESORT   FMATRX   NIPTETS    SWLOCL    PSFAIL   T10JTOL      ICOH    TET13K
         0         0         4         0         0       0.0         0         0
```

| 필드 | 값 | 근거 |
|------|-----|------|
| ESORT | 0 | 요소 정렬 기본값 |
| FMATRIX | 0 | F-bar는 5% 개선에 불과, 안 써도 됨 |
| NIPTETS | 4 | Tet4 표준 적분점 |
| TET13K | 0 | TET13V=1은 효과 없음 (검증 결과 Bare와 동일) |

**참고**: Ex03 가이드에서는 TET13V=1을 권장했으나, Ex16 Phase 2(18건)에서 **효과 없음** 확인됨.
degenerate hex tet4에서는 TET13V가 작동하지 않는다. 진짜 tet4 메시에서만 유효할 수 있음.

### 4.2 CONTROL_TIMESTEP

```
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST
       0.0  {TSSFAC}         0       0.0  {DT2MS}         0         0         0
```

| 해석 유형 | TSSFAC | DT2MS | 근거 |
|-----------|--------|-------|------|
| **동적 충격** | 0.67~0.90 | **0** | DT2MS≠0이면 COR 36% 오차 |
| 준정적 압축 | 0.30~0.50 | -5.0E-07 | mass scaling 허용 |
| EFG (EF42) | 0.70~0.90 | 0 | EFG는 DT2MS=0 필수 |

**절대 규칙**: 동적 충격에서 DT2MS ≠ 0 금지. COR이 36% 틀어진다.

### 4.3 CONTROL_ACCURACY

```
*CONTROL_ACCURACY
$      OSU       INN    PIDOSU
         0         4
```

- INN=4: invariant node numbering → 고무 대변형에서 정확도 향상
- OSU=0: objective stress update 기본값

### 4.4 Hourglass 제어 — 파트별 분리 필수

#### 왜 파트별 분리가 필요한가

`*CONTROL_HOURGLASS`는 **전역 기본값**으로, 모든 파트에 동일하게 적용된다.
고무 모델에는 보통 여러 재질의 파트가 혼재하므로 (고무 + 금속 + 리지드),
**고무 파트에만** 적절한 HG를 적용하려면 `*HOURGLASS` 키워드를 파트별로 지정해야 한다.

#### 파트별 Hourglass 적용 방법

```
$ 고무 파트용 hourglass 정의
*HOURGLASS
$     HGID       IHQ        QH        IBQ        Q1        Q2    QB/VDC        QW
         1         5      0.05

$ 금속 파트용 hourglass 정의 (hex8 reduced integration 등)
*HOURGLASS
         2         4      0.10

$ PART 카드에서 HGID 참조
*PART
Rubber_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         1         0         0         0
*PART
Metal_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         2         2         0         2         0         0         0
```

#### 재질별 권장 HG 설정

| 재질/메시 | IHQ | QH | HGID 필요? | 비고 |
|-----------|-----|-----|-----------|------|
| **고무 Tet4 (EF13)** | 5 | 0.05 | O | fully integrated → HG 거의 없음. 형식적이지만 명시 |
| **고무 Hex8 (EF-1/2)** | 5 | 0.10 | O | reduced integration → HG 실질적으로 작동 |
| **금속 Hex8** | 4 | 0.10 | O | Flanagan-Belytschko viscous, 표준 |
| **금속 Shell** | 4 | 0.10 | O | 쉘 기본값 |
| **리지드 (MAT_020)** | — | — | X (HGID=0) | 리지드는 HG 불필요, HGID=0으로 둠 |
| **EFG (EF42)** | 6 | 0.15 | O | EFG 전용 |

#### CONTROL_HOURGLASS의 역할

```
*CONTROL_HOURGLASS
$      IHQ        QH
         4      0.10
```

- HGID=0인 **비-리지드** 파트에 적용되는 **전역 기본값**
- 리지드 파트는 HG 자체가 적용되지 않음 (HGID 무관)
- **권장**: 전역은 금속 기본값(IHQ=4, QH=0.10)으로 두고, 고무 파트만 `*HOURGLASS`로 오버라이드

### 4.5 CONTROL_BULK_VISCOSITY

```
*CONTROL_BULK_VISCOSITY
$       Q1        Q2      TYPE     BTYPE
    1.5000    0.0600         1         0
```

- Q1=1.5 (quadratic), Q2=0.06 (linear) — LS-DYNA 기본값
- TYPE=1: standard formulation

### 4.6 CONTROL_ENERGY

```
*CONTROL_ENERGY
$     HGEN      RWEN    SLNTEN     RYLEN
         2         2         2         2
```

- 모든 에너지 항목 추적 활성화 (2 = output to binout + d3plot)
- 에너지 밸런스 검증에 필수

### 4.7 CONTROL_TERMINATION

```
*CONTROL_TERMINATION
$   ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS      NOSOL
  {ENDTIM}         0       0.0       0.0       0.0         0
```

- 동적 충격: ENDTIM = 이벤트 시간의 2~3배 (예: 5ms 충격 → 10~15ms)
- 준정적 압축: ENDTIM = ramp 시간 + hold 시간

---

## 5. Contact 설정

### 5.1 기본 접촉

```
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE
$     SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
   {SSID}    {MSID}         3         3         0         0         0         0
$       FS        FD        DC        VC       VDC    PENCHK        BT        DT
  {FS}      {FD}         0.0       0.0  {VDC}         0       0.01.0000E+20
$      SFS       SFM       SST       MST      SFST      SFMT       FSF       VSF
    1.0000    1.0000       0.0       0.0    1.0000    1.0000    1.0000    1.0000
```

### 5.2 SSTYP/MSTYP 값 (자주 틀리는 부분)

```
SSTYP/MSTYP 의미:
  0 = Segment set ID
  1 = Shell set ID
  2 = Part set ID
  3 = Part ID (개별 파트)         ← 가장 직관적
  4 = Node set ID (single surface용)
```

**주의**: SSTYP=3이면 SSID는 Part ID를 직접 참조.
SSTYP=2이면 SSID는 SET_PART의 SID를 참조 (다름!).

### 5.3 SOFT 파라미터

```
SOFT=0 (기본 penalty)  ← 권장
```

| 파라미터 | 권장값 | 근거 |
|----------|--------|------|
| SOFT | 0 | SOFT 0/1/2 모두 COR 차이 <0.05% |
| VDC | 20~25 | COR 미세 조정용 (대부분 불필요) |
| SOFSCL | — | COR에 영향 없음 (12건 검증) |
| DEPTH | — | COR에 영향 없음 |
| SBOPT | 2.0 | **SBOPT=1.0은 불안정 → 절대 금지** |

**결론**: 접촉 파라미터로 COR을 제어하려 하지 마라. COR은 재료 감쇠(hysteresis alpha, Prony)로 제어한다.

### 5.4 CONTACT_AUTOMATIC_SINGLE_SURFACE — 치명적 함정

```
*CONTACT_AUTOMATIC_SINGLE_SURFACE
$     SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         0         0         0         0         0         0         0         0
```

**SSTYP 절대 규칙**:

| SSTYP | SSID | 결과 |
|-------|------|------|
| **0** | 0 | 전체 파트 포함 ✓ (올바름) |
| 1 | 0 | Part set 0 = 없음 → **접촉 없음** ✗ |
| 2 | 0 | Part 0 = 없음 → **접촉 없음** ✗ |
| 3 | 0 | Segment set 0 = 없음 → **접촉 없음** ✗ |

**증상**: 시뮬레이션 정상 종료, 물체가 서로 통과, SlideE = 0 (무한히 조용한 실패).
이 버그는 에러 메시지 없이 발생하므로 발견이 매우 어렵다.

**규칙**: Single surface 접촉에서 전체 파트를 포함하려면 **반드시 SSTYP=0**.

### 5.5 CONTROL_CONTACT (선택사항)

```
*CONTROL_CONTACT
$   SLSFAC    RWPNAL    ISLCHK    SHLTHK    PENOPT    THKCHG     OTEFR    ENMASS
       0.1       0.0         2         2         1         0         0         0
$   USRSTR    USRFRC     NSBCS    INTERM     XPENE     SSTHK      ....
       0.0       0.0         0         0       4.0
```

**중요**: CONTROL_CONTACT는 **반드시 2개의 데이터 카드**를 가진다.
Card 2를 생략하면 다음 키워드를 데이터로 읽어서 Error 10246 발생.
확실하지 않으면 CONTROL_CONTACT를 아예 쓰지 마라 — 접촉 파라미터는 CONTACT 카드에 직접 넣는다.

---

## 6. Database Output

```
*DATABASE_GLSTAT
$       DT    BINARY      LCUR     IOOPT
  {DB_DT}         0         0         1
*DATABASE_SPCFORC
  {DB_DT}         0         0         1
*DATABASE_MATSUM
  {DB_DT}         0         0         1
*DATABASE_RCFORC
  {DB_DT}         0         0         1
*DATABASE_RBDOUT
  {DB_DT}         0         0         1
*DATABASE_BINARY_D3PLOT
$       DT      LCDT      BEAM     NPLTC    PSETID
  {D3_DT}         0         0         0         0
```

| 해석 유형 | DB_DT | D3_DT | 근거 |
|-----------|-------|-------|------|
| 동적 충격 (1~10ms) | 1.0E-06 ~ 1.0E-05 | 종료시간/20 | Peak aliasing 방지 |
| 준정적 (1~10s) | 0.01 | 0.5 | 충분한 곡선 해상도 |

---

## 7. 절대 금지 목록

### 7.1 수렴 실패를 유발하는 설정

| # | 금지 설정 | 결과 | 대안 |
|---|----------|------|------|
| 1 | **PR = 0.4999** (tet4) | R²=-24.7, 8.9배 force 과대 | PR=0.490~0.495 |
| 2 | **ELFORM=43** (대변형 고무) | locking ratio 28.8 (최악) | ELFORM=13 |
| 3 | **ELFORM=41** (60%+ 압축) | timestep collapse, 300 cycles에서 crash | ELFORM=13 또는 42 |
| 4 | **ELFORM=60** | NaN at t=1.4e-4 | ELFORM=13 |
| 5 | **SBOPT=1.0** (SOFT=2) | 음의 에너지, 불안정 | SBOPT=2.0 |
| 6 | **DT2MS ≠ 0** (동적 충격) | COR 36% 오차 | DT2MS=0 |
| 7 | **VFLAG=1** (MAT_181 Prony) | negative volume in large deformation | VFLAG=0 |
| 8 | **CONTROL_CONTACT Card 2 누락** | Error 10246 | Card 2 포함 또는 키워드 자체 삭제 |

### 7.2 효과 없는 설정 (쓸 필요 없음)

| 설정 | 효과 | 근거 |
|------|------|------|
| TET13V=1 (degenerate hex tet4) | 없음 | Phase 2: Bare와 완전 동일 |
| FMATRIX=2 (F-bar, tet4) | 5% 미만 | locking ratio 8.87→8.42 |
| SOFSCL 변경 | 없음 | 0.01~1.0 전 범위 동일 |
| DEPTH 변경 | 없음 | 2~15 동일 |
| MAT_181 MU 파라미터 | 없음 | G=0, SIGF=0이면 MU 무시됨 |

---

## 8. 완전한 K-file 템플릿

### 8.1 동적 충격 (Ball Drop 등) — Tet4

```
*KEYWORD
*TITLE
Rubber Impact Simulation
$
*CONTROL_TERMINATION
$   ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS      NOSOL
  0.010000         0       0.0       0.0       0.0         0
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST
       0.0  0.670000         0       0.0       0.0         0         0         0
*CONTROL_ACCURACY
$      OSU       INN    PIDOSU
         0         4
*CONTROL_ENERGY
$     HGEN      RWEN    SLNTEN     RYLEN
         2         2         2         2
*CONTROL_HOURGLASS
$      IHQ        QH
         4      0.10
*CONTROL_BULK_VISCOSITY
$       Q1        Q2      TYPE     BTYPE
    1.5000    0.0600         1         0
*CONTROL_SOLID
$    ESORT   FMATRX   NIPTETS    SWLOCL    PSFAIL   T10JTOL      ICOH    TET13K
         0         0         4         0         0       0.0         0         0
$
*DATABASE_GLSTAT
$ ...
*DATABASE_RCFORC
$ ...
*DATABASE_RBDOUT
$ ...
*DATABASE_BINARY_D3PLOT
$ ...
$
$ --- Hourglass (파트별) ---
*HOURGLASS
$     HGID       IHQ        QH
         1         5      0.05
$
$ --- Section ---
*SECTION_SOLID
$    SECID    ELFORM       AET
         1        13         0
*SECTION_SOLID
         2        10         0
$
$ --- Material ---
*MAT_MOONEY-RIVLIN_RUBBER
$      MID       RHO        PR
         1  1.10E-09     0.495
$      C10       C01
    0.7500    0.2500
*MAT_RIGID_TITLE
Rigid_Impactor
$      MID       RHO         E        PR         N    COUPLE         M     ALIAS
         2  7.85E-09  2.10E+05     0.300         0         0         0
$      CMO      CON1      CON2
       1.0         7         7
$  LCO/A1        A2        A3        V1        V2        V3
       0.0       0.0       0.0       0.0       0.0       0.0
$
$ --- Part (HGID로 hourglass 분리) ---
*PART
Rubber_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         1         0         0         0
*PART
Rigid_Impactor
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         2         2         0         0         0         0         0
$
$ ... (NODES, ELEMENTS, BOUNDARY, CONTACT, INITIAL_VELOCITY)
$
*END
```

### 8.2 준정적 압축 — Tet4

CONTROL_TIMESTEP만 변경:
```
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST
       0.0  0.500000         0       0.0-5.000E-07         0         0         0
```

- TSSFAC=0.50 (안정성 우선)
- DT2MS=-5.0E-07 (mass scaling 허용, 준정적이므로 OK)

---

## 9. Validation Checklist

시뮬레이션 완료 후 반드시 확인:

```
1. d3hsp 마지막 줄에 "N o r m a l    t e r m i n a t i o n" 있는가?
   → ERROR면 원인 분석 (d3hsp에서 Error 번호 검색)

2. glstat에서 에너지 밸런스:
   → |total_energy - external_work| / |external_work| < 5%
   → hourglass_energy / internal_energy < 5%

3. matsum에서 mass scaling:
   → (final_mass - initial_mass) / initial_mass < 100%
   → 동적 충격에서는 0% 이어야 함 (DT2MS=0이므로)

4. 반력 크기가 물리적으로 합리적인가?
   → 예상 응력 = 재료 전단 계수 × 변형률 수준
   → 비정상적으로 큰 반력 = locking 의심 → PR 확인

5. 시간 이력이 매끄러운가?
   → 급격한 oscillation = 접촉 불안정 또는 timestep 문제
```

---

## 10. 자주 발생하는 에러와 해결

| Error | 메시지 | 원인 | 해결 |
|-------|--------|------|------|
| 30073 | negative or zero determinant | ELFORM=43 + hex8 메시 | ELFORM=13으로 변경 또는 tet4 메시 사용 |
| 40024 | negative volume | 과도한 요소 변형 | DT2MS=0, TSSFAC 감소, 메시 세분화 |
| 10246 | improperly formatted data | K-file 포맷 오류 | 필드 폭(8/10/20자) 확인, Card 수 확인 |
| 20459 | LCID=0 not permitted | LOAD_BODY_Z에서 LCID=0 | DEFINE_CURVE 생성 후 참조 |
| 10904 | integer overflow | memory 파라미터 과대 | memory=200m (SP), 500m (DP) |
| element type=0 | 모든 파트 type=0 | CONTROL 카드 누락/포맷 오류 | 템플릿 기반 접근법 사용 |

---

## 11. Template Modification 전략 (권장)

**프로그래밍으로 K-file을 처음부터 생성하지 마라.**

이유: CONTROL 카드 간 상호 의존성, Card 수, 필드 폭 등으로 포맷 에러가 빈번.
Phase 5에서 프로그래밍 모델이 "element type=0"으로 전부 실패하고,
V7 템플릿으로 전환 후 11/12 NORMAL 달성한 사례가 있다.

### 권장 워크플로우

```
1. 검증된 K-file을 템플릿으로 복사
2. TITLE만 변경
3. 필요한 카드만 수정 (MAT, CONTACT 등)
4. 나머지 CONTROL 카드는 절대 건드리지 않음
5. 테스트 → NORMAL 확인 → 다음 변경
```

### 검증된 템플릿 위치

| 용도 | 템플릿 파일 |
|------|-----------|
| Ball drop (동적 충격) | `/data/ball_drop_test_v7/ex11_mat077h_hys_med/ex11_mat077h_hys_med.k` |
| 큐브 압축 (준정적) | `/data/rubber_advanced_study/phase1_efg_benchmark/case01_fem_yeoh/case01_fem_yeoh.k` |
| EFG 부싱 (다축) | `/data/rubber_advanced_study/phase4_bushing/case01_mr_biaxial/case01_mr_biaxial.k` |

---

## 12. 단위 체계 요약

이 가이드의 모든 값은 **mm-ton-s-MPa** 단위:

| 물리량 | 단위 | 고무 전형값 |
|--------|------|-----------|
| 길이 | mm | — |
| 질량 | ton | — |
| 시간 | s (또는 ms) | — |
| 밀도 | ton/mm³ | 1.0~1.3 × 10⁻⁹ |
| 응력/계수 | MPa | G = 0.5~5.0 |
| 힘 | N | — |
| 에너지 | mJ (N·mm) | — |
| 속도 | mm/s | — |
| 중력 | mm/s² | 9810 (= 0.00981 mm/ms²) |

---

## 13. K-file 포맷팅 규칙 — 다른 AI가 가장 많이 틀리는 부분

### 13.1 필드 폭 규칙

LS-DYNA K-file은 **고정 폭** 필드를 사용한다. 키워드별로 필드 폭이 다르다:

| 키워드 | 필드 폭 | 설명 |
|--------|---------|------|
| 대부분의 CONTROL/MAT/SECTION | **10칸** | 표준 필드 |
| SET_NODE_LIST, SET_SHELL_LIST | **10칸** | ~~8칸 아님~~ |
| ELEMENT_SOLID | **8칸** | EID + 8 노드 = 8칸 × 9필드 |
| NODE | **8칸(ID) + 16칸(X,Y,Z)** | 좌표는 16칸 |
| DEFINE_CURVE 데이터 | **20칸** | A1, O1 각 20칸 |

### 13.2 Tet4 요소 (*ELEMENT_SOLID) — Degenerate Hex 포맷

LS-DYNA R16 SP는 tet4의 N5~N8에 0을 **허용하지 않는다**.
반드시 **degenerate hex** 포맷 사용:

```
정상 (4-node tet):   N1, N2, N3, N4, 0, 0, 0, 0   ← ERROR!
Degenerate hex:      N1, N2, N3, N4, N4, N4, N4, N4 ← 올바름
```

Python 예시:
```python
# 8칸 고정 폭
def f8(v): return f'{v:>8d}'

# Tet4 → degenerate hex
for eid, (n1, n2, n3, n4) in enumerate(tet4_elements, 1):
    line = f8(eid) + f8(pid) + f8(n1) + f8(n2) + f8(n3) + f8(n4) + f8(n4) + f8(n4) + f8(n4) + f8(n4)
```

### 13.3 SET_NODE_LIST 포맷

```
*SET_NODE_LIST
$      SID
         1
$ 10칸 고정폭, 줄당 최대 8개 노드
$      NID       NID       NID       NID       NID       NID       NID       NID
         1         2         3         4         5         6         7         8
         9        10
```

Python 예시:
```python
def f10(v):
    if isinstance(v, int): return f'{v:>10d}'
    return f'{v:>10.4f}'

# 8개씩 줄바꿈
for i in range(0, len(nodes), 8):
    line = ''.join(f10(n) for n in nodes[i:i+8])
```

### 13.4 DEFINE_CURVE 데이터 포맷

```
*DEFINE_CURVE
$     LCID      SIDR       SFA       SFO      OFFA      OFFO     DATTYP
         1         0       1.0       1.0       0.0       0.0         0
$                 A1                  O1
                 0.0                 0.0       ← 각 20칸
               0.100               1.500
               0.200               3.200
```

**주의**: A1, O1은 **20칸** 고정폭. 10칸으로 쓰면 파싱 에러.

---

## 14. MAT_RIGID (리지드 파트) — 임팩터, 고정판, 하우징

고무 모델에는 거의 항상 리지드 파트가 동반된다 (임팩터, 고정판, 금형 등).

### 14.1 기본 설정

```
*MAT_RIGID_TITLE
Rigid_Steel
$ Card 1: 기본 물성
$      MID       RHO         E        PR         N    COUPLE         M     ALIAS
         2  7.85E-09  2.10E+05     0.300         0         0         0
$ Card 2: 구속 (반드시 포함!)
$      CMO      CON1      CON2
       1.0         7         7
$ Card 3: 방향 벡터 (반드시 포함!)
$  LCO/A1        A2        A3        V1        V2        V3
       0.0       0.0       0.0       0.0       0.0       0.0
```

### 14.2 카드 누락 에러

| 누락 | 에러 |
|------|------|
| Card 2 (CMO) 누락 | Error 10246 "improperly formatted data" |
| Card 3 (LCO/A1) 누락 | Error 10246 at *NODE line (!!오해의 소지!!) |

Card 3을 빼면 *NODE 줄에서 에러가 발생하므로, 원인을 찾기 매우 어렵다.
**반드시 3장의 카드를 모두 작성**하라.

### 14.3 CON1/CON2 값 (열거형, 비트마스크 아님!)

| 값 | 구속 방향 |
|----|----------|
| 0 | 없음 |
| 1 | X |
| 2 | Y |
| 3 | Z |
| 4 | XY |
| 5 | YZ |
| 6 | ZX |
| **7** | **XYZ (완전 구속)** |

**주의**: CON1=7, CON2=7은 "모든 자유도 구속" = 완전 고정.
비트마스크(1+2+4=7)와 우연히 같은 값이지만 **열거형**이다. 예: XY=4 (비트마스크라면 3).

### 14.4 CMO 형식 주의

```
CMO = 1.0  ← 반드시 float (1이 아니라 1.0)
CON1, CON2 = integer
```

### 14.5 ELFORM for Rigid

```
MAT_RIGID (type 20)는 ELFORM=13을 지원하지 않는다.
→ 리지드 tet4 파트에는 ELFORM=10 사용
```

| 메시 유형 | Rubber ELFORM | Rigid ELFORM |
|-----------|--------------|--------------|
| Tet4 | 13 | **10** |
| Hex8 | -1 또는 2 | 1 |

---

## 15. 초기 속도 설정 (INITIAL_VELOCITY)

### 15.1 리지드 바디 vs 일반 노드

| 대상 | 키워드 | 비고 |
|------|--------|------|
| **리지드 바디** | `*INITIAL_VELOCITY_RIGID_BODY` | PID 직접 지정 |
| 일반 노드/파트 | `*INITIAL_VELOCITY_GENERATION` | STYP으로 대상 지정 |

**절대 규칙**: 리지드 바디에 `*INITIAL_VELOCITY_GENERATION`을 쓰면 무시되거나 오동작.

### 15.2 INITIAL_VELOCITY_RIGID_BODY

```
*INITIAL_VELOCITY_RIGID_BODY
$      PID        VX        VY        VZ       VRX       VRY       VRZ
         2       0.0       0.0  {VZ_mm_s}       0.0       0.0       0.0
```

- PID = Part ID (SET이 아님)
- 속도 단위: mm/s (mm-ton-s 체계)
- 예: 1m/s 낙하 = VZ = -1000.0 mm/s

### 15.3 INITIAL_VELOCITY_GENERATION (일반 노드용)

```
*INITIAL_VELOCITY_GENERATION
$ Card 1: 대상 지정
$       ID      STYP     OMEGA        VX        VY        VZ     IVATN      ICID
   {ID}      {STYP}       0.0       0.0       0.0  {VZ}         0         0
$ Card 2: 회전 중심/방향 (반드시 포함!)
$       XC        YC        ZC        NX        NY        NZ     PHASE    IRIGID
       0.0       0.0       0.0       0.0       0.0       0.0         0         0
```

**반드시 2줄 (Card 1 + Card 2)**. Card 2 생략 시 Error 10246 + Error 10450.

### 15.4 STYP 값과 함정

| STYP | 의미 | ID는? |
|------|------|-------|
| 0 | Node set | SET_NODE ID |
| 1 | Part set | SET_PART ID |
| **2** | **Part ID** | Part ID (직접) |
| 3 | All nodes | — |

**치명적 함정**: STYP=0 + 존재하지 않는 node set → **전체 노드에 속도 적용** (에러 없이!)
→ 고무 파트에도 임팩터 속도가 적용되어 비물리적 결과.

---

## 16. LOAD_BODY_Z (중력)

### 16.1 기본 형식

```
*LOAD_BODY_Z
$     LCID        SF    LCIDDR        XC        YC        ZC
         {LC}  {SF}
```

### 16.2 LCID = 0 금지

```
LCID = 0 → Error 20459 "LCID=0 is not permitted"
```

반드시 DEFINE_CURVE를 생성하고 참조:

```
*DEFINE_CURVE
$     LCID
       999
$                 A1                  O1
               0.000               1.000
           10000.000               1.000
*LOAD_BODY_Z
$     LCID        SF
       999   0.00981
```

### 16.3 부호 규칙 (자주 틀리는 부분)

LS-DYNA의 LOAD_BODY는 **관성 가속도(base acceleration)** 해석:

```
실제 가속도 = -SF × curve_value

하향 중력 (Z-):
  SF = +0.00981  (mm/ms²)
  curve = +1.0
  → 실제 = -0.00981 mm/ms² = 하향 ✓

SF = -0.00981 → 실제 = +0.00981 = 상향 (반중력!) ✗
```

**규칙**: 하향 중력 → SF = **양수** (+9.81E-03 mm/ms² 또는 +9810 mm/s²)

---

## 17. Quick Reference Card

```
고무 파트 발견 시 즉시 적용:
┌──────────────────────────────────────────────────┐
│  [고무 파트]                                       │
│  ELFORM = 13          (tet4)                      │
│  PR     = 0.490~0.495 (절대 0.4999 금지)           │
│  INN    = 4           (CONTROL_ACCURACY)          │
│  *HOURGLASS HGID=N, IHQ=5, QH=0.05 (파트별!)      │
│  CONTROL_HG = 전역 기본(금속용 IHQ=4, QH=0.10)    │
│  Q1=1.5, Q2=0.06      (CONTROL_BULK_VISC)         │
│  NIPTETS = 4          (CONTROL_SOLID)             │
│  SOFT   = 0           (CONTACT)                   │
│  TSSFAC = 0.67 (충격) / 0.50 (압축)                │
│  DT2MS  = 0 (충격) / -5E-7 (압축)                  │
│                                                   │
│  [리지드 파트]                                      │
│  ELFORM = 10 (tet4) / 1 (hex8)                    │
│  MAT_RIGID: Card 1 + Card 2(CMO) + Card 3(LCO)   │
│  CMO=1.0(float), CON1=CON2=7(완전구속)             │
│                                                   │
│  [초기 속도]                                        │
│  리지드 → INITIAL_VELOCITY_RIGID_BODY              │
│  일반   → INITIAL_VELOCITY_GENERATION (2줄 필수)   │
│  STYP=0+없는set = 전체적용 버그!                    │
│                                                   │
│  [중력]                                            │
│  LOAD_BODY_Z: LCID≠0, SF=+0.00981 (하향)          │
│                                                   │
│  [K-file 포맷]                                     │
│  Tet4: N1,N2,N3,N4,N4,N4,N4,N4 (degenerate hex)  │
│  SET: 10칸, ELEMENT: 8칸, CURVE: 20칸              │
│  SINGLE_SURFACE: SSTYP=0 필수 (≠0+SSID=0=무접촉) │
│                                                   │
│  [금지]                                            │
│  EF43, EF41, EF60, PR≥0.4999, SBOPT=1.0,         │
│  DT2MS≠0(충격), VFLAG=1, LCID=0(LOAD_BODY),      │
│  MAT_RIGID Card2/3 생략, IV_GENERATION Card2 생략  │
└──────────────────────────────────────────────────┘
```

---

## 부록 A: 전체 섹션 목록

| # | 주제 | 핵심 |
|---|------|------|
| 0 | 적용 조건 | 초탄성, PR>0.49, 변형률>20% |
| 1 | Element Formulation | ELFORM=13 only (tet4) |
| 2 | Poisson비 | PR≤0.495 |
| 3 | Material Model | MAT_027/077_H/181 + 완전 카드 순서 |
| 4 | Control Cards | 7개 CONTROL 정확한 값 |
| 5 | Contact | SOFT=0, SSTYP=0, CONTROL_CONTACT 2카드 |
| 6 | Database Output | DB_DT, D3_DT |
| 7 | 금지 목록 | 8개 수렴실패 + 5개 무효 설정 |
| 8 | K-file 템플릿 | 동적충격 + 준정적 |
| 9 | Validation Checklist | NORMAL, 에너지, mass scaling |
| 10 | 에러 해결 | 6개 주요 에러 |
| 11 | Template 전략 | 프로그래밍 금지, 템플릿 수정 |
| 12 | 단위 체계 | mm-ton-s-MPa |
| 13 | K-file 포맷 규칙 | 필드 폭, tet4, SET, CURVE |
| 14 | MAT_RIGID | 카드 3장 필수, CON 열거형 |
| 15 | 초기 속도 | RIGID_BODY vs GENERATION, STYP 함정 |
| 16 | 중력 | LCID≠0, SF 부호 |
| 17 | Quick Reference | 한 눈에 전체 요약 |

---

*본 가이드는 LS-DYNA R16.1.1 MPP 기반 300건+ 시뮬레이션 결과입니다.*
*SLURM cluster, 2 CPU, Apptainer, SP(aocc420_ompi4.0.5) / DP(ifort2022_impi)*
*작성: 2026-03-01, Examples 03/09/10/16 통합, 2026-03-01 보강 (포맷/리지드/속도/중력)*
