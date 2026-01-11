# KooRemapper

**LS-DYNA K-file용 메쉬 매핑 도구**

KooRemapper는 평평한(flat) 메쉬를 구부러진(bent) 구조화 메쉬에 매핑하는 크로스 플랫폼 CLI 도구입니다. 폴더블 디스플레이, 곡면 구조물 등의 FEM 해석에서 상세한 메쉬를 복잡한 형상에 정확하게 매핑할 수 있습니다.

## 주요 기능

- **메쉬 매핑**: 평평한 비정형 메쉬를 구부러진 정형 메쉬에 매핑
- **언폴딩**: 구부러진 메쉬를 평평하게 펼친 메쉬 생성
- **예제 생성**: 테스트용 다양한 형상의 메쉬 생성
- **스트레인 계산**: 두 메쉬 간의 변형률 계산
- **메쉬 정보**: K-file의 메쉬 정보 및 품질 확인

---

## ⭐ 핵심 워크플로우: 두 가지 모드

KooRemapper는 **두 가지 핵심 모드**로 동작합니다:

### 모드 1: `unfold` - 레퍼런스 모델 펴기

구부러진(bent) 레퍼런스 메쉬를 평평하게(flat) 펼칩니다.

```
┌─────────────────┐                    ┌─────────────────┐
│   Bent Mesh     │      unfold        │   Flat Mesh     │
│   (레퍼런스)     │  ──────────────→   │   (펼쳐진 형상)  │
│   곡면 형상      │                    │   평면 형상      │
└─────────────────┘                    └─────────────────┘
```

```bash
KooRemapper unfold bent_reference.k unfolded_flat.k
```

### 모드 2: `map` - 상세 모델 벤딩

평평한(flat) 상세 메쉬를 구부러진(bent) 레퍼런스 형상으로 매핑합니다.

```
┌─────────────────┐
│   Bent Mesh     │ (레퍼런스 - 형상 정의)
│   (coarse)      │
└────────┬────────┘
         │
         │  + ┌─────────────────┐
         │    │   Flat Mesh     │ (상세 메쉬 - 매핑 대상)
         │    │   (fine)        │
         │    └────────┬────────┘
         │             │
         ▼      map    ▼
┌─────────────────────────────────┐
│        Mapped Mesh              │
│   (상세 메쉬가 bent 형상으로)    │
└─────────────────────────────────┘
```

```bash
KooRemapper map bent_reference.k flat_detailed.k result_mapped.k
```

### 전체 워크플로우 다이어그램

```
                                    ┌─────────────────┐
                                    │  CAD에서 생성한  │
                                    │  상세 Flat 메쉬  │
                                    │  (fine, 다층 등) │
                                    └────────┬────────┘
                                             │
┌─────────────────┐      unfold     ┌────────▼────────┐      map       ┌─────────────────┐
│   Bent Mesh     │ ──────────────→ │   Flat Mesh     │ ─────────────→ │  Mapped Mesh    │
│   (레퍼런스)     │    (선택적)     │   (참조용)       │   (필수)       │  (최종 결과)     │
│   정형 HEX8     │                 │   정형 HEX8     │                │  상세+곡면       │
└─────────────────┘                 └─────────────────┘                └─────────────────┘
        ▲                                   ▲
        │                                   │
        └───────────────────────────────────┘
                동일한 bounding box 범위
```

**사용 시나리오:**

| 시나리오 | 사용 모드 |
|----------|-----------|
| CAD에서 bent 형상만 있고, flat 메쉬가 필요할 때 | `unfold` |
| flat 상세 메쉬를 bent 형상으로 변환할 때 | `map` |
| 처음부터 끝까지 전체 워크플로우 | `unfold` → CAD 상세화 → `map` |

---

## 빌드

### 요구사항
- CMake 3.16 이상
- C++17 지원 컴파일러

### Windows
```cmd
cd KooRemapper
scripts\build_windows.bat
```

### Linux / macOS
```bash
cd KooRemapper
chmod +x scripts/build_linux.sh   # 또는 build_macos.sh
./scripts/build_linux.sh
```

