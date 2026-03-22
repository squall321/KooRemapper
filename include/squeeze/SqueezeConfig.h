#pragma once

#include <vector>
#include <string>

namespace KooRemapper {

/**
 * Dynamic Relaxation options embedded in squeeze config.
 * If enabled, DR keywords are inserted into the output K-file.
 */
struct SqueezeRelaxConfig {
    bool enabled = false;
    int level = 2;               // 1(fast) ~ 5(max conservative)
    std::string mode = "explicit"; // "explicit" (IDRFLG=1) | "implicit" (IDRFLG=5)
    double drterm = 0.0;         // DR termination time (0 = convergence only)
    double endtime = -1.0;       // post-DR analysis endtime (-1 = omit CONTROL_TERMINATION)
    bool d3drlf = true;          // insert *DATABASE_BINARY_D3DRLF
    // per-param overrides (-1 = use level preset)
    double nrcyckOvr = -1.0;
    double drtolOvr  = -1.0;
    double drfctrOvr = -1.0;
    double tssfdrOvr = -1.0;
    double edttlOvr  = -1.0;
    int    irelalOvr = -1;
};

/**
 * Per-part squeeze configuration
 */
struct PartSqueezeConfig {
    int pid = 0;
    double eps_x = 0.0;  // X-direction strain (negative = compression)
    double eps_y = 0.0;  // Y-direction strain
    double eps_z = 0.0;  // Z-direction strain
    double swelling = 0.0; // Isotropic swelling via thermal expansion (e.g., 0.01 = 1%)

    bool hasSwelling() const { return swelling != 0.0; }
    bool hasSqueeze() const { return eps_x != 0.0 || eps_y != 0.0 || eps_z != 0.0; }
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
    SqueezeRelaxConfig relax;
    bool strainMode = false; // true = write *INITIAL_STRAIN_SOLID (no material needed)

    bool hasMaterial() const { return E > 0 && nu > 0 && nu < 0.5; }
};

} // namespace KooRemapper
