$
$ LS-DYNA Keyword File with Material
$
*KEYWORD
*PART
$#     pid     secid       mid
         1         1         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1   7.85e-9   210000.0       0.3
*SECTION_SOLID
$#   secid    elform
         1         1
*NODE
       1      0.0      0.0      0.0
       2     10.0      0.0      0.0
       3     10.0     10.0      0.0
       4      0.0     10.0      0.0
       5      0.0      0.0     10.0
       6     10.0      0.0     10.0
       7     10.0     10.0     10.0
       8      0.0     10.0     10.0
       9     20.0      0.0      0.0
      10     20.0     10.0      0.0
      11     20.0      0.0     10.0
      12     20.0     10.0     10.0
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       1       2       9      10       3       6      11      12       7
*END
