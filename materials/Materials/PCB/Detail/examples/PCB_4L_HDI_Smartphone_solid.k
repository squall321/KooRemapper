$ ========================================================================
$ PCB EQUIVALENT MATERIAL (MAT_002 + Rayleigh) — PCB_4L_HDI_Smartphone
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Element type: SOLID (MAT_002 only supports elastic)
$
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
$ Equivalent orthotropic elastic properties:
$   E_a = E_b (in-plane) =    40669.2 MPa =  40.67 GPa
$   E_c     (through)    =    12298.2 MPa =  12.30 GPa
$   nu_ba (in-plane)     = 0.2025
$   nu_ca (through)      = 0.3059
$   G_ab (in-plane)      =    16485.1 MPa
$   G_bc = G_ca          =     4722.5 MPa
$   rho                  = 2.9752e-09 ton/mm^3 (2.975 g/cc)
$   CTE_a = CTE_b        =  14.06 ppm/K
$   CTE_c                =  25.98 ppm/K
$
$ Rayleigh damping configuration:
$   Source               : material tan(d)=0.0151 @ BETA=800.0 rad/s
$   Material tan(delta)  = 0.0151  (PPG intrinsic, reference)
$   Material zeta        = 0.0076  (reference)
$   Applied zeta         = 0.0076  (0.76%)
$   Reference omega      = 800.0 rad/s (127.3 Hz)
$   alpha_mass (VALDMP)  = 6.0450e+00 /s
$   beta_stiffness       = 9.4452e-06 s
$   NOTE: Using material-based damping (intrinsic PPG loss only).
$         To use engineering target zeta, add to your YAML:
$           rayleigh_damping:
$             target_zeta: 0.02      # 2%
$             omega_ref_hz: 1000     # 1 kHz
$
$ =================================================================
$ USAGE:
$   1. INCLUDE this file in your main model
$   2. Create or assign your PCB PART(s) with MID=200002
$   3. Add those PIDs to *SET_PART_LIST SID=1000002 below
$   4. Damping is applied automatically to all parts in the set
$ ========================================================================
*KEYWORD
$
$ ----- MATERIAL (MAT_002 Orthotropic Elastic) -----
$$ PCB_4L_HDI_Smartphone — Solid element version
$$ 4층 스마트폰 HDI 메인보드 (DS-8402H + ED Cu)
*MAT_ORTHOTROPIC_ELASTIC_TITLE
PCB_4L_HDI_Smartphone_SOLID
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    200002 2.975e-09   40669.2   40669.2   12298.2    0.2025    0.3059    0.3059
$      GAB       GBC       GCA      AOPT         G      SIGF
   16485.1    4722.5    4722.5       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$ ----- ORTHOTROPIC THERMAL EXPANSION -----
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT     LCIDY     MULTY     LCIDZ     MULTZ
    200002         0 1.406e-05         0 1.406e-05         0 2.598e-05
$
$ ----- PART SET (populate with actual PCB PIDs) -----
$$ SID=1000002: collects all solid PCB parts using this material
$$ Edit the list below to include your actual PART IDs.
*SET_PART_LIST_TITLE
PCB_4L_HDI_Smartphone_parts
$      SID       DA1       DA2       DA3       DA4
   1000002       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace the zero below with your actual PCB PART IDs
         0         0         0         0         0         0         0         0
$
$ ----- RAYLEIGH DAMPING (mass + stiffness proportional) -----
$$ Damping source: material tan(d)=0.0151 @ BETA=800.0 rad/s
$$ Applied zeta=0.0076 (0.76%) at f_ref=127 Hz
$$ Material ref: tan(d)=0.0151, zeta_mat=0.0076
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP       STX       STY       STZ       SRX       SRY
   1000002         0 6.045e+00       1.0       1.0       1.0       1.0       1.0
$
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
   1000002 9.445e-06
$
*END
