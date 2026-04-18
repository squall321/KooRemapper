$ ========================================================================
$ RUBBER — Natural & Synthetic: Mechanical (MAT_001 + MAT_027 + MAT_077_O)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Natural & Synthetic — NR, SBR, BR, IIR, CR, NBR, EPDM
$ MID: 100901~100908 (lin), 110901~110908 (MR), 130901~130908 (Ogden)
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
$   100901   110901  130901  NR_SoftSuperior               40    1.60  0.267 0.067  0.92
$   100902   110902  130902  NR_Standard                   60    3.60  0.600 0.150  0.93
$   100903   110903  130903  SBR_TireTread                 65    4.30  0.700 0.200  0.94
$   100904   110904  130904  BR_Butadiene                  55    2.80  0.480 0.120  0.93
$   100905   110905  130905  IIR_Butyl                     55    2.70  0.450 0.120  0.92
$   100906   110906  130906  CR_Neoprene                   60    3.60  0.600 0.150  1.23
$   100907   110907  130907  NBR_Nitrile                   70    5.60  0.930 0.200  1.00
$   100908   110908  130908  EPDM_Standard                 65    4.30  0.720 0.170  0.86
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001, for low-strain preview)
$ ========================================================================
$
$$ --- NR_SoftSuperior Linear (MID 100901) ---
$$ Natural Rubber, soft Shore A 40, vibration mount
$$ Hardness: Shore A 40, Source: Treloar 1975, Morton Rubber Technology 3rd ed, ASTM D2000 AA
$$ E=1.6 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
NR_SoftSuperior Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100901 9.200e-10    1.6000    0.4990       0.0       0.0       0.0
$
$$ --- NR_Standard Linear (MID 100902) ---
$$ Natural Rubber Shore A 60, general purpose gasket
$$ Hardness: Shore A 60, Source: ASTM D2000 AA, Arruda-Boyce 1993
$$ E=3.6 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
NR_Standard Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100902 9.300e-10    3.6000    0.4990       0.0       0.0       0.0
$
$$ --- SBR_TireTread Linear (MID 100903) ---
$$ Styrene-Butadiene tire tread compound
$$ Hardness: Shore A 65, Source: Rubber Technology (Morton 1987), ASTM D2000 BA
$$ E=4.3 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
SBR_TireTread Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100903 9.400e-10    4.3000    0.4990       0.0       0.0       0.0
$
$$ --- BR_Butadiene Linear (MID 100904) ---
$$ Butadiene Rubber, tire sidewall, abrasion resistant
$$ Hardness: Shore A 55, Source: ASTM D2000 BA, Morton 1987
$$ E=2.8 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
BR_Butadiene Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100904 9.300e-10    2.8000    0.4990       0.0       0.0       0.0
$
$$ --- IIR_Butyl Linear (MID 100905) ---
$$ Butyl rubber (IIR), excellent gas impermeability, damping
$$ Hardness: Shore A 55, Source: ASTM D2000 AA, ExxonMobil Butyl TDS
$$ E=2.7 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
IIR_Butyl Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100905 9.200e-10    2.7000    0.4990       0.0       0.0       0.0
$
$$ --- CR_Neoprene Linear (MID 100906) ---
$$ Chloroprene (Neoprene), oil-resistant, wetsuit, cable
$$ Hardness: Shore A 60, Source: DuPont Neoprene TDS, ASTM D2000 BC
$$ E=3.6 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
CR_Neoprene Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100906 1.230e-09    3.6000    0.4990       0.0       0.0       0.0
$
$$ --- NBR_Nitrile Linear (MID 100907) ---
$$ Nitrile (Buna-N), excellent fuel/oil resistance
$$ Hardness: Shore A 70, Source: ASTM D2000 BG, Arlanxeo Perbunan TDS
$$ E=5.6 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
NBR_Nitrile Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100907 1.000e-09    5.6000    0.4990       0.0       0.0       0.0
$
$$ --- EPDM_Standard Linear (MID 100908) ---
$$ Ethylene-Propylene-Diene, weather/ozone resistant
$$ Hardness: Shore A 65, Source: ASTM D2000 CA, ISO 4097, Dow Nordel TDS
$$ E=4.3 MPa (linear approximation for small strain ≤10%)
*MAT_ELASTIC_TITLE
EPDM_Standard Linear
$      MID        RO         E        PR        DA        DB  NOT_USED
    100908 8.600e-10    4.3000    0.4990       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MOONEY-RIVLIN HYPERELASTIC (MAT_027, standard)
