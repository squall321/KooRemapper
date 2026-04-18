$ ================================================================
$ Cu (Copper) Foil Material Library for PCB
$ ================================================================
$ Unit: mm, s, ton -> MPa, N, ton/mm^3
$ MID range: 100401~100404
$
$ Data sources (TDS = Technical Data Sheet / IPC standards):
$   [1] IPC-TM-650 2.4.18B: density (ED=8.909, Rolled=8.93 g/cc)
$   [2] Rogers Corporation TDS: Cu foil properties for HF materials
$   [3] IPC-4562A: Copper foil specification (rolled, ED, HTE, HVLP)
$   [4] Tensile strength & elongation values from ASTM E345
$
$ Young's modulus of Cu foil:
$   Bulk Cu: 117-130 GPa (isotropic polycrystalline)
$   Thin foil: 110-120 GPa (grain size effect)
$   Annealed (RA): ~115 GPa (larger grains, lower strength)
$   Electrodeposited (ED): ~117 GPa (columnar grains)
$   HTE: ~120 GPa (fine grain)
$
$ Poisson's ratio: 0.34 (bulk Cu)
$ CTE: 16.5~17.0 ppm/K (well-established)
$ Thermal conductivity: ~400 W/m.K (bulk), foil slightly lower
$
$ ================================================================
$
$ SUMMARY TABLE
$
$  MID    Name               E(GPa) rho(g/cc) YieldStr(MPa) TS(MPa) Elong(%)  CTE  Use
$  ----------------------------------------------------------------------------------------
$  100401 Cu_RA_Std           115    8.93     80            152     13       16.8 Flex PCB (FPC)
$  100402 Cu_ED_Std           117    8.909    220           276     3        16.8 Rigid PCB (표준)
$  100403 Cu_HTE              120    8.909    280           345     4        16.8 다층 고신뢰성
$  100404 Cu_HVLP             118    8.909    250           310     3.5      16.8 고주파/5G (low profile)
$
$ ================================================================
*KEYWORD
$
$
$ ================================================================
$ 1. Rolled Annealed (RA) Copper — 압연박
$ ================================================================
$
$$ --- Cu Rolled Annealed Standard (MID 100401) ---
$$ 압연 후 어닐링 처리한 연질 Cu 박. 고연신률, 유연성
$$ 용도: FPC, 폴더블 디스플레이, 플렉스 회로, 곡면 접합
$$ 제조사: Furukawa RX-2, JX Nippon BHYX, Mitsui RA foil
$$ 출처: IPC-TM-650 2.4.18B (rho=8.93 g/cc), Rogers TDS
$$
$$ Mechanical (1 oz / 35um):
$$   E = 115 GPa (resonance method, thin foil)
$$   nu = 0.34
$$   Yield = 80 MPa (낮음, 연함)
$$   Tensile = 152 MPa (22 kpsi, Rogers TDS)
$$   Elongation = 13% (Rogers TDS)
$$ Thermal:
$$   CTE = 16.8 ppm/K
$$   TC = 390 W/m.K (annealed = 거의 bulk)
$$   rho = 8.93 g/cc (IPC standard for rolled)
$$ 특징: 낮은 yield로 벤딩 반복성 우수
$*MAT_ELASTIC_TITLE
$Cu Rolled Annealed Standard (FPC grade)
$$      MID        RO         E        PR
$    100401 8.930e-09  115000.0    0.3400       0.0       0.0       0.0
$$
$$ Alt: use MAT_PIECEWISE_LINEAR_PLASTICITY (024) for plasticity
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Cu Rolled Annealed Standard (FPC grade)
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100401 8.930e-09  115000.0    0.3400      80.0    1000.0      0.13       0.0
$        C         P      LCSS      LCSR        VP
       0.0       0.0         0         0       0.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ [DB] PID slot holds MID=100401 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100401         0 1.680e-05
