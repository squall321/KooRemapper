#include "ale.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <map>
#include <set>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cstdio>

using KooRemapper::ConsoleOutput;

// ── ALE helpers ──────────────────────────────────────────────────────────────

struct AlePartEntry { int pid; std::string material; };
struct AlePartInfo  { int secid; int mid; int eosid; int hgid; };

static std::vector<int> ale_parsePidList(const std::string& val) {
    std::vector<int> pids;
    std::string s = val;
    size_t lb = s.find('['); if (lb != std::string::npos) s.erase(lb, 1);
    size_t rb = s.find(']'); if (rb != std::string::npos) s.erase(rb, 1);
    std::istringstream iss(s);
    std::string tok;
    while (std::getline(iss, tok, ',')) {
        std::string t = kw_trim(tok);
        if (!t.empty()) { try { pids.push_back(std::stoi(t)); } catch (...) {} }
    }
    return pids;
}

static std::map<int, AlePartInfo> ale_buildPartMap(
    const std::vector<std::string>& lines) {
    std::map<int, AlePartInfo> pm;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind("*PART", 0) != 0) continue;
        if (up.rfind("*PART_", 0) == 0 && up.find("*PART_TITLE") != 0) continue;
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j < (int)lines.size()) ++j; // skip title line
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j >= (int)lines.size()) continue;
        auto toks = kw_tok10(lines[j]);
        if (toks.size() < 3) continue;
        AlePartInfo info{};
        try {
            int pid = std::stoi(toks[0]);
            info.secid = (toks.size() > 1) ? std::stoi(toks[1]) : 0;
            info.mid   = (toks.size() > 2) ? std::stoi(toks[2]) : 0;
            info.eosid = (toks.size() > 3) ? std::stoi(toks[3]) : 0;
            info.hgid  = (toks.size() > 4) ? std::stoi(toks[4]) : 0;
            pm[pid] = info;
        } catch (...) {}
    }
    return pm;
}

static void ale_findMaxIds(const std::vector<std::string>& lines,
    int& maxMid, int& maxEosid, int& maxSecid, int& maxHgid) {
    maxMid = 0; maxEosid = 0; maxSecid = 0; maxHgid = 0;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = kw_upper(kw_trim(lines[i]));
        bool isMat  = (up.rfind("*MAT_", 0) == 0);
        bool isEos  = (up.rfind("*EOS_", 0) == 0);
        bool isSec  = (up.rfind("*SECTION_", 0) == 0);
        bool isHg   = (up.rfind("*HOURGLASS", 0) == 0);
        if (!isMat && !isEos && !isSec && !isHg) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = kw_tok10(lines[j]);
        if (toks.empty()) continue;
        try {
            int id = std::stoi(toks[0]);
            if (isMat  && id > maxMid)   maxMid   = id;
            if (isEos  && id > maxEosid) maxEosid = id;
            if (isSec  && id > maxSecid) maxSecid = id;
            if (isHg   && id > maxHgid)  maxHgid  = id;
        } catch (...) {}
    }
}

static bool ale_isSharedSection(const std::map<int, AlePartInfo>& partMap,
    int secid, const std::set<int>& alePids) {
    for (const auto& kv : partMap) {
        if (alePids.count(kv.first) == 0 && kv.second.secid == secid)
            return true;
    }
    return false;
}

static int ale_modifySectionElform(std::vector<std::string>& lines,
    int secid, int newElform) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind("*SECTION_SOLID", 0) != 0) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = kw_tok10(lines[j]);
        if (toks.size() < 2) continue;
        try {
            int sid = std::stoi(toks[0]);
            if (sid != secid) continue;
            int oldElform = std::stoi(toks[1]);
            lines[j] = kw_setField(lines[j], 10, 10, std::to_string(newElform));
            return oldElform;
        } catch (...) {}
    }
    return -1;
}

