$ ========================================================================
$ METAL DAMPING LIBRARY (Rayleigh for MAT_024 solids)
$ ========================================================================
$ Unit: mm, s, ton
$ Reference frequency: 1000 Hz (6283.2 rad/s)
$
$ Damping ratios (zeta) by material family:
$   SUS austenitic (201,301,304,316):   0.5%  (FCC, solid-sol)
$   SUS martensitic/PH (410,420,17-4PH):0.3%  (rate-insensitive BCC)
$   SUS ferritic (430):                 0.4%
$   Al solid-sol (1xxx,3xxx,5xxx):      0.6~0.8% (Mg content)
$   Al precipitation (2xxx,6xxx,7xxx):  0.3%     (heat treated)
$   ADC12 die cast:                     1.5%     (porosity/defects)
$   Ti CP (Gr1/2/4):                    0.5%
$   Ti-6Al-4V (Gr5,Gr5 ELI):            0.3%     (two-phase)
$   Ti-3Al-2.5V (Gr9):                  0.4%
$
$ Rayleigh coefficients:
$   alpha (mass)      = zeta * omega_ref
$   beta  (stiffness) = zeta / omega_ref
$
$ USAGE:
$   1. INCLUDE this file in your main model
$   2. Each material has a *SET_PART_LIST placeholder with empty PID list
$      Part Set SID = MID + 800000
$      Example: Al6061-T6 bi  -> MID 100535 -> SID 900535
$               Al6061-T6 mu  -> MID 110535 -> SID 910535
$   3. Fill in the actual PART IDs for each material you use
$   4. Damping auto-applied via DAMPING_PART_MASS_SET + STIFFNESS_SET
$ ========================================================================
$
$ SUMMARY TABLE (4 variants per material)
$
$   MID      Variant  Name                    zeta  alpha(/s)  beta(s)
$   -------------------------------------------------------------------------
$   100501  bi_iso   SUS201_annealed         0.0050  3.142e+01  7.958e-07
$   110501  mu_iso   SUS201_annealed         0.0050  3.142e+01  7.958e-07
$   130501  kin_pure SUS201_annealed         0.0050  3.142e+01  7.958e-07
$   140501  kin_mix  SUS201_annealed         0.0050  3.142e+01  7.958e-07
$   100502  bi_iso   SUS301_annealed         0.0050  3.142e+01  7.958e-07
$   110502  mu_iso   SUS301_annealed         0.0050  3.142e+01  7.958e-07
$   130502  kin_pure SUS301_annealed         0.0050  3.142e+01  7.958e-07
$   140502  kin_mix  SUS301_annealed         0.0050  3.142e+01  7.958e-07
$   100503  bi_iso   SUS304_annealed         0.0050  3.142e+01  7.958e-07
$   110503  mu_iso   SUS304_annealed         0.0050  3.142e+01  7.958e-07
$   130503  kin_pure SUS304_annealed         0.0050  3.142e+01  7.958e-07
$   140503  kin_mix  SUS304_annealed         0.0050  3.142e+01  7.958e-07
$   100504  bi_iso   SUS304L_annealed        0.0050  3.142e+01  7.958e-07
$   110504  mu_iso   SUS304L_annealed        0.0050  3.142e+01  7.958e-07
$   130504  kin_pure SUS304L_annealed        0.0050  3.142e+01  7.958e-07
$   140504  kin_mix  SUS304L_annealed        0.0050  3.142e+01  7.958e-07
$   100505  bi_iso   SUS316_annealed         0.0050  3.142e+01  7.958e-07
$   110505  mu_iso   SUS316_annealed         0.0050  3.142e+01  7.958e-07
$   130505  kin_pure SUS316_annealed         0.0050  3.142e+01  7.958e-07
$   140505  kin_mix  SUS316_annealed         0.0050  3.142e+01  7.958e-07
$   100506  bi_iso   SUS316L_annealed        0.0050  3.142e+01  7.958e-07
$   110506  mu_iso   SUS316L_annealed        0.0050  3.142e+01  7.958e-07
$   130506  kin_pure SUS316L_annealed        0.0050  3.142e+01  7.958e-07
$   140506  kin_mix  SUS316L_annealed        0.0050  3.142e+01  7.958e-07
$   100507  bi_iso   SUS410_annealed         0.0030  1.885e+01  4.775e-07
$   110507  mu_iso   SUS410_annealed         0.0030  1.885e+01  4.775e-07
$   130507  kin_pure SUS410_annealed         0.0030  1.885e+01  4.775e-07
$   140507  kin_mix  SUS410_annealed         0.0030  1.885e+01  4.775e-07
$   100508  bi_iso   SUS420_annealed         0.0030  1.885e+01  4.775e-07
$   110508  mu_iso   SUS420_annealed         0.0030  1.885e+01  4.775e-07
$   130508  kin_pure SUS420_annealed         0.0030  1.885e+01  4.775e-07
$   140508  kin_mix  SUS420_annealed         0.0030  1.885e+01  4.775e-07
$   100509  bi_iso   SUS430_annealed         0.0040  2.513e+01  6.366e-07
$   110509  mu_iso   SUS430_annealed         0.0040  2.513e+01  6.366e-07
$   130509  kin_pure SUS430_annealed         0.0040  2.513e+01  6.366e-07
$   140509  kin_mix  SUS430_annealed         0.0040  2.513e+01  6.366e-07
$   100510  bi_iso   SUS_17-4PH_H900         0.0030  1.885e+01  4.775e-07
$   110510  mu_iso   SUS_17-4PH_H900         0.0030  1.885e+01  4.775e-07
$   130510  kin_pure SUS_17-4PH_H900         0.0030  1.885e+01  4.775e-07
$   140510  kin_mix  SUS_17-4PH_H900         0.0030  1.885e+01  4.775e-07
$   100521  bi_iso   Al1050-O                0.0080  5.027e+01  1.273e-06
$   110521  mu_iso   Al1050-O                0.0080  5.027e+01  1.273e-06
$   130521  kin_pure Al1050-O                0.0080  5.027e+01  1.273e-06
$   140521  kin_mix  Al1050-O                0.0080  5.027e+01  1.273e-06
$   100522  bi_iso   Al1100-O                0.0080  5.027e+01  1.273e-06
$   110522  mu_iso   Al1100-O                0.0080  5.027e+01  1.273e-06
$   130522  kin_pure Al1100-O                0.0080  5.027e+01  1.273e-06
$   140522  kin_mix  Al1100-O                0.0080  5.027e+01  1.273e-06
$   100523  bi_iso   Al2024-T3               0.0030  1.885e+01  4.775e-07
$   110523  mu_iso   Al2024-T3               0.0030  1.885e+01  4.775e-07
$   130523  kin_pure Al2024-T3               0.0030  1.885e+01  4.775e-07
$   140523  kin_mix  Al2024-T3               0.0030  1.885e+01  4.775e-07
$   100524  bi_iso   Al3003-H14              0.0060  3.770e+01  9.549e-07
$   110524  mu_iso   Al3003-H14              0.0060  3.770e+01  9.549e-07
$   130524  kin_pure Al3003-H14              0.0060  3.770e+01  9.549e-07
$   140524  kin_mix  Al3003-H14              0.0060  3.770e+01  9.549e-07
$   100525  bi_iso   Al5052-H32              0.0080  5.027e+01  1.273e-06
$   110525  mu_iso   Al5052-H32              0.0080  5.027e+01  1.273e-06
$   130525  kin_pure Al5052-H32              0.0080  5.027e+01  1.273e-06
$   140525  kin_mix  Al5052-H32              0.0080  5.027e+01  1.273e-06
$   100526  bi_iso   Al5083-H116             0.0080  5.027e+01  1.273e-06
$   110526  mu_iso   Al5083-H116             0.0080  5.027e+01  1.273e-06
$   130526  kin_pure Al5083-H116             0.0080  5.027e+01  1.273e-06
$   140526  kin_mix  Al5083-H116             0.0080  5.027e+01  1.273e-06
$   100535  bi_iso   Al6061-T6               0.0030  1.885e+01  4.775e-07
$   110535  mu_iso   Al6061-T6               0.0030  1.885e+01  4.775e-07
$   130535  kin_pure Al6061-T6               0.0030  1.885e+01  4.775e-07
$   140535  kin_mix  Al6061-T6               0.0030  1.885e+01  4.775e-07
$   100536  bi_iso   Al6063-T5               0.0030  1.885e+01  4.775e-07
$   110536  mu_iso   Al6063-T5               0.0030  1.885e+01  4.775e-07
$   130536  kin_pure Al6063-T5               0.0030  1.885e+01  4.775e-07
$   140536  kin_mix  Al6063-T5               0.0030  1.885e+01  4.775e-07
$   100537  bi_iso   Al6063-T6               0.0030  1.885e+01  4.775e-07
$   110537  mu_iso   Al6063-T6               0.0030  1.885e+01  4.775e-07
$   130537  kin_pure Al6063-T6               0.0030  1.885e+01  4.775e-07
$   140537  kin_mix  Al6063-T6               0.0030  1.885e+01  4.775e-07
$   100538  bi_iso   Al7050-T7451            0.0030  1.885e+01  4.775e-07
$   110538  mu_iso   Al7050-T7451            0.0030  1.885e+01  4.775e-07
$   130538  kin_pure Al7050-T7451            0.0030  1.885e+01  4.775e-07
$   140538  kin_mix  Al7050-T7451            0.0030  1.885e+01  4.775e-07
$   100539  bi_iso   Al7075-T6               0.0030  1.885e+01  4.775e-07
$   110539  mu_iso   Al7075-T6               0.0030  1.885e+01  4.775e-07
$   130539  kin_pure Al7075-T6               0.0030  1.885e+01  4.775e-07
$   140539  kin_mix  Al7075-T6               0.0030  1.885e+01  4.775e-07
$   100540  bi_iso   ADC12_diecast           0.0150  9.425e+01  2.387e-06
$   110540  mu_iso   ADC12_diecast           0.0150  9.425e+01  2.387e-06
$   130540  kin_pure ADC12_diecast           0.0150  9.425e+01  2.387e-06
$   140540  kin_mix  ADC12_diecast           0.0150  9.425e+01  2.387e-06
$   100561  bi_iso   Ti_Grade1               0.0050  3.142e+01  7.958e-07
$   110561  mu_iso   Ti_Grade1               0.0050  3.142e+01  7.958e-07
$   130561  kin_pure Ti_Grade1               0.0050  3.142e+01  7.958e-07
$   140561  kin_mix  Ti_Grade1               0.0050  3.142e+01  7.958e-07
$   100562  bi_iso   Ti_Grade2               0.0050  3.142e+01  7.958e-07
$   110562  mu_iso   Ti_Grade2               0.0050  3.142e+01  7.958e-07
$   130562  kin_pure Ti_Grade2               0.0050  3.142e+01  7.958e-07
$   140562  kin_mix  Ti_Grade2               0.0050  3.142e+01  7.958e-07
$   100563  bi_iso   Ti_Grade4               0.0050  3.142e+01  7.958e-07
$   110563  mu_iso   Ti_Grade4               0.0050  3.142e+01  7.958e-07
$   130563  kin_pure Ti_Grade4               0.0050  3.142e+01  7.958e-07
$   140563  kin_mix  Ti_Grade4               0.0050  3.142e+01  7.958e-07
$   100564  bi_iso   Ti6Al4V_Grade5          0.0030  1.885e+01  4.775e-07
$   110564  mu_iso   Ti6Al4V_Grade5          0.0030  1.885e+01  4.775e-07
$   130564  kin_pure Ti6Al4V_Grade5          0.0030  1.885e+01  4.775e-07
$   140564  kin_mix  Ti6Al4V_Grade5          0.0030  1.885e+01  4.775e-07
$   100565  bi_iso   Ti6Al4V_Grade5_ELI      0.0030  1.885e+01  4.775e-07
$   110565  mu_iso   Ti6Al4V_Grade5_ELI      0.0030  1.885e+01  4.775e-07
$   130565  kin_pure Ti6Al4V_Grade5_ELI      0.0030  1.885e+01  4.775e-07
$   140565  kin_mix  Ti6Al4V_Grade5_ELI      0.0030  1.885e+01  4.775e-07
$   100566  bi_iso   Ti3Al2.5V_Grade9        0.0040  2.513e+01  6.366e-07
$   110566  mu_iso   Ti3Al2.5V_Grade9        0.0040  2.513e+01  6.366e-07
$   130566  kin_pure Ti3Al2.5V_Grade9        0.0040  2.513e+01  6.366e-07
$   140566  kin_mix  Ti3Al2.5V_Grade9        0.0040  2.513e+01  6.366e-07
$   100581  bi_iso   Mg_AZ31B_H24            0.0100  6.283e+01  1.592e-06
$   110581  mu_iso   Mg_AZ31B_H24            0.0100  6.283e+01  1.592e-06
$   130581  kin_pure Mg_AZ31B_H24            0.0100  6.283e+01  1.592e-06
$   140581  kin_mix  Mg_AZ31B_H24            0.0100  6.283e+01  1.592e-06
$   100582  bi_iso   Mg_AZ91D_diecast        0.0150  9.425e+01  2.387e-06
$   110582  mu_iso   Mg_AZ91D_diecast        0.0150  9.425e+01  2.387e-06
$   130582  kin_pure Mg_AZ91D_diecast        0.0150  9.425e+01  2.387e-06
$   140582  kin_mix  Mg_AZ91D_diecast        0.0150  9.425e+01  2.387e-06
$   100583  bi_iso   Mg_ZK60A_T5             0.0100  6.283e+01  1.592e-06
$   110583  mu_iso   Mg_ZK60A_T5             0.0100  6.283e+01  1.592e-06
$   130583  kin_pure Mg_ZK60A_T5             0.0100  6.283e+01  1.592e-06
$   140583  kin_mix  Mg_ZK60A_T5             0.0100  6.283e+01  1.592e-06
$   100591  bi_iso   SPCC_mild_steel         0.0030  1.885e+01  4.775e-07
$   110591  mu_iso   SPCC_mild_steel         0.0030  1.885e+01  4.775e-07
$   130591  kin_pure SPCC_mild_steel         0.0030  1.885e+01  4.775e-07
$   140591  kin_mix  SPCC_mild_steel         0.0030  1.885e+01  4.775e-07
$   100592  bi_iso   S45C_medium_carbon      0.0030  1.885e+01  4.775e-07
$   110592  mu_iso   S45C_medium_carbon      0.0030  1.885e+01  4.775e-07
$   130592  kin_pure S45C_medium_carbon      0.0030  1.885e+01  4.775e-07
$   140592  kin_mix  S45C_medium_carbon      0.0030  1.885e+01  4.775e-07
$   100593  bi_iso   SCM440_alloy_steel      0.0030  1.885e+01  4.775e-07
$   110593  mu_iso   SCM440_alloy_steel      0.0030  1.885e+01  4.775e-07
$   130593  kin_pure SCM440_alloy_steel      0.0030  1.885e+01  4.775e-07
$   140593  kin_mix  SCM440_alloy_steel      0.0030  1.885e+01  4.775e-07
$   100601  bi_iso   C26000_Cartridge_Brass  0.0040  2.513e+01  6.366e-07
$   110601  mu_iso   C26000_Cartridge_Brass  0.0040  2.513e+01  6.366e-07
$   130601  kin_pure C26000_Cartridge_Brass  0.0040  2.513e+01  6.366e-07
$   140601  kin_mix  C26000_Cartridge_Brass  0.0040  2.513e+01  6.366e-07
$   100602  bi_iso   C36000_FreeCutting_Brass  0.0040  2.513e+01  6.366e-07
$   110602  mu_iso   C36000_FreeCutting_Brass  0.0040  2.513e+01  6.366e-07
$   130602  kin_pure C36000_FreeCutting_Brass  0.0040  2.513e+01  6.366e-07
$   140602  kin_mix  C36000_FreeCutting_Brass  0.0040  2.513e+01  6.366e-07
$   100603  bi_iso   C51000_Phosphor_Bronze  0.0050  3.142e+01  7.958e-07
$   110603  mu_iso   C51000_Phosphor_Bronze  0.0050  3.142e+01  7.958e-07
$   130603  kin_pure C51000_Phosphor_Bronze  0.0050  3.142e+01  7.958e-07
$   140603  kin_mix  C51000_Phosphor_Bronze  0.0050  3.142e+01  7.958e-07
$   100611  bi_iso   Inconel_625_annealed    0.0030  1.885e+01  4.775e-07
$   110611  mu_iso   Inconel_625_annealed    0.0030  1.885e+01  4.775e-07
$   130611  kin_pure Inconel_625_annealed    0.0030  1.885e+01  4.775e-07
$   140611  kin_mix  Inconel_625_annealed    0.0030  1.885e+01  4.775e-07
$   100612  bi_iso   Inconel_718_aged        0.0030  1.885e+01  4.775e-07
$   110612  mu_iso   Inconel_718_aged        0.0030  1.885e+01  4.775e-07
$   130612  kin_pure Inconel_718_aged        0.0030  1.885e+01  4.775e-07
$   140612  kin_mix  Inconel_718_aged        0.0030  1.885e+01  4.775e-07
$   100621  bi_iso   Tungsten_99pct          0.0020  1.257e+01  3.183e-07
$   110621  mu_iso   Tungsten_99pct          0.0020  1.257e+01  3.183e-07
$   130621  kin_pure Tungsten_99pct          0.0020  1.257e+01  3.183e-07
$   140621  kin_mix  Tungsten_99pct          0.0020  1.257e+01  3.183e-07
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ SUS DAMPING
$ ========================================================================
$
$$ --- SUS201_annealed (bi_iso, MID 100501) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS201_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900501       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900501         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900501 7.958e-07
$
$$ --- SUS201_annealed (mu_iso, MID 110501) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS201_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910501       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910501         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910501 7.958e-07
$
$$ --- SUS201_annealed (kin_pure, MID 130501) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS201_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930501       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930501         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930501 7.958e-07
$
$$ --- SUS201_annealed (kin_mix, MID 140501) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS201_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940501       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940501         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940501 7.958e-07
$
$$ --- SUS301_annealed (bi_iso, MID 100502) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS301_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900502       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900502         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900502 7.958e-07
$
$$ --- SUS301_annealed (mu_iso, MID 110502) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS301_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910502       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910502         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910502 7.958e-07
$
$$ --- SUS301_annealed (kin_pure, MID 130502) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS301_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930502       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930502         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930502 7.958e-07
$
$$ --- SUS301_annealed (kin_mix, MID 140502) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS301_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940502       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940502         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940502 7.958e-07
$
$$ --- SUS304_annealed (bi_iso, MID 100503) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900503       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900503         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900503 7.958e-07
$
$$ --- SUS304_annealed (mu_iso, MID 110503) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910503       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910503         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910503 7.958e-07
$
$$ --- SUS304_annealed (kin_pure, MID 130503) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930503       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930503         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930503 7.958e-07
$
$$ --- SUS304_annealed (kin_mix, MID 140503) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940503       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940503         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940503 7.958e-07
$
$$ --- SUS304L_annealed (bi_iso, MID 100504) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304L_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900504       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900504         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900504 7.958e-07
$
$$ --- SUS304L_annealed (mu_iso, MID 110504) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304L_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910504       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910504         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910504 7.958e-07
$
$$ --- SUS304L_annealed (kin_pure, MID 130504) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304L_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930504       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930504         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930504 7.958e-07
$
$$ --- SUS304L_annealed (kin_mix, MID 140504) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS304L_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940504       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940504         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940504 7.958e-07
$
$$ --- SUS316_annealed (bi_iso, MID 100505) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900505       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900505         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900505 7.958e-07
$
$$ --- SUS316_annealed (mu_iso, MID 110505) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910505       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910505         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910505 7.958e-07
$
$$ --- SUS316_annealed (kin_pure, MID 130505) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930505       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930505         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930505 7.958e-07
$
$$ --- SUS316_annealed (kin_mix, MID 140505) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940505       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940505         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940505 7.958e-07
$
$$ --- SUS316L_annealed (bi_iso, MID 100506) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316L_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900506       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900506         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900506 7.958e-07
$
$$ --- SUS316L_annealed (mu_iso, MID 110506) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316L_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910506       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910506         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910506 7.958e-07
$
$$ --- SUS316L_annealed (kin_pure, MID 130506) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316L_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930506       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930506         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930506 7.958e-07
$
$$ --- SUS316L_annealed (kin_mix, MID 140506) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
SUS316L_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940506       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940506         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940506 7.958e-07
$
$$ --- SUS410_annealed (bi_iso, MID 100507) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS410_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900507       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900507         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900507 4.775e-07
$
$$ --- SUS410_annealed (mu_iso, MID 110507) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS410_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910507       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910507         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910507 4.775e-07
$
$$ --- SUS410_annealed (kin_pure, MID 130507) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS410_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930507       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930507         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930507 4.775e-07
$
$$ --- SUS410_annealed (kin_mix, MID 140507) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS410_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940507       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940507         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940507 4.775e-07
$
$$ --- SUS420_annealed (bi_iso, MID 100508) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS420_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900508       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900508         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900508 4.775e-07
$
$$ --- SUS420_annealed (mu_iso, MID 110508) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS420_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910508       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910508         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910508 4.775e-07
$
$$ --- SUS420_annealed (kin_pure, MID 130508) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS420_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930508       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930508         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930508 4.775e-07
$
$$ --- SUS420_annealed (kin_mix, MID 140508) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS420_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940508       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940508         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940508 4.775e-07
$
$$ --- SUS430_annealed (bi_iso, MID 100509) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
SUS430_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900509       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900509         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900509 6.366e-07
$
$$ --- SUS430_annealed (mu_iso, MID 110509) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
SUS430_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910509       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910509         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910509 6.366e-07
$
$$ --- SUS430_annealed (kin_pure, MID 130509) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
SUS430_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930509       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930509         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930509 6.366e-07
$
$$ --- SUS430_annealed (kin_mix, MID 140509) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
SUS430_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940509       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940509         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940509 6.366e-07
$
$$ --- SUS_17-4PH_H900 (bi_iso, MID 100510) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS_17-4PH_H900_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900510       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900510         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900510 4.775e-07
$
$$ --- SUS_17-4PH_H900 (mu_iso, MID 110510) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS_17-4PH_H900_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910510       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910510         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910510 4.775e-07
$
$$ --- SUS_17-4PH_H900 (kin_pure, MID 130510) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS_17-4PH_H900_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930510       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930510         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930510 4.775e-07
$
$$ --- SUS_17-4PH_H900 (kin_mix, MID 140510) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SUS_17-4PH_H900_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940510       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940510         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940510 4.775e-07
$
$ ========================================================================
$ Al DAMPING
$ ========================================================================
$
$$ --- Al1050-O (bi_iso, MID 100521) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1050-O_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900521       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900521         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900521 1.273e-06
$
$$ --- Al1050-O (mu_iso, MID 110521) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1050-O_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910521       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910521         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910521 1.273e-06
$
$$ --- Al1050-O (kin_pure, MID 130521) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1050-O_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930521       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930521         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930521 1.273e-06
$
$$ --- Al1050-O (kin_mix, MID 140521) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1050-O_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940521       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940521         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940521 1.273e-06
$
$$ --- Al1100-O (bi_iso, MID 100522) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1100-O_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900522       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900522         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900522 1.273e-06
$
$$ --- Al1100-O (mu_iso, MID 110522) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1100-O_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910522       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910522         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910522 1.273e-06
$
$$ --- Al1100-O (kin_pure, MID 130522) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1100-O_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930522       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930522         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930522 1.273e-06
$
$$ --- Al1100-O (kin_mix, MID 140522) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al1100-O_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940522       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940522         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940522 1.273e-06
$
$$ --- Al2024-T3 (bi_iso, MID 100523) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2024-T3_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900523       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900523         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900523 4.775e-07
$
$$ --- Al2024-T3 (mu_iso, MID 110523) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2024-T3_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910523       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910523         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910523 4.775e-07
$
$$ --- Al2024-T3 (kin_pure, MID 130523) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2024-T3_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930523       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930523         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930523 4.775e-07
$
$$ --- Al2024-T3 (kin_mix, MID 140523) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al2024-T3_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940523       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940523         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940523 4.775e-07
$
$$ --- Al3003-H14 (bi_iso, MID 100524) ---
$$ zeta=0.0060 (0.60%) @ f_ref=1000 Hz
$$ alpha=3.770e+01 /s, beta=9.549e-07 s
*SET_PART_LIST_TITLE
Al3003-H14_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900524       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900524         0 3.770e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900524 9.549e-07
$
$$ --- Al3003-H14 (mu_iso, MID 110524) ---
$$ zeta=0.0060 (0.60%) @ f_ref=1000 Hz
$$ alpha=3.770e+01 /s, beta=9.549e-07 s
*SET_PART_LIST_TITLE
Al3003-H14_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910524       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910524         0 3.770e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910524 9.549e-07
$
$$ --- Al3003-H14 (kin_pure, MID 130524) ---
$$ zeta=0.0060 (0.60%) @ f_ref=1000 Hz
$$ alpha=3.770e+01 /s, beta=9.549e-07 s
*SET_PART_LIST_TITLE
Al3003-H14_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930524       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930524         0 3.770e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930524 9.549e-07
$
$$ --- Al3003-H14 (kin_mix, MID 140524) ---
$$ zeta=0.0060 (0.60%) @ f_ref=1000 Hz
$$ alpha=3.770e+01 /s, beta=9.549e-07 s
*SET_PART_LIST_TITLE
Al3003-H14_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940524       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940524         0 3.770e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940524 9.549e-07
$
$$ --- Al5052-H32 (bi_iso, MID 100525) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5052-H32_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900525       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900525         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900525 1.273e-06
$
$$ --- Al5052-H32 (mu_iso, MID 110525) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5052-H32_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910525       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910525         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910525 1.273e-06
$
$$ --- Al5052-H32 (kin_pure, MID 130525) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5052-H32_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930525       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930525         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930525 1.273e-06
$
$$ --- Al5052-H32 (kin_mix, MID 140525) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5052-H32_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940525       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940525         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940525 1.273e-06
$
$$ --- Al5083-H116 (bi_iso, MID 100526) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5083-H116_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900526       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900526         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900526 1.273e-06
$
$$ --- Al5083-H116 (mu_iso, MID 110526) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5083-H116_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910526       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910526         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910526 1.273e-06
$
$$ --- Al5083-H116 (kin_pure, MID 130526) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5083-H116_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930526       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930526         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930526 1.273e-06
$
$$ --- Al5083-H116 (kin_mix, MID 140526) ---
$$ zeta=0.0080 (0.80%) @ f_ref=1000 Hz
$$ alpha=5.027e+01 /s, beta=1.273e-06 s
*SET_PART_LIST_TITLE
Al5083-H116_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940526       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940526         0 5.027e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940526 1.273e-06
$
$$ --- Al6061-T6 (bi_iso, MID 100535) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6061-T6_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900535       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900535         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900535 4.775e-07
$
$$ --- Al6061-T6 (mu_iso, MID 110535) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6061-T6_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910535       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910535         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910535 4.775e-07
$
$$ --- Al6061-T6 (kin_pure, MID 130535) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6061-T6_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930535       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930535         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930535 4.775e-07
$
$$ --- Al6061-T6 (kin_mix, MID 140535) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6061-T6_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940535       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940535         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940535 4.775e-07
$
$$ --- Al6063-T5 (bi_iso, MID 100536) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T5_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900536       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900536         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900536 4.775e-07
$
$$ --- Al6063-T5 (mu_iso, MID 110536) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T5_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910536       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910536         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910536 4.775e-07
$
$$ --- Al6063-T5 (kin_pure, MID 130536) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T5_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930536       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930536         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930536 4.775e-07
$
$$ --- Al6063-T5 (kin_mix, MID 140536) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T5_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940536       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940536         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940536 4.775e-07
$
$$ --- Al6063-T6 (bi_iso, MID 100537) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T6_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900537       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900537         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900537 4.775e-07
$
$$ --- Al6063-T6 (mu_iso, MID 110537) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T6_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910537       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910537         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910537 4.775e-07
$
$$ --- Al6063-T6 (kin_pure, MID 130537) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T6_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930537       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930537         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930537 4.775e-07
$
$$ --- Al6063-T6 (kin_mix, MID 140537) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al6063-T6_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940537       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940537         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940537 4.775e-07
$
$$ --- Al7050-T7451 (bi_iso, MID 100538) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7050-T7451_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900538       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900538         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900538 4.775e-07
$
$$ --- Al7050-T7451 (mu_iso, MID 110538) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7050-T7451_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910538       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910538         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910538 4.775e-07
$
$$ --- Al7050-T7451 (kin_pure, MID 130538) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7050-T7451_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930538       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930538         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930538 4.775e-07
$
$$ --- Al7050-T7451 (kin_mix, MID 140538) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7050-T7451_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940538       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940538         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940538 4.775e-07
$
$$ --- Al7075-T6 (bi_iso, MID 100539) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7075-T6_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900539       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900539         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900539 4.775e-07
$
$$ --- Al7075-T6 (mu_iso, MID 110539) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7075-T6_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910539       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910539         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910539 4.775e-07
$
$$ --- Al7075-T6 (kin_pure, MID 130539) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7075-T6_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930539       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930539         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930539 4.775e-07
$
$$ --- Al7075-T6 (kin_mix, MID 140539) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Al7075-T6_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940539       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940539         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940539 4.775e-07
$
$$ --- ADC12_diecast (bi_iso, MID 100540) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
ADC12_diecast_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900540       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900540         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900540 2.387e-06
$
$$ --- ADC12_diecast (mu_iso, MID 110540) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
ADC12_diecast_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910540       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910540         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910540 2.387e-06
$
$$ --- ADC12_diecast (kin_pure, MID 130540) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
ADC12_diecast_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930540       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930540         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930540 2.387e-06
$
$$ --- ADC12_diecast (kin_mix, MID 140540) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
ADC12_diecast_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940540       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940540         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940540 2.387e-06
$
$ ========================================================================
$ Ti DAMPING
$ ========================================================================
$
$$ --- Ti_Grade1 (bi_iso, MID 100561) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade1_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900561       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900561         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900561 7.958e-07
$
$$ --- Ti_Grade1 (mu_iso, MID 110561) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade1_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910561       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910561         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910561 7.958e-07
$
$$ --- Ti_Grade1 (kin_pure, MID 130561) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade1_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930561       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930561         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930561 7.958e-07
$
$$ --- Ti_Grade1 (kin_mix, MID 140561) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade1_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940561       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940561         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940561 7.958e-07
$
$$ --- Ti_Grade2 (bi_iso, MID 100562) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade2_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900562       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900562         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900562 7.958e-07
$
$$ --- Ti_Grade2 (mu_iso, MID 110562) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade2_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910562       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910562         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910562 7.958e-07
$
$$ --- Ti_Grade2 (kin_pure, MID 130562) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade2_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930562       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930562         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930562 7.958e-07
$
$$ --- Ti_Grade2 (kin_mix, MID 140562) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade2_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940562       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940562         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940562 7.958e-07
$
$$ --- Ti_Grade4 (bi_iso, MID 100563) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade4_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900563       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900563         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900563 7.958e-07
$
$$ --- Ti_Grade4 (mu_iso, MID 110563) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade4_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910563       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910563         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910563 7.958e-07
$
$$ --- Ti_Grade4 (kin_pure, MID 130563) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade4_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930563       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930563         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930563 7.958e-07
$
$$ --- Ti_Grade4 (kin_mix, MID 140563) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
Ti_Grade4_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940563       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940563         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940563 7.958e-07
$
$$ --- Ti6Al4V_Grade5 (bi_iso, MID 100564) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900564       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900564         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900564 4.775e-07
$
$$ --- Ti6Al4V_Grade5 (mu_iso, MID 110564) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910564       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910564         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910564 4.775e-07
$
$$ --- Ti6Al4V_Grade5 (kin_pure, MID 130564) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930564       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930564         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930564 4.775e-07
$
$$ --- Ti6Al4V_Grade5 (kin_mix, MID 140564) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940564       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940564         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940564 4.775e-07
$
$$ --- Ti6Al4V_Grade5_ELI (bi_iso, MID 100565) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_ELI_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900565       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900565         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900565 4.775e-07
$
$$ --- Ti6Al4V_Grade5_ELI (mu_iso, MID 110565) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_ELI_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910565       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910565         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910565 4.775e-07
$
$$ --- Ti6Al4V_Grade5_ELI (kin_pure, MID 130565) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_ELI_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930565       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930565         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930565 4.775e-07
$
$$ --- Ti6Al4V_Grade5_ELI (kin_mix, MID 140565) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Ti6Al4V_Grade5_ELI_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940565       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940565         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940565 4.775e-07
$
$$ --- Ti3Al2.5V_Grade9 (bi_iso, MID 100566) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
Ti3Al2.5V_Grade9_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900566       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900566         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900566 6.366e-07
$
$$ --- Ti3Al2.5V_Grade9 (mu_iso, MID 110566) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
Ti3Al2.5V_Grade9_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910566       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910566         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910566 6.366e-07
$
$$ --- Ti3Al2.5V_Grade9 (kin_pure, MID 130566) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
Ti3Al2.5V_Grade9_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930566       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930566         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930566 6.366e-07
$
$$ --- Ti3Al2.5V_Grade9 (kin_mix, MID 140566) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
Ti3Al2.5V_Grade9_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940566       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940566         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940566 6.366e-07
$
$ ========================================================================
$ Mg DAMPING
$ ========================================================================
$
$$ --- Mg_AZ31B_H24 (bi_iso, MID 100581) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_AZ31B_H24_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900581       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900581         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900581 1.592e-06
$
$$ --- Mg_AZ31B_H24 (mu_iso, MID 110581) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_AZ31B_H24_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910581       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910581         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910581 1.592e-06
$
$$ --- Mg_AZ31B_H24 (kin_pure, MID 130581) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_AZ31B_H24_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930581       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930581         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930581 1.592e-06
$
$$ --- Mg_AZ31B_H24 (kin_mix, MID 140581) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_AZ31B_H24_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940581       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940581         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940581 1.592e-06
$
$$ --- Mg_AZ91D_diecast (bi_iso, MID 100582) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
Mg_AZ91D_diecast_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900582       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900582         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900582 2.387e-06
$
$$ --- Mg_AZ91D_diecast (mu_iso, MID 110582) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
Mg_AZ91D_diecast_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910582       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910582         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910582 2.387e-06
$
$$ --- Mg_AZ91D_diecast (kin_pure, MID 130582) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
Mg_AZ91D_diecast_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930582       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930582         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930582 2.387e-06
$
$$ --- Mg_AZ91D_diecast (kin_mix, MID 140582) ---
$$ zeta=0.0150 (1.50%) @ f_ref=1000 Hz
$$ alpha=9.425e+01 /s, beta=2.387e-06 s
*SET_PART_LIST_TITLE
Mg_AZ91D_diecast_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940582       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940582         0 9.425e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940582 2.387e-06
$
$$ --- Mg_ZK60A_T5 (bi_iso, MID 100583) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_ZK60A_T5_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900583       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900583         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900583 1.592e-06
$
$$ --- Mg_ZK60A_T5 (mu_iso, MID 110583) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_ZK60A_T5_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910583       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910583         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910583 1.592e-06
$
$$ --- Mg_ZK60A_T5 (kin_pure, MID 130583) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_ZK60A_T5_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930583       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930583         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930583 1.592e-06
$
$$ --- Mg_ZK60A_T5 (kin_mix, MID 140583) ---
$$ zeta=0.0100 (1.00%) @ f_ref=1000 Hz
$$ alpha=6.283e+01 /s, beta=1.592e-06 s
*SET_PART_LIST_TITLE
Mg_ZK60A_T5_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940583       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940583         0 6.283e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940583 1.592e-06
$
$ ========================================================================
$ Steel DAMPING
$ ========================================================================
$
$$ --- SPCC_mild_steel (bi_iso, MID 100591) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SPCC_mild_steel_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900591       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900591         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900591 4.775e-07
$
$$ --- SPCC_mild_steel (mu_iso, MID 110591) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SPCC_mild_steel_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910591       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910591         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910591 4.775e-07
$
$$ --- SPCC_mild_steel (kin_pure, MID 130591) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SPCC_mild_steel_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930591       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930591         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930591 4.775e-07
$
$$ --- SPCC_mild_steel (kin_mix, MID 140591) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SPCC_mild_steel_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940591       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940591         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940591 4.775e-07
$
$$ --- S45C_medium_carbon (bi_iso, MID 100592) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
S45C_medium_carbon_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900592       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900592         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900592 4.775e-07
$
$$ --- S45C_medium_carbon (mu_iso, MID 110592) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
S45C_medium_carbon_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910592       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910592         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910592 4.775e-07
$
$$ --- S45C_medium_carbon (kin_pure, MID 130592) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
S45C_medium_carbon_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930592       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930592         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930592 4.775e-07
$
$$ --- S45C_medium_carbon (kin_mix, MID 140592) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
S45C_medium_carbon_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940592       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940592         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940592 4.775e-07
$
$$ --- SCM440_alloy_steel (bi_iso, MID 100593) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SCM440_alloy_steel_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900593       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900593         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900593 4.775e-07
$
$$ --- SCM440_alloy_steel (mu_iso, MID 110593) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SCM440_alloy_steel_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910593       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910593         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910593 4.775e-07
$
$$ --- SCM440_alloy_steel (kin_pure, MID 130593) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SCM440_alloy_steel_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930593       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930593         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930593 4.775e-07
$
$$ --- SCM440_alloy_steel (kin_mix, MID 140593) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
SCM440_alloy_steel_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940593       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940593         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940593 4.775e-07
$
$ ========================================================================
$ Brass DAMPING
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass (bi_iso, MID 100601) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C26000_Cartridge_Brass_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900601       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900601         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900601 6.366e-07
$
$$ --- C26000_Cartridge_Brass (mu_iso, MID 110601) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C26000_Cartridge_Brass_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910601       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910601         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910601 6.366e-07
$
$$ --- C26000_Cartridge_Brass (kin_pure, MID 130601) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C26000_Cartridge_Brass_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930601       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930601         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930601 6.366e-07
$
$$ --- C26000_Cartridge_Brass (kin_mix, MID 140601) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C26000_Cartridge_Brass_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940601       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940601         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940601 6.366e-07
$
$$ --- C36000_FreeCutting_Brass (bi_iso, MID 100602) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C36000_FreeCutting_Brass_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900602       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900602         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900602 6.366e-07
$
$$ --- C36000_FreeCutting_Brass (mu_iso, MID 110602) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C36000_FreeCutting_Brass_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910602       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910602         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910602 6.366e-07
$
$$ --- C36000_FreeCutting_Brass (kin_pure, MID 130602) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C36000_FreeCutting_Brass_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930602       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930602         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930602 6.366e-07
$
$$ --- C36000_FreeCutting_Brass (kin_mix, MID 140602) ---
$$ zeta=0.0040 (0.40%) @ f_ref=1000 Hz
$$ alpha=2.513e+01 /s, beta=6.366e-07 s
*SET_PART_LIST_TITLE
C36000_FreeCutting_Brass_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940602       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940602         0 2.513e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940602 6.366e-07
$
$$ --- C51000_Phosphor_Bronze (bi_iso, MID 100603) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
C51000_Phosphor_Bronze_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900603       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900603         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900603 7.958e-07
$
$$ --- C51000_Phosphor_Bronze (mu_iso, MID 110603) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
C51000_Phosphor_Bronze_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910603       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910603         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910603 7.958e-07
$
$$ --- C51000_Phosphor_Bronze (kin_pure, MID 130603) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
C51000_Phosphor_Bronze_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930603       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930603         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930603 7.958e-07
$
$$ --- C51000_Phosphor_Bronze (kin_mix, MID 140603) ---
$$ zeta=0.0050 (0.50%) @ f_ref=1000 Hz
$$ alpha=3.142e+01 /s, beta=7.958e-07 s
*SET_PART_LIST_TITLE
C51000_Phosphor_Bronze_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940603       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940603         0 3.142e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940603 7.958e-07
$
$ ========================================================================
$ Inconel DAMPING
$ ========================================================================
$
$$ --- Inconel_625_annealed (bi_iso, MID 100611) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_625_annealed_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900611       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900611         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900611 4.775e-07
$
$$ --- Inconel_625_annealed (mu_iso, MID 110611) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_625_annealed_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910611       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910611         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910611 4.775e-07
$
$$ --- Inconel_625_annealed (kin_pure, MID 130611) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_625_annealed_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930611       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930611         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930611 4.775e-07
$
$$ --- Inconel_625_annealed (kin_mix, MID 140611) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_625_annealed_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940611       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940611         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940611 4.775e-07
$
$$ --- Inconel_718_aged (bi_iso, MID 100612) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_718_aged_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900612       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900612         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900612 4.775e-07
$
$$ --- Inconel_718_aged (mu_iso, MID 110612) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_718_aged_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910612       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910612         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910612 4.775e-07
$
$$ --- Inconel_718_aged (kin_pure, MID 130612) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_718_aged_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930612       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930612         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930612 4.775e-07
$
$$ --- Inconel_718_aged (kin_mix, MID 140612) ---
$$ zeta=0.0030 (0.30%) @ f_ref=1000 Hz
$$ alpha=1.885e+01 /s, beta=4.775e-07 s
*SET_PART_LIST_TITLE
Inconel_718_aged_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940612       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940612         0 1.885e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940612 4.775e-07
$
$ ========================================================================
$ Tungsten DAMPING
$ ========================================================================
$
$$ --- Tungsten_99pct (bi_iso, MID 100621) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Tungsten_99pct_bi_iso_parts
$      SID       DA1       DA2       DA3       DA4
    900621       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    900621         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    900621 3.183e-07
