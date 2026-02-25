*KEYWORD
*TITLE
ALE Shell Warning Test
$
*NODE
       1  0.000000  0.000000  0.000000
       2  1.000000  0.000000  0.000000
       3  1.000000  1.000000  0.000000
       4  0.000000  1.000000  0.000000
$
*ELEMENT_SHELL
       1       1       1       2       3       4
$
*PART
Shell part
         1         1         2         1         1         0         0         0
$
*SECTION_SHELL
         1         2  1.000000
$
*MAT_ELASTIC
         1  7.85E-09  2.10E+05  3.00E-01
$
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
         2 1.293E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
*EOS_LINEAR_POLYNOMIAL
$    EOSID        C0        C1        C2        C3        C4        C5        C6
         1  0.000000  0.000000  0.000000  0.000000  0.400000  0.400000  0.000000
$       E0        V0
2.5330E-01  1.000000
*HOURGLASS
$     HGID       IHQ        QM       IBQ        Q1        Q2    QB/VDC        QW
         1         3 1.000E-06         0  1.500000 6.000E-02  0.100000  0.100000
*CONTROL_ALE
$      DCT      NADV      METH      AFAC      BFAC      CFAC      DFAC      EFAC
         1         1         2  0.000000  0.000000  0.000000  0.000000  0.000000
*ALE_MULTI-MATERIAL_GROUP
$      SID    IDTYPE
         1         1
*ALE_REFERENCE_SYSTEM_GROUP
$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT
         0         0         4         0         0         0
*END
