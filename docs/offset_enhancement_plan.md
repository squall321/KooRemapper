# Offset Operation 완전 개선 계획 (10 Phases)

**목표**: 현재 한계점 14개 모두 해결, 산업용 수준의 robust offset operation 구현

**전체 예상 기간**: 8-10주

**우선순위 원칙**:
1. 안정성 (Stability) → 사용자 오류 방지
2. 정확도 (Accuracy) → 물리적으로 정확한 결과
3. 유연성 (Flexibility) → 다양한 use case 대응
4. 성능 (Performance) → 대용량 메쉬 처리

---

## Phase 1: 기본 품질 개선 (안정성 확보) ⭐⭐⭐

**목표**: 사용자 오류를 사전에 방지하고, 결과 품질 보장

**예상 기간**: 1주

### 1.1 Material Card Validation

**문제**:
- 잘못된 `material_card` 형식도 그대로 출력
- LS-DYNA 실행 시 오류 발생

**구현**:
```cpp
class MaterialCardValidator {
public:
    struct ValidationResult {
        bool isValid;
        std::vector<std::string> errors;
        std::vector<std::string> warnings;
    };

    ValidationResult validate(const std::string& materialCard);

private:
    bool checkKeywordFormat(const std::string& line);
    bool checkFieldCount(const std::string& keyword, const std::vector<std::string>& fields);
    bool checkFieldRanges(const std::string& keyword, const std::vector<double>& values);
};
```

**구현 상세**:
1. Keyword 인식 (*MAT_ELASTIC, *MAT_COHESIVE_*, etc.)
2. Field 수 검증 (각 MAT type별 기대값)
3. 값 범위 검증 (E>0, 0<nu<0.5, etc.)
4. @MID@ placeholder 존재 확인
5. 다중 카드 검증 (여러 줄)

**파일**:
- `include/validation/MaterialCardValidator.h` (신규)
- `src/validation/MaterialCardValidator.cpp` (신규)
- `src/assembly/AssemblyConfigReader.cpp` (validateMaterialCard 호출)

**테스트**:
```yaml
# 잘못된 예제
material_card: |
  *MAT_ELASTIC
  @MID@ 1000 0.3  # ❌ 필드 수 부족 → 경고

# 올바른 예제
material_card: |
  *MAT_ELASTIC
  $#     mid        ro         e        pr
       @MID@       1.0     10000       0.3  # ✅
```

### 1.2 Element Quality Check

**문제**:
- 생성된 요소의 품질 검증 없음
- Aspect ratio, Jacobian, warping 체크 없음

**구현**:
```cpp
class ElementQualityChecker {
public:
    struct QualityMetrics {
        double aspectRatio;
        double minJacobian;
        double maxWarping;
        double skewness;
    };

    QualityMetrics checkHex8(const std::array<Vector3D, 8>& nodes);
    QualityMetrics checkWedge6(const std::array<Vector3D, 6>& nodes);
    bool isAcceptable(const QualityMetrics& metrics);
};
```

**품질 기준**:
- Aspect ratio < 10 (경고: < 20, 오류: >= 20)
- Min Jacobian > 0.1 (경고: > 0.01, 오류: <= 0)
- Max warping < 30° (경고: < 45°, 오류: >= 60°)
- Skewness < 0.8 (경고: < 0.9, 오류: >= 0.95)

**파일**:
- `include/validation/ElementQualityChecker.h` (신규)
- `src/validation/ElementQualityChecker.cpp` (신규)
- `src/assembly/ModelAssembler.cpp` (extrudeToSolid 내 체크)

**출력**:
```
[INFO] Created 580 solid elements
[WARNING] 12 elements with aspect ratio > 10 (max: 15.3)
[WARNING] 3 elements with warping > 30° (max: 42.1°)
[OK] All elements have positive Jacobian
```

### 1.3 Self-Intersection Warning

**문제**:
- Concave 표면 + normal offset → 교차 가능
- 사전 감지 없음

**구현**:
```cpp
class IntersectionDetector {
public:
    struct Intersection {
        int elem1, elem2;
        Vector3D location;
    };

    std::vector<Intersection> detectSelfIntersections(
        const std::vector<AddedElement>& elements,
        const std::vector<AddedNode>& nodes);

private:
    bool elementsIntersect(const Element& e1, const Element& e2);
    bool triTriIntersect(const Vector3D t1[3], const Vector3D t2[3]);
};
```

