$ ========================================================================
$ AL METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: AL — Aluminum Alloys
$ MID: 100521~100560 (bi), 110521~110560 (multi)
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
$   100521  110521     130521    140521   Al1050-O                   28     76
$   100522  110522     130522    140522   Al1100-O                   34     90
$   100523  110523     130523    140523   Al2024-T3                 345    483
$   100524  110524     130524    140524   Al3003-H14                145    150
$   100525  110525     130525    140525   Al5052-H32                193    228
$   100526  110526     130526    140526   Al5083-H116               215    305
$   100535  110535     130535    140535   Al6061-T6                 276    310
$   100536  110536     130536    140536   Al6063-T5                 145    186
$   100537  110537     130537    140537   Al6063-T6                 214    241
$   100538  110538     130538    140538   Al7050-T7451              469    524
$   100539  110539     130539    140539   Al7075-T6                 503    572
$   100540  110540     130540    140540   ADC12_diecast             150    310
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- Al1050-O Bilinear (MID 100521) ---
$$ Pure Al annealed, reflector grade
$$ Temper: O (annealed)
$$ Source: Al Association, MatWeb
$$ rho=2.705 g/cc, E=69.0 GPa, nu=0.33
$$ sigy=28.0 MPa, sigu=76.0 MPa, eps_f=0.36
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 133.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al1050-O Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100521 2.705e-09   69000.0    0.3300     28.00    133.48    0.3600      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al1100-O Bilinear (MID 100522) ---
$$ Commercial pure Al, foil and sheet
$$ Temper: O (annealed)
$$ Source: ASTM B209, Al Assoc
$$ rho=2.71 g/cc, E=69.0 GPa, nu=0.33
$$ sigy=34.0 MPa, sigu=90.0 MPa, eps_f=0.35
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 160.2 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al1100-O Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100522 2.710e-09   69000.0    0.3300     34.00    160.23    0.3500      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al2024-T3 Bilinear (MID 100523) ---
$$ Al-Cu aerospace alloy
$$ Temper: T3
$$ Source: ASTM B209, MIL-HDBK-5; Bodner-Partom (rate-insensitive)
$$ rho=2.78 g/cc, E=73.1 GPa, nu=0.33
$$ sigy=345.0 MPa, sigu=483.0 MPa, eps_f=0.18
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 787.3 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al2024-T3 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100523 2.780e-09   73100.0    0.3300    345.00    787.31    0.1800      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al3003-H14 Bilinear (MID 100524) ---
$$ Al-Mn, roofing and radiator
$$ Temper: H14 (half-hard)
$$ Source: ASTM B209
$$ rho=2.73 g/cc, E=68.9 GPa, nu=0.33
$$ sigy=145.0 MPa, sigu=150.0 MPa, eps_f=0.1
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 51.1 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al3003-H14 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100524 2.730e-09   68900.0    0.3300    145.00     51.07    0.1000      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al5052-H32 Bilinear (MID 100525) ---
$$ Al-Mg marine grade
$$ Temper: H32 (strain-hardened)
$$ Source: ASTM B209
$$ rho=2.68 g/cc, E=70.3 GPa, nu=0.33
$$ sigy=193.0 MPa, sigu=228.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 298.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al5052-H32 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100525 2.680e-09   70300.0    0.3300    193.00    298.50    0.1200      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al5083-H116 Bilinear (MID 100526) ---
$$ High-strength Al-Mg, LNG tanks
$$ Temper: H116
$$ Source: ASTM B928
$$ rho=2.66 g/cc, E=70.3 GPa, nu=0.33
$$ sigy=215.0 MPa, sigu=305.0 MPa, eps_f=0.16
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 573.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al5083-H116 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100526 2.660e-09   70300.0    0.3300    215.00    573.46    0.1600      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al6061-T6 Bilinear (MID 100535) ---
$$ Al-Mg-Si general structural (most common)
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5; precipitation hardened rate-insensitive
$$ rho=2.7 g/cc, E=68.9 GPa, nu=0.33
$$ sigy=276.0 MPa, sigu=310.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 293.1 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6061-T6 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100535 2.700e-09   68900.0    0.3300    276.00    293.12    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al6063-T5 Bilinear (MID 100536) ---
$$ Extrusion alloy, windows/frames
$$ Temper: T5
$$ Source: ASTM B221
$$ rho=2.7 g/cc, E=68.9 GPa, nu=0.33
$$ sigy=145.0 MPa, sigu=186.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 347.8 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6063-T5 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100536 2.700e-09   68900.0    0.3300    145.00    347.77    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al6063-T6 Bilinear (MID 100537) ---
$$ T6 heat-treated 6063 extrusion
$$ Temper: T6
$$ Source: ASTM B221
$$ rho=2.7 g/cc, E=68.9 GPa, nu=0.33
$$ sigy=214.0 MPa, sigu=241.0 MPa, eps_f=0.12
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 231.0 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6063-T6 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100537 2.700e-09   68900.0    0.3300    214.00    230.98    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al7050-T7451 Bilinear (MID 100538) ---
$$ Al-Zn aerospace, stress-corrosion resistant
$$ Temper: T7451
$$ Source: ASTM B209, MIL-HDBK-5
$$ rho=2.83 g/cc, E=71.7 GPa, nu=0.33
$$ sigy=469.0 MPa, sigu=524.0 MPa, eps_f=0.11
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 531.6 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al7050-T7451 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100538 2.830e-09   71700.0    0.3300    469.00    531.61    0.1100      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al7075-T6 Bilinear (MID 100539) ---
$$ Highest-strength Al-Zn aerospace
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5
$$ rho=2.81 g/cc, E=71.7 GPa, nu=0.33
$$ sigy=503.0 MPa, sigu=572.0 MPa, eps_f=0.11
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 670.0 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al7075-T6 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100539 2.810e-09   71700.0    0.3300    503.00    670.00    0.1100      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- ADC12_diecast Bilinear (MID 100540) ---
$$ Die-cast Al-Si-Cu (smartphone frames)
$$ Temper: As-cast
$$ Source: JIS H 5302, Nadca handbook; porosity raises damping
$$ rho=2.7 g/cc, E=71.0 GPa, nu=0.33
$$ sigy=150.0 MPa, sigu=310.0 MPa, eps_f=0.025
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 6990.8 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
ADC12_diecast Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100540 2.700e-09   71000.0    0.3300    150.00   6990.77    0.0250      0.00
$        C         P      LCSS      LCSR        VP
    1500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- Al1050-O Multilinear (MID 110521) ---
