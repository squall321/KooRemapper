#include "analysis/StrainCalculator.h"
#include <cmath>
#include <fstream>
#include <algorithm>
#include <limits>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace KooRemapper {

// Principal strain calculation using analytical solution for 3x3 symmetric matrix
std::array<double, 3> StrainData::principal() const {
    // Characteristic polynomial: λ³ - I1*λ² + I2*λ - I3 = 0
    // Invariants
    double I1 = exx + eyy + ezz;
    double I2 = exx * eyy + eyy * ezz + ezz * exx - exy * exy - eyz * eyz - exz * exz;
    double I3 = exx * eyy * ezz + 2.0 * exy * eyz * exz
                - exx * eyz * eyz - eyy * exz * exz - ezz * exy * exy;

    // Solve using Cardano's formula
    double p = I2 - I1 * I1 / 3.0;
    double q = 2.0 * I1 * I1 * I1 / 27.0 - I1 * I2 / 3.0 + I3;

    std::array<double, 3> result = {0.0, 0.0, 0.0};

    double discriminant = q * q / 4.0 + p * p * p / 27.0;

    if (discriminant < 0) {
        // Three real roots
        double m = 2.0 * std::sqrt(-p / 3.0);
        double theta = std::acos(3.0 * q / (p * m)) / 3.0;

        result[0] = m * std::cos(theta) + I1 / 3.0;
        result[1] = m * std::cos(theta - 2.0 * M_PI / 3.0) + I1 / 3.0;
        result[2] = m * std::cos(theta - 4.0 * M_PI / 3.0) + I1 / 3.0;
    } else {
        // One or two real roots (handle edge cases)
        double sqrtD = std::sqrt(std::max(0.0, discriminant));
        double u = std::cbrt(-q / 2.0 + sqrtD);
        double v = std::cbrt(-q / 2.0 - sqrtD);
        result[0] = u + v + I1 / 3.0;
        result[1] = result[0];
        result[2] = result[0];
    }

    // Sort in descending order
    std::sort(result.begin(), result.end(), std::greater<double>());
    return result;
}

StrainCalculator::StrainCalculator() = default;

bool StrainCalculator::calculate() {
    if (!refMesh_ || !defMesh_) {
        errorMessage_ = "Reference or deformed mesh not set";
        return false;
    }

    if (refMesh_->getNodeCount() != defMesh_->getNodeCount()) {
        errorMessage_ = "Mesh node counts do not match";
        return false;
    }

    // Calculate displacements
    if (!calculateDisplacements()) {
        return false;
    }

    // Calculate strains for each element
    elementStrains_.clear();

    for (const auto& [elemId, element] : refMesh_->getElements()) {
        ElementStrainData data;
        data.elementId = elemId;

        if (calculateElementStrain(element, data)) {
            elementStrains_[elemId] = data;
        }
    }

    // Update statistics
    updateStats();

    return true;
}

bool StrainCalculator::calculateDisplacements() {
    displacements_.clear();

    for (const auto& [nodeId, refNode] : refMesh_->getNodes()) {
        const Node* defNode = defMesh_->getNode(nodeId);
        if (!defNode) {
            errorMessage_ = "Node " + std::to_string(nodeId) + " not found in deformed mesh";
            return false;
        }

        Vector3D displacement = defNode->position - refNode.position;
        displacements_[nodeId] = displacement;
    }

    return true;
}

