#include "cnrb2solid.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <map>
#include <set>
#include <cmath>
#include <algorithm>
#include <sstream>
#include <fstream>
#include <cstdio>

using KooRemapper::ConsoleOutput;

// ============================================================
// Internal helpers
// ============================================================

static std::vector<std::string> cs_splitWS(const std::string& s) {
    std::vector<std::string> toks;
    std::istringstream ss(s);
    std::string t;
    while (ss >> t) toks.push_back(t);
    return toks;
}

static std::string cs_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string cs_upper(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)toupper((unsigned char)c);
    return r;
}

static int cs_parseInt(const std::string& s) {
    try { return std::stoi(cs_trim(s)); } catch (...) { return 0; }
}

static double cs_parseDouble(const std::string& s) {
    try { return std::stod(cs_trim(s)); } catch (...) { return 0.0; }
}

// Fixed-width 10-char field token
static std::string cs_field10(const std::string& line, int idx) {
    int pos = idx * 10;
    if (pos >= (int)line.size()) return "";
    int len = std::min(10, (int)line.size() - pos);
    return cs_trim(line.substr(pos, len));
}

// ============================================================
// 3x3 symmetric matrix analytic eigendecomposition (Cardano)
// Returns eigenvalues sorted descending; eigenvectors in rows of evec[3][3]
// ============================================================

static void cs_eigen3x3sym(
    double A[3][3],
    double eigenvalues[3],
    double eigenvectors[3][3])
{
    // Characteristic polynomial: λ³ - p1λ² + p2λ - p3 = 0
    double a = A[0][0], b = A[1][1], c = A[2][2];
    double d = A[0][1], e = A[0][2], f = A[1][2];

    double p1 = a + b + c;
    double p2 = a*b + a*c + b*c - d*d - e*e - f*f;
    double p3 = a*(b*c - f*f) - d*(d*c - f*e) + e*(d*f - b*e);

    // Depressed cubic: t³ + pt + q = 0  where t = λ - p1/3
    double q_ = p1/3.0;
    double p  = p2 - p1*p1/3.0;          // negative for positive semi-definite
    double q  = 2.0*p1*p1*p1/27.0 - p1*p2/3.0 + p3;

    double D = -4.0*p*p*p - 27.0*q*q;    // discriminant * -1/4

    // Three real roots (covariance matrix is positive semi-definite)
    double lam[3];
    if (D >= 0.0) {
        double m = 2.0 * std::sqrt(-p / 3.0);
        double theta = std::acos(3.0*q / (p * m)) / 3.0;
        static const double TWO_PI_3 = 2.0 * M_PI / 3.0;
        lam[0] = m * std::cos(theta)              + q_;
        lam[1] = m * std::cos(theta - TWO_PI_3)   + q_;
        lam[2] = m * std::cos(theta - 2*TWO_PI_3) + q_;
    } else {
        // Fallback: all equal (degenerate, e.g., single point)
        lam[0] = lam[1] = lam[2] = q_;
    }

    // Sort descending
    if (lam[0] < lam[1]) std::swap(lam[0], lam[1]);
    if (lam[0] < lam[2]) std::swap(lam[0], lam[2]);
    if (lam[1] < lam[2]) std::swap(lam[1], lam[2]);
    eigenvalues[0] = lam[0];
    eigenvalues[1] = lam[1];
    eigenvalues[2] = lam[2];

    // Eigenvectors via null space of (A - λI)
    for (int k = 0; k < 3; ++k) {
        double M[3][3] = {
            {A[0][0]-lam[k], A[0][1],        A[0][2]       },
            {A[1][0],        A[1][1]-lam[k],  A[1][2]       },
            {A[2][0],        A[2][1],         A[2][2]-lam[k]}
        };
        // Cross product of two rows to find null vector
        double v[3] = {0, 0, 0};
        for (int r1 = 0; r1 < 3 && v[0]==0 && v[1]==0 && v[2]==0; ++r1) {
            for (int r2 = r1+1; r2 < 3; ++r2) {
                v[0] = M[r1][1]*M[r2][2] - M[r1][2]*M[r2][1];
                v[1] = M[r1][2]*M[r2][0] - M[r1][0]*M[r2][2];
                v[2] = M[r1][0]*M[r2][1] - M[r1][1]*M[r2][0];
                double nm = std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
                if (nm > 1e-12) { v[0]/=nm; v[1]/=nm; v[2]/=nm; break; }
                v[0] = v[1] = v[2] = 0.0;
            }
        }
        if (v[0]==0 && v[1]==0 && v[2]==0) {
            // Degenerate: use canonical basis
            v[k] = 1.0;
        }
        eigenvectors[k][0] = v[0];
        eigenvectors[k][1] = v[1];
        eigenvectors[k][2] = v[2];
    }
}

// ============================================================
// Vector helpers
// ============================================================

struct Vec3 { double x, y, z; };

