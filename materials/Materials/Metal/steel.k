$ ========================================================================
$ STEEL METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: STEEL — Carbon/Alloy Steel (brackets, fasteners)
$ MID: 100591~100600 (bi), 110591~110600 (multi)
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
$   100591  110591     130591    140591   SPCC_mild_steel           195    350
$   100592  110592     130592    140592   S45C_medium_carbon        343    569
$   100593  110593     130593    140593   SCM440_alloy_steel        835    980
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- SPCC_mild_steel Bilinear (MID 100591) ---
$$ Cold-rolled mild steel sheet (brackets, housings)
$$ Temper: Cold rolled
$$ Source: JIS G 3141 SPCC, ASTM A1008
$$ rho=7.85 g/cc, E=210.0 GPa, nu=0.3
$$ sigy=195.0 MPa, sigu=350.0 MPa, eps_f=0.37
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 420.0 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SPCC_mild_steel Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100591 7.850e-09  210000.0    0.3000    195.00    419.97    0.3700      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- S45C_medium_carbon Bilinear (MID 100592) ---
$$ 0.45%C medium carbon steel (shafts, fasteners)
$$ Temper: Normalized
$$ Source: JIS G 4051 S45C, AISI 1045
$$ rho=7.85 g/cc, E=205.0 GPa, nu=0.29
$$ sigy=343.0 MPa, sigu=569.0 MPa, eps_f=0.2
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1139.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
S45C_medium_carbon Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100592 7.850e-09  205000.0    0.2900    343.00   1139.53    0.2000      0.00
$        C         P      LCSS      LCSR        VP
     802.0       3.6         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SCM440_alloy_steel Bilinear (MID 100593) ---
$$ Cr-Mo alloy steel Q&T (high-strength bolts, gears)
$$ Temper: Q&T (HB 285)
$$ Source: JIS G 4053 SCM440, AISI 4140
$$ rho=7.85 g/cc, E=205.0 GPa, nu=0.29
$$ sigy=835.0 MPa, sigu=980.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1250.8 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SCM440_alloy_steel Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100593 7.850e-09  205000.0    0.2900    835.00   1250.79    0.1200      0.00
$        C         P      LCSS      LCSR        VP
     802.0       3.6         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- SPCC_mild_steel Multilinear (MID 110591) ---
$$ Cold-rolled mild steel sheet (brackets, housings)
$$ Temper: Cold rolled
$$ Source: JIS G 3141 SPCC, ASTM A1008
$$ LCSS curve: 7 points, LCID=110591
*DEFINE_CURVE_TITLE
SPCC_mild_steel true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110591         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.9500000000e+02
    2.0000000000e-02    2.4000000000e+02
    5.0000000000e-02    2.7500000000e+02
    1.0000000000e-01    3.1000000000e+02
    2.0000000000e-01    3.3500000000e+02
    3.0000000000e-01    3.4500000000e+02
    3.7000000000e-01    3.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SPCC_mild_steel Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110591 7.850e-09  210000.0    0.3000      0.00      0.00    0.3700      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0    110591         0       1.0
$
$$ --- S45C_medium_carbon Multilinear (MID 110592) ---
$$ 0.45%C medium carbon steel (shafts, fasteners)
$$ Temper: Normalized
$$ Source: JIS G 4051 S45C, AISI 1045
$$ LCSS curve: 7 points, LCID=110592
*DEFINE_CURVE_TITLE
S45C_medium_carbon true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110592         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.4300000000e+02
    1.0000000000e-02    4.1000000000e+02
    2.0000000000e-02    4.5000000000e+02
    5.0000000000e-02    5.0000000000e+02
    1.0000000000e-01    5.4000000000e+02
    1.5000000000e-01    5.6000000000e+02
    2.0000000000e-01    5.6900000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
S45C_medium_carbon Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110592 7.850e-09  205000.0    0.2900      0.00      0.00    0.2000      0.00
$        C         P      LCSS      LCSR        VP
     802.0       3.6    110592         0       1.0
