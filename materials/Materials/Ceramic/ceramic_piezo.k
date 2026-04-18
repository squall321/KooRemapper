$ ========================================================================
$ CERAMIC — Piezoelectric Ceramics: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Piezoelectric Ceramics
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
$   101031  111031  131031  PZT_5A_soft                61.0        80   1.50  7.75
$   101032  111032  131032  PZT_4_hard                 64.0       100   1.50  7.50
$   101033  111033  131033  AlN_piezo_thinfilm        330.0       320   2.80  3.26
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- PZT_5A_soft Linear (MID 101031) ---
$$ PZT-5A soft piezo, sensor, hydrophone, guitar pickup
$$ Source: APC 850, Morgan PZT-5A, CTS 3203HD
$$ E=61.0 GPa, nu=0.31, rho=7.75 g/cc, sigma_flex=80.0 MPa
$$ Piezoelectric d33 = 374 pC/N (not used in pure mechanical analysis)
*MAT_ELASTIC_TITLE
PZT_5A_soft Linear
$      MID        RO         E        PR        DA        DB
    101031 7.750e-09   61000.0    0.3100       0.0       0.0
$
$$ --- PZT_4_hard Linear (MID 101032) ---
$$ PZT-4 hard piezo, actuator, LRA motor, ultrasonic
$$ Source: APC 840, Morgan PZT-4, CTS 3195HD
$$ E=64.0 GPa, nu=0.31, rho=7.5 g/cc, sigma_flex=100.0 MPa
$$ Piezoelectric d33 = 289 pC/N (not used in pure mechanical analysis)
*MAT_ELASTIC_TITLE
PZT_4_hard Linear
$      MID        RO         E        PR        DA        DB
    101032 7.500e-09   64000.0    0.3100       0.0       0.0
$
$$ --- AlN_piezo_thinfilm Linear (MID 101033) ---
$$ AlN thin-film piezoelectric, MEMS, BAW filter
$$ Source: OEM thin-film AlN piezoelectric properties
$$ E=330.0 GPa, nu=0.24, rho=3.26 g/cc, sigma_flex=320.0 MPa
$$ Piezoelectric d33 = 5 pC/N (not used in pure mechanical analysis)
*MAT_ELASTIC_TITLE
AlN_piezo_thinfilm Linear
$      MID        RO         E        PR        DA        DB
    101033 3.260e-09  330000.0    0.2400       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- PZT_5A_soft Elastic+Erosion (MID 111031) ---
$$ Erosion: principal stress > 80.0 MPa
$$ K1C=1.5 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
PZT_5A_soft Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111031 7.750e-09   61000.0    0.3100       0.0       0.0
$
$$ [DB] PID slot holds MID=111031 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111031       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0     80.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- PZT_4_hard Elastic+Erosion (MID 111032) ---
$$ Erosion: principal stress > 100.0 MPa
$$ K1C=1.5 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
PZT_4_hard Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111032 7.500e-09   64000.0    0.3100       0.0       0.0
$
$$ [DB] PID slot holds MID=111032 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111032       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    100.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- AlN_piezo_thinfilm Elastic+Erosion (MID 111033) ---
$$ Erosion: principal stress > 320.0 MPa
$$ K1C=2.8 MPa*sqrt(m)
*MAT_ELASTIC_TITLE
AlN_piezo_thinfilm Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111033 3.260e-09  330000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=111033 (replace with actual PART IDs)
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111033       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    320.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
