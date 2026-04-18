$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_086) — PCB_8L_043T_DS7402_EM370Z
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Generated from layup: 8층 HDI 0.43mm — DS-7402 series + EM-370Z, ED Cu
$ Total thickness: 430.0 um (0.4300 mm)
$
$ Layup composition (top -> bottom):
$   L1: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$   L2: Elite EM-370Z                       PPG   35.0 um
$   L3: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L4: Doosan DS-7402H                     PPG   45.0 um
$   L5: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L6: Doosan DS-7402H                     PPG   45.0 um
$   L7: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L8: Doosan DS-7402LC                    PPG   72.0 um
$   L9: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L10: Doosan DS-7402H                     PPG   45.0 um
$   L11: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L12: Doosan DS-7402H                     PPG   45.0 um
$   L13: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L14: Elite EM-370Z                       PPG   35.0 um
$   L15: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$
$ Equivalent orthotropic properties:
$   E_a = E_b (in-plane) =    40161.5 MPa =  40.16 GPa
$   E_c     (through)   =    11639.1 MPa =  11.64 GPa
$   nu_ba (in-plane)    = 0.1985
$   nu_ca (through)     = 0.3065
$   G_ab (in-plane)     =    16301.0 MPa
$   G_bc = G_ca         =     4467.8 MPa
$   rho                 = 3.0465e-09 ton/mm^3 (3.046 g/cc)
$   BULK                =    30647.8 MPa
$   Visco G0            =    16342.1 MPa
$   Visco GI            =    15877.4 MPa
$   Visco BETA          = 955.3 /s  (tau=1.05 ms)
$   CTE_a = CTE_b       =  14.20 ppm/K
$   CTE_c               =  32.08 ppm/K
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
$$ PCB_8L_043T_DS7402_EM370Z
$$ 8층 HDI 0.43mm — DS-7402 series + EM-370Z, ED Cu
*MAT_ORTHOTROPIC_VISCOELASTIC_TITLE
PCB_8L_043T_DS7402_EM370Z
$      MID        RO        EA        EB      PRBA       GAB       GBC       GCA
    200008 3.046e-09   40161.5   40161.5    0.1985   16301.0    4467.8    4467.8
$     AOPT         K        G0      GINF      BETA     REF
       0.0   30647.8   16342.1   15877.4     955.3       0.0
$       XP        YP        ZP        A1        A2        A3
       0.0       0.0       0.0       0.0       0.0       0.0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ Orthotropic thermal expansion (separate x/y/z)
$$ [DB] PID slot holds MID=200008 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200008         0 1.420e-05         0 1.420e-05         0 3.208e-05
$
*END
