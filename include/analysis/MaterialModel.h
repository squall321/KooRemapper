#pragma once

#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include <array>
#include <string>

namespace KooRemapper {

/**
 * Material model type
 */
enum class MaterialType {
    LINEAR_ELASTIC,
    // Future extensions:
    // ELASTIC_PLASTIC,
    // HYPERELASTIC,
};

/**
 * Material model for constitutive relations
 * 
 * Currently supports isotropic linear elasticity (Hooke's Law)
 */
class MaterialModel {
public:
    /**
     * Create isotropic linear elastic material
     * 
     * @param E   Young's modulus (Pa or MPa, consistent units)
     * @param nu  Poisson's ratio (0 < ν < 0.5)
     */
    static MaterialModel isotropicElastic(double E, double nu);

    /**
     * Create material from LS-DYNA *MAT_ELASTIC parameters
     */
    static MaterialModel fromLSDyna_MatElastic(double rho, double E, double nu);

    // Default constructor (no material)
    MaterialModel() : type_(MaterialType::LINEAR_ELASTIC), E_(0), nu_(0) {}

    // Getters
    MaterialType type() const { return type_; }
    double youngsModulus() const { return E_; }
    double poissonsRatio() const { return nu_; }
    double shearModulus() const { return E_ / (2.0 * (1.0 + nu_)); }
    double bulkModulus() const { return E_ / (3.0 * (1.0 - 2.0 * nu_)); }
    double lameLambda() const { return E_ * nu_ / ((1.0 + nu_) * (1.0 - 2.0 * nu_)); }
    double density() const { return rho_; }

    /**
     * Check if material is valid
     */
    bool isValid() const { return E_ > 0 && nu_ > 0 && nu_ < 0.5; }

    /**
     * Compute stress from strain
     */
    StressTensor computeStress(const StrainTensor& strain) const;

    /**
     * Get 6x6 elastic stiffness matrix (Voigt notation)
     * 
     *     [C11 C12 C12  0   0   0 ]
     * C = [C12 C11 C12  0   0   0 ]
     *     [C12 C12 C11  0   0   0 ]
     *     [ 0   0   0  C44  0   0 ]
     *     [ 0   0   0   0  C44  0 ]
     *     [ 0   0   0   0   0  C44]
     * 
     * where C11 = λ + 2μ, C12 = λ, C44 = μ
     */
    std::array<std::array<double, 6>, 6> stiffnessMatrix() const;

    /**
     * Get 6x6 compliance matrix (inverse of stiffness)
     */
    std::array<std::array<double, 6>, 6> complianceMatrix() const;

    /**
     * Material description string
     */
    std::string toString() const;

private:
    MaterialType type_;
    double E_;    // Young's modulus
    double nu_;   // Poisson's ratio
    double rho_;  // Density (optional)

    MaterialModel(MaterialType type, double E, double nu, double rho = 0)
        : type_(type), E_(E), nu_(nu), rho_(rho) {}
};

} // namespace KooRemapper

