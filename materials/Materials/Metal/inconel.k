$ ========================================================================
$ INCONEL METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: INCONEL — Ni-base Superalloys (high temperature)
$ MID: 100611~100620 (bi), 110611~110620 (multi)
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
$   100611  110611     130611    140611   Inconel_625_annealed      415    827
$   100612  110612     130612    140612   Inconel_718_aged         1035   1240
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- Inconel_625_annealed Bilinear (MID 100611) ---
$$ Ni-Cr-Mo solid-solution superalloy (aerospace, marine)
$$ Temper: Annealed
$$ Source: ASTM B443 / UNS N06625, Special Metals TDS
$$ rho=8.44 g/cc, E=207.5 GPa, nu=0.312
$$ sigy=415.0 MPa, sigu=827.0 MPa, eps_f=0.3
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1382.6 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Inconel_625_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100611 8.440e-09  207500.0    0.3120    415.00   1382.55    0.3000      0.00
$        C         P      LCSS      LCSR        VP
   17200.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Inconel_718_aged Bilinear (MID 100612) ---
$$ Ni-Cr precipitation-hardenable (turbine, rocket)
$$ Temper: Solution + aged
$$ Source: ASTM B637 / UNS N07718, Special Metals TDS
$$ rho=8.19 g/cc, E=205.0 GPa, nu=0.294
$$ sigy=1035.0 MPa, sigu=1240.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1783.4 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Inconel_718_aged Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100612 8.190e-09  205000.0    0.2940   1035.00   1783.37    0.1200      0.00
$        C         P      LCSS      LCSR        VP
   17200.0       3.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- Inconel_625_annealed Multilinear (MID 110611) ---
$$ Ni-Cr-Mo solid-solution superalloy (aerospace, marine)
$$ Temper: Annealed
$$ Source: ASTM B443 / UNS N06625, Special Metals TDS
$$ LCSS curve: 7 points, LCID=110611
*DEFINE_CURVE_TITLE
Inconel_625_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110611         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.1500000000e+02
    1.0000000000e-02    5.1000000000e+02
    2.0000000000e-02    5.8500000000e+02
    5.0000000000e-02    6.8500000000e+02
    1.0000000000e-01    7.6000000000e+02
    2.0000000000e-01    8.1000000000e+02
    3.0000000000e-01    8.2700000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Inconel_625_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110611 8.440e-09  207500.0    0.3120      0.00      0.00    0.3000      0.00
$        C         P      LCSS      LCSR        VP
   17200.0       3.0    110611         0       1.0
$
$$ --- Inconel_718_aged Multilinear (MID 110612) ---
$$ Ni-Cr precipitation-hardenable (turbine, rocket)
$$ Temper: Solution + aged
$$ Source: ASTM B637 / UNS N07718, Special Metals TDS
$$ LCSS curve: 7 points, LCID=110612
*DEFINE_CURVE_TITLE
Inconel_718_aged true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110612         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.0350000000e+03
    5.0000000000e-03    1.1050000000e+03
    1.0000000000e-02    1.1500000000e+03
    2.0000000000e-02    1.1850000000e+03
    5.0000000000e-02    1.2150000000e+03
    1.0000000000e-01    1.2350000000e+03
    1.2000000000e-01    1.2400000000e+03
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Inconel_718_aged Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110612 8.190e-09  205000.0    0.2940      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
   17200.0       3.0    110612         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- Inconel_625_annealed Kinematic Pure (MID 130611) ---
$$ Ni-Cr-Mo solid-solution superalloy (aerospace, marine)
$$ Temper: Annealed
$$ Source: ASTM B443 / UNS N06625, Special Metals TDS
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=415.0 MPa, ETAN=1382.6 MPa, eps_f=0.3
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Inconel_625_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130611 8.440e-09  207500.0    0.3120    415.00   1382.55    0.0000
$      SRC       SRP        FS        VP
   17200.0       3.0    0.3000       1.0
$
$$ --- Inconel_718_aged Kinematic Pure (MID 130612) ---
$$ Ni-Cr precipitation-hardenable (turbine, rocket)
$$ Temper: Solution + aged
$$ Source: ASTM B637 / UNS N07718, Special Metals TDS
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=1035.0 MPa, ETAN=1783.4 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Inconel_718_aged Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130612 8.190e-09  205000.0    0.2940   1035.00   1783.37    0.0000
$      SRC       SRP        FS        VP
   17200.0       3.0    0.1200       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- Inconel_625_annealed Kinematic Mixed (MID 140611) ---
$$ Ni-Cr-Mo solid-solution superalloy (aerospace, marine)
$$ Temper: Annealed
$$ Source: ASTM B443 / UNS N06625, Special Metals TDS
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=415.0 MPa, ETAN=1382.6 MPa, eps_f=0.3
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Inconel_625_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140611 8.440e-09  207500.0    0.3120    415.00   1382.55    0.5000
$      SRC       SRP        FS        VP
   17200.0       3.0    0.3000       1.0
$
$$ --- Inconel_718_aged Kinematic Mixed (MID 140612) ---
$$ Ni-Cr precipitation-hardenable (turbine, rocket)
$$ Temper: Solution + aged
$$ Source: ASTM B637 / UNS N07718, Special Metals TDS
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=1035.0 MPa, ETAN=1783.4 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Inconel_718_aged Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140612 8.190e-09  205000.0    0.2940   1035.00   1783.37    0.5000
$      SRC       SRP        FS        VP
   17200.0       3.0    0.1200       1.0
$
*END