static Vec3 cs_add(Vec3 a, Vec3 b) { return {a.x+b.x, a.y+b.y, a.z+b.z}; }
static Vec3 cs_sub(Vec3 a, Vec3 b) { return {a.x-b.x, a.y-b.y, a.z-b.z}; }
static Vec3 cs_scale(Vec3 a, double s) { return {a.x*s, a.y*s, a.z*s}; }
static double cs_dot(Vec3 a, Vec3 b) { return a.x*b.x + a.y*b.y + a.z*b.z; }
static Vec3 cs_cross(Vec3 a, Vec3 b) {
    return {a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x};
}
static Vec3 cs_norm(Vec3 a) {
    double n = std::sqrt(cs_dot(a,a));
    if (n < 1e-15) return {1,0,0};
    return {a.x/n, a.y/n, a.z/n};
}

// ============================================================
// Data structures
// ============================================================

struct CnrbDef {
    int pid   = 0;
    int nsid  = 0;
    int pnode = 0;
    std::string title;
    bool hasTitle = false;
    size_t lineStart = 0;  // index of keyword line in rawLines
    size_t lineEnd   = 0;  // one past last line of this block
};

struct NodeXYZ {
    double x = 0, y = 0, z = 0;
};

// ============================================================
// Parsing helpers (operate on raw line buffer)
// ============================================================

static std::map<int, NodeXYZ> cs_parseNodes(const std::vector<std::string>& lines) {
    std::map<int, NodeXYZ> nodes;
    bool inNode = false;
    for (const auto& ln : lines) {
        std::string tr = cs_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            inNode = (cs_upper(tr).rfind("*NODE", 0) == 0 &&
                      cs_upper(tr).find("SET") == std::string::npos);
            continue;
        }
        if (!inNode || tr[0] == '$') continue;
        auto toks = cs_splitWS(ln);
        if (toks.size() >= 4) {
            int nid = cs_parseInt(toks[0]);
            if (nid > 0) {
                nodes[nid] = {cs_parseDouble(toks[1]),
                              cs_parseDouble(toks[2]),
                              cs_parseDouble(toks[3])};
            }
        }
    }
    return nodes;
}

static std::map<int, std::vector<int>> cs_parseNodeSets(const std::vector<std::string>& lines) {
    std::map<int, std::vector<int>> sets;
    bool inSet = false;
    bool hasTitle = false, titleDone = false, headerDone = false;
    int curSid = 0;
    for (const auto& ln : lines) {
        std::string tr = cs_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = cs_upper(tr);
            inSet = (up.rfind("*SET_NODE_LIST", 0) == 0);
            if (inSet) {
                hasTitle   = (up.find("_TITLE") != std::string::npos);
                titleDone  = false;
                headerDone = false;
                curSid     = 0;
            }
            continue;
        }
        if (!inSet || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if (!headerDone) {
            // First data line: SID DA1 DA2 DA3 DA4 ...
            curSid = cs_parseInt(cs_field10(ln, 0));
            headerDone = true;
            sets[curSid]; // create entry
            continue;
        }
        // Node ID lines: 8 per line, 10-char fields
        for (int i = 0; i < 8; ++i) {
            std::string tok = cs_field10(ln, i);
            if (tok.empty()) break;
            int nid = cs_parseInt(tok);
            if (nid > 0) sets[curSid].push_back(nid);
        }
    }
    return sets;
}

static std::vector<CnrbDef> cs_parseCnrbs(const std::vector<std::string>& lines) {
    std::vector<CnrbDef> cnrbs;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string tr = cs_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = cs_upper(tr);
        if (up.rfind("*CONSTRAINED_NODAL_RIGID_BODY", 0) != 0) continue;

        CnrbDef def;
        def.hasTitle  = (up.find("_TITLE") != std::string::npos);
        def.lineStart = i;

        size_t j = i + 1;
        if (def.hasTitle) {
            // skip title line (non-comment, non-keyword)
            while (j < lines.size()) {
                std::string jt = cs_trim(lines[j]);
                if (!jt.empty() && jt[0] != '$') {
                    def.title = jt; ++j; break;
                }
                ++j;
            }
        }
        // skip comment lines to reach data line
        while (j < lines.size() && !cs_trim(lines[j]).empty() && cs_trim(lines[j])[0] == '$') ++j;

        if (j < lines.size()) {
            // Data line: PID CID NSID PNODE ...  (10-char fields)
            def.pid   = cs_parseInt(cs_field10(lines[j], 0));
            // field 1 = CID (unused)
            def.nsid  = cs_parseInt(cs_field10(lines[j], 2));
            def.pnode = cs_parseInt(cs_field10(lines[j], 3));
            ++j;
        }

        // Block ends at next keyword line
        while (j < lines.size()) {
            std::string jt = cs_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*') break;
            ++j;
        }
        def.lineEnd = j;
        cnrbs.push_back(def);
    }
    return cnrbs;
}

// ============================================================
// PCA: detect cylinder axis from node cloud
// ============================================================

