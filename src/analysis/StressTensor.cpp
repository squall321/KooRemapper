#include "analysis/StressTensor.h"
#include <algorithm>
#include <cmath>

// Knowledge graph (lat.md):
//   @lat: [[modules/analysis]]

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace KooRemapper {

StressTensor StressTensor::fromStrain(
    const StrainTensor& strain,
    double E,
    double nu)
{
    // Lamé parameters
    double lambda = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu));
    double mu = E / (2.0 * (1.0 + nu));  // Shear modulus G
    
    // σ = λ·tr(ε)·I + 2μ·ε
    double traceE = strain.volumetricStrain();
    
    StressTensor stress;
    
    // Normal stresses
    stress.xx = lambda * traceE + 2.0 * mu * strain.xx;
    stress.yy = lambda * traceE + 2.0 * mu * strain.yy;
    stress.zz = lambda * traceE + 2.0 * mu * strain.zz;
    
    // Shear stresses: τ = G·γ = μ·γ
    // Note: strain.xy is engineering shear γ, not tensor shear ε
    stress.xy = mu * strain.xy;
    stress.yz = mu * strain.yz;
    stress.xz = mu * strain.xz;
    
    return stress;
}

StressTensor StressTensor::fromMatrix(const Matrix3x3& S)
{
    StressTensor s;
    s.xx = S(0, 0);
    s.yy = S(1, 1);
    s.zz = S(2, 2);
    s.xy = S(0, 1);  // Symmetric, so S(0,1) = S(1,0)
    s.yz = S(1, 2);
    s.xz = S(0, 2);
    return s;
}

Matrix3x3 StressTensor::toMatrix() const
{
    return Matrix3x3(
        xx, xy, xz,
        xy, yy, yz,
        xz, yz, zz
    );
}

std::array<double, 6> StressTensor::toVoigt() const
{
    return {{xx, yy, zz, xy, yz, xz}};
}

StressTensor StressTensor::fromVoigt(const std::array<double, 6>& v)
{
    return StressTensor(v[0], v[1], v[2], v[3], v[4], v[5]);
}

std::array<double, 3> StressTensor::principalStresses() const
{
    // Solve eigenvalue problem using analytical cubic solution
    double I1 = this->I1();
    double I2 = this->I2();
    double I3 = this->I3();
    
    // Depressed cubic: t³ + pt + q = 0 where σ = t + I1/3
    double p = I2 - I1 * I1 / 3.0;
    // ⚠ **부호가 틀려 있었다.** λ³ - I1λ² + I2λ - I3 = 0 에 λ = t + I1/3 을 넣으면
    //   t³ + Pt + Q = 0 이고 **Q = -2I1³/27 + I1I2/3 - I3** 다. 예전 판은 그 반대 부호를 썼고,
    //   그러면 삼각해의 `acos` 인자가 뒤집혀 π-θ 가 나와 **편차 고유값이 음수로 뒤집힌다**
    //   (Cardano 분기의 `cbrt(-q/2 ± √D)` 도 같이 틀린다).
    //   손검산 — diag(2,1,1) 이면 I1=4·I2=5·I3=2 이고 정답은 {2,1,1} 인데 옛 식은
    //   {1.667, 0.667, 1.667} 을 냈다. 실측에서도 같은 상태의 두 요소가 서로 다른 주응력을
    //   보고했다(2026-10-02 검증 중 발견 — 현장 보고에는 없던 결함이다).
    //   ⚠ `StrainTensor::principalStrains` 는 **다른 매개화**(p=I1/3 · r=(I1²-3I2)/9 ·
    //   cosArg=+q/(2r√r))를 쓰고 그쪽 부호는 **맞다** — 손검산으로 확인했다. 건드리지 말 것.
    double q = -2.0 * I1 * I1 * I1 / 27.0 + I1 * I2 / 3.0 - I3;
    
    std::array<double, 3> sigma;
    
    double discriminant = q * q / 4.0 + p * p * p / 27.0;
    
    if (std::abs(p) < 1e-14) {
        // Hydrostatic state
        double s = I1 / 3.0;
        sigma = {{s, s, s}};
    }
    else if (discriminant <= 0) {
        // Three real roots (use trigonometric method)
        double r = std::sqrt(-p * p * p / 27.0);
        double theta = std::acos(std::max(-1.0, std::min(1.0, -q / (2.0 * r))));
        double rCbrt = std::cbrt(r);
        
        double s0 = I1 / 3.0;
        sigma[0] = s0 + 2.0 * rCbrt * std::cos(theta / 3.0);
        sigma[1] = s0 + 2.0 * rCbrt * std::cos((theta + 2.0 * M_PI) / 3.0);
        sigma[2] = s0 + 2.0 * rCbrt * std::cos((theta + 4.0 * M_PI) / 3.0);
    }
    else {
        // One real root (shouldn't happen for symmetric stress)
        double sqrtD = std::sqrt(discriminant);
        double u = std::cbrt(-q / 2.0 + sqrtD);
        double v = std::cbrt(-q / 2.0 - sqrtD);
        double s0 = I1 / 3.0;
        sigma = {{s0 + u + v, s0 + u + v, s0 + u + v}};
    }
    
    // Sort descending
    std::sort(sigma.begin(), sigma.end(), std::greater<double>());
    
    return sigma;
}

