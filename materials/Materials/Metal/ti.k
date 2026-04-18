$ ========================================================================
$ TI METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: TI — Titanium Alloys
$ MID: 100561~100580 (bi), 110561~110580 (multi)
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
$   100561  110561     130561    140561   Ti_Grade1                 170    240
$   100562  110562     130562    140562   Ti_Grade2                 275    345
$   100563  110563     130563    140563   Ti_Grade4                 480    550
$   100564  110564     130564    140564   Ti6Al4V_Grade5            880    950
$   100565  110565     130565    140565   Ti6Al4V_Grade5_ELI        795    860
$   100566  110566     130566    140566   Ti3Al2.5V_Grade9          485    620
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- Ti_Grade1 Bilinear (MID 100561) ---
$$ CP Ti, softest, medical
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 1
$$ rho=4.51 g/cc, E=105.0 GPa, nu=0.34
$$ sigy=170.0 MPa, sigu=240.0 MPa, eps_f=0.24
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 293.6 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade1 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100561 4.510e-09  105000.0    0.3400    170.00    293.65    0.2400      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Ti_Grade2 Bilinear (MID 100562) ---
$$ CP Ti, most common commercial grade
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 2
$$ rho=4.51 g/cc, E=105.0 GPa, nu=0.34
$$ sigy=275.0 MPa, sigu=345.0 MPa, eps_f=0.2
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 354.6 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade2 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100562 4.510e-09  105000.0    0.3400    275.00    354.64    0.2000      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Ti_Grade4 Bilinear (MID 100563) ---
$$ High-strength CP Ti
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 4
$$ rho=4.51 g/cc, E=105.0 GPa, nu=0.34
$$ sigy=480.0 MPa, sigu=550.0 MPa, eps_f=0.15
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 481.3 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade4 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100563 4.510e-09  105000.0    0.3400    480.00    481.34    0.1500      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Ti6Al4V_Grade5 Bilinear (MID 100564) ---
$$ Ti-6Al-4V workhorse alpha-beta alloy
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 5, MIL-HDBK-5; Meyer&Kleponis 2001 (CS)
$$ rho=4.43 g/cc, E=113.8 GPa, nu=0.342
$$ sigy=880.0 MPa, sigu=950.0 MPa, eps_f=0.14
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 529.2 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti6Al4V_Grade5 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100564 4.430e-09  113800.0    0.3420    880.00    529.23    0.1400      0.00
$        C         P      LCSS      LCSR        VP
     255.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Ti6Al4V_Grade5_ELI Bilinear (MID 100565) ---
$$ Extra-Low Interstitial Ti-6Al-4V, medical implant
$$ Temper: Annealed ELI
$$ Source: ASTM F136, ASTM B348 Gr 23
$$ rho=4.43 g/cc, E=113.8 GPa, nu=0.342
$$ sigy=795.0 MPa, sigu=860.0 MPa, eps_f=0.14
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 488.7 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti6Al4V_Grade5_ELI Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100565 4.430e-09  113800.0    0.3420    795.00    488.67    0.1400      0.00
$        C         P      LCSS      LCSR        VP
     255.0       2.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Ti3Al2.5V_Grade9 Bilinear (MID 100566) ---
$$ Ti-3Al-2.5V, bicycle/tubing grade
$$ Temper: Annealed
$$ Source: ASTM B338 Grade 9
$$ rho=4.48 g/cc, E=100.0 GPa, nu=0.3
$$ sigy=485.0 MPa, sigu=620.0 MPa, eps_f=0.15
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 930.1 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti3Al2.5V_Grade9 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100566 4.480e-09  100000.0    0.3000    485.00    930.07    0.1500      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- Ti_Grade1 Multilinear (MID 110561) ---
$$ CP Ti, softest, medical
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 1
$$ LCSS curve: 6 points, LCID=110561
*DEFINE_CURVE_TITLE
Ti_Grade1 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110561         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.7000000000e+02
    1.0000000000e-02    1.9500000000e+02
    3.0000000000e-02    2.1500000000e+02
    6.0000000000e-02    2.2800000000e+02
    1.2000000000e-01    2.3600000000e+02
    2.4000000000e-01    2.4000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade1 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110561 4.510e-09  105000.0    0.3400      0.00      0.00    0.2400      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0    110561         0       1.0
