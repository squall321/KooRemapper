$# LS-DYNA Keyword File
$# Combined test: 3-part model for assemble replace + squeeze
$# Part 1: Coarse arc region (to be replaced with detail mesh)
$# Part 2: Adjacent block (to be preserved as-is)
$# Part 3: Inner block (to be squeezed)
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
         9   8.5000000e+00   0.0000000e+00   0.0000000e+00
        10   1.0000000e+01   0.0000000e+00   0.0000000e+00
        11   1.0000000e+01   2.0000000e+00   0.0000000e+00
        12   8.5000000e+00   2.0000000e+00   0.0000000e+00
        13   8.5000000e+00   0.0000000e+00   5.0000000e+00
        14   1.0000000e+01   0.0000000e+00   5.0000000e+00
        15   1.0000000e+01   2.0000000e+00   5.0000000e+00
        16   8.5000000e+00   2.0000000e+00   5.0000000e+00
        17   6.0000000e+00   0.0000000e+00   0.0000000e+00
        18   8.0000000e+00   0.0000000e+00   0.0000000e+00
        19   8.0000000e+00   2.0000000e+00   0.0000000e+00
        20   6.0000000e+00   2.0000000e+00   0.0000000e+00
        21   6.0000000e+00   0.0000000e+00   2.0000000e+00
        22   8.0000000e+00   0.0000000e+00   2.0000000e+00
        23   8.0000000e+00   2.0000000e+00   2.0000000e+00
        24   6.0000000e+00   2.0000000e+00   2.0000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       2       1       2       3       4       5       6       7       8
       2       1       9      10      11      12      13      14      15      16
       3       3      17      18      19      20      21      22      23      24
*PART
Arc region (coarse)
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         1                1       1        0       0           0         0
*PART
Adjacent block
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         2                1       1        0       0           0         0
*PART
Inner block
$#   pid             secid     mid    eosid    hgid      adpopt      tmid
         3                1       1        0       0           0         0
*SECTION_SOLID
$#  secid    elform
         1         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09  2.10E+05       0.3
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE
$# This contact definition should be preserved
$#  ssid      msid
         2         3
*BOUNDARY_SPC_NODE
$#   nid       dofx      dofy      dofz     dofrx     dofry     dofrz
         1       1         1         1         0         0         0
         4       1         1         1         0         0         0
*END
