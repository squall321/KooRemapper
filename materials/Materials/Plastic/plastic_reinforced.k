$ ========================================================================
$ PLASTIC — Reinforced: Mechanical (MAT_001/024/003/187)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Reinforced — PA66-GF30, PA66-GF50, PBT-GF30, PPS-GF40
$ MID: 100971~100974 (5 variants per material)
$
$ 5 mechanical variants per material:
$   1. Linear (MAT_001)          1009xx — preview
$   2. Bilinear iso (MAT_024)    1109xx — standard
$   3. Multilinear iso (LCSS)    1209xx — precise
$   4. Bilinear kin mixed (003)  1309xx — cyclic/Bauschinger
$   5. SAMP-1 (MAT_187)          1409xx — advanced polymer
$
$ Cowper-Symonds strain-rate per material (literature).
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin      bi       mu       kin      samp     Name                E(GPa)  sigy  sigu
$   ----------------------------------------------------------------------------------------
$   100971  110971  120971  130971  140971  PA66_GF30              9.50    180   195
$   100972  110972  120972  130972  140972  PA66_GF50             16.00    230   250
$   100973  110973  120973  130973  140973  PBT_GF30              10.00    130   145
$   100974  110974  120974  130974  140974  PPS_GF40              14.00    180   195
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- PA66_GF30 Linear (MID 100971) ---
$$ PA66 + 30% Glass Fiber, high-strength connectors
$$ Source: BASF Ultramid A3WG6 TDS, DuPont Zytel 70G30
$$ E=9.5 GPa, nu=0.37, rho=1.36 g/cc
*MAT_ELASTIC_TITLE
PA66_GF30 Linear
$      MID        RO         E        PR
    100971 1.360e-09    9500.0    0.3700       0.0       0.0       0.0
$
$$ --- PA66_GF50 Linear (MID 100972) ---
$$ PA66 + 50% Glass Fiber, structural parts
$$ Source: BASF Ultramid A3WG10 TDS
$$ E=16.0 GPa, nu=0.36, rho=1.57 g/cc
*MAT_ELASTIC_TITLE
PA66_GF50 Linear
$      MID        RO         E        PR
    100972 1.570e-09   16000.0    0.3600       0.0       0.0       0.0
$
$$ --- PBT_GF30 Linear (MID 100973) ---
$$ PBT + 30% GF, electrical parts
$$ Source: DuPont Crastin SK605 TDS
$$ E=10.0 GPa, nu=0.37, rho=1.53 g/cc
*MAT_ELASTIC_TITLE
PBT_GF30 Linear
$      MID        RO         E        PR
    100973 1.530e-09   10000.0    0.3700       0.0       0.0       0.0
$
$$ --- PPS_GF40 Linear (MID 100974) ---
$$ PPS + 40% GF, high-temperature structural
$$ Source: Solvay Ryton R-4-02XT TDS
$$ E=14.0 GPa, nu=0.38, rho=1.66 g/cc
*MAT_ELASTIC_TITLE
PPS_GF40 Linear
$      MID        RO         E        PR
    100974 1.660e-09   14000.0    0.3800       0.0       0.0       0.0
$
$ ========================================================================
$ 2. BILINEAR ISOTROPIC (MAT_024)
$ ========================================================================
$
$$ --- PA66_GF30 Bilinear Isotropic (MID 110971) ---
$$ PA66 + 30% Glass Fiber, high-strength connectors
$$ sigy=180.0, sigu=195.0, eps_f=0.04
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 712.5 MPa
$$ Cowper-Symonds: C=50.0, P=2.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_GF30 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110971 1.360e-09    9500.0    0.3700    180.00    712.50    0.0400      0.00
$        C         P      LCSS      LCSR        VP
      50.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PA66_GF50 Bilinear Isotropic (MID 110972) ---
$$ PA66 + 50% Glass Fiber, structural parts
$$ sigy=230.0, sigu=250.0, eps_f=0.025
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1882.4 MPa
$$ Cowper-Symonds: C=80.0, P=2.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_GF50 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110972 1.570e-09   16000.0    0.3600    230.00   1882.35    0.0250      0.00
$        C         P      LCSS      LCSR        VP
      80.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PBT_GF30 Bilinear Isotropic (MID 110973) ---
