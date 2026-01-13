#pragma once

#include <vector>
#include <cmath>

namespace KooRemapper {

/**
 * 2D Vector for curve operations
 */
struct Vector2D {
    double x, y;
    
    Vector2D() : x(0), y(0) {}
    Vector2D(double x, double y) : x(x), y(y) {}
    
    Vector2D operator+(const Vector2D& v) const { return Vector2D(x + v.x, y + v.y); }
    Vector2D operator-(const Vector2D& v) const { return Vector2D(x - v.x, y - v.y); }
    Vector2D operator*(double s) const { return Vector2D(x * s, y * s); }
    Vector2D operator/(double s) const { return Vector2D(x / s, y / s); }
    
    Vector2D& operator+=(const Vector2D& v) { x += v.x; y += v.y; return *this; }
    Vector2D& operator*=(double s) { x *= s; y *= s; return *this; }
    
    double length() const { return std::sqrt(x * x + y * y); }
    double lengthSquared() const { return x * x + y * y; }
    
    Vector2D normalized() const {
        double len = length();
        return (len > 0) ? Vector2D(x / len, y / len) : Vector2D(0, 0);
    }
    
    // Perpendicular vector (rotated 90 degrees counter-clockwise)
    Vector2D perpendicular() const { return Vector2D(-y, x); }
    
    double dot(const Vector2D& v) const { return x * v.x + y * v.y; }
};

inline Vector2D operator*(double s, const Vector2D& v) { return v * s; }

/**
 * Interpolation type for curves
 */
enum class InterpolationType {
    LINEAR,         // Linear interpolation between points
    CATMULL_ROM,    // Catmull-Rom spline (passes through all points)
    BSPLINE         // B-Spline (smooth, may not pass through all points)
};

/**
 * Curve interpolator for 2D curves
 * 
 * Supports multiple interpolation types and provides:
 * - Position evaluation at parameter t
 * - Tangent (derivative) evaluation
 * - Arc length computation
 * - Arc length parameterization
 */
class CurveInterpolator {
public:
    CurveInterpolator();
    ~CurveInterpolator() = default;
    
    /**
     * Set control points for the curve
     */
    void setControlPoints(const std::vector<Vector2D>& points);
    
    /**
     * Set interpolation type
     */
    void setInterpolationType(InterpolationType type) { interpolationType_ = type; }
    
    /**
     * Get number of control points
     */
    size_t getPointCount() const { return controlPoints_.size(); }
    
    /**
     * Evaluate curve position at parameter t (0 to 1)
     */
    Vector2D evaluate(double t) const;
    
    /**
     * Evaluate curve tangent (derivative) at parameter t
     */
    Vector2D evaluateTangent(double t) const;
    
    /**
     * Evaluate curve normal (perpendicular to tangent) at parameter t
     */
    Vector2D evaluateNormal(double t) const;
    
    /**
     * Get total arc length of the curve
     */
    double getArcLength() const { return totalArcLength_; }
    
    /**
     * Convert arc length to parameter t
     * @param s Arc length from start (0 to totalArcLength)
     * @return Parameter t (0 to 1)
     */
    double parameterAtArcLength(double s) const;
    
    /**
     * Evaluate position at arc length s
     */
    Vector2D evaluateAtArcLength(double s) const;
    
    /**
     * Evaluate tangent at arc length s
     */
    Vector2D evaluateTangentAtArcLength(double s) const;
    
    /**
     * Scale all control points by a factor
     */
    void scale(double factor);
    
    /**
     * Translate all control points
     */
    void translate(const Vector2D& offset);
    
    /**
     * Get control points
     */
    const std::vector<Vector2D>& getControlPoints() const { return controlPoints_; }

private:
    std::vector<Vector2D> controlPoints_;
    InterpolationType interpolationType_;
    
    // Precomputed arc length data
    double totalArcLength_;
    std::vector<double> arcLengthTable_;    // Arc length at each sample point
    std::vector<double> parameterTable_;    // Parameter t at each sample point
    static constexpr int ARC_LENGTH_SAMPLES = 1000;
    
    /**
     * Recompute arc length table after control points change
     */
    void recomputeArcLength();
    
    /**
     * Catmull-Rom spline evaluation
     */
    Vector2D catmullRom(const Vector2D& p0, const Vector2D& p1,
                        const Vector2D& p2, const Vector2D& p3, double t) const;
    
    /**
     * Catmull-Rom tangent evaluation
     */
    Vector2D catmullRomTangent(const Vector2D& p0, const Vector2D& p1,
                               const Vector2D& p2, const Vector2D& p3, double t) const;
    
    /**
     * Get segment index and local t for global parameter t
     */
    void getSegmentAndLocalT(double t, int& segment, double& localT) const;
    
    /**
     * Get control points for a segment (with virtual endpoints for Catmull-Rom)
     */
    void getSegmentPoints(int segment, Vector2D& p0, Vector2D& p1,
                          Vector2D& p2, Vector2D& p3) const;
};

} // namespace KooRemapper
