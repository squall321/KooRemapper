*KEYWORD
*NODE
       1       0.0       0.0       0.0
       2       1.0       0.0       0.0
       3       1.0       1.0       0.0
       4       0.0       1.0       0.0
       5       0.0       0.0       1.0
       6       1.0       0.0       1.0
       7       1.0       1.0       1.0
       8       0.0       1.0       1.0
       9       2.0       0.0       0.0
      10       2.0       1.0       0.0
      11       2.0       0.0       1.0
      12       2.0       1.0       1.0
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       2       9      10       3       6      11      12       7
*PART
$#
Part1
$#     pid     secid       mid
       1       1       1
*PART
$#
Part2
$#     pid     secid       mid
       2       1       1
*SECTION_SOLID
$#   secid    elform       aet
       1       1       0
*MAT_ELASTIC
$#     mid        ro         e        pr        da        db  not used
       1  7.85E-09    210000       0.3
*INCLUDE
 iga_multi_out_iga_p1.k
*INCLUDE
 iga_multi_out_iga_p2.k
*END
