$ ========================================================================
$ SOLDER MATERIAL LIBRARY for PCB Drop/Thermal Analysis
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ MID: 100701~100710 (bilinear), 110701~110710 (multi-linear)
$       130701~130710 (kin pure), 140701~140710 (kin mixed)
$       120701~120710 (thermal TMID)
$
$ Model: *MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024) — elastoplastic
$
$ Solder is the weakest link in BGA drop tests. Cyclic loading causes
$ low-cycle fatigue at solder joint. Kinematic hardening variants are
$ provided for Bauschinger-aware analysis under thermal/shock cycling.
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID,
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ Data sources:
$   - SAC305 (Sn-3.0Ag-0.5Cu): Che & Pang (2012), IPC J-STD-006
$   - SAC405: Pang et al (2003), Syed (2004)
$   - Sn63Pb37 eutectic: Lau (1991), MIL-HDBK-5
$   - Sn42Bi58 low-temp: iNEMI Roadmap, indium corp
$   - Pure Sn: ASM Handbook Vol 2
$
$ ========================================================================
$ SUMMARY TABLE
$
$  MID     Name                    rho   E(GPa)  sigy   sigu  eps_f  TC   Cp
$  ---------------------------------------------------------------------------
$  100701  SAC305                  7.44   48.0    30     45   0.28   58  220
$  100702  SAC405                  7.48   52.0    35     50   0.25   58  220
$  100703  Sn63Pb37_eutectic       8.40   30.0    27     42   0.40   50  150
$  100704  Sn42Bi58_lowtemp        8.76   42.0    55     72   0.15   19  201
$  100705  Sn_pure                 7.30   50.0    15     20   0.60   67  228
$
$ Cowper-Symonds (Wang & Yi 2001, Qu & Wong 2002):
$   SAC solders: C=5000, P=4  (moderately rate-sensitive)
$   Sn63Pb37:    C=600,  P=4  (more rate-sensitive, lower melting)
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. SAC305 (Sn-3.0Ag-0.5Cu) — Lead-free industry standard
$ ========================================================================
$
$$ --- SAC305 Bilinear (MID 100701) ---
$$ Lead-free workhorse solder for BGA / QFN / chip components
$$ Source: IPC J-STD-006, Che & Pang (2012)
$$ E=48 GPa, sigy=30 MPa, sigu=45 MPa, eps_f=28%
$$ ETAN = (45-30)/(0.28-0.000625) = 53.6 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SAC305 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100701 7.440e-09   48000.0    0.3500     30.00     53.62    0.2800      0.00
$        C         P      LCSS      LCSR        VP
    5000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SAC305 Multilinear (MID 110701) ---
$$ Source: Anand model data from Syed (2004), scaled to static
*DEFINE_CURVE_TITLE
SAC305 true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110701         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.0000000000e+01
    5.0000000000e-03    3.4000000000e+01
    1.0000000000e-02    3.7000000000e+01
    2.0000000000e-02    4.0000000000e+01
    5.0000000000e-02    4.2500000000e+01
    1.0000000000e-01    4.3500000000e+01
    2.0000000000e-01    4.4500000000e+01
    2.8000000000e-01    4.5000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SAC305 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110701 7.440e-09   48000.0    0.3500      0.00      0.00    0.2800      0.00
$        C         P      LCSS      LCSR        VP
    5000.0       4.0    110701         0       1.0
$
$$ --- SAC305 Kinematic Pure (MID 130701) ---
*MAT_PLASTIC_KINEMATIC_TITLE
SAC305 Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130701 7.440e-09   48000.0    0.3500     30.00     53.62    0.0000
$      SRC       SRP        FS        VP
    5000.0       4.0    0.2800       1.0
$
$$ --- SAC305 Kinematic Mixed (MID 140701) ---
*MAT_PLASTIC_KINEMATIC_TITLE
SAC305 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140701 7.440e-09   48000.0    0.3500     30.00     53.62    0.5000
$      SRC       SRP        FS        VP
    5000.0       4.0    0.2800       1.0
$
$$ --- SAC305 Thermal (TMID 120701) ---
$$ TC=58 W/m/K, Cp=220 J/kg/K, CTE=21.8 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
SAC305 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120701 7.440e-09         0    1.0000       0.0       0.0
$       HC         TC
 2.200e+08 5.800e+01
$
$$ [DB] PID slot holds MID for all 4 SAC305 variants
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100701         0 2.180e-05
*MAT_ADD_THERMAL_EXPANSION
    110701         0 2.180e-05
*MAT_ADD_THERMAL_EXPANSION
    130701         0 2.180e-05
*MAT_ADD_THERMAL_EXPANSION
    140701         0 2.180e-05
$
$ ========================================================================
$ 2. SAC405 (Sn-4.0Ag-0.5Cu) — Higher Ag content, stronger
$ ========================================================================
$
$$ --- SAC405 Bilinear (MID 100702) ---
$$ Source: Pang et al (2003), higher Ag gives stronger Ag3Sn precipitates
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SAC405 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100702 7.480e-09   52000.0    0.3500     35.00     60.21    0.2500      0.00
$        C         P      LCSS      LCSR        VP
    5000.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
*DEFINE_CURVE_TITLE
SAC405 true stress vs plastic strain
    110702         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.5000000000e+01
    5.0000000000e-03    3.9500000000e+01
    1.0000000000e-02    4.2500000000e+01
    2.0000000000e-02    4.5500000000e+01
    5.0000000000e-02    4.8000000000e+01
    1.0000000000e-01    4.9000000000e+01
    2.5000000000e-01    5.0000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
