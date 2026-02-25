*KEYWORD
*TITLE
ALE All Presets Test - 14 parts
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
$
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       1       2       3       4       5       6       7       8
       3       3       1       2       3       4       5       6       7       8
       4       4       1       2       3       4       5       6       7       8
       5       5       1       2       3       4       5       6       7       8
       6       6       1       2       3       4       5       6       7       8
       7       7       1       2       3       4       5       6       7       8
       8       8       1       2       3       4       5       6       7       8
       9       9       1       2       3       4       5       6       7       8
      10      10       1       2       3       4       5       6       7       8
      11      11       1       2       3       4       5       6       7       8
      12      12       1       2       3       4       5       6       7       8
      13      13       1       2       3       4       5       6       7       8
      14      14       1       2       3       4       5       6       7       8
$
*PART
air part
         1         1        15         1         1         0         0         0
*PART
nitrogen part
         2         2        16         2         1         0         0         0
*PART
argon part
         3         3        17         3         1         0         0         0
*PART
water part
         4         4        18         4         1         0         0         0
*PART
electrolyte part
         5         5        19         5         1         0         0         0
*PART
gasoline part
         6         6        20         6         1         0         0         0
*PART
oil part
         7         7        21         7         1         0         0         0
*PART
coolant part
         8         8        22         8         1         0         0         0
*PART
resin part
         9         9        23         9         1         0         0         0
*PART
tim part
        10        10        24        10         1         0         0         0
*PART
silicone part
        11        11        25        11         1         0         0         0
*PART
tnt part
        12        12        26        12         1         0         0         0
*PART
c4 part
        13        13        27        13         1         0         0         0
*PART
vacuum part
        14        14        28         0         1         0         0         0
$
*SECTION_SOLID
         1        11
*SECTION_SOLID
         2        11
*SECTION_SOLID
         3        11
*SECTION_SOLID
         4        11
*SECTION_SOLID
         5        11
*SECTION_SOLID
         6        11
*SECTION_SOLID
         7        11
*SECTION_SOLID
         8        11
*SECTION_SOLID
         9        11
*SECTION_SOLID
        10        11
*SECTION_SOLID
        11        11
*SECTION_SOLID
        12        11
*SECTION_SOLID
        13        11
*SECTION_SOLID
        14        11
$
*MAT_ELASTIC
         1  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         2  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         3  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         4  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         5  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         6  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         7  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         8  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
         9  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
        10  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
        11  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
        12  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
        13  7.85E-09  2.10E+05  3.00E-01
*MAT_ELASTIC
        14  7.85E-09  2.10E+05  3.00E-01
$
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        15 1.293E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
*EOS_LINEAR_POLYNOMIAL
$    EOSID        C0        C1        C2        C3        C4        C5        C6
         1  0.000000  0.000000  0.000000  0.000000  0.400000  0.400000  0.000000
$       E0        V0
2.5330E-01  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        16 1.165E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
*EOS_LINEAR_POLYNOMIAL
$    EOSID        C0        C1        C2        C3        C4        C5        C6
         2  0.000000  0.000000  0.000000  0.000000  0.400000  0.400000  0.000000
$       E0        V0
2.2800E-01  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        17 1.661E-12  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000
*EOS_LINEAR_POLYNOMIAL
$    EOSID        C0        C1        C2        C3        C4        C5        C6
         3  0.000000  0.000000  0.000000  0.000000  0.670000  0.670000  0.000000
$       E0        V0
1.5190E-01  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        18 1.000E-09  0.000000 0.000E+00  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         4 1.484E+06  1.979000  0.000000  0.000000  0.110000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        19 1.180E-09  0.000000 0.000E+00  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         5 1.200E+06  1.580000  0.000000  0.000000  0.130000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        20 7.500E-10  0.000000 0.000E+00  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         6 1.250E+06  1.600000  0.000000  0.000000  0.100000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        21 8.700E-10  0.000000 0.000E+00  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         7 1.350E+06  1.800000  0.000000  0.000000  0.100000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        22 1.080E-09  0.000000 0.000E+00  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         8 1.600E+06  1.850000  0.000000  0.000000  0.120000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        23 1.150E-09  0.000000 1.000E-05  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
         9 1.700E+06  1.700000  0.000000  0.000000  0.100000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        24 2.800E-09  0.000000 5.000E-04  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
        10 1.800E+06  1.600000  0.000000  0.000000  0.100000  0.000000  0.000000
$       V0
  1.000000
*MAT_NULL
$      MID        RO        PC        MU     TEROD     CEROD        YM        PR
        25 1.050E-09  0.000000 1.000E-04  0.000000  0.000000  0.000000  0.000000
*EOS_GRUNEISEN
$    EOSID         C        S1        S2        S3     GAMAO         A        E0
        11 1.050E+06  1.500000  0.000000  0.000000  0.100000  0.000000  0.000000
$       V0
  1.000000
*MAT_HIGH_EXPLOSIVE_BURN
$      MID        RO         D       PCJ      BETA         K         G      SIGY
        26 1.630E-09 6.930E+06 2.100E+04  0.000000  0.000000  0.000000  0.000000
*EOS_JWL
$    EOSID         A         B        R1        R2      OMEG        E0        VO
        12 3.712E+05 3.231E+03  4.150000  0.950000  0.300000 7.000E+03  1.000000
*MAT_HIGH_EXPLOSIVE_BURN
$      MID        RO         D       PCJ      BETA         K         G      SIGY
        27 1.601E-09 8.193E+06 2.800E+04  0.000000  0.000000  0.000000  0.000000
*EOS_JWL
$    EOSID         A         B        R1        R2      OMEG        E0        VO
        13 6.098E+05 1.295E+04  4.500000  1.400000  0.250000 9.000E+03  1.000000
*MAT_VACUUM
$      MID        RO
        28 1.000E-18
*HOURGLASS
$     HGID       IHQ        QM       IBQ        Q1        Q2    QB/VDC        QW
         1         3 1.000E-06         0  1.500000 6.000E-02  0.100000  0.100000
*CONTROL_ALE
$      DCT      NADV      METH      AFAC      BFAC      CFAC      DFAC      EFAC
         1         1         2  0.000000  0.000000  0.000000  0.000000  0.000000
*ALE_MULTI-MATERIAL_GROUP
$      SID    IDTYPE
         1         1
         2         1
         3         1
         4         1
         5         1
         6         1
         7         1
         8         1
         9         1
        10         1
        11         1
        12         1
        13         1
        14         1
*ALE_REFERENCE_SYSTEM_GROUP
$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT
         0         0         4         0         0         0
*INITIAL_DETONATION
$      PID         X         Y         Z        LT
        12    0.5000    0.5000    0.5000    0.0000
*END
