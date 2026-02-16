*KEYWORD
*TITLE
Mixed QUAD4 and TRIA3 shell elements - for QUAD8/TRIA6 conversion test
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       1.000000       1.000000       0.000000
       4       0.000000       1.000000       0.000000
       5       2.000000       0.000000       0.000000
       6       2.000000       1.000000       0.000000
       7 5.000000000e-01 0.000000000e+00 0.000000000e+00
       8 1.000000000e+00 5.000000000e-01 0.000000000e+00
       9 5.000000000e-01 1.000000000e+00 0.000000000e+00
      10 0.000000000e+00 5.000000000e-01 0.000000000e+00
      11 1.500000000e+00 0.000000000e+00 0.000000000e+00
      12 2.000000000e+00 5.000000000e-01 0.000000000e+00
      13 1.500000000e+00 1.000000000e+00 0.000000000e+00
      14 5.000000000e-01 5.000000000e-01 0.000000000e+00
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4
       1       1       1       2       3       4       7       8       9      10
       2       1       2       5       6       3      11      12      13       8
       3       2       1       2       3       7       8      14       0       0
*PART
QUAD4 part
$#     pid     secid       mid
         1         1         1
*PART
TRIA3 part
$#     pid     secid       mid
         2         2         1
*SECTION_SHELL
$#  secid    elform      shrf       nip     propt   qr/irid     icomp
         1        23       1.0         2       0.0         0         0
$#     t1        t2        t3        t4
       1.0       1.0       1.0       1.0
*SECTION_SHELL
$#  secid    elform      shrf       nip     propt   qr/irid     icomp
         2        24       1.0         2       0.0         0         0
$#     t1        t2        t3        t4
       1.0       1.0       1.0       1.0
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09    210000       0.3
*END
