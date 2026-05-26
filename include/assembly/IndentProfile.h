
// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]
#pragma once

namespace KooRemapper {

class IndentProfile {
public:
    IndentProfile(double depth, double r1, double r2);

    // signed distance -> displacement (negative = indent direction)
    double getDisplacement(double signedDist) const;

    // signed distance -> curvature h''(d) for bending stress calculation
    double getCurvature(double signedDist) const;

    double transitionWidth() const { return r1_ + r2_; }
    double getDepth() const { return depth_; }
    double getR1() const { return r1_; }
    double getR2() const { return r2_; }
    double getK() const { return k_; }

private:
    double depth_;
    double r1_;
    double r2_;
    double k_;     // = depth / (r1 + r2)

    double arcR1(double d) const;    // d in [0, r1]
    double arcR2(double d) const;    // d in [r1, r1+r2]
};

} // namespace KooRemapper
