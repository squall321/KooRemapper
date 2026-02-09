# KooRemapper

**LS-DYNA K-file용 메쉬 매핑 및 응력 분석 도구**

KooRemapper는 평평한(flat) 메쉬를 구부러진(bent) 구조화 메쉬에 매핑하고, 변형에 따른 초기 응력을 계산하는 크로스 플랫폼 CLI 도구입니다.

## 주요 기능

- **메쉬 매핑 (`map`)**: 디테일 플랫 → 디테일 벤트 (HEX8 정형 레퍼런스)
- **쉘 기반 매핑 (`shellmap`)**: QUAD4 쉘 레퍼런스로 매핑 (비정형 가능, CAD 쉘 직접 사용)
- **레퍼런스 생성 (`generate-var`)**: 심플 벤트/플랫 레퍼런스 생성
  - 곡선 메쉬: 사용자 정의 2D centerline 기반
  - 가변 밀도 메쉬: 영역별 요소 밀도 제어
- **언폴딩 (`unfold`)**: 벤트 → 플랫 (arc-length 기반)
- **응력 계산 (`prestress`)**: 플랫 + 벤트 → dynain 초기 응력
- **예제 생성 (`generate`)**: 테스트용 심플 메쉬 (arc, torus, helix 등)

---

## 전체 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│ 1단계: 심플 벤트 생성 (형상 정의) - 필수                     │
└─────────────────────────────────────────────────────────────┘
YAML Config ──→ generate-var ──→ Simple Bent (10K 요소)
     (curved)                           │
                                        │
                                        │ unfold (선택)
                                        ▼
                                  Simple Flat (크기 참조용)
                                        │
┌───────────────────────────────────────┼─────────────────────┐
│ 2단계: 디테일 플랫 준비 - 필수         │                     │
│  방법 A: generate-var (reference 사용)│                     │
│  방법 B: CAD 직접 생성 (크기 대략 맞춤)│                     │
└───────────────────────────────────────┼─────────────────────┘
                                        │
       방법 A: generate-var (YAML) ─────┤
       방법 B: CAD ─────────────────────┤
                                        ▼
                                 Detail Flat (1M 요소)
                                        │
┌───────────────────────────────────────┼─────────────────────┐
│ 3단계: 매핑 - 필수                     │                     │
│  (디테일 플랫 → 디테일 벤트)          │                     │
└───────────────────────────────────────┼─────────────────────┘
                                        │
       Simple Bent (레퍼런스) ──────────┤
                                   map  │
                                        ▼
                                 Detail Bent (1M 요소)
                                        │
┌───────────────────────────────────────┼─────────────────────┐
│ 4단계: 초기 응력 계산 - 필수           │                     │
└───────────────────────────────────────┼─────────────────────┘
                                        │
       Detail Flat ──────────────────prestress
                                        │
                                        ▼
                                  prestress.dynain
                                   (초기 응력)
                                        │
                                        ▼
                                  LS-DYNA 해석

필수 파일: Simple Bent + Detail Flat
선택 파일: Simple Flat (크기 자동 맞춤 시에만)
```

---

## 설치 및 빌드

### 방법 1: 소스에서 빌드 (권장)

**Windows:**
```cmd
# 1. 저장소 클론
git clone https://github.com/squall321/KooRemapper.git
cd KooRemapper

# 2. 빌드
scripts\build_windows.bat

# 3. 실행파일 위치
build\bin\Release\KooRemapper.exe
```

**Linux / macOS:**
```bash
# 1. 저장소 클론
git clone https://github.com/squall321/KooRemapper.git
cd KooRemapper

# 2. 빌드
./scripts/build_linux.sh

# 3. 실행파일 위치
build/bin/Release/KooRemapper
```

**필요 환경:**
- CMake 3.15+
- C++17 지원 컴파일러
  - Windows: Visual Studio 2019+
  - Linux: GCC 9+ / Clang 10+
  - macOS: Xcode 11+

### 방법 2: 실행파일만 복사 (간편)

KooRemapper는 **정적 링크**로 빌드되어 외부 DLL 없이 단독 실행됩니다.

**Windows:**
```cmd
# 빌드된 실행파일만 복사
KooRemapper.exe → 원하는 위치