$
$
$ ================================================================
$ 2. Electrodeposited (ED) Copper — 전해박 (표준)
$ ================================================================
$
$$ --- Cu Electrodeposited Standard (MID 100402) ---
$$ 전해 증착 Cu 박. 높은 tensile strength, 표준 rigid PCB용
$$ 용도: FR-4 다층 PCB, 스마트폰 HDI, 메인보드, 서버 PCB
$$ 제조사: Furukawa FV (TAX), Oak-Mitsui TWX, Circuit Foil TWY
$$ 출처: IPC-TM-650 2.4.18B (rho=8.909 g/cc), Rogers TDS (1 oz)
$$
$$ Mechanical (1 oz / 35um, as-received):
$$   E = 117 GPa
$$   nu = 0.34
$$   Yield = 220 MPa (높은 항복강도)
$$   Tensile = 276 MPa (40 kpsi, Rogers TDS)
$$   Elongation = 3% (Rogers TDS, annealed 하지 않음)
$$ Thermal:
$$   CTE = 16.8 ppm/K
$$   TC = 380 W/m.K
$$   rho = 8.909 g/cc (IPC standard for ED)
$$ 특징: columnar grain, 높은 강도, 제한된 연신
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Cu Electrodeposited Standard (Rigid PCB)
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100402 8.909e-09  117000.0    0.3400     220.0    1800.0      0.03       0.0
$        C         P      LCSS      LCSR        VP
       0.0       0.0         0         0       0.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ [DB] PID slot holds MID=100402 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100402         0 1.680e-05
$
$
$ ================================================================
$ 3. HTE (High Temperature Elongation) — 고온 연신 ED
$ ================================================================
$
$$ --- Cu HTE (MID 100403) ---
$$ 고온 연신 Cu — 다층 프레스 중 변형 감소, 고신뢰성
$$ 용도: 다층 rigid PCB, 고온 공정, 오토모티브
$$ 제조사: Mitsui HTE, Furukawa F2-WS, Circuit Foil HS
$$ 출처: IPC-4562A, Rogers/Isola TDS
$$
$$ Mechanical (1 oz / 35um):
$$   E = 120 GPa (fine-grained)
$$   nu = 0.34
$$   Yield = 280 MPa
$$   Tensile = 345 MPa (50 kpsi, high strength)
$$   Elongation = 4-8% (180°C elongation 기준)
$$ Thermal:
$$   CTE = 16.8 ppm/K
$$   TC = 380 W/m.K
$$   rho = 8.909 g/cc
$$ 특징: 적층 공정 중 굴곡/파괴 저항 우수, TCT 사이클 신뢰성
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Cu HTE High Temperature Elongation
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100403 8.909e-09  120000.0    0.3400     280.0    2000.0      0.06       0.0
$        C         P      LCSS      LCSR        VP
       0.0       0.0         0         0       0.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ [DB] PID slot holds MID=100403 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100403         0 1.680e-05
$
$
$ ================================================================
$ 4. HVLP (Very High Low Profile) — 고주파 ED
$ ================================================================
$
$$ --- Cu HVLP (MID 100404) ---
$$ 극저 조도 ED Cu — 고주파 신호 손실 최소화
$$ 용도: 5G 밀리미터파, 25Gbps+ 디지털, 고주파 안테나
$$ 제조사: Mitsui MQ-VLP, Furukawa F1-WS-HVLP, Circuit Foil TWLP
$$ 출처: IPC-4562A, Rogers TDS (HVLP grade)
$$
$$ Mechanical (1 oz / 35um):
$$   E = 118 GPa
$$   nu = 0.34
$$   Yield = 250 MPa
$$   Tensile = 310 MPa (45 kpsi)
$$   Elongation = 3.5%
$$   Surface roughness Rz < 2 um (표준 ED 대비 극저)
$$ Thermal:
$$   CTE = 16.8 ppm/K
$$   TC = 390 W/m.K
$$ 특징: 표면조도 최소화로 skin effect 감소, 고주파 손실 개선
*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE
Cu HVLP Very High Low Profile
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
    100404 8.909e-09  118000.0    0.3400     250.0    1900.0      0.035      0.0
$        C         P      LCSS      LCSR        VP
       0.0       0.0         0         0       0.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ [DB] PID slot holds MID=100404 (external tool must replace with actual PART IDs)
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
    100404         0 1.680e-05
$
$ ================================================================
$ END OF Cu MATERIAL LIBRARY
$ ================================================================
*END
