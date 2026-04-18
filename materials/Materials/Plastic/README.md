# Plastic (Engineering Thermoplastic) Material Library for LS-DYNA

엔지니어링 플라스틱 (PC, ABS, PA, PBT, PEEK 등)의 **탄소성 + 점탄성** LS-DYNA 재료 카드 라이브러리. Metal/Rubber/PCB와 동일한 구조로 제공.

## 왜 플라스틱은 탄소성인가

플라스틱은 금속과 고무의 중간 특성을 가진다:

1. **항복점 존재** — σ_y에서 yielding 시작 (60~150 MPa)
2. **큰 변형률 속도 의존성** — PC는 1000x rate로 σ_y 30% 증가
3. **점탄성** — 크리프, 응력 이완
4. **열역학적 전이** — Tg 근처에서 물성 급변
5. **필러 영향** — GF/CF 강화 시 이방성 (본 라이브러리는 등방 근사)

### 낙하 해석 관점

- 스마트폰 드롭: **PC/ABS 미드프레임, PC 백커버, PA 커넥터**가 충격 흡수
- Yielding 발생 → 에너지 흡수 → crack 전파
- 탄성만 쓰면 응력 과대, 변형 과소 → 부정확한 결과

## 하이브리드 전략: 4가지 경화 변형 + SAMP-1

Metal과 동일한 4 variants + 고급 SAMP-1 총 **5가지 MID**:

### 1. Linear Elastic (MAT_001)
- `*MAT_ELASTIC`
- E, ν만 사용 (preview용, ≤5% strain)
- **MID 100961~100975**

### 2. Bilinear Isotropic (MAT_024)
- `*MAT_PIECEWISE_LINEAR_PLASTICITY` SIGY + ETAN
- 표준 해석
- **MID 110961~110975**

### 3. Multi-linear Isotropic (MAT_024 + LCSS)
- `*MAT_PIECEWISE_LINEAR_PLASTICITY` + `*DEFINE_CURVE`
- 정밀 σ-ε 커브
- **MID 120961~120975**

### 4. Bilinear Kinematic Mixed (MAT_003)
- `*MAT_PLASTIC_KINEMATIC` BETA=0.5 (50/50)
- Cyclic loading, Bauschinger
- **MID 130961~130975**

### 5. SAMP-1 Advanced Polymer (MAT_187)
- `*MAT_SAMP-1` — 압축/인장 비대칭, 네킹, 경화
- 최고 정밀, 폴리머 전용
- **MID 140961~140975**

### Thermal TMID
- **TMID 150961~150975**

| 카드 | 난이도 | 정확도 | 용도 |
|------|------|--------|------|
| MAT_001 Linear | ★ | 저변형 | Preview, debug |
| MAT_024 Bilinear | ★★ | 좋음 | **표준 해석** |
| MAT_024 Multilinear | ★★★ | 매우 좋음 | 정밀 σ-ε |
| MAT_003 Kinematic | ★★★ | 좋음 | **Cyclic/Bauschinger** |
| **MAT_187 SAMP-1** | ★★★★★ | 최고 | **Crack, necking, damage** |

## 재료 목록 (15종)

### Standard Engineering Thermoplastics (8종)

| 등급 | 설명 | E (GPa) | σ_y (MPa) | 용도 |
|------|------|--------|-----------|------|
| **PC** | Polycarbonate (Makrolon/Lexan) | 2.3 | 62 | 백커버, 렌즈 |
| **ABS** | Acrylonitrile-Butadiene-Styrene | 2.3 | 42 | 하우징, 프레임 |
| **PC/ABS** | PC/ABS blend | 2.4 | 55 | **스마트폰 미드프레임** |
| **PA6** | Nylon 6 (polyamide) | 2.7 | 75 | 커넥터, 기어 |
| **PA66** | Nylon 66 | 3.0 | 80 | 커넥터, 기어 |
| **PBT** | Polybutylene Terephthalate | 2.6 | 60 | 커넥터, 스위치 |
| **POM** | Polyoxymethylene (Delrin) | 3.1 | 72 | 기어, 슬라이드 |
| **PP** | Polypropylene | 1.5 | 35 | 저가 하우징 |