# 바로 실행 가능 (DLL 불필요)
KooRemapper.exe --help
```

**Linux / macOS:**
```bash
# 실행파일만 복사
cp KooRemapper /usr/local/bin/

# 또는 PATH에 추가
export PATH=$PATH:/path/to/KooRemapper
```

### 방법 3: 다른 컴퓨터에 배포

**Windows:**
1. `build\bin\Release\KooRemapper.exe` 파일만 복사
2. 대상 컴퓨터 아무 폴더에 붙여넣기
3. 명령 프롬프트에서 바로 실행

**Linux / macOS:**
1. `build/bin/Release/KooRemapper` 파일만 복사
2. 실행 권한 부여: `chmod +x KooRemapper`
3. PATH에 추가하거나 직접 실행

**주의:** 정적 링크되어 있어 런타임 의존성이 없습니다.

---

## 명령어

### 1. 가변 메쉬 생성 (`generate-var`)

YAML 설정으로 가변 밀도 평면 메쉬 또는 곡선 메쉬를 생성합니다.

```bash
KooRemapper generate-var <config.yaml> <output.k>
```

#### 타입 1: 가변 밀도 평면 메쉬 (`type: flat`)

요소 밀도가 영역별로 다른 평면 메쉬를 생성합니다. 밴딩 영역은 조밀하게, 평평한 영역은 성기게 설정 가능합니다.

**YAML 예제 (레퍼런스 기반):**
```yaml
type: flat
reference: bent_ref.k  # 이 메쉬의 크기에 자동 맞춤

zones:
  - id: 1
    type: uniform
    element_count: 20
    element_size: 2.0

  - id: 2
    type: transition
    element_count: 30
    start_size: 2.0
    end_size: 0.5

  - id: 3
    type: uniform
    element_count: 80
    element_size: 0.5  # 밴딩 영역: 조밀

  - id: 4
    type: transition
    element_count: 30
    start_size: 0.5
    end_size: 2.0

  - id: 5
    type: uniform
    element_count: 20
    element_size: 2.0

elements_j: 30
elements_k: 10
```

**YAML 예제 (직접 크기 지정):**
```yaml
type: flat
# reference 없으면 length 값 사용

zones:
  - id: 1
    type: uniform
    element_count: 50
    element_size: 1.0
    length: 50.0  # reference 없을 때만 필요

elements_j: 20
elements_k: 5
width: 20.0      # reference 없을 때 필요
thickness: 2.0   # reference 없을 때 필요
```

**명령어:**
```bash
KooRemapper generate-var vardens.yaml fine_flat.k
```

**특징:**
- `reference` 지정 시: 총 길이/폭/두께를 레퍼런스에 자동 맞춤
- `transition` 영역: 요소 크기가 점진적으로 변화 (자동 길이 계산)
- 최종 스케일링으로 레퍼런스와 정확히 동일한 크기 보장

---

#### 타입 2: 곡선 메쉬 (`type: curved`)

사용자 정의 centerline을 따라 구부러진 메쉬를 생성합니다.

**YAML 예제 (레퍼런스 기반):**
```yaml
type: curved
reference: flat_ref.k  # 이 메쉬의 크기에 자동 맞춤

centerline_points:
  - [0, 0]
  - [20, 0]
  - [40, 10]
  - [60, 30]
  - [80, 30]
  - [100, 10]
  - [120, 0]
  - [140, 0]

interpolation: catmull_rom  # linear, catmull_rom, bspline

elements_along_curve: 50
elements_j: 10
elements_k: 4
```

**YAML 예제 (직접 크기 지정):**
```yaml
type: curved
# reference 없으면 cross_section 값 사용

centerline_points:
  - [0, 0]
  - [30, 0]
  - [60, 20]
  - [90, 0]

