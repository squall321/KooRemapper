*KEYWORD
*TITLE
ALE Shared Section Test
$
*NODE
       1  0.000000  0.000000  0.000000
       2  1.000000  0.000000  0.000000
       3  1.000000  1.000000  0.000000
       4  0.000000  1.000000  0.000000
       5  0.000000  0.000000  1.000000
       6  1.000000  0.000000  1.000000
       7  1.000000  1.000000  1.000000
       8  0.000000  1.000000  1.000000
       9  2.000000  0.000000  0.000000
      10  2.000000  1.000000  0.000000
      11  2.000000  0.000000  1.000000
      12  2.000000  1.000000  1.000000
$
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       2       9      10       3       6      11      12       7
$
*PART
Structure (shared sec)
         1         1         1         0         0         0         0         0
*PART
Air domain (shared sec)
         2         2         3         1         1         0         0         0
$
*SECTION_SOLID
         1         1
$
*MAT_ELASTIC
         1  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         2  1.29E-12  1.01E-01  0.00E+00
$
*SECTION_SOLID
$    SECID    ELFORM       AET
         2        11
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
         3 1.293E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
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
         2         1
*ALE_REFERENCE_SYSTEM_GROUP
$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT
         0         0         4         0         0         0
*END