**알고리즘**:
1. Bounding box 기반 broad phase
2. Triangle-triangle intersection test (Möller-Trumbore)
3. 교차된 요소 쌍 리스트 반환

**파일**:
- `include/validation/IntersectionDetector.h` (신규)
- `src/validation/IntersectionDetector.cpp` (신규)
- `src/assembly/ModelAssembler.cpp` (applyOffset 끝에 호출)

**출력**:
```
[WARNING] Self-intersection detected!
  Element 127 intersects with Element 234 at (10.2, 5.3, 2.1)
  Element 128 intersects with Element 235 at (10.5, 5.4, 2.1)
  Total: 2 intersections
[SUGGESTION] Consider using:
  - Fixed direction (±x/±y/±z) instead of +normal
  - Smaller offset distance (current: 1.5mm)
  - Region selection to exclude concave areas
```

---

## Phase 2: 방향 개선 (정확도 향상) ⭐⭐⭐

**목표**: 복잡한 곡면에서 균일한 두께 보장

**예상 기간**: 1.5주

### 2.1 Local Normal Option

**문제**:
- Global average normal만 지원
- 복잡한 곡면에서 불균일한 두께

**구현**:
```cpp
enum class NormalMode {
    GLOBAL_AVERAGE,   // 기존: 모든 면의 평균
    LOCAL_AVERAGE,    // 신규: 각 노드별 인접 면 평균
    WEIGHTED_AVERAGE  // 신규: 면적 가중 평균
};

Vector3D ModelAssembler::computeNodeNormal(
    int nodeId,
    const std::vector<ShellElement>& surface,
    NormalMode mode);
```

**알고리즘**:
```
Local Average:
  1. 노드를 공유하는 모든 표면 면 수집
  2. 각 면의 법선 계산
  3. 평균 (또는 면적 가중 평균)
  4. 정규화

Weighted Average:
  1. 면 법선 * 면 면적
  2. 합산 후 정규화
  → 큰 면의 영향력 증가 (smooth)
```

**YAML**:
```yaml
- type: offset
  offset_direction: local_normal     # 신규
  normal_mode: weighted              # global | local | weighted
```

**파일**:
- `include/assembly/AssemblyConfig.h` (NormalMode enum 추가)
- `src/assembly/AssemblyConfigReader.cpp` (normal_mode 파싱)
- `src/assembly/ModelAssembler.cpp` (computeNodeNormal 구현)

**테스트**:
- 구형 표면 offset
- 원통형 표면 offset
- 복잡한 곡면 (말굽, 토러스)

### 2.2 Normal Smoothing

**문제**:
- 예각 모서리에서 법선 불연속

**구현**:
```cpp
void ModelAssembler::smoothNormals(
    std::map<int, Vector3D>& nodeNormals,
    int iterations,
    double relaxation);
```

**알고리즘**:
```
Laplacian smoothing:
  for iter in 1..iterations:
    for each node:
      n_new = (1-α) * n_old + α * avg(n_neighbors)
      n_new.normalize()
```

**YAML**:
```yaml
- type: offset
  offset_direction: local_normal
  smooth_normals: true
  smooth_iterations: 3
  smooth_relaxation: 0.5
```

---

## Phase 3: 선택 기능 (유연성 확보) ⭐⭐

**목표**: 부분 표면 offset, 영역 선택 지원

**예상 기간**: 2주

### 3.1 Region Selection

**문제**:
- 전체 표면만 offset 가능
- 특정 영역 선택 불가

**구현**:
```cpp
struct RegionSelector {
    enum Type { BBOX, NODE_SET, DIRECTION_FILTER, MANUAL_FACES };
    Type type;

    // BBOX
    double xmin, xmax, ymin, ymax, zmin, zmax;

    // NODE_SET
    std::vector<int> nodeIds;

    // DIRECTION_FILTER
    Vector3D direction;
    double angleThreshold;  // degrees

    // MANUAL_FACES
    std::vector<std::array<int, 4>> faceNodeIds;
};

std::vector<ShellElement> ModelAssembler::selectRegion(
    const std::vector<ShellElement>& allSurface,
    const RegionSelector& selector);
```

**YAML 예시**:

