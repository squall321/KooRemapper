# Rubber Material Library for LS-DYNA

엘라스토머(고무)의 **초탄성 + 점탄성** LS-DYNA 재료 카드 라이브러리.

## 왜 hyperelastic + viscoelastic인가

고무는 금속과 근본적으로 다른 거동을 보이며, 선형 탄성(MAT_001)만으로는 낙하/충격 해석에서 큰 오차가 발생한다:

1. **큰 변형 (strain > 50%)** — 선형 탄성 이론이 완전히 무너짐
2. **비압축성** — ν ≈ 0.49~0.4999
3. **응력-변형 곡선이 S-형** — Mooney-Rivlin, Ogden 모델 필요
4. **주파수 의존 감쇠** — Prony series로 표현
5. **Mullins 효과** — 첫 하중 후 강성 감소 (선택)

## Hybrid 전략: 3가지 변형

각 고무 재료를 **3가지 MID**로 제공:

### 1. Linear Elastic (MAT_001) — 빠른 해석
- `*MAT_ELASTIC`
- E, ν만 사용 (저변형 ≤ 10% 근사)
- **MID 100901~100999**
- 용도: 프리뷰, 디버깅, 저변형 해석

### 2. Mooney-Rivlin (MAT_027) — 표준 초탄성
- `*MAT_MOONEY-RIVLIN_RUBBER`
- C10, C01 두 상수 hyperelastic
- **MID 110901~110999**
- 용도: 고무 표준 정적/준정적 해석

### 3. Ogden + Viscoelastic (MAT_077_O) — 정밀 동적
- `*MAT_OGDEN_RUBBER` 또는 `*MAT_HYPERELASTIC_RUBBER`
- Ogden 3-term + Prony series
- **MID 130901~130999**
- 용도: 낙하 충격, 진동 감쇠, 주파수 응답

| 카드 | 변형률 범위 | 동적 감쇠 | 난이도 | MID |
|------|------------|---------|-------|-----|
| MAT_001 Linear | ≤10% | 없음 (rate-independent) | ★ | 1009xx |
| MAT_027 Mooney-Rivlin | ≤300% | 없음 (rate-independent) | ★★ | 1109xx |
| MAT_077_O Ogden+Visco | ≤500% | Prony series | ★★★★ | 1309xx |

## 재료 목록 (14종)

### Natural & Synthetic Rubbers (8종)

| 등급 | Full Name | 주용도 |
|------|-----------|-------|
| **NR** | Natural Rubber (polyisoprene) | 범용, 진동 마운트, 가스켓 |
| **SBR** | Styrene-Butadiene | 타이어 tread, 벨트 |
| **BR** | Butadiene | 타이어 sidewall |
| **IIR** | Butyl (Isobutylene-Isoprene) | 기밀/방수 씰, 튜브 |
| **CR** | Chloroprene (Neoprene) | 내유, 전선 피복 |
| **NBR** | Nitrile (Buna-N) | 연료 씰, O-ring |
| **HNBR** | Hydrogenated NBR | 고온 내유 (자동차) |
| **EPDM** | Ethylene-Propylene-Diene | 창호 씰, 루핑, 라디에이터 |

### High-Performance (4종)

| 등급 | Full Name | 주용도 |
|------|-----------|-------|
| **VMQ** | Silicone (PDMS) | 의료, 식품, 고온 (-55~250°C) |
| **FVMQ** | Fluorosilicone | 연료 저항 + silicone 특성 |
| **FKM** | Fluoroelastomer (Viton) | 극한 내유, 내약품 |
| **FFKM** | Perfluoroelastomer (Kalrez) | 반도체, 화학공정 |

### Thermoplastic Elastomer (2종)

| 등급 | Full Name | 주용도 |
|------|-----------|-------|
| **TPU** | Thermoplastic Polyurethane | 휴대기기 케이스, 롤러 |
| **TPE-S** | Styrenic TPE (SBS/SIS) | 그립, 오버몰딩 |

## MID 할당 규칙

| 범주 | Linear | Mooney-Rivlin | Ogden+Visco | Thermal |
|------|--------|---------------|-------------|---------|
| Natural/Synthetic (8종) | 100901~100908 | 110901~110908 | 130901~130908 | 120901~120908 |
| High-Perf (4종) | 100911~100914 | 110911~110914 | 130911~130914 | 120911~120914 |
| TPE (2종) | 100921~100922 | 110921~110922 | 130921~130922 | 120921~120922 |

**규칙**: 끝 3자리 매칭. 예: NR → `100901` / `110901` / `130901` / `120901`

## 카드 구조 예시

### Linear (MAT_001) for NR

```
*MAT_ELASTIC_TITLE
Natural Rubber Linear
$      MID        RO         E        PR
    100901 9.200e-10       3.0    0.4990
```

### Mooney-Rivlin (MAT_027) for NR

```
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
Natural Rubber Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110901 9.200e-10    0.3000    0.1000    0.4990       0.0       0.0       0.0
$                  LCID     (uniaxial test data, optional)
                     0
```

C10 = A, C01 = B (strain energy W = A(I1-3) + B(I2-3))

