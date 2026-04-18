$ ========================================================================
$ CERAMIC THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$
$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs
$
$ SUMMARY TABLE
$
$   TMID    Name                    CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)
$   -------------------------------------------------------------------------
$   131021  Al2O3_96pct                 7.10     24.00      880.0
$   131022  Al2O3_99p5pct               8.00     32.00      880.0
$   131023  AlN_HighK                   4.50    170.00      740.0
$   131024  ZrO2_YTZP                  10.30      2.00      420.0
$   131025  Si3N4                       3.20     25.00      700.0
$   131026  SiC                         4.00    120.00      750.0
$   131031  PZT_5A_soft                 2.00      1.80      420.0
$   131032  PZT_4_hard                  2.00      1.80      420.0
$   131033  AlN_piezo_thinfilm          4.50    140.00      740.0
$   131041  LCP_Vectra_A950             5.00      0.20     1090.0
$   131042  LCP_Vectra_E130i            3.00      0.25     1050.0
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Structural THERMAL
$ ========================================================================
$
$$ --- Al2O3_96pct Thermal (TMID 131021) ---
$$ TC=24.0 W/m/K, Cp=880.0 J/kg/K, CTE=7.1 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al2O3_96pct Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131021 3.720e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 2.400e+01
$
$$ CTE=7.1 ppm/K applied to both MIDs of Al2O3_96pct
$$ [DB] PID slot holds MID=101021 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101021         0 7.100e-06
$$ [DB] PID slot holds MID=111021 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111021         0 7.100e-06
$
$$ --- Al2O3_99p5pct Thermal (TMID 131022) ---
$$ TC=32.0 W/m/K, Cp=880.0 J/kg/K, CTE=8.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al2O3_99p5pct Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131022 3.890e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 3.200e+01
$
$$ CTE=8.0 ppm/K applied to both MIDs of Al2O3_99p5pct
$$ [DB] PID slot holds MID=101022 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101022         0 8.000e-06
$$ [DB] PID slot holds MID=111022 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111022         0 8.000e-06
$
$$ --- AlN_HighK Thermal (TMID 131023) ---
$$ TC=170.0 W/m/K, Cp=740.0 J/kg/K, CTE=4.5 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
AlN_HighK Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131023 3.260e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.400e+08 1.700e+02
$
$$ CTE=4.5 ppm/K applied to both MIDs of AlN_HighK
$$ [DB] PID slot holds MID=101023 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101023         0 4.500e-06
$$ [DB] PID slot holds MID=111023 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111023         0 4.500e-06
$
$$ --- ZrO2_YTZP Thermal (TMID 131024) ---
$$ TC=2.0 W/m/K, Cp=420.0 J/kg/K, CTE=10.3 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
ZrO2_YTZP Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131024 6.050e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.200e+08 2.000e+00
$
$$ CTE=10.3 ppm/K applied to both MIDs of ZrO2_YTZP
$$ [DB] PID slot holds MID=101024 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101024         0 1.030e-05
$$ [DB] PID slot holds MID=111024 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111024         0 1.030e-05
$
$$ --- Si3N4 Thermal (TMID 131025) ---
$$ TC=25.0 W/m/K, Cp=700.0 J/kg/K, CTE=3.2 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Si3N4 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131025 3.200e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.000e+08 2.500e+01
$
$$ CTE=3.2 ppm/K applied to both MIDs of Si3N4
$$ [DB] PID slot holds MID=101025 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101025         0 3.200e-06
$$ [DB] PID slot holds MID=111025 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111025         0 3.200e-06
$
$$ --- SiC Thermal (TMID 131026) ---
$$ TC=120.0 W/m/K, Cp=750.0 J/kg/K, CTE=4.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
SiC Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131026 3.100e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.500e+08 1.200e+02
$
$$ CTE=4.0 ppm/K applied to both MIDs of SiC
$$ [DB] PID slot holds MID=101026 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101026         0 4.000e-06
$$ [DB] PID slot holds MID=111026 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111026         0 4.000e-06
$
$ ========================================================================
$ Piezo THERMAL
$ ========================================================================
$
$$ --- PZT_5A_soft Thermal (TMID 131031) ---
$$ TC=1.8 W/m/K, Cp=420.0 J/kg/K, CTE=2.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PZT_5A_soft Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131031 7.750e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.200e+08 1.800e+00
$
$$ CTE=2.0 ppm/K applied to both MIDs of PZT_5A_soft
$$ [DB] PID slot holds MID=101031 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101031         0 2.000e-06
$$ [DB] PID slot holds MID=111031 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111031         0 2.000e-06
$
$$ --- PZT_4_hard Thermal (TMID 131032) ---
$$ TC=1.8 W/m/K, Cp=420.0 J/kg/K, CTE=2.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PZT_4_hard Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131032 7.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.200e+08 1.800e+00
$
$$ CTE=2.0 ppm/K applied to both MIDs of PZT_4_hard
$$ [DB] PID slot holds MID=101032 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101032         0 2.000e-06
$$ [DB] PID slot holds MID=111032 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111032         0 2.000e-06
$
$$ --- AlN_piezo_thinfilm Thermal (TMID 131033) ---
$$ TC=140.0 W/m/K, Cp=740.0 J/kg/K, CTE=4.5 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
AlN_piezo_thinfilm Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131033 3.260e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.400e+08 1.400e+02
$
$$ CTE=4.5 ppm/K applied to both MIDs of AlN_piezo_thinfilm
$$ [DB] PID slot holds MID=101033 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101033         0 4.500e-06
$$ [DB] PID slot holds MID=111033 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111033         0 4.500e-06
$
$ ========================================================================
$ LCP THERMAL
$ ========================================================================
$
$$ --- LCP_Vectra_A950 Thermal (TMID 131041) ---
$$ TC=0.2 W/m/K, Cp=1090.0 J/kg/K, CTE=5.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
LCP_Vectra_A950 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131041 1.400e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.090e+09 2.000e-01
$
$$ CTE=5.0 ppm/K applied to both MIDs of LCP_Vectra_A950
$$ [DB] PID slot holds MID=101041 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101041         0 5.000e-06
$$ [DB] PID slot holds MID=111041 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111041         0 5.000e-06
$
$$ --- LCP_Vectra_E130i Thermal (TMID 131042) ---
$$ TC=0.25 W/m/K, Cp=1050.0 J/kg/K, CTE=3.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
LCP_Vectra_E130i Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131042 1.620e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.050e+09 2.500e-01
$
$$ CTE=3.0 ppm/K applied to both MIDs of LCP_Vectra_E130i
$$ [DB] PID slot holds MID=101042 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101042         0 3.000e-06
$$ [DB] PID slot holds MID=111042 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111042         0 3.000e-06
$
*END