static std::string ale_duplicateSection(const std::vector<std::string>& lines,
    int oldSecid, int newSecid, int newElform) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind("*SECTION_SOLID", 0) != 0) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = kw_tok10(lines[j]);
        if (toks.size() < 2) continue;
        try {
            int sid = std::stoi(toks[0]);
            if (sid != oldSecid) continue;
            std::string result = "*SECTION_SOLID\n";
            result += "$    SECID    ELFORM       AET\n";
            std::string dataLine = lines[j];
            dataLine = kw_setField(dataLine, 0, 10, std::to_string(newSecid));
            dataLine = kw_setField(dataLine, 10, 10, std::to_string(newElform));
            result += dataLine + "\n";
            return result;
        } catch (...) {}
    }
    return "";
}

static bool ale_updatePartField(std::vector<std::string>& lines,
    int pid, int fieldPos, int newValue) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind("*PART", 0) != 0) continue;
        if (up.rfind("*PART_", 0) == 0 && up.find("*PART_TITLE") != 0) continue;
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j < (int)lines.size()) ++j; // skip title line
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j >= (int)lines.size()) continue;
        auto toks = kw_tok10(lines[j]);
        if (toks.empty()) continue;
        try {
            int p = std::stoi(toks[0]);
            if (p != pid) continue;
            lines[j] = kw_setField(lines[j], fieldPos, 10, std::to_string(newValue));
            return true;
        } catch (...) {}
    }
    return false;
}

static const std::vector<std::string> ALE_PRESET_NAMES = {
    "air", "nitrogen", "argon",
    "water", "electrolyte", "gasoline", "oil", "coolant",
    "resin", "tim", "silicone",
    "tnt", "c4", "vacuum"
};

static bool ale_isPreset(const std::string& mat) {
    std::string m = kw_upper(kw_trim(mat));
    for (const auto& p : ALE_PRESET_NAMES)
        if (m == kw_upper(p)) return true;
    return false;
}

