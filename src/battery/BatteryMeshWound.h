#pragma once
// =============================================================
// BatteryMeshWound.h — Flat-wound (jellyroll) battery mesh
// =============================================================
// XZ cross-section: racetrack (stadium) shape
//   Upper/lower straight sections + elliptical arcs at ends
// Y-axis: winding axis (electrode height)
//
// Flat mode (woundFlat=true):
//   Each layer is an independent closed racetrack loop at fixed z-height.
//   Non-conformal: layers do not share nodes (contact-only interaction).
//   n_winds layers of [Al CC → Cathode → Sep → Anode → Cu CC] stacked in Z.
//
// Spiral mode (woundFlat=false):  [future]
//   Archimedean spiral path with continuously increasing radius.
//
// Units: mm, ton, s (LS-DYNA consistent)
// =============================================================

#include "BatteryConfig.h"
#include "BatteryMeshStacked.h"   // reuse MeshStats
#include <ostream>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// Generate complete wound-cell mesh into 'out'.
// Returns mesh statistics.
MeshStats writeMeshWound(std::ostream& out, const BatteryConfig& cfg);

} // namespace bat
