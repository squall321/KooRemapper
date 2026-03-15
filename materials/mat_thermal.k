$$ ============================================================================
$$  *MAT_THERMAL_ISOTROPIC (Type T01) for all materials
$$  Unit: t / mm / s / K
$$  HC [mJ/(t·K)] = Cp [J/(kg·K)] × 1e6
$$  TC [mW/(mm·K)] = k  [W/(m·K)]   (numerically same)
$$ ============================================================================
*KEYWORD
$
$$ ========== METALS ==========
$
$$ --- TMID 1: TAPE_1620MPa (PET film) ---
*MAT_THERMAL_ISOTROPIC_TITLE
TAPE_1620MPa
$     TMID       TRO     TGRLC    TGMULT
         1       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 2: STS304 (Stainless Steel 304) ---
*MAT_THERMAL_ISOTROPIC_TITLE
STS304
$     TMID       TRO     TGRLC    TGMULT
         2       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
$
$$ --- TMID 3: Mobile.Rigid (Carbon steel) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Mobile.Rigid
$     TMID       TRO     TGRLC    TGMULT
         3       0.0       0.0       0.0
$       HC        TC
 4.800E+08      50.0
$
$$ --- TMID 4: AL7003H (Aluminum 7003-H) ---
*MAT_THERMAL_ISOTROPIC_TITLE
AL7003H
$     TMID       TRO     TGRLC    TGMULT
         4       0.0       0.0       0.0
$       HC        TC
 8.900E+08     155.0
$
$$ --- TMID 5: PC_QF1035 (Polycarbonate) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PC_QF1035
$     TMID       TRO     TGRLC    TGMULT
         5       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 6: Ground (Carbon steel, mass-scaled) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Ground
$     TMID       TRO     TGRLC    TGMULT
         6       0.0       0.0       0.0
$       HC        TC
 4.800E+08      50.0
$
$$ --- TMID 7: B_PI (Polyimide / Kapton) ---
*MAT_THERMAL_ISOTROPIC_TITLE
B_PI
$     TMID       TRO     TGRLC    TGMULT
         7       0.0       0.0       0.0
$       HC        TC
 1.090E+09      0.12
$
$$ --- TMID 8: POL (Generic polymer) ---
*MAT_THERMAL_ISOTROPIC_TITLE
POL
$     TMID       TRO     TGRLC    TGMULT
         8       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 9: Panel (Polymer composite) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Panel
$     TMID       TRO     TGRLC    TGMULT
         9       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 10: TPU (Thermoplastic polyurethane) ---
*MAT_THERMAL_ISOTROPIC_TITLE
TPU
$     TMID       TRO     TGRLC    TGMULT
        10       0.0       0.0       0.0
$       HC        TC
 1.500E+09      0.15
$
$$ --- TMID 11: CU (Copper) ---
*MAT_THERMAL_ISOTROPIC_TITLE
CU
$     TMID       TRO     TGRLC    TGMULT
        11       0.0       0.0       0.0
$       HC        TC
 3.850E+08     401.0
$
$$ --- TMID 12: PSA (Pressure-sensitive adhesive) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA
$     TMID       TRO     TGRLC    TGMULT
        12       0.0       0.0       0.0
$       HC        TC
 2.000E+09      0.20
$
$$ --- TMID 13: SUS (Stainless steel) ---
*MAT_THERMAL_ISOTROPIC_TITLE
SUS
$     TMID       TRO     TGRLC    TGMULT
        13       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
$
$$ --- TMID 14: DL (Display laminate) ---
*MAT_THERMAL_ISOTROPIC_TITLE
DL
$     TMID       TRO     TGRLC    TGMULT
        14       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 15: Glass (UTG, soda-lime) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Glass
$     TMID       TRO     TGRLC    TGMULT
        15       0.0       0.0       0.0
$       HC        TC
 8.400E+08       1.0
$
$$ --- TMID 16: PL (Polarizer, PVA) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PL
$     TMID       TRO     TGRLC    TGMULT
        16       0.0       0.0       0.0
