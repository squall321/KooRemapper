$ ========================================================================
$ CERAMIC — Liquid Crystal Polymer: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Liquid Crystal Polymer
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
$   101041  111041  131041  LCP_Vectra_A950            10.6       145   5.00  1.40
$   101042  111042  131042  LCP_Vectra_E130i           14.0       185   5.50  1.62
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- LCP_Vectra_A950 Linear (MID 101041) ---
$$ LCP Vectra A950, 5G mm-wave antenna substrate, low Df
$$ Source: Celanese Ticona Vectra A950 TDS
$$ E=10.6 GPa, nu=0.38, rho=1.4 g/cc, sigma_flex=145.0 MPa
*MAT_ELASTIC_TITLE
LCP_Vectra_A950 Linear
$      MID        RO         E        PR        DA        DB
    101041 1.400e-09   10600.0    0.3800       0.0       0.0
$
$$ --- LCP_Vectra_E130i Linear (MID 101042) ---
$$ LCP Vectra E130i reinforced, connectors, high mech
$$ Source: Celanese Ticona Vectra E130i TDS
$$ E=14.0 GPa, nu=0.35, rho=1.62 g/cc, sigma_flex=185.0 MPa
*MAT_ELASTIC_TITLE
LCP_Vectra_E130i Linear
$      MID        RO         E        PR        DA        DB
    101042 1.620e-09   14000.0    0.3500       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- LCP_Vectra_A950 Elastic+Erosion (MID 111041) ---
$$ Erosion: principal stress > 145.0 MPa
$$ K1C=5.0 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
LCP_Vectra_A950 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111041 1.400e-09   10600.0    0.3800       0.0       0.0
$
$$ [DB] PID slot holds MID=111041 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111041       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    145.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- LCP_Vectra_E130i Elastic+Erosion (MID 111042) ---
$$ Erosion: principal stress > 185.0 MPa
$$ K1C=5.5 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
LCP_Vectra_E130i Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111042 1.620e-09   14000.0    0.3500       0.0       0.0
$
$$ [DB] PID slot holds MID=111042 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111042       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    185.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
