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
#include "util/YamlComment.h"

#include <map>
#include <set>
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
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

    BatteryConfig cfg;
    std::string section;   // current top-level section (geometry, materials, etc.)
    std::string subsect;   // sub-section (e.g. "al_cc" inside materials)

    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string t = bat_trim(line);
        if (t.empty() || t[0] == '#') continue;

        int indent = bat_countIndent(line);

        // Top-level keys (indent=0)
        if (indent == 0) {
            section = "";
            subsect = "";
        }

        size_t colon = t.find(':');
        if (colon == std::string::npos) continue;
        std::string key = bat_trim(t.substr(0, colon));
        // 예전엔 줄 단위로 ' #' 앞을 잘라 탭 앞 주석('stacked\t# note')은 값에 남고 따옴표 안 # 는 잘렸다
        std::string val = bat_trim(KooRemapper::yamlStripComment(t.substr(colon + 1)));

        // Detect section headers (value empty = section start)
        if (val.empty()) {
            if (indent == 0) section = key;
            else if (indent == 2) subsect = key;
            continue;
        }
        if (val.size() >= 2 && (val.front() == '"' || val.front() == '\'') && val.back() == val.front())
            val = val.substr(1, val.size() - 2);

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

// 덱 이름 규칙 하나 — 쓰기 관문(assemble 의 battery 처리)이 쓰기 전에 같은 이름으로 견준다(2026-11-07)
std::string batteryKFilePath(const BatteryConfig& cfg) {
    const std::string phaseSuffix = (cfg.phase == 2) ? "_phase2" : "_phase1";
    const std::string typePart = cfg.nameWithModelType ? "_" + cfg.modelType : std::string();
    return cfg.output + typePart + batteryTierSuffix(cfg.tier) + phaseSuffix + ".k";
}

std::string batteryDynainSkipWarning(const BatteryConfig& cfg) {
    if (!cfg.useDynain || !cfg.dynainFile.empty()) return "";
    return "[battery] use_dynain: true 인데 dynain_file 이 비어 「" + batteryKFilePath(cfg) +
           "」 에 *INCLUDE_DYNAIN 을 쓰지 않았다 — 앞 단계 실행의 dynain 이름을 dynain_file 에 적어라(이름을 스스로 짓는 것은 "
           "batch.phases 에 1 과 2 가 다 있을 때 뒤 phase 뿐이다)";
}

// 배터리 덱 글자를 메모리에 짓는다 — 파일은 쓰지 않는다(2026-11-08 · assemble 이 번호를 옮긴 뒤 쓴다). `what` 은 「Generating:」
// 줄의 이름(쓸 경로 · 주 덱에 펼친다는 말), 「Done. …」 줄은 `done` 에 둔다(부르는 쪽이 쓴 뒤에 찍는다). 모르는 model_type 이면 false
static bool buildBatteryDeck(const BatteryConfig& cfg, ConsoleOutput& console, const std::string& what,
                             std::string& text, std::string& done) {
    console.println("[battery] Generating: " + what);
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
        text = out.str();

        char sbuf[128];
        snprintf(sbuf, sizeof(sbuf),
                 "[battery] Done. Nodes=%d Shells=%d Solids=%d",
                 stats.nNodes, stats.nShells, stats.nSolids);
        done = sbuf;
        return true;
    }

    if (cfg.modelType != "stacked") {
        console.error("[battery] Unknown model_type: " + cfg.modelType +
                      " (supported: stacked, wound)");
        return false;
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
    text = out.str();

    {
        char buf[128];
        snprintf(buf, sizeof(buf),
                 "[battery] Done. Nodes=%d Shells=%d Solids=%d TotalZ=%.4fmm",
                 stats.nNodes, stats.nShells, stats.nSolids, stats.totalZ);
        done = buf;
    }
    return true;
}

bool writeBatteryKFileText(const std::string& path, const std::string& text, ConsoleOutput& console) {
    std::ofstream f(path);
    if (!f.is_open()) {
        console.error("[battery] Cannot write output: " + path);
        return false;
    }
    f << text;
    f.close();
    if (f.fail()) {
        console.error("[battery] Cannot write output: " + path);
        return false;
    }
    return true;
}

