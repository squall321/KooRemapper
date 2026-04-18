# Magnet Material Library for LS-DYNA

영구자석 및 자성 재료의 **구조 해석** LS-DYNA 재료 카드 라이브러리.

## 범위: **기계적 물성 only**

본 라이브러리는 **구조 해석 용도의 기계적 특성만** 제공:
- ρ, E, ν (탄성 특성)
- σ_flex (취성 파괴 한계)
- CTE, TC, Cp (열물성)

**자기력 해석 (Lorentz force, demagnetization)은 별도 EM solver 필요**:
- `*EM_MAT_PERMANENT_MAGNET`
- `*EM_CONTROL`

본 라이브러리는 **permanent magnet의 구조적 거동**에만 집중.

## 재료 분류

### 1. NdFeB (Neodymium Iron Boron) — 영구자석 최강
스마트폰 필수: **스피커, 리니어 모터(LRA), 카메라 OIS, 무선충전, 진동모터**

| 등급 | BHmax (MGOe) | T_max | 용도 |
|------|-------------|-------|------|
| **N35** | 35 | 80°C | 경제형 |
| **N42** | 42 | 80°C | 중급 (표준 스피커) |
| **N52** | 52 | 65°C | **최고 에너지** (카메라 OIS, 프리미엄 스피커) |
| **N35SH** | 35 | 150°C | 고온 내성 |

### 2. SmCo (Samarium Cobalt)
- 고온 환경, 부식 저항 (코팅 불필요)
- 스마트폰에는 덜 사용, 프로 장비에 주로

| 등급 | BHmax | T_max | 용도 |
|------|-------|-------|------|
| **SmCo 2:17** | 24~33 | 350°C | 고온 환경 |
| **SmCo 1:5** | 16~22 | 250°C | 표준 |

### 3. Hard Ferrite (저가)
- Sr-ferrite (SrFe12O19)
- 가전제품, 장난감
- 스마트폰에는 거의 사용 안 됨 (낮은 에너지)

### 4. Bonded Magnet
- 폴리머 + 자성 분말 (injection molded)
- 복잡 형상 가능

## 카드 선택

자석 재료는 **세라믹 같은 취성 재료**:
- 소결 자석 (NdFeB, SmCo, Ferrite)은 **금속-세라믹 중간 특성**
- 매우 단단하지만 취성 (drop 시 crack)

### 3 variants

1. **MAT_001 Linear** (MID 101061~)
2. **MAT_001 + MAT_ADD_EROSION** (MID 111061~) — crack 반영
3. **MAT_002 Orthotropic** (MID 121061~) — 자화 방향 이방성

### 자화 방향 이방성
소결 자석은 **자화 방향으로 약간의 이방성**을 가짐:
- 자화 축 방향: E 약간 높음
- 수직 방향: E 약간 낮음
- 차이 ~5~10% (무시 가능 → isotropic 근사 사용)

본 라이브러리는 **isotropic** 근사 주로 사용, orthotropic은 참고용.

## 재료 목록 (6종)

| 재료 | 등급 | E (GPa) | ρ (g/cc) | σ_flex (MPa) | 용도 |
|------|------|---------|----------|--------------|------|
| **NdFeB N35** | 경제형 | 150 | 7.40 | 270 | 저가 스피커 |
| **NdFeB N42** | 표준 | 160 | 7.50 | 280 | 표준 스피커, 무선충전 |
| **NdFeB N52** | 최고 | 170 | 7.60 | 290 | **프리미엄 (카메라 OIS)** |
| **SmCo 2:17** | 고온 | 150 | 8.40 | 150 | 프로 장비 |
| **SrFerrite Y30** | 저가 | 160 | 4.90 | 70 | 장난감, 가전 |
| **Bonded NdFeB** | 유연 | 12 | 5.50 | 100 | 복잡 형상 |

## MID 범위

| 재료 | Linear | Erode | Orthotropic | Thermal |
|------|--------|-------|-------------|---------|
| Magnets (6) | 101061~101066 | 111061~111066 | 121061~121066 | 131061~131066 |

## 데이터 출처

- **Arnold Magnetic Technologies** NdFeB N-series datasheet
- **Vacuumschmelze (VAC)** Vacodym NdFeB
- **Hitachi Metals Neomax** series
- **Shin-Etsu Rare-Earth Magnet** TDS
- **Ceramic Magnetics / Magnet Applications** Ferrite
- **Sura Magnets** SmCo 2:17
- **MMG Canada** Bonded magnet

## 파일 구조

```
Magnet/
├── README.md
├── MAGNET_VALIDATION.md
├── magnet_generator.py
├── magnet_materials_db.json
├── magnet_ndfeb.k        # N35, N42, N52
├── magnet_smco.k         # SmCo 2:17
├── magnet_ferrite.k      # Hard ferrite, Bonded
├── magnet_thermal.k
└── references/
```

## 주의사항

1. **자기력 시뮬레이션**: 본 라이브러리는 **구조만** 제공. Lorentz force나 탈자 해석은 `*EM_*` 카드 추가 필요.
2. **결정 방향**: 소결 자석은 약간 이방성이지만 본 라이브러리는 **등방성 근사** 사용.
3. **브리틀 파괴**: NdFeB는 특히 drop test에서 **crack 위험 큼** — EROSION 변형 사용 권장.
4. **온도 민감도**: NdFeB는 100°C 이상에서 탈자. 본 물성은 25°C 기준.
