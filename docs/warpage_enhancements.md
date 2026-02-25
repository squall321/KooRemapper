# Warpage Operation 보강 내용

> 기존 `warpage_feature_plan.md`에 추가할 상세 구현, 에러 처리, 성능 최적화, 경계 조건 처리

---

## 3.7 Phase 6: 에러 처리 및 검증

### 3.7.1 입력 검증

```cpp
bool ModelAssembler::validateWarpageOperation(const WarpageOperation& op) {
    std::vector<std::string> errors;

    // 1. 필수 파라미터 검증
    if (op.targetPid <= 0) {
        errors.push_back("target_pid must be > 0");
    }
    if (op.datFile.empty()) {
        errors.push_back("dat_file is required");
    }
    if (!std::filesystem::exists(op.datFile)) {
        errors.push_back("dat_file not found: " + op.datFile);
    }

    // 2. plane 검증
    if (op.plane != "xy" && op.plane != "yz" && op.plane != "zx") {
        errors.push_back("plane must be xy, yz, or zx");
    }

    // 3. deflection_axis 검증
    std::set<std::string> validAxes = {"+x", "-x", "+y", "-y", "+z", "-z"};
    if (validAxes.find(op.deflectionAxis) == validAxes.end()) {
        errors.push_back("deflection_axis must be one of: +x, -x, +y, -y, +z, -z");
    }

    // 4. unit 검증
    std::set<std::string> validUnits = {"um", "mm", "m"};
    if (validUnits.find(op.unit) == validUnits.end()) {
        errors.push_back("unit must be one of: um, mm, m");
    }

    // 5. morph_factor 검증
    if (op.morphFactor <= 0.0) {
        errors.push_back("morph_factor must be > 0");
    }
    if (op.morphFactor > 10.0) {
        errors.push_back("WARNING: morph_factor > 10.0 may cause excessive warpage");
    }

    // 6. mode 검증
    if (op.mode != "prestress" && op.mode != "deform") {
        errors.push_back("mode must be prestress or deform");
    }

    // 7. data_bbox 검증
    if (op.hasDataBbox) {
        if (op.dataBboxXmax <= op.dataBboxXmin) {
            errors.push_back("data_bbox: x_max must be > x_min");
        }
        if (op.dataBboxYmax <= op.dataBboxYmin) {
            errors.push_back("data_bbox: y_max must be > y_min");
        }
    }

    // 8. prestress 모드 재료 검증
    if (op.mode == "prestress") {
        if (!config_.hasMaterial()) {
            int mid = findPartMid(op.targetPid);
            if (mid < 0) {
                errors.push_back("prestress mode requires material (E, nu) - not found");
            }
        }
    }

    // 오류 출력
    if (!errors.empty()) {
        errorMessage_ = "Warpage validation failed:\n";
        for (const auto& err : errors) {
            errorMessage_ += "  - " + err + "\n";
        }
        return false;
    }

    return true;
}
```

### 3.7.2 데이터 로딩 에러 처리

