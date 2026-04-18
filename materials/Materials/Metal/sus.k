$ ========================================================================
$ SUS METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: SUS — Stainless Steel Alloys
$ MID: 100501~100520 (bi), 110501~110520 (multi)
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
$   100501  110501     130501    140501   SUS201_annealed           260    655
$   100502  110502     130502    140502   SUS301_annealed           275    690
$   100503  110503     130503    140503   SUS304_annealed           215    505
$   100504  110504     130504    140504   SUS304L_annealed          205    485
$   100505  110505     130505    140505   SUS316_annealed           240    550
$   100506  110506     130506    140506   SUS316L_annealed          220    520
$   100507  110507     130507    140507   SUS410_annealed           275    485
$   100508  110508     130508    140508   SUS420_annealed           345    655
$   100509  110509     130509    140509   SUS430_annealed           205    450
$   100510  110510     130510    140510   SUS_17-4PH_H900          1170   1310
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- SUS201_annealed Bilinear (MID 100501) ---
$$ Low-Ni austenitic, economic grade
$$ Temper: Annealed
$$ Source: ASTM A666, AISI 201, MatWeb
$$ rho=7.8 g/cc, E=200.0 GPa, nu=0.3
$$ sigy=260.0 MPa, sigu=655.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 990.7 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS201_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100501 7.800e-09  200000.0    0.3000    260.00    990.72    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS301_annealed Bilinear (MID 100502) ---
$$ High-strength spring austenitic
$$ Temper: Annealed
$$ Source: AISI 301, ASM Handbook
$$ rho=7.88 g/cc, E=193.0 GPa, nu=0.3
$$ sigy=275.0 MPa, sigu=690.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1041.2 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS301_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100502 7.880e-09  193000.0    0.3000    275.00   1041.21    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS304_annealed Bilinear (MID 100503) ---
$$ Most common austenitic stainless steel
$$ Temper: Annealed
$$ Source: AISI 304, ASTM A240, MatWeb
$$ rho=8.0 g/cc, E=193.0 GPa, nu=0.29
$$ sigy=215.0 MPa, sigu=505.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 727.0 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS304_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100503 8.000e-09  193000.0    0.2900    215.00    727.02    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS304L_annealed Bilinear (MID 100504) ---
$$ Low-carbon 304, weld-friendly
$$ Temper: Annealed
$$ Source: AISI 304L, ASTM A240
$$ rho=8.0 g/cc, E=193.0 GPa, nu=0.29
$$ sigy=205.0 MPa, sigu=485.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 701.9 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS304L_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100504 8.000e-09  193000.0    0.2900    205.00    701.86    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS316_annealed Bilinear (MID 100505) ---
$$ Mo-bearing austenitic, corrosion resistant
$$ Temper: Annealed
$$ Source: AISI 316, ASTM A240
$$ rho=8.0 g/cc, E=193.0 GPa, nu=0.3
$$ sigy=240.0 MPa, sigu=550.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 777.4 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS316_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100505 8.000e-09  193000.0    0.3000    240.00    777.42    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS316L_annealed Bilinear (MID 100506) ---
$$ Low-carbon 316, medical/weld
$$ Temper: Annealed
$$ Source: AISI 316L, ASTM A240, Hsu&Jones 2004 (CS)
$$ rho=8.0 g/cc, E=193.0 GPa, nu=0.3
$$ sigy=220.0 MPa, sigu=520.0 MPa, eps_f=0.4
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 752.1 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS316L_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100506 8.000e-09  193000.0    0.3000    220.00    752.14    0.4000      0.00
$        C         P      LCSS      LCSR        VP
      50.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS410_annealed Bilinear (MID 100507) ---
