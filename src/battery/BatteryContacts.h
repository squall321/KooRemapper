#pragma once
// =============================================================
// BatteryContacts.h — Contact card generation (SOFT=1)
// =============================================================

#include "BatteryConfig.h"
#include <ostream>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// Write all contact definitions for a stacked cell model.
// Includes:
//   - CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (indenter→cell)
//   - CONTACT_AUTOMATIC_SINGLE_SURFACE     (cell self-contact)
//   - CONTACT_TIED_SURFACE_TO_SURFACE      (layer bonding, Phase 1)
//
// nUnitCells: number of unit cells (for TIED contacts)
// phase:      1 = SOLID+SHELL → TIED contacts needed
//             2 = TSHELL nodes shared → no TIED between jellyroll layers
//             (Phase 2 still needs TIED at pouch ↔ jellyroll boundary)
void writeContacts(std::ostream& out, const BatteryConfig& cfg,
                   int nUnitCells,
                   const std::vector<int>& cellPids);

} // namespace bat
