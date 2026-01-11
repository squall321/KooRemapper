#pragma once

#include "core/Vector3D.h"
#include <vector>

namespace KooRemapper {

/**
 * Interpolates along an edge using arc-length parameterization
 */
class EdgeInterpolator {
public:
    EdgeInterpolator();
    ~EdgeInterpolator() = default;

    /**
     * Build interpolator from a list of points
     */
    void build(const std::vector<Vector3D>& points);

    /**
     * Get interpolated position at parameter t (0 to 1)
     */
    Vector3D interpolate(double t) const;

    /**
     * Get tangent vector at parameter t
     */
    Vector3D tangent(double t) const;

    /**
     * Get total arc length
     */
    double getTotalLength() const { return totalLength_; }

    /**
     * Get number of points
     */
    size_t getPointCount() const { return points_.size(); }

    /**
     * Get point by index
     */
    const Vector3D& getPoint(size_t index) const { return points_[index]; }

    /**
     * Check if interpolator is valid
     */
    bool isValid() const { return points_.size() >= 2; }

private:
    std::vector<Vector3D> points_;
    std::vector<double> arcLengths_;  // Cumulative arc lengths
    double totalLength_;

    /**
     * Find segment containing parameter t
     * Returns segment index and local parameter within segment
     */
    std::pair<size_t, double> findSegment(double t) const;
};

} // namespace KooRemapper
