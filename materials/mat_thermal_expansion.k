$$ ============================================================================
$$  *MAT_ADD_THERMAL_EXPANSION per material (MID)
$$  LCID=0 -> constant CTE (MULT = ALPHA in 1/K)
$$  NOTE: PID field = MID here. Replace with actual PID at use time.
$$  Unit: 1/K
$$ ============================================================================
*KEYWORD
$
$$ --- MID 1: TAPE_1620MPa (PET_HingeTape, ALPHA=5.9E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         1         05.9000E-05
$
$$ --- MID 2: Mobile.STS304 (STS304_Stainless, ALPHA=1.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         2         01.7300E-05
$
$$ --- MID 3: Mobile.Rigid (S45C_CarbonSteel, ALPHA=1.2E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         3         01.1700E-05
$
$$ --- MID 4: AL7003H (AL7003H_Aluminum, ALPHA=2.4E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         4         02.3600E-05
$
$$ --- MID 5: PC_QF1035 (PC_Polycarbonate, ALPHA=6.5E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         5         06.5000E-05
$
$$ --- MID 6: Ground (Steel_Ground_MassScaled, ALPHA=1.2E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         6         01.1700E-05
$
$$ --- MID 7: B_PI (PI_Kapton, ALPHA=2.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         7         02.0000E-05
$
$$ --- MID 8: POL (Polymer_LowE, ALPHA=7.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         8         07.0000E-05
$
$$ --- MID 9: Panel (OLED_Panel, ALPHA=5.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         9         05.0000E-05
$
$$ --- MID 10: TPU (TPU_Elastomer, ALPHA=1.5E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        10         01.5000E-04
$
$$ --- MID 11: CU (Cu_FPCB, ALPHA=1.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        11         01.6500E-05
$
$$ --- MID 12: PSA (PSA_Acrylic_Elastic, ALPHA=2.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        12         02.0000E-04
$
$$ --- MID 13: SUS (SUS_Spring_159GPa, ALPHA=1.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        13         01.7300E-05
$
$$ --- MID 14: DL (DisplayLaminate_OCA, ALPHA=8.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        14         08.0000E-05
$
$$ --- MID 15: Glass (UTG_SodaLime, ALPHA=9.0E-06 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        15         09.0000E-06
$
$$ --- MID 16: PL (Polarizer_PVA, ALPHA=6.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        16         06.0000E-05
$
$$ --- MID 17: P-Film (ProtectiveFilm_PET, ALPHA=5.9E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        17         05.9000E-05
$
$$ --- MID 18: AL (AL_Frame, ALPHA=2.3E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        18         02.3000E-05
$
$$ --- MID 19: Ti (Ti_Lattice, ALPHA=8.6E-06 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        19         08.6000E-06
$
$$ --- MID 20: Tape (PET_AdhesiveTape, ALPHA=5.9E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        20         05.9000E-05
$
$$ --- MID 21: Rigid (Rigid_SUS_FullLock, ALPHA=1.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        21         01.7300E-05
$
$$ --- MID 22: Nail (NailAdhesive, ALPHA=8.0E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        22         08.0000E-05
$
$$ --- MID 38: M-Film (Ti_MetalFilm_EP, ALPHA=8.6E-06 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        38         08.6000E-06
$
$$ --- MID 39: PSA1515 (PSA_1515_LowDensity, ALPHA=2.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        39         02.0000E-04
$
$$ --- MID 40: Rubber (Rubber_Linear, ALPHA=2.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        40         02.0000E-04
$
$$ --- MID 41: Mobile.Epoxy.1 (Epoxy_Structural, ALPHA=5.5E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        41         05.5000E-05
$
$$ --- MID 42: Peek (PEEK_Elastic, ALPHA=4.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        42         04.7000E-05
$
$$ --- MID 43: visco (Viscoelastic_Damper, ALPHA=1.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        43         01.0000E-04
$
$$ --- MID 44: CFRP (CFRP_QuasiIso, ALPHA=2.0E-06 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        44         02.0000E-06
$
$$ --- MID 45: Rubber-Mooney (Rubber_MR_PCAP, ALPHA=2.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        45         02.0000E-04
$
$$ --- MID 46: Peek-RIGID (PEEK_Rigid_Fixture, ALPHA=4.7E-05 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        46         04.7000E-05
$
$$ --- MID 47: PSA-31.7 (PSA_MR_Adhesive, ALPHA=2.0E-04 1/K) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        47         02.0000E-04
$
*END