```yaml
# Bounding box selection
- type: offset
  source_pid: 1
  region_selection:
    type: bbox
    xmin: 0
    xmax: 10
    zmin: 5  # 상단만 offset
  thickness: 1.0

# Direction filter (특정 방향 면만)
- type: offset
  source_pid: 1
  region_selection:
    type: direction_filter
    direction: [0, 0, 1]  # +Z 방향 면만
    angle_threshold: 30   # ±30° 이내
  thickness: 1.0

# Node set (수동 선택)
- type: offset
  source_pid: 1
  region_selection:
    type: node_set
    node_ids: [1, 5, 10, 23, 45, ...]  # 특정 노드만
  thickness: 1.0
```

**파일**:
- `include/assembly/AssemblyConfig.h` (RegionSelector struct)
- `src/assembly/AssemblyConfigReader.cpp` (region_selection 파싱)
- `src/assembly/ModelAssembler.cpp` (selectRegion 구현)

**알고리즘**:

```cpp
// BBOX filter
bool inBoundingBox(const ShellElement& shell, const RegionSelector& sel) {
    for (int nid : shell.nodeIds) {
        Vector3D pos = getNodePosition(nid);
        if (pos.x < sel.xmin || pos.x > sel.xmax) return false;
        if (pos.y < sel.ymin || pos.y > sel.ymax) return false;
        if (pos.z < sel.zmin || pos.z > sel.zmax) return false;
    }
    return true;
}

// Direction filter
bool matchesDirection(const ShellElement& shell, const RegionSelector& sel) {
    Vector3D normal = computeElementNormal(shell);
    double angle = acos(normal.dot(sel.direction)) * 180 / M_PI;
    return angle <= sel.angleThreshold;
}
```

### 3.2 Multi-Region Offset

**확장**: 한 operation에서 여러 영역에 각각 다른 설정 적용

```yaml
- type: offset
  source_pid: 1
  regions:
    - selection:
        type: direction_filter
        direction: [0, 0, 1]  # 상면
      thickness: 2.0
      material_card: MAT_THICK

    - selection:
        type: direction_filter
        direction: [0, 0, -1]  # 하면
      thickness: 0.5
      material_card: MAT_THIN
```

---

## Phase 4: 가변 두께 (고급 기능) ⭐⭐

**목표**: 위치에 따라 다른 두께 적용

**예상 기간**: 1.5주

### 4.1 Thickness Formula

**구현**:
```cpp
class ThicknessEvaluator {
public:
    double evaluate(const Vector3D& position,
                   const std::string& formula);

private:
    FormulaEvaluator formulaEval_;  // 기존 bend에서 사용
};
```

**YAML**:
```yaml
- type: offset
  source_pid: 1
  thickness_mode: formula
  thickness_formula: "1.0 + 0.5 * sin(pi * x / 20)"
  # 변수: x, y, z (절대 좌표)
  #      L_x, L_y, L_z (bbox 크기)
  #      pi
```

### 4.2 Nodal Thickness Map

**구현**:
```cpp
std::map<int, double> ModelAssembler::loadThicknessMap(
    const std::string& filename);
```

**파일 형식** (thickness.dat):
```
# NodeID  Thickness(mm)
1         1.0
2         1.2
5         0.8
10        1.5
...
```

**YAML**:
```yaml
- type: offset
  source_pid: 1
  thickness_mode: nodal_map
  thickness_map_file: thickness.dat
  default_thickness: 1.0  # 미지정 노드
```

**보간**:
- 면 중심 두께 = 4개 노드 평균
- 각 layer 노드는 면 중심 두께 사용

### 4.3 Adaptive Thickness (Self-Intersection 회피)

**구현**:
```cpp
double ModelAssembler::computeAdaptiveThickness(
    const Vector3D& position,
    const Vector3D& direction,
    double requestedThickness,
    const std::vector<Element>& allElements);
```

**알고리즘**:
```
1. Ray-casting: position + direction * t
2. 첫 교차점까지 거리 = max_safe_thickness
3. actual_thickness = min(requested, max_safe * safety_factor)
4. safety_factor = 0.9 (10% 여유)
```

**YAML**:
```yaml
- type: offset
  source_pid: 1
  thickness: 2.0
  adaptive_thickness: true
  safety_factor: 0.9  # max의 90%까지만
```

---

## Phase 5: Shell Source 지원 (확장성) ⭐⭐

**목표**: Shell element를 source로 사용 가능

**예상 기간**: 1.5주

### 5.1 Shell Surface Extraction

**문제**:
- 현재는 solid face만 추출
- Shell은 이미 표면 (추출 불필요)

