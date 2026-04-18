$ ========================================================================
$ DISPLAY — OLED Stacks: Homogenized stack mechanical
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$
$ 3 mechanical variants per material:
$   1. MAT_001 Linear (isotropic)       1010xx — simplest
$   2. MAT_002 Orthotropic              1110xx — in-plane vs through-plane
$   3. MAT_001 + MAT_ADD_EROSION         1210xx — crack simulation ★
$
$ Each material is HOMOGENIZED single layer representing
$ the entire display stack (cover glass + OCA + OLED/LCD + substrate).
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION / *MAT_ADD_EROSION holds
$ !!  the MATERIAL ID (MID), NOT an actual Part ID.
$ !! ========================================================================
$
$ SUMMARY TABLE
$
$   lin     ortho   erode   tmid    Name                    E_xy  E_z  t(mm) rho
$   ----------------------------------------------------------------------------------------
$   101051  111051  121051  131051  Display_RigidOLED       60.0 30.0   1.2 2.10
$   101052  111052  121052  131052  Display_FlexibleOLED    35.0  8.0   0.4 1.50
$   101053  111053  121053  131053  Display_FoldableOLED_UTG  40.0 10.0   0.6 1.80
$   101054  111054  121054  131054  Display_FoldableOLED_CPI  10.0  3.0   0.3 1.40
$   101056  111056  121056  131056  Display_MicroLED        70.0 40.0   0.8 2.30
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- Display_RigidOLED Linear Isotropic (MID 101051) ---
$$ Rigid OLED stack equivalent (Gorilla + OCA + OLED + glass substrate)
$$ Homogenized: E=60.0 GPa (in-plane), rho=2.1 g/cc
$$ Stack thickness: 1.2 mm
$$ Source: Samsung Display / LG Display OLED stack public data; Voigt avg
*MAT_ELASTIC_TITLE
Display_RigidOLED Linear
$      MID        RO         E        PR        DA        DB
    101051 2.100e-09   60000.0    0.2500       0.0       0.0
$
$$ --- Display_FlexibleOLED Linear Isotropic (MID 101052) ---
$$ Flexible OLED (edge curved), polymer on PI substrate
$$ Homogenized: E=35.0 GPa (in-plane), rho=1.5 g/cc
$$ Stack thickness: 0.4 mm
$$ Source: Samsung Edge display, LG Flexible OLED
*MAT_ELASTIC_TITLE
Display_FlexibleOLED Linear
$      MID        RO         E        PR        DA        DB
    101052 1.500e-09   35000.0    0.3000       0.0       0.0
$
$$ --- Display_FoldableOLED_UTG Linear Isotropic (MID 101053) ---
$$ Foldable OLED with UTG (Ultra-Thin Glass), Galaxy Fold/Flip
$$ Homogenized: E=40.0 GPa (in-plane), rho=1.8 g/cc
$$ Stack thickness: 0.6 mm
$$ Source: Samsung UTG 30um + OLED + PI substrate
*MAT_ELASTIC_TITLE
Display_FoldableOLED_UTG Linear
$      MID        RO         E        PR        DA        DB
    101053 1.800e-09   40000.0    0.2800       0.0       0.0
$
$$ --- Display_FoldableOLED_CPI Linear Isotropic (MID 101054) ---
$$ Foldable OLED with CPI (Colorless Polyimide) window, early foldable
$$ Homogenized: E=10.0 GPa (in-plane), rho=1.4 g/cc
$$ Stack thickness: 0.3 mm
$$ Source: Galaxy Fold 1, SKC CPI
*MAT_ELASTIC_TITLE
Display_FoldableOLED_CPI Linear
$      MID        RO         E        PR        DA        DB
    101054 1.400e-09   10000.0    0.3500       0.0       0.0
$
$$ --- Display_MicroLED Linear Isotropic (MID 101056) ---
$$ Micro-LED display (reference, sapphire substrate + cover glass)
$$ Homogenized: E=70.0 GPa (in-plane), rho=2.3 g/cc
$$ Stack thickness: 0.8 mm
$$ Source: Samsung The Wall, Sony Crystal LED technical papers
*MAT_ELASTIC_TITLE
Display_MicroLED Linear
$      MID        RO         E        PR        DA        DB
    101056 2.300e-09   70000.0    0.2400       0.0       0.0