bool StrainCalculator::calculateElementStrain(const Element& element, ElementStrainData& data) {
    // Gauss points for 2x2x2 integration
    const double gp = 1.0 / std::sqrt(3.0);
    const double gaussPoints[2] = {-gp, gp};

    StrainData avgStrain;
    int numPoints = 0;

    // Integrate over Gauss points
    for (double xi : gaussPoints) {
        for (double eta : gaussPoints) {
            for (double zeta : gaussPoints) {
                // Calculate deformation gradient
                auto F = calculateDeformationGradient(element, xi, eta, zeta);

                // Calculate strain based on type
                StrainData strain;

                if (strainType_ == StrainType::ENGINEERING) {
                    // Engineering strain: e = 0.5 * (F + F^T) - I
                    strain.exx = F[0][0] - 1.0;
                    strain.eyy = F[1][1] - 1.0;
                    strain.ezz = F[2][2] - 1.0;
                    strain.exy = 0.5 * (F[0][1] + F[1][0]);
                    strain.eyz = 0.5 * (F[1][2] + F[2][1]);
                    strain.exz = 0.5 * (F[0][2] + F[2][0]);
                }
                else if (strainType_ == StrainType::GREEN_LAGRANGE) {
                    // Green-Lagrange: E = 0.5 * (F^T * F - I)
                    // C = F^T * F (Right Cauchy-Green tensor)
                    double C[3][3];
                    for (int i = 0; i < 3; ++i) {
                        for (int j = 0; j < 3; ++j) {
                            C[i][j] = 0.0;
                            for (int k = 0; k < 3; ++k) {
                                C[i][j] += F[k][i] * F[k][j];
                            }
                        }
                    }

                    strain.exx = 0.5 * (C[0][0] - 1.0);
                    strain.eyy = 0.5 * (C[1][1] - 1.0);
                    strain.ezz = 0.5 * (C[2][2] - 1.0);
                    strain.exy = 0.5 * C[0][1];
                    strain.eyz = 0.5 * C[1][2];
                    strain.exz = 0.5 * C[0][2];
                }
                else if (strainType_ == StrainType::LOGARITHMIC) {
                    // Logarithmic (Hencky) strain: e = 0.5 * ln(C)
                    // Simplified: use principal stretches
                    double C[3][3];
                    for (int i = 0; i < 3; ++i) {
                        for (int j = 0; j < 3; ++j) {
                            C[i][j] = 0.0;
                            for (int k = 0; k < 3; ++k) {
                                C[i][j] += F[k][i] * F[k][j];
                            }
                        }
                    }

                    // For now, use diagonal approximation
                    strain.exx = 0.5 * std::log(std::max(1e-10, C[0][0]));
                    strain.eyy = 0.5 * std::log(std::max(1e-10, C[1][1]));
                    strain.ezz = 0.5 * std::log(std::max(1e-10, C[2][2]));
                    strain.exy = 0.5 * C[0][1] / std::sqrt(C[0][0] * C[1][1]);
                    strain.eyz = 0.5 * C[1][2] / std::sqrt(C[1][1] * C[2][2]);
                    strain.exz = 0.5 * C[0][2] / std::sqrt(C[0][0] * C[2][2]);
                }

                avgStrain.exx += strain.exx;
                avgStrain.eyy += strain.eyy;
                avgStrain.ezz += strain.ezz;
                avgStrain.exy += strain.exy;
                avgStrain.eyz += strain.eyz;
                avgStrain.exz += strain.exz;
                numPoints++;
            }
        }
    }

    // Average strain
    if (numPoints > 0) {
        avgStrain.exx /= numPoints;
        avgStrain.eyy /= numPoints;
        avgStrain.ezz /= numPoints;
        avgStrain.exy /= numPoints;
        avgStrain.eyz /= numPoints;
        avgStrain.exz /= numPoints;
    }

    data.strain = avgStrain;

    // Calculate Jacobian at center
    auto J = jacobianMatrix(element, 0.0, 0.0, 0.0, false);
    data.jacobian = determinant3x3(J);

    // Calculate strain at element nodes
    const double nodeCoords[8][3] = {
        {-1, -1, -1}, {1, -1, -1}, {1, 1, -1}, {-1, 1, -1},
        {-1, -1,  1}, {1, -1,  1}, {1, 1,  1}, {-1, 1,  1}
    };

    for (int n = 0; n < 8; ++n) {
        auto F = calculateDeformationGradient(element,
            nodeCoords[n][0], nodeCoords[n][1], nodeCoords[n][2]);

        StrainData& ns = data.nodeStrains[n];

        // Use Green-Lagrange for node strains
        double C[3][3];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                C[i][j] = 0.0;
                for (int k = 0; k < 3; ++k) {
                    C[i][j] += F[k][i] * F[k][j];
                }
            }
        }

        ns.exx = 0.5 * (C[0][0] - 1.0);
        ns.eyy = 0.5 * (C[1][1] - 1.0);
        ns.ezz = 0.5 * (C[2][2] - 1.0);
        ns.exy = 0.5 * C[0][1];
        ns.eyz = 0.5 * C[1][2];
        ns.exz = 0.5 * C[0][2];
    }

    return true;
}