빌드 결과물: `build/bin/Release/KooRemapper` (또는 `KooRemapper.exe`)

---

## 사용법

### 1. 메쉬 매핑 (`map`)

평평한 메쉬를 구부러진 참조 메쉬에 매핑합니다.

```bash
KooRemapper map <bent_mesh> <flat_mesh> <output>
```

**인자:**
- `bent_mesh`: 구부러진 정형 참조 메쉬 (HEX8, K-file)
- `flat_mesh`: 매핑할 평평한 메쉬 (K-file)
- `output`: 출력 파일 경로

**예제:**
```bash
# arc30 예제: 30도 곡률 아크에 상세 메쉬 매핑
KooRemapper map examples/arc30/arc30_bent.k examples/arc30/arc30_flat_fine.k result.k

# 폴더블 디스플레이: U자형 접힘에 상세 메쉬 매핑
KooRemapper map examples/foldable_display/foldable_bent.k examples/foldable_display/foldable_flat_fine.k result.k
```

**출력 예시:**
```
[INFO] Loading bent mesh: arc30_bent.k
[OK] Loaded 924 nodes, 600 elements
[INFO] Loading flat mesh: arc30_flat_fine.k
[OK] Loaded 6027 nodes, 4800 elements
[INFO] Performing mesh mapping...
[OK] Mapping completed successfully

Mapping Statistics
------------------
Nodes processed:         6027
Elements processed:      4800
Min Jacobian:            5.449568
Max Jacobian:            7.627045
Processing time:         9.29 ms
```

---

### 2. 메쉬 언폴딩 (`unfold`)

구부러진 정형 메쉬를 평평하게 펼친 메쉬를 생성합니다.

```bash
KooRemapper unfold <bent_mesh> <output_flat>
```

**인자:**
- `bent_mesh`: 구부러진 정형 메쉬 (HEX8, K-file)
- `output_flat`: 출력할 평평한 메쉬 파일

**예제:**
```bash
KooRemapper unfold examples/arc30/arc30_bent.k arc30_unfolded.k
```

**설명:**
- 중심선(centerline)을 따라 arc-length를 계산하여 X 좌표 결정
- 단면(cross-section) 크기를 Y, Z 좌표에 보존
- 생성된 평평한 메쉬는 상세 메쉬 매핑의 참조로 사용 가능

---

### 3. 예제 메쉬 생성 (`generate`)

테스트용 예제 메쉬를 생성합니다.

```bash
KooRemapper generate [options] <type> <output_prefix>
```

**메쉬 타입:**
| 타입 | 설명 |
|------|------|
| `teardrop` | 물방울 형상 |
| `arc` | 단순 곡률 아크 |
| `scurve` | S자 곡선 |
| `helix` | 나선형 |
| `torus` | 토러스 (도넛) |
| `twist` | 비틀림 |
| `bendtwist` | 굽힘 + 비틀림 |
| `wave` | 파형 |
| `bulge` | 부풀림 |
| `taper` | 테이퍼 |
| `waterdrop` | 폴더블 디스플레이 (U-fold) |

**옵션:**
- `--dim-i <n>`: I 방향 요소 수 (기본: 10)
- `--dim-j <n>`: J 방향 요소 수 (기본: 5)
- `--dim-k <n>`: K 방향 요소 수 (기본: 5)

**예제:**
```bash
# 기본 arc 메쉬 생성
KooRemapper generate arc myarc

# 20x10x5 해상도의 waterdrop 메쉬 생성
KooRemapper generate --dim-i 20 --dim-j 10 --dim-k 5 waterdrop foldable

# 출력 파일:
#   foldable_bent.k      - 구부러진 메쉬
#   foldable_flat.k      - 평평한 메쉬 (매핑 참조용)
#   foldable_flat_fine.k - 상세 평평한 메쉬 (매핑 대상)
```

---

### 4. 스트레인 계산 (`strain`)

두 메쉬 간의 변형률(strain)을 계산합니다.

```bash
KooRemapper strain [options] <ref_mesh> <def_mesh> <output.csv>
```

