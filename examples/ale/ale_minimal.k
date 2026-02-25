*KEYWORD
*TITLE
ALE Example Base Model
$
$ Simple multi-part solid model for ALE examples
$ PIDs: 1,2 = Lagrangian structure, 3-5 = Fluid/HE domains, 10 = Electrolyte
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
      13  3.000000  0.000000  0.000000
      14  3.000000  1.000000  0.000000
      15  3.000000  0.000000  1.000000
      16  3.000000  1.000000  1.000000
      17  4.000000  0.000000  0.000000
      18  4.000000  1.000000  0.000000
      19  4.000000  0.000000  1.000000
      20  4.000000  1.000000  1.000000
      21  5.000000  0.000000  0.000000
      22  5.000000  1.000000  0.000000
      23  5.000000  0.000000  1.000000
      24  5.000000  1.000000  1.000000
      25  6.000000  0.000000  0.000000
      26  6.000000  1.000000  0.000000
      27  6.000000  0.000000  1.000000
      28  6.000000  1.000000  1.000000
$
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       2       9      10       3       6      11      12       7
       3       3       9      13      14      10      11      15      16      12
       4       4      13      17      18      14      15      19      20      16
       5       5      17      21      22      18      19      23      24      20
       6      10      21      25      26      22      23      27      28      24
$
*PART
Lagrangian plate
         1         1         1         0         0         0         0         0
*PART
Lagrangian frame
         2         1         2         0         0         0         0         0
*PART
Air domain
         3         3        11         1         1         0         0         0
*PART
Water domain
         4         2         4         0         0         0         0         0
*PART
Explosive region
         5         2         5         0         0         0         0         0
*PART
Electrolyte domain
        10         2        10         0         0         0         0         0
$
*SECTION_SOLID
         1         1
*SECTION_SOLID
         2         1
$
*MAT_ELASTIC
         1  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         2  1.29E-12  1.01E-01  0.00E+00
*MAT_ELASTIC
         3  1.29E-12  1.01E-01  0.00E+00
*MAT_ELASTIC
         4  1.00E-09  2.20E+03  4.90E-01
*MAT_ELASTIC
         5  1.63E-09  1.00E+01  0.00E+00
*MAT_ELASTIC
        10  1.18E-09  2.00E+03  4.90E-01
$
*CONTROL_TERMINATION
  1.000E-02         0  0.000000  0.000000  0.000000
$
*SECTION_SOLID
$    SECID    ELFORM       AET
         3        11
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        11 1.293E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
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
         3         1
*ALE_REFERENCE_SYSTEM_GROUP
$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT
         0         0         4         0         0         0
*END
