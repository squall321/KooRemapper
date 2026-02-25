# Warpage Operation 개발 계획서

> **목적**: 측정 데이터 기반 휨(warpage) 패턴을 메시에 적용하고, Dynamic Relaxation 시 원래 휨 형상으로 복원되도록 역방향 초기 응력을 생성

---

## 1. 요구사항 정리

### 1.1 입력 데이터 포맷

**파일**: `warpage.dat` (또는 사용자 지정 경로)

**형식**:
- 탭(`\t`) 또는 공백(` `) 구분 2D 그리드
- 예시: 15×15 행렬 (가변 크기 지원)
- 각 셀: 부동소수점 숫자 또는 마스킹 값

**좌표계 규칙**:
```
            +X →
        ┌─────────────┐
    +Y  │ row 0       │  (상단 = Y_max)
     ↓  │             │
        │             │
        │             │
        └─────────────┘  (하단 = Y_min)
     left=X_min  right=X_max
```

- **행(row)**: row 0 = Y_max (상단), row N-1 = Y_min (하단)
- **열(col)**: col 0 = X_min (좌측), col M-1 = X_max (우측)
- **값**: Z 방향 처짐량 (warpage)

**특수 값 처리**:
- `9999` (또는 사용자 지정 마스킹 값) → **마스킹된 데이터**
  - 주변 유효 데이터로부터 **양방향 선형 보간(bilinear interpolation)** 수행
  - 마스킹 영역이 크면 **inpainting** 알고리즘 (Laplacian smoothing) 적용
- 매우 작은 값 (`< 1e-10`) → 0으로 간주 (노이즈 제거)

**단위**:
- 기본값: **μm (마이크로미터)**
- 사용자 지정 가능: `mm`, `m` 등
- 모델 단위로 자동 변환

---

### 1.2 물리 모델

#### 1.2.1 휨(warpage)의 정의

평면 파트가 휨에 의해 Z 방향으로 변형:

$$w(x, y) = \text{warpage deflection at } (x, y)$$

중립면 기준 곡률:

$$\kappa_{xx} = -\frac{\partial^2 w}{\partial x^2}, \quad \kappa_{yy} = -\frac{\partial^2 w}{\partial y^2}, \quad \kappa_{xy} = -\frac{\partial^2 w}{\partial x \partial y}$$

**수치 미분** (유한 차분, 2차 중심 차분):

$$\kappa_{xx}(i,j) \approx -\frac{w_{i-1,j} - 2w_{i,j} + w_{i+1,j}}{h_x^2}$$

$$\kappa_{yy}(i,j) \approx -\frac{w_{i,j-1} - 2w_{i,j} + w_{i,j+1}}{h_y^2}$$

$$\kappa_{xy}(i,j) \approx -\frac{w_{i+1,j+1} - w_{i+1,j-1} - w_{i-1,j+1} + w_{i-1,j-1}}{4 h_x h_y}$$

여기서:
- $h_x = \Delta x$ (그리드 간격 X)
- $h_y = \Delta y$ (그리드 간격 Y)

#### 1.2.2 굽힘 초기 응력 (Kirchhoff 판 이론)

중립면에서 거리 $z$인 지점의 굽힘 변형률:

$$\varepsilon_{xx}(z) = z \cdot \kappa_{xx}, \quad \varepsilon_{yy}(z) = z \cdot \kappa_{yy}, \quad \varepsilon_{xy}(z) = z \cdot \kappa_{xy}$$

평면응력 가정:

$$\sigma_{xx} = \frac{E}{1-\nu^2}(\varepsilon_{xx} + \nu \varepsilon_{yy})$$

$$\sigma_{yy} = \frac{E}{1-\nu^2}(\varepsilon_{yy} + \nu \varepsilon_{xx})$$

$$\sigma_{xy} = \frac{E}{1+\nu} \varepsilon_{xy}$$

#### 1.2.3 역방향 초기 응력 (Dynamic Relaxation 복원)

**목표**: 평탄한 초기 형상에 역방향 응력을 적용하여, DR 실행 시 원래 휨 형상으로 복원

**방법**:
1. 휨 형상의 곡률 $\kappa$ 계산
2. 굽힘 응력 $\sigma$ 계산
3. **부호 반전**: $\sigma_{init} = -\sigma$
4. `*INITIAL_STRESS_SOLID` 출력

