*KEYWORD
*TITLE
Single TRIA3 shell element
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       0.500000       1.000000       0.000000
       4 5.000000000e-01 0.000000000e+00 0.000000000e+00
       5 7.500000000e-01 5.000000000e-01 0.000000000e+00
       6 2.500000000e-01 5.000000000e-01 0.000000000e+00
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4
       1       1       1       2       3       3
*PART
TRIA3 part
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
