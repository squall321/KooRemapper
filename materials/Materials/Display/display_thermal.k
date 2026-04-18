$ ========================================================================
$ DISPLAY THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$
$ !! DB CONVENTION: PID field holds MID, external tool replaces with PART IDs
$
*KEYWORD
$
$ ========================================================================
$ Display THERMAL
$ ========================================================================
$
$$ --- Display_RigidOLED Thermal (TMID 131051) ---
$$ TC=0.8 W/m/K, Cp=900.0 J/kg/K, CTE=15.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_RigidOLED Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131051 2.100e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.000e+08 8.000e-01
$
$$ CTE=15.0 ppm/K, applied to all 3 MIDs of Display_RigidOLED
$$ [DB] PID slot holds MID=101051 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101051         0 1.500e-05
$$ [DB] PID slot holds MID=111051 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111051         0 1.500e-05
$$ [DB] PID slot holds MID=121051 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121051         0 1.500e-05
$
$$ --- Display_FlexibleOLED Thermal (TMID 131052) ---
$$ TC=0.3 W/m/K, Cp=1200.0 J/kg/K, CTE=30.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_FlexibleOLED Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131052 1.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.200e+09 3.000e-01
$
$$ CTE=30.0 ppm/K, applied to all 3 MIDs of Display_FlexibleOLED
$$ [DB] PID slot holds MID=101052 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101052         0 3.000e-05
$$ [DB] PID slot holds MID=111052 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111052         0 3.000e-05
$$ [DB] PID slot holds MID=121052 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121052         0 3.000e-05
$
$$ --- Display_FoldableOLED_UTG Thermal (TMID 131053) ---
$$ TC=0.5 W/m/K, Cp=1100.0 J/kg/K, CTE=25.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_FoldableOLED_UTG Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131053 1.800e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.100e+09 5.000e-01
$
$$ CTE=25.0 ppm/K, applied to all 3 MIDs of Display_FoldableOLED_UTG
$$ [DB] PID slot holds MID=101053 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101053         0 2.500e-05
$$ [DB] PID slot holds MID=111053 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111053         0 2.500e-05
$$ [DB] PID slot holds MID=121053 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121053         0 2.500e-05
$
$$ --- Display_FoldableOLED_CPI Thermal (TMID 131054) ---
$$ TC=0.25 W/m/K, Cp=1300.0 J/kg/K, CTE=45.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_FoldableOLED_CPI Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131054 1.400e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.300e+09 2.500e-01
$
$$ CTE=45.0 ppm/K, applied to all 3 MIDs of Display_FoldableOLED_CPI
$$ [DB] PID slot holds MID=101054 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101054         0 4.500e-05
$$ [DB] PID slot holds MID=111054 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111054         0 4.500e-05
$$ [DB] PID slot holds MID=121054 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121054         0 4.500e-05
$
$$ --- Display_LCD_IPS Thermal (TMID 131055) ---
$$ TC=0.5 W/m/K, Cp=1000.0 J/kg/K, CTE=25.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_LCD_IPS Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131055 1.800e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.000e+09 5.000e-01
$
$$ CTE=25.0 ppm/K, applied to all 3 MIDs of Display_LCD_IPS
$$ [DB] PID slot holds MID=101055 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101055         0 2.500e-05
$$ [DB] PID slot holds MID=111055 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111055         0 2.500e-05
$$ [DB] PID slot holds MID=121055 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121055         0 2.500e-05
$
$$ --- Display_MicroLED Thermal (TMID 131056) ---
$$ TC=5.0 W/m/K, Cp=800.0 J/kg/K, CTE=10.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Display_MicroLED Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    131056 2.300e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.000e+08 5.000e+00
$
$$ CTE=10.0 ppm/K, applied to all 3 MIDs of Display_MicroLED
$$ [DB] PID slot holds MID=101056 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    101056         0 1.000e-05
$$ [DB] PID slot holds MID=111056 (Orthotropic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    111056         0 1.000e-05
$$ [DB] PID slot holds MID=121056 (Elastic+Erode, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    121056         0 1.000e-05
$
*END