**물리적 의미**:
- 평탄 상태 = "억지로 펼친 상태"
- 역방향 응력 = "복원력"
- DR 해석 → 응력 완화 → 원래 휨 형상으로 복귀

---

### 1.3 바운딩 박스 매핑

#### Case A: 데이터 bbox = 파트 bbox (1:1 매핑)

```yaml
- type: warpage
  target_pid: 1
  dat_file: warpage.dat
  plane: xy              # 면내 방향 (X, Y)
  deflection_axis: z     # 휨 방향 (Z)
  # bbox 미지정 → 파트 bbox 자동 사용
```

**동작**:
- 파트의 바운딩 박스 `[x_min, x_max] × [y_min, y_max]` 계산
- 데이터 그리드를 파트 bbox에 1:1 매핑
- 각 노드 $(x, y)$에 대해 양방향 선형 보간으로 $w(x, y)$ 계산

#### Case B: 사용자 지정 bbox (데이터는 일부 영역)

```yaml
- type: warpage
  target_pid: 1
  dat_file: warpage.dat
  plane: xy
  deflection_axis: z
  data_bbox:             # 데이터가 커버하는 물리적 영역
    x_min: 0.0
    x_max: 100.0
    y_min: 0.0
    y_max: 50.0
```

**동작**:
- 데이터는 지정된 `data_bbox` 영역을 커버
- 파트의 실제 bbox가 더 크면, 데이터가 그 일부만 커버
- 데이터 외부 영역: $w = 0$ (또는 경계값 외삽)

**예시**:
```
데이터 bbox: [0, 100] × [0, 50]  (15×15 그리드)
파트 bbox:   [-10, 110] × [-5, 55]

→ 파트 노드 중 데이터 bbox 내부만 휨 적용
→ 외부 노드는 w = 0 (평탄)
```

---

### 1.4 모핑(Morphing) — 휨 패턴 스케일링

**목적**: 휨의 정도를 증폭/감쇠

```yaml
- type: warpage
  target_pid: 1
  dat_file: warpage.dat
  plane: xy
  deflection_axis: z
  morph_factor: 1.5      # 1.5배 증폭 (기본값: 1.0)
```

**적용**:

$$w'(x, y) = \text{morph\_factor} \times w(x, y)$$

$$\kappa' = \text{morph\_factor} \times \kappa$$

$$\sigma' = \text{morph\_factor} \times \sigma$$

**사용 사례**:
- `morph_factor = 0.5` → 휨의 50%만 적용 (부분 복원)
- `morph_factor = 2.0` → 휨을 2배 과장 (worst-case 시뮬레이션)
- `morph_factor = -1.0` → 휨 방향 반전 (볼록 ↔ 오목)

---

## 2. YAML 인터페이스 설계

### 2.1 전체 YAML 구조

```yaml
base_model: flat_part.k
output: warpage_result

material:                # 전역 재료 (선택)
  E: 210000
  nu: 0.3

dynamic_relaxation: true # DR 키워드 자동 삽입 (필수)

operations:
  - type: warpage
    target_pid: 1
    dat_file: data/warpage.dat    # 휨 데이터 파일 (필수)

    # 좌표계 설정
    plane: xy                      # 면내 방향 (xy | yz | zx)
    deflection_axis: z             # 휨 방향 (+z | -z | +x | -x | +y | -y)

    # 데이터 해석
    unit: um                       # 데이터 단위 (um | mm | m, 기본: um)
    mask_value: 9999               # 마스킹 값 (기본: 9999)
    noise_threshold: 1.0e-10       # 노이즈 임계값 (기본: 1e-10)

    # 바운딩 박스 매핑 (선택)
    data_bbox:                     # 미지정 시 파트 bbox 사용
      x_min: 0.0
      x_max: 100.0
      y_min: 0.0
      y_max: 50.0

    # 모핑 (선택)
    morph_factor: 1.0              # 휨 스케일 (기본: 1.0)

    # 모드 선택
    mode: prestress                # prestress | deform (기본: prestress)

    # prestress 모드: 평탄 상태 + 역방향 초기 응력 (DR용)
    # deform 모드: 휨 형상 직접 적용 (노드 이동, 응력 없음)
```

