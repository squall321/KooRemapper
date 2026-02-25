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
       6 0.000000000e+00 0.000000000e+00 5.000000000e-01
       7 1.000000000e+00 0.000000000e+00 5.000000000e-01
       8 5.000000000e-01 5.000000000e-01 1.500000000e+00
       9 5.000000000e-01 1.000000000e+00 5.000000000e-01
      10 5.000000000e-01 5.000000000e-01-5.000000000e-01
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       4       4       4       4
       2       1       1       3       2       5       5       5       5       5
       3      10       1       2       4       4       6       7       8       8
       4      10       1       3       5       5       6       9      10      10
       5      10       1       4       4       4       6       8       8       8
       6      10       1       5       5       5       6      10      10      10
       7      10       2       3       4       4       7       9       8       8
       8      10       3       2       5       5       9       7      10      10
       9      10       5       2       5       5      10       7      10      10
      10      10       4       3       4       4       8       9       8       8
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
*PART
"TET4_Offset_Test"
        10         2         2
*SECTION_SOLID
$#   secid    elform       aet
         2         1
*MAT_ELASTIC
$#     mid        ro         e        pr
              2  7.85E-09    210000       0.3*END