static std::string ale_presetMaterial(const std::string& preset, int mid, int eosid) {
    char buf[4096]; int n = 0;
    std::string p = kw_trim(preset);
    std::transform(p.begin(), p.end(), p.begin(), [](unsigned char c){ return (char)std::tolower(c); });

    struct GasPreset { const char* name; double rho; double gamma; double e0; };
    GasPreset gases[] = {
        {"air",      1.293e-12, 1.40, 2.533e-01},
        {"nitrogen", 1.165e-12, 1.40, 2.280e-01},
        {"argon",    1.661e-12, 1.67, 1.519e-01},
    };
    for (const auto& g : gases) {
        if (p != g.name) continue;
        double c45 = g.gamma - 1.0;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_NULL\n"
            "$      MID        RO        PC        MU     TEROD     CEROD        YM        PR\n"
            "%10d%10.3E  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000\n",
            mid, g.rho);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_LINEAR_POLYNOMIAL\n"
            "$    EOSID        C0        C1        C2        C3        C4        C5        C6\n"
            "%10d  0.000000  0.000000  0.000000  0.000000%10.6f%10.6f  0.000000\n"
            "$       E0        V0\n"
            "%10.4E  1.000000\n",
            eosid, c45, c45, g.e0);
        return std::string(buf, n);
    }

    struct LiqPreset { const char* name; double rho; double c; double s1; double gam; double mu; };
    LiqPreset liqs[] = {
        {"water",       1.00e-9,  1.484e+6, 1.979, 0.11, 0.0},
        {"electrolyte", 1.18e-9,  1.200e+6, 1.58,  0.13, 0.0},
        {"gasoline",    7.50e-10, 1.250e+6, 1.60,  0.10, 0.0},
        {"oil",         8.70e-10, 1.350e+6, 1.80,  0.10, 0.0},
        {"coolant",     1.08e-9,  1.600e+6, 1.85,  0.12, 0.0},
        {"resin",       1.15e-9,  1.700e+6, 1.70,  0.10, 1.0e-5},
        {"tim",         2.80e-9,  1.800e+6, 1.60,  0.10, 5.0e-4},
        {"silicone",    1.05e-9,  1.050e+6, 1.50,  0.10, 1.0e-4},
    };
    for (const auto& l : liqs) {
        if (p != l.name) continue;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_NULL\n"
            "$      MID        RO        PC        MU     TEROD     CEROD        YM        PR\n"
            "%10d%10.3E  0.000000%10.3E  0.000000  0.000000  0.000000  0.000000\n",
            mid, l.rho, l.mu);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_GRUNEISEN\n"
            "$    EOSID         C        S1        S2        S3     GAMAO         A        E0\n"
            "%10d%10.3E%10.6f  0.000000  0.000000%10.6f  0.000000  0.000000\n"
            "$       V0\n"
            "  1.000000\n",
            eosid, l.c, l.s1, l.gam);
        return std::string(buf, n);
    }

    struct HePreset { const char* name; double rho; double d; double pcj;
                      double a; double b; double r1; double r2; double omeg; double e0; };
    HePreset hes[] = {
        {"tnt", 1.630e-9, 6.930e+6, 2.100e+4,  3.712e+5, 3.231e+3, 4.15, 0.95, 0.30, 7.0e+3},
        {"c4",  1.601e-9, 8.193e+6, 2.800e+4,  6.098e+5, 1.295e+4, 4.50, 1.40, 0.25, 9.0e+3},
    };
    for (const auto& h : hes) {
        if (p != h.name) continue;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_HIGH_EXPLOSIVE_BURN\n"
            "$      MID        RO         D       PCJ      BETA         K         G      SIGY\n"
            "%10d%10.3E%10.3E%10.3E  0.000000  0.000000  0.000000  0.000000\n",
            mid, h.rho, h.d, h.pcj);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_JWL\n"
            "$    EOSID         A         B        R1        R2      OMEG        E0        VO\n"
            "%10d%10.3E%10.3E%10.6f%10.6f%10.6f%10.3E  1.000000\n",
            eosid, h.a, h.b, h.r1, h.r2, h.omeg, h.e0);
        return std::string(buf, n);
    }

    if (p == "vacuum") {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_VACUUM\n"
            "$      MID        RO\n"
            "%10d 1.000E-18\n",
            mid);
        return std::string(buf, n);
    }

    return "";
}

static std::string ale_customMaterial(const std::string& path, int mid, int eosid) {
    std::ifstream fin(path);
    if (!fin.is_open()) return "";
    std::vector<std::string> blines;
    std::string ln;
    while (std::getline(fin, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        blines.push_back(ln);
    }
    std::string result;
    bool inBlock = false;
    bool isMat = false, isEos = false;
    bool foundMat = false, foundEos = false;
    bool matIdDone = false, eosIdDone = false;
    for (int i = 0; i < (int)blines.size(); ++i) {
        std::string up = kw_upper(kw_trim(blines[i]));
        if (!up.empty() && up[0] == '*') {
            inBlock = false;
            isMat = (up.rfind("*MAT_", 0) == 0) && !foundMat;
            isEos = (up.rfind("*EOS_", 0) == 0) && !foundEos;
            if (isMat) { inBlock = true; foundMat = true; matIdDone = false; }
            if (isEos) { inBlock = true; foundEos = true; eosIdDone = false; }
        }
        if (!inBlock) continue;
        std::string line = blines[i];
        if (line.empty() || line[0] == '*' || line[0] == '$') {
            result += line + "\n";
            continue;
        }
        if (isMat && !matIdDone) {
            line = kw_setField(line, 0, 10, std::to_string(mid));
            matIdDone = true;
        }
        if (isEos && !eosIdDone) {
            line = kw_setField(line, 0, 10, std::to_string(eosid));
            eosIdDone = true;
        }
        result += line + "\n";
    }
    return result;
}

static std::string ale_generateHourglass(int hgid) {
    char buf[512]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*HOURGLASS\n"
        "$     HGID       IHQ        QM       IBQ        Q1        Q2    QB/VDC        QW\n"
        "%10d         3 1.000E-06         0  1.500000 6.000E-02  0.100000  0.100000\n",
        hgid);
    return std::string(buf, n);
}