```cpp
bool WarpageGrid::loadFromFile(const std::string& filepath, double maskValue, double noiseThreshold) {
    try {
        // 1. 파일 존재 확인
        std::ifstream file(filepath);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open file: " + filepath);
        }

        // 2. 파일 읽기
        parseTabDelimitedFile(filepath);

        // 3. 그리드 크기 검증
        if (nRows_ < 3 || nCols_ < 3) {
            throw std::runtime_error("Grid too small (min 3×3): " +
                                     std::to_string(nRows_) + "×" + std::to_string(nCols_));
        }
        if (nRows_ > 1000 || nCols_ > 1000) {
            throw std::runtime_error("Grid too large (max 1000×1000): " +
                                     std::to_string(nRows_) + "×" + std::to_string(nCols_));
        }

        // 4. 마스킹 비율 검사
        int maskedCount = countMaskedCells(maskValue);
        double maskedRatio = static_cast<double>(maskedCount) / (nRows_ * nCols_);
        if (maskedRatio > 0.5) {
            std::cerr << "[WARNING] Warpage: " << (maskedRatio * 100) << "% of data is masked\n";
        }

        // 5. 마스킹 보간
        applyMaskInterpolation(maskValue);

        // 6. 보간 후 검증 (여전히 마스킹 값이 남아있는지)
        int remainingMasked = countMaskedCells(maskValue);
        if (remainingMasked > 0) {
            throw std::runtime_error("Mask interpolation failed - isolated masked regions remain");
        }

        // 7. 노이즈 제거
        removeNoise(noiseThreshold);

        // 8. 데이터 범위 검사
        auto [minVal, maxVal] = getDataRange();
        std::cout << "[INFO] Warpage data range: [" << minVal << ", " << maxVal << "]\n";
        if (std::abs(maxVal - minVal) < 1e-12) {
            std::cerr << "[WARNING] Warpage data is nearly constant (no variation)\n";
        }

        return true;

    } catch (const std::exception& e) {
        std::cerr << "[ERROR] WarpageGrid::loadFromFile: " << e.what() << "\n";
        return false;
    }
}
```

### 3.7.3 런타임 검증

```cpp
void ModelAssembler::validateWarpageResults(const WarpageOperation& op, const WarpageGrid& grid) {
    // 1. 곡률 범위 검사
    auto [minK, maxK] = grid.getCurvatureRange();
    double avgK = grid.getAverageCurvature();

    std::cout << "[INFO] Warpage curvature range: [" << minK << ", " << maxK << "]\n";
    std::cout << "[INFO] Average curvature: " << avgK << "\n";

    if (std::abs(maxK) > 1e6) {
        std::cerr << "[WARNING] Extremely high curvature detected (κ_max = " << maxK << ")\n";
        std::cerr << "          This may indicate data issues or very sharp warpage.\n";
    }

    // 2. 초기 응력 범위 검사 (prestress 모드)
    if (op.mode == "prestress") {
        double maxStress = 0.0;
        for (const auto& [eid, stress] : elementStresses_) {
            double vonMises = stress.vonMises();
            maxStress = std::max(maxStress, vonMises);
        }

        std::cout << "[INFO] Max von Mises prestress: " << maxStress << " MPa\n";

        // 재료 항복응력과 비교 (있으면)
        double E = config_.E;
        double estimatedYield = E / 500.0;  // 대략 0.2% 변형률 기준
        if (maxStress > estimatedYield) {
            std::cerr << "[WARNING] Prestress exceeds estimated yield ("
                      << maxStress << " > " << estimatedYield << ")\n";
            std::cerr << "          Consider reducing morph_factor.\n";
        }
    }

    // 3. 변위 범위 검사 (deform 모드)
    if (op.mode == "deform") {
        double maxDisp = 0.0;
        for (const auto& [nid, pos] : modifiedNodePositions_) {
            const Node* n = baseMesh_.getNode(nid);
            if (n) {
                double disp = (pos - n->position).length();
                maxDisp = std::max(maxDisp, disp);
            }
        }
        std::cout << "[INFO] Max node displacement: " << maxDisp << "\n";
    }
}
```

---

## 3.8 Phase 7: 성능 최적화

### 3.8.1 병렬화 (OpenMP)

```cpp
void ModelAssembler::calculateWarpagePrestress(/* ... */) {
    // ...기존 코드...

    // 병렬 처리 (OpenMP)
    #pragma omp parallel for schedule(dynamic, 100)
    for (int idx = 0; idx < static_cast<int>(baseMesh_.getElements().size()); ++idx) {
        auto it = std::next(baseMesh_.getElements().begin(), idx);
        auto& [eid, elem] = *it;

        if (elem.partId != op.targetPid) continue;

        // ... 요소별 응력 계산 (thread-safe) ...

        // Critical section: elementStresses_ 맵 접근
        #pragma omp critical
        {
            if (elementStresses_.count(eid)) {
                elementStresses_[eid] = elementStresses_[eid] + stress;
            } else {
                elementStresses_[eid] = stress;
            }
        }
    }
}
```

