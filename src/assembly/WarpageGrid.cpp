#include "assembly/WarpageGrid.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>
#include <algorithm>
#include <cmath>
#include <queue>

namespace KooRemapper {

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
    grad_x_.resize(nRows_, std::vector<double>(nCols_, 0.0));
    grad_y_.resize(nRows_, std::vector<double>(nCols_, 0.0));

    double hx = 1.0 / (nCols_ - 1);  // 정규화 간격
    double hy = 1.0 / (nRows_ - 1);

    // 내부 노드 (중심 차분)
    for (int i = 1; i < nRows_ - 1; ++i) {
        for (int j = 1; j < nCols_ - 1; ++j) {
            // 1차 미분 (gradients) for finite strain
            grad_x_[i][j] = (data_[i][j+1] - data_[i][j-1]) / (2*hx);
            grad_y_[i][j] = (data_[i+1][j] - data_[i-1][j]) / (2*hy);

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

        // 1차 미분 (gradients) for boundaries in y-direction
        if (j > 0 && j < nCols_ - 1) {
            grad_x_[0][j] = (data_[0][j+1] - data_[0][j-1]) / (2*hx);
            grad_x_[nRows_-1][j] = (data_[nRows_-1][j+1] - data_[nRows_-1][j-1]) / (2*hx);
        }
        // Forward/backward difference for y-gradient at top/bottom boundaries
        grad_y_[0][j] = (data_[1][j] - data_[0][j]) / hy;  // forward
        grad_y_[nRows_-1][j] = (data_[nRows_-1][j] - data_[nRows_-2][j]) / hy;  // backward
    }

    for (int i = 0; i < nRows_; ++i) {
        kappa_xx_[i][0] = forwardDifferenceX(i, 0);
        kappa_xx_[i][nCols_-1] = backwardDifferenceX(i, nCols_-1);

        // 1차 미분 (gradients) for boundaries in x-direction
        if (i > 0 && i < nRows_ - 1) {
            grad_y_[i][0] = (data_[i+1][0] - data_[i-1][0]) / (2*hy);
            grad_y_[i][nCols_-1] = (data_[i+1][nCols_-1] - data_[i-1][nCols_-1]) / (2*hy);
        }
        // Forward/backward difference for x-gradient at left/right boundaries
        grad_x_[i][0] = (data_[i][1] - data_[i][0]) / hx;  // forward
        grad_x_[i][nCols_-1] = (data_[i][nCols_-1] - data_[i][nCols_-2]) / hx;  // backward
    }

    // 코너 (단측 차분 조합)
    for (int i : {0, nRows_-1}) {
        for (int j : {0, nCols_-1}) {
            kappa_xy_[i][j] = forwardDifferenceXY(i, j);

            // Corner gradients using forward/backward differences
            if (i == 0 && j == 0) {
                grad_x_[i][j] = (data_[i][j+1] - data_[i][j]) / hx;
                grad_y_[i][j] = (data_[i+1][j] - data_[i][j]) / hy;
            } else if (i == 0 && j == nCols_-1) {
                grad_x_[i][j] = (data_[i][j] - data_[i][j-1]) / hx;
                grad_y_[i][j] = (data_[i+1][j] - data_[i][j]) / hy;
            } else if (i == nRows_-1 && j == 0) {
                grad_x_[i][j] = (data_[i][j+1] - data_[i][j]) / hx;
                grad_y_[i][j] = (data_[i][j] - data_[i-1][j]) / hy;
            } else if (i == nRows_-1 && j == nCols_-1) {
                grad_x_[i][j] = (data_[i][j] - data_[i][j-1]) / hx;
                grad_y_[i][j] = (data_[i][j] - data_[i-1][j]) / hy;
            }
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

double WarpageGrid::getGradientX(int i, int j) const {
    return grad_x_[i][j];
}

double WarpageGrid::getGradientY(int i, int j) const {
    return grad_y_[i][j];
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

} // namespace KooRemapper