### 2.2 파라미터 상세

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `target_pid` | int | (필수) | 대상 파트 ID |
| `dat_file` | string | (필수) | 휨 데이터 파일 경로 (상대/절대) |
| `plane` | string | `xy` | 면내 방향 (xy, yz, zx) |
| `deflection_axis` | string | `z` | 휨 방향 (+z, -z, +x, -x, +y, -y) |
| `unit` | string | `um` | 데이터 단위 (um, mm, m) |
| `mask_value` | double | `9999` | 마스킹 값 |
| `noise_threshold` | double | `1e-10` | 노이즈 제거 임계값 |
| `data_bbox` | object | (auto) | 데이터 물리 영역 (x_min, x_max, y_min, y_max) |
| `morph_factor` | double | `1.0` | 휨 스케일 배율 |
| `mode` | string | `prestress` | prestress (역응력) 또는 deform (직접 변형) |

---

## 3. 구현 계획

### 3.1 파일 구조

```
include/assembly/
  ├─ AssemblyConfig.h              ← WarpageOperation 구조체 추가
  └─ WarpageGrid.h                 ← 새 파일 (2D 그리드 + 보간)

src/assembly/
  ├─ AssemblyConfigReader.cpp      ← warpage YAML 파싱
  ├─ ModelAssembler.cpp             ← applyWarpage() 구현
  └─ WarpageGrid.cpp                ← 새 파일 (그리드 읽기/보간/곡률)
```

---

### 3.2 Phase 1: 데이터 구조 (`AssemblyConfig.h`)

```cpp
struct WarPageOperation {
    int targetPid = 0;
    std::string datFile;            // 필수
    std::string plane = "xy";       // xy | yz | zx
    std::string deflectionAxis = "z"; // +z | -z | +x | -x | +y | -y
    std::string unit = "um";        // um | mm | m
    double maskValue = 9999.0;
    double noiseThreshold = 1.0e-10;

    // data_bbox (선택)
    bool hasDataBbox = false;
    double dataBboxXmin = 0.0;
    double dataBboxXmax = 0.0;
    double dataBboxYmin = 0.0;
    double dataBboxYmax = 0.0;

    double morphFactor = 1.0;
    std::string mode = "prestress"; // prestress | deform
};

// AssemblyOperation::Type에 WARPAGE 추가
enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN,
            TET10_CONVERT, REFINE, ELFORM, DISCONNECT, IGA, WARPAGE };

// AssemblyOperation에 warpage 멤버 추가
WarpageOperation warpage;
```

---

### 3.3 Phase 2: WarpageGrid 클래스 (`WarpageGrid.h/cpp`)

```cpp
class WarpageGrid {
public:
    // 파일 읽기
    bool loadFromFile(const std::string& filepath, double maskValue, double noiseThreshold);

    // 마스킹 영역 보간
    void interpolateMaskedRegions();

    // 양방향 선형 보간
    double interpolate(double u, double v) const;  // u,v ∈ [0, 1]

    // 곡률 계산 (유한 차분)
    void computeCurvatures();
    double getCurvatureXX(int i, int j) const;
    double getCurvatureYY(int i, int j) const;
    double getCurvatureXY(int i, int j) const;

    // Getter
    int rows() const { return nRows_; }
    int cols() const { return nCols_; }
    double get(int i, int j) const { return data_[i][j]; }

private:
    int nRows_ = 0;
    int nCols_ = 0;
    std::vector<std::vector<double>> data_;      // 원본 데이터
    std::vector<std::vector<double>> kappa_xx_;  // 곡률 XX
    std::vector<std::vector<double>> kappa_yy_;  // 곡률 YY
    std::vector<std::vector<double>> kappa_xy_;  // 곡률 XY

    // 내부 헬퍼
    void parseTabDelimitedFile(const std::string& filepath);
    void applyMaskInterpolation(double maskValue);
    void removeNoise(double threshold);
};
```

#### 3.3.1 `loadFromFile()` 구현

```cpp
bool WarpageGrid::loadFromFile(const std::string& filepath, double maskValue, double noiseThreshold) {
    // 1. 파일 읽기 (tab/space delimited)
    parseTabDelimitedFile(filepath);

    // 2. 마스킹 영역 보간
    applyMaskInterpolation(maskValue);

    // 3. 노이즈 제거
    removeNoise(noiseThreshold);

    return true;
}
```