### 3.8.2 그리드 캐싱

```cpp
class WarpageGrid {
public:
    // 보간 캐싱 (동일 (u,v) 재사용 시)
    double interpolate(double u, double v) const {
        // 캐시 키 생성 (정수 그리드 인덱스)
        int cacheKey = static_cast<int>(u * 1000) * 100000 + static_cast<int>(v * 1000);

        if (interpCache_.count(cacheKey)) {
            return interpCache_[cacheKey];
        }

        double result = interpolateImpl(u, v);
        interpCache_[cacheKey] = result;
        return result;
    }

private:
    mutable std::unordered_map<int, double> interpCache_;

    double interpolateImpl(double u, double v) const {
        // ... 기존 bilinear interpolation ...
    }
};
```

### 3.8.3 메모리 최적화

```cpp
// 큰 그리드의 경우 단정밀도 사용 (선택 사항)
class WarpageGrid {
private:
    std::vector<std::vector<float>> data_;      // double → float (메모리 절반)
    std::vector<std::vector<float>> kappa_xx_;
    std::vector<std::vector<float>> kappa_yy_;
    std::vector<std::vector<float>> kappa_xy_;

    // 반환값은 double로 변환
public:
    double get(int i, int j) const {
        return static_cast<double>(data_[i][j]);
    }
};
```

---

## 3.9 Phase 8: 경계 조건 및 엣지 케이스

### 3.9.1 경계 노드 곡률 계산

```cpp
void WarpageGrid::computeCurvatures() {
    // ... 내부 노드 (i=1…nRows-2) 처리는 기존과 동일 ...

    // 경계 노드: 단측 차분 (forward/backward difference)
    for (int j = 0; j < nCols_; ++j) {
        // 상단 경계 (i=0)
        kappa_yy_[0][j] = forwardDifferenceY(0, j);
        // 하단 경계 (i=nRows-1)
        kappa_yy_[nRows_-1][j] = backwardDifferenceY(nRows_-1, j);
    }

    for (int i = 0; i < nRows_; ++i) {
        // 좌측 경계 (j=0)
        kappa_xx_[i][0] = forwardDifferenceX(i, 0);
        // 우측 경계 (j=nCols-1)
        kappa_xx_[i][nCols_-1] = backwardDifferenceX(i, nCols_-1);
    }

    // 코너: 단측 차분 조합
    kappa_xy_[0][0] = forwardDifferenceXY(0, 0);
    kappa_xy_[0][nCols_-1] = forwardDifferenceXY(0, nCols_-1);
    // ... 나머지 코너 ...
}

double WarpageGrid::forwardDifferenceY(int i, int j) const {
    // κ_yy ≈ -(w[i+2] - 2*w[i+1] + w[i]) / hy²  (2nd order forward)
    double hy = 1.0 / (nRows_ - 1);
    if (i + 2 < nRows_) {
        return -(data_[i+2][j] - 2*data_[i+1][j] + data_[i][j]) / (hy*hy);
    } else {
        // 1차 근사로 폴백
        return -(data_[i+1][j] - data_[i][j]) / (hy*hy);
    }
}
```

### 3.9.2 data_bbox 외부 처리

```cpp
double ModelAssembler::getWarpageAtNode(int nid, const WarpageGrid& grid, /* ... */) {
    Vector3D pos = getNodePosition(nid);

    double u = (pos[axis1] - dataBbox.xmin) / (dataBbox.xmax - dataBbox.xmin);
    double v = (pos[axis2] - dataBbox.ymin) / (dataBbox.ymax - dataBbox.ymin);

    // 외부 처리 옵션
    if (u < 0 || u > 1 || v < 0 || v > 1) {
        switch (op.outsideBehavior) {
            case "zero":
                return 0.0;  // 기본값: 평탄

            case "clamp":
                // 경계값으로 클램핑
                u = std::clamp(u, 0.0, 1.0);
                v = std::clamp(v, 0.0, 1.0);
                return grid.interpolate(u, v);

            case "extrapolate":
                // 선형 외삽 (경고 출력)
                if (!warnedExtrapolation) {
                    std::cerr << "[WARNING] Warpage: extrapolating outside data_bbox\n";
                    warnedExtrapolation = true;
                }
                return grid.interpolate(u, v);  // 외삽 허용

            default:
                return 0.0;
        }
    }

    return grid.interpolate(u, v);
}
```

