#include "generator/CurveInterpolator.h"
#include <algorithm>
#include <stdexcept>

namespace KooRemapper {

CurveInterpolator::CurveInterpolator()
    : interpolationType_(InterpolationType::CATMULL_ROM)
    , totalArcLength_(0)
{}

void CurveInterpolator::setControlPoints(const std::vector<Vector2D>& points) {
    if (points.size() < 2) {
        throw std::runtime_error("Curve requires at least 2 control points");
    }
    controlPoints_ = points;
    recomputeArcLength();
}

void CurveInterpolator::recomputeArcLength() {
    arcLengthTable_.clear();
    parameterTable_.clear();
    
    if (controlPoints_.size() < 2) {
        totalArcLength_ = 0;
        return;
    }
    
    arcLengthTable_.reserve(ARC_LENGTH_SAMPLES + 1);
    parameterTable_.reserve(ARC_LENGTH_SAMPLES + 1);
    
    double cumLength = 0;
    Vector2D prevPoint = evaluate(0);
    
    arcLengthTable_.push_back(0);
    parameterTable_.push_back(0);
    
    for (int i = 1; i <= ARC_LENGTH_SAMPLES; ++i) {
        double t = static_cast<double>(i) / ARC_LENGTH_SAMPLES;
        Vector2D currPoint = evaluate(t);
        
        cumLength += (currPoint - prevPoint).length();
        
        arcLengthTable_.push_back(cumLength);
        parameterTable_.push_back(t);
        
        prevPoint = currPoint;
    }
    
    totalArcLength_ = cumLength;
}

void CurveInterpolator::getSegmentAndLocalT(double t, int& segment, double& localT) const {
    int numSegments = static_cast<int>(controlPoints_.size()) - 1;
    
    t = std::clamp(t, 0.0, 1.0);
    
    double scaledT = t * numSegments;
    segment = static_cast<int>(scaledT);
    
    if (segment >= numSegments) {
        segment = numSegments - 1;
        localT = 1.0;
    } else {
        localT = scaledT - segment;
    }
}

void CurveInterpolator::getSegmentPoints(int segment, Vector2D& p0, Vector2D& p1,
                                          Vector2D& p2, Vector2D& p3) const {
    int n = static_cast<int>(controlPoints_.size());
    
    // p1 and p2 are the actual segment endpoints
    p1 = controlPoints_[segment];
    p2 = controlPoints_[segment + 1];
    
    // p0 is the point before p1 (or extrapolated)
    if (segment == 0) {
        // Extrapolate: p0 = p1 - (p2 - p1) = 2*p1 - p2
        p0 = p1 * 2 - p2;
    } else {
        p0 = controlPoints_[segment - 1];
    }
    
    // p3 is the point after p2 (or extrapolated)
    if (segment + 2 >= n) {
        // Extrapolate: p3 = p2 + (p2 - p1) = 2*p2 - p1
        p3 = p2 * 2 - p1;
    } else {
        p3 = controlPoints_[segment + 2];
    }
}

Vector2D CurveInterpolator::catmullRom(const Vector2D& p0, const Vector2D& p1,
                                        const Vector2D& p2, const Vector2D& p3,
                                        double t) const {
    double t2 = t * t;
    double t3 = t2 * t;
    
    // Catmull-Rom basis functions
    // P(t) = 0.5 * [(2*P1) + (-P0 + P2)*t + (2*P0 - 5*P1 + 4*P2 - P3)*t^2 + 
    //               (-P0 + 3*P1 - 3*P2 + P3)*t^3]
    
    return 0.5 * (
        (p1 * 2) +
        (p2 - p0) * t +
        (p0 * 2 - p1 * 5 + p2 * 4 - p3) * t2 +
        (p1 * 3 - p0 - p2 * 3 + p3) * t3
    );
}

Vector2D CurveInterpolator::catmullRomTangent(const Vector2D& p0, const Vector2D& p1,
                                               const Vector2D& p2, const Vector2D& p3,
                                               double t) const {
    double t2 = t * t;
    
    // Derivative of Catmull-Rom
    // P'(t) = 0.5 * [(-P0 + P2) + (4*P0 - 10*P1 + 8*P2 - 2*P3)*t + 
    //                (-3*P0 + 9*P1 - 9*P2 + 3*P3)*t^2]
    
    return 0.5 * (
        (p2 - p0) +
        (p0 * 4 - p1 * 10 + p2 * 8 - p3 * 2) * t +
        (p1 * 9 - p0 * 3 - p2 * 9 + p3 * 3) * t2
    );
}

Vector2D CurveInterpolator::evaluate(double t) const {
    if (controlPoints_.size() < 2) {
        return Vector2D(0, 0);
    }
    
    t = std::clamp(t, 0.0, 1.0);
    
    switch (interpolationType_) {
        case InterpolationType::LINEAR: {
            int segment;
            double localT;
            getSegmentAndLocalT(t, segment, localT);
            
            const Vector2D& p1 = controlPoints_[segment];
            const Vector2D& p2 = controlPoints_[segment + 1];
            
            return p1 + (p2 - p1) * localT;
        }
        
        case InterpolationType::CATMULL_ROM:
        case InterpolationType::BSPLINE: {  // Using Catmull-Rom for now
            int segment;
            double localT;
            getSegmentAndLocalT(t, segment, localT);
            
            Vector2D p0, p1, p2, p3;
            getSegmentPoints(segment, p0, p1, p2, p3);
            
            return catmullRom(p0, p1, p2, p3, localT);
        }
    }
    
    return Vector2D(0, 0);
}

Vector2D CurveInterpolator::evaluateTangent(double t) const {
    if (controlPoints_.size() < 2) {
        return Vector2D(1, 0);
    }
    
    t = std::clamp(t, 0.0, 1.0);
    
    switch (interpolationType_) {
        case InterpolationType::LINEAR: {
            int segment;
            double localT;
            getSegmentAndLocalT(t, segment, localT);
            
            const Vector2D& p1 = controlPoints_[segment];
            const Vector2D& p2 = controlPoints_[segment + 1];
            
            Vector2D tangent = p2 - p1;
            // Scale by number of segments to get correct magnitude
            int numSegments = static_cast<int>(controlPoints_.size()) - 1;
            return tangent * numSegments;
        }
        
        case InterpolationType::CATMULL_ROM:
        case InterpolationType::BSPLINE: {
            int segment;
            double localT;
            getSegmentAndLocalT(t, segment, localT);
            
            Vector2D p0, p1, p2, p3;
            getSegmentPoints(segment, p0, p1, p2, p3);
            
            Vector2D tangent = catmullRomTangent(p0, p1, p2, p3, localT);
            int numSegments = static_cast<int>(controlPoints_.size()) - 1;
            return tangent * numSegments;
        }
    }
    
    return Vector2D(1, 0);
}

Vector2D CurveInterpolator::evaluateNormal(double t) const {
    Vector2D tangent = evaluateTangent(t).normalized();
    return tangent.perpendicular();
}

double CurveInterpolator::parameterAtArcLength(double s) const {
    if (totalArcLength_ <= 0 || arcLengthTable_.empty()) {
        return 0;
    }
    
    s = std::clamp(s, 0.0, totalArcLength_);
    
    // Binary search in arc length table
    auto it = std::lower_bound(arcLengthTable_.begin(), arcLengthTable_.end(), s);
    
    if (it == arcLengthTable_.begin()) {
        return 0;
    }
    if (it == arcLengthTable_.end()) {
        return 1;
    }
    
    size_t idx = std::distance(arcLengthTable_.begin(), it);
    
    // Linear interpolation between samples
    double s0 = arcLengthTable_[idx - 1];
    double s1 = arcLengthTable_[idx];
    double t0 = parameterTable_[idx - 1];
    double t1 = parameterTable_[idx];
    
    if (s1 - s0 < 1e-10) {
        return t0;
    }
    
    double localT = (s - s0) / (s1 - s0);
    return t0 + (t1 - t0) * localT;
}

Vector2D CurveInterpolator::evaluateAtArcLength(double s) const {
    double t = parameterAtArcLength(s);
    return evaluate(t);
}

Vector2D CurveInterpolator::evaluateTangentAtArcLength(double s) const {
    double t = parameterAtArcLength(s);
    return evaluateTangent(t);
}

void CurveInterpolator::scale(double factor) {
    for (auto& pt : controlPoints_) {
        pt *= factor;
    }
    recomputeArcLength();
}

void CurveInterpolator::translate(const Vector2D& offset) {
    for (auto& pt : controlPoints_) {
        pt += offset;
    }
    // Translation doesn't affect arc length, no need to recompute
}

} // namespace KooRemapper
