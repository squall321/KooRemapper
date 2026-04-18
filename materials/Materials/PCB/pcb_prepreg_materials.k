$ ========================================================================
$ PCB PREPREG (PPG) MATERIAL LIBRARY — COMPREHENSIVE
$ ========================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ Total materials: 54
$
$ !! ========================================================================
$ !!  DATABASE CONVENTION — IMPORTANT
$ !!
$ !!  The PID field of *MAT_ADD_THERMAL_EXPANSION in this file holds the
$ !!  MATERIAL ID (MID), NOT an actual LS-DYNA Part ID.
$ !!
$ !!  This is a library convention:
$ !!    1. All CTE cards are template placeholders keyed by MID.
$ !!    2. Before running LS-DYNA, an external tool must:
$ !!       - Scan user's main model for *PART cards using this MID
$ !!       - Replace each MID-in-PID slot with the actual PART ID
$ !!       - Duplicate the card once per PART that uses the same MID
$ !!    3. Running as-is will cause LS-DYNA to complain about missing PIDs.
$ !!
$ !!  The *MAT_VISCOELASTIC cards are standalone and referenced by *PART's
$ !!  MID field directly — no replacement needed.
$ !! ========================================================================
$ MID ranges:
$   100101~100112  General PPG (12 types)
$   100201~100237  Doosan (두산전자) — TDS 직접 추출 (37 types)
$   100301~100305  Elite Material (EMC) — TDS 직접 추출 (5 types)
$
$ Model: *MAT_VISCOELASTIC (MAT_006) + *MAT_ADD_THERMAL_EXPANSION
$ Target: Drop impact simulation (~100-2000 Hz)
$
$ Viscoelastic parameters:
$   Isotropic: G = E/(2*(1+nu)), K = E/(3*(1-2*nu))
$   G0/GI ratio chosen to match target tan(delta) at drop freq
$
$ tan(delta) selection guide (at RT, ~1 kHz):
$   Standard FR-4 (Tg 130-165):  0.030 ~ 0.040
$   High-Tg FR-4 (Tg 170-190):   0.020 ~ 0.030
$   Low-loss (Megtron, EM-526):  0.015 ~ 0.020
$   Ultra low-loss (EM-892K):    0.010 ~ 0.015
$   BT/PI/CE (Tg 185+):          0.015 ~ 0.025
$   PTFE:                        0.010
$   ABF (soft low Tg):           0.060
$
$ Reference files (in ./references/):
$   - doosan_CCL_All_Properties.pdf (Doosan official TDS, all materials)
$   - elite_EM-370Z_datasheet.pdf (Elite EM-370Z)
$   - elite_EM-526_datasheet.pdf (Elite EM-526)
$   - elite_EM-528_datasheet.pdf (Elite EM-528)
$   - elite_EM-892K_datasheet.pdf (Elite EM-892K)
$   - elite_EM-S570_datasheet.pdf (Elite EM-S570)
$   - doosan_materials_db.json (parsed Doosan DB)
$   - elite_materials_db.json (parsed Elite DB)
$
$ ========================================================================
$
$ SUMMARY TABLE
$
$    MID    Name                                          E(GPa) rho  Tg  CTExy tand
$    ----------------------------------------------------------------------------------------
$    100101  PPG FR-4 Standard (Tg 130C)                  22.0  1.85  130  14.0  0.040
$    100102  PPG Hitachi MCL-E-679F (Tg 150C)             23.0  1.87  150  13.0  0.035
$    100103  PPG Panasonic R-1566 (Tg 170C)               24.0  1.88  170  13.0  0.030
$    100104  PPG Isola 370HR (Tg 180C)                    24.0  1.90  180  14.0  0.025
$    100105  PPG Panasonic Megtron-6 (Tg 185C)            25.0  1.88  185  13.0  0.020
$    100106  PPG BT Resin (AGC N5000)                     26.0  1.90  185  11.0  0.025
$    100107  PPG Isola P95 Polyimide (Tg 250C)            20.0  1.40  250  14.0  0.015
$    100108  PPG Cyanate Ester (Tg 240C)                  22.0  1.85  240  12.0  0.018
$    100109  PPG Rogers RO3003 (PTFE)                      8.0  2.20  327  17.0  0.010
$    100110  PPG Rogers RO4350B (Tg 280C)                 16.0  1.86  280  11.0  0.020
$    100111  PPG Ajinomoto ABF GX (Tg 160C)                6.0  1.40  160  35.0  0.060
$    100112  PPG DuPont Kapton Polyimide                   3.0  1.42  220  17.0  0.020
$    100201  Doosan DS-7402                               24.5  1.90  165  14.5  0.035
$    100202  Doosan DS-7402M                              24.5  1.87  165  14.5  0.035
$    100203  Doosan DS-7402BS(DF)                         16.5  1.60  185  19.5  0.025
$    100204  Doosan DS-7402LC                             32.5  2.03  175  10.5  0.025
$    100205  Doosan DS-7402H                              23.0  1.87  200  14.5  0.020
$    100206  Doosan DS-7402HD                             25.0  1.90  210  14.0  0.020
$    100207  Doosan DS-8402H                              23.0  1.87  190  14.5  0.025
$    100208  Doosan DS-8502LC                             29.5  1.96  280   9.5  0.015
$    100209  Doosan DS-8502SQ                             30.0  1.95  260   9.5  0.015
$    100210  Doosan DS-8502SQN                            30.0  1.95  260   9.5  0.015
$    100211  Doosan DS-8502HQ                             25.5  1.93  240  13.5  0.020
$    100212  Doosan DS-8502HQN                            25.5  1.93  240  13.5  0.020
$    100213  Doosan DS-9530                                0.8  2.10  180  24.0  0.025
$    100214  Doosan DSR-1000                              12.0  1.90  170  12.5  0.025
$    100215  Doosan DSF-900LC                             10.0  1.75  280  25.0  0.015
$    100216  Doosan DSF-900SQ                             10.0  1.70  190  25.0  0.025
$    100217  Doosan DST-9000                              14.0  1.90  130  30.0  0.035
$    100218  Doosan DST-9000HT                            14.0  2.00  180  25.0  0.025
$    100219  Doosan DSflex-600                             6.9  1.42  320  23.5  0.015
$    100220  Doosan DSflex-600P                            4.6  1.42  350  20.0  0.015
$    100221  Doosan DSflex-600U                            6.2  1.42  330  20.0  0.015
$    100222  Doosan DSflex-600D                            4.2  1.42  330  23.5  0.015
$    100223  Doosan DSflex-600UY                           7.7  1.42  260  26.5  0.015
$    100224  Doosan DSflex-600UF                           7.5  1.42  280  20.0  0.015
$    100225  Doosan DSflex-600UK                           7.5  1.42  280  20.0  0.015
$    100226  Doosan DSflex-900                             5.7  1.42  340  23.5  0.015
$    100227  Doosan DS-7409DV(N)                          23.0  1.90  225  16.0  0.020
$    100228  Doosan DS-7409DX(C)                          24.0  1.90  220  16.0  0.020
$    100229  Doosan DS-7409DJG                            22.0  1.90  220  16.0  0.020
$    100230  Doosan DS-7409DXG                            25.5  1.71  280   9.5  0.015
$    100231  Doosan DS-7409S(N)                           22.0  1.90  190  15.5  0.025
$    100232  Doosan DS-7409HG(FQ)                         35.0  2.30  200   3.0  0.020
$    100233  Doosan DS-7409HG(ZL)                         40.0  2.30  300   2.0  0.015
$    100234  Doosan DS-7409HG(X)                          38.0  2.30  260   5.0  0.015
$    100235  Doosan DS-7409HG(LE)                         33.0  2.20  240   8.0  0.020
$    100236  Doosan DS-7409HG(I)                          38.0  2.30  270   3.0  0.015
$    100237  Doosan RAPIDON-10W                           15.0  2.00  200  13.0  0.020
$    100301  Elite EM-370Z                                24.0  1.88  210  12.0  0.036
$    100302  Elite EM-526                                 25.0  1.88  260   9.5  0.015
$    100303  Elite EM-528                                 25.0  1.88  250   9.5  0.014
$    100304  Elite EM-892K                                24.0  1.88  215  12.5  0.010
$    100305  Elite EM-S570                                31.0  1.88  320   5.0  0.018
$
$ ========================================================================
*KEYWORD
$
$
$ ========================================================================
$ 1. General PPG (Industry Standard)
$ ========================================================================
$
$$ --- PPG FR-4 Standard (Tg 130C) (MID 100101) ---
$$ 표준 FR-4 — 가장 보편적, 저가 범용
$$ 용도: 일반 PCB, 소비자 전자
$$ 출처: Wikipedia FR-4 + typical industry
$$
$$ E=22.0 GPa, nu=0.2, rho=1.85 g/cm^3
$$   -> K=12222 MPa, G_avg=9174 MPa
$$ Tg=130 C, Td=310 C
$$ CTE: xy=14.0 ppm/K (used), z=70.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.041x, BETA=500/s (tau=2.00ms)
$$ tan(delta) @ drop freq ~ 0.040
*MAT_VISCOELASTIC_TITLE
PPG FR-4 Standard (Tg 130C)
$      MID        RO      BULK        G0        GI      BETA
    100101 1.850e-09   12222.2    9540.7    8807.3     500.0
