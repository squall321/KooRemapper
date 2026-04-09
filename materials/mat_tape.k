$$ ================================================================
$$ SMARTPHONE ADHESIVE TAPE MATERIAL LIBRARY
$$ ================================================================
$$ Unit: mm, s, ton -> MPa, N, ton/mm³
$$ MID: 100001 ~ 100020 (20 types)
$$ Model: *MAT_VISCOELASTIC (MAT_006), single Maxwell
$$
$$ G(t) = GI + (G0 - GI) * exp(-BETA * t)
$$   G0   = instantaneous shear modulus
$$   GI   = equilibrium shear modulus
$$   BETA = 1/tau (decay constant)
$$   BULK = elastic bulk modulus (volumetric)
$$
$$ References:
$$   [1] PMC 8879156 - OCA mechanical characterization
$$   [2] PMC 6835935 - TPU PSA viscoelastic blends
$$   [3] PMC 10537401 - Acrylic PSA rheological properties
$$   [4] oaepublish ss.2024.22 - OCA for flexible display
$$   [5] 3M VHB Technical Data (stockwell.com)
$$
$$ ================================================================
$$
$$ SUMMARY TABLE
$$
$$  MID     Name                    G0     GI   BETA   tau    BULK   tan(d)  App
$$  ─────────────────────────────────────────────────────────────────────────────
$$  100001  OCA_RIGID_STANDARD        0.15  0.015     50   20.0ms  2000   1.42   커버글라스-LCD/OLED
$$  100002  OCA_RIGID_HIGH_BOND       0.25  0.030     80   12.5ms  2200   1.27   Gorilla Glass-OLED
$$  100003  OCA_FOLDABLE              0.05  0.010     20   50.0ms  2000   0.89   Galaxy Fold/Flip 힌지
$$  100004  OCA_ROLLABLE              0.03  0.005     10  100.0ms  1800   1.02   LG Rollable TV
$$  100005  OCA_UV_CURED              0.40  0.050    150    6.7ms  2500   1.24   고해상도 디스플레이
$$  100006  PSA_ACRYLIC_GENERAL       0.30  0.050    100   10.0ms  2500   1.02   FPC-메인보드
$$  100007  PSA_SILICONE_HIGHTEMP     0.08  0.020     30   33.3ms  1500   0.75   배터리 인접부
$$  100008  PSA_HIGH_SHEAR            0.50  0.100    200    5.0ms  2800   0.89   카메라모듈 고정
$$  100009  PSA_REMOVABLE             0.05  0.008     30   33.3ms  1800   1.05   스크린 프로텍터
$$  100010  VHB_CLEAR_THIN            0.10  0.010     30   33.3ms   500   1.42   후면 커버 접합
$$  100011  VHB_BLACK_THICK           0.08  0.008     25   40.0ms   350   1.42   배터리 마운팅
$$  100012  FOAM_PE_GENERAL           0.05  0.005     20   50.0ms   200   1.42   프레임-후면커버
$$  100013  FOAM_PU_IMPACT            0.15  0.010     40   25.0ms   300   1.81   디스플레이 쿠션
$$  100014  BATTERY_STRETCH_RELEASE   0.50  0.100    200    5.0ms  1800   0.89   배터리 교체 가능 설계
$$  100015  BATTERY_PERMANENT         0.35  0.080    120    8.3ms  2000   0.81   배터리 스웰링 저항
$$  100016  THERMAL_INTERFACE_TAPE    0.60  0.100    300    3.3ms  3000   1.02   히트스프레더-미드프레임
$$  100017  WATERPROOF_GASKET         0.20  0.030     60   16.7ms  2200   1.10   디스플레이-프레임 방수씰
$$  100018  WATERPROOF_BUTYL          0.25  0.005     40   25.0ms  1500   3.46   스피커 방수
$$  100019  DAMPING_SPEAKER           0.30  0.010     80   12.5ms  1800   2.65   스피커-프레임
$$  100020  DAMPING_HAPTIC            0.20  0.003     50   20.0ms  1200   4.02   LRA/ERM 모터 마운팅
$$
$$ ================================================================
*KEYWORD
$
$
$$ ================================================================
$$ 1. OCA (Optically Clear Adhesive) — 디스플레이 접합
$$ ================================================================
$
$$ --- OCA_RIGID_STANDARD (MID 100001) ---
$$ 일반 OCA — rigid 디스플레이 접합 (3M 8171/8212 계열)
$$ 용도: 커버글라스-LCD/OLED, 터치패널 접합
$$ 두께: 50~175 um
$$ 출처: PMC 8879156: G0=150kPa, GI=16kPa at 30°C
$$ E_inst=0.45MPa E_equil=0.045MPa tau=20.0ms
$$ tan(d)=1.42 M=2000MPa G0/GI=10x
*MAT_VISCOELASTIC_TITLE
OCA Rigid Standard (3M 8171)
$      MID        RO      BULK        G0        GI      BETA
    100001 1.050e-09    2000.0    0.1500    0.0150      50.0
