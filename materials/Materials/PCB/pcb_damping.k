$ ========================================================================
$ PCB COMPONENT DAMPING LIBRARY (Rayleigh for elastic/elastoplastic)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios (by sub-group):
$   Cu foil (rolled/ED):                  0.5%  (work-hardened metal)
$   Solder alloys (SAC305/405, SnPb, etc): 1.0%  (soft, grain boundary)
$   Solder mask / coatings / underfill:    2.0%  (polymer, higher loss)
$ 
$ Note: FR-4 / prepreg (MAT_VISCOELASTIC) have built-in damping, excluded here
$
$ Part Set SID = MID + 800000
$ ========================================================================
$
$ SUMMARY TABLE
$
$   MID      Name                           zeta    alpha(/s)    beta(s)
$   -----------------------------------------------------------------------
$   100401   Cu Rolled Annealed Standard (FPC grade) 0.0050  3.142e+01  7.958e-07
$   100402   Cu Electrodeposited Standard (Rigid PCB) 0.0050  3.142e+01  7.958e-07
$   100403   Cu HTE High Temperature Elongation 0.0050  3.142e+01  7.958e-07
$   100404   Cu HVLP Very High Low Profile  0.0050  3.142e+01  7.958e-07
$   100701   SAC305 Bilinear                0.0100  6.283e+01  1.592e-06
$   100702   SAC405 Bilinear                0.0100  6.283e+01  1.592e-06
$   100703   Sn63Pb37 Bilinear              0.0100  6.283e+01  1.592e-06
$   100704   Sn42Bi58 Bilinear              0.0100  6.283e+01  1.592e-06
$   100705   Pure Sn Bilinear               0.0100  6.283e+01  1.592e-06
$   100801   Solder Mask LPI Epoxy          0.0200  1.257e+02  3.183e-06
$   100802   Solder Mask Dry Film           0.0200  1.257e+02  3.183e-06
$   100803   Conformal Coating Acrylic      0.0200  1.257e+02  3.183e-06
$   100804   Conformal Coating Silicone     0.0200  1.257e+02  3.183e-06
$   100805   Conformal Coating Polyurethane 0.0200  1.257e+02  3.183e-06
$   100806   TIM Silicone Gap Filler        0.0200  1.257e+02  3.183e-06
$   100807   TIM Acrylic Pre-cured          0.0200  1.257e+02  3.183e-06
$   100808   Underfill Epoxy Capillary      0.0200  1.257e+02  3.183e-06
$   100809   Underfill Epoxy High-Tg        0.0200  1.257e+02  3.183e-06
$   100810   Conductive Adhesive Ag Epoxy   0.0200  1.257e+02  3.183e-06
$   110701   SAC305 Multilinear             0.0100  6.283e+01  1.592e-06
$   110702   SAC405 Multilinear             0.0100  6.283e+01  1.592e-06
$   110703   Sn63Pb37 Multilinear           0.0100  6.283e+01  1.592e-06
$   110704   Sn42Bi58 Multilinear           0.0100  6.283e+01  1.592e-06
$   130701   SAC305 Kinematic Pure          0.0100  6.283e+01  1.592e-06
$   140701   SAC305 Kinematic Mixed         0.0100  6.283e+01  1.592e-06
$   140702   SAC405 Kinematic Mixed         0.0100  6.283e+01  1.592e-06
$   140703   Sn63Pb37 Kinematic Mixed       0.0100  6.283e+01  1.592e-06
$ ========================================================================
*KEYWORD
$
$$ --- Cu Rolled Annealed Standard (FPC grade) (MID 100401) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Cu_Rolled_Annealed_Standard_(FPC_grade)_parts
$      SID       DA1       DA2       DA3       DA4
    900401       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900401         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900401 7.958e-07
$
$$ --- Cu Electrodeposited Standard (Rigid PCB) (MID 100402) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Cu_Electrodeposited_Standard_(Rigid_PCB)_parts
$      SID       DA1       DA2       DA3       DA4
    900402       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900402         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900402 7.958e-07
$
$$ --- Cu HTE High Temperature Elongation (MID 100403) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Cu_HTE_High_Temperature_Elongation_parts
$      SID       DA1       DA2       DA3       DA4
    900403       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900403         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900403 7.958e-07
$
$$ --- Cu HVLP Very High Low Profile (MID 100404) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Cu_HVLP_Very_High_Low_Profile_parts
$      SID       DA1       DA2       DA3       DA4
    900404       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900404         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900404 7.958e-07
