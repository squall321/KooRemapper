$ ========================================================================
$ PCB MISCELLANEOUS MATERIALS
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ MID: 100801~100810
$
$ Contents:
$   100801  Solder Mask LPI (liquid photoimageable epoxy)
$   100802  Solder Mask dry-film
$   100803  Conformal Coating Acrylic
$   100804  Conformal Coating Silicone
$   100805  Conformal Coating Polyurethane
$   100806  TIM Silicone (gap filler, non-cured)
$   100807  TIM Acrylic (pre-cured film)
$   100808  Underfill Epoxy (capillary, for BGA)
$   100809  Underfill Epoxy (CUF, capillary underfill high Tg)
$   100810  Conductive Adhesive (Ag filled epoxy)
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION holds the MATERIAL ID,
$ !!  NOT an actual Part ID. External tool must replace with real PIDs.
$ !! ========================================================================
$
$ Data sources:
$   - Solder mask: Taiyo Ink PSR-4000 TDS, DuPont ImageMaster
$   - Conformal coatings: Humiseal, MG Chemicals, Dow Corning TDS
$   - TIM: Shin-Etsu TC-10, Dow TC-5022, Henkel Bergquist
$   - Underfill: Namics U8443, Loctite 3568, Hitachi CEL400
$
$ ========================================================================
$ SUMMARY TABLE
$
$  MID     Name                       rho    E(MPa)  Tg    CTE   TC   Cp
$  ---------------------------------------------------------------------------
$  100801  Solder Mask LPI            1.30   4000    150   60    0.25 900
$  100802  Solder Mask Dry Film       1.25   3500    140   70    0.20 950
$  100803  Conformal Coating Acrylic  1.10   1500    60    80    0.15 1500
$  100804  Conformal Coating Silicone 1.05   5       -120  250   0.20 1400
$  100805  Conformal Coating PU       1.15   500     80    120   0.18 1600
$  100806  TIM Silicone gap filler    2.50   10      -100  300   2.00 900
$  100807  TIM Acrylic pre-cured      1.80   200     50    150   1.00 1200
$  100808  Underfill Capillary        1.65   5000    110   35    0.50 900
$  100809  Underfill CUF High-Tg      1.75   6500    140   28    0.60 900
$  100810  Conductive Adhesive Ag     3.00   4500    100   55    8.00 700
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. Solder Mask LPI (Liquid Photoimageable) — most common
$ ========================================================================
$
$$ --- Solder Mask LPI (MID 100801) ---
$$ Taiyo Ink PSR-4000 family, DuPont ImageMaster
$$ Epoxy-based photoimageable resist, green/red/black
$$ E = 4 GPa (glassy state), nu=0.35, Tg=150°C
$$ Used for: Trace protection, component marking
*MAT_ELASTIC_TITLE
Solder Mask LPI Epoxy
$      MID        RO         E        PR        DA        DB  NOT_USED
    100801 1.300e-09    4000.0    0.3500       0.0       0.0       0.0
$
$$ --- Solder Mask LPI Thermal (TMID 120801) ---
$$ k=0.25 W/m/K, Cp=900 J/kg/K, CTE=60 ppm/K
*MAT_THERMAL_ISOTROPIC_TITLE
Solder Mask LPI Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120801 1.300e-09         0    1.0000       0.0       0.0
$       HC         TC
 9.000e+08 2.500e-01
$
$$ [DB] PID slot holds MID=100801 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100801         0 6.000e-05
$
$ ========================================================================
$ 2. Solder Mask Dry Film
$ ========================================================================
$
$$ --- Solder Mask Dry Film (MID 100802) ---
*MAT_ELASTIC_TITLE
Solder Mask Dry Film
    100802 1.250e-09    3500.0    0.3500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Solder Mask Dry Film Thermal
    120802 1.250e-09         0    1.0000       0.0       0.0
 9.500e+08 2.000e-01
$
$$ [DB] PID slot holds MID=100802
*MAT_ADD_THERMAL_EXPANSION
    100802         0 7.000e-05
$
$ ========================================================================
$ 3. Conformal Coating Acrylic — cheap, re-workable
$ ========================================================================
$
$$ --- Conformal Coating Acrylic (MID 100803) ---
$$ MG Chemicals 419 series, HumiSeal 1B73
$$ E ≈ 1.5 GPa (hard acrylic), Tg=60°C, rework-friendly
*MAT_ELASTIC_TITLE
Conformal Coating Acrylic
    100803 1.100e-09    1500.0    0.3800       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Conformal Coating Acrylic Thermal
    120803 1.100e-09         0    1.0000       0.0       0.0
 1.500e+09 1.500e-01
$
$$ [DB] PID slot holds MID=100803
*MAT_ADD_THERMAL_EXPANSION
    100803         0 8.000e-05
$
$ ========================================================================
$ 4. Conformal Coating Silicone — wide temp range, flexible
$ ========================================================================
$
$$ --- Conformal Coating Silicone (MID 100804) ---
$$ Dow 1-2577, HumiSeal 1C51
$$ Very soft (E≈5 MPa), high CTE=250 ppm/K, -55 to +200°C
*MAT_ELASTIC_TITLE
Conformal Coating Silicone
    100804 1.050e-09       5.0    0.4900       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Conformal Coating Silicone Thermal
    120804 1.050e-09         0    1.0000       0.0       0.0
 1.400e+09 2.000e-01