$
$$ --- OCA_RIGID_HIGH_BOND (MID 100002) ---
$$ 고접착 OCA — 강화유리 접합, 높은 유지력
$$ 용도: Gorilla Glass-OLED, 높은 전단 저항 필요
$$ 두께: 100~200 um
$$ 출처: 가교밀도 높은 아크릴 OCA, G' 증가
$$ E_inst=0.75MPa E_equil=0.090MPa tau=12.5ms
$$ tan(d)=1.27 M=2200MPa G0/GI=8x
*MAT_VISCOELASTIC_TITLE
OCA Rigid High Bond
$      MID        RO      BULK        G0        GI      BETA
    100002 1.080e-09    2200.0    0.2500    0.0300      80.0
$
$$ --- OCA_FOLDABLE (MID 100003) ---
$$ 폴더블 OCA — 폴더블폰 힌지영역 (Tg<-30°C)
$$ 용도: Galaxy Fold/Flip 힌지, 반복 굽힘
$$ 두께: 25~50 um
$$ 출처: oaepublish ss.2024.22: G'~10kPa at RT
$$ E_inst=0.15MPa E_equil=0.030MPa tau=50.0ms
$$ tan(d)=0.89 M=2000MPa G0/GI=5x
*MAT_VISCOELASTIC_TITLE
OCA Foldable (Tg<-30C)
$      MID        RO      BULK        G0        GI      BETA
    100003 1.050e-09    2000.0    0.0500    0.0100      20.0
$
$$ --- OCA_ROLLABLE (MID 100004) ---
$$ 롤러블 OCA — 롤러블 디스플레이용 극유연
$$ 용도: LG Rollable TV, 롤러블폰 컨셉
$$ 두께: 25~50 um
$$ 출처: oaepublish: Tg<-40°C, G'<10kPa, recovery>85%
$$ E_inst=0.09MPa E_equil=0.015MPa tau=100.0ms
$$ tan(d)=1.02 M=1800MPa G0/GI=6x
*MAT_VISCOELASTIC_TITLE
OCA Rollable (Tg<-40C)
$      MID        RO      BULK        G0        GI      BETA
    100004 1.030e-09    1800.0    0.0300    0.0050      10.0
$
$$ --- OCA_UV_CURED (MID 100005) ---
$$ UV경화 OCA — 접합 후 UV 경화로 강성 증가
$$ 용도: 고해상도 디스플레이, 광학 정밀 접합
$$ 두께: 25~100 um
$$ 출처: UV 가교 후 G' 증가, BULK 상승
$$ E_inst=1.20MPa E_equil=0.150MPa tau=6.7ms
$$ tan(d)=1.24 M=2501MPa G0/GI=8x
*MAT_VISCOELASTIC_TITLE
OCA UV Cured
$      MID        RO      BULK        G0        GI      BETA
    100005 1.100e-09    2500.0    0.4000    0.0500     150.0
$
$$ ================================================================
$$ PSA Thin Film — FPC/부품 접합
$$ ================================================================
$
$$ --- PSA_ACRYLIC_GENERAL (MID 100006) ---
$$ 범용 아크릴 PSA — FPC, 보강판 접합
$$ 용도: FPC-메인보드, 보강판, 차폐필름 접합
$$ 두께: 10~50 um
$$ 출처: PMC 10537401: E=0.45MPa, Tg=-40°C, v=0.499
$$ E_inst=0.90MPa E_equil=0.150MPa tau=10.0ms
$$ tan(d)=1.02 M=2500MPa G0/GI=6x
*MAT_VISCOELASTIC_TITLE
PSA Acrylic General (3M 467MP)
$      MID        RO      BULK        G0        GI      BETA
    100006 1.100e-09    2500.0    0.3000    0.0500     100.0
$
$$ --- PSA_SILICONE_HIGHTEMP (MID 100007) ---
$$ 실리콘 PSA — 고온 안정성 (Tg<-100°C)
$$ 용도: 배터리 인접부, 열원 주변 접합
$$ 두께: 25~75 um
$$ 출처: 실리콘 PSA: 넓은 온도범위, 낮은 G'
$$ E_inst=0.24MPa E_equil=0.060MPa tau=33.3ms
$$ tan(d)=0.75 M=1500MPa G0/GI=4x
*MAT_VISCOELASTIC_TITLE
PSA Silicone High-Temp
$      MID        RO      BULK        G0        GI      BETA
    100007 1.150e-09    1500.0    0.0800    0.0200      30.0