$
$$ --- Ti_Grade2 Multilinear (MID 110562) ---
$$ CP Ti, most common commercial grade
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 2
$$ LCSS curve: 6 points, LCID=110562
*DEFINE_CURVE_TITLE
Ti_Grade2 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110562         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.7500000000e+02
    1.0000000000e-02    3.0000000000e+02
    3.0000000000e-02    3.2000000000e+02
    6.0000000000e-02    3.3500000000e+02
    1.2000000000e-01    3.4200000000e+02
    2.0000000000e-01    3.4500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade2 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110562 4.510e-09  105000.0    0.3400      0.00      0.00    0.2000      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0    110562         0       1.0
$
$$ --- Ti_Grade4 Multilinear (MID 110563) ---
$$ High-strength CP Ti
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 4
$$ LCSS curve: 6 points, LCID=110563
*DEFINE_CURVE_TITLE
Ti_Grade4 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110563         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.8000000000e+02
    1.0000000000e-02    5.0500000000e+02
    3.0000000000e-02    5.2500000000e+02
    6.0000000000e-02    5.4000000000e+02
    1.0000000000e-01    5.4700000000e+02
    1.5000000000e-01    5.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti_Grade4 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110563 4.510e-09  105000.0    0.3400      0.00      0.00    0.1500      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0    110563         0       1.0
$
$$ --- Ti6Al4V_Grade5 Multilinear (MID 110564) ---
$$ Ti-6Al-4V workhorse alpha-beta alloy
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 5, MIL-HDBK-5; Meyer&Kleponis 2001 (CS)
$$ LCSS curve: 7 points, LCID=110564
*DEFINE_CURVE_TITLE
Ti6Al4V_Grade5 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110564         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.8000000000e+02
    5.0000000000e-03    9.0500000000e+02
    1.0000000000e-02    9.2000000000e+02
    2.0000000000e-02    9.3500000000e+02
    5.0000000000e-02    9.4500000000e+02
    1.0000000000e-01    9.5000000000e+02
    1.4000000000e-01    9.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti6Al4V_Grade5 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110564 4.430e-09  113800.0    0.3420      0.00      0.00    0.1400      0.00
$        C         P      LCSS      LCSR        VP
     255.0       2.0    110564         0       1.0
$
$$ --- Ti6Al4V_Grade5_ELI Multilinear (MID 110565) ---
$$ Extra-Low Interstitial Ti-6Al-4V, medical implant
$$ Temper: Annealed ELI
$$ Source: ASTM F136, ASTM B348 Gr 23
$$ LCSS curve: 7 points, LCID=110565
*DEFINE_CURVE_TITLE
Ti6Al4V_Grade5_ELI true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110565         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.9500000000e+02
    5.0000000000e-03    8.2000000000e+02
    1.0000000000e-02    8.3500000000e+02
    2.0000000000e-02    8.4800000000e+02
    5.0000000000e-02    8.5700000000e+02
    1.0000000000e-01    8.6000000000e+02
    1.4000000000e-01    8.6000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti6Al4V_Grade5_ELI Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110565 4.430e-09  113800.0    0.3420      0.00      0.00    0.1400      0.00
$        C         P      LCSS      LCSR        VP
     255.0       2.0    110565         0       1.0
$
$$ --- Ti3Al2.5V_Grade9 Multilinear (MID 110566) ---
$$ Ti-3Al-2.5V, bicycle/tubing grade
$$ Temper: Annealed
$$ Source: ASTM B338 Grade 9
$$ LCSS curve: 6 points, LCID=110566
*DEFINE_CURVE_TITLE
Ti3Al2.5V_Grade9 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110566         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.8500000000e+02
    1.0000000000e-02    5.4000000000e+02
    2.0000000000e-02    5.7500000000e+02
    5.0000000000e-02    6.0500000000e+02
    1.0000000000e-01    6.1800000000e+02
    1.5000000000e-01    6.2000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Ti3Al2.5V_Grade9 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110566 4.480e-09  100000.0    0.3000      0.00      0.00    0.1500      0.00
$        C         P      LCSS      LCSR        VP
     120.0       9.0    110566         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- Ti_Grade1 Kinematic Pure (MID 130561) ---
$$ CP Ti, softest, medical
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 1
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=170.0 MPa, ETAN=293.6 MPa, eps_f=0.24
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade1 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130561 4.510e-09  105000.0    0.3400    170.00    293.65    0.0000
$      SRC       SRP        FS        VP
     120.0       9.0    0.2400       1.0
$
$$ --- Ti_Grade2 Kinematic Pure (MID 130562) ---
$$ CP Ti, most common commercial grade
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 2
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=354.6 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade2 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130562 4.510e-09  105000.0    0.3400    275.00    354.64    0.0000
$      SRC       SRP        FS        VP
     120.0       9.0    0.2000       1.0
