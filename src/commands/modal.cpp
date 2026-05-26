#include "modal.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <fstream>
#include <sstream>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/modal]]

using KooRemapper::ConsoleOutput;

// ---------------------------------------------------------------------------
// Modal helpers
// ---------------------------------------------------------------------------

static std::string modal_eigmthName(int eigmth) {
    switch (eigmth) {
        case 2:   return "Block Shift Lanczos";
        case 101: return "MCMS (NVH)";
        case 102: return "LOBPCG";
        case 103: return "Fast Lanczos (MPP)";
        default:  return "Method " + std::to_string(eigmth);
    }
}

static std::string modal_generateCards(int nmode, double fmin, double fmax,
                                        double center, int eigmth, int lsolvr) {
    char buf[4096]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_GENERAL\n"
        "$   IMFLAG       DT0    IMFORM      NSBS       IGS    CNSTN      FORM    ZERO_V\n"
        "         1  1.000000         2         1         2         0         0         0\n");
    int lflag = (fmin > 0.0) ? 1 : 0;
    int rflag = (fmax > 0.0) ? 1 : 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_EIGENVALUE\n"
        "$      NEIG    CENTER     LFLAG    LFTEND     RFLAG    RHTEND    EIGMTH    SHFSCL\n"
        "%10d%10.4f%10d%10.4f%10d%10.4f%10d  0.000000\n",
        nmode, center, lflag, fmin, rflag, fmax, eigmth);
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_SOLUTION\n"
        "$   NSOLVR    ILIMIT    MAXREF     DCTOL     ECTOL     RCTOL     LSTOL    ABSTOL\n"
        "        12        11        15  0.001000  0.010000 1.000E+10  0.900000 1.000E-10\n");
    if (lsolvr == 30) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_SOLVER\n"
            "$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC    AUTOTOL\n"
            "        30         0         2         0         4  0.000000         1 1.000E-07\n");
    }
    return std::string(buf, n);
}

// ---------------------------------------------------------------------------
// runModal
// ---------------------------------------------------------------------------

