$ ========================================================================
$ BRASS METAL MATERIAL LIBRARY — Mechanical (MAT_024 + MAT_003)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: BRASS — Brass & Bronze (connectors, springs)
$ MID: 100601~100610 (bi), 110601~110610 (multi)
$ Model: *MAT_PIECEWISE_LINEAR_PLASTICITY (MAT_024)
$
$ Hybrid strategy:
$   Bilinear    MID 1005xx (fast, SIGY+ETAN)
$   Multilinear MID 1105xx (precise, LCSS=MID)
$
$ Cowper-Symonds strain-rate (Jones, Structural Impact):
$   Aluminum: C=6500  P=4
$   Stainless:C=100   P=10
$   Titanium: C=120   P=9
$
$ Thermal properties (TC, Cp, CTE) in metal_thermal.k
$ ========================================================================
$
$ 4 hardening variants per material:
$   1. Bilinear isotropic  (MAT_024, SIGY+ETAN)            1005xx
$   2. Multilinear isotropic (MAT_024 + LCSS curve)         1105xx
$   3. Bilinear kinematic pure  (MAT_003, BETA=0.0)         1305xx
$   4. Bilinear kinematic mixed (MAT_003, BETA=0.5)         1405xx
$
$ Use isotropic for monotonic drop impact,
$ kinematic/mixed for cyclic or reverse loading (Bauschinger effect).
$
$ SUMMARY TABLE
$
$   bi_iso  multi_iso  kin_pure  kin_mix   Name                    sigy   sigu
$   --------------------------------------------------------------------------------
$   100601  110601     130601    140601   C26000_Cartridge_Brass    310    425
$   100602  110602     130602    140602   C36000_FreeCutting_Brass    310    400
$   100603  110603     130603    140603   C51000_Phosphor_Bronze    590    655
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. BILINEAR ISOTROPIC (MAT_024 with SIGY + ETAN)
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass Bilinear (MID 100601) ---
$$ 70/30 Cu-Zn cartridge brass (connector shells)
$$ Temper: 1/2 Hard
$$ Source: ASTM B36 / UNS C26000, Copper Development Assoc
$$ rho=8.53 g/cc, E=110.0 GPa, nu=0.375
$$ sigy=310.0 MPa, sigu=425.0 MPa, eps_f=0.23
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 506.2 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C26000_Cartridge_Brass Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100601 8.530e-09  110000.0    0.3750    310.00    506.20    0.2300      0.00
$        C         P      LCSS      LCSR        VP
    1400.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- C36000_FreeCutting_Brass Bilinear (MID 100602) ---
$$ Free-cutting leaded brass (precision machined parts)
$$ Temper: Half hard
$$ Source: ASTM B16 / UNS C36000
$$ rho=8.5 g/cc, E=97.0 GPa, nu=0.31
$$ sigy=310.0 MPa, sigu=400.0 MPa, eps_f=0.18
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 509.0 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C36000_FreeCutting_Brass Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100602 8.500e-09   97000.0    0.3100    310.00    509.04    0.1800      0.00
$        C         P      LCSS      LCSR        VP
    1400.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- C51000_Phosphor_Bronze Bilinear (MID 100603) ---
$$ 5% Sn phosphor bronze spring material (contacts, bearings)
$$ Temper: Spring temper
$$ Source: ASTM B103 / UNS C51000
$$ rho=8.86 g/cc, E=110.0 GPa, nu=0.34
$$ sigy=590.0 MPa, sigu=655.0 MPa, eps_f=0.08
$$ ETAN = (sigu-sigy)/(eps_f-eps_y) = 870.9 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C51000_Phosphor_Bronze Bilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100603 8.860e-09  110000.0    0.3400    590.00    870.89    0.0800      0.00
$        C         P      LCSS      LCSR        VP
    1800.0       5.0         0         0       1.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$ ========================================================================
$ 2. MULTI-LINEAR ISOTROPIC (MAT_024 with LCSS curve)
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass Multilinear (MID 110601) ---
$$ 70/30 Cu-Zn cartridge brass (connector shells)
$$ Temper: 1/2 Hard
$$ Source: ASTM B36 / UNS C26000, Copper Development Assoc
$$ LCSS curve: 7 points, LCID=110601
*DEFINE_CURVE_TITLE
C26000_Cartridge_Brass true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110601         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.1000000000e+02
    1.0000000000e-02    3.4500000000e+02
    2.0000000000e-02    3.7000000000e+02
    5.0000000000e-02    3.9500000000e+02
    1.0000000000e-01    4.1000000000e+02
    1.5000000000e-01    4.2000000000e+02
    2.3000000000e-01    4.2500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C26000_Cartridge_Brass Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110601 8.530e-09  110000.0    0.3750      0.00      0.00    0.2300      0.00
$        C         P      LCSS      LCSR        VP
    1400.0       5.0    110601         0       1.0
$
$$ --- C36000_FreeCutting_Brass Multilinear (MID 110602) ---
$$ Free-cutting leaded brass (precision machined parts)
$$ Temper: Half hard
$$ Source: ASTM B16 / UNS C36000
$$ LCSS curve: 6 points, LCID=110602
*DEFINE_CURVE_TITLE
C36000_FreeCutting_Brass true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110602         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    3.1000000000e+02
    1.0000000000e-02    3.4000000000e+02
    2.0000000000e-02    3.6000000000e+02
    5.0000000000e-02    3.8000000000e+02
    1.0000000000e-01    3.9200000000e+02
    1.8000000000e-01    4.0000000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C36000_FreeCutting_Brass Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110602 8.500e-09   97000.0    0.3100      0.00      0.00    0.1800      0.00