std::array<std::array<double, 3>, 3> StrainCalculator::calculateDeformationGradient(
    const Element& element, double xi, double eta, double zeta) const {

    // Get shape function derivatives
    auto dN = shapeDerivatives(xi, eta, zeta);

    // Reference Jacobian
    auto J_ref = jacobianMatrix(element, xi, eta, zeta, false);

    // Invert reference Jacobian
    std::array<std::array<double, 3>, 3> J_inv;
    if (!invertMatrix3x3(J_ref, J_inv)) {
        // Return identity if singular
        return {{{1, 0, 0}, {0, 1, 0}, {0, 0, 1}}};
    }

    // Transform derivatives to physical coordinates
    std::array<Vector3D, 8> dN_phys;
    for (int n = 0; n < 8; ++n) {
        dN_phys[n].x = J_inv[0][0] * dN[n].x + J_inv[0][1] * dN[n].y + J_inv[0][2] * dN[n].z;
        dN_phys[n].y = J_inv[1][0] * dN[n].x + J_inv[1][1] * dN[n].y + J_inv[1][2] * dN[n].z;
        dN_phys[n].z = J_inv[2][0] * dN[n].x + J_inv[2][1] * dN[n].y + J_inv[2][2] * dN[n].z;
    }

    // Calculate deformation gradient F = dx/dX = I + du/dX
    std::array<std::array<double, 3>, 3> F = {{{1, 0, 0}, {0, 1, 0}, {0, 0, 1}}};

    for (int n = 0; n < 8; ++n) {
        int nodeId = element.nodeIds[n];
        auto it = displacements_.find(nodeId);
        if (it == displacements_.end()) continue;

        const Vector3D& u = it->second;

        // F_ij = δ_ij + ∂u_i/∂X_j
        F[0][0] += u.x * dN_phys[n].x;
        F[0][1] += u.x * dN_phys[n].y;
        F[0][2] += u.x * dN_phys[n].z;
        F[1][0] += u.y * dN_phys[n].x;
        F[1][1] += u.y * dN_phys[n].y;
        F[1][2] += u.y * dN_phys[n].z;
        F[2][0] += u.z * dN_phys[n].x;
        F[2][1] += u.z * dN_phys[n].y;
        F[2][2] += u.z * dN_phys[n].z;
    }

    return F;
}

std::array<Vector3D, 8> StrainCalculator::shapeDerivatives(double xi, double eta, double zeta) {
    // Shape function derivatives for 8-node hex
    // N_i = (1/8)(1 + xi_i*xi)(1 + eta_i*eta)(1 + zeta_i*zeta)
    std::array<Vector3D, 8> dN;

    const double nodeXi[8]   = {-1, 1, 1, -1, -1, 1, 1, -1};
    const double nodeEta[8]  = {-1, -1, 1, 1, -1, -1, 1, 1};
    const double nodeZeta[8] = {-1, -1, -1, -1, 1, 1, 1, 1};

    for (int i = 0; i < 8; ++i) {
        double xi_i = nodeXi[i];
        double eta_i = nodeEta[i];
        double zeta_i = nodeZeta[i];

        dN[i].x = 0.125 * xi_i * (1.0 + eta_i * eta) * (1.0 + zeta_i * zeta);
        dN[i].y = 0.125 * (1.0 + xi_i * xi) * eta_i * (1.0 + zeta_i * zeta);
        dN[i].z = 0.125 * (1.0 + xi_i * xi) * (1.0 + eta_i * eta) * zeta_i;
    }

    return dN;
}

std::array<std::array<double, 3>, 3> StrainCalculator::jacobianMatrix(
    const Element& element, double xi, double eta, double zeta, bool useDeformed) const {

    auto dN = shapeDerivatives(xi, eta, zeta);

    std::array<std::array<double, 3>, 3> J = {{{0, 0, 0}, {0, 0, 0}, {0, 0, 0}}};

    const Mesh* mesh = useDeformed ? defMesh_ : refMesh_;

    for (int n = 0; n < 8; ++n) {
        int nodeId = element.nodeIds[n];
        const Node* node = mesh->getNode(nodeId);
        if (!node) continue;

        const Vector3D& pos = node->position;

        J[0][0] += pos.x * dN[n].x;
        J[0][1] += pos.x * dN[n].y;
        J[0][2] += pos.x * dN[n].z;
        J[1][0] += pos.y * dN[n].x;
        J[1][1] += pos.y * dN[n].y;
        J[1][2] += pos.y * dN[n].z;
        J[2][0] += pos.z * dN[n].x;
        J[2][1] += pos.z * dN[n].y;
        J[2][2] += pos.z * dN[n].z;
    }

    return J;
}