StressTensor StressTensor::deviatoric() const
{
    double hydro = hydrostaticStress();
    return StressTensor(
        xx - hydro, yy - hydro, zz - hydro,
        xy, yz, xz
    );
}

double StressTensor::vonMises() const
{
    // von Mises equivalent stress
    // σ_vm = sqrt(3/2 * s:s)
    // = sqrt(1/2 * [(σ_xx-σ_yy)² + (σ_yy-σ_zz)² + (σ_zz-σ_xx)² + 6(τ_xy² + τ_yz² + τ_xz²)])
    
    double d1 = xx - yy;
    double d2 = yy - zz;
    double d3 = zz - xx;
    
    return std::sqrt(0.5 * (d1*d1 + d2*d2 + d3*d3 + 6.0*(xy*xy + yz*yz + xz*xz)));
}

double StressTensor::maxShearStress() const
{
    auto principal = principalStresses();
    return (principal[0] - principal[2]) / 2.0;
}

double StressTensor::triaxiality() const
{
    double vm = vonMises();
    if (std::abs(vm) < 1e-14) return 0.0;
    return hydrostaticStress() / vm;
}

double StressTensor::I2() const
{
    // I2 = σ_xx*σ_yy + σ_yy*σ_zz + σ_zz*σ_xx - τ_xy² - τ_yz² - τ_xz²
    return xx*yy + yy*zz + zz*xx - xy*xy - yz*yz - xz*xz;
}

double StressTensor::I3() const
{
    // I3 = det(σ)
    return toMatrix().determinant();
}

StressTensor StressTensor::operator+(const StressTensor& other) const
{
    return StressTensor(
        xx + other.xx, yy + other.yy, zz + other.zz,
        xy + other.xy, yz + other.yz, xz + other.xz
    );
}

StressTensor StressTensor::operator-(const StressTensor& other) const
{
    return StressTensor(
        xx - other.xx, yy - other.yy, zz - other.zz,
        xy - other.xy, yz - other.yz, xz - other.xz
    );
}

StressTensor StressTensor::operator*(double scalar) const
{
    return StressTensor(
        xx * scalar, yy * scalar, zz * scalar,
        xy * scalar, yz * scalar, xz * scalar
    );
}

StressTensor StressTensor::operator/(double scalar) const
{
    return StressTensor(
        xx / scalar, yy / scalar, zz / scalar,
        xy / scalar, yz / scalar, xz / scalar
    );
}

StressTensor& StressTensor::operator+=(const StressTensor& other)
{
    xx += other.xx; yy += other.yy; zz += other.zz;
    xy += other.xy; yz += other.yz; xz += other.xz;
    return *this;
}

StressTensor& StressTensor::operator*=(double scalar)
{
    xx *= scalar; yy *= scalar; zz *= scalar;
    xy *= scalar; yz *= scalar; xz *= scalar;
    return *this;
}

double StressTensor::doubleContraction(const StressTensor& other) const
{
    // σ1 : σ2
    return xx * other.xx + yy * other.yy + zz * other.zz
         + 2.0 * (xy * other.xy + yz * other.yz + xz * other.xz);
}

double StressTensor::magnitude() const
{
    return std::sqrt(doubleContraction(*this));
}

} // namespace KooRemapper

