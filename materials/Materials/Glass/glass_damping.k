$ ========================================================================
$ GLASS DAMPING LIBRARY (Rayleigh for MAT_001 elastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios:
$   Cover glass (soda-lime, aluminosilicate, Gorilla): 0.2%
$   Sapphire: 0.2%
$   Very low — brittle amorphous/crystalline, minimal internal friction
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   15       Glass                          0.0020  1.257e+01  3.183e-07
$   101001   SodaLime_Standard Linear       0.0020  1.257e+01  3.183e-07
$   101002   Aluminosilicate_Dragontrail Linear 0.0020  1.257e+01  3.183e-07
$   101003   GorillaGlass_3 Linear          0.0020  1.257e+01  3.183e-07
$   101004   GorillaGlass_5 Linear          0.0020  1.257e+01  3.183e-07
$   101005   GorillaGlass_6 Linear          0.0020  1.257e+01  3.183e-07
$   101006   GorillaGlass_Victus Linear     0.0020  1.257e+01  3.183e-07
$   101011   Sapphire_Cplane Linear         0.0020  1.257e+01  3.183e-07
$   101012   Sapphire_Aplane Linear         0.0020  1.257e+01  3.183e-07
$   111001   SodaLime_Standard Elastic+Erode 0.0020  1.257e+01  3.183e-07
$   111002   Aluminosilicate_Dragontrail Elastic+Erode 0.0020  1.257e+01  3.183e-07
$   111003   GorillaGlass_3 Elastic+Erode   0.0020  1.257e+01  3.183e-07
$   111004   GorillaGlass_5 Elastic+Erode   0.0020  1.257e+01  3.183e-07
$   111005   GorillaGlass_6 Elastic+Erode   0.0020  1.257e+01  3.183e-07
$   111006   GorillaGlass_Victus Elastic+Erode 0.0020  1.257e+01  3.183e-07
$   111011   Sapphire_Cplane Elastic+Erode  0.0020  1.257e+01  3.183e-07
$   111012   Sapphire_Aplane Elastic+Erode  0.0020  1.257e+01  3.183e-07
$ ========================================================================
*KEYWORD
$
$$ --- Glass (MID 15) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Glass_parts
$      SID       DA1       DA2       DA3       DA4
    800015       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    800015         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    800015 3.183e-07
$
$$ --- SodaLime_Standard Linear (MID 101001) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
SodaLime_Standard_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901001       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901001         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901001 3.183e-07
$
$$ --- Aluminosilicate_Dragontrail Linear (MID 101002) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Aluminosilicate_Dragontrail_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901002       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901002         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901002 3.183e-07
$
$$ --- GorillaGlass_3 Linear (MID 101003) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_3_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901003       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901003         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901003 3.183e-07
$
$$ --- GorillaGlass_5 Linear (MID 101004) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_5_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901004       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901004         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901004 3.183e-07
$
$$ --- GorillaGlass_6 Linear (MID 101005) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_6_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901005       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901005         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901005 3.183e-07
$
$$ --- GorillaGlass_Victus Linear (MID 101006) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_Victus_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901006       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901006         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901006 3.183e-07
$
$$ --- Sapphire_Cplane Linear (MID 101011) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Sapphire_Cplane_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901011       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901011         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901011 3.183e-07
$
$$ --- Sapphire_Aplane Linear (MID 101012) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Sapphire_Aplane_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901012       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901012         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901012 3.183e-07
$
$$ --- SodaLime_Standard Elastic+Erode (MID 111001) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
SodaLime_Standard_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911001       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911001         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911001 3.183e-07
$
$$ --- Aluminosilicate_Dragontrail Elastic+Erode (MID 111002) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Aluminosilicate_Dragontrail_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911002       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911002         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911002 3.183e-07
$
$$ --- GorillaGlass_3 Elastic+Erode (MID 111003) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_3_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911003       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911003         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911003 3.183e-07
$
$$ --- GorillaGlass_5 Elastic+Erode (MID 111004) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_5_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911004       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911004         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911004 3.183e-07
$
$$ --- GorillaGlass_6 Elastic+Erode (MID 111005) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_6_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911005       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911005         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911005 3.183e-07
$
$$ --- GorillaGlass_Victus Elastic+Erode (MID 111006) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
GorillaGlass_Victus_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911006       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911006         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911006 3.183e-07
$
$$ --- Sapphire_Cplane Elastic+Erode (MID 111011) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Sapphire_Cplane_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911011       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911011         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911011 3.183e-07
$
$$ --- Sapphire_Aplane Elastic+Erode (MID 111012) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Sapphire_Aplane_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911012       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911012         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911012 3.183e-07
$
$ ========================================================================
$ END
$ ========================================================================
*END
