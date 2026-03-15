*KEYWORD
$ Test model for matdb command
*MAT_ELASTIC_TITLE
Mobile.STS304
$      MID       RHO         E        PR        DA        DB  NOT USED
         2  7.9000E-09  190000.0       0.3       0.0       0.0       0.0
*MAT_ELASTIC_TITLE
TAPE_1620MPa
$      MID       RHO         E        PR        DA        DB  NOT USED
         1  1.1000E-09    1620.0    0.3902       0.0       0.0       0.0
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
         1         1         2         0         0         0         0         0
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
*END
