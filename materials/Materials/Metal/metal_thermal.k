$ ========================================================================
$ METAL THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)
$   Cp (specific heat)        : mm^2/s^2/K (= J/kg/K * 1e6)
$   CTE                       : 1/K  (= ppm/K * 1e-6)
$
$ *MAT_THERMAL_ISOTROPIC for coupled thermal-mechanical analysis
$   Reference the TMID in your *PART card.
$ *MAT_ADD_THERMAL_EXPANSION for thermal strain
$   Paired with 4 structural MIDs: bi_iso, multi_iso, kin_pure, kin_mixed.
$
$ !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
$ !!  DATABASE CONVENTION — IMPORTANT                                  !!
$ !!                                                                     !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID  !!
$ !!  (MID), NOT an actual Part ID. This is a library convention:        !!
$ !!                                                                     !!
$ !!    1. All CTE cards in this file are template placeholders.         !!
$ !!    2. Before running LS-DYNA, an external tool must:                !!
$ !!       - Scan user's main model for *PART cards                      !!
$ !!       - Find all PIDs that reference each MID from this library     !!
$ !!       - Generate one *MAT_ADD_THERMAL_EXPANSION per actual PID       !!
$ !!    3. Running this file as-is will cause LS-DYNA to complain that   !!
$ !!       PID (e.g. 100535) does not exist.                             !!
$ !!                                                                     !!
$ !!  The *MAT_THERMAL_ISOTROPIC cards themselves are standalone and     !!
$ !!  used directly via TMID field in *PART — no replacement needed.     !!
$ !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
$
$ ========================================================================
$ SUMMARY TABLE
$
$   TMID    Name                     CTE(ppm/K)  TC(W/m/K)  Cp(J/kg/K)
$   ----------------------------------------------------------------------
$   120501  SUS201_annealed              16.90     16.20     500.0
$   120502  SUS301_annealed              16.90     16.20     500.0
$   120503  SUS304_annealed              17.30     16.20     500.0
$   120504  SUS304L_annealed             17.30     16.20     500.0
$   120505  SUS316_annealed              16.00     15.90     500.0
$   120506  SUS316L_annealed             16.00     15.90     500.0
$   120507  SUS410_annealed              10.40     24.90     460.0
$   120508  SUS420_annealed              10.30     24.90     460.0
$   120509  SUS430_annealed              10.40     26.10     460.0
$   120510  SUS_17-4PH_H900              10.80     17.90     460.0
$   120521  Al1050-O                     23.60    229.00     900.0
$   120522  Al1100-O                     23.60    222.00     904.0
$   120523  Al2024-T3                    23.20    121.00     875.0
$   120524  Al3003-H14                   23.20    159.00     893.0
$   120525  Al5052-H32                   23.80    138.00     880.0
$   120526  Al5083-H116                  23.80    117.00     900.0
$   120535  Al6061-T6                    23.40    167.00     896.0
$   120536  Al6063-T5                    23.40    201.00     900.0
$   120537  Al6063-T6                    23.40    201.00     900.0
$   120538  Al7050-T7451                 23.50    157.00     860.0
$   120539  Al7075-T6                    23.60    130.00     960.0
$   120540  ADC12_diecast                21.00     96.00     963.0
$   120561  Ti_Grade1                     8.60     16.40     523.0
$   120562  Ti_Grade2                     8.60     16.40     523.0
$   120563  Ti_Grade4                     8.60     16.40     523.0
$   120564  Ti6Al4V_Grade5                8.60      6.70     526.3
$   120565  Ti6Al4V_Grade5_ELI            8.60      6.70     526.3
$   120566  Ti3Al2.5V_Grade9              9.40      8.30     540.0
$   120581  Mg_AZ31B_H24                 26.00     96.00    1024.0
$   120582  Mg_AZ91D_diecast             26.00     72.00    1020.0
$   120583  Mg_ZK60A_T5                  26.00    117.00    1004.0
$   120591  SPCC_mild_steel              12.00     52.00     465.0
$   120592  S45C_medium_carbon           11.00     49.80     486.0
$   120593  SCM440_alloy_steel           12.30     42.60     477.0
$   120601  C26000_Cartridge_Brass       19.90    120.00     375.0
$   120602  C36000_FreeCutting_Brass     20.50    115.00     380.0
$   120603  C51000_Phosphor_Bronze       17.80     69.00     380.0
$   120611  Inconel_625_annealed         12.80      9.80     410.0
$   120612  Inconel_718_aged             13.00     11.40     435.0
$   120621  Tungsten_99pct                4.50    174.00     134.0
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ SUS THERMAL
$ ========================================================================
$
$$ --- SUS201_annealed Thermal (TMID 120501) ---
$$ TC=16.2 W/m/K, Cp=500.0 J/kg/K, rho=7.8 g/cc
$$ Converted: TC=1.6200e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS201_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120501 7.800e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.620e+01
$
$$ CTE=16.9 ppm/K, applied to all 4 MIDs of SUS201_annealed
$$   bi_iso=100501, multi_iso=110501, kin_pure=130501, kin_mixed=140501
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS201_annealed bi_iso -- PID slot holds MID=100501
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100501         0 1.690e-05
$$ [DB] SUS201_annealed multi_iso -- PID slot holds MID=110501
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110501         0 1.690e-05
$$ [DB] SUS201_annealed kin_pure -- PID slot holds MID=130501
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130501         0 1.690e-05
$$ [DB] SUS201_annealed kin_mixed -- PID slot holds MID=140501
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140501         0 1.690e-05
$
$$ --- SUS301_annealed Thermal (TMID 120502) ---
$$ TC=16.2 W/m/K, Cp=500.0 J/kg/K, rho=7.88 g/cc
$$ Converted: TC=1.6200e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS301_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120502 7.880e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.620e+01
$
$$ CTE=16.9 ppm/K, applied to all 4 MIDs of SUS301_annealed
$$   bi_iso=100502, multi_iso=110502, kin_pure=130502, kin_mixed=140502
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS301_annealed bi_iso -- PID slot holds MID=100502
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100502         0 1.690e-05
$$ [DB] SUS301_annealed multi_iso -- PID slot holds MID=110502
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110502         0 1.690e-05
$$ [DB] SUS301_annealed kin_pure -- PID slot holds MID=130502
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130502         0 1.690e-05
$$ [DB] SUS301_annealed kin_mixed -- PID slot holds MID=140502
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140502         0 1.690e-05
$
$$ --- SUS304_annealed Thermal (TMID 120503) ---
$$ TC=16.2 W/m/K, Cp=500.0 J/kg/K, rho=8.0 g/cc
$$ Converted: TC=1.6200e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS304_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120503 8.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.620e+01
$
$$ CTE=17.3 ppm/K, applied to all 4 MIDs of SUS304_annealed
$$   bi_iso=100503, multi_iso=110503, kin_pure=130503, kin_mixed=140503
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS304_annealed bi_iso -- PID slot holds MID=100503
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100503         0 1.730e-05
$$ [DB] SUS304_annealed multi_iso -- PID slot holds MID=110503
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110503         0 1.730e-05
$$ [DB] SUS304_annealed kin_pure -- PID slot holds MID=130503
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130503         0 1.730e-05
$$ [DB] SUS304_annealed kin_mixed -- PID slot holds MID=140503
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140503         0 1.730e-05
$
$$ --- SUS304L_annealed Thermal (TMID 120504) ---
$$ TC=16.2 W/m/K, Cp=500.0 J/kg/K, rho=8.0 g/cc
$$ Converted: TC=1.6200e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS304L_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120504 8.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.620e+01
$
$$ CTE=17.3 ppm/K, applied to all 4 MIDs of SUS304L_annealed
$$   bi_iso=100504, multi_iso=110504, kin_pure=130504, kin_mixed=140504
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS304L_annealed bi_iso -- PID slot holds MID=100504
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100504         0 1.730e-05
$$ [DB] SUS304L_annealed multi_iso -- PID slot holds MID=110504
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110504         0 1.730e-05
$$ [DB] SUS304L_annealed kin_pure -- PID slot holds MID=130504
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130504         0 1.730e-05
$$ [DB] SUS304L_annealed kin_mixed -- PID slot holds MID=140504
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140504         0 1.730e-05
$
$$ --- SUS316_annealed Thermal (TMID 120505) ---
$$ TC=15.9 W/m/K, Cp=500.0 J/kg/K, rho=8.0 g/cc
$$ Converted: TC=1.5900e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS316_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120505 8.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.590e+01
$
$$ CTE=16.0 ppm/K, applied to all 4 MIDs of SUS316_annealed
$$   bi_iso=100505, multi_iso=110505, kin_pure=130505, kin_mixed=140505
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS316_annealed bi_iso -- PID slot holds MID=100505
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100505         0 1.600e-05
$$ [DB] SUS316_annealed multi_iso -- PID slot holds MID=110505
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110505         0 1.600e-05
$$ [DB] SUS316_annealed kin_pure -- PID slot holds MID=130505
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130505         0 1.600e-05
$$ [DB] SUS316_annealed kin_mixed -- PID slot holds MID=140505
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140505         0 1.600e-05
$
$$ --- SUS316L_annealed Thermal (TMID 120506) ---
$$ TC=15.9 W/m/K, Cp=500.0 J/kg/K, rho=8.0 g/cc
$$ Converted: TC=1.5900e+01 mW/mm/K, Cp=5.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS316L_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120506 8.000e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.000e+08 1.590e+01
$
$$ CTE=16.0 ppm/K, applied to all 4 MIDs of SUS316L_annealed
$$   bi_iso=100506, multi_iso=110506, kin_pure=130506, kin_mixed=140506
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS316L_annealed bi_iso -- PID slot holds MID=100506
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100506         0 1.600e-05
$$ [DB] SUS316L_annealed multi_iso -- PID slot holds MID=110506
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110506         0 1.600e-05
$$ [DB] SUS316L_annealed kin_pure -- PID slot holds MID=130506
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130506         0 1.600e-05
$$ [DB] SUS316L_annealed kin_mixed -- PID slot holds MID=140506
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140506         0 1.600e-05
$
$$ --- SUS410_annealed Thermal (TMID 120507) ---
$$ TC=24.9 W/m/K, Cp=460.0 J/kg/K, rho=7.74 g/cc
$$ Converted: TC=2.4900e+01 mW/mm/K, Cp=4.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS410_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120507 7.740e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 2.490e+01
$
$$ CTE=10.4 ppm/K, applied to all 4 MIDs of SUS410_annealed
$$   bi_iso=100507, multi_iso=110507, kin_pure=130507, kin_mixed=140507
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS410_annealed bi_iso -- PID slot holds MID=100507
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100507         0 1.040e-05
$$ [DB] SUS410_annealed multi_iso -- PID slot holds MID=110507
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110507         0 1.040e-05
$$ [DB] SUS410_annealed kin_pure -- PID slot holds MID=130507
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130507         0 1.040e-05
$$ [DB] SUS410_annealed kin_mixed -- PID slot holds MID=140507
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140507         0 1.040e-05
$
$$ --- SUS420_annealed Thermal (TMID 120508) ---
$$ TC=24.9 W/m/K, Cp=460.0 J/kg/K, rho=7.75 g/cc
$$ Converted: TC=2.4900e+01 mW/mm/K, Cp=4.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS420_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120508 7.750e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 2.490e+01
$
$$ CTE=10.3 ppm/K, applied to all 4 MIDs of SUS420_annealed
$$   bi_iso=100508, multi_iso=110508, kin_pure=130508, kin_mixed=140508
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS420_annealed bi_iso -- PID slot holds MID=100508
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100508         0 1.030e-05
$$ [DB] SUS420_annealed multi_iso -- PID slot holds MID=110508
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110508         0 1.030e-05
$$ [DB] SUS420_annealed kin_pure -- PID slot holds MID=130508
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130508         0 1.030e-05
$$ [DB] SUS420_annealed kin_mixed -- PID slot holds MID=140508
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140508         0 1.030e-05
$
$$ --- SUS430_annealed Thermal (TMID 120509) ---
$$ TC=26.1 W/m/K, Cp=460.0 J/kg/K, rho=7.7 g/cc
$$ Converted: TC=2.6100e+01 mW/mm/K, Cp=4.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS430_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120509 7.700e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 2.610e+01
$
$$ CTE=10.4 ppm/K, applied to all 4 MIDs of SUS430_annealed
$$   bi_iso=100509, multi_iso=110509, kin_pure=130509, kin_mixed=140509
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS430_annealed bi_iso -- PID slot holds MID=100509
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100509         0 1.040e-05
$$ [DB] SUS430_annealed multi_iso -- PID slot holds MID=110509
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110509         0 1.040e-05
$$ [DB] SUS430_annealed kin_pure -- PID slot holds MID=130509
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130509         0 1.040e-05
$$ [DB] SUS430_annealed kin_mixed -- PID slot holds MID=140509
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140509         0 1.040e-05
$
$$ --- SUS_17-4PH_H900 Thermal (TMID 120510) ---
$$ TC=17.9 W/m/K, Cp=460.0 J/kg/K, rho=7.8 g/cc
$$ Converted: TC=1.7900e+01 mW/mm/K, Cp=4.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SUS_17-4PH_H900 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120510 7.800e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.600e+08 1.790e+01
$
$$ CTE=10.8 ppm/K, applied to all 4 MIDs of SUS_17-4PH_H900
$$   bi_iso=100510, multi_iso=110510, kin_pure=130510, kin_mixed=140510
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SUS_17-4PH_H900 bi_iso -- PID slot holds MID=100510
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100510         0 1.080e-05
$$ [DB] SUS_17-4PH_H900 multi_iso -- PID slot holds MID=110510
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110510         0 1.080e-05
$$ [DB] SUS_17-4PH_H900 kin_pure -- PID slot holds MID=130510
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130510         0 1.080e-05
$$ [DB] SUS_17-4PH_H900 kin_mixed -- PID slot holds MID=140510
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140510         0 1.080e-05
$
$ ========================================================================
$ Al THERMAL
$ ========================================================================
$
$$ --- Al1050-O Thermal (TMID 120521) ---
$$ TC=229.0 W/m/K, Cp=900.0 J/kg/K, rho=2.705 g/cc
$$ Converted: TC=2.2900e+02 mW/mm/K, Cp=9.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al1050-O Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120521 2.705e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.000e+08 2.290e+02
$
$$ CTE=23.6 ppm/K, applied to all 4 MIDs of Al1050-O
$$   bi_iso=100521, multi_iso=110521, kin_pure=130521, kin_mixed=140521
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al1050-O bi_iso -- PID slot holds MID=100521
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100521         0 2.360e-05
$$ [DB] Al1050-O multi_iso -- PID slot holds MID=110521
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110521         0 2.360e-05
$$ [DB] Al1050-O kin_pure -- PID slot holds MID=130521
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130521         0 2.360e-05
$$ [DB] Al1050-O kin_mixed -- PID slot holds MID=140521
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140521         0 2.360e-05
$
$$ --- Al1100-O Thermal (TMID 120522) ---
$$ TC=222.0 W/m/K, Cp=904.0 J/kg/K, rho=2.71 g/cc
$$ Converted: TC=2.2200e+02 mW/mm/K, Cp=9.0400e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al1100-O Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120522 2.710e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.040e+08 2.220e+02
$
$$ CTE=23.6 ppm/K, applied to all 4 MIDs of Al1100-O
$$   bi_iso=100522, multi_iso=110522, kin_pure=130522, kin_mixed=140522
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al1100-O bi_iso -- PID slot holds MID=100522
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100522         0 2.360e-05
$$ [DB] Al1100-O multi_iso -- PID slot holds MID=110522
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110522         0 2.360e-05
$$ [DB] Al1100-O kin_pure -- PID slot holds MID=130522
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130522         0 2.360e-05
$$ [DB] Al1100-O kin_mixed -- PID slot holds MID=140522
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140522         0 2.360e-05
$
$$ --- Al2024-T3 Thermal (TMID 120523) ---
$$ TC=121.0 W/m/K, Cp=875.0 J/kg/K, rho=2.78 g/cc
$$ Converted: TC=1.2100e+02 mW/mm/K, Cp=8.7500e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al2024-T3 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120523 2.780e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.750e+08 1.210e+02
$
$$ CTE=23.2 ppm/K, applied to all 4 MIDs of Al2024-T3
$$   bi_iso=100523, multi_iso=110523, kin_pure=130523, kin_mixed=140523
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al2024-T3 bi_iso -- PID slot holds MID=100523
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100523         0 2.320e-05
$$ [DB] Al2024-T3 multi_iso -- PID slot holds MID=110523
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110523         0 2.320e-05
$$ [DB] Al2024-T3 kin_pure -- PID slot holds MID=130523
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130523         0 2.320e-05
$$ [DB] Al2024-T3 kin_mixed -- PID slot holds MID=140523
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140523         0 2.320e-05
$
$$ --- Al3003-H14 Thermal (TMID 120524) ---
$$ TC=159.0 W/m/K, Cp=893.0 J/kg/K, rho=2.73 g/cc
$$ Converted: TC=1.5900e+02 mW/mm/K, Cp=8.9300e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al3003-H14 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120524 2.730e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.930e+08 1.590e+02
$
$$ CTE=23.2 ppm/K, applied to all 4 MIDs of Al3003-H14
$$   bi_iso=100524, multi_iso=110524, kin_pure=130524, kin_mixed=140524
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al3003-H14 bi_iso -- PID slot holds MID=100524
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100524         0 2.320e-05
$$ [DB] Al3003-H14 multi_iso -- PID slot holds MID=110524
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110524         0 2.320e-05
$$ [DB] Al3003-H14 kin_pure -- PID slot holds MID=130524
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130524         0 2.320e-05
$$ [DB] Al3003-H14 kin_mixed -- PID slot holds MID=140524
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140524         0 2.320e-05
$
$$ --- Al5052-H32 Thermal (TMID 120525) ---
$$ TC=138.0 W/m/K, Cp=880.0 J/kg/K, rho=2.68 g/cc
$$ Converted: TC=1.3800e+02 mW/mm/K, Cp=8.8000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al5052-H32 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120525 2.680e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.800e+08 1.380e+02
$
$$ CTE=23.8 ppm/K, applied to all 4 MIDs of Al5052-H32
$$   bi_iso=100525, multi_iso=110525, kin_pure=130525, kin_mixed=140525
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al5052-H32 bi_iso -- PID slot holds MID=100525
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100525         0 2.380e-05
$$ [DB] Al5052-H32 multi_iso -- PID slot holds MID=110525
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110525         0 2.380e-05
$$ [DB] Al5052-H32 kin_pure -- PID slot holds MID=130525
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130525         0 2.380e-05
$$ [DB] Al5052-H32 kin_mixed -- PID slot holds MID=140525
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140525         0 2.380e-05
$
$$ --- Al5083-H116 Thermal (TMID 120526) ---
$$ TC=117.0 W/m/K, Cp=900.0 J/kg/K, rho=2.66 g/cc
$$ Converted: TC=1.1700e+02 mW/mm/K, Cp=9.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al5083-H116 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120526 2.660e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.000e+08 1.170e+02
$
$$ CTE=23.8 ppm/K, applied to all 4 MIDs of Al5083-H116
$$   bi_iso=100526, multi_iso=110526, kin_pure=130526, kin_mixed=140526
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al5083-H116 bi_iso -- PID slot holds MID=100526
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100526         0 2.380e-05
$$ [DB] Al5083-H116 multi_iso -- PID slot holds MID=110526
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110526         0 2.380e-05
$$ [DB] Al5083-H116 kin_pure -- PID slot holds MID=130526
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130526         0 2.380e-05
$$ [DB] Al5083-H116 kin_mixed -- PID slot holds MID=140526
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140526         0 2.380e-05
$
$$ --- Al6061-T6 Thermal (TMID 120535) ---
$$ TC=167.0 W/m/K, Cp=896.0 J/kg/K, rho=2.7 g/cc
$$ Converted: TC=1.6700e+02 mW/mm/K, Cp=8.9600e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al6061-T6 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120535 2.700e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.960e+08 1.670e+02
$
$$ CTE=23.4 ppm/K, applied to all 4 MIDs of Al6061-T6
$$   bi_iso=100535, multi_iso=110535, kin_pure=130535, kin_mixed=140535
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al6061-T6 bi_iso -- PID slot holds MID=100535
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100535         0 2.340e-05
$$ [DB] Al6061-T6 multi_iso -- PID slot holds MID=110535
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110535         0 2.340e-05
$$ [DB] Al6061-T6 kin_pure -- PID slot holds MID=130535
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130535         0 2.340e-05
$$ [DB] Al6061-T6 kin_mixed -- PID slot holds MID=140535
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140535         0 2.340e-05
$
$$ --- Al6063-T5 Thermal (TMID 120536) ---
$$ TC=201.0 W/m/K, Cp=900.0 J/kg/K, rho=2.7 g/cc
$$ Converted: TC=2.0100e+02 mW/mm/K, Cp=9.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al6063-T5 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120536 2.700e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.000e+08 2.010e+02
$
$$ CTE=23.4 ppm/K, applied to all 4 MIDs of Al6063-T5
$$   bi_iso=100536, multi_iso=110536, kin_pure=130536, kin_mixed=140536
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al6063-T5 bi_iso -- PID slot holds MID=100536
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100536         0 2.340e-05
$$ [DB] Al6063-T5 multi_iso -- PID slot holds MID=110536
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110536         0 2.340e-05
$$ [DB] Al6063-T5 kin_pure -- PID slot holds MID=130536
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130536         0 2.340e-05
$$ [DB] Al6063-T5 kin_mixed -- PID slot holds MID=140536
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140536         0 2.340e-05
$
$$ --- Al6063-T6 Thermal (TMID 120537) ---
$$ TC=201.0 W/m/K, Cp=900.0 J/kg/K, rho=2.7 g/cc
$$ Converted: TC=2.0100e+02 mW/mm/K, Cp=9.0000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al6063-T6 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120537 2.700e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.000e+08 2.010e+02
$
$$ CTE=23.4 ppm/K, applied to all 4 MIDs of Al6063-T6
$$   bi_iso=100537, multi_iso=110537, kin_pure=130537, kin_mixed=140537
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al6063-T6 bi_iso -- PID slot holds MID=100537
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100537         0 2.340e-05
$$ [DB] Al6063-T6 multi_iso -- PID slot holds MID=110537
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110537         0 2.340e-05
$$ [DB] Al6063-T6 kin_pure -- PID slot holds MID=130537
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130537         0 2.340e-05
$$ [DB] Al6063-T6 kin_mixed -- PID slot holds MID=140537
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140537         0 2.340e-05
$
$$ --- Al7050-T7451 Thermal (TMID 120538) ---
$$ TC=157.0 W/m/K, Cp=860.0 J/kg/K, rho=2.83 g/cc
$$ Converted: TC=1.5700e+02 mW/mm/K, Cp=8.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al7050-T7451 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120538 2.830e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 8.600e+08 1.570e+02
$
$$ CTE=23.5 ppm/K, applied to all 4 MIDs of Al7050-T7451
$$   bi_iso=100538, multi_iso=110538, kin_pure=130538, kin_mixed=140538
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al7050-T7451 bi_iso -- PID slot holds MID=100538
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100538         0 2.350e-05
$$ [DB] Al7050-T7451 multi_iso -- PID slot holds MID=110538
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110538         0 2.350e-05
$$ [DB] Al7050-T7451 kin_pure -- PID slot holds MID=130538
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130538         0 2.350e-05
$$ [DB] Al7050-T7451 kin_mixed -- PID slot holds MID=140538
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140538         0 2.350e-05
$
$$ --- Al7075-T6 Thermal (TMID 120539) ---
$$ TC=130.0 W/m/K, Cp=960.0 J/kg/K, rho=2.81 g/cc
$$ Converted: TC=1.3000e+02 mW/mm/K, Cp=9.6000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Al7075-T6 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120539 2.810e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.600e+08 1.300e+02
$
$$ CTE=23.6 ppm/K, applied to all 4 MIDs of Al7075-T6
$$   bi_iso=100539, multi_iso=110539, kin_pure=130539, kin_mixed=140539
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Al7075-T6 bi_iso -- PID slot holds MID=100539
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100539         0 2.360e-05
$$ [DB] Al7075-T6 multi_iso -- PID slot holds MID=110539
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110539         0 2.360e-05
$$ [DB] Al7075-T6 kin_pure -- PID slot holds MID=130539
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130539         0 2.360e-05
$$ [DB] Al7075-T6 kin_mixed -- PID slot holds MID=140539
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140539         0 2.360e-05
$
$$ --- ADC12_diecast Thermal (TMID 120540) ---
$$ TC=96.0 W/m/K, Cp=963.0 J/kg/K, rho=2.7 g/cc
$$ Converted: TC=9.6000e+01 mW/mm/K, Cp=9.6300e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
ADC12_diecast Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120540 2.700e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 9.630e+08 9.600e+01
$
$$ CTE=21.0 ppm/K, applied to all 4 MIDs of ADC12_diecast
$$   bi_iso=100540, multi_iso=110540, kin_pure=130540, kin_mixed=140540
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] ADC12_diecast bi_iso -- PID slot holds MID=100540
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100540         0 2.100e-05
$$ [DB] ADC12_diecast multi_iso -- PID slot holds MID=110540
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110540         0 2.100e-05
$$ [DB] ADC12_diecast kin_pure -- PID slot holds MID=130540
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130540         0 2.100e-05
$$ [DB] ADC12_diecast kin_mixed -- PID slot holds MID=140540
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140540         0 2.100e-05
$
$ ========================================================================
$ Ti THERMAL
$ ========================================================================
$
$$ --- Ti_Grade1 Thermal (TMID 120561) ---
$$ TC=16.4 W/m/K, Cp=523.0 J/kg/K, rho=4.51 g/cc
$$ Converted: TC=1.6400e+01 mW/mm/K, Cp=5.2300e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti_Grade1 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120561 4.510e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.230e+08 1.640e+01
$
$$ CTE=8.6 ppm/K, applied to all 4 MIDs of Ti_Grade1
$$   bi_iso=100561, multi_iso=110561, kin_pure=130561, kin_mixed=140561
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti_Grade1 bi_iso -- PID slot holds MID=100561
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100561         0 8.600e-06
$$ [DB] Ti_Grade1 multi_iso -- PID slot holds MID=110561
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110561         0 8.600e-06
$$ [DB] Ti_Grade1 kin_pure -- PID slot holds MID=130561
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130561         0 8.600e-06
$$ [DB] Ti_Grade1 kin_mixed -- PID slot holds MID=140561
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140561         0 8.600e-06
$
$$ --- Ti_Grade2 Thermal (TMID 120562) ---
$$ TC=16.4 W/m/K, Cp=523.0 J/kg/K, rho=4.51 g/cc
$$ Converted: TC=1.6400e+01 mW/mm/K, Cp=5.2300e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti_Grade2 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120562 4.510e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.230e+08 1.640e+01
$
$$ CTE=8.6 ppm/K, applied to all 4 MIDs of Ti_Grade2
$$   bi_iso=100562, multi_iso=110562, kin_pure=130562, kin_mixed=140562
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti_Grade2 bi_iso -- PID slot holds MID=100562
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100562         0 8.600e-06
$$ [DB] Ti_Grade2 multi_iso -- PID slot holds MID=110562
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110562         0 8.600e-06
$$ [DB] Ti_Grade2 kin_pure -- PID slot holds MID=130562
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130562         0 8.600e-06
$$ [DB] Ti_Grade2 kin_mixed -- PID slot holds MID=140562
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140562         0 8.600e-06
$
$$ --- Ti_Grade4 Thermal (TMID 120563) ---
$$ TC=16.4 W/m/K, Cp=523.0 J/kg/K, rho=4.51 g/cc
$$ Converted: TC=1.6400e+01 mW/mm/K, Cp=5.2300e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti_Grade4 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120563 4.510e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.230e+08 1.640e+01
$
$$ CTE=8.6 ppm/K, applied to all 4 MIDs of Ti_Grade4
$$   bi_iso=100563, multi_iso=110563, kin_pure=130563, kin_mixed=140563
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti_Grade4 bi_iso -- PID slot holds MID=100563
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100563         0 8.600e-06
$$ [DB] Ti_Grade4 multi_iso -- PID slot holds MID=110563
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110563         0 8.600e-06
$$ [DB] Ti_Grade4 kin_pure -- PID slot holds MID=130563
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130563         0 8.600e-06
$$ [DB] Ti_Grade4 kin_mixed -- PID slot holds MID=140563
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140563         0 8.600e-06
$
$$ --- Ti6Al4V_Grade5 Thermal (TMID 120564) ---
$$ TC=6.7 W/m/K, Cp=526.3 J/kg/K, rho=4.43 g/cc
$$ Converted: TC=6.7000e+00 mW/mm/K, Cp=5.2630e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti6Al4V_Grade5 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120564 4.430e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.263e+08 6.700e+00
$
$$ CTE=8.6 ppm/K, applied to all 4 MIDs of Ti6Al4V_Grade5
$$   bi_iso=100564, multi_iso=110564, kin_pure=130564, kin_mixed=140564
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti6Al4V_Grade5 bi_iso -- PID slot holds MID=100564
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100564         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5 multi_iso -- PID slot holds MID=110564
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110564         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5 kin_pure -- PID slot holds MID=130564
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130564         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5 kin_mixed -- PID slot holds MID=140564
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140564         0 8.600e-06
$
$$ --- Ti6Al4V_Grade5_ELI Thermal (TMID 120565) ---
$$ TC=6.7 W/m/K, Cp=526.3 J/kg/K, rho=4.43 g/cc
$$ Converted: TC=6.7000e+00 mW/mm/K, Cp=5.2630e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti6Al4V_Grade5_ELI Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120565 4.430e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.263e+08 6.700e+00
$
$$ CTE=8.6 ppm/K, applied to all 4 MIDs of Ti6Al4V_Grade5_ELI
$$   bi_iso=100565, multi_iso=110565, kin_pure=130565, kin_mixed=140565
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti6Al4V_Grade5_ELI bi_iso -- PID slot holds MID=100565
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100565         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5_ELI multi_iso -- PID slot holds MID=110565
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110565         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5_ELI kin_pure -- PID slot holds MID=130565
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130565         0 8.600e-06
$$ [DB] Ti6Al4V_Grade5_ELI kin_mixed -- PID slot holds MID=140565
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140565         0 8.600e-06
$
$$ --- Ti3Al2.5V_Grade9 Thermal (TMID 120566) ---
$$ TC=8.3 W/m/K, Cp=540.0 J/kg/K, rho=4.48 g/cc
$$ Converted: TC=8.3000e+00 mW/mm/K, Cp=5.4000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Ti3Al2.5V_Grade9 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120566 4.480e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 5.400e+08 8.300e+00
$
$$ CTE=9.4 ppm/K, applied to all 4 MIDs of Ti3Al2.5V_Grade9
$$   bi_iso=100566, multi_iso=110566, kin_pure=130566, kin_mixed=140566
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Ti3Al2.5V_Grade9 bi_iso -- PID slot holds MID=100566
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100566         0 9.400e-06
$$ [DB] Ti3Al2.5V_Grade9 multi_iso -- PID slot holds MID=110566
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110566         0 9.400e-06
$$ [DB] Ti3Al2.5V_Grade9 kin_pure -- PID slot holds MID=130566
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130566         0 9.400e-06
$$ [DB] Ti3Al2.5V_Grade9 kin_mixed -- PID slot holds MID=140566
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140566         0 9.400e-06
$
$ ========================================================================
$ Mg THERMAL
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 Thermal (TMID 120581) ---
$$ TC=96.0 W/m/K, Cp=1024.0 J/kg/K, rho=1.77 g/cc
$$ Converted: TC=9.6000e+01 mW/mm/K, Cp=1.0240e+09 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Mg_AZ31B_H24 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120581 1.770e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.024e+09 9.600e+01
$
$$ CTE=26.0 ppm/K, applied to all 4 MIDs of Mg_AZ31B_H24
$$   bi_iso=100581, multi_iso=110581, kin_pure=130581, kin_mixed=140581
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Mg_AZ31B_H24 bi_iso -- PID slot holds MID=100581
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100581         0 2.600e-05
$$ [DB] Mg_AZ31B_H24 multi_iso -- PID slot holds MID=110581
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110581         0 2.600e-05
$$ [DB] Mg_AZ31B_H24 kin_pure -- PID slot holds MID=130581
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130581         0 2.600e-05
$$ [DB] Mg_AZ31B_H24 kin_mixed -- PID slot holds MID=140581
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140581         0 2.600e-05
$
$$ --- Mg_AZ91D_diecast Thermal (TMID 120582) ---
$$ TC=72.0 W/m/K, Cp=1020.0 J/kg/K, rho=1.81 g/cc
$$ Converted: TC=7.2000e+01 mW/mm/K, Cp=1.0200e+09 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Mg_AZ91D_diecast Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120582 1.810e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.020e+09 7.200e+01
$
$$ CTE=26.0 ppm/K, applied to all 4 MIDs of Mg_AZ91D_diecast
$$   bi_iso=100582, multi_iso=110582, kin_pure=130582, kin_mixed=140582
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Mg_AZ91D_diecast bi_iso -- PID slot holds MID=100582
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100582         0 2.600e-05
$$ [DB] Mg_AZ91D_diecast multi_iso -- PID slot holds MID=110582
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110582         0 2.600e-05
$$ [DB] Mg_AZ91D_diecast kin_pure -- PID slot holds MID=130582
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130582         0 2.600e-05
$$ [DB] Mg_AZ91D_diecast kin_mixed -- PID slot holds MID=140582
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140582         0 2.600e-05
$
$$ --- Mg_ZK60A_T5 Thermal (TMID 120583) ---
$$ TC=117.0 W/m/K, Cp=1004.0 J/kg/K, rho=1.83 g/cc
$$ Converted: TC=1.1700e+02 mW/mm/K, Cp=1.0040e+09 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Mg_ZK60A_T5 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120583 1.830e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 1.004e+09 1.170e+02
$
$$ CTE=26.0 ppm/K, applied to all 4 MIDs of Mg_ZK60A_T5
$$   bi_iso=100583, multi_iso=110583, kin_pure=130583, kin_mixed=140583
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Mg_ZK60A_T5 bi_iso -- PID slot holds MID=100583
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100583         0 2.600e-05
$$ [DB] Mg_ZK60A_T5 multi_iso -- PID slot holds MID=110583
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110583         0 2.600e-05
$$ [DB] Mg_ZK60A_T5 kin_pure -- PID slot holds MID=130583
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130583         0 2.600e-05
$$ [DB] Mg_ZK60A_T5 kin_mixed -- PID slot holds MID=140583
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140583         0 2.600e-05
$
$ ========================================================================
$ Steel THERMAL
$ ========================================================================
$
$$ --- SPCC_mild_steel Thermal (TMID 120591) ---
$$ TC=52.0 W/m/K, Cp=465.0 J/kg/K, rho=7.85 g/cc
$$ Converted: TC=5.2000e+01 mW/mm/K, Cp=4.6500e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SPCC_mild_steel Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120591 7.850e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.650e+08 5.200e+01
$
$$ CTE=12.0 ppm/K, applied to all 4 MIDs of SPCC_mild_steel
$$   bi_iso=100591, multi_iso=110591, kin_pure=130591, kin_mixed=140591
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SPCC_mild_steel bi_iso -- PID slot holds MID=100591
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100591         0 1.200e-05
$$ [DB] SPCC_mild_steel multi_iso -- PID slot holds MID=110591
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110591         0 1.200e-05
$$ [DB] SPCC_mild_steel kin_pure -- PID slot holds MID=130591
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130591         0 1.200e-05
$$ [DB] SPCC_mild_steel kin_mixed -- PID slot holds MID=140591
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140591         0 1.200e-05
$
$$ --- S45C_medium_carbon Thermal (TMID 120592) ---
$$ TC=49.8 W/m/K, Cp=486.0 J/kg/K, rho=7.85 g/cc
$$ Converted: TC=4.9800e+01 mW/mm/K, Cp=4.8600e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
S45C_medium_carbon Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120592 7.850e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.860e+08 4.980e+01
$
$$ CTE=11.0 ppm/K, applied to all 4 MIDs of S45C_medium_carbon
$$   bi_iso=100592, multi_iso=110592, kin_pure=130592, kin_mixed=140592
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] S45C_medium_carbon bi_iso -- PID slot holds MID=100592
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100592         0 1.100e-05
$$ [DB] S45C_medium_carbon multi_iso -- PID slot holds MID=110592
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110592         0 1.100e-05
$$ [DB] S45C_medium_carbon kin_pure -- PID slot holds MID=130592
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130592         0 1.100e-05
$$ [DB] S45C_medium_carbon kin_mixed -- PID slot holds MID=140592
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140592         0 1.100e-05
$
$$ --- SCM440_alloy_steel Thermal (TMID 120593) ---
$$ TC=42.6 W/m/K, Cp=477.0 J/kg/K, rho=7.85 g/cc
$$ Converted: TC=4.2600e+01 mW/mm/K, Cp=4.7700e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
SCM440_alloy_steel Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120593 7.850e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.770e+08 4.260e+01
$
$$ CTE=12.3 ppm/K, applied to all 4 MIDs of SCM440_alloy_steel
$$   bi_iso=100593, multi_iso=110593, kin_pure=130593, kin_mixed=140593
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] SCM440_alloy_steel bi_iso -- PID slot holds MID=100593
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100593         0 1.230e-05
$$ [DB] SCM440_alloy_steel multi_iso -- PID slot holds MID=110593
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110593         0 1.230e-05
$$ [DB] SCM440_alloy_steel kin_pure -- PID slot holds MID=130593
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130593         0 1.230e-05
$$ [DB] SCM440_alloy_steel kin_mixed -- PID slot holds MID=140593
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140593         0 1.230e-05
$
$ ========================================================================
$ Brass THERMAL
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass Thermal (TMID 120601) ---
$$ TC=120.0 W/m/K, Cp=375.0 J/kg/K, rho=8.53 g/cc
$$ Converted: TC=1.2000e+02 mW/mm/K, Cp=3.7500e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
C26000_Cartridge_Brass Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120601 8.530e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 3.750e+08 1.200e+02
$
$$ CTE=19.9 ppm/K, applied to all 4 MIDs of C26000_Cartridge_Brass
$$   bi_iso=100601, multi_iso=110601, kin_pure=130601, kin_mixed=140601
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] C26000_Cartridge_Brass bi_iso -- PID slot holds MID=100601
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100601         0 1.990e-05
$$ [DB] C26000_Cartridge_Brass multi_iso -- PID slot holds MID=110601
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110601         0 1.990e-05
$$ [DB] C26000_Cartridge_Brass kin_pure -- PID slot holds MID=130601
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130601         0 1.990e-05
$$ [DB] C26000_Cartridge_Brass kin_mixed -- PID slot holds MID=140601
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140601         0 1.990e-05
$
$$ --- C36000_FreeCutting_Brass Thermal (TMID 120602) ---
$$ TC=115.0 W/m/K, Cp=380.0 J/kg/K, rho=8.5 g/cc
$$ Converted: TC=1.1500e+02 mW/mm/K, Cp=3.8000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
C36000_FreeCutting_Brass Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120602 8.500e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 3.800e+08 1.150e+02
$
$$ CTE=20.5 ppm/K, applied to all 4 MIDs of C36000_FreeCutting_Brass
$$   bi_iso=100602, multi_iso=110602, kin_pure=130602, kin_mixed=140602
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] C36000_FreeCutting_Brass bi_iso -- PID slot holds MID=100602
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100602         0 2.050e-05
$$ [DB] C36000_FreeCutting_Brass multi_iso -- PID slot holds MID=110602
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110602         0 2.050e-05
$$ [DB] C36000_FreeCutting_Brass kin_pure -- PID slot holds MID=130602
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130602         0 2.050e-05
$$ [DB] C36000_FreeCutting_Brass kin_mixed -- PID slot holds MID=140602
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140602         0 2.050e-05
$
$$ --- C51000_Phosphor_Bronze Thermal (TMID 120603) ---
$$ TC=69.0 W/m/K, Cp=380.0 J/kg/K, rho=8.86 g/cc
$$ Converted: TC=6.9000e+01 mW/mm/K, Cp=3.8000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
C51000_Phosphor_Bronze Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120603 8.860e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 3.800e+08 6.900e+01
$
$$ CTE=17.8 ppm/K, applied to all 4 MIDs of C51000_Phosphor_Bronze
$$   bi_iso=100603, multi_iso=110603, kin_pure=130603, kin_mixed=140603
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] C51000_Phosphor_Bronze bi_iso -- PID slot holds MID=100603
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100603         0 1.780e-05
$$ [DB] C51000_Phosphor_Bronze multi_iso -- PID slot holds MID=110603
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110603         0 1.780e-05
$$ [DB] C51000_Phosphor_Bronze kin_pure -- PID slot holds MID=130603
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130603         0 1.780e-05
$$ [DB] C51000_Phosphor_Bronze kin_mixed -- PID slot holds MID=140603
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140603         0 1.780e-05
$
$ ========================================================================
$ Inconel THERMAL
$ ========================================================================
$
$$ --- Inconel_625_annealed Thermal (TMID 120611) ---
$$ TC=9.8 W/m/K, Cp=410.0 J/kg/K, rho=8.44 g/cc
$$ Converted: TC=9.8000e+00 mW/mm/K, Cp=4.1000e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Inconel_625_annealed Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120611 8.440e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.100e+08 9.800e+00
$
$$ CTE=12.8 ppm/K, applied to all 4 MIDs of Inconel_625_annealed
$$   bi_iso=100611, multi_iso=110611, kin_pure=130611, kin_mixed=140611
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Inconel_625_annealed bi_iso -- PID slot holds MID=100611
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100611         0 1.280e-05
$$ [DB] Inconel_625_annealed multi_iso -- PID slot holds MID=110611
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110611         0 1.280e-05
$$ [DB] Inconel_625_annealed kin_pure -- PID slot holds MID=130611
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130611         0 1.280e-05
$$ [DB] Inconel_625_annealed kin_mixed -- PID slot holds MID=140611
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140611         0 1.280e-05
$
$$ --- Inconel_718_aged Thermal (TMID 120612) ---
$$ TC=11.4 W/m/K, Cp=435.0 J/kg/K, rho=8.19 g/cc
$$ Converted: TC=1.1400e+01 mW/mm/K, Cp=4.3500e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Inconel_718_aged Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120612 8.190e-09         0    1.0000    0.0000    0.0000
$       HC         TC
 4.350e+08 1.140e+01
