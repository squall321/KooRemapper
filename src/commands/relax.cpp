#include "relax.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <cstdio>

using KooRemapper::ConsoleOutput;

// ---------------------------------------------------------------------------
// relax_generateCards — also called from assemble command
// ---------------------------------------------------------------------------

std::string relax_generateCards(int level, const std::string& mode,
    double drterm, double nrcyckOvr, double drtolOvr, double drfctrOvr,
    double tssfdrOvr, int irelalOvr, double edttlOvr, bool d3drlf)
{
    // Level presets: NRCYCK, DRTOL, DRFCTR, TSSFDR, IRELAL, EDTTL
    struct LP { int nrcyck; double drtol, drfctr, tssfdr; int irelal; double edttl; };
    static const LP lv[5] = {
        { 500, 0.010,  0.990, 0.95, 0, 0.04  },  // 1: fast
        { 250, 0.001,  0.995, 0.90, 0, 0.04  },  // 2: standard
        { 100, 0.001,  0.998, 0.80, 0, 0.04  },  // 3: stable
        {  50, 1e-4,   0.999, 0.67, 1, 0.01  },  // 4: conservative
        {  25, 1e-5,   0.999, 0.50, 1, 0.001 },  // 5: max
    };
    int li = level - 1;
    int    nrcyck = (nrcyckOvr > 0) ? (int)nrcyckOvr : lv[li].nrcyck;
    double drtol  = (drtolOvr  > 0) ? drtolOvr       : lv[li].drtol;
    double drfctr = (drfctrOvr > 0) ? drfctrOvr      : lv[li].drfctr;
    double tssfdr = (tssfdrOvr > 0) ? tssfdrOvr      : lv[li].tssfdr;
    int    irelal = (irelalOvr >= 0)? irelalOvr      : lv[li].irelal;
    double edttl  = (edttlOvr  > 0) ? edttlOvr       : lv[li].edttl;
    int    idrflg = (mode == "implicit") ? 5 : 1;

    std::ostringstream ss;
    ss << "*CONTROL_DYNAMIC_RELAXATION\n";
    ss << "$#  nrcyck    drtol   drfctr   drterm   tssfdr   irelal    edttl    idrflg\n";
    char buf[128];
    snprintf(buf, sizeof(buf), "%10d%10.6f%10.6f%10g%10.6f%10d%10.6f%10d",
             nrcyck, drtol, drfctr, drterm, tssfdr, irelal, edttl, idrflg);
    ss << buf << "\n";

    if (d3drlf) {
        ss << "*DATABASE_BINARY_D3DRLF\n";
        ss << "$#      dt      lcid\n";
        ss << " 1.000e-03         0\n";
    }

    // mode=implicit: add CONTROL_IMPLICIT_GENERAL + SOLUTION for IDRFLG=5
    if (mode == "implicit") {
        ss << "*CONTROL_IMPLICIT_GENERAL\n";
        ss << "$#  imflag       dt0    imform      nsbs       igs     cnstn      form  zero_v\n";
        ss << "         1       1.0         2         1         2         0         0         0\n";
        ss << "*CONTROL_IMPLICIT_SOLUTION\n";
        ss << "$#  nsolvr    ilimit    maxref    dctol     ectol     rctol     lstol    abstol\n";
        ss << "        12        11        15 0.001000 0.010000 1.000e+10 0.900000       0.0\n";
    }

    return ss.str();
}

// ---------------------------------------------------------------------------
// runRelax
// ---------------------------------------------------------------------------