**인자:**
- `ref_mesh`: 참조(변형 전) 메쉬
- `def_mesh`: 변형된 메쉬
- `output.csv`: 스트레인 데이터 출력 CSV 파일

**옵션:**
- `--type <t>`: 스트레인 타입
  - `engineering` (기본): 공학적 스트레인
  - `green`: Green-Lagrange 스트레인
  - `log`: 로그 스트레인

**예제:**
```bash
KooRemapper strain examples/foldable_display/foldable_flat.k examples/foldable_display/foldable_bent.k strain.csv
KooRemapper strain --type green ref.k deformed.k green_strain.csv
```

---

### 5. 메쉬 정보 (`info`)

K-file의 메쉬 정보와 요소 품질을 확인합니다.

```bash
KooRemapper info <mesh_file>
```

**예제:**
```bash
KooRemapper info examples/arc30/arc30_bent.k
```

**출력 예시:**
```
Mesh Information: arc30_bent.k
==============================
Nodes:                   924
Elements:                600
Min bound:               (-0.008, 10.0, -10.0)
Max bound:               (60.0, 50.0, 10.0)
Size:                    (60.0, 40.0, 20.0)

Element Quality
---------------
Min Jacobian:            5.449568
Max Jacobian:            7.627045
[OK] All elements have positive Jacobian
```

---

## 워크플로우 예제

### 폴더블 디스플레이 해석

1. **예제 메쉬 생성** (또는 기존 CAD 메쉬 사용)
   ```bash
   KooRemapper generate --dim-i 50 --dim-j 10 --dim-k 5 waterdrop foldable
   ```

2. **상세 평평한 메쉬 준비**
   - CAD에서 상세 메쉬 생성 (예: 다층 구조, 미세 피처)
   - 또는 기존 `foldable_flat_fine.k` 사용

3. **메쉬 매핑 실행**
   ```bash
   KooRemapper map foldable_bent.k my_detailed_flat.k final_model.k
   ```

4. **결과 검증**
   ```bash
   KooRemapper info final_model.k
   ```

5. **LS-DYNA 해석 실행**
   - `final_model.k`를 LS-DYNA에서 해석

---

## 기술 세부사항

### 지원 요소 타입

| 메쉬 역할 | HEX8 (육면체) | TET4 (사면체) |
|-----------|---------------|---------------|
| **Bent (레퍼런스)** | ✅ 필수 (정형 그리드) | ❌ 미지원 |
| **Flat (매핑 대상)** | ✅ 지원 | ✅ 지원 |

**중요**: Bent 메쉬는 반드시 **정형 구조화 HEX8 메쉬**여야 합니다.
- 비정형 메쉬(TET4)를 bent 메쉬로 사용하면 에러 발생
- 정형 그리드가 아닌 HEX8 메쉬도 에러 발생

### 매핑 알고리즘
1. **정형 그리드 분석**: bent 메쉬의 (i, j, k) 인덱스 구조 추출
2. **Edge Arc-length 계산**: 12개 edge의 실제 arc-length 계산
3. **파라메트릭 좌표 변환**: flat 메쉬 좌표를 (u, v, w) ∈ [0,1]³로 변환
4. **Transfinite 보간**: arc-length 기반 edge 보간으로 bent 위치 계산

### 품질 검증
- **Jacobian 체크**: 모든 요소의 Jacobian이 양수인지 확인
- **Bounding Box 일치**: 원본 bent 메쉬와 매핑 결과의 경계 일치 확인
- **Corner 노드 정합성**: 코너 노드 위치의 정확한 일치 확인

---

## 예제 파일

`examples/` 폴더에 다양한 테스트 예제 포함:

| 폴더 | 설명 |
|------|------|
| `arc30/` | 30도 곡률 아크 |
| `foldable_display/` | 폴더블 디스플레이 (U-fold) |
| `torus/` | 토러스 형상 |
| `twist/` | 비틀림 형상 |
| `wave/` | 파형 형상 |
| `bendtwist/` | 굽힘+비틀림 복합 |
| `bulge/` | 부풀림 형상 |
| `taper/` | 테이퍼 형상 |

---

## 라이선스

MIT License

## 버전

v1.0.0 (2026-01-11)