std::string generateBatteryKFile(const BatteryConfig& cfg,
                                  ConsoleOutput& console) {
    const std::string outPath = batteryKFilePath(cfg);
    std::string text, done;
    if (!buildBatteryDeck(cfg, console, outPath, text, done)) return "";
    if (!writeBatteryKFileText(outPath, text, console)) return "";
    console.println(done);
    return outPath;
}

bool buildBatteryKFileText(const BatteryConfig& cfg, ConsoleOutput& console, const std::string& what, std::string& text) {
    std::string done;
    if (!buildBatteryDeck(cfg, console, what, text, done)) return false;
    console.println(done);
    return true;
}

// ─────────────────────────────────────────────────────────────
// Batch generation
// ─────────────────────────────────────────────────────────────
// ★두 조합이 같은 파일 이름이면 쓰기 전에 거절한다(2026-11-07) — 이름(`<output><tier>_phase{1|2}.k`)에 모델 종류가 없고 tier 는
//   다섯 칸으로 묶이고 phase 2 가 아니면 모두 _phase1 이라, 예전엔 [stacked, wound] · tiers [0, 0.2] · phases [1, 3] 이 앞 조합의
//   덱을 조용히 덮고 rc 0 이었다. 이름 규칙(문서에 적힌 것)은 바꾸지 않는다.
static int generateBatch(const BatteryConfig& baseCfg,
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
    // ★모델 종류가 둘 이상이면 종류를 이름에 넣는다(2026-11-07 · 사용자 결정) — 예전엔 이름에 종류가 없어 [stacked, wound] 가
    //   같은 덱에 차례로 썼다(앞 커밋부터는 거절). 하나뿐이면 문서의 예전 이름 그대로
    const bool typeInName = std::set<std::string>(mts.begin(), mts.end()).size() >= 2;

    std::vector<BatteryConfig> combos;
    std::vector<bool> chainHead;   // 자동 사슬의 첫 phase — dynain 을 받지 않는 것이 맞다(경고하지 않는다)
    for (const auto& mt : mts) {
        for (double tier : tiers) {
            for (size_t pi = 0; pi < phases.size(); ++pi) {
                int ph = phases[pi];
                BatteryConfig cur = baseCfg;
                cur.modelType = mt;
                cur.tier      = tier;
                cur.phase     = ph;
                cur.nameWithModelType = typeInName;

                // Per-phase mode override (phase_modes: [swell, dent])
                if (pi < batch.phaseModes.size()) {
                    cur.mode = batch.phaseModes[pi];
                }

                // Enable swelling for phase 2 or swell mode
                cur.swelling.enabled = (ph == 2 || cur.mode == "swell");

                // Auto-chain: later phases get *INCLUDE_DYNAIN from the previous phase output
                if (autoChain && pi > 0 && cur.dynainFile.empty()) {
                    int prevPhase = phases[pi - 1];
                    // ★*INCLUDE_DYNAIN 은 산출 덱 옆에서 솔버가 찾을 이름이다(§43.1 · 2026-11-07) — 앞 phase 덱과 같은 폴더라 접두사의
                    //   파일 이름 부분만 쓴다. 예전엔 YAML 폴더로 푼 접두사를 통째로 붙여 `battery cfg/b.yaml` 의 phase 2 덱이
                    //   cfg/bt_tier0_phase1.dynain(덱 폴더 기준이면 cfg/cfg/…)을, 절대 경로 설정이면 그 절대 경로를 적었다
                    const size_t cut = cur.output.find_last_of("/\\");
                    cur.dynainFile = (cut == std::string::npos ? cur.output : cur.output.substr(cut + 1))
                                   + (typeInName ? "_" + mt : std::string())   // 앞 phase 덱 이름과 같은 규칙
                                   + batteryTierSuffix(tier)
                                   + "_phase" + std::to_string(prevPhase)
                                   + ".dynain";
                }

                combos.push_back(cur);
                chainHead.push_back(autoChain && pi == 0);
            }
        }
    }

    auto label = [](const BatteryConfig& c) {
        char tierBuf[32];
        snprintf(tierBuf, sizeof(tierBuf), "%g", c.tier);
        return "model_type " + c.modelType + " · tier " + tierBuf + " · phase " + std::to_string(c.phase);
    };
    std::map<std::string, std::vector<std::string>> byName;   // 파일 이름 → 그 이름을 쓸 조합
    for (const auto& c : combos) byName[batteryKFilePath(c)].push_back(label(c));
    bool clash = false;
    for (const auto& [name, who] : byName) {
        if (who.size() < 2) continue;
        if (!clash) console.error("[battery] batch 의 두 조합이 같은 파일 이름에 쓴다 — 하나가 다른 하나를 덮는다(아무 파일도 쓰지 않았다)");
        clash = true;
        std::string list;
        for (const auto& w : who) list += (list.empty() ? "" : " / ") + w;
        console.error("[battery]   " + name + " ← " + list);
    }
    if (clash) {
        console.info("[battery] 이름은 <output><tier>_phase{1|2}.k 다(모델 종류가 둘 이상이면 <output>_<model_type><tier>_phase{1|2}.k · "
                     "tier 는 _tier-1 · _tier0 · _tier0_5 · _tier1 · _tier2 · phase 2 가 아니면 _phase1) — 겹치는 조합은 output 을 달리 해 "
                     "따로 돌려라");
        return 1;
    }
    // ★조합 하나라도 못 만들면 rc 1 과 못 만든 조합의 요약(2026-11-07) — 예전엔 실패를 버리고 rc 0 이었다(자동화는 rc 만 본다).
    //   나머지 조합은 끝까지 만든다
    std::vector<std::string> failed;
    for (size_t ci = 0; ci < combos.size(); ++ci) {
        const auto& c = combos[ci];
        if (generateBatteryKFile(c, console).empty()) {
            failed.push_back(label(c) + " → " + batteryKFilePath(c));
            continue;
        }
        // ★dynain 을 바란 조합이 그것을 받지 못하면 알린다(2026-11-08) — 예전엔 말없이 *INCLUDE_DYNAIN 이 빠졌다
        const std::string warn = chainHead[ci] ? std::string() : batteryDynainSkipWarning(c);
        if (!warn.empty()) console.warning(warn);
    }
    if (!failed.empty()) {
        console.error("[battery] batch 의 조합 " + std::to_string(combos.size()) + "개 가운데 " + std::to_string(failed.size()) +
                      "개를 만들지 못했다(까닭은 위 [ERROR] 다)");
        for (const auto& f : failed) console.error("[battery]   " + f);
        return 1;
    }
    return 0;
}

