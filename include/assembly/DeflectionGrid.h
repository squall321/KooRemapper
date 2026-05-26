#pragma once

#include <vector>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

/**
 * Grid-based deflection field reader and interpolator
 *
 * Reads space-separated .dat files representing a 2D deflection field.
 * File format:
 *   - First row = y_max (x2_max), last row = y_min (x2_min)
 *   - Columns = x direction (x1_min to x1_max)
 *   - Values = out-of-plane deflection w
 *
 * Provides bilinear interpolation of deflection, curvature, and slope
 * at arbitrary (x1, x2) positions within the mapped range.
 */
class DeflectionGrid {
public:
    DeflectionGrid() : nRows_(0), nCols_(0),
        x1Min_(0), x1Max_(0), x2Min_(0), x2Max_(0), dx1_(0), dx2_(0) {}

    /**
     * Load grid data from a space-separated file
     * @return true on success
     */
    bool loadFromFile(const std::string& filename);

    /**
     * Set grid data directly (for formula-generated grids).
     * data[row][col], row 0 = x2_max, row N-1 = x2_min.
     */
    void setData(const std::vector<std::vector<double>>& data);

    /**
     * Set the physical coordinate range that the grid maps to.
     * Must be called after loadFromFile()/setData() and before querying.
     * Triggers derivative computation.
     */
    void setRange(double x1_min, double x1_max, double x2_min, double x2_max);

    /**
     * Get interpolated deflection w at (x1, x2)
     */
    double getDeflection(double x1, double x2) const;

    /**
     * Get curvatures at (x1, x2) via pre-computed finite differences
     * kappa_11 = d2w/dx1^2, kappa_22 = d2w/dx2^2, kappa_12 = d2w/(dx1*dx2)
     * Sign convention: kappa = -d2w/dx^2 (positive = concave up)
     */
    void getCurvature(double x1, double x2,
                      double& kappa_11, double& kappa_22, double& kappa_12) const;

    /**
     * Get slopes (first derivatives) at (x1, x2)
     * dw_dx1 = dw/dx1, dw_dx2 = dw/dx2
     */
    void getSlope(double x1, double x2,
                  double& dw_dx1, double& dw_dx2) const;

    int getRows() const { return nRows_; }
    int getCols() const { return nCols_; }
    bool isLoaded() const { return nRows_ > 0 && nCols_ > 0; }

    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    std::vector<std::vector<double>> data_;       // [row][col] raw deflection
    std::vector<std::vector<double>> kappa11_;    // pre-computed curvatures
    std::vector<std::vector<double>> kappa22_;
    std::vector<std::vector<double>> kappa12_;
    std::vector<std::vector<double>> slope1_;     // dw/dx1
    std::vector<std::vector<double>> slope2_;     // dw/dx2

    int nRows_, nCols_;
    double x1Min_, x1Max_, x2Min_, x2Max_;
    double dx1_, dx2_;    // grid spacing in physical coordinates
    std::string errorMessage_;

    /**
     * Compute finite-difference derivatives at all grid nodes
     */
    void computeDerivatives();

    /**
     * Bilinear interpolation on any pre-computed 2D field
     */
    double interpolate(const std::vector<std::vector<double>>& field,
                       double x1, double x2) const;

    /**
     * Convert physical coordinates to fractional grid indices
     * gi = fractional row index (0 = x2_max row, nRows-1 = x2_min row)
     * gj = fractional column index (0 = x1_min col, nCols-1 = x1_max col)
     */
    void worldToGrid(double x1, double x2, double& gi, double& gj) const;
};

} // namespace KooRemapper
