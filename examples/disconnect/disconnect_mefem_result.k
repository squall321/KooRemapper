*KEYWORD
*TITLE
Two HEX8 elements in different parts - for CZM/MEFEM test
*NODE
$#   nid               x               y               z
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       1.000000       1.000000       0.000000
       4       0.000000       1.000000       0.000000
       5       0.000000       0.000000       1.000000
       6       1.000000       0.000000       1.000000
       7       1.000000       1.000000       1.000000
       8       0.000000       1.000000       1.000000
       9       0.000000       0.000000       2.000000
      10       1.000000       0.000000       2.000000
      11       1.000000       1.000000       2.000000
      12       0.000000       1.000000       2.000000
      13 0.000000000e+00 0.000000000e+00 1.000000000e+00
      14 1.000000000e+00 0.000000000e+00 1.000000000e+00
      15 1.000000000e+00 1.000000000e+00 1.000000000e+00
      16 0.000000000e+00 1.000000000e+00 1.000000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       2      13      14      15      16       9      10      11      12
*PART
Layer 1
$#     pid     secid       mid
         1         1         1
*PART
Layer 2
$#     pid     secid       mid
         2         2         1
*SECTION_SOLID
$#  secid    elform
         1         1
*SECTION_SOLID
$#  secid    elform
         2         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09    210000       0.3
*SET_NODE_LIST
$#     sid
      1002
$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8
         5        13
*CONSTRAINED_TIED_NODES_FAILURE
$#    nsid      eppf     etype
      1002     0.085         1
*SET_NODE_LIST
$#     sid
      1003
$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8
         6        14
*CONSTRAINED_TIED_NODES_FAILURE
$#    nsid      eppf     etype
      1003     0.085         1
*SET_NODE_LIST
$#     sid
      1004
$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8
         7        15
*CONSTRAINED_TIED_NODES_FAILURE
$#    nsid      eppf     etype
      1004     0.085         1
*SET_NODE_LIST
$#     sid
      1005
$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8
         8        16
*CONSTRAINED_TIED_NODES_FAILURE
$#    nsid      eppf     etype
      1005     0.085         1
*END
