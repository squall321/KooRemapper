#pragma once
// =============================================================
// BatteryMeshStacked.h — Stacked battery cell mesh generation
// =============================================================
// Generates nodes and elements for a prismatic stacked cell:
//   XY-plane: uniform grid (nx × ny)
//   Z-axis:   stacked unit cells  (Al CC / Cathode / Sep / Anode / Cu CC) × n_uc
//             wrapped by pouch top/bottom
//
// Node sharing:
//   UC-internal: SHELL and SOLID share boundary nodes directly
//   UC-boundary: Cu CC(uc) shares nodes with Al CC(uc+1)
//   Pouch ↔ jellyroll: independent nodes + TIED contact
//
// Z-plane layout (Phase 1, n_uc=N):
//   iz=0           : bottom pouch (z=0)
//   iz=1           : UC0 Al CC / Cathode-bot  (z = buffer)
//   iz=2           : UC0 Cathode-top / Sep / Anode-bot
//   iz=3           : UC0 Anode-top / Cu CC / UC1 Al CC
//   ...
//   iz=2*k+1       : UCk Al CC / Cathode-bot
//   iz=2*k+2       : UCk Cathode-top / Sep / Anode-bot
//   iz=2*(k+1)+1   : UCk Anode-top / Cu CC / UC(k+1) Al CC
//   ...
//   iz=2*N-1       : UC(N-1) Al CC / Cathode-bot
//   iz=2*N         : UC(N-1) Cathode-top / Sep / Anode-bot
//   iz=2*N+1       : UC(N-1) Anode-top / last Cu CC
//   iz=2*N+2       : top pouch (z = total)
// =============================================================

#include "BatteryConfig.h"
#include <ostream>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

struct MeshStats {
    int nNodes    = 0;
    int nShells   = 0;
    int nSolids   = 0;
    double totalZ = 0.0;   // mm, total cell thickness
};

// Generate complete stacked mesh into 'out'.
// Returns mesh statistics.
// Indenter and ground plate geometry also written.
// All SET_* and PART definitions written here too.
MeshStats writeMeshStacked(std::ostream& out, const BatteryConfig& cfg);

} // namespace bat
