# 가변 밀도 메쉬 생성기 계획

## 개요

굽힘부(bend) 근처는 요소가 밀집하고, 평탄부(flat)는 성기며, 그 사이는 점진적으로 변화하는 **가변 밀도 flat 메쉬**를 생성하는 기능.

## 핵심 기능: 자동 스케일링

**레퍼런스 flat 메쉬와 치수가 다르더라도 자동으로 비례 스케일링!**

```
사용자 정의 (YAML)              →  자동 스케일링  →   실제 생성 메쉬
┌─────────────────────┐                         ┌─────────────────────┐
│ zone1: 10           │        Reference        │ zone1: 15.03        │
│ zone2: 20           │        length_i         │ zone2: 30.06        │
│ zone3: 90           │   ──────────────→       │ zone3: 135.25       │
│ zone4: 20           │        150.28           │ zone4: 30.06        │
│ zone5: 10           │                         │ zone5: 15.03        │
│ total: 150          │                         │ total: 150.28 ✓     │
└─────────────────────┘                         └─────────────────────┘
```

### 스케일링 방식

```cpp
// 사용자 정의 길이 합계
double userTotal = zone1.length + zone2.length + ... + zone5.length;

// 레퍼런스 flat 메쉬에서 실제 길이 읽기
double refLength = refFlatMesh.boundingBox.max.x - refFlatMesh.boundingBox.min.x;

// 스케일 팩터
double scale = refLength / userTotal;

// 각 zone 길이 조정
zone1.actualLength = zone1.length * scale;
zone2.actualLength = zone2.length * scale;
// ...
```

## 메쉬 밀도 패턴

가장 긴 변(I 방향) 따라 5개 구간으로 구성:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Zone 1  │  Zone 2   │     Zone 3      │  Zone 4   │  Zone 5  │
│ Dense   │ Increase  │     Sparse      │ Decrease  │  Dense   │
│ (등간격) │ (밀→소)   │    (등간격)      │ (소→밀)   │ (등간격) │
│ |||||||  ||| || |   |    |    |    |   | || |||    |||||||   │
└─────────────────────────────────────────────────────────────────────┘
     ←d1→   ←  d2  →      ←   d3   →      ← d4 →      ←d5→
```

### 구간 설명

| Zone | 이름 | 요소 간격 | 용도 |
|------|------|----------|------|
| 1 | Dense Start | 균일 (작음) | 시작부 굽힘 영역 |
| 2 | Increasing | 점진적 증가 | 밀집→성김 전이 |
| 3 | Sparse | 균일 (큼) | 평탄부 중앙 |
| 4 | Decreasing | 점진적 감소 | 성김→밀집 전이 |
| 5 | Dense End | 균일 (작음) | 끝부 굽힘 영역 |

## YAML 설정 파일 형식

```yaml
# variable_mesh_config.yaml

# 레퍼런스 메쉬 (선택적 - 지정시 자동 스케일링)
reference:
  flat_mesh: "reference_flat.k"    # 레퍼런스 flat 메쉬 파일
  # 또는 직접 치수 지정 (레퍼런스 없을 때)
  # dimensions:
  #   length_i: 150.28
  #   length_j: 70.0
  #   length_k: 1.0

# J, K 방향 요소 수 (균일)
elements_j: 50
elements_k: 10

# I 방향 가변 밀도 설정
variable_density:
  # Zone 1: Dense Start (시작부 밀집)
  zone1_dense_start:
    length: 10.0           # 이 구간의 길이
    num_elements: 50       # 요소 수
    # → 요소 크기 = 10.0 / 50 = 0.2

  # Zone 2: Increasing (밀집→성김 전이)
  zone2_increasing:
    length: 20.0           # 전이 구간 길이
    num_elements: 30       # 전이 구간 요소 수
    growth_type: linear    # linear, exponential, geometric
    # 시작 크기 = Zone1의 요소 크기 (0.2)
    # 끝 크기 = Zone3의 요소 크기로 자동 계산

  # Zone 3: Sparse (중앙 성김)
  zone3_sparse:
    length: 90.0           # 중앙 구간 길이
    num_elements: 60       # 요소 수
    # → 요소 크기 = 90.0 / 60 = 1.5

  # Zone 4: Decreasing (성김→밀집 전이)
  zone4_decreasing:
    length: 20.0           # 전이 구간 길이
    num_elements: 30       # 전이 구간 요소 수
    growth_type: linear    # linear, exponential, geometric

  # Zone 5: Dense End (끝부 밀집)
  zone5_dense_end:
    length: 10.0           # 이 구간의 길이
    num_elements: 50       # 요소 수
    # → 요소 크기 = 10.0 / 50 = 0.2

# 선택적 설정
options:
  center_at_origin: true   # 중심을 원점에 배치
  output_format: k         # k, vtk
```

## 전이 구간 알고리즘

### Linear Growth (선형 증가)

```
d_i = d_start + (d_end - d_start) * i / (n-1)
```

여기서:
- `d_start`: 시작 요소 크기
- `d_end`: 끝 요소 크기
- `n`: 전이 구간 요소 수
- `i`: 0부터 n-1까지

### Geometric Growth (기하급수적)

```
ratio = (d_end / d_start)^(1/(n-1))
d_i = d_start * ratio^i
```

### Exponential (지수적)

```
d_i = d_start * exp(ln(d_end/d_start) * i / (n-1))
```

## 구현 구조

### 새 파일

```
include/
  generator/
    VariableDensityMeshGenerator.h
    YamlConfigReader.h
    
