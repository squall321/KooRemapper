$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_086) — PCB_4L_HDI_Smartphone
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Generated from layup: 4층 스마트폰 HDI 메인보드 (DS-8402H + ED Cu)
$ Total thickness: 506.0 um (0.5060 mm)
$
$ Layup composition (top -> bottom):
$   L1: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.35)
$   L2: Doosan DS-8402H                     PPG  100.0 um
$   L3: Cu Electrodeposited Standard (Rigid PCB) Cu   35.0 um  (eta=0.90)
$   L4: Doosan DS-7402LC                    PPG  200.0 um
$   L5: Cu Electrodeposited Standard (Rigid PCB) Cu   35.0 um  (eta=0.88)
$   L6: Doosan DS-8402H                     PPG  100.0 um
$   L7: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.35)
$
$ Equivalent orthotropic properties:
$   E_a = E_b (in-plane) =    40669.2 MPa =  40.67 GPa
$   E_c     (through)   =    12298.2 MPa =  12.30 GPa
$   nu_ba (in-plane)    = 0.2025
$   nu_ca (through)     = 0.3059
$   G_ab (in-plane)     =    16485.1 MPa
$   G_bc = G_ca         =     4722.5 MPa
$   rho                 = 2.9752e-09 ton/mm^3 (2.975 g/cc)
$   BULK                =    30326.3 MPa
$   Visco G0            =    16592.5 MPa
$   Visco GI            =    16098.6 MPa
$   Visco BETA          = 800.0 /s  (tau=1.25 ms)
$   CTE_a = CTE_b       =  14.06 ppm/K
$   CTE_c               =  25.98 ppm/K
$
$ Calculation methodology:
$   In-plane (a,b): Rule of Mixture (Voigt) — thickness-weighted E
$   Through (c):    Reuss (series) — compliance average
$   CTE in-plane:   E-weighted Schapery-like average
$   CTE through:    Thickness-weighted free expansion
$   Cu gap filling: Non-Cu area replaced by adjacent PPG resin
$ ========================================================================
*KEYWORD
$
$$ PCB_4L_HDI_Smartphone
$$ 4층 스마트폰 HDI 메인보드 (DS-8402H + ED Cu)
*MAT_ORTHOTROPIC_VISCOELASTIC_TITLE
PCB_4L_HDI_Smartphone
$      MID        RO        EA        EB      PRBA       GAB       GBC       GCA
    200002 2.975e-09   40669.2   40669.2    0.2025   16485.1    4722.5    4722.5
$     AOPT         K        G0      GINF      BETA     REF
       0.0   30326.3   16592.5   16098.6     800.0       0.0
$       XP        YP        ZP        A1        A2        A3
       0.0       0.0       0.0       0.0       0.0       0.0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ Orthotropic thermal expansion (separate x/y/z)
$$ [DB] PID slot holds MID=200002 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200002         0 1.406e-05         0 1.406e-05         0 2.598e-05
$
*END
