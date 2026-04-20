$ 3-layer stacked box: Steel / Polymer(VE) / Aluminum
$ 2x2 in-plane, 3 layers in Z
$ Layer 1 (z=0~1): PID=1, Steel MAT_ELASTIC
$ Layer 2 (z=1~2): PID=2, Polymer MAT_GENERAL_VISCOELASTIC
$ Layer 3 (z=2~3): PID=3, Aluminum MAT_024
*KEYWORD
$
$ ==================== MATERIALS ====================
$
*MAT_ELASTIC_TITLE
Steel_E210
$#     mid        ro         e        pr        da        db  not used
         1 7.850E-09    210000      0.30       0.0       0.0       0.0
*MAT_GENERAL_VISCOELASTIC_TITLE
Polymer_VE
$#     mid        ro      bulk       pcf        ef      tref         a         b
         2 1.200E-09 3.000E+03       0.0       0.0       0.0       0.0       0.0
$#    lcid        nt    bstart     tramp     lcidk       ntk   bstartk    trampk
         0         0       0.0       0.0         0         0       0.0       0.0
$#      gi     betai        ki    betaki
 2.000E+02       0.0       0.0       0.0
 5.000E+01 1.000E+00       0.0       0.0
 1.000E+02 1.000E+02       0.0       0.0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Aluminum_024
$#     mid        ro         e        pr      sigy      etan      fail      tdel
         3 2.700E-09     70000      0.33     280.0       0.0       0.0       0.0
$#      c         p      lcss      lcsr        vp     lcf    unused
       0.0       0.0         0         0       0.0         0       0.0
$
$ ==================== CTE ====================
$
*MAT_ADD_THERMAL_EXPANSION_TITLE
Steel_CTE
$#     pid      lcid      mult
         1         0    1.0000
$#                                   alpha
  1.20E-05
*MAT_ADD_THERMAL_EXPANSION_TITLE
Aluminum_CTE
$#     pid      lcid      mult
         3         0    1.0000
$#                                   alpha
  2.30E-05
$
$ ==================== SECTIONS ====================
$
*SECTION_SOLID
$#   secid    elform
         1         1
*SECTION_SOLID
$#   secid    elform
         2         1
*SECTION_SOLID
$#   secid    elform
         3         1
$
$ ==================== PARTS ====================
$
*PART
Steel_Layer
         1         1         1
*PART
Polymer_Layer
         2         2         2
*PART
Aluminum_Layer
         3         3         3
$
$ ==================== NODES ====================
$ 3x3 grid x 4 planes (z=0,1,2,3)
$
*NODE
         1       0.0       0.0       0.0
         2       5.0       0.0       0.0
         3      10.0       0.0       0.0
         4       0.0       5.0       0.0
         5       5.0       5.0       0.0
         6      10.0       5.0       0.0
         7       0.0      10.0       0.0
         8       5.0      10.0       0.0
         9      10.0      10.0       0.0
        10       0.0       0.0       1.0
        11       5.0       0.0       1.0
        12      10.0       0.0       1.0
        13       0.0       5.0       1.0
        14       5.0       5.0       1.0
        15      10.0       5.0       1.0
        16       0.0      10.0       1.0
        17       5.0      10.0       1.0
        18      10.0      10.0       1.0
        19       0.0       0.0       2.0
        20       5.0       0.0       2.0
        21      10.0       0.0       2.0
        22       0.0       5.0       2.0
        23       5.0       5.0       2.0
        24      10.0       5.0       2.0
        25       0.0      10.0       2.0
        26       5.0      10.0       2.0
        27      10.0      10.0       2.0
        28       0.0       0.0       3.0
        29       5.0       0.0       3.0
        30      10.0       0.0       3.0
        31       0.0       5.0       3.0
        32       5.0       5.0       3.0
        33      10.0       5.0       3.0
        34       0.0      10.0       3.0
        35       5.0      10.0       3.0
        36      10.0      10.0       3.0
$
$ ==================== ELEMENTS ====================
$ Layer 1 (z=0~1): PID=1
$
*ELEMENT_SOLID
$ Layer 2 (z=1~2): PID=2
$ Layer 3 (z=2~3): PID=3
$
$
$ === Merged: Homogenized_Stack ===
$
*MAT_ELASTIC_TITLE
Homogenized_Stack
$#     mid        ro         e        pr        da        db  not used
         4 3.917E-09   47635.2    0.3658       0.0       0.0       0.0
*MAT_ADD_THERMAL_EXPANSION_TITLE
Homogenized_Stack_CTE
$#     pid      lcid      mult
         4         0 1.000E+00
$#                                   alpha
 1.167E-05
*SECTION_SOLID
$#   secid    elform
         4         1
*PART
Homogenized_Stack
         4         4         4
$
$ === Merged Elements ===
$
*ELEMENT_SOLID
      13       4       1       2       5       4      28      29      32      31
      14       4       2       3       6       5      29      30      33      32
      15       4       4       5       8       7      31      32      35      34
      16       4       5       6       9       8      32      33      36      35
*END
