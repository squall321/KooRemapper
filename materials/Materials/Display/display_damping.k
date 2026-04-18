$ ========================================================================
$ DISPLAY DAMPING LIBRARY (Rayleigh for MAT_001 / MAT_002 elastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios:
$   OLED/LCD/MicroLED layered film stacks: 0.5%
$   Polymer+glass+metal composite layers — moderate internal friction
$   Orthotropic variants included (same damping as isotropic)
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   101051   Display_RigidOLED Linear       0.0050  3.142e+01  7.958e-07
$   101052   Display_FlexibleOLED Linear    0.0050  3.142e+01  7.958e-07
$   101053   Display_FoldableOLED_UTG Linear 0.0050  3.142e+01  7.958e-07
$   101054   Display_FoldableOLED_CPI Linear 0.0050  3.142e+01  7.958e-07
$   101055   Display_LCD_IPS Linear         0.0050  3.142e+01  7.958e-07
$   101056   Display_MicroLED Linear        0.0050  3.142e+01  7.958e-07
$   111051   Display_RigidOLED Orthotropic  0.0050  3.142e+01  7.958e-07
$   111052   Display_FlexibleOLED Orthotropic 0.0050  3.142e+01  7.958e-07
$   111053   Display_FoldableOLED_UTG Orthotropic 0.0050  3.142e+01  7.958e-07
$   111054   Display_FoldableOLED_CPI Orthotropic 0.0050  3.142e+01  7.958e-07
$   111055   Display_LCD_IPS Orthotropic    0.0050  3.142e+01  7.958e-07
$   111056   Display_MicroLED Orthotropic   0.0050  3.142e+01  7.958e-07
$   121051   Display_RigidOLED Elastic+Erode 0.0050  3.142e+01  7.958e-07
$   121052   Display_FlexibleOLED Elastic+Erode 0.0050  3.142e+01  7.958e-07
$   121053   Display_FoldableOLED_UTG Elastic+Erode 0.0050  3.142e+01  7.958e-07
$   121054   Display_FoldableOLED_CPI Elastic+Erode 0.0050  3.142e+01  7.958e-07
$   121055   Display_LCD_IPS Elastic+Erode  0.0050  3.142e+01  7.958e-07
$   121056   Display_MicroLED Elastic+Erode 0.0050  3.142e+01  7.958e-07
$ ========================================================================
*KEYWORD
$
$$ --- Display_RigidOLED Linear (MID 101051) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_RigidOLED_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901051       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901051         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901051 7.958e-07
$
$$ --- Display_FlexibleOLED Linear (MID 101052) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FlexibleOLED_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901052       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901052         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901052 7.958e-07
$
$$ --- Display_FoldableOLED_UTG Linear (MID 101053) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_UTG_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901053       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901053         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901053 7.958e-07
$
$$ --- Display_FoldableOLED_CPI Linear (MID 101054) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_CPI_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901054       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901054         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901054 7.958e-07
$
$$ --- Display_LCD_IPS Linear (MID 101055) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_LCD_IPS_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901055       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901055         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901055 7.958e-07
$
$$ --- Display_MicroLED Linear (MID 101056) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_MicroLED_Linear_parts
$      SID       DA1       DA2       DA3       DA4
    901056       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    901056         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    901056 7.958e-07
$
$$ --- Display_RigidOLED Orthotropic (MID 111051) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_RigidOLED_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911051       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911051         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911051 7.958e-07
$
$$ --- Display_FlexibleOLED Orthotropic (MID 111052) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FlexibleOLED_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911052       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911052         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911052 7.958e-07
$
$$ --- Display_FoldableOLED_UTG Orthotropic (MID 111053) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_UTG_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911053       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911053         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911053 7.958e-07
$
$$ --- Display_FoldableOLED_CPI Orthotropic (MID 111054) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_CPI_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911054       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911054         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911054 7.958e-07
$
$$ --- Display_LCD_IPS Orthotropic (MID 111055) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_LCD_IPS_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911055       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911055         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911055 7.958e-07
$
$$ --- Display_MicroLED Orthotropic (MID 111056) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_MicroLED_Orthotropic_parts
$      SID       DA1       DA2       DA3       DA4
    911056       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    911056         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    911056 7.958e-07
$
$$ --- Display_RigidOLED Elastic+Erode (MID 121051) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_RigidOLED_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921051       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921051         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921051 7.958e-07
$
$$ --- Display_FlexibleOLED Elastic+Erode (MID 121052) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FlexibleOLED_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921052       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921052         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921052 7.958e-07
$
$$ --- Display_FoldableOLED_UTG Elastic+Erode (MID 121053) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_UTG_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921053       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921053         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921053 7.958e-07
$
$$ --- Display_FoldableOLED_CPI Elastic+Erode (MID 121054) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_FoldableOLED_CPI_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921054       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921054         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921054 7.958e-07
$
$$ --- Display_LCD_IPS Elastic+Erode (MID 121055) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_LCD_IPS_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921055       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921055         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921055 7.958e-07
$
$$ --- Display_MicroLED Elastic+Erode (MID 121056) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Display_MicroLED_Elastic+Erode_parts
$      SID       DA1       DA2       DA3       DA4
    921056       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    921056         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    921056 7.958e-07
$
$ ========================================================================
$ END
$ ========================================================================
*END