$$ Pure Al annealed, reflector grade
$$ Temper: O (annealed)
$$ Source: Al Association, MatWeb
$$ LCSS curve: 6 points, LCID=110521
*DEFINE_CURVE_TITLE
Al1050-O true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110521         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.8000000000e+01
    2.0000000000e-02    4.0000000000e+01
    5.0000000000e-02    5.2000000000e+01
    1.0000000000e-01    6.2000000000e+01
    2.0000000000e-01    7.2000000000e+01
    3.6000000000e-01    7.6000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al1050-O Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110521 2.705e-09   69000.0    0.3300      0.00      0.00    0.3600      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110521         0       1.0
$
$$ --- Al1100-O Multilinear (MID 110522) ---
$$ Commercial pure Al, foil and sheet
$$ Temper: O (annealed)
$$ Source: ASTM B209, Al Assoc
$$ LCSS curve: 6 points, LCID=110522
*DEFINE_CURVE_TITLE
Al1100-O true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110522         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.4000000000e+01
    2.0000000000e-02    4.8000000000e+01
    5.0000000000e-02    6.2000000000e+01
    1.0000000000e-01    7.3000000000e+01
    2.0000000000e-01    8.4000000000e+01
    3.5000000000e-01    9.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al1100-O Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110522 2.710e-09   69000.0    0.3300      0.00      0.00    0.3500      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110522         0       1.0
$
$$ --- Al2024-T3 Multilinear (MID 110523) ---
$$ Al-Cu aerospace alloy
$$ Temper: T3
$$ Source: ASTM B209, MIL-HDBK-5; Bodner-Partom (rate-insensitive)
$$ LCSS curve: 7 points, LCID=110523
*DEFINE_CURVE_TITLE
Al2024-T3 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110523         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.4500000000e+02
    5.0000000000e-03    3.8500000000e+02
    1.0000000000e-02    4.1000000000e+02
    2.0000000000e-02    4.3500000000e+02
    5.0000000000e-02    4.6500000000e+02
    1.0000000000e-01    4.7800000000e+02
    1.8000000000e-01    4.8300000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al2024-T3 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110523 2.780e-09   73100.0    0.3300      0.00      0.00    0.1800      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110523         0       1.0
