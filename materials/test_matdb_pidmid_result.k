*KEYWORD
$ Test: PID=10 uses MID=2, PID=20 uses MID=1
$ Existing thermal+expansion cards should be removed on matdb replace
*SECTION_SOLID_TITLE
Section_1
$    SECID    ELFORM       AET
         1         1         0
*PART
Part_STS
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
        10         1         2         0         0         0         0         2
*PART
Part_Tape
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
        20         1         1         0         0         0         0         1
*NODE
         1             0.0             0.0             0.0
         2            10.0             0.0             0.0
         3            10.0            10.0             0.0
         4             0.0            10.0             0.0
         5             0.0             0.0            10.0
         6            10.0             0.0            10.0
         7            10.0            10.0            10.0
         8             0.0            10.0            10.0
*ELEMENT_SOLID
         1        10       1       2       3       4       5       6       7       8
*MAT_ELASTIC_TITLE
$HWCOLOR MATERIAL          2     43
Mobile.STS304::CAE_Hinge-Edge_JG2_x_t_Fem::[2]
$      MID       RHO         E        PR        DA        DB         K
         27.9000E-09  190000.0       0.3       0.0       0.0       0.0
*MAT_THERMAL_ISOTROPIC_TITLE
STS304
$     TMID       TRO     TGRLC    TGMULT
         2       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        10         01.7300E-05
*MAT_ELASTIC_TITLE
$HWCOLOR MATERIAL          1     11
TAPE_1620MPa::CAE_Hinge-Edge_JG2_x_t_Fem::[1]
$      MID       RHO         E        PR        DA        DB         K
         11.1000E-09    1620.0    0.3902       0.0       0.0       0.0
*MAT_THERMAL_ISOTROPIC_TITLE
TAPE_1620MPa
$     TMID       TRO     TGRLC    TGMULT
         1       0.0       0.0       0.0
$       HC        TC
 1.200E+09      0.20
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
        20         05.9000E-05
*END