#### 3.3.2 마스킹 보간 알고리즘

**전략**: **Laplacian inpainting** (iterative smoothing)

```cpp
void WarpageGrid::applyMaskInterpolation(double maskValue) {
    // 마스킹 위치 기록
    std::vector<std::pair<int, int>> maskedCells;
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            if (std::abs(data_[i][j] - maskValue) < 1e-6) {
                maskedCells.push_back({i, j});
            }
        }
    }

    if (maskedCells.empty()) return;

    // Iterative Laplacian smoothing (Jacobi iteration)
    const int maxIter = 1000;
    const double tol = 1e-8;

    for (int iter = 0; iter < maxIter; ++iter) {
        double maxChange = 0.0;
        auto dataCopy = data_;

        for (auto [i, j] : maskedCells) {
            // 4-이웃 평균
            double sum = 0.0;
            int count = 0;
            if (i > 0)          { sum += dataCopy[i-1][j]; count++; }
            if (i < nRows_-1)   { sum += dataCopy[i+1][j]; count++; }
            if (j > 0)          { sum += dataCopy[i][j-1]; count++; }
            if (j < nCols_-1)   { sum += dataCopy[i][j+1]; count++; }

            if (count > 0) {
                double newVal = sum / count;
                maxChange = std::max(maxChange, std::abs(newVal - data_[i][j]));
                data_[i][j] = newVal;
            }
        }

        if (maxChange < tol) break;
    }
}
```

#### 3.3.3 곡률 계산 (유한 차분)

```cpp
void WarpageGrid::computeCurvatures() {
    kappa_xx_.resize(nRows_, std::vector<double>(nCols_, 0.0));
    kappa_yy_.resize(nRows_, std::vector<double>(nCols_, 0.0));
    kappa_xy_.resize(nRows_, std::vector<double>(nCols_, 0.0));

    double hx = 1.0 / (nCols_ - 1);  // 정규화 간격
    double hy = 1.0 / (nRows_ - 1);

    for (int i = 1; i < nRows_ - 1; ++i) {
        for (int j = 1; j < nCols_ - 1; ++j) {
            // κ_xx = -d²w/dx²
            kappa_xx_[i][j] = -(data_[i][j-1] - 2*data_[i][j] + data_[i][j+1]) / (hx*hx);

            // κ_yy = -d²w/dy²
            kappa_yy_[i][j] = -(data_[i-1][j] - 2*data_[i][j] + data_[i+1][j]) / (hy*hy);

            // κ_xy = -d²w/dxdy
            double dw_dxdy = (data_[i+1][j+1] - data_[i+1][j-1]
                            - data_[i-1][j+1] + data_[i-1][j-1]) / (4*hx*hy);
            kappa_xy_[i][j] = -dw_dxdy;
        }
    }
}
```

#### 3.3.4 양방향 선형 보간

```cpp
double WarpageGrid::interpolate(double u, double v) const {
    // u, v ∈ [0, 1] → grid index
    double fi = v * (nRows_ - 1);
    double fj = u * (nCols_ - 1);

    int i0 = static_cast<int>(std::floor(fi));
    int j0 = static_cast<int>(std::floor(fj));
    int i1 = std::min(i0 + 1, nRows_ - 1);
    int j1 = std::min(j0 + 1, nCols_ - 1);

    double dy = fi - i0;
    double dx = fj - j0;

    // Bilinear interpolation
    double w00 = data_[i0][j0];
    double w01 = data_[i0][j1];
    double w10 = data_[i1][j0];
    double w11 = data_[i1][j1];

    return (1-dx)*(1-dy)*w00 + dx*(1-dy)*w01 + (1-dx)*dy*w10 + dx*dy*w11;
}
```

---

### 3.4 Phase 3: YAML 파싱 (`AssemblyConfigReader.cpp`)

