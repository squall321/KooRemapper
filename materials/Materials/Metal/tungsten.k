$ ========================================================================
$ TUNGSTEN METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: TUNGSTEN — Tungsten (haptic motor counterweight, highest density)
$ MID: 100621 (bi), 110621 (multi)
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
$   100621  110621     130621    140621   Tungsten_99pct            750    980
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- Tungsten_99pct Bilinear (MID 100621) ---
$$ Tungsten 99% pure sintered (haptic motor counterweight, densest)
$$ Temper: Sintered 99%
$$ Source: Plansee Tungsten TDS, ASM Handbook Vol 2
$$ rho=19.3 g/cc, E=411.0 GPa, nu=0.28
$$ sigy=750.0 MPa, sigu=980.0 MPa, eps_f=0.03
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 8163.2 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Tungsten_99pct Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100621 1.930e-08  411000.0    0.2800    750.00   8163.21    0.0300      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- Tungsten_99pct Multilinear (MID 110621) ---
$$ Tungsten 99% pure sintered (haptic motor counterweight, densest)
$$ Temper: Sintered 99%
$$ Source: Plansee Tungsten TDS, ASM Handbook Vol 2
$$ LCSS curve: 6 points, LCID=110621
*DEFINE_CURVE_TITLE
Tungsten_99pct true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110621         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    7.5000000000e+02
    5.0000000000e-03    8.2000000000e+02
    1.0000000000e-02    8.7000000000e+02
    1.5000000000e-02    9.2000000000e+02
    2.0000000000e-02    9.6000000000e+02
    3.0000000000e-02    9.8000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Tungsten_99pct Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110621 1.930e-08  411000.0    0.2800      0.00      0.00    0.0300      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0    110621         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- Tungsten_99pct Kinematic Pure (MID 130621) ---
$$ Tungsten 99% pure sintered (haptic motor counterweight, densest)
$$ Temper: Sintered 99%
$$ Source: Plansee Tungsten TDS, ASM Handbook Vol 2
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=750.0 MPa, ETAN=8163.2 MPa, eps_f=0.03
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Tungsten_99pct Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130621 1.930e-08  411000.0    0.2800    750.00   8163.21    0.0000
$      SRC       SRP        FS        VP
      40.0       5.0    0.0300       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- Tungsten_99pct Kinematic Mixed (MID 140621) ---
$$ Tungsten 99% pure sintered (haptic motor counterweight, densest)
$$ Temper: Sintered 99%
$$ Source: Plansee Tungsten TDS, ASM Handbook Vol 2
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=750.0 MPa, ETAN=8163.2 MPa, eps_f=0.03
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Tungsten_99pct Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140621 1.930e-08  411000.0    0.2800    750.00   8163.21    0.5000
$      SRC       SRP        FS        VP
      40.0       5.0    0.0300       1.0
$
*END
