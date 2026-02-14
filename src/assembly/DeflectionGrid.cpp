#include "assembly/DeflectionGrid.h"
#include <fstream>
#include <sstream>
#include <cmath>
#include <algorithm>

namespace KooRemapper {

bool DeflectionGrid::loadFromFile(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open deflection grid file: " + filename;
        return false;
    }

    data_.clear();
    std::string line;
    while (std::getline(file, line)) {
        // Strip CR
        if (!line.empty() && line.back() == '\r') line.pop_back();

        // Skip empty lines and comments
        std::string trimmed = line;
        size_t s = trimmed.find_first_not_of(" \t");
        if (s == std::string::npos) continue;
        trimmed = trimmed.substr(s);
        if (trimmed[0] == '#' || trimmed[0] == '$') continue;

        // Parse space-separated values
        std::istringstream iss(line);
        std::vector<double> row;
        double val;
        while (iss >> val) {
            row.push_back(val);
        }

        if (row.empty()) continue;

        // Verify consistent column count
        if (!data_.empty() && static_cast<int>(row.size()) != nCols_) {
            errorMessage_ = "Inconsistent column count at row " +
                std::to_string(data_.size() + 1) + ": expected " +
                std::to_string(nCols_) + ", got " + std::to_string(row.size());
            return false;
        }

        if (data_.empty()) {
            nCols_ = static_cast<int>(row.size());
        }
        data_.push_back(std::move(row));
    }

    nRows_ = static_cast<int>(data_.size());

    if (nRows_ < 2 || nCols_ < 2) {
        errorMessage_ = "Grid too small: " + std::to_string(nRows_) + "x" +
            std::to_string(nCols_) + " (minimum 2x2)";
        return false;
    }

    return true;
}

void DeflectionGrid::setData(const std::vector<std::vector<double>>& data) {
    data_ = data;
    nRows_ = static_cast<int>(data_.size());
    nCols_ = nRows_ > 0 ? static_cast<int>(data_[0].size()) : 0;
}

void DeflectionGrid::setRange(double x1_min, double x1_max,
                               double x2_min, double x2_max) {
    x1Min_ = x1_min;
    x1Max_ = x1_max;
    x2Min_ = x2_min;
    x2Max_ = x2_max;

    dx1_ = (x1Max_ - x1Min_) / (nCols_ - 1);
    dx2_ = (x2Max_ - x2Min_) / (nRows_ - 1);

    computeDerivatives();
}

void DeflectionGrid::worldToGrid(double x1, double x2,
                                  double& gi, double& gj) const {
    // Column index: x1_min → col 0, x1_max → col nCols-1
    gj = (x1 - x1Min_) / dx1_;
    gj = std::max(0.0, std::min(gj, static_cast<double>(nCols_ - 1)));

    // Row index: x2_max → row 0, x2_min → row nRows-1 (inverted)
    gi = (x2Max_ - x2) / dx2_;
    gi = std::max(0.0, std::min(gi, static_cast<double>(nRows_ - 1)));
}

double DeflectionGrid::interpolate(const std::vector<std::vector<double>>& field,
                                    double x1, double x2) const {
    double gi, gj;
    worldToGrid(x1, x2, gi, gj);

    int i0 = static_cast<int>(gi);
    int j0 = static_cast<int>(gj);
    int i1 = std::min(i0 + 1, nRows_ - 1);
    int j1 = std::min(j0 + 1, nCols_ - 1);

    double fi = gi - i0;  // fractional part in row direction
    double fj = gj - j0;  // fractional part in col direction

    // Bilinear interpolation
    double v00 = field[i0][j0];
    double v10 = field[i1][j0];
    double v01 = field[i0][j1];
    double v11 = field[i1][j1];

    return v00 * (1 - fi) * (1 - fj) +
           v10 * fi * (1 - fj) +
           v01 * (1 - fi) * fj +
           v11 * fi * fj;
}

double DeflectionGrid::getDeflection(double x1, double x2) const {
    return interpolate(data_, x1, x2);
}

void DeflectionGrid::getCurvature(double x1, double x2,
                                   double& kappa_11, double& kappa_22,
                                   double& kappa_12) const {
    kappa_11 = interpolate(kappa11_, x1, x2);
    kappa_22 = interpolate(kappa22_, x1, x2);
    kappa_12 = interpolate(kappa12_, x1, x2);
}

void DeflectionGrid::getSlope(double x1, double x2,
                               double& dw_dx1, double& dw_dx2) const {
    dw_dx1 = interpolate(slope1_, x1, x2);
    dw_dx2 = interpolate(slope2_, x1, x2);
}

