# 사용자 정의 곡선 메쉬 생성기 계획

## 개요

기존 가변 밀도 메쉬 생성기를 확장하여:
1. **Flat 타입**: 현재 기능 (평면 가변 밀도 메쉬)
2. **Curved 타입**: 사용자 정의 곡선을 따라 bent 메쉬 생성

## 통합 YAML 스키마

### 타입 필드 추가

```yaml
# 메쉬 타입: flat (기본) 또는 curved
type: flat | curved
```

## 사용 케이스 및 예제

### Case 1: Flat + Reference 있음 (현재 기능)

```yaml
# case1_flat_with_ref.yaml
# 레퍼런스에 맞춰 자동 스케일링되는 가변 밀도 플랫 메쉬

type: flat

reference:
  flat_mesh: "ufold_ref_flat.k"

elements_j: 50
elements_k: 10

variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 50
  zone2_increasing:
    num_elements: 30
    growth_type: linear
  zone3_sparse:
    length: 90.0
    num_elements: 60
  zone4_decreasing:
    num_elements: 30
    growth_type: linear
  zone5_dense_end:
    length: 10.0
    num_elements: 50
```

**동작:**
- 레퍼런스 flat mesh에서 dimensions 읽기
- 전체 길이를 레퍼런스에 맞춰 스케일링
- 가변 밀도 패턴 적용

---

### Case 2: Flat + Reference 없음

```yaml
# case2_flat_no_ref.yaml
# 직접 치수 지정하는 가변 밀도 플랫 메쉬

type: flat

# 직접 치수 지정 (reference 없을 때 필수)
dimensions:
  length_j: 70.0    # Y 방향 길이
  length_k: 1.0     # Z 방향 두께

elements_j: 50
elements_k: 10

variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 50
  zone2_increasing:
    num_elements: 30
    growth_type: linear
  zone3_sparse:
    length: 90.0
    num_elements: 60
  zone4_decreasing:
    num_elements: 30
    growth_type: linear
  zone5_dense_end:
    length: 10.0
    num_elements: 50

# 총 I 길이 = zone 합계 (스케일링 없음)
```

**동작:**
- dimensions에서 J, K 크기 읽기
- zone 길이 합계가 그대로 I 길이가 됨
- 가변 밀도 패턴 적용

---

### Case 3: Curved + Reference 있음

```yaml
# case3_curved_with_ref.yaml
# 레퍼런스에 맞춰 스케일링되는 곡선 bent 메쉬

type: curved

reference:
  flat_mesh: "ufold_ref_flat.k"
  # 레퍼런스에서 읽는 정보:
  # - 총 arc length (I 길이)
  # - cross section size (J, K 길이)

# 중립축 좌표 (측면에서 본 형상)
# 곡선의 arc length가 레퍼런스 I 길이에 맞춰 스케일링됨
centerline_points:
  - [0.0, 0.0]       # 시작점 (x, y)
  - [30.0, 0.0]      # 직선 구간
  - [50.0, 10.0]     # 굽힘 시작
  - [70.0, 25.0]     # 굽힘 정점
  - [90.0, 10.0]     # 굽힘 끝
  - [110.0, 0.0]     # 직선 구간
  - [140.0, 0.0]     # 끝점

interpolation: catmull_rom  # catmull_rom, bspline, linear

# 곡선 방향 요소 수
elements_along_curve: 200

# J, K 요소 수 (레퍼런스에서 크기 자동 결정)
elements_j: 50
elements_k: 10
```

**동작:**
1. 레퍼런스에서 flat mesh 치수 읽기
2. centerline_points로 곡선 생성
3. 곡선의 arc length를 레퍼런스 I 길이에 맞춰 스케일링
4. 단면 크기를 레퍼런스 J, K에 맞춤
5. 곡선을 따라 bent 메쉬 생성

---

### Case 4: Curved + Reference 없음

```yaml
# case4_curved_no_ref.yaml
# 직접 치수 지정하는 곡선 bent 메쉬

type: curved

# 직접 치수 지정 (reference 없을 때 필수)
cross_section:
  width: 70.0       # Y 방향 폭
  thickness: 1.0    # Z 방향 두께

# 중립축 좌표 (측면에서 본 형상)
# 스케일링 없음 - 좌표 그대로 사용
centerline_points:
  - [0.0, 0.0]
  - [30.0, 0.0]
  - [50.0, 10.0]
  - [70.0, 25.0]
  - [90.0, 10.0]
  - [110.0, 0.0]
  - [140.0, 0.0]

interpolation: catmull_rom

elements_along_curve: 200
elements_j: 50
elements_k: 10
```