$$ Martensitic, hardenable
$$ Temper: Annealed
$$ Source: AISI 410, ASTM A240
$$ rho=7.74 g/cc, E=200.0 GPa, nu=0.3
$$ sigy=275.0 MPa, sigu=485.0 MPa, eps_f=0.22
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 960.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS410_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100507 7.740e-09  200000.0    0.3000    275.00    960.55    0.2200      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS420_annealed Bilinear (MID 100508) ---
$$ High-C martensitic, knife/mold
$$ Temper: Annealed
$$ Source: AISI 420, ASM Handbook
$$ rho=7.75 g/cc, E=200.0 GPa, nu=0.29
$$ sigy=345.0 MPa, sigu=655.0 MPa, eps_f=0.2
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1563.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS420_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100508 7.750e-09  200000.0    0.2900    345.00   1563.49    0.2000      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS430_annealed Bilinear (MID 100509) ---
$$ Ferritic, magnetic
$$ Temper: Annealed
$$ Source: AISI 430, ASTM A240
$$ rho=7.7 g/cc, E=200.0 GPa, nu=0.3
$$ sigy=205.0 MPa, sigu=450.0 MPa, eps_f=0.22
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1118.8 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS430_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100509 7.700e-09  200000.0    0.3000    205.00   1118.85    0.2200      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SUS_17-4PH_H900 Bilinear (MID 100510) ---
$$ Precipitation hardening, high strength
$$ Temper: H900 (aged)
$$ Source: AMS 5643, ASM Handbook
$$ rho=7.8 g/cc, E=196.0 GPa, nu=0.272
$$ sigy=1170.0 MPa, sigu=1310.0 MPa, eps_f=0.14
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 1044.5 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS_17-4PH_H900 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100510 7.800e-09  196000.0    0.2720   1170.00   1044.54    0.1400      0.00
$        C         P      LCSS      LCSR        VP
    3200.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- SUS201_annealed Multilinear (MID 110501) ---
$$ Low-Ni austenitic, economic grade
$$ Temper: Annealed
$$ Source: ASTM A666, AISI 201, MatWeb
$$ LCSS curve: 7 points, LCID=110501
*DEFINE_CURVE_TITLE
SUS201_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110501         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.6000000000e+02
    2.0000000000e-02    3.4000000000e+02
    5.0000000000e-02    4.2000000000e+02
    1.0000000000e-01    5.1000000000e+02
    2.0000000000e-01    6.0000000000e+02
    3.0000000000e-01    6.4000000000e+02
    4.0000000000e-01    6.5500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS201_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110501 7.800e-09  200000.0    0.3000      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0    110501         0       1.0
$
$$ --- SUS301_annealed Multilinear (MID 110502) ---
$$ High-strength spring austenitic
$$ Temper: Annealed
$$ Source: AISI 301, ASM Handbook
$$ LCSS curve: 7 points, LCID=110502
*DEFINE_CURVE_TITLE
SUS301_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110502         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.7500000000e+02
    2.0000000000e-02    3.6000000000e+02
    5.0000000000e-02    4.4500000000e+02
    1.0000000000e-01    5.3500000000e+02
    2.0000000000e-01    6.2500000000e+02
    3.0000000000e-01    6.7500000000e+02
    4.0000000000e-01    6.9000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS301_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110502 7.880e-09  193000.0    0.3000      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0    110502         0       1.0
$
$$ --- SUS304_annealed Multilinear (MID 110503) ---
$$ Most common austenitic stainless steel
$$ Temper: Annealed
$$ Source: AISI 304, ASTM A240, MatWeb
$$ LCSS curve: 7 points, LCID=110503
*DEFINE_CURVE_TITLE
SUS304_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110503         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.1500000000e+02
    2.0000000000e-02    2.8000000000e+02
    5.0000000000e-02    3.4000000000e+02
    1.0000000000e-01    4.0000000000e+02
    2.0000000000e-01    4.6000000000e+02
    3.0000000000e-01    4.9000000000e+02
    4.0000000000e-01    5.0500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS304_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110503 8.000e-09  193000.0    0.2900      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0    110503         0       1.0
$
$$ --- SUS304L_annealed Multilinear (MID 110504) ---
$$ Low-carbon 304, weld-friendly
$$ Temper: Annealed
$$ Source: AISI 304L, ASTM A240
$$ LCSS curve: 7 points, LCID=110504
*DEFINE_CURVE_TITLE
SUS304L_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110504         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.0500000000e+02
    2.0000000000e-02    2.6500000000e+02
    5.0000000000e-02    3.2500000000e+02
    1.0000000000e-01    3.8000000000e+02
    2.0000000000e-01    4.4000000000e+02
    3.0000000000e-01    4.7000000000e+02
    4.0000000000e-01    4.8500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS304L_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110504 8.000e-09  193000.0    0.2900      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0    110504         0       1.0