$
$$ [DB] PID slot holds MID=100101 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100101         0 1.400e-05
$
$$ --- PPG Hitachi MCL-E-679F (Tg 150C) (MID 100102) ---
$$ 중간 Tg 할로겐프리
$$ 용도: 스마트폰 4-6층, 5G
$$ 출처: Hitachi MCL-E-679F: Tg=150C, Df=0.012
$$
$$ E=23.0 GPa, nu=0.2, rho=1.87 g/cm^3
$$   -> K=12778 MPa, G_avg=9589 MPa
$$ Tg=150 C, Td=340 C
$$ CTE: xy=13.0 ppm/K (used), z=60.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.036x, BETA=600/s (tau=1.67ms)
$$ tan(delta) @ drop freq ~ 0.035
*MAT_VISCOELASTIC_TITLE
PPG Hitachi MCL-E-679F (Tg 150C)
$      MID        RO      BULK        G0        GI      BETA
    100102 1.870e-09   12777.8    9924.6    9253.8     600.0
$
$$ [DB] PID slot holds MID=100102 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100102         0 1.300e-05
$
$$ --- PPG Panasonic R-1566 (Tg 170C) (MID 100103) ---
$$ 고 Tg HDI — 스마트폰 메인보드
$$ 용도: 10+층 HDI, AP 기판
$$ 출처: Panasonic R-1566: Tg=170C, Df=0.010
$$
$$ E=24.0 GPa, nu=0.2, rho=1.88 g/cm^3
$$   -> K=13333 MPa, G_avg=10004 MPa
$$ Tg=170 C, Td=350 C
$$ CTE: xy=13.0 ppm/K (used), z=55.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.030x, BETA=700/s (tau=1.43ms)
$$ tan(delta) @ drop freq ~ 0.030
*MAT_VISCOELASTIC_TITLE
PPG Panasonic R-1566 (Tg 170C)
$      MID        RO      BULK        G0        GI      BETA
    100103 1.880e-09   13333.3   10304.5    9704.5     700.0
