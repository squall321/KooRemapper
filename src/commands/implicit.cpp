#include "implicit.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cstdio>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/implicit]]

using KooRemapper::ConsoleOutput;

// ---------------------------------------------------------------------------
// Generate the *CONTROL_IMPLICIT_* block set as a string
// ---------------------------------------------------------------------------

static std::string impl_generateImplicitCards(
        const std::string& mode, int level, double endtime,
        double dctolOvr, double ectolOvr, double dt0Ovr, double dtmaxOvr,
        int nsolvrOvr, int kfailOvr, int lsolvrOvr, double rctolOvr,
        int stabOvr,
        double stabScaleOvr,
        int arcOvr) {
    struct LP { int nsolvr,ilimit,maxref,iteopt,kfail,lsolvr;
                double dctol,ectol,lstol,rctol,dt0f,dtmaxf,dtminf;
                bool stab,arcl; double stabScale; };
    static const LP lv[8] = {
        {12,11,10,11,0, 7, 0.005,0.050,0.90,1e10, 1./100,  1./20,   1./1000,   false,false,1.0},
        {12,11,15,11,0, 7, 0.001,0.010,0.90,1e10, 1./500,  1./100,  1./10000,  false,false,1.0},
        {12,15,20,11,0, 7, 0.001,0.010,0.95,1e10, 1./1000, 1./200,  1./10000,  false,false,1.0},
        {-2,20,25,11,3, 7, 0.001,0.010,0.95,1e10, 1./2000, 1./500,  1./100000, false,false,1.0},
        {-2,25,30,15,5, 7, 0.001,0.005,0.99,1e10, 1./5000, 1./1000, 1./100000, true, false,1.0},
        {-2,30,40,15,8, 30,0.0005,0.002,0.99,0.1, 1./10000,1./2000, 1./100000, true, false,1.0},
        {-2,40,50,20,15,30,0.0001,0.001,0.99,0.01,1./50000,1./10000,1./1000000,true, false,1.0},
        { 7,40,50,20,15,30,0.0001,0.001,0.99,0.01,1./50000,1./10000,1./1000000,true, true, 1.0},
    };
    int idx = std::max(0, std::min(7, level-1));
    const LP& p = lv[idx];
    int    nsolvr    = (nsolvrOvr!=0)   ? nsolvrOvr    : p.nsolvr;
    double dctol     = (dctolOvr>0)     ? dctolOvr     : p.dctol;
    double ectol     = (ectolOvr>0)     ? ectolOvr     : p.ectol;
    double rctol     = (rctolOvr>0)     ? rctolOvr     : p.rctol;
    double dt0       = (dt0Ovr>0)       ? dt0Ovr       : endtime*p.dt0f;
    double dtmax     = (dtmaxOvr>0)     ? dtmaxOvr     : endtime*p.dtmaxf;
    double dtmin     = -(endtime*p.dtminf);
    int    kfail     = (kfailOvr>=0)    ? kfailOvr     : p.kfail;
    int    lsolvr    = (lsolvrOvr>0)    ? lsolvrOvr    : p.lsolvr;
    bool   stab      = (stabOvr>=0)     ? (stabOvr>0)  : p.stab;
    double stabScale = (stabScaleOvr>0) ? stabScaleOvr : p.stabScale;
    bool   arcl      = (arcOvr>=0)      ? (arcOvr>0)   : p.arcl;
    int    imass     = (mode=="dynamic") ? 1 : 0;
    double gamma     = (mode=="dynamic") ? 0.6  : 0.5;
    double beta      = (mode=="dynamic") ? 0.30 : 0.25;

    if (arcl && (nsolvr < 6 || nsolvr > 9)) nsolvr = 7;

    char rctolBuf[12];
    if (rctol >= 1e9) snprintf(rctolBuf, sizeof(rctolBuf), " 1.000E+10");
    else              snprintf(rctolBuf, sizeof(rctolBuf), "%10.3E", rctol);

    char buf[2048];
    int n = snprintf(buf, sizeof(buf),
        "*CONTROL_IMPLICIT_GENERAL\n"
        "$   IMFLAG       DT0    IMFORM      NSBS       IGS    CNSTN      FORM    ZERO_V\n"
        "         1%10.6f         2         1         2         0         0         0\n"
        "*CONTROL_IMPLICIT_DYNAMICS\n"
        "$    IMASS     GAMMA      BETA    TDYBIR    TDYDTH    TDYBUR     IRATE\n"
        "%10d%10.6f%10.6f       0.0 1.000E+28 1.000E+28         0\n"
        "*CONTROL_IMPLICIT_SOLUTION\n"
        "$   NSOLVR    ILIMIT    MAXREF     DCTOL     ECTOL     RCTOL     LSTOL    ABSTOL\n"
        "%10d%10d%10d%10.6f%10.6f%s%10.6f 1.000E-10\n",
        dt0,
        imass, gamma, beta,
        nsolvr, p.ilimit, p.maxref, dctol, ectol, rctolBuf, p.lstol);

    if (arcl) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "$    DNORM    DIVERG     ISTIF   NLPRINT    NLNORM   D3ITCTL     CPCHK\n"
            "         0         0         1         0         0         0         0\n"
            "$   ARCCTL    ARCDIR    ARCLEN    ARCMTH    ARCDMP    ARCPSI    ARCALF    ARCTIM\n"
            "         0         0  0.000000         1         2  0.000000  0.000000  0.000000\n");
    }

    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_AUTO\n"
        "$    IAUTO    ITEOPT    ITEWIN     DTMIN     DTMAX     DTEXP     KFAIL    KCYCLE\n"
        "         1%10d         5%10.3E%10.3E       0.0%10d         0\n",
        p.iteopt, dtmin, dtmax, kfail);

    if (stab) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_STABILIZATION\n"
            "$       IAS     SCALE    TSTART      TEND\n"
            "         1%10.6f       0.0 1.000E+28\n",
            stabScale);
    }

    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_SOLVER\n"
        "$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC   AUTOTOL\n"
        "%10d         0         2         0         4       0.0         1       0.0\n",
        lsolvr);

    return std::string(buf);
}

