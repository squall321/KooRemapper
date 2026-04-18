$ ========================================================================
$ EMC / SEMICONDUCTOR DAMPING LIBRARY (Rayleigh for MAT_001 elastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios:
$   EMC (Epoxy Molding Compound): 1.5%  (filled epoxy, moderate polymer loss)
$   PKG Homogenized (Si+EMC):    1.5%  (volume-averaged)
$ 
$ Note: EMC VE variants (MAT_006) have built-in damping, excluded here
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   100951   EMC High-Tg Green (EME-G700)   0.0150  9.425e+01  2.387e-06
$   100952   EMC Mid-Tg Standard (CEL-9200) 0.0150  9.425e+01  2.387e-06
$   100953   EMC Low-Tg Fast Cure           0.0150  9.425e+01  2.387e-06
$   100954   EMC Low-CTE High-Filled (EME-G780) 0.0150  9.425e+01  2.387e-06
$   100955   EMC Green Ultra-HighTg (GE-series) 0.0150  9.425e+01  2.387e-06
$   100956   EMC Molded Underfill (Namics MUF) 0.0150  9.425e+01  2.387e-06
$   100957   EMC WLP Black (CRP-9800)       0.0150  9.425e+01  2.387e-06
$   100958   EMC Thermal Conductive (GE-100) 0.0150  9.425e+01  2.387e-06
$   100959   PKG Homogenized (Si+EMC)       0.0150  9.425e+01  2.387e-06
$ ========================================================================
*KEYWORD
$
$$ --- EMC High-Tg Green (EME-G700) (MID 100951) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_High-Tg_Green_(EME-G700)_parts
$      SID       DA1       DA2       DA3       DA4
    900951       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900951         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900951 2.387e-06
$
$$ --- EMC Mid-Tg Standard (CEL-9200) (MID 100952) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Mid-Tg_Standard_(CEL-9200)_parts
$      SID       DA1       DA2       DA3       DA4
    900952       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900952         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900952 2.387e-06
$
$$ --- EMC Low-Tg Fast Cure (MID 100953) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Low-Tg_Fast_Cure_parts
$      SID       DA1       DA2       DA3       DA4
    900953       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900953         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900953 2.387e-06
$
$$ --- EMC Low-CTE High-Filled (EME-G780) (MID 100954) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Low-CTE_High-Filled_(EME-G780)_parts
$      SID       DA1       DA2       DA3       DA4
    900954       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900954         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900954 2.387e-06
$
$$ --- EMC Green Ultra-HighTg (GE-series) (MID 100955) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Green_Ultra-HighTg_(GE-series)_parts
$      SID       DA1       DA2       DA3       DA4
    900955       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900955         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900955 2.387e-06
$
$$ --- EMC Molded Underfill (Namics MUF) (MID 100956) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Molded_Underfill_(Namics_MUF)_parts
$      SID       DA1       DA2       DA3       DA4
    900956       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900956         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900956 2.387e-06
$
$$ --- EMC WLP Black (CRP-9800) (MID 100957) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_WLP_Black_(CRP-9800)_parts
$      SID       DA1       DA2       DA3       DA4
    900957       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900957         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900957 2.387e-06
$
$$ --- EMC Thermal Conductive (GE-100) (MID 100958) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
EMC_Thermal_Conductive_(GE-100)_parts
$      SID       DA1       DA2       DA3       DA4
    900958       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900958         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900958 2.387e-06
$
$$ --- PKG Homogenized (Si+EMC) (MID 100959) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
PKG_Homogenized_(Si+EMC)_parts
$      SID       DA1       DA2       DA3       DA4
    900959       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900959         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900959 2.387e-06
$
$ ========================================================================
$ END
$ ========================================================================
*END