**구현**:
```cpp
void ModelAssembler::extractShellSurface(
    int sourcePid,
    std::vector<ShellElement>& surface);
```

**알고리즘**:
```
1. baseMesh_.getShellElements() 순회
2. partId == sourcePid인 것만 수집
3. 그대로 surface에 추가 (이미 QUAD4/TRIA3)
```

**YAML**:
```yaml
base_model: shell_model.k  # QUAD4/TRIA3만 있는 모델

operations:
  - type: offset
    source_pid: 1  # Shell part
    thickness: 1.0
    element_type: solid  # Shell → Solid extrusion
```

### 5.2 Shell → Solid Extrusion

**이미 구현됨!**
- `extrudeToSolid()`는 `std::vector<ShellElement>`를 받음
- Shell source에도 그대로 사용 가능

### 5.3 Shell → TShell Extrusion

**이미 구현됨!**
- `extrudeToTShell()`도 `std::vector<ShellElement>`를 받음

### 5.4 Shell → Shell Offset

**구현**:
- `createOffsetShell()`도 이미 지원
- 단, shell_offset 파라미터 의미 변경:
  - Solid source: mid-plane offset
  - Shell source: 기존 shell에서 떨어진 거리

**수정**:
```cpp
void ModelAssembler::applyOffset(...) {
    // Auto-detect source type
    bool isShellSource = isShellPart(op.sourcePid);

    if (isShellSource) {
        extractShellSurface(op.sourcePid, sourceSurface);
    } else {
        extractSourceSurface(op.sourcePid, sourceSurface);
    }

    // Rest is same
}
```

---

## Phase 6: Multi-Material Layers (복합 구조) ⭐

**목표**: 한 operation으로 다층 다재료 생성

**예상 기간**: 1주

### 6.1 Layers Array Format

**현재** (연속 offset 필요):
```yaml
- type: offset
  source_pid: 1
  material_card: MAT1
  new_pid: 10

- type: offset
  source_pid: 10
  material_card: MAT2
  new_pid: 11
```

**신규** (한번에):
```yaml
- type: offset
  source_pid: 1
  offset_direction: +z
  layers:
    - thickness: 0.5
      material_card: |
        *MAT_ELASTIC
        @MID@ 1.0 5000 0.3
      part_title: "Layer 1"

    - thickness: 0.3
      material_card: |
        *MAT_ELASTIC
        @MID@ 1.2 8000 0.35
      part_title: "Layer 2"

    - thickness: 0.2
      material_card: |
        *MAT_COHESIVE_MIXED_MODE
        @MID@ 1.0 1e6 1e6 1.0 2.0 1.0
      part_title: "Interface Layer"
      element_type: cohesive  # Special
```

### 6.2 구현

**Config**:
```cpp
struct OffsetLayer {
    double thickness;
    std::string materialCard;
    std::string partTitle;
    std::string elementType;  // solid | tshell | shell | cohesive
};

struct OffsetOperation {
    // ... 기존 ...
    std::vector<OffsetLayer> layers;  // 신규
};
```

**알고리즘**:
```cpp
void ModelAssembler::applyMultiLayerOffset(const OffsetOperation& op) {
    std::vector<ShellElement> currentSurface = baseSurface;

    for (size_t i = 0; i < op.layers.size(); ++i) {
        const auto& layer = op.layers[i];
        int layerPid = op.newPid + i;

        if (layer.elementType == "cohesive") {
            // Zero-thickness CZM
            createCohesiveInterface(currentSurface, layer, layerPid);
        } else {
            // Regular extrusion
            extrudeLayer(currentSurface, layer, layerPid);
            // Update currentSurface to top of this layer
            currentSurface = getTopSurface();
        }
    }
}
```

**자동 ID 할당**:
```
Layer 1: PID = newPid + 0, SECID = newSecid + 0, MID = newMid + 0
Layer 2: PID = newPid + 1, SECID = newSecid + 1, MID = newMid + 1
...
```

---

## Phase 7: CZM/Contact 개선 (사용성) ⭐

**목표**: CZM/Contact를 쉽게 사용

**예상 기간**: 1주

### 7.1 CZM Material Library

**구현**:
```cpp
class CzmMaterialLibrary {
public:
    struct CzmMaterial {
        std::string name;
        double EN, ET;        // Stiffness
        double GIC, GIIC;     // Fracture energy
        double T, S;          // Strength
        double XMU;           // Mode mixity
    };

    static const std::map<std::string, CzmMaterial> library;
    std::string generateMaterialCard(const std::string& materialName, int mid);
};
```

