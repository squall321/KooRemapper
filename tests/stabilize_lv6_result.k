*KEYWORD
*TITLE
Optimize Test Model
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST
       0.0  0.800000         0       0.0-5.000E-07         0         0         0
*CONTROL_ACCURACY
$      OSU       INN    PIDOSU
         1         4
*CONTROL_BULK_VISCOSITY
$       Q1        Q2      TYPE     BTYPE
    2.0000    0.1000         1         0
*MAT_ELASTIC_TITLE
Steel
$      MID       RHO         E        PR         N
         1  7.85E-09  2.10E+05     0.300
*MAT_ELASTIC_TITLE
Rubber_placeholder
$      MID       RHO         E        PR         N
         2  1.10E-09  5.000000     0.495
*SECTION_SOLID
$    SECID    ELFORM       AET
         1         1         0
*SECTION_SOLID
         2        13         0
*PART
Steel_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         0         0         0         0
*PART
Rubber_Part
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         2         2         0         0         0         0         0
*NODE
       1            0.000000            0.000000            0.000000
       2            1.000000            0.000000            0.000000
       3            1.000000            1.000000            0.000000
       4            0.000000            1.000000            0.000000
       5            0.000000            0.000000            1.000000
       6            1.000000            0.000000            1.000000
       7            1.000000            1.000000            1.000000
       8            0.000000            1.000000            1.000000
       9            2.000000            0.000000            0.000000
      10            2.000000            1.000000            0.000000
      11            2.000000            0.000000            1.000000
      12            2.000000            1.000000            1.000000
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       2       9      10       3       6      11      12       7
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE
Steel_Rubber
$     SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         1         2         3         3         0         0         0         0
$       FS        FD        DC        VC       VDC    PENCHK        BT        DT
    0.3000    0.2000       0.0       0.0       0.0         0       0.01.0000E+20
$      SFS       SFM       SST       MST      SFST      SFMT       FSF       VSF
    1.0000    1.0000       0.0       0.0    1.0000    1.0000    1.0000    1.0000
$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq
         1      0.10         0    1.0250         2         3         0         1
*CONTROL_ENERGY
$     HGEN      RWEN    SLNTEN     RYLEN
         2         2         2         2
*CONTROL_SOLID
$    ESORT    FMATRX    NIPTETS     SWLOCL     PSFAIL       T10      ICOH     TET13
         1
*CONTROL_HOURGLASS
$      IHQ        QH
         4    0.1000
*CONTROL_CONTACT
$    SLSFAC    RWPNAL    ISLCHK    SHLTHK    PENOPT    THKCHG     ORIEN    ENMASS
                             2         1                             2          
$    USRSTR    USRFRC     NSBCS    INTERM     XPENE     SSTHK      ECDT   TIEDPRJ
                                            2.0000                              
*END
