$ ========================================================================
$ PLASTIC — High-Performance: Mechanical (MAT_001/024/003/187)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: High-Performance — PPS, PEEK, PEI
$ MID: 100975~100977 (5 variants per material)
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
$   100975  110975  120975  130975  140975  PPS_Ryton              3.80     80    90
$   100976  110976  120976  130976  140976  PEEK_Victrex           4.00     98   115
$   100977  110977  120977  130977  140977  PEI_Ultem              3.00    105   110
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- PPS_Ryton Linear (MID 100975) ---
$$ Polyphenylene Sulfide (Ryton), high-temp base resin
$$ Source: Solvay Ryton PR06 TDS
$$ E=3.8 GPa, nu=0.38, rho=1.35 g/cc
*MAT_ELASTIC_TITLE
PPS_Ryton Linear
$      MID        RO         E        PR
    100975 1.350e-09    3800.0    0.3800       0.0       0.0       0.0
$
$$ --- PEEK_Victrex Linear (MID 100976) ---
$$ Polyetheretherketone (PEEK), medical, aerospace
$$ Source: Victrex PEEK 450G TDS: E=4.0 GPa, sigy=98 MPa, ISO 527
$$ E=4.0 GPa, nu=0.39, rho=1.32 g/cc
*MAT_ELASTIC_TITLE
PEEK_Victrex Linear
$      MID        RO         E        PR
    100976 1.320e-09    4000.0    0.3900       0.0       0.0       0.0
$
$$ --- PEI_Ultem Linear (MID 100977) ---
$$ Polyetherimide (Ultem 1000), high-temp electrical
$$ Source: SABIC Ultem 1000 TDS
$$ E=3.0 GPa, nu=0.36, rho=1.27 g/cc
*MAT_ELASTIC_TITLE
PEI_Ultem Linear
$      MID        RO         E        PR
    100977 1.270e-09    3000.0    0.3600       0.0       0.0       0.0
$
$ ========================================================================
$ 2. BILINEAR ISOTROPIC (MAT_024)
$ ========================================================================
$
$$ --- PPS_Ryton Bilinear Isotropic (MID 110975) ---
$$ Polyphenylene Sulfide (Ryton), high-temp base resin
$$ sigy=80.0, sigu=90.0, eps_f=0.02
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 10000000.0 MPa
$$ Cowper-Symonds: C=100.0, P=2.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PPS_Ryton Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110975 1.350e-09    3800.0    0.3800     80.0010000000.00    0.0200      0.00
$        C         P      LCSS      LCSR        VP
     100.0       2.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PEEK_Victrex Bilinear Isotropic (MID 110976) ---
$$ Polyetheretherketone (PEEK), medical, aerospace
$$ sigy=98.0, sigu=115.0, eps_f=0.5
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 35.8 MPa
$$ Cowper-Symonds: C=40.0, P=2.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PEEK_Victrex Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110976 1.320e-09    4000.0    0.3900     98.00     35.75    0.5000      0.00
$        C         P      LCSS      LCSR        VP
      40.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PEI_Ultem Bilinear Isotropic (MID 110977) ---
$$ Polyetherimide (Ultem 1000), high-temp electrical
$$ sigy=105.0, sigu=110.0, eps_f=0.6
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 8.8 MPa
$$ Cowper-Symonds: C=50.0, P=2.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PEI_Ultem Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110977 1.270e-09    3000.0    0.3600    105.00      8.85    0.6000      0.00
$        C         P      LCSS      LCSR        VP
      50.0       2.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 3. MULTILINEAR ISOTROPIC (MAT_024 + LCSS)
$ ========================================================================
$
$$ --- PPS_Ryton Multilinear (MID 120975) ---
$$ LCSS curve: 5 points, LCID=120975
*DEFINE_CURVE_TITLE
PPS_Ryton true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120975         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.0000000000e+01
    5.0000000000e-03    8.4000000000e+01
    1.0000000000e-02    8.7000000000e+01
    1.5000000000e-02    8.9000000000e+01
    2.0000000000e-02    9.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PPS_Ryton Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120975 1.350e-09    3800.0    0.3800      0.00      0.00    0.0200      0.00
$        C         P      LCSS      LCSR        VP
     100.0       2.5    120975         0       1.0
$
$$ --- PEEK_Victrex Multilinear (MID 120976) ---
$$ LCSS curve: 8 points, LCID=120976
*DEFINE_CURVE_TITLE
PEEK_Victrex true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120976         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.8000000000e+01
    5.0000000000e-03    1.0300000000e+02
    1.0000000000e-02    1.0600000000e+02
    2.0000000000e-02    1.0900000000e+02
    5.0000000000e-02    1.0800000000e+02
    1.0000000000e-01    1.0700000000e+02
    3.0000000000e-01    1.1200000000e+02
    5.0000000000e-01    1.1500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PEEK_Victrex Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120976 1.320e-09    4000.0    0.3900      0.00      0.00    0.5000      0.00
$        C         P      LCSS      LCSR        VP
      40.0       2.0    120976         0       1.0