$ ========================================================================
$
$$ --- NR_SoftSuperior Mooney-Rivlin (MID 110901) ---
$$ Natural Rubber, soft Shore A 40, vibration mount
$$ Hardness: Shore A 40, Source: Treloar 1975, Morton Rubber Technology 3rd ed, ASTM D2000 AA
$$ C10=0.267 MPa, C01=0.067 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
NR_SoftSuperior Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110901 9.200e-10    0.2670    0.0670    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- NR_Standard Mooney-Rivlin (MID 110902) ---
$$ Natural Rubber Shore A 60, general purpose gasket
$$ Hardness: Shore A 60, Source: ASTM D2000 AA, Arruda-Boyce 1993
$$ C10=0.6 MPa, C01=0.15 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
NR_Standard Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110902 9.300e-10    0.6000    0.1500    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- SBR_TireTread Mooney-Rivlin (MID 110903) ---
$$ Styrene-Butadiene tire tread compound
$$ Hardness: Shore A 65, Source: Rubber Technology (Morton 1987), ASTM D2000 BA
$$ C10=0.7 MPa, C01=0.2 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
SBR_TireTread Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110903 9.400e-10    0.7000    0.2000    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- BR_Butadiene Mooney-Rivlin (MID 110904) ---
$$ Butadiene Rubber, tire sidewall, abrasion resistant
$$ Hardness: Shore A 55, Source: ASTM D2000 BA, Morton 1987
$$ C10=0.48 MPa, C01=0.12 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
BR_Butadiene Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110904 9.300e-10    0.4800    0.1200    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- IIR_Butyl Mooney-Rivlin (MID 110905) ---
$$ Butyl rubber (IIR), excellent gas impermeability, damping
$$ Hardness: Shore A 55, Source: ASTM D2000 AA, ExxonMobil Butyl TDS
$$ C10=0.45 MPa, C01=0.12 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
IIR_Butyl Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110905 9.200e-10    0.4500    0.1200    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- CR_Neoprene Mooney-Rivlin (MID 110906) ---
$$ Chloroprene (Neoprene), oil-resistant, wetsuit, cable
$$ Hardness: Shore A 60, Source: DuPont Neoprene TDS, ASTM D2000 BC
$$ C10=0.6 MPa, C01=0.15 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
CR_Neoprene Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110906 1.230e-09    0.6000    0.1500    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- NBR_Nitrile Mooney-Rivlin (MID 110907) ---
$$ Nitrile (Buna-N), excellent fuel/oil resistance
$$ Hardness: Shore A 70, Source: ASTM D2000 BG, Arlanxeo Perbunan TDS
$$ C10=0.93 MPa, C01=0.2 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
NBR_Nitrile Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110907 1.000e-09    0.9300    0.2000    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$$ --- EPDM_Standard Mooney-Rivlin (MID 110908) ---
$$ Ethylene-Propylene-Diene, weather/ozone resistant
$$ Hardness: Shore A 65, Source: ASTM D2000 CA, ISO 4097, Dow Nordel TDS
$$ C10=0.72 MPa, C01=0.17 MPa
$$ W = C10*(I1-3) + C01*(I2-3)
*MAT_MOONEY-RIVLIN_RUBBER_TITLE
EPDM_Standard Mooney-Rivlin
$      MID        RO         A         B        PR       REF       SGL       SW
    110908 8.600e-10    0.7200    0.1700    0.4990       0.0       0.0       0.0
$                  LCID (optional uniaxial test data)
                     0
