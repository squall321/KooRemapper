$ ========================================================================
$ PLASTIC — Standard: Mechanical (MAT_001/024/003/187)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Standard — PC, ABS, PC/ABS, PA6, PA66, PBT, POM, PP
$ MID: 100961~100968 (5 variants per material)
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
$   100961  110961  120961  130961  140961  PC_Makrolon            2.40     65    68
$   100962  110962  120962  130962  140962  ABS_Cycolac            2.30     42    45
$   100963  110963  120963  130963  140963  PC_ABS_Cycoloy         2.40     55    60
$   100964  110964  120964  130964  140964  PA6_Ultramid_B         3.00     90    95
$   100965  110965  120965  130965  140965  PA66_Zytel             3.00     80    85
$   100966  110966  120966  130966  140966  PBT_Crastin            2.60     60    65
$   100967  110967  120967  130967  140967  POM_Delrin             3.10     72    78
$   100968  110968  120968  130968  140968  PP_Homo                1.50     35    40
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- PC_Makrolon Linear (MID 100961) ---
$$ Polycarbonate (Makrolon 2405), transparent, cover glass
$$ Source: Covestro Makrolon 2405 TDS: E=2.4 GPa, sigy=65 MPa, ISO 527, eps_break=115%
$$ E=2.4 GPa, nu=0.37, rho=1.2 g/cc
*MAT_ELASTIC_TITLE
PC_Makrolon Linear
$      MID        RO         E        PR
    100961 1.200e-09    2400.0    0.3700       0.0       0.0       0.0
$
$$ --- ABS_Cycolac Linear (MID 100962) ---
$$ Acrylonitrile-Butadiene-Styrene, housings
$$ Source: SABIC Cycolac TDS, Louche 2009
$$ E=2.3 GPa, nu=0.38, rho=1.05 g/cc
*MAT_ELASTIC_TITLE
ABS_Cycolac Linear
$      MID        RO         E        PR
    100962 1.050e-09    2300.0    0.3800       0.0       0.0       0.0
$
$$ --- PC_ABS_Cycoloy Linear (MID 100963) ---
$$ PC/ABS blend (Cycoloy), smartphone midframe
$$ Source: SABIC Cycoloy C1200HF TDS
$$ E=2.4 GPa, nu=0.38, rho=1.14 g/cc
*MAT_ELASTIC_TITLE
PC_ABS_Cycoloy Linear
$      MID        RO         E        PR
    100963 1.140e-09    2400.0    0.3800       0.0       0.0       0.0
$
$$ --- PA6_Ultramid_B Linear (MID 100964) ---
$$ Nylon 6 (PA6) BASF Ultramid B27, connectors, gears (dry state)
$$ Source: BASF Ultramid B27 E 01 TDS: E=3.0 GPa, sigy=90 MPa (dry)
$$ E=3.0 GPa, nu=0.38, rho=1.14 g/cc
*MAT_ELASTIC_TITLE
PA6_Ultramid_B Linear
$      MID        RO         E        PR
    100964 1.140e-09    3000.0    0.3800       0.0       0.0       0.0
$
$$ --- PA66_Zytel Linear (MID 100965) ---
$$ Nylon 66 (Zytel 101), high-strength connectors
$$ Source: DuPont Zytel 101 TDS
$$ E=3.0 GPa, nu=0.38, rho=1.14 g/cc
*MAT_ELASTIC_TITLE
PA66_Zytel Linear
$      MID        RO         E        PR
    100965 1.140e-09    3000.0    0.3800       0.0       0.0       0.0
$
$$ --- PBT_Crastin Linear (MID 100966) ---
$$ Polybutylene Terephthalate, connectors, switches
$$ Source: DuPont Crastin S600F20 TDS
$$ E=2.6 GPa, nu=0.38, rho=1.31 g/cc
*MAT_ELASTIC_TITLE
PBT_Crastin Linear
$      MID        RO         E        PR
    100966 1.310e-09    2600.0    0.3800       0.0       0.0       0.0
