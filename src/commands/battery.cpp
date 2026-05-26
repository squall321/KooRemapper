#include "battery.h"
#include "battery/BatteryConfig.h"
#include "battery/BatteryIds.h"
#include "battery/BatteryWriter.h"
#include "battery/BatteryMaterials.h"
#include "battery/BatteryContacts.h"
#include "battery/BatteryControl.h"
#include "battery/BatteryMeshStacked.h"
#include "battery/BatteryMeshWound.h"
#include "battery/BatterySwelling.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <cstdio>
#include <cmath>
#include <algorithm>
#include <stdexcept>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/battery]]

using KooRemapper::ConsoleOutput;

// ─────────────────────────────────────────────────────────────
// YAML helpers (same pattern as hfdamp.cpp / implicit.cpp)
// ─────────────────────────────────────────────────────────────

static std::string bat_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static int bat_countIndent(const std::string& line) {
    int n = 0;
    while (n < (int)line.size() && line[n] == ' ') ++n;
    return n;
}

static double bat_toDouble(const std::string& s, double def = 0.0) {
    try { return std::stod(s); } catch (...) { return def; }
}

static int bat_toInt(const std::string& s, int def = 0) {
    try { return std::stoi(s); } catch (...) { return def; }
}

static bool bat_toBool(const std::string& s) {
    std::string lo = s;
    for (auto& c : lo) c = (char)tolower((unsigned char)c);
    return (lo == "true" || lo == "yes" || lo == "1");
}

// ─────────────────────────────────────────────────────────────
// Config parser
// ─────────────────────────────────────────────────────────────

