$ ========================================================================
$ PLASTIC THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),
$ !!  NOT an actual Part ID. Applied to all 5 MIDs per material.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   TMID    Name                  CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)
$   -----------------------------------------------------------------
$   150961  PC_Makrolon                 65.0     0.210    1200.0
$   150962  ABS_Cycolac                 90.0     0.170    1300.0
$   150963  PC_ABS_Cycoloy              78.0     0.190    1250.0
$   150964  PA6_Ultramid_B             100.0     0.270    1700.0
$   150965  PA66_Zytel                  80.0     0.260    1670.0
$   150966  PBT_Crastin                 75.0     0.300    1450.0
$   150967  POM_Delrin                 110.0     0.300    1470.0
$   150968  PP_Homo                    150.0     0.220    1920.0
$   150971  PA66_GF30                   25.0     0.300    1400.0
$   150972  PA66_GF50                   18.0     0.400    1350.0
$   150973  PBT_GF30                    30.0     0.350    1350.0
$   150974  PPS_GF40                    20.0     0.350    1100.0
$   150975  PPS_Ryton                   49.0     0.290    1000.0
$   150976  PEEK_Victrex                47.0     0.250    1340.0
$   150977  PEI_Ultem                   56.0     0.220    1200.0
$   150981  PMMA_Plexiglas              75.0     0.190    1470.0
$   150982  COP_Zeonex                  70.0     0.150    1800.0
$   150983  COC_TOPAS                   60.0     0.150    1750.0
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Standard THERMAL
$ ========================================================================
$
$$ --- PC_Makrolon Thermal (TMID 150961) ---
$$ TC=0.21 W/m/K, Cp=1200.0 J/kg/K, CTE=65.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PC_Makrolon Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150961 1.200e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.200e+09 2.100e-01
$
$$ CTE=65.0 ppm/K, applied to all 5 MIDs of PC_Makrolon
$$ [DB] PID slot holds MID=100961 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100961         0 6.500e-05
$$ [DB] PID slot holds MID=110961 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110961         0 6.500e-05
$$ [DB] PID slot holds MID=120961 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120961         0 6.500e-05
$$ [DB] PID slot holds MID=130961 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130961         0 6.500e-05
$$ [DB] PID slot holds MID=140961 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140961         0 6.500e-05
$
$$ --- ABS_Cycolac Thermal (TMID 150962) ---
$$ TC=0.17 W/m/K, Cp=1300.0 J/kg/K, CTE=90.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
ABS_Cycolac Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150962 1.050e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.300e+09 1.700e-01
$
$$ CTE=90.0 ppm/K, applied to all 5 MIDs of ABS_Cycolac
$$ [DB] PID slot holds MID=100962 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100962         0 9.000e-05
$$ [DB] PID slot holds MID=110962 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110962         0 9.000e-05
$$ [DB] PID slot holds MID=120962 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120962         0 9.000e-05
$$ [DB] PID slot holds MID=130962 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130962         0 9.000e-05
$$ [DB] PID slot holds MID=140962 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140962         0 9.000e-05
$
$$ --- PC_ABS_Cycoloy Thermal (TMID 150963) ---
$$ TC=0.19 W/m/K, Cp=1250.0 J/kg/K, CTE=78.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PC_ABS_Cycoloy Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150963 1.140e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.250e+09 1.900e-01
$
$$ CTE=78.0 ppm/K, applied to all 5 MIDs of PC_ABS_Cycoloy
$$ [DB] PID slot holds MID=100963 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100963         0 7.800e-05
$$ [DB] PID slot holds MID=110963 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110963         0 7.800e-05
$$ [DB] PID slot holds MID=120963 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120963         0 7.800e-05
$$ [DB] PID slot holds MID=130963 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130963         0 7.800e-05
$$ [DB] PID slot holds MID=140963 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140963         0 7.800e-05
$
$$ --- PA6_Ultramid_B Thermal (TMID 150964) ---
$$ TC=0.27 W/m/K, Cp=1700.0 J/kg/K, CTE=100.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PA6_Ultramid_B Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150964 1.140e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.700e+09 2.700e-01
$
$$ CTE=100.0 ppm/K, applied to all 5 MIDs of PA6_Ultramid_B
$$ [DB] PID slot holds MID=100964 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100964         0 1.000e-04
$$ [DB] PID slot holds MID=110964 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110964         0 1.000e-04
$$ [DB] PID slot holds MID=120964 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120964         0 1.000e-04
$$ [DB] PID slot holds MID=130964 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130964         0 1.000e-04
$$ [DB] PID slot holds MID=140964 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140964         0 1.000e-04
$
$$ --- PA66_Zytel Thermal (TMID 150965) ---
$$ TC=0.26 W/m/K, Cp=1670.0 J/kg/K, CTE=80.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PA66_Zytel Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150965 1.140e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.670e+09 2.600e-01
$
$$ CTE=80.0 ppm/K, applied to all 5 MIDs of PA66_Zytel
$$ [DB] PID slot holds MID=100965 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100965         0 8.000e-05
$$ [DB] PID slot holds MID=110965 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110965         0 8.000e-05
$$ [DB] PID slot holds MID=120965 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120965         0 8.000e-05
$$ [DB] PID slot holds MID=130965 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130965         0 8.000e-05
$$ [DB] PID slot holds MID=140965 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140965         0 8.000e-05
$
$$ --- PBT_Crastin Thermal (TMID 150966) ---
$$ TC=0.3 W/m/K, Cp=1450.0 J/kg/K, CTE=75.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PBT_Crastin Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150966 1.310e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.450e+09 3.000e-01
$
$$ CTE=75.0 ppm/K, applied to all 5 MIDs of PBT_Crastin
$$ [DB] PID slot holds MID=100966 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100966         0 7.500e-05
$$ [DB] PID slot holds MID=110966 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110966         0 7.500e-05
$$ [DB] PID slot holds MID=120966 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120966         0 7.500e-05
$$ [DB] PID slot holds MID=130966 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130966         0 7.500e-05
$$ [DB] PID slot holds MID=140966 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140966         0 7.500e-05
$
$$ --- POM_Delrin Thermal (TMID 150967) ---
$$ TC=0.3 W/m/K, Cp=1470.0 J/kg/K, CTE=110.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
POM_Delrin Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150967 1.410e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.470e+09 3.000e-01
$
$$ CTE=110.0 ppm/K, applied to all 5 MIDs of POM_Delrin
$$ [DB] PID slot holds MID=100967 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100967         0 1.100e-04
$$ [DB] PID slot holds MID=110967 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110967         0 1.100e-04
$$ [DB] PID slot holds MID=120967 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120967         0 1.100e-04
$$ [DB] PID slot holds MID=130967 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130967         0 1.100e-04
$$ [DB] PID slot holds MID=140967 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140967         0 1.100e-04
$
$$ --- PP_Homo Thermal (TMID 150968) ---
$$ TC=0.22 W/m/K, Cp=1920.0 J/kg/K, CTE=150.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PP_Homo Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150968 9.000e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.920e+09 2.200e-01
$
$$ CTE=150.0 ppm/K, applied to all 5 MIDs of PP_Homo
$$ [DB] PID slot holds MID=100968 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100968         0 1.500e-04
$$ [DB] PID slot holds MID=110968 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110968         0 1.500e-04
$$ [DB] PID slot holds MID=120968 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120968         0 1.500e-04
$$ [DB] PID slot holds MID=130968 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130968         0 1.500e-04
$$ [DB] PID slot holds MID=140968 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140968         0 1.500e-04
$
$ ========================================================================
$ Reinforced THERMAL
$ ========================================================================
$
$$ --- PA66_GF30 Thermal (TMID 150971) ---
$$ TC=0.3 W/m/K, Cp=1400.0 J/kg/K, CTE=25.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PA66_GF30 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150971 1.360e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.400e+09 3.000e-01
$
$$ CTE=25.0 ppm/K, applied to all 5 MIDs of PA66_GF30
$$ [DB] PID slot holds MID=100971 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100971         0 2.500e-05
$$ [DB] PID slot holds MID=110971 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110971         0 2.500e-05
$$ [DB] PID slot holds MID=120971 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120971         0 2.500e-05
$$ [DB] PID slot holds MID=130971 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130971         0 2.500e-05
$$ [DB] PID slot holds MID=140971 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140971         0 2.500e-05
$
$$ --- PA66_GF50 Thermal (TMID 150972) ---
$$ TC=0.4 W/m/K, Cp=1350.0 J/kg/K, CTE=18.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PA66_GF50 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150972 1.570e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.350e+09 4.000e-01
$
$$ CTE=18.0 ppm/K, applied to all 5 MIDs of PA66_GF50
$$ [DB] PID slot holds MID=100972 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100972         0 1.800e-05
$$ [DB] PID slot holds MID=110972 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110972         0 1.800e-05
$$ [DB] PID slot holds MID=120972 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120972         0 1.800e-05
$$ [DB] PID slot holds MID=130972 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130972         0 1.800e-05
$$ [DB] PID slot holds MID=140972 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140972         0 1.800e-05
$
$$ --- PBT_GF30 Thermal (TMID 150973) ---
$$ TC=0.35 W/m/K, Cp=1350.0 J/kg/K, CTE=30.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PBT_GF30 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150973 1.530e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.350e+09 3.500e-01
$
$$ CTE=30.0 ppm/K, applied to all 5 MIDs of PBT_GF30
$$ [DB] PID slot holds MID=100973 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100973         0 3.000e-05
$$ [DB] PID slot holds MID=110973 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110973         0 3.000e-05
$$ [DB] PID slot holds MID=120973 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120973         0 3.000e-05
$$ [DB] PID slot holds MID=130973 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130973         0 3.000e-05
$$ [DB] PID slot holds MID=140973 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140973         0 3.000e-05
$
$$ --- PPS_GF40 Thermal (TMID 150974) ---
$$ TC=0.35 W/m/K, Cp=1100.0 J/kg/K, CTE=20.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PPS_GF40 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150974 1.660e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.100e+09 3.500e-01
$
$$ CTE=20.0 ppm/K, applied to all 5 MIDs of PPS_GF40
$$ [DB] PID slot holds MID=100974 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100974         0 2.000e-05
$$ [DB] PID slot holds MID=110974 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110974         0 2.000e-05
$$ [DB] PID slot holds MID=120974 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120974         0 2.000e-05
$$ [DB] PID slot holds MID=130974 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130974         0 2.000e-05
$$ [DB] PID slot holds MID=140974 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140974         0 2.000e-05
$
$ ========================================================================
$ HighPerformance THERMAL
$ ========================================================================
$
$$ --- PPS_Ryton Thermal (TMID 150975) ---
$$ TC=0.29 W/m/K, Cp=1000.0 J/kg/K, CTE=49.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PPS_Ryton Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150975 1.350e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.000e+09 2.900e-01
$
$$ CTE=49.0 ppm/K, applied to all 5 MIDs of PPS_Ryton
$$ [DB] PID slot holds MID=100975 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100975         0 4.900e-05
$$ [DB] PID slot holds MID=110975 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110975         0 4.900e-05
$$ [DB] PID slot holds MID=120975 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120975         0 4.900e-05
$$ [DB] PID slot holds MID=130975 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130975         0 4.900e-05
$$ [DB] PID slot holds MID=140975 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140975         0 4.900e-05
$
$$ --- PEEK_Victrex Thermal (TMID 150976) ---
$$ TC=0.25 W/m/K, Cp=1340.0 J/kg/K, CTE=47.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PEEK_Victrex Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150976 1.320e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.340e+09 2.500e-01
$
$$ CTE=47.0 ppm/K, applied to all 5 MIDs of PEEK_Victrex
$$ [DB] PID slot holds MID=100976 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100976         0 4.700e-05
$$ [DB] PID slot holds MID=110976 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110976         0 4.700e-05
$$ [DB] PID slot holds MID=120976 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120976         0 4.700e-05
$$ [DB] PID slot holds MID=130976 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130976         0 4.700e-05
$$ [DB] PID slot holds MID=140976 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140976         0 4.700e-05
$
$$ --- PEI_Ultem Thermal (TMID 150977) ---
$$ TC=0.22 W/m/K, Cp=1200.0 J/kg/K, CTE=56.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PEI_Ultem Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150977 1.270e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.200e+09 2.200e-01
$
$$ CTE=56.0 ppm/K, applied to all 5 MIDs of PEI_Ultem
$$ [DB] PID slot holds MID=100977 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100977         0 5.600e-05
$$ [DB] PID slot holds MID=110977 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110977         0 5.600e-05
$$ [DB] PID slot holds MID=120977 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120977         0 5.600e-05
$$ [DB] PID slot holds MID=130977 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130977         0 5.600e-05
$$ [DB] PID slot holds MID=140977 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140977         0 5.600e-05
$
$ ========================================================================
$ Optical THERMAL
$ ========================================================================
$
$$ --- PMMA_Plexiglas Thermal (TMID 150981) ---
$$ TC=0.19 W/m/K, Cp=1470.0 J/kg/K, CTE=75.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
PMMA_Plexiglas Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150981 1.190e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.470e+09 1.900e-01
$
$$ CTE=75.0 ppm/K, applied to all 5 MIDs of PMMA_Plexiglas
$$ [DB] PID slot holds MID=100981 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100981         0 7.500e-05
$$ [DB] PID slot holds MID=110981 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110981         0 7.500e-05
$$ [DB] PID slot holds MID=120981 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120981         0 7.500e-05
$$ [DB] PID slot holds MID=130981 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130981         0 7.500e-05
$$ [DB] PID slot holds MID=140981 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140981         0 7.500e-05
$
$$ --- COP_Zeonex Thermal (TMID 150982) ---
$$ TC=0.15 W/m/K, Cp=1800.0 J/kg/K, CTE=70.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
COP_Zeonex Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150982 1.010e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.800e+09 1.500e-01
$
$$ CTE=70.0 ppm/K, applied to all 5 MIDs of COP_Zeonex
$$ [DB] PID slot holds MID=100982 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100982         0 7.000e-05
$$ [DB] PID slot holds MID=110982 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110982         0 7.000e-05
$$ [DB] PID slot holds MID=120982 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120982         0 7.000e-05
$$ [DB] PID slot holds MID=130982 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130982         0 7.000e-05
$$ [DB] PID slot holds MID=140982 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140982         0 7.000e-05
$
$$ --- COC_TOPAS Thermal (TMID 150983) ---
$$ TC=0.15 W/m/K, Cp=1750.0 J/kg/K, CTE=60.0 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
COC_TOPAS Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    150983 1.020e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.750e+09 1.500e-01
$
$$ CTE=60.0 ppm/K, applied to all 5 MIDs of COC_TOPAS
$$ [DB] PID slot holds MID=100983 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100983         0 6.000e-05
$$ [DB] PID slot holds MID=110983 (Bilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110983         0 6.000e-05
$$ [DB] PID slot holds MID=120983 (Multilinear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    120983         0 6.000e-05
$$ [DB] PID slot holds MID=130983 (Kinematic, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130983         0 6.000e-05
$$ [DB] PID slot holds MID=140983 (SAMP-1, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    140983         0 6.000e-05
$
*END