$
$$ --- POM_Delrin Linear (MID 100967) ---
$$ Polyoxymethylene (Delrin), gears, slides
$$ Source: DuPont Delrin 500P TDS
$$ E=3.1 GPa, nu=0.35, rho=1.41 g/cc
*MAT_ELASTIC_TITLE
POM_Delrin Linear
$      MID        RO         E        PR
    100967 1.410e-09    3100.0    0.3500       0.0       0.0       0.0
$
$$ --- PP_Homo Linear (MID 100968) ---
$$ Homopolymer Polypropylene, low-cost housings
$$ Source: LyondellBasell Moplen TDS
$$ E=1.5 GPa, nu=0.42, rho=0.9 g/cc
*MAT_ELASTIC_TITLE
PP_Homo Linear
$      MID        RO         E        PR
    100968 9.000e-10    1500.0    0.4200       0.0       0.0       0.0
$
$ ========================================================================
$ 2. BILINEAR ISOTROPIC (MAT_024)
$ ========================================================================
$
$$ --- PC_Makrolon Bilinear Isotropic (MID 110961) ---
$$ Polycarbonate (Makrolon 2405), transparent, cover glass
$$ sigy=65.0, sigu=68.0, eps_f=1.15
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 2.7 MPa
$$ Cowper-Symonds: C=1.4, P=2.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PC_Makrolon Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110961 1.200e-09    2400.0    0.3700     65.00      2.67    1.1500      0.00
$        C         P      LCSS      LCSR        VP
       1.4       2.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- ABS_Cycolac Bilinear Isotropic (MID 110962) ---
$$ Acrylonitrile-Butadiene-Styrene, housings
$$ sigy=42.0, sigu=45.0, eps_f=0.25
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 12.9 MPa
$$ Cowper-Symonds: C=5.0, P=3.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
ABS_Cycolac Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110962 1.050e-09    2300.0    0.3800     42.00     12.95    0.2500      0.00
$        C         P      LCSS      LCSR        VP
       5.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PC_ABS_Cycoloy Bilinear Isotropic (MID 110963) ---
$$ PC/ABS blend (Cycoloy), smartphone midframe
$$ sigy=55.0, sigu=60.0, eps_f=0.5
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 10.5 MPa
$$ Cowper-Symonds: C=2.5, P=2.8
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PC_ABS_Cycoloy Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110963 1.140e-09    2400.0    0.3800     55.00     10.48    0.5000      0.00
$        C         P      LCSS      LCSR        VP
       2.5       2.8         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PA6_Ultramid_B Bilinear Isotropic (MID 110964) ---
$$ Nylon 6 (PA6) BASF Ultramid B27, connectors, gears (dry state)
$$ sigy=90.0, sigu=95.0, eps_f=0.15
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 41.7 MPa
$$ Cowper-Symonds: C=0.5, P=5.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA6_Ultramid_B Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110964 1.140e-09    3000.0    0.3800     90.00     41.67    0.1500      0.00
$        C         P      LCSS      LCSR        VP
       0.5       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PA66_Zytel Bilinear Isotropic (MID 110965) ---
$$ Nylon 66 (Zytel 101), high-strength connectors
$$ sigy=80.0, sigu=85.0, eps_f=0.6
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 8.7 MPa
$$ Cowper-Symonds: C=0.8, P=4.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_Zytel Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110965 1.140e-09    3000.0    0.3800     80.00      8.72    0.6000      0.00
$        C         P      LCSS      LCSR        VP
       0.8       4.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PBT_Crastin Bilinear Isotropic (MID 110966) ---
$$ Polybutylene Terephthalate, connectors, switches
$$ sigy=60.0, sigu=65.0, eps_f=0.25
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 22.0 MPa
$$ Cowper-Symonds: C=3.0, P=3.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PBT_Crastin Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110966 1.310e-09    2600.0    0.3800     60.00     22.03    0.2500      0.00
$        C         P      LCSS      LCSR        VP
       3.0       3.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- POM_Delrin Bilinear Isotropic (MID 110967) ---
