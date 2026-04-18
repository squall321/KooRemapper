$ ========================================================================
$ CERAMIC — Structural Ceramics: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Structural Ceramics
$
$ 2 mechanical variants per material:
$   1. MAT_001 Linear Elastic       1010xx — preview
$   2. MAT_001 + MAT_ADD_EROSION    1110xx — brittle failure ★
$
$ Erosion: principal stress > sigma_flex (flexural strength)
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds
$ !!  the MATERIAL ID (MID), NOT an actual Part ID.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin     erode   tmid    Name                     E(GPa)  sigma(MPa)  K1C   rho
$   -----------------------------------------------------------------------------------
$   101021  111021  131021  Al2O3_96pct               300.0       300   3.50  3.72
$   101022  111022  131022  Al2O3_99p5pct             370.0       400   4.00  3.89
$   101023  111023  131023  AlN_HighK                 320.0       320   3.00  3.26
$   101024  111024  131024  ZrO2_YTZP                 210.0      1200   10.00  6.05
$   101025  111025  131025  Si3N4                     310.0       800   7.00  3.20
$   101026  111026  131026  SiC                       410.0       390   3.50  3.10
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- Al2O3_96pct Linear (MID 101021) ---
$$ Alumina 96% purity, standard substrate (HTCC), housings
$$ Source: CoorsTek AD-96, Kyocera A-476
$$ E=300.0 GPa, nu=0.21, rho=3.72 g/cc, sigma_flex=300.0 MPa
*MAT_ELASTIC_TITLE
Al2O3_96pct Linear
$      MID        RO         E        PR        DA        DB
    101021 3.720e-09  300000.0    0.2100       0.0       0.0
$
$$ --- Al2O3_99p5pct Linear (MID 101022) ---
$$ Alumina 99.5% high-purity, high-performance substrate
$$ Source: CoorsTek AD-995, Kyocera A-479
$$ E=370.0 GPa, nu=0.22, rho=3.89 g/cc, sigma_flex=400.0 MPa
*MAT_ELASTIC_TITLE
Al2O3_99p5pct Linear
$      MID        RO         E        PR        DA        DB
    101022 3.890e-09  370000.0    0.2200       0.0       0.0
$
$$ --- AlN_HighK Linear (MID 101023) ---
$$ Aluminum Nitride, high thermal conductivity (IGBT, LED)
$$ Source: CoorsTek AlN-170, Kyocera Shapal-M (AlN)
$$ E=320.0 GPa, nu=0.23, rho=3.26 g/cc, sigma_flex=320.0 MPa
*MAT_ELASTIC_TITLE
AlN_HighK Linear
$      MID        RO         E        PR        DA        DB
    101023 3.260e-09  320000.0    0.2300       0.0       0.0
$
$$ --- ZrO2_YTZP Linear (MID 101024) ---
$$ Yttria-stabilized Zirconia (Y-TZP), premium back cover, dental
$$ Source: CoorsTek YZP, Kyocera Z-001, Tosoh TZ-3Y
$$ E=210.0 GPa, nu=0.31, rho=6.05 g/cc, sigma_flex=1200.0 MPa
*MAT_ELASTIC_TITLE
ZrO2_YTZP Linear
$      MID        RO         E        PR        DA        DB
    101024 6.050e-09  210000.0    0.3100       0.0       0.0
$
$$ --- Si3N4 Linear (MID 101025) ---
$$ Silicon Nitride, high reliability bearings, IC substrates
$$ Source: CoorsTek SN, Kyocera SN-240, Ceradyne Silicon Nitride
$$ E=310.0 GPa, nu=0.27, rho=3.2 g/cc, sigma_flex=800.0 MPa
*MAT_ELASTIC_TITLE
Si3N4 Linear
$      MID        RO         E        PR        DA        DB
    101025 3.200e-09  310000.0    0.2700       0.0       0.0
$
$$ --- SiC Linear (MID 101026) ---
$$ Silicon Carbide, high performance semiconductor substrate
$$ Source: CoorsTek SC-30, Saint-Gobain Hexoloy SA
$$ E=410.0 GPa, nu=0.14, rho=3.1 g/cc, sigma_flex=390.0 MPa
*MAT_ELASTIC_TITLE
SiC Linear
$      MID        RO         E        PR        DA        DB
    101026 3.100e-09  410000.0    0.1400       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- Al2O3_96pct Elastic+Erosion (MID 111021) ---
$$ Erosion: principal stress > 300.0 MPa
$$ K1C=3.5 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
Al2O3_96pct Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111021 3.720e-09  300000.0    0.2100       0.0       0.0
$
$$ [DB] PID slot holds MID=111021 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111021       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    300.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Al2O3_99p5pct Elastic+Erosion (MID 111022) ---
$$ Erosion: principal stress > 400.0 MPa
$$ K1C=4.0 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
Al2O3_99p5pct Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111022 3.890e-09  370000.0    0.2200       0.0       0.0
$
$$ [DB] PID slot holds MID=111022 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111022       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    400.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- AlN_HighK Elastic+Erosion (MID 111023) ---
$$ Erosion: principal stress > 320.0 MPa
$$ K1C=3.0 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
AlN_HighK Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111023 3.260e-09  320000.0    0.2300       0.0       0.0
$
$$ [DB] PID slot holds MID=111023 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111023       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    320.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- ZrO2_YTZP Elastic+Erosion (MID 111024) ---
$$ Erosion: principal stress > 1200.0 MPa
$$ K1C=10.0 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
ZrO2_YTZP Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111024 6.050e-09  210000.0    0.3100       0.0       0.0
$
$$ [DB] PID slot holds MID=111024 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111024       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0   1200.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Si3N4 Elastic+Erosion (MID 111025) ---
$$ Erosion: principal stress > 800.0 MPa
$$ K1C=7.0 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
Si3N4 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111025 3.200e-09  310000.0    0.2700       0.0       0.0
$
$$ [DB] PID slot holds MID=111025 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111025       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    800.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- SiC Elastic+Erosion (MID 111026) ---
$$ Erosion: principal stress > 390.0 MPa
$$ K1C=3.5 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
SiC Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111026 3.100e-09  410000.0    0.1400       0.0       0.0
$
$$ [DB] PID slot holds MID=111026 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111026       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    390.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
