$ ========================================================================
$ MAGNET — Ferrite / Bonded: Mechanical (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Group: Ferrite / Bonded
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
$   101065  111065  131065  SrFerrite_Y30        160.0  4.90     70    4.0  250
$   101066  111066  131066  NdFeB_Bonded          12.0  5.50    100   10.0  120
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- SrFerrite_Y30 Linear (MID 101065) ---
$$ Strontium ferrite Y30, low-cost hard magnet (toys, appliances)
$$ Source: TDK Ceramagnet 8, Hitachi Ferrite FB
$$ E=160.0 GPa, rho=4.9 g/cc, BHmax=4.0 MGOe
$$ Max operating temperature: 250 C
*MAT_ELASTIC_TITLE
SrFerrite_Y30 Linear
$      MID        RO         E        PR        DA        DB
    101065 4.900e-09  160000.0    0.2800       0.0       0.0
$
$$ --- NdFeB_Bonded Linear (MID 101066) ---
$$ Injection-molded bonded NdFeB (polymer + magnetic powder)
$$ Source: MMG Canada Bonded NdFeB, MagForce
$$ E=12.0 GPa, rho=5.5 g/cc, BHmax=10 MGOe
$$ Max operating temperature: 120 C
*MAT_ELASTIC_TITLE
NdFeB_Bonded Linear
$      MID        RO         E        PR        DA        DB
    101066 5.500e-09   12000.0    0.3500       0.0       0.0
$
$ ========================================================================
$ 2. ELASTIC + EROSION
$ ========================================================================
$
$$ --- SrFerrite_Y30 Elastic+Erosion (MID 111065) ---
$$ Brittle failure: principal stress > 70.0 MPa
*MAT_ELASTIC_TITLE
SrFerrite_Y30 Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111065 4.900e-09  160000.0    0.2800       0.0       0.0
$
$$ [DB] PID slot holds MID=111065
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111065       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0     70.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- NdFeB_Bonded Elastic+Erosion (MID 111066) ---
$$ Brittle failure: principal stress > 100.0 MPa
*MAT_ELASTIC_TITLE
NdFeB_Bonded Elastic+Erode
$      MID        RO         E        PR        DA        DB
    111066 5.500e-09   12000.0    0.3500       0.0       0.0
$
$$ [DB] PID slot holds MID=111066
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    111066       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    100.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