// ---------------------------------------------------------------------------
// runExplicit
// ---------------------------------------------------------------------------

int runExplicit(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    bool keepDrCurves = false;

    std::string line;
    while (std::getline(f, line)) {
        std::string t = kw_trim(line);
        if (t.empty() || t[0] == '#') continue;
        size_t cp = t.find(':');
        if (cp == std::string::npos) continue;
        std::string key = kw_trim(t.substr(0, cp));
        std::string val = kw_trim(t.substr(cp + 1));
        { size_t h = val.find('#'); if (h != std::string::npos) val = kw_trim(val.substr(0, h)); }
        if (val.empty()) continue;
        if      (key == "model")           modelFile  = val;
        else if (key == "output")          outputFile = val;
        else if (key == "keep_dr_curves")  keepDrCurves = (val == "true" || val == "yes" || val == "1");
    }

    if (modelFile.empty())  { console.error("explicit YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("explicit YAML: 'output' not specified"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/') == std::string::npos && p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }

    console.println("[explicit] Model   : " + modelPath);
    console.println("[explicit] Output  : " + outPath);
    console.println("[explicit] Stripping implicit/DR/modal keywords...");

    auto removeAndLog = [&](const std::string& kw) {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, kw);
        if (lines.size() < before) console.println("[explicit] Removed : " + kw);
    };

    removeAndLog("*CONTROL_DYNAMIC_RELAXATION");
    removeAndLog("*DATABASE_BINARY_D3DRLF");
    removeAndLog("*CONTROL_IMPLICIT_GENERAL");
    removeAndLog("*CONTROL_IMPLICIT_DYNAMICS");
    removeAndLog("*CONTROL_IMPLICIT_SOLUTION");
    removeAndLog("*CONTROL_IMPLICIT_AUTO");
    removeAndLog("*CONTROL_IMPLICIT_STABILIZATION");
    removeAndLog("*CONTROL_IMPLICIT_SOLVER");
    removeAndLog("*CONTROL_IMPLICIT_BUCKLE");
    removeAndLog("*CONTROL_IMPLICIT_FORMING");
    removeAndLog("*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
    removeAndLog("*CONTROL_IMPLICIT_EIGENVALUE");

    if (!keepDrCurves) {
        int n = kw_removeDrCurves(lines);
        if (n > 0) {
            char buf[64];
            snprintf(buf, sizeof(buf), "[explicit] Removed : %d *DEFINE_CURVE (SIDR=1)", n);
            console.println(buf);
        }
    }

    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[explicit] Done    -> " + outPath);
    return 0;
}

// ---------------------------------------------------------------------------
// runImplicit
// ---------------------------------------------------------------------------

int runImplicit(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    std::string mode = "static";
    int level = 2;
    double endtimeYaml = -1.0;
    double dctolOvr=-1.0, ectolOvr=-1.0, dt0Ovr=-1.0, dtmaxOvr=-1.0, rctolOvr=-1.0;
    double stabScaleOvr = 0.0;
    int nsolvrOvr = 0, kfailOvr = -1, lsolvrOvr = 0, stabOvr = -1, arcOvr = -1;
    bool fixShellElform = false;
    bool keepDrCurves   = false;
    bool stripMode      = false;

    std::string line;
    while (std::getline(f, line)) {
        std::string tr = kw_trim(line);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp==std::string::npos) continue;
        std::string key = kw_trim(tr.substr(0,cp));
        std::string val = kw_trim(tr.substr(cp+1));
        { size_t h = val.find('#'); if (h != std::string::npos) val = kw_trim(val.substr(0,h)); }
        if (val.empty()) continue;
        try {
            if      (key=="model")   modelFile  = val;
            else if (key=="output")  outputFile = val;
            else if (key=="mode")    mode = val;
            else if (key=="level")   level = std::stoi(val);
            else if (key=="endtime") endtimeYaml = std::stod(val);
            else if (key=="dctol")   dctolOvr  = std::stod(val);
            else if (key=="ectol")   ectolOvr  = std::stod(val);
            else if (key=="dt0")     dt0Ovr    = std::stod(val);
            else if (key=="dtmax")   dtmaxOvr  = std::stod(val);
            else if (key=="nsolvr")     nsolvrOvr    = std::stoi(val);
            else if (key=="kfail")      kfailOvr     = std::stoi(val);
            else if (key=="lsolvr")     lsolvrOvr    = std::stoi(val);
            else if (key=="rctol")      rctolOvr     = std::stod(val);
            else if (key=="stab")        stabOvr      = (val=="true"||val=="yes"||val=="1")?1:0;
            else if (key=="stab_scale")  stabScaleOvr = std::stod(val);
            else if (key=="arc_length")  arcOvr       = (val=="true"||val=="yes"||val=="1")?1:0;
            else if (key=="fix_shell_elform") fixShellElform=(val=="true"||val=="yes"||val=="1");
            else if (key=="keep_dr_curves")   keepDrCurves  =(val=="true"||val=="yes"||val=="1");
            else if (key=="strip") stripMode=(val=="true"||val=="yes"||val=="1");
        } catch(...) {}
    }

    if (modelFile.empty())  { console.error("implicit YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("implicit YAML: 'output' not specified"); return 1; }
    if (!stripMode && (level<1||level>8))   { console.error("implicit: level must be 1~8"); return 1; }
    if (!stripMode && mode!="static"&&mode!="dynamic") {
        console.error("implicit: mode must be 'static' or 'dynamic'"); return 1;
    }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0]!='/' && p[0]!='\\' && !(p.size()>=2 && p[1]==':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    if (stripMode) {
        console.println("[implicit] Model   : " + modelPath);
        console.println("[implicit] Output  : " + outPath);
        console.println("[implicit] Mode    : STRIP (remove implicit keywords)");

        auto removeAndLog = [&](const std::string& kw) {
            size_t before = lines.size();
            lines = kw_removeKeyword(lines, kw);
            if (lines.size() < before) console.println("[implicit] Removed : " + kw);
        };
        removeAndLog("*CONTROL_IMPLICIT_GENERAL");
        removeAndLog("*CONTROL_IMPLICIT_DYNAMICS");
        removeAndLog("*CONTROL_IMPLICIT_SOLUTION");
        removeAndLog("*CONTROL_IMPLICIT_AUTO");
        removeAndLog("*CONTROL_IMPLICIT_STABILIZATION");
        removeAndLog("*CONTROL_IMPLICIT_SOLVER");
        removeAndLog("*CONTROL_IMPLICIT_BUCKLE");
        removeAndLog("*CONTROL_IMPLICIT_FORMING");
        removeAndLog("*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
        removeAndLog("*CONTROL_IMPLICIT_EIGENVALUE");

        std::ofstream out(outPath);
        if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
        for (const auto& ln : lines) out << ln << "\n";
        console.println("[implicit] Done    -> " + outPath);
        return 0;
    }

    static const char* levelNames[8] = {"공격적","표준","안정","수렴우선","강건","고강건","최대안정","좌굴/스냅스루"};
    static const double dtmaxF[8]  = {1./20,1./100,1./200,1./500,1./1000,1./2000,1./10000,1./10000};
    static const int    nsolvrL[8] = {12,12,12,-2,-2,-2,-2,7};
    static const double dctolL[8]  = {0.005,0.001,0.001,0.001,0.001,0.0005,0.0001,0.0001};
    static const int    kfailL[8]  = {0,0,0,3,5,8,15,15};
    static const int    lsolvrL[8] = {7,7,7,7,7,30,30,30};
    static const bool   stabL[8]   = {false,false,false,false,true,true,true,true};
    static const double rctolL[8]  = {1e10,1e10,1e10,1e10,1e10,0.1,0.01,0.01};
    static const bool   arclL[8]   = {false,false,false,false,false,false,false,true};
    int li = level-1;

    console.println("[implicit] Model   : " + modelPath);
    console.println("[implicit] Output  : " + outPath);
    console.println("[implicit] Mode    : " + mode +
                    " (IMASS=" + (mode=="static"?"0":"1") + ")");

    double endtime = endtimeYaml;
    std::string endtimeSource;
    if (endtime < 0) {
        double modelEnd = kw_readEndtime(lines);
        if (modelEnd > 0.0) {
            endtime = modelEnd; endtimeSource = "from model";
        } else if (modelEnd == 0.0) {
            console.println("[WARNING]  endtim=0 detected (DR mode). Add 'endtime:' to YAML. Using 1.0 as fallback.");
            endtime = 1.0; endtimeSource = "fallback=1.0";
        } else {
            console.println("[WARNING]  *CONTROL_TERMINATION not found. Add 'endtime:' to YAML. Using 1.0 as fallback.");
            endtime = 1.0; endtimeSource = "fallback=1.0";
        }
    } else {
        endtimeSource = "from YAML";
    }

    int    dispNsolvr = (nsolvrOvr!=0) ? nsolvrOvr : nsolvrL[li];
    double dispDctol  = (dctolOvr>0)   ? dctolOvr  : dctolL[li];
    double dispDtmax  = (dtmaxOvr>0)   ? dtmaxOvr  : endtime*dtmaxF[li];
    int    dispKfail  = (kfailOvr>=0)  ? kfailOvr  : kfailL[li];
    int    dispLsolvr = (lsolvrOvr>0)  ? lsolvrOvr : lsolvrL[li];
    bool   dispStab   = (stabOvr>=0)   ? (stabOvr>0): stabL[li];
    double dispRctol  = (rctolOvr>0)   ? rctolOvr  : rctolL[li];
    bool   dispArcl   = (arcOvr>=0)    ? (arcOvr>0) : arclL[li];
    if (dispArcl && (dispNsolvr < 6 || dispNsolvr > 9)) dispNsolvr = 7;

    char lvBuf[256];
    int ln = snprintf(lvBuf, sizeof(lvBuf),
        "[implicit] Level   : %d (%s)  NSOLVR=%d  DCTOL=%.6g  DTMAX=%.6g",
        level, levelNames[li], dispNsolvr, dispDctol, dispDtmax);
    if (dispKfail  > 0)   ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +KFAIL=%d", dispKfail);
    if (dispStab)         ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +STAB");
    if (dispLsolvr == 30) ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +MUMPS");
    if (dispRctol  < 1e9) ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +RCTOL=%.4g", dispRctol);
    if (dispArcl)         ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +ARC-LENGTH");
    console.println(lvBuf);
    char etBuf[80];
    snprintf(etBuf, sizeof(etBuf), "[implicit] Endtime : %g (%s)", endtime, endtimeSource.c_str());
    console.println(etBuf);

    auto removeAndLog = [&](const std::string& kw) {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, kw);
        if (lines.size() < before) console.println("[implicit] Removed : " + kw);
    };
    removeAndLog("*CONTROL_DYNAMIC_RELAXATION");
    removeAndLog("*CONTROL_BULK_VISCOSITY");
    removeAndLog("*DATABASE_BINARY_D3DRLF");
    removeAndLog("*CONTROL_DYNAMICS");

    if (!keepDrCurves) {
        int n = kw_removeDrCurves(lines);
        if (n > 0) {
            char buf[64];
            snprintf(buf, sizeof(buf), "[implicit] Removed : %d *DEFINE_CURVE (SIDR=1)", n);
            console.println(buf);
        }
    }

    if (kw_modifyTimestep(lines))
        console.println("[implicit] Modified: *CONTROL_TIMESTEP (DT2MS=0.0, TSSFAC=0.90)");

    if (endtimeYaml > 0) {
        double oldEnd = kw_readEndtime(lines);
        if (kw_modifyTermination(lines, endtimeYaml)) {
            char buf[128];
            snprintf(buf, sizeof(buf),
                "[implicit] Modified: *CONTROL_TERMINATION (endtim: %g -> %g)", oldEnd, endtimeYaml);
            console.println(buf);
        }
    }

    std::vector<std::string> shellWarnings;
    kw_checkShellElform(lines, fixShellElform, shellWarnings);
    for (const auto& w : shellWarnings) console.println(w);
    if (fixShellElform && !shellWarnings.empty())
        console.println("[implicit] Fixed   : ELFORM=16 -> 2 in *SECTION_SHELL");

    {
        bool hadImplicit = false;
        for (const auto& l : lines)
            if (kw_upper(kw_trim(l)).rfind("*CONTROL_IMPLICIT",0)==0) { hadImplicit=true; break; }
        if (hadImplicit) {
            console.println("[WARNING]  *CONTROL_IMPLICIT_* already exists. Replacing...");
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

    std::string implCards = impl_generateImplicitCards(
        mode, level, endtime, dctolOvr, ectolOvr, dt0Ovr, dtmaxOvr,
        nsolvrOvr, kfailOvr, lsolvrOvr, rctolOvr, stabOvr, stabScaleOvr, arcOvr);
    kw_insertBeforeEnd(lines, implCards);
    {
        std::string msg = "[implicit] Inserted: *CONTROL_IMPLICIT_GENERAL/DYNAMICS/SOLUTION/AUTO";
        if ((stabOvr>=0)?(stabOvr>0):stabL[li])              msg += "  +STABILIZATION";
        if (((lsolvrOvr>0)?lsolvrOvr:lsolvrL[li]) == 30)     msg += "  +SOLVER(MUMPS)";
        if ((arcOvr>=0)?(arcOvr>0):arclL[li])                msg += "  +ARC-LENGTH(Crisfield)";
        console.println(msg);
    }

    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[implicit] Done    -> " + outPath);
    return 0;
}
