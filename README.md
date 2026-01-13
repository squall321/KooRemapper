# KooRemapper

**LS-DYNA K-file용 메쉬 매핑 및 응력 분석 도구**

KooRemapper는 평평한(flat) 메쉬를 구부러진(bent) 구조화 메쉬에 매핑하고, 변형에 따른 초기 응력을 계산하는 크로스 플랫폼 CLI 도구입니다.

## 주요 기능

- **메쉬 매핑**: 평평한 비정형 메쉬를 구부러진 정형 메쉬에 매핑
- **언폴딩**: 구부러진 메쉬를 평평하게 펼친 메쉬 생성
- **곡선 메쉬 생성**: 사용자 정의 centerline으로 곡선 메쉬 생성 (YAML)
- **가변 밀도 메쉬**: 밀-소 영역이 다른 메쉬 생성 (YAML)
- **Prestress 계산**: 변형에 따른 응력을 dynain 포맷으로 출력
- **스트레인 계산**: 두 메쉬 간의 변형률 계산

---

## 전체 워크플로우

```
YAML Config ──→ generate-var ──→ Bent Mesh (레퍼런스)
                                      │
                                      │ unfold (선택)
                                      ▼
Fine Flat Mesh ──────────────→ map ──→ Mapped Mesh
(CAD에서 생성)                              │
                                           │ prestress
                                           ▼
                                      dynain 파일
                                      (초기 응력)
                                           │
                                           ▼
                                      LS-DYNA 해석
```

---

## 빌드

### Windows
```cmd
cd KooRemapper
scripts\build_windows.bat
```

### Linux / macOS
```bash
cd KooRemapper
./scripts/build_linux.sh
```

---

## 명령어

### 1. 곡선 메쉬 생성 (`generate-var`)

YAML 설정으로 곡선 또는 가변 밀도 메쉬를 생성합니다.

```bash
KooRemapper generate-var <config.yaml> <output.k>
```

**곡선 메쉬 YAML 예제:**
```yaml
type: curved

centerline_points:
  - [0, 0]
  - [20, 0]
  - [40, 10]
  - [60, 30]
  - [80, 30]
  - [100, 10]
  - [120, 0]
  - [140, 0]

interpolation: catmull_rom

cross_section:
  width: 10.0
  thickness: 2.0

elements_along_curve: 50
elements_j: 10
elements_k: 4
```

**명령어:**
```bash
KooRemapper generate-var curved.yaml bent_mesh.k
```

### 2. 메쉬 매핑 (`map`)

평평한 메쉬를 구부러진 참조 메쉬에 매핑합니다.

```bash
KooRemapper map <bent_mesh> <flat_mesh> <output>
```

**예제:**
```bash
KooRemapper map bent_mesh.k fine_flat.k mapped_result.k
```

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

구부러진 메쉬를 평평하게 펼칩니다.

```bash
KooRemapper unfold <bent_mesh> <output_flat>
```

### 5. 예제 메쉬 생성 (`generate`)

테스트용 예제 메쉬를 생성합니다.

```bash
KooRemapper generate <type> <output_prefix>
```

타입: `arc`, `scurve`, `waterdrop`, `helix`, `torus`, `twist`, `wave`

### 6. 메쉬 정보 (`info`)

```bash
KooRemapper info <mesh_file>
```

---

## 전체 예제: 사용자 정의 곡선 + 응력 계산

```bash
# 1. 곡선 형상 정의 (YAML)
# my_curve.yaml 파일 생성

# 2. 곡선 레퍼런스 메쉬 생성
KooRemapper generate-var my_curve.yaml bent_ref.k

# 3. 상세 평면 메쉬 준비 (CAD 또는 스크립트)
# fine_flat.k: arc-length x width x thickness 크기

# 4. 상세 메쉬를 곡선 형상으로 매핑
KooRemapper map bent_ref.k fine_flat.k mapped.k

# 5. 매핑 결과 확인
KooRemapper info mapped.k

# 6. 초기 응력 계산
KooRemapper prestress -E 210000 -nu 0.3 fine_flat.k mapped.k prestress.dynain

# 7. LS-DYNA에서 *INCLUDE로 사용
```

---

## 기술 세부사항

### 지원 요소 타입

| 메쉬 역할 | HEX8 | TET4 |
|-----------|------|------|
| Bent (레퍼런스) | 필수 (정형) | 미지원 |
| Flat (매핑 대상) | 지원 | 지원 |

### 매핑 알고리즘
1. 정형 그리드 분석: (i, j, k) 인덱스 구조 추출
2. Edge Arc-length 계산
3. 파라메트릭 좌표 변환: (u, v, w)
4. Transfinite 보간

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