$
$$ --- PSA_HIGH_SHEAR (MID 100008) ---
$$ 고전단 PSA — 높은 유지력, 구조접합 보조
$$ 용도: 카메라모듈 고정, 커넥터 접합, 진동 부위
$$ 두께: 25~100 um
$$ 출처: 고가교 아크릴: Nitto 5000계열 수준
$$ E_inst=1.50MPa E_equil=0.300MPa tau=5.0ms
$$ tan(d)=0.89 M=2801MPa G0/GI=5x
*MAT_VISCOELASTIC_TITLE
PSA High Shear (Nitto 5000)
$      MID        RO      BULK        G0        GI      BETA
    100008 1.120e-09    2800.0    0.5000    0.1000     200.0
$
$$ --- PSA_REMOVABLE (MID 100009) ---
$$ 재작업용 PSA — 수리 시 분리 가능
$$ 용도: 스크린 프로텍터, 임시 고정, 검사용
$$ 두께: 10~25 um
$$ 출처: 저가교 아크릴: 낮은 peel/shear, 재탈착
$$ E_inst=0.15MPa E_equil=0.024MPa tau=33.3ms
$$ tan(d)=1.05 M=1800MPa G0/GI=6x
*MAT_VISCOELASTIC_TITLE
PSA Removable
$      MID        RO      BULK        G0        GI      BETA
    100009 1.050e-09    1800.0    0.0500    0.0080      30.0
$
$$ ================================================================
$$ VHB/Foam Tape — 구조 접합
$$ ================================================================
$
$$ --- VHB_CLEAR_THIN (MID 100010) ---
$$ 3M VHB 투명 (4905) — 0.5mm 얇은 폼
$$ 용도: 후면 커버 접합, 투명 구조접합
$$ 두께: 500 um
$$ 출처: PMC 6835935: G'~50kPa@100rad/s, Tg=-36°C
$$ E_inst=0.30MPa E_equil=0.030MPa tau=33.3ms
$$ tan(d)=1.42 M=500MPa G0/GI=10x
*MAT_VISCOELASTIC_TITLE
VHB Clear 0.5mm (3M 4905)
$      MID        RO      BULK        G0        GI      BETA
    100010 9.600e-10     500.0    0.1000    0.0100      30.0
$
$$ --- VHB_BLACK_THICK (MID 100011) ---
$$ 3M VHB 블랙 (5952) — 1.1mm 두꺼운 폼
$$ 용도: 배터리 마운팅, 진동 흡수, 갭 충진
$$ 두께: 1100 um
$$ 출처: VHB 5952: 낮은 밀도(720kg/m3), 높은 접착
$$ E_inst=0.24MPa E_equil=0.024MPa tau=40.0ms
$$ tan(d)=1.42 M=350MPa G0/GI=10x
*MAT_VISCOELASTIC_TITLE
VHB Black 1.1mm (3M 5952)
$      MID        RO      BULK        G0        GI      BETA
    100011 7.200e-10     350.0    0.0800    0.0080      25.0
$
$$ --- FOAM_PE_GENERAL (MID 100012) ---
$$ PE 폼 양면테이프 — 범용 구조접합
$$ 용도: 프레임-후면커버, 스피커 가스켓
$$ 두께: 200~500 um
$$ 출처: PE폼: 밀도 500kg/m3, 매우 낮은 BULK
$$ E_inst=0.15MPa E_equil=0.015MPa tau=50.0ms
$$ tan(d)=1.42 M=200MPa G0/GI=10x
*MAT_VISCOELASTIC_TITLE
Foam PE General
$      MID        RO      BULK        G0        GI      BETA
    100012 5.000e-10     200.0    0.0500    0.0050      20.0
$
$$ --- FOAM_PU_IMPACT (MID 100013) ---
$$ PU 폼테이프 — 충격 흡수, 진동 절연
$$ 용도: 디스플레이 쿠션, 카메라 충격 보호
$$ 두께: 100~300 um
$$ 출처: PU폼: 중간 밀도, 적절한 반발탄성
$$ E_inst=0.45MPa E_equil=0.030MPa tau=25.0ms
$$ tan(d)=1.81 M=300MPa G0/GI=15x
*MAT_VISCOELASTIC_TITLE
Foam PU Impact Absorber
$      MID        RO      BULK        G0        GI      BETA
    100013 6.000e-10     300.0    0.1500    0.0100      40.0
$
$$ ================================================================
$$ Battery/Special — 배터리/특수
$$ ================================================================
$
$$ --- BATTERY_STRETCH_RELEASE (MID 100014) ---
$$ 배터리 탈착 테이프 (SIS 블록공중합체)
$$ 용도: 배터리 교체 가능 설계, stretch-release
$$ 두께: 50~200 um
$$ 출처: SIS: PS경질+PI연질 block copolymer
$$ E_inst=1.50MPa E_equil=0.300MPa tau=5.0ms
$$ tan(d)=0.89 M=1801MPa G0/GI=5x
*MAT_VISCOELASTIC_TITLE
Battery Stretch-Release (SIS)
$      MID        RO      BULK        G0        GI      BETA
    100014 1.000e-09    1800.0    0.5000    0.1000     200.0
