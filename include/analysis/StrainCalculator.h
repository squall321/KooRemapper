#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include <array>
#include <vector>
#include <map>

namespace KooRemapper {

/**
 * Legacy strain data structure
 * Stored as: [e_xx, e_yy, e_zz, e_xy, e_yz, e_xz]
 */
struct StrainData {
    double exx = 0.0;  // Normal strain in x
    double eyy = 0.0;  // Normal strain in y
    double ezz = 0.0;  // Normal strain in z
    double exy = 0.0;  // Shear strain xy (engineering shear / 2)
    double eyz = 0.0;  // Shear strain yz
    double exz = 0.0;  // Shear strain xz

    // Volumetric strain (trace of strain tensor)
    double volumetric() const {
        return exx + eyy + ezz;
    }

    // Von Mises equivalent strain
    double vonMises() const {
        double dev_xx = exx - volumetric() / 3.0;
        double dev_yy = eyy - volumetric() / 3.0;
        double dev_zz = ezz - volumetric() / 3.0;

        double j2 = 0.5 * (dev_xx * dev_xx + dev_yy * dev_yy + dev_zz * dev_zz) +
                    exy * exy + eyz * eyz + exz * exz;

        return std::sqrt(2.0 / 3.0 * j2);
    }

    // Principal strains (eigenvalues of strain tensor)
    std::array<double, 3> principal() const;

    // Maximum shear strain
    double maxShear() const {
        auto p = principal();
        double max_shear = 0.0;
        max_shear = std::max(max_shear, std::abs(p[0] - p[1]) / 2.0);
        max_shear = std::max(max_shear, std::abs(p[1] - p[2]) / 2.0);
        max_shear = std::max(max_shear, std::abs(p[2] - p[0]) / 2.0);
        return max_shear;
    }
};

/**
 * Element strain data
 */
struct ElementStrainData {
    int elementId;
    StrainData strain;           // Average strain for element
    std::array<StrainData, 8> nodeStrains;  // Strain at each node
    double jacobian;               // Element Jacobian determinant
};

/**
 * Strain calculation statistics
 */
struct StrainStats {
    double minVonMises = 0.0;
    double maxVonMises = 0.0;
    double avgVonMises = 0.0;
    double minVolumetric = 0.0;
    double maxVolumetric = 0.0;
    double avgVolumetric = 0.0;
    double minMaxShear = 0.0;
    double maxMaxShear = 0.0;
    double avgMaxShear = 0.0;
    double minPrincipal = 0.0;
    double maxPrincipal = 0.0;
    int elementsProcessed = 0;
};

/**
 * Calculates strain field between flat (reference) and bent (deformed) meshes
 *
 * Uses Green-Lagrange strain tensor:
 *   E = 0.5 * (F^T * F - I)
 * where F is the deformation gradient
 *
 * For small strains, this reduces to engineering strain:
 *   e = 0.5 * (grad(u) + grad(u)^T)
 */
class StrainCalculator {
public:
    enum class StrainType {
        ENGINEERING,      // Small strain (linear)
        GREEN_LAGRANGE,   // Large strain (nonlinear)
        LOGARITHMIC       // True/Hencky strain
    };

    StrainCalculator();
    ~StrainCalculator() = default;

    /**
     * Set reference (flat/undeformed) mesh
     */
    void setReferenceMesh(const Mesh* mesh) { refMesh_ = mesh; }

    /**
     * Set deformed (bent) mesh
     */
    void setDeformedMesh(const Mesh* mesh) { defMesh_ = mesh; }

    /**
     * Set strain calculation type
     */
    void setStrainType(StrainType type) { strainType_ = type; }

    /**
     * Calculate strain field
     * @return true on success
     */
    bool calculate();

    /**
     * Get strain data for an element
     */
    const ElementStrainData* getElementStrain(int elementId) const;

    /**
     * Get all element strains
     */
    const std::map<int, ElementStrainData>& getElementStrains() const {
        return elementStrains_;
    }

    /**
     * Get strain statistics
     */
    const StrainStats& getStats() const { return stats_; }
    const StrainStats& getStatistics() const { return stats_; }

    /**
     * Get node displacement vector
     */
    Vector3D getNodeDisplacement(int nodeId) const;

    /**
     * Get all displacements
     */
    const std::map<int, Vector3D>& getDisplacements() const {
        return displacements_;
    }

    /**
     * Export strain field to CSV
     */
    bool exportToCSV(const std::string& filename) const;

    /**
     * Get error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    const Mesh* refMesh_ = nullptr;
    const Mesh* defMesh_ = nullptr;
    StrainType strainType_ = StrainType::GREEN_LAGRANGE;

    std::map<int, Vector3D> displacements_;
    std::map<int, ElementStrainData> elementStrains_;
    StrainStats stats_;
    std::string errorMessage_;

    /**
     * Calculate displacement field
     */
    bool calculateDisplacements();

    /**
     * Calculate strain for a single element
     */
    bool calculateElementStrain(const Element& element, ElementStrainData& data);

    /**
     * Calculate deformation gradient F at a natural coordinate point
     */
    std::array<std::array<double, 3>, 3> calculateDeformationGradient(
        const Element& element,
        double xi, double eta, double zeta) const;

    /**
     * Shape function derivatives in natural coordinates
     */
    static std::array<Vector3D, 8> shapeDerivatives(double xi, double eta, double zeta);

    /**
     * Calculate Jacobian matrix
     */
    std::array<std::array<double, 3>, 3> jacobianMatrix(
        const Element& element,
        double xi, double eta, double zeta,
        bool useDeformed) const;

    /**
     * Invert 3x3 matrix
     */
    static bool invertMatrix3x3(
        const std::array<std::array<double, 3>, 3>& m,
        std::array<std::array<double, 3>, 3>& inv);

    /**
     * Calculate determinant of 3x3 matrix
     */
    static double determinant3x3(const std::array<std::array<double, 3>, 3>& m);

    /**
     * Update statistics
     */
    void updateStats();
};

} // namespace KooRemapper