$
$$ --- SUS316_annealed Multilinear (MID 110505) ---
$$ Mo-bearing austenitic, corrosion resistant
$$ Temper: Annealed
$$ Source: AISI 316, ASTM A240
$$ LCSS curve: 7 points, LCID=110505
*DEFINE_CURVE_TITLE
SUS316_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110505         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.4000000000e+02
    2.0000000000e-02    3.1000000000e+02
    5.0000000000e-02    3.7500000000e+02
    1.0000000000e-01    4.4000000000e+02
    2.0000000000e-01    5.1000000000e+02
    3.0000000000e-01    5.4000000000e+02
    4.0000000000e-01    5.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS316_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110505 8.000e-09  193000.0    0.3000      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     100.0      10.0    110505         0       1.0
$
$$ --- SUS316L_annealed Multilinear (MID 110506) ---
$$ Low-carbon 316, medical/weld
$$ Temper: Annealed
$$ Source: AISI 316L, ASTM A240, Hsu&Jones 2004 (CS)
$$ LCSS curve: 7 points, LCID=110506
*DEFINE_CURVE_TITLE
SUS316L_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110506         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.2000000000e+02
    2.0000000000e-02    2.8500000000e+02
    5.0000000000e-02    3.4500000000e+02
    1.0000000000e-01    4.1000000000e+02
    2.0000000000e-01    4.7500000000e+02
    3.0000000000e-01    5.1000000000e+02
    4.0000000000e-01    5.2000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS316L_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110506 8.000e-09  193000.0    0.3000      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
      50.0       5.0    110506         0       1.0
$
$$ --- SUS410_annealed Multilinear (MID 110507) ---
$$ Martensitic, hardenable
$$ Temper: Annealed
$$ Source: AISI 410, ASTM A240
$$ LCSS curve: 6 points, LCID=110507
*DEFINE_CURVE_TITLE
SUS410_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110507         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.7500000000e+02
    2.0000000000e-02    3.5000000000e+02
    5.0000000000e-02    4.1000000000e+02
    1.0000000000e-01    4.5000000000e+02
    1.5000000000e-01    4.7500000000e+02
    2.2000000000e-01    4.8500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS410_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110507 7.740e-09  200000.0    0.3000      0.00      0.00    0.2200      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0    110507         0       1.0
$
$$ --- SUS420_annealed Multilinear (MID 110508) ---
$$ High-C martensitic, knife/mold
$$ Temper: Annealed
$$ Source: AISI 420, ASM Handbook
$$ LCSS curve: 6 points, LCID=110508
*DEFINE_CURVE_TITLE
SUS420_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110508         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.4500000000e+02
    2.0000000000e-02    4.4000000000e+02
    5.0000000000e-02    5.2000000000e+02
    1.0000000000e-01    5.8500000000e+02
    1.5000000000e-01    6.3000000000e+02
    2.0000000000e-01    6.5500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS420_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110508 7.750e-09  200000.0    0.2900      0.00      0.00    0.2000      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0    110508         0       1.0
$
$$ --- SUS430_annealed Multilinear (MID 110509) ---
$$ Ferritic, magnetic
$$ Temper: Annealed
$$ Source: AISI 430, ASTM A240
$$ LCSS curve: 6 points, LCID=110509
*DEFINE_CURVE_TITLE
SUS430_annealed true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110509         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.0500000000e+02
    2.0000000000e-02    2.7500000000e+02
    5.0000000000e-02    3.4000000000e+02
    1.0000000000e-01    3.9500000000e+02
    1.5000000000e-01    4.3000000000e+02
    2.2000000000e-01    4.5000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS430_annealed Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110509 7.700e-09  200000.0    0.3000      0.00      0.00    0.2200      0.00
$        C         P      LCSS      LCSR        VP
      40.0       5.0    110509         0       1.0
