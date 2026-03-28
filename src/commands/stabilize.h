#pragma once
#include <string>
#include <vector>
#include <climits>

namespace KooRemapper { class ConsoleOutput; }

struct StabilizeConfig {
    std::string mode;           // "explicit"
    int level = 0;             // 0=manual, 1-12=preset
    bool confirmErosion = false;
    // time step / erosion
    double tssfac = -1;         // -1 = not set
    int erode = -1;
    // hourglass
    int ihq = -1;
    double qh = -1;
    // accuracy
    int osu = -1;
    int inn = -1;
    int esortSolid = -1;
    int esortShell = -1;
    // shell (irnxx: INT_MIN = not set; valid values: -1, -2)
    int bwc = -1;
    int miter = -1;
    int irnxx = INT_MIN;
    double wrpang = -1;
    // contact global Card 1
    int orien = -1;
    int shlthk = -1;
    int enmass = -1;
    int islchk = -1;
    // contact global Card 2
    double xpene = -1;
    int nsbcs = -1;
    // contact per-contact (Card A)
    int soft = -1;
    int sbopt = -1;
    int depth = -1;
    double maxpar = -1;
    // contact per-contact (Card C)
    int ignore_ = -1;
    // bulk viscosity (forced override)
    double bulkQ1 = -1;
    double bulkQ2 = -1;
    // energy
    int hgen = -1;
    int rwen = -1;
    int slnten = -1;
    int rylen = -1;
};

// Defined in main.cpp (bridge to anonymous-namespace ct_* helpers)
// Applies per-contact Card A/C options; appends messages to msgs.
void stab_applyPerContact(std::vector<std::string>& lines,
                           const StabilizeConfig& cfg,
                           std::vector<std::string>& msgs);

// Defined in stabilize.cpp
std::vector<std::string> stab_applyExplicit(std::vector<std::string>& lines,
                                              const StabilizeConfig& cfg);

int runStabilize(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
