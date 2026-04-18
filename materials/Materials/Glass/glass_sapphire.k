$ ========================================================================
$ GLASS SAPPHIRE — Mechanical (MAT_001 + MAT_ADD_EROSION)
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
$   101011  111011  131011  Sapphire_Cplane               345.0  3.97        700  2.20
$   101012  111012  131012  Sapphire_Aplane               370.0  3.97        800  2.20
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- Sapphire_Cplane Linear Elastic (MID 101011) ---
$$ Sapphire single crystal C-plane (0001), camera window, watch face
$$ Source: Goodfellow Al2O3 99.9% (AZoM 1721), Kyocera sapphire TDS
$$ E=345.0 GPa, nu=0.29, rho=3.97 g/cc
$$ K1C=2.2 MPa*sqrt(m), sigma_strength=700.0 MPa
*MAT_ELASTIC_TITLE
Sapphire_Cplane Linear
$      MID        RO         E        PR        DA        DB
    101011 3.970e-09  345000.0    0.2900       0.0       0.0
$
$$ --- Sapphire_Aplane Linear Elastic (MID 101012) ---
$$ Sapphire single crystal A-plane (1120), higher strength window
$$ Source: Goodfellow Al2O3, Kyocera
$$ E=370.0 GPa, nu=0.27, rho=3.97 g/cc
$$ K1C=2.2 MPa*sqrt(m), sigma_strength=800.0 MPa
*MAT_ELASTIC_TITLE
Sapphire_Aplane Linear
$      MID        RO         E        PR        DA        DB
    101012 3.970e-09  370000.0    0.2700       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- Sapphire_Cplane Elastic+Erosion (MID 111011) ---
$$ Sapphire single crystal C-plane (0001), camera window, watch face
$$ Principal stress erosion: sigma_p_max > 700.0 MPa -> delete
*MAT_ELASTIC_TITLE
Sapphire_Cplane Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111011 3.970e-09  345000.0    0.2900       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111011 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111011       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    700.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Sapphire_Aplane Elastic+Erosion (MID 111012) ---
$$ Sapphire single crystal A-plane (1120), higher strength window
$$ Principal stress erosion: sigma_p_max > 800.0 MPa -> delete
*MAT_ELASTIC_TITLE
Sapphire_Aplane Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111012 3.970e-09  370000.0    0.2700       0.0       0.0
$
$ Erosion: principal stress + minimum timestep criteria
$$ [DB] PID slot holds MID=111012 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111012       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    800.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
