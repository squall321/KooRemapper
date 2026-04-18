# Metal Material Library for LS-DYNA

엔지니어링 금속(SUS, Al, Ti 계열)의 **탄소성 + 열물성** LS-DYNA 재료 카드 라이브러리.

## 왜 탄소성인가

낙하/충격 해석에서 금속은 반드시 탄소성으로 모델링해야 한다:

1. **국부 소성변형** — 충격 지점에서 σ > σ_y 에너지 흡수
2. **영구 변형 예측** — dent, 굽힘, 잔류 변형
3. **파단 기준** — failure strain으로 구조 손상 평가
4. **strain hardening 재료별 상이** — SUS304 (큼) vs Al6061-T6 (작음)

탄성만 넣으면 응력이 무한대로 상승하고 에너지 흡수가 안 되어 실제 거동과 전혀 다른 결과가 나온다.

## 하이브리드 전략: 4가지 경화 변형

각 재료를 **4가지 버전**으로 제공한다:

### 1. Bilinear isotropic (빠른 해석용)
- `*MAT_PIECEWISE_LINEAR_PLASTICITY` (MAT_024)
- SIGY + ETAN 직접 입력 (2-segment 직선)
- Isotropic hardening (항복면 균일 확장)
- **MID 100501~100599**

### 2. Multi-linear isotropic (정밀 해석용)
- `*MAT_PIECEWISE_LINEAR_PLASTICITY` + `*DEFINE_CURVE` (LCSS)
- 5~8점 σ_eff vs ε_plastic 곡선
- Isotropic hardening
- **MID 110501~110599**, LCID = MID

### 3. Bilinear kinematic pure (Bauschinger 효과)
- `*MAT_PLASTIC_KINEMATIC` (MAT_003), **BETA = 0.0**
- 순수 kinematic — 항복면이 평행이동 (크기 불변)
- Bauschinger 효과 완전히 반영
- **사이클 하중, 반사, 역방향 재하**에 적합
- **MID 130501~130599**

### 4. Bilinear kinematic mixed (혼합 경화)
- `*MAT_PLASTIC_KINEMATIC` (MAT_003), **BETA = 0.5**
- 50/50 isotropic + kinematic 혼합
- 실제 금속에 가장 가까운 거동
- **MID 140501~140599**

**언제 무엇을 쓸 것인가:**

| 해석 종류 | 추천 MID |
|---------|---------|
| 단조 낙하 (한 번만 떨어짐) | Bilinear iso (1005xx) or Multi iso (1105xx) |
| 정밀 소성 예측, 파단 | Multi iso (1105xx) |
| 낙하 후 반사 진동, cyclic | Kinematic mixed (1405xx) |
| 반복 하중, Bauschinger 중요 | Kinematic pure (1305xx) |
| 열처리, 어닐링 | Iso (1005xx/1105xx) |

모든 변형에 대해 CTE, damping part set, Cowper-Symonds 가 자동 적용된다.

## 파일 구조

```
Metal/
├── README.md                   # 본 문서
├── references/                  # TDS PDF 원본 저장소
├── metal_generator.py          # 재료 DB → K-file 생성기
├── metal_materials_db.json     # 파싱된 재료 DB
├── sus.k                        # SUS 계열 (bilinear + multilinear)
├── al.k                         # Al 계열 (bilinear + multilinear)
├── ti.k                         # Ti 계열 (bilinear + multilinear)
└── metal_thermal.k             # 열물성 (TC, Cp, CTE)
```

## MID 할당 규칙

| 범주 | Bi iso (MAT_024) | Multi iso (MAT_024+LCSS) | Kin pure (MAT_003, β=0) | Kin mixed (MAT_003, β=0.5) | Thermal TMID |
|------|------|------|------|------|------|
| SUS 계열 | 100501~100520 | 110501~110520 | 130501~130520 | 140501~140520 | 120501~120520 |
| Al 계열 | 100521~100560 | 110521~110560 | 130521~130560 | 140521~140560 | 120521~120560 |
| Ti 계열 | 100561~100580 | 110561~110580 | 130561~130580 | 140561~140580 | 120561~120580 |

