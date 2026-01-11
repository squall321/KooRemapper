#pragma once

#include "core/Matrix3x3.h"
#include <array>
#include <cmath>

namespace KooRemapper {

/**
 * Strain type enumeration
 */
enum class StrainType {
    ENGINEERING,      // Small strain: ε = 1/2(F + F^T) - I
    GREEN_LAGRANGE    // Large strain: E = 1/2(F^T·F - I)
};

/**
 * Symmetric strain tensor (6 independent components)
 * 
 * Voigt notation order: [ε_xx, ε_yy, ε_zz, γ_xy, γ_yz, γ_xz]
 * where γ = 2ε (engineering shear strain)
 */
class StrainTensor {
public:
    // Normal strains
    double xx, yy, zz;
    
    // Shear strains (engineering: γ = 2ε)
    double xy, yz, xz;

    // Constructors
    StrainTensor() : xx(0), yy(0), zz(0), xy(0), yz(0), xz(0) {}
    
    StrainTensor(double exx, double eyy, double ezz,
                 double gxy, double gyz, double gxz)
        : xx(exx), yy(eyy), zz(ezz), xy(gxy), yz(gyz), xz(gxz) {}

    /**
     * Create strain tensor from deformation gradient
     * 
     * @param F  Deformation gradient tensor
     * @param type  Strain type (Engineering or Green-Lagrange)
     */
    static StrainTensor fromDeformationGradient(
        const Matrix3x3& F,
        StrainType type = StrainType::ENGINEERING
    );

    /**
     * Create strain tensor from 3x3 symmetric matrix
     * Extracts diagonal and off-diagonal components
     */
    static StrainTensor fromMatrix(const Matrix3x3& E);

    /**
     * Convert to 3x3 symmetric matrix
     */
    Matrix3x3 toMatrix() const;

    /**
     * Convert to Voigt notation vector [ε_xx, ε_yy, ε_zz, γ_xy, γ_yz, γ_xz]
     */
    std::array<double, 6> toVoigt() const;

    /**
     * Create from Voigt notation
     */
    static StrainTensor fromVoigt(const std::array<double, 6>& v);

    /**
     * Principal strains (eigenvalues, sorted descending)
     */
    std::array<double, 3> principalStrains() const;

    /**
     * Volumetric strain: ε_vol = ε_xx + ε_yy + ε_zz
     */
    double volumetricStrain() const {
        return xx + yy + zz;
    }

    /**
     * Deviatoric strain tensor
     */
    StrainTensor deviatoric() const;

    /**
     * von Mises equivalent strain
     * ε_eq = sqrt(2/3 * ε':ε') where ε' is deviatoric strain
     */
    double vonMisesStrain() const;

    /**
     * Maximum shear strain
     */
    double maxShearStrain() const;

    /**
     * Strain invariants I1, I2, I3
     */
    double I1() const { return volumetricStrain(); }
    double I2() const;
    double I3() const;

    // Arithmetic operators
    StrainTensor operator+(const StrainTensor& other) const;
    StrainTensor operator-(const StrainTensor& other) const;
    StrainTensor operator*(double scalar) const;
    StrainTensor operator/(double scalar) const;

    StrainTensor& operator+=(const StrainTensor& other);
    StrainTensor& operator*=(double scalar);

    // Double contraction: ε1 : ε2
    double doubleContraction(const StrainTensor& other) const;

    // Magnitude (Frobenius norm)
    double magnitude() const;
};

// Scalar multiplication from left
inline StrainTensor operator*(double scalar, const StrainTensor& s) {
    return s * scalar;
}

} // namespace KooRemapper