```cpp
// "type: warpage" 인식
else if (trimmed == "type: warpage") {
    op.type = AssemblyOperation::WARPAGE;
}

// operation sub-keys 파싱
else if (op.type == AssemblyOperation::WARPAGE) {
    if (key == "dat_file") op.warpage.datFile = val;
    else if (key == "plane") op.warpage.plane = val;
    else if (key == "deflection_axis") op.warpage.deflectionAxis = val;
    else if (key == "unit") op.warpage.unit = val;
    else if (key == "mask_value") op.warpage.maskValue = std::stod(val);
    else if (key == "noise_threshold") op.warpage.noiseThreshold = std::stod(val);
    else if (key == "morph_factor") op.warpage.morphFactor = std::stod(val);
    else if (key == "mode") op.warpage.mode = val;

    // data_bbox 섹션
    else if (key == "data_bbox") {
        inDataBboxSection = true;
        dataBboxIndent = indent;
        op.warpage.hasDataBbox = true;
    }
}

// data_bbox 서브키 파싱
if (inDataBboxSection && op.type == AssemblyOperation::WARPAGE) {
    if (indent <= dataBboxIndent) {
        inDataBboxSection = false;
    } else {
        if (key == "x_min") op.warpage.dataBboxXmin = std::stod(val);
        else if (key == "x_max") op.warpage.dataBboxXmax = std::stod(val);
        else if (key == "y_min") op.warpage.dataBboxYmin = std::stod(val);
        else if (key == "y_max") op.warpage.dataBboxYmax = std::stod(val);
    }
}
```

---

### 3.5 Phase 4: `applyWarpage()` 구현 (`ModelAssembler.cpp`)

#### 3.5.1 메서드 시그니처

```cpp
// ModelAssembler.h
bool applyWarpage(const WarpageOperation& op);

// ModelAssembler.cpp
bool ModelAssembler::applyWarpage(const WarpageOperation& op) {
    // 1. WarpageGrid 로드
    WarpageGrid grid;
    if (!grid.loadFromFile(op.datFile, op.maskValue, op.noiseThreshold)) {
        errorMessage_ = "Failed to load warpage data: " + op.datFile;
        return false;
    }

    // 2. 단위 변환 계수 계산
    double unitScale = getUnitScale(op.unit);  // um→1e-3, mm→1.0, m→1e3

    // 3. 파트 바운딩 박스 계산
    auto nodeIds = getPartNodeIds(op.targetPid);
    if (nodeIds.empty()) {
        errorMessage_ = "Warpage: part " + std::to_string(op.targetPid) + " has no nodes";
        return false;
    }

    BoundingBox partBbox = computeBoundingBox(nodeIds);

    // 4. 데이터 bbox 결정 (사용자 지정 또는 파트 bbox)
    BoundingBox dataBbox;
    if (op.hasDataBbox) {
        dataBbox = {op.dataBboxXmin, op.dataBboxXmax,
                    op.dataBboxYmin, op.dataBboxYmax};
    } else {
        dataBbox = partBbox;  // 1:1 매핑
    }

    // 5. 좌표계 결정 (plane, deflection_axis)
    int axis1, axis2, deflAxis;
    parseAxes(op.plane, op.deflectionAxis, axis1, axis2, deflAxis);

    // 6. 곡률 계산
    grid.computeCurvatures();

    // 7. 각 노드에 대해 처리
    for (int nid : nodeIds) {
        Vector3D pos = getNodePosition(nid);

        // 7.1 정규화 좌표 계산 (u, v ∈ [0, 1])
        double u = (pos[axis1] - dataBbox.xmin) / (dataBbox.xmax - dataBbox.xmin);
        double v = (pos[axis2] - dataBbox.ymin) / (dataBbox.ymax - dataBbox.ymin);

        // 데이터 bbox 외부 → 스킵
        if (u < 0 || u > 1 || v < 0 || v > 1) continue;

        // 7.2 처짐 보간
        double w = grid.interpolate(u, v) * unitScale * op.morphFactor;

        // 7.3 모드별 처리
        if (op.mode == "deform") {
            // 직접 변형: 노드 이동
            pos[deflAxis] += w;
            modifiedNodePositions_[nid] = pos;
        }
        else if (op.mode == "prestress") {
            // 역방향 초기 응력 계산 (평탄 상태 유지, 응력만)
            // → 아래 응력 계산 섹션에서 처리
        }
    }

    // 8. prestress 모드: 초기 응력 계산
    if (op.mode == "prestress") {
        calculateWarpagePrestress(op, grid, dataBbox, unitScale, axis1, axis2, deflAxis);
    }

    return true;
}
```