$$ Polyoxymethylene (Delrin), gears, slides
$$ sigy=72.0, sigu=78.0, eps_f=0.3
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 21.7 MPa
$$ Cowper-Symonds: C=800.0, P=2.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
POM_Delrin Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110967 1.410e-09    3100.0    0.3500     72.00     21.68    0.3000      0.00
$        C         P      LCSS      LCSR        VP
     800.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PP_Homo Bilinear Isotropic (MID 110968) ---
$$ Homopolymer Polypropylene, low-cost housings
$$ sigy=35.0, sigu=40.0, eps_f=1.5
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 3.4 MPa
$$ Cowper-Symonds: C=3.0, P=3.5
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PP_Homo Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110968 9.000e-10    1500.0    0.4200     35.00      3.39    1.5000      0.00
$        C         P      LCSS      LCSR        VP
       3.0       3.5         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 3. MULTILINEAR ISOTROPIC (MAT_024 + LCSS)
$ ========================================================================
$
$$ --- PC_Makrolon Multilinear (MID 120961) ---
$$ LCSS curve: 9 points, LCID=120961
*DEFINE_CURVE_TITLE
PC_Makrolon true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120961         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.5000000000e+01
    5.0000000000e-03    6.6000000000e+01
    1.0000000000e-02    6.6500000000e+01
    2.0000000000e-02    6.5500000000e+01
    5.0000000000e-02    6.2000000000e+01
    1.0000000000e-01    6.0000000000e+01
    3.0000000000e-01    6.4000000000e+01
    6.0000000000e-01    6.8000000000e+01
    1.1500000000e+00    6.8000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PC_Makrolon Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120961 1.200e-09    2400.0    0.3700      0.00      0.00    1.1500      0.00
$        C         P      LCSS      LCSR        VP
       1.4       2.5    120961         0       1.0
$
$$ --- ABS_Cycolac Multilinear (MID 120962) ---
$$ LCSS curve: 7 points, LCID=120962
*DEFINE_CURVE_TITLE
ABS_Cycolac true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120962         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.2000000000e+01
    1.0000000000e-02    4.4000000000e+01
    2.0000000000e-02    4.5000000000e+01
    5.0000000000e-02    4.4000000000e+01
    1.0000000000e-01    4.3000000000e+01
    1.5000000000e-01    4.4000000000e+01
    2.5000000000e-01    4.5000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
ABS_Cycolac Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120962 1.050e-09    2300.0    0.3800      0.00      0.00    0.2500      0.00
$        C         P      LCSS      LCSR        VP
       5.0       3.0    120962         0       1.0
$
$$ --- PC_ABS_Cycoloy Multilinear (MID 120963) ---
$$ LCSS curve: 8 points, LCID=120963
*DEFINE_CURVE_TITLE
PC_ABS_Cycoloy true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120963         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    5.5000000000e+01
    1.0000000000e-02    5.7000000000e+01
    2.0000000000e-02    5.8000000000e+01
    4.0000000000e-02    5.7500000000e+01
    8.0000000000e-02    5.6000000000e+01
    1.5000000000e-01    5.5000000000e+01
    3.0000000000e-01    5.8000000000e+01
    5.0000000000e-01    6.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PC_ABS_Cycoloy Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120963 1.140e-09    2400.0    0.3800      0.00      0.00    0.5000      0.00
$        C         P      LCSS      LCSR        VP
       2.5       2.8    120963         0       1.0
$
$$ --- PA6_Ultramid_B Multilinear (MID 120964) ---
$$ LCSS curve: 7 points, LCID=120964
*DEFINE_CURVE_TITLE
PA6_Ultramid_B true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120964         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.0000000000e+01
    1.0000000000e-02    9.2000000000e+01
    2.0000000000e-02    9.3000000000e+01
    4.0000000000e-02    9.2000000000e+01
    6.0000000000e-02    9.1000000000e+01
    1.0000000000e-01    9.3000000000e+01
    1.5000000000e-01    9.5000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA6_Ultramid_B Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120964 1.140e-09    3000.0    0.3800      0.00      0.00    0.1500      0.00