static Vec3 cs_detectAxis(const std::vector<NodeXYZ>& nodes,
                           const std::string& axisDir) {
    if (axisDir == "x") return {1,0,0};
    if (axisDir == "y") return {0,1,0};
    if (axisDir == "z") return {0,0,1};

    if (nodes.empty()) return {0,0,1};

    // Centroid
    double cx = 0, cy = 0, cz = 0;
    for (const auto& n : nodes) { cx += n.x; cy += n.y; cz += n.z; }
    cx /= nodes.size(); cy /= nodes.size(); cz /= nodes.size();

    // Covariance matrix (symmetric 3x3)
    double cov[3][3] = {};
    for (const auto& n : nodes) {
        double dx = n.x-cx, dy = n.y-cy, dz = n.z-cz;
        double v[3] = {dx, dy, dz};
        for (int r = 0; r < 3; ++r)
            for (int c = 0; c < 3; ++c)
                cov[r][c] += v[r]*v[c];
    }
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            cov[r][c] /= (double)nodes.size();

    double evals[3];
    double evecs[3][3];
    cs_eigen3x3sym(cov, evals, evecs);

    // Largest eigenvalue eigenvector = cylinder axis
    Vec3 axis = {evecs[0][0], evecs[0][1], evecs[0][2]};

    // Snap to canonical axis if close (avoids floating-point tilt artifacts)
    if (std::fabs(axis.x) > 0.9) return {axis.x > 0 ? 1.0 : -1.0, 0, 0};
    if (std::fabs(axis.y) > 0.9) return {0, axis.y > 0 ? 1.0 : -1.0, 0};
    if (std::fabs(axis.z) > 0.9) return {0, 0, axis.z > 0 ? 1.0 : -1.0};
    return axis;
}

// ============================================================
// Build two perpendicular vectors to axis
// ============================================================

static void cs_buildPerp(Vec3 axis, Vec3& perp1, Vec3& perp2) {
    Vec3 up = {0, 0, 1};
    if (std::fabs(axis.z) > 0.9) up = {1, 0, 0};
    perp1 = cs_norm(cs_cross(axis, up));
    perp2 = cs_cross(axis, perp1);
}

// ============================================================
// Round Z value to grid (within tolerance)
// ============================================================

static double cs_roundZ(double z, double tol) {
    return std::round(z / tol) * tol;
}

// ============================================================
// Format a fixed-width LS-DYNA node line
// ============================================================

static std::string cs_fmtNode(int nid, double x, double y, double z) {
    char buf[128];
    snprintf(buf, sizeof(buf), "%8d%16.8e%16.8e%16.8e       0       0", nid, x, y, z);
    return std::string(buf);
}

// ============================================================
// Format a HEX8 element line (LS-DYNA)
// ============================================================

static std::string cs_fmtHex8(int eid, int pid,
    int n1,int n2,int n3,int n4, int n5,int n6,int n7,int n8) {
    char buf[128];
    snprintf(buf, sizeof(buf),
        "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d",
        eid, pid, n1, n2, n3, n4, n5, n6, n7, n8);
    return std::string(buf);
}

// ============================================================
// Format a 10-char field line value
// ============================================================

static std::string cs_fmt10(double v) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%10.4E", v);
    return std::string(buf);
}

static std::string cs_fmt10i(int v) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%10d", v);
    return std::string(buf);
}

// ============================================================
// Main per-CNRB conversion
// ============================================================

struct CnrbConvResult {
    std::vector<std::string> nodeLines;
    std::vector<std::string> elemLines;
    std::vector<std::string> partLines;
    std::vector<std::string> sectionLines;
    std::vector<std::string> matLines;
    std::vector<std::string> setLines;   // new SET_NODE_LIST for tied contact
    std::vector<std::string> contactLines;
    std::set<int> removedNodeIds;         // PNODE to remove from *NODE section
};

