# Material DB Viewer v2 종합 개선 계획

## Phase 1: 데이터 인프라 (Data Infrastructure)

### 1-A. ETAN 추출 → mechanical dict 반영
- **현황**: 171개 재료가 card text에 ETAN>0 값을 갖고 있으나, `mechanical` dict에는 0으로 기록
- **작업**: `build_material_db.py`의 MAT_024 파서에서 ETAN 필드(Card 2, Field 5) 추출 → `mechanical.ETAN` 키로 저장
- **효과**: Viewer에서 card text 파싱 없이 직접 stress-strain 그래프 생성 가능, 검색/필터에도 활용

### 1-B. Thermal TDS 데이터 확보 및 확장

**현황 분석 (k_SI / Cp_SI 부재율)**:

| Category | Total | Missing k/Cp | Coverage |
|----------|-------|-------------|----------|
| ceramic | 22 | 22 | 0% |
| display | 18 | 18 | 0% |
| magnet | 12 | 12 | 0% |
| semiconductor | 18 | 18 | 0% |
| pcb | 81 | 81 | 0% |
| tape | 34 | 34 | 0% |
| metal | 171 | 160 | 6% |
| polymer | 106 | 90 | 15% |
| rubber | 45 | 42 | 7% |
| glass | 17 | 16 | 6% |
| composite | 1 | 0 | 100% |
| **Total** | **525** | **493** | **6%** |

**TDS 소싱 전략 (우선순위순)**:

#### Tier 1 — 핸드북 일괄 반영 (즉시 가능, ~250개)
- **metal (160개)**: ASM Handbook / MatWeb 기준값. Al6061→167 W/m·K, 896 J/kg·K 등 합금별 표준값 확보 용이
- **glass (16개)**: Corning GorillaGlass TDS + 일반 유리 핸드북값 (k≈1.0, Cp≈840)
- **rubber (42개)**: 실리콘/EPDM/NBR 등 generic 범위값 (k≈0.15-0.30, Cp≈1000-2000)
- **소스**: MatWeb, ASM International, CRC Handbook of Chemistry and Physics
- **정확도**: ±10-15% (합금 조성 변동분)

#### Tier 2 — 제조사 TDS 개별 확보 (~130개)
- **tape (34개)**: 3M, Nitto Denko, tesa TDS 확보 (VHB, Kapton 등 제품 라인별)
- **polymer (90개)**: 수지별 BASF/DuPont/Sabic TDS (PA66-GF30, POM, PBT 등)
- **magnet (12개)**: TDK/Murata/Samsung Electro-Mechanics TDS (NdFeB, Ferrite 등)
- **소스**: 제조사 웹사이트 TDS PDF, 대리점 요청
- **정확도**: ±5% (제조사 공시값)

#### Tier 3 — 전문 문헌 참조 (~110개)
- **ceramic (22개)**: BaTiO3 MLCC → 공개 논문값 (k≈2.5-3.5, Cp≈430-500), Al2O3 기판 등
- **semiconductor (18개)**: Si wafer (k=148), molding compound (k≈0.6-0.8) 등 반도체 패키지 자료
- **pcb (81개)**: FR-4 표준값 (k≈0.3 in-plane, Cp≈1100), flex PI (k≈0.12)
- **display (18개)**: OLED/LCD 적층별 실측 논문값 (polarizer, glass substrate 등)
- **소스**: IEEE/ECTC 컨퍼런스 논문, JEDEC 표준, Ansys/Siemens 라이브러리
- **정확도**: ±15-25% (적층/두께 의존성 높음)

**데이터 입력 워크플로**:
```
1. TDS/문헌 확보 → Excel 정리 (name, k_SI, Cp_SI, source, accuracy)
2. materials/Materials/{category}/{category}_thermal.k 에 반영
   - 기존 9개 thermal k-file 확장 + 신규 category별 파일 생성
3. python scripts/build_material_db.py → material_db.json 재빌드
4. Viewer에서 thermal coverage 확인 (gap report 자동 생성)
```

