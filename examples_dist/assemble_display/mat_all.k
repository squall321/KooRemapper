$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8
$ mat_all.k - LS-DYNA Material Keyword File
$ Unit System: mm, s, ton, N, MPa
$ Generated from MaterialKeyword.txt
$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8
*KEYWORD
$
$ ====================================================================
$  [1] FTG_R - Flexible Thin Glass / Rigid
$      E=70000 MPa, PR=0.22, rho=2.50 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
FTG_R
$#     mid        ro         e        pr        da        db  not used
         1 2.500E-09 7.000E+04 2.200E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [2] FTG_F - Flexible Thin Glass / Flexible Film
$      E=3000 MPa, PR=0.34, rho=1.35 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
FTG_F
$#     mid        ro         e        pr        da        db  not used
         2 1.350E-09 3.000E+03 3.400E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [3] CU - Copper (Rolled Annealed)
$      E=110000 MPa, PR=0.34, SIGY=250 MPa, ETAN=1000 MPa
$      rho=8.90 g/cm3
$ ====================================================================
*MAT_PLASTIC_KINEMATIC_TITLE
CU
$#     mid        ro         e        pr      sigy      etan      beta
         3 8.900E-09 1.100E+05 3.400E-01 2.500E+02 1.000E+03       0.0
$#     src       srp        fs        vp
       0.0       0.0       0.0       0.0
$
$ ====================================================================
$  [4] Panel-F - Panel Film (PET/COP based)
$      E=3300 MPa, PR=0.25, rho=1.42 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
Panel-F
$#     mid        ro         e        pr        da        db  not used
         4 1.420E-09 3.300E+03 2.500E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [5] Panel-PI - Panel Polyimide
$      E=3000 MPa, PR=0.34, rho=1.42 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
Panel-PI
$#     mid        ro         e        pr        da        db  not used
         5 1.420E-09 3.000E+03 3.400E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [6] BarrierPI - Barrier Polyimide Film
$      E=3000 MPa, PR=0.34, rho=1.40 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
BarrierPI
$#     mid        ro         e        pr        da        db  not used
         6 1.400E-09 3.000E+03 3.400E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [7] POL - Polyolefin Film (MAT_006)
$      BULK=2200, G0=470, GI=200, BETA=500
$      rho=1.20 g/cm3, K/G0=4.7
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
POL
$#     mid        ro      bulk        g0        gi      beta
         7 1.200E-09 2.200E+03 4.700E+02 2.000E+02 5.000E+02
$
$ ====================================================================
$  [8] P-film - Protective Film (PET based, MAT_006)
$      BULK=3300, G0=700, GI=300, BETA=500
$      rho=1.39 g/cm3, K/G0=4.7
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
P-film
$#     mid        ro      bulk        g0        gi      beta
         8 1.390E-09 3.300E+03 7.000E+02 3.000E+02 5.000E+02
$
$ ====================================================================
$  [9] PL - Polarizer Film (MAT_006)
$      BULK=5600, G0=1190, GI=510, BETA=500
$      rho=1.35 g/cm3, K/G0=4.7
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
PL
$#     mid        ro      bulk        g0        gi      beta
         9 1.350E-09 5.600E+03 1.190E+03 5.100E+02 5.000E+02
$
$ ====================================================================
$  [10] Lattice - Lattice/Spacer Structure
$       E=3000 MPa, PR=0.30, rho=1.50 g/cm3
$ ====================================================================
*MAT_ELASTIC_TITLE
Lattice
$#     mid        ro         e        pr        da        db  not used
        10 1.500E-09 3.000E+03 3.000E-01       0.0       0.0       0.0
$
$ ====================================================================
$  [11] TPU - Thermoplastic Polyurethane (MAT_006)
$       BULK=3000, G0=47, GI=20, BETA=2000
$       rho=1.58 g/cm3, K/G0=63.8
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
TPU
$#     mid        ro      bulk        g0        gi      beta
        11 1.580E-09 3.000E+03 4.700E+01 2.000E+01 2.000E+03
$
$ ====================================================================
$  [12] PSA - Pressure Sensitive Adhesive (MAT_006)
$       BULK=500, G0=20, GI=0.5, BETA=1000
$       rho=1.10 g/cm3, K/G0=25.0
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
PSA
$#     mid        ro      bulk        g0        gi      beta
        12 1.100E-09 5.000E+02 2.000E+01 5.000E-01 1.000E+03
$
$ ====================================================================
$  [13] OCA - Optically Clear Adhesive (MAT_006)
$       BULK=400, G0=10, GI=0.3, BETA=1000
$       rho=1.05 g/cm3, K/G0=40.0
$ ====================================================================
*MAT_VISCOELASTIC_TITLE
OCA
$#     mid        ro      bulk        g0        gi      beta
        13 1.050E-09 4.000E+02 1.000E+01 3.000E-01 1.000E+03
