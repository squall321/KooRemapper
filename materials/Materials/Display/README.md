# Display Stack Material Library for LS-DYNA

스마트폰/디바이스 디스플레이 스택의 **등가 물성** LS-DYNA 재료 카드 라이브러리.

## Display Stack 구조

디스플레이는 여러 층의 복합 구조지만, 드롭 해석에서는 **단일 등가 재료**로 처리하는 것이 일반적.

### Rigid OLED (스마트폰 표준)
```
Cover Glass       ─── 0.5~0.8 mm (Gorilla Glass)
OCA               ─── 0.05~0.1 mm (tape)
Touch film        ─── 0.1 mm
OCA               ─── 0.05 mm
Polarizer         ─── 0.1 mm
Encapsulation Glass  ─ 0.2~0.3 mm
OLED TFE layer    ─── 0.01 mm
Glass substrate   ─── 0.3~0.5 mm
```

### Flexible OLED (Edge curved, foldable)
```
Window film (CPI or UTG) ─ 0.1 mm
OCA                       ─ 0.05 mm
Polarizer (flexible)      ─ 0.05 mm
Touch film                ─ 0.02 mm
OLED on PI substrate     ─ 0.03 mm
PI backplate              ─ 0.05 mm
```

### LCD Module (여전히 저가폰/태블릿)
```
Cover Glass              ─ 0.5 mm
OCA                       ─ 0.1 mm
Polarizer                 ─ 0.1 mm
Color filter glass       ─ 0.3 mm
Liquid crystal            ─ 0.004 mm
TFT glass substrate      ─ 0.3 mm
Polarizer                 ─ 0.1 mm
Backlight unit (BLU)     ─ 1.0~1.5 mm
```

## 등가 물성 계산 방법

**Rule of Mixtures (Voigt)** 두께 가중 평균:

```
E_eq = Σ(t_i × E_i) / Σ(t_i)
ρ_eq = Σ(t_i × ρ_i) / Σ(t_i)
CTE_eq = Σ(t_i × E_i × α_i) / Σ(t_i × E_i)
```

또는 **Classical Lamination Theory (CLT)** for bending:
```
D_eq = Σ(E_i × (z_i^3 - z_{i-1}^3) / 3)
```

### 본 라이브러리는 **homogenized single-layer equivalent** 제공

- 면내(xy) 거동은 Voigt 평균
- 면외(z) 거동은 Reuss 또는 무시 (얇음)

## 카드 선택

Display는 **복합 재료**이므로 3가지 모델 제공:

### 1. Linear Elastic (MAT_001) — 등가 등방성
- 가장 간단
- E는 가중 평균
- **MID 101051~101060**

### 2. Orthotropic Elastic (MAT_002) — 면내/면외 구분
- E_a = E_b (xy), E_c (z)
- Glass + polymer layer 혼합 반영
- **MID 111051~111060**

### 3. Elastic + Erosion (MAT_001 + MAT_ADD_EROSION)
- Cover glass 깨짐 반영
- **MID 121051~121060**

### Shell 모델링 경우
- `*MAT_034 FABRIC` 또는 `*PART_COMPOSITE` 가능
- 본 라이브러리는 solid 중심

## 재료 목록 (6종)

| 타입 | 설명 | E_eq (GPa) | 두께 (mm) | 용도 |
|------|------|-----------|-----------|------|
| **Rigid OLED** | 일반 스마트폰 | 60 | 1.2 | Samsung S, iPhone (non-fold) |
| **Flexible OLED** | Edge curved | 35 | 0.4 | Samsung edge display |
| **Foldable OLED UTG** | 접이식 with UTG | 40 | 0.6 | Galaxy Fold/Flip |
| **Foldable OLED CPI** | 접이식 with PI window | 10 | 0.3 | Early foldable |
| **LCD IPS Module** | 태블릿, 저가폰 | 25 | 2.0 | iPad, budget phones |
| **MicroLED Reference** | 차세대 (참고) | 70 | 0.8 | TV, AR glass |

## MID 범위

| 타입 | Linear | Orthotropic | Elastic+Erode | Thermal |
|------|--------|-------------|---------------|---------|
| All (6) | 101051~101056 | 111051~111056 | 121051~121056 | 131051~131056 |

## 데이터 출처

- **Samsung Display OLED** 공개 기술 자료
- **LG Display** OLED/LCD stack 기술 문헌
- **BOE, JDI** LCD module datasheet
- **PMC PubMed** foldable OLED mechanical characterization papers
- **TCL CSOT** display module specs
- **ASM Handbook Vol 2** 고분자/유리 혼합 계산

## 파일 구조

```
Display/
├── README.md
├── DISPLAY_VALIDATION.md
├── display_generator.py
├── display_materials_db.json
├── display_oled.k          # Rigid, Flexible OLED, Foldable
├── display_lcd.k           # LCD IPS, VA modules
├── display_thermal.k
└── references/
```