$
$$ --- Tungsten_99pct (mu_iso, MID 110621) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Tungsten_99pct_mu_iso_parts
$      SID       DA1       DA2       DA3       DA4
    910621       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    910621         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    910621 3.183e-07
$
$$ --- Tungsten_99pct (kin_pure, MID 130621) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Tungsten_99pct_kin_pure_parts
$      SID       DA1       DA2       DA3       DA4
    930621       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    930621         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    930621 3.183e-07
$
$$ --- Tungsten_99pct (kin_mix, MID 140621) ---
$$ zeta=0.0020 (0.20%) @ f_ref=1000 Hz
$$ alpha=1.257e+01 /s, beta=3.183e-07 s
*SET_PART_LIST_TITLE
Tungsten_99pct_kin_mix_parts
$      SID       DA1       DA2       DA3       DA4
    940621       0.0       0.0       0.0       0.0
$      PID1      PID2      PID3      PID4      PID5      PID6      PID7      PID8
$ TODO: replace zeros below with actual PART IDs using this material
         0         0         0         0         0         0         0         0
*DAMPING_PART_MASS_SET
$     PSID      LCID    VALDMP      FLAG
    940621         0 1.257e+01         1
$      STX       STY       STZ       SRX       SRY       SRZ
       1.0       1.0       1.0       1.0       1.0       1.0
*DAMPING_PART_STIFFNESS_SET
$     PSID      COEF
    940621 3.183e-07
$
*END