$        C         P      LCSS      LCSR        VP
    1400.0       5.0    110602         0       1.0
$
$$ --- C51000_Phosphor_Bronze Multilinear (MID 110603) ---
$$ 5% Sn phosphor bronze spring material (contacts, bearings)
$$ Temper: Spring temper
$$ Source: ASTM B103 / UNS C51000
$$ LCSS curve: 6 points, LCID=110603
*DEFINE_CURVE_TITLE
C51000_Phosphor_Bronze true stress vs plastic strain
$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP
    110603         0       1.0       1.0       0.0       0.0         0
    0.0000000000e+00    5.9000000000e+02
    5.0000000000e-03    6.1500000000e+02
    1.0000000000e-02    6.3000000000e+02
    2.0000000000e-02    6.4200000000e+02
    5.0000000000e-02    6.5000000000e+02
    8.0000000000e-02    6.5500000000e+02
$
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
C51000_Phosphor_Bronze Multilinear
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    110603 8.860e-09  110000.0    0.3400      0.00      0.00    0.0800      0.00
$        C         P      LCSS      LCSR        VP
    1800.0       5.0    110603         0       1.0
$
$ ========================================================================
$ 3. BILINEAR KINEMATIC PURE (MAT_003, BETA=0)
$    For Bauschinger effect / reverse cyclic loading
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass Kinematic Pure (MID 130601) ---
$$ 70/30 Cu-Zn cartridge brass (connector shells)
$$ Temper: 1/2 Hard
$$ Source: ASTM B36 / UNS C26000, Copper Development Assoc
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=310.0 MPa, ETAN=506.2 MPa, eps_f=0.23
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C26000_Cartridge_Brass Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130601 8.530e-09  110000.0    0.3750    310.00    506.20    0.0000
$      SRC       SRP        FS        VP
    1400.0       5.0    0.2300       1.0
$
$$ --- C36000_FreeCutting_Brass Kinematic Pure (MID 130602) ---
$$ Free-cutting leaded brass (precision machined parts)
$$ Temper: Half hard
$$ Source: ASTM B16 / UNS C36000
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=310.0 MPa, ETAN=509.0 MPa, eps_f=0.18
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C36000_FreeCutting_Brass Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130602 8.500e-09   97000.0    0.3100    310.00    509.04    0.0000
$      SRC       SRP        FS        VP
    1400.0       5.0    0.1800       1.0
$
$$ --- C51000_Phosphor_Bronze Kinematic Pure (MID 130603) ---
$$ 5% Sn phosphor bronze spring material (contacts, bearings)
$$ Temper: Spring temper
$$ Source: ASTM B103 / UNS C51000
$$ Hardening: BETA=0.0  (0=pure kinematic, 1=isotropic)
$$ sigy=590.0 MPa, ETAN=870.9 MPa, eps_f=0.08
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C51000_Phosphor_Bronze Kinematic Pure
$      MID        RO         E        PR      SIGY      ETAN      BETA
    130603 8.860e-09  110000.0    0.3400    590.00    870.89    0.0000
$      SRC       SRP        FS        VP
    1800.0       5.0    0.0800       1.0
$
$ ========================================================================
$ 4. BILINEAR KINEMATIC MIXED (MAT_003, BETA=0.5)
$    50/50 isotropic-kinematic, realistic for metals
$ ========================================================================
$
$$ --- C26000_Cartridge_Brass Kinematic Mixed (MID 140601) ---
$$ 70/30 Cu-Zn cartridge brass (connector shells)
$$ Temper: 1/2 Hard
$$ Source: ASTM B36 / UNS C26000, Copper Development Assoc
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=310.0 MPa, ETAN=506.2 MPa, eps_f=0.23
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C26000_Cartridge_Brass Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140601 8.530e-09  110000.0    0.3750    310.00    506.20    0.5000
$      SRC       SRP        FS        VP
    1400.0       5.0    0.2300       1.0
$
$$ --- C36000_FreeCutting_Brass Kinematic Mixed (MID 140602) ---
$$ Free-cutting leaded brass (precision machined parts)
$$ Temper: Half hard
$$ Source: ASTM B16 / UNS C36000
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=310.0 MPa, ETAN=509.0 MPa, eps_f=0.18
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C36000_FreeCutting_Brass Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140602 8.500e-09   97000.0    0.3100    310.00    509.04    0.5000
$      SRC       SRP        FS        VP
    1400.0       5.0    0.1800       1.0
$
$$ --- C51000_Phosphor_Bronze Kinematic Mixed (MID 140603) ---
$$ 5% Sn phosphor bronze spring material (contacts, bearings)
$$ Temper: Spring temper
$$ Source: ASTM B103 / UNS C51000
$$ Hardening: BETA=0.5  (0=pure kinematic, 1=isotropic)
$$ sigy=590.0 MPa, ETAN=870.9 MPa, eps_f=0.08
$$ Note: MAT_003 uses Cowper-Symonds as SRC(=C) and SRP(=P)
*MAT_PLASTIC_KINEMATIC_TITLE
C51000_Phosphor_Bronze Kinematic Mixed
$      MID        RO         E        PR      SIGY      ETAN      BETA
    140603 8.860e-09  110000.0    0.3400    590.00    870.89    0.5000
$      SRC       SRP        FS        VP
    1800.0       5.0    0.0800       1.0
$
*END