BatteryConfig parseBatteryConfig(const std::string& yamlFile) {
    std::ifstream f(yamlFile);
    if (!f.is_open())
        throw std::runtime_error("Cannot open battery config: " + yamlFile);

    BatteryConfig cfg;
    std::string section;   // current top-level section (geometry, materials, etc.)
    std::string subsect;   // sub-section (e.g. "al_cc" inside materials)

    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string t = bat_trim(line);
        if (t.empty() || t[0] == '#') continue;
        // Strip inline comment
        {
            size_t hsh = t.find(" #");
            if (hsh != std::string::npos) t = bat_trim(t.substr(0, hsh));
        }

        int indent = bat_countIndent(line);

        // Top-level keys (indent=0)
        if (indent == 0) {
            section = "";
            subsect = "";
        }

        size_t colon = t.find(':');
        if (colon == std::string::npos) continue;
        std::string key = bat_trim(t.substr(0, colon));
        std::string val = bat_trim(t.substr(colon + 1));

        // Detect section headers (value empty = section start)
        if (val.empty()) {
            if (indent == 0) section = key;
            else if (indent == 2) subsect = key;
            continue;
        }

        // Dispatch by section
        if (indent == 0) {
            if      (key == "output")      cfg.output     = val;
            else if (key == "model_type")  cfg.modelType  = val;
            else if (key == "tier")        cfg.tier       = bat_toDouble(val);
            else if (key == "phase")       cfg.phase      = bat_toInt(val);
            else if (key == "mode")        cfg.mode       = val;
            else if (key == "displacement") cfg.displacement = bat_toDouble(val);
            else if (key == "ramp_time")   cfg.rampTime   = bat_toDouble(val);
            else if (key == "hold")        cfg.hold       = bat_toBool(val);
            else if (key == "plate_gap")   cfg.plateGap   = bat_toDouble(val);
            else if (key == "airbag_fill")  cfg.airbagFill  = bat_toBool(val);
            else if (key == "no_pcm")            cfg.noPcm            = bat_toBool(val);
            else if (key == "core_fill")         cfg.coreFill         = bat_toBool(val);
            else if (key == "no_impactor")       cfg.noImpactor       = bat_toBool(val);
            else if (key == "all_shell")          cfg.allShell         = bat_toBool(val);
            else if (key == "solid_electrode")    cfg.solidElectrode   = bat_toBool(val);
            else if (key == "solid_elform")       cfg.solidElform      = (int)bat_toDouble(val);
            else if (key == "pouch_expand_ratio") cfg.pouchExpandRatio = bat_toDouble(val);
            else if (key == "em_randles")         cfg.emRandles        = bat_toBool(val);
            else if (key == "merge_cc")           cfg.mergeCc          = bat_toBool(val);
            else if (key == "no_thermal")         cfg.noThermal        = bat_toBool(val);
            else if (key == "no_fixture")         cfg.noFixture        = bat_toBool(val);
            else if (key == "termination_time") cfg.terminationTime = bat_toDouble(val);
            else if (key == "timestep_safety")  cfg.tssfac          = bat_toDouble(val);
            else if (key == "dt2ms")            cfg.dt2ms           = bat_toDouble(val);
            else if (key == "output_interval")  cfg.outputInterval  = bat_toDouble(val);
            // Bare mode / DR parameters
            else if (key == "external_pressure") cfg.externalPressure = bat_toDouble(val);
            else if (key == "dr_tolerance")      cfg.drTolerance      = bat_toDouble(val);
            else if (key == "dr_endtim")         cfg.drEndtim         = bat_toDouble(val);
            else if (key == "dr_factor")         cfg.drFactor         = bat_toDouble(val);
            else if (key == "dr_nrcyck")         cfg.drNrcyck         = bat_toInt(val);
            else if (key == "pouch_gap")         cfg.pouchGap         = bat_toDouble(val);
            else if (key == "core_void")         cfg.coreVoid         = bat_toBool(val);
            else if (key == "target_thickness")  cfg.targetThickness  = bat_toDouble(val);
            else if (key == "layer_gap_frac")    cfg.layerGapFrac     = bat_toDouble(val);
            // Phase chaining
            else if (key == "use_dynain")  cfg.useDynain  = bat_toBool(val);
            else if (key == "dynain_file") cfg.dynainFile = val;
        }
        else if (section == "geometry" && indent == 2) {
            if      (key == "cell_width")   cfg.geo.cellWidth  = bat_toDouble(val);
            else if (key == "cell_height")  cfg.geo.cellHeight = bat_toDouble(val);
            else if (key == "n_unit_cells") cfg.geo.nUnitCells = bat_toInt(val);
            else if (key == "capacity")     cfg.geo.capacity   = bat_toDouble(val);
        }
        else if (section == "layer_thickness" && indent == 2) {
            if      (key == "al_cc")        cfg.thick.alCC     = bat_toDouble(val);
            else if (key == "cathode")      cfg.thick.cathode  = bat_toDouble(val);
            else if (key == "separator")    cfg.thick.separator= bat_toDouble(val);
            else if (key == "anode")        cfg.thick.anode    = bat_toDouble(val);
            else if (key == "cu_cc")        cfg.thick.cuCC     = bat_toDouble(val);
            else if (key == "sep_overhang") cfg.thick.sepOverhang = bat_toDouble(val);
            else if (key == "pouch")        cfg.thick.pouch    = bat_toDouble(val);
            else if (key == "electrolyte_buffer") cfg.thick.buffer = bat_toDouble(val);
        }
        else if (section == "indenter" && indent == 2) {
            if      (key == "radius")            cfg.indenter.radius          = bat_toDouble(val);
            else if (key == "height")            cfg.indenter.height          = bat_toDouble(val);
            else if (key == "offset")            cfg.indenter.offset          = bat_toDouble(val);
            else if (key == "cx")                cfg.indenter.cx              = bat_toDouble(val);
            else if (key == "cy")                cfg.indenter.cy              = bat_toDouble(val);
            else if (key == "n_circ")            cfg.indenter.nCirc           = bat_toInt(val);
            else if (key == "n_radial")          cfg.indenter.nRadial         = bat_toInt(val);
            else if (key == "type")              cfg.indenter.type            = val;
            else if (key == "length")            cfg.indenter.length          = bat_toDouble(val);
            else if (key == "nail_tip_length")   cfg.indenter.nailTipLength   = bat_toDouble(val);
            else if (key == "nail_tip_radius")   cfg.indenter.nailTipRadius   = bat_toDouble(val);
            else if (key == "nail_shaft_radius") cfg.indenter.nailShaftRadius = bat_toDouble(val);
        }
        else if (section == "ground_plate" && indent == 2) {
            if      (key == "thickness") cfg.plate.thickness = bat_toDouble(val);
            else if (key == "gap")       cfg.plate.gap       = bat_toDouble(val);
            else if (key == "margin")    cfg.plate.margin    = bat_toDouble(val);
            else if (key == "n_elem")    cfg.plate.nX = cfg.plate.nY = bat_toInt(val);
            else if (key == "n_x")       cfg.plate.nX        = bat_toInt(val);
            else if (key == "n_y")       cfg.plate.nY        = bat_toInt(val);
        }
        else if (section == "swelling" && indent == 2) {
            if      (key == "soc")           cfg.swelling.soc          = bat_toDouble(val);
            else if (key == "graphite_cte")  cfg.swelling.graphiteCte  = bat_toDouble(val);
            else if (key == "nmc_cte")       cfg.swelling.nmcCte       = bat_toDouble(val);
            else if (key == "sei_enabled")   cfg.swelling.seiEnabled   = bat_toBool(val);
        }
        else if (section == "contact" && indent == 2) {
            if      (key == "soft")         cfg.contact.soft        = bat_toInt(val);
            else if (key == "sofscl_base")  cfg.contact.sofscl_base = bat_toDouble(val);
            else if (key == "sofscl_power") cfg.contact.sofscl_pow  = bat_toDouble(val);
            else if (key == "sst_external") cfg.contact.sst_ext     = bat_toDouble(val);
            else if (key == "sst_self")     cfg.contact.sst_self    = bat_toDouble(val);
            else if (key == "depth")        cfg.contact.depth       = bat_toInt(val);
        }
        else if (section == "materials" && indent == 2) {
            subsect = key;  // al_cc / nmc_cathode / graphite_anode / etc.
        }
        else if (section == "materials" && indent == 4) {
            // Material sub-properties
            if (subsect == "al_cc") {
                if      (key == "name") cfg.matAl.name = val;
                else if (key == "E")   cfg.matAl.E   = bat_toDouble(val);
                else if (key == "nu")  cfg.matAl.nu  = bat_toDouble(val);
                else if (key == "rho") cfg.matAl.rho = bat_toDouble(val);
            } else if (subsect == "cu_cc") {
                if      (key == "name") cfg.matCu.name = val;
                else if (key == "E")   cfg.matCu.E   = bat_toDouble(val);
                else if (key == "nu")  cfg.matCu.nu  = bat_toDouble(val);
                else if (key == "rho") cfg.matCu.rho = bat_toDouble(val);
            } else if (subsect == "nmc_cathode") {
                if      (key == "name")  cfg.matCat.name   = val;
                else if (key == "rho")   cfg.matCat.rho    = bat_toDouble(val);
                else if (key == "G0")    cfg.matCat.G0     = bat_toDouble(val);
                else if (key == "G_inf") cfg.matCat.Ginf   = bat_toDouble(val);
                else if (key == "beta")  cfg.matCat.beta   = bat_toDouble(val);
                else if (key == "bulk")  cfg.matCat.bulk   = bat_toDouble(val);
                else if (key == "E_elastic")  cfg.matCat.E_elas  = bat_toDouble(val);
                else if (key == "nu_elastic") cfg.matCat.nu_elas = bat_toDouble(val);
                else if (key == "cte_intercalation") cfg.matCat.cte = bat_toDouble(val);
            } else if (subsect == "graphite_anode") {
                if      (key == "name")  cfg.matAno.name   = val;
                else if (key == "rho")   cfg.matAno.rho    = bat_toDouble(val);
                else if (key == "G0")    cfg.matAno.G0     = bat_toDouble(val);
                else if (key == "G_inf") cfg.matAno.Ginf   = bat_toDouble(val);
                else if (key == "beta")  cfg.matAno.beta   = bat_toDouble(val);
                else if (key == "bulk")  cfg.matAno.bulk   = bat_toDouble(val);
                else if (key == "E_elastic")  cfg.matAno.E_elas  = bat_toDouble(val);
                else if (key == "nu_elastic") cfg.matAno.nu_elas = bat_toDouble(val);
                else if (key == "cte_intercalation") cfg.matAno.cte = bat_toDouble(val);
            } else if (subsect == "separator") {
                if      (key == "name") cfg.matSep.name = val;
                else if (key == "rho")  cfg.matSep.rho  = bat_toDouble(val);
                else if (key == "E")    cfg.matSep.E    = bat_toDouble(val);
                else if (key == "nu")   cfg.matSep.nu   = bat_toDouble(val);
            } else if (subsect == "pouch") {
                if      (key == "name") cfg.matPouch.name = val;
                else if (key == "rho")  cfg.matPouch.rho  = bat_toDouble(val);
                else if (key == "E")    cfg.matPouch.E    = bat_toDouble(val);
                else if (key == "nu")   cfg.matPouch.nu   = bat_toDouble(val);
            }
        }
        else if (section == "pouch" && indent == 2) {
            if      (key == "r_fillet")       cfg.pouch.rFillet     = bat_toDouble(val);
            else if (key == "n_fillet_segs")  cfg.pouch.nFilletSegs = bat_toInt(val);
            else if (key == "buf_x")          cfg.pouch.bufX        = bat_toDouble(val);
            else if (key == "buf_y")          cfg.pouch.bufY        = bat_toDouble(val);
            else if (key == "dome_cap")       cfg.pouch.domeCap     = bat_toBool(val);
        }
        else if (section == "tabs" && indent == 2) {
            if      (key == "width")          cfg.tabs.width        = bat_toDouble(val);
            else if (key == "height")         cfg.tabs.height       = bat_toDouble(val);
            else if (key == "pos_x_center")   cfg.tabs.posXCenter   = bat_toDouble(val);
            else if (key == "neg_x_center")   cfg.tabs.negXCenter   = bat_toDouble(val);
        }
        else if (section == "pcm" && indent == 2) {
            if      (key == "width")          cfg.pcm.width         = bat_toDouble(val);
            else if (key == "height")         cfg.pcm.height        = bat_toDouble(val);
            else if (key == "thickness")      cfg.pcm.thickness     = bat_toDouble(val);
        }
        else if (section == "wound" && indent == 2) {
            if      (key == "flat")            cfg.woundFlat         = bat_toBool(val);
            else if (key == "flat_ratio")      cfg.woundFlatRatio    = bat_toDouble(val);
            else if (key == "n_winds")         cfg.woundNWinds       = (int)bat_toDouble(val);
            else if (key == "mandrel")         cfg.woundMandrel      = bat_toDouble(val);
            else if (key == "mesh_size_path")  cfg.woundMeshSizePath = bat_toDouble(val);
        }
        else if (section == "batch" && indent == 2) {
            // batch.tiers / model_types / phases parsed as simple scalar for now
            // (list parsing: "[1, 2]" → split by comma)
            if (key == "tiers" || key == "model_types" || key == "phases" || key == "phase_modes") {
                // strip brackets
                std::string v = val;
                if (!v.empty() && v.front() == '[') v = v.substr(1);
                if (!v.empty() && v.back()  == ']') v.pop_back();
                std::istringstream ss(v);
                std::string tok;
                while (std::getline(ss, tok, ',')) {
                    tok = bat_trim(tok);
                    if (tok.empty()) continue;
                    if (key == "tiers")             cfg.batch.tiers.push_back(bat_toDouble(tok));
                    else if (key == "phases")        cfg.batch.phases.push_back(bat_toInt(tok));
                    else if (key == "model_types")   cfg.batch.modelTypes.push_back(tok);
                    else if (key == "phase_modes")   cfg.batch.phaseModes.push_back(tok);
                }
            }
        }
    }

    // Phase 2 swelling: enable if phase==2
    if (cfg.phase == 2) {
        cfg.swelling.enabled = true;
    }

    // bare/swell mode: fixture-free DR equilibration mesh
    if (cfg.mode == "bare" || cfg.mode == "swell") {
        cfg.noFixture = true;
    }

    // swell mode: initial strain + DR — enable swelling
    if (cfg.mode == "swell") {
        cfg.swelling.enabled = true;
    }

    // no_fixture: implies no_pcm + no_impactor + no tabs
    if (cfg.noFixture) {
        cfg.noPcm      = true;
        cfg.noImpactor = true;
    }

    // n_unit_cells from capacity if given
    if (cfg.geo.capacity > 0.0) {
        double area_cm2 = (cfg.geo.cellWidth / 10.0) * (cfg.geo.cellHeight / 10.0);
        double capPerUC = cfg.geo.arealCap * area_cm2 * 2.0;
        cfg.geo.nUnitCells = std::max(1, (int)std::round(cfg.geo.capacity * 1000.0 / capPerUC));
    }

    // Auto-sizing: derive n_winds or n_unit_cells from target jellyroll thickness
    if (cfg.targetThickness > 0.0) {
        const auto& t = cfg.thick;
        if (cfg.modelType == "wound") {
            // wound unit cell: Al + cathode (1-side) + sep + anode (1-side) + Cu
            double uc = t.alCC + t.cathode + t.separator + t.anode + t.cuCC;
            if (uc > 0.0)
                cfg.woundNWinds = std::max(1, (int)std::round(cfg.targetThickness / uc));
        } else {
            // stacked unit cell: Al + 2×cathode + 2×sep + 2×anode + Cu (double-sided)
            double uc = t.alCC + 2.0*t.cathode + 2.0*t.separator + 2.0*t.anode + t.cuCC;
            if (uc > 0.0)
                cfg.geo.nUnitCells = std::max(1, (int)std::round(cfg.targetThickness / uc));
        }
    }

    return cfg;
}