$
$$ --- Ti_Grade4 Kinematic Pure (MID 130563) ---
$$ High-strength CP Ti
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 4
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=480.0 MPa, ETAN=481.3 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade4 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130563 4.510e-09  105000.0    0.3400    480.00    481.34    0.0000
$      SRC       SRP        FS        VP
     120.0       9.0    0.1500       1.0
$
$$ --- Ti6Al4V_Grade5 Kinematic Pure (MID 130564) ---
$$ Ti-6Al-4V workhorse alpha-beta alloy
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 5, MIL-HDBK-5; Meyer&Kleponis 2001 (CS)
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=880.0 MPa, ETAN=529.2 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti6Al4V_Grade5 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130564 4.430e-09  113800.0    0.3420    880.00    529.23    0.0000
$      SRC       SRP        FS        VP
     255.0       2.0    0.1400       1.0
$
$$ --- Ti6Al4V_Grade5_ELI Kinematic Pure (MID 130565) ---
$$ Extra-Low Interstitial Ti-6Al-4V, medical implant
$$ Temper: Annealed ELI
$$ Source: ASTM F136, ASTM B348 Gr 23
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=795.0 MPa, ETAN=488.7 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti6Al4V_Grade5_ELI Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130565 4.430e-09  113800.0    0.3420    795.00    488.67    0.0000
$      SRC       SRP        FS        VP
     255.0       2.0    0.1400       1.0
$
$$ --- Ti3Al2.5V_Grade9 Kinematic Pure (MID 130566) ---
$$ Ti-3Al-2.5V, bicycle/tubing grade
$$ Temper: Annealed
$$ Source: ASTM B338 Grade 9
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=485.0 MPa, ETAN=930.1 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti3Al2.5V_Grade9 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130566 4.480e-09  100000.0    0.3000    485.00    930.07    0.0000
$      SRC       SRP        FS        VP
     120.0       9.0    0.1500       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- Ti_Grade1 Kinematic Mixed (MID 140561) ---
$$ CP Ti, softest, medical
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 1
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=170.0 MPa, ETAN=293.6 MPa, eps_f=0.24
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade1 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140561 4.510e-09  105000.0    0.3400    170.00    293.65    0.5000
$      SRC       SRP        FS        VP
     120.0       9.0    0.2400       1.0
$
$$ --- Ti_Grade2 Kinematic Mixed (MID 140562) ---
$$ CP Ti, most common commercial grade
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 2
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=354.6 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade2 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140562 4.510e-09  105000.0    0.3400    275.00    354.64    0.5000
$      SRC       SRP        FS        VP
     120.0       9.0    0.2000       1.0
$
$$ --- Ti_Grade4 Kinematic Mixed (MID 140563) ---
$$ High-strength CP Ti
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 4
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=480.0 MPa, ETAN=481.3 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti_Grade4 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140563 4.510e-09  105000.0    0.3400    480.00    481.34    0.5000
$      SRC       SRP        FS        VP
     120.0       9.0    0.1500       1.0
$
$$ --- Ti6Al4V_Grade5 Kinematic Mixed (MID 140564) ---
$$ Ti-6Al-4V workhorse alpha-beta alloy
$$ Temper: Annealed
$$ Source: ASTM B265 Grade 5, MIL-HDBK-5; Meyer&Kleponis 2001 (CS)
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=880.0 MPa, ETAN=529.2 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti6Al4V_Grade5 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140564 4.430e-09  113800.0    0.3420    880.00    529.23    0.5000
$      SRC       SRP        FS        VP
     255.0       2.0    0.1400       1.0
$
$$ --- Ti6Al4V_Grade5_ELI Kinematic Mixed (MID 140565) ---
$$ Extra-Low Interstitial Ti-6Al-4V, medical implant
$$ Temper: Annealed ELI
$$ Source: ASTM F136, ASTM B348 Gr 23
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=795.0 MPa, ETAN=488.7 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti6Al4V_Grade5_ELI Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140565 4.430e-09  113800.0    0.3420    795.00    488.67    0.5000
$      SRC       SRP        FS        VP
     255.0       2.0    0.1400       1.0
$
$$ --- Ti3Al2.5V_Grade9 Kinematic Mixed (MID 140566) ---
$$ Ti-3Al-2.5V, bicycle/tubing grade
$$ Temper: Annealed
$$ Source: ASTM B338 Grade 9
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=485.0 MPa, ETAN=930.1 MPa, eps_f=0.15
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Ti3Al2.5V_Grade9 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140566 4.480e-09  100000.0    0.3000    485.00    930.07    0.5000
$      SRC       SRP        FS        VP
     120.0       9.0    0.1500       1.0
$
*END