$
$ ========================================================================
$ 2. ORTHOTROPIC ELASTIC (MAT_002)
$ ========================================================================
$
$$ --- Display_RigidOLED Orthotropic (MID 111051) ---
$$ E_inplane=60.0, E_through=30.0 GPa
$$ G_inplane=24.0, G_through=12.0 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_RigidOLED Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111051 2.100e-09   60000.0   60000.0   30000.0    0.2500    0.3000    0.3000
$      GAB       GBC       GCA      AOPT         G      SIGF
   24000.0   12000.0   12000.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$$ --- Display_FlexibleOLED Orthotropic (MID 111052) ---
$$ E_inplane=35.0, E_through=8.0 GPa
$$ G_inplane=13.5, G_through=3.0 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_FlexibleOLED Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111052 1.500e-09   35000.0   35000.0    8000.0    0.3000    0.3500    0.3500
$      GAB       GBC       GCA      AOPT         G      SIGF
   13500.0    3000.0    3000.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$$ --- Display_FoldableOLED_UTG Orthotropic (MID 111053) ---
$$ E_inplane=40.0, E_through=10.0 GPa
$$ G_inplane=15.6, G_through=3.8 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_FoldableOLED_UTG Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111053 1.800e-09   40000.0   40000.0   10000.0    0.2800    0.3200    0.3200
$      GAB       GBC       GCA      AOPT         G      SIGF
   15600.0    3800.0    3800.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$$ --- Display_FoldableOLED_CPI Orthotropic (MID 111054) ---
$$ E_inplane=10.0, E_through=3.0 GPa
$$ G_inplane=3.7, G_through=1.1 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_FoldableOLED_CPI Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111054 1.400e-09   10000.0   10000.0    3000.0    0.3500    0.4000    0.4000
$      GAB       GBC       GCA      AOPT         G      SIGF
    3700.0    1100.0    1100.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$$ --- Display_MicroLED Orthotropic (MID 111056) ---
$$ E_inplane=70.0, E_through=40.0 GPa
$$ G_inplane=28.0, G_through=15.0 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_MicroLED Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111056 2.300e-09   70000.0   70000.0   40000.0    0.2400    0.2800    0.2800
$      GAB       GBC       GCA      AOPT         G      SIGF
   28000.0   15000.0   15000.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$ ========================================================================
$ 3. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- Display_RigidOLED Elastic+Erosion (MID 121051) ---
$$ Erosion: principal stress > 400.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_RigidOLED Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121051 2.100e-09   60000.0    0.2500       0.0       0.0
$
$$ [DB] PID slot holds MID=121051
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121051       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    400.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Display_FlexibleOLED Elastic+Erosion (MID 121052) ---
$$ Erosion: principal stress > 300.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_FlexibleOLED Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121052 1.500e-09   35000.0    0.3000       0.0       0.0
$
$$ [DB] PID slot holds MID=121052
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121052       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    300.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Display_FoldableOLED_UTG Elastic+Erosion (MID 121053) ---
$$ Erosion: principal stress > 500.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_FoldableOLED_UTG Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121053 1.800e-09   40000.0    0.2800       0.0       0.0
$
$$ [DB] PID slot holds MID=121053
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121053       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    500.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Display_FoldableOLED_CPI Elastic+Erosion (MID 121054) ---
$$ Erosion: principal stress > 200.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_FoldableOLED_CPI Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121054 1.400e-09   10000.0    0.3500       0.0       0.0
$
$$ [DB] PID slot holds MID=121054
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121054       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    200.00       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- Display_MicroLED Elastic+Erosion (MID 121056) ---
$$ Erosion: principal stress > 450.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_MicroLED Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121056 2.300e-09   70000.0    0.2400       0.0       0.0
$
$$ [DB] PID slot holds MID=121056
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121056       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    450.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