int runRelax(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    std::string mode = "explicit";
    int level = 2;
    double drterm = 0.0;
    double endtimeYaml = -1.0;
    double nrcyckOvr = -1, drtolOvr = -1, drfctrOvr = -1, tssfdrOvr = -1, edttlOvr = -1;
    int irelalOvr = -1;
    bool d3drlf = true;
    bool fixShellElform = false;
    bool stripMode = false;

    std::string line;
    while (std::getline(f, line)) {
        std::string tr = kw_trim(line);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = kw_trim(tr.substr(0, cp));
        std::string val = kw_trim(tr.substr(cp + 1));
        { size_t h = val.find('#'); if (h != std::string::npos) val = kw_trim(val.substr(0, h)); }
        if (val.empty()) continue;
        try {
            if      (key == "model")   modelFile  = val;
            else if (key == "output")  outputFile = val;
            else if (key == "mode")    mode = val;
            else if (key == "level")   level = std::stoi(val);
            else if (key == "drterm")  drterm = std::stod(val);
            else if (key == "endtime") endtimeYaml = std::stod(val);
            else if (key == "nrcyck")  nrcyckOvr = std::stod(val);
            else if (key == "drtol")   drtolOvr  = std::stod(val);
            else if (key == "drfctr")  drfctrOvr = std::stod(val);
            else if (key == "tssfdr")  tssfdrOvr = std::stod(val);
            else if (key == "irelal")  irelalOvr = std::stoi(val);
            else if (key == "edttl")   edttlOvr  = std::stod(val);
            else if (key == "d3drlf")  d3drlf = (val == "true" || val == "yes" || val == "1");
            else if (key == "fix_shell_elform") fixShellElform = (val == "true" || val == "yes" || val == "1");
            else if (key == "strip") stripMode = (val == "true" || val == "yes" || val == "1");
        } catch (...) {}
    }

    if (modelFile.empty())  { console.error("relax YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("relax YAML: 'output' not specified"); return 1; }
    if (!stripMode && (level < 1 || level > 5)) { console.error("relax: level must be 1~5"); return 1; }
    if (!stripMode && mode != "explicit" && mode != "implicit") {
        console.error("relax: mode must be 'explicit' or 'implicit'"); return 1;
    }

    // Resolve paths
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/') == std::string::npos && p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    // 2. Read model file
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    // 3. Strip mode: remove DR keywords and exit
    if (stripMode) {
        console.println("[relax] Model    : " + modelPath);
        console.println("[relax] Output   : " + outPath);
        console.println("[relax] Mode     : STRIP (remove DR keywords)");

        auto removeAndLog = [&](const std::string& kw) {
            size_t before = lines.size();
            lines = kw_removeKeyword(lines, kw);
            if (lines.size() < before) console.println("[relax] Removed  : " + kw);
        };
        removeAndLog("*CONTROL_DYNAMIC_RELAXATION");
        removeAndLog("*DATABASE_BINARY_D3DRLF");

        std::ofstream out(outPath);
        if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
        for (const auto& ln : lines) out << ln << "\n";
        console.println("[relax] Done     -> " + outPath);
        return 0;
    }

    // 3b. Print header (normal mode)
    static const char* levelNames[5] = {"빠름", "표준", "안정", "보수", "최대"};
    struct LP { int nrcyck; double drtol, drfctr, tssfdr; int irelal; double edttl; };
    static const LP lv[5] = {
        {500, 0.010, 0.990, 0.95, 0, 0.04},
        {250, 0.001, 0.995, 0.90, 0, 0.04},
        {100, 0.001, 0.998, 0.80, 0, 0.04},
        { 50, 1e-4,  0.999, 0.67, 1, 0.01},
        { 25, 1e-5,  0.999, 0.50, 1, 0.001},
    };
    int li = level - 1;
    int    dispNrcyck = (nrcyckOvr > 0) ? (int)nrcyckOvr : lv[li].nrcyck;
    double dispDrtol  = (drtolOvr  > 0) ? drtolOvr       : lv[li].drtol;
    double dispDrfctr = (drfctrOvr > 0) ? drfctrOvr      : lv[li].drfctr;
    double dispTssfdr = (tssfdrOvr > 0) ? tssfdrOvr      : lv[li].tssfdr;

    console.println("[relax] Model    : " + modelPath);
    console.println("[relax] Output   : " + outPath);
    console.println("[relax] Mode     : " + mode +
                    " (IDRFLG=" + (mode == "implicit" ? "5" : "1") + ")");
    char lvBuf[256];
    snprintf(lvBuf, sizeof(lvBuf),
        "[relax] Level    : %d (%s)  NRCYCK=%d  DRTOL=%.6g  DRFCTR=%.6f  TSSFDR=%.4g",
        level, levelNames[li], dispNrcyck, dispDrtol, dispDrfctr, dispTssfdr);
    console.println(lvBuf);
    if (drterm > 0) {
        char dtBuf[80];
        snprintf(dtBuf, sizeof(dtBuf), "[relax] DRTERM   : %g", drterm);
        console.println(dtBuf);
    }

    // 4. Remove existing DR card (will re-insert with new values)
    auto removeAndLog = [&](const std::string& kw) {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, kw);
        if (lines.size() < before) console.println("[relax] Removed  : " + kw);
    };
    removeAndLog("*CONTROL_DYNAMIC_RELAXATION");
    removeAndLog("*DATABASE_BINARY_D3DRLF");

    // 5. Remove existing CONTROL_IMPLICIT_* (conflicting)
    {
        bool hadImplicit = false;
        for (const auto& ln : lines)
            if (kw_upper(kw_trim(ln)).rfind("*CONTROL_IMPLICIT", 0) == 0) { hadImplicit = true; break; }
        if (hadImplicit) {
            console.println("[relax] Removing existing *CONTROL_IMPLICIT_* cards...");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_GENERAL");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_DYNAMICS");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLUTION");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_AUTO");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_STABILIZATION");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLVER");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_BUCKLE");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_FORMING");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
        }
    }

    // 6. NOTE: SIDR=1 DEFINE_CURVEs are preserved (DR needs them)

    // 7. Modify *CONTROL_TERMINATION if user specified endtime
    if (endtimeYaml > 0) {
        double oldEnd = kw_readEndtime(lines);
        if (kw_modifyTermination(lines, endtimeYaml)) {
            char buf[128];
            snprintf(buf, sizeof(buf), "[relax] Modified : *CONTROL_TERMINATION (endtim: %g -> %g)", oldEnd, endtimeYaml);
            console.println(buf);
        }
    }

    // 8. Check ELFORM
    if (fixShellElform) {
        std::vector<std::string> shellWarnings;
        kw_checkShellElform(lines, fixShellElform, shellWarnings);
        for (const auto& w : shellWarnings) console.println(w);
    }

    // 9. Generate and insert DR cards
    std::string drCards = relax_generateCards(level, mode, drterm,
        nrcyckOvr, drtolOvr, drfctrOvr, tssfdrOvr, irelalOvr, edttlOvr, d3drlf);
    kw_insertBeforeEnd(lines, drCards);

    std::string insertMsg = "[relax] Inserted : *CONTROL_DYNAMIC_RELAXATION";
    if (d3drlf) insertMsg += "  +D3DRLF";
    if (mode == "implicit") insertMsg += "  +IMPLICIT_GENERAL/SOLUTION";
    console.println(insertMsg);

    // 10. Write output
    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[relax] Done     -> " + outPath);
    return 0;
}