$
$$ --- SAC305 Bilinear (MID 100701) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC305_Bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    900701       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900701         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900701 1.592e-06
$
$$ --- SAC405 Bilinear (MID 100702) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC405_Bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    900702       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900702         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900702 1.592e-06
$
$$ --- Sn63Pb37 Bilinear (MID 100703) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Sn63Pb37_Bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    900703       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900703         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900703 1.592e-06
$
$$ --- Sn42Bi58 Bilinear (MID 100704) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Sn42Bi58_Bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    900704       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900704         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900704 1.592e-06
$
$$ --- Pure Sn Bilinear (MID 100705) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Pure_Sn_Bilinear_parts
$      SID       DA1       DA2       DA3       DA4
    900705       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900705         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900705 1.592e-06
$
$$ --- Solder Mask LPI Epoxy (MID 100801) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Solder_Mask_LPI_Epoxy_parts
$      SID       DA1       DA2       DA3       DA4
    900801       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900801         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900801 3.183e-06
$
$$ --- Solder Mask Dry Film (MID 100802) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Solder_Mask_Dry_Film_parts
$      SID       DA1       DA2       DA3       DA4
    900802       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900802         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900802 3.183e-06
$
$$ --- Conformal Coating Acrylic (MID 100803) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Conformal_Coating_Acrylic_parts
$      SID       DA1       DA2       DA3       DA4
    900803       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900803         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900803 3.183e-06
$
$$ --- Conformal Coating Silicone (MID 100804) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Conformal_Coating_Silicone_parts
$      SID       DA1       DA2       DA3       DA4
    900804       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900804         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900804 3.183e-06
$
$$ --- Conformal Coating Polyurethane (MID 100805) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Conformal_Coating_Polyurethane_parts
$      SID       DA1       DA2       DA3       DA4
    900805       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900805         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900805 3.183e-06
$
$$ --- TIM Silicone Gap Filler (MID 100806) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
TIM_Silicone_Gap_Filler_parts
$      SID       DA1       DA2       DA3       DA4
    900806       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900806         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900806 3.183e-06
$
$$ --- TIM Acrylic Pre-cured (MID 100807) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
TIM_Acrylic_Pre-cured_parts
$      SID       DA1       DA2       DA3       DA4
    900807       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900807         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900807 3.183e-06
$
$$ --- Underfill Epoxy Capillary (MID 100808) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Underfill_Epoxy_Capillary_parts
$      SID       DA1       DA2       DA3       DA4
    900808       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900808         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900808 3.183e-06
$
$$ --- Underfill Epoxy High-Tg (MID 100809) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Underfill_Epoxy_High-Tg_parts
$      SID       DA1       DA2       DA3       DA4
    900809       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900809         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900809 3.183e-06
$
$$ --- Conductive Adhesive Ag Epoxy (MID 100810) ---
$$ zeta=0.0200 (2.00%) @ f_ref=1000 Hz
$$ alpha=1.257e+02 /s, beta=3.183e-06 s
*SET_PART_LIST_TITLE
Conductive_Adhesive_Ag_Epoxy_parts
$      SID       DA1       DA2       DA3       DA4
    900810       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900810         0 1.257e+02         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900810 3.183e-06
$
$$ --- SAC305 Multilinear (MID 110701) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC305_Multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910701       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910701         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910701 1.592e-06
$
$$ --- SAC405 Multilinear (MID 110702) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC405_Multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910702       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910702         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910702 1.592e-06
$
$$ --- Sn63Pb37 Multilinear (MID 110703) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Sn63Pb37_Multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910703       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910703         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910703 1.592e-06
$
$$ --- Sn42Bi58 Multilinear (MID 110704) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Sn42Bi58_Multilinear_parts
$      SID       DA1       DA2       DA3       DA4
    910704       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910704         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910704 1.592e-06
$
$$ --- SAC305 Kinematic Pure (MID 130701) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC305_Kinematic_Pure_parts
$      SID       DA1       DA2       DA3       DA4
    930701       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930701         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930701 1.592e-06
$
$$ --- SAC305 Kinematic Mixed (MID 140701) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC305_Kinematic_Mixed_parts
$      SID       DA1       DA2       DA3       DA4
    940701       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940701         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940701 1.592e-06
$
$$ --- SAC405 Kinematic Mixed (MID 140702) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
SAC405_Kinematic_Mixed_parts
$      SID       DA1       DA2       DA3       DA4
    940702       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940702         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940702 1.592e-06
$
$$ --- Sn63Pb37 Kinematic Mixed (MID 140703) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Sn63Pb37_Kinematic_Mixed_parts
$      SID       DA1       DA2       DA3       DA4
    940703       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros with actual PART IDs
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940703         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940703 1.592e-06
$
$ ========================================================================
$ END
$ ========================================================================
*END
