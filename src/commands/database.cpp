#include "database.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <set>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstdio>
#include <cctype>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/database]]

using KooRemapper::ConsoleOutput;

// ---------------------------------------------------------------------------
// Database keyword definitions
// ---------------------------------------------------------------------------

namespace {

struct DbKeywordDef {
    const char* name;
    const char* keyword;
    const char* comment;
    const char* role;
    bool isBinary;
};

// ASCII databases (Card 1: dt, binary, lcur, ioopt)
const DbKeywordDef DB_ASCII[] = {
    {"glstat",  "*DATABASE_GLSTAT",  "$#      dt    binary      lcur     ioopt",
     "Global statistics (energies, timestep, velocities)", false},
    {"matsum",  "*DATABASE_MATSUM",  "$#      dt    binary      lcur     ioopt",
     "Material energies per part", false},
    {"nodout",  "*DATABASE_NODOUT",  "$#      dt    binary      lcur     ioopt",
     "Nodal point output (disp/vel/acc at history nodes)", false},
    {"elout",   "*DATABASE_ELOUT",   "$#      dt    binary      lcur     ioopt",
     "Element output (stress/strain at history elements)", false},
    {"rcforc",  "*DATABASE_RCFORC",  "$#      dt    binary      lcur     ioopt",
     "Resultant contact interface forces", false},
    {"sleout",  "*DATABASE_SLEOUT",  "$#      dt    binary      lcur     ioopt",
     "Sliding interface energy", false},
    {"spcforc", "*DATABASE_SPCFORC", "$#      dt    binary      lcur     ioopt",
     "SPC reaction forces", false},
    {"nodfor",  "*DATABASE_NODFOR",  "$#      dt    binary      lcur     ioopt",
     "Nodal force groups", false},
    {"rwforc",  "*DATABASE_RWFORC",  "$#      dt    binary      lcur     ioopt",
     "Rigid wall forces", false},
    {"secforc", "*DATABASE_SECFORC", "$#      dt    binary      lcur     ioopt",
     "Cross-section forces", false},
    {"jntforc", "*DATABASE_JNTFORC", "$#      dt    binary      lcur     ioopt",
     "Joint forces", false},
    {"bndout",  "*DATABASE_BNDOUT",  "$#      dt    binary      lcur     ioopt",
     "Boundary condition output", false},
    {"abstat",  "*DATABASE_ABSTAT",  "$#      dt    binary      lcur     ioopt",
     "Airbag statistics", false},
    {"swforc",  "*DATABASE_SWFORC",  "$#      dt    binary      lcur     ioopt",
     "Spot weld/rivet forces", false},
    {"ssstat",  "*DATABASE_SSSTAT",  "$#      dt    binary      lcur     ioopt",
     "Subsystem statistics", false},
    {"deforc",  "*DATABASE_DEFORC",  "$#      dt    binary      lcur     ioopt",
     "Discrete element forces", false},
    {"disbout", "*DATABASE_DISBOUT", "$#      dt    binary      lcur     ioopt",
     "Displacement output (binary)", false},
    {"ncforc",  "*DATABASE_NCFORC",  "$#      dt    binary      lcur     ioopt",
     "Nodal contact forces", false},
    {"tprint",  "*DATABASE_TPRINT",  "$#      dt    binary      lcur     ioopt",
     "Thermal print interval", false},
    {"massout", "*DATABASE_MASSOUT", "$#      dt    binary      lcur     ioopt",
     "Added mass output", false},
};
const int DB_ASCII_COUNT = (int)(sizeof(DB_ASCII) / sizeof(DB_ASCII[0]));

// Binary databases (Card 1: dt, lcdt, beam, npltc, psetid)
const DbKeywordDef DB_BINARY[] = {
    {"d3plot",  "*DATABASE_BINARY_D3PLOT",
     "$#      dt      lcdt      beam     npltc    psetid",
     "d3plot output (full state)", true},
    {"d3thdt",  "*DATABASE_BINARY_D3THDT",
     "$#      dt      lcdt      beam     npltc    psetid",
     "d3thdt time history output", true},
    {"d3dump",  "*DATABASE_BINARY_D3DUMP",
     "$#      dt      lcdt      beam     npltc    psetid",
     "Restart dump files", true},
    {"runrsf",  "*DATABASE_BINARY_RUNRSF",
     "$#      dt      lcdt      beam     npltc    psetid",
     "Running restart files", true},
    {"intfor",  "*DATABASE_BINARY_INTFOR",
     "$#      dt      lcdt      beam     npltc    psetid",
     "Interface force file", true},
    {"d3drlf",  "*DATABASE_BINARY_D3DRLF",
     "$#      dt      lcdt      beam     npltc    psetid",
     "Dynamic relaxation output", true},
};
const int DB_BINARY_COUNT = (int)(sizeof(DB_BINARY) / sizeof(DB_BINARY[0]));

struct DbPreset {
    const char* name;
    const char* description;
    std::vector<std::string> ascii;
    std::vector<std::string> binary;
    bool extentBinary;
};

std::vector<DbPreset> db_getPresets() {
    std::vector<DbPreset> presets;
    presets.push_back({"all", "Maximum output for comprehensive analysis",
        {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","nodfor",
         "rwforc","secforc","jntforc","bndout","abstat","swforc","ssstat","deforc",
         "disbout","ncforc","tprint","massout"},
        {"d3plot","d3thdt","d3dump","runrsf"}, true});
    presets.push_back({"drop", "Drop test analysis",
        {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","rwforc",
         "nodfor","secforc","bndout","ncforc"},
        {"d3plot","d3thdt","d3dump"}, true});
    presets.push_back({"crash", "Crash / impact analysis",
        {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","rwforc",
         "nodfor","secforc","swforc","ncforc","abstat"},
        {"d3plot","d3thdt","d3dump"}, true});
    presets.push_back({"static", "Static / implicit analysis",
        {"glstat","matsum","nodout","elout","spcforc","nodfor","bndout","secforc"},
        {"d3plot","d3thdt"}, true});
    presets.push_back({"thermal", "Thermal analysis",
        {"glstat","matsum","nodout","elout","spcforc","tprint","bndout"},
        {"d3plot","d3thdt"}, true});
    presets.push_back({"forming", "Metal forming analysis",
        {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","nodfor",
         "secforc","ncforc","swforc"},
        {"d3plot","d3thdt","d3dump"}, true});
    presets.push_back({"modal", "Modal / eigenvalue analysis",
        {"glstat","matsum","nodout","elout","spcforc"},
        {"d3plot"}, false});
    presets.push_back({"minimal", "Minimal essential output",
        {"glstat","matsum"}, {"d3plot"}, false});
    return presets;
}

std::string db_buildExtentBinary(int neiph, int neips, int maxint,
                                  int strflg, int sigflg, int epsflg,
                                  int rltflg, int engflg, int cmpflg) {
    std::stringstream ss;
    ss << "*DATABASE_EXTENT_BINARY\n";
    ss << "$#   neiph     neips    maxint    strflg    sigflg    epsflg    rltflg    engflg\n";
    char buf[256];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             neiph, neips, maxint, strflg, sigflg, epsflg, rltflg, engflg);
    ss << buf;
    ss << "$#  cmpflg    ieverp    beamip     dcomp      shge     stssz    n3thdt   ialemat\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
             cmpflg, 0, 0, 1, 1, 0, 0, 0);
    ss << buf;
    return ss.str();
}

} // anonymous namespace

