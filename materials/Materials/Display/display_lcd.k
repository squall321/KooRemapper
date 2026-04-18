$ ========================================================================
$ DISPLAY — LCD Modules: Homogenized stack mechanical
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
$   101055  111055  121055  131055  Display_LCD_IPS         25.0  8.0   2.0 1.80
$
$ ========================================================================
*KEYWORD
$
$ ========================================================================
$ 1. LINEAR ELASTIC (MAT_001)
$ ========================================================================
$
$$ --- Display_LCD_IPS Linear Isotropic (MID 101055) ---
$$ LCD IPS module (Cover glass + polarizer + LC cell + BLU)
$$ Homogenized: E=25.0 GPa (in-plane), rho=1.8 g/cc
$$ Stack thickness: 2.0 mm
$$ Source: JDI / BOE LCD IPS module specs
*MAT_ELASTIC_TITLE
Display_LCD_IPS Linear
$      MID        RO         E        PR        DA        DB
    101055 1.800e-09   25000.0    0.2800       0.0       0.0
$
$ ========================================================================
$ 2. ORTHOTROPIC ELASTIC (MAT_002)
$ ========================================================================
$
$$ --- Display_LCD_IPS Orthotropic (MID 111055) ---
$$ E_inplane=25.0, E_through=8.0 GPa
$$ G_inplane=9.8, G_through=3.0 GPa
*MAT_ORTHOTROPIC_ELASTIC_TITLE
Display_LCD_IPS Orthotropic
$      MID        RO        EA        EB        EC      PRBA      PRCA      PRCB
    111055 1.800e-09   25000.0   25000.0    8000.0    0.2800    0.3200    0.3200
$      GAB       GBC       GCA      AOPT         G      SIGF
    9800.0    3000.0    3000.0       2.0       0.0       0.0
$       XP        YP        ZP        A1        A2        A3      MACF
       0.0       0.0       0.0       1.0       0.0       0.0         0
$       V1        V2        V3        D1        D2        D3      BETA
       0.0       0.0       0.0       0.0       1.0       0.0       0.0
$
$ ========================================================================
$ 3. ELASTIC + EROSION (MAT_001 + MAT_ADD_EROSION)
$ ========================================================================
$
$$ --- Display_LCD_IPS Elastic+Erosion (MID 121055) ---
$$ Erosion: principal stress > 200.0 MPa (cover glass fracture)
*MAT_ELASTIC_TITLE
Display_LCD_IPS Elastic+Erode
$      MID        RO         E        PR        DA        DB
    121055 1.800e-09   25000.0    0.2800       0.0       0.0
$
$$ [DB] PID slot holds MID=121055
*MAT_ADD_EROSION
$      PID       EXCL     MXPRES     MNEPS    EFFEPS    VOLEPS      NUMFIP       NCS
    121055       0.0       0.0       0.0       0.0       0.0         1         1
$    MNPRES    SIGP1     SIGVM    MXEPS      EPSSH     SIGTH    IMPULSE    FAILTM
       0.0    200.00       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
