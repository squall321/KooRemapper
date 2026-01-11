#include "analysis/MaterialModel.h"
#include <sstream>
#include <iomanip>

namespace KooRemapper {

MaterialModel MaterialModel::isotropicElastic(double E, double nu)
{
    return MaterialModel(MaterialType::LINEAR_ELASTIC, E, nu, 0);
}

MaterialModel MaterialModel::fromLSDyna_MatElastic(double rho, double E, double nu)
{
    return MaterialModel(MaterialType::LINEAR_ELASTIC, E, nu, rho);
}

StressTensor MaterialModel::computeStress(const StrainTensor& strain) const
{
    if (type_ == MaterialType::LINEAR_ELASTIC) {
        return StressTensor::fromStrain(strain, E_, nu_);
    }
    
    // Default: return zero stress
    return StressTensor();
}

std::array<std::array<double, 6>, 6> MaterialModel::stiffnessMatrix() const
{
    std::array<std::array<double, 6>, 6> C = {{{0}}};
    
    if (type_ == MaterialType::LINEAR_ELASTIC) {
        double lambda = lameLambda();
        double mu = shearModulus();
        
        double C11 = lambda + 2.0 * mu;
        double C12 = lambda;
        double C44 = mu;
        
        // Normal-normal coupling
        C[0][0] = C11; C[0][1] = C12; C[0][2] = C12;
        C[1][0] = C12; C[1][1] = C11; C[1][2] = C12;
        C[2][0] = C12; C[2][1] = C12; C[2][2] = C11;
        
        // Shear (diagonal)
        C[3][3] = C44;
        C[4][4] = C44;
        C[5][5] = C44;
    }
    
    return C;
}

std::array<std::array<double, 6>, 6> MaterialModel::complianceMatrix() const
{
    std::array<std::array<double, 6>, 6> S = {{{0}}};
    
    if (type_ == MaterialType::LINEAR_ELASTIC && E_ > 0) {
        double E = E_;
        double nu = nu_;
        double G = shearModulus();
        
        // Normal strains
        S[0][0] = 1.0 / E;  S[0][1] = -nu / E;  S[0][2] = -nu / E;
        S[1][0] = -nu / E;  S[1][1] = 1.0 / E;  S[1][2] = -nu / E;
        S[2][0] = -nu / E;  S[2][1] = -nu / E;  S[2][2] = 1.0 / E;
        
        // Shear strains (engineering shear γ = τ/G)
        S[3][3] = 1.0 / G;
        S[4][4] = 1.0 / G;
        S[5][5] = 1.0 / G;
    }
    
    return S;
}

std::string MaterialModel::toString() const
{
    std::ostringstream oss;
    
    if (type_ == MaterialType::LINEAR_ELASTIC) {
        oss << "Linear Elastic: E=" << std::scientific << std::setprecision(3) << E_
            << ", nu=" << std::fixed << std::setprecision(2) << nu_;
        if (rho_ > 0) {
            oss << ", rho=" << std::scientific << rho_;
        }
    }
    
    return oss.str();
}

} // namespace KooRemapper

