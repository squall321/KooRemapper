$# LS-DYNA Keyword File
$# Restack test: Part 1 is Z-extruded (2 layers), Part 2 is adjacent
*KEYWORD
*NODE
$#   nid               x               y               z
       1   0.000000e+00   0.000000e+00   0.000000e+00
       2   1.000000e+00   0.000000e+00   0.000000e+00
       3   1.000000e+00   1.000000e+00   0.000000e+00
       4   0.000000e+00   1.000000e+00   0.000000e+00
       9   0.000000e+00   0.000000e+00   1.000000e+00
      10   1.000000e+00   0.000000e+00   1.000000e+00
      11   1.000000e+00   1.000000e+00   1.000000e+00
      12   0.000000e+00   1.000000e+00   1.000000e+00
      13   2.000000e+00   0.000000e+00   0.000000e+00
      14   2.000000e+00   1.000000e+00   0.000000e+00
      15   2.000000e+00   0.000000e+00   1.000000e+00
      16   2.000000e+00   1.000000e+00   1.000000e+00
      17 0.000000000e+00 0.000000000e+00 3.181818182e-01
      18 0.000000000e+00 0.000000000e+00 6.818181818e-01
      19 1.000000000e+00 0.000000000e+00 3.181818182e-01
      20 1.000000000e+00 0.000000000e+00 6.818181818e-01
      21 1.000000000e+00 1.000000000e+00 3.181818182e-01
      22 1.000000000e+00 1.000000000e+00 6.818181818e-01
      23 0.000000000e+00 1.000000000e+00 3.181818182e-01
      24 0.000000000e+00 1.000000000e+00 6.818181818e-01
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       3       2       2      13      14       3      10      15      16      11
       4       3       1       2       3       4      17      19      21      23
       5       4      17      19      21      23      18      20      22      24
       6       5      18      20      22      24       9      10      11      12
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
*MAT_ELASTIC
$#     mid        ro         e        pr
          2  7.85E-09  2.10E+05       0.3

*SECTION_SOLID
$#  secid    elform
         2         1
*PART
Restack Layer 1
$#     pid     secid       mid
         3         2         2
*MAT_ELASTIC
$#     mid        ro         e        pr
          3  7.85E-09  1.50E+05      0.25

*SECTION_SOLID
$#  secid    elform
         3         1
*PART
Restack Layer 2
$#     pid     secid       mid
         4         3         3
*SECTION_SOLID
$#  secid    elform
         4         1
*PART
Restack Layer 3
$#     pid     secid       mid
         5         4         2
*INCLUDE
restack_mismatch_result.dynain
*CONTROL_DYNAMIC_RELAXATION
$#  nrcyck    drtol   drfctr   drterm   tssfdr   irelal    edttl    idrflg
       250 0.001000       0.0       0.0       0.0         0       0.0         0
*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas     nosol
       0.0         0       0.0       0.0       0.01e+20         0
*END
