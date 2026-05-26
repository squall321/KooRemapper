#pragma once

#include <vector>
#include <array>
#include <cmath>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

struct Vec2 {
    double x, y;
    Vec2() : x(0), y(0) {}
    Vec2(double x_, double y_) : x(x_), y(y_) {}
    Vec2 operator-(const Vec2& o) const { return {x - o.x, y - o.y}; }
    Vec2 operator+(const Vec2& o) const { return {x + o.x, y + o.y}; }
    Vec2 operator*(double s) const { return {x * s, y * s}; }
    double dot(const Vec2& o) const { return x * o.x + y * o.y; }
    double cross(const Vec2& o) const { return x * o.y - y * o.x; }
    double lengthSq() const { return x * x + y * y; }
    double length() const { return std::sqrt(lengthSq()); }
};

class ClosedLoop {
public:
    void setPolygon(const std::vector<Vec2>& points);
    void setSpline(const std::vector<Vec2>& controlPoints,
                   int samplesPerSegment = 20);

    // Signed distance: negative = inside, positive = outside
    double signedDistance(const Vec2& p) const;

    // Signed distance + outward gradient direction (unit vector pointing away from boundary)
    double signedDistanceWithGradient(const Vec2& p, Vec2& gradient) const;

    bool isInside(const Vec2& p) const;

    // AABB for pre-filtering (with optional padding)
    void getAABB(double& x1Min, double& x1Max,
                 double& x2Min, double& x2Max) const;

    int getVertexCount() const { return static_cast<int>(vertices_.size()); }

private:
    std::vector<Vec2> vertices_;   // closed polyline vertices (last→first auto-connected)

    int windingNumber(const Vec2& p) const;
    double minDistanceToEdges(const Vec2& p) const;
    double minDistanceToEdgesWithClosest(const Vec2& p, Vec2& closestPoint) const;
};

} // namespace KooRemapper