// ---------------------------------------------------------------------------
// runDatabase
// ---------------------------------------------------------------------------

int runDatabase(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    {
        size_t sp = yamlFile.find_last_of("/\\");
        if (sp != std::string::npos) configDir = yamlFile.substr(0, sp + 1);
    }

    std::string modelPath, outputPath;
    std::string preset;
    double dt = 0.001;
    double dt_plot = 0.0;
    double dt_thdt = 0.0;
    double dt_dump = 0.0;

    std::set<std::string> enabledAscii;
    std::set<std::string> enabledBinary;
    bool extentBinary = false;
    bool hasIndividual = false;

    int neiph = 0, neips = 0, maxint = 3;
    int strflg = 1, sigflg = 1, epsflg = 1, rltflg = 1, engflg = 1, cmpflg = 0;

    std::string line;
    enum class Section { NONE, ASCII, BINARY, EXTENT };
    Section section = Section::NONE;

    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string trimmed = line;
        size_t s = trimmed.find_first_not_of(" \t");
        if (s == std::string::npos) continue;
        trimmed = trimmed.substr(s);
        if (trimmed.empty() || trimmed[0] == '#') continue;

        int indent = (int)s;

        if (indent == 0) {
            if (trimmed.find("ascii:") == 0) { section = Section::ASCII; continue; }
            if (trimmed.find("binary:") == 0) { section = Section::BINARY; continue; }
            if (trimmed.find("extent:") == 0) { section = Section::EXTENT; continue; }
            section = Section::NONE;
        }

        size_t cp = trimmed.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trimmed.substr(0, cp);
        std::string val = trimmed.substr(cp + 1);
        size_t vs = val.find_first_not_of(" \t\"'");
        size_t ve = val.find_last_not_of(" \t\"'");
        if (vs != std::string::npos) val = val.substr(vs, ve - vs + 1);
        else val = "";

        if (section == Section::NONE) {
            if (key == "model") {
                modelPath = val;
                if (!configDir.empty() && modelPath.find('/') == std::string::npos && modelPath.find('\\') == std::string::npos)
                    modelPath = configDir + modelPath;
            } else if (key == "output") {
                outputPath = val;
                if (!configDir.empty() && outputPath.find('/') == std::string::npos && outputPath.find('\\') == std::string::npos)
                    outputPath = configDir + outputPath;
            } else if (key == "preset") preset = val;
            else if (key == "dt")      try { dt      = std::stod(val); } catch (...) {}
            else if (key == "dt_plot") try { dt_plot = std::stod(val); } catch (...) {}
            else if (key == "dt_thdt") try { dt_thdt = std::stod(val); } catch (...) {}
            else if (key == "dt_dump") try { dt_dump = std::stod(val); } catch (...) {}
        } else if (section == Section::ASCII) {
            hasIndividual = true;
            if (val == "true" || val == "1" || val == "on") enabledAscii.insert(key);
        } else if (section == Section::BINARY) {
            hasIndividual = true;
            if (val == "true" || val == "1" || val == "on") enabledBinary.insert(key);
        } else if (section == Section::EXTENT) {
            extentBinary = true;
            try {
                if      (key == "neiph")  neiph  = std::stoi(val);
                else if (key == "neips")  neips  = std::stoi(val);
                else if (key == "maxint") maxint = std::stoi(val);
                else if (key == "strflg") strflg = std::stoi(val);
                else if (key == "sigflg") sigflg = std::stoi(val);
                else if (key == "epsflg") epsflg = std::stoi(val);
                else if (key == "rltflg") rltflg = std::stoi(val);
                else if (key == "engflg") engflg = std::stoi(val);
                else if (key == "cmpflg") cmpflg = std::stoi(val);
            } catch (...) {}
        }
    }
    f.close();

    if (modelPath.empty() || outputPath.empty()) {
        console.error("model and output are required");
        return 1;
    }

    if (!hasIndividual && !preset.empty()) {
        auto presets = db_getPresets();
        bool found = false;
        for (const auto& p : presets) {
            if (preset == p.name) {
                for (const auto& a : p.ascii) enabledAscii.insert(a);
                for (const auto& b : p.binary) enabledBinary.insert(b);
                if (p.extentBinary) extentBinary = true;
                found = true;
                console.info("Preset: " + std::string(p.name) + " (" + p.description + ")");
                break;
            }
        }
        if (!found) {
            console.error("Unknown preset: " + preset);
            console.info("Available: all, drop, crash, static, thermal, forming, modal, minimal");
            return 1;
        }
    } else if (!hasIndividual && preset.empty()) {
        preset = "all";
        auto presets = db_getPresets();
        for (const auto& p : presets) {
            if (preset == p.name) {
                for (const auto& a : p.ascii) enabledAscii.insert(a);
                for (const auto& b : p.binary) enabledBinary.insert(b);
                if (p.extentBinary) extentBinary = true;
                console.info("Preset: all (default — maximum output)");
                break;
            }
        }
    }

    if (dt_plot <= 0) dt_plot = dt * 10.0;
    if (dt_thdt <= 0) dt_thdt = dt;
    if (dt_dump <= 0) dt_dump = dt_plot * 10.0;

    console.info("Reading model: " + modelPath);
    std::ifstream modelFile(modelPath);
    if (!modelFile.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }

    std::vector<std::string> rawLines;
    {
        std::string ln;
        while (std::getline(modelFile, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            rawLines.push_back(ln);
        }
    }
    modelFile.close();

    std::set<std::string> existingKeywords;
    for (const auto& ln : rawLines) {
        std::string up = ln;
        for (auto& c : up) c = (char)toupper((unsigned char)c);
        size_t s2 = up.find_first_not_of(" \t");
        if (s2 != std::string::npos) up = up.substr(s2);
        if (up.find("*DATABASE_") == 0) {
            std::string kw = up;
            size_t e2 = kw.find_first_of(" \t\r\n");
            if (e2 != std::string::npos) kw = kw.substr(0, e2);
            existingKeywords.insert(kw);
        }
    }

    if (!existingKeywords.empty()) {
        console.info("Existing DATABASE keywords found: " + std::to_string(existingKeywords.size()));
        for (const auto& kw : existingKeywords) console.println("  " + kw);
    }

    std::string insertBlock;
    int insertedCount = 0;
    int skippedCount = 0;

    insertBlock += "$\n";
    insertBlock += "$ === DATABASE OUTPUT CONTROL (auto-generated by KooRemapper) ===\n";
    insertBlock += "$\n";

    char buf[256];
    for (int i = 0; i < DB_ASCII_COUNT; ++i) {
        const auto& def = DB_ASCII[i];
        if (enabledAscii.find(def.name) == enabledAscii.end()) continue;
        std::string kwUp = def.keyword;
        for (auto& c : kwUp) c = (char)toupper((unsigned char)c);
        if (existingKeywords.count(kwUp)) {
            console.println("  [SKIP] " + std::string(def.keyword) + " (already exists)");
            skippedCount++;
            continue;
        }
        insertBlock += std::string(def.keyword) + "\n";
        insertBlock += std::string(def.comment) + "\n";
        snprintf(buf, sizeof(buf), "%10.4g%10d%10d%10d\n", dt, 0, 0, 1);
        insertBlock += buf;
        insertedCount++;
    }

    for (int i = 0; i < DB_BINARY_COUNT; ++i) {
        const auto& def = DB_BINARY[i];
        if (enabledBinary.find(def.name) == enabledBinary.end()) continue;
        std::string kwUp = def.keyword;
        for (auto& c : kwUp) c = (char)toupper((unsigned char)c);
        if (existingKeywords.count(kwUp)) {
            console.println("  [SKIP] " + std::string(def.keyword) + " (already exists)");
            skippedCount++;
            continue;
        }
        double interval = dt;
        if (std::string(def.name) == "d3plot") interval = dt_plot;
        else if (std::string(def.name) == "d3thdt") interval = dt_thdt;
        else if (std::string(def.name) == "d3dump") interval = dt_dump;
        else if (std::string(def.name) == "runrsf") interval = dt_dump;
        else if (std::string(def.name) == "d3drlf") interval = dt_plot;
        insertBlock += std::string(def.keyword) + "\n";
        insertBlock += std::string(def.comment) + "\n";
        snprintf(buf, sizeof(buf), "%10.4g%10d%10d%10d%10d\n", interval, 0, 0, 0, 0);
        insertBlock += buf;
        insertedCount++;
    }

    if (extentBinary) {
        if (existingKeywords.count("*DATABASE_EXTENT_BINARY")) {
            console.println("  [SKIP] *DATABASE_EXTENT_BINARY (already exists)");
            skippedCount++;
        } else {
            insertBlock += db_buildExtentBinary(neiph, neips, maxint,
                                                 strflg, sigflg, epsflg,
                                                 rltflg, engflg, cmpflg);
            insertedCount++;
        }
    }

    insertBlock += "$\n";
    insertBlock += "$ === END DATABASE OUTPUT CONTROL ===\n";
    insertBlock += "$\n";

    console.info("Writing output: " + outputPath);
    std::ofstream out(outputPath);
    if (!out.is_open()) { console.error("Cannot write: " + outputPath); return 1; }

    bool endFound = false;
    for (const auto& ln : rawLines) {
        std::string up = ln;
        for (auto& c : up) c = (char)toupper((unsigned char)c);
        size_t s2 = up.find_first_not_of(" \t");
        if (s2 != std::string::npos) up = up.substr(s2);
        if (up.find("*END") == 0 && (up.size() == 4 || !std::isalpha(up[4]))) {
            out << insertBlock;
            endFound = true;
        }
        out << ln << "\n";
    }

    if (!endFound) {
        out << insertBlock;
        out << "*END\n";
    }
    out.close();

    std::cout << "\n";
    console.success("Inserted: " + std::to_string(insertedCount) + " keyword(s)");
    if (skippedCount > 0) console.info("Skipped: " + std::to_string(skippedCount) + " (already exist)");

    return 0;
}
