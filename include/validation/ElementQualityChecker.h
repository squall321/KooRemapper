#ifndef ELEMENTQUALITYCHECKER_H
#define ELEMENTQUALITYCHECKER_H

#include "core/Vector3D.h"
#include <array>
#include <vector>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/validation]]

namespace KooRemapper {

class ElementQualityChecker {
public:
    struct QualityMetrics {
        double aspectRatio = 0.0;
        double minJacobian = 1.0;
        double maxWarping = 0.0;     // In degrees
        double skewness = 0.0;
        bool isAcceptable = true;
        std::vector<std::string> warnings;
    };

    struct QualitySummary {
        int totalElements = 0;
        int poorAspectRatio = 0;      // > 10
        int veryPoorAspectRatio = 0;  // > 20
        int poorJacobian = 0;          // < 0.1
        int negativeJacobian = 0;      // <= 0
        int poorWarping = 0;           // > 30°
        int severeWarping = 0;         // > 45°
        double maxAspectRatio = 0.0;
        double minJacobian = 1.0;
        double maxWarping = 0.0;
    };

    // Check individual HEX8 element
    QualityMetrics checkHex8(const std::array<Vector3D, 8>& nodes);

    // Check individual TET4 element
    QualityMetrics checkTet4(const std::array<Vector3D, 4>& nodes);

    // Check individual QUAD4 element
    QualityMetrics checkQuad4(const std::array<Vector3D, 4>& nodes);

    // Thresholds for quality checks
    static constexpr double ASPECT_RATIO_WARN = 10.0;
    static constexpr double ASPECT_RATIO_ERROR = 20.0;
    static constexpr double MIN_JACOBIAN_WARN = 0.1;
    static constexpr double MIN_JACOBIAN_ERROR = -1.0e-10;  // Allow numerical noise near zero
    static constexpr double MAX_WARPING_WARN = 30.0;  // degrees
    static constexpr double MAX_WARPING_ERROR = 45.0; // degrees

    // Compute signed volume for TET4 (positive = valid, negative = inverted)
    static double computeVolumeTet4(const std::array<Vector3D, 4>& nodes);

private:
    // Compute Jacobian at a point (xi, eta, zeta) for HEX8
    double computeJacobianHex8(const std::array<Vector3D, 8>& nodes,
                                double xi, double eta, double zeta);

    // Compute aspect ratio (max edge / min edge)
    double computeAspectRatio(const std::vector<double>& edgeLengths);

    // Compute warping angle for a quad face
    double computeWarpingAngle(const Vector3D& n1, const Vector3D& n2,
                               const Vector3D& n3, const Vector3D& n4);

    // Get all edge lengths
    std::vector<double> getEdgeLengths(const std::array<Vector3D, 8>& nodes);
};

} // namespace KooRemapper

#endif // ELEMENTQUALITYCHECKER_H
