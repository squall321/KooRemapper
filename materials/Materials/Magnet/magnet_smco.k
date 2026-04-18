$ ========================================================================
$ MAGNET — SmCo: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: SmCo
$
$ 2 variants per material:
$   1. MAT_001 Linear           1010xx — preview
$   2. MAT_001 + MAT_ADD_EROSION 1110xx — brittle crack ★
$
$ NOTE: Mechanical properties ONLY.
$       For EM/magnetic force simulation, use *EM_MAT_PERMANENT_MAGNET.
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds
$ !!  the MATERIAL ID (MID), NOT an actual Part ID.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin     erode   tmid    Name                 E(GPa) rho   sigma  BHmax  Tmax
$   -------------------------------------------------------------------------------------
$   101064  111064  131064  SmCo_2_17            150.0  8.40    150   30.0  350
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- SmCo_2_17 Linear (MID 101064) ---
$$ SmCo 2:17 sintered, high-temperature, corrosion resistant
$$ Source: Arnold Recoma 26, Vacuumschmelze Vacomax 225 HR
$$ E=150.0 GPa, rho=8.4 g/cc, BHmax=30 MGOe
$$ Max operating temperature: 350 C
*MAT_ELASTIC_TITLE
SmCo_2_17 Linear
$      MID        RO         E        PR        DA        DB
    101064 8.400e-09  150000.0    0.2400       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION
$ ========================================================================
$
$$ --- SmCo_2_17 Elastic+Erosion (MID 111064) ---
$$ Brittle failure: principal stress > 150.0 MPa
*MAT_ELASTIC_TITLE
SmCo_2_17 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111064 8.400e-09  150000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=111064
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111064       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    150.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