#### 3.5.2 초기 응력 계산 (`calculateWarpagePrestress()`)

```cpp
void ModelAssembler::calculateWarpagePrestress(
    const WarpageOperation& op,
    const WarpageGrid& grid,
    const BoundingBox& dataBbox,
    double unitScale,
    int axis1, int axis2, int deflAxis)
{
    // 재료 상수
    double E = config_.E;
    double nu = config_.nu;
    if (E <= 0) {
        // K-파일에서 재료 읽기 (findPartMid 재사용)
        int mid = findPartMid(op.targetPid);
        // ... 재료 파싱 ...
    }

    double factor = E / (1 - nu*nu);

    // 각 요소에 대해
    for (auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId != op.targetPid) continue;

        // 요소 중심 계산
        Vector3D centroid = computeElementCentroid(elem);

        // 정규화 좌표
        double u = (centroid[axis1] - dataBbox.xmin) / (dataBbox.xmax - dataBbox.xmin);
        double v = (centroid[axis2] - dataBbox.ymin) / (dataBbox.ymax - dataBbox.ymin);

        if (u < 0 || u > 1 || v < 0 || v > 1) continue;

        // 그리드 인덱스
        int i = static_cast<int>(v * (grid.rows() - 1));
        int j = static_cast<int>(u * (grid.cols() - 1));
        i = std::clamp(i, 1, grid.rows() - 2);
        j = std::clamp(j, 1, grid.cols() - 2);

        // 곡률 (물리 단위로 스케일)
        double physicalLenX = dataBbox.xmax - dataBbox.xmin;
        double physicalLenY = dataBbox.ymax - dataBbox.ymin;
        double scaledKappaXX = grid.getCurvatureXX(i, j) * unitScale / (physicalLenX * physicalLenX) * op.morphFactor;
        double scaledKappaYY = grid.getCurvatureYY(i, j) * unitScale / (physicalLenY * physicalLenY) * op.morphFactor;
        double scaledKappaXY = grid.getCurvatureXY(i, j) * unitScale / (physicalLenX * physicalLenY) * op.morphFactor;

        // 중립면에서 거리 (두께 t, 중립면 = t/2)
        double thickness = getElementThickness(elem);  // *SECTION_SOLID 또는 bbox Z 범위
        double z_neutral = thickness / 2.0;

        // 굽힘 변형률 (상면 z = +t/2, 하면 z = -t/2)
        // 적분점마다 다른 z 값 → 여기서는 중심(z=0)과 상/하면 평균으로 근사
        double eps_xx = z_neutral * scaledKappaXX;
        double eps_yy = z_neutral * scaledKappaYY;
        double eps_xy = z_neutral * scaledKappaXY;

        // 응력
        double sig_xx = factor * (eps_xx + nu * eps_yy);
        double sig_yy = factor * (eps_yy + nu * eps_xx);
        double sig_xy = (E / (1 + nu)) * eps_xy;

        // 역방향 응력 (부호 반전)
        sig_xx = -sig_xx;
        sig_yy = -sig_yy;
        sig_xy = -sig_xy;

        // elementStresses_ 맵에 저장 (기존 bend/indent와 동일 방식)
        StressTensor stress;
        stress.sigma_xx = sig_xx;
        stress.sigma_yy = sig_yy;
        stress.sigma_zz = 0.0;  // 평면응력
        stress.sigma_xy = sig_xy;
        stress.sigma_yz = 0.0;
        stress.sigma_xz = 0.0;

        // 누적 (기존 응력이 있으면 합산)
        if (elementStresses_.count(eid)) {
            elementStresses_[eid] = elementStresses_[eid] + stress;
        } else {
            elementStresses_[eid] = stress;
        }
    }
}
```

---

### 3.6 Phase 5: `main.cpp` 디스패치

```cpp
case AssemblyOperation::WARPAGE:
    if (!assembler.applyWarpage(op.warpage)) {
        std::cerr << "[ERROR] " << assembler.getErrorMessage() << "\n";
        return 1;
    }
    std::cout << "  [warpage] Applied to part " << op.warpage.targetPid
              << " (mode: " << op.warpage.mode << ")\n";
    break;
```

