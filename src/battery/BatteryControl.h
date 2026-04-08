#pragma once
// =============================================================
// BatteryControl.h — Control, boundary, curves, database cards
// =============================================================

#include "BatteryConfig.h"
#include <ostream>
#include <vector>

namespace bat {

// Write *CONTROL_* cards for the given phase/mode
void writeControlCards(std::ostream& out, const BatteryConfig& cfg);

// Write *BOUNDARY_SPC + *BOUNDARY_PRESCRIBED_MOTION cards
// nodeTop: Z-top nodes (for displacement BC)
// nodeGnd: ground plate nodes
// nodeInd: indenter nodes
void writeBoundaryCards(std::ostream& out, const BatteryConfig& cfg);

// Write *DEFINE_CURVE blocks for indenter displacement and stress-strain
void writeCurves(std::ostream& out, const BatteryConfig& cfg);

// Write *DATABASE_BINARY_D3PLOT + *DATABASE_GLSTAT + *DATABASE_RCFORC
void writeDatabaseCards(std::ostream& out, const BatteryConfig& cfg);

} // namespace bat
