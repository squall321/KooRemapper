$# LS-DYNA Keyword File
$# Replace test: 2-part model for assemble replace operation
$# Part 1: Coarse arc region (to be replaced with detail mesh)
$# Part 2: Adjacent block (to be preserved)
*KEYWORD
*NODE
$#   nid               x               y               z
         1   0.0000000e+00   0.0000000e+00   0.0000000e+00
         2   5.0000000e+00   0.0000000e+00   0.0000000e+00
         3   5.0000000e+00   2.0000000e+00   0.0000000e+00
         4   0.0000000e+00   2.0000000e+00   0.0000000e+00
         5   0.0000000e+00   0.0000000e+00   2.0000000e+00
         6   5.0000000e+00   0.0000000e+00   2.0000000e+00
         7   5.0000000e+00   2.0000000e+00   2.0000000e+00
         8   0.0000000e+00   2.0000000e+00   2.0000000e+00
       9 8.515000000e+00 0.000000000e+00 0.000000000e+00
      10 9.985000000e+00 0.000000000e+00 0.000000000e+00
      11 9.985000000e+00 2.000000000e+00 0.000000000e+00
      12 8.515000000e+00 2.000000000e+00 0.000000000e+00
      13 8.515000000e+00 0.000000000e+00 5.000000000e+00
      14 9.985000000e+00 0.000000000e+00 5.000000000e+00
      15 9.985000000e+00 2.000000000e+00 5.000000000e+00
      16 8.515000000e+00 2.000000000e+00 5.000000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       2       1       2       3       4       5       6       7       8
       2       1       9      10      11      12      13      14      15      16
*PART
Arc region (coarse)
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
*BOUNDARY_SPC_NODE
$# This should be preserved in the output
$#   nid       dofx      dofy      dofz     dofrx     dofry     dofrz
         1       1         1         1         0         0         0
         4       1         1         1         0         0         0
         5       1         1         1         0         0         0
         8       1         1         1         0         0         0
*INCLUDE
assembled_dr_result.dynain
*CONTROL_DYNAMIC_RELAXATION
$#  nrcyck    drtol   drfctr   drterm   tssfdr   irelal    edttl    idrflg
       250 0.001000       0.0       0.0       0.0         0       0.0         0
*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas     nosol
       0.0         0       0.0       0.0       0.01e+20         0
*END
