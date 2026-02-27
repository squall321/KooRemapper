$# LS-DYNA Keyword File - Contact test model
$# 3 solid parts, 2 contacts, 1 set
*KEYWORD
*NODE
$#   nid               x               y               z
         1   0.0000000e+00   0.0000000e+00   0.0000000e+00
         2   1.0000000e+00   0.0000000e+00   0.0000000e+00
         3   1.0000000e+00   1.0000000e+00   0.0000000e+00
         4   0.0000000e+00   1.0000000e+00   0.0000000e+00
         5   0.0000000e+00   0.0000000e+00   1.0000000e+00
         6   1.0000000e+00   0.0000000e+00   1.0000000e+00
         7   1.0000000e+00   1.0000000e+00   1.0000000e+00
         8   0.0000000e+00   1.0000000e+00   1.0000000e+00
         9   2.0000000e+00   0.0000000e+00   0.0000000e+00
        10   2.0000000e+00   1.0000000e+00   0.0000000e+00
        11   2.0000000e+00   0.0000000e+00   1.0000000e+00
        12   2.0000000e+00   1.0000000e+00   1.0000000e+00
        13   3.0000000e+00   0.0000000e+00   0.0000000e+00
        14   3.0000000e+00   1.0000000e+00   0.0000000e+00
        15   3.0000000e+00   0.0000000e+00   1.0000000e+00
        16   3.0000000e+00   1.0000000e+00   1.0000000e+00
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
       2       2       2       9      10       3       6      11      12       7
       3       3       9      13      14      10      11      15      16      12
*PART
Part_1_Left
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         1         1         1         0         0         0         0         0
*PART
Part_2_Center
         2         1         1         0         0         0         0         0
*PART
Part_3_Right
         3         1         1         0         0         0         0         0
*SECTION_SOLID
$#   secid    elform
         1         1
*MAT_ELASTIC
$#     mid        ro         e        pr
         1  7.85E-09  2.10E+05       0.3
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE
Contact_1_2
$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr
        11        12         0         0         0         0         0         0
$#      fs        fd        dc        vc       vdc    penchk        bt        dt
       0.2       0.1       0.0       0.0       0.0         0       0.0  1.00E+20
$#    sfsa      sfsb      sast      sbst     sfsat    sfsbt       fsf       vsf
       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0
*CONTACT_TIED_SURFACE_TO_SURFACE_TITLE
Contact_2_3
$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr
         2         3         3         3         0         0         0         0
$#      fs        fd        dc        vc       vdc    penchk        bt        dt
       0.0       0.0       0.0       0.0       0.0         0       0.0  1.00E+20
$#    sfsa      sfsb      sast      sbst     sfsat    sfsbt       fsf       vsf
       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0
*SET_PART_LIST_TITLE
AllParts
$#     sid       da1       da2       da3       da4    solver
        10       0.0       0.0       0.0       0.0MECH
$#    pid1      pid2      pid3      pid4      pid5      pid6      pid7      pid8
         1         2         3
*BOUNDARY_SPC_NODE
$#   nid       dofx      dofy      dofz     dofrx     dofry     dofrz
         1       1         1         1         0         0         0
*SET_SEGMENT_TITLE
Slave_PID1
$#     sid       da1       da2       da3       da4
        11  0.000000  0.000000  0.000000  0.000000
$#      n1        n2        n3        n4
         1         2         3         4
         1         2         6         5
         1         4         8         5
         2         3         7         6
         4         3         7         8
         5         6         7         8
*SET_SEGMENT_TITLE
Master_PID2
$#     sid       da1       da2       da3       da4
        12  0.000000  0.000000  0.000000  0.000000
$#      n1        n2        n3        n4
         2         3         7         6
         2         9        10         3
         2         9        11         6
         3        10        12         7
         6        11        12         7
         9        10        12        11
*END
