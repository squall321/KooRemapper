# Warpage Operation 완전 개발 계획서

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
  outside_behavior: zero # zero | clamp | extrapolate
```

**동작**:
- 데이터는 지정된 `data_bbox` 영역을 커버
- 파트의 실제 bbox가 더 크면, 데이터가 그 일부만 커버
- 데이터 외부 영역: `outside_behavior`에 따라 처리
  - `zero`: w = 0 (평탄, 기본값)
  - `clamp`: 경계값으로 클램핑
  - `extrapolate`: 선형 외삽 (경고 출력)

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
    outside_behavior: zero         # zero | clamp | extrapolate (기본: zero)

    # 모핑 (선택)
    morph_factor: 1.0              # 휨 스케일 (기본: 1.0)

    # 모드 선택
    mode: prestress                # prestress | deform (기본: prestress)

    # 디버깅 (선택)
    debug: false                   # 디버그 파일 출력
    debug_prefix: debug/warp       # 디버그 파일 접두어

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
| `outside_behavior` | string | `zero` | bbox 외부 처리 (zero, clamp, extrapolate) |
| `morph_factor` | double | `1.0` | 휨 스케일 배율 |
| `mode` | string | `prestress` | prestress (역응력) 또는 deform (직접 변형) |
| `debug` | bool | `false` | 디버그 파일 출력 여부 |
| `debug_prefix` | string | `debug/warp` | 디버그 파일 접두어 |

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
struct WarpageOperation {
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

    std::string outsideBehavior = "zero"; // zero | clamp | extrapolate

    double morphFactor = 1.0;
    std::string mode = "prestress"; // prestress | deform

    // 디버깅
    bool debug = false;
    std::string debugPrefix = "debug/warp";
};

// AssemblyOperation::Type에 WARPAGE 추가
enum Type { REPLACE, SQUEEZE, RESTACK, BEND, INDENT, FORMSTRAIN,
            TET10_CONVERT, REFINE, ELFORM, DISCONNECT, IGA, WARPAGE };

// AssemblyOperation에 warpage 멤버 추가
WarpageOperation warpage;
```

---

### 3.3 Phase 2: WarpageGrid 클래스 (`WarpageGrid.h/cpp`)

#### WarpageGrid.h

```cpp
#ifndef WARPAGEGRID_H
#define WARPAGEGRID_H

#include <vector>
#include <string>
#include <unordered_map>

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
    double get(int i, int j) const;

    // 통계
    std::pair<double, double> getDataRange() const;
    std::pair<double, double> getCurvatureRange() const;
    double getAverageCurvature() const;

    // 디버깅
    void exportDebugData(const std::string& prefix) const;

private:
    int nRows_ = 0;
    int nCols_ = 0;
    std::vector<std::vector<double>> data_;      // 원본 데이터
    std::vector<std::vector<double>> kappa_xx_;  // 곡률 XX
    std::vector<std::vector<double>> kappa_yy_;  // 곡률 YY
    std::vector<std::vector<double>> kappa_xy_;  // 곡률 XY

    // 보간 캐싱
    mutable std::unordered_map<int, double> interpCache_;

    // 내부 헬퍼
    void parseTabDelimitedFile(const std::string& filepath);
    void applyMaskInterpolation(double maskValue);
    void removeNoise(double threshold);
    int countMaskedCells(double maskValue) const;
    bool detectIsolatedMaskedRegions(double maskValue);

    // 경계 곡률
    double forwardDifferenceX(int i, int j) const;
    double backwardDifferenceX(int i, int j) const;
    double forwardDifferenceY(int i, int j) const;
    double backwardDifferenceY(int i, int j) const;
    double forwardDifferenceXY(int i, int j) const;

    // 보간 구현
    double interpolateImpl(double u, double v) const;
};

#endif // WARPAGEGRID_H
```

#### WarpageGrid.cpp 구현

