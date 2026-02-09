#pragma once

#include <vector>
#include <string>

namespace KooRemapper {

/**
 * Per-part squeeze configuration
 */
struct PartSqueezeConfig {
    int pid = 0;
    double eps_x = 0.0;  // X-direction strain (negative = compression)
    double eps_y = 0.0;  // Y-direction strain
    double eps_z = 0.0;  // Z-direction strain
};

/**
 * Squeeze configuration for interference fit modeling
 *
 * Specifies per-part strain conditions and optional material override.
 * Negative strain = compression, positive = expansion.
 */
struct SqueezeConfig {
    std::vector<PartSqueezeConfig> parts;
    double E = 0.0;       // Optional override Young's modulus
    double nu = 0.0;      // Optional override Poisson's ratio

    bool hasMaterial() const { return E > 0 && nu > 0 && nu < 0.5; }
};

} // namespace KooRemapper
