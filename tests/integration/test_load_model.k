*KEYWORD
$ Test model for load command: single hex block, PID=1
*SECTION_SOLID_TITLE
Section_1
$    SECID    ELFORM       AET
         1         1         0
*PART
Block_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         0         0         0         0
*MAT_ELASTIC_TITLE
Steel
$      MID       RHO         E        PR        DA        DB         K
         17.8500E-09  210000.0       0.3       0.0       0.0       0.0
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
*ELEMENT_SOLID
$    EID     PID      N1      N2      N3      N4      N5      N6      N7      N8
       1       1       1       2       3       4       5       6       7       8
*END
