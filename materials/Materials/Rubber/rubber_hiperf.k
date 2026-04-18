$ ========================================================================
$ RUBBER — High-Performance: Mechanical (MAT_001 + MAT_027 + MAT_077_O)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: High-Performance — VMQ Silicone, FKM Viton, FFKM Kalrez
$ MID: 100911~100914 (lin), 110911~110914 (MR), 130911~130914 (Ogden)
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
$   100911   110911  130911  VMQ_Silicone_Std              50    2.20  0.370 0.090  1.15
$   100912   110912  130912  VMQ_Silicone_Firm             70    5.60  0.930 0.200  1.20
$   100913   110913  130913  FKM_Viton                     75    6.80  1.130 0.250  1.85
$   100914   110914  130914  FFKM_Kalrez                   75    7.00  1.170 0.250  2.00
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001, for low-strain preview)
$ ========================================================================
$
$$ --- VMQ_Silicone_Std Linear (MID 100911) ---
$$ Silicone VMQ Shore A 50, -55~250°C, low damping
$$ Hardness: Shore A 50, Source: Shin-Etsu KE-961-U TDS, ASTM D2000 FC/FE
$$ E=2.2 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
VMQ_Silicone_Std Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100911 1.150e-09    2.2000    0.4990       0.0       0.0       0.0
$
$$ --- VMQ_Silicone_Firm Linear (MID 100912) ---
$$ Silicone VMQ Shore A 70, firmer gasket/keypad
$$ Hardness: Shore A 70, Source: Dow 3-6749, Shin-Etsu KE-951-U
$$ E=5.6 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
VMQ_Silicone_Firm Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100912 1.200e-09    5.6000    0.4990       0.0       0.0       0.0
$
$$ --- FKM_Viton Linear (MID 100913) ---
$$ Fluoroelastomer (Viton A/B), extreme oil/heat
$$ Hardness: Shore A 75, Source: DuPont Viton A/B TDS, ASTM D2000 HK
$$ E=6.8 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
FKM_Viton Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100913 1.850e-09    6.8000    0.4990       0.0       0.0       0.0
$
$$ --- FFKM_Kalrez Linear (MID 100914) ---
$$ Perfluoroelastomer (Kalrez), semiconductor, chemical
$$ Hardness: Shore A 75, Source: DuPont Kalrez 4079 TDS
$$ E=7.0 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
FFKM_Kalrez Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100914 2.000e-09    7.0000    0.4990       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MOONEY-RIVLIN HYPERELASTIC (MAT_027, standard)
$ ========================================================================
$
$$ --- VMQ_Silicone_Std Mooney-Rivlin (MID 110911) ---
$$ Silicone VMQ Shore A 50, -55~250°C, low damping
$$ Hardness: Shore A 50, Source: Shin-Etsu KE-961-U TDS, ASTM D2000 FC/FE
$$ C10=0.37 MPa, C01=0.09 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
VMQ_Silicone_Std Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110911 1.150e-09    0.3700    0.0900    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- VMQ_Silicone_Firm Mooney-Rivlin (MID 110912) ---
$$ Silicone VMQ Shore A 70, firmer gasket/keypad
$$ Hardness: Shore A 70, Source: Dow 3-6749, Shin-Etsu KE-951-U
$$ C10=0.93 MPa, C01=0.2 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
VMQ_Silicone_Firm Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110912 1.200e-09    0.9300    0.2000    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- FKM_Viton Mooney-Rivlin (MID 110913) ---
$$ Fluoroelastomer (Viton A/B), extreme oil/heat
$$ Hardness: Shore A 75, Source: DuPont Viton A/B TDS, ASTM D2000 HK
$$ C10=1.13 MPa, C01=0.25 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
FKM_Viton Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110913 1.850e-09    1.1300    0.2500    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- FFKM_Kalrez Mooney-Rivlin (MID 110914) ---
$$ Perfluoroelastomer (Kalrez), semiconductor, chemical
$$ Hardness: Shore A 75, Source: DuPont Kalrez 4079 TDS
$$ C10=1.17 MPa, C01=0.25 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
FFKM_Kalrez Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110914 2.000e-09    1.1700    0.2500    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$ ========================================================================
$ 3. OGDEN HYPERELASTIC + PRONY VISCOELASTIC (MAT_077_O)
$ ========================================================================
$
$$ --- VMQ_Silicone_Std Ogden Viscoelastic (MID 130911) ---
$$ Silicone VMQ Shore A 50, -55~250°C, low damping
$$ Hardness: Shore A 50, Source: Shin-Etsu KE-961-U TDS, ASTM D2000 FC/FE
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
VMQ_Silicone_Std Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130911 1.150e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    0.9000    1.3000    0.0012    5.0000   -0.0120   -2.0000    0.0000    0.0000
    0.0800    100.00
    0.0500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- VMQ_Silicone_Firm Ogden Viscoelastic (MID 130912) ---
$$ Silicone VMQ Shore A 70, firmer gasket/keypad
$$ Hardness: Shore A 70, Source: Dow 3-6749, Shin-Etsu KE-951-U
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
VMQ_Silicone_Firm Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130912 1.200e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    2.2000    1.3000    0.0030    5.0000   -0.0300   -2.0000    0.0000    0.0000
    0.0800    100.00
    0.0500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- FKM_Viton Ogden Viscoelastic (MID 130913) ---
$$ Fluoroelastomer (Viton A/B), extreme oil/heat
$$ Hardness: Shore A 75, Source: DuPont Viton A/B TDS, ASTM D2000 HK
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
FKM_Viton Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130913 1.850e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    2.8000    1.3000    0.0035    5.0000   -0.0350   -2.0000    0.0000    0.0000
    0.1500    100.00
    0.1000   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- FFKM_Kalrez Ogden Viscoelastic (MID 130914) ---
$$ Perfluoroelastomer (Kalrez), semiconductor, chemical
$$ Hardness: Shore A 75, Source: DuPont Kalrez 4079 TDS
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
FFKM_Kalrez Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130914 2.000e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    2.9000    1.3000    0.0036    5.0000   -0.0360   -2.0000    0.0000    0.0000
    0.1500    100.00
    0.1000   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
*END