$        C         P      LCSS      LCSR        VP
       0.5       5.0    120964         0       1.0
$
$$ --- PA66_Zytel Multilinear (MID 120965) ---
$$ LCSS curve: 7 points, LCID=120965
*DEFINE_CURVE_TITLE
PA66_Zytel true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120965         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.0000000000e+01
    1.0000000000e-02    8.2000000000e+01
    2.0000000000e-02    8.3000000000e+01
    5.0000000000e-02    8.2000000000e+01
    1.0000000000e-01    8.1000000000e+01
    3.0000000000e-01    8.3000000000e+01
    6.0000000000e-01    8.5000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PA66_Zytel Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120965 1.140e-09    3000.0    0.3800      0.00      0.00    0.6000      0.00
$        C         P      LCSS      LCSR        VP
       0.8       4.5    120965         0       1.0
$
$$ --- PBT_Crastin Multilinear (MID 120966) ---
$$ LCSS curve: 7 points, LCID=120966
*DEFINE_CURVE_TITLE
PBT_Crastin true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120966         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.0000000000e+01
    1.0000000000e-02    6.2000000000e+01
    2.0000000000e-02    6.3000000000e+01
    5.0000000000e-02    6.2000000000e+01
    1.0000000000e-01    6.1000000000e+01
    2.0000000000e-01    6.4000000000e+01
    2.5000000000e-01    6.5000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PBT_Crastin Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120966 1.310e-09    2600.0    0.3800      0.00      0.00    0.2500      0.00
$        C         P      LCSS      LCSR        VP
       3.0       3.5    120966         0       1.0
$
$$ --- POM_Delrin Multilinear (MID 120967) ---
$$ LCSS curve: 7 points, LCID=120967
*DEFINE_CURVE_TITLE
POM_Delrin true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120967         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.2000000000e+01
    1.0000000000e-02    7.4000000000e+01
    2.0000000000e-02    7.6000000000e+01
    5.0000000000e-02    7.5000000000e+01
    1.0000000000e-01    7.4000000000e+01
    2.0000000000e-01    7.6000000000e+01
    3.0000000000e-01    7.8000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
POM_Delrin Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120967 1.410e-09    3100.0    0.3500      0.00      0.00    0.3000      0.00
$        C         P      LCSS      LCSR        VP
     800.0       2.0    120967         0       1.0
$
$$ --- PP_Homo Multilinear (MID 120968) ---
$$ LCSS curve: 8 points, LCID=120968
*DEFINE_CURVE_TITLE
PP_Homo true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    120968         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.5000000000e+01
    1.0000000000e-02    3.6000000000e+01
    2.0000000000e-02    3.6500000000e+01
    5.0000000000e-02    3.5500000000e+01
    1.0000000000e-01    3.4000000000e+01
    3.0000000000e-01    3.5000000000e+01
    8.0000000000e-01    3.8000000000e+01
    1.5000000000e+00    4.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
PP_Homo Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    120968 9.000e-10    1500.0    0.4200      0.00      0.00    1.5000      0.00
$        C         P      LCSS      LCSR        VP
       3.0       3.5    120968         0       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$ ========================================================================
$
$$ --- PC_Makrolon Kinematic Mixed BETA=0.5 (MID 130961) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PC_Makrolon Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130961 1.200e-09    2400.0    0.3700     65.00      2.67    0.5000
$      SRC       SRP        FS        VP
       1.4       2.5    1.1500       1.0
$
$$ --- ABS_Cycolac Kinematic Mixed BETA=0.5 (MID 130962) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
ABS_Cycolac Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130962 1.050e-09    2300.0    0.3800     42.00     12.95    0.5000
$      SRC       SRP        FS        VP
       5.0       3.0    0.2500       1.0
