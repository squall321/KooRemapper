#include "mapper/EdgeInterpolator.h"
#include <algorithm>

namespace KooRemapper {

EdgeInterpolator::EdgeInterpolator()
    : totalLength_(0.0)
{}

void EdgeInterpolator::build(const std::vector<Vector3D>& points) {
    points_ = points;
    arcLengths_.clear();
    totalLength_ = 0.0;

    if (points_.size() < 2) {
        return;
    }

    // Calculate cumulative arc lengths
    arcLengths_.push_back(0.0);

    for (size_t i = 1; i < points_.size(); ++i) {
        double segmentLength = points_[i].distanceTo(points_[i - 1]);
        totalLength_ += segmentLength;
        arcLengths_.push_back(totalLength_);
    }
}

Vector3D EdgeInterpolator::interpolate(double t) const {
    if (points_.empty()) return Vector3D();
    if (points_.size() == 1) return points_[0];

    t = std::max(0.0, std::min(1.0, t));

    if (t <= 0.0) return points_.front();
    if (t >= 1.0) return points_.back();

    // Arc-length based interpolation: t maps to arc-length position
    // t = 0.5 means 50% along the total arc-length, not 50% of node count
    // This ensures physical correspondence between flat and bent meshes
    double targetLength = t * totalLength_;

    // Find the segment containing this arc-length position
    size_t idx = 0;
    for (size_t i = 0; i + 1 < arcLengths_.size(); ++i) {
        if (targetLength >= arcLengths_[i] && targetLength <= arcLengths_[i + 1]) {
            idx = i;
            break;
        }
    }

    // Calculate local parameter within the segment
    double segmentLength = arcLengths_[idx + 1] - arcLengths_[idx];
    double localT = (segmentLength > 0)
                  ? (targetLength - arcLengths_[idx]) / segmentLength
                  : 0.0;

    return Vector3D::lerp(points_[idx], points_[idx + 1], localT);
}

Vector3D EdgeInterpolator::tangent(double t) const {
    if (points_.size() < 2) return Vector3D(1, 0, 0);

    t = std::max(0.0, std::min(1.0, t));

    auto [segIdx, localT] = findSegment(t);

    Vector3D dir = points_[segIdx + 1] - points_[segIdx];
    return dir.normalized();
}

std::pair<size_t, double> EdgeInterpolator::findSegment(double t) const {
    if (totalLength_ <= 0.0) return {0, 0.0};

    double targetLength = t * totalLength_;

    // Binary search for the segment
    for (size_t i = 0; i + 1 < arcLengths_.size(); ++i) {
        if (targetLength >= arcLengths_[i] && targetLength <= arcLengths_[i + 1]) {
            double segmentLength = arcLengths_[i + 1] - arcLengths_[i];
            double localT = (segmentLength > 0)
                          ? (targetLength - arcLengths_[i]) / segmentLength
                          : 0.0;
            return {i, localT};
        }
    }

    // Fallback to last segment
    return {arcLengths_.size() - 2, 1.0};
}

} // namespace KooRemapper