static std::string ale_generateControlALE(int dct, int nadv, int meth) {
    char buf[512]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_ALE\n"
        "$      DCT      NADV      METH      AFAC      BFAC      CFAC      DFAC      EFAC\n"
        "%10d%10d%10d  0.000000  0.000000  0.000000  0.000000  0.000000\n",
        dct, nadv, meth);
    return std::string(buf, n);
}

static std::string ale_generateAMMG(const std::vector<int>& pids) {
    std::string s = "*ALE_MULTI-MATERIAL_GROUP\n";
    s += "$      SID    IDTYPE\n";
    for (int pid : pids) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%10d         1\n", pid);
        s += buf;
    }
    return s;
}

static std::string ale_generateRefSystem() {
    return
        "*ALE_REFERENCE_SYSTEM_GROUP\n"
        "$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT\n"
        "         0         0         4         0         0         0\n";
}

static std::string ale_generateCLIS(const std::vector<int>& fsiPids,
    const std::vector<int>& alePids, int ctype, int direc, int nquad, double pfac) {
    std::string s;
    for (int fpid : fsiPids) {
        for (int apid : alePids) {
            char buf[1024]; int n = 0;
            n += snprintf(buf+n, sizeof(buf)-n,
                "*CONSTRAINED_LAGRANGE_IN_SOLID\n"
                "$    SLAVE    MASTER     SSTYP    MSTYP    NQUAD    CTYPE    DIREC     MCOUP\n"
                "%10d%10d         1         1%10d%10d%10d         0\n",
                fpid, apid, nquad, ctype, direc);
            n += snprintf(buf+n, sizeof(buf)-n,
                "$      MC      NORM  NORMTYP     DAMP        K     HMIN     HMAX     PFAC\n"
                "         0  0.000000         0  0.000000  0.000000  0.000000  0.000000%10.6f\n",
                pfac);
            n += snprintf(buf+n, sizeof(buf)-n,
                "$   ILEAK    PLEAK  LCIDPOR     NVENT   IBLOCK\n"
                "         0  0.000000         0         0         0\n");
            s += std::string(buf, n);
        }
    }
    return s;
}

static std::string ale_generateDetonation(int pid, double x, double y, double z, double lt) {
    char buf[256]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*INITIAL_DETONATION\n"
        "$      PID         X         Y         Z        LT\n"
        "%10d%10.4f%10.4f%10.4f%10.4f\n",
        pid, x, y, z, lt);
    return std::string(buf, n);
}

// ── runAle ───────────────────────────────────────────────────────────────────