void DeflectionGrid::computeDerivatives() {
    // Allocate arrays
    kappa11_.assign(nRows_, std::vector<double>(nCols_, 0.0));
    kappa22_.assign(nRows_, std::vector<double>(nCols_, 0.0));
    kappa12_.assign(nRows_, std::vector<double>(nCols_, 0.0));
    slope1_.assign(nRows_, std::vector<double>(nCols_, 0.0));
    slope2_.assign(nRows_, std::vector<double>(nCols_, 0.0));

    // Note on grid orientation:
    //   Column direction (j) = x1 direction, spacing dx1_
    //   Row direction (i) = x2 direction (inverted), spacing dx2_
    //   Row 0 = x2_max, row N-1 = x2_min
    //   So d/dx2 in physical space = -d/di in grid space

    for (int i = 0; i < nRows_; i++) {
        for (int j = 0; j < nCols_; j++) {
            // --- First derivatives (slopes) ---

            // dw/dx1 (column direction, no inversion)
            if (j == 0) {
                slope1_[i][j] = (data_[i][1] - data_[i][0]) / dx1_;
            } else if (j == nCols_ - 1) {
                slope1_[i][j] = (data_[i][nCols_ - 1] - data_[i][nCols_ - 2]) / dx1_;
            } else {
                slope1_[i][j] = (data_[i][j + 1] - data_[i][j - 1]) / (2.0 * dx1_);
            }

            // dw/dx2 (row direction, inverted: increasing row = decreasing x2)
            if (i == 0) {
                // Forward difference in grid = backward in physical x2
                slope2_[i][j] = -(data_[i + 1][j] - data_[i][j]) / dx2_;
            } else if (i == nRows_ - 1) {
                slope2_[i][j] = -(data_[i][j] - data_[i - 1][j]) / dx2_;
            } else {
                slope2_[i][j] = -(data_[i + 1][j] - data_[i - 1][j]) / (2.0 * dx2_);
            }

            // --- Second derivatives (curvatures) ---
            // Convention: kappa = -d2w/dx2 (positive = concave up)

            // kappa_11 = -d2w/dx1^2
            if (j == 0) {
                if (nCols_ >= 3)
                    kappa11_[i][j] = -(data_[i][2] - 2 * data_[i][1] + data_[i][0]) / (dx1_ * dx1_);
                else
                    kappa11_[i][j] = 0.0;
            } else if (j == nCols_ - 1) {
                if (nCols_ >= 3)
                    kappa11_[i][j] = -(data_[i][nCols_ - 1] - 2 * data_[i][nCols_ - 2] + data_[i][nCols_ - 3]) / (dx1_ * dx1_);
                else
                    kappa11_[i][j] = 0.0;
            } else {
                kappa11_[i][j] = -(data_[i][j + 1] - 2 * data_[i][j] + data_[i][j - 1]) / (dx1_ * dx1_);
            }

            // kappa_22 = -d2w/dx2^2
            // Grid row inversion: d2w/dx2^2 in physical = d2w/di^2 in grid
            // (the inversion sign cancels out in second derivative)
            if (i == 0) {
                if (nRows_ >= 3)
                    kappa22_[i][j] = -(data_[i + 2][j] - 2 * data_[i + 1][j] + data_[i][j]) / (dx2_ * dx2_);
                else
                    kappa22_[i][j] = 0.0;
            } else if (i == nRows_ - 1) {
                if (nRows_ >= 3)
                    kappa22_[i][j] = -(data_[i][j] - 2 * data_[i - 1][j] + data_[i - 2][j]) / (dx2_ * dx2_);
                else
                    kappa22_[i][j] = 0.0;
            } else {
                kappa22_[i][j] = -(data_[i + 1][j] - 2 * data_[i][j] + data_[i - 1][j]) / (dx2_ * dx2_);
            }

            // kappa_12 = -d2w/(dx1*dx2)
            // Mixed derivative: inversion of row direction adds one sign flip
            if (i > 0 && i < nRows_ - 1 && j > 0 && j < nCols_ - 1) {
                double d2w = (data_[i - 1][j + 1] - data_[i - 1][j - 1]
                            - data_[i + 1][j + 1] + data_[i + 1][j - 1]);
                // Grid: d2w/(di*dj), physical: d2w/(dx1*dx2) = d2w/(dj * (-di)) = -d2w/(di*dj)
                // Then kappa_12 = -d2w/dx1dx2 = d2w/(di*dj)
                kappa12_[i][j] = d2w / (4.0 * dx1_ * dx2_);
            } else {
                kappa12_[i][j] = 0.0;  // Simplified at boundaries
            }
        }
    }
}

} // namespace KooRemapper
