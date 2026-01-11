#pragma once

#include "analysis/StrainTensor.h"
#include "core/Matrix3x3.h"
#include <array>

namespace KooRemapper {

/**
 * Symmetric stress tensor (6 independent components)
 * 
 * Voigt notation order: [σ_xx, σ_yy, σ_zz, τ_xy, τ_yz, τ_xz]
 */
class StressTensor {
public:
    // Normal stresses
    double xx, yy, zz;
    
    // Shear stresses
    double xy, yz, xz;

    // Constructors
    StressTensor() : xx(0), yy(0), zz(0), xy(0), yz(0), xz(0) {}
    
    StressTensor(double sxx, double syy, double szz,
                 double sxy, double syz, double sxz)
        : xx(sxx), yy(syy), zz(szz), xy(sxy), yz(syz), xz(sxz) {}

    /**
     * Compute stress from strain using isotropic linear elasticity
     * 
     * σ = λ·tr(ε)·I + 2μ·ε
     * 
     * where:
     *   λ = E·ν / ((1+ν)(1-2ν))  (Lamé's first parameter)
     *   μ = E / (2(1+ν))          (Shear modulus)
     * 
     * @param strain  Strain tensor
     * @param E       Young's modulus
     * @param nu      Poisson's ratio
     */
    static StressTensor fromStrain(
        const StrainTensor& strain,
        double E,
        double nu
    );

    /**
     * Create from 3x3 symmetric matrix
     */
    static StressTensor fromMatrix(const Matrix3x3& S);

    /**
     * Convert to 3x3 symmetric matrix
     */
    Matrix3x3 toMatrix() const;

    /**
     * Convert to Voigt notation [σ_xx, σ_yy, σ_zz, τ_xy, τ_yz, τ_xz]
     */
    std::array<double, 6> toVoigt() const;

    /**
     * Create from Voigt notation
     */
    static StressTensor fromVoigt(const std::array<double, 6>& v);

    /**
     * Principal stresses (eigenvalues, sorted descending)
     */
    std::array<double, 3> principalStresses() const;

    /**
     * Hydrostatic (mean) stress: σ_m = (σ_xx + σ_yy + σ_zz) / 3
     */
    double hydrostaticStress() const {
        return (xx + yy + zz) / 3.0;
    }

    /**
     * Deviatoric stress tensor
     */
    StressTensor deviatoric() const;

    /**
     * von Mises equivalent stress
     * σ_vm = sqrt(3/2 * s:s) where s is deviatoric stress
     */
    double vonMises() const;

    /**
     * Maximum shear stress (Tresca)
     */
    double maxShearStress() const;

    /**
     * Stress triaxiality: η = σ_m / σ_vm
     */
    double triaxiality() const;

    /**
     * Stress invariants I1, I2, I3
     */
    double I1() const { return xx + yy + zz; }
    double I2() const;
    double I3() const;

    // Arithmetic operators
    StressTensor operator+(const StressTensor& other) const;
    StressTensor operator-(const StressTensor& other) const;
    StressTensor operator*(double scalar) const;
    StressTensor operator/(double scalar) const;

    StressTensor& operator+=(const StressTensor& other);
    StressTensor& operator*=(double scalar);

    // Double contraction: σ1 : σ2
    double doubleContraction(const StressTensor& other) const;

    // Magnitude (Frobenius norm)
    double magnitude() const;
};

// Scalar multiplication from left
inline StressTensor operator*(double scalar, const StressTensor& s) {
    return s * scalar;
}

} // namespace KooRemapper

