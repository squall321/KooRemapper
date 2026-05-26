#include "hfdamp.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <array>
#include <map>
#include <set>
#include <cmath>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <cstdio>
#include <climits>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

using KooRemapper::ConsoleOutput;

// ============================================================
// String helpers
// ============================================================

static std::string hf_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string hf_upper(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)toupper((unsigned char)c);
    return r;
}

static std::vector<std::string> hf_splitWS(const std::string& s) {
    std::vector<std::string> toks;
    std::istringstream ss(s);
    std::string t;
    while (ss >> t) toks.push_back(t);
    return toks;
}

// 10-char fixed-width field
static std::string hf_field10(const std::string& line, int idx) {
    int pos = idx * 10;
    if (pos >= (int)line.size()) return "";
    int len = std::min(10, (int)line.size() - pos);
    return hf_trim(line.substr(pos, len));
}

static double hf_parseDouble(const std::string& s) {
    try { return std::stod(hf_trim(s)); } catch (...) { return 0.0; }
}
static int hf_parseInt(const std::string& s) {
    try { return std::stoi(hf_trim(s)); } catch (...) { return 0; }
}

// Format float in 12-char scientific notation
static std::string hf_fmtSci(double v) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%12.4E", v);
    return std::string(buf);
}
// 10-char integer field
static std::string hf_fmtInt10(int v) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%10d", v);
    return std::string(buf);
}

// ============================================================
// Geometry helpers
// ============================================================

struct Vec3d { double x, y, z; };