$
$$ --- Al3003-H14 Multilinear (MID 110524) ---
$$ Al-Mn, roofing and radiator
$$ Temper: H14 (half-hard)
$$ Source: ASTM B209
$$ LCSS curve: 6 points, LCID=110524
*DEFINE_CURVE_TITLE
Al3003-H14 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110524         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.4500000000e+02
    1.0000000000e-02    1.4800000000e+02
    3.0000000000e-02    1.4900000000e+02
    5.0000000000e-02    1.5000000000e+02
    8.0000000000e-02    1.5000000000e+02
    1.0000000000e-01    1.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al3003-H14 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110524 2.730e-09   68900.0    0.3300      0.00      0.00    0.1000      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110524         0       1.0
$
$$ --- Al5052-H32 Multilinear (MID 110525) ---
$$ Al-Mg marine grade
$$ Temper: H32 (strain-hardened)
$$ Source: ASTM B209
$$ LCSS curve: 6 points, LCID=110525
*DEFINE_CURVE_TITLE
Al5052-H32 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110525         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.9300000000e+02
    1.0000000000e-02    2.0500000000e+02
    2.0000000000e-02    2.1300000000e+02
    5.0000000000e-02    2.2200000000e+02
    8.0000000000e-02    2.2600000000e+02
    1.2000000000e-01    2.2800000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al5052-H32 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110525 2.680e-09   70300.0    0.3300      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110525         0       1.0
$
$$ --- Al5083-H116 Multilinear (MID 110526) ---
$$ High-strength Al-Mg, LNG tanks
$$ Temper: H116
$$ Source: ASTM B928
$$ LCSS curve: 7 points, LCID=110526
*DEFINE_CURVE_TITLE
Al5083-H116 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110526         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.1500000000e+02
    5.0000000000e-03    2.4000000000e+02
    1.0000000000e-02    2.5800000000e+02
    2.0000000000e-02    2.7500000000e+02
    5.0000000000e-02    2.9300000000e+02
    1.0000000000e-01    3.0300000000e+02
    1.6000000000e-01    3.0500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al5083-H116 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110526 2.660e-09   70300.0    0.3300      0.00      0.00    0.1600      0.00
$        C         P      LCSS      LCSR        VP
    6500.0       4.0    110526         0       1.0
$
$$ --- Al6061-T6 Multilinear (MID 110535) ---
$$ Al-Mg-Si general structural (most common)
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5; precipitation hardened rate-insensitive
$$ LCSS curve: 7 points, LCID=110535
*DEFINE_CURVE_TITLE
Al6061-T6 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110535         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.7600000000e+02
    5.0000000000e-03    2.8900000000e+02
    1.0000000000e-02    2.9600000000e+02
    2.0000000000e-02    3.0200000000e+02
    5.0000000000e-02    3.0800000000e+02
    1.0000000000e-01    3.1000000000e+02
    1.2000000000e-01    3.1000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6061-T6 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110535 2.700e-09   68900.0    0.3300      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110535         0       1.0
$
$$ --- Al6063-T5 Multilinear (MID 110536) ---
$$ Extrusion alloy, windows/frames
$$ Temper: T5
$$ Source: ASTM B221
$$ LCSS curve: 7 points, LCID=110536
*DEFINE_CURVE_TITLE
Al6063-T5 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110536         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.4500000000e+02
    5.0000000000e-03    1.5800000000e+02
    1.0000000000e-02    1.6800000000e+02
    2.0000000000e-02    1.7600000000e+02
    5.0000000000e-02    1.8300000000e+02
    1.0000000000e-01    1.8600000000e+02
    1.2000000000e-01    1.8600000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6063-T5 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110536 2.700e-09   68900.0    0.3300      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110536         0       1.0
