$ ========================================================================
$ RUBBER DAMPING LIBRARY (Rayleigh for MAT_001 / MAT_027 / MAT_077_O)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Note: MAT_077_O (Ogden+Prony) already has viscoelastic damping built in.
$       Additional Rayleigh is OPTIONAL — include only if needed for
$       global structural damping beyond material Prony.
$
$ Damping ratios by rubber family:
$   NR/SBR/BR:           3~5%  (general)
$   IIR (Butyl):         20%   (extreme damping for isolation)
$   NBR/CR/EPDM:         4~6%
$   VMQ (Silicone):      2~3%  (lowest)
$   FKM/FFKM:            3~4%
$   TPU/TPE:             6~8%
$
$ Part Set SID = MID + 800000
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ Natural DAMPING
$ ========================================================================
$
$$ --- NR_SoftSuperior (linear, MID 100901) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
NR_SoftSuperior_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900901       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900901         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900901 7.958e-06
$
$$ --- NR_SoftSuperior (mooney, MID 110901) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
NR_SoftSuperior_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910901       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910901         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910901 7.958e-06
$
$$ --- NR_SoftSuperior (ogden, MID 130901) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
NR_SoftSuperior_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930901       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930901         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930901 7.958e-06
$
$$ --- NR_Standard (linear, MID 100902) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
NR_Standard_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900902       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900902         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900902 6.366e-06
$
$$ --- NR_Standard (mooney, MID 110902) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
NR_Standard_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910902       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910902         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910902 6.366e-06
$
$$ --- NR_Standard (ogden, MID 130902) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
NR_Standard_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930902       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930902         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930902 6.366e-06
$
$$ --- SBR_TireTread (linear, MID 100903) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
SBR_TireTread_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900903       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900903         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900903 7.958e-06
$
$$ --- SBR_TireTread (mooney, MID 110903) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
SBR_TireTread_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910903       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910903         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910903 7.958e-06
$
$$ --- SBR_TireTread (ogden, MID 130903) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
SBR_TireTread_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930903       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930903         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930903 7.958e-06
$
$$ --- BR_Butadiene (linear, MID 100904) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
BR_Butadiene_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900904       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900904         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900904 6.366e-06
$
$$ --- BR_Butadiene (mooney, MID 110904) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
BR_Butadiene_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910904       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910904         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910904 6.366e-06
$
$$ --- BR_Butadiene (ogden, MID 130904) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
BR_Butadiene_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930904       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930904         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930904 6.366e-06
$
$$ --- IIR_Butyl (linear, MID 100905) ---
$$ zeta=0.2000 (20.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+03 /s, beta=3.183e-05 s
*SET_PART_LIST_TITLE
IIR_Butyl_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900905       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900905         0 1.257e+03         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900905 3.183e-05
$
$$ --- IIR_Butyl (mooney, MID 110905) ---
$$ zeta=0.2000 (20.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+03 /s, beta=3.183e-05 s
*SET_PART_LIST_TITLE
IIR_Butyl_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910905       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910905         0 1.257e+03         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910905 3.183e-05
$
$$ --- IIR_Butyl (ogden, MID 130905) ---
$$ zeta=0.2000 (20.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+03 /s, beta=3.183e-05 s
*SET_PART_LIST_TITLE
IIR_Butyl_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930905       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930905         0 1.257e+03         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930905 3.183e-05
$
$$ --- CR_Neoprene (linear, MID 100906) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
CR_Neoprene_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900906       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900906         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900906 7.958e-06
$
$$ --- CR_Neoprene (mooney, MID 110906) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
CR_Neoprene_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910906       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910906         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910906 7.958e-06
$
$$ --- CR_Neoprene (ogden, MID 130906) ---
$$ zeta=0.0500 (5.00%) @ f_ref=1000 Hz
$$ alpha=3.142e+02 /s, beta=7.958e-06 s
*SET_PART_LIST_TITLE
CR_Neoprene_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930906       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930906         0 3.142e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930906 7.958e-06
$
$$ --- NBR_Nitrile (linear, MID 100907) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
NBR_Nitrile_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900907       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900907         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900907 9.549e-06
$
$$ --- NBR_Nitrile (mooney, MID 110907) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
NBR_Nitrile_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910907       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910907         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910907 9.549e-06
$
$$ --- NBR_Nitrile (ogden, MID 130907) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
NBR_Nitrile_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930907       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930907         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930907 9.549e-06
$
$$ --- EPDM_Standard (linear, MID 100908) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
EPDM_Standard_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900908       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900908         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900908 6.366e-06
$
$$ --- EPDM_Standard (mooney, MID 110908) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
EPDM_Standard_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910908       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910908         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910908 6.366e-06
$
$$ --- EPDM_Standard (ogden, MID 130908) ---
$$ zeta=0.0400 (4.00%) @ f_ref=1000 Hz
$$ alpha=2.513e+02 /s, beta=6.366e-06 s
*SET_PART_LIST_TITLE
EPDM_Standard_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930908       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930908         0 2.513e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930908 6.366e-06
$
$ ========================================================================
$ HighPerformance DAMPING
$ ========================================================================
$
$$ --- VMQ_Silicone_Std (linear, MID 100911) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Std_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900911       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900911         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900911 3.979e-06
$
$$ --- VMQ_Silicone_Std (mooney, MID 110911) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Std_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910911       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910911         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910911 3.979e-06
$
$$ --- VMQ_Silicone_Std (ogden, MID 130911) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Std_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930911       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930911         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930911 3.979e-06
$
$$ --- VMQ_Silicone_Firm (linear, MID 100912) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Firm_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900912       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900912         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900912 3.979e-06
$
$$ --- VMQ_Silicone_Firm (mooney, MID 110912) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Firm_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910912       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910912         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910912 3.979e-06
$
$$ --- VMQ_Silicone_Firm (ogden, MID 130912) ---
$$ zeta=0.0250 (2.50%) @ f_ref=1000 Hz
$$ alpha=1.571e+02 /s, beta=3.979e-06 s
*SET_PART_LIST_TITLE
VMQ_Silicone_Firm_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930912       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930912         0 1.571e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930912 3.979e-06
$
$$ --- FKM_Viton (linear, MID 100913) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FKM_Viton_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900913       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900913         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900913 5.570e-06
$
$$ --- FKM_Viton (mooney, MID 110913) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FKM_Viton_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910913       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910913         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910913 5.570e-06
$
$$ --- FKM_Viton (ogden, MID 130913) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FKM_Viton_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930913       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930913         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930913 5.570e-06
$
$$ --- FFKM_Kalrez (linear, MID 100914) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FFKM_Kalrez_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900914       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900914         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900914 5.570e-06
$
$$ --- FFKM_Kalrez (mooney, MID 110914) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FFKM_Kalrez_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910914       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910914         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910914 5.570e-06
$
$$ --- FFKM_Kalrez (ogden, MID 130914) ---
$$ zeta=0.0350 (3.50%) @ f_ref=1000 Hz
$$ alpha=2.199e+02 /s, beta=5.570e-06 s
*SET_PART_LIST_TITLE
FFKM_Kalrez_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930914       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930914         0 2.199e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930914 5.570e-06
$
$ ========================================================================
$ TPE DAMPING
$ ========================================================================
$
$$ --- TPU_Hard_85A (linear, MID 100921) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
$$ alpha=4.398e+02 /s, beta=1.114e-05 s
*SET_PART_LIST_TITLE
TPU_Hard_85A_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900921       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900921         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900921 1.114e-05
$
$$ --- TPU_Hard_85A (mooney, MID 110921) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
$$ alpha=4.398e+02 /s, beta=1.114e-05 s
*SET_PART_LIST_TITLE
TPU_Hard_85A_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910921       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910921         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910921 1.114e-05
$
$$ --- TPU_Hard_85A (ogden, MID 130921) ---
$$ zeta=0.0700 (7.00%) @ f_ref=1000 Hz
$$ alpha=4.398e+02 /s, beta=1.114e-05 s
*SET_PART_LIST_TITLE
TPU_Hard_85A_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930921       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930921         0 4.398e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930921 1.114e-05
$
$$ --- TPE_S_SBS (linear, MID 100922) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
TPE_S_SBS_linear_parts
$      SID       DA1       DA2       DA3       DA4
    900922       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900922         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900922 9.549e-06
$
$$ --- TPE_S_SBS (mooney, MID 110922) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
TPE_S_SBS_mooney_parts
$      SID       DA1       DA2       DA3       DA4
    910922       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910922         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910922 9.549e-06
$
$$ --- TPE_S_SBS (ogden, MID 130922) ---
$$ zeta=0.0600 (6.00%) @ f_ref=1000 Hz
$$ alpha=3.770e+02 /s, beta=9.549e-06 s
*SET_PART_LIST_TITLE
TPE_S_SBS_ogden_parts
$      SID       DA1       DA2       DA3       DA4
    930922       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930922         0 3.770e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930922 9.549e-06
$
*END