interpolation: bspline

cross_section:
  width: 10.0
  thickness: 2.0

elements_along_curve: 40
elements_j: 8
elements_k: 4
```

**명령어:**
```bash
KooRemapper generate-var curved.yaml bent_mesh.k
```

**특징:**
- `reference` 지정 시: 곡선 총 길이를 레퍼런스에 맞춰 스케일링
- 보간 방법: `linear`, `catmull_rom` (모든 점 통과), `bspline` (부드러운 근사)
- 곡선 통계 출력: 총 길이, 최대 곡률, 최소 반경

### 2. 메쉬 매핑 (`map`)

평평한 **디테일 메쉬**를 구부러진 **심플 레퍼런스 메쉬** 형상으로 변형시킵니다.

```bash
KooRemapper map <bent_ref> <flat_detail> <bent_detail_output>
```

**역할:**
- `bent_ref`: 심플 벤트 메쉬 (정형, 적은 요소) - **형상 정의 역할**
- `flat_detail`: 디테일 플랫 메쉬 (비정형, 많은 요소) - **매핑 대상**
- `bent_detail_output`: 디테일 벤트 메쉬 - **결과**

**예제 1: generate-var 레퍼런스 사용**
```bash
# 1. 심플 레퍼런스 (10,000 요소)
KooRemapper generate-var curved.yaml bent_ref.k

# 2. 디테일 플랫 준비 (1,000,000 요소, CAD 또는 generate-var)
# fine_flat.k

# 3. 디테일 플랫 → 디테일 벤트 매핑
KooRemapper map bent_ref.k fine_flat.k bent_detail.k
# → bent_detail.k: 1,000,000 요소의 구부러진 메쉬
```

**예제 2: 예제 메쉬 사용**
```bash
# 1. 심플 레퍼런스 생성
KooRemapper generate arc simple
# → simple_bent.k (간단한 호 형상)

# 2. 디테일 플랫은 CAD에서 준비
# detail_flat.k (복잡한 형상, TET4/HEX8 혼합 가능)

# 3. 매핑
KooRemapper map simple_bent.k detail_flat.k detail_bent.k
```

**특징:**
- Bent 레퍼런스는 **반드시 HEX8 정형 메쉬**
- Flat 디테일은 **HEX8 또는 TET4, 비정형 가능**
- 크기 자동 조정: Flat의 (길이 x 폭 x 두께)가 Bent의 (arc-length x width x thickness)에 맞춰짐

### 3. 초기 응력 계산 (`prestress`)

변형 전/후 메쉬로부터 응력을 계산하고 dynain 포맷으로 출력합니다.

```bash
KooRemapper prestress [options] <ref_mesh> <def_mesh> <output.dynain>
```

**옵션:**
- `-E <value>`: 영률 (MPa) - K-file 물성 덮어쓰기
- `-nu <value>`: 푸아송비 - K-file 물성 덮어쓰기
- `--strain <type>`: 스트레인 타입 (`engineering`, `green`)
- `--csv`: CSV 파일도 함께 출력

#### 물성 정의 방법

**방법 1: K-file에 정의된 물성 자동 사용 (권장)**

ref_mesh K-file에 `*PART`와 `*MAT_ELASTIC`이 정의되어 있으면 자동으로 읽어옵니다.

```bash
# K-file에 물성이 정의되어 있으면 -E, -nu 옵션 불필요
KooRemapper prestress ref_with_material.k deformed.k prestress.dynain
```

K-file 예시:
```
*PART
$#     pid     secid       mid
         1         1         1

*MAT_ELASTIC
$#     mid        ro         e        pr
         1   7.85e-9   210000.0       0.3