$
$$ --- Al6063-T6 Multilinear (MID 110537) ---
$$ T6 heat-treated 6063 extrusion
$$ Temper: T6
$$ Source: ASTM B221
$$ LCSS curve: 7 points, LCID=110537
*DEFINE_CURVE_TITLE
Al6063-T6 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110537         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.1400000000e+02
    5.0000000000e-03    2.2500000000e+02
    1.0000000000e-02    2.3200000000e+02
    2.0000000000e-02    2.3700000000e+02
    5.0000000000e-02    2.4000000000e+02
    1.0000000000e-01    2.4100000000e+02
    1.2000000000e-01    2.4100000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al6063-T6 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110537 2.700e-09   68900.0    0.3300      0.00      0.00    0.1200      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110537         0       1.0
$
$$ --- Al7050-T7451 Multilinear (MID 110538) ---
$$ Al-Zn aerospace, stress-corrosion resistant
$$ Temper: T7451
$$ Source: ASTM B209, MIL-HDBK-5
$$ LCSS curve: 7 points, LCID=110538
*DEFINE_CURVE_TITLE
Al7050-T7451 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110538         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    4.6900000000e+02
    5.0000000000e-03    4.9200000000e+02
    1.0000000000e-02    5.0500000000e+02
    2.0000000000e-02    5.1500000000e+02
    5.0000000000e-02    5.2100000000e+02
    1.0000000000e-01    5.2400000000e+02
    1.1000000000e-01    5.2400000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al7050-T7451 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110538 2.830e-09   71700.0    0.3300      0.00      0.00    0.1100      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110538         0       1.0
$
$$ --- Al7075-T6 Multilinear (MID 110539) ---
$$ Highest-strength Al-Zn aerospace
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5
$$ LCSS curve: 7 points, LCID=110539
*DEFINE_CURVE_TITLE
Al7075-T6 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110539         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    5.0300000000e+02
    5.0000000000e-03    5.2800000000e+02
    1.0000000000e-02    5.4300000000e+02
    2.0000000000e-02    5.5500000000e+02
    5.0000000000e-02    5.6700000000e+02
    1.0000000000e-01    5.7200000000e+02
    1.1000000000e-01    5.7200000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Al7075-T6 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110539 2.810e-09   71700.0    0.3300      0.00      0.00    0.1100      0.00
$        C         P      LCSS      LCSR        VP
 1288000.0       4.0    110539         0       1.0
$
$$ --- ADC12_diecast Multilinear (MID 110540) ---
$$ Die-cast Al-Si-Cu (smartphone frames)
$$ Temper: As-cast
$$ Source: JIS H 5302, Nadca handbook; porosity raises damping
$$ LCSS curve: 6 points, LCID=110540
*DEFINE_CURVE_TITLE
ADC12_diecast true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110540         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.5000000000e+02
    5.0000000000e-03    2.2000000000e+02
    1.0000000000e-02    2.6000000000e+02
    1.5000000000e-02    2.8500000000e+02
    2.0000000000e-02    3.0000000000e+02
    2.5000000000e-02    3.1000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
ADC12_diecast Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110540 2.700e-09   71000.0    0.3300      0.00      0.00    0.0250      0.00
$        C         P      LCSS      LCSR        VP
    1500.0       4.0    110540         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- Al1050-O Kinematic Pure (MID 130521) ---
