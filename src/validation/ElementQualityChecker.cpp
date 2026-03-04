#include "validation/ElementQualityChecker.h"
#include <cmath>
#include <algorithm>
#include <limits>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace KooRemapper {

ElementQualityChecker::QualityMetrics ElementQualityChecker::checkHex8(
    const std::array<Vector3D, 8>& nodes) {

    QualityMetrics metrics;
    metrics.isAcceptable = true;

    // 1. Aspect Ratio check
    auto edgeLengths = getEdgeLengths(nodes);
    metrics.aspectRatio = computeAspectRatio(edgeLengths);

    if (metrics.aspectRatio > ASPECT_RATIO_ERROR) {
        metrics.isAcceptable = false;
        metrics.warnings.push_back("Aspect ratio " + std::to_string(metrics.aspectRatio) +
                                   " exceeds error threshold " + std::to_string(ASPECT_RATIO_ERROR));
    } else if (metrics.aspectRatio > ASPECT_RATIO_WARN) {
        metrics.warnings.push_back("Aspect ratio " + std::to_string(metrics.aspectRatio) +
                                   " exceeds warning threshold " + std::to_string(ASPECT_RATIO_WARN));
    }

    // 2. Jacobian check at 8 Gauss points
    const double g = 1.0 / std::sqrt(3.0);  // Gauss point location
    std::vector<std::array<double, 3>> gaussPts = {
        {-g, -g, -g}, {+g, -g, -g}, {+g, +g, -g}, {-g, +g, -g},
        {-g, -g, +g}, {+g, -g, +g}, {+g, +g, +g}, {-g, +g, +g}
    };

    metrics.minJacobian = std::numeric_limits<double>::max();
    for (const auto& pt : gaussPts) {
        double jac = computeJacobianHex8(nodes, pt[0], pt[1], pt[2]);
        metrics.minJacobian = std::min(metrics.minJacobian, jac);
    }

    if (metrics.minJacobian <= MIN_JACOBIAN_ERROR) {
        metrics.isAcceptable = false;
        metrics.warnings.push_back("Negative or zero Jacobian detected: " +
                                   std::to_string(metrics.minJacobian));
    } else if (metrics.minJacobian < MIN_JACOBIAN_WARN) {
        metrics.warnings.push_back("Low Jacobian " + std::to_string(metrics.minJacobian) +
                                   " below warning threshold " + std::to_string(MIN_JACOBIAN_WARN));
    }

    // 3. Warping check for each face
    // Check bottom face (0-1-2-3)
    double warp1 = computeWarpingAngle(nodes[0], nodes[1], nodes[2], nodes[3]);
    metrics.maxWarping = std::max(metrics.maxWarping, warp1);

    // Check top face (4-5-6-7)
    double warp2 = computeWarpingAngle(nodes[4], nodes[5], nodes[6], nodes[7]);
    metrics.maxWarping = std::max(metrics.maxWarping, warp2);

    if (metrics.maxWarping > MAX_WARPING_ERROR) {
        metrics.isAcceptable = false;
        metrics.warnings.push_back("Severe warping " + std::to_string(metrics.maxWarping) +
                                   "° exceeds error threshold " + std::to_string(MAX_WARPING_ERROR) + "°");
    } else if (metrics.maxWarping > MAX_WARPING_WARN) {
        metrics.warnings.push_back("Warping " + std::to_string(metrics.maxWarping) +
                                   "° exceeds warning threshold " + std::to_string(MAX_WARPING_WARN) + "°");
    }

    return metrics;
}

ElementQualityChecker::QualityMetrics ElementQualityChecker::checkQuad4(
    const std::array<Vector3D, 4>& nodes) {

    QualityMetrics metrics;
    metrics.isAcceptable = true;

    // Simple aspect ratio check (max edge / min edge)
    std::vector<double> edges = {
        (nodes[1] - nodes[0]).magnitude(),
        (nodes[2] - nodes[1]).magnitude(),
        (nodes[3] - nodes[2]).magnitude(),
        (nodes[0] - nodes[3]).magnitude()
    };

    double maxEdge = *std::max_element(edges.begin(), edges.end());
    double minEdge = *std::min_element(edges.begin(), edges.end());
    metrics.aspectRatio = (minEdge > 1e-10) ? (maxEdge / minEdge) : 999.0;

    if (metrics.aspectRatio > ASPECT_RATIO_WARN) {
        metrics.warnings.push_back("Aspect ratio " + std::to_string(metrics.aspectRatio));
    }

    // Warping check
    metrics.maxWarping = computeWarpingAngle(nodes[0], nodes[1], nodes[2], nodes[3]);

    if (metrics.maxWarping > MAX_WARPING_WARN) {
        metrics.warnings.push_back("Warping " + std::to_string(metrics.maxWarping) + "°");
    }

    return metrics;
}

