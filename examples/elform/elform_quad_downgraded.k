*KEYWORD
*TITLE
Single QUAD4 shell element - ELFORM 2 test
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       1.000000       1.000000       0.000000
       4       0.000000       1.000000       0.000000
       5 5.000000000e-01 0.000000000e+00 0.000000000e+00
       6 1.000000000e+00 5.000000000e-01 0.000000000e+00
       7 5.000000000e-01 1.000000000e+00 0.000000000e+00
       8 0.000000000e+00 5.000000000e-01 0.000000000e+00
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4
       1       1       1       2       3       4
*PART
QUAD4 part
$#     pid     secid       mid
         1         1         1
*SECTION_SHELL
$#  secid    elform      shrf       nip     propt
         1         2       0.0         2       0.0
$#     t1        t2        t3        t4
       1.0       1.0       1.0       1.0
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09    210000       0.3
*END
