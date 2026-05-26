#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/relax]]

namespace KooRemapper { class ConsoleOutput; }

// Generate *CONTROL_DYNAMIC_RELAXATION card string (also used by assemble command)
std::string relax_generateCards(int level, const std::string& mode,
    double drterm, double nrcyckOvr, double drtolOvr, double drfctrOvr,
    double tssfdrOvr, int irelalOvr, double edttlOvr, bool d3drlf);

int runRelax(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
