$ ========================================================================
$ MAGNET THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$
$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs
$
*KEYWORD
$
$ ========================================================================
$ NdFeB THERMAL
$ ========================================================================
$
$$ --- NdFeB_N35 Thermal (TMID 131061) ---
$$ TC=9.0 W/m/K, Cp=460.0 J/kg/K, CTE=5.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
NdFeB_N35 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131061 7.400e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 9.000e+00
$
$$ CTE=5.0 ppm/K, applied to both MIDs of NdFeB_N35
$$ [DB] PID slot holds MID=101061 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101061         0 5.000e-06
$$ [DB] PID slot holds MID=111061 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111061         0 5.000e-06
$
$$ --- NdFeB_N42 Thermal (TMID 131062) ---
$$ TC=9.0 W/m/K, Cp=460.0 J/kg/K, CTE=5.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
NdFeB_N42 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131062 7.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 9.000e+00
$
$$ CTE=5.0 ppm/K, applied to both MIDs of NdFeB_N42
$$ [DB] PID slot holds MID=101062 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101062         0 5.000e-06
$$ [DB] PID slot holds MID=111062 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111062         0 5.000e-06
$
$$ --- NdFeB_N52 Thermal (TMID 131063) ---
$$ TC=9.0 W/m/K, Cp=460.0 J/kg/K, CTE=5.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
NdFeB_N52 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131063 7.600e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 9.000e+00
$
$$ CTE=5.0 ppm/K, applied to both MIDs of NdFeB_N52
$$ [DB] PID slot holds MID=101063 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101063         0 5.000e-06
$$ [DB] PID slot holds MID=111063 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111063         0 5.000e-06
$
$ ========================================================================
$ SmCo THERMAL
$ ========================================================================
$
$$ --- SmCo_2_17 Thermal (TMID 131064) ---
$$ TC=12.0 W/m/K, Cp=360.0 J/kg/K, CTE=9.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
SmCo_2_17 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131064 8.400e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 3.600e+08 1.200e+01
$
$$ CTE=9.0 ppm/K, applied to both MIDs of SmCo_2_17
$$ [DB] PID slot holds MID=101064 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101064         0 9.000e-06
$$ [DB] PID slot holds MID=111064 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111064         0 9.000e-06
$
$ ========================================================================
$ Ferrite/Bonded THERMAL
$ ========================================================================
$
$$ --- SrFerrite_Y30 Thermal (TMID 131065) ---
$$ TC=4.0 W/m/K, Cp=790.0 J/kg/K, CTE=13.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
SrFerrite_Y30 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131065 4.900e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.900e+08 4.000e+00
$
$$ CTE=13.0 ppm/K, applied to both MIDs of SrFerrite_Y30
$$ [DB] PID slot holds MID=101065 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101065         0 1.300e-05
$$ [DB] PID slot holds MID=111065 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111065         0 1.300e-05
$
$$ --- NdFeB_Bonded Thermal (TMID 131066) ---
$$ TC=1.5 W/m/K, Cp=1000.0 J/kg/K, CTE=20.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
NdFeB_Bonded Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131066 5.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.000e+09 1.500e+00
$
$$ CTE=20.0 ppm/K, applied to both MIDs of NdFeB_Bonded
$$ [DB] PID slot holds MID=101066 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101066         0 2.000e-05
$$ [DB] PID slot holds MID=111066 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111066         0 2.000e-05
$
*END
