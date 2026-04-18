$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_086) — PCB_10L_050T_DS7402_EM370Z
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Generated from layup: 10층 HDI 0.50mm — DS-7402 series + EM-370Z, ED Cu
$ Total thickness: 500.0 um (0.5000 mm)
$
$ Layup composition (top -> bottom):
$   L1: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$   L2: Elite EM-370Z                       PPG   30.0 um
$   L3: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L4: Doosan DS-7402H                     PPG   40.0 um
$   L5: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L6: Doosan DS-7402H                     PPG   40.0 um
$   L7: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L8: Doosan DS-7402H                     PPG   40.0 um
$   L9: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L10: Doosan DS-7402LC                    PPG   68.0 um
$   L11: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L12: Doosan DS-7402H                     PPG   40.0 um
$   L13: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L14: Doosan DS-7402H                     PPG   40.0 um
$   L15: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L16: Doosan DS-7402H                     PPG   40.0 um
$   L17: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L18: Elite EM-370Z                       PPG   30.0 um
$   L19: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$
$ Equivalent orthotropic properties:
$   E_a = E_b (in-plane) =    41728.5 MPa =  41.73 GPa
$   E_c     (through)   =    11750.5 MPa =  11.75 GPa
$   nu_ba (in-plane)    = 0.2005
$   nu_ca (through)     = 0.3073
$   G_ab (in-plane)     =    16848.8 MPa
$   G_bc = G_ca         =     4510.4 MPa
$   rho                 = 3.1844e-09 ton/mm^3 (3.184 g/cc)
$   BULK                =    32646.3 MPa
$   Visco G0            =    16881.2 MPa
$   Visco GI            =    16450.6 MPa
$   Visco BETA          = 963.0 /s  (tau=1.04 ms)
$   CTE_a = CTE_b       =  14.53 ppm/K
$   CTE_c               =  32.39 ppm/K
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
$$ PCB_10L_050T_DS7402_EM370Z
$$ 10층 HDI 0.50mm — DS-7402 series + EM-370Z, ED Cu
*MAT_ORTHOTROPIC_VISCOELASTIC_TITLE
PCB_10L_050T_DS7402_EM370Z
$      MID        RO        EA        EB      PRBA       GAB       GBC       GCA
    200010 3.184e-09   41728.5   41728.5    0.2005   16848.8    4510.4    4510.4
$     AOPT         K        G0      GINF      BETA     REF
       0.0   32646.3   16881.2   16450.6     963.0       0.0
$       XP        YP        ZP        A1        A2        A3
       0.0       0.0       0.0       0.0       0.0       0.0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ Orthotropic thermal expansion (separate x/y/z)
$$ [DB] PID slot holds MID=200010 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200010         0 1.453e-05         0 1.453e-05         0 3.239e-05
$
*END