**Library**:
```cpp
const std::map<std::string, CzmMaterial> CzmMaterialLibrary::library = {
    {"epoxy_carbon", {1e6, 1e6, 0.5, 1.0, 50, 80, 1.0}},
    {"aluminum_adhesive", {5e5, 5e5, 0.3, 0.6, 30, 40, 1.0}},
    {"polymer_weak", {1e5, 1e5, 0.1, 0.2, 10, 15, 1.0}},
    // ... more
};
```

**YAML**:
```yaml
# 기존 (수동)
- type: offset
  connection_mode: czm
  czm_material_card: |
    *MAT_COHESIVE_MIXED_MODE
    ...

# 신규 (library)
- type: offset
  connection_mode: czm
  czm_material: epoxy_carbon  # Library name

# 또는 override
- type: offset
  connection_mode: czm
  czm_material: epoxy_carbon
  czm_override:
    GIC: 0.8    # 특정 값만 override
    GIIC: 1.5
```

### 7.2 Auto-Contact Generation

**현재**: Template만 주석 출력

**신규**: 자동 활성화 옵션

**YAML**:
```yaml
- type: offset
  connection_mode: contact
  auto_contact: true          # 자동 생성
  contact_type: automatic     # automatic | mortar | tied
  friction: 0.3
  penalty_stiffness: 1.0
```

**구현**:
```cpp
void ModelAssembler::createContactDefinition(
    int ssid, int msid,
    const std::string& contactType,
    double friction,
    double penalty) {

    std::ostringstream oss;
    if (contactType == "automatic") {
        oss << "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n";
        // ...
    } else if (contactType == "mortar") {
        oss << "*CONTACT_MORTAR\n";
        // ...
    }
    addedKeywordBlocks_.push_back(oss.str());
}
```

---

## Phase 8: TET 지원 개선 (정확도) ⭐

**목표**: TET4 source에서 올바른 요소 생성

**예상 기간**: 1주

### 8.1 TRIA3 → WEDGE6 Extrusion

**문제**:
- TET4 표면은 TRIA3
- TRIA3 → HEX8은 degenerate (3 nodes 중복)
- 올바른 방법: TRIA3 → WEDGE6 (prism)

**구현**:
```cpp
void ModelAssembler::extrudeToWedge(
    const std::vector<ShellElement>& surface,
    const Vector3D& direction,
    double thickness, int numLayers,
    int newPid, int newSecid);
```

**WEDGE6 구조**:
```
     5
    /|\
   / | \
  3-----4
  |  2  |
  | / \ |
  |/   \|
  0-----1
```

**알고리즘**:
```
for each TRIA3 face:
  for layer in 0..(numLayers-1):
    WEDGE6:
      N0, N1, N2 = bottom triangle (layer)
      N3, N4, N5 = top triangle (layer+1)
```

**LS-DYNA 출력**:
```
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
     123       1     101     102     103     104     105     106     106     106
              ^ WEDGE6: N6=N7=N8 (degenerate HEX8)
```

### 8.2 Element Type Detection

**자동 감지**:
```cpp
ElementType ModelAssembler::detectSourceElementType(int sourcePid) {
    for (const auto& pair : baseMesh_.getElements()) {
        if (pair.second.partId == sourcePid) {
            if (isTet4(pair.second)) return ElementType::TET4;
            if (isHex8(pair.second)) return ElementType::HEX8;
        }
    }
    // ...
}
```

**자동 extrusion 선택**:
```cpp
if (sourceType == ElementType::TET4 && op.elementType == "solid") {
    extrudeToWedge(...);  // TRIA3 → WEDGE6
} else if (sourceType == ElementType::HEX8 && op.elementType == "solid") {
    extrudeToSolid(...);  // QUAD4 → HEX8
}
```

---

## Phase 9: Performance 최적화 (대용량) ⭐

**목표**: 100만 요소급 메쉬에서도 빠른 처리

**예상 기간**: 1.5주

### 9.1 Parallel Face Extraction

**현재**: 순차 처리
**신규**: OpenMP 병렬화

