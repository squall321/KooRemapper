#include "analysis/DeformationGradient.h"
#include <cmath>

namespace KooRemapper {

// HEX8 corner natural coordinates
// Node ordering follows LS-DYNA convention
const std::array<Vector3D, 8> DeformationGradient::HEX8_CORNERS = {{
    Vector3D(-1, -1, -1),  // 0
    Vector3D(+1, -1, -1),  // 1
    Vector3D(+1, +1, -1),  // 2
    Vector3D(-1, +1, -1),  // 3
    Vector3D(-1, -1, +1),  // 4
    Vector3D(+1, -1, +1),  // 5
    Vector3D(+1, +1, +1),  // 6
    Vector3D(-1, +1, +1)   // 7
}};

std::array<double, 8> DeformationGradient::shapeFunctionsHex8(
    double xi, double eta, double zeta)
{
    std::array<double, 8> N;
    
    // N_i = 1/8 * (1 + xi_i*xi) * (1 + eta_i*eta) * (1 + zeta_i*zeta)
    for (int i = 0; i < 8; ++i) {
        double xi_i = HEX8_CORNERS[i].x;
        double eta_i = HEX8_CORNERS[i].y;
        double zeta_i = HEX8_CORNERS[i].z;
        
        N[i] = 0.125 * (1.0 + xi_i * xi) 
                     * (1.0 + eta_i * eta) 
                     * (1.0 + zeta_i * zeta);
    }
    
    return N;
}

std::array<Vector3D, 8> DeformationGradient::shapeFunctionDerivativesHex8(
    double xi, double eta, double zeta)
{
    std::array<Vector3D, 8> dN;
    
    for (int i = 0; i < 8; ++i) {
        double xi_i = HEX8_CORNERS[i].x;
        double eta_i = HEX8_CORNERS[i].y;
        double zeta_i = HEX8_CORNERS[i].z;
        
        // dN/dxi
        dN[i].x = 0.125 * xi_i * (1.0 + eta_i * eta) * (1.0 + zeta_i * zeta);
        
        // dN/deta
        dN[i].y = 0.125 * (1.0 + xi_i * xi) * eta_i * (1.0 + zeta_i * zeta);
        
        // dN/dzeta
        dN[i].z = 0.125 * (1.0 + xi_i * xi) * (1.0 + eta_i * eta) * zeta_i;
    }
    
    return dN;
}

Matrix3x3 DeformationGradient::computeJacobianHex8(
    const std::array<Vector3D, 8>& nodes,
    double xi, double eta, double zeta)
{
    auto dN = shapeFunctionDerivativesHex8(xi, eta, zeta);
    
    // J_ij = sum_k (dN_k/dξ_j * x_ki)
    // J = [dx/dxi, dx/deta, dx/dzeta]
    //     [dy/dxi, dy/deta, dy/dzeta]
    //     [dz/dxi, dz/deta, dz/dzeta]
    
    Matrix3x3 J;
    
    for (int i = 0; i < 3; ++i) {  // x, y, z
        for (int j = 0; j < 3; ++j) {  // xi, eta, zeta
            double sum = 0.0;
            for (int k = 0; k < 8; ++k) {
                double nodeCoord = nodes[k][i];
                double dNdXi = dN[k][j];
                sum += dNdXi * nodeCoord;
            }
            J(i, j) = sum;
        }
    }
    
    return J;
}

Matrix3x3 DeformationGradient::computeJacobianTet4(
    const std::array<Vector3D, 4>& nodes)
{
    // For TET4, Jacobian is simply the matrix of edge vectors
    // J = [X2-X1, X3-X1, X4-X1]^T
    Vector3D e1 = nodes[1] - nodes[0];
    Vector3D e2 = nodes[2] - nodes[0];
    Vector3D e3 = nodes[3] - nodes[0];
    
    return Matrix3x3::fromColumns(e1, e2, e3);
}

Matrix3x3 DeformationGradient::computeHex8(
    const std::array<Vector3D, 8>& refNodes,
    const std::array<Vector3D, 8>& defNodes,
    double xi, double eta, double zeta)
{
    // Compute Jacobians
    Matrix3x3 J_ref = computeJacobianHex8(refNodes, xi, eta, zeta);
    Matrix3x3 J_def = computeJacobianHex8(defNodes, xi, eta, zeta);
    
    // Deformation gradient: F = J_def * J_ref^(-1)
    // F = ∂x/∂X = (∂x/∂ξ) * (∂X/∂ξ)^(-1)
    Matrix3x3 J_ref_inv = J_ref.inverse();
    
    return J_def * J_ref_inv;
}

Matrix3x3 DeformationGradient::computeTet4(
    const std::array<Vector3D, 4>& refNodes,
    const std::array<Vector3D, 4>& defNodes)
{
    // Compute Jacobians
    Matrix3x3 J_ref = computeJacobianTet4(refNodes);
    Matrix3x3 J_def = computeJacobianTet4(defNodes);
    
    // Deformation gradient: F = J_def * J_ref^(-1)
    Matrix3x3 J_ref_inv = J_ref.inverse();
    
    return J_def * J_ref_inv;
}

std::vector<std::array<double, 4>> DeformationGradient::gaussPointsHex8(int numPoints)
{
    std::vector<std::array<double, 4>> points;
    
    if (numPoints == 1) {
        // Single point at center with weight 8
        points.push_back({{0.0, 0.0, 0.0, 8.0}});
    }
    else if (numPoints == 8) {
        // 2x2x2 Gauss quadrature
        const double g = 1.0 / std::sqrt(3.0);  // ≈ 0.577
        const double w = 1.0;
        
        for (int i = 0; i < 2; ++i) {
            for (int j = 0; j < 2; ++j) {
                for (int k = 0; k < 2; ++k) {
                    double xi = (i == 0) ? -g : g;
                    double eta = (j == 0) ? -g : g;
                    double zeta = (k == 0) ? -g : g;
                    points.push_back({{xi, eta, zeta, w}});
                }
            }
        }
    }
    
    return points;
}

} // namespace KooRemapper