---

## 4. 검증 계획

### 4.1 단위 테스트

#### Test 1: 마스킹 보간

**입력**:
```
1.0  2.0  3.0
4.0  9999 6.0
7.0  8.0  9.0
```

**기대 출력** (중심 셀):
```
1.0  2.0  3.0
4.0  5.0  6.0   ← (4+6+2+8)/4 = 5.0
7.0  8.0  9.0
```

#### Test 2: 곡률 계산

**입력** (포물선 w = x²):
```
0.0  1.0  4.0  9.0  16.0
```

**기대 출력** (κ_xx):
```
# d²w/dx² = 2 (상수)
κ_xx ≈ -2.0 (everywhere)
```

#### Test 3: 양방향 선형 보간

**입력** 2×2 그리드:
```
0.0  1.0
2.0  3.0
```

**쿼리**: u=0.5, v=0.5 (중심)

**기대 출력**: (0+1+2+3)/4 = 1.5

### 4.2 통합 테스트

#### Test 4: 단순 dome 휨 + prestress

**Setup**:
- 평탄 사각 플레이트 (100×50×1 mm)
- Dome 휨 데이터 (중앙 최대 처짐 1 mm)
- `mode: prestress`
- `morph_factor: 1.0`

**검증**:
1. 메시 노드 위치는 변하지 않음 (평탄 유지)
2. `*INITIAL_STRESS_SOLID` dynain 생성됨
3. LS-DYNA DR 해석 실행 → 최종 형상이 dome으로 복원
4. 최대 처짐 오차 < 5%

#### Test 5: 마스킹 영역 포함 데이터

**Setup**:
- `warpage.dat` (15×15, 9999 마스킹 포함)
- `mode: prestress`

**검증**:
1. 마스킹 영역이 부드럽게 보간됨
2. 곡률 계산 결과에 불연속 없음
3. dynain 출력에 NaN/Inf 없음

#### Test 6: bbox 매핑 (데이터가 일부만 커버)

**Setup**:
- 파트 bbox: [0, 100] × [0, 100]
- `data_bbox`: [20, 80] × [20, 80]
- 휨 데이터: 중앙 영역만 적용

**검증**:
1. 데이터 bbox 외부 노드는 w = 0 (평탄)
2. 내부 노드만 휨 적용
3. 경계에서 부드러운 전이

---

## 5. 문서화

### 5.1 KooRemapper_Guide.txt 업데이트

#### [warpage] 섹션 추가

```
================================================================
2.X warpage — 측정 휨 데이터 기반 초기 응력 생성
================================================================

용도:
  측정된 휨(warpage) 패턴을 기반으로 평탄 초기 상태에 역방향
  초기 응력을 적용하여, Dynamic Relaxation 해석 시 원래 휨
  형상으로 복원되도록 함.

사용법:
  - type: warpage
    target_pid: <파트 ID>
    dat_file: <휨 데이터 파일>
    plane: xy                # 면내 방향
    deflection_axis: z       # 휨 방향
    unit: um                 # 데이터 단위 (um|mm|m)
    mode: prestress          # prestress|deform
    morph_factor: 1.0        # 휨 스케일

파라미터:
  ┌──────────────────┬──────────┬───────────────────────────────────┐
  │ 파라미터          │ 기본값   │ 설명                              │
  ├──────────────────┼──────────┼───────────────────────────────────┤
  │ target_pid (필수) │ -        │ 대상 파트 ID                      │
  │ dat_file (필수)   │ -        │ 휨 데이터 파일 (탭/공백 구분)     │
  │ plane            │ xy       │ 면내 방향 (xy|yz|zx)              │
  │ deflection_axis  │ z        │ 휨 방향 (+z|-z|+x|-x|+y|-y)       │
  │ unit             │ um       │ 데이터 단위 (um|mm|m)             │
  │ mask_value       │ 9999     │ 마스킹 값 (보간 대상)              │
  │ noise_threshold  │ 1e-10    │ 노이즈 제거 임계값                │
  │ data_bbox        │ (auto)   │ 데이터 물리 영역 (선택)            │
  │ morph_factor     │ 1.0      │ 휨 스케일 배율                    │
  │ mode             │ prestress│ prestress (역응력) | deform       │
  └──────────────────┴──────────┴───────────────────────────────────┘

동작 원리:
  1. .dat 파일 읽기 (2D 그리드, 마스킹 값 9999 보간)
  2. 곡률 계산 (유한 차분: κ = -d²w/dx²)
  3. 굽힘 응력 계산 (Kirchhoff 판이론)
  4. 역방향 응력 적용 → dynain 출력
  5. DR 해석 시 원래 휨 형상으로 복원

주의사항:
  * dynamic_relaxation: true 필수 (prestress 모드)
  * 재료 상수 E, nu 필요 (전역 material 또는 *MAT_ELASTIC)
  * 데이터는 row 0 = Y_max (상단), col 0 = X_min (좌측)
```