double ElementQualityChecker::computeJacobianHex8(
    const std::array<Vector3D, 8>& nodes,
    double xi, double eta, double zeta) {

    // Shape function derivatives (dN/dxi, dN/deta, dN/dzeta) for HEX8
    // LS-DYNA node ordering (0-indexed):
    // Bottom (zeta=-1): 0,1,2,3 counterclockwise
    // Top (zeta=+1): 4,5,6,7 counterclockwise
    // Natural coordinates: xi, eta, zeta in [-1, +1]

    double dN[8][3];

    // dN/dxi (derivative w.r.t. xi)
    dN[0][0] = -0.125 * (1 - eta) * (1 - zeta);
    dN[1][0] = +0.125 * (1 - eta) * (1 - zeta);
    dN[2][0] = +0.125 * (1 + eta) * (1 - zeta);
    dN[3][0] = -0.125 * (1 + eta) * (1 - zeta);
    dN[4][0] = -0.125 * (1 - eta) * (1 + zeta);
    dN[5][0] = +0.125 * (1 - eta) * (1 + zeta);
    dN[6][0] = +0.125 * (1 + eta) * (1 + zeta);
    dN[7][0] = -0.125 * (1 + eta) * (1 + zeta);

    // dN/deta (derivative w.r.t. eta)
    dN[0][1] = -0.125 * (1 - xi) * (1 - zeta);
    dN[1][1] = -0.125 * (1 + xi) * (1 - zeta);
    dN[2][1] = +0.125 * (1 + xi) * (1 - zeta);
    dN[3][1] = +0.125 * (1 - xi) * (1 - zeta);
    dN[4][1] = -0.125 * (1 - xi) * (1 + zeta);
    dN[5][1] = -0.125 * (1 + xi) * (1 + zeta);
    dN[6][1] = +0.125 * (1 + xi) * (1 + zeta);
    dN[7][1] = +0.125 * (1 - xi) * (1 + zeta);

    // dN/dzeta (derivative w.r.t. zeta)
    dN[0][2] = -0.125 * (1 - xi) * (1 - eta);
    dN[1][2] = -0.125 * (1 + xi) * (1 - eta);
    dN[2][2] = -0.125 * (1 + xi) * (1 + eta);
    dN[3][2] = -0.125 * (1 - xi) * (1 + eta);
    dN[4][2] = +0.125 * (1 - xi) * (1 - eta);
    dN[5][2] = +0.125 * (1 + xi) * (1 - eta);
    dN[6][2] = +0.125 * (1 + xi) * (1 + eta);
    dN[7][2] = +0.125 * (1 - xi) * (1 + eta);

    // Jacobian matrix J = [dx/dxi, dx/deta, dx/dzeta;
    //                       dy/dxi, dy/deta, dy/dzeta;
    //                       dz/dxi, dz/deta, dz/dzeta]
    double J[3][3] = {{0}};

    for (int i = 0; i < 8; ++i) {
        J[0][0] += dN[i][0] * nodes[i].x;  // dx/dxi
        J[0][1] += dN[i][1] * nodes[i].x;  // dx/deta
        J[0][2] += dN[i][2] * nodes[i].x;  // dx/dzeta

        J[1][0] += dN[i][0] * nodes[i].y;  // dy/dxi
        J[1][1] += dN[i][1] * nodes[i].y;  // dy/deta
        J[1][2] += dN[i][2] * nodes[i].y;  // dy/dzeta

        J[2][0] += dN[i][0] * nodes[i].z;  // dz/dxi
        J[2][1] += dN[i][1] * nodes[i].z;  // dz/deta
        J[2][2] += dN[i][2] * nodes[i].z;  // dz/dzeta
    }

    // Determinant of 3x3 Jacobian matrix
    double det = J[0][0] * (J[1][1] * J[2][2] - J[1][2] * J[2][1])
               - J[0][1] * (J[1][0] * J[2][2] - J[1][2] * J[2][0])
               + J[0][2] * (J[1][0] * J[2][1] - J[1][1] * J[2][0]);

    return det;
}

double ElementQualityChecker::computeAspectRatio(const std::vector<double>& edgeLengths) {
    if (edgeLengths.empty()) return 1.0;

    double maxLen = *std::max_element(edgeLengths.begin(), edgeLengths.end());
    double minLen = *std::min_element(edgeLengths.begin(), edgeLengths.end());

    return (minLen > 1e-10) ? (maxLen / minLen) : 999.0;
}

double ElementQualityChecker::computeWarpingAngle(
    const Vector3D& n1, const Vector3D& n2,
    const Vector3D& n3, const Vector3D& n4) {

    // Split quad into two triangles and compute normal vectors
    Vector3D v12 = n2 - n1;
    Vector3D v13 = n3 - n1;
    Vector3D normal1 = v12.cross(v13);
    normal1 = normal1.normalized();

    Vector3D v31 = n1 - n3;
    Vector3D v34 = n4 - n3;
    Vector3D normal2 = v31.cross(v34);
    normal2 = normal2.normalized();

    // Angle between normals
    double cosAngle = normal1.dot(normal2);
    cosAngle = std::max(-1.0, std::min(1.0, cosAngle));  // Clamp to [-1, 1]

    double angleRad = std::acos(cosAngle);
    double angleDeg = angleRad * 180.0 / M_PI;

    return angleDeg;
}

std::vector<double> ElementQualityChecker::getEdgeLengths(const std::array<Vector3D, 8>& nodes) {
    // HEX8 has 12 edges
    std::vector<double> lengths;
    lengths.reserve(12);

    // Bottom face edges
    lengths.push_back((nodes[1] - nodes[0]).magnitude());
    lengths.push_back((nodes[2] - nodes[1]).magnitude());
    lengths.push_back((nodes[3] - nodes[2]).magnitude());
    lengths.push_back((nodes[0] - nodes[3]).magnitude());

    // Top face edges
    lengths.push_back((nodes[5] - nodes[4]).magnitude());
    lengths.push_back((nodes[6] - nodes[5]).magnitude());
    lengths.push_back((nodes[7] - nodes[6]).magnitude());
    lengths.push_back((nodes[4] - nodes[7]).magnitude());

    // Vertical edges
    lengths.push_back((nodes[4] - nodes[0]).magnitude());
    lengths.push_back((nodes[5] - nodes[1]).magnitude());
    lengths.push_back((nodes[6] - nodes[2]).magnitude());
    lengths.push_back((nodes[7] - nodes[3]).magnitude());

    return lengths;
}

} // namespace KooRemapper
