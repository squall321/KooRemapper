$ ========================================================================
$ SMARTPHONE TAPE THERMAL PROPERTIES
$ ========================================================================
$ Unit: mm, s, ton -> temperature K
$   TC (thermal conductivity) : mW/mm/K  (= W/m/K)
$   Cp (specific heat)        : mm^2/s^2/K  (= J/kg/K * 1e6)
$   CTE (thermal expansion)   : 1/K  (= ppm/K * 1e-6)
$
$ TMID convention: structural MID + 20000
$   100001 (OCA Rigid Std)       -> TMID 120001
$   100010 (VHB Clear Thin)      -> TMID 120010
$   100016 (Thermal Interface)   -> TMID 120016
$   ...
$
$ Data sources:
$   - Acrylic PSA/OCA: k=0.18~0.22 W/m/K, Cp=1500 J/kg/K (Alfa Chemistry)
$   - VHB foam: k=0.17 W/m/K, Cp=1450 J/kg/K (3M VHB TDS)
$   - PE foam: k=0.04~0.05 W/m/K, Cp=2300 J/kg/K (foam, very insulating)
$   - PU foam: k=0.025~0.03 W/m/K, Cp=1700 J/kg/K
$   - Butyl rubber: k=0.13 W/m/K, Cp=1960 J/kg/K
$   - Silicone PSA: k=0.20 W/m/K, Cp=1300 J/kg/K
$   - SIS block copolymer: k=0.15 W/m/K, Cp=1900 J/kg/K
$   - Thermal interface filled: k=0.8~3.0 W/m/K (filled with ceramic/metal)
$
$ Specific heat values (polymer reference):
$   Acrylic:             1500 J/kg/K
$   Polyethylene (PE):   2300 J/kg/K (high Cp, low density)
$   Polyurethane (PU):   1700 J/kg/K
$   Butyl rubber:        1960 J/kg/K
$   Silicone:            1300 J/kg/K
$   SIS/SBS:             1900 J/kg/K
$
$ Thermal conductivity notes:
$   Unfilled acrylic tape: ~0.2 W/m/K
$   Foam tape:             0.03~0.05 W/m/K (air + polymer)
$   Filled thermal tape:   0.5~3.0 W/m/K (ceramic/graphite fillers)
$   Damping tape:          similar to base polymer
$
$ Reference: [Alfa Chemistry Plastic Thermal Conductivity Table],
$            [3M VHB Technical Data], [Engineered Materials Inc PSA tapes]
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. OCA (Optically Clear Adhesive) — Display
$ ========================================================================
$
$$ --- OCA_RIGID_STANDARD (MID 100001) ---
$$ Acrylic OCA: k=0.20 W/m/K, Cp=1500 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
OCA Rigid Standard Thermal
$     TMID        TRO      TGRLC    TGMULT     TLAT       HLAT
    120001 1.050e-09         0    1.0000       0.0       0.0
$       HC         TC
 1.500e+09 2.000e-01
$
$$ --- OCA_RIGID_HIGH_BOND (MID 100002) ---
*MAT_THERMAL_ISOTROPIC_TITLE
OCA Rigid High Bond Thermal
    120002 1.080e-09         0    1.0000       0.0       0.0
 1.500e+09 2.000e-01
$
$$ --- OCA_FOLDABLE (MID 100003) ---
*MAT_THERMAL_ISOTROPIC_TITLE
OCA Foldable Thermal
    120003 1.050e-09         0    1.0000       0.0       0.0
 1.500e+09 1.900e-01
$
$$ --- OCA_ROLLABLE (MID 100004) ---
*MAT_THERMAL_ISOTROPIC_TITLE
OCA Rollable Thermal
    120004 1.030e-09         0    1.0000       0.0       0.0
 1.500e+09 1.800e-01
$
$$ --- OCA_UV_CURED (MID 100005) ---
$$ UV-cured slightly higher crosslink density -> slightly higher k
*MAT_THERMAL_ISOTROPIC_TITLE
OCA UV Cured Thermal
    120005 1.100e-09         0    1.0000       0.0       0.0
 1.500e+09 2.100e-01
$
$ ========================================================================
$ 2. PSA Thin Film — FPC/Components
$ ========================================================================
$
$$ --- PSA_ACRYLIC_GENERAL (MID 100006) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA Acrylic General Thermal
    120006 1.100e-09         0    1.0000       0.0       0.0
 1.500e+09 2.000e-01
$
$$ --- PSA_SILICONE_HIGHTEMP (MID 100007) ---
$$ Silicone PSA: k=0.20, Cp=1300 J/kg/K
*MAT_THERMAL_ISOTROPIC_TITLE
PSA Silicone High-Temp Thermal
    120007 1.150e-09         0    1.0000       0.0       0.0
 1.300e+09 2.000e-01