// ─────────────────────────────────────────────────────────────
// Single K-file generator
// ─────────────────────────────────────────────────────────────

std::string generateBatteryKFile(const BatteryConfig& cfg,
                                  ConsoleOutput& console) {
    // Build output filename
    std::string phaseSuffix = (cfg.phase == 2) ? "_phase2" : "_phase1";
    std::string outPath = cfg.output + batteryTierSuffix(cfg.tier) + phaseSuffix + ".k";

    console.println("[battery] Generating: " + outPath);
    console.println("[battery]   model_type : " + cfg.modelType);
    {
        char buf[64];
        snprintf(buf, sizeof(buf), "%.1f", cfg.tier);
        console.println(std::string("[battery]   tier       : ") + buf);
        snprintf(buf, sizeof(buf), "%d", cfg.phase);
        console.println(std::string("[battery]   phase      : ") + buf);
        if (cfg.modelType == "wound") {
            snprintf(buf, sizeof(buf), "%d", cfg.woundNWinds);
            console.println(std::string("[battery]   n_winds    : ") + buf);
            if (cfg.targetThickness > 0.0) {
                const auto& t = cfg.thick;
                double uc = t.alCC + t.cathode + t.separator + t.anode + t.cuCC;
                snprintf(buf, sizeof(buf), "%.3f", uc * cfg.woundNWinds);
                console.println(std::string("[battery]   jelly_thk  : ") + buf + " mm");
            }
        } else {
            snprintf(buf, sizeof(buf), "%d", cfg.geo.nUnitCells);
            console.println(std::string("[battery]   n_uc       : ") + buf);
            if (cfg.targetThickness > 0.0) {
                const auto& t = cfg.thick;
                double uc = t.alCC + 2.0*t.cathode + 2.0*t.separator + 2.0*t.anode + t.cuCC;
                snprintf(buf, sizeof(buf), "%.3f", uc * cfg.geo.nUnitCells);
                console.println(std::string("[battery]   jelly_thk  : ") + buf + " mm");
            }
        }
    }

    // Compute mesh dimensions
    double meshSize = batteryMeshSize(cfg.tier);
    int nx = (int)std::round(cfg.geo.cellWidth  / meshSize);
    int ny = (int)std::round(cfg.geo.cellHeight / meshSize);
    if (nx < 1) nx = 1;
    if (ny < 1) ny = 1;

    // ── Wound model ──────────────────────────────────────────
    if (cfg.modelType == "wound") {
        std::ostringstream out;
        out << "$ KooRemapper battery — generated model\n"
            << "$ model_type      : wound\n"
            << "$ tier            : " << cfg.tier << "\n"
            << "$ phase           : " << cfg.phase << "\n"
            << "$ n_winds         : " << cfg.woundNWinds << "\n"
            << "$ solid_electrode : " << (cfg.solidElectrode ? "true" : "false") << "\n"
            << "$ airbag_fill     : " << (cfg.airbagFill     ? "true" : "false") << "\n"
            << "*KEYWORD\n";

        // Dynain restart: initial deformed geometry + stress/strain state
        if (cfg.useDynain && !cfg.dynainFile.empty()) {
            out << "$ ── Dynain: deformed initial positions + stress/strain state ──\n"
                << "*INCLUDE_DYNAIN\n"
                << cfg.dynainFile << "\n";
        }

        bat::writeSections_Wound(out, cfg);
        bat::writeMaterials(out, cfg);
        bat::MeshStats stats = bat::writeMeshWound(out, cfg);
        bat::writeControlCards(out, cfg);
        bat::writeBoundaryCards(out, cfg);
        bat::writeCurves(out, cfg);
        bat::writeDatabaseCards(out, cfg);

        // Swelling for wound: thermal expansion with ramped temperature
        if (cfg.mode == "swell" && cfg.swelling.enabled) {
            std::vector<int> catPids = {PID_W_CAT};
            std::vector<int> anoPids = {PID_W_ANO};
            bat::writeSwellingThermal(out, cfg, catPids, anoPids);
            console.println("[battery]   swelling: thermal expansion (wound)");
        }

        out << "*END\n";

        std::ofstream f(outPath);
        if (!f.is_open()) {
            console.error("[battery] Cannot write output: " + outPath);
            return "";
        }
        f << out.str();

        char sbuf[128];
        snprintf(sbuf, sizeof(sbuf),
                 "[battery] Done. Nodes=%d Shells=%d Solids=%d",
                 stats.nNodes, stats.nShells, stats.nSolids);
        console.println(sbuf);
        return outPath;
    }

    if (cfg.modelType != "stacked") {
        console.error("[battery] Unknown model_type: " + cfg.modelType +
                      " (supported: stacked, wound)");
        return "";
    }

    // ── Stacked model ─────────────────────────────────────────
    // Build K-file in memory
    std::ostringstream out;

    out << "$ KooRemapper battery — generated model\n"
        << "$ model_type : " << cfg.modelType << "\n"
        << "$ tier       : " << cfg.tier << "\n"
        << "$ phase      : " << cfg.phase << "\n"
        << "$ n_uc       : " << cfg.geo.nUnitCells << "\n"
        << "*KEYWORD\n";

    // Dynain restart: initial deformed geometry + stress/strain state
    if (cfg.useDynain && !cfg.dynainFile.empty()) {
        out << "$ ── Dynain: deformed initial positions + stress/strain state ──\n"
            << "*INCLUDE_DYNAIN\n"
            << cfg.dynainFile << "\n";
    }

    // 1. Sections + hourglass
    bat::writeSections_Phase1(out, cfg);

    // 2. Materials
    bat::writeMaterials(out, cfg);

    // 3. Mesh (nodes + elements + parts + sets)
    bat::MeshStats stats = bat::writeMeshStacked(out, cfg);

    // 4. Contacts
    std::vector<int> cellPids;   // populated inside writeContacts via SID_PART_CELL
    bat::writeContacts(out, cfg, cfg.geo.nUnitCells, cellPids);

    // 5. Control cards
    bat::writeControlCards(out, cfg);

    // 6. Boundary + curves
    bat::writeBoundaryCards(out, cfg);
    bat::writeCurves(out, cfg);

    // 7. Database
    bat::writeDatabaseCards(out, cfg);

    // 8. Swelling: Phase 2 uses INITIAL_STRAIN_SOLID (post-processing),
    //    swell mode uses MAT_ADD_THERMAL_EXPANSION (structural deformation)
    if (cfg.phase == 2 && cfg.swelling.enabled && !cfg.useDynain) {
        auto elems = bat::collectSwellElements(cfg, nx, ny);
        bat::writeSwellingStrains(out, elems, cfg.swelling.soc);

        char buf[64];
        snprintf(buf, sizeof(buf), "%zu", elems.size());
        console.println(std::string("[battery]   swelling elements : ") + buf);
    } else if (cfg.mode == "swell" && cfg.swelling.enabled) {
        // Thermal expansion approach: MAT_ADD_THERMAL_EXPANSION + LOAD_THERMAL_VARIABLE
        // Build PID lists for cathode and anode
        std::vector<int> catPids, anoPids;
        if (cfg.modelType == "stacked") {
            for (int uc = 0; uc < cfg.geo.nUnitCells; ++uc) {
                catPids.push_back(bat_pid_stacked(uc, LT_CAT));
                anoPids.push_back(bat_pid_stacked(uc, LT_ANO));
            }
        } else {
            catPids.push_back(PID_W_CAT);
            anoPids.push_back(PID_W_ANO);
        }
        bat::writeSwellingThermal(out, cfg, catPids, anoPids);

        auto elems = bat::collectSwellElements(cfg, nx, ny);
        char buf[64];
        snprintf(buf, sizeof(buf), "%zu", elems.size());
        console.println(std::string("[battery]   swelling elements : ") + buf);
    }

    out << "*END\n";

    // Write to file
    std::ofstream f(outPath);
    if (!f.is_open()) {
        console.error("[battery] Cannot write output: " + outPath);
        return "";
    }
    f << out.str();

    {
        char buf[128];
        snprintf(buf, sizeof(buf),
                 "[battery] Done. Nodes=%d Shells=%d Solids=%d TotalZ=%.4fmm",
                 stats.nNodes, stats.nShells, stats.nSolids, stats.totalZ);
        console.println(buf);
    }

    return outPath;
}

