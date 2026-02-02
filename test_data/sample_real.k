*KEYWORD
*TITLE
Sample Real K-File Test
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
Flex-Dummy
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         1         1         1         0         0         0         0         0
*SECTION_SOLID_TITLE
Section 1
$#   secid    elform       aet
         1         1         0
*MAT_ELASTIC_TITLE
Material 1
$#     mid        ro         e        pr        da        db  not used
         1   7.85E-9   2.10E+5      0.30
*END
