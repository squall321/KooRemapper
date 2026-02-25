*KEYWORD
$ Two HEX8 cubes - Steel (PID=1) and Steel (PID=2)
$ Used for matswap examples
*PART
Cube_1
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         3         1         0         3         0         0         0
*PART
Cube_2
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         4         2         0         4         0         0         0
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
*HOURGLASS_TITLE
Rubber_HG
$     HGID       IHQ        QH        IBQ        Q1        Q2    QB/VDC        QW
         3         5    0.0500         0       0.0       0.0       0.0       0.0
*DEFINE_CURVE_TITLE
Rubber_StressStrain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT
         1         0     1.000     1.000       0.0       0.0         0         0
$                  X                   Y
           -0.900000           -2.045893
           -0.600000           -1.370176
           -0.300000           -0.491087
           -0.100000           -0.007407
            0.000000            0.000000
            0.100000            0.001989
            0.200000            0.003978
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
Rubber_MAT181
$      MID       RHO        KM        MU         G      SIGF       REF     PRTEN
         11.1000E-09   10.0000       0.0       0.0       0.0       0.0       0.0
$      SGL        SW        ST   LC/TBID   TENSION     RTYPE    AVGOPT        PR
    1.0000    1.0000    1.0000         1    1.0000       0.0       0.0       0.0
$   LCUNLD        HU     SHAPE      STOL     VISCO    HISOUT
         0       0.0       0.0       0.0    1.0000         0
$       Gi     BETAi     VFLAG
    0.0500 3000.0000         0
    0.1000  300.0000
*SECTION_SOLID_TITLE
Rubber_Section
$    SECID    ELFORM       AET
         3        13         0
*HOURGLASS_TITLE
Rubber_HG
$     HGID       IHQ        QH        IBQ        Q1        Q2    QB/VDC        QW
         4         5    0.0500         0       0.0       0.0       0.0       0.0
*DEFINE_CURVE_TITLE
Rubber_StressStrain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT
         2         0     1.000     1.000       0.0       0.0         0         0
$                  X                   Y
           -0.900000           -2.045893
           -0.600000           -1.370176
           -0.300000           -0.491087
           -0.100000           -0.007407
            0.000000            0.000000
            0.100000            0.001989
            0.200000            0.003978
*MAT_SIMPLIFIED_RUBBER/FOAM_TITLE
Rubber_MAT181
$      MID       RHO        KM        MU         G      SIGF       REF     PRTEN
         21.1000E-09   10.0000       0.0       0.0       0.0       0.0       0.0
$      SGL        SW        ST   LC/TBID   TENSION     RTYPE    AVGOPT        PR
    1.0000    1.0000    1.0000         2    1.0000       0.0       0.0       0.0
$   LCUNLD        HU     SHAPE      STOL     VISCO    HISOUT
         0       0.0       0.0       0.0    1.0000         0
$       Gi     BETAi     VFLAG
    0.0500 3000.0000         0
    0.1000  300.0000
*SECTION_SOLID_TITLE
Rubber_Section
$    SECID    ELFORM       AET
         4        13         0
*END