$$ Pure Al annealed, reflector grade
$$ Temper: O (annealed)
$$ Source: Al Association, MatWeb
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=28.0 MPa, ETAN=133.5 MPa, eps_f=0.36
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al1050-O Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130521 2.705e-09   69000.0    0.3300     28.00    133.48    0.0000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.3600       1.0
$
$$ --- Al1100-O Kinematic Pure (MID 130522) ---
$$ Commercial pure Al, foil and sheet
$$ Temper: O (annealed)
$$ Source: ASTM B209, Al Assoc
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=34.0 MPa, ETAN=160.2 MPa, eps_f=0.35
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al1100-O Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130522 2.710e-09   69000.0    0.3300     34.00    160.23    0.0000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.3500       1.0
$
$$ --- Al2024-T3 Kinematic Pure (MID 130523) ---
$$ Al-Cu aerospace alloy
$$ Temper: T3
$$ Source: ASTM B209, MIL-HDBK-5; Bodner-Partom (rate-insensitive)
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=345.0 MPa, ETAN=787.3 MPa, eps_f=0.18
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al2024-T3 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130523 2.780e-09   73100.0    0.3300    345.00    787.31    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1800       1.0
$
$$ --- Al3003-H14 Kinematic Pure (MID 130524) ---
$$ Al-Mn, roofing and radiator
$$ Temper: H14 (half-hard)
$$ Source: ASTM B209
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=145.0 MPa, ETAN=51.1 MPa, eps_f=0.1
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al3003-H14 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130524 2.730e-09   68900.0    0.3300    145.00     51.07    0.0000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1000       1.0
$
$$ --- Al5052-H32 Kinematic Pure (MID 130525) ---
$$ Al-Mg marine grade
$$ Temper: H32 (strain-hardened)
$$ Source: ASTM B209
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=193.0 MPa, ETAN=298.5 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al5052-H32 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130525 2.680e-09   70300.0    0.3300    193.00    298.50    0.0000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1200       1.0
$
$$ --- Al5083-H116 Kinematic Pure (MID 130526) ---
$$ High-strength Al-Mg, LNG tanks
$$ Temper: H116
$$ Source: ASTM B928
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=215.0 MPa, ETAN=573.5 MPa, eps_f=0.16
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al5083-H116 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130526 2.660e-09   70300.0    0.3300    215.00    573.46    0.0000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1600       1.0
$
$$ --- Al6061-T6 Kinematic Pure (MID 130535) ---
$$ Al-Mg-Si general structural (most common)
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5; precipitation hardened rate-insensitive
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=276.0 MPa, ETAN=293.1 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6061-T6 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130535 2.700e-09   68900.0    0.3300    276.00    293.12    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al6063-T5 Kinematic Pure (MID 130536) ---
$$ Extrusion alloy, windows/frames
$$ Temper: T5
$$ Source: ASTM B221
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=145.0 MPa, ETAN=347.8 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6063-T5 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130536 2.700e-09   68900.0    0.3300    145.00    347.77    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al6063-T6 Kinematic Pure (MID 130537) ---
$$ T6 heat-treated 6063 extrusion
$$ Temper: T6
$$ Source: ASTM B221
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=214.0 MPa, ETAN=231.0 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6063-T6 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130537 2.700e-09   68900.0    0.3300    214.00    230.98    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al7050-T7451 Kinematic Pure (MID 130538) ---
$$ Al-Zn aerospace, stress-corrosion resistant
$$ Temper: T7451
$$ Source: ASTM B209, MIL-HDBK-5
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=469.0 MPa, ETAN=531.6 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al7050-T7451 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130538 2.830e-09   71700.0    0.3300    469.00    531.61    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1100       1.0
$
$$ --- Al7075-T6 Kinematic Pure (MID 130539) ---
$$ Highest-strength Al-Zn aerospace
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=503.0 MPa, ETAN=670.0 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al7075-T6 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130539 2.810e-09   71700.0    0.3300    503.00    670.00    0.0000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1100       1.0
$
$$ --- ADC12_diecast Kinematic Pure (MID 130540) ---
$$ Die-cast Al-Si-Cu (smartphone frames)
$$ Temper: As-cast
$$ Source: JIS H 5302, Nadca handbook; porosity raises damping
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=150.0 MPa, ETAN=6990.8 MPa, eps_f=0.025
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
ADC12_diecast Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130540 2.700e-09   71000.0    0.3300    150.00   6990.77    0.0000
$      SRC       SRP        FS        VP
    1500.0       4.0    0.0250       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- Al1050-O Kinematic Mixed (MID 140521) ---
