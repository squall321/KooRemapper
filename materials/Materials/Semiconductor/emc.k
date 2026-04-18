$ ========================================================================
$ EPOXY MOLDING COMPOUND (EMC) MATERIAL LIBRARY
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ MID: 100951~100958 (Linear MAT_001), 110951~110958 (Viscoelastic MAT_006)
$      120951~120958 (Thermal TMID)
$
$ Usage: IC package body in BGA/QFN/CSP/LGA drop impact analysis
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID,
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ Data sources:
$   [1] Sumitomo Bakelite SUMIKON EME series TDS
$   [2] Hitachi Chemical CEL-9200, GE-100 TDS (PMC 10179932)
$   [3] Shin-Etsu KMC-184 series TDS
$   [4] Namics MUF (Molded Underfill) series
$   [5] Resonac (formerly Hitachi) GE-series product guide
$
$ Model selection:
$   MAT_001 (Linear) — primary, sufficient for drop analysis
$   MAT_006 (VE)     — optional, slight rate stiffening
$
$ ========================================================================
$ SUMMARY TABLE
$
$  lin_mid  ve_mid  tmid   Name                          E(GPa) rho   Tg(C) CTE1 CTE2
$  ---------------------------------------------------------------------------------
$  100951  110951  120951  EMC High-Tg Green             24.0   1.90  175   9.0  40
$  100952  110952  120952  EMC Mid-Tg Standard           22.0   1.85  155   10   45
$  100953  110953  120953  EMC Low-Tg Fast Cure          19.0   1.80  125   12   50
$  100954  110954  120954  EMC Low-CTE High-Filled       28.0   2.05  165   7.0  30
$  100955  110955  120955  EMC Green Ultra-HighTg        26.0   1.92  185   8.5  38
$  100956  110956  120956  EMC Molded Underfill          18.0   1.85  140   15   55
$  100957  110957  120957  EMC Wafer-Level Black         23.0   1.95  160   9.5  42
$  100958  110958  120958  EMC Thermal Conductive        25.0   2.10  170   8.5  36
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. EMC High-Tg Green (Sumitomo EME-G700)
$ ========================================================================
$
$$ --- EMC High-Tg Green Linear (MID 100951) ---
$$ Sumitomo EME-G700, Tg=175C, halogen-free
$$ Filler: silica 85 wt%, E=24 GPa
$$ Source: Sumitomo Bakelite SUMIKON EME series TDS
*MAT_ELASTIC_TITLE
EMC High-Tg Green (EME-G700)
$      MID        RO         E        PR
    100951 1.900e-09   24000.0    0.3000       0.0       0.0       0.0
$
$$ --- EMC High-Tg Green Viscoelastic (MID 110951) ---
$$ Slight rate stiffening for drop impact (~1 kHz)
$$ G0/GI ratio 1.03x, tan(d) ~ 0.015
*MAT_VISCOELASTIC_TITLE
EMC High-Tg Green VE
$      MID        RO      BULK        G0        GI      BETA
    110951 1.900e-09   20000.0    9508.0    8932.0    1000.0
$
$$ --- EMC High-Tg Green Thermal (TMID 120951) ---
$$ CTE1=9 ppm/K (below Tg), CTE2=40 ppm/K (above Tg)
$$ k=0.80 W/m/K, Cp=870 J/kg/K
$$ We use CTE1 for RT drop analysis
*MAT_THERMAL_ISOTROPIC_TITLE
EMC High-Tg Green Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120951 1.900e-09         0    1.0000       0.0       0.0
$       HC         TC
 8.700e+08 8.000e-01