YAML에 추가:
```yaml
- type: warpage
  # ...
  outside_behavior: zero    # zero | clamp | extrapolate
```

### 3.9.3 마스킹 영역 격리 감지

```cpp
bool WarpageGrid::detectIsolatedMaskedRegions(double maskValue) {
    // Flood-fill로 연결된 마스킹 영역 찾기
    std::vector<std::vector<bool>> visited(nRows_, std::vector<bool>(nCols_, false));
    std::vector<std::vector<bool>> isMasked(nRows_, std::vector<bool>(nCols_, false));

    // 마스킹 셀 표시
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            isMasked[i][j] = (std::abs(data_[i][j] - maskValue) < 1e-6);
        }
    }

    // 유효 데이터로부터 flood-fill
    std::queue<std::pair<int,int>> q;
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            if (!isMasked[i][j]) {
                q.push({i, j});
                visited[i][j] = true;
            }
        }
    }

    while (!q.empty()) {
        auto [i, j] = q.front(); q.pop();

        // 4-이웃 탐색
        int di[] = {-1, 1, 0, 0};
        int dj[] = {0, 0, -1, 1};
        for (int k = 0; k < 4; ++k) {
            int ni = i + di[k];
            int nj = j + dj[k];
            if (ni >= 0 && ni < nRows_ && nj >= 0 && nj < nCols_) {
                if (!visited[ni][nj]) {
                    visited[ni][nj] = true;
                    q.push({ni, nj});
                }
            }
        }
    }

    // 방문하지 못한 마스킹 셀 = 격리된 영역
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            if (isMasked[i][j] && !visited[i][j]) {
                std::cerr << "[ERROR] Isolated masked region at (" << i << "," << j << ")\n";
                return true;  // 격리 영역 발견
            }
        }
    }

    return false;  // 모두 연결됨
}
```

---

## 3.10 Phase 9: 디버깅 및 시각화

### 3.10.1 중간 데이터 출력

```cpp
void WarpageGrid::exportDebugData(const std::string& prefix) const {
    // 1. 원본 데이터 출력
    std::ofstream rawFile(prefix + "_raw.dat");
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            rawFile << data_[i][j];
            if (j < nCols_ - 1) rawFile << "\t";
        }
        rawFile << "\n";
    }

    // 2. 곡률 출력
    std::ofstream kappaFile(prefix + "_curvature.dat");
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            double kappa = std::sqrt(kappa_xx_[i][j]*kappa_xx_[i][j] +
                                     kappa_yy_[i][j]*kappa_yy_[i][j]);
            kappaFile << kappa;
            if (j < nCols_ - 1) kappaFile << "\t";
        }
        kappaFile << "\n";
    }

    // 3. VTK 출력 (ParaView 시각화용)
    std::ofstream vtkFile(prefix + "_warpage.vtk");
    vtkFile << "# vtk DataFile Version 3.0\n";
    vtkFile << "Warpage Grid\n";
    vtkFile << "ASCII\n";
    vtkFile << "DATASET STRUCTURED_GRID\n";
    vtkFile << "DIMENSIONS " << nCols_ << " " << nRows_ << " 1\n";
    vtkFile << "POINTS " << (nRows_ * nCols_) << " float\n";

    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            double x = static_cast<double>(j) / (nCols_ - 1);
            double y = static_cast<double>(i) / (nRows_ - 1);
            double z = data_[i][j];
            vtkFile << x << " " << y << " " << z << "\n";
        }
    }

    vtkFile << "POINT_DATA " << (nRows_ * nCols_) << "\n";
    vtkFile << "SCALARS curvature float 1\n";
    vtkFile << "LOOKUP_TABLE default\n";
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            double kappa = std::sqrt(kappa_xx_[i][j]*kappa_xx_[i][j] +
                                     kappa_yy_[i][j]*kappa_yy_[i][j]);
            vtkFile << kappa << "\n";
        }
    }

    std::cout << "[DEBUG] Exported: " << prefix << "_{raw,curvature,warpage.vtk}\n";
}
```

