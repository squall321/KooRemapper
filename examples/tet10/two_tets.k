*KEYWORD
*TITLE
Two TET4 elements sharing one face - for TET10 conversion test
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       0.500000       1.000000       0.000000
       4       0.500000       0.500000       1.000000
       5       0.500000       0.500000      -1.000000
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       4       4       4       4
       2       1       1       3       2       5       5       5       5       5
*PART
TET4 part
$#     pid     secid       mid
         1         1         1
*SECTION_SOLID
$#  secid    elform
         1        10
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09    210000       0.3
*END
