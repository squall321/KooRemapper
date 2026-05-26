#include "assembly/IndentProfile.h"
#include <cmath>
#include <algorithm>
#include <stdexcept>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

IndentProfile::IndentProfile(double depth, double r1, double r2)
    : depth_(depth), r1_(r1), r2_(r2) {
    if (depth == 0.0)
        throw std::runtime_error("IndentProfile: depth must be non-zero (positive=indent, negative=emboss)");
    if (r1 <= 0.0 || r2 <= 0.0)
        throw std::runtime_error("IndentProfile: r1 and r2 must be positive");

    k_ = depth / (r1 + r2);
}

double IndentProfile::getDisplacement(double signedDist) const {
    if (signedDist < 0.0) {
        // Inside loop: flat indent
        return -depth_;
    } else if (signedDist < r1_) {
        // r1 zone: bottom arc
        return arcR1(signedDist);
    } else if (signedDist < r1_ + r2_) {
        // r2 zone: top arc
        return arcR2(signedDist);
    } else {
        // Outside transition: no displacement
        return 0.0;
    }
}

double IndentProfile::arcR1(double d) const {
    // h(d) = -depth + k*r1*(1 - sqrt(1 - (d/r1)^2))
    double t = d / r1_;
    // Clamp for numerical safety near t=1
    if (t >= 1.0) t = 1.0 - 1e-15;
    double sq = std::sqrt(1.0 - t * t);
    return -depth_ + k_ * r1_ * (1.0 - sq);
}

double IndentProfile::arcR2(double d) const {
    // h(d) = -k*r2*(1 - sqrt(1 - ((r1+r2-d)/r2)^2))
    double u = (r1_ + r2_ - d) / r2_;
    // Clamp for numerical safety near u=1
    if (u >= 1.0) u = 1.0 - 1e-15;
    if (u <= 0.0) return 0.0;
    double sq = std::sqrt(1.0 - u * u);
    return -k_ * r2_ * (1.0 - sq);
}

double IndentProfile::getCurvature(double signedDist) const {
    if (signedDist < 0.0) {
        // Inside loop: flat → no curvature
        return 0.0;
    } else if (signedDist < r1_) {
        // r1 zone: h''(d) = k / (r1 * (1 - t^2)^(3/2)), t = d/r1
        double t = signedDist / r1_;
        if (t >= 1.0 - 1e-10) t = 1.0 - 1e-10;  // clamp near singularity
        double omt2 = 1.0 - t * t;
        return k_ / (r1_ * omt2 * std::sqrt(omt2));
    } else if (signedDist < r1_ + r2_) {
        // r2 zone: h''(d) = -k / (r2 * (1 - u^2)^(3/2)), u = (r1+r2-d)/r2
        double u = (r1_ + r2_ - signedDist) / r2_;
        if (u >= 1.0 - 1e-10) u = 1.0 - 1e-10;
        if (u <= 1e-10) return 0.0;
        double omu2 = 1.0 - u * u;
        return -k_ / (r2_ * omu2 * std::sqrt(omu2));
    } else {
        // Outside: no curvature
        return 0.0;
    }
}

} // namespace KooRemapper
