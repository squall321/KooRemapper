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
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
*PART
$#
Block
$#     pid     secid       mid
       1       1       1
*SECTION_SOLID
$#   secid    elform       aet
       1       1       0
*MAT_ELASTIC
$#     mid        ro         e        pr        da        db  not used
       1  7.85E-09    210000       0.3
*INCLUDE
 iga_out_iga_p1.k
*END
