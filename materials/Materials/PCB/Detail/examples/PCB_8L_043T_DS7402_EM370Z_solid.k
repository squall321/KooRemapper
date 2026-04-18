$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_002 + Rayleigh) — PCB_8L_043T_DS7402_EM370Z
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Element type: SOLID (MAT_002 only supports elastic)
$
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
$ Equivalent orthotropic elastic properties:
$   E_a = E_b (in-plane) =    40161.5 MPa =  40.16 GPa
$   E_c     (through)    =    11639.1 MPa =  11.64 GPa
$   nu_ba (in-plane)     = 0.1985
$   nu_ca (through)      = 0.3065
$   G_ab (in-plane)      =    16301.0 MPa
$   G_bc = G_ca          =     4467.8 MPa
$   rho                  = 3.0465e-09 ton/mm^3 (3.046 g/cc)
$   CTE_a = CTE_b        =  14.20 ppm/K
$   CTE_c                =  32.08 ppm/K
$
$ Rayleigh damping configuration:
$   Source               : target_zeta=0.0200 @ 1000 Hz (engineering)
$   Material tan(delta)  = 0.0144  (PPG intrinsic, reference)
$   Material zeta        = 0.0072  (reference)
$   Applied zeta         = 0.0200  (2.00%)
$   Reference omega      = 6283.2 rad/s (1000.0 Hz)
$   alpha_mass (VALDMP)  = 1.2566e+02 /s
$   beta_stiffness       = 3.1831e-06 s
$
$ =================================================================
$ USAGE:
$   1. INCLUDE this file in your main model
$   2. Create or assign your PCB PART(s) with MID=200008
$   3. Add those PIDs to *SET_PART_LIST SID=1000008 below
$   4. Damping is applied automatically to all parts in the set
$ ========================================================================
*KEYWORD
$
$ ----- MATERIAL (MAT_002 Orthotropic Elastic) -----
$$ PCB_8L_043T_DS7402_EM370Z — Solid element version
$$ 8층 HDI 0.43mm — DS-7402 series + EM-370Z, ED Cu
*MAT_ORTHOTROPIC_ELASTIC_TITLE
PCB_8L_043T_DS7402_EM370Z_SOLID
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    200008 3.046e-09   40161.5   40161.5   11639.1    0.1985    0.3065    0.3065
$      GAB       GBC       GCA      AOPT         G      SIGF
   16301.0    4467.8    4467.8       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$ ----- ORTHOTROPIC THERMAL EXPANSION -----
$$ [DB] PID slot holds MID=200008 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200008         0 1.420e-05         0 1.420e-05         0 3.208e-05
$
$ ----- PART SET (populate with actual PCB PIDs) -----
$$ SID=1000008: collects all solid PCB parts using this material
$$ Edit the list below to include your actual PART IDs.
*SET_PART_LIST_TITLE
PCB_8L_043T_DS7402_EM370Z_parts
$      SID       DA1       DA2       DA3       DA4
   1000008       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace the zero below with your actual PCB PART IDs
         0         0         0         0         0         0         0         0
$
$ ----- RAYLEIGH DAMPING (mass + stiffness proportional) -----
$$ Damping source: target_zeta=0.0200 @ 1000 Hz (engineering)
$$ Applied zeta=0.0200 (2.00%) at f_ref=1000 Hz
$$ Material ref: tan(d)=0.0144, zeta_mat=0.0072
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP       STX       STY       STZ       SRX       SRY
   1000008         0 1.257e+02       1.0       1.0       1.0       1.0       1.0
$
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
   1000008 3.183e-06
$
*END
