$
$ LS-DYNA Test File with MAT_VISCOELASTIC (deformed)
$
*KEYWORD
*PART
$#                                                                         title
Viscoelastic Part
$#     pid     secid       mid
         1         1         1
*MAT_VISCOELASTIC
$#     mid        ro      bulk        g0        gi      beta
         1  1.00e-09   2000.00   1000.00    500.00      0.10
*SECTION_SOLID
$#   secid    elform
         1         1
*NODE
       1      0.0      0.0      0.0
       2     10.0      0.0      0.5
       3     10.0     10.0      0.5
       4      0.0     10.0      0.0
       5      0.0      0.0     10.0
       6     10.0      0.0     10.5
       7     10.0     10.0     10.5
       8      0.0     10.0     10.0
       9     20.0      0.0      1.5
      10     20.0     10.0      1.5
      11     20.0      0.0     11.5
      12     20.0     10.0     11.5
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       1       2       9      10       3       6      11      12       7
*END