### Ogden + Prony (MAT_077_O) for NR

```
*MAT_HYPERELASTIC_RUBBER_TITLE  (or *MAT_077_O)
Natural Rubber Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF      REF
    130901 9.200e-10    0.4990         3         6      0.0       0.0       0.0
$       MU1     ALPHA1       MU2     ALPHA2       MU3     ALPHA3
      0.630       1.30    0.0012       5.00   -0.01      -2.00
$ Viscoelastic Prony series (up to 6 terms)
$       G_i      BETA_i
    0.0500  100.000
    0.0300  300.000
    0.0200  1000.00
```

## 단위계

LS-DYNA **mm, s, ton** 단위계:

| 물리량 | 단위 |
|--------|------|
| Stress (E, G, C10, Mu) | MPa |
| Density | ton/mm³ (= g/cc × 1e-9) |
| CTE | 1/K |
| TC | mW/mm/K (= W/m/K) |
| Cp | mm²/s²/K (= J/kg/K × 1e6) |

## Damping

고무는 **내부 마찰이 크고** 점탄성 Prony로 이미 반영되지만, 전체 구조 감쇠를 위해 추가 Rayleigh damping도 제공한다:

### Family damping ζ (at 1 kHz)

| 재료 | ζ | 근거 |
|------|---|------|
| NR, SBR | 3~5% | 소프트 고무, 높은 tan(δ) |
| NBR | 4~6% | 폴라 고무 |
| **IIR (Butyl)** | **15~25%** | **극한 감쇠** (진동 차단) |
| EPDM | 3~5% | 중간 |
| VMQ (Silicone) | 2~3% | 낮은 tan(δ) |
| FKM (Viton) | 2~4% | |
| TPU | 5~8% | |

## 데이터 출처

- **ASTM D2000** — Rubber classification system
- **ISO 4097** — EPDM rubber
- **ASM Engineered Materials Handbook Vol 2** (Engineering Plastics)
- **Rubber Technology** by Morton (3rd Edition, 1987)
- **Handbook of Rubber Bonding** by Crowther (2001)
- **Shin-Etsu Silicone TDS** (VMQ properties)
- **Dupont Viton TDS** (FKM properties)
- **BASF Elastollan TDS** (TPU properties)
- **Treloar (1975)** *The Physics of Rubber Elasticity* — Mooney-Rivlin/Ogden reference
- **Ogden, R.W. (1972)** "Large deformation isotropic elasticity" — Ogden model
- **Arruda & Boyce (1993)** — 8-chain model data for various rubbers

## 파일 구조

```
Rubber/
├── README.md                    # 본 문서
├── references/                  # TDS PDF 저장소
├── rubber_generator.py          # DB 내장 생성기
├── rubber_materials_db.json     # 파싱된 DB
├── rubber_natural.k             # NR, SBR, BR, IIR
├── rubber_synthetic.k           # CR, NBR, HNBR, EPDM
├── rubber_hiperf.k              # VMQ, FVMQ, FKM, FFKM
├── rubber_tpe.k                 # TPU, TPE-S
├── rubber_thermal.k             # 전체 열물성 (TC, Cp, CTE)
├── rubber_damping.k             # Rayleigh damping (MAT_001/027에 적용)
└── RUBBER_VALIDATION.md         # 문헌 검증 보고서
```

## 사용법

```bash
cd Rubber
python3 rubber_generator.py
# Generates all K-files and DB
```

LS-DYNA 모델에서:

```
*INCLUDE
rubber_natural.k
rubber_synthetic.k
rubber_hiperf.k
rubber_tpe.k
rubber_thermal.k
rubber_damping.k

*PART
Gasket_EPDM
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
        20         1    130908         0         0         0         0    120908
$                              ^^^^^^ Ogden+Visco EPDM              ^^^^^^ thermal
```

Linear/Mooney/Ogden 중 선택:
- **빠른 preview**: MID 1009xx (MAT_001 linear)
- **대변형 정적**: MID 1109xx (MAT_027 Mooney-Rivlin)
- **드롭/동적**: MID 1309xx (MAT_077_O Ogden+Prony) ★ 권장

## Cowper-Symonds for rubber?

고무는 점탄성 Prony series가 이미 rate dependence를 반영하므로 **Cowper-Symonds를 별도로 쓰지 않는다.** Prony series의 BETA 값이 rate 효과를 자동 표현한다.

## 주의사항

1. **Poisson's ratio**: 0.499 이상은 solid 요소에서 locking 발생. `*SECTION_SOLID`에 `ELFORM=-2` (fully integrated with assumed strain) 또는 `ELFORM=-1` 사용 권장.
2. **Foam rubbers**: 본 라이브러리는 solid rubber 전용. Foam (PORON, PU foam)은 Tape/tape_specialty.k 참조.
3. **Mullins effect (damage)**: 첫 하중 사이클에서 강성 감소. 반복 하중 해석이면 `*MAT_MULLINS` 또는 MAT_077 옵션 활성화 필요.
4. **Temperature**: 본 값은 25°C 기준. 고온/저온 해석은 별도 튜닝 필요.
