$ ========================================================================
$ MG METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: MG — Magnesium Alloys (smartphone frames)
$ MID: 100581~100590 (bi), 110581~110590 (multi)
$ Model: *MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024)
$
$ Hybrid strategy:
$   Bilinear    MID 1005xx (fast, SIGY+ETAN)
$   Multilinear MID 1105xx (precise, LCSS=MID)
$
$ Cowper-Symonds strain-rate (Jones, Structural Impact):
$   Aluminum: C=6500  P=4
$   Stainless:C=100   P=10
$   Titanium: C=120   P=9
$
$ Thermal properties (TC, Cp, CTE) in metal_thermal.k
$ ========================================================================
$
$ 4 hardening variants per material:
$   1. Bilinear isotropic  (MAT_024, SIGY+ETAN)            1005xx
$   2. Multilinear isotropic (MAT_024 + LCSS curve)         1105xx
$   3. Bilinear kinematic pure  (MAT_003, BETA=0.0)         1305xx
$   4. Bilinear kinematic mixed (MAT_003, BETA=0.5)         1405xx
$
$ Use isotropic for monotonic drop impact,
$ kinematic/mixed for cyclic or reverse loading (Bauschinger effect).
$
$ SUMMARY TABLE
$
$   bi_iso  multi_iso  kin_pure  kin_mix   Name                    sigy   sigu
$   --------------------------------------------------------------------------------
$   100581  110581     130581    140581   Mg_AZ31B_H24              220    290
$   100582  110582     130582    140582   Mg_AZ91D_diecast          160    230
$   100583  110583     130583    140583   Mg_ZK60A_T5               255    325
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 Bilinear (MID 100581) ---
$$ Wrought Mg-Al-Zn, most common sheet grade (smartphone midframe)
$$ Temper: H24
$$ Source: ASTM B90 AZ31B-H24, ASM Handbook Vol 2
$$ rho=1.77 g/cc, E=45.0 GPa, nu=0.35
$$ sigy=220.0 MPa, sigu=290.0 MPa, eps_f=0.15
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 482.4 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_AZ31B_H24 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100581 1.770e-09   45000.0    0.3500    220.00    482.39    0.1500      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Mg_AZ91D_diecast Bilinear (MID 100582) ---
$$ Die-cast Mg-Al-Zn, laptop/phone housings
$$ Temper: As-cast
$$ Source: ASTM B94 AZ91D, NADCA standards
$$ rho=1.81 g/cc, E=45.0 GPa, nu=0.35
$$ sigy=160.0 MPa, sigu=230.0 MPa, eps_f=0.03
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 2647.1 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_AZ91D_diecast Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100582 1.810e-09   45000.0    0.3500    160.00   2647.06    0.0300      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Mg_ZK60A_T5 Bilinear (MID 100583) ---
$$ Extruded Mg-Zn-Zr high-strength (aerospace/bike frame)
$$ Temper: T5 (aged)
$$ Source: ASTM B107 ZK60A-T5
$$ rho=1.83 g/cc, E=45.0 GPa, nu=0.35
$$ sigy=255.0 MPa, sigu=325.0 MPa, eps_f=0.11
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 670.9 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_ZK60A_T5 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100583 1.830e-09   45000.0    0.3500    255.00    670.93    0.1100      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 Multilinear (MID 110581) ---
$$ Wrought Mg-Al-Zn, most common sheet grade (smartphone midframe)
$$ Temper: H24
$$ Source: ASTM B90 AZ31B-H24, ASM Handbook Vol 2
$$ LCSS curve: 6 points, LCID=110581
*DEFINE_CURVE_TITLE
Mg_AZ31B_H24 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110581         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.2000000000e+02
    1.0000000000e-02    2.4000000000e+02
    2.0000000000e-02    2.5500000000e+02
    5.0000000000e-02    2.7500000000e+02
    1.0000000000e-01    2.8500000000e+02
    1.5000000000e-01    2.9000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_AZ31B_H24 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110581 1.770e-09   45000.0    0.3500      0.00      0.00    0.1500      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0    110581         0       1.0