static double hf_dist(const Vec3d& a, const Vec3d& b) {
    double dx = a.x-b.x, dy = a.y-b.y, dz = a.z-b.z;
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

// Hexahedron (8 nodes) characteristic length = min edge length
// LS-DYNA HEX8 node ordering: 1-2-3-4 bottom, 5-6-7-8 top
//   Edges: bottom(0-1,1-2,2-3,3-0), top(4-5,5-6,6-7,7-4), vertical(0-4,1-5,2-6,3-7)
static double hf_hexMinEdge(const Vec3d n[8]) {
    static const int edges[12][2] = {
        {0,1},{1,2},{2,3},{3,0},   // bottom ring
        {4,5},{5,6},{6,7},{7,4},   // top ring
        {0,4},{1,5},{2,6},{3,7}    // verticals
    };
    double minL = 1e30;
    for (auto& e : edges) {
        double l = hf_dist(n[e[0]], n[e[1]]);
        if (l < minL) minL = l;
    }
    return minL;
}

// Quad4 characteristic length = sqrt(area)
// area = 0.5 * |d1 × d2| where d1,d2 are diagonals
static double hf_quadCharLen(const Vec3d n[4]) {
    // Diagonals: n0-n2 and n1-n3
    Vec3d d1 = {n[2].x-n[0].x, n[2].y-n[0].y, n[2].z-n[0].z};
    Vec3d d2 = {n[3].x-n[1].x, n[3].y-n[1].y, n[3].z-n[1].z};
    // cross product
    double cx = d1.y*d2.z - d1.z*d2.y;
    double cy = d1.z*d2.x - d1.x*d2.z;
    double cz = d1.x*d2.y - d1.y*d2.x;
    double area = 0.5 * std::sqrt(cx*cx + cy*cy + cz*cz);
    return (area > 0.0) ? std::sqrt(area) : 0.0;
}

// ============================================================
// Material data
// ============================================================

struct MatData {
    double E   = 0.0;   // Young's modulus
    double PR  = 0.0;   // Poisson's ratio
    double RHO = 0.0;   // density
    bool   valid = false;
};

// P-wave speed for isotropic solid
static double hf_pWaveSpeed(const MatData& m) {
    if (!m.valid || m.RHO <= 0.0 || m.E <= 0.0) return 0.0;
    double nu = m.PR;
    // c_L = sqrt(E(1-nu) / rho(1+nu)(1-2nu))
    double denom = m.RHO * (1.0 + nu) * (1.0 - 2.0*nu);
    if (denom <= 0.0) return 0.0;
    return std::sqrt(m.E * (1.0 - nu) / denom);
}

// Plane-stress membrane wave speed for shells: c = sqrt(E / rho(1-nu^2))
static double hf_shellWaveSpeed(const MatData& m) {
    if (!m.valid || m.RHO <= 0.0 || m.E <= 0.0) return 0.0;
    double nu = m.PR;
    double denom = m.RHO * (1.0 - nu*nu);
    if (denom <= 0.0) return 0.0;
    return std::sqrt(m.E / denom);
}

// ============================================================
// Minimal K-file parser for selective mode
// Parses: nodes, solid elements, shell elements, parts, materials
// ============================================================

struct HFParseResult {
    // nodeId → position
    std::map<int, Vec3d> nodes;
    // eid → {pid, nodeIds[8]}  (solid HEX8; unused slots = -1 for tet/wedge)
    std::map<int, std::pair<int, std::array<int,8>>> solidElems;
    // eid → {pid, nodeIds[4]}
    std::map<int, std::pair<int, std::array<int,4>>> shellElems;
    // pid → mid
    std::map<int, int> partMid;
    // mid → material
    std::map<int, MatData> mats;
    // max set ID found
    int maxSetId = 0;
};

static HFParseResult hf_parseKFile(const std::vector<std::string>& lines) {
    HFParseResult res;

    std::string section;
    bool inPartTitle  = false;
    bool inMatTitle   = false;
    bool inSetTitle   = false;  // true if *SET_*_TITLE: skip one title line before SID
    int  matLineIdx   = 0;   // which material data line we're on
    int  curMatId     = 0;
    MatData curMat;

    for (const auto& raw : lines) {
        std::string line = raw;
        if (!line.empty() && line.back() == '\r') line.pop_back();

        // Keywords
        if (!line.empty() && line[0] == '*') {
            std::string kw = hf_upper(hf_trim(line));
            // Strip options to get base keyword
            size_t us = kw.find('_', 1);
            inPartTitle = false; inMatTitle = false; matLineIdx = 0;

            if (kw == "*NODE") { section = "NODE"; }
            else if (kw.substr(0,15) == "*ELEMENT_SOLID") { section = "SOLID"; }
            else if (kw.substr(0,14) == "*ELEMENT_SHELL") { section = "SHELL"; }
            else if (kw.substr(0,5) == "*PART") { section = "PART"; inPartTitle = true; }
            else if (kw.substr(0,12) == "*MAT_ELASTIC") { section = "MAT"; inMatTitle = false; curMat = MatData(); matLineIdx = 0; }
            else if (kw.substr(0,5) == "*MAT_") {
                // Try to catch MAT_024 / MAT_PIECEWISE etc. (same Card1 layout as MAT_ELASTIC)
                // Filter out ones that definitely don't have E,PR,RHO on card1
                if (kw.find("MAT_NULL") == std::string::npos &&
                    kw.find("MAT_RIGID") == std::string::npos &&
                    kw.find("MAT_SPRING") == std::string::npos &&
                    kw.find("MAT_DAMPER") == std::string::npos &&
                    kw.find("MAT_VACUUM") == std::string::npos &&
                    kw.find("MAT_HE_BURN") == std::string::npos &&
                    kw.find("MAT_THERMAL") == std::string::npos) {
                    section = "MAT"; curMat = MatData(); matLineIdx = 0;
                } else {
                    section = "OTHER";
                }
            }
            else if (kw.substr(0,9) == "*SET_PART") {
                section = "SETPART";
                // _TITLE suffix: first data line is a title string, not SID
                inSetTitle = (kw.find("_TITLE") != std::string::npos);
            }
            else { section = "OTHER"; }
            (void)us;
            continue;
        }
        // Skip comments
        if (!line.empty() && line[0] == '$') continue;
        if (hf_trim(line).empty()) continue;

        // --- NODE ---
        if (section == "NODE") {
            // NID X Y Z (free format or fixed)
            auto toks = hf_splitWS(line);
            if (toks.size() >= 4) {
                int nid = std::stoi(toks[0]);
                Vec3d p;
                p.x = std::stod(toks[1]);
                p.y = std::stod(toks[2]);
                p.z = std::stod(toks[3]);
                res.nodes[nid] = p;
            }
        }
        // --- SOLID ---
        else if (section == "SOLID") {
            auto toks = hf_splitWS(line);
            if (toks.size() >= 10) {
                int eid = std::stoi(toks[0]);
                int pid = std::stoi(toks[1]);
                std::array<int,8> ns; ns.fill(0);
                for (int i = 0; i < 8; ++i) ns[i] = std::stoi(toks[2+i]);
                res.solidElems[eid] = std::make_pair(pid, ns);
            } else if (toks.size() >= 6) {
                int eid = std::stoi(toks[0]);
                int pid = std::stoi(toks[1]);
                std::array<int,8> ns; ns.fill(0);
                for (int i = 0; i < (int)toks.size()-2 && i < 8; ++i)
                    ns[i] = std::stoi(toks[2+i]);
                res.solidElems[eid] = std::make_pair(pid, ns);
            }
        }
        // --- SHELL ---
        else if (section == "SHELL") {
            auto toks = hf_splitWS(line);
            if (toks.size() >= 6) {
                int eid = std::stoi(toks[0]);
                int pid = std::stoi(toks[1]);
                std::array<int,4> ns; ns.fill(0);
                for (int i = 0; i < 4; ++i)
                    ns[i] = (2+i < (int)toks.size()) ? std::stoi(toks[2+i]) : ns[std::max(0,i-1)];
                res.shellElems[eid] = std::make_pair(pid, ns);
            }
        }
        // --- PART ---
        else if (section == "PART") {
            if (inPartTitle) { inPartTitle = false; continue; } // skip title line
            // data: PID SECID MID
            auto toks = hf_splitWS(line);
            if (toks.size() >= 3) {
                int pid = std::stoi(toks[0]);
                int mid = std::stoi(toks[2]);
                res.partMid[pid] = mid;
            }
        }
        // --- MAT (card 1: MID RHO E PR ...) ---
        else if (section == "MAT") {
            matLineIdx++;
            if (matLineIdx == 1) {
                // Card 1: MID RHO E PR (10-char fields)
                curMatId = hf_parseInt(hf_field10(line, 0));
                curMat.RHO = hf_parseDouble(hf_field10(line, 1));
                curMat.E   = hf_parseDouble(hf_field10(line, 2));
                curMat.PR  = hf_parseDouble(hf_field10(line, 3));
                curMat.valid = (curMat.E > 0.0 && curMat.RHO > 0.0);
                res.mats[curMatId] = curMat;
            }
        }
        // --- SET_PART (find max SID) ---
        else if (section == "SETPART") {
            if (inSetTitle) {
                inSetTitle = false; // this line is the title string — skip, read SID next
            } else {
                auto toks = hf_splitWS(line);
                if (!toks.empty()) {
                    try {
                        int sid = std::stoi(toks[0]);
                        if (sid > res.maxSetId) res.maxSetId = sid;
                    } catch (...) {}
                }
                section = "OTHER"; // done — only need the SID line
            }
        }
    }
    return res;
}

// ============================================================
// Selective mode: find parts with element dt <= dt_target
// ============================================================

static std::vector<int> hf_findTargetParts(
    const HFParseResult& pr,
    const HFDampConfig& cfg,
    ConsoleOutput& console)
{
    // pid → minimum element dt found
    std::map<int, double> partMinDt;

    // Build pid→mid→material lookup
    // (partMid and mats already in pr)

    // Helper: get wave speed for a pid
    auto getWaveSpeed = [&](int pid, bool isShell) -> double {
        auto it = pr.partMid.find(pid);
        if (it == pr.partMid.end()) return 0.0;
        auto jt = pr.mats.find(it->second);
        if (jt == pr.mats.end()) return 0.0;
        return isShell ? hf_shellWaveSpeed(jt->second) : hf_pWaveSpeed(jt->second);
    };

    // Solid elements
    for (auto& kv : pr.solidElems) {
        int pid = kv.second.first;
        const auto& ns = kv.second.second;
        double c = getWaveSpeed(pid, false);
        if (c <= 0.0) continue;

        // Gather node positions
        Vec3d pts[8];
        bool ok = true;
        for (int i = 0; i < 8; ++i) {
            if (ns[i] == 0) { pts[i] = pts[0]; continue; } // degenerate
            auto it = pr.nodes.find(ns[i]);
            if (it == pr.nodes.end()) { ok = false; break; }
            pts[i] = it->second;
        }
        if (!ok) continue;

        double L = hf_hexMinEdge(pts);
        if (L <= 0.0) continue;
        double dt_e = cfg.tssfac * L / c;

        auto it = partMinDt.find(pid);
        if (it == partMinDt.end() || dt_e < it->second)
            partMinDt[pid] = dt_e;
    }

    // Shell elements
    for (auto& kv : pr.shellElems) {
        int pid = kv.second.first;
        const auto& ns = kv.second.second;
        double c = getWaveSpeed(pid, true);
        if (c <= 0.0) continue;

        Vec3d pts[4] = {};
        bool ok = true;
        // First, find node 0
        {
            auto it0 = pr.nodes.find(ns[0]);
            if (it0 == pr.nodes.end()) { ok = false; }
            else pts[0] = it0->second;
        }
        if (!ok) continue;
        for (int i = 1; i < 4; ++i) {
            if (ns[i] == 0 || ns[i] == ns[0]) { pts[i] = pts[0]; continue; } // degenerate (tria3)
            auto it = pr.nodes.find(ns[i]);
            if (it == pr.nodes.end()) { ok = false; break; }
            pts[i] = it->second;
        }
        if (!ok) continue;

        double L = hf_quadCharLen(pts);
        if (L <= 0.0) continue;
        double dt_e = cfg.tssfac * L / c;

        auto it = partMinDt.find(pid);
        if (it == partMinDt.end() || dt_e < it->second)
            partMinDt[pid] = dt_e;
    }

    // Collect PIDs where min dt <= dt_target
    std::vector<int> targetPids;
    for (auto& kv : partMinDt) {
        if (kv.second <= cfg.dtTarget) {
            targetPids.push_back(kv.first);
            char buf[128];
            snprintf(buf, sizeof(buf), "  [selective] PID=%-5d min_dt=%.3e <= %.3e → targeted",
                     kv.first, kv.second, cfg.dtTarget);
            console.println(std::string(buf));
        }
    }
    std::sort(targetPids.begin(), targetPids.end());

    // Warn about parts with unknown material
    for (auto& kv : pr.partMid) {
        if (pr.mats.find(kv.second) == pr.mats.end()) {
            char buf[80];
            snprintf(buf, sizeof(buf), "  [selective] PID=%-5d MID=%-5d unknown material, skipped",
                     kv.first, kv.second);
            console.println(std::string(buf));
        }
    }

    return targetPids;
}

// ============================================================
// Core: insert DAMPING_FREQUENCY_RANGE_DEFORM keyword
// ============================================================

int hfdamp_apply(std::vector<std::string>& lines,
                 const HFDampConfig& cfg,
                 int& maxSetId,
                 ConsoleOutput& console)
{
    if (cfg.dtTarget <= 0.0) {
        console.error("hfdamp: dt_target must be > 0");
        return -1;
    }
    if (cfg.cdamp <= 0.0 || cfg.cdamp > 1.0) {
        console.error("hfdamp: cdamp must be in (0, 1]");
        return -1;
    }
    if (cfg.fhighRatio < 2.0) {
        console.error("hfdamp: fhigh_ratio must be >= 2");
        return -1;
    }

    // Compute frequency band
    double fLow  = 1.0 / (2.0 * cfg.dtTarget);
    double fHigh = fLow * cfg.fhighRatio;

    char buf[256];
    snprintf(buf, sizeof(buf),
             "[hfdamp] dt_target=%.3e  FLOW=%.4E Hz  FHIGH=%.4E Hz  CDAMP=%.4f",
             cfg.dtTarget, fLow, fHigh, cfg.cdamp);
    console.println(std::string(buf));

    // Selective mode: find target PIDs
    int psid = 0; // 0 = all parts
    std::vector<int> targetPids;

    if (cfg.mode == "selective") {
        HFParseResult pr = hf_parseKFile(lines);
        // Update maxSetId from what we found in the file
        if (pr.maxSetId > maxSetId) maxSetId = pr.maxSetId;
        targetPids = hf_findTargetParts(pr, cfg, console);

        if (targetPids.empty()) {
            console.println("[hfdamp] Selective mode: no parts found with dt <= dt_target");
            console.println("[hfdamp] Falling back to global (PSID=0)");
        } else {
            psid = ++maxSetId;
            snprintf(buf, sizeof(buf),
                     "[hfdamp] Selective mode: %d part(s) targeted → SET_PART SID=%d",
                     (int)targetPids.size(), psid);
            console.println(std::string(buf));
        }
    }

    // Build the keyword lines to insert
    std::vector<std::string> insert;

    // --- SET_PART_LIST for selective mode ---
    if (psid > 0) {
        insert.push_back("*SET_PART_LIST_TITLE");
        snprintf(buf, sizeof(buf), "HFDamp parts (dt<=%g)", cfg.dtTarget);
        insert.push_back(std::string(buf));
        insert.push_back(hf_fmtInt10(psid)); // SID on its own line
        // PIDs: 8 per line, 10-char fields
        std::string pidLine;
        for (int i = 0; i < (int)targetPids.size(); ++i) {
            pidLine += hf_fmtInt10(targetPids[i]);
            if ((i+1) % 8 == 0 || i+1 == (int)targetPids.size()) {
                insert.push_back(pidLine);
                pidLine.clear();
            }
        }
        insert.push_back("$");
    }

    // --- DAMPING_FREQUENCY_RANGE_DEFORM ---
    insert.push_back("*DAMPING_FREQUENCY_RANGE_DEFORM");
    insert.push_back("$#     CDAMP          FLOW         FHIGH          PSID            PIDREL        IFLG      ICARD2");
    // Card 1: CDAMP FLOW FHIGH PSID (blank) PIDREL IFLG ICARD2
    // 10-char fields
    snprintf(buf, sizeof(buf), "%10.4E%10.4E%10.4E%10d%10s%10d%10d%10d",
             cfg.cdamp, fLow, fHigh, psid, "", 0, 0, 0);
    insert.push_back(std::string(buf));

    // Find *END and insert before it
    int endIdx = -1;
    for (int i = (int)lines.size()-1; i >= 0; --i) {
        std::string kw = hf_upper(hf_trim(lines[i]));
        if (kw == "*END") { endIdx = i; break; }
    }

    if (endIdx < 0) {
        // No *END found: append at end
        lines.insert(lines.end(), insert.begin(), insert.end());
        lines.push_back("*END");
    } else {
        lines.insert(lines.begin() + endIdx, insert.begin(), insert.end());
    }

    return 0;
}

// ============================================================
// Standalone command: runHFDamp
// ============================================================

int runHFDamp(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) {
        console.error("Cannot open config: " + yamlFile);
        return 1;
    }

    // Determine config directory for relative path resolution
    std::string configDir;
    {
        size_t sl = yamlFile.find_last_of("/\\");
        if (sl != std::string::npos) configDir = yamlFile.substr(0, sl);
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':'))
            return configDir + "/" + p;
        return p;
    };

    std::string modelFile, outputFile;
    HFDampConfig cfg;

    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string t = hf_trim(line);
        if (t.empty() || t[0] == '#') continue;

        size_t colon = t.find(':');
        if (colon == std::string::npos) continue;
        std::string key = hf_trim(t.substr(0, colon));
        std::string val = hf_trim(t.substr(colon + 1));
        // Strip inline comment
        size_t hsh = val.find('#');
        if (hsh != std::string::npos) val = hf_trim(val.substr(0, hsh));
        if (val.empty()) continue;

        try {
            if      (key == "model")        modelFile       = val;
            else if (key == "output")       outputFile      = val;
            else if (key == "dt_target")    cfg.dtTarget    = std::stod(val);
            else if (key == "cdamp")        cfg.cdamp       = std::stod(val);
            else if (key == "fhigh_ratio")  cfg.fhighRatio  = std::stod(val);
            else if (key == "mode")         cfg.mode        = val;
            else if (key == "tssfac")       cfg.tssfac      = std::stod(val);
        } catch (...) {}
    }

    if (modelFile.empty())  { console.error("hfdamp: 'model' not specified");     return 1; }
    if (outputFile.empty()) { console.error("hfdamp: 'output' not specified");    return 1; }
    if (cfg.dtTarget <= 0.0){ console.error("hfdamp: 'dt_target' not specified"); return 1; }

    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    // Read model
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

    console.println("[hfdamp] Model  : " + modelPath);
    console.println("[hfdamp] Output : " + outPath);
    console.println("[hfdamp] Mode   : " + cfg.mode);

    // Find max set ID in file (handles both plain and _TITLE variants)
    int maxSetId = 0;
    {
        bool inSetSection = false;
        bool setHasTitle  = false;
        for (auto& l : lines) {
            std::string kw = hf_upper(hf_trim(l));
            if (!l.empty() && l[0] == '*') {
                if (kw.substr(0,4) == "*SET") {
                    inSetSection = true;
                    setHasTitle  = (kw.find("_TITLE") != std::string::npos);
                } else {
                    inSetSection = false;
                }
                continue;
            }
            if (!inSetSection || l[0] == '$') continue;
            if (setHasTitle) {
                setHasTitle = false; // skip title line, read SID on next iteration
                continue;
            }
            try {
                int sid = std::stoi(hf_trim(l));
                if (sid > maxSetId) maxSetId = sid;
            } catch (...) {}
            inSetSection = false;
        }
    }

    // Apply damping
    int rc = hfdamp_apply(lines, cfg, maxSetId, console);
    if (rc != 0) return rc;

    // Write output
    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (auto& l : lines) out << l << "\n";

    console.println("[hfdamp] Done   -> " + outPath);
    return 0;
}