```

**방법 2: 명령줄 옵션으로 물성 지정**

```bash
# 모든 요소에 동일한 물성 적용 (K-file 물성 덮어쓰기)
KooRemapper prestress -E 210000 -nu 0.3 flat.k mapped.k prestress.dynain
```

**다중 파트 지원:**
- 각 파트별로 다른 물성 사용 가능
- K-file의 `*PART` → `*MAT_ELASTIC` 연결 자동 추적
- `-E`, `-nu` 옵션 사용 시 모든 파트에 동일 물성 적용

**출력:**
```
Analysis Results
================
Valid elements:          16000
Min von Mises stress:    4755.48 MPa
Max von Mises stress:    121772.94 MPa
Avg von Mises stress:    63123.85 MPa
```

**LS-DYNA에서 사용:**
```
*INCLUDE
prestress.dynain
```

### 4. 메쉬 언폴딩 (`unfold`)

구부러진 정형 메쉬를 평평하게 펼칩니다. Arc-length를 기준으로 평면 메쉬를 생성합니다.

```bash
KooRemapper unfold <bent_mesh> <output_flat>
```

**예제:**
```bash
# generate-var로 만든 곡선 메쉬를 펼치기
KooRemapper unfold bent_curved.k flat_unfolded.k

# 펼친 메쉬 크기 확인
KooRemapper info flat_unfolded.k
```

**용도:**
- 곡선 메쉬의 평면 형태 확인
- Arc-length 기반 평면 메쉬 생성
- 매핑용 레퍼런스 flat 메쉬 준비

### 5. 예제 메쉬 생성 (`generate`)

간단한 테스트용 예제 메쉬를 생성합니다 (bent/flat 쌍 생성).

```bash
KooRemapper generate <type> <output_prefix>
```

**지원 타입:**
- `arc`: 단순 호 (30° 벤딩)
- `scurve`: S자 곡선
- `waterdrop`: 물방울 형상
- `helix`: 나선형
- `torus`: 토러스 형상
- `twist`: 비틀림 변형
- `wave`: 파형

**예제:**
```bash
# arc 예제 생성 -> test_arc_bent.k, test_arc_flat.k
KooRemapper generate arc test_arc

# 생성된 파일로 매핑 테스트
KooRemapper map test_arc_bent.k test_arc_flat.k test_arc_mapped.k
```

### 6. 쉘 기반 매핑 (`shellmap`)

QUAD4 쉘 메쉬를 레퍼런스로 사용하여, 평평한 디테일 메쉬를 구부러진 형상으로 매핑합니다.

```bash
KooRemapper shellmap [options] <bent_shell> <flat_detail> <output>
```

**역할:**
- `bent_shell`: 구부러진 QUAD4 쉘 메쉬 (비정형 가능)
- `flat_detail`: 평평한 디테일 메쉬 (HEX8/TET4, 비정형 가능)
- `output`: 매핑된 결과 메쉬

**옵션:**
- `--thickness <t>`: 쉘 두께 (기본값: flat 메쉬의 Z 범위에서 자동 감지)

**동작 원리:**
```
┌─────────────────────────────────────────────────────────┐
│ 1. Shell Unfold (edge-length 보존 전개)                  │
│    Bent QUAD4 Shell ──→ Flat 2D Shell                    │
│                                                          │
│ 2. Auto-Alignment (자동 정렬)                            │
│    Flat Detail BB ←→ Unfolded Shell BB                   │
│    (축 스왑 + 크기 스케일링 자동 감지)                    │
│                                                          │
│ 3. Point-in-Element (요소 검색)                          │
│    각 노드가 어느 flat shell 요소에 속하는지 탐색         │
│                                                          │
│ 4. Surface Interpolation (표면 보간)                     │
│    Bent shell 위의 대응점 + 법선 방향 두께 오프셋         │
└─────────────────────────────────────────────────────────┘
```

**`map` 명령과의 차이:**

| 항목 | `map` (HEX8) | `shellmap` (QUAD4) |
|------|-------------|-------------------|
| 레퍼런스 메쉬 | HEX8 정형 (structured) 필수 | QUAD4 비정형 가능 |
| 레퍼런스 생성 | `generate-var`로 HEX8 생성 | CAD/전처리기에서 쉘 메쉬 직접 생성 |
| 두께 정보 | 레퍼런스에 포함 | `--thickness`로 지정 또는 자동 감지 |
| 적용 대상 | 일반적인 굽힘 형상 | 판형 구조물 (폴더블 디스플레이 등) |

**예제 1: 원통형 호 (arc)**
```bash
# 예제 파일 위치: examples/shellmap_arc/
KooRemapper shellmap \
    examples/shellmap_arc/arc_shell.k \
    examples/shellmap_arc/arc_flat.k \
    examples/shellmap_arc/arc_mapped.k

