$ ========================================================================
$ RUBBER THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)
$   Cp (specific heat)        : mm^2/s^2/K (= J/kg/K * 1e6)
$   CTE                       : 1/K  (= ppm/K * 1e-6)
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID,
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !!  CTE is applied to all 3 MIDs (linear/Mooney-Rivlin/Ogden+Visco).
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   TMID    Name                      CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)
$   ----------------------------------------------------------------------
$   120901  NR_SoftSuperior               220.0     0.140     1900.0
$   120902  NR_Standard                   220.0     0.140     1900.0
$   120903  SBR_TireTread                 225.0     0.200     1880.0
$   120904  BR_Butadiene                  220.0     0.220     1900.0
$   120905  IIR_Butyl                     195.0     0.130     1960.0
$   120906  CR_Neoprene                   200.0     0.190     1700.0
$   120907  NBR_Nitrile                   230.0     0.250     1900.0
$   120908  EPDM_Standard                 200.0     0.360     2000.0
$   120911  VMQ_Silicone_Std              310.0     0.220     1300.0
$   120912  VMQ_Silicone_Firm             300.0     0.240     1300.0
$   120913  FKM_Viton                     160.0     0.250     1700.0
$   120914  FFKM_Kalrez                   150.0     0.250     1700.0
$   120921  TPU_Hard_85A                  170.0     0.190     1800.0
$   120922  TPE_S_SBS                     180.0     0.140     1900.0
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Natural THERMAL
$ ========================================================================
$
$$ --- NR_SoftSuperior Thermal (TMID 120901) ---
$$ TC=0.14 W/m/K, Cp=1900.0 J/kg/K, rho=0.92 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
NR_SoftSuperior Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120901 9.200e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.900e+09 1.400e-01
$
$$ CTE=220.0 ppm/K, applied to all 3 MIDs of NR_SoftSuperior
$$ [DB] PID slot holds MID=100901 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100901         0 2.200e-04
$$ [DB] PID slot holds MID=110901 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110901         0 2.200e-04
$$ [DB] PID slot holds MID=130901 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130901         0 2.200e-04
$
$$ --- NR_Standard Thermal (TMID 120902) ---
$$ TC=0.14 W/m/K, Cp=1900.0 J/kg/K, rho=0.93 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
NR_Standard Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120902 9.300e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.900e+09 1.400e-01
$
$$ CTE=220.0 ppm/K, applied to all 3 MIDs of NR_Standard
$$ [DB] PID slot holds MID=100902 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100902         0 2.200e-04
$$ [DB] PID slot holds MID=110902 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110902         0 2.200e-04
$$ [DB] PID slot holds MID=130902 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130902         0 2.200e-04
$
$$ --- SBR_TireTread Thermal (TMID 120903) ---
$$ TC=0.2 W/m/K, Cp=1880.0 J/kg/K, rho=0.94 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
SBR_TireTread Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120903 9.400e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.880e+09 2.000e-01
$
$$ CTE=225.0 ppm/K, applied to all 3 MIDs of SBR_TireTread
$$ [DB] PID slot holds MID=100903 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100903         0 2.250e-04
$$ [DB] PID slot holds MID=110903 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110903         0 2.250e-04
$$ [DB] PID slot holds MID=130903 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130903         0 2.250e-04
$
$$ --- BR_Butadiene Thermal (TMID 120904) ---
$$ TC=0.22 W/m/K, Cp=1900.0 J/kg/K, rho=0.93 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
BR_Butadiene Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120904 9.300e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.900e+09 2.200e-01
$
$$ CTE=220.0 ppm/K, applied to all 3 MIDs of BR_Butadiene
$$ [DB] PID slot holds MID=100904 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100904         0 2.200e-04
$$ [DB] PID slot holds MID=110904 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110904         0 2.200e-04
$$ [DB] PID slot holds MID=130904 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130904         0 2.200e-04
$
$$ --- IIR_Butyl Thermal (TMID 120905) ---
$$ TC=0.13 W/m/K, Cp=1960.0 J/kg/K, rho=0.92 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
IIR_Butyl Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120905 9.200e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.960e+09 1.300e-01
$
$$ CTE=195.0 ppm/K, applied to all 3 MIDs of IIR_Butyl
$$ [DB] PID slot holds MID=100905 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100905         0 1.950e-04
$$ [DB] PID slot holds MID=110905 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110905         0 1.950e-04
$$ [DB] PID slot holds MID=130905 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130905         0 1.950e-04
$
$$ --- CR_Neoprene Thermal (TMID 120906) ---
$$ TC=0.19 W/m/K, Cp=1700.0 J/kg/K, rho=1.23 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
CR_Neoprene Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120906 1.230e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.700e+09 1.900e-01
$
$$ CTE=200.0 ppm/K, applied to all 3 MIDs of CR_Neoprene
$$ [DB] PID slot holds MID=100906 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100906         0 2.000e-04
$$ [DB] PID slot holds MID=110906 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110906         0 2.000e-04
$$ [DB] PID slot holds MID=130906 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130906         0 2.000e-04
$
$$ --- NBR_Nitrile Thermal (TMID 120907) ---
$$ TC=0.25 W/m/K, Cp=1900.0 J/kg/K, rho=1.0 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
NBR_Nitrile Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120907 1.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.900e+09 2.500e-01
$
$$ CTE=230.0 ppm/K, applied to all 3 MIDs of NBR_Nitrile
$$ [DB] PID slot holds MID=100907 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100907         0 2.300e-04
$$ [DB] PID slot holds MID=110907 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110907         0 2.300e-04
$$ [DB] PID slot holds MID=130907 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130907         0 2.300e-04
$
$$ --- EPDM_Standard Thermal (TMID 120908) ---
$$ TC=0.36 W/m/K, Cp=2000.0 J/kg/K, rho=0.86 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
EPDM_Standard Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120908 8.600e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 2.000e+09 3.600e-01
$
$$ CTE=200.0 ppm/K, applied to all 3 MIDs of EPDM_Standard
$$ [DB] PID slot holds MID=100908 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100908         0 2.000e-04
$$ [DB] PID slot holds MID=110908 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110908         0 2.000e-04
$$ [DB] PID slot holds MID=130908 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130908         0 2.000e-04
$
$ ========================================================================
$ HighPerformance THERMAL
$ ========================================================================
$
$$ --- VMQ_Silicone_Std Thermal (TMID 120911) ---
$$ TC=0.22 W/m/K, Cp=1300.0 J/kg/K, rho=1.15 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
VMQ_Silicone_Std Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120911 1.150e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.300e+09 2.200e-01
$
$$ CTE=310.0 ppm/K, applied to all 3 MIDs of VMQ_Silicone_Std
$$ [DB] PID slot holds MID=100911 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100911         0 3.100e-04
$$ [DB] PID slot holds MID=110911 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110911         0 3.100e-04
$$ [DB] PID slot holds MID=130911 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130911         0 3.100e-04
$
$$ --- VMQ_Silicone_Firm Thermal (TMID 120912) ---
$$ TC=0.24 W/m/K, Cp=1300.0 J/kg/K, rho=1.2 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
VMQ_Silicone_Firm Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120912 1.200e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.300e+09 2.400e-01
$
$$ CTE=300.0 ppm/K, applied to all 3 MIDs of VMQ_Silicone_Firm
$$ [DB] PID slot holds MID=100912 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100912         0 3.000e-04
$$ [DB] PID slot holds MID=110912 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110912         0 3.000e-04
$$ [DB] PID slot holds MID=130912 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130912         0 3.000e-04
$
$$ --- FKM_Viton Thermal (TMID 120913) ---
$$ TC=0.25 W/m/K, Cp=1700.0 J/kg/K, rho=1.85 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
FKM_Viton Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120913 1.850e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.700e+09 2.500e-01
$
$$ CTE=160.0 ppm/K, applied to all 3 MIDs of FKM_Viton
$$ [DB] PID slot holds MID=100913 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100913         0 1.600e-04
$$ [DB] PID slot holds MID=110913 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110913         0 1.600e-04
$$ [DB] PID slot holds MID=130913 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130913         0 1.600e-04
$
$$ --- FFKM_Kalrez Thermal (TMID 120914) ---
$$ TC=0.25 W/m/K, Cp=1700.0 J/kg/K, rho=2.0 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
FFKM_Kalrez Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120914 2.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.700e+09 2.500e-01
$
$$ CTE=150.0 ppm/K, applied to all 3 MIDs of FFKM_Kalrez
$$ [DB] PID slot holds MID=100914 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100914         0 1.500e-04
$$ [DB] PID slot holds MID=110914 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110914         0 1.500e-04
$$ [DB] PID slot holds MID=130914 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130914         0 1.500e-04
$
$ ========================================================================
$ TPE THERMAL
$ ========================================================================
$
$$ --- TPU_Hard_85A Thermal (TMID 120921) ---
$$ TC=0.19 W/m/K, Cp=1800.0 J/kg/K, rho=1.2 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
TPU_Hard_85A Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120921 1.200e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.800e+09 1.900e-01
$
$$ CTE=170.0 ppm/K, applied to all 3 MIDs of TPU_Hard_85A
$$ [DB] PID slot holds MID=100921 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100921         0 1.700e-04
$$ [DB] PID slot holds MID=110921 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110921         0 1.700e-04
$$ [DB] PID slot holds MID=130921 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130921         0 1.700e-04
$
$$ --- TPE_S_SBS Thermal (TMID 120922) ---
$$ TC=0.14 W/m/K, Cp=1900.0 J/kg/K, rho=0.93 g/cc
*MAT_THERMAL_ISOTROPIC_TITLE
TPE_S_SBS Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120922 9.300e-10         0    1.0000    0.0000    0.0000
$       HC         TC
 1.900e+09 1.400e-01
$
$$ CTE=180.0 ppm/K, applied to all 3 MIDs of TPE_S_SBS
$$ [DB] PID slot holds MID=100922 (Linear, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100922         0 1.800e-04
$$ [DB] PID slot holds MID=110922 (Mooney-Rivlin, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    110922         0 1.800e-04
$$ [DB] PID slot holds MID=130922 (Ogden+Visco, external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    130922         0 1.800e-04
$
*END
