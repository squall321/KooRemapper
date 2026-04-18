$ ========================================================================
$ CERAMIC DAMPING LIBRARY (Rayleigh for MAT_001 elastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios:
$   Structural ceramics (Al2O3, AlN, ZrO2, Si3N4, SiC): 0.3%
$   Piezoelectric ceramics (PZT): 0.3%  (dielectric loss separate)
$   LCP (Liquid Crystal Polymer): 0.3%
$   Low — sintered/polycrystalline, grain boundary friction only
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   101021   Al2O3_96pct Linear             0.0030  1.885e+01  4.775e-07
$   101022   Al2O3_99p5pct Linear           0.0030  1.885e+01  4.775e-07
$   101023   AlN_HighK Linear               0.0030  1.885e+01  4.775e-07
$   101024   ZrO2_YTZP Linear               0.0030  1.885e+01  4.775e-07
$   101025   Si3N4 Linear                   0.0030  1.885e+01  4.775e-07
$   101026   SiC Linear                     0.0030  1.885e+01  4.775e-07
$   101031   PZT_5A_soft Linear             0.0030  1.885e+01  4.775e-07
$   101032   PZT_4_hard Linear              0.0030  1.885e+01  4.775e-07
$   101033   AlN_piezo_thinfilm Linear      0.0030  1.885e+01  4.775e-07
$   101041   LCP_Vectra_A950 Linear         0.0030  1.885e+01  4.775e-07
$   101042   LCP_Vectra_E130i Linear        0.0030  1.885e+01  4.775e-07
$   111021   Al2O3_96pct Elastic+Erode      0.0030  1.885e+01  4.775e-07
$   111022   Al2O3_99p5pct Elastic+Erode    0.0030  1.885e+01  4.775e-07
$   111023   AlN_HighK Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111024   ZrO2_YTZP Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111025   Si3N4 Elastic+Erode            0.0030  1.885e+01  4.775e-07
$   111026   SiC Elastic+Erode              0.0030  1.885e+01  4.775e-07
$   111031   PZT_5A_soft Elastic+Erode      0.0030  1.885e+01  4.775e-07
$   111032   PZT_4_hard Elastic+Erode       0.0030  1.885e+01  4.775e-07
$   111033   AlN_piezo_thinfilm Elastic+Erode 0.0030  1.885e+01  4.775e-07
$   111041   LCP_Vectra_A950 Elastic+Erode  0.0030  1.885e+01  4.775e-07
$   111042   LCP_Vectra_E130i Elastic+Erode 0.0030  1.885e+01  4.775e-07
$ ========================================================================
*KEYWORD
$
$$ --- Al2O3_96pct Linear (MID 101021) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2O3_96pct_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901021       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901021         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901021 4.775e-07
$
$$ --- Al2O3_99p5pct Linear (MID 101022) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2O3_99p5pct_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901022       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901022         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901022 4.775e-07
$
$$ --- AlN_HighK Linear (MID 101023) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
AlN_HighK_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901023       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901023         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901023 4.775e-07
$
$$ --- ZrO2_YTZP Linear (MID 101024) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
ZrO2_YTZP_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901024       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901024         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901024 4.775e-07
$
$$ --- Si3N4 Linear (MID 101025) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Si3N4_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901025       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901025         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901025 4.775e-07
$
$$ --- SiC Linear (MID 101026) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SiC_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901026       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901026         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901026 4.775e-07
$
$$ --- PZT_5A_soft Linear (MID 101031) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
PZT_5A_soft_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901031       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901031         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901031 4.775e-07
$
$$ --- PZT_4_hard Linear (MID 101032) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
PZT_4_hard_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901032       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901032         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901032 4.775e-07
$
$$ --- AlN_piezo_thinfilm Linear (MID 101033) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
AlN_piezo_thinfilm_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901033       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901033         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901033 4.775e-07
$
$$ --- LCP_Vectra_A950 Linear (MID 101041) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
LCP_Vectra_A950_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901041       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901041         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901041 4.775e-07
$
$$ --- LCP_Vectra_E130i Linear (MID 101042) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
LCP_Vectra_E130i_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901042       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901042         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901042 4.775e-07
$
$$ --- Al2O3_96pct Elastic+Erode (MID 111021) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2O3_96pct_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911021       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911021         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911021 4.775e-07
$
$$ --- Al2O3_99p5pct Elastic+Erode (MID 111022) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2O3_99p5pct_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911022       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911022         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911022 4.775e-07
$
$$ --- AlN_HighK Elastic+Erode (MID 111023) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
AlN_HighK_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911023       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911023         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911023 4.775e-07
$
$$ --- ZrO2_YTZP Elastic+Erode (MID 111024) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
ZrO2_YTZP_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911024       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911024         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911024 4.775e-07
$
$$ --- Si3N4 Elastic+Erode (MID 111025) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Si3N4_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911025       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911025         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911025 4.775e-07
$
$$ --- SiC Elastic+Erode (MID 111026) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SiC_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911026       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911026         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911026 4.775e-07
$
$$ --- PZT_5A_soft Elastic+Erode (MID 111031) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
PZT_5A_soft_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911031       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911031         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911031 4.775e-07
$
$$ --- PZT_4_hard Elastic+Erode (MID 111032) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
PZT_4_hard_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911032       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911032         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911032 4.775e-07
$
$$ --- AlN_piezo_thinfilm Elastic+Erode (MID 111033) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
AlN_piezo_thinfilm_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911033       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911033         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911033 4.775e-07
$
$$ --- LCP_Vectra_A950 Elastic+Erode (MID 111041) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
LCP_Vectra_A950_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911041       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911041         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911041 4.775e-07
$
$$ --- LCP_Vectra_E130i Elastic+Erode (MID 111042) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
LCP_Vectra_E130i_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911042       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911042         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911042 4.775e-07
$
$ ========================================================================
$ END
$ ========================================================================
*END
