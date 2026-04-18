$ ========================================================================
$ SPECIALTY TAPE/PAD MATERIAL LIBRARY (smartphone + electronics)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ MID: 100021~100040 (extending from smartphone_tape_materials.k 100001~100020)
$
$ Contents:
$   100021  Thermal Pad Silicone Soft (1.5 W/m/K)
$   100022  Thermal Pad Silicone Medium (3.0 W/m/K)
$   100023  Thermal Pad Silicone High (5.0 W/m/K, graphene/BN filled)
$   100024  Graphite Sheet (pyrolytic graphite heat spreader)
$   100025  PORON 4701 Foam Gasket (microcellular urethane)
$   100026  PORON SR-S Foam (softer grade)
$   100027  EAR Isodamp C-1002 (damping urethane)
$   100028  Kapton HN Polyimide Film (tape backing)
$   100029  Kapton PI Adhesive Tape (high-temp masking)
$   100030  Teflon PTFE Tape (low friction, slip liner)
$   100031  EMI Copper Foil Tape (shielding, adhesive)
$   100032  EMI Aluminum Foil Tape (lighter shielding)
$   100033  Graphite Film Single-sided (heat spreader, iPhone style)
$   100034  Graphite Film Multi-layer (stacked heat spreader)
$   100035  Cushion Rubber (NBR nitrile)
$
$ Model selection:
$   - Foam/rubber/gasket: *MAT_VISCOELASTIC (MAT_006, single Maxwell)
$   - Film backings (Kapton, PTFE): *MAT_ELASTIC (MAT_001)
$   - Graphite sheet (anisotropic but simplified): *MAT_ELASTIC
$   - Copper/Al foil: *MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024)
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID,
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ Data sources:
$   - Shin-Etsu TC-10/TC-30 Silicone Pad TDS
$   - BerquisgtTflex series
$   - Rogers PORON 4701/SR-S TDS
$   - EAR Specialty Isodamp C-1002
$   - DuPont Kapton HN TDS
$   - 3M EMI Foil Tape 1181/1267
$   - Panasonic/Kaneka Graphite Sheet TDS
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. Thermal Pads (Silicone gap fillers)
$ ========================================================================
$
$$ --- Thermal Pad Silicone Soft (MID 100021) ---
$$ 1.5 W/m/K, Shore OO 30, for SoC-to-frame gap fill
$$ Source: Shin-Etsu TC-10W
*MAT_VISCOELASTIC_TITLE
Thermal Pad Silicone Soft 1.5 W/mK
$      MID        RO      BULK        G0        GI      BETA
    100021 2.500e-09    1500.0    0.0500    0.0100      30.0
$
$$ --- Thermal Pad Silicone Soft Thermal (TMID 120021) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Thermal Pad Silicone Soft Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120021 2.500e-09         0    1.0000       0.0       0.0
$       HC         TC
 1.200e+09 1.500e+00
$
$$ [DB] PID slot holds MID=100021
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100021         0 3.000e-04
$
$$ --- Thermal Pad Silicone Medium (MID 100022) ---
$$ 3.0 W/m/K, Shore OO 50, firmer
*MAT_VISCOELASTIC_TITLE
Thermal Pad Silicone Medium 3.0 W/mK
    100022 2.700e-09    1800.0    0.0800    0.0150      40.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Thermal Pad Silicone Medium Thermal
    120022 2.700e-09         0    1.0000       0.0       0.0
 1.200e+09 3.000e+00
$
$$ [DB] PID slot holds MID=100022
*MAT_ADD_THERMAL_EXPANSION
    100022         0 2.500e-04
$
$$ --- Thermal Pad Silicone High (MID 100023) ---
$$ 5.0 W/m/K, premium BN/graphene filled
*MAT_VISCOELASTIC_TITLE
Thermal Pad Silicone High 5.0 W/mK
    100023 3.000e-09    2000.0    0.1000    0.0200      50.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Thermal Pad Silicone High Thermal
    120023 3.000e-09         0    1.0000       0.0       0.0
 1.100e+09 5.000e+00
