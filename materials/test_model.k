*KEYWORD
*HOURGLASS_TITLE
Steel_HG
$     HGID       IHQ        QH        IBQ        Q1        Q2    QB/VDC        QW
         5         5    0.1000         0       0.0       0.0       0.0       0.0
*MAT_ELASTIC_TITLE
Steel
$      MID       RHO         E        PR        DA        DB  NOT USED
         5  7.8500E-09  210000.0       0.3       0.0       0.0       0.0
*SECTION_SOLID_TITLE
Steel_Section
$    SECID    ELFORM       AET
         5         1         0
$
*PART
Steel_Cube
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         5         5         0         5         0         0         0
$
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
$      EID       PID      N1      N2      N3      N4      N5      N6      N7      N8
         1         1       1       2       3       4       5       6       7       8
*END
