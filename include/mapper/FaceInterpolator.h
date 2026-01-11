#pragma once

#include "core/Vector3D.h"
#include "mapper/EdgeInterpolator.h"
#include <array>

namespace KooRemapper {

/**
 * Interpolates over a face using Coons patch
 *
 * Face is defined by 4 boundary edges:
 *   edge0: s=0 (s varies 0->1)
 *   edge1: s=1
 *   edge2: t=0 (t varies 0->1)
 *   edge3: t=1
 *
 *        edge3 (t=1)
 *     3 --------- 2
 *     |           |
 *  e  |           |  e
 *  d  |           |  d
 *  g  |           |  g
 *  e  |           |  e
 *  0  |           |  1
 *     |           |
 *     0 --------- 1
 *        edge2 (t=0)
 */
class FaceInterpolator {
public:
    FaceInterpolator();
    ~FaceInterpolator() = default;

    /**
     * Build face interpolator from 4 boundary edges
     * @param edge0 Edge at s=0 (points from corner0 to corner3)
     * @param edge1 Edge at s=1 (points from corner1 to corner2)
     * @param edge2 Edge at t=0 (points from corner0 to corner1)
     * @param edge3 Edge at t=1 (points from corner3 to corner2)
     */
    void build(const EdgeInterpolator& edge0, const EdgeInterpolator& edge1,
               const EdgeInterpolator& edge2, const EdgeInterpolator& edge3);

    /**
     * Build from corner points only (bilinear)
     */
    void buildBilinear(const Vector3D& c00, const Vector3D& c10,
                       const Vector3D& c01, const Vector3D& c11);

    /**
     * Get interpolated position at parameters (s, t)
     * Both s and t are in [0, 1]
     */
    Vector3D interpolate(double s, double t) const;

    /**
     * Check if interpolator is valid
     */
    bool isValid() const { return isValid_; }

private:
    EdgeInterpolator edges_[4];
    std::array<Vector3D, 4> corners_;  // c00, c10, c01, c11
    bool isValid_;
    bool isBilinear_;
};

} // namespace KooRemapper
