$ ========================================================================
$ PLASTIC — Optical: Mechanical (MAT_001/024/003/187)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Optical — PMMA, COP (Zeonex), COC (TOPAS) — camera lens
$ MID: 100981~100983 (5 variants per material)
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
$   100981  110981  120981  130981  140981  PMMA_Plexiglas         3.00     72    80
$   100982  110982  120982  130982  140982  COP_Zeonex             2.40     68    72
$   100983  110983  120983  130983  140983  COC_TOPAS              2.60     63    66
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- PMMA_Plexiglas Linear (MID 100981) ---
$$ Polymethyl Methacrylate (Plexiglas), transparent, cheap lens
$$ Source: Altuglas V825 TDS, Arkema Plexiglas V825-100
$$ E=3.0 GPa, nu=0.38, rho=1.19 g/cc
*MAT_ELASTIC_TITLE
PMMA_Plexiglas Linear
$      MID        RO         E        PR
    100981 1.190e-09    3000.0    0.3800       0.0       0.0       0.0
$
$$ --- COP_Zeonex Linear (MID 100982) ---
$$ Cyclic Olefin Polymer (Zeonex), smartphone camera lens (low birefringence)
$$ Source: Zeon Zeonex E48R TDS, Japan Zeon CL
$$ E=2.4 GPa, nu=0.37, rho=1.01 g/cc
*MAT_ELASTIC_TITLE
COP_Zeonex Linear
$      MID        RO         E        PR
    100982 1.010e-09    2400.0    0.3700       0.0       0.0       0.0
$
$$ --- COC_TOPAS Linear (MID 100983) ---
$$ Cyclic Olefin Copolymer (TOPAS), optical and medical
$$ Source: TOPAS 5013 TDS, Polyplastics TOPAS
$$ E=2.6 GPa, nu=0.37, rho=1.02 g/cc
*MAT_ELASTIC_TITLE
COC_TOPAS Linear
$      MID        RO         E        PR
    100983 1.020e-09    2600.0    0.3700       0.0       0.0       0.0
$
$ ========================================================================
$ 2. BILINEAR ISOTROPIC (MAT_024)
$ ========================================================================
$
$$ --- PMMA_Plexiglas Bilinear Isotropic (MID 110981) ---
$$ Polymethyl Methacrylate (Plexiglas), transparent, cheap lens
$$ sigy=72.0, sigu=80.0, eps_f=0.05
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 307.7 MPa
$$ Cowper-Symonds: C=50.0, P=3.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PMMA_Plexiglas Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110981 1.190e-09    3000.0    0.3800     72.00    307.69    0.0500      0.00
$        C         P      LCSS      LCSR        VP
      50.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- COP_Zeonex Bilinear Isotropic (MID 110982) ---
$$ Cyclic Olefin Polymer (Zeonex), smartphone camera lens (low birefringence)
$$ sigy=68.0, sigu=72.0, eps_f=0.1
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 55.8 MPa
$$ Cowper-Symonds: C=30.0, P=3.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
COP_Zeonex Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110982 1.010e-09    2400.0    0.3700     68.00     55.81    0.1000      0.00
$        C         P      LCSS      LCSR        VP
      30.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- COC_TOPAS Bilinear Isotropic (MID 110983) ---
$$ Cyclic Olefin Copolymer (TOPAS), optical and medical
$$ sigy=63.0, sigu=66.0, eps_f=0.04
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 190.2 MPa
$$ Cowper-Symonds: C=30.0, P=3.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
COC_TOPAS Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110983 1.020e-09    2600.0    0.3700     63.00    190.24    0.0400      0.00
$        C         P      LCSS      LCSR        VP
      30.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 3. MULTILINEAR ISOTROPIC (MAT_024 + LCSS)
$ ========================================================================
$
$$ --- PMMA_Plexiglas Multilinear (MID 120981) ---
$$ LCSS curve: 6 points, LCID=120981
*DEFINE_CURVE_TITLE
PMMA_Plexiglas true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120981         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.2000000000e+01
    5.0000000000e-03    7.5000000000e+01
    1.0000000000e-02    7.7000000000e+01
    2.0000000000e-02    7.9000000000e+01
    3.0000000000e-02    7.9500000000e+01
    5.0000000000e-02    8.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PMMA_Plexiglas Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120981 1.190e-09    3000.0    0.3800      0.00      0.00    0.0500      0.00
$        C         P      LCSS      LCSR        VP
      50.0       3.0    120981         0       1.0
$
$$ --- COP_Zeonex Multilinear (MID 120982) ---
$$ LCSS curve: 6 points, LCID=120982
*DEFINE_CURVE_TITLE
COP_Zeonex true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120982         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.8000000000e+01
    5.0000000000e-03    6.9500000000e+01
    1.0000000000e-02    7.0500000000e+01
    2.0000000000e-02    7.1500000000e+01
    5.0000000000e-02    7.2000000000e+01
    1.0000000000e-01    7.2000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
