#include "BatterySwelling.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"
#include <ostream>
#include <vector>
#include <set>
#include <cmath>
#include <cstdio>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// ─────────────────────────────────────────────────────────────
// collectSwellElements
//
// BatteryMeshStacked assigns element IDs sequentially:
//   1. Pouch bottom shells   (ny-1)*(nx-1) shells
//   2. Pouch top shells      (ny-1)*(nx-1) shells
//   3. Per UC (k=0..nUC-1):
//      a. Al CC shells       (ny-1)*(nx-1)
//      b. Cathode solids     (ny-1)*(nx-1)   ← swelling
//      c. Sep shells         (ny-1)*(nx-1)
//      d. Anode solids       (ny-1)*(nx-1)   ← swelling
//      e. Cu CC shells       (ny-1)*(nx-1)
//   4. Indenter solids
//   5. Ground plate solids
// ─────────────────────────────────────────────────────────────
std::vector<SwellElement> collectSwellElements(
    const BatteryConfig& cfg,
    int nx, int ny) {

    int nUC  = cfg.geo.nUnitCells;
    int nXY  = nx * ny;   // elements per flat layer (nx,ny are element counts)

    // Offset to reach UC k's elements:
    //   Pouch bottom + top = 2 * nXY shells  (nXY = nx*ny element count per layer)
    //   Each UC = 5 * nXY elements (3 shells + 2 solids)
    int eid = 1;
    eid += 2 * nXY;   // skip pouch shells

    std::vector<SwellElement> result;
    result.reserve(nUC * 2 * nXY);

    double catCte = cfg.matCat.cte;
    double anoCte = cfg.matAno.cte;
    // Override from swelling config if provided
    if (cfg.swelling.nmcCte > 0.0)     catCte = cfg.swelling.nmcCte;
    if (cfg.swelling.graphiteCte > 0.0) anoCte = cfg.swelling.graphiteCte;

    for (int uc = 0; uc < nUC; ++uc) {
        // a. Al CC shells (skip)
        eid += nXY;
        // b. Cathode solids (collect)
        for (int e = 0; e < nXY; ++e) {
            result.push_back({eid++, catCte});
        }
        // c. Sep shells (skip)
        eid += nXY;
        // d. Anode solids (collect)
        for (int e = 0; e < nXY; ++e) {
            result.push_back({eid++, anoCte});
        }
        // e. Cu CC shells (skip)
        eid += nXY;
    }

    return result;
}

// ─────────────────────────────────────────────────────────────
// writeSwellingStrains (legacy — post-processing only)
// Writes *INITIAL_STRAIN_SOLID for each electrode element.
// NOTE: This is post-processing only and does NOT drive deformation.
//       Crashes LS-DYNA R16.1 with large element counts.
//       Use writeSwellingThermal() instead for swell mode.
// ─────────────────────────────────────────────────────────────
void writeSwellingStrains(std::ostream& out,
                          const std::vector<SwellElement>& elems,
                          double soc) {
    if (elems.empty()) return;

    out << "$\n$ --- Phase 2: Intercalation Swelling Strains ---\n"
        << "$ eps_z = -(cte * soc),  eps_x = eps_y = 0\n"
        << "$ Sign: negative = tensile expansion (P1 convention)\n$\n";

    for (const auto& el : elems) {
        double eps_z = swellEps(el.cte, soc);
        writeInitialStrainSolid(out, el.eid,
                                0.0, 0.0, eps_z,   // exx eyy ezz
                                0.0, 0.0, 0.0);    // exy eyz exz
    }
}

// ─────────────────────────────────────────────────────────────
// writeSwellingThermal
//
// Drives intercalation swelling via thermal expansion mechanism:
//   *MAT_ADD_THERMAL_EXPANSION  alpha = CTE * SOC  (per electrode PID, z-only)
//   *LOAD_THERMAL_VARIABLE      T = 1.0 instant (DR finds equilibrium)
//
// Instant T=1.0 approach (same as squeeze_assemble pattern):
//   DR starts with full thermal strain applied → finds static equilibrium.
//   Requires elastic material (not viscoelastic) + VDC > 0 for stability.
// ─────────────────────────────────────────────────────────────
void writeSwellingThermal(std::ostream& out,
                          const BatteryConfig& cfg,
                          const std::vector<int>& catPids,
                          const std::vector<int>& anoPids) {
    double catCte = cfg.matCat.cte;
    double anoCte = cfg.matAno.cte;
    if (cfg.swelling.nmcCte > 0.0)     catCte = cfg.swelling.nmcCte;
    if (cfg.swelling.graphiteCte > 0.0) anoCte = cfg.swelling.graphiteCte;

    double soc = cfg.swelling.soc;
    double catAlpha = catCte * soc;
    double anoAlpha = anoCte * soc;

    writeComment(out, "Swelling via Thermal Expansion (CTE*SOC)");
    out << "$ Cathode alpha=" << catAlpha
        << "  Anode alpha=" << anoAlpha << "\n"
        << "$ T=1.0 instant — DR finds equilibrium of swelled state\n";

    // *MAT_ADD_THERMAL_EXPANSION per electrode PID
    // Isotropic: same alpha in all directions (physically correct for lattice expansion)
    // LCID=0, MULT=alpha → isotropic CTE
    // Isotropic: only PID, LCID=0, MULT=alpha needed.
    // Leave LCIDY/MULTY/LCIDZ/MULTZ blank (not zero) for isotropic materials.
    char buf[128];
    for (int pid : catPids) {
        out << "*MAT_ADD_THERMAL_EXPANSION\n"
            << "$#     pid      lcid      mult\n";
        std::snprintf(buf, sizeof(buf), "%10d%10d%10.6f\n",
                      pid, 0, catAlpha);
        out << buf;
    }
    for (int pid : anoPids) {
        out << "*MAT_ADD_THERMAL_EXPANSION\n"
            << "$#     pid      lcid      mult\n";
        std::snprintf(buf, sizeof(buf), "%10d%10d%10.6f\n",
                      pid, 0, anoAlpha);
        out << buf;
    }

    // Constant temperature curve: f(t) = 1.0 for all time
    std::vector<std::pair<double,double>> constPts = {
        {0.0,    1.0},
        {1.0e20, 1.0}
    };
    writeDefineCurve(out, LCID_SWELL_RAMP, "Swell_Temp_Const", constPts);

    // *LOAD_THERMAL_VARIABLE: T = TB + TS × f(t) = 0 + 1.0 × 1.0 = 1.0
    // LCID must reference a real curve (LCID=0 means no curve → f(t)=0)
    out << "*LOAD_THERMAL_VARIABLE\n"
        << "$#    nsid    nsidex     boxid\n";
    std::snprintf(buf, sizeof(buf), "%10d%10d%10d\n", 0, 0, 0);
    out << buf;
    out << "$#      ts        tb      lcid       tse       tbe     lcide     lcidr   lcidedr\n";
    std::snprintf(buf, sizeof(buf),
        "%10.4f%10.4f%10d%10.4f%10.4f%10d%10d%10d\n",
        1.0, 0.0, LCID_SWELL_RAMP, 0.0, 0.0, 0, LCID_SWELL_RAMP, 0);
    out << buf;
}

} // namespace bat
