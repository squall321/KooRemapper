$ ========================================================================
$ GLASS THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),
$ !!  NOT an actual Part ID. Applied to both mechanical variants.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   TMID    Name                        CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)
$   ---------------------------------------------------------------------------
$   131001  SodaLime_Standard                 9.00      1.05      840.0
$   131002  Aluminosilicate_Dragontrail       8.50      1.00      830.0
$   131003  GorillaGlass_3                    7.80      0.96      880.0
$   131004  GorillaGlass_5                    7.70      0.95      880.0
$   131005  GorillaGlass_6                    7.60      0.95      880.0
$   131006  GorillaGlass_Victus               7.50      0.95      880.0
$   131011  Sapphire_Cplane                   5.30     35.10      750.0
$   131012  Sapphire_Aplane                   5.80     35.10      750.0
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Cover THERMAL
$ ========================================================================
$
$$ --- SodaLime_Standard Thermal (TMID 131001) ---
$$ TC=1.05 W/m/K, Cp=840.0 J/kg/K, CTE=9.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
SodaLime_Standard Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131001 2.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.400e+08 1.050e+00
$
$$ CTE=9.0 ppm/K, applied to both MIDs of SodaLime_Standard
$$ [DB] PID slot holds MID=101001 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101001         0 9.000e-06
$$ [DB] PID slot holds MID=111001 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111001         0 9.000e-06
$
$$ --- Aluminosilicate_Dragontrail Thermal (TMID 131002) ---
$$ TC=1.0 W/m/K, Cp=830.0 J/kg/K, CTE=8.5 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Aluminosilicate_Dragontrail Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131002 2.480e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.300e+08 1.000e+00
$
$$ CTE=8.5 ppm/K, applied to both MIDs of Aluminosilicate_Dragontrail
$$ [DB] PID slot holds MID=101002 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101002         0 8.500e-06
$$ [DB] PID slot holds MID=111002 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111002         0 8.500e-06
$
$$ --- GorillaGlass_3 Thermal (TMID 131003) ---
$$ TC=0.96 W/m/K, Cp=880.0 J/kg/K, CTE=7.8 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
GorillaGlass_3 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131003 2.450e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 9.600e-01
$
$$ CTE=7.8 ppm/K, applied to both MIDs of GorillaGlass_3
$$ [DB] PID slot holds MID=101003 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101003         0 7.800e-06
$$ [DB] PID slot holds MID=111003 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111003         0 7.800e-06
$
$$ --- GorillaGlass_5 Thermal (TMID 131004) ---
$$ TC=0.95 W/m/K, Cp=880.0 J/kg/K, CTE=7.7 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
GorillaGlass_5 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131004 2.430e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 9.500e-01
$
$$ CTE=7.7 ppm/K, applied to both MIDs of GorillaGlass_5
$$ [DB] PID slot holds MID=101004 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101004         0 7.700e-06
$$ [DB] PID slot holds MID=111004 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111004         0 7.700e-06
$
$$ --- GorillaGlass_6 Thermal (TMID 131005) ---
$$ TC=0.95 W/m/K, Cp=880.0 J/kg/K, CTE=7.6 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
GorillaGlass_6 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131005 2.400e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 9.500e-01
$
$$ CTE=7.6 ppm/K, applied to both MIDs of GorillaGlass_6
$$ [DB] PID slot holds MID=101005 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101005         0 7.600e-06
$$ [DB] PID slot holds MID=111005 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111005         0 7.600e-06
$
$$ --- GorillaGlass_Victus Thermal (TMID 131006) ---
$$ TC=0.95 W/m/K, Cp=880.0 J/kg/K, CTE=7.5 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
GorillaGlass_Victus Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131006 2.440e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 9.500e-01
$
$$ CTE=7.5 ppm/K, applied to both MIDs of GorillaGlass_Victus
$$ [DB] PID slot holds MID=101006 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101006         0 7.500e-06
$$ [DB] PID slot holds MID=111006 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111006         0 7.500e-06
$
$ ========================================================================
$ Sapphire THERMAL
$ ========================================================================
$
$$ --- Sapphire_Cplane Thermal (TMID 131011) ---
$$ TC=35.1 W/m/K, Cp=750.0 J/kg/K, CTE=5.3 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Sapphire_Cplane Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131011 3.970e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.500e+08 3.510e+01
$
$$ CTE=5.3 ppm/K, applied to both MIDs of Sapphire_Cplane
$$ [DB] PID slot holds MID=101011 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101011         0 5.300e-06
$$ [DB] PID slot holds MID=111011 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111011         0 5.300e-06
$
$$ --- Sapphire_Aplane Thermal (TMID 131012) ---
$$ TC=35.1 W/m/K, Cp=750.0 J/kg/K, CTE=5.8 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Sapphire_Aplane Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131012 3.970e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 7.500e+08 3.510e+01
$
$$ CTE=5.8 ppm/K, applied to both MIDs of Sapphire_Aplane
$$ [DB] PID slot holds MID=101012 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101012         0 5.800e-06
$$ [DB] PID slot holds MID=111012 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111012         0 5.800e-06
$
*END