$
$$ [DB] PID slot holds MID=100804
*MAT_ADD_THERMAL_EXPANSION
    100804         0 2.500e-04
$
$ ========================================================================
$ 5. Conformal Coating Polyurethane — abrasion resistant
$ ========================================================================
$
$$ --- Conformal Coating PU (MID 100805) ---
$$ HumiSeal 1A33, MG Chemicals 4223
$$ E ≈ 500 MPa (flexible), Tg=80°C, abrasion resistant
*MAT_ELASTIC_TITLE
Conformal Coating Polyurethane
    100805 1.150e-09     500.0    0.4000       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Conformal Coating PU Thermal
    120805 1.150e-09         0    1.0000       0.0       0.0
 1.600e+09 1.800e-01
$
$$ [DB] PID slot holds MID=100805
*MAT_ADD_THERMAL_EXPANSION
    100805         0 1.200e-04
$
$ ========================================================================
$ 6. TIM Silicone Gap Filler (SoC thermal path)
$ ========================================================================
$
$$ --- TIM Silicone Gap Filler (MID 100806) ---
$$ Shin-Etsu TC-10, Dow TC-5022, BerquuistGapPad
$$ Very soft (E≈10 MPa), high k=2.0 W/m/K, conforms to surface
$$ Critical: for SoC heat dissipation to midframe
*MAT_ELASTIC_TITLE
TIM Silicone Gap Filler
    100806 2.500e-09      10.0    0.4900       0.0       0.0       0.0
$
$$ --- TIM Silicone Thermal (TMID 120806) ---
$$ High thermal conductivity k=2.0 W/m/K (ceramic filled)
$$ Cp=900, rho=2.5 g/cc (high loading)
*MAT_THERMAL_ISOTROPIC_TITLE
TIM Silicone Gap Filler Thermal
    120806 2.500e-09         0    1.0000       0.0       0.0
 9.000e+08 2.000e+00
$
$$ [DB] PID slot holds MID=100806
*MAT_ADD_THERMAL_EXPANSION
    100806         0 3.000e-04
$
$ ========================================================================
$ 7. TIM Acrylic Pre-cured Film
$ ========================================================================
$
$$ --- TIM Acrylic Pre-cured (MID 100807) ---
$$ 3M TCM-1620, Laird Tflex series
$$ Firmer than silicone, E≈200 MPa, k=1.0 W/m/K
*MAT_ELASTIC_TITLE
TIM Acrylic Pre-cured
    100807 1.800e-09     200.0    0.4500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
TIM Acrylic Pre-cured Thermal
    120807 1.800e-09         0    1.0000       0.0       0.0
 1.200e+09 1.000e+00
$
$$ [DB] PID slot holds MID=100807
*MAT_ADD_THERMAL_EXPANSION
    100807         0 1.500e-04
$
$ ========================================================================
$ 8. Underfill Epoxy (BGA capillary flow)
$ ========================================================================
$
$$ --- Underfill Epoxy Capillary (MID 100808) ---
$$ Namics U8443, Loctite 3568
$$ Critical for BGA drop reliability — fills gap under BGA
$$ E=5 GPa, Tg=110°C, CTE=35 ppm/K (low for stress control)
*MAT_ELASTIC_TITLE
Underfill Epoxy Capillary
    100808 1.650e-09    5000.0    0.3500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Underfill Epoxy Capillary Thermal
    120808 1.650e-09         0    1.0000       0.0       0.0
 9.000e+08 5.000e-01
$
$$ [DB] PID slot holds MID=100808
*MAT_ADD_THERMAL_EXPANSION
    100808         0 3.500e-05
$
$ ========================================================================
$ 9. Underfill High-Tg (CUF, for high reliability)
$ ========================================================================
$
$$ --- Underfill High-Tg (MID 100809) ---
$$ Hitachi CEL400 series, higher Tg for PbF assembly
$$ E=6.5 GPa, Tg=140°C, CTE=28 ppm/K
*MAT_ELASTIC_TITLE
Underfill Epoxy High-Tg
    100809 1.750e-09    6500.0    0.3500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Underfill High-Tg Thermal
    120809 1.750e-09         0    1.0000       0.0       0.0
 9.000e+08 6.000e-01
$
$$ [DB] PID slot holds MID=100809
*MAT_ADD_THERMAL_EXPANSION
    100809         0 2.800e-05
$
$ ========================================================================
$ 10. Conductive Adhesive (Ag filled epoxy)
$ ========================================================================
$
$$ --- Conductive Adhesive Ag Epoxy (MID 100810) ---
$$ Henkel Ablestik, Epotek H20E
$$ Silver-filled epoxy for chip attach, EMI bonding
$$ E=4.5 GPa, k=8 W/m/K (moderate thermal, high electrical)
*MAT_ELASTIC_TITLE
Conductive Adhesive Ag Epoxy
    100810 3.000e-09    4500.0    0.3500       0.0       0.0       0.0
$
*MAT_THERMAL_ISOTROPIC_TITLE
Conductive Adhesive Thermal
    120810 3.000e-09         0    1.0000       0.0       0.0
 7.000e+08 8.000e+00
$
$$ [DB] PID slot holds MID=100810
*MAT_ADD_THERMAL_EXPANSION
    100810         0 5.500e-05
$
$ ========================================================================
$ END OF PCB MISCELLANEOUS LIBRARY
$ ========================================================================
*END