# 결과 확인
KooRemapper info examples/shellmap_arc/arc_mapped.k
```

**예제 2: S자 스플라인 곡면 (spline)**
```bash
# 예제 파일 위치: examples/shellmap_spline/
KooRemapper shellmap \
    examples/shellmap_spline/spline_shell.k \
    examples/shellmap_spline/spline_flat.k \
    examples/shellmap_spline/spline_mapped.k

# 결과 확인
KooRemapper info examples/shellmap_spline/spline_mapped.k
```

**예제 3: 사용자 쉘 메쉬 사용**
```bash
# CAD/전처리기에서 만든 bent shell + flat detail 사용
KooRemapper shellmap my_bent_shell.k my_flat_detail.k my_mapped.k --thickness 1.0

# 응력 계산까지
KooRemapper prestress -E 210000 -nu 0.3 my_flat_detail.k my_mapped.k prestress.dynain
```

**특징:**
- Bent 레퍼런스: QUAD4 쉘 (비정형 가능, CAD에서 쉽게 생성)
- Flat 디테일: HEX8 또는 TET4, 비정형 가능
- **자동 축 정렬**: flat 메쉬와 unfolded shell의 종횡비를 비교하여 축 스왑 자동 감지
- **자동 크기 맞춤**: bounding box 스케일링으로 크기 자동 조정
- Developable surface (단일 곡률)에서 전개 왜곡 0%
- Non-developable surface는 왜곡 경고 출력

### 7. 메쉬 정보 (`info`)

메쉬 파일의 기본 정보를 출력합니다.

```bash
KooRemapper info <mesh_file>
```

**출력 정보:**
- 노드/요소 개수
- 파트 개수 및 ID
- 요소 타입 (HEX8/TET4)
- Bounding Box (X, Y, Z 범위)
- 정형 그리드 구조 (i, j, k 차원)

**예제:**
```bash
KooRemapper info bent_mesh.k
```

**출력 예시:**
```
Mesh Information for bent_mesh.k
=================================
Nodes:           12,000
Elements:        10,000
Parts:           1
Element Type:    HEX8

Bounding Box:
  X: [0.00, 140.23]
  Y: [0.00, 10.00]
  Z: [-1.00, 33.45]

Structured Grid:
  I-direction: 50 elements
  J-direction: 10 elements
  K-direction: 20 elements
```

---

## 전체 워크플로우 예제

### 예제 1: 곡선 형상 + 가변 밀도 메쉬 + 응력 계산

**목표**: 심플 벤트 레퍼런스로 100만개 디테일 플랫 메쉬를 변형

```bash
# 1. 심플 벤트 레퍼런스 생성 (10,000 요소, 형상 정의용) - 필수
# curved.yaml 파일 작성 (type: curved, 50x10x20 = 10K 요소)
KooRemapper generate-var curved.yaml simple_bent.k
KooRemapper info simple_bent.k

# 2. 심플 플랫 생성 (크기 자동 맞춤용) - 선택
KooRemapper unfold simple_bent.k simple_flat.k

# 3. 디테일 플랫 메쉬 생성 (1,000,000 요소) - 필수
# vardens.yaml 작성 (type: flat, reference: simple_flat.k)
# 183x183x30 = 1M 요소
KooRemapper generate-var vardens.yaml detail_flat.k
KooRemapper info detail_flat.k

# 4. 디테일 플랫 → 디테일 벤트 매핑 - 필수
KooRemapper map simple_bent.k detail_flat.k detail_bent.k
KooRemapper info detail_bent.k

