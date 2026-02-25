*PARAMETER
$# prmname   value
I HGID1            1I LCID1            1
I MID1             1I SECID1           1
I PID1             1
*HOURGLASS_TITLE
Rubber_HG
$     HGID       IHQ        QH        IBQ        Q1        Q2    QB/VDC        QW
    &HGID1         5    0.0500         0       0.0       0.0       0.0       0.0
*DEFINE_CURVE_TITLE
Rubber_StressStrain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT
    &LCID1         0     1.000     1.000       0.0       0.0         0         0
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
     &MID11.1000E-09   10.0000       0.0       0.0       0.0       0.0       0.0
$      SGL        SW        ST   LC/TBID   TENSION     RTYPE    AVGOPT        PR
    1.0000    1.0000    1.0000    &LCID1    1.0000       0.0       0.0       0.0
$   LCUNLD        HU     SHAPE      STOL     VISCO    HISOUT
         0       0.0       0.0       0.0    1.0000         0
$       Gi     BETAi     VFLAG
    0.0500 3000.0000         0
    0.1000  300.0000
*SECTION_SOLID_TITLE
Rubber_Section
$    SECID    ELFORM       AET
   &SECID1        13         0
*PART
Rubber_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
     &PID1   &SECID1     &MID1         0    &HGID1         0         0         0
*END
