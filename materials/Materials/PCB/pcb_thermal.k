$ ========================================================================
$ PCB PREPREG (PPG) THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)
$   Cp (specific heat)        : mm^2/s^2/K  (= J/kg/K * 1e6)
$   CTE (thermal expansion)   : 1/K  (= ppm/K * 1e-6)
$
$ TMID convention: structural MID + 20000  (pcb_prepreg_materials.k uses 1001xx)
$   100101 (FR-4 Std)         -> TMID 120101
$   100201 (Doosan DS-7402)   -> TMID 120201
$   100301 (Elite EM-370Z)    -> TMID 120301
$   ...
$
$ Note: CTE is already applied in pcb_prepreg_materials.k via
$       *MAT_ADD_THERMAL_EXPANSION. This file only adds thermal conduction
$       and heat capacity needed for COUPLED THERMAL-STRUCTURAL analysis.
$
$ Data sources:
$   - FR-4 generic: Wikipedia (k=0.29 z, 0.81 xy), ASM Handbook
$   - Isola 370HR TDS: k=0.4 W/m/K
$   - Doosan CCL TDS (direct extraction): k=0.3~1.3 W/m/K
$   - Elite Material TDS: k=0.46~0.6 W/m/K
$   - Rogers RO3003/RO4350B TDS
$   - DuPont Kapton: k=0.12, Cp=1090
$   - Polyimide typical: k=0.12, Cp=1090
$
$ Specific heat (Cp) values:
$   Generic epoxy/FR-4:  ~900 J/kg/K (well-established)
$   Polyimide:           ~1090 J/kg/K
$   PTFE composite:      ~970 J/kg/K
$   ABF (epoxy-based):   ~950 J/kg/K
$
$ Note: MAT_THERMAL_ISOTROPIC is an isotropic model. PCB PPG is actually
$ anisotropic (xy > z by ~2-3x due to glass fiber weave), but the average
$ value (~0.4 W/m/K) is used here for simplicity. For precise through-plane
$ heating, use *MAT_THERMAL_ORTHOTROPIC (MAT_T03) with separate TCX/TCY/TCZ.
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. General PPG (100101~100112)
$ ========================================================================
$
$$ --- PPG FR-4 Standard (Tg 130C) ---
$$ k=0.40 W/m/K (avg), Cp=900 J/kg/K, Tg=130C
*MAT_THERMAL_ISOTROPIC_TITLE
FR-4 Standard (Tg 130C) Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120101 1.850e-09         0    1.0000       0.0       0.0
$       HC         TC
 9.000e+08 4.000e-01
$
$$ --- PPG Hitachi MCL-E-679F (Tg 150C) ---
$$ k=0.4 W/m/K, Cp=900 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Hitachi MCL-E-679F Thermal
    120102 1.870e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- PPG Panasonic R-1566 (Tg 170C) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Panasonic R-1566 Thermal
    120103 1.880e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- PPG Isola 370HR (Tg 180C) ---
$$ Isola 370HR TDS: TC=0.4 W/m/K
*MAT_THERMAL_ISOTROPIC_TITLE
Isola 370HR Thermal
    120104 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- PPG Panasonic Megtron-6 (Tg 185C) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Panasonic Megtron-6 Thermal
    120105 1.880e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- PPG BT Resin (AGC N5000) ---
$$ BT epoxy: k=0.4 W/m/K
*MAT_THERMAL_ISOTROPIC_TITLE
BT Resin (AGC N5000) Thermal
    120106 1.900e-09         0    1.0000       0.0       0.0
 9.500e+08 4.000e-01
$
$$ --- PPG Isola P95 Polyimide (Tg 250C) ---
$$ Polyimide: k=0.12 W/m/K, Cp=1090 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Isola P95 Polyimide Thermal
    120107 1.400e-09         0    1.0000       0.0       0.0
 1.090e+09 1.200e-01
$
$$ --- PPG Cyanate Ester (Tg 240C) ---
$$ CE: k=0.3 W/m/K
*MAT_THERMAL_ISOTROPIC_TITLE
Cyanate Ester Thermal
    120108 1.850e-09         0    1.0000       0.0       0.0
 9.200e+08 3.000e-01
