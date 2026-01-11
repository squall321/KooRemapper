#pragma once

#include "core/Matrix3x3.h"
#include "core/Vector3D.h"
#include <array>
#include <vector>

namespace KooRemapper {

/**
 * Computes deformation gradient tensor F for finite elements
 * 
 * F = ∂x/∂X = J_deformed * J_reference^(-1)
 * 
 * where:
 *   x = current (deformed) coordinates
 *   X = reference (undeformed) coordinates
 *   J = Jacobian matrix = ∂X/∂ξ (or ∂x/∂ξ)
 */
class DeformationGradient {
public:
    /**
     * Compute deformation gradient for HEX8 element at a given point
     * 
     * @param refNodes  8 reference (undeformed) node positions
     * @param defNodes  8 current (deformed) node positions
     * @param xi, eta, zeta  Natural coordinates (-1 to 1)
     * @return Deformation gradient tensor F
     */
    static Matrix3x3 computeHex8(
        const std::array<Vector3D, 8>& refNodes,
        const std::array<Vector3D, 8>& defNodes,
        double xi, double eta, double zeta
    );

    /**
     * Compute deformation gradient for TET4 element
     * TET4 has constant strain, so no natural coordinates needed
     * 
     * @param refNodes  4 reference node positions
     * @param defNodes  4 current node positions
     * @return Deformation gradient tensor F
     */
    static Matrix3x3 computeTet4(
        const std::array<Vector3D, 4>& refNodes,
        const std::array<Vector3D, 4>& defNodes
    );

    /**
     * Compute Jacobian matrix for HEX8 at given natural coordinates
     * J_ij = ∂x_i/∂ξ_j
     */
    static Matrix3x3 computeJacobianHex8(
        const std::array<Vector3D, 8>& nodes,
        double xi, double eta, double zeta
    );

    /**
     * Compute Jacobian matrix for TET4
     */
    static Matrix3x3 computeJacobianTet4(
        const std::array<Vector3D, 4>& nodes
    );

    /**
     * Shape function values for HEX8 at natural coordinates
     */
    static std::array<double, 8> shapeFunctionsHex8(
        double xi, double eta, double zeta
    );

    /**
     * Shape function derivatives for HEX8 at natural coordinates
     * Returns dN/dξ, dN/dη, dN/dζ for each of 8 nodes
     */
    static std::array<Vector3D, 8> shapeFunctionDerivativesHex8(
        double xi, double eta, double zeta
    );

    /**
     * Gauss quadrature points and weights for HEX8
     * @param numPoints  1 (center) or 8 (2x2x2)
     * @return Vector of (xi, eta, zeta, weight)
     */
    static std::vector<std::array<double, 4>> gaussPointsHex8(int numPoints = 1);

    /**
     * Natural coordinates of HEX8 corner nodes
     */
    static const std::array<Vector3D, 8> HEX8_CORNERS;
};

} // namespace KooRemapper