**구현**:
```cpp
void ModelAssembler::extractSourceSurfaceParallel(
    int sourcePid,
    std::vector<ShellElement>& surfaceShells) {

    // Thread-local face maps
    std::vector<std::map<FaceKey, int>> localMaps(numThreads);

    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        auto& localMap = localMaps[tid];

        #pragma omp for
        for (int i = 0; i < elements.size(); ++i) {
            // Process element faces
            // ...
        }
    }

    // Merge local maps
    mergeThreadLocalMaps(localMaps);
}
```

**CMakeLists.txt**:
```cmake
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(kooremapper_lib PUBLIC OpenMP::OpenMP_CXX)
endif()
```

### 9.2 Spatial Hashing (Self-Intersection)

**현재**: O(N²) brute-force
**신규**: O(N) spatial hash

**구현**:
```cpp
class SpatialHash {
public:
    void insert(int elemId, const BoundingBox& bbox);
    std::vector<int> query(const BoundingBox& bbox);

private:
    double cellSize_;
    std::unordered_map<GridCell, std::vector<int>> grid_;
};
```

**알고리즘**:
```
1. BBox → grid cells
2. Hash: (x/cellSize, y/cellSize, z/cellSize)
3. Query: 주변 cells만 검사 (27개)
4. Broad phase 후 정밀 검사
```

### 9.3 Memory Pool

**현재**: 매번 new/delete
**신규**: Pre-allocated pool

**구현**:
```cpp
class NodePool {
public:
    NodePool(size_t reserveSize) {
        nodes_.reserve(reserveSize);
    }

    int allocate(const Vector3D& pos) {
        nodes_.push_back({nextId_++, pos.x, pos.y, pos.z});
        return nextId_ - 1;
    }

private:
    std::vector<AddedNode> nodes_;
    int nextId_ = 0;
};
```

---

## Phase 10: 통합 및 검증 ⭐⭐⭐

**목표**: 모든 개선사항 통합, 전체 테스트, 문서화

**예상 기간**: 2주

### 10.1 통합 테스트 Suite

**테스트 커버리지**:
```
tests/offset/
  ├─ basic/
  │  ├─ solid_tied.yaml
  │  ├─ tshell_multi.yaml
  │  └─ shell_offset.yaml
  │
  ├─ connection/
  │  ├─ czm_library.yaml          # Phase 7
  │  ├─ czm_custom.yaml
  │  └─ auto_contact.yaml         # Phase 7
  │
  ├─ direction/
  │  ├─ global_normal.yaml
  │  ├─ local_normal.yaml         # Phase 2
  │  ├─ weighted_normal.yaml      # Phase 2
  │  └─ smooth_normal.yaml        # Phase 2
  │
  ├─ region/
  │  ├─ bbox_selection.yaml       # Phase 3
  │  ├─ direction_filter.yaml     # Phase 3
  │  └─ multi_region.yaml         # Phase 3
  │
  ├─ thickness/
  │  ├─ formula.yaml              # Phase 4
  │  ├─ nodal_map.yaml            # Phase 4
  │  └─ adaptive.yaml             # Phase 4
  │
  ├─ source/
  │  ├─ shell_source_solid.yaml   # Phase 5
  │  ├─ shell_source_tshell.yaml  # Phase 5
  │  └─ tet4_source.yaml          # Phase 8
  │
  ├─ multilayer/
  │  ├─ layers_array.yaml         # Phase 6
  │  └─ mixed_types.yaml          # Phase 6
  │
  ├─ validation/
  │  ├─ bad_material.yaml         # Phase 1 (should fail)
  │  ├─ self_intersect.yaml       # Phase 1 (should warn)
  │  └─ poor_quality.yaml         # Phase 1 (should warn)
  │
  └─ performance/
     ├─ large_mesh_100k.yaml      # Phase 9
     └─ large_mesh_1M.yaml        # Phase 9
```

### 10.2 자동화된 검증

**CI/CD 통합**:
```bash
#!/bin/bash
# tests/offset/run_all_tests.sh

echo "Running all offset tests..."

for test in tests/offset/**/*.yaml; do
    echo "Testing: $test"
    KooRemapper assemble "$test" || exit 1
done

echo "All tests passed!"
```

**성능 벤치마크**:
```cpp
// tests/offset/benchmark.cpp
void benchmarkOffsetOperation() {
    auto start = std::chrono::high_resolution_clock::now();

    // Run offset
    // ...

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);

    std::cout << "Offset operation time: " << duration.count() << " ms\n";

    // Assert performance target
    ASSERT_LT(duration.count(), 1000);  // < 1 second
}
```