### 5.2 KooRemapper_Manual.md 업데이트

**8.14 warpage** 섹션 추가 (수식 포함)

---

## 6. 예제 파일

### 6.1 기본 예제 (`examples/warpage/warpage_basic.yaml`)

```yaml
base_model: flat_plate.k
output: warpage_result

material:
  E: 210000
  nu: 0.3

dynamic_relaxation: true

operations:
  - type: warpage
    target_pid: 1
    dat_file: data/warpage.dat
    plane: xy
    deflection_axis: z
    unit: um
    mode: prestress
```

### 6.2 고급 예제 (bbox + morph)

```yaml
base_model: large_plate.k
output: warpage_scaled

material:
  E: 210000
  nu: 0.3

dynamic_relaxation: true

operations:
  - type: warpage
    target_pid: 1
    dat_file: data/warpage.dat
    plane: xy
    deflection_axis: z
    unit: um
    data_bbox:
      x_min: 20.0
      x_max: 80.0
      y_min: 10.0
      y_max: 40.0
    morph_factor: 1.5      # 휨 1.5배 증폭
    mode: prestress
```

---

## 7. 향후 확장

### 7.1 3D 볼륨 warpage

현재는 2D 면내 + 1D 휨 방향. 향후:
- 3D 텐서 데이터 (.vtk, .dat 3D grid)
- 모든 방향 변형장 지원

### 7.2 시간 의존 warpage

```yaml
- type: warpage
  time_series:
    - time: 0.0
      dat_file: warpage_t0.dat
    - time: 1.0
      dat_file: warpage_t1.dat
```

### 7.3 재료 비선형 고려

현재는 선형 탄성. 향후:
- 소성 변형 고려 (*INITIAL_STRESS_SHELL + EPS)
- 잔류응력 재분배

---

## 8. 타임라인

| Phase | 작업 | 예상 시간 |
|-------|------|-----------|
| 1 | 데이터 구조 (AssemblyConfig.h) | 30분 |
| 2 | WarpageGrid 클래스 (파일 읽기, 보간, 곡률) | 2시간 |
| 3 | YAML 파싱 (AssemblyConfigReader.cpp) | 1시간 |
| 4 | applyWarpage() 구현 (ModelAssembler.cpp) | 3시간 |
| 5 | main.cpp 디스패치 | 15분 |
| 6 | 단위 테스트 작성 + 실행 | 1시간 |
| 7 | 통합 테스트 (LS-DYNA DR 검증) | 2시간 |
| 8 | 문서화 (Guide + Manual) | 1시간 |
| **합계** | | **약 10시간** |

---

## 9. 리스크 및 대응

| 리스크 | 영향 | 대응 방안 |
|--------|------|-----------|
| 마스킹 영역이 너무 넓어 보간 불가 | High | Laplacian inpainting 반복 횟수 증가, 경고 출력 |
| 곡률 계산 시 노이즈 증폭 | Medium | Gaussian blur 전처리, 곡률 smoothing |
| 데이터 단위 오인식 (um vs mm) | High | 출력 로그에 변환 계수 명시, 검증 메시지 |
| DR 수렴 실패 | Medium | 초기 응력 스케일 감소 (morph_factor < 1.0), CONTROL_DR 파라미터 조정 가이드 |
| bbox 외부 노드 처리 불명확 | Low | 명확한 문서화 + 경고 메시지 |

---

**END OF PLAN**

*이 계획서를 기반으로 warpage operation을 체계적으로 구현합니다.*
