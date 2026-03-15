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
         2         2         1         0         0         0         0         0
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
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Mobile.STS304
$      MID       RHO         E        PR      SIGY      ETAN      FAIL      TDEL
         27.9000E-09  190000.0    0.3000     215.0       0.0       0.0       0.0
$        C         P      LCSS      LCSR        VP       LCF
       0.0       0.0         0         0       0.0          
*MAT_THERMAL_ISOTROPIC_TITLE
STS304
$     TMID       TRO     TGRLC    TGMULT
         2       0.0       0.0       0.0
$       HC        TC
 5.000E+08      16.2
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         1         01.7300E-05
*MAT_ELASTIC_TITLE
$HWCOLOR MATERIAL          1     11
TAPE_1620MPa::CAE_Hinge-Edge_JG2_x_t_Fem::[1]
$      MID       RHO         E        PR        DA        DB         K
         11.1000E-09    1620.0    0.3902       0.0       0.0       0.0
*END