int runAle(const std::string& yamlFile, ConsoleOutput& console) {
    std::string modelFile, outputFile;
    std::vector<AlePartEntry> aleEntries;
    std::vector<int> fsiPids;
    int    elform  = 11;
    int    dct     = 1, nadv = 1, meth = 2;
    int    ctype   = 2, direc = 1, nquad = 2;
    double pfac    = 0.1;
    bool   hasDet  = false;
    int    detPid  = 0;
    double detX = 0, detY = 0, detZ = 0, detLt = 0;

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
        bool inAleParts = false;
        bool inDetonation = false;
        AlePartEntry curEntry{0, ""};
        int aleIndent = 0;
        while (std::getline(yin, line)) {
            std::string raw = line;
            int indent = 0;
            for (char c : raw) { if (c == ' ') ++indent; else break; }
            std::string t = kw_trim(raw);
            if (t.empty() || t[0] == '#') continue;

            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = kw_trim(t.substr(0, colon));
            std::string val = kw_trim(t.substr(colon+1));
            { size_t h = val.find('#'); if (h != std::string::npos) val = kw_trim(val.substr(0, h)); }

            if (key == "ale_parts" && indent < 4) {
                inAleParts = true;
                inDetonation = false;
                aleIndent = indent;
                continue;
            }
            if (key == "detonation" && indent < 4) {
                inDetonation = true;
                inAleParts = false;
                hasDet = true;
                continue;
            }

            if (inAleParts) {
                if (indent <= aleIndent && key != "-" && t.find("- pid") == std::string::npos
                    && key != "pid" && key != "material") {
                    inAleParts = false;
                    if (curEntry.pid > 0) aleEntries.push_back(curEntry);
                    curEntry = {0, ""};
                } else {
                    if (t.find("- pid") != std::string::npos) {
                        if (curEntry.pid > 0) aleEntries.push_back(curEntry);
                        curEntry = {0, ""};
                        size_t pidColon = t.find("pid:");
                        if (pidColon != std::string::npos) {
                            std::string pv = kw_trim(t.substr(pidColon + 4));
                            size_t h = pv.find('#'); if (h != std::string::npos) pv = kw_trim(pv.substr(0, h));
                            try { curEntry.pid = std::stoi(pv); } catch (...) {}
                        }
                    } else if (key == "material") {
                        curEntry.material = val;
                    }
                    continue;
                }
            }

            if (inDetonation) {
                if (indent < 2 && key != "pid" && key != "x" && key != "y" && key != "z" && key != "lt") {
                    inDetonation = false;
                } else {
                    if (key == "pid") try { detPid = std::stoi(val); } catch (...) {}
                    else if (key == "x") try { detX = std::stod(val); } catch (...) {}
                    else if (key == "y") try { detY = std::stod(val); } catch (...) {}
                    else if (key == "z") try { detZ = std::stod(val); } catch (...) {}
                    else if (key == "lt") try { detLt = std::stod(val); } catch (...) {}
                    continue;
                }
            }

            if (key == "model")    modelFile  = val;
            else if (key == "output")   outputFile = val;
            else if (key == "fsi_pids") fsiPids    = ale_parsePidList(val);
            else if (key == "elform")   try { elform = std::stoi(val); } catch (...) {}
            else if (key == "dct")      try { dct    = std::stoi(val); } catch (...) {}
            else if (key == "nadv")     try { nadv   = std::stoi(val); } catch (...) {}
            else if (key == "meth")     try { meth   = std::stoi(val); } catch (...) {}
            else if (key == "ctype")    try { ctype  = std::stoi(val); } catch (...) {}
            else if (key == "direc")    try { direc  = std::stoi(val); } catch (...) {}
            else if (key == "nquad")    try { nquad  = std::stoi(val); } catch (...) {}
            else if (key == "pfac")     try { pfac   = std::stod(val); } catch (...) {}
        }
        if (curEntry.pid > 0) aleEntries.push_back(curEntry);
    }

    if (modelFile.empty())  { console.error("YAML missing 'model' field"); return 1; }
    if (outputFile.empty()) { console.error("YAML missing 'output' field"); return 1; }
    if (aleEntries.empty()) { console.error("YAML missing 'ale_parts' entries"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    std::vector<std::string> lines;
    {
        std::ifstream fin(modelPath);
        if (!fin.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(fin, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }

    auto partMap = ale_buildPartMap(lines);

    std::vector<int> alePids;
    std::set<int> alePidSet;
    for (const auto& e : aleEntries) {
        alePids.push_back(e.pid);
        alePidSet.insert(e.pid);
    }

    {
        std::string pidStr;
        for (const auto& e : aleEntries) {
            if (!pidStr.empty()) pidStr += ", ";
            pidStr += std::to_string(e.pid) + " (" + e.material + ")";
        }
        console.println("[ale] Model    : " + modelFile);
        console.println("[ale] Output   : " + outputFile);
        console.println("[ale] ALE PIDs : " + pidStr);
        if (!fsiPids.empty()) {
            std::string fs;
            for (int p : fsiPids) { if (!fs.empty()) fs += ", "; fs += std::to_string(p); }
            console.println("[ale] FSI PIDs : " + fs);
        }
        console.println("[ale] Unit sys : t/mm/s (preset values in MPa)");
    }

    {
        std::vector<AlePartEntry> validEntries;
        for (const auto& e : aleEntries) {
            if (partMap.find(e.pid) == partMap.end()) {
                console.error("[ale] PID " + std::to_string(e.pid) + " not found in model. Skipping.");
            } else {
                validEntries.push_back(e);
            }
        }
        aleEntries = validEntries;
        alePids.clear();
        alePidSet.clear();
        for (const auto& e : aleEntries) { alePids.push_back(e.pid); alePidSet.insert(e.pid); }
    }
    {
        std::vector<int> validFsi;
        for (int fp : fsiPids) {
            if (alePidSet.count(fp)) {
                console.error("[ale] FSI PID " + std::to_string(fp) + " overlaps with ALE PID. Self-coupling not allowed.");
            } else {
                validFsi.push_back(fp);
            }
        }
        fsiPids = validFsi;
    }
    if (aleEntries.empty()) {
        console.error("[ale] No valid ALE parts to process. Aborting.");
        return 1;
    }

    int maxMid = 0, maxEosid = 0, maxSecid = 0, maxHgid = 0;
    ale_findMaxIds(lines, maxMid, maxEosid, maxSecid, maxHgid);
    int nextMid = maxMid + 1;
    int nextEosid = maxEosid + 1;
    int nextSecid = maxSecid + 1;
    int nextHgid  = maxHgid + 1;
    int aleHgid = nextHgid++;

    std::string insertCards;
    bool hasHe = false;

    for (const auto& entry : aleEntries) {
        if (partMap.find(entry.pid) == partMap.end()) continue;
        const auto& info = partMap[entry.pid];

        if (ale_isSharedSection(partMap, info.secid, alePidSet)) {
            int newSecid = nextSecid++;
            std::string secCard = ale_duplicateSection(lines, info.secid, newSecid, elform);
            if (!secCard.empty()) {
                insertCards += secCard;
                ale_updatePartField(lines, entry.pid, 10, newSecid);
                console.println("[ale] NewSec   : SECID=" + std::to_string(newSecid) +
                    " (copied from " + std::to_string(info.secid) +
                    ", shared) ELFORM -> " + std::to_string(elform));
            } else {
                console.println("[WARNING]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) +
                    " — *SECTION_SOLID not found (shell element?)");
            }
        } else {
            int oldElform = ale_modifySectionElform(lines, info.secid, elform);
            if (oldElform == elform) {
                console.println("[INFO]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) + " already ELFORM=" + std::to_string(elform));
            } else if (oldElform >= 0) {
                console.println("[ale] Modified : *SECTION_SOLID SECID=" + std::to_string(info.secid) +
                    " ELFORM=" + std::to_string(oldElform) + " -> " + std::to_string(elform) +
                    "  (PID=" + std::to_string(entry.pid) + ")");
            } else {
                console.println("[WARNING]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) +
                    " — *SECTION_SOLID not found (shell element?)");
            }
        }

        int newMid = nextMid++;
        int newEosid = (entry.material != "vacuum") ? nextEosid++ : 0;

        std::string matCards;
        if (ale_isPreset(entry.material)) {
            matCards = ale_presetMaterial(entry.material, newMid, newEosid);
        } else {
            std::string bundlePath = resolvePath(entry.material);
            matCards = ale_customMaterial(bundlePath, newMid, newEosid);
            if (matCards.empty()) {
                console.error("[ale] Cannot load bundle: " + entry.material);
                continue;
            }
        }
        insertCards += matCards;

        ale_updatePartField(lines, entry.pid, 20, newMid);
        ale_updatePartField(lines, entry.pid, 30, newEosid);
        ale_updatePartField(lines, entry.pid, 40, aleHgid);

        std::string matName, eosName;
        std::string matLower = kw_trim(entry.material);
        std::transform(matLower.begin(), matLower.end(), matLower.begin(), [](unsigned char c){ return (char)std::tolower(c); });
        if (matLower == "tnt" || matLower == "c4") {
            matName = "*MAT_HIGH_EXPLOSIVE_BURN"; eosName = "*EOS_JWL"; hasHe = true;
        } else if (matLower == "vacuum") {
            matName = "*MAT_VACUUM"; eosName = "(none)";
        } else if (matLower == "air" || matLower == "nitrogen" || matLower == "argon") {
            matName = "*MAT_NULL"; eosName = "*EOS_LINEAR_POLYNOMIAL";
        } else if (ale_isPreset(entry.material)) {
            matName = "*MAT_NULL"; eosName = "*EOS_GRUNEISEN";
        } else {
            matName = "custom"; eosName = "custom";
        }
        console.println("[ale] Material : PID=" + std::to_string(entry.pid) +
            " -> " + matName + " (MID=" + std::to_string(newMid) + ") + " +
            eosName + " (EOSID=" + std::to_string(newEosid) + ")");
    }

    insertCards += ale_generateHourglass(aleHgid);
    console.println("[ale] Hourglass: HGID=" + std::to_string(aleHgid) + " (IHQ=3, Flanagan-Belytschko)");

    {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, "*CONTROL_ALE");
        if (lines.size() < before) console.println("[WARNING]  Existing *CONTROL_ALE replaced.");
    }
    insertCards += ale_generateControlALE(dct, nadv, meth);
    console.println("[ale] Inserted : *CONTROL_ALE (DCT=" + std::to_string(dct) +
        ", NADV=" + std::to_string(nadv) + ", METH=" + std::to_string(meth) + ")");

    {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, "*ALE_MULTI-MATERIAL_GROUP");
        if (lines.size() < before) console.println("[WARNING]  Existing *ALE_MULTI-MATERIAL_GROUP replaced.");
    }
    insertCards += ale_generateAMMG(alePids);
    console.println("[ale] Inserted : *ALE_MULTI-MATERIAL_GROUP (" +
        std::to_string(alePids.size()) + " groups)");

    {
        size_t before = lines.size();
        lines = kw_removeKeyword(lines, "*ALE_REFERENCE_SYSTEM_GROUP");
        if (lines.size() < before) console.println("[WARNING]  Existing *ALE_REFERENCE_SYSTEM_GROUP replaced.");
    }
    insertCards += ale_generateRefSystem();
    console.println("[ale] Inserted : *ALE_REFERENCE_SYSTEM_GROUP (PRTYPE=4)");

    if (!fsiPids.empty()) {
        lines = kw_removeKeyword(lines, "*CONSTRAINED_LAGRANGE_IN_SOLID");
        insertCards += ale_generateCLIS(fsiPids, alePids, ctype, direc, nquad, pfac);
        int numClis = (int)fsiPids.size() * (int)alePids.size();
        console.println("[ale] Inserted : *CONSTRAINED_LAGRANGE_IN_SOLID x" +
            std::to_string(numClis));
    }

    if (hasDet && detPid > 0) {
        insertCards += ale_generateDetonation(detPid, detX, detY, detZ, detLt);
        console.println("[ale] Inserted : *INITIAL_DETONATION (PID=" +
            std::to_string(detPid) + ")");
    } else if (hasHe && !hasDet) {
        console.println("[WARNING]  HE preset used but no 'detonation:' section in YAML");
    }

    kw_insertBeforeEnd(lines, insertCards);

    std::ofstream outf(outPath);
    if (!outf.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) outf << ln << "\n";
    console.println("[ale] Done     -> " + outputFile);
    return 0;
}