YAML 추가 옵션:
```yaml
- type: warpage
  # ...
  debug: true               # 디버그 파일 출력
  debug_prefix: debug/warp  # 디버그 파일 접두어
```

### 3.10.2 응력 분포 검증

```cpp
void ModelAssembler::exportStressDistribution(const std::string& filename) const {
    std::ofstream csv(filename);
    csv << "ElementID,Centroid_X,Centroid_Y,Centroid_Z,Sigma_XX,Sigma_YY,Sigma_ZZ,VonMises\n";

    for (const auto& [eid, stress] : elementStresses_) {
        auto it = baseMesh_.getElements().find(eid);
        if (it == baseMesh_.getElements().end()) continue;

        Vector3D centroid = computeElementCentroid(it->second);
        double vonMises = stress.vonMises();

        csv << eid << ","
            << centroid.x << "," << centroid.y << "," << centroid.z << ","
            << stress.sigma_xx << "," << stress.sigma_yy << "," << stress.sigma_zz << ","
            << vonMises << "\n";
    }

    std::cout << "[INFO] Exported stress distribution: " << filename << "\n";
}
```

---

## 3.11 Phase 10: 추가 헬퍼 함수

### 3.11.1 단위 변환

```cpp
double ModelAssembler::getUnitScale(const std::string& unit) const {
    static const std::map<std::string, double> scaleMap = {
        {"um", 1.0e-3},   // μm → mm
        {"mm", 1.0},      // mm → mm
        {"m",  1.0e3}     // m → mm
    };

    auto it = scaleMap.find(unit);
    if (it == scaleMap.end()) {
        std::cerr << "[WARNING] Unknown unit '" << unit << "', using um\n";
        return 1.0e-3;
    }

    return it->second;
}
```

### 3.11.2 좌표축 파싱

```cpp
void ModelAssembler::parseAxes(const std::string& plane,
                                const std::string& deflAxis,
                                int& axis1, int& axis2, int& deflection) const
{
    // plane → axis1, axis2
    if (plane == "xy") {
        axis1 = 0; axis2 = 1;  // X, Y
    } else if (plane == "yz") {
        axis1 = 1; axis2 = 2;  // Y, Z
    } else if (plane == "zx") {
        axis1 = 2; axis2 = 0;  // Z, X
    } else {
        throw std::runtime_error("Invalid plane: " + plane);
    }

    // deflection_axis → deflection, sign
    if (deflAxis == "+z" || deflAxis == "z") {
        deflection = 2; deflSign_ = +1.0;
    } else if (deflAxis == "-z") {
        deflection = 2; deflSign_ = -1.0;
    } else if (deflAxis == "+x" || deflAxis == "x") {
        deflection = 0; deflSign_ = +1.0;
    } else if (deflAxis == "-x") {
        deflection = 0; deflSign_ = -1.0;
    } else if (deflAxis == "+y" || deflAxis == "y") {
        deflection = 1; deflSign_ = +1.0;
    } else if (deflAxis == "-y") {
        deflection = 1; deflSign_ = -1.0;
    } else {
        throw std::runtime_error("Invalid deflection_axis: " + deflAxis);
    }

    // plane과 deflection axis가 겹치는지 검증
    if (deflection == axis1 || deflection == axis2) {
        throw std::runtime_error("deflection_axis must be perpendicular to plane");
    }
}
```

### 3.11.3 요소 두께 추정

