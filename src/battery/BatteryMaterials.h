#pragma once
// =============================================================
// BatteryMaterials.h — MAT_* card generation for battery cells
// =============================================================

#include "BatteryConfig.h"
#include <ostream>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// Write all section definitions (SHELL/SOLID/HOURGLASS) for stacked
void writeSections_Phase1(std::ostream& out,
                           const BatteryConfig& cfg);

// Write wound model sections (TSHELL electrodes, or SOLID when solidElectrode=true)
void writeSections_Wound(std::ostream& out, const BatteryConfig& cfg);

// Write all MAT_* cards for the given phase
// phase=1: MAT_JOHNSON_COOK + MAT_VISCOELASTIC + MAT_024 + MAT_RIGID + MAT_NULL
// phase=2: same + MAT_ELASTIC for electrodes + MAT_THERMAL_ISOTROPIC
void writeMaterials(std::ostream& out, const BatteryConfig& cfg);

} // namespace bat