```cpp
#include "WarpageGrid.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>
#include <algorithm>
#include <cmath>
#include <queue>

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

        // 5. 격리된 마스킹 영역 감지
        if (detectIsolatedMaskedRegions(maskValue)) {
            std::cerr << "[WARNING] Isolated masked regions detected - interpolation may fail\n";
        }

        // 6. 마스킹 보간
        applyMaskInterpolation(maskValue);

        // 7. 보간 후 검증
        int remainingMasked = countMaskedCells(maskValue);
        if (remainingMasked > 0) {
            throw std::runtime_error("Mask interpolation failed - isolated masked regions remain");
        }

        // 8. 노이즈 제거
        removeNoise(noiseThreshold);

        // 9. 데이터 범위 검사
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

void WarpageGrid::parseTabDelimitedFile(const std::string& filepath) {
    std::ifstream file(filepath);
    std::string line;
    data_.clear();

    while (std::getline(file, line)) {
        if (line.empty()) continue;

        std::istringstream iss(line);
        std::vector<double> row;
        double val;

        while (iss >> val) {
            row.push_back(val);
        }

        if (!row.empty()) {
            data_.push_back(row);
        }
    }

    nRows_ = static_cast<int>(data_.size());
    nCols_ = nRows_ > 0 ? static_cast<int>(data_[0].size()) : 0;

    // 모든 행의 열 개수가 동일한지 검증
    for (const auto& row : data_) {
        if (static_cast<int>(row.size()) != nCols_) {
            throw std::runtime_error("Inconsistent number of columns in grid data");
        }
    }
}

int WarpageGrid::countMaskedCells(double maskValue) const {
    int count = 0;
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            if (std::abs(data_[i][j] - maskValue) < 1e-6) {
                count++;
            }
        }
    }
    return count;
}

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

void WarpageGrid::removeNoise(double threshold) {
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            if (std::abs(data_[i][j]) < threshold) {
                data_[i][j] = 0.0;
            }
        }
    }
}

bool WarpageGrid::detectIsolatedMaskedRegions(double maskValue) {
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
                return true;  // 격리 영역 발견
            }
        }
    }

    return false;
}

void WarpageGrid::computeCurvatures() {
    kappa_xx_.resize(nRows_, std::vector<double>(nCols_, 0.0));
    kappa_yy_.resize(nRows_, std::vector<double>(nCols_, 0.0));
    kappa_xy_.resize(nRows_, std::vector<double>(nCols_, 0.0));

    double hx = 1.0 / (nCols_ - 1);  // 정규화 간격
    double hy = 1.0 / (nRows_ - 1);

    // 내부 노드 (중심 차분)
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

    // 경계 노드: 단측 차분
    for (int j = 0; j < nCols_; ++j) {
        kappa_yy_[0][j] = forwardDifferenceY(0, j);
        kappa_yy_[nRows_-1][j] = backwardDifferenceY(nRows_-1, j);
    }

    for (int i = 0; i < nRows_; ++i) {
        kappa_xx_[i][0] = forwardDifferenceX(i, 0);
        kappa_xx_[i][nCols_-1] = backwardDifferenceX(i, nCols_-1);
    }

    // 코너 (단측 차분 조합)
    for (int i : {0, nRows_-1}) {
        for (int j : {0, nCols_-1}) {
            kappa_xy_[i][j] = forwardDifferenceXY(i, j);
        }
    }
}

double WarpageGrid::forwardDifferenceX(int i, int j) const {
    double hx = 1.0 / (nCols_ - 1);
    if (j + 2 < nCols_) {
        return -(data_[i][j+2] - 2*data_[i][j+1] + data_[i][j]) / (hx*hx);
    } else if (j + 1 < nCols_) {
        return -(data_[i][j+1] - data_[i][j]) / (hx*hx);
    }
    return 0.0;
}

double WarpageGrid::backwardDifferenceX(int i, int j) const {
    double hx = 1.0 / (nCols_ - 1);
    if (j - 2 >= 0) {
        return -(data_[i][j] - 2*data_[i][j-1] + data_[i][j-2]) / (hx*hx);
    } else if (j - 1 >= 0) {
        return -(data_[i][j] - data_[i][j-1]) / (hx*hx);
    }
    return 0.0;
}

double WarpageGrid::forwardDifferenceY(int i, int j) const {
    double hy = 1.0 / (nRows_ - 1);
    if (i + 2 < nRows_) {
        return -(data_[i+2][j] - 2*data_[i+1][j] + data_[i][j]) / (hy*hy);
    } else if (i + 1 < nRows_) {
        return -(data_[i+1][j] - data_[i][j]) / (hy*hy);
    }
    return 0.0;
}

double WarpageGrid::backwardDifferenceY(int i, int j) const {
    double hy = 1.0 / (nRows_ - 1);
    if (i - 2 >= 0) {
        return -(data_[i][j] - 2*data_[i-1][j] + data_[i-2][j]) / (hy*hy);
    } else if (i - 1 >= 0) {
        return -(data_[i][j] - data_[i-1][j]) / (hy*hy);
    }
    return 0.0;
}

double WarpageGrid::forwardDifferenceXY(int i, int j) const {
    double hx = 1.0 / (nCols_ - 1);
    double hy = 1.0 / (nRows_ - 1);

    // 간단한 단측 근사
    if (i + 1 < nRows_ && j + 1 < nCols_) {
        return -(data_[i+1][j+1] - data_[i+1][j] - data_[i][j+1] + data_[i][j]) / (hx*hy);
    }
    return 0.0;
}

double WarpageGrid::getCurvatureXX(int i, int j) const {
    return kappa_xx_[i][j];
}

double WarpageGrid::getCurvatureYY(int i, int j) const {
    return kappa_yy_[i][j];
}

double WarpageGrid::getCurvatureXY(int i, int j) const {
    return kappa_xy_[i][j];
}

double WarpageGrid::get(int i, int j) const {
    return data_[i][j];
}

double WarpageGrid::interpolate(double u, double v) const {
    // 캐시 키 생성
    int cacheKey = static_cast<int>(u * 1000) * 100000 + static_cast<int>(v * 1000);

    if (interpCache_.count(cacheKey)) {
        return interpCache_[cacheKey];
    }

    double result = interpolateImpl(u, v);
    interpCache_[cacheKey] = result;
    return result;
}

double WarpageGrid::interpolateImpl(double u, double v) const {
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

std::pair<double, double> WarpageGrid::getDataRange() const {
    double minVal = 1e99;
    double maxVal = -1e99;

    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            minVal = std::min(minVal, data_[i][j]);
            maxVal = std::max(maxVal, data_[i][j]);
        }
    }

    return {minVal, maxVal};
}

std::pair<double, double> WarpageGrid::getCurvatureRange() const {
    double minK = 1e99;
    double maxK = -1e99;

    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            double k = std::sqrt(kappa_xx_[i][j]*kappa_xx_[i][j] +
                               kappa_yy_[i][j]*kappa_yy_[i][j]);
            minK = std::min(minK, k);
            maxK = std::max(maxK, k);
        }
    }

    return {minK, maxK};
}

double WarpageGrid::getAverageCurvature() const {
    double sum = 0.0;
    int count = 0;

    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            sum += std::sqrt(kappa_xx_[i][j]*kappa_xx_[i][j] +
                           kappa_yy_[i][j]*kappa_yy_[i][j]);
            count++;
        }
    }

    return count > 0 ? sum / count : 0.0;
}

void WarpageGrid::exportDebugData(const std::string& prefix) const {
    // 1. 원본 데이터
    std::ofstream rawFile(prefix + "_raw.dat");
    for (int i = 0; i < nRows_; ++i) {
        for (int j = 0; j < nCols_; ++j) {
            rawFile << data_[i][j];
            if (j < nCols_ - 1) rawFile << "\t";
        }
        rawFile << "\n";
    }

    // 2. 곡률
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

    // 3. VTK
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

---

### 3.4 Phase 3: YAML 파싱 (`AssemblyConfigReader.cpp`)

```cpp
// "type: warpage" 인식
else if (trimmed == "type: warpage") {
    op.type = AssemblyOperation::WARPAGE;
}