### 10.3 문서 완전 업데이트

**KooRemapper_Guide.txt**:
1. 3.2 [offset] 섹션 확장
   - 모든 신규 파라미터 추가
   - 예제 20개 이상

2. 3.29 Offset 이론 확장
   - Local normal 이론
   - Region selection 알고리즘
   - Variable thickness 수학
   - Performance 최적화 설명

**신규 문서**:
```
docs/
  ├─ offset_user_guide.md          # 사용자 가이드 (한글+영문)
  ├─ offset_api_reference.md       # API 레퍼런스
  ├─ offset_cookbook.md            # 요리책 (실전 예제 30개)
  └─ offset_troubleshooting.md     # 문제 해결 가이드
```

### 10.4 예제 확장

**examples/offset/ 구조**:
```
examples/offset/
  ├─ basic/              # 기본 (6개) - 기존
  ├─ advanced/           # 고급 (신규)
  │  ├─ local_normal_sphere.yaml
  │  ├─ adaptive_concave.yaml
  │  ├─ variable_thickness_thermal.yaml
  │  └─ ...
  ├─ industrial/         # 산업 응용 (신규)
  │  ├─ battery_pouch_wrapping.yaml
  │  ├─ composite_laminate.yaml
  │  ├─ thermal_barrier_coating.yaml
  │  └─ ...
  └─ cookbook/           # 요리책 (신규)
     ├─ 01_simple_insulation.yaml
     ├─ 02_multi_layer_composite.yaml
     ├─ ...
     └─ 30_complex_assembly.yaml
```

---

## 📊 전체 일정 요약

| Phase | 주제 | 기간 | 우선순위 |
|-------|------|------|----------|
| 1 | 기본 품질 개선 | 1주 | ⭐⭐⭐ |
| 2 | 방향 개선 | 1.5주 | ⭐⭐⭐ |
| 3 | 선택 기능 | 2주 | ⭐⭐ |
| 4 | 가변 두께 | 1.5주 | ⭐⭐ |
| 5 | Shell Source | 1.5주 | ⭐⭐ |
| 6 | Multi-Material | 1주 | ⭐ |
| 7 | CZM/Contact 개선 | 1주 | ⭐ |
| 8 | TET 지원 | 1주 | ⭐ |
| 9 | Performance | 1.5주 | ⭐ |
| 10 | 통합 검증 | 2주 | ⭐⭐⭐ |
| **합계** | | **14주 (3.5개월)** | |

**병렬 작업 가능**:
- Phase 1-2: 동시 진행 가능 (다른 파일)
- Phase 3-5: 부분 병렬 가능
- Phase 6-8: 독립적, 병렬 가능

**실제 예상**: **8-10주** (병렬 작업 시)

---

## 🎯 마일스톤

### Milestone 1 (4주차)
- ✅ Phase 1-2 완료
- 품질 검증 + Local normal 작동
- **배포**: v1.4.0-alpha

### Milestone 2 (8주차)
- ✅ Phase 3-5 완료
- Region selection + Shell source 작동
- **배포**: v1.4.0-beta

### Milestone 3 (10주차)
- ✅ Phase 6-9 완료
- Multi-layer + Performance 개선
- **배포**: v1.4.0-rc1

### Milestone 4 (12주차)
- ✅ Phase 10 완료
- 전체 테스트 통과
- **배포**: v1.4.0 (정식)

---

## 🔧 구현 우선순위 (단계적 배포)

사용자가 **지금 당장** 원하는 기능에 따라:

### Option A: 안정성 우선
```
Phase 1 → Phase 2 → Phase 10 (부분)
(4주 만에 robust + local normal 배포)
```

### Option B: 기능 우선
```
Phase 2 → Phase 3 → Phase 4
(5주 만에 local normal + region + variable thickness)
```

### Option C: 완전성 우선
```
Phase 1-10 순차 진행
(12주 만에 완전한 시스템)
```

---

## 📝 다음 단계

1. **우선순위 확인**: 어떤 Phase를 먼저 시작할까요?
2. **리소스 확인**: 혼자? 팀? 작업 시간?
3. **배포 전략**: Alpha/Beta 단계별? 한번에?

**지금 시작할 Phase를 선택해주세요!** 🚀

---

**이 계획으로 Offset operation이 산업용 수준의 완전한 기능을 갖추게 됩니다.**