SAC405 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110702 7.480e-09   52000.0    0.3500      0.00      0.00    0.2500      0.00
$        C         P      LCSS      LCSR        VP
    5000.0       4.0    110702         0       1.0
$
*MAT_PLASTIC_KINEMATIC_TITLE
SAC405 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140702 7.480e-09   52000.0    0.3500     35.00     60.21    0.5000
$      SRC       SRP        FS        VP
    5000.0       4.0    0.2500       1.0
$
$$ --- SAC405 Thermal (TMID 120702) ---
*MAT_THERMAL_ISOTROPIC_TITLE
SAC405 Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120702 7.480e-09         0    1.0000       0.0       0.0
$       HC         TC
 2.200e+08 5.800e+01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100702         0 2.050e-05
*MAT_ADD_THERMAL_EXPANSION
    110702         0 2.050e-05
*MAT_ADD_THERMAL_EXPANSION
    140702         0 2.050e-05
$
$ ========================================================================
$ 3. Sn63Pb37 Eutectic — Legacy leaded solder (still used in mil/aero)
$ ========================================================================
$
$$ --- Sn63Pb37 Bilinear (MID 100703) ---
$$ Source: Lau (1991), MIL-HDBK-5
$$ Lower E (30 GPa), higher ductility vs SAC
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Sn63Pb37 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100703 8.400e-09   30000.0    0.4000     27.00     37.61    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     600.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
*DEFINE_CURVE_TITLE
Sn63Pb37 true stress vs plastic strain
    110703         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    2.7000000000e+01
    5.0000000000e-03    3.0000000000e+01
    1.0000000000e-02    3.3000000000e+01
    2.0000000000e-02    3.6000000000e+01
    5.0000000000e-02    3.9500000000e+01
    1.0000000000e-01    4.1000000000e+01
    2.0000000000e-01    4.2000000000e+01
    4.0000000000e-01    4.2000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Sn63Pb37 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110703 8.400e-09   30000.0    0.4000      0.00      0.00    0.4000      0.00
$        C         P      LCSS      LCSR        VP
     600.0       4.0    110703         0       1.0
$
*MAT_PLASTIC_KINEMATIC_TITLE
Sn63Pb37 Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140703 8.400e-09   30000.0    0.4000     27.00     37.61    0.5000
$      SRC       SRP        FS        VP
     600.0       4.0    0.4000       1.0
$
$$ --- Sn63Pb37 Thermal (TMID 120703) ---
$$ CTE=24.7 ppm/K, TC=50 W/m/K, Cp=150 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Sn63Pb37 Thermal
    120703 8.400e-09         0    1.0000       0.0       0.0
 1.500e+08 5.000e+01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100703         0 2.470e-05
*MAT_ADD_THERMAL_EXPANSION
    110703         0 2.470e-05
*MAT_ADD_THERMAL_EXPANSION
    140703         0 2.470e-05
$
$ ========================================================================
$ 4. Sn42Bi58 — Low-temperature solder (for heat-sensitive assemblies)
$ ========================================================================
$
$$ --- Sn42Bi58 Bilinear (MID 100704) ---
$$ Melting point 138°C (vs 217°C for SAC). For PLA/PCB sensitive processes.
$$ Source: iNEMI Low-Temp Solder Roadmap
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Sn42Bi58 Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100704 8.760e-09   42000.0    0.4000     55.00    117.56    0.1500      0.00
$        C         P      LCSS      LCSR        VP
    3000.0       4.0         0         0       1.0
$
*DEFINE_CURVE_TITLE
Sn42Bi58 true stress vs plastic strain
    110704         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    5.5000000000e+01
    5.0000000000e-03    6.0000000000e+01
    1.0000000000e-02    6.4000000000e+01
    2.0000000000e-02    6.8000000000e+01
    5.0000000000e-02    7.1000000000e+01
    1.0000000000e-01    7.2000000000e+01
    1.5000000000e-01    7.2000000000e+01
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Sn42Bi58 Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110704 8.760e-09   42000.0    0.4000      0.00      0.00    0.1500      0.00
$        C         P      LCSS      LCSR        VP
    3000.0       4.0    110704         0       1.0
$
$$ --- Sn42Bi58 Thermal (TMID 120704) ---
$$ CTE=15 ppm/K, TC=19 W/m/K, Cp=201 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
Sn42Bi58 Thermal
    120704 8.760e-09         0    1.0000       0.0       0.0
 2.010e+08 1.900e+01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100704         0 1.500e-05
*MAT_ADD_THERMAL_EXPANSION
    110704         0 1.500e-05
$
$ ========================================================================
$ 5. Pure Sn — Reference / plating / whisker studies
$ ========================================================================
$
$$ --- Pure Sn Bilinear (MID 100705) ---
$$ Pure tin reference material, ASM Handbook Vol 2
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Pure Sn Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100705 7.300e-09   50000.0    0.3600     15.00      8.36    0.6000      0.00
$        C         P      LCSS      LCSR        VP
    6000.0       4.0         0         0       1.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Pure Sn Thermal
    120705 7.300e-09         0    1.0000       0.0       0.0
 2.280e+08 6.700e+01
$
$$ [DB] PID slot holds MID
*MAT_ADD_THERMAL_EXPANSION
    100705         0 2.230e-05
$
$ ========================================================================
$ END OF SOLDER LIBRARY
$ ========================================================================
*END