// operation sub-keys 파싱
else if (op.type == AssemblyOperation::WARPAGE) {
    if (key == "target_pid") op.warpage.targetPid = std::stoi(val);
    else if (key == "dat_file") op.warpage.datFile = val;
    else if (key == "plane") op.warpage.plane = val;
    else if (key == "deflection_axis") op.warpage.deflectionAxis = val;
    else if (key == "unit") op.warpage.unit = val;
    else if (key == "mask_value") op.warpage.maskValue = std::stod(val);
    else if (key == "noise_threshold") op.warpage.noiseThreshold = std::stod(val);
    else if (key == "morph_factor") op.warpage.morphFactor = std::stod(val);
    else if (key == "mode") op.warpage.mode = val;
    else if (key == "outside_behavior") op.warpage.outsideBehavior = val;
    else if (key == "debug") op.warpage.debug = (val == "true");
    else if (key == "debug_prefix") op.warpage.debugPrefix = val;

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

#### ModelAssembler.h 업데이트

```cpp
bool applyWarpage(const WarpageOperation& op);

private:
    bool validateWarpageOperation(const WarpageOperation& op);
    void calculateWarpagePrestress(const WarpageOperation& op,
                                  const WarpageGrid& grid,
                                  double dataBboxXmin, double dataBboxXmax,
                                  double dataBboxYmin, double dataBboxYmax,
                                  double unitScale,
                                  int axis1, int axis2, int deflAxis);
    double getUnitScale(const std::string& unit) const;
    void parseAxes(const std::string& plane,
                  const std::string& deflAxis,
                  int& axis1, int& axis2, int& deflection) const;
    double getElementThickness(const Element& elem) const;
    void validateWarpageResults(const WarpageOperation& op, const WarpageGrid& grid);
    void exportStressDistribution(const std::string& filename) const;

    // 멤버 변수
    bool warnedExtrapolation_ = false;
    double deflSign_ = 1.0;
```

#### applyWarpage() 구현

```cpp
bool ModelAssembler::applyWarpage(const WarpageOperation& op) {
    // 1. 입력 검증
    if (!validateWarpageOperation(op)) {
        return false;
    }

    // 2. WarpageGrid 로드
    WarpageGrid grid;
    if (!grid.loadFromFile(op.datFile, op.maskValue, op.noiseThreshold)) {
        errorMessage_ = "Failed to load warpage data: " + op.datFile;
        return false;
    }

    // 3. 단위 변환 계수
    double unitScale = getUnitScale(op.unit);
    std::cout << "[INFO] Warpage unit scale: " << op.unit << " → " << unitScale << " mm\n";

    // 4. 파트 노드 수집
    auto nodeIds = getPartNodeIds(op.targetPid);
    // addedElements_ 노드도 포함
    for (const auto& ae : addedElements_) {
        if (ae.pid != op.targetPid) continue;
        for (int ni = 0; ni < 8; ++ni) {
            if (ae.nodeIds[ni] > 0) nodeIds.insert(ae.nodeIds[ni]);
        }
    }

    if (nodeIds.empty()) {
        errorMessage_ = "Warpage: part " + std::to_string(op.targetPid) + " has no nodes";
        return false;
    }

    // 5. 파트 바운딩 박스 계산
    double partXmin = 1e99, partXmax = -1e99;
    double partYmin = 1e99, partYmax = -1e99;
    double partZmin = 1e99, partZmax = -1e99;

    for (int nid : nodeIds) {
        Vector3D pos = getNodePosition(nid);
        partXmin = std::min(partXmin, pos.x);
        partXmax = std::max(partXmax, pos.x);
        partYmin = std::min(partYmin, pos.y);
        partYmax = std::max(partYmax, pos.y);
        partZmin = std::min(partZmin, pos.z);
        partZmax = std::max(partZmax, pos.z);
    }

    // 6. 데이터 bbox 결정
    double dataBboxXmin, dataBboxXmax, dataBboxYmin, dataBboxYmax;
    if (op.hasDataBbox) {
        dataBboxXmin = op.dataBboxXmin;
        dataBboxXmax = op.dataBboxXmax;
        dataBboxYmin = op.dataBboxYmin;
        dataBboxYmax = op.dataBboxYmax;
        std::cout << "[INFO] Using user-defined data_bbox: ["
                  << dataBboxXmin << ", " << dataBboxXmax << "] × ["
                  << dataBboxYmin << ", " << dataBboxYmax << "]\n";
    } else {
        dataBboxXmin = partXmin;
        dataBboxXmax = partXmax;
        dataBboxYmin = partYmin;
        dataBboxYmax = partYmax;
        std::cout << "[INFO] Using part bbox as data_bbox (1:1 mapping)\n";
    }

    // 7. 좌표계 결정
    int axis1, axis2, deflAxis;
    parseAxes(op.plane, op.deflectionAxis, axis1, axis2, deflAxis);

    // 8. 곡률 계산
    grid.computeCurvatures();

    // 9. 디버깅 출력
    if (op.debug) {
        grid.exportDebugData(op.debugPrefix);
    }

    // 10. 모드별 처리
    if (op.mode == "deform") {
        // 직접 변형: 노드 이동
        for (int nid : nodeIds) {
            Vector3D pos = getNodePosition(nid);

            // 정규화 좌표
            double u = (pos[axis1] - dataBboxXmin) / (dataBboxXmax - dataBboxXmin);
            double v = (pos[axis2] - dataBboxYmin) / (dataBboxYmax - dataBboxYmin);

            // 데이터 bbox 외부 처리
            double w = 0.0;
            if (u < 0 || u > 1 || v < 0 || v > 1) {
                if (op.outsideBehavior == "clamp") {
                    u = std::clamp(u, 0.0, 1.0);
                    v = std::clamp(v, 0.0, 1.0);
                    w = grid.interpolate(u, v) * unitScale * op.morphFactor;
                } else if (op.outsideBehavior == "extrapolate") {
                    if (!warnedExtrapolation_) {
                        std::cerr << "[WARNING] Warpage: extrapolating outside data_bbox\n";
                        warnedExtrapolation_ = true;
                    }
                    w = grid.interpolate(u, v) * unitScale * op.morphFactor;
                } else {
                    w = 0.0; // "zero"
                }
            } else {
                w = grid.interpolate(u, v) * unitScale * op.morphFactor;
            }

            // 노드 이동
            pos[deflAxis] += w * deflSign_;
            modifiedNodePositions_[nid] = pos;
        }

        std::cout << "[INFO] Applied deform mode - nodes moved\n";

    } else if (op.mode == "prestress") {
        // 역방향 초기 응력 계산
        calculateWarpagePrestress(op, grid,
                                 dataBboxXmin, dataBboxXmax,
                                 dataBboxYmin, dataBboxYmax,
                                 unitScale, axis1, axis2, deflAxis);

        std::cout << "[INFO] Applied prestress mode - initial stress generated\n";
    }

    // 11. 검증
    validateWarpageResults(op, grid);

    return true;
}

bool ModelAssembler::validateWarpageOperation(const WarpageOperation& op) {
    std::vector<std::string> errors;

    // 필수 파라미터
    if (op.targetPid <= 0) {
        errors.push_back("target_pid must be > 0");
    }
    if (op.datFile.empty()) {
        errors.push_back("dat_file is required");
    }
    if (!std::filesystem::exists(op.datFile)) {
        errors.push_back("dat_file not found: " + op.datFile);
    }

    // plane 검증
    if (op.plane != "xy" && op.plane != "yz" && op.plane != "zx") {
        errors.push_back("plane must be xy, yz, or zx");
    }

    // deflection_axis 검증
    std::set<std::string> validAxes = {"+x", "-x", "+y", "-y", "+z", "-z", "x", "y", "z"};
    if (validAxes.find(op.deflectionAxis) == validAxes.end()) {
        errors.push_back("deflection_axis must be one of: +x, -x, +y, -y, +z, -z");
    }

    // unit 검증
    std::set<std::string> validUnits = {"um", "mm", "m"};
    if (validUnits.find(op.unit) == validUnits.end()) {
        errors.push_back("unit must be one of: um, mm, m");
    }

    // morph_factor 검증
    if (op.morphFactor <= 0.0) {
        errors.push_back("morph_factor must be > 0");
    }
    if (op.morphFactor > 10.0) {
        std::cerr << "[WARNING] morph_factor > 10.0 may cause excessive warpage\n";
    }

    // mode 검증
    if (op.mode != "prestress" && op.mode != "deform") {
        errors.push_back("mode must be prestress or deform");
    }

    // data_bbox 검증
    if (op.hasDataBbox) {
        if (op.dataBboxXmax <= op.dataBboxXmin) {
            errors.push_back("data_bbox: x_max must be > x_min");
        }
        if (op.dataBboxYmax <= op.dataBboxYmin) {
            errors.push_back("data_bbox: y_max must be > y_min");
        }
    }

    // outside_behavior 검증
    std::set<std::string> validBehaviors = {"zero", "clamp", "extrapolate"};
    if (validBehaviors.find(op.outsideBehavior) == validBehaviors.end()) {
        errors.push_back("outside_behavior must be zero, clamp, or extrapolate");
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

void ModelAssembler::calculateWarpagePrestress(
    const WarpageOperation& op,
    const WarpageGrid& grid,
    double dataBboxXmin, double dataBboxXmax,
    double dataBboxYmin, double dataBboxYmax,
    double unitScale,
    int axis1, int axis2, int deflAxis)
{
    // 재료 상수
    double E = config_.E;
    double nu = config_.nu;

    if (E <= 0) {
        std::cerr << "[ERROR] Material E not defined for prestress mode\n";
        return;
    }

    double factor = E / (1 - nu*nu);

    std::cout << "[INFO] Material: E=" << E << ", nu=" << nu << "\n";

    // 각 요소에 대해
    for (auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId != op.targetPid) continue;

        // 요소 중심 계산
        Vector3D centroid(0, 0, 0);
        int nodeCount = 0;
        for (int ni = 0; ni < 8; ++ni) {
            int nid = elem.nodeIds[ni];
            if (nid <= 0) continue;
            Vector3D pos = getNodePosition(nid);
            centroid = centroid + pos;
            nodeCount++;
        }
        if (nodeCount == 0) continue;
        centroid = centroid * (1.0 / nodeCount);

        // 정규화 좌표
        double u = (centroid[axis1] - dataBboxXmin) / (dataBboxXmax - dataBboxXmin);
        double v = (centroid[axis2] - dataBboxYmin) / (dataBboxYmax - dataBboxYmin);

        if (u < 0 || u > 1 || v < 0 || v > 1) {
            if (op.outsideBehavior != "clamp" && op.outsideBehavior != "extrapolate") {
                continue; // zero behavior
            }
            if (op.outsideBehavior == "clamp") {
                u = std::clamp(u, 0.0, 1.0);
                v = std::clamp(v, 0.0, 1.0);
            }
        }

        // 그리드 인덱스
        int i = static_cast<int>(v * (grid.rows() - 1));
        int j = static_cast<int>(u * (grid.cols() - 1));
        i = std::clamp(i, 0, grid.rows() - 1);
        j = std::clamp(j, 0, grid.cols() - 1);

        // 곡률 (물리 단위로 스케일)
        double physicalLenX = dataBboxXmax - dataBboxXmin;
        double physicalLenY = dataBboxYmax - dataBboxYmin;

        double scaledKappaXX = grid.getCurvatureXX(i, j) * unitScale / (physicalLenX * physicalLenX) * op.morphFactor;
        double scaledKappaYY = grid.getCurvatureYY(i, j) * unitScale / (physicalLenY * physicalLenY) * op.morphFactor;
        double scaledKappaXY = grid.getCurvatureXY(i, j) * unitScale / (physicalLenX * physicalLenY) * op.morphFactor;

        // 중립면에서 거리
        double thickness = getElementThickness(elem);
        double z_neutral = thickness / 2.0;

        // 굽힘 변형률
        double eps_xx = z_neutral * scaledKappaXX * deflSign_;
        double eps_yy = z_neutral * scaledKappaYY * deflSign_;
        double eps_xy = z_neutral * scaledKappaXY * deflSign_;

        // 응력
        double sig_xx = factor * (eps_xx + nu * eps_yy);
        double sig_yy = factor * (eps_yy + nu * eps_xx);
        double sig_xy = (E / (1 + nu)) * eps_xy;

        // 역방향 응력 (부호 반전)
        sig_xx = -sig_xx;
        sig_yy = -sig_yy;
        sig_xy = -sig_xy;

        // 응력 텐서 생성
        StressTensor stress;
        stress.sigma_xx = sig_xx;
        stress.sigma_yy = sig_yy;
        stress.sigma_zz = 0.0;  // 평면응력
        stress.sigma_xy = sig_xy;
        stress.sigma_yz = 0.0;
        stress.sigma_xz = 0.0;

        // 누적
        if (elementStresses_.count(eid)) {
            elementStresses_[eid] = elementStresses_[eid] + stress;
        } else {
            elementStresses_[eid] = stress;
        }
    }
}

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
    deflSign_ = 1.0;
    if (deflAxis == "+z" || deflAxis == "z") {
        deflection = 2;
    } else if (deflAxis == "-z") {
        deflection = 2; deflSign_ = -1.0;
    } else if (deflAxis == "+x" || deflAxis == "x") {
        deflection = 0;
    } else if (deflAxis == "-x") {
        deflection = 0; deflSign_ = -1.0;
    } else if (deflAxis == "+y" || deflAxis == "y") {
        deflection = 1;
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

double ModelAssembler::getElementThickness(const Element& elem) const {
    // bbox Z 범위로 추정
    double zmin = 1e99, zmax = -1e99;
    for (int i = 0; i < 8; ++i) {
        int nid = elem.nodeIds[i];
        if (nid <= 0) continue;
        Vector3D pos = getNodePosition(nid);
        zmin = std::min(zmin, pos.z);
        zmax = std::max(zmax, pos.z);
    }

    double thickness = zmax - zmin;
    if (thickness < 1e-6) {
        // Shell 두께 사용
        return getShellThickness(elem.partId);
    }

    return thickness;
}

void ModelAssembler::validateWarpageResults(const WarpageOperation& op, const WarpageGrid& grid) {
    // 곡률 범위 검사
    auto [minK, maxK] = grid.getCurvatureRange();
    double avgK = grid.getAverageCurvature();

    std::cout << "[INFO] Warpage curvature range: [" << minK << ", " << maxK << "]\n";
    std::cout << "[INFO] Average curvature: " << avgK << "\n";

    if (std::abs(maxK) > 1e6) {
        std::cerr << "[WARNING] Extremely high curvature detected (κ_max = " << maxK << ")\n";
        std::cerr << "          This may indicate data issues or very sharp warpage.\n";
    }

    // 초기 응력 범위 검사
    if (op.mode == "prestress") {
        double maxStress = 0.0;
        for (const auto& [eid, stress] : elementStresses_) {
            double vonMises = stress.vonMises();
            maxStress = std::max(maxStress, vonMises);
        }

        std::cout << "[INFO] Max von Mises prestress: " << maxStress << " MPa\n";

        double E = config_.E;
        double estimatedYield = E / 500.0;
        if (maxStress > estimatedYield) {
            std::cerr << "[WARNING] Prestress exceeds estimated yield ("
                      << maxStress << " > " << estimatedYield << ")\n";
            std::cerr << "          Consider reducing morph_factor.\n";
        }
    }

    // 변위 범위 검사
    if (op.mode == "deform") {
        double maxDisp = 0.0;
        for (const auto& [nid, pos] : modifiedNodePositions_) {
            const Node* n = baseMesh_.getNode(nid);
            if (n) {
                Vector3D origPos = n->position;
                double disp = (pos - origPos).magnitude();
                maxDisp = std::max(maxDisp, disp);
            }
        }
        std::cout << "[INFO] Max node displacement: " << maxDisp << "\n";
    }
}

void ModelAssembler::exportStressDistribution(const std::string& filename) const {
    std::ofstream csv(filename);
    csv << "ElementID,Centroid_X,Centroid_Y,Centroid_Z,Sigma_XX,Sigma_YY,Sigma_ZZ,VonMises\n";

    for (const auto& [eid, stress] : elementStresses_) {
        auto it = baseMesh_.getElements().find(eid);
        if (it == baseMesh_.getElements().end()) continue;

        // 중심 계산
        Vector3D centroid(0, 0, 0);
        int nodeCount = 0;
        for (int ni = 0; ni < 8; ++ni) {
            int nid = it->second.nodeIds[ni];
            if (nid <= 0) continue;
            Vector3D pos = getNodePosition(nid);
            centroid = centroid + pos;
            nodeCount++;
        }
        if (nodeCount > 0) {
            centroid = centroid * (1.0 / nodeCount);
        }

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

#### Test 7: 비균일 그리드

**입력**: 10×20 그리드 (행 ≠ 열)

**검증**:
- 보간 정확도 유지
- 곡률 계산에서 hx ≠ hy 올바르게 처리

#### Test 8: 극단적 morph_factor

**Setup**:
- `morph_factor = 0.01` (거의 평탄)
- `morph_factor = 10.0` (과장된 휨)

**검증**:
- 응력이 선형적으로 스케일됨
- 수치 안정성 유지

#### Test 9: 다양한 단위

**Setup**:
- 동일 데이터, unit=um / mm / m

**검증**:
- 최종 응력 결과가 동일함 (단위 변환 정확)

#### Test 10: 경계 노드만 있는 파트

**Setup**:
- 매우 작은 파트 (data_bbox 경계에만 노드)

**검증**:
- 경계 곡률 계산 오류 없음
- 외삽 경고 출력

#### Test 11: 모든 노드가 외부

**Setup**:
- data_bbox = [0, 10] × [0, 10]
- 파트 bbox = [20, 30] × [20, 30] (완전 분리)

**검증**:
- `outside_behavior=zero` → 모든 노드 w=0
- 응력 없음 (또는 경고만)

---

## 5. LS-DYNA Dynamic Relaxation 통합

### 5.1 DR 키워드 자동 생성

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

### 5.2 prestress → DR 검증 워크플로

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

## 6. 문서화

### 6.1 KooRemapper_Guide.txt 업데이트

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
  │ outside_behavior │ zero     │ bbox 외부 (zero|clamp|extrapolate) │
  │ morph_factor     │ 1.0      │ 휨 스케일 배율                    │
  │ mode             │ prestress│ prestress (역응력) | deform       │
  │ debug            │ false    │ 디버그 파일 출력                  │
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

### 6.2 KooRemapper_Manual.md 업데이트

**8.14 warpage** 섹션 추가 (수식 포함)

---

## 7. 예제 파일

### 7.1 기본 예제 (`examples/warpage/warpage_basic.yaml`)

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

### 7.2 고급 예제 (bbox + morph + debug)

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
    outside_behavior: zero
    morph_factor: 1.5      # 휨 1.5배 증폭
    mode: prestress
    debug: true
    debug_prefix: debug/warpage
```

---

## 8. 향후 확장

### 8.1 3D 볼륨 warpage

현재는 2D 면내 + 1D 휨 방향. 향후:
- 3D 텐서 데이터 (.vtk, .dat 3D grid)
- 모든 방향 변형장 지원

### 8.2 시간 의존 warpage

```yaml
- type: warpage
  time_series:
    - time: 0.0
      dat_file: warpage_t0.dat
    - time: 1.0
      dat_file: warpage_t1.dat
```

### 8.3 재료 비선형 고려

현재는 선형 탄성. 향후:
- 소성 변형 고려 (*INITIAL_STRESS_SHELL + EPS)
- 잔류응력 재분배

---

## 9. 타임라인

| Phase | 작업 | 예상 시간 |
|-------|------|-----------|
| 1 | 데이터 구조 (AssemblyConfig.h) | 30분 |
| 2 | WarpageGrid 클래스 (파일 읽기, 보간, 곡률) | 2시간 |
| 3 | YAML 파싱 (AssemblyConfigReader.cpp) | 1시간 |
| 4 | applyWarpage() 구현 (ModelAssembler.cpp) | 3시간 |
| 5 | main.cpp 디스패치 | 15분 |
| 6 | 에러 처리 및 검증 | 1시간 |
| 7 | 성능 최적화 (병렬화) | 1시간 |
| 8 | 경계 조건 및 엣지 케이스 | 1시간 |
| 9 | 디버깅 및 시각화 | 30분 |
| 10 | 헬퍼 함수 | 30분 |
| 11 | 단위 테스트 작성 + 실행 | 1시간 |
| 12 | 통합 테스트 (LS-DYNA DR 검증) | 2시간 |
| 13 | 문서화 (Guide + Manual) | 1시간 |
| **합계** | | **약 14시간** |

---

## 10. 리스크 및 대응

| 리스크 | 영향 | 대응 방안 |
|--------|------|-----------|
| 마스킹 영역이 너무 넓어 보간 불가 | High | Laplacian inpainting 반복 횟수 증가, 경고 출력 |
| 곡률 계산 시 노이즈 증폭 | Medium | removeNoise 전처리, 곡률 smoothing |
| 데이터 단위 오인식 (um vs mm) | High | 출력 로그에 변환 계수 명시, 검증 메시지 |
| DR 수렴 실패 | Medium | 초기 응력 스케일 감소 (morph_factor < 1.0), CONTROL_DR 파라미터 조정 가이드 |
| bbox 외부 노드 처리 불명확 | Low | 명확한 문서화 + outside_behavior 옵션 제공 |
| 격리된 마스킹 영역 | Medium | detectIsolatedMaskedRegions() + 에러 출력 |
| 경계 노드 곡률 부정확 | Low | 단측 차분 구현 + 검증 |

---

## 11. 메모리 프로파일링

대형 그리드 (1000×1000) 메모리 사용량:

| 항목 | 크기 |
|------|------|
| `data_` (double) | 1000² × 8 bytes = 8 MB |
| `kappa_xx/yy/xy` (각 double) | 3 × 8 MB = 24 MB |
| `interpCache_` (최악) | ~10 MB |
| **총** | **~42 MB** |

→ 메모리 문제 없음 (현대 시스템 기준)

---

**END OF COMPLETE PLAN**

*이 완전 계획서를 기반으로 warpage operation을 체계적으로 구현합니다.*