# 5. 초기 응력 계산 - 필수
KooRemapper prestress detail_flat.k detail_bent.k prestress.dynain

# 6. LS-DYNA 입력 파일에서 사용
# *INCLUDE
# prestress.dynain
```

**결과:**
- `simple_bent.k`: 10K 요소의 심플 레퍼런스
- `simple_flat.k`: (선택) 크기 참조용, 매핑에는 불필요
- `detail_flat.k`: 1M 요소의 디테일 플랫
- `detail_bent.k`: 1M 요소의 디테일 벤트
- `prestress.dynain`: 1M 요소의 초기 응력

### 예제 1-1: 심플 플랫 없이 진행 (CAD에서 디테일 플랫 준비)

```bash
# 1. 심플 벤트 레퍼런스 생성
KooRemapper generate-var curved.yaml simple_bent.k

# 2. CAD에서 디테일 플랫 준비 (크기 대략 맞춤)
# detail_flat_from_cad.k (arc-length x width x thickness 크기)

# 3. 매핑 (자동 크기 조정됨)
KooRemapper map simple_bent.k detail_flat_from_cad.k detail_bent.k

# 4. 응력 계산
KooRemapper prestress detail_flat_from_cad.k detail_bent.k prestress.dynain
```

**핵심**: `map` 명령어가 자동으로 크기를 조정하므로, 심플 플랫 없이도 작동합니다.

### 예제 2: 간단한 arc 예제

```bash
# 1. 예제 메쉬 생성
KooRemapper generate arc test_arc
# -> test_arc_bent.k, test_arc_flat.k

# 2. 매핑
KooRemapper map test_arc_bent.k test_arc_flat.k test_arc_mapped.k

# 3. 응력 계산
KooRemapper prestress -E 210000 -nu 0.3 \
    test_arc_flat.k test_arc_mapped.k test_arc_stress.dynain
```

### 예제 3: shellmap으로 쉘 기반 매핑

```bash
# 1. CAD/전처리기에서 QUAD4 쉘 메쉬 준비
#    bent_shell.k: 구부러진 형상의 QUAD4 쉘

# 2. 디테일 플랫 메쉬 준비 (CAD 또는 generate-var)
#    detail_flat.k: 평평한 HEX8 솔리드 메쉬

# 3. shellmap으로 매핑 (두께 자동 감지)
KooRemapper shellmap bent_shell.k detail_flat.k detail_bent.k

# 4. 응력 계산
KooRemapper prestress -E 210000 -nu 0.3 \
    detail_flat.k detail_bent.k prestress.dynain
```

**핵심**: `shellmap`은 HEX8 정형 레퍼런스 없이 QUAD4 쉘만으로 매핑 가능합니다.

---

## 기술 세부사항

### 지원 요소 타입

| 메쉬 역할 | HEX8 | TET4 | QUAD4 |
|-----------|------|------|-------|
| `map` Bent 레퍼런스 | 필수 (정형) | 미지원 | 미지원 |
| `shellmap` Bent 레퍼런스 | 미지원 | 미지원 | 필수 (비정형 가능) |
| Flat (매핑 대상) | 지원 | 지원 | - |

### 매핑 알고리즘 (`map`)

1. 정형 그리드 분석: (i, j, k) 인덱스 구조 추출
2. Edge Arc-length 계산
3. 파라메트릭 좌표 변환: (u, v, w)
4. Transfinite 보간

### 쉘 매핑 알고리즘 (`shellmap`)

1. Edge-length 보존 전개: BFS로 QUAD4 쉘을 2D 평면에 전개
2. 자동 정렬: Flat detail ↔ Unfolded shell BB 매칭 (축 스왑/스케일 자동)
3. Point-in-element: 2D Spatial Hash + Newton-Raphson으로 (ξ, η) 좌표 계산
4. 표면 보간: Bilinear shape function으로 bent 위치 + **Smooth Normal** 두께 오프셋

#### Smooth Normal 보간 (Phong Shading 원리)

QUAD4 요소는 4개 노드로 정의되는 평면 패싯(facet)이므로, 요소 내부의 법선이 일정합니다.
이 상태로 두께 방향 오프셋을 적용하면 요소 내부에서 곡률이 0이 되어 **굽힘 응력이 누락**됩니다.

KooRemapper는 **노드 평균 법선(Node-Averaged Normal)** 을 사용하여 이 문제를 해결합니다:

```text
[평면 패싯 법선 (기존)]            [Smooth Normal (현재)]

  n↑    n↑    n↑                    n↗    n↑    n↖
  ┌─────┬─────┐                    ┌─────┬─────┐
  │요소A │요소B │                    │요소A │요소B │
  └─────┴─────┘                    └─────┴─────┘
  요소 내 법선 일정                  노드에서 법선 혼합 → 연속 변화
  → 곡률 = 0                        → 곡률 ≠ 0 → 굽힘 포착
