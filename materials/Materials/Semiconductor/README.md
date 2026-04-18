# Semiconductor Material Library for LS-DYNA

반도체 패키징 재료 (EMC, underfill, die attach 등)의 LS-DYNA 재료 카드 라이브러리.

**현재 구성**: **EMC (Epoxy Molding Compound)** — IC 패키지 body 재료

## EMC란

**Epoxy Molding Compound** — BGA, QFN, CSP, LGA 등 IC 패키지를 감싸는 몰딩 재료. 에폭시 수지 + 실리카 필러(70~90 vol%) + 경화제 + 첨가제로 구성.

### 물성 특성

- **매우 단단한 glassy polymer** (E = 15~30 GPa)
- 실리카 필러가 대부분 → **거의 등방성**
- Tg 이하에서 **거의 탄성 거동** (낙하 strain < 1%)
- **취성 파괴** — 소성 변형 없음, σ_u 도달 시 crack
- **낮은 CTE** (α1 = 7~10 ppm/K below Tg, α2 = 30~40 ppm/K above Tg)
- Tg = 120~200°C (grade에 따라)

## 카드 선택: MAT_001 + 선택적 MAT_006

EMC는 낙하 해석에서 거의 순수 탄성 영역에 있으므로 **단순 탄성 모델로 충분**합니다.

### 1. MAT_001 (ELASTIC) — 기본

```
*MAT_ELASTIC
$      MID        RO         E        PR
    100951 1.900e-09   20000.0    0.3000
```

### 2. MAT_006 (VISCOELASTIC) — 약한 rate 효과 (선택)

```
*MAT_VISCOELASTIC
$      MID        RO      BULK        G0        GI      BETA
    110951 1.900e-09   16667.0    7900.0    7692.0    1000.0
```

G0/GI 비율 매우 작음 (1.03x) → 거의 탄성, rate 효과 약간 반영.

### MID 범위

| 카테고리 | Linear (MAT_001) | VE (MAT_006) | Thermal TMID |
|---------|------------------|--------------|--------------|
| EMC standard | 100951~100958 | 110951~110958 | 120951~120958 |

## 재료 목록 (8종)

| 등급 | 제조사 | Tg | 용도 |
|------|-------|-----|------|
| **EMC_HighTg_Green** | Sumitomo EME-G700 | 175°C | 범용 BGA/QFN |
| **EMC_MidTg_Standard** | Hitachi CEL-9200 | 155°C | 표준 패키지 |
| **EMC_LowTg_Fast** | Shin-Etsu KMC-184 | 125°C | 저온 경화 |
| **EMC_LowCTE_Filled** | Sumitomo EME-G780 | 165°C | 저 CTE 고집적 |
| **EMC_Green_HighTg** | Resonac GE-series | 180°C | 환경규제 |
| **EMC_Underfill_Mold** | Namics MUF | 140°C | Molded Underfill |
| **EMC_WLP_BLK** | Sumitomo CRP-9800 | 160°C | Wafer-level packaging |
| **EMC_HighK_Thermal** | Hitachi GE-100 | 170°C | 고열전도 |

## 데이터 출처

- **Sumitomo Bakelite** SUMIKON EME series (EME-G700, G780) TDS
- **Hitachi Chemical** CEL-9200, GE-100 TDS
- **Shin-Etsu** KMC-184 TDS
- **Resonac (formerly Hitachi Chemical)** GE-series product guide
- **Namics** Molded Underfill series
- **PMC 10179932** — EMC warpage study with various grades
- **ASM Electronic Materials Handbook Vol 1** — Packaging

## 주의사항

1. **CTE α1/α2 분리**: EMC는 Tg에서 CTE가 크게 변하지만, MAT_ADD_THERMAL_EXPANSION은 단일값만. 상온 낙하 해석은 α1만 사용.
2. **Moisture sensitivity**: EMC는 수분 흡수 후 열처리에서 popcorn cracking 발생 가능. 이건 MAT_110 (MOISTURE_TEMP)이 필요하지만 본 라이브러리에선 미포함.
3. **Brittle failure**: 낙하에서 EMC가 crack 되려면 MAT_ADD_EROSION 추가 필요.