$$ PBT + 30% GF, electrical parts
$$ sigy=130.0, sigu=145.0, eps_f=0.03
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 882.4 MPa
$$ Cowper-Symonds: C=60.0, P=2.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PBT_GF30 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110973 1.530e-09   10000.0    0.3700    130.00    882.35    0.0300      0.00
$        C         P      LCSS      LCSR        VP
      60.0       2.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PPS_GF40 Bilinear Isotropic (MID 110974) ---
$$ PPS + 40% GF, high-temperature structural
$$ sigy=180.0, sigu=195.0, eps_f=0.02
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 2100.0 MPa
$$ Cowper-Symonds: C=150.0, P=2.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PPS_GF40 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110974 1.660e-09   14000.0    0.3800    180.00   2100.00    0.0200      0.00
$        C         P      LCSS      LCSR        VP
     150.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 3. MULTILINEAR ISOTROPIC (MAT_024 + LCSS)
$ ========================================================================
$
$$ --- PA66_GF30 Multilinear (MID 120971) ---
$$ LCSS curve: 6 points, LCID=120971
*DEFINE_CURVE_TITLE
PA66_GF30 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120971         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.8000000000e+02
    5.0000000000e-03    1.8500000000e+02
    1.0000000000e-02    1.9000000000e+02
    2.0000000000e-02    1.9300000000e+02
    3.0000000000e-02    1.9400000000e+02
    4.0000000000e-02    1.9500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_GF30 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120971 1.360e-09    9500.0    0.3700      0.00      0.00    0.0400      0.00
$        C         P      LCSS      LCSR        VP
      50.0       2.0    120971         0       1.0
$
$$ --- PA66_GF50 Multilinear (MID 120972) ---
$$ LCSS curve: 6 points, LCID=120972
*DEFINE_CURVE_TITLE
PA66_GF50 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120972         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.3000000000e+02
    3.0000000000e-03    2.3800000000e+02
    7.0000000000e-03    2.4400000000e+02
    1.2000000000e-02    2.4700000000e+02
    2.0000000000e-02    2.4900000000e+02
    2.5000000000e-02    2.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_GF50 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120972 1.570e-09   16000.0    0.3600      0.00      0.00    0.0250      0.00
$        C         P      LCSS      LCSR        VP
      80.0       2.0    120972         0       1.0
$
$$ --- PBT_GF30 Multilinear (MID 120973) ---
$$ LCSS curve: 6 points, LCID=120973
*DEFINE_CURVE_TITLE
PBT_GF30 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120973         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.3000000000e+02
    5.0000000000e-03    1.3600000000e+02
    1.0000000000e-02    1.4000000000e+02
    1.5000000000e-02    1.4200000000e+02
    2.0000000000e-02    1.4400000000e+02
    3.0000000000e-02    1.4500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PBT_GF30 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120973 1.530e-09   10000.0    0.3700      0.00      0.00    0.0300      0.00
$        C         P      LCSS      LCSR        VP
      60.0       2.5    120973         0       1.0
$
$$ --- PPS_GF40 Multilinear (MID 120974) ---
$$ LCSS curve: 6 points, LCID=120974
*DEFINE_CURVE_TITLE
PPS_GF40 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120974         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.8000000000e+02
    4.0000000000e-03    1.8600000000e+02
    8.0000000000e-03    1.9000000000e+02
    1.2000000000e-02    1.9200000000e+02
    1.6000000000e-02    1.9400000000e+02
    2.0000000000e-02    1.9500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PPS_GF40 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120974 1.660e-09   14000.0    0.3800      0.00      0.00    0.0200      0.00
$        C         P      LCSS      LCSR        VP
     150.0       2.0    120974         0       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$ ========================================================================
$
$$ --- PA66_GF30 Kinematic Mixed BETA=0.5 (MID 130971) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PA66_GF30 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130971 1.360e-09    9500.0    0.3700    180.00    712.50    0.5000
$      SRC       SRP        FS        VP
      50.0       2.0    0.0400       1.0
$
$$ --- PA66_GF50 Kinematic Mixed BETA=0.5 (MID 130972) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PA66_GF50 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130972 1.570e-09   16000.0    0.3600    230.00   1882.35    0.5000
$      SRC       SRP        FS        VP
      80.0       2.0    0.0250       1.0
$
$$ --- PBT_GF30 Kinematic Mixed BETA=0.5 (MID 130973) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PBT_GF30 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130973 1.530e-09   10000.0    0.3700    130.00    882.35    0.5000
$      SRC       SRP        FS        VP
      60.0       2.5    0.0300       1.0