$
$$ [DB] PID slot holds MID (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100951         0 9.000e-06
*MAT_ADD_THERMAL_EXPANSION
    110951         0 9.000e-06
$
$ ========================================================================
$ 2. EMC Mid-Tg Standard (Hitachi CEL-9200)
$ ========================================================================
$
$$ --- EMC Mid-Tg Standard Linear (MID 100952) ---
$$ Hitachi CEL-9200, Tg=155C, standard packaging
$$ E=22 GPa, filler ~82 wt%
*MAT_ELASTIC_TITLE
EMC Mid-Tg Standard (CEL-9200)
    100952 1.850e-09   22000.0    0.3000       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC Mid-Tg Standard VE
    110952 1.850e-09   18333.0    8713.0    8185.0    1000.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC Mid-Tg Standard Thermal
    120952 1.850e-09         0    1.0000       0.0       0.0
 8.700e+08 7.500e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100952         0 1.000e-05
*MAT_ADD_THERMAL_EXPANSION
    110952         0 1.000e-05
$
$ ========================================================================
$ 3. EMC Low-Tg Fast Cure (Shin-Etsu KMC-184)
$ ========================================================================
$
$$ --- EMC Low-Tg Fast Cure Linear (MID 100953) ---
$$ Shin-Etsu KMC-184 variant, Tg=125C, fast cure
$$ E=19 GPa, softer for thermal mismatch
*MAT_ELASTIC_TITLE
EMC Low-Tg Fast Cure
    100953 1.800e-09   19000.0    0.3100       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC Low-Tg Fast Cure VE
    110953 1.800e-09   16667.0    7529.0    7073.0     800.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC Low-Tg Thermal
    120953 1.800e-09         0    1.0000       0.0       0.0
 8.500e+08 7.000e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100953         0 1.200e-05
*MAT_ADD_THERMAL_EXPANSION
    110953         0 1.200e-05
$
$ ========================================================================
$ 4. EMC Low-CTE High-Filled (Sumitomo EME-G780)
$ ========================================================================
$
$$ --- EMC Low-CTE Linear (MID 100954) ---
$$ Sumitomo EME-G780, ultra-high filler 90 wt%, Tg=165C
$$ E=28 GPa (highest among EMCs)
$$ Ultra-low CTE1=7 ppm/K for high-reliability
*MAT_ELASTIC_TITLE
EMC Low-CTE High-Filled (EME-G780)
    100954 2.050e-09   28000.0    0.2800       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC Low-CTE VE
    110954 2.050e-09   21212.0   11316.0   10650.0    1200.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC Low-CTE Thermal
    120954 2.050e-09         0    1.0000       0.0       0.0
 8.000e+08 9.000e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100954         0 7.000e-06
*MAT_ADD_THERMAL_EXPANSION
    110954         0 7.000e-06
$
$ ========================================================================
$ 5. EMC Green Ultra-HighTg (Resonac GE-series)
$ ========================================================================
$
$$ --- EMC Green Ultra-HighTg Linear (MID 100955) ---
$$ Resonac GE-series, Tg=185C, halogen-free, automotive grade
*MAT_ELASTIC_TITLE
EMC Green Ultra-HighTg (GE-series)
    100955 1.920e-09   26000.0    0.2900       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC Green Ultra-HighTg VE
    110955 1.920e-09   20635.0   10308.0    9701.0    1100.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC Green Ultra-HighTg Thermal
    120955 1.920e-09         0    1.0000       0.0       0.0
 8.700e+08 8.500e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100955         0 8.500e-06
*MAT_ADD_THERMAL_EXPANSION
    110955         0 8.500e-06
$
$ ========================================================================
$ 6. EMC Molded Underfill (Namics MUF)
$ ========================================================================
$
$$ --- EMC Molded Underfill Linear (MID 100956) ---
$$ Namics MUF, Tg=140C, for flip-chip MUF process
$$ Lower filler → lower E, higher CTE
$$ Used: flip-chip BGA with molded underfill
*MAT_ELASTIC_TITLE
EMC Molded Underfill (Namics MUF)
    100956 1.850e-09   18000.0    0.3200       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC MUF VE
    110956 1.850e-09   16667.0    7050.0    6627.0     900.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC MUF Thermal
    120956 1.850e-09         0    1.0000       0.0       0.0
 9.000e+08 6.000e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100956         0 1.500e-05
*MAT_ADD_THERMAL_EXPANSION
    110956         0 1.500e-05
$
$ ========================================================================
$ 7. EMC Wafer-Level Black (Sumitomo CRP-9800)
$ ========================================================================
$
$$ --- EMC WLP Black Linear (MID 100957) ---
$$ Sumitomo CRP-9800 for wafer-level package (eWLB/fan-out)
$$ Tg=160C, E=23 GPa, black pigment for laser marking
*MAT_ELASTIC_TITLE
EMC WLP Black (CRP-9800)
    100957 1.950e-09   23000.0    0.3000       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC WLP Black VE
    110957 1.950e-09   19167.0    9110.0    8558.0    1000.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC WLP Black Thermal
    120957 1.950e-09         0    1.0000       0.0       0.0
 8.700e+08 7.800e-01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100957         0 9.500e-06
*MAT_ADD_THERMAL_EXPANSION
    110957         0 9.500e-06
$
$ ========================================================================
$ 8. EMC Thermal Conductive (Hitachi GE-100 High-k)
$ ========================================================================
$
$$ --- EMC Thermal Conductive Linear (MID 100958) ---
$$ Hitachi GE-100 high-k series, Tg=170C, filler boosted
$$ k=2.0 W/m/K (vs standard 0.8) for heat dissipation
$$ Used: power device packaging
*MAT_ELASTIC_TITLE
EMC Thermal Conductive (GE-100)
    100958 2.100e-09   25000.0    0.2900       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
EMC Thermal Conductive VE
    110958 2.100e-09   19841.0    9912.0    9329.0    1100.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMC Thermal Conductive Thermal
    120958 2.100e-09         0    1.0000       0.0       0.0
 8.200e+08 2.000e+00
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100958         0 8.500e-06
*MAT_ADD_THERMAL_EXPANSION
    110958         0 8.500e-06
$
$ ========================================================================
$ 9. PKG Homogenized (Si die + EMC volume-averaged)
$ ========================================================================
$
$$ --- PKG Homogenized Linear (MID 100959) ---
$$ Volume-averaged properties for IC package body modeled as single part
$$ Si die: E=130GPa, PR=0.28, rho=2.33 g/cm³, CTE=2.6 ppm/K
$$ EMC:    E=24GPa,  PR=0.30, rho=1.90 g/cm³, CTE=9.0 ppm/K
$$ Typical die/package volume ratio ~30-40%, using 35%:
$$   E_eff  = 0.35*130 + 0.65*24  = 61.1 GPa
$$   PR_eff = 0.35*0.28 + 0.65*0.30 = 0.293
$$   rho    = 0.35*2.33 + 0.65*1.90 = 2.05 g/cm³
$$   CTE    = 0.35*2.6  + 0.65*9.0  = 6.8 ppm/K
$$ Used: PKG parts where die+EMC are a single solid element group
*MAT_ELASTIC_TITLE
PKG Homogenized (Si+EMC)
    100959 2.050e-09   61100.0    0.2930       0.0       0.0       0.0
$
*MAT_VISCOELASTIC_TITLE
PKG Homogenized VE
    110959 2.050e-09   48492.0   24200.0   22760.0    1100.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
PKG Homogenized Thermal
    120959 2.050e-09         0    1.0000       0.0       0.0
 7.600e+08 1.500e+00
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100959         0 6.800e-06
*MAT_ADD_THERMAL_EXPANSION
    110959         0 6.800e-06
$
$ ========================================================================
$ END OF EMC MATERIAL LIBRARY
$ ========================================================================
*END