$
$$ --- SUS_17-4PH_H900 Multilinear (MID 110510) ---
$$ Precipitation hardening, high strength
$$ Temper: H900 (aged)
$$ Source: AMS 5643, ASM Handbook
$$ LCSS curve: 6 points, LCID=110510
*DEFINE_CURVE_TITLE
SUS_17-4PH_H900 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110510         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    1.1700000000e+03
    1.0000000000e-02    1.2200000000e+03
    2.0000000000e-02    1.2500000000e+03
    5.0000000000e-02    1.2850000000e+03
    1.0000000000e-01    1.3050000000e+03
    1.4000000000e-01    1.3100000000e+03
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS_17-4PH_H900 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110510 7.800e-09  196000.0    0.2720      0.00      0.00    0.1400      0.00
$        C         P      LCSS      LCSR        VP
    3200.0       5.0    110510         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- SUS201_annealed Kinematic Pure (MID 130501) ---
$$ Low-Ni austenitic, economic grade
$$ Temper: Annealed
$$ Source: ASTM A666, AISI 201, MatWeb
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=260.0 MPa, ETAN=990.7 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS201_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130501 7.800e-09  200000.0    0.3000    260.00    990.72    0.0000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS301_annealed Kinematic Pure (MID 130502) ---
$$ High-strength spring austenitic
$$ Temper: Annealed
$$ Source: AISI 301, ASM Handbook
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=1041.2 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS301_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130502 7.880e-09  193000.0    0.3000    275.00   1041.21    0.0000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS304_annealed Kinematic Pure (MID 130503) ---
$$ Most common austenitic stainless steel
$$ Temper: Annealed
$$ Source: AISI 304, ASTM A240, MatWeb
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=215.0 MPa, ETAN=727.0 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS304_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130503 8.000e-09  193000.0    0.2900    215.00    727.02    0.0000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS304L_annealed Kinematic Pure (MID 130504) ---
$$ Low-carbon 304, weld-friendly
$$ Temper: Annealed
$$ Source: AISI 304L, ASTM A240
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=205.0 MPa, ETAN=701.9 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS304L_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130504 8.000e-09  193000.0    0.2900    205.00    701.86    0.0000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS316_annealed Kinematic Pure (MID 130505) ---
$$ Mo-bearing austenitic, corrosion resistant
$$ Temper: Annealed
$$ Source: AISI 316, ASTM A240
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=240.0 MPa, ETAN=777.4 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS316_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130505 8.000e-09  193000.0    0.3000    240.00    777.42    0.0000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS316L_annealed Kinematic Pure (MID 130506) ---
$$ Low-carbon 316, medical/weld
$$ Temper: Annealed
$$ Source: AISI 316L, ASTM A240, Hsu&Jones 2004 (CS)
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=220.0 MPa, ETAN=752.1 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS316L_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130506 8.000e-09  193000.0    0.3000    220.00    752.14    0.0000
$      SRC       SRP        FS        VP
      50.0       5.0    0.4000       1.0
$
$$ --- SUS410_annealed Kinematic Pure (MID 130507) ---
$$ Martensitic, hardenable
$$ Temper: Annealed
$$ Source: AISI 410, ASTM A240
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=960.5 MPa, eps_f=0.22
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS410_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130507 7.740e-09  200000.0    0.3000    275.00    960.55    0.0000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2200       1.0
$
$$ --- SUS420_annealed Kinematic Pure (MID 130508) ---
$$ High-C martensitic, knife/mold
$$ Temper: Annealed
$$ Source: AISI 420, ASM Handbook
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=345.0 MPa, ETAN=1563.5 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS420_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130508 7.750e-09  200000.0    0.2900    345.00   1563.49    0.0000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2000       1.0
$
$$ --- SUS430_annealed Kinematic Pure (MID 130509) ---
$$ Ferritic, magnetic
$$ Temper: Annealed
$$ Source: AISI 430, ASTM A240
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=205.0 MPa, ETAN=1118.8 MPa, eps_f=0.22
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS430_annealed Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130509 7.700e-09  200000.0    0.3000    205.00   1118.85    0.0000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2200       1.0
$
$$ --- SUS_17-4PH_H900 Kinematic Pure (MID 130510) ---
$$ Precipitation hardening, high strength
$$ Temper: H900 (aged)
$$ Source: AMS 5643, ASM Handbook
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=1170.0 MPa, ETAN=1044.5 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS_17-4PH_H900 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130510 7.800e-09  196000.0    0.2720   1170.00   1044.54    0.0000
$      SRC       SRP        FS        VP
    3200.0       5.0    0.1400       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- SUS201_annealed Kinematic Mixed (MID 140501) ---
