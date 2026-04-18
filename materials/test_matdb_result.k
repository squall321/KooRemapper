*KEYWORD
$ Test model for matdb command
*SECTION_SOLID_TITLE
Section_1
$    SECID    ELFORM       AET
         1         1         0
*SECTION_SOLID_TITLE
Section_2
$    SECID    ELFORM       AET
         2         1         0
*PART
Part_STS
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         2         0         0         0         0         2
*PART
Part_Tape
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         2         1         0         0         0         0         1
*NODE
$      NID               X               Y               Z
         1             0.0             0.0             0.0
         2            10.0             0.0             0.0
         3            10.0            10.0             0.0
         4             0.0            10.0             0.0
         5             0.0             0.0            10.0
         6            10.0             0.0            10.0
         7            10.0            10.0            10.0
         8             0.0            10.0            10.0
         9             0.0             0.0            20.0
        10            10.0             0.0            20.0
        11            10.0            10.0            20.0
        12             0.0            10.0            20.0
*ELEMENT_SOLID
$      EID       PID      N1      N2      N3      N4      N5      N6      N7      N8
         1         1       1       2       3       4       5       6       7       8
         2         2       5       6       7       8       9      10      11      12
*MAT_ELASTIC_TITLE
Mobile.STS304
$      MID       RHO         E        PR        DA        DB         K
         27.9000E-09  190000.0       0.3       0.0       0.0       0.0
$
$$ --- MID 3: Mobile.Rigid (Steel-like, unused) ---
*MAT_THERMAL_ISOTROPIC_TITLE
STS304
$     TMID       TRO     TGRLC    TGMULT
         2       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
$
$$ --- TMID 3: Mobile.Rigid (Carbon steel) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         1         01.7300E-05
$
$$ --- MID 3: Mobile.Rigid (S45C_CarbonSteel, ALPHA=1.2E-05 1/K) ---
*MAT_ELASTIC_TITLE
TAPE_1620MPa
$      MID       RHO         E        PR        DA        DB         K
         11.1000E-09    1620.0    0.3902       0.0       0.0       0.0
$
$$ --- MID 2: Mobile.STS304 (STS304 stainless steel) ---
*MAT_THERMAL_ISOTROPIC_TITLE
TAPE_1620MPa
$     TMID       TRO     TGRLC    TGMULT
         1       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
$
$$ --- TMID 2: STS304 (Stainless Steel 304) ---
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         2         05.9000E-05
$
$$ --- MID 2: Mobile.STS304 (STS304_Stainless, ALPHA=1.7E-05 1/K) ---
*END
