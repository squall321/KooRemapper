*KEYWORD
*TITLE
Test Explicit Model
*CONTROL_TERMINATION
$    ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS
         1         0       0.0       0.0       0.0
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS    LCTM     ERODE    MSIST
       0.0  0.900000         0       0.0       0.0         0         0         0
*DEFINE_CURVE_TITLE
Material_Stress_Strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
         2         0     1.000     1.000       0.0       0.0         0
$                  X                   Y
           0.000000            0.000000
           0.200000          200.000000
*SECTION_SHELL_TITLE
Shell_Section
$    SECID    ELFORM      SHRF       NIP     PROPT   QR/IRID     ICOMP      SETYP
         1        16  0.833333         2     1.000         0         0         1
$      T1        T2        T3        T4      NLOC    MAREA     IDOF    EDGSET
  1.000000  1.000000  1.000000  1.000000       0.0       0.0       0.0
*MAT_ELASTIC_TITLE
Steel
$      MID       RHO         E        PR        DA        DB  NOT USED
         1  7.85E-09  210000.0      0.30       0.0       0.0
*PART
Steel_Shell
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         0         0         0         0
*NODE
$      NID               X               Y               Z      TC      RC
         1         0.000000         0.000000         0.000000       0       0
         2         1.000000         0.000000         0.000000       0       0
         3         1.000000         1.000000         0.000000       0       0
         4         0.000000         1.000000         0.000000       0       0
*ELEMENT_SHELL
$    EID     PID      N1      N2      N3      N4
       1       1       1       2       3       4
*CONTROL_IMPLICIT_GENERAL
$   IMFLAG       DT0    IMFORM      NSBS       IGS    CNSTN      FORM    ZERO_V
         1  0.000020         2         1         2         0         0         0
*CONTROL_IMPLICIT_DYNAMICS
$    IMASS     GAMMA      BETA    TDYBIR    TDYDTH    TDYBUR     IRATE
         0  0.500000  0.250000       0.0 1.000E+28 1.000E+28         0
*CONTROL_IMPLICIT_SOLUTION
$   NSOLVR    ILIMIT    MAXREF     DCTOL     ECTOL     RCTOL     LSTOL    ABSTOL
         7        40        50  0.000100  0.001000 1.000E-02  0.990000 1.000E-10
$    DNORM    DIVERG     ISTIF   NLPRINT    NLNORM   D3ITCTL     CPCHK
         0         0         1         0         0         0         0
$   ARCCTL    ARCDIR    ARCLEN    ARCMTH    ARCDMP    ARCPSI    ARCALF    ARCTIM
         0         0  0.000000         1         2  0.000000  0.000000  0.000000
*CONTROL_IMPLICIT_AUTO
$    IAUTO    ITEOPT    ITEWIN     DTMIN     DTMAX     DTEXP     KFAIL    KCYCLE
         1        20         5-1.000E-06 1.000E-04       0.0        15         0
*CONTROL_IMPLICIT_STABILIZATION
$       IAS     SCALE    TSTART      TEND
         1  1.000000       0.0 1.000E+28
*CONTROL_IMPLICIT_SOLVER
$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC   AUTOTOL
        30         0         2         0         4       0.0         1       0.0
*END