$
$$ --- PC_ABS_Cycoloy Kinematic Mixed BETA=0.5 (MID 130963) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PC_ABS_Cycoloy Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130963 1.140e-09    2400.0    0.3800     55.00     10.48    0.5000
$      SRC       SRP        FS        VP
       2.5       2.8    0.5000       1.0
$
$$ --- PA6_Ultramid_B Kinematic Mixed BETA=0.5 (MID 130964) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PA6_Ultramid_B Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130964 1.140e-09    3000.0    0.3800     90.00     41.67    0.5000
$      SRC       SRP        FS        VP
       0.5       5.0    0.1500       1.0
$
$$ --- PA66_Zytel Kinematic Mixed BETA=0.5 (MID 130965) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PA66_Zytel Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130965 1.140e-09    3000.0    0.3800     80.00      8.72    0.5000
$      SRC       SRP        FS        VP
       0.8       4.5    0.6000       1.0
$
$$ --- PBT_Crastin Kinematic Mixed BETA=0.5 (MID 130966) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PBT_Crastin Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130966 1.310e-09    2600.0    0.3800     60.00     22.03    0.5000
$      SRC       SRP        FS        VP
       3.0       3.5    0.2500       1.0
$
$$ --- POM_Delrin Kinematic Mixed BETA=0.5 (MID 130967) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
POM_Delrin Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130967 1.410e-09    3100.0    0.3500     72.00     21.68    0.5000
$      SRC       SRP        FS        VP
     800.0       2.0    0.3000       1.0
$
$$ --- PP_Homo Kinematic Mixed BETA=0.5 (MID 130968) ---
$$ 50/50 isotropic/kinematic for cyclic loading
*MAT_PLASTIC_KINEMATIC_TITLE
PP_Homo Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130968 9.000e-10    1500.0    0.4200     35.00      3.39    0.5000
$      SRC       SRP        FS        VP
       3.0       3.5    1.5000       1.0
$
$ ========================================================================
$ 5. SAMP-1 ADVANCED POLYMER (MAT_187)
$ ========================================================================
$
$$ --- PC_Makrolon SAMP-1 Advanced (MID 140961) ---
$$ Polycarbonate (Makrolon 2405), transparent, cover glass
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PC_Makrolon SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140961         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.5000000000e+01
    5.0000000000e-03    6.6000000000e+01
    1.0000000000e-02    6.6500000000e+01
    2.0000000000e-02    6.5500000000e+01
    5.0000000000e-02    6.2000000000e+01
    1.0000000000e-01    6.0000000000e+01
    3.0000000000e-01    6.4000000000e+01
    6.0000000000e-01    6.8000000000e+01
    1.1500000000e+00    6.8000000000e+01
$
*DEFINE_CURVE_TITLE
PC_Makrolon SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640961         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.4750000000e+01
    5.0000000000e-03    7.5900000000e+01
    1.0000000000e-02    7.6475000000e+01
    2.0000000000e-02    7.5325000000e+01
    5.0000000000e-02    7.1300000000e+01
    1.0000000000e-01    6.9000000000e+01
    3.0000000000e-01    7.3600000000e+01
    6.0000000000e-01    7.8200000000e+01
    1.1500000000e+00    7.8200000000e+01
$
*MAT_SAMP-1_TITLE
PC_Makrolon SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140961 1.200e-09    2400.0    0.3700    140961    0.0000    640961         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    1.1500    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- ABS_Cycolac SAMP-1 Advanced (MID 140962) ---
$$ Acrylonitrile-Butadiene-Styrene, housings
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
ABS_Cycolac SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140962         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.2000000000e+01
    1.0000000000e-02    4.4000000000e+01
    2.0000000000e-02    4.5000000000e+01
    5.0000000000e-02    4.4000000000e+01
    1.0000000000e-01    4.3000000000e+01
    1.5000000000e-01    4.4000000000e+01
    2.5000000000e-01    4.5000000000e+01