### Reinforced Plastics (4종)

| 등급 | 설명 | E (GPa) | σ_y (MPa) | 용도 |
|------|------|--------|-----------|------|
| **PA66-GF30** | Nylon 66 + 30% Glass Fiber | 9.5 | 180 | 고강도 커넥터 |
| **PA66-GF50** | Nylon 66 + 50% Glass Fiber | 16.0 | 230 | 구조 부품 |
| **PBT-GF30** | PBT + 30% GF | 10.0 | 130 | 전기부품 |
| **PPS-GF40** | PPS + 40% GF | 14.0 | 180 | 고온 구조 |

### High-Performance (3종)

| 등급 | 설명 | E (GPa) | σ_y (MPa) | 용도 |
|------|------|--------|-----------|------|
| **PPS** | Polyphenylene Sulfide (Ryton) | 3.8 | 80 | 고온 부품 |
| **PEEK** | Polyetheretherketone | 3.6 | 100 | 의료, 항공 |
| **PEI** | Polyetherimide (Ultem) | 3.0 | 105 | 항공, 고온 전기 |

## MID 할당 규칙

| 범주 | Linear | Bilinear | Multi | Kinematic | SAMP-1 | TMID |
|------|--------|----------|-------|-----------|--------|------|
| Standard (8종) | 100961~100968 | 110961~110968 | 120961~120968 | 130961~130968 | 140961~140968 | 150961~150968 |
| Reinforced (4종) | 100971~100974 | 110971~110974 | 120971~120974 | 130971~130974 | 140971~140974 | 150971~150974 |
| High-Perf (3종) | 100975~100977 | 110975~110977 | 120975~120977 | 130975~130977 | 140975~140977 | 150975~150977 |

**규칙**: 끝 3자리 매칭. 예: PC/ABS → `100963` / `110963` / `120963` / `130963` / `140963` / `150963`

## Cowper-Symonds for Plastics (중요)

플라스틱은 금속과 다른 rate 의존 특성:

| 재료 | C (/s) | P | Reference |
|------|--------|---|-----------|
| **PC** | 1.4 | 2.5 | Kwon et al (2008), Mulliken-Boyce (2006) |
| **ABS** | 5.0 | 3.0 | Louche et al (2009) |
| **PC/ABS** | 2.5 | 2.8 | Estimated blend |
| **PA6** | 0.5 | 5.0 | Very rate-sensitive |
| **PA66** | 0.8 | 4.5 | |
| **PA66-GF** | 50 | 2.0 | Fiber suppresses rate effect |
| **PBT** | 3.0 | 3.5 | |
| **POM** | 800 | 2.0 | Semi-crystalline, less sensitive |
| **PP** | 3.0 | 3.5 | |
| **PPS** | 100 | 2.5 | Aromatic, less sensitive |
| **PEEK** | 40 | 2.0 | |
| **PEI** | 50 | 2.5 | |

**핵심**: PC, PA 같은 비결정 플라스틱은 C가 매우 작아서 (1~5) rate에 매우 민감. PEEK, PPS, GF 강화는 C가 커서 상대적으로 덜 민감.

## 단위계

LS-DYNA **mm, s, ton**:

| 물리량 | 단위 |
|--------|------|
| Stress (E, σ) | MPa |
| Density | ton/mm³ (= g/cc × 1e-9) |
| CTE | 1/K (= ppm/K × 1e-6) |
| TC | mW/mm/K (= W/m/K) |
| Cp | mm²/s²/K (= J/kg/K × 1e6) |

## Damping (Rayleigh)