$
$ ========================================================================
$ 3. OGDEN HYPERELASTIC + PRONY VISCOELASTIC (MAT_077_O)
$ ========================================================================
$
$$ --- NR_SoftSuperior Ogden Viscoelastic (MID 130901) ---
$$ Natural Rubber, soft Shore A 40, vibration mount
$$ Hardness: Shore A 40, Source: Treloar 1975, Morton Rubber Technology 3rd ed, ASTM D2000 AA
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
NR_SoftSuperior Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130901 9.200e-10    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    0.6300    1.3000    0.0012    5.0000   -0.0100   -2.0000    0.0000    0.0000
    0.2000    100.00
    0.1500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- NR_Standard Ogden Viscoelastic (MID 130902) ---
$$ Natural Rubber Shore A 60, general purpose gasket
$$ Hardness: Shore A 60, Source: ASTM D2000 AA, Arruda-Boyce 1993
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
NR_Standard Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130902 9.300e-10    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.5000    1.3000    0.0020    5.0000   -0.0200   -2.0000    0.0000    0.0000
    0.1500    100.00
    0.1000   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- SBR_TireTread Ogden Viscoelastic (MID 130903) ---
$$ Styrene-Butadiene tire tread compound
$$ Hardness: Shore A 65, Source: Rubber Technology (Morton 1987), ASTM D2000 BA
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
SBR_TireTread Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130903 9.400e-10    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.8000    1.3000    0.0025    5.0000   -0.0250   -2.0000    0.0000    0.0000
    0.2500    100.00
    0.1800   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- BR_Butadiene Ogden Viscoelastic (MID 130904) ---
$$ Butadiene Rubber, tire sidewall, abrasion resistant
$$ Hardness: Shore A 55, Source: ASTM D2000 BA, Morton 1987
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
BR_Butadiene Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130904 9.300e-10    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.2000    1.3000    0.0015    5.0000   -0.0150   -2.0000    0.0000    0.0000
    0.1800    100.00
    0.1200   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- IIR_Butyl Ogden Viscoelastic (MID 130905) ---
$$ Butyl rubber (IIR), excellent gas impermeability, damping
$$ Hardness: Shore A 55, Source: ASTM D2000 AA, ExxonMobil Butyl TDS
$$ Ogden 3-term + 3 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
IIR_Butyl Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130905 9.200e-10    0.4990         3         3       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.2000    1.3000    0.0018    5.0000   -0.0180   -2.0000    0.0000    0.0000
    0.4000     50.00
    0.3000    500.00
    0.2000   5000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- CR_Neoprene Ogden Viscoelastic (MID 130906) ---
$$ Chloroprene (Neoprene), oil-resistant, wetsuit, cable
$$ Hardness: Shore A 60, Source: DuPont Neoprene TDS, ASTM D2000 BC
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
CR_Neoprene Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130906 1.230e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.5000    1.3000    0.0020    5.0000   -0.0200   -2.0000    0.0000    0.0000
    0.2000    100.00
    0.1500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- NBR_Nitrile Ogden Viscoelastic (MID 130907) ---
$$ Nitrile (Buna-N), excellent fuel/oil resistance
$$ Hardness: Shore A 70, Source: ASTM D2000 BG, Arlanxeo Perbunan TDS
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
NBR_Nitrile Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130907 1.000e-09    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    2.2000    1.3000    0.0030    5.0000   -0.0300   -2.0000    0.0000    0.0000
    0.2200    100.00
    0.1500   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
$$ --- EPDM_Standard Ogden Viscoelastic (MID 130908) ---
$$ Ethylene-Propylene-Diene, weather/ozone resistant
$$ Hardness: Shore A 65, Source: ASTM D2000 CA, ISO 4097, Dow Nordel TDS
$$ Ogden 3-term + 2 Prony terms
*MAT_HYPERELASTIC_RUBBER_TITLE
EPDM_Standard Ogden Viscoelastic
$      MID        RO        PR         N        NV         G      SIGF       REF
    130908 8.600e-10    0.4990         3         2       0.0       0.0       0.0
$      SGL        SW        ST      LCID      DATA     LCID2
       0.0       0.0       0.0         0         0         0
$      MU1    ALPHA1       MU2    ALPHA2       MU3    ALPHA3       MU4    ALPHA4
    1.8000    1.3000    0.0025    5.0000   -0.0250   -2.0000    0.0000    0.0000
    0.1500    100.00
    0.1000   1000.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
    0.0000      0.00
$
*END