$
$$ --- Mg_AZ91D_diecast Multilinear (MID 110582) ---
$$ Die-cast Mg-Al-Zn, laptop/phone housings
$$ Temper: As-cast
$$ Source: ASTM B94 AZ91D, NADCA standards
$$ LCSS curve: 6 points, LCID=110582
*DEFINE_CURVE_TITLE
Mg_AZ91D_diecast true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110582         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.6000000000e+02
    5.0000000000e-03    1.8500000000e+02
    1.0000000000e-02    2.0000000000e+02
    1.5000000000e-02    2.1500000000e+02
    2.0000000000e-02    2.2300000000e+02
    3.0000000000e-02    2.3000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_AZ91D_diecast Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110582 1.810e-09   45000.0    0.3500      0.00      0.00    0.0300      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0    110582         0       1.0
$
$$ --- Mg_ZK60A_T5 Multilinear (MID 110583) ---
$$ Extruded Mg-Zn-Zr high-strength (aerospace/bike frame)
$$ Temper: T5 (aged)
$$ Source: ASTM B107 ZK60A-T5
$$ LCSS curve: 6 points, LCID=110583
*DEFINE_CURVE_TITLE
Mg_ZK60A_T5 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110583         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.5500000000e+02
    5.0000000000e-03    2.7500000000e+02
    1.0000000000e-02    2.9000000000e+02
    3.0000000000e-02    3.1000000000e+02
    6.0000000000e-02    3.2000000000e+02
    1.1000000000e-01    3.2500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mg_ZK60A_T5 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110583 1.830e-09   45000.0    0.3500      0.00      0.00    0.1100      0.00
$        C         P      LCSS      LCSR        VP
    4800.0       4.0    110583         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 Kinematic Pure (MID 130581) ---
$$ Wrought Mg-Al-Zn, most common sheet grade (smartphone midframe)
$$ Temper: H24
$$ Source: ASTM B90 AZ31B-H24, ASM Handbook Vol 2
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=220.0 MPa, ETAN=482.4 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_AZ31B_H24 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130581 1.770e-09   45000.0    0.3500    220.00    482.39    0.0000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.1500       1.0
$
$$ --- Mg_AZ91D_diecast Kinematic Pure (MID 130582) ---
$$ Die-cast Mg-Al-Zn, laptop/phone housings
$$ Temper: As-cast
$$ Source: ASTM B94 AZ91D, NADCA standards
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=160.0 MPa, ETAN=2647.1 MPa, eps_f=0.03
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_AZ91D_diecast Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130582 1.810e-09   45000.0    0.3500    160.00   2647.06    0.0000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.0300       1.0
$
$$ --- Mg_ZK60A_T5 Kinematic Pure (MID 130583) ---
$$ Extruded Mg-Zn-Zr high-strength (aerospace/bike frame)
$$ Temper: T5 (aged)
$$ Source: ASTM B107 ZK60A-T5
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=255.0 MPa, ETAN=670.9 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_ZK60A_T5 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130583 1.830e-09   45000.0    0.3500    255.00    670.93    0.0000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.1100       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 Kinematic Mixed (MID 140581) ---
$$ Wrought Mg-Al-Zn, most common sheet grade (smartphone midframe)
$$ Temper: H24
$$ Source: ASTM B90 AZ31B-H24, ASM Handbook Vol 2
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=220.0 MPa, ETAN=482.4 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_AZ31B_H24 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140581 1.770e-09   45000.0    0.3500    220.00    482.39    0.5000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.1500       1.0
$
$$ --- Mg_AZ91D_diecast Kinematic Mixed (MID 140582) ---
$$ Die-cast Mg-Al-Zn, laptop/phone housings
$$ Temper: As-cast
$$ Source: ASTM B94 AZ91D, NADCA standards
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=160.0 MPa, ETAN=2647.1 MPa, eps_f=0.03
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_AZ91D_diecast Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140582 1.810e-09   45000.0    0.3500    160.00   2647.06    0.5000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.0300       1.0
$
$$ --- Mg_ZK60A_T5 Kinematic Mixed (MID 140583) ---
$$ Extruded Mg-Zn-Zr high-strength (aerospace/bike frame)
$$ Temper: T5 (aged)
$$ Source: ASTM B107 ZK60A-T5
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=255.0 MPa, ETAN=670.9 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Mg_ZK60A_T5 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140583 1.830e-09   45000.0    0.3500    255.00    670.93    0.5000
$      SRC       SRP        FS        VP
    4800.0       4.0    0.1100       1.0
$
*END