```

**원리:**

1. 각 쉘 요소의 법선을 면적 가중 평균하여 노드 법선 계산
2. 요소 내부에서 shape function으로 노드 법선을 보간
3. 보간된 법선 방향으로 두께 오프셋 → 요소 내에서 법선 연속 변화 → 곡률 발생

이는 컴퓨터 그래픽스의 **Phong Shading**과 동일한 원리입니다.
저해상도 메쉬(삼각형/사각형 패싯)에서도 부드러운 곡면 법선을 재현합니다.

#### 굽힘 응력 포착을 위한 디테일 메쉬 구성

쉘의 굽힘 응력(bending stress)을 정확히 포착하려면 디테일 솔리드 메쉬의 **두께 방향 요소 수**가 중요합니다:

| 두께 방향 요소 | 포착 가능한 응력 | 비고 |
| :---: | --- | --- |
| 1개 | 막응력(membrane)만 | 중립면 응력만 계산, 굽힘 응력 누락 |
| **2개 이상** | **막응력 + 굽힘 응력** | 상면/하면 응력 차이로 굽힘 포착 |

```
[1개 요소 (두께 방향)]         [2개 요소 (두께 방향)]

  ┌──────────────┐              ┌──────────────┐ ← 인장 (outer)
  │   1개 적분점   │              ├──────────────┤ ← 중립면
  │  (중립면 응력)  │              │              │
  └──────────────┘              └──────────────┘ ← 압축 (inner)

  σ_top = σ_bottom               σ_top ≠ σ_bottom
  (굽힘 구분 불가)               (굽힘 응력 포착)
```

**검증 결과** (30° arc, R=10, 2-layer, Green-Lagrange):

| 위치 | eps_xx | sig_xx | 방향 |
| ------ | -------- | -------- | ------ |
| Inner (Z < 0) | -0.0057 | -1,675 MPa | 압축 |
| Outer (Z > 0) | +0.0043 | +1,148 MPa | 인장 |
| 이론값 (z/R) | ±0.005 | | |

내부 요소의 bending strain이 이론값 z/R = 0.005와 99.9% 일치합니다.

### 응력 계산
1. 변형 구배 텐서(F) 계산
2. 스트레인 텐서 (Engineering / Green-Lagrange)
3. Hooke's Law로 응력 계산
4. dynain 포맷 출력 (`*INITIAL_STRESS_SOLID`)

### 곡선 보간
- **Linear**: 직선 보간
- **Catmull-Rom**: 모든 점을 통과하는 스플라인
- **B-Spline**: 부드러운 근사 곡선

---

## 파일 포맷

| 용도 | 포맷 |
|------|------|
| 메쉬 입출력 | LS-DYNA K-file (*.k) |
| 설정 | YAML (*.yaml) |
| 초기 응력 | dynain (*.dynain) |
| 스트레인 데이터 | CSV (*.csv) |

---

## 라이선스

MIT License

## 버전

v1.1.0 (2026-01-13)
