*KEYWORD
*TITLE
Complex K-File with Multiple Materials and Keywords
*SET_SEGMENT
$# sid       da1       da2       da3       da4    solver
         1       0.0       0.0       0.0       0.0MECH
$#      n1        n2        n3        n4        a1        a2        a3        a4
         1         2         3         4       0.0       0.0       0.0       0.0
*DEFINE_CURVE
$#    lcid      sidr       sfa       sfo      offa      offo    dattyp     lcint
         1         0       1.0       1.0       0.0       0.0         0         0
$#                a1                  o1
                 0.0                 0.0
                 1.0               100.0
*NODE
$#   nid               x               y               z      tc      rc
       1       -19.76956        76.57547        2.333668       0       0
       2       -18.76956        76.57547        2.333668       0       0
       3       -18.76956        77.57547        2.333668       0       0
       4       -19.76956        77.57547        2.333668       0       0
       5       -19.76956        76.57547        3.333668       0       0
       6       -18.76956        76.57547        3.333668       0       0
       7       -18.76956        77.57547        3.333668       0       0
       8       -19.76956        77.57547        3.333668       0       0
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1
       1       2       3       4       5       6       7       8       0       0
*PART_TITLE
Flex-Part-Plastic
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         1         1         1         0         0         0         0         0
*PART_TITLE
Rigid-Part
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         2         1         2         0         0         0         0         0
*SECTION_SOLID_TITLE
Section 1
$#   secid    elform       aet
         1         1         0
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Plastic Material
$#     mid        ro         e        pr      sigy      etan      fail      tdel
         1   7.85E-9   2.10E+5      0.30     250.0      1000       0.0       0.0
$#       c         p      lcss      lcsr        vp       lcf
       0.0       0.0         0         0       0.0         0
$#    eps1      eps2      eps3      eps4      eps5      eps6      eps7      eps8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$#     es1       es2       es3       es4       es5       es6       es7       es8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
*MAT_RIGID_TITLE
Rigid Material
$#     mid        ro         e        pr         n    couple         m     alias
         2   7.85E-9   2.10E+5      0.30       0.0       0.0       0.0
$#     cmo      con1      con2
       1.0         7         7
$#lco or a1        a2        a3        v1        v2        v3
       0.0       0.0       0.0       0.0       0.0       0.0
*BOUNDARY_SPC_SET
$#    nsid       cid      dofx      dofy      dofz     dofrx     dofry     dofrz
         1         0         1         1         1         1         1         1
*END