$$ Pure Al annealed, reflector grade
$$ Temper: O (annealed)
$$ Source: Al Association, MatWeb
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=28.0 MPa, ETAN=133.5 MPa, eps_f=0.36
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al1050-O Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140521 2.705e-09   69000.0    0.3300     28.00    133.48    0.5000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.3600       1.0
$
$$ --- Al1100-O Kinematic Mixed (MID 140522) ---
$$ Commercial pure Al, foil and sheet
$$ Temper: O (annealed)
$$ Source: ASTM B209, Al Assoc
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=34.0 MPa, ETAN=160.2 MPa, eps_f=0.35
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al1100-O Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140522 2.710e-09   69000.0    0.3300     34.00    160.23    0.5000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.3500       1.0
$
$$ --- Al2024-T3 Kinematic Mixed (MID 140523) ---
$$ Al-Cu aerospace alloy
$$ Temper: T3
$$ Source: ASTM B209, MIL-HDBK-5; Bodner-Partom (rate-insensitive)
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=345.0 MPa, ETAN=787.3 MPa, eps_f=0.18
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al2024-T3 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140523 2.780e-09   73100.0    0.3300    345.00    787.31    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1800       1.0
$
$$ --- Al3003-H14 Kinematic Mixed (MID 140524) ---
$$ Al-Mn, roofing and radiator
$$ Temper: H14 (half-hard)
$$ Source: ASTM B209
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=145.0 MPa, ETAN=51.1 MPa, eps_f=0.1
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al3003-H14 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140524 2.730e-09   68900.0    0.3300    145.00     51.07    0.5000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1000       1.0
$
$$ --- Al5052-H32 Kinematic Mixed (MID 140525) ---
$$ Al-Mg marine grade
$$ Temper: H32 (strain-hardened)
$$ Source: ASTM B209
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=193.0 MPa, ETAN=298.5 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al5052-H32 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140525 2.680e-09   70300.0    0.3300    193.00    298.50    0.5000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1200       1.0
$
$$ --- Al5083-H116 Kinematic Mixed (MID 140526) ---
$$ High-strength Al-Mg, LNG tanks
$$ Temper: H116
$$ Source: ASTM B928
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=215.0 MPa, ETAN=573.5 MPa, eps_f=0.16
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al5083-H116 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140526 2.660e-09   70300.0    0.3300    215.00    573.46    0.5000
$      SRC       SRP        FS        VP
    6500.0       4.0    0.1600       1.0
$
$$ --- Al6061-T6 Kinematic Mixed (MID 140535) ---
$$ Al-Mg-Si general structural (most common)
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5; precipitation hardened rate-insensitive
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=276.0 MPa, ETAN=293.1 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6061-T6 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140535 2.700e-09   68900.0    0.3300    276.00    293.12    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al6063-T5 Kinematic Mixed (MID 140536) ---
$$ Extrusion alloy, windows/frames
$$ Temper: T5
$$ Source: ASTM B221
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=145.0 MPa, ETAN=347.8 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6063-T5 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140536 2.700e-09   68900.0    0.3300    145.00    347.77    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al6063-T6 Kinematic Mixed (MID 140537) ---
$$ T6 heat-treated 6063 extrusion
$$ Temper: T6
$$ Source: ASTM B221
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=214.0 MPa, ETAN=231.0 MPa, eps_f=0.12
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al6063-T6 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140537 2.700e-09   68900.0    0.3300    214.00    230.98    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1200       1.0
$
$$ --- Al7050-T7451 Kinematic Mixed (MID 140538) ---
$$ Al-Zn aerospace, stress-corrosion resistant
$$ Temper: T7451
$$ Source: ASTM B209, MIL-HDBK-5
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=469.0 MPa, ETAN=531.6 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al7050-T7451 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140538 2.830e-09   71700.0    0.3300    469.00    531.61    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1100       1.0
$
$$ --- Al7075-T6 Kinematic Mixed (MID 140539) ---
$$ Highest-strength Al-Zn aerospace
$$ Temper: T6
$$ Source: ASTM B209, MIL-HDBK-5
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=503.0 MPa, ETAN=670.0 MPa, eps_f=0.11
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
Al7075-T6 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140539 2.810e-09   71700.0    0.3300    503.00    670.00    0.5000
$      SRC       SRP        FS        VP
 1288000.0       4.0    0.1100       1.0
$
$$ --- ADC12_diecast Kinematic Mixed (MID 140540) ---
$$ Die-cast Al-Si-Cu (smartphone frames)
$$ Temper: As-cast
$$ Source: JIS H 5302, Nadca handbook; porosity raises damping
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=150.0 MPa, ETAN=6990.8 MPa, eps_f=0.025
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
ADC12_diecast Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140540 2.700e-09   71000.0    0.3300    150.00   6990.77    0.5000
$      SRC       SRP        FS        VP
    1500.0       4.0    0.0250       1.0
$
*END