$
$
$ ####################################################################
$ ##  ADVANCED: MAT_GENERAL_VISCOELASTIC (*MAT_076)                 ##
$ ##  6-Term Prony Series for Broadband Drop Damping                ##
$ ####################################################################
$
$ ====================================================================
$  [14] PSA_ADV - PSA Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=800, K(0)=2000 MPa (K0/Kinf=2.5x)
$       G_inf=0.3, G(0)=162.3 MPa
$       rho=1.10 g/cm3
$
$       K/G ratio over time (with bulk relaxation):
$         t=0ms:  K=2000, G=162.3 -> K/G=12.3
$         t=1ms:  K=1255, G=35.5  -> K/G=35.4  (was 56.3 without Ki)
$         t=5ms:  K=985,  G=16.4  -> K/G=60.1  (was 122)
$         t=50ms: K=802,  G=5.3   -> K/G=151   (was 377)
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
PSA_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        14 1.100E-09 8.000E+02       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 3.000E-01       0.0       0.0       0.0
 2.000E+00 1.000E+00 5.000E+01 1.000E+00
 5.000E+00 1.000E+01 1.000E+02 1.000E+01
 1.500E+01 1.000E+02 2.500E+02 1.000E+02
 4.000E+01 1.000E+03 4.500E+02 1.000E+03
 1.000E+02 1.000E+04 3.500E+02 1.000E+04
$
$ ====================================================================
$  [15] OCA_ADV - OCA Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=700, K(0)=2000 MPa (K0/Kinf=2.86x)
$       G_inf=0.1, G(0)=82.1 MPa
$       rho=1.05 g/cm3
$
$       K/G ratio over time:
$         t=0ms:  K=2000, G=82.1  -> K/G=24.4
$         t=1ms:  K=1192, G=18.7  -> K/G=63.7  (was 107)
$         t=5ms:  K=886,  G=8.9   -> K/G=99.6  (was 225)
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
OCA_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        15 1.050E-09 7.000E+02       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 1.000E-01       0.0       0.0       0.0
 1.000E+00 1.000E+00 5.000E+01 1.000E+00
 3.000E+00 1.000E+01 1.000E+02 1.000E+01
 8.000E+00 1.000E+02 3.000E+02 1.000E+02
 2.000E+01 1.000E+03 5.000E+02 1.000E+03
 5.000E+01 1.000E+04 3.500E+02 1.000E+04
$
$ ====================================================================
$  [16] TPU_ADV - TPU Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=1500, K(0)=3000 MPa (K0/Kinf=2.0x)
$       G_inf=5.0, G(0)=48.0 MPa
$       rho=1.58 g/cm3
$       Note: TPU at 25C is 65C above Tg, limited bulk relaxation
$
$       K/G ratio over time:
$         t=0ms:  K=3000, G=48.0  -> K/G=62.5
$         t=1ms:  K=2089, G=9.6   -> K/G=218   (was 312)
$         t=5ms:  K=1710, G=7.2   -> K/G=238   (was 417)
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
TPU_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        16 1.580E-09 1.500E+03       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 5.000E+00       0.0       0.0       0.0
 1.000E+00 1.000E+01 1.000E+02 1.000E+01
 2.000E+00 1.000E+02 2.500E+02 1.000E+02
 5.000E+00 1.000E+03 5.000E+02 1.000E+03
 1.000E+01 1.000E+04 4.000E+02 1.000E+04
 2.500E+01 1.000E+05 2.500E+02 1.000E+05
$
$ ====================================================================
$  [17] POL_ADV - Polyolefin Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=1600, K(0)=2200 MPa (K0/Kinf=1.38x, semi-crystalline)
$       G_inf=150.0, G(0)=470.0 MPa
$       rho=1.20 g/cm3
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
POL_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        17 1.200E-09 1.600E+03       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 1.500E+02       0.0       0.0       0.0
 3.000E+01 1.000E+00 3.000E+01 1.000E+00
 6.000E+01 1.000E+01 7.000E+01 1.000E+01
 8.000E+01 1.000E+02 1.500E+02 1.000E+02
 1.000E+02 1.000E+03 2.500E+02 1.000E+03
 5.000E+01 1.000E+04 1.000E+02 1.000E+04
$
$ ====================================================================
$  [18] P-film_ADV - Protective Film Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=2400, K(0)=3300 MPa (K0/Kinf=1.38x, PET semi-crystalline)
$       G_inf=220.0, G(0)=700.0 MPa
$       rho=1.39 g/cm3
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
P-film_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        18 1.390E-09 2.400E+03       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 2.200E+02       0.0       0.0       0.0
 5.000E+01 1.000E+00 5.000E+01 1.000E+00
 9.000E+01 1.000E+01 1.000E+02 1.000E+01
 1.200E+02 1.000E+02 2.000E+02 1.000E+02
 1.500E+02 1.000E+03 3.500E+02 1.000E+03
 7.000E+01 1.000E+04 2.000E+02 1.000E+04
$
$ ====================================================================
$  [19] PL_ADV - Polarizer Film Advanced (*MAT_076) with Bulk Relaxation
$       K_inf=4000, K(0)=5600 MPa (K0/Kinf=1.40x, PVA/TAC)
$       G_inf=380.0, G(0)=1190.0 MPa
$       rho=1.35 g/cm3
$ ====================================================================
*MAT_GENERAL_VISCOELASTIC_TITLE
PL_ADV
$#     mid        ro      bulk       pcf        ef      tref         a         b
        19 1.350E-09 4.000E+03       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 3.800E+02       0.0       0.0       0.0
 8.000E+01 1.000E+00 8.000E+01 1.000E+00
 1.500E+02 1.000E+01 1.700E+02 1.000E+01
 2.000E+02 1.000E+02 3.500E+02 1.000E+02
 2.500E+02 1.000E+03 6.000E+02 1.000E+03
 1.300E+02 1.000E+04 4.000E+02 1.000E+04
$
*END