**동작:**
1. cross_section에서 단면 크기 읽기
2. centerline_points로 곡선 생성 (스케일링 없음)
3. 곡선의 arc length가 그대로 총 길이
4. 곡선을 따라 bent 메쉬 생성

---

## 기술 상세

### B-Spline / Catmull-Rom 보간

```cpp
// Catmull-Rom 스플라인 (모든 제어점 통과)
Vector2D catmullRom(
    const Vector2D& p0, const Vector2D& p1,
    const Vector2D& p2, const Vector2D& p3,
    double t)
{
    double t2 = t * t;
    double t3 = t2 * t;
    
    return 0.5 * (
        (2*p1) +
        (-p0 + p2) * t +
        (2*p0 - 5*p1 + 4*p2 - p3) * t2 +
        (-p0 + 3*p1 - 3*p2 + p3) * t3
    );
}
```

### 곡선 Arc Length 계산

```cpp
// 수치적 arc length 계산
double computeArcLength(const std::vector<Vector2D>& points) {
    double length = 0;
    for (size_t i = 1; i < points.size(); ++i) {
        length += (points[i] - points[i-1]).length();
    }
    return length;
}

// Arc length 기반 파라미터화
std::vector<double> computeArcLengthParams(const std::vector<Vector2D>& points) {
    std::vector<double> params;
    params.push_back(0);
    
    double cumLength = 0;
    for (size_t i = 1; i < points.size(); ++i) {
        cumLength += (points[i] - points[i-1]).length();
        params.push_back(cumLength);
    }
    
    // 정규화
    for (auto& p : params) p /= cumLength;
    return params;
}
```

### 곡선 따라 Bent 메쉬 생성

```cpp
// 곡선의 각 위치에서:
for (int i = 0; i <= elementsAlongCurve; ++i) {
    double t = (double)i / elementsAlongCurve;
    
    // 1. 곡선 위 위치
    Vector2D pos = evaluateCurve(t);
    
    // 2. 접선 벡터 (곡선 방향)
    Vector2D tangent = evaluateTangent(t).normalized();
    
    // 3. 법선 벡터 (접선에 수직)
    Vector2D normal(-tangent.y, tangent.x);
    
    // 4. 단면 노드 생성
    for (int k = 0; k <= elementsK; ++k) {
        for (int j = 0; j <= elementsJ; ++j) {
            double y = (j / (double)elementsJ - 0.5) * width;
            double z = (k / (double)elementsK - 0.5) * thickness;
            
            // 3D 위치
            Vector3D nodePos(
                pos.x + normal.x * z,  // X = 곡선 X + 법선 * 두께
                y,                      // Y = 폭 방향
                pos.y + normal.y * z   // Z = 곡선 Y + 법선 * 두께
            );
            
            mesh.addNode(nodeId++, nodePos.x, nodePos.y, nodePos.z);
        }
    }
}
```

### 스케일링 로직

```cpp
// Reference가 있을 때 스케일링
if (hasReference) {
    double refLength = refFlatMesh.boundingBox.sizeX;
    double curveArcLength = computeArcLength(curvePoints);
    double scaleFactor = refLength / curveArcLength;
    
    // 모든 좌표에 스케일 적용
    for (auto& pt : curvePoints) {
        pt.x *= scaleFactor;
        pt.y *= scaleFactor;
    }
    
    // 단면 크기도 레퍼런스에서
    width = refFlatMesh.boundingBox.sizeY;
    thickness = refFlatMesh.boundingBox.sizeZ;
}
```

---

## 구현 구조

### 새 파일

```
include/generator/
  CurveInterpolator.h       # B-spline, Catmull-Rom 보간
  CurvedMeshGenerator.h     # 곡선 따라 메쉬 생성
  
src/generator/
  CurveInterpolator.cpp
  CurvedMeshGenerator.cpp
```

### 클래스 설계