$
$$ --- SCM440_alloy_steel Multilinear (MID 110593) ---
$$ Cr-Mo alloy steel Q&T (high-strength bolts, gears)
$$ Temper: Q&T (HB 285)
$$ Source: JIS G 4053 SCM440, AISI 4140
$$ LCSS curve: 7 points, LCID=110593
*DEFINE_CURVE_TITLE
SCM440_alloy_steel true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110593         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    8.3500000000e+02
    5.0000000000e-03    8.7500000000e+02
    1.0000000000e-02    9.0500000000e+02
    2.0000000000e-02    9.3500000000e+02
    5.0000000000e-02    9.6500000000e+02
    1.0000000000e-01    9.7800000000e+02
    1.2000000000e-01    9.8000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SCM440_alloy_steel Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110593 7.850e-09  205000.0    0.2900      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
     802.0       3.6    110593         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- SPCC_mild_steel Kinematic Pure (MID 130591) ---
$$ Cold-rolled mild steel sheet (brackets, housings)
$$ Temper: Cold rolled
$$ Source: JIS G 3141 SPCC, ASTM A1008
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=195.0 MPa, ETAN=420.0 MPa, eps_f=0.37
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SPCC_mild_steel Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130591 7.850e-09  210000.0    0.3000    195.00    419.97    0.0000
$      SRC       SRP        FS        VP
      40.0       5.0    0.3700       1.0
$
$$ --- S45C_medium_carbon Kinematic Pure (MID 130592) ---
$$ 0.45%C medium carbon steel (shafts, fasteners)
$$ Temper: Normalized
$$ Source: JIS G 4051 S45C, AISI 1045
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=343.0 MPa, ETAN=1139.5 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
S45C_medium_carbon Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130592 7.850e-09  205000.0    0.2900    343.00   1139.53    0.0000
$      SRC       SRP        FS        VP
     802.0       3.6    0.2000       1.0
$
$$ --- SCM440_alloy_steel Kinematic Pure (MID 130593) ---
$$ Cr-Mo alloy steel Q&T (high-strength bolts, gears)
$$ Temper: Q&T (HB 285)
$$ Source: JIS G 4053 SCM440, AISI 4140
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=835.0 MPa, ETAN=1250.8 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SCM440_alloy_steel Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130593 7.850e-09  205000.0    0.2900    835.00   1250.79    0.0000
$      SRC       SRP        FS        VP
     802.0       3.6    0.1200       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- SPCC_mild_steel Kinematic Mixed (MID 140591) ---
$$ Cold-rolled mild steel sheet (brackets, housings)
$$ Temper: Cold rolled
$$ Source: JIS G 3141 SPCC, ASTM A1008
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=195.0 MPa, ETAN=420.0 MPa, eps_f=0.37
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SPCC_mild_steel Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140591 7.850e-09  210000.0    0.3000    195.00    419.97    0.5000
$      SRC       SRP        FS        VP
      40.0       5.0    0.3700       1.0
$
$$ --- S45C_medium_carbon Kinematic Mixed (MID 140592) ---
$$ 0.45%C medium carbon steel (shafts, fasteners)
$$ Temper: Normalized
$$ Source: JIS G 4051 S45C, AISI 1045
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=343.0 MPa, ETAN=1139.5 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
S45C_medium_carbon Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140592 7.850e-09  205000.0    0.2900    343.00   1139.53    0.5000
$      SRC       SRP        FS        VP
     802.0       3.6    0.2000       1.0
$
$$ --- SCM440_alloy_steel Kinematic Mixed (MID 140593) ---
$$ Cr-Mo alloy steel Q&T (high-strength bolts, gears)
$$ Temper: Q&T (HB 285)
$$ Source: JIS G 4053 SCM440, AISI 4140
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=835.0 MPa, ETAN=1250.8 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SCM440_alloy_steel Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140593 7.850e-09  205000.0    0.2900    835.00   1250.79    0.5000
$      SRC       SRP        FS        VP
     802.0       3.6    0.1200       1.0
$
*END
