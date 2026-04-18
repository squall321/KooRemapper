$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_086) — PCB_12L_055T_DS7402_EM370Z
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Generated from layup: 12층 HDI 0.55mm — DS-7402 series + EM-370Z, ED Cu
$ Total thickness: 550.0 um (0.5500 mm)
$
$ Layup composition (top -> bottom):
$   L1: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$   L2: Elite EM-370Z                       PPG   25.0 um
$   L3: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L4: Doosan DS-7402H                     PPG   35.0 um
$   L5: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L6: Doosan DS-7402H                     PPG   35.0 um
$   L7: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L8: Doosan DS-7402H                     PPG   35.0 um
$   L9: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L10: Doosan DS-7402H                     PPG   35.0 um
$   L11: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L12: Doosan DS-7402LC                    PPG   64.0 um
$   L13: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L14: Doosan DS-7402H                     PPG   35.0 um
$   L15: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L16: Doosan DS-7402H                     PPG   35.0 um
$   L17: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.90)
$   L18: Doosan DS-7402H                     PPG   35.0 um
$   L19: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.50)
$   L20: Doosan DS-7402H                     PPG   35.0 um
$   L21: Cu Electrodeposited Standard (Rigid PCB) Cu   12.0 um  (eta=0.92)
$   L22: Elite EM-370Z                       PPG   25.0 um
$   L23: Cu Electrodeposited Standard (Rigid PCB) Cu   18.0 um  (eta=0.40)
$
$ Equivalent orthotropic properties:
$   E_a = E_b (in-plane) =    42011.3 MPa =  42.01 GPa
$   E_c     (through)   =    11726.5 MPa =  11.73 GPa
$   nu_ba (in-plane)    = 0.2004
$   nu_ca (through)     = 0.3075
$   G_ab (in-plane)     =    16978.8 MPa
$   G_bc = G_ca         =     4500.0 MPa
$   rho                 = 3.2174e-09 ton/mm^3 (3.217 g/cc)
$   BULK                =    33070.3 MPa
$   Visco G0            =    16972.3 MPa
$   Visco GI            =    16554.2 MPa
$   Visco BETA          = 967.5 /s  (tau=1.03 ms)
$   CTE_a = CTE_b       =  14.57 ppm/K
$   CTE_c               =  32.72 ppm/K
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
$$ PCB_12L_055T_DS7402_EM370Z
$$ 12층 HDI 0.55mm — DS-7402 series + EM-370Z, ED Cu
*MAT_ORTHOTROPIC_VISCOELASTIC_TITLE
PCB_12L_055T_DS7402_EM370Z
$      MID        RO        EA        EB      PRBA       GAB       GBC       GCA
    200012 3.217e-09   42011.3   42011.3    0.2004   16978.8    4500.0    4500.0
$     AOPT         K        G0      GINF      BETA     REF
       0.0   33070.3   16972.3   16554.2     967.5       0.0
$       XP        YP        ZP        A1        A2        A3
       0.0       0.0       0.0       0.0       0.0       0.0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ Orthotropic thermal expansion (separate x/y/z)
$$ [DB] PID slot holds MID=200012 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200012         0 1.457e-05         0 1.457e-05         0 3.272e-05
$
*END
