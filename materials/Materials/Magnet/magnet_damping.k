$ ========================================================================
$ MAGNET DAMPING LIBRARY (Rayleigh for MAT_001 elastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios:
$   NdFeB sintered (N35/N42/N52):   0.3%  (brittle sintered)
$   SmCo sintered:                  0.3%
$   SrFerrite (Y30):               0.3%
$   NdFeB Bonded (polymer matrix):  0.3%
$   Low — sintered ceramic-like, minimal internal friction
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   101061   NdFeB_N35 Linear               0.0030  1.885e+01  4.775e-07
$   101062   NdFeB_N42 Linear               0.0030  1.885e+01  4.775e-07
$   101063   NdFeB_N52 Linear               0.0030  1.885e+01  4.775e-07
$   101064   SmCo_2_17 Linear               0.0030  1.885e+01  4.775e-07
$   101065   SrFerrite_Y30 Linear           0.0030  1.885e+01  4.775e-07
$   101066   NdFeB_Bonded Linear            0.0030  1.885e+01  4.775e-07
$   111061   NdFeB_N35 Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111062   NdFeB_N42 Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111063   NdFeB_N52 Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111064   SmCo_2_17 Elastic+Erode        0.0030  1.885e+01  4.775e-07
$   111065   SrFerrite_Y30 Elastic+Erode    0.0030  1.885e+01  4.775e-07
$   111066   NdFeB_Bonded Elastic+Erode     0.0030  1.885e+01  4.775e-07
$ ========================================================================
*KEYWORD
$
$$ --- NdFeB_N35 Linear (MID 101061) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N35_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901061       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901061         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901061 4.775e-07
$
$$ --- NdFeB_N42 Linear (MID 101062) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N42_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901062       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901062         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901062 4.775e-07
$
$$ --- NdFeB_N52 Linear (MID 101063) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N52_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901063       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901063         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901063 4.775e-07
$
$$ --- SmCo_2_17 Linear (MID 101064) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SmCo_2_17_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901064       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901064         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901064 4.775e-07
$
$$ --- SrFerrite_Y30 Linear (MID 101065) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SrFerrite_Y30_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901065       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901065         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901065 4.775e-07
$
$$ --- NdFeB_Bonded Linear (MID 101066) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_Bonded_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901066       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901066         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901066 4.775e-07
$
$$ --- NdFeB_N35 Elastic+Erode (MID 111061) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N35_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911061       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911061         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911061 4.775e-07
$
$$ --- NdFeB_N42 Elastic+Erode (MID 111062) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N42_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911062       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911062         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911062 4.775e-07
$
$$ --- NdFeB_N52 Elastic+Erode (MID 111063) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_N52_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911063       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911063         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911063 4.775e-07
$
$$ --- SmCo_2_17 Elastic+Erode (MID 111064) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SmCo_2_17_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911064       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911064         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911064 4.775e-07
$
$$ --- SrFerrite_Y30 Elastic+Erode (MID 111065) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SrFerrite_Y30_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911065       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911065         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911065 4.775e-07
$
$$ --- NdFeB_Bonded Elastic+Erode (MID 111066) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
NdFeB_Bonded_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    911066       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911066         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911066 4.775e-07
$
$ ========================================================================
$ END
$ ========================================================================
*END