$
*DEFINE_CURVE_TITLE
ABS_Cycolac SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640962         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.8300000000e+01
    1.0000000000e-02    5.0600000000e+01
    2.0000000000e-02    5.1750000000e+01
    5.0000000000e-02    5.0600000000e+01
    1.0000000000e-01    4.9450000000e+01
    1.5000000000e-01    5.0600000000e+01
    2.5000000000e-01    5.1750000000e+01
$
*MAT_SAMP-1_TITLE
ABS_Cycolac SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140962 1.050e-09    2300.0    0.3800    140962    0.0000    640962         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.2500    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PC_ABS_Cycoloy SAMP-1 Advanced (MID 140963) ---
$$ PC/ABS blend (Cycoloy), smartphone midframe
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PC_ABS_Cycoloy SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140963         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    5.5000000000e+01
    1.0000000000e-02    5.7000000000e+01
    2.0000000000e-02    5.8000000000e+01
    4.0000000000e-02    5.7500000000e+01
    8.0000000000e-02    5.6000000000e+01
    1.5000000000e-01    5.5000000000e+01
    3.0000000000e-01    5.8000000000e+01
    5.0000000000e-01    6.0000000000e+01
$
*DEFINE_CURVE_TITLE
PC_ABS_Cycoloy SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640963         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.3250000000e+01
    1.0000000000e-02    6.5550000000e+01
    2.0000000000e-02    6.6700000000e+01
    4.0000000000e-02    6.6125000000e+01
    8.0000000000e-02    6.4400000000e+01
    1.5000000000e-01    6.3250000000e+01
    3.0000000000e-01    6.6700000000e+01
    5.0000000000e-01    6.9000000000e+01
$
*MAT_SAMP-1_TITLE
PC_ABS_Cycoloy SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140963 1.140e-09    2400.0    0.3800    140963    0.0000    640963         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.5000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PA6_Ultramid_B SAMP-1 Advanced (MID 140964) ---
$$ Nylon 6 (PA6) BASF Ultramid B27, connectors, gears (dry state)
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PA6_Ultramid_B SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140964         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.0000000000e+01
    1.0000000000e-02    9.2000000000e+01
    2.0000000000e-02    9.3000000000e+01
    4.0000000000e-02    9.2000000000e+01
    6.0000000000e-02    9.1000000000e+01
    1.0000000000e-01    9.3000000000e+01
    1.5000000000e-01    9.5000000000e+01
$
*DEFINE_CURVE_TITLE
PA6_Ultramid_B SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640964         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.0350000000e+02
    1.0000000000e-02    1.0580000000e+02
    2.0000000000e-02    1.0695000000e+02
    4.0000000000e-02    1.0580000000e+02
    6.0000000000e-02    1.0465000000e+02
    1.0000000000e-01    1.0695000000e+02
    1.5000000000e-01    1.0925000000e+02
$
*MAT_SAMP-1_TITLE
PA6_Ultramid_B SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140964 1.140e-09    3000.0    0.3800    140964    0.0000    640964         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.1500    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PA66_Zytel SAMP-1 Advanced (MID 140965) ---
$$ Nylon 66 (Zytel 101), high-strength connectors
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PA66_Zytel SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140965         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.0000000000e+01
    1.0000000000e-02    8.2000000000e+01
    2.0000000000e-02    8.3000000000e+01
    5.0000000000e-02    8.2000000000e+01
    1.0000000000e-01    8.1000000000e+01
    3.0000000000e-01    8.3000000000e+01
    6.0000000000e-01    8.5000000000e+01
$
*DEFINE_CURVE_TITLE
PA66_Zytel SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640965         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    9.2000000000e+01
    1.0000000000e-02    9.4300000000e+01
    2.0000000000e-02    9.5450000000e+01
    5.0000000000e-02    9.4300000000e+01
    1.0000000000e-01    9.3150000000e+01
    3.0000000000e-01    9.5450000000e+01
    6.0000000000e-01    9.7750000000e+01