$
$$ [DB] PID slot holds MID=100023
*MAT_ADD_THERMAL_EXPANSION
    100023         0 2.000e-04
$
$ ========================================================================
$ 2. Graphite Heat Spreader Sheets
$ ========================================================================
$
$$ --- Graphite Sheet Single-sided (MID 100024) ---
$$ Panasonic PGS (Pyrolytic Graphite Sheet), in-plane k=700~1500 W/m/K
$$ Used as isotropic (simplified): k=500 W/m/K
$$ Note: actual is highly anisotropic - in-plane >> through
*MAT_ELASTIC_TITLE
Graphite Sheet PGS
$      MID        RO         E        PR
    100024 1.000e-09    5000.0    0.2000       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Graphite Sheet PGS Thermal
    120024 1.000e-09         0    1.0000       0.0       0.0
 7.500e+08 5.000e+02
$
$$ [DB] PID slot holds MID=100024
*MAT_ADD_THERMAL_EXPANSION
    100024         0 1.000e-06
$
$$ --- Graphite Film Multi-layer (MID 100033) ---
$$ Kaneka GS-25 stacked graphite, used in high-end phones
*MAT_ELASTIC_TITLE
Graphite Film Multi-layer
    100033 1.100e-09    4500.0    0.2500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Graphite Film Multi-layer Thermal
    120033 1.100e-09         0    1.0000       0.0       0.0
 7.500e+08 8.000e+02
$
$$ [DB] PID slot holds MID=100033
*MAT_ADD_THERMAL_EXPANSION
    100033         0 1.000e-06
$
$ ========================================================================
$ 3. Foam Gaskets (PORON, EAR Isodamp)
$ ========================================================================
$
$$ --- PORON 4701 Foam Gasket (MID 100025) ---
$$ Rogers PORON 4701-40 (microcellular urethane)
$$ Low compression set, good vibration damping
$$ Used: speaker mount, press button, display edge seal
*MAT_VISCOELASTIC_TITLE
PORON 4701 Foam Gasket
    100025 3.200e-10     250.0    0.1500    0.0100      30.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
PORON 4701 Thermal
    120025 3.200e-10         0    1.0000       0.0       0.0
 1.700e+09 6.000e-02
$
$$ [DB] PID slot holds MID=100025
*MAT_ADD_THERMAL_EXPANSION
    100025         0 1.800e-04
$
$$ --- PORON SR-S Foam (MID 100026) ---
$$ Softer grade, higher energy absorption
*MAT_VISCOELASTIC_TITLE
PORON SR-S Soft Foam
    100026 2.500e-10     200.0    0.0800    0.0050      25.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
PORON SR-S Thermal
    120026 2.500e-10         0    1.0000       0.0       0.0
 1.700e+09 5.000e-02
$
$$ [DB] PID slot holds MID=100026
*MAT_ADD_THERMAL_EXPANSION
    100026         0 2.000e-04
$
$$ --- EAR Isodamp C-1002 (MID 100027) ---
$$ Damping urethane — extreme tan(delta) at 20Hz~1kHz
$$ Used: vibration isolation, LRA motor mount
*MAT_VISCOELASTIC_TITLE
EAR Isodamp C-1002
    100027 1.100e-09    1500.0    0.3000    0.0050      80.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EAR Isodamp Thermal
    120027 1.100e-09         0    1.0000       0.0       0.0
 1.600e+09 1.500e-01
$
$$ [DB] PID slot holds MID=100027
*MAT_ADD_THERMAL_EXPANSION
    100027         0 1.500e-04
$
$ ========================================================================
$ 4. Polyimide (Kapton) Films and Tapes
$ ========================================================================
$
$$ --- Kapton HN Polyimide Film (MID 100028) ---
$$ DuPont Kapton HN (unmetalized), backing film
$$ E=2.5 GPa, Tg=400C, excellent high-temp stability
*MAT_ELASTIC_TITLE
Kapton HN Polyimide Film
    100028 1.420e-09    2500.0    0.3400       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Kapton HN Thermal
    120028 1.420e-09         0    1.0000       0.0       0.0
 1.090e+09 1.200e-01