$
$$ [DB] PID slot holds MID=100103 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100103         0 1.300e-05
$
$$ --- PPG Isola 370HR (Tg 180C) (MID 100104) ---
$$ Isola 370HR — Pb-free 호환
$$ 용도: 자동차 ECU, 의료기기
$$ 출처: Isola 370HR TDS
$$
$$ E=24.0 GPa, nu=0.19, rho=1.9 g/cm^3
$$   -> K=12903 MPa, G_avg=10087 MPa
$$ Tg=180 C, Td=340 C
$$ CTE: xy=14.0 ppm/K (used), z=45.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
PPG Isola 370HR (Tg 180C)
$      MID        RO      BULK        G0        GI      BETA
    100104 1.900e-09   12903.2   10339.3    9835.1     800.0
$
$$ [DB] PID slot holds MID=100104 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100104         0 1.400e-05
$
$$ --- PPG Panasonic Megtron-6 (Tg 185C) (MID 100105) ---
$$ Megtron-6 저손실 HDI
$$ 용도: 서버, AP, 5G
$$ 출처: Panasonic Megtron-6 TDS
$$
$$ E=25.0 GPa, nu=0.19, rho=1.88 g/cm^3
$$   -> K=13441 MPa, G_avg=10506 MPa
$$ Tg=185 C, Td=380 C
$$ CTE: xy=13.0 ppm/K (used), z=50.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=900/s (tau=1.11ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
PPG Panasonic Megtron-6 (Tg 185C)
$      MID        RO      BULK        G0        GI      BETA
    100105 1.880e-09   13440.9   10716.4   10296.2     900.0
$
$$ [DB] PID slot holds MID=100105 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100105         0 1.300e-05
$
$$ --- PPG BT Resin (AGC N5000) (MID 100106) ---
$$ BT 수지 저 z-CTE
$$ 용도: IC 패키징, BGA
$$ 출처: AGC N5000 BT epoxy
$$
$$ E=26.0 GPa, nu=0.19, rho=1.9 g/cm^3
$$   -> K=13978 MPa, G_avg=10928 MPa
$$ Tg=185 C, Td=380 C
$$ CTE: xy=11.0 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
PPG BT Resin (AGC N5000)
$      MID        RO      BULK        G0        GI      BETA
    100106 1.900e-09   13978.5   11200.9   10654.7    1000.0
$
$$ [DB] PID slot holds MID=100106 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100106         0 1.100e-05
$
$$ --- PPG Isola P95 Polyimide (Tg 250C) (MID 100107) ---
$$ 폴리이미드 초고온
$$ 용도: 항공우주, 고온 전자
$$ 출처: Isola P95 TDS
$$
$$ E=20.0 GPa, nu=0.22, rho=1.4 g/cm^3
$$   -> K=11905 MPa, G_avg=8198 MPa
$$ Tg=250 C, Td=450 C
$$ CTE: xy=14.0 ppm/K (used), z=25.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
PPG Isola P95 Polyimide (Tg 250C)
$      MID        RO      BULK        G0        GI      BETA
    100107 1.400e-09   11904.8    8320.6    8074.7    1000.0
$
$$ [DB] PID slot holds MID=100107 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100107         0 1.400e-05
$
$$ --- PPG Cyanate Ester (Tg 240C) (MID 100108) ---
$$ CE 저 Dk/Df 우주용
$$ 용도: mm-wave, 우주
$$ 출처: CE resin: Dk=3.3
$$
$$ E=22.0 GPa, nu=0.21, rho=1.85 g/cm^3
$$   -> K=12644 MPa, G_avg=9092 MPa
$$ Tg=240 C, Td=420 C
$$ CTE: xy=12.0 ppm/K (used), z=45.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.018x, BETA=900/s (tau=1.11ms)
$$ tan(delta) @ drop freq ~ 0.018
*MAT_VISCOELASTIC_TITLE
PPG Cyanate Ester (Tg 240C)
$      MID        RO      BULK        G0        GI      BETA
    100108 1.850e-09   12643.7    9256.0    8928.7     900.0
$
$$ [DB] PID slot holds MID=100108 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100108         0 1.200e-05
$
$$ --- PPG Rogers RO3003 (PTFE) (MID 100109) ---
$$ PTFE/세라믹 고주파
$$ 용도: 10+ GHz RF, 안테나
$$ 출처: Rogers RO3003 TDS
$$
$$ E=8.0 GPa, nu=0.28, rho=2.2 g/cm^3
$$   -> K=6061 MPa, G_avg=3125 MPa
$$ Tg=327 C, Td=400 C
$$ CTE: xy=17.0 ppm/K (used), z=24.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.010x, BETA=500/s (tau=2.00ms)
$$ tan(delta) @ drop freq ~ 0.010
*MAT_VISCOELASTIC_TITLE
PPG Rogers RO3003 (PTFE)
$      MID        RO      BULK        G0        GI      BETA
    100109 2.200e-09    6060.6    3156.4    3093.9     500.0
$
$$ [DB] PID slot holds MID=100109 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100109         0 1.700e-05
$
$$ --- PPG Rogers RO4350B (Tg 280C) (MID 100110) ---
$$ 하이브리드 세라믹 RF
$$ 용도: 저가 RF, 셀룰러
$$ 출처: Rogers RO4350B TDS
$$
$$ E=16.0 GPa, nu=0.21, rho=1.86 g/cm^3
$$   -> K=9195 MPa, G_avg=6613 MPa
$$ Tg=280 C, Td=390 C
$$ CTE: xy=11.0 ppm/K (used), z=32.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=700/s (tau=1.43ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
PPG Rogers RO4350B (Tg 280C)
$      MID        RO      BULK        G0        GI      BETA
    100110 1.860e-09    9195.4    6745.1    6480.7     700.0
$
$$ [DB] PID slot holds MID=100110 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100110         0 1.100e-05
$
$$ --- PPG Ajinomoto ABF GX (Tg 160C) (MID 100111) ---
$$ ABF 빌드업 연질 필름
$$ 용도: CPU/GPU FC-BGA
$$ 출처: Ajinomoto ABF GX series
$$
$$ E=6.0 GPa, nu=0.25, rho=1.4 g/cm^3
$$   -> K=4000 MPa, G_avg=2404 MPa
$$ Tg=160 C, Td=320 C
$$ CTE: xy=35.0 ppm/K (used), z=50.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.062x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.060
*MAT_VISCOELASTIC_TITLE
PPG Ajinomoto ABF GX (Tg 160C)
$      MID        RO      BULK        G0        GI      BETA
    100111 1.400e-09    4000.0    2548.3    2260.3    1200.0
$
$$ [DB] PID slot holds MID=100111 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100111         0 3.500e-05
$
$$ --- PPG DuPont Kapton Polyimide (MID 100112) ---
$$ 연성 폴리이미드 Kapton
$$ 용도: FPC, 폴더블
$$ 출처: DuPont Kapton Polyimide
$$
$$ E=3.0 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=3125 MPa, G_avg=1120 MPa
$$ Tg=220 C, Td=450 C
$$ CTE: xy=17.0 ppm/K (used), z=60.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=500/s (tau=2.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
PPG DuPont Kapton Polyimide
$      MID        RO      BULK        G0        GI      BETA
    100112 1.420e-09    3125.0    1142.0    1097.2     500.0
$
$$ [DB] PID slot holds MID=100112 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100112         0 1.700e-05
$
$ ========================================================================
$ 2. Doosan (두산전자) — CCL TDS All Grades
$ ========================================================================
$
$$ --- Doosan DS-7402 (MID 100201) ---
$$ 범용 할로겐프리 FR-4, 중간 Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402
$$
$$ E=24.5 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=12010 MPa, G_avg=10567 MPa
$$ Tg=165 C, Td=380 C
$$ CTE: xy=14.5 ppm/K (used), z=38.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.036x, BETA=600/s (tau=1.67ms)
$$ tan(delta) @ drop freq ~ 0.035
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402
$      MID        RO      BULK        G0        GI      BETA
    100201 1.900e-09   12009.8   10936.4   10197.2     600.0
$
$$ [DB] PID slot holds MID=100201 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100201         0 1.450e-05
$
$$ --- Doosan DS-7402M (MID 100202) ---
$$ DS-7402 개량형
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402M
$$
$$ E=24.5 GPa, nu=0.16, rho=1.87 g/cm^3
$$   -> K=12010 MPa, G_avg=10567 MPa
$$ Tg=165 C, Td=370 C
$$ CTE: xy=14.5 ppm/K (used), z=39.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.036x, BETA=600/s (tau=1.67ms)
$$ tan(delta) @ drop freq ~ 0.035
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402M
$      MID        RO      BULK        G0        GI      BETA
    100202 1.870e-09   12009.8   10936.4   10197.2     600.0
$
$$ [DB] PID slot holds MID=100202 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100202         0 1.450e-05
$
$$ --- Doosan DS-7402BS(DF) (MID 100203) ---
$$ Foil backing 제품
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402BS(DF)
$$
$$ E=16.5 GPa, nu=0.16, rho=1.6 g/cm^3
$$   -> K=8088 MPa, G_avg=7114 MPa
$$ Tg=185 C, Td=360 C
$$ CTE: xy=19.5 ppm/K (used), z=95.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402BS(DF)
$      MID        RO      BULK        G0        GI      BETA
    100203 1.600e-09    8088.2    7292.1    6936.5     800.0
$
$$ [DB] PID slot holds MID=100203 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100203         0 1.950e-05
$
$$ --- Doosan DS-7402LC (MID 100204) ---
$$ 저 CTE 고강성 (필러충진)
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402LC
$$
$$ E=32.5 GPa, nu=0.2, rho=2.03 g/cm^3
$$   -> K=18056 MPa, G_avg=13546 MPa
$$ Tg=175 C, Td=360 C
$$ CTE: xy=10.5 ppm/K (used), z=19.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402LC
$      MID        RO      BULK        G0        GI      BETA
    100204 2.030e-09   18055.6   13884.4   13207.4     800.0
$
$$ [DB] PID slot holds MID=100204 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100204         0 1.050e-05
$
$$ --- Doosan DS-7402H (MID 100205) ---
$$ FR-4 High Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402H
$$
$$ E=23 GPa, nu=0.16, rho=1.87 g/cm^3
$$   -> K=11275 MPa, G_avg=9916 MPa
$$ Tg=200 C, Td=380 C
$$ CTE: xy=14.5 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402H
$      MID        RO      BULK        G0        GI      BETA
    100205 1.870e-09   11274.5   10114.1    9717.5    1000.0
$
$$ [DB] PID slot holds MID=100205 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100205         0 1.450e-05
$
$$ --- Doosan DS-7402HD (MID 100206) ---
$$ 고방열 FR-4
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7402HD
$$
$$ E=25 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=12255 MPa, G_avg=10778 MPa
$$ Tg=210 C, Td=380 C
$$ CTE: xy=14.0 ppm/K (used), z=30.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7402HD
$      MID        RO      BULK        G0        GI      BETA
    100206 1.900e-09   12254.9   10993.5   10562.5    1000.0
$
$$ [DB] PID slot holds MID=100206 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100206         0 1.400e-05
$
$$ --- Doosan DS-8402H (MID 100207) ---
$$ 저손실 할로겐프리 고Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8402H
$$
$$ E=23 GPa, nu=0.16, rho=1.87 g/cm^3
$$   -> K=11275 MPa, G_avg=9917 MPa
$$ Tg=190 C, Td=380 C
$$ CTE: xy=14.5 ppm/K (used), z=35.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DS-8402H
$      MID        RO      BULK        G0        GI      BETA
    100207 1.870e-09   11274.5   10164.7    9669.0     800.0
$
$$ [DB] PID slot holds MID=100207 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100207         0 1.450e-05
$
$$ --- Doosan DS-8502LC (MID 100208) ---
$$ CE 기반 초고Tg 저CTE
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8502LC
$$
$$ E=29.5 GPa, nu=0.2, rho=1.96 g/cm^3
$$   -> K=16389 MPa, G_avg=12293 MPa
$$ Tg=280 C, Td=430 C
$$ CTE: xy=9.5 ppm/K (used), z=20.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-8502LC
$      MID        RO      BULK        G0        GI      BETA
    100208 1.960e-09   16388.9   12477.4   12108.7    1200.0
$
$$ [DB] PID slot holds MID=100208 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100208         0 9.500e-06
$
$$ --- Doosan DS-8502SQ (MID 100209) ---
$$ 초고Tg 저CTE SQ grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8502SQ
$$
$$ E=30 GPa, nu=0.16, rho=1.95 g/cm^3
$$   -> K=14706 MPa, G_avg=12932 MPa
$$ Tg=260 C, Td=420 C
$$ CTE: xy=9.5 ppm/K (used), z=22.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-8502SQ
$      MID        RO      BULK        G0        GI      BETA
    100209 1.950e-09   14705.9   13126.5   12738.5    1200.0
$
$$ [DB] PID slot holds MID=100209 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100209         0 9.500e-06
$
$$ --- Doosan DS-8502SQN (MID 100210) ---
$$ SQ no-halogen variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8502SQN
$$
$$ E=30 GPa, nu=0.16, rho=1.95 g/cm^3
$$   -> K=14706 MPa, G_avg=12932 MPa
$$ Tg=260 C, Td=420 C
$$ CTE: xy=9.5 ppm/K (used), z=22.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-8502SQN
$      MID        RO      BULK        G0        GI      BETA
    100210 1.950e-09   14705.9   13126.5   12738.5    1200.0
$
$$ [DB] PID slot holds MID=100210 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100210         0 9.500e-06
$
$$ --- Doosan DS-8502HQ (MID 100211) ---
$$ 고 Tg HQ grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8502HQ
$$
$$ E=25.5 GPa, nu=0.16, rho=1.93 g/cm^3
$$   -> K=12500 MPa, G_avg=10994 MPa
$$ Tg=240 C, Td=420 C
$$ CTE: xy=13.5 ppm/K (used), z=27.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-8502HQ
$      MID        RO      BULK        G0        GI      BETA
    100211 1.930e-09   12500.0   11213.4   10773.7    1000.0
$
$$ [DB] PID slot holds MID=100211 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100211         0 1.350e-05
$
$$ --- Doosan DS-8502HQN (MID 100212) ---
$$ HQ no-halogen
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-8502HQN
$$
$$ E=25.5 GPa, nu=0.16, rho=1.93 g/cm^3
$$   -> K=12500 MPa, G_avg=10994 MPa
$$ Tg=240 C, Td=420 C
$$ CTE: xy=13.5 ppm/K (used), z=27.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-8502HQN
$      MID        RO      BULK        G0        GI      BETA
    100212 1.930e-09   12500.0   11213.4   10773.7    1000.0
$
$$ [DB] PID slot holds MID=100212 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100212         0 1.350e-05
$
$$ --- Doosan DS-9530 (MID 100213) ---
$$ 초고 Td 저유전율 필름
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-9530
$$
$$ E=0.8 GPa, nu=0.17, rho=2.1 g/cm^3
$$   -> K=404 MPa, G_avg=342 MPa
$$ Tg=180 C, Td=510 C
$$ CTE: xy=24.0 ppm/K (used), z=30.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DS-9530
$      MID        RO      BULK        G0        GI      BETA
    100213 2.100e-09     404.0     350.5     333.4     800.0
$
$$ [DB] PID slot holds MID=100213 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100213         0 2.400e-05
$
$$ --- Doosan DSR-1000 (MID 100214) ---
$$ 고신뢰성 중가 Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSR-1000
$$
$$ E=12 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=5882 MPa, G_avg=5174 MPa
$$ Tg=170 C, Td=353 C
$$ CTE: xy=12.5 ppm/K (used), z=115.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DSR-1000
$      MID        RO      BULK        G0        GI      BETA
    100214 1.900e-09    5882.4    5303.3    5044.7     800.0
$
$$ [DB] PID slot holds MID=100214 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100214         0 1.250e-05
$
$$ --- Doosan DSF-900LC (MID 100215) ---
$$ 저유전율 플루오로폴리머
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSF-900LC
$$
$$ E=10 GPa, nu=0.3, rho=1.75 g/cm^3
$$   -> K=8333 MPa, G_avg=3847 MPa
$$ Tg=280 C, Td=360 C
$$ CTE: xy=25.0 ppm/K (used), z=25.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSF-900LC
$      MID        RO      BULK        G0        GI      BETA
    100215 1.750e-09    8333.3    3904.3    3788.9    1200.0
$
$$ [DB] PID slot holds MID=100215 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100215         0 2.500e-05
$
$$ --- Doosan DSF-900SQ (MID 100216) ---
$$ 저유전율 SQ grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSF-900SQ
$$
$$ E=10 GPa, nu=0.28, rho=1.7 g/cm^3
$$   -> K=7576 MPa, G_avg=3907 MPa
$$ Tg=190 C, Td=400 C
$$ CTE: xy=25.0 ppm/K (used), z=25.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DSF-900SQ
$      MID        RO      BULK        G0        GI      BETA
    100216 1.700e-09    7575.8    4005.1    3809.8     800.0
$
$$ [DB] PID slot holds MID=100216 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100216         0 2.500e-05
$
$$ --- Doosan DST-9000 (MID 100217) ---
$$ 열전도 저 Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DST-9000
$$
$$ E=14 GPa, nu=0.18, rho=1.9 g/cm^3
$$   -> K=7292 MPa, G_avg=5936 MPa
$$ Tg=130 C, Td=380 C
$$ CTE: xy=30.0 ppm/K (used), z=30.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.036x, BETA=600/s (tau=1.67ms)
$$ tan(delta) @ drop freq ~ 0.035
*MAT_VISCOELASTIC_TITLE
Doosan DST-9000
$      MID        RO      BULK        G0        GI      BETA
    100217 1.900e-09    7291.7    6143.5    5728.2     600.0
$
$$ [DB] PID slot holds MID=100217 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100217         0 3.000e-05
$
$$ --- Doosan DST-9000HT (MID 100218) ---
$$ 열전도 고 Tg
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DST-9000HT
$$
$$ E=14 GPa, nu=0.18, rho=2.0 g/cm^3
$$   -> K=7292 MPa, G_avg=5934 MPa
$$ Tg=180 C, Td=410 C
$$ CTE: xy=25.0 ppm/K (used), z=25.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DST-9000HT
$      MID        RO      BULK        G0        GI      BETA
    100218 2.000e-09    7291.7    6082.4    5785.8     800.0
$
$$ [DB] PID slot holds MID=100218 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100218         0 2.500e-05
$
$$ --- Doosan DSflex-600 (MID 100219) ---
$$ 폴리이미드 플렉스 기본
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600
$$
$$ E=6.9 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=7188 MPa, G_avg=2575 MPa
$$ Tg=320 C, Td=500 C
$$ CTE: xy=23.5 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600
$      MID        RO      BULK        G0        GI      BETA
    100219 1.420e-09    7187.5    2613.5    2536.3    1200.0
$
$$ [DB] PID slot holds MID=100219 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100219         0 2.350e-05
$
$$ --- Doosan DSflex-600P (MID 100220) ---
$$ 고 Tg 플렉스
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600P
$$
$$ E=4.6 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=4792 MPa, G_avg=1717 MPa
$$ Tg=350 C, Td=500 C
$$ CTE: xy=20.0 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600P
$      MID        RO      BULK        G0        GI      BETA
    100220 1.420e-09    4791.7    1742.4    1690.9    1200.0
$
$$ [DB] PID slot holds MID=100220 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100220         0 2.000e-05
$
$$ --- Doosan DSflex-600U (MID 100221) ---
$$ 플렉스 U variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600U
$$
$$ E=6.2 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=6458 MPa, G_avg=2314 MPa
$$ Tg=330 C, Td=500 C
$$ CTE: xy=20.0 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600U
$      MID        RO      BULK        G0        GI      BETA
    100221 1.420e-09    6458.3    2348.4    2279.0    1200.0
$
$$ [DB] PID slot holds MID=100221 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100221         0 2.000e-05
$
$$ --- Doosan DSflex-600D (MID 100222) ---
$$ 플렉스 D variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600D
$$
$$ E=4.2 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=4375 MPa, G_avg=1567 MPa
$$ Tg=330 C, Td=500 C
$$ CTE: xy=23.5 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600D
$      MID        RO      BULK        G0        GI      BETA
    100222 1.420e-09    4375.0    1590.8    1543.8    1200.0
$
$$ [DB] PID slot holds MID=100222 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100222         0 2.350e-05
$
$$ --- Doosan DSflex-600UY (MID 100223) ---
$$ 플렉스 UY variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600UY
$$
$$ E=7.7 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=8021 MPa, G_avg=2873 MPa
$$ Tg=260 C, Td=500 C
$$ CTE: xy=26.5 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600UY
$      MID        RO      BULK        G0        GI      BETA
    100223 1.420e-09    8020.8    2916.6    2830.4    1200.0
$
$$ [DB] PID slot holds MID=100223 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100223         0 2.650e-05
$
$$ --- Doosan DSflex-600UF (MID 100224) ---
$$ 플렉스 UF variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600UF
$$
$$ E=7.5 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=7813 MPa, G_avg=2799 MPa
$$ Tg=280 C, Td=500 C
$$ CTE: xy=20.0 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600UF
$      MID        RO      BULK        G0        GI      BETA
    100224 1.420e-09    7812.5    2840.8    2756.8    1200.0
$
$$ [DB] PID slot holds MID=100224 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100224         0 2.000e-05
$
$$ --- Doosan DSflex-600UK (MID 100225) ---
$$ 플렉스 UK variant
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-600UK
$$
$$ E=7.5 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=7813 MPa, G_avg=2799 MPa
$$ Tg=280 C, Td=500 C
$$ CTE: xy=20.0 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-600UK
$      MID        RO      BULK        G0        GI      BETA
    100225 1.420e-09    7812.5    2840.8    2756.8    1200.0
$
$$ [DB] PID slot holds MID=100225 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100225         0 2.000e-05
$
$$ --- Doosan DSflex-900 (MID 100226) ---
$$ 플렉스 900 series
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DSflex-900
$$
$$ E=5.7 GPa, nu=0.34, rho=1.42 g/cm^3
$$   -> K=5938 MPa, G_avg=2127 MPa
$$ Tg=340 C, Td=500 C
$$ CTE: xy=23.5 ppm/K (used), z=40.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DSflex-900
$      MID        RO      BULK        G0        GI      BETA
    100226 1.420e-09    5937.5    2159.0    2095.2    1200.0
$
$$ [DB] PID slot holds MID=100226 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100226         0 2.350e-05
$
$$ --- Doosan DS-7409DV(N) (MID 100227) ---
$$ 고속 저손실 DV(N)
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409DV(N)
$$
$$ E=23 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=11275 MPa, G_avg=9916 MPa
$$ Tg=225 C, Td=400 C
$$ CTE: xy=16.0 ppm/K (used), z=45.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409DV(N)
$      MID        RO      BULK        G0        GI      BETA
    100227 1.900e-09   11274.5   10114.1    9717.5    1000.0
$
$$ [DB] PID slot holds MID=100227 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100227         0 1.600e-05
$
$$ --- Doosan DS-7409DX(C) (MID 100228) ---
$$ 고속 저손실 DX(C)
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409DX(C)
$$
$$ E=24 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=11765 MPa, G_avg=10347 MPa
$$ Tg=220 C, Td=365 C
$$ CTE: xy=16.0 ppm/K (used), z=35.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409DX(C)
$      MID        RO      BULK        G0        GI      BETA
    100228 1.900e-09   11764.7   10553.8   10140.0    1000.0
$
$$ [DB] PID slot holds MID=100228 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100228         0 1.600e-05
$
$$ --- Doosan DS-7409DJG (MID 100229) ---
$$ 고속 저손실 DJG
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409DJG
$$
$$ E=22 GPa, nu=0.17, rho=1.9 g/cm^3
$$   -> K=11111 MPa, G_avg=9404 MPa
$$ Tg=220 C, Td=400 C
$$ CTE: xy=16.0 ppm/K (used), z=45.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409DJG
$      MID        RO      BULK        G0        GI      BETA
    100229 1.900e-09   11111.1    9591.6    9215.6    1000.0
$
$$ [DB] PID slot holds MID=100229 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100229         0 1.600e-05
$
$$ --- Doosan DS-7409DXG (MID 100230) ---
$$ 초고 Tg 저CTE DXG
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409DXG
$$
$$ E=25.5 GPa, nu=0.18, rho=1.71 g/cm^3
$$   -> K=13281 MPa, G_avg=10806 MPa
$$ Tg=280 C, Td=430 C
$$ CTE: xy=9.5 ppm/K (used), z=20.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409DXG
$      MID        RO      BULK        G0        GI      BETA
    100230 1.710e-09   13281.2   10968.4   10644.2    1200.0
$
$$ [DB] PID slot holds MID=100230 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100230         0 9.500e-06
$
$$ --- Doosan DS-7409S(N) (MID 100231) ---
$$ 고속 S(N) grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409S(N)
$$
$$ E=22 GPa, nu=0.16, rho=1.9 g/cm^3
$$   -> K=10784 MPa, G_avg=9486 MPa
$$ Tg=190 C, Td=350 C
$$ CTE: xy=15.5 ppm/K (used), z=50.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.025x, BETA=800/s (tau=1.25ms)
$$ tan(delta) @ drop freq ~ 0.025
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409S(N)
$      MID        RO      BULK        G0        GI      BETA
    100231 1.900e-09   10784.3    9722.8    9248.7     800.0
$
$$ [DB] PID slot holds MID=100231 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100231         0 1.550e-05
$
$$ --- Doosan DS-7409HG(FQ) (MID 100232) ---
$$ 초저CTE FQ (세라믹 고충진)
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409HG(FQ)
$$
$$ E=35 GPa, nu=0.18, rho=2.3 g/cm^3
$$   -> K=18229 MPa, G_avg=14833 MPa
$$ Tg=200 C, Td=380 C
$$ CTE: xy=3.0 ppm/K (used), z=12.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409HG(FQ)
$      MID        RO      BULK        G0        GI      BETA
    100232 2.300e-09   18229.2   15130.1   14536.9    1000.0
$
$$ [DB] PID slot holds MID=100232 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100232         0 3.000e-06
$
$$ --- Doosan DS-7409HG(ZL) (MID 100233) ---
$$ 극한 저CTE ZL
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409HG(ZL)
$$
$$ E=40 GPa, nu=0.18, rho=2.3 g/cm^3
$$   -> K=20833 MPa, G_avg=16951 MPa
$$ Tg=300 C, Td=380 C
$$ CTE: xy=2.0 ppm/K (used), z=8.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409HG(ZL)
$      MID        RO      BULK        G0        GI      BETA
    100233 2.300e-09   20833.3   17205.3   16696.8    1200.0
$
$$ [DB] PID slot holds MID=100233 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100233         0 2.000e-06
$
$$ --- Doosan DS-7409HG(X) (MID 100234) ---
$$ 저CTE X grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409HG(X)
$$
$$ E=38 GPa, nu=0.18, rho=2.3 g/cm^3
$$   -> K=19792 MPa, G_avg=16104 MPa
$$ Tg=260 C, Td=380 C
$$ CTE: xy=5.0 ppm/K (used), z=12.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409HG(X)
$      MID        RO      BULK        G0        GI      BETA
    100234 2.300e-09   19791.7   16345.0   15862.0    1200.0
$
$$ [DB] PID slot holds MID=100234 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100234         0 5.000e-06
$
$$ --- Doosan DS-7409HG(LE) (MID 100235) ---
$$ 저CTE LE grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409HG(LE)
$$
$$ E=33 GPa, nu=0.18, rho=2.2 g/cm^3
$$   -> K=17188 MPa, G_avg=13986 MPa
$$ Tg=240 C, Td=380 C
$$ CTE: xy=8.0 ppm/K (used), z=20.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409HG(LE)
$      MID        RO      BULK        G0        GI      BETA
    100235 2.200e-09   17187.5   14265.5   13706.2    1000.0
$
$$ [DB] PID slot holds MID=100235 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100235         0 8.000e-06
$
$$ --- Doosan DS-7409HG(I) (MID 100236) ---
$$ 초저CTE I grade
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: DS-7409HG(I)
$$
$$ E=38 GPa, nu=0.18, rho=2.3 g/cm^3
$$   -> K=19792 MPa, G_avg=16104 MPa
$$ Tg=270 C, Td=380 C
$$ CTE: xy=3.0 ppm/K (used), z=9.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Doosan DS-7409HG(I)
$      MID        RO      BULK        G0        GI      BETA
    100236 2.300e-09   19791.7   16345.0   15862.0    1200.0
$
$$ [DB] PID slot holds MID=100236 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100236         0 3.000e-06
$
$$ --- Doosan RAPIDON-10W (MID 100237) ---
$$ 고열전도 1.0 W/mK
$$ 용도: 스마트폰 HDI / PCB 제조용
$$ 출처: Doosan CCL TDS: RAPIDON-10W
$$
$$ E=15 GPa, nu=0.17, rho=2.0 g/cm^3
$$   -> K=7576 MPa, G_avg=6412 MPa
$$ Tg=200 C, Td=400 C
$$ CTE: xy=13.0 ppm/K (used), z=25.0 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.020x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.020
*MAT_VISCOELASTIC_TITLE
Doosan RAPIDON-10W
$      MID        RO      BULK        G0        GI      BETA
    100237 2.000e-09    7575.8    6539.7    6283.3    1000.0
$
$$ [DB] PID slot holds MID=100237 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100237         0 1.300e-05
$
$ ========================================================================
$ 3. Elite Material (EMC) — High Performance
$ ========================================================================
$
$$ --- Elite EM-370Z (MID 100301) ---
$$ 고 Tg 할로겐프리 고신뢰성 (automotive, power, heavy Cu)
$$ 용도: 고성능 HDI, 고주파, IC 패키징
$$ 출처: Elite EM-370Z TDS (2022 Nov / 2024 Jul)
$$
$$ E=24 GPa, nu=0.17, rho=1.88 g/cm^3
$$   -> K=12121 MPa, G_avg=10263 MPa
$$ Tg=210 C, Td=390 C
$$ CTE: xy=12.0 ppm/K (used), z=37.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.037x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.036
*MAT_VISCOELASTIC_TITLE
Elite EM-370Z
$      MID        RO      BULK        G0        GI      BETA
    100301 1.880e-09   12121.2   10632.3    9893.8    1000.0
$
$$ [DB] PID slot holds MID=100301 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100301         0 1.200e-05
$
$$ --- Elite EM-526 (MID 100302) ---
$$ 저손실 저CTE HDI/SiP용
$$ 용도: 고성능 HDI, 고주파, IC 패키징
$$ 출처: Elite EM-526 TDS (2021 Aug)
$$
$$ E=25 GPa, nu=0.17, rho=1.88 g/cm^3
$$   -> K=12626 MPa, G_avg=10685 MPa
$$ Tg=260 C, Td=430 C
$$ CTE: xy=9.5 ppm/K (used), z=27.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.015x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.015
*MAT_VISCOELASTIC_TITLE
Elite EM-526
$      MID        RO      BULK        G0        GI      BETA
    100302 1.880e-09   12626.3   10845.2   10524.7    1200.0
$
$$ [DB] PID slot holds MID=100302 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100302         0 9.500e-06
$
$$ --- Elite EM-528 (MID 100303) ---
$$ 고 Tg 매우 저손실 할로겐프리 (high-speed server/network)
$$ 용도: 고성능 HDI, 고주파, IC 패키징
$$ 출처: Elite EM-528 TDS (2024 Jul)
$$
$$ E=25 GPa, nu=0.17, rho=1.88 g/cm^3
$$   -> K=12626 MPa, G_avg=10685 MPa
$$ Tg=250 C, Td=420 C
$$ CTE: xy=9.5 ppm/K (used), z=27.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.014x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.014
*MAT_VISCOELASTIC_TITLE
Elite EM-528
$      MID        RO      BULK        G0        GI      BETA
    100303 1.880e-09   12626.3   10835.5   10534.2    1200.0
$
$$ [DB] PID slot holds MID=100303 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100303         0 9.500e-06
$
$$ --- Elite EM-892K (MID 100304) ---
$$ 고 Tg 극저손실 (112G, HPC/AI/5G 안테나)
$$ 용도: 고성능 HDI, 고주파, IC 패키징
$$ 출처: Elite EM-892K TDS (2024 Jul)
$$
$$ E=24.0 GPa, nu=0.17, rho=1.88 g/cm^3
$$   -> K=12121 MPa, G_avg=10257 MPa
$$ Tg=215 C, Td=420 C
$$ CTE: xy=12.5 ppm/K (used), z=42.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.010x, BETA=1000/s (tau=1.00ms)
$$ tan(delta) @ drop freq ~ 0.010
*MAT_VISCOELASTIC_TITLE
Elite EM-892K
$      MID        RO      BULK        G0        GI      BETA
    100304 1.880e-09   12121.2   10359.5   10154.4    1000.0
$
$$ [DB] PID slot holds MID=100304 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100304         0 1.250e-05
$
$$ --- Elite EM-S570 (MID 100305) ---
$$ 극저 CTE 고강성 (FC-CSP/BGA, PoP, SiP)
$$ 용도: 고성능 HDI, 고주파, IC 패키징
$$ 출처: Elite EM-S570 TDS (2024 Jul, Preliminary)
$$
$$ E=31 GPa, nu=0.17, rho=1.88 g/cm^3
$$   -> K=15657 MPa, G_avg=13250 MPa
$$ Tg=320 C, Td=440 C
$$ CTE: xy=5.0 ppm/K (used), z=10.5 ppm/K (ortho ref)
$$ Viscoelastic: G0/GI=1.018x, BETA=1200/s (tau=0.83ms)
$$ tan(delta) @ drop freq ~ 0.018
*MAT_VISCOELASTIC_TITLE
Elite EM-S570
$      MID        RO      BULK        G0        GI      BETA
    100305 1.880e-09   15656.6   13488.5   13011.5    1200.0
$
$$ [DB] PID slot holds MID=100305 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100305         0 5.000e-06
$
$ ========================================================================
$ END OF PCB PREPREG MATERIAL LIBRARY
$ ========================================================================
*END