**규칙**: 끝 3자리 매칭. 예: Al6061-T6 →
- `100535` bi iso
- `110535` multi iso
- `130535` kin pure
- `140535` kin mixed
- `120535` TMID

**Part Set SID** (metal_damping.k): MID + 800000
- 900535 / 910535 / 930535 / 940535 (Al6061-T6의 4 variants)

## 재료 목록

### SUS (스테인리스강) — 10종

| 등급 | 설명 | 주용도 |
|------|------|-------|
| SUS201 | 저 Ni 오스테나이트, 경제형 | 주방용품, 장식 |
| SUS301 | 고강도 스프링용 오스테나이트 | 스프링, 와셔 |
| SUS304 | 가장 보편적인 오스테나이트 | **범용** |
| SUS304L | 저탄소 304 (용접용) | 용접 구조물 |
| SUS316 | Mo 첨가 내식성 오스테나이트 | 해양, 화학 |
| SUS316L | 저탄소 316 | 의료, 용접 |
| SUS410 | 마르텐사이트 (경화 가능) | 칼날, 베어링 |
| SUS420 | 고탄소 마르텐사이트 | 칼, 금형 |
| SUS430 | 페라이트 (자성) | 가전, 자동차 |
| 17-4PH | 석출경화 마르텐사이트 | 고강도 구조 |

### Al (알루미늄 합금) — 12종

| 등급 | 설명 | 주용도 |
|------|------|-------|
| Al1050-O | 순 Al 어닐링 | 반사판, 화학 |
| Al1100-O | 순 Al (덜 순) | 호일, 판재 |
| Al2024-T3 | Al-Cu 항공재 | 항공기 구조 |
| Al3003-H14 | Al-Mn 판재 | 지붕, 라디에이터 |
| Al5052-H32 | Al-Mg 해양 | 선박, 차체 |
| Al5083-H116 | 고강도 Al-Mg | 선박, LNG 탱크 |
| Al6061-T6 | Al-Mg-Si 범용 구조 | **범용 구조** |
| Al6063-T5 | 압출용 Al-Mg-Si | 창호, 섀시 |
| Al6063-T6 | T6 처리 6063 | 구조용 압출 |
| Al7050-T7451 | Zn 항공재 | 항공기 |
| Al7075-T6 | 최고강도 Al-Zn | 항공기, 스포츠 |
| ADC12 | 다이캐스트 Al | **스마트폰 프레임** |

### Ti (티타늄) — 6종

| 등급 | 설명 | 주용도 |
|------|------|-------|
| Ti Grade 1 | CP Ti, 최연질 | 의료, 화학 |
| Ti Grade 2 | CP Ti, 보편 | **CP 범용** |
| Ti Grade 4 | CP Ti, 고강도 | 해양, 구조 |
| Ti Grade 5 | Ti-6Al-4V (α-β) | **범용 고강도** |
| Ti Grade 5 ELI | Low interstitial | 의료 임플란트 |
| Ti Grade 9 | Ti-3Al-2.5V | 자전거, 튜빙 |

## 카드 구조 예시

### Bilinear Al6061-T6 (MID 100535)

```
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6061-T6 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
   100535 2.700e-09   68900.0    0.3300     276.0     695.0     0.120       0.0
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       0.0
```

### Multi-linear Al6061-T6 (MID 110535 + LCID 110535)

```
*DEFINE_CURVE_TITLE
Al6061-T6 true stress-plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
   110535         0       1.0       1.0       0.0       0.0         0
$   eps_p              stress
   0.000e+00   2.760e+02
   5.000e-03   2.890e+02
   1.000e-02   2.960e+02
   2.000e-02   3.020e+02
   5.000e-02   3.080e+02
   1.000e-01   3.100e+02
   1.200e-01   3.100e+02

*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6061-T6 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
   110535 2.700e-09   68900.0    0.3300       0.0       0.0     0.120       0.0
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110535         0       0.0
```