```cpp
// 곡선 보간기
class CurveInterpolator {
public:
    enum class Type { LINEAR, CATMULL_ROM, BSPLINE };
    
    void setControlPoints(const std::vector<Vector2D>& points);
    void setType(Type type);
    
    Vector2D evaluate(double t) const;       // 위치
    Vector2D evaluateTangent(double t) const; // 접선
    double getArcLength() const;             // 총 길이
    double paramAtArcLength(double s) const; // arc length → t
};

// 곡선 메쉬 생성기
class CurvedMeshGenerator {
public:
    struct Config {
        std::vector<Vector2D> centerlinePoints;
        CurveInterpolator::Type interpolation;
        
        double width;           // J 방향
        double thickness;       // K 방향
        
        int elementsAlongCurve;
        int elementsJ;
        int elementsK;
    };
    
    Mesh generate(const Config& config);
    Mesh generate(const Config& config, const Mesh& refFlat);
};
```

### YamlConfigReader 확장

```cpp
// type 필드 추가
enum class MeshType { FLAT, CURVED };

struct ExtendedConfig {
    MeshType type;
    
    // Flat 설정 (기존)
    VariableDensityConfig flatConfig;
    
    // Curved 설정 (새로 추가)
    CurvedMeshConfig curvedConfig;
};
```

---

## 구현 단계

### Phase 1: 곡선 보간기 (1시간)
1. [ ] `Vector2D` 클래스 (또는 기존 활용)
2. [ ] `CurveInterpolator` 기본 구현
3. [ ] Catmull-Rom 스플라인 구현
4. [ ] Arc length 계산

### Phase 2: 곡선 메쉬 생성기 (2시간)
5. [ ] `CurvedMeshGenerator` 클래스
6. [ ] 접선/법선 계산
7. [ ] 단면 노드 배치
8. [ ] HEX8 요소 생성

### Phase 3: YAML 스키마 확장 (1시간)
9. [ ] `type` 필드 파싱
10. [ ] `centerline_points` 파싱
11. [ ] `cross_section` 파싱
12. [ ] 레퍼런스 스케일링 로직

### Phase 4: CLI 통합 (30분)
13. [ ] `generate-var` 명령어 확장
14. [ ] 도움말 업데이트

### Phase 5: 테스트 (30분)
15. [ ] 4가지 케이스 예제 파일 작성
16. [ ] 생성 테스트
17. [ ] 매핑 테스트 (curved → flat 언폴드 검증)

---

## 예상 출력

### Curved 메쉬 생성 결과

```
============================================================
  KooRemapper - Mesh Mapping Tool for LS-DYNA
  Version 1.0.0
============================================================

[INFO] Reading configuration: custom_curve.yaml
[OK] Configuration loaded
Type:                    curved
Centerline points:       7
Interpolation:           catmull_rom

[INFO] Loading reference mesh: ufold_ref_flat.k
[OK] Reference dimensions: 150.283 x 70.000 x 1.000

[INFO] Computing curve properties...
Original arc length:     156.832
Scale factor:            0.958
Scaled arc length:       150.283 ✓

[INFO] Generating curved mesh...
[========================================] 100%
[OK] Generated 124,000 nodes, 110,000 elements

============================================================
Curve Statistics
============================================================
Arc length:              150.283 (matches reference)
Cross section:           70.000 x 1.000
Max curvature:           0.0234 at t=0.52
Min radius:              42.74

[INFO] Writing output: custom_bent.k
[OK] Output written successfully
```

---

## 활용 시나리오

### 시나리오 1: 실제 측정 데이터 기반 굽힘

```yaml
# 실제 측정된 foldable display 굽힘 형상
type: curved
reference:
  flat_mesh: "display_flat.k"

centerline_points:
  # 측정 데이터에서 추출한 좌표
  - [0.0, 0.0]
  - [10.5, 0.2]
  - [21.3, 1.1]
  - [32.8, 3.5]
  # ... 더 많은 측정점
```

### 시나리오 2: 수학적 곡선 정의

```python
# Python으로 좌표 생성 후 YAML에 입력
import numpy as np

# 예: 사인파 굽힘
x = np.linspace(0, 150, 50)
y = 5 * np.sin(x * np.pi / 50)

for xi, yi in zip(x, y):
    print(f"  - [{xi:.2f}, {yi:.2f}]")
```

---

## 향후 확장 가능성

1. **3D 곡선**: (x, y, z) 좌표로 3차원 곡선 지원
2. **가변 단면**: 곡선 위치에 따라 단면 크기 변화
3. **가변 밀도**: curved 메쉬에도 zone 기반 밀도 적용
4. **다중 곡선**: 여러 세그먼트 연결