$$ Low-Ni austenitic, economic grade
$$ Temper: Annealed
$$ Source: ASTM A666, AISI 201, MatWeb
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=260.0 MPa, ETAN=990.7 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS201_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140501 7.800e-09  200000.0    0.3000    260.00    990.72    0.5000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS301_annealed Kinematic Mixed (MID 140502) ---
$$ High-strength spring austenitic
$$ Temper: Annealed
$$ Source: AISI 301, ASM Handbook
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=1041.2 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS301_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140502 7.880e-09  193000.0    0.3000    275.00   1041.21    0.5000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS304_annealed Kinematic Mixed (MID 140503) ---
$$ Most common austenitic stainless steel
$$ Temper: Annealed
$$ Source: AISI 304, ASTM A240, MatWeb
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=215.0 MPa, ETAN=727.0 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS304_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140503 8.000e-09  193000.0    0.2900    215.00    727.02    0.5000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS304L_annealed Kinematic Mixed (MID 140504) ---
$$ Low-carbon 304, weld-friendly
$$ Temper: Annealed
$$ Source: AISI 304L, ASTM A240
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=205.0 MPa, ETAN=701.9 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS304L_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140504 8.000e-09  193000.0    0.2900    205.00    701.86    0.5000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS316_annealed Kinematic Mixed (MID 140505) ---
$$ Mo-bearing austenitic, corrosion resistant
$$ Temper: Annealed
$$ Source: AISI 316, ASTM A240
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=240.0 MPa, ETAN=777.4 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS316_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140505 8.000e-09  193000.0    0.3000    240.00    777.42    0.5000
$      SRC       SRP        FS        VP
     100.0      10.0    0.4000       1.0
$
$$ --- SUS316L_annealed Kinematic Mixed (MID 140506) ---
$$ Low-carbon 316, medical/weld
$$ Temper: Annealed
$$ Source: AISI 316L, ASTM A240, Hsu&Jones 2004 (CS)
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=220.0 MPa, ETAN=752.1 MPa, eps_f=0.4
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS316L_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140506 8.000e-09  193000.0    0.3000    220.00    752.14    0.5000
$      SRC       SRP        FS        VP
      50.0       5.0    0.4000       1.0
$
$$ --- SUS410_annealed Kinematic Mixed (MID 140507) ---
$$ Martensitic, hardenable
$$ Temper: Annealed
$$ Source: AISI 410, ASTM A240
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=275.0 MPa, ETAN=960.5 MPa, eps_f=0.22
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS410_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140507 7.740e-09  200000.0    0.3000    275.00    960.55    0.5000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2200       1.0
$
$$ --- SUS420_annealed Kinematic Mixed (MID 140508) ---
$$ High-C martensitic, knife/mold
$$ Temper: Annealed
$$ Source: AISI 420, ASM Handbook
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=345.0 MPa, ETAN=1563.5 MPa, eps_f=0.2
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS420_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140508 7.750e-09  200000.0    0.2900    345.00   1563.49    0.5000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2000       1.0
$
$$ --- SUS430_annealed Kinematic Mixed (MID 140509) ---
$$ Ferritic, magnetic
$$ Temper: Annealed
$$ Source: AISI 430, ASTM A240
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=205.0 MPa, ETAN=1118.8 MPa, eps_f=0.22
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS430_annealed Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140509 7.700e-09  200000.0    0.3000    205.00   1118.85    0.5000
$      SRC       SRP        FS        VP
      40.0       5.0    0.2200       1.0
$
$$ --- SUS_17-4PH_H900 Kinematic Mixed (MID 140510) ---
$$ Precipitation hardening, high strength
$$ Temper: H900 (aged)
$$ Source: AMS 5643, ASM Handbook
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=1170.0 MPa, ETAN=1044.5 MPa, eps_f=0.14
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
SUS_17-4PH_H900 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140510 7.800e-09  196000.0    0.2720   1170.00   1044.54    0.5000
$      SRC       SRP        FS        VP
    3200.0       5.0    0.1400       1.0
$
*END