static bool cs_convertOneCnrb(
    const CnrbDef& cnrb,
    const std::map<int, NodeXYZ>& allNodes,
    const std::map<int, std::vector<int>>& nodeSets,
    const Cnrb2SolidConfig& cfg,
    int& nodeId, int& elemId, int& secId, int& matId, int& setId,
    CnrbConvResult& result,
    ConsoleOutput& console)
{
    // --- 1. Gather hole nodes ---
    auto sit = nodeSets.find(cnrb.nsid);
    if (sit == nodeSets.end() || sit->second.empty()) {
        console.println("[cnrb2solid] WARNING: NSID=" + std::to_string(cnrb.nsid) +
                        " not found or empty, skipping PID=" + std::to_string(cnrb.pid));
        return false;
    }
    const std::vector<int>& nsNodes = sit->second;

    std::vector<NodeXYZ> pts;
    for (int nid : nsNodes) {
        auto nit = allNodes.find(nid);
        if (nit != allNodes.end()) pts.push_back(nit->second);
    }
    if (pts.size() < 4) {
        console.println("[cnrb2solid] WARNING: PID=" + std::to_string(cnrb.pid) +
                        " has too few nodes (" + std::to_string(pts.size()) + "), skipping");
        return false;
    }

    // --- 2. PCA axis + center ---
    Vec3 axis = cs_detectAxis(pts, cfg.axisDirection);

    // Center from PNODE or centroid
    Vec3 center = {0, 0, 0};
    if (cnrb.pnode > 0) {
        auto pit = allNodes.find(cnrb.pnode);
        if (pit != allNodes.end()) {
            center = {pit->second.x, pit->second.y, pit->second.z};
            result.removedNodeIds.insert(cnrb.pnode);
        }
    }
    if (cnrb.pnode <= 0 || result.removedNodeIds.empty()) {
        for (const auto& p : pts) { center.x += p.x; center.y += p.y; center.z += p.z; }
        center.x /= pts.size(); center.y /= pts.size(); center.z /= pts.size();
    }

    Vec3 perp1, perp2;
    cs_buildPerp(axis, perp1, perp2);

    // --- 3. Cylindrical coordinates ---
    struct CylNode { double R, theta, Z; int origNid; };
    std::vector<CylNode> cylNodes;
    for (size_t i = 0; i < nsNodes.size(); ++i) {
        auto nit = allNodes.find(nsNodes[i]);
        if (nit == allNodes.end()) continue;
        Vec3 pt = {nit->second.x, nit->second.y, nit->second.z};
        Vec3 v  = cs_sub(pt, center);
        double Z     = cs_dot(v, axis);
        Vec3 radial  = cs_sub(v, cs_scale(axis, Z));
        double R     = std::sqrt(cs_dot(radial, radial));
        double theta = std::atan2(cs_dot(radial, perp2), cs_dot(radial, perp1));
        cylNodes.push_back({R, theta, Z, nsNodes[i]});
    }

    // --- 4. Z-level grouping ---
    std::map<double, std::vector<int>> zGroups; // rounded-Z → indices into cylNodes
    for (int i = 0; i < (int)cylNodes.size(); ++i) {
        double rz = cs_roundZ(cylNodes[i].Z, cfg.zTolerance);
        zGroups[rz].push_back(i);
    }

    // Sorted Z levels
    std::vector<double> zLevels;
    for (auto& kv : zGroups) zLevels.push_back(kv.first);
    std::sort(zLevels.begin(), zLevels.end());

    if (zLevels.size() < 2) {
        console.println("[cnrb2solid] WARNING: PID=" + std::to_string(cnrb.pid) +
                        " has only 1 Z-level, skipping");
        return false;
    }

    // --- 5. R-value per Z-level (use max R in each level) ---
    std::map<double, double> zRmax; // z → max R at that level
    for (double z : zLevels) {
        double rmax = 0;
        for (int idx : zGroups[z])
            rmax = std::max(rmax, cylNodes[idx].R);
        zRmax[z] = rmax;
    }

    double R_shaft_global = 0;
    for (auto& kv : zRmax) R_shaft_global = std::max(R_shaft_global, kv.second);

    // --- 6. Auto NumCircumNodes ---
    int N = cfg.numCircumNodes;
    if (N <= 0) {
        int maxPerLevel = 0;
        for (double z : zLevels) maxPerLevel = std::max(maxPerLevel, (int)zGroups[z].size());
        N = std::max(8, (maxPerLevel / 4) * 4); // round to multiple of 4
    }
    N = ((N + 3) / 4) * 4; // ensure multiple of 4
    int m = N / 4;

    // --- 7. Bolt head: add extra Z-level ---
    std::vector<double> allZ = zLevels; // may be extended
    std::map<double, double> zRlocal = zRmax; // z → local R for filtering

    double headR   = 0.0;
    double headZ   = 0.0;     // base Z of head (= extremal Z of shaft)
    double headTopZ = 0.0;    // outer Z of head
    bool   hasHead = (cfg.headOffsetR > 0.0 && cfg.headPosition != "none");

    if (hasHead) {
        headR = R_shaft_global + cfg.headOffsetR;

        // Determine head position
        double zMin = zLevels.front();
        double zMax = zLevels.back();

        bool atTop = true; // default
        if (cfg.headPosition == "bottom") {
            atTop = false;
        } else if (cfg.headPosition == "auto") {
            // Place head at the end with higher R (larger bolt feature)
            double rMin_side = zRmax[zMin];
            double rMax_side = zRmax[zMax];
            atTop = (rMax_side >= rMin_side);
        }

        if (atTop) {
            headZ    = zMax;
            headTopZ = zMax + cfg.headThickness;
        } else {
            headZ    = zMin;
            headTopZ = zMin - cfg.headThickness;
        }

        // Add head Z-level
        allZ.push_back(headTopZ);
        std::sort(allZ.begin(), allZ.end());
        zRlocal[headTopZ] = headR;
        // Head base Z-level also uses headR so head layer gets full ring set
        zRlocal[headZ]    = headR;
    }

    // --- 8. Determine radial rings ---
    // Build one ring per distinct R cluster found across all Z-levels,
    // plus additional rings for bolt head if present.

    // Collect and cluster all R values (from shaft levels only, not head)
    std::vector<double> allShaftR;
    for (double z : zLevels) allShaftR.push_back(zRmax[z]);
    std::sort(allShaftR.begin(), allShaftR.end());

    // Cluster with r_tolerance
    std::vector<double> rClusters;
    for (double rv : allShaftR) {
        if (rClusters.empty() || rv - rClusters.back() > cfg.rTolerance)
            rClusters.push_back(rv);
        else
            rClusters.back() = 0.5 * (rClusters.back() + rv); // running mean
    }

    // Ring radii = cluster centers * radiusScale
    std::vector<double> ringRadii;
    for (double rc : rClusters)
        ringRadii.push_back(rc * cfg.radiusScale);

    if (hasHead) {
        // Add head rings: evenly spaced from R_shaft to headR
        int headRings = std::max(1, (int)std::round(cfg.headOffsetR / (R_shaft_global / 2.0)));
        double R_shaft_scaled = R_shaft_global * cfg.radiusScale;
        for (int k = 1; k <= headRings; ++k)
            ringRadii.push_back(R_shaft_scaled + (headR - R_shaft_global) * k / headRings * cfg.radiusScale);
    }

    // --- 9. Generate nodes for all Z-levels at full R_max ---
    // Node layout per Z-level:
    //   core nodes: (m+1)*(m+1)  indices [0 .. (m+1)*(m+1)-1]
    //   ring nodes: N * numRings  indices [(m+1)*(m+1) .. ]
    //
    // We store: zNodeMap[z][ring_or_core_idx] = global node ID

    double coreHalf = ringRadii[0] * cfg.innerRadiusRatio; // half-side of core square

    // Maps: per Z-level → flat array of node IDs
    //   coreBase: (m+1)*(m+1) nodes
    //   ringBase per ring: N nodes
    struct ZNodes {
        std::vector<int> core;  // (m+1)*(m+1) entries, row-major [i*(m+1)+j]
        std::vector<std::vector<int>> rings; // rings[ri][k]
    };

    std::map<double, ZNodes> zNodes;

    // theta offset: align ring node 0 with core corner direction
    // Core corner at (-d, -d) → angle = 5π/4
    double thetaOffset = 5.0 * M_PI / 4.0;

    for (double z : allZ) {
        ZNodes zn;
        // Core nodes
        Vec3 zCenter = cs_add(center, cs_scale(axis, z));
        zn.core.resize((m+1)*(m+1));
        for (int ci = 0; ci <= m; ++ci) {
            for (int cj = 0; cj <= m; ++cj) {
                double xl = -coreHalf + 2.0*coreHalf*ci/m;
                double yl = -coreHalf + 2.0*coreHalf*cj/m;
                Vec3 pos = cs_add(cs_add(zCenter,
                                  cs_scale(perp1, xl)),
                                  cs_scale(perp2, yl));
                ++nodeId;
                zn.core[ci*(m+1)+cj] = nodeId;
                result.nodeLines.push_back(cs_fmtNode(nodeId, pos.x, pos.y, pos.z));
            }
        }
        // Ring nodes (all rings, at their radii)
        zn.rings.resize(ringRadii.size());
        for (int ri = 0; ri < (int)ringRadii.size(); ++ri) {
            double R_ring = ringRadii[ri];
            zn.rings[ri].resize(N);
            for (int k = 0; k < N; ++k) {
                double theta = thetaOffset + 2.0*M_PI*k/N;
                Vec3 pos = cs_add(cs_add(zCenter,
                                  cs_scale(perp1, R_ring*std::cos(theta))),
                                  cs_scale(perp2, R_ring*std::sin(theta)));
                ++nodeId;
                zn.rings[ri][k] = nodeId;
                result.nodeLines.push_back(cs_fmtNode(nodeId, pos.x, pos.y, pos.z));
            }
        }
        zNodes[z] = std::move(zn);
    }

    // --- 10. Generate elements layer by layer ---
    // For each consecutive Z-pair, determine R_local and create elements up to that ring
    for (int li = 0; li + 1 < (int)allZ.size(); ++li) {
        double zBot = allZ[li];
        double zTop = allZ[li+1];

        // R_local for this layer = min of R at bot and top * scale
        // (zRlocal already has headR for headZ and headTopZ levels)
        double rBot = zRlocal.count(zBot) ? zRlocal[zBot] : R_shaft_global;
        double rTop = zRlocal.count(zTop) ? zRlocal[zTop] : R_shaft_global;
        double rLocal = std::min(rBot, rTop) * cfg.radiusScale;

        const ZNodes& znBot = zNodes[zBot];
        const ZNodes& znTop = zNodes[zTop];

        // Core elements: m*m per layer
        for (int ci = 0; ci < m; ++ci) {
            for (int cj = 0; cj < m; ++cj) {
                // Bottom face CCW: (ci,cj)→(ci+1,cj)→(ci+1,cj+1)→(ci,cj+1)
                int b0 = znBot.core[ ci   *(m+1)+ cj  ];
                int b1 = znBot.core[(ci+1)*(m+1)+ cj  ];
                int b2 = znBot.core[(ci+1)*(m+1)+(cj+1)];
                int b3 = znBot.core[ ci   *(m+1)+(cj+1)];
                int t0 = znTop.core[ ci   *(m+1)+ cj  ];
                int t1 = znTop.core[(ci+1)*(m+1)+ cj  ];
                int t2 = znTop.core[(ci+1)*(m+1)+(cj+1)];
                int t3 = znTop.core[ ci   *(m+1)+(cj+1)];
                ++elemId;
                result.elemLines.push_back(cs_fmtHex8(elemId, cnrb.pid,
                    b0, b1, b2, b3, t0, t1, t2, t3));
            }
        }

        // Shell (core→ring0) elements: N per layer
        // Core boundary nodes CCW order (4m = N segments):
        // Bottom: (0,0)→(1,0)→...→(m,0)  [m seg]
        // Right:  (m,0)→(m,1)→...→(m,m)  [m seg]
        // Top:    (m,m)→(m-1,m)→...→(0,m)[m seg]
        // Left:   (0,m)→(0,m-1)→...→(0,1)[m seg]
        std::vector<int> coreBoundaryBot(N), coreBoundaryTop(N);
        for (int k = 0; k < N; ++k) {
            int seg = k;
            int ci_b, cj_b;
            if      (seg <   m) { ci_b = seg;     cj_b = 0; }
            else if (seg <  2*m){ ci_b = m;        cj_b = seg - m; }
            else if (seg <  3*m){ ci_b = 3*m-seg;  cj_b = m; }
            else                { ci_b = 0;        cj_b = N-seg; }
            coreBoundaryBot[k] = znBot.core[ci_b*(m+1)+cj_b];
            coreBoundaryTop[k] = znTop.core[ci_b*(m+1)+cj_b];
        }

        // Check if shaft ring is within R_local
        if (ringRadii[0] <= rLocal * 1.01) {
            for (int k = 0; k < N; ++k) {
                int kn = (k+1) % N;
                // Bottom: outer[k]→outer[k+1]→core[k+1]→core[k]
                int b0 = znBot.rings[0][k];
                int b1 = znBot.rings[0][kn];
                int b2 = coreBoundaryBot[kn];
                int b3 = coreBoundaryBot[k];
                int t0 = znTop.rings[0][k];
                int t1 = znTop.rings[0][kn];
                int t2 = coreBoundaryTop[kn];
                int t3 = coreBoundaryTop[k];
                ++elemId;
                result.elemLines.push_back(cs_fmtHex8(elemId, cnrb.pid,
                    b0, b1, b2, b3, t0, t1, t2, t3));
            }
        }

        // Additional rings (head or multi-radius)
        for (int ri = 1; ri < (int)ringRadii.size(); ++ri) {
            if (ringRadii[ri] > rLocal * 1.01) break;
            for (int k = 0; k < N; ++k) {
                int kn = (k+1) % N;
                int b0 = znBot.rings[ri][k];
                int b1 = znBot.rings[ri][kn];
                int b2 = znBot.rings[ri-1][kn];
                int b3 = znBot.rings[ri-1][k];
                int t0 = znTop.rings[ri][k];
                int t1 = znTop.rings[ri][kn];
                int t2 = znTop.rings[ri-1][kn];
                int t3 = znTop.rings[ri-1][k];
                ++elemId;
                result.elemLines.push_back(cs_fmtHex8(elemId, cnrb.pid,
                    b0, b1, b2, b3, t0, t1, t2, t3));
            }
        }
    }

    // --- 11. Part, Section, Material ---
    ++secId;
    ++matId;

    result.partLines.push_back("*PART");
    result.partLines.push_back(cnrb.title.empty() ? "CNRB_" + std::to_string(cnrb.pid) + "_Solid" : cnrb.title + "_Solid");
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "%10d%10d%10d", cnrb.pid, secId, matId);
        result.partLines.push_back(std::string(buf));
    }

    result.sectionLines.push_back("*SECTION_SOLID_TITLE");
    result.sectionLines.push_back("CNRB_" + std::to_string(cnrb.pid) + "_Section");
    {
        char buf[64]; snprintf(buf, sizeof(buf), "%10d%10d", secId, 1);
        result.sectionLines.push_back(std::string(buf));
    }

    result.matLines.push_back("*MAT_ELASTIC_TITLE");
    result.matLines.push_back("CNRB_" + std::to_string(cnrb.pid) + "_Material");
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "%10d%s%s%s",
            matId, cs_fmt10(cfg.RHO).c_str(), cs_fmt10(cfg.E).c_str(), cs_fmt10(cfg.PR).c_str());
        result.matLines.push_back(std::string(buf));
    }

    // --- 12. Tied Contact (original hole nodes ↔ new solid part) ---
    ++setId;

    // SET_NODE_LIST for original CNRB nodes
    result.setLines.push_back("*SET_NODE_LIST_TITLE");
    result.setLines.push_back("Tied_CNRB_" + std::to_string(cnrb.pid));
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "%10d       0.0       0.0       0.0       0.0", setId);
        result.setLines.push_back(std::string(buf));
    }
    // Write node IDs, 8 per line
    for (int i = 0; i < (int)nsNodes.size(); i += 8) {
        std::string ln;
        for (int j = i; j < std::min(i+8, (int)nsNodes.size()); ++j)
            ln += cs_fmt10i(nsNodes[j]);
        result.setLines.push_back(ln);
    }

    // CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET
    static int contactId = 0;
    ++contactId;
    result.contactLines.push_back("*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID");
    {
        char buf[64]; snprintf(buf, sizeof(buf), "%10d", contactId);
        result.contactLines.push_back(std::string(buf) + "                                            Tied_CNRB_" + std::to_string(cnrb.pid));
    }
    {
        char buf[128];
        // SSID=setId(SSTYP=4 node set), MSID=cnrb.pid(MSTYP=3 part)
        snprintf(buf, sizeof(buf),
            "%10d%10d%10d%10d%10d%10d%10d%10d",
            setId, cnrb.pid, 4, 3, 0, 0, 0, 0);
        result.contactLines.push_back(std::string(buf));
    }
    result.contactLines.push_back("       0.0       0.0       0.0       0.0       0.0         0      0.011.0000E+20");
    result.contactLines.push_back("       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0");

    return true;
}