$
$$ --- PEI_Ultem Multilinear (MID 120977) ---
$$ LCSS curve: 8 points, LCID=120977
*DEFINE_CURVE_TITLE
PEI_Ultem true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120977         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.0500000000e+02
    5.0000000000e-03    1.0700000000e+02
    1.0000000000e-02    1.0900000000e+02
    2.0000000000e-02    1.1000000000e+02
    5.0000000000e-02    1.0900000000e+02
    1.0000000000e-01    1.0800000000e+02
    3.0000000000e-01    1.0900000000e+02
    6.0000000000e-01    1.1000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PEI_Ultem Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120977 1.270e-09    3000.0    0.3600      0.00      0.00    0.6000      0.00
$        C         P      LCSS      LCSR        VP
      50.0       2.5    120977         0       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$ ========================================================================
$
$$ --- PPS_Ryton Kinematic Mixed BETA=0.5 (MID 130975) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PPS_Ryton Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130975 1.350e-09    3800.0    0.3800     80.0010000000.00    0.5000
$      SRC       SRP        FS        VP
     100.0       2.5    0.0200       1.0
$
$$ --- PEEK_Victrex Kinematic Mixed BETA=0.5 (MID 130976) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PEEK_Victrex Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130976 1.320e-09    4000.0    0.3900     98.00     35.75    0.5000
$      SRC       SRP        FS        VP
      40.0       2.0    0.5000       1.0
$
$$ --- PEI_Ultem Kinematic Mixed BETA=0.5 (MID 130977) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PEI_Ultem Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130977 1.270e-09    3000.0    0.3600    105.00      8.85    0.5000
$      SRC       SRP        FS        VP
      50.0       2.5    0.6000       1.0
$
$ ========================================================================
$ 5. SAMP-1 ADVANCED POLYMER (MAT_187)
$ ========================================================================
$
$$ --- PPS_Ryton SAMP-1 Advanced (MID 140975) ---
$$ Polyphenylene Sulfide (Ryton), high-temp base resin
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PPS_Ryton SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140975         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.0000000000e+01
    5.0000000000e-03    8.4000000000e+01
    1.0000000000e-02    8.7000000000e+01
    1.5000000000e-02    8.9000000000e+01
    2.0000000000e-02    9.0000000000e+01
$
*DEFINE_CURVE_TITLE
PPS_Ryton SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640975         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.2000000000e+01
    5.0000000000e-03    9.6600000000e+01
    1.0000000000e-02    1.0005000000e+02
    1.5000000000e-02    1.0235000000e+02
    2.0000000000e-02    1.0350000000e+02
$
*MAT_SAMP-1_TITLE
PPS_Ryton SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140975 1.350e-09    3800.0    0.3800    140975    0.0000    640975         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.0200    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PEEK_Victrex SAMP-1 Advanced (MID 140976) ---
$$ Polyetheretherketone (PEEK), medical, aerospace
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PEEK_Victrex SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140976         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.8000000000e+01
    5.0000000000e-03    1.0300000000e+02
    1.0000000000e-02    1.0600000000e+02
    2.0000000000e-02    1.0900000000e+02
    5.0000000000e-02    1.0800000000e+02
    1.0000000000e-01    1.0700000000e+02
    3.0000000000e-01    1.1200000000e+02
    5.0000000000e-01    1.1500000000e+02
$
*DEFINE_CURVE_TITLE
PEEK_Victrex SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640976         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.1270000000e+02
    5.0000000000e-03    1.1845000000e+02
    1.0000000000e-02    1.2190000000e+02
    2.0000000000e-02    1.2535000000e+02
    5.0000000000e-02    1.2420000000e+02
    1.0000000000e-01    1.2305000000e+02
    3.0000000000e-01    1.2880000000e+02
    5.0000000000e-01    1.3225000000e+02
$
*MAT_SAMP-1_TITLE
PEEK_Victrex SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140976 1.320e-09    4000.0    0.3900    140976    0.0000    640976         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.5000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PEI_Ultem SAMP-1 Advanced (MID 140977) ---
$$ Polyetherimide (Ultem 1000), high-temp electrical
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PEI_Ultem SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140977         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.0500000000e+02
    5.0000000000e-03    1.0700000000e+02
    1.0000000000e-02    1.0900000000e+02
    2.0000000000e-02    1.1000000000e+02
    5.0000000000e-02    1.0900000000e+02
    1.0000000000e-01    1.0800000000e+02
    3.0000000000e-01    1.0900000000e+02
    6.0000000000e-01    1.1000000000e+02
$
*DEFINE_CURVE_TITLE
PEI_Ultem SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640977         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.2075000000e+02
    5.0000000000e-03    1.2305000000e+02
    1.0000000000e-02    1.2535000000e+02
    2.0000000000e-02    1.2650000000e+02
    5.0000000000e-02    1.2535000000e+02
    1.0000000000e-01    1.2420000000e+02
    3.0000000000e-01    1.2535000000e+02
    6.0000000000e-01    1.2650000000e+02
$
*MAT_SAMP-1_TITLE
PEI_Ultem SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140977 1.270e-09    3000.0    0.3600    140977    0.0000    640977         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.6000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
*END
