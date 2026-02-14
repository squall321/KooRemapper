$# LS-DYNA Keyword File
$# Test model with existing *CONTROL_TERMINATION
*KEYWORD
*NODE
$#   nid               x               y               z
       1 5.000000000e-02 0.000000000e+00 0.000000000e+00
       2 4.950000000e+00 0.000000000e+00 0.000000000e+00
       3 4.950000000e+00 2.000000000e+00 0.000000000e+00
       4 5.000000000e-02 2.000000000e+00 0.000000000e+00
       5 5.000000000e-02 0.000000000e+00 2.000000000e+00
       6 4.950000000e+00 0.000000000e+00 2.000000000e+00
       7 4.950000000e+00 2.000000000e+00 2.000000000e+00
       8 5.000000000e-02 2.000000000e+00 2.000000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
*PART
Block
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         1                1       1        0       0           0         0
*SECTION_SOLID
$#  secid    elform
         1         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09  2.10E+05       0.3
*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas     nosol
       0.0         0       0.0       0.0       0.01e+20         0
*INCLUDE
assembled_dr_term_result.dynain
*CONTROL_DYNAMIC_RELAXATION
$#  nrcyck    drtol   drfctr   drterm   tssfdr   irelal    edttl    idrflg
       250 0.001000       0.0       0.0       0.0         0       0.0         0
*END