$
*MAT_SAMP-1_TITLE
PA66_Zytel SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140965 1.140e-09    3000.0    0.3800    140965    0.0000    640965         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.6000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PBT_Crastin SAMP-1 Advanced (MID 140966) ---
$$ Polybutylene Terephthalate, connectors, switches
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PBT_Crastin SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140966         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.0000000000e+01
    1.0000000000e-02    6.2000000000e+01
    2.0000000000e-02    6.3000000000e+01
    5.0000000000e-02    6.2000000000e+01
    1.0000000000e-01    6.1000000000e+01
    2.0000000000e-01    6.4000000000e+01
    2.5000000000e-01    6.5000000000e+01
$
*DEFINE_CURVE_TITLE
PBT_Crastin SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640966         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    6.9000000000e+01
    1.0000000000e-02    7.1300000000e+01
    2.0000000000e-02    7.2450000000e+01
    5.0000000000e-02    7.1300000000e+01
    1.0000000000e-01    7.0150000000e+01
    2.0000000000e-01    7.3600000000e+01
    2.5000000000e-01    7.4750000000e+01
$
*MAT_SAMP-1_TITLE
PBT_Crastin SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140966 1.310e-09    2600.0    0.3800    140966    0.0000    640966         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.2500    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- POM_Delrin SAMP-1 Advanced (MID 140967) ---
$$ Polyoxymethylene (Delrin), gears, slides
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
POM_Delrin SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140967         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.2000000000e+01
    1.0000000000e-02    7.4000000000e+01
    2.0000000000e-02    7.6000000000e+01
    5.0000000000e-02    7.5000000000e+01
    1.0000000000e-01    7.4000000000e+01
    2.0000000000e-01    7.6000000000e+01
    3.0000000000e-01    7.8000000000e+01
$
*DEFINE_CURVE_TITLE
POM_Delrin SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640967         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.2800000000e+01
    1.0000000000e-02    8.5100000000e+01
    2.0000000000e-02    8.7400000000e+01
    5.0000000000e-02    8.6250000000e+01
    1.0000000000e-01    8.5100000000e+01
    2.0000000000e-01    8.7400000000e+01
    3.0000000000e-01    8.9700000000e+01
$
*MAT_SAMP-1_TITLE
POM_Delrin SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140967 1.410e-09    3100.0    0.3500    140967    0.0000    640967         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    0.3000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
$$ --- PP_Homo SAMP-1 Advanced (MID 140968) ---
$$ Homopolymer Polypropylene, low-cost housings
$$ SAMP-1 polymer model with tension/compression asymmetry
$$ Note: simplified — uses same curve for T and C (refine with measured data)
*DEFINE_CURVE_TITLE
PP_Homo SAMP-1 tension true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    140968         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.5000000000e+01
    1.0000000000e-02    3.6000000000e+01
    2.0000000000e-02    3.6500000000e+01
    5.0000000000e-02    3.5500000000e+01
    1.0000000000e-01    3.4000000000e+01
    3.0000000000e-01    3.5000000000e+01
    8.0000000000e-01    3.8000000000e+01
    1.5000000000e+00    4.0000000000e+01
$
*DEFINE_CURVE_TITLE
PP_Homo SAMP-1 compression true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    640968         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.0250000000e+01
    1.0000000000e-02    4.1400000000e+01
    2.0000000000e-02    4.1975000000e+01
    5.0000000000e-02    4.0825000000e+01
    1.0000000000e-01    3.9100000000e+01
    3.0000000000e-01    4.0250000000e+01
    8.0000000000e-01    4.3700000000e+01
    1.5000000000e+00    4.6000000000e+01
$
*MAT_SAMP-1_TITLE
PP_Homo SAMP-1
$      MID        RO         E       NUE     LCIDT      NUEP     LCIDC     LCIDS
    140968 9.000e-10    1500.0    0.4200    140968    0.0000    640968         0
$    LCIDB      NUEB     LCEPS    EPFAIL    DEPRPT     LCIDD     LCIDP
         0    0.0000         0    1.5000    0.0000         0         0
$     FLAG     DRATE
         0    0.0000
$
*END
