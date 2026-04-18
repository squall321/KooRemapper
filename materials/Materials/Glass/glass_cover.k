$ ========================================================================
$ GLASS COVER GLASS — Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$
$ 2 mechanical variants per material:
$   1. MAT_001 Linear Elastic       1010xx — preview
$   2. MAT_001 + MAT_ADD_EROSION    1110xx — drop analysis ★
$
$ Erosion criterion: principal stress > sigma_strength
$   sigma_strength = chemically strengthened CS (Gorilla: 680~900 MPa)
$
$ Thermal properties in glass_thermal.k
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds
$ !!  the MATERIAL ID (MID), NOT an actual Part ID.
$ !!  External tool must replace with real PIDs before running LS-DYNA.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin     erode   tmid    Name                         E(GPa) rho    sigma(MPa) K1C
$   ----------------------------------------------------------------------------------------
$   101001  111001  131001  SodaLime_Standard              72.0  2.50         45  0.75
$   101002  111002  131002  Aluminosilicate_Dragontrail    74.0  2.48        500  0.75
$   101003  111003  131003  GorillaGlass_3                 71.5  2.45        680  0.70
$   101004  111004  131004  GorillaGlass_5                 77.0  2.43        850  0.69
$   101005  111005  131005  GorillaGlass_6                 77.0  2.40        850  0.70
$   101006  111006  131006  GorillaGlass_Victus            78.0  2.44        900  0.72
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- SodaLime_Standard Linear Elastic (MID 101001) ---
$$ Soda-lime glass (standard window/mirror)
$$ Source: MatWeb soda-lime, ASM Vol 4
$$ E=72.0 GPa, nu=0.22, rho=2.5 g/cc
$$ K1C=0.75 MPa*sqrt(m), sigma_strength=45.0 MPa
*MAT_ELASTIC_TITLE
SodaLime_Standard Linear
$      MID        RO         E        PR        DA        DB
    101001 2.500e-09   72000.0    0.2200       0.0       0.0
$
$$ --- Aluminosilicate_Dragontrail Linear Elastic (MID 101002) ---
$$ AGC Dragontrail aluminosilicate (chemically strengthened)
$$ Source: AGC Dragontrail TDS
$$ E=74.0 GPa, nu=0.22, rho=2.48 g/cc
$$ K1C=0.75 MPa*sqrt(m), sigma_strength=500.0 MPa
*MAT_ELASTIC_TITLE
Aluminosilicate_Dragontrail Linear
$      MID        RO         E        PR        DA        DB
    101002 2.480e-09   74000.0    0.2200       0.0       0.0
$
$$ --- GorillaGlass_3 Linear Elastic (MID 101003) ---
$$ Corning Gorilla Glass 3 (2013), NDR (Native Damage Resistance)
$$ Source: Corning Gorilla Glass 3 PI Sheet
$$ E=71.5 GPa, nu=0.22, rho=2.45 g/cc
$$ K1C=0.7 MPa*sqrt(m), sigma_strength=680.0 MPa
*MAT_ELASTIC_TITLE
GorillaGlass_3 Linear
$      MID        RO         E        PR        DA        DB
    101003 2.450e-09   71500.0    0.2200       0.0       0.0
$
$$ --- GorillaGlass_5 Linear Elastic (MID 101004) ---
$$ Corning Gorilla Glass 5 (2016), drop performance
$$ Source: Corning Gorilla Glass 5 PI Sheet: E=77 GPa, nu=0.21, rho=2.43, K1C=0.69
$$ E=77.0 GPa, nu=0.21, rho=2.43 g/cc
$$ K1C=0.69 MPa*sqrt(m), sigma_strength=850.0 MPa
*MAT_ELASTIC_TITLE
GorillaGlass_5 Linear
$      MID        RO         E        PR        DA        DB
    101004 2.430e-09   77000.0    0.2100       0.0       0.0
$
$$ --- GorillaGlass_6 Linear Elastic (MID 101005) ---
$$ Corning Gorilla Glass 6 (2018), improved repeated drop
$$ Source: Corning Gorilla Glass 6 PI Sheet: E=77 GPa, nu=0.21, rho=2.40, K1C=0.70
$$ E=77.0 GPa, nu=0.21, rho=2.4 g/cc
$$ K1C=0.7 MPa*sqrt(m), sigma_strength=850.0 MPa
*MAT_ELASTIC_TITLE
GorillaGlass_6 Linear
$      MID        RO         E        PR        DA        DB
    101005 2.400e-09   77000.0    0.2100       0.0       0.0
$
$$ --- GorillaGlass_Victus Linear Elastic (MID 101006) ---
$$ Corning Gorilla Glass Victus (2020), flagship drop + scratch
$$ Source: Corning Gorilla Glass Victus PI Sheet
$$ E=78.0 GPa, nu=0.21, rho=2.44 g/cc
$$ K1C=0.72 MPa*sqrt(m), sigma_strength=900.0 MPa
*MAT_ELASTIC_TITLE
GorillaGlass_Victus Linear
$      MID        RO         E        PR        DA        DB
    101006 2.440e-09   78000.0    0.2100       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- SodaLime_Standard Elastic+Erosion (MID 111001) ---
$$ Soda-lime glass (standard window/mirror)
$$ Principal stress erosion: sigma_p_max > 45.0 MPa -> delete
*MAT_ELASTIC_TITLE
SodaLime_Standard Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111001 2.500e-09   72000.0    0.2200       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111001 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111001       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0     45.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Aluminosilicate_Dragontrail Elastic+Erosion (MID 111002) ---
$$ AGC Dragontrail aluminosilicate (chemically strengthened)
$$ Principal stress erosion: sigma_p_max > 500.0 MPa -> delete
*MAT_ELASTIC_TITLE
Aluminosilicate_Dragontrail Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111002 2.480e-09   74000.0    0.2200       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111002 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111002       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    500.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- GorillaGlass_3 Elastic+Erosion (MID 111003) ---
$$ Corning Gorilla Glass 3 (2013), NDR (Native Damage Resistance)
$$ Principal stress erosion: sigma_p_max > 680.0 MPa -> delete
*MAT_ELASTIC_TITLE
GorillaGlass_3 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111003 2.450e-09   71500.0    0.2200       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111003 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111003       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    680.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- GorillaGlass_5 Elastic+Erosion (MID 111004) ---
$$ Corning Gorilla Glass 5 (2016), drop performance
$$ Principal stress erosion: sigma_p_max > 850.0 MPa -> delete
*MAT_ELASTIC_TITLE
GorillaGlass_5 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111004 2.430e-09   77000.0    0.2100       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111004 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111004       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    850.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- GorillaGlass_6 Elastic+Erosion (MID 111005) ---
$$ Corning Gorilla Glass 6 (2018), improved repeated drop
$$ Principal stress erosion: sigma_p_max > 850.0 MPa -> delete
*MAT_ELASTIC_TITLE
GorillaGlass_6 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111005 2.400e-09   77000.0    0.2100       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111005 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111005       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    850.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- GorillaGlass_Victus Elastic+Erosion (MID 111006) ---
$$ Corning Gorilla Glass Victus (2020), flagship drop + scratch
$$ Principal stress erosion: sigma_p_max > 900.0 MPa -> delete
*MAT_ELASTIC_TITLE
GorillaGlass_Victus Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111006 2.440e-09   78000.0    0.2100       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111006 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111006       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    900.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