$
$$ --- PSA_HIGH_SHEAR (MID 100008) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA High Shear Thermal
    120008 1.120e-09         0    1.0000       0.0       0.0
 1.500e+09 2.000e-01
$
$$ --- PSA_REMOVABLE (MID 100009) ---
*MAT_THERMAL_ISOTROPIC_TITLE
PSA Removable Thermal
    120009 1.050e-09         0    1.0000       0.0       0.0
 1.500e+09 2.000e-01
$
$ ========================================================================
$ 3. VHB/Foam Tape — Structural bonding
$ ========================================================================
$
$$ --- VHB_CLEAR_THIN (MID 100010) ---
$$ 3M VHB 4905: k=0.17 W/m/K, Cp=1450 J/kg/K (3M TDS)
*MAT_THERMAL_ISOTROPIC_TITLE
VHB Clear Thin Thermal
    120010 9.600e-10         0    1.0000       0.0       0.0
 1.450e+09 1.700e-01
$
$$ --- VHB_BLACK_THICK (MID 100011) ---
$$ 3M VHB 5952: k=0.17, Cp=1450
*MAT_THERMAL_ISOTROPIC_TITLE
VHB Black Thick Thermal
    120011 7.200e-10         0    1.0000       0.0       0.0
 1.450e+09 1.700e-01
$
$$ --- FOAM_PE_GENERAL (MID 100012) ---
$$ PE foam: k=0.05 (very insulating), Cp=2300
*MAT_THERMAL_ISOTROPIC_TITLE
Foam PE General Thermal
    120012 5.000e-10         0    1.0000       0.0       0.0
 2.300e+09 5.000e-02
$
$$ --- FOAM_PU_IMPACT (MID 100013) ---
$$ PU foam: k=0.03, Cp=1700
*MAT_THERMAL_ISOTROPIC_TITLE
Foam PU Impact Thermal
    120013 6.000e-10         0    1.0000       0.0       0.0
 1.700e+09 3.000e-02
$
$ ========================================================================
$ 4. Battery / Special
$ ========================================================================
$
$$ --- BATTERY_STRETCH_RELEASE (MID 100014) ---
$$ SIS block copolymer: k=0.15, Cp=1900
*MAT_THERMAL_ISOTROPIC_TITLE
Battery Stretch-Release Thermal
    120014 1.000e-09         0    1.0000       0.0       0.0
 1.900e+09 1.500e-01
$
$$ --- BATTERY_PERMANENT (MID 100015) ---
$$ High-tack acrylic: k=0.20
*MAT_THERMAL_ISOTROPIC_TITLE
Battery Permanent Thermal
    120015 1.050e-09         0    1.0000       0.0       0.0
 1.500e+09 2.000e-01
$
$$ --- THERMAL_INTERFACE_TAPE (MID 100016) ---
$$ Filled thermal tape: k=1.5 W/m/K (high k, ceramic filler)
*MAT_THERMAL_ISOTROPIC_TITLE
Thermal Interface Tape Thermal
    120016 2.000e-09         0    1.0000       0.0       0.0
 1.200e+09 1.500e+00
$
$ ========================================================================
$ 5. Waterproof / Gasket
$ ========================================================================
$
$$ --- WATERPROOF_GASKET (MID 100017) ---
$$ Modified acrylic: k=0.22
*MAT_THERMAL_ISOTROPIC_TITLE
Waterproof Gasket Thermal
    120017 1.150e-09         0    1.0000       0.0       0.0
 1.500e+09 2.200e-01
$
$$ --- WATERPROOF_BUTYL (MID 100018) ---
$$ Butyl rubber: k=0.13, Cp=1960
*MAT_THERMAL_ISOTROPIC_TITLE
Waterproof Butyl Thermal
    120018 1.300e-09         0    1.0000       0.0       0.0
 1.960e+09 1.300e-01
$
$ ========================================================================
$ 6. Damping Tape
$ ========================================================================
$
$$ --- DAMPING_SPEAKER (MID 100019) ---
$$ Damping acrylic blend: k=0.20
*MAT_THERMAL_ISOTROPIC_TITLE
Damping Speaker Thermal
    120019 1.200e-09         0    1.0000       0.0       0.0
 1.700e+09 2.000e-01
$
$$ --- DAMPING_HAPTIC (MID 100020) ---
$$ High damping butyl blend: k=0.15
*MAT_THERMAL_ISOTROPIC_TITLE
Damping Haptic Thermal
    120020 1.250e-09         0    1.0000       0.0       0.0
 1.850e+09 1.500e-01
$
$ ========================================================================
$ END OF TAPE THERMAL LIBRARY
$ ========================================================================
*END
