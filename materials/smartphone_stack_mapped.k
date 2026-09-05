*KEYWORD
$ 대표 스마트폰 스택 (이름 기반 matdb 매핑): 소성 금속 + 점탄성 접착/PCB/폼
*SECTION_SOLID
$    secid    elform
         1         1
*PART
MIDFRAME
$      pid     secid       mid
         1         1         1
*PART
HOUSING
$      pid     secid       mid
         2         1         2
*PART
BRACKET
$      pid     secid       mid
         3         1         3
*PART
SIDEKEY
$      pid     secid       mid
         4         1         4
*PART
DISPLAY_OCA
$      pid     secid       mid
         5         1         5
*PART
TOUCH_PSA
$      pid     secid       mid
         6         1         6
*PART
MAIN_PCB
$      pid     secid       mid
         7         1         7
*PART
BATTERY
$      pid     secid       mid
         8         1         8
*PART
FOAM
$      pid     secid       mid
         9         1         9
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
AL7003H
$      MID       RHO         E        PR      SIGY      ETAN      FAIL      TDEL
         12.7000E-09   63100.0    0.3300     126.2                              
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS304_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
         2 8.000e-09  193000.0    0.2900    215.00    727.02    0.4000      0.00
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
$
$ Damping for MID 2 (alpha scale=1.000000 floor=0.000000)
*SET_PART_LIST_TITLE
SUS304_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    800002       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         2         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    800002         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    800002 7.958e-07
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS301_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
         3 7.880e-09  193000.0    0.3000    275.00   1041.21    0.4000      0.00
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
$
$ Damping for MID 3 (alpha scale=1.000000 floor=0.000000)
*SET_PART_LIST_TITLE
SUS301_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    800003       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         3         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    800003         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    800003 7.958e-07
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SUS201_annealed Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
         4 7.800e-09  200000.0    0.3000    260.00    990.72    0.4000      0.00
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
$
$ Damping for MID 4 (alpha scale=1.000000 floor=0.000000)
*SET_PART_LIST_TITLE
SUS201_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    800004       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         4         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    800004         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    800004 7.958e-07
$
*MAT_VISCOELASTIC_TITLE
OCA Rigid Standard (3M 8171)
$      MID        RO      BULK        G0        GI      BETA
         5 1.050e-09    2.5000    0.1500    0.0150      50.0
$
$$ [DB] PID slot holds MID=100001 (external tool must replace with actual PART IDs)
$$ CTE=80 ppm/K (polymer standard value)
*MAT_VISCOELASTIC_TITLE
PSA Acrylic General (3M 467MP)
$      MID        RO      BULK        G0        GI      BETA
         6 1.100e-09    5.0000    0.3000    0.0500     100.0
$
$$ [DB] PID slot holds MID=100006 (external tool must replace with actual PART IDs)
$$ CTE=85 ppm/K (polymer standard value)
*MAT_VISCOELASTIC_TITLE
PPG FR-4 Standard (Tg 130C)
$      MID        RO      BULK        G0        GI      BETA
         7 1.850e-09   12222.2    9540.7    8807.3     500.0
$
$$ [DB] PID slot holds MID=100101 (external tool must replace with actual PART IDs)
*MAT_VISCOELASTIC_TITLE
Battery Stretch-Release (SIS)
$      MID        RO      BULK        G0        GI      BETA
         8 1.000e-09    6.2500    0.5000    0.1000     200.0
$
$$ [DB] PID slot holds MID=100014 (external tool must replace with actual PART IDs)
$$ CTE=130 ppm/K (polymer standard value)
*MAT_VISCOELASTIC_TITLE
Foam PE General
$      MID        RO      BULK        G0        GI      BETA
         9 5.000e-10    0.1667    0.0500    0.0050      20.0
$
$$ [DB] PID slot holds MID=100012 (external tool must replace with actual PART IDs)
$$ CTE=200 ppm/K (polymer standard value)
*NODE
*END
