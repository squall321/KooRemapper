$# LS-DYNA Keyword File
$# Test: Part 1 = TSHELL, Part 2 = SHELL, Part 3 = SOLID
*KEYWORD
*NODE
$#   nid               x               y               z
       1   0.000000e+00   0.000000e+00   0.000000e+00
       2   1.000000e+00   0.000000e+00   0.000000e+00
       3   1.000000e+00   1.000000e+00   0.000000e+00
       4   0.000000e+00   1.000000e+00   0.000000e+00
       5   0.000000e+00   0.000000e+00   1.000000e+00
       6   1.000000e+00   0.000000e+00   1.000000e+00
       7   1.000000e+00   1.000000e+00   1.000000e+00
       8   0.000000e+00   1.000000e+00   1.000000e+00
       9   2.000000e+00   0.000000e+00   0.000000e+00
      10   2.000000e+00   1.000000e+00   0.000000e+00
      11   2.000000e+00   0.000000e+00   1.000000e+00
      12   2.000000e+00   1.000000e+00   1.000000e+00
      13   3.000000e+00   0.000000e+00   0.000000e+00
      14   3.000000e+00   1.000000e+00   0.000000e+00
      15   3.000000e+00   0.000000e+00   1.000000e+00
      16   3.000000e+00   1.000000e+00   1.000000e+00
*ELEMENT_TSHELL
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4
       2       2       2       9      10       3
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       3       3       9      13      14      10      11      15      16      12
*PART
TSHELL Part
$#   pid             secid     mid
         1                1       1        0       0           0         0
*PART
Shell Part
$#   pid             secid     mid
         2                2       1        0       0           0         0
*PART
Solid Part
$#   pid             secid     mid
         3                3       1        0       0           0         0
*SECTION_TSHELL_TITLE
My Tshell Section
$#  secid    elform
         1         1
*SECTION_SHELL
$#  secid    elform
         2         2
*SECTION_SOLID
$#  secid    elform
         3         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09  2.10E+05       0.3
*END