| 재료 군 | ζ | 근거 |
|--------|---|------|
| Amorphous glassy (PC, PEI) | 2~3% | Low damping |
| Semi-crystalline (PA, POM) | 3~5% | Crystalline regions add damping |
| ABS, PC/ABS | 4~6% | Rubber phase increases damping |
| GF-reinforced | 2~3% | Fiber reduces damping |
| PP (flexible) | 5~8% | Highest among engineering plastics |

## SAMP-1 (MAT_187) 특징

SAMP-1 = **Semi-Analytical Model for Polymers** — LS-DYNA 폴리머 전용 고급 카드:

- **인장/압축 비대칭** — 플라스틱의 실제 거동 반영
- **네킹 안정화** — PC, PA의 strain localization
- **Damage coupling** — 변형에 따른 강성 감소
- **Strain rate** — 자체 rate formulation
- **Failure criteria** — multiple options

**Trade-off**: 파라미터 20+ 개 필요, 각 재료별로 측정 데이터 필수. 본 라이브러리에서는 **대표값 기반 근사**를 제공하며, 정밀 해석 시 DIC 측정 후 파라미터 fitting 권장.

## 데이터 출처

- **Covestro Makrolon** PC series TDS
- **SABIC Lexan, Cycolac (ABS), Cycoloy (PC/ABS), Ultem (PEI)** TDS
- **BASF Ultramid** PA6/PA66/PA66-GF series TDS
- **DuPont Zytel** (PA), **Delrin** (POM), **Crastin** (PBT) TDS
- **Solvay Ryton** (PPS) TDS
- **Victrex PEEK** TDS
- **PMC 10179745** — PC high strain rate tension data
- **ScienceDirect S0142941823000661** — PC wide rate/temp
- **Mulliken & Boyce (2006)** — PC constitutive model
- **Kwon et al (2008)** — PC strain rate
- **Louche et al (2009)** — ABS thermomechanical

## 파일 구조

```
Plastic/
├── README.md                   # 본 문서
├── PLASTIC_VALIDATION.md       # 문헌 검증
├── plastic_generator.py        # 통합 생성기
├── plastic_materials_db.json   # 파싱된 DB
├── plastic_standard.k          # 표준 플라스틱 (8종, 5 variants each)
├── plastic_reinforced.k        # 강화 플라스틱 (4종)
├── plastic_hiperf.k            # PPS, PEEK, PEI (3종)
├── plastic_thermal.k           # 15종 열물성
├── plastic_damping.k           # 75개 Rayleigh part sets (15 × 5)
└── references/                 # TDS 저장소
```

## 사용법

```bash
cd Plastic
python3 plastic_generator.py
# Generates all K-files and JSON DB
```

LS-DYNA 모델에서:

```
*INCLUDE
plastic_standard.k
plastic_reinforced.k
plastic_hiperf.k
plastic_thermal.k
plastic_damping.k

*PART
Phone_Midframe_PCABS
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
        15         1    110963         0         0         0         0    150963
$                              ^ PC/ABS bilinear              ^ thermal
```

각 재료 MID 선택 가이드:
- **빠른 preview**: 1009xx (Linear)
- **표준 낙하**: **1109xx (Bilinear)** ★
- **정밀 소성**: 1209xx (Multilinear)
- **사이클 하중**: 1309xx (Kinematic Mixed)
- **Damage/necking 예측**: 1409xx (SAMP-1)

## 주의사항

1. **Temperature dependence 미포함** — 25°C 기준. 고온 해석 시 MAT_024의 온도 테이블 옵션 사용
2. **이방성 미포함** — GF 재료도 등방성 근사. 사출 성형 유동 방향 중요하면 MAT_022 orthotropic 고려
3. **SAMP-1 파라미터**는 대표값이며, 정밀 해석에는 실측 fitting 권장
4. **MAT_001 linear는 preview 전용** — 실제 drop 해석에는 MAT_024 이상 사용