$
$$ --- BATTERY_PERMANENT (MID 100015) ---
$$ 배터리 영구접합 테이프 — 강한 유지력
$$ 용도: 배터리 스웰링 저항, 낙하 시 이탈 방지
$$ 두께: 100~300 um
$$ 출처: 고접착 아크릴, 높은 정적 전단 저항
$$ E_inst=1.05MPa E_equil=0.240MPa tau=8.3ms
$$ tan(d)=0.81 M=2000MPa G0/GI=4x
*MAT_VISCOELASTIC_TITLE
Battery Permanent Bond
$      MID        RO      BULK        G0        GI      BETA
    100015 1.050e-09    2000.0    0.3500    0.0800     120.0
$
$$ --- THERMAL_INTERFACE_TAPE (MID 100016) ---
$$ 열전도 양면테이프 — AP/SoC 방열
$$ 용도: 히트스프레더-미드프레임, 열관리
$$ 두께: 50~150 um
$$ 출처: 필러충진 실리콘/아크릴: 높은 밀도, 높은 BULK
$$ E_inst=1.80MPa E_equil=0.300MPa tau=3.3ms
$$ tan(d)=1.02 M=3001MPa G0/GI=6x
*MAT_VISCOELASTIC_TITLE
Thermal Interface Tape
$      MID        RO      BULK        G0        GI      BETA
    100016 2.000e-09    3000.0    0.6000    0.1000     300.0
$
$$ ================================================================
$$ Waterproof/Gasket — 방수/기밀
$$ ================================================================
$
$$ --- WATERPROOF_GASKET (MID 100017) ---
$$ 방수 가스켓 테이프 — IP67/68 등급
$$ 용도: 디스플레이-프레임 방수씰, SIM트레이
$$ 두께: 100~300 um
$$ 출처: 변성 아크릴: 내수성, 중간 접착력
$$ E_inst=0.60MPa E_equil=0.090MPa tau=16.7ms
$$ tan(d)=1.10 M=2200MPa G0/GI=7x
*MAT_VISCOELASTIC_TITLE
Waterproof Gasket IP68
$      MID        RO      BULK        G0        GI      BETA
    100017 1.150e-09    2200.0    0.2000    0.0300      60.0
$
$$ --- WATERPROOF_BUTYL (MID 100018) ---
$$ 부틸 방수테이프 — 극한 내수/기밀
$$ 용도: 스피커 방수, 마이크 기밀
$$ 두께: 50~200 um
$$ 출처: 부틸고무: Tg~-70°C, 극한 기밀성
$$ E_inst=0.75MPa E_equil=0.015MPa tau=25.0ms
$$ tan(d)=3.46 M=1500MPa G0/GI=50x
*MAT_VISCOELASTIC_TITLE
Waterproof Butyl Seal
$      MID        RO      BULK        G0        GI      BETA
    100018 1.300e-09    1500.0    0.2500    0.0050      40.0
$
$$ ================================================================
$$ Damping — 진동/감쇠
$$ ================================================================
$
$$ --- DAMPING_SPEAKER (MID 100019) ---
$$ 스피커 마운팅 감쇠 테이프
$$ 용도: 스피커-프레임, 레시버-하우징
$$ 두께: 50~150 um
$$ 출처: 감쇠 최적화 아크릴: tan(d)~1.4
$$ E_inst=0.90MPa E_equil=0.030MPa tau=12.5ms
$$ tan(d)=2.65 M=1800MPa G0/GI=30x
*MAT_VISCOELASTIC_TITLE
Damping Speaker Mount
$      MID        RO      BULK        G0        GI      BETA
    100019 1.200e-09    1800.0    0.3000    0.0100      80.0
$
$$ --- DAMPING_HAPTIC (MID 100020) ---
$$ 진동모터(햅틱) 절연 테이프
$$ 용도: LRA/ERM 모터 마운팅, 진동 전달 차단
$$ 두께: 100~300 um
$$ 출처: 고감쇠 부틸/아크릴 블렌드
$$ E_inst=0.60MPa E_equil=0.009MPa tau=20.0ms
$$ tan(d)=4.02 M=1200MPa G0/GI=67x
*MAT_VISCOELASTIC_TITLE
Damping Haptic Isolator
$      MID        RO      BULK        G0        GI      BETA
    100020 1.250e-09    1200.0    0.2000    0.0030      50.0
$
$$ ================================================================
$$ END OF TAPE MATERIAL LIBRARY
$$ ================================================================
*END