**검증**:
- 단위 일관성 체크: W/m·K (k_SI), J/kg·K (Cp_SI)
- 범위 체크: k < 0.01 or k > 500 → 경고, Cp < 100 or Cp > 5000 → 경고
- Cross-check: 동일 카테고리 내 이상치 자동 플래그

---

## Phase 2: Viewer Core UX

### 2-A. Variant Grouping (접을 수 있는 그룹)
- **현황**: 525개 재료 중 309개가 94개 그룹에 속함, 216개는 단독 → 접으면 310개 항목
- **7가지 variant suffix**: Bilinear(62), Multilinear(62), Kinematic Mixed(61), Linear(49), Kinematic Pure(41), Elastic+Erode(31), Rigid(1)
- **구현**:
  - Sidebar에서 그룹 대표명 표시 + 접기/펼치기 토글
  - 그룹 헤더: base name + badge (x7 variants)
  - 펼치면 하위 variant를 indent + suffix chip으로 표시
  - build_material_db.py에 variant_group 필드 추가 또는 Viewer에서 런타임 그룹핑

### 2-B. Search Highlight
- 검색어 입력 시 sidebar 목록에서 매칭 부분 mark 태그로 하이라이트
- Detail 패널에서도 name/category/tags에 하이라이트 적용

### 2-C. URL Hash Deep Link
- `#mid=100535` → 페이지 로드 시 해당 MID 자동 선택 + 스크롤
- `#mid=100535&compare=100503` → 비교 모드 자동 진입
- `#cat=metal` → 카테고리 필터 자동 적용
- history.pushState로 탐색 시 URL 자동 갱신

---

## Phase 3: 시각화 확장 (Visualization)

### 3-A. Ashby Plot (E vs rho Scatter)
- 전체 재료를 E vs rho 산점도에 표시 (로그-로그 축)
- 카테고리별 색상 구분
- 클릭 시 해당 재료 상세 이동, 선택 재료 강조
- 등고선 가이드: E/rho = const (비강성), E^(1/2)/rho = const (경량 설계)

### 3-B. Unit System Toggle
- 기본: LS-DYNA 단위 (ton/mm/s → MPa, ton/mm3)
- 토글: SI 공학 단위 (GPa, g/cm3, W/m·K)
- Topbar에 토글 스위치, 전환 시 모든 숫자/차트 실시간 갱신

---

## Phase 4: Export & 공유

### 4-A. Compare 결과 Export
- CSV: 비교 테이블 그대로 CSV 다운로드 (A vs B, 절대값 + %diff)
- PNG: html2canvas로 비교 패널 캡처, Chart.js toBase64Image() 개별 차트 PNG

### 4-B. 단일 재료 Export
- 현재 Copy/Download .k는 구현 완료
- 추가: 재료 속성 요약 카드 PNG 다운로드 (보고서 삽입용)

---

## 실행 타임라인

| Phase | 작업 | 의존성 | 예상 규모 |
|-------|------|--------|----------|
| **1-A** | ETAN → mechanical dict | 없음 | build_material_db.py 수정 + DB 재빌드 |
| **1-B Tier1** | Metal/Glass/Rubber thermal | 없음 | thermal k-file 3개 확장 (~250 entries) |
| **1-B Tier2** | Tape/Polymer/Magnet thermal | TDS 확보 | thermal k-file 3개 신규 (~130 entries) |
| **1-B Tier3** | Ceramic/Semi/PCB/Display thermal | 문헌 조사 | thermal k-file 4개 신규 (~110 entries) |
| **2-A** | Variant grouping | 1-A | index.html 대규모 수정 |
| **2-B** | Search highlight | 없음 | index.html 소규모 수정 |
| **2-C** | URL deep link | 없음 | index.html 소규모 수정 |
| **3-A** | Ashby plot | 없음 | Chart.js scatter 추가 |
| **3-B** | Unit toggle | 없음 | 전역 변환 레이어 |
| **4-A** | Export CSV/PNG | 2-A | html2canvas + CSV 생성 |

**권장 실행 순서**: 1-A → 2-B/2-C → 2-A → 3-A → 3-B → 4-A → 1-B (Tier1→2→3 병행)