COP_Zeonex Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120982 1.010e-09    2400.0    0.3700      0.00      0.00    0.1000      0.00
$        C         P      LCSS      LCSR        VP
      30.0       3.0    120982         0       1.0
$
$$ --- COC_TOPAS Multilinear (MID 120983) ---
$$ LCSS curve: 6 points, LCID=120983
*DEFINE_CURVE_TITLE
COC_TOPAS true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120983         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.3000000000e+01
    5.0000000000e-03    6.4500000000e+01
    1.0000000000e-02    6.5500000000e+01
    2.0000000000e-02    6.6000000000e+01
    3.0000000000e-02    6.6000000000e+01
    4.0000000000e-02    6.6000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
COC_TOPAS Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120983 1.020e-09    2600.0    0.3700      0.00      0.00    0.0400      0.00
$        C         P      LCSS      LCSR        VP
      30.0       3.0    120983         0       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$ ========================================================================
$
$$ --- PMMA_Plexiglas Kinematic Mixed BETA=0.5 (MID 130981) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PMMA_Plexiglas Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130981 1.190e-09    3000.0    0.3800     72.00    307.69    0.5000
$      SRC       SRP        FS        VP
      50.0       3.0    0.0500       1.0
$
$$ --- COP_Zeonex Kinematic Mixed BETA=0.5 (MID 130982) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
COP_Zeonex Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130982 1.010e-09    2400.0    0.3700     68.00     55.81    0.5000
$      SRC       SRP        FS        VP
      30.0       3.0    0.1000       1.0
$
$$ --- COC_TOPAS Kinematic Mixed BETA=0.5 (MID 130983) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
COC_TOPAS Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130983 1.020e-09    2600.0    0.3700     63.00    190.24    0.5000
$      SRC       SRP        FS        VP
      30.0       3.0    0.0400       1.0
$
$ ========================================================================
$ 5. SAMP-1 ADVANCED POLYMER (MAT_187)
$ ========================================================================
$
$$ --- PMMA_Plexiglas SAMP-1 Advanced (MID 140981) ---
$$ Polymethyl Methacrylate (Plexiglas), transparent, cheap lens
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PMMA_Plexiglas SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140981         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.2000000000e+01
    5.0000000000e-03    7.5000000000e+01
    1.0000000000e-02    7.7000000000e+01
    2.0000000000e-02    7.9000000000e+01
    3.0000000000e-02    7.9500000000e+01
    5.0000000000e-02    8.0000000000e+01
$
*DEFINE_CURVE_TITLE
PMMA_Plexiglas SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640981         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.2800000000e+01
    5.0000000000e-03    8.6250000000e+01
    1.0000000000e-02    8.8550000000e+01
    2.0000000000e-02    9.0850000000e+01
    3.0000000000e-02    9.1425000000e+01
    5.0000000000e-02    9.2000000000e+01
$
*MAT_SAMP-1_TITLE
PMMA_Plexiglas SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140981 1.190e-09    3000.0    0.3800    140981    0.0000    640981         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0500    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- COP_Zeonex SAMP-1 Advanced (MID 140982) ---
$$ Cyclic Olefin Polymer (Zeonex), smartphone camera lens (low birefringence)
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
COP_Zeonex SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140982         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.8000000000e+01
    5.0000000000e-03    6.9500000000e+01
    1.0000000000e-02    7.0500000000e+01
    2.0000000000e-02    7.1500000000e+01
    5.0000000000e-02    7.2000000000e+01
    1.0000000000e-01    7.2000000000e+01
$
*DEFINE_CURVE_TITLE
COP_Zeonex SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640982         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.8200000000e+01
    5.0000000000e-03    7.9925000000e+01
    1.0000000000e-02    8.1075000000e+01
    2.0000000000e-02    8.2225000000e+01
    5.0000000000e-02    8.2800000000e+01
    1.0000000000e-01    8.2800000000e+01
$
*MAT_SAMP-1_TITLE
COP_Zeonex SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140982 1.010e-09    2400.0    0.3700    140982    0.0000    640982         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.1000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- COC_TOPAS SAMP-1 Advanced (MID 140983) ---
$$ Cyclic Olefin Copolymer (TOPAS), optical and medical
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
COC_TOPAS SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140983         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.3000000000e+01
    5.0000000000e-03    6.4500000000e+01
    1.0000000000e-02    6.5500000000e+01
    2.0000000000e-02    6.6000000000e+01
    3.0000000000e-02    6.6000000000e+01
    4.0000000000e-02    6.6000000000e+01
$
*DEFINE_CURVE_TITLE
COC_TOPAS SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640983         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.2450000000e+01
    5.0000000000e-03    7.4175000000e+01
    1.0000000000e-02    7.5325000000e+01
    2.0000000000e-02    7.5900000000e+01
    3.0000000000e-02    7.5900000000e+01
    4.0000000000e-02    7.5900000000e+01
$
*MAT_SAMP-1_TITLE
COC_TOPAS SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140983 1.020e-09    2600.0    0.3700    140983    0.0000    640983         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0400    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
*END