int runModal(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::string modelPath, outPath;
    int    nmode        = 10;
    double fmin         = 0.0;
    double fmax         = 0.0;
    double center       = 0.0;
    int    eigmth       = 2;
    int    lsolvr       = 7;
    bool   fixElform    = false;
    bool   keepDrCurves = false;
    bool   stripMode    = false;

    // Resolve configDir for relative paths
    std::string configDir;
    {
        std::string yf = yamlFile;
        size_t sep = yf.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yf.substr(0, sep+1) : "";
    }

    {
        std::ifstream yin(yamlFile);
        if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }
        std::string line;
        while (std::getline(yin, line)) {
            std::string t = kw_trim(line);
            if (t.empty() || t[0] == '#') continue;
            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = kw_trim(t.substr(0, colon));
            std::string val = kw_trim(t.substr(colon+1));
            if (val.empty() || val[0] == '#') continue;
            size_t hpos = val.find('#');
            if (hpos != std::string::npos) val = kw_trim(val.substr(0, hpos));
            if      (key == "model")             modelPath    = val;
            else if (key == "output")            outPath      = val;
            else if (key == "nmode")             nmode        = std::stoi(val);
            else if (key == "fmin")              fmin         = std::stod(val);
            else if (key == "fmax")              fmax         = std::stod(val);
            else if (key == "center")            center       = std::stod(val);
            else if (key == "eigmth")            eigmth       = std::stoi(val);
            else if (key == "solver")            lsolvr       = std::stoi(val);
            else if (key == "fix_shell_elform")  fixElform    = (val == "true");
            else if (key == "keep_dr_curves")    keepDrCurves = (val == "true");
            else if (key == "strip")             stripMode    = (val == "true" || val == "yes" || val == "1");
        }
    }

    if (modelPath.empty()) { console.error("YAML missing 'model' field"); return 1; }
    if (outPath.empty())   { console.error("YAML missing 'output' field"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelFullPath = resolvePath(modelPath);
    std::string outFullPath   = resolvePath(outPath);

    // 2. Read model file
    std::vector<std::string> lines;
    {
        std::ifstream fin(modelFullPath);
        if (!fin.is_open()) { console.error("Cannot open model: " + modelFullPath); return 1; }
        std::string ln;
        while (std::getline(fin, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }

    // Strip mode: remove modal keywords and exit
    if (stripMode) {
        console.println("[modal] Model   : " + modelPath);
        console.println("[modal] Output  : " + outPath);
        console.println("[modal] Mode    : STRIP (remove modal keywords)");

        auto removeAndLog = [&](const std::string& kw) {
            size_t before = lines.size();
            lines = kw_removeKeyword(lines, kw);
            if (lines.size() < before) console.println("[modal] Removed : " + kw);
        };
        removeAndLog("*CONTROL_IMPLICIT_EIGENVALUE");
        removeAndLog("*CONTROL_IMPLICIT_GENERAL");
        removeAndLog("*CONTROL_IMPLICIT_SOLUTION");
        removeAndLog("*CONTROL_IMPLICIT_SOLVER");

        std::ofstream out(outFullPath);
        if (!out.is_open()) { console.error("Cannot write output: " + outFullPath); return 1; }
        for (const auto& ln : lines) out << ln << "\n";
        console.println("[modal] Done    -> " + outPath);
        return 0;
    }

    // Console header
    console.println("[modal] Model   : " + modelPath);
    console.println("[modal] Output  : " + outPath);
    {
        std::string freqRange = (fmin > 0.0 || fmax > 0.0)
            ? " (" + std::to_string((int)fmin) + " ~ " + std::to_string((int)fmax) + " Hz)"
            : " (no frequency limits)";
        console.println("[modal] Modes   : " + std::to_string(nmode) + freqRange);
    }
    console.println("[modal] Method  : " + modal_eigmthName(eigmth) + " (EIGMTH=" + std::to_string(eigmth) + ")");
    console.println("[modal] Solver  : " + std::to_string(lsolvr) + (lsolvr == 30 ? " (MUMPS)" : " (default)"));

    // 3. Remove explicit-only blocks
    size_t before;
    before = lines.size();
    lines = kw_removeKeyword(lines, "*CONTROL_DYNAMIC_RELAXATION");
    if (lines.size() < before) console.println("[modal] Removed : *CONTROL_DYNAMIC_RELAXATION");

    before = lines.size();
    lines = kw_removeKeyword(lines, "*CONTROL_BULK_VISCOSITY");
    if (lines.size() < before) console.println("[modal] Removed : *CONTROL_BULK_VISCOSITY");

    before = lines.size();
    lines = kw_removeKeyword(lines, "*DATABASE_BINARY_D3DRLF");
    if (lines.size() < before) console.println("[modal] Removed : *DATABASE_BINARY_D3DRLF");

    // 4. Remove DR curves (SIDR=1) unless keep_dr_curves
    if (!keepDrCurves) {
        int nRemoved = kw_removeDrCurves(lines);
        if (nRemoved > 0)
            console.println("[modal] Removed : " + std::to_string(nRemoved) + " *DEFINE_CURVE (SIDR=1)");
    }

    // 5. Modify CONTROL_TIMESTEP (DT2MS=0, TSSFAC=0.9)
    if (kw_modifyTimestep(lines))
        console.println("[modal] Modified: *CONTROL_TIMESTEP (DT2MS=0.0, TSSFAC=0.90)");

    // 6. Shell ELFORM=16 check/fix
    {
        std::vector<std::string> warnings;
        kw_checkShellElform(lines, fixElform, warnings);
        for (const auto& w : warnings) console.println(w);
    }

    // 7. Remove existing CONTROL_IMPLICIT_* blocks, then re-insert fresh ones
    {
        bool hadImplicit = false;
        for (const auto& ln : lines) {
            std::string up = kw_upper(kw_trim(ln));
            if (up.rfind("*CONTROL_IMPLICIT_", 0) == 0) { hadImplicit = true; break; }
        }
        if (hadImplicit) {
            console.println("[WARNING]  *CONTROL_IMPLICIT_* already exists. Replacing...");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_GENERAL");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_DYNAMICS");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLUTION");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_AUTO");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_STABILIZATION");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLVER");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_EIGENVALUE");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_BUCKLE");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_FORMING");
            lines = kw_removeKeyword(lines, "*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
        }
    }

    // 8. Generate and insert modal CONTROL cards
    std::string modalCards = modal_generateCards(nmode, fmin, fmax, center, eigmth, lsolvr);
    kw_insertBeforeEnd(lines, modalCards);
    console.println("[modal] Inserted: *CONTROL_IMPLICIT_GENERAL");
    {
        std::string freq = "";
        if (fmin > 0.0 || fmax > 0.0)
            freq = " (NEIG=" + std::to_string(nmode) + ", " +
                   std::to_string((int)fmin) + "~" + std::to_string((int)fmax) + " Hz)";
        else
            freq = " (NEIG=" + std::to_string(nmode) + ", no freq limits)";
        console.println("[modal] Inserted: *CONTROL_IMPLICIT_EIGENVALUE" + freq);
    }
    console.println("[modal] Inserted: *CONTROL_IMPLICIT_SOLUTION");
    if (lsolvr == 30)
        console.println("[modal] Inserted: *CONTROL_IMPLICIT_SOLVER (MUMPS)");

    // 9. Write output
    std::ofstream out(outFullPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outFullPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[modal] Done    -> " + outPath);
    return 0;
}