```cpp
double ModelAssembler::getElementThickness(const Element& elem) const {
    // 1. *SECTION_SOLID에서 두께 파라미터 읽기 (있으면)
    // (현재 KFileReader가 파싱 안 함 → 향후 확장)

    // 2. 요소 bbox Z 범위로 추정
    double zmin = 1e99, zmax = -1e99;
    for (int i = 0; i < 8; ++i) {
        int nid = elem.nodeIds[i];
        if (nid <= 0) continue;
        const Node* n = baseMesh_.getNode(nid);
        if (n) {
            zmin = std::min(zmin, n->position.z);
            zmax = std::max(zmax, n->position.z);
        }
    }

    double thickness = zmax - zmin;
    if (thickness < 1e-6) {
        // Shell처럼 얇으면 *SECTION_SHELL thickness 사용 (기존 코드 재사용)
        return getShellThickness(elem.partId);
    }

    return thickness;
}
```

---

## 추가 검증 테스트 케이스

### Test 7: 비균일 그리드 (non-square grid)

**입력**: 10×20 그리드 (행 ≠ 열)

**검증**:
- 보간 정확도 유지
- 곡률 계산에서 hx ≠ hy 올바르게 처리

### Test 8: 극단적 morph_factor

**Setup**:
- `morph_factor = 0.01` (거의 평탄)
- `morph_factor = 10.0` (과장된 휨)

**검증**:
- 응력이 선형적으로 스케일됨
- 수치 안정성 유지

### Test 9: 다양한 단위

**Setup**:
- 동일 데이터, unit=um / mm / m

**검증**:
- 최종 응력 결과가 동일함 (단위 변환 정확)

### Test 10: 경계 노드만 있는 파트

**Setup**:
- 매우 작은 파트 (data_bbox 경계에만 노드)

**검증**:
- 경계 곡률 계산 오류 없음
- 외삽 경고 출력

### Test 11: 모든 노드가 외부

**Setup**:
- data_bbox = [0, 10] × [0, 10]
- 파트 bbox = [20, 30] × [20, 30] (완전 분리)

**검증**:
- `outside_behavior=zero` → 모든 노드 w=0
- 응력 없음 (또는 경고만)

---

## LS-DYNA Dynamic Relaxation 통합 상세

### DR 키워드 자동 생성

`dynamic_relaxation: true` 시 자동 삽입:

```
*CONTROL_DYNAMIC_RELAXATION
$#    drtol    drfctr    drterm    tssfdr    irelal
     0.001       0.5         5         0         0
$#   edttl    iadfr    irelald
        0         0          0

*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas     nosol
       0.0         0       0.0       0.0       0.0         0

*CONTROL_TIMESTEP
$#  dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st
       0.0       0.9         0       0.0       0.0         0         1         0
```

### prestress → DR 검증 워크플로

1. **입력**: flat_part.k + warpage.dat
2. **KooRemapper 실행**:
   ```bash
   KooRemapper.exe assemble warpage_config.yaml
   ```
   출력: `result.k` (평탄 메시) + `result_dynain.dat` (역방향 응력)

3. **LS-DYNA DR 실행**:
   ```bash
   ls-dyna_smp i=result.k
   ```
   - Phase 1: DR 수렴 (endtim=0)
   - 최종 형상: 원래 휨 형상으로 복원

4. **검증**:
   - LS-PrePost에서 최종 Z 변위 분포 확인
   - 원본 warpage.dat와 비교
   - 오차 < 5%

---

## 메모리 프로파일링

대형 그리드 (1000×1000) 메모리 사용량:

| 항목 | 크기 |
|------|------|
| `data_` (double) | 1000² × 8 bytes = 8 MB |
| `kappa_xx/yy/xy` (각 double) | 3 × 8 MB = 24 MB |
| `interpCache_` (최악) | ~10 MB |
| **총** | **~42 MB** |

→ 메모리 문제 없음 (현대 시스템 기준)

---

**보강 완료**

*이 문서의 내용을 `warpage_feature_plan.md`의 해당 섹션에 통합하여 완전 강화 버전 생성*