$
$$ [DB] PID slot holds MID=100028
*MAT_ADD_THERMAL_EXPANSION
    100028         0 2.000e-05
$
$$ --- Kapton PI Adhesive Tape (MID 100029) ---
$$ 3M 5413, Saint-Gobain Chr 2905
$$ High-temp masking and insulation for PCB processing
*MAT_VISCOELASTIC_TITLE
Kapton PI Adhesive Tape
    100029 1.450e-09    2400.0    0.8000    0.1000     100.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Kapton PI Tape Thermal
    120029 1.450e-09         0    1.0000       0.0       0.0
 1.090e+09 1.200e-01
$
$$ [DB] PID slot holds MID=100029
*MAT_ADD_THERMAL_EXPANSION
    100029         0 2.500e-05
$
$ ========================================================================
$ 5. Teflon PTFE Tape
$ ========================================================================
$
$$ --- PTFE Teflon Tape (MID 100030) ---
$$ 3M 5490, Saint-Gobain Chr T3005
$$ Low friction, slip liner, chemical resistance
*MAT_ELASTIC_TITLE
PTFE Teflon Tape
    100030 2.200e-09     500.0    0.4600       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
PTFE Tape Thermal
    120030 2.200e-09         0    1.0000       0.0       0.0
 1.000e+09 2.500e-01
$
$$ [DB] PID slot holds MID=100030
*MAT_ADD_THERMAL_EXPANSION
    100030         0 1.100e-04
$
$ ========================================================================
$ 6. EMI Shielding Tapes
$ ========================================================================
$
$$ --- EMI Copper Foil Tape (MID 100031) ---
$$ 3M 1181 Cu foil with conductive acrylic adhesive
$$ 35um Cu + 25um adhesive = 60um total
$$ Used: EMI shielding, grounding
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
EMI Copper Foil Tape
$      MID        RO         E        PR      SIGY      ETAN      FAIL
    100031 8.900e-09  115000.0    0.3400     150.0    1500.0      0.10       0.0
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMI Cu Foil Tape Thermal
    120031 8.900e-09         0    1.0000       0.0       0.0
 3.850e+08 3.800e+02
$
$$ [DB] PID slot holds MID=100031
*MAT_ADD_THERMAL_EXPANSION
    100031         0 1.680e-05
$
$$ --- EMI Aluminum Foil Tape (MID 100032) ---
$$ 3M 425 Al foil 50um + adhesive
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
EMI Aluminum Foil Tape
$      MID        RO         E        PR      SIGY      ETAN      FAIL
    100032 2.700e-09   69000.0    0.3300      90.0     800.0      0.15       0.0
$        C         P      LCSS      LCSR        VP
    6500.0       4.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
EMI Al Foil Tape Thermal
    120032 2.700e-09         0    1.0000       0.0       0.0
 9.000e+08 2.100e+02
$
$$ [DB] PID slot holds MID=100032
*MAT_ADD_THERMAL_EXPANSION
    100032         0 2.300e-05
$
$ ========================================================================
$ 7. NBR Cushion Rubber (nitrile)
$ ========================================================================
$
$$ --- NBR Cushion Rubber (MID 100035) ---
$$ Nitrile rubber, used for shock absorbing mounts
$$ Oil-resistant, moderate damping
*MAT_VISCOELASTIC_TITLE
NBR Cushion Rubber
    100035 1.300e-09    2000.0    0.8000    0.0500     100.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
NBR Cushion Thermal
    120035 1.300e-09         0    1.0000       0.0       0.0
 1.700e+09 2.500e-01
$
$$ [DB] PID slot holds MID=100035
*MAT_ADD_THERMAL_EXPANSION
    100035         0 2.000e-04
$
$ ========================================================================
$ END OF SPECIALTY TAPE LIBRARY
$ ========================================================================
*END