// ─────────────────────────────────────────────────────────────
// Batch generation
// ─────────────────────────────────────────────────────────────
static void generateBatch(const BatteryConfig& baseCfg,
                           ConsoleOutput& console) {
    const auto& batch = baseCfg.batch;

    std::vector<double> tiers    = batch.tiers.empty()
                                   ? std::vector<double>{baseCfg.tier}
                                   : batch.tiers;
    std::vector<std::string> mts = batch.modelTypes.empty()
                                   ? std::vector<std::string>{baseCfg.modelType}
                                   : batch.modelTypes;
    std::vector<int> phases      = batch.phases.empty()
                                   ? std::vector<int>{baseCfg.phase}
                                   : batch.phases;

    // When use_dynain=true and both phase 1 and 2 are in the list,
    // auto-compute the phase 1 dynain filename to inject into phase 2.
    bool autoChain = baseCfg.useDynain
                     && (std::find(phases.begin(), phases.end(), 1) != phases.end())
                     && (std::find(phases.begin(), phases.end(), 2) != phases.end());

    for (const auto& mt : mts) {
        for (double tier : tiers) {
            for (size_t pi = 0; pi < phases.size(); ++pi) {
                int ph = phases[pi];
                BatteryConfig cur = baseCfg;
                cur.modelType = mt;
                cur.tier      = tier;
                cur.phase     = ph;

                // Per-phase mode override (phase_modes: [swell, dent])
                if (pi < batch.phaseModes.size()) {
                    cur.mode = batch.phaseModes[pi];
                }

                // Enable swelling for phase 2 or swell mode
                cur.swelling.enabled = (ph == 2 || cur.mode == "swell");

                // Auto-chain: later phases get *INCLUDE_DYNAIN from the previous phase output
                if (autoChain && pi > 0 && cur.dynainFile.empty()) {
                    int prevPhase = phases[pi - 1];
                    cur.dynainFile = cur.output
                                   + batteryTierSuffix(tier)
                                   + "_phase" + std::to_string(prevPhase)
                                   + ".dynain";
                }

                generateBatteryKFile(cur, console);
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────
// runBattery entry point
// ─────────────────────────────────────────────────────────────

int runBattery(const std::string& yamlFile, ConsoleOutput& console) {
    BatteryConfig cfg;
    try {
        cfg = parseBatteryConfig(yamlFile);
    } catch (const std::exception& e) {
        console.error(e.what());
        return 1;
    }

    // Batch mode?
    bool isBatch = !cfg.batch.tiers.empty() ||
                   !cfg.batch.phases.empty() ||
                   !cfg.batch.modelTypes.empty();

    if (isBatch) {
        generateBatch(cfg, console);
    } else {
        std::string out = generateBatteryKFile(cfg, console);
        if (out.empty()) return 1;
    }

    return 0;
}