### Thermal (TMID 120535)

```
*MAT_THERMAL_ISOTROPIC_TITLE
Al6061-T6 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
   120535 2.700e-09       0.0       1.0       0.0       0.0
$       HC         TC
    8.96e8     167.0

$ Applied to structural MID 100535 and 110535 via ADD_THERMAL_EXPANSION
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
   100535         0 2.340e-05
*MAT_ADD_THERMAL_EXPANSION
   110535         0 2.340e-05
```

## 단위계

LS-DYNA **mm, s, ton** 단위계:

| 물리량 | 단위 | 변환 |
|--------|------|------|
| Stress | MPa | N/mm² |
| Density | ton/mm³ | g/cc × 1e-9 |
| Specific heat Cp | mm²/s²/K | J/kg/K × 1e6 |
| Thermal conductivity | mW/mm/K | W/m/K (× 1) |
| CTE | 1/K | ppm/K × 1e-6 |

## 데이터 출처

- **ASM Handbook Vol 2** (Properties of Nonferrous Alloys)
- **ASM Handbook Vol 4** (Heat Treating)
- **MatWeb.com** (material data aggregator)
- **Kaiser Aluminum TDS**, **Alcoa Data Sheets**
- **POSCO 스테인리스강 카탈로그**
- **ASTM B209** (Al sheet), **B265** (Ti), **A240** (SUS sheet)
- **JIS G 4304** (stainless sheet)
- **Timet Titanium TDS**

## 사용법

```bash
cd Metal
python3 metal_generator.py
# 출력: sus.k, al.k, ti.k, metal_thermal.k, metal_materials_db.json
```

LS-DYNA 모델에서:

```
*INCLUDE
sus.k
al.k
ti.k
metal_thermal.k
```

그리고 해당 PART에서 MID/TMID를 참조:

```
*PART
Frame_Al6061
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         5         1    100535         0         0         0         0    120535
```

## Cowper-Symonds 변형률 속도 (재료별 세분화)

낙하 충격(ε̇ ~ 10²~10⁴ /s)에서는 strain-rate 효과가 무시할 수 없다:

```
σ_y(ε̇) = σ_y,static × [1 + (ε̇/C)^(1/P)]
```

**재료 군별 실측 기반 계수**:

| 재료 군 | C (/s) | P | 출처 |
|---------|--------|---|------|
| **Al solid-sol** (1xxx, 3xxx, 5xxx) | 6500 | 4 | Jones 1989 |
| **Al precipitation** (2xxx, 6xxx, 7xxx) | 1288000 | 4 | Bodner-Partom 1975 (rate-insensitive) |
| **Al die cast** (ADC12) | 1500 | 4 | 중간값 추정 |
| **SUS austenitic** (201, 301, 304, 316) | 100 | 10 | Jones 1989 |
| **SUS 316L** (low-C) | 50 | 5 | Hsu & Jones 2004 |
| **SUS martensitic/ferritic** (410, 420, 430) | 40 | 5 | mild-steel analogue |
| **SUS 17-4PH** (precipitation) | 3200 | 5 | low rate-sensitivity |
| **Ti CP** (Gr1/2/4) | 120 | 9 | Jones 1989 |
| **Ti-6Al-4V** (Gr5) | 255 | 2 | Meyer & Kleponis 2001 |

핵심 원리: **FCC solid-solution** 는 rate-sensitive (낮은 C), **precipitation-hardened** 합금은 rate-insensitive (높은 C). BCC 재료는 중간.

모든 카드에 `VP=1` (viscoplastic formulation)로 정확한 strain-rate 효과 반영.

## 데이터 신뢰도 등급

각 파라미터의 신뢰도:

| 파라미터 | 등급 | 비고 |
|---------|------|------|
| ρ (density) | ★★★★★ | ASTM/MatWeb 표준값 |
| E (Young's modulus) | ★★★★★ | 동일 |
| ν (Poisson ratio) | ★★★★☆ | 재료별 약간 편차 가능 |
| σ_y (yield) | ★★★★★ | ASTM 공식 스펙 최소값 (보수적) |
| σ_u (ultimate) | ★★★★★ | 동일 |
| ε_f (elongation) | ★★★★☆ | ASTM 명시값 |
| **Multi-linear σ-ε 곡선** | ★★★☆☆ | **Hollomon/Voce 근사** — 10~20% 오차 가능 |
| CTE | ★★★★★ | 정밀 측정값 |
| TC, Cp | ★★★★★ | RT 기준 표준값 |
| **Cowper-Symonds C, P** | ★★★★☆ | 재료별 문헌값 적용 (수정됨) |
| **damping_zeta** | ★★★☆☆ | **엔지니어링 추정** (material damping + 구조 감쇠 근사) |

정밀 해석이 필요하면 실측 σ-ε 곡선과 DMA 데이터로 **LCSS 교체** 및 **damping 튜닝** 권장.

## Damping 설정

`metal_damping.k` 파일에 각 재료별로 **Rayleigh damping** 카드가 생성된다.

### Material-family damping zeta (기본값, drop test @ 1 kHz)

| 재료 군 | zeta | 근거 |
|---------|------|------|
| SUS austenitic (201~316) | 0.5% | FCC, 중간 감쇠 |
| SUS martensitic/PH (410, 420, 17-4PH) | 0.3% | 경화재, 매우 낮음 |
| SUS ferritic (430) | 0.4% | |
| Al solid-sol (1xxx, 3xxx, 5xxx) | 0.6~0.8% | Mg 함량에 따라 |
| Al precipitation (2xxx, 6xxx, 7xxx) | 0.3% | 석출 강화 |
| ADC12 die cast | 1.5% | 기공/결함 많음 |
| Ti CP (Gr1/2/4) | 0.5% | |
| Ti-6Al-4V (Gr5) | 0.3% | 2상 합금 |
| Ti-3Al-2.5V (Gr9) | 0.4% | |

### Rayleigh 계수 계산

```
ω_ref = 2π × 1000 Hz = 6283 rad/s
alpha (mass)      = zeta × ω_ref
beta  (stiffness) = zeta / ω_ref
```

예: Al6061-T6 (zeta=0.3%)
- alpha = 0.003 × 6283 = **18.85 /s**
- beta = 0.003 / 6283 = **4.77e-7 s**

### Part Set 할당 규칙

`metal_damping.k`는 각 material MID 당 하나의 `*SET_PART_LIST` placeholder를 생성한다.

**Part Set SID = MID + 800000**

- Al6061-T6 bilinear: MID 100535 → SID **900535**
- Al6061-T6 multilinear: MID 110535 → SID **910535**
- SUS304 bilinear: MID 100503 → SID **900503**

### 사용 방법

1. `*INCLUDE metal_damping.k`
2. 해당 material을 사용하는 PART의 PID를 적절한 `*SET_PART_LIST`에 추가:
   ```
   *SET_PART_LIST_TITLE
   Al6061-T6_bi_parts
        900535       0.0       0.0       0.0       0.0
   $    PID1      PID2      PID3      PID4 ...
   $ TODO 부분에 실제 PCB/구조 PART ID 추가
        1001      1002      1003      1004      0      0      0      0
   ```
3. 자동으로 `*DAMPING_PART_MASS_SET` + `*DAMPING_PART_STIFFNESS_SET`이 그 part set에 적용됨

### 주파수 변경

`metal_generator.py` 내의 `omega_ref_hz` 파라미터(기본 1000 Hz)를 바꿔서 재생성하면 해당 주파수 기준의 Rayleigh 계수로 재계산된다.

- 500 Hz: 낮은 주파수 충격 (큰 구조물)
- **1000 Hz (default)**: 일반 drop test
- 2000 Hz: 고주파 충격 (소형 전자기기)
