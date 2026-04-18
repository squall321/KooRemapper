# Ceramic Material Library for LS-DYNA

결정성 세라믹 (Al2O3, AlN, ZrO2, Si3N4, PZT), LCP 재료의 LS-DYNA 카드 라이브러리.

## 재료 분류

### 1. 구조 세라믹 (Structural Ceramics)
- **Al2O3** (Alumina) — 기판, 프리미엄 케이스
- **AlN** (Aluminum Nitride) — 고열전도 기판
- **ZrO2** (Zirconia) — 프리미엄 백커버, 치과용
- **Si3N4** (Silicon Nitride) — 고신뢰성 베어링, IC 기판
- **SiC** (Silicon Carbide) — 참고용

### 2. 압전 세라믹 (Piezoelectric)
- **PZT-5A** — Soft piezo (sensor)
- **PZT-4** — Hard piezo (actuator, LRA motor)
- **AlN thin-film** — MEMS piezo

### 3. LCP (Liquid Crystal Polymer)
- **LCP Vectra A950** — 5G antenna substrate
- **LCP Vectra E130i** — reinforced

## 카드 선택

### 구조 세라믹 (Al2O3, AlN, ZrO2, Si3N4, SiC)
세라믹은 유리와 유사하게 **취성 파괴**:
- **MAT_001** Linear elastic (MID 1010xx)
- **MAT_001 + MAT_ADD_EROSION** (MID 1110xx) — σ_flexural 초과 시 erosion
- 금속처럼 소성 없음

### 압전 세라믹 (PZT 계열)
압전 구성방정식 필요:
- **MAT_028 (MOMENT_CURVATURE_BEAM)** — NOT applicable
- **LS-DYNA piezo coupling**: `*EM_EP_COUPLING` + MAT_ELASTIC
- 본 라이브러리는 **기계적 특성만** (탄성 + CTE)
- Full piezo analysis 는 EM solver 필요 (별도)

### LCP
이방성 폴리머 (fiber-like 배향):
- **MAT_001** Isotropic 근사 (대부분 해석에 충분)
- **MAT_002 (ORTHOTROPIC_ELASTIC)** — flow direction vs transverse

## MID 범위

| 카테고리 | Linear | Erode/Kin | Thermal |
|---------|--------|-----------|---------|
| Structural (6) | 101021~101026 | 111021~111026 | 131021~131026 |
| Piezo (3) | 101031~101033 | 111031~111033 | 131031~131033 |
| LCP (2) | 101041~101042 | 111041~111042 | 131041~131042 |

## 재료 목록 (11종)

### Structural Ceramics (6종)

| 재료 | E (GPa) | σ_flex (MPa) | k (W/m·K) | 용도 |
|------|--------|--------------|-----------|------|
| **Al2O3 96%** | 300 | 300 | 24 | 표준 기판, HTCC |
| **Al2O3 99.5%** | 370 | 400 | 32 | 고성능 기판 |
| **AlN** | 320 | 320 | **170** | 고열전도 기판 (IGBT) |
| **ZrO2 Y-TZP** | 210 | 1200 | 2 | 고인성 프리미엄 |
| **Si3N4** | 310 | 800 | 25 | 고신뢰성 베어링 |
| **SiC** | 410 | 390 | 120 | 반도체/우주 |

### Piezoelectric (3종)

| 재료 | E (GPa) | d33 (pC/N) | 용도 |
|------|--------|------------|------|
| **PZT-5A** (soft) | 61 | 374 | Sensor, hydrophone |
| **PZT-4** (hard) | 64 | 289 | Actuator, LRA motor |
| **AlN piezo** (thin film) | 330 | 5 | MEMS, BAW filter |

### LCP (2종)

| 재료 | E (GPa) | Tm (°C) | 용도 |
|------|--------|---------|------|
| **LCP Vectra A950** | 10.6 | 280 | 5G antenna |
| **LCP Vectra E130i** | 14.0 | 335 | Reinforced, connectors |

## 데이터 출처

- **CoorsTek Al2O3/AlN** TDS
- **Kyocera** fine ceramics TDS (Al2O3, AlN, Si3N4, ZrO2)
- **Saint-Gobain Crystals** (sapphire, Al2O3)
- **CTS Corp / APC International** PZT-4, PZT-5A TDS
- **Morgan Electro Ceramics** PZT series
- **Ticona Vectra LCP** A950, E130i TDS
- **Celanese Vectra** LCP series
- **ASM Engineered Materials Handbook Vol 4** — Ceramics

## 파일 구조

```
Ceramic/
├── README.md
├── CERAMIC_VALIDATION.md
├── ceramic_generator.py
├── ceramic_materials_db.json
├── ceramic_structural.k      # Al2O3, AlN, ZrO2, Si3N4, SiC
├── ceramic_piezo.k           # PZT-5A, PZT-4, AlN piezo
├── ceramic_lcp.k             # LCP Vectra A950, E130i
├── ceramic_thermal.k
└── references/
```
