$# LS-DYNA Keyword File
$# Restack test: Part 1 is Z-extruded (2 layers), Part 2 is adjacent
*KEYWORD
*NODE
$#   nid               x               y               z
       1   0.000000e+00   0.000000e+00   0.000000e+00
       2   1.000000e+00   0.000000e+00   0.000000e+00
       3   1.000000e+00   1.000000e+00   0.000000e+00
       4   0.000000e+00   1.000000e+00   0.000000e+00
       5   0.000000e+00   0.000000e+00   5.000000e-01
       6   1.000000e+00   0.000000e+00   5.000000e-01
       7   1.000000e+00   1.000000e+00   5.000000e-01
       8   0.000000e+00   1.000000e+00   5.000000e-01
       9   0.000000e+00   0.000000e+00   1.000000e+00
      10   1.000000e+00   0.000000e+00   1.000000e+00
      11   1.000000e+00   1.000000e+00   1.000000e+00
      12   0.000000e+00   1.000000e+00   1.000000e+00
      13   2.000000e+00   0.000000e+00   0.000000e+00
      14   2.000000e+00   1.000000e+00   0.000000e+00
      15   2.000000e+00   0.000000e+00   1.000000e+00
      16   2.000000e+00   1.000000e+00   1.000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       1       5       6       7       8       9      10      11      12
       3       2       2      13      14       3      10      15      16      11
*PART
Extruded block
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         1                1       1        0       0           0         0
*PART
Adjacent block
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         2                1       1        0       0           0         0
*SECTION_SOLID
$#  secid    elform
         1         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09  2.10E+05       0.3
*END
