#include "mapper/FaceInterpolator.h"

namespace KooRemapper {

FaceInterpolator::FaceInterpolator()
    : isValid_(false), isBilinear_(false)
{}

void FaceInterpolator::build(const EdgeInterpolator& edge0, const EdgeInterpolator& edge1,
                             const EdgeInterpolator& edge2, const EdgeInterpolator& edge3) {
    edges_[0] = edge0;
    edges_[1] = edge1;
    edges_[2] = edge2;
    edges_[3] = edge3;

    // Extract corner points
    corners_[0] = edge0.getPoint(0);                    // c00
    corners_[1] = edge1.getPoint(0);                    // c10
    corners_[2] = edge0.getPoint(edge0.getPointCount() - 1);  // c01
    corners_[3] = edge1.getPoint(edge1.getPointCount() - 1);  // c11

    isValid_ = edge0.isValid() && edge1.isValid() &&
               edge2.isValid() && edge3.isValid();
    isBilinear_ = false;
}

void FaceInterpolator::buildBilinear(const Vector3D& c00, const Vector3D& c10,
                                      const Vector3D& c01, const Vector3D& c11) {
    corners_[0] = c00;
    corners_[1] = c10;
    corners_[2] = c01;
    corners_[3] = c11;

    // Build edge interpolators from corners
    std::vector<Vector3D> edge0Points = {c00, c01};
    std::vector<Vector3D> edge1Points = {c10, c11};
    std::vector<Vector3D> edge2Points = {c00, c10};
    std::vector<Vector3D> edge3Points = {c01, c11};

    edges_[0].build(edge0Points);
    edges_[1].build(edge1Points);
    edges_[2].build(edge2Points);
    edges_[3].build(edge3Points);

    isValid_ = true;
    isBilinear_ = true;
}

Vector3D FaceInterpolator::interpolate(double s, double t) const {
    if (!isValid_) return Vector3D();

    s = std::max(0.0, std::min(1.0, s));
    t = std::max(0.0, std::min(1.0, t));

    if (isBilinear_) {
        // Simple bilinear interpolation
        Vector3D p0 = Vector3D::lerp(corners_[0], corners_[1], s);  // Bottom edge
        Vector3D p1 = Vector3D::lerp(corners_[2], corners_[3], s);  // Top edge
        return Vector3D::lerp(p0, p1, t);
    }

    // Coons patch interpolation
    // P(s,t) = Lc(s,t) + Ld(s,t) - B(s,t)
    //
    // Lc: Ruled surface from s-edges
    // Ld: Ruled surface from t-edges
    // B: Bilinear correction

    // Lc(s,t) = (1-s) * edge0(t) + s * edge1(t)
    Vector3D Lc = edges_[0].interpolate(t) * (1.0 - s) +
                  edges_[1].interpolate(t) * s;

    // Ld(s,t) = (1-t) * edge2(s) + t * edge3(s)
    Vector3D Ld = edges_[2].interpolate(s) * (1.0 - t) +
                  edges_[3].interpolate(s) * t;

    // B(s,t) = bilinear blend of corners
    Vector3D B = corners_[0] * (1.0 - s) * (1.0 - t) +
                 corners_[1] * s * (1.0 - t) +
                 corners_[2] * (1.0 - s) * t +
                 corners_[3] * s * t;

    return Lc + Ld - B;
}

} // namespace KooRemapper