$
$$ --- PPG Rogers RO3003 (PTFE) ---
$$ PTFE/ceramic: k=0.50 W/m/K, Cp=970 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Rogers RO3003 PTFE Thermal
    120109 2.200e-09         0    1.0000       0.0       0.0
 9.700e+08 5.000e-01
$
$$ --- PPG Rogers RO4350B (Tg 280C) ---
$$ Rogers RO4350B TDS: TC=0.69 W/m/K
*MAT_THERMAL_ISOTROPIC_TITLE
Rogers RO4350B Thermal
    120110 1.860e-09         0    1.0000       0.0       0.0
 9.200e+08 6.900e-01
$
$$ --- PPG Ajinomoto ABF GX (Tg 160C) ---
$$ ABF: k=0.3 W/m/K, Cp=950 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ajinomoto ABF GX Thermal
    120111 1.400e-09         0    1.0000       0.0       0.0
 9.500e+08 3.000e-01
$
$$ --- PPG DuPont Kapton Polyimide ---
$$ DuPont Kapton: k=0.12 W/m/K, Cp=1090 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
DuPont Kapton Polyimide Thermal
    120112 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 1.200e-01
$
$ ========================================================================
$ 2. Doosan (두산전자) - Direct TDS extraction (100201~100237)
$ ========================================================================
$
$$ --- Doosan DS-7402 (Tg 165C, TC=0.45 W/m/K per TDS) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402 Thermal
    120201 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.500e-01
$
$$ --- Doosan DS-7402M (TC=0.45) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402M Thermal
    120202 1.870e-09         0    1.0000       0.0       0.0
 9.000e+08 4.500e-01
$
$$ --- Doosan DS-7402BS(DF) (TC=0.35) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402BS(DF) Thermal
    120203 1.600e-09         0    1.0000       0.0       0.0
 9.500e+08 3.500e-01
$
$$ --- Doosan DS-7402LC (TC=0.6 W/m/K, ceramic filled) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402LC Thermal
    120204 2.030e-09         0    1.0000       0.0       0.0
 8.500e+08 6.000e-01
