$ ========================================================================
$ RUBBER — Thermoplastic Elastomer: Mechanical (MAT_001 + MAT_027 + MAT_077_O)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Thermoplastic Elastomer — TPU, TPE-S (SBS/SIS)
$ MID: 100921~100922 (lin), 110921~110922 (MR), 130921~130922 (Ogden)
$
$ Hybrid strategy (3 variants per material):
$   Linear elastic (MAT_001)    MID 1009xx — low strain preview
$   Mooney-Rivlin (MAT_027)     MID 1109xx — standard hyperelastic
$   Ogden+Prony (MAT_077_O)     MID 1309xx — dynamic with damping
$
$ Thermal properties (TC, Cp, CTE) in rubber_thermal.k
$ Rayleigh damping for MAT_001/MAT_027 in rubber_damping.k
$ (MAT_077_O has built-in Prony viscoelasticity)
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds MATERIAL ID (MID),
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin_mid  mr_mid  og_mid  Name                       ShoreA  E(MPa) C10   C01   rho
$   ----------------------------------------------------------------------------------------
$   100921   110921  130921  TPU_Hard_85A                  85   15.00  2.500 0.500  1.20
$   100922   110922  130922  TPE_S_SBS                     65    4.30  0.720 0.150  0.93
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001, for low-strain preview)
$ ========================================================================
$
$$ --- TPU_Hard_85A Linear (MID 100921) ---
$$ Thermoplastic Polyurethane Shore A 85, phone cases
$$ Hardness: Shore A 85, Source: BASF Elastollan 1185A TDS, Lubrizol ISOPLAST
$$ E=15.0 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
TPU_Hard_85A Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100921 1.200e-09   15.0000    0.4990       0.0       0.0       0.0
$
$$ --- TPE_S_SBS Linear (MID 100922) ---
$$ Styrenic TPE (SBS), grip, overmolding
$$ Hardness: Shore A 65, Source: Kraton G1650 TDS, Shell TPE
$$ E=4.3 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
TPE_S_SBS Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100922 9.300e-10    4.3000    0.4900       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MOONEY-RIVLIN HYPERELASTIC (MAT_027, standard)
$ ========================================================================
$
$$ --- TPU_Hard_85A Mooney-Rivlin (MID 110921) ---
$$ Thermoplastic Polyurethane Shore A 85, phone cases
$$ Hardness: Shore A 85, Source: BASF Elastollan 1185A TDS, Lubrizol ISOPLAST
$$ C10=2.5 MPa, C01=0.5 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
TPU_Hard_85A Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110921 1.200e-09    2.5000    0.5000    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- TPE_S_SBS Mooney-Rivlin (MID 110922) ---
$$ Styrenic TPE (SBS), grip, overmolding
$$ Hardness: Shore A 65, Source: Kraton G1650 TDS, Shell TPE
$$ C10=0.72 MPa, C01=0.15 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
TPE_S_SBS Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110922 9.300e-10    0.7200    0.1500    0.4900       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$ ========================================================================
$ 3. OGDEN HYPERELASTIC + PRONY VISCOELASTIC (MAT_077_O)
$ ========================================================================
$
$$ --- TPU_Hard_85A Ogden Viscoelastic (MID 130921) ---
$$ Thermoplastic Polyurethane Shore A 85, phone cases
$$ Hardness: Shore A 85, Source: BASF Elastollan 1185A TDS, Lubrizol ISOPLAST
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
TPU_Hard_85A Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130921 1.200e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    5.0000    1.3000    0.0080    5.0000   -0.0800   -2.0000    0.0000    0.0000
    0.2500    100.00
    0.1500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- TPE_S_SBS Ogden Viscoelastic (MID 130922) ---
$$ Styrenic TPE (SBS), grip, overmolding
$$ Hardness: Shore A 65, Source: Kraton G1650 TDS, Shell TPE
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
TPE_S_SBS Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130922 9.300e-10    0.4900         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.8000    1.3000    0.0025    5.0000   -0.0250   -2.0000    0.0000    0.0000
    0.3000    100.00
    0.2000   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
*END
