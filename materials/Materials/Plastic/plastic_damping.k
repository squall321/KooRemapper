$ ========================================================================
$ PLASTIC DAMPING LIBRARY (Rayleigh for all 5 variants)
$ ========================================================================
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios by plastic family:
$   Amorphous glassy (PC, PEI):    2~3%
$   Semi-crystalline (PA, POM):    3~5%
$   ABS, PC/ABS (rubber phase):    4~6%
$   GF-reinforced:                 2~3% (fiber reduces)
$   PP (flexible):                 5~8%
$
$ Part Set SID = MID + 800000
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Standard DAMPING
$ ========================================================================
$
$$ --- PC_Makrolon (linear, MID 100961) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_Makrolon_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900961       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900961         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900961 3.979e-06
$
$$ --- PC_Makrolon (bilinear, MID 110961) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_Makrolon_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910961       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910961         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910961 3.979e-06
$
$$ --- PC_Makrolon (multilinear, MID 120961) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_Makrolon_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920961       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920961         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920961 3.979e-06
$
$$ --- PC_Makrolon (kinematic, MID 130961) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_Makrolon_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930961       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930961         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930961 3.979e-06
$
$$ --- PC_Makrolon (samp1, MID 140961) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_Makrolon_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940961       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940961         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940961 3.979e-06
$
$$ --- ABS_Cycolac (linear, MID 100962) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
ABS_Cycolac_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900962       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900962         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900962 7.958e-06
$
$$ --- ABS_Cycolac (bilinear, MID 110962) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
ABS_Cycolac_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910962       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910962         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910962 7.958e-06
$
$$ --- ABS_Cycolac (multilinear, MID 120962) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
ABS_Cycolac_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920962       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920962         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920962 7.958e-06
$
$$ --- ABS_Cycolac (kinematic, MID 130962) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
ABS_Cycolac_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930962       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930962         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930962 7.958e-06
$
$$ --- ABS_Cycolac (samp1, MID 140962) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
ABS_Cycolac_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940962       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940962         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940962 7.958e-06
$
$$ --- PC_ABS_Cycoloy (linear, MID 100963) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_ABS_Cycoloy_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900963       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900963         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900963 7.162e-06
$
$$ --- PC_ABS_Cycoloy (bilinear, MID 110963) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_ABS_Cycoloy_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910963       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910963         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910963 7.162e-06
$
$$ --- PC_ABS_Cycoloy (multilinear, MID 120963) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_ABS_Cycoloy_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920963       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920963         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920963 7.162e-06
$
$$ --- PC_ABS_Cycoloy (kinematic, MID 130963) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_ABS_Cycoloy_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930963       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930963         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930963 7.162e-06
$
$$ --- PC_ABS_Cycoloy (samp1, MID 140963) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PC_ABS_Cycoloy_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940963       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940963         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940963 7.162e-06
$
$$ --- PA6_Ultramid_B (linear, MID 100964) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA6_Ultramid_B_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900964       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900964         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900964 6.366e-06
$
$$ --- PA6_Ultramid_B (bilinear, MID 110964) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA6_Ultramid_B_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910964       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910964         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910964 6.366e-06
$
$$ --- PA6_Ultramid_B (multilinear, MID 120964) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA6_Ultramid_B_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920964       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920964         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920964 6.366e-06
$
$$ --- PA6_Ultramid_B (kinematic, MID 130964) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA6_Ultramid_B_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930964       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930964         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930964 6.366e-06
$
$$ --- PA6_Ultramid_B (samp1, MID 140964) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA6_Ultramid_B_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940964       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940964         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940964 6.366e-06
$
$$ --- PA66_Zytel (linear, MID 100965) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_Zytel_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900965       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900965         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900965 6.366e-06
$
$$ --- PA66_Zytel (bilinear, MID 110965) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_Zytel_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910965       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910965         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910965 6.366e-06
$
$$ --- PA66_Zytel (multilinear, MID 120965) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_Zytel_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920965       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920965         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920965 6.366e-06
$
$$ --- PA66_Zytel (kinematic, MID 130965) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_Zytel_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930965       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930965         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930965 6.366e-06
$
$$ --- PA66_Zytel (samp1, MID 140965) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_Zytel_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940965       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940965         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940965 6.366e-06
$
$$ --- PBT_Crastin (linear, MID 100966) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_Crastin_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900966       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900966         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900966 7.162e-06
$
$$ --- PBT_Crastin (bilinear, MID 110966) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_Crastin_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910966       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910966         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910966 7.162e-06
$
$$ --- PBT_Crastin (multilinear, MID 120966) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_Crastin_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920966       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920966         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920966 7.162e-06
$
$$ --- PBT_Crastin (kinematic, MID 130966) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_Crastin_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930966       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930966         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930966 7.162e-06
$
$$ --- PBT_Crastin (samp1, MID 140966) ---
$$ zeta=0.0450 (4.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_Crastin_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940966       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940966         0 2.827e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940966 7.162e-06
$
$$ --- POM_Delrin (linear, MID 100967) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
POM_Delrin_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900967       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900967         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900967 6.366e-06
$
$$ --- POM_Delrin (bilinear, MID 110967) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
POM_Delrin_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910967       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910967         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910967 6.366e-06
$
$$ --- POM_Delrin (multilinear, MID 120967) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
POM_Delrin_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920967       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920967         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920967 6.366e-06
$
$$ --- POM_Delrin (kinematic, MID 130967) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
POM_Delrin_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930967       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930967         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930967 6.366e-06
$
$$ --- POM_Delrin (samp1, MID 140967) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
POM_Delrin_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940967       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940967         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940967 6.366e-06
$
$$ --- PP_Homo (linear, MID 100968) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PP_Homo_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900968       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900968         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900968 1.114e-05
$
$$ --- PP_Homo (bilinear, MID 110968) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PP_Homo_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910968       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910968         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910968 1.114e-05
$
$$ --- PP_Homo (multilinear, MID 120968) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PP_Homo_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920968       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920968         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920968 1.114e-05
$
$$ --- PP_Homo (kinematic, MID 130968) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PP_Homo_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930968       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930968         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930968 1.114e-05
$
$$ --- PP_Homo (samp1, MID 140968) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PP_Homo_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940968       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940968         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940968 1.114e-05
$
$ ========================================================================
$ Reinforced DAMPING
$ ========================================================================
$
$$ --- PA66_GF30 (linear, MID 100971) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF30_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900971       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900971         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900971 3.979e-06
$
$$ --- PA66_GF30 (bilinear, MID 110971) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF30_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910971       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910971         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910971 3.979e-06
$
$$ --- PA66_GF30 (multilinear, MID 120971) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF30_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920971       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920971         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920971 3.979e-06
$
$$ --- PA66_GF30 (kinematic, MID 130971) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF30_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930971       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930971         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930971 3.979e-06
$
$$ --- PA66_GF30 (samp1, MID 140971) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF30_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940971       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940971         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940971 3.979e-06
$
$$ --- PA66_GF50 (linear, MID 100972) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF50_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900972       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900972         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900972 3.183e-06
$
$$ --- PA66_GF50 (bilinear, MID 110972) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF50_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910972       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910972         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910972 3.183e-06
$
$$ --- PA66_GF50 (multilinear, MID 120972) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF50_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920972       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920972         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920972 3.183e-06
$
$$ --- PA66_GF50 (kinematic, MID 130972) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF50_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930972       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930972         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930972 3.183e-06
$
$$ --- PA66_GF50 (samp1, MID 140972) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PA66_GF50_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940972       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940972         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940972 3.183e-06
$
$$ --- PBT_GF30 (linear, MID 100973) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_GF30_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900973       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900973         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900973 3.979e-06
$
$$ --- PBT_GF30 (bilinear, MID 110973) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_GF30_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910973       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910973         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910973 3.979e-06
$
$$ --- PBT_GF30 (multilinear, MID 120973) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_GF30_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920973       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920973         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920973 3.979e-06
$
$$ --- PBT_GF30 (kinematic, MID 130973) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_GF30_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930973       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930973         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930973 3.979e-06
$
$$ --- PBT_GF30 (samp1, MID 140973) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PBT_GF30_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940973       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940973         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940973 3.979e-06
$
$$ --- PPS_GF40 (linear, MID 100974) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_GF40_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900974       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900974         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900974 3.183e-06
$
$$ --- PPS_GF40 (bilinear, MID 110974) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_GF40_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910974       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910974         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910974 3.183e-06
$
$$ --- PPS_GF40 (multilinear, MID 120974) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_GF40_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920974       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920974         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920974 3.183e-06
$
$$ --- PPS_GF40 (kinematic, MID 130974) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_GF40_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930974       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930974         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930974 3.183e-06
$
$$ --- PPS_GF40 (samp1, MID 140974) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_GF40_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940974       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940974         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940974 3.183e-06
$
$ ========================================================================
$ HighPerformance DAMPING
$ ========================================================================
$
$$ --- PPS_Ryton (linear, MID 100975) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_Ryton_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900975       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900975         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900975 3.979e-06
$
$$ --- PPS_Ryton (bilinear, MID 110975) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_Ryton_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910975       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910975         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910975 3.979e-06
$
$$ --- PPS_Ryton (multilinear, MID 120975) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_Ryton_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920975       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920975         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920975 3.979e-06
$
$$ --- PPS_Ryton (kinematic, MID 130975) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_Ryton_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930975       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930975         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930975 3.979e-06
$
$$ --- PPS_Ryton (samp1, MID 140975) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PPS_Ryton_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940975       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940975         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940975 3.979e-06
$
$$ --- PEEK_Victrex (linear, MID 100976) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEEK_Victrex_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900976       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900976         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900976 3.979e-06
$
$$ --- PEEK_Victrex (bilinear, MID 110976) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEEK_Victrex_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910976       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910976         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910976 3.979e-06
$
$$ --- PEEK_Victrex (multilinear, MID 120976) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEEK_Victrex_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920976       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920976         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920976 3.979e-06
$
$$ --- PEEK_Victrex (kinematic, MID 130976) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEEK_Victrex_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930976       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930976         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930976 3.979e-06
$
$$ --- PEEK_Victrex (samp1, MID 140976) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEEK_Victrex_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940976       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940976         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940976 3.979e-06
$
$$ --- PEI_Ultem (linear, MID 100977) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEI_Ultem_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900977       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900977         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900977 3.979e-06
$
$$ --- PEI_Ultem (bilinear, MID 110977) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEI_Ultem_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910977       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910977         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910977 3.979e-06
$
$$ --- PEI_Ultem (multilinear, MID 120977) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEI_Ultem_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920977       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920977         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920977 3.979e-06
$
$$ --- PEI_Ultem (kinematic, MID 130977) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEI_Ultem_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930977       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930977         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930977 3.979e-06
$
$$ --- PEI_Ultem (samp1, MID 140977) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PEI_Ultem_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940977       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940977         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940977 3.979e-06
$
$ ========================================================================
$ Optical DAMPING
$ ========================================================================
$
$$ --- PMMA_Plexiglas (linear, MID 100981) ---
$$ zeta=0.0300 (3.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PMMA_Plexiglas_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900981       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900981         0 1.885e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900981 4.775e-06
$
$$ --- PMMA_Plexiglas (bilinear, MID 110981) ---
$$ zeta=0.0300 (3.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PMMA_Plexiglas_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910981       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910981         0 1.885e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910981 4.775e-06
$
$$ --- PMMA_Plexiglas (multilinear, MID 120981) ---
$$ zeta=0.0300 (3.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PMMA_Plexiglas_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920981       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920981         0 1.885e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920981 4.775e-06
$
$$ --- PMMA_Plexiglas (kinematic, MID 130981) ---
$$ zeta=0.0300 (3.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PMMA_Plexiglas_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930981       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930981         0 1.885e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930981 4.775e-06
$
$$ --- PMMA_Plexiglas (samp1, MID 140981) ---
$$ zeta=0.0300 (3.00%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
PMMA_Plexiglas_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940981       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940981         0 1.885e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940981 4.775e-06
$
$$ --- COP_Zeonex (linear, MID 100982) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COP_Zeonex_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900982       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900982         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900982 3.979e-06
$
$$ --- COP_Zeonex (bilinear, MID 110982) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COP_Zeonex_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910982       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910982         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910982 3.979e-06
$
$$ --- COP_Zeonex (multilinear, MID 120982) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COP_Zeonex_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920982       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920982         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920982 3.979e-06
$
$$ --- COP_Zeonex (kinematic, MID 130982) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COP_Zeonex_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930982       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930982         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930982 3.979e-06
$
$$ --- COP_Zeonex (samp1, MID 140982) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COP_Zeonex_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940982       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940982         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940982 3.979e-06
$
$$ --- COC_TOPAS (linear, MID 100983) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COC_TOPAS_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900983       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900983         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900983 3.979e-06
$
$$ --- COC_TOPAS (bilinear, MID 110983) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COC_TOPAS_bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910983       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910983         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910983 3.979e-06
$
$$ --- COC_TOPAS (multilinear, MID 120983) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COC_TOPAS_multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    920983       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    920983         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    920983 3.979e-06
$
$$ --- COC_TOPAS (kinematic, MID 130983) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COC_TOPAS_kinematic_parts
$      SID       DA1       DA2       DA3       DA4
    930983       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930983         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930983 3.979e-06
$
$$ --- COC_TOPAS (samp1, MID 140983) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
*SET_PART_LIST_TITLE
COC_TOPAS_samp1_parts
$      SID       DA1       DA2       DA3       DA4
    940983       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940983         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940983 3.979e-06
$
*END