$
$$ CTE=13.0 ppm/K, applied to all 4 MIDs of Inconel_718_aged
$$   bi_iso=100612, multi_iso=110612, kin_pure=130612, kin_mixed=140612
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Inconel_718_aged bi_iso -- PID slot holds MID=100612
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100612         0 1.300e-05
$$ [DB] Inconel_718_aged multi_iso -- PID slot holds MID=110612
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110612         0 1.300e-05
$$ [DB] Inconel_718_aged kin_pure -- PID slot holds MID=130612
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130612         0 1.300e-05
$$ [DB] Inconel_718_aged kin_mixed -- PID slot holds MID=140612
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140612         0 1.300e-05
$
$ ========================================================================
$ Tungsten THERMAL
$ ========================================================================
$
$$ --- Tungsten_99pct Thermal (TMID 120621) ---
$$ TC=174.0 W/m/K, Cp=134.0 J/kg/K, rho=19.3 g/cc
$$ Converted: TC=1.7400e+02 mW/mm/K, Cp=1.3400e+08 mm^2/s^2/K
*MAT_THERMAL_ISOTROPIC_TITLE
Tungsten_99pct Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT      HLAT
    120621 1.930e-08         0    1.0000    0.0000    0.0000
$       HC         TC
 1.340e+08 1.740e+02
$
$$ CTE=4.5 ppm/K, applied to all 4 MIDs of Tungsten_99pct
$$   bi_iso=100621, multi_iso=110621, kin_pure=130621, kin_mixed=140621
$$ NOTE: The value in the PID field is the MATERIAL ID (MID).
$$ An external tool must replace this with actual PART IDs
$$ that reference each MID before running LS-DYNA.
$$ [DB] Tungsten_99pct bi_iso -- PID slot holds MID=100621
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    100621         0 4.500e-06
$$ [DB] Tungsten_99pct multi_iso -- PID slot holds MID=110621
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    110621         0 4.500e-06
$$ [DB] Tungsten_99pct kin_pure -- PID slot holds MID=130621
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    130621         0 4.500e-06
$$ [DB] Tungsten_99pct kin_mixed -- PID slot holds MID=140621
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    140621         0 4.500e-06
$
*END