$       HC        TC
 1.400E+09      0.20
$
$$ --- TMID 17: P-Film (Protective film) ---
*MAT_THERMAL_ISOTROPIC_TITLE
P-Film
$     TMID       TRO     TGRLC    TGMULT
        17       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.15
$
$$ --- TMID 18: AL (Aluminum alloy) ---
*MAT_THERMAL_ISOTROPIC_TITLE
AL
$     TMID       TRO     TGRLC    TGMULT
        18       0.0       0.0       0.0
$       HC        TC
 9.000E+08     155.0
$
$$ --- TMID 19: Ti (Titanium) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Ti
$     TMID       TRO     TGRLC    TGMULT
        19       0.0       0.0       0.0
$       HC        TC
 5.200E+08      21.9
$
$$ --- TMID 20: Tape (PET tape) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Tape
$     TMID       TRO     TGRLC    TGMULT
        20       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 21: Rigid (SUS-based) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Rigid
$     TMID       TRO     TGRLC    TGMULT
        21       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
$
$$ --- TMID 22: Nail (Adhesive) ---
*MAT_THERMAL_ISOTROPIC_TITLE
Nail
$     TMID       TRO     TGRLC    TGMULT
        22       0.0       0.0       0.0
$       HC        TC
 1.500E+09      0.20
$
$$ --- TMID 38: M-Film (Ti alloy, MAT_024) ---
*MAT_THERMAL_ISOTROPIC_TITLE
M-Film
$     TMID       TRO     TGRLC    TGMULT
        38       0.0       0.0       0.0
$       HC        TC
 5.200E+08      21.9
$
$$ --- TMID 39: PSA1515 ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA1515
$     TMID       TRO     TGRLC    TGMULT
        39       0.0       0.0       0.0
$       HC        TC
 2.000E+09      0.20
$
$$ --- TMID 40: Rubber ---
*MAT_THERMAL_ISOTROPIC_TITLE
Rubber
$     TMID       TRO     TGRLC    TGMULT
        40       0.0       0.0       0.0
$       HC        TC
 2.000E+09      0.16
$
$$ --- TMID 41: Epoxy ---
*MAT_THERMAL_ISOTROPIC_TITLE
Epoxy
$     TMID       TRO     TGRLC    TGMULT
        41       0.0       0.0       0.0
$       HC        TC
 1.100E+09      0.20
$
$$ --- TMID 42: Peek ---
*MAT_THERMAL_ISOTROPIC_TITLE
Peek
$     TMID       TRO     TGRLC    TGMULT
        42       0.0       0.0       0.0
$       HC        TC
 1.340E+09      0.25
$
$$ --- TMID 43: visco (Viscoelastic) ---
*MAT_THERMAL_ISOTROPIC_TITLE
visco
$     TMID       TRO     TGRLC    TGMULT
        43       0.0       0.0       0.0
$       HC        TC
 1.500E+09      0.20
$
$$ --- TMID 44: CFRP (CF/Epoxy, avg direction) ---
*MAT_THERMAL_ISOTROPIC_TITLE
CFRP
$     TMID       TRO     TGRLC    TGMULT
        44       0.0       0.0       0.0
$       HC        TC
 8.000E+08       5.0
$
$$ --- TMID 45: Rubber-Mooney ---
*MAT_THERMAL_ISOTROPIC_TITLE
Rubber-Mooney
$     TMID       TRO     TGRLC    TGMULT
        45       0.0       0.0       0.0
$       HC        TC
 2.000E+09      0.16
$
$$ --- TMID 46: Peek-RIGID ---
*MAT_THERMAL_ISOTROPIC_TITLE
Peek-RIGID
$     TMID       TRO     TGRLC    TGMULT
        46       0.0       0.0       0.0
$       HC        TC
 1.340E+09      0.25
$
$$ --- TMID 47: PSA-31.7 ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA-31.7
$     TMID       TRO     TGRLC    TGMULT
        47       0.0       0.0       0.0
$       HC        TC
 2.000E+09      0.20
$
*END
