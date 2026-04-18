# Glass Material Library for LS-DYNA

스마트폰/전자기기용 유리 재료 (cover glass, sapphire, optical glass) LS-DYNA 재료 카드 라이브러리.

## 왜 Glass 전용 카드가 필요한가

유리는 **취성 파괴** 재료로, 금속/플라스틱과 근본적으로 다른 거동을 보인다:

1. **소성 변형 없음** — yield 없이 바로 crack 전파
2. **높은 강성** (E = 70~90 GPa) + **높은 경도**
3. **낮은 CTE** (3~9 ppm/K)
4. **주 응력(principal stress) 기반 파괴** — 인장 응력이 파괴 임계 도달 시 즉시 crack
5. **이온 교환 강화** (Gorilla 계열): 표면 압축 응력층 + 내부 인장 응력

낙하 해석에서 **cover glass는 가장 취약한 구성요소** — 정확한 모델링이 필수.

## 카드 선택: 3 variants per material

### 1. Linear Elastic (MAT_001) — 기본 preview
- `*MAT_ELASTIC`
- E, ν, ρ만
- **MID 101001~101015**
- 빠른 해석, 파괴 없음

### 2. Elastic + Erosion (MAT_001 + MAT_ADD_EROSION)
- **표준 낙하 해석**
- 주응력/효과응력 기반 요소 제거
- **MID 111001~111015**
- Principal stress criterion: `σ_max > σ_strength → erode`

### 3. Glass Failure (MAT_032 LAMINATED_GLASS) — 선택
- `*MAT_LAMINATED_GLASS` (MAT_032)
- Multi-layer glass + interlayer (PVB, SentryGlas)
- **MID 121001~121005** (제한적, laminated용)
- 자동차 윈드실드 해석용 (스마트폰은 single layer)

### 본 라이브러리는 **Variant 1 + 2** 중심 (스마트폰 용)

| 카드 | 용도 | MID |
|------|------|-----|
| MAT_001 Linear | Preview, 빠른 해석 | 1010xx |
| **MAT_001 + MAT_ADD_EROSION** | **표준 낙하 해석** ★ | 1110xx |

## 재료 목록 (8종)

### Soda-lime / Aluminosilicate (2종)
| 등급 | 설명 | 제조사 |
|------|------|-------|
| **Soda-lime** | 일반 유리 (창유리, 거울) | Generic |
| **Aluminosilicate** | 화학강화 표준 (Dragontrail) | AGC Asahi |

### Chemically Strengthened (4종) — 이온교환 강화
| 등급 | 세대 | 비고 |
|------|------|-----|
| **Gorilla Glass 3** | 2013 | NDR 기술, 기본 |
| **Gorilla Glass 5** | 2016 | drop 강화 |
| **Gorilla Glass 6** | 2018 | 반복 drop |
| **Gorilla Glass Victus** | 2020 | 현재 플래그십 표준 |

### Sapphire (2종)
| 등급 | 배향 | 주용도 |
|------|------|-------|
| **Sapphire C-plane** | (0001) | 카메라 렌즈, Watch face |
| **Sapphire A-plane** | (1120) | 고강도 윈도우 |

## MID 범위

| 카테고리 | Linear (MAT_001) | Elastic+Erode | Thermal TMID |
|---------|------------------|--------------|--------------|
| Soda-lime/Alumino (2) | 101001~101002 | 111001~111002 | 131001~131002 |
| Gorilla (4) | 101003~101006 | 111003~111006 | 131003~131006 |
| Sapphire (2) | 101011~101012 | 111011~111012 | 131011~131012 |

**규칙**: 끝 3자리 매칭

## Erosion 기준

Glass는 **인장 응력에서 파괴**하므로, MAT_ADD_EROSION에서:

```
SIGP1 = σ_strength_tensile  (principal stress max)
MXEPS = ε_failure (very small, ~0.01)
```

### 재료별 파괴 응력 (실측값)

| 재료 | σ_tensile (pristine) | σ_tensile (CS layer) | 사용값 |
|------|---------------------|----------------------|--------|
| Soda-lime | 40~50 MPa | N/A | 45 MPa |
| Aluminosilicate | 100~150 | ~500 (CS) | 150 MPa |
| Gorilla 3 | 100 | **680** (CS) | 680 MPa |
| Gorilla 5 | 100 | **850** (CS) | 850 MPa |
| Gorilla 6 | 100 | **850** (CS) | 850 MPa |
| Gorilla Victus | 100 | **≥900** (CS) | 900 MPa |
| Sapphire C | 400~1000 | N/A | 700 MPa |
| Sapphire A | 400~1000 | N/A | 800 MPa |

**Note**: Chemically strengthened glass는 **표면 압축 응력층(CS) > 600 MPa**이므로, 표면에 **순 인장 응력이 CS를 초과할 때만** 균열이 발생한다. 이 값을 erosion 임계값으로 사용.

## 단위계

LS-DYNA **mm, s, ton**:

| 물리량 | 단위 |
|--------|------|
| Stress, σ_strength | MPa |
| Density | ton/mm³ |
| CTE | 1/K |
| TC | mW/mm/K (= W/m/K) |
| Cp | mm²/s²/K (= J/kg/K × 1e6) |

## 데이터 출처

- **Corning Gorilla Glass PI Sheets** (Gorilla Glass 5/6/Victus)
- **AGC Dragontrail** TDS
- **Goodfellow Sapphire** (single crystal Al2O3, 99.9%)
- **AZoM 1721** — Sapphire single crystal properties
- **Kyocera Sapphire** TDS
- **ASM Handbook Vol 4** — Ceramics and Glasses
- **MatWeb** glass database

## 파일 구조

```
Glass/
├── README.md
├── GLASS_VALIDATION.md
├── glass_generator.py
├── glass_materials_db.json
├── glass_cover.k           # Soda-lime, Aluminosilicate, Gorilla 3/5/6/Victus
├── glass_sapphire.k        # Sapphire C-plane, A-plane
├── glass_thermal.k         # 8 thermal cards
└── references/
```

## 사용법

```bash
cd Glass
python3 glass_generator.py
```

LS-DYNA 모델에서:

```
*INCLUDE
glass_cover.k
glass_sapphire.k
glass_thermal.k

*PART
Cover_Glass_Victus
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
        50         1    111006         0         0         0         0    131006
$                              ^ Gorilla Victus with erosion   ^ thermal
```

## 주의사항

1. **Cover glass 두께**: 실제 스마트폰 cover glass는 0.5~0.8 mm. 메쉬 시 3~5 layer 권장.
2. **CS layer 반영**: 화학강화 유리는 표면 ~75 μm 압축층 존재. 정밀 해석은 through-thickness variation 필요하지만 단순 erosion 모델은 평균값 사용.
3. **Sapphire anisotropy**: Sapphire는 결정 방향에 따라 E=340~380 GPa 범위. 본 라이브러리는 **등방성 평균값** 제공.
4. **Damping**: Glass는 internal friction 매우 낮음 (ζ~0.1%). 구조 감쇠는 인접 접착층에서 지배.
5. **No damping file**: Glass는 damping이 매우 낮아 별도 파일 생략. 필요시 Tape/tape damping 참조.