// ============================================================
// cnrb2solid_convert  — main entry point
// ============================================================

int cnrb2solid_convert(std::vector<std::string>& lines,
                       const Cnrb2SolidConfig& cfg,
                       int& maxNodeId, int& maxElemId,
                       int& maxSecId,  int& maxMatId,
                       int& maxSetId,  int& /*maxPartId*/,
                       ConsoleOutput& console)
{
    // Build lookup structures
    auto allNodes  = cs_parseNodes(lines);
    auto nodeSets  = cs_parseNodeSets(lines);
    auto cnrbs     = cs_parseCnrbs(lines);

    if (cnrbs.empty()) {
        console.println("[cnrb2solid] No *CONSTRAINED_NODAL_RIGID_BODY found.");
        return 0;
    }

    // Seed max IDs from parsed nodes/elements (if not already set by caller)
    if (maxNodeId == 0) for (auto& kv : allNodes) maxNodeId = std::max(maxNodeId, kv.first);

    int converted = 0;
    std::set<int> targetSet(cfg.targetPids.begin(), cfg.targetPids.end());

    // Collect all conversion results and track which lines to remove
    std::vector<std::pair<size_t,size_t>> removeRanges; // [start, end) line ranges to remove
    std::set<int>  allRemovedNodeIds;
    std::vector<std::string> insertLines; // appended before *END

    for (const auto& cnrb : cnrbs) {
        if (!targetSet.empty() && targetSet.find(cnrb.pid) == targetSet.end()) continue;

        CnrbConvResult res;
        bool ok = cs_convertOneCnrb(cnrb, allNodes, nodeSets, cfg,
                                     maxNodeId, maxElemId, maxSecId, maxMatId, maxSetId,
                                     res, console);
        if (!ok) continue;

        // Mark CNRB block for removal
        removeRanges.push_back({cnrb.lineStart, cnrb.lineEnd});
        for (int nid : res.removedNodeIds) allRemovedNodeIds.insert(nid);

        // Collect insert lines
        insertLines.push_back("$$ --- CNRB2SOLID: PID=" + std::to_string(cnrb.pid) + " ---");
        insertLines.push_back("*NODE");
        for (auto& l : res.nodeLines)    insertLines.push_back(l);
        insertLines.push_back("*ELEMENT_SOLID");
        for (auto& l : res.elemLines)    insertLines.push_back(l);
        for (auto& l : res.partLines)    insertLines.push_back(l);
        for (auto& l : res.sectionLines) insertLines.push_back(l);
        for (auto& l : res.matLines)     insertLines.push_back(l);
        for (auto& l : res.setLines)     insertLines.push_back(l);
        for (auto& l : res.contactLines) insertLines.push_back(l);
        ++converted;
    }

    if (converted == 0) return 0;

    // --- Remove CNRB blocks (mark removed lines) ---
    std::vector<bool> rm(lines.size(), false);
    for (auto& rng : removeRanges)
        for (size_t i = rng.first; i < rng.second; ++i) rm[i] = true;

    // --- Remove PNODE lines from *NODE section ---
    bool inNodeSection = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (rm[i]) continue;
        std::string tr = cs_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            inNodeSection = (cs_upper(tr).rfind("*NODE", 0) == 0 &&
                             cs_upper(tr).find("SET") == std::string::npos);
            continue;
        }
        if (!inNodeSection || tr[0] == '$') continue;
        auto toks = cs_splitWS(lines[i]);
        if (!toks.empty()) {
            int nid = cs_parseInt(toks[0]);
            if (allRemovedNodeIds.count(nid)) rm[i] = true;
        }
    }

    // Build new line buffer
    std::vector<std::string> newLines;
    newLines.reserve(lines.size() + insertLines.size());
    for (size_t i = 0; i < lines.size(); ++i) {
        if (rm[i]) continue;
        std::string tr = cs_trim(lines[i]);
        if (cs_upper(tr) == "*END") {
            for (auto& l : insertLines) newLines.push_back(l);
        }
        newLines.push_back(lines[i]);
    }
    lines = std::move(newLines);
    return converted;
}