src/
  generator/
    VariableDensityMeshGenerator.cpp
    YamlConfigReader.cpp
```

### 클래스 설계

```cpp
// YAML 설정 구조체
struct ZoneConfig {
    double length;
    int numElements;
    std::string growthType;  // "linear", "geometric", "exponential"
};

struct VariableDensityConfig {
    // 전체 치수
    double lengthI, lengthJ, lengthK;
    int elementsJ, elementsK;
    
    // 5개 Zone 설정
    ZoneConfig zone1_denseStart;
    ZoneConfig zone2_increasing;
    ZoneConfig zone3_sparse;
    ZoneConfig zone4_decreasing;
    ZoneConfig zone5_denseEnd;
    
    // 옵션
    bool centerAtOrigin;
};

// 메쉬 생성기
class VariableDensityMeshGenerator {
public:
    Mesh generate(const VariableDensityConfig& config);
    
private:
    std::vector<double> computeXCoordinates(const VariableDensityConfig& config);
    std::vector<double> computeTransitionSpacing(
        double startSize, double endSize, int numElements, 
        const std::string& growthType);
};

// YAML 파서
class YamlConfigReader {
public:
    VariableDensityConfig readConfig(const std::string& filename);
};
```

## CLI 인터페이스

```bash
# 방법 1: YAML에 레퍼런스 파일 경로 지정
KooRemapper generate-var config.yaml output.k

# 방법 2: 명령줄에서 레퍼런스 지정 (YAML의 reference 무시)
KooRemapper generate-var config.yaml output.k --ref reference_flat.k

# 방법 3: 레퍼런스 없이 YAML의 dimensions 사용
KooRemapper generate-var config.yaml output.k --no-scale
```

### 동작 우선순위

1. `--ref` 옵션이 있으면 → 해당 파일에서 치수 읽기
2. YAML에 `reference.flat_mesh` 있으면 → 해당 파일에서 치수 읽기
3. YAML에 `reference.dimensions` 있으면 → 해당 치수 사용
4. 위 모두 없으면 → zone 길이 합계를 그대로 사용

## 구현 단계

### Phase 1: 기본 구조 (1-2시간)
1. [ ] `VariableDensityConfig` 구조체 정의
2. [ ] `YamlConfigReader` 기본 파싱 구현
3. [ ] 설정 검증 로직

### Phase 2: 좌표 계산 (1-2시간)
4. [ ] Zone별 요소 크기 계산
5. [ ] 전이 구간 스페이싱 알고리즘 (linear, geometric)
6. [ ] 전체 X 좌표 배열 생성

### Phase 3: 메쉬 생성 (1시간)
7. [ ] 노드 생성 (X 좌표 배열 + Y, Z 균일)
8. [ ] HEX8 요소 생성
9. [ ] K-file 출력

### Phase 4: CLI 통합 (30분)
10. [ ] 새 명령어 추가
11. [ ] 도움말 업데이트

### Phase 5: 테스트 (30분)
12. [ ] 예제 YAML 파일 작성
13. [ ] 생성 테스트
14. [ ] 매핑 테스트

## 예상 결과

### 입력 (YAML)
```yaml
reference:
  flat_mesh: "ufold_ref_flat.k"   # 실제 길이: 150.28 x 70.0 x 1.0

elements_j: 50
elements_k: 10

variable_density:
  zone1_dense_start:
    length: 10.0       # 비율: 6.67%
    num_elements: 50
  zone2_increasing:
    length: 20.0       # 비율: 13.33%
    num_elements: 30
    growth_type: linear
  zone3_sparse:
    length: 90.0       # 비율: 60%
    num_elements: 60
  zone4_decreasing:
    length: 20.0       # 비율: 13.33%
    num_elements: 30
    growth_type: linear
  zone5_dense_end:
    length: 10.0       # 비율: 6.67%
    num_elements: 50
```

### 출력 통계
```
============================================================
Reference mesh: ufold_ref_flat.k
Reference dimensions: 150.283 x 70.000 x 1.000
============================================================

Scale factor: 1.00189 (150.283 / 150.0)

Zone lengths (after scaling):
  Zone 1 (Dense):      10.019 (50 elements, size=0.200)
  Zone 2 (Increasing): 20.038 (30 elements, size=0.200→1.506)
  Zone 3 (Sparse):     90.170 (60 elements, size=1.503)
  Zone 4 (Decreasing): 20.038 (30 elements, size=1.506→0.200)
  Zone 5 (Dense):      10.019 (50 elements, size=0.200)
  
Total I length: 150.283 ✓ (matches reference)

============================================================
Mesh Statistics
============================================================
Total I elements: 50 + 30 + 60 + 30 + 50 = 220
Total J elements: 50
Total K elements: 10
Total elements: 220 × 50 × 10 = 110,000

Dense element size:  0.200
Sparse element size: 1.503
Size ratio: 7.5:1
```

## 확장 가능성

1. **비대칭 설정**: Zone 1과 Zone 5의 길이/밀도를 다르게
2. **다중 전이**: 3개 이상의 밀도 구간
3. **2D 가변 밀도**: J 방향도 가변 밀도
4. **자동 최적화**: 곡률 기반 자동 밀도 결정

## 참고

- YAML 파싱: yaml-cpp 라이브러리 또는 간단한 자체 파서
- 외부 의존성 최소화를 위해 자체 파서 권장