$
$$ --- PPS_GF40 Kinematic Mixed BETA=0.5 (MID 130974) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PPS_GF40 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130974 1.660e-09   14000.0    0.3800    180.00   2100.00    0.5000
$      SRC       SRP        FS        VP
     150.0       2.0    0.0200       1.0
$
$ ========================================================================
$ 5. SAMP-1 ADVANCED POLYMER (MAT_187)
$ ========================================================================
$
$$ --- PA66_GF30 SAMP-1 Advanced (MID 140971) ---
$$ PA66 + 30% Glass Fiber, high-strength connectors
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PA66_GF30 SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140971         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.8000000000e+02
    5.0000000000e-03    1.8500000000e+02
    1.0000000000e-02    1.9000000000e+02
    2.0000000000e-02    1.9300000000e+02
    3.0000000000e-02    1.9400000000e+02
    4.0000000000e-02    1.9500000000e+02
$
*DEFINE_CURVE_TITLE
PA66_GF30 SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640971         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.0700000000e+02
    5.0000000000e-03    2.1275000000e+02
    1.0000000000e-02    2.1850000000e+02
    2.0000000000e-02    2.2195000000e+02
    3.0000000000e-02    2.2310000000e+02
    4.0000000000e-02    2.2425000000e+02
$
*MAT_SAMP-1_TITLE
PA66_GF30 SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140971 1.360e-09    9500.0    0.3700    140971    0.0000    640971         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0400    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PA66_GF50 SAMP-1 Advanced (MID 140972) ---
$$ PA66 + 50% Glass Fiber, structural parts
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PA66_GF50 SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140972         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.3000000000e+02
    3.0000000000e-03    2.3800000000e+02
    7.0000000000e-03    2.4400000000e+02
    1.2000000000e-02    2.4700000000e+02
    2.0000000000e-02    2.4900000000e+02
    2.5000000000e-02    2.5000000000e+02
$
*DEFINE_CURVE_TITLE
PA66_GF50 SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640972         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.6450000000e+02
    3.0000000000e-03    2.7370000000e+02
    7.0000000000e-03    2.8060000000e+02
    1.2000000000e-02    2.8405000000e+02
    2.0000000000e-02    2.8635000000e+02
    2.5000000000e-02    2.8750000000e+02
$
*MAT_SAMP-1_TITLE
PA66_GF50 SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140972 1.570e-09   16000.0    0.3600    140972    0.0000    640972         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0250    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PBT_GF30 SAMP-1 Advanced (MID 140973) ---
$$ PBT + 30% GF, electrical parts
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PBT_GF30 SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140973         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.3000000000e+02
    5.0000000000e-03    1.3600000000e+02
    1.0000000000e-02    1.4000000000e+02
    1.5000000000e-02    1.4200000000e+02
    2.0000000000e-02    1.4400000000e+02
    3.0000000000e-02    1.4500000000e+02
$
*DEFINE_CURVE_TITLE
PBT_GF30 SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640973         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.4950000000e+02
    5.0000000000e-03    1.5640000000e+02
    1.0000000000e-02    1.6100000000e+02
    1.5000000000e-02    1.6330000000e+02
    2.0000000000e-02    1.6560000000e+02
    3.0000000000e-02    1.6675000000e+02
$
*MAT_SAMP-1_TITLE
PBT_GF30 SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140973 1.530e-09   10000.0    0.3700    140973    0.0000    640973         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0300    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PPS_GF40 SAMP-1 Advanced (MID 140974) ---
$$ PPS + 40% GF, high-temperature structural
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PPS_GF40 SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140974         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.8000000000e+02
    4.0000000000e-03    1.8600000000e+02
    8.0000000000e-03    1.9000000000e+02
    1.2000000000e-02    1.9200000000e+02
    1.6000000000e-02    1.9400000000e+02
    2.0000000000e-02    1.9500000000e+02
$
*DEFINE_CURVE_TITLE
PPS_GF40 SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640974         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.0700000000e+02
    4.0000000000e-03    2.1390000000e+02
    8.0000000000e-03    2.1850000000e+02
    1.2000000000e-02    2.2080000000e+02
    1.6000000000e-02    2.2310000000e+02
    2.0000000000e-02    2.2425000000e+02
$
*MAT_SAMP-1_TITLE
PPS_GF40 SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140974 1.660e-09   14000.0    0.3800    140974    0.0000    640974         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0200    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
*END