// ============================================================
// Standalone YAML runner
// ============================================================

int runCnrb2Solid(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    Cnrb2SolidConfig cfg;

    std::string line;
    while (std::getline(f, line)) {
        std::string tr = cs_trim(line);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = cs_trim(tr.substr(0, cp));
        std::string val = cs_trim(tr.substr(cp + 1));
        { size_t h = val.find('#'); if (h != std::string::npos) val = cs_trim(val.substr(0, h)); }
        if (val.empty()) continue;
        try {
            if      (key == "model")               modelFile        = val;
            else if (key == "output")              outputFile       = val;
            else if (key == "E")                   cfg.E            = std::stod(val);
            else if (key == "PR" || key == "pr")   cfg.PR           = std::stod(val);
            else if (key == "RHO" || key == "rho") cfg.RHO          = std::stod(val);
            else if (key == "radius_scale")        cfg.radiusScale  = std::stod(val);
            else if (key == "num_circum_nodes")    cfg.numCircumNodes = std::stoi(val);
            else if (key == "inner_radius_ratio")  cfg.innerRadiusRatio = std::stod(val);
            else if (key == "axis_direction")      cfg.axisDirection = val;
            else if (key == "z_tolerance")         cfg.zTolerance   = std::stod(val);
            else if (key == "r_tolerance")         cfg.rTolerance   = std::stod(val);
            else if (key == "head_offset_r")       cfg.headOffsetR  = std::stod(val);
            else if (key == "head_thickness")      cfg.headThickness = std::stod(val);
            else if (key == "head_position")       cfg.headPosition = val;
        } catch (...) {}
    }

    if (modelFile.empty())  { console.error("cnrb2solid: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("cnrb2solid: 'output' not specified"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':'))
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

    console.println("[cnrb2solid] Model  : " + modelPath);
    console.println("[cnrb2solid] Output : " + outPath);

    int maxNodeId = 0, maxElemId = 0, maxSecId = 0, maxMatId = 0, maxSetId = 0, maxPartId = 0;

    // Scan for existing max IDs
    bool inElem = false;
    for (const auto& ln : lines) {
        std::string tr = cs_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = cs_upper(tr);
            inElem = (up.rfind("*ELEMENT_SOLID", 0) == 0 || up.rfind("*ELEMENT_SHELL", 0) == 0);
            continue;
        }
        if (tr[0] == '$') continue;
        auto toks = cs_splitWS(ln);
        if (toks.empty()) continue;
        int id = cs_parseInt(toks[0]);
        if (id <= 0) continue;

        if (inElem) maxElemId = std::max(maxElemId, id);

        if (toks.size() >= 2) {
            std::string up2 = cs_upper(cs_trim(lines[&ln - &lines[0] > 0 ? 0 : 0]));
            (void)up2;
        }
    }
    // Simple pass: max node ID
    {
        bool inN = false;
        for (const auto& ln : lines) {
            std::string tr = cs_trim(ln);
            if (tr.empty()) continue;
            if (tr[0] == '*') {
                inN = (cs_upper(tr).rfind("*NODE", 0) == 0 && cs_upper(tr).find("SET") == std::string::npos);
                continue;
            }
            if (!inN || tr[0] == '$') continue;
            auto toks = cs_splitWS(ln);
            if (!toks.empty()) maxNodeId = std::max(maxNodeId, cs_parseInt(toks[0]));
        }
    }
    // Max section/mat IDs
    for (const auto& ln : lines) {
        std::string tr = cs_trim(ln);
        if (tr.empty() || tr[0] == '$') continue;
        if (tr[0] == '*') continue;
        int id = cs_parseInt(cs_field10(ln, 0));
        // We'll be conservative and use these as base
        maxSecId  = std::max(maxSecId,  id);
        maxMatId  = std::max(maxMatId,  id);
        maxSetId  = std::max(maxSetId,  id);
        maxPartId = std::max(maxPartId, id);
    }

    int n = cnrb2solid_convert(lines, cfg,
                                maxNodeId, maxElemId, maxSecId, maxMatId, maxSetId, maxPartId,
                                console);

    if (n < 0) { console.error("[cnrb2solid] Conversion failed"); return 1; }

    char buf[64]; snprintf(buf, sizeof(buf), "[cnrb2solid] Converted %d CNRB(s)", n);
    console.println(buf);

    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[cnrb2solid] Done   -> " + outPath);
    return 0;
}
