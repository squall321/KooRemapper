$ ========================================================================
$ MAGNET — NdFeB: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: NdFeB
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
$   101061  111061  131061  NdFeB_N35            150.0  7.40    270   35.0   80
$   101062  111062  131062  NdFeB_N42            160.0  7.50    280   42.0   80
$   101063  111063  131063  NdFeB_N52            170.0  7.60    290   52.0   65
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- NdFeB_N35 Linear (MID 101061) ---
$$ NdFeB N35 sintered magnet, economy grade
$$ Source: Arnold Magnetic N35, Vacuumschmelze Vacodym 633 HR
$$ E=150.0 GPa, rho=7.4 g/cc, BHmax=35 MGOe
$$ Max operating temperature: 80 C
*MAT_ELASTIC_TITLE
NdFeB_N35 Linear
$      MID        RO         E        PR        DA        DB
    101061 7.400e-09  150000.0    0.2400       0.0       0.0
$
$$ --- NdFeB_N42 Linear (MID 101062) ---
$$ NdFeB N42, standard speaker/wireless charging
$$ Source: Arnold N42, Hitachi Metals NEOMAX-42
$$ E=160.0 GPa, rho=7.5 g/cc, BHmax=42 MGOe
$$ Max operating temperature: 80 C
*MAT_ELASTIC_TITLE
NdFeB_N42 Linear
$      MID        RO         E        PR        DA        DB
    101062 7.500e-09  160000.0    0.2400       0.0       0.0
$
$$ --- NdFeB_N52 Linear (MID 101063) ---
$$ NdFeB N52 highest energy, premium (camera OIS, premium speaker)
$$ Source: Shin-Etsu N52, Arnold N52
$$ E=170.0 GPa, rho=7.6 g/cc, BHmax=52 MGOe
$$ Max operating temperature: 65 C
*MAT_ELASTIC_TITLE
NdFeB_N52 Linear
$      MID        RO         E        PR        DA        DB
    101063 7.600e-09  170000.0    0.2400       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION
$ ========================================================================
$
$$ --- NdFeB_N35 Elastic+Erosion (MID 111061) ---
$$ Brittle failure: principal stress > 270.0 MPa
*MAT_ELASTIC_TITLE
NdFeB_N35 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111061 7.400e-09  150000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=111061
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111061       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    270.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- NdFeB_N42 Elastic+Erosion (MID 111062) ---
$$ Brittle failure: principal stress > 280.0 MPa
*MAT_ELASTIC_TITLE
NdFeB_N42 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111062 7.500e-09  160000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=111062
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111062       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    280.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- NdFeB_N52 Elastic+Erosion (MID 111063) ---
$$ Brittle failure: principal stress > 290.0 MPa
*MAT_ELASTIC_TITLE
NdFeB_N52 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111063 7.600e-09  170000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=111063
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111063       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    290.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