$
$$ --- Doosan DS-7402H (TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402H Thermal
    120205 1.870e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DS-7402HD (TC=0.6) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7402HD Thermal
    120206 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 6.000e-01
$
$$ --- Doosan DS-8402H (TC=0.45, Low-loss HF) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8402H Thermal
    120207 1.870e-09         0    1.0000       0.0       0.0
 9.000e+08 4.500e-01
$
$$ --- Doosan DS-8502LC (TC=0.6, Tg 280C CE-based) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8502LC Thermal
    120208 1.960e-09         0    1.0000       0.0       0.0
 8.800e+08 6.000e-01
$
$$ --- Doosan DS-8502SQ (TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8502SQ Thermal
    120209 1.950e-09         0    1.0000       0.0       0.0
 8.800e+08 5.000e-01
$
$$ --- Doosan DS-8502SQN (TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8502SQN Thermal
    120210 1.950e-09         0    1.0000       0.0       0.0
 8.800e+08 5.000e-01
$
$$ --- Doosan DS-8502HQ (TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8502HQ Thermal
    120211 1.930e-09         0    1.0000       0.0       0.0
 8.800e+08 5.000e-01
$
$$ --- Doosan DS-8502HQN (TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-8502HQN Thermal
    120212 1.930e-09         0    1.0000       0.0       0.0
 8.800e+08 5.000e-01
$
$$ --- Doosan DS-9530 (ultra high Td film) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-9530 Thermal
    120213 2.100e-09         0    1.0000       0.0       0.0
 9.500e+08 5.000e-01
$
$$ --- Doosan DSR-1000 (TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSR-1000 Thermal
    120214 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DSF-900LC (low Dk film TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSF-900LC Thermal
    120215 1.750e-09         0    1.0000       0.0       0.0
 9.500e+08 5.000e-01
$
$$ --- Doosan DSF-900SQ (TC=0.5) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSF-900SQ Thermal
    120216 1.700e-09         0    1.0000       0.0       0.0
 9.500e+08 5.000e-01
$
$$ --- Doosan DST-9000 (thermal conductive TC=1.3 W/m/K) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DST-9000 Thermal
    120217 1.900e-09         0    1.0000       0.0       0.0
 8.000e+08 1.300e+00
$
$$ --- Doosan DST-9000HT (thermal conductive TC=3.0 W/m/K) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DST-9000HT Thermal
    120218 2.000e-09         0    1.0000       0.0       0.0
 8.000e+08 3.000e+00
$
$$ --- Doosan DSflex-600 (flex PI TC=0.2) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600 Thermal
    120219 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600P ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600P Thermal
    120220 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600U ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600U Thermal
    120221 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600D ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600D Thermal
    120222 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600UY ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600UY Thermal
    120223 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600UF ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600UF Thermal
    120224 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-600UK ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-600UK Thermal
    120225 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DSflex-900 ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DSflex-900 Thermal
    120226 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 2.000e-01
$
$$ --- Doosan DS-7409DV(N) (high-speed low-loss, TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409DV(N) Thermal
    120227 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DS-7409DX(C) (TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409DX(C) Thermal
    120228 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DS-7409DJG (TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409DJG Thermal
    120229 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DS-7409DXG (TC=0.6) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409DXG Thermal
    120230 1.710e-09         0    1.0000       0.0       0.0
 8.800e+08 6.000e-01
$
$$ --- Doosan DS-7409S(N) (TC=0.4) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409S(N) Thermal
    120231 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 4.000e-01
$
$$ --- Doosan DS-7409HG(FQ) (ultra low CTE ceramic, TC=0.7) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409HG(FQ) Thermal
    120232 2.300e-09         0    1.0000       0.0       0.0
 8.000e+08 7.000e-01
$
$$ --- Doosan DS-7409HG(ZL) (TC=0.9) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409HG(ZL) Thermal
    120233 2.300e-09         0    1.0000       0.0       0.0
 8.000e+08 9.000e-01
$
$$ --- Doosan DS-7409HG(X) (TC=0.8) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409HG(X) Thermal
    120234 2.300e-09         0    1.0000       0.0       0.0
 8.000e+08 8.000e-01
$
$$ --- Doosan DS-7409HG(LE) (TC=0.7) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409HG(LE) Thermal
    120235 2.200e-09         0    1.0000       0.0       0.0
 8.000e+08 7.000e-01
$
$$ --- Doosan DS-7409HG(I) (TC=0.9) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan DS-7409HG(I) Thermal
    120236 2.300e-09         0    1.0000       0.0       0.0
 8.000e+08 9.000e-01
$
$$ --- Doosan RAPIDON-10W (high TC = 1.0 W/m/K) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Doosan RAPIDON-10W Thermal
    120237 2.000e-09         0    1.0000       0.0       0.0
 8.500e+08 1.000e+00
$
$ ========================================================================
$ 3. Elite Material (EMC) - Direct TDS extraction (100301~100305)
$ ========================================================================
$
$$ --- Elite EM-370Z (TC=0.58 W/m/K per TDS) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Elite EM-370Z Thermal
    120301 1.880e-09         0    1.0000       0.0       0.0
 9.000e+08 5.800e-01
$
$$ --- Elite EM-526 (TC=0.6 W/m/K, low-loss low-CTE) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Elite EM-526 Thermal
    120302 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 6.000e-01
$
$$ --- Elite EM-528 (TC=0.6 W/m/K) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Elite EM-528 Thermal
    120303 1.900e-09         0    1.0000       0.0       0.0
 9.000e+08 6.000e-01
$
$$ --- Elite EM-892K (TC=0.46 W/m/K, extreme low-loss) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Elite EM-892K Thermal
    120304 1.880e-09         0    1.0000       0.0       0.0
 9.200e+08 4.600e-01
$
$$ --- Elite EM-S570 (TC=0.59, ultra low CTE) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Elite EM-S570 Thermal
    120305 2.000e-09         0    1.0000       0.0       0.0
 8.800e+08 5.900e-01
$
$ ========================================================================
$ END OF PCB THERMAL LIBRARY
$ ========================================================================
*END
