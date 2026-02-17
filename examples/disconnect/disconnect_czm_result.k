*KEYWORD
*TITLE
Two HEX8 elements in different parts - for CZM/MEFEM test
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       1.000000       1.000000       0.000000
       4       0.000000       1.000000       0.000000
       5       0.000000       0.000000       1.000000
       6       1.000000       0.000000       1.000000
       7       1.000000       1.000000       1.000000
       8       0.000000       1.000000       1.000000
       9       0.000000       0.000000       2.000000
      10       1.000000       0.000000       2.000000
      11       1.000000       1.000000       2.000000
      12       0.000000       1.000000       2.000000
      13 0.000000000e+00 0.000000000e+00 1.000000000e+00
      14 1.000000000e+00 0.000000000e+00 1.000000000e+00
      15 1.000000000e+00 1.000000000e+00 1.000000000e+00
      16 0.000000000e+00 1.000000000e+00 1.000000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       2      13      14      15      16       9      10      11      12
       3       3       5       6       7       8      13      14      15      16
*PART
Layer 1
$#     pid     secid       mid
         1         1         1
*PART
Layer 2
$#     pid     secid       mid
         2         2         1
*SECTION_SOLID
$#  secid    elform
         1         1
*SECTION_SOLID
$#  secid    elform
         2         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09    210000       0.3
*MAT_COHESIVE_MIXED_MODE
$#     mid        ro     roflg   intfail        en        et       gic      giic
         2     0.0         0       0.0     1.0E6     1.0E6       1.0       2.0
$#      xmu         t         s       und       utd     gamma
       1.0      50.0      30.0       0.0       0.0       1.0
*SECTION_SOLID
$#  secid    elform
         3        19
*PART
Cohesive interface
$#     pid     secid       mid
         3         3         2
*END
