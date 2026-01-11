#include "analysis/StrainTensor.h"
#include <algorithm>
#include <cmath>

namespace KooRemapper {

StrainTensor StrainTensor::fromDeformationGradient(
    const Matrix3x3& F,
    StrainType type)
{
    Matrix3x3 E;
    
    if (type == StrainType::ENGINEERING) {
        // Small strain: ε = 1/2(F + F^T) - I
        // This is linearized strain, valid for small deformations
        Matrix3x3 sym = F.symmetric();
        E = sym - Matrix3x3::identity();
    }
    else {  // GREEN_LAGRANGE
        // Green-Lagrange strain: E = 1/2(F^T·F - I)
        // This is exact for large deformations
        Matrix3x3 FtF = F.transpose() * F;
        E = (FtF - Matrix3x3::identity()) * 0.5;
    }
    
    return fromMatrix(E);
}

StrainTensor StrainTensor::fromMatrix(const Matrix3x3& E)
{
    StrainTensor s;
    
    // Diagonal: normal strains
    s.xx = E(0, 0);
    s.yy = E(1, 1);
    s.zz = E(2, 2);
    
    // Off-diagonal: shear strains (engineering shear = 2 * tensor shear)
    s.xy = E(0, 1) + E(1, 0);  // γ_xy = 2 * ε_xy
    s.yz = E(1, 2) + E(2, 1);  // γ_yz = 2 * ε_yz
    s.xz = E(0, 2) + E(2, 0);  // γ_xz = 2 * ε_xz
    
    return s;
}

Matrix3x3 StrainTensor::toMatrix() const
{
    // Convert back to tensor form (shear = γ/2)
    return Matrix3x3(
        xx,       xy * 0.5, xz * 0.5,
        xy * 0.5, yy,       yz * 0.5,
        xz * 0.5, yz * 0.5, zz
    );
}

std::array<double, 6> StrainTensor::toVoigt() const
{
    // Voigt order: [ε_xx, ε_yy, ε_zz, γ_xy, γ_yz, γ_xz]
    return {{xx, yy, zz, xy, yz, xz}};
}

StrainTensor StrainTensor::fromVoigt(const std::array<double, 6>& v)
{
    return StrainTensor(v[0], v[1], v[2], v[3], v[4], v[5]);
}

std::array<double, 3> StrainTensor::principalStrains() const
{
    // Solve eigenvalue problem for symmetric 3x3 matrix
    // Using analytical solution for cubic equation
    
    double I1 = this->I1();
    double I2 = this->I2();
    double I3 = this->I3();
    
    // Characteristic equation: λ³ - I1·λ² + I2·λ - I3 = 0
    // Use trigonometric solution for real eigenvalues
    
    double p = I1 / 3.0;
    double q = (2.0 * I1 * I1 * I1 - 9.0 * I1 * I2 + 27.0 * I3) / 27.0;
    double r = (I1 * I1 - 3.0 * I2) / 9.0;
    
    std::array<double, 3> lambda;
    
    if (std::abs(r) < 1e-14) {
        // Hydrostatic state
        lambda = {{p, p, p}};
    }
    else {
        double rSqrt = std::sqrt(std::max(0.0, r));
        double cosArg = q / (2.0 * r * rSqrt);
        cosArg = std::max(-1.0, std::min(1.0, cosArg));  // Clamp to [-1, 1]
        double theta = std::acos(cosArg);
        
        double coeff = 2.0 * rSqrt;
        lambda[0] = p + coeff * std::cos(theta / 3.0);
        lambda[1] = p + coeff * std::cos((theta + 2.0 * M_PI) / 3.0);
        lambda[2] = p + coeff * std::cos((theta + 4.0 * M_PI) / 3.0);
    }
    
    // Sort descending
    std::sort(lambda.begin(), lambda.end(), std::greater<double>());
    
    return lambda;
}

StrainTensor StrainTensor::deviatoric() const
{
    double hydroStrain = volumetricStrain() / 3.0;
    return StrainTensor(
        xx - hydroStrain,
        yy - hydroStrain,
        zz - hydroStrain,
        xy, yz, xz
    );
}

double StrainTensor::vonMisesStrain() const
{
    // von Mises equivalent strain
    // ε_eq = sqrt(2/3 * ε':ε')
    // where ε' is deviatoric strain
    
    StrainTensor dev = deviatoric();
    
    // For symmetric tensor: ε':ε' = sum(ε_ii'^2) + 2*sum(ε_ij'^2)
    // In engineering shear: γ = 2ε, so ε_ij = γ/2
    double sum = dev.xx * dev.xx + dev.yy * dev.yy + dev.zz * dev.zz;
    sum += 0.5 * (dev.xy * dev.xy + dev.yz * dev.yz + dev.xz * dev.xz);
    
    return std::sqrt(2.0 / 3.0 * sum);
}

double StrainTensor::maxShearStrain() const
{
    auto principal = principalStrains();
    return (principal[0] - principal[2]) / 2.0;
}

double StrainTensor::I2() const
{
    // I2 = ε_xx*ε_yy + ε_yy*ε_zz + ε_zz*ε_xx - ε_xy² - ε_yz² - ε_xz²
    // Note: use tensor shear (γ/2)
    double exy = xy * 0.5;
    double eyz = yz * 0.5;
    double exz = xz * 0.5;
    
    return xx * yy + yy * zz + zz * xx - exy * exy - eyz * eyz - exz * exz;
}

double StrainTensor::I3() const
{
    // I3 = det(ε)
    Matrix3x3 E = toMatrix();
    return E.determinant();
}

StrainTensor StrainTensor::operator+(const StrainTensor& other) const
{
    return StrainTensor(
        xx + other.xx, yy + other.yy, zz + other.zz,
        xy + other.xy, yz + other.yz, xz + other.xz
    );
}

StrainTensor StrainTensor::operator-(const StrainTensor& other) const
{
    return StrainTensor(
        xx - other.xx, yy - other.yy, zz - other.zz,
        xy - other.xy, yz - other.yz, xz - other.xz
    );
}

StrainTensor StrainTensor::operator*(double scalar) const
{
    return StrainTensor(
        xx * scalar, yy * scalar, zz * scalar,
        xy * scalar, yz * scalar, xz * scalar
    );
}

StrainTensor StrainTensor::operator/(double scalar) const
{
    return StrainTensor(
        xx / scalar, yy / scalar, zz / scalar,
        xy / scalar, yz / scalar, xz / scalar
    );
}

StrainTensor& StrainTensor::operator+=(const StrainTensor& other)
{
    xx += other.xx; yy += other.yy; zz += other.zz;
    xy += other.xy; yz += other.yz; xz += other.xz;
    return *this;
}

StrainTensor& StrainTensor::operator*=(double scalar)
{
    xx *= scalar; yy *= scalar; zz *= scalar;
    xy *= scalar; yz *= scalar; xz *= scalar;
    return *this;
}

double StrainTensor::doubleContraction(const StrainTensor& other) const
{
    // ε1 : ε2 = sum(ε1_ij * ε2_ij)
    // For symmetric tensors with engineering shear
    return xx * other.xx + yy * other.yy + zz * other.zz
         + 0.5 * (xy * other.xy + yz * other.yz + xz * other.xz);
}

double StrainTensor::magnitude() const
{
    return std::sqrt(doubleContraction(*this));
}

} // namespace KooRemapper