bool StrainCalculator::invertMatrix3x3(
    const std::array<std::array<double, 3>, 3>& m,
    std::array<std::array<double, 3>, 3>& inv) {

    double det = determinant3x3(m);
    if (std::abs(det) < 1e-20) return false;

    double invDet = 1.0 / det;

    inv[0][0] = (m[1][1] * m[2][2] - m[1][2] * m[2][1]) * invDet;
    inv[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
    inv[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
    inv[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
    inv[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
    inv[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
    inv[2][0] = (m[1][0] * m[2][1] - m[1][1] * m[2][0]) * invDet;
    inv[2][1] = (m[0][1] * m[2][0] - m[0][0] * m[2][1]) * invDet;
    inv[2][2] = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) * invDet;

    return true;
}

double StrainCalculator::determinant3x3(const std::array<std::array<double, 3>, 3>& m) {
    return m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
         - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
         + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
}

void StrainCalculator::updateStats() {
    stats_ = StrainStats();

    if (elementStrains_.empty()) return;

    stats_.minVonMises = std::numeric_limits<double>::max();
    stats_.maxVonMises = std::numeric_limits<double>::lowest();
    stats_.minVolumetric = std::numeric_limits<double>::max();
    stats_.maxVolumetric = std::numeric_limits<double>::lowest();
    stats_.minMaxShear = std::numeric_limits<double>::max();
    stats_.maxMaxShear = std::numeric_limits<double>::lowest();
    stats_.minPrincipal = std::numeric_limits<double>::max();
    stats_.maxPrincipal = std::numeric_limits<double>::lowest();

    double sumVonMises = 0.0;
    double sumVolumetric = 0.0;
    double sumMaxShear = 0.0;

    for (const auto& [id, data] : elementStrains_) {
        double vm = data.strain.vonMises();
        double vol = data.strain.volumetric();
        double ms = data.strain.maxShear();
        auto principals = data.strain.principal();

        stats_.minVonMises = std::min(stats_.minVonMises, vm);
        stats_.maxVonMises = std::max(stats_.maxVonMises, vm);
        stats_.minVolumetric = std::min(stats_.minVolumetric, vol);
        stats_.maxVolumetric = std::max(stats_.maxVolumetric, vol);
        stats_.minMaxShear = std::min(stats_.minMaxShear, ms);
        stats_.maxMaxShear = std::max(stats_.maxMaxShear, ms);
        stats_.minPrincipal = std::min(stats_.minPrincipal, principals[2]);
        stats_.maxPrincipal = std::max(stats_.maxPrincipal, principals[0]);

        sumVonMises += vm;
        sumVolumetric += vol;
        sumMaxShear += ms;
        stats_.elementsProcessed++;
    }

    if (stats_.elementsProcessed > 0) {
        stats_.avgVonMises = sumVonMises / stats_.elementsProcessed;
        stats_.avgVolumetric = sumVolumetric / stats_.elementsProcessed;
        stats_.avgMaxShear = sumMaxShear / stats_.elementsProcessed;
    }
}

const ElementStrainData* StrainCalculator::getElementStrain(int elementId) const {
    auto it = elementStrains_.find(elementId);
    return (it != elementStrains_.end()) ? &it->second : nullptr;
}

Vector3D StrainCalculator::getNodeDisplacement(int nodeId) const {
    auto it = displacements_.find(nodeId);
    return (it != displacements_.end()) ? it->second : Vector3D();
}

bool StrainCalculator::exportToCSV(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        return false;
    }

    file << "ElementID,exx,eyy,ezz,exy,eyz,exz,VonMises,Volumetric,MaxShear,Jacobian\n";

    for (const auto& [id, data] : elementStrains_) {
        file << id << ","
             << data.strain.exx << ","
             << data.strain.eyy << ","
             << data.strain.ezz << ","
             << data.strain.exy << ","
             << data.strain.eyz << ","
             << data.strain.exz << ","
             << data.strain.vonMises() << ","
             << data.strain.volumetric() << ","
             << data.strain.maxShear() << ","
             << data.jacobian << "\n";
    }

    return true;
}

} // namespace KooRemapper