// ─────────────────────────────────────────────────────────────
// runBattery entry point
// ─────────────────────────────────────────────────────────────

int runBattery(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("battery", tabLine));
            return 1;
        }
    }
    BatteryConfig cfg;
    try {
        cfg = parseBatteryConfig(yamlFile);
    } catch (const std::exception& e) {
        console.error(e.what());
        return 1;
    }

    // YAML 안의 상대 경로 = 그 YAML 폴더 기준 (§3.1(a), 다른 op 과 같은 규칙).
    // 예전엔 battery 만 작업 폴더 기준이라 'battery cfg/bat.yaml' 이 산출 덱을 작업 폴더에 떨궜다.
    {
        std::string configDir;
        size_t lastSlash = yamlFile.find_last_of("/\\");
        if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);
        cfg.output     = KooRemapper::yamlResolvePath(configDir, cfg.output);
        // dynain_file 은 경로 해석 대상이 아니다 — KooRemapper 가 이 파일을 열지 않고
        // *INCLUDE_DYNAIN 다음 줄에 적힌 문자열을 그대로 찍는다. 솔버는 그 줄을 덱이
        // 있는 폴더 기준으로 읽으므로 configDir 을 붙이면 include 가 어긋난다.
    }

    // Batch mode?
    bool isBatch = !cfg.batch.tiers.empty() ||
                   !cfg.batch.phases.empty() ||
                   !cfg.batch.modelTypes.empty();

    if (isBatch) {
        if (generateBatch(cfg, console) != 0) return 1;
    } else {
        std::string out = generateBatteryKFile(cfg, console);
        if (out.empty()) return 1;
        // ★use_dynain: true 인데 dynain_file 이 비면 *INCLUDE_DYNAIN 이 빠진다 — 알린다(2026-11-08 · 예전엔 말없이)
        const std::string warn = batteryDynainSkipWarning(cfg);
        if (!warn.empty()) console.warning(warn);
    }

    return 0;
}
