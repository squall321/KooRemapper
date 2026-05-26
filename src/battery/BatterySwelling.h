#pragma once
// =============================================================
// BatterySwelling.h — Intercalation swelling for battery cells
// =============================================================
// Two mechanisms:
//   1. writeSwellingStrains()  — *INITIAL_STRAIN_SOLID (post-processing only)
//   2. writeSwellingThermal()  — *MAT_ADD_THERMAL_EXPANSION + *INITIAL_TEMPERATURE
//      Drives actual structural deformation via thermal strain = alpha × DT.
//      Pattern from squeeze_assemble.cpp swelling implementation.
// =============================================================

#include "BatteryConfig.h"
#include <ostream>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// Per-element swelling record (built during mesh generation)
struct SwellElement {
    int    eid;          // element ID
    double cte;          // intercalation CTE (graphite or NMC)
};

// Compute eps_z for a given CTE and SOC
// Returns negative value (tensile expansion)
inline double swellEps(double cte, double soc) {
    return -(cte * soc);   // negative = tensile per P1 sign convention
}

// Collect all electrode element IDs from the stacked mesh
std::vector<SwellElement> collectSwellElements(
    const BatteryConfig& cfg,
    int nx, int ny);

// Write *INITIAL_STRAIN_SOLID blocks (legacy, post-processing only)
void writeSwellingStrains(std::ostream& out,
                          const std::vector<SwellElement>& elems,
                          double soc);

// Write *MAT_ADD_THERMAL_EXPANSION + *LOAD_THERMAL_VARIABLE (ramped)
// Drives actual structural swelling deformation with gradual temperature ramp.
// catPids/anoPids: electrode part IDs to apply thermal expansion
void writeSwellingThermal(std::ostream& out,
                          const BatteryConfig& cfg,
                          const std::vector<int>& catPids,
                          const std::vector<int>& anoPids);

} // namespace bat
