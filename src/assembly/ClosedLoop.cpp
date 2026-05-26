#include "assembly/ClosedLoop.h"
#include <algorithm>
#include <limits>
#include <stdexcept>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

void ClosedLoop::setPolygon(const std::vector<Vec2>& points) {
    if (points.size() < 3) {
        throw std::runtime_error("ClosedLoop: polygon requires at least 3 points");
    }
    vertices_ = points;
}

void ClosedLoop::setSpline(const std::vector<Vec2>& controlPoints,
                            int samplesPerSegment) {
    if (controlPoints.size() < 3) {
        throw std::runtime_error("ClosedLoop: spline requires at least 3 control points");
    }

    // Catmull-Rom closed spline: each segment uses 4 control points
    int n = static_cast<int>(controlPoints.size());
    vertices_.clear();
    vertices_.reserve(n * samplesPerSegment);

    for (int i = 0; i < n; ++i) {
        const Vec2& p0 = controlPoints[(i - 1 + n) % n];
        const Vec2& p1 = controlPoints[i];
        const Vec2& p2 = controlPoints[(i + 1) % n];
        const Vec2& p3 = controlPoints[(i + 2) % n];

        for (int s = 0; s < samplesPerSegment; ++s) {
            double t = static_cast<double>(s) / samplesPerSegment;
            double t2 = t * t;
            double t3 = t2 * t;

            // Catmull-Rom basis (tau = 0.5)
            double h1 = -0.5 * t3 + t2 - 0.5 * t;
            double h2 = 1.5 * t3 - 2.5 * t2 + 1.0;
            double h3 = -1.5 * t3 + 2.0 * t2 + 0.5 * t;
            double h4 = 0.5 * t3 - 0.5 * t2;

            Vec2 pt;
            pt.x = h1 * p0.x + h2 * p1.x + h3 * p2.x + h4 * p3.x;
            pt.y = h1 * p0.y + h2 * p1.y + h3 * p2.y + h4 * p3.y;
            vertices_.push_back(pt);
        }
    }
}

double ClosedLoop::signedDistance(const Vec2& p) const {
    double minDist = minDistanceToEdges(p);
    int wn = windingNumber(p);
    return (wn != 0) ? -minDist : minDist;
}

bool ClosedLoop::isInside(const Vec2& p) const {
    return windingNumber(p) != 0;
}

void ClosedLoop::getAABB(double& x1Min, double& x1Max,
                          double& x2Min, double& x2Max) const {
    if (vertices_.empty()) {
        x1Min = x1Max = x2Min = x2Max = 0.0;
        return;
    }
    x1Min = x1Max = vertices_[0].x;
    x2Min = x2Max = vertices_[0].y;
    for (const auto& v : vertices_) {
        if (v.x < x1Min) x1Min = v.x;
        if (v.x > x1Max) x1Max = v.x;
        if (v.y < x2Min) x2Min = v.y;
        if (v.y > x2Max) x2Max = v.y;
    }
}

int ClosedLoop::windingNumber(const Vec2& p) const {
    int wn = 0;
    int n = static_cast<int>(vertices_.size());

    for (int i = 0; i < n; ++i) {
        const Vec2& a = vertices_[i];
        const Vec2& b = vertices_[(i + 1) % n];

        if (a.y <= p.y) {
            if (b.y > p.y) {
                // Upward crossing
                Vec2 edge = b - a;
                Vec2 toP = p - a;
                if (edge.cross(toP) > 0.0) {
                    ++wn;
                }
            }
        } else {
            if (b.y <= p.y) {
                // Downward crossing
                Vec2 edge = b - a;
                Vec2 toP = p - a;
                if (edge.cross(toP) < 0.0) {
                    --wn;
                }
            }
        }
    }
    return wn;
}

double ClosedLoop::signedDistanceWithGradient(const Vec2& p, Vec2& gradient) const {
    Vec2 closestPt;
    double minDist = minDistanceToEdgesWithClosest(p, closestPt);
    int wn = windingNumber(p);
    double sd = (wn != 0) ? -minDist : minDist;

    // Gradient = unit vector from closest boundary point to p (outward direction)
    Vec2 diff = p - closestPt;
    double len = diff.length();
    if (len > 1e-15) {
        gradient = {diff.x / len, diff.y / len};
    } else {
        // Exactly on boundary: use edge normal
        gradient = {1.0, 0.0};
    }
    // If inside, gradient still points from boundary to p (inward), which is correct
    // because the gradient of signed distance = outward normal at boundary
    // For inside points, the gradient direction matters for curvature decomposition
    return sd;
}

double ClosedLoop::minDistanceToEdgesWithClosest(const Vec2& p, Vec2& closestPoint) const {
    double minDistSq = std::numeric_limits<double>::max();
    int n = static_cast<int>(vertices_.size());

    for (int i = 0; i < n; ++i) {
        const Vec2& a = vertices_[i];
        const Vec2& b = vertices_[(i + 1) % n];

        Vec2 ab = b - a;
        double lenSq = ab.lengthSq();

        double t;
        if (lenSq < 1e-30) {
            t = 0.0;
        } else {
            Vec2 ap = p - a;
            t = ap.dot(ab) / lenSq;
            if (t < 0.0) t = 0.0;
            if (t > 1.0) t = 1.0;
        }

        Vec2 closest = a + ab * t;
        Vec2 diff = p - closest;
        double distSq = diff.lengthSq();

        if (distSq < minDistSq) {
            minDistSq = distSq;
            closestPoint = closest;
        }
    }

    return std::sqrt(minDistSq);
}

double ClosedLoop::minDistanceToEdges(const Vec2& p) const {
    double minDistSq = std::numeric_limits<double>::max();
    int n = static_cast<int>(vertices_.size());

    for (int i = 0; i < n; ++i) {
        const Vec2& a = vertices_[i];
        const Vec2& b = vertices_[(i + 1) % n];

        Vec2 ab = b - a;
        double lenSq = ab.lengthSq();

        double t;
        if (lenSq < 1e-30) {
            t = 0.0;
        } else {
            Vec2 ap = p - a;
            t = ap.dot(ab) / lenSq;
            if (t < 0.0) t = 0.0;
            if (t > 1.0) t = 1.0;
        }

        Vec2 closest = a + ab * t;
        Vec2 diff = p - closest;
        double distSq = diff.lengthSq();

        if (distSq < minDistSq) {
            minDistSq = distSq;
        }
    }

    return std::sqrt(minDistSq);
}

} // namespace KooRemapper
