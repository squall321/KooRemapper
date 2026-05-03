#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#  ifdef ERROR
#    undef ERROR
#  endif
#endif

#include "commands/meshfix.h"
#include "core/Mesh.h"
#include "core/Element.h"
#include "core/Node.h"
#include "parser/KFileReader.h"
#include "cli/ConsoleOutput.h"
#include "util/Timer.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <array>
#include <algorithm>
#include <queue>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <cctype>

namespace fs = std::filesystem;
using namespace KooRemapper;

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────
namespace {

struct Cfg {
    std::string model;
    std::string output;
    int pid = -1;

    // element size
    double lcTarget = 1.0;
    double lcMin    = -1.0;   // -1 = auto-derive
    double lcMax    = -1.0;   // -1 = lcTarget * 2

    // min_dt based lc_min
    double minDt   = -1.0;
    double density = -1.0;
    double E       = -1.0;
    double nu      = -1.0;

    // thin solid
    int minLayersThin = 2;

    // adaptive size field
    bool   adaptive        = true;
    double attractorRatio  = 0.4;   // edge < lcTarget*ratio → attractor
    double attractorMinJac = 0.2;   // scaledJac < this   → attractor
    double decayFactor     = 8.0;   // distMax = lcMin * decayFactor

    // boundary node handling
    std::string boundaryNodes = "free"; // free | fixed | snap
    double snapTolerance = 0.001;

    // gmsh options
    std::string algorithm   = "hxt"; // hxt | frontal3d | del3d
    bool optimizeNetgen     = true;

    // quality report after remesh
    bool   qualityCheck = true;
    double warnMinJac   = 0.15;
};

// ─── YAML helpers ─────────────────────────────────────────────────────────────

static std::string mf_trim(std::string s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    size_t b = s.find_last_not_of(" \t\r\n");
    return (a == std::string::npos) ? "" : s.substr(a, b - a + 1);
}
static std::string mf_stripQ(std::string s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}
static bool mf_bool(const std::string& v) {
    std::string t = v;
    for (auto& c : t) c = (char)std::tolower((unsigned char)c);
    return t == "true" || t == "yes" || t == "on" || t == "1";
}

static bool readConfig(const std::string& path, Cfg& cfg, std::string& err) {
    std::ifstream f(path);
    if (!f.is_open()) { err = "Cannot open " + path; return false; }

    std::string line, section;
    int secIndent = -1;
    while (std::getline(f, line)) {
        size_t h = line.find('#');
        if (h != std::string::npos) line = line.substr(0, h);
        if (line.find_first_not_of(" \t\r\n") == std::string::npos) continue;

        int indent = 0;
        while (indent < (int)line.size() && (line[indent]==' '||line[indent]=='\t')) ++indent;
        std::string body = mf_trim(line);
        size_t col = body.find(':');
        if (col == std::string::npos) continue;
        std::string key = mf_trim(body.substr(0, col));
        std::string val = mf_stripQ(mf_trim(body.substr(col + 1)));

        if (indent == 0) { section.clear(); secIndent = -1; }
        else if (secIndent >= 0 && indent <= secIndent) { section.clear(); secIndent = -1; }

        auto trySection = [&](const std::string& k) {
            if (key == k && val.empty() && indent == 0) {
                section = k; secIndent = 0; return true;
            }
            return false;
        };

        // top-level
        if (indent == 0) {
            if (key=="model")          { cfg.model   = val; continue; }
            if (key=="output")         { cfg.output  = val; continue; }
            if (key=="pid")            { cfg.pid     = std::stoi(val); continue; }
            if (key=="lc_target")      { cfg.lcTarget= std::stod(val); continue; }
            if (key=="lc_min")         { cfg.lcMin   = std::stod(val); continue; }
            if (key=="lc_max")         { cfg.lcMax   = std::stod(val); continue; }
            if (key=="min_dt")         { cfg.minDt   = std::stod(val); continue; }
            if (key=="density")        { cfg.density = std::stod(val); continue; }
            if (key=="E")              { cfg.E       = std::stod(val); continue; }
            if (key=="nu")             { cfg.nu      = std::stod(val); continue; }
            if (key=="min_layers_thin"){ cfg.minLayersThin = std::stoi(val); continue; }
            if (key=="adaptive"&&!val.empty()){ cfg.adaptive = mf_bool(val); continue; }
            if (key=="attractor_ratio")    { cfg.attractorRatio  = std::stod(val); continue; }
            if (key=="attractor_min_jac")  { cfg.attractorMinJac = std::stod(val); continue; }
            if (key=="decay_factor")       { cfg.decayFactor = std::stod(val); continue; }
            if (key=="boundary_nodes") { cfg.boundaryNodes = val; continue; }
            if (key=="snap_tolerance") { cfg.snapTolerance = std::stod(val); continue; }
            if (key=="algorithm")      { cfg.algorithm = val; continue; }
            if (key=="optimize_netgen"){ cfg.optimizeNetgen = mf_bool(val); continue; }
            if (key=="quality_check")  { cfg.qualityCheck = mf_bool(val); continue; }
            if (key=="warn_min_jac")   { cfg.warnMinJac = std::stod(val); continue; }
            // section headers (val empty)
            if (trySection("material")) continue;
            if (trySection("adaptive")) continue;
            if (trySection("gmsh"))     continue;
            if (trySection("boundary")) continue;
            if (trySection("quality"))  continue;
        } else if (!section.empty()) {
            if (key=="min_dt")         cfg.minDt   = std::stod(val);
            if (key=="density")        cfg.density = std::stod(val);
            if (key=="E")              cfg.E       = std::stod(val);
            if (key=="nu")             cfg.nu      = std::stod(val);
            if (key=="min_layers_thin")cfg.minLayersThin = std::stoi(val);
            if (key=="attractor_ratio")    cfg.attractorRatio  = std::stod(val);
            if (key=="attractor_min_jac")  cfg.attractorMinJac = std::stod(val);
            if (key=="decay_factor")       cfg.decayFactor = std::stod(val);
            if (key=="nodes")          cfg.boundaryNodes = val;
            if (key=="snap_tolerance") cfg.snapTolerance = std::stod(val);
            if (key=="algorithm")      cfg.algorithm = val;
            if (key=="optimize_netgen")cfg.optimizeNetgen = mf_bool(val);
            if (key=="warn_min_jac")   cfg.warnMinJac = std::stod(val);
        }
    }
    if (cfg.model.empty())  { err = "Missing 'model'";  return false; }
    if (cfg.output.empty()) { err = "Missing 'output'"; return false; }
    if (cfg.pid < 0)        { err = "Missing 'pid'";    return false; }
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gmsh detection
// ─────────────────────────────────────────────────────────────────────────────

static std::string findGmshExe() {
    fs::path execDir;
#ifdef _WIN32
    char buf[4096] = {};
    DWORD n = GetModuleFileNameA(nullptr, buf, sizeof(buf));
    if (n > 0) execDir = fs::path(std::string(buf)).parent_path();
#else
    char buf[4096] = {};
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf));
    if (n > 0) execDir = fs::path(std::string(buf, (size_t)n)).parent_path();
#endif
    if (execDir.empty()) execDir = ".";

    // 1. simple: execDir/gmsh/gmsh.exe
    {
        auto p = execDir / "gmsh" / "gmsh.exe";
        if (fs::exists(p)) return p.string();
    }
    // 2. versioned dir: execDir/gmsh-*/gmsh.exe
    std::error_code ec;
    for (auto& entry : fs::directory_iterator(execDir, ec)) {
        if (!entry.is_directory()) continue;
        std::string name = entry.path().filename().string();
        if (name.rfind("gmsh", 0) == 0) {
            auto p = entry.path() / "gmsh.exe";
            if (fs::exists(p)) return p.string();
        }
    }
    return "";
}

// ─────────────────────────────────────────────────────────────────────────────
// TET4 geometry helpers
// ─────────────────────────────────────────────────────────────────────────────

// TET4 stored as degenerate HEX8: nodeIds[3..7] all = nodeIds[3]
static bool isTet4(const Element& e) {
    return e.type == ElementType::TET4 ||
           (e.type == ElementType::HEX8 &&
            e.nodeIds[3] == e.nodeIds[4] &&
            e.nodeIds[4] == e.nodeIds[5] &&
            e.nodeIds[5] == e.nodeIds[6] &&
            e.nodeIds[6] == e.nodeIds[7]);
}

static void getTet(const Element& e, int out[4]) {
    out[0]=e.nodeIds[0]; out[1]=e.nodeIds[1];
    out[2]=e.nodeIds[2]; out[3]=e.nodeIds[3];
}

// TET4: 4 faces × 3 nodes each (outward-normal winding for positive-volume TET4).
// For V = det([n1-n0, n2-n0, n3-n0]) > 0:
//   face opp n3 → {0,2,1} (reversed from {0,1,2} which points inward toward n3)
//   face opp n2 → {0,1,3} (outward away from n2)
//   face opp n0 → {1,2,3} (outward away from n0)
//   face opp n1 → {0,3,2} (reversed from {0,2,3} which points inward toward n1)
static const int TF[4][3] = {{0,2,1},{0,1,3},{1,2,3},{0,3,2}};
// TET4: 6 edges × 2 nodes each
static const int TE[6][2] = {{0,1},{0,2},{0,3},{1,2},{1,3},{2,3}};

static double dist2(const Node& a, const Node& b) {
    double dx=a.position.x-b.position.x, dy=a.position.y-b.position.y, dz=a.position.z-b.position.z;
    return dx*dx+dy*dy+dz*dz;
}
static double edgeLen(const Node& a, const Node& b) { return std::sqrt(dist2(a,b)); }

static double tetScaledJac(const Mesh& mesh, const Element& e) {
    int t[4]; getTet(e, t);
    const Node* n[4];
    for (int i=0;i<4;++i) { n[i]=mesh.getNode(t[i]); if(!n[i]) return 0.0; }
    // volume via triple product
    double v1x=n[1]->position.x-n[0]->position.x, v1y=n[1]->position.y-n[0]->position.y, v1z=n[1]->position.z-n[0]->position.z;
    double v2x=n[2]->position.x-n[0]->position.x, v2y=n[2]->position.y-n[0]->position.y, v2z=n[2]->position.z-n[0]->position.z;
    double v3x=n[3]->position.x-n[0]->position.x, v3y=n[3]->position.y-n[0]->position.y, v3z=n[3]->position.z-n[0]->position.z;
    double vol=(v1x*(v2y*v3z-v2z*v3y)-v1y*(v2x*v3z-v2z*v3x)+v1z*(v2x*v3y-v2y*v3x))/6.0;
    if (vol <= 0.0) return vol;
    double maxE=0;
    for (int ei=0;ei<6;++ei) maxE=std::max(maxE, edgeLen(*n[TE[ei][0]], *n[TE[ei][1]]));
    return (maxE>1e-15) ? 6.0*vol/(maxE*maxE*maxE)*std::sqrt(2.0) : 0.0;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mesh Analysis → lc_min + attractors
// ─────────────────────────────────────────────────────────────────────────────

struct AttractorPt { double x,y,z; };

struct AnalysisResult {
    double lcMinEff;
    double lcMaxEff;
    double edgeMin, edgeAvg, edgeMax;
    double thinDim;       // >0 if thin solid detected
    int    nodeCount, elemCount, badElemCount;
    std::vector<AttractorPt> attractors;
};

static AnalysisResult analyzePart(const Mesh& mesh, int pid, const Cfg& cfg) {
    AnalysisResult ar{};
    ar.thinDim = -1;

    std::vector<const Element*> elems;
    for (auto& [eid,e] : mesh.elements)
        if (e.partId==pid && isTet4(e)) elems.push_back(&e);
    ar.elemCount = (int)elems.size();

    std::set<int> nids;
    for (auto* e : elems) { int t[4]; getTet(*e,t); for(int i=0;i<4;++i) nids.insert(t[i]); }
    ar.nodeCount = (int)nids.size();

    // BBox
    double bMin[3]={1e30,1e30,1e30}, bMax[3]={-1e30,-1e30,-1e30};
    for (int nid : nids) {
        const Node* n = mesh.getNode(nid); if(!n) continue;
        bMin[0]=std::min(bMin[0],n->position.x); bMax[0]=std::max(bMax[0],n->position.x);
        bMin[1]=std::min(bMin[1],n->position.y); bMax[1]=std::max(bMax[1],n->position.y);
        bMin[2]=std::min(bMin[2],n->position.z); bMax[2]=std::max(bMax[2],n->position.z);
    }
    double dims[3]={bMax[0]-bMin[0], bMax[1]-bMin[1], bMax[2]-bMin[2]};
    double minDim = *std::min_element(dims, dims+3);

    // Edge stats
    double eMin=1e30, eMax=0, eSum=0; int eCnt=0;
    for (auto* e : elems) {
        int t[4]; getTet(*e,t);
        const Node* n[4]; bool ok=true;
        for (int i=0;i<4;++i) { n[i]=mesh.getNode(t[i]); if(!n[i]) { ok=false; break; } }
        if (!ok) continue;
        for (int ei=0;ei<6;++ei) {
            double l = edgeLen(*n[TE[ei][0]], *n[TE[ei][1]]);
            eMin=std::min(eMin,l); eMax=std::max(eMax,l); eSum+=l; eCnt++;
        }
    }
    ar.edgeMin = eCnt>0 ? eMin : cfg.lcTarget;
    ar.edgeAvg = eCnt>0 ? eSum/eCnt : cfg.lcTarget;
    ar.edgeMax = eCnt>0 ? eMax : cfg.lcTarget;

    // lc_min
    double lcMin = cfg.lcMin;
    if (lcMin < 0 && cfg.minDt>0 && cfg.E>0 && cfg.nu>0 && cfg.density>0) {
        double cd = std::sqrt(cfg.E*(1-cfg.nu)/(cfg.density*(1+cfg.nu)*(1-2*cfg.nu)));
        lcMin = cfg.minDt * cd;
    }
    if (lcMin < 0) lcMin = ar.edgeMin * 0.8;

    // thin solid
    if (minDim > 0 && minDim < cfg.lcTarget * 0.6) {
        ar.thinDim = minDim;
        double lcThin = minDim / std::max(cfg.minLayersThin, 1);
        lcMin = std::min(lcMin, lcThin);
    }

    ar.lcMinEff = lcMin;
    ar.lcMaxEff = (cfg.lcMax > 0) ? cfg.lcMax : cfg.lcTarget * 2.0;

    // Attractors — cap at 1000 to keep geo file/Distance field manageable
    static constexpr int MAX_ATTRACTORS = 1000;
    if (cfg.adaptive) {
        double thresh = cfg.lcTarget * cfg.attractorRatio;
        std::set<std::pair<int,int>> seenEdge;
        for (auto* e : elems) {
            int t[4]; getTet(*e,t);
            const Node* n[4]; bool ok=true;
            for (int i=0;i<4;++i) { n[i]=mesh.getNode(t[i]); if(!n[i]) { ok=false; break; } }
            if (!ok) continue;

            // small edge → attractor at midpoint
            for (int ei=0;ei<6;++ei) {
                if ((int)ar.attractors.size() >= MAX_ATTRACTORS) break;
                int a=t[TE[ei][0]], b=t[TE[ei][1]];
                auto key=std::make_pair(std::min(a,b),std::max(a,b));
                if (seenEdge.count(key)) continue;
                double l = edgeLen(*n[TE[ei][0]], *n[TE[ei][1]]);
                if (l < thresh) {
                    seenEdge.insert(key);
                    ar.attractors.push_back({
                        (n[TE[ei][0]]->position.x + n[TE[ei][1]]->position.x)*0.5,
                        (n[TE[ei][0]]->position.y + n[TE[ei][1]]->position.y)*0.5,
                        (n[TE[ei][0]]->position.z + n[TE[ei][1]]->position.z)*0.5
                    });
                }
            }
            if ((int)ar.attractors.size() >= MAX_ATTRACTORS) break;

            // low quality → attractor at centroid
            double jac = tetScaledJac(mesh, *e);
            if (jac < cfg.attractorMinJac) {
                ++ar.badElemCount;
                double cx=0,cy=0,cz=0;
                for (int i=0;i<4;++i) { cx+=n[i]->position.x; cy+=n[i]->position.y; cz+=n[i]->position.z; }
                ar.attractors.push_back({cx/4,cy/4,cz/4});
            }
        }
    }
    return ar;
}

// ─────────────────────────────────────────────────────────────────────────────
// STL extraction (boundary faces of TET4 in target PID)
// ─────────────────────────────────────────────────────────────────────────────

static bool extractSTL(const Mesh& mesh, int pid,
                        const std::string& stlPath, std::string& err,
                        int* facesOut = nullptr) {
    using FaceKey = std::array<int,3>;
    std::map<FaceKey, std::pair<int, std::array<int,3>>> fc; // sorted_key → {count, winding}

    for (auto& [eid,e] : mesh.elements) {
        if (e.partId!=pid || !isTet4(e)) continue;
        int t[4]; getTet(e,t);
        for (int fi=0;fi<4;++fi) {
            int n0=t[TF[fi][0]], n1=t[TF[fi][1]], n2=t[TF[fi][2]];
            FaceKey key={n0,n1,n2}; std::sort(key.begin(),key.end());
            auto& entry = fc[key];
            entry.first++;
            if (entry.first==1) entry.second={n0,n1,n2};
        }
    }

    std::vector<std::array<int,3>> bndFaces;
    for (auto& [key,val] : fc)
        if (val.first==1) bndFaces.push_back(val.second);

    if (bndFaces.empty()) {
        err = "No boundary faces found for PID " + std::to_string(pid);
        return false;
    }

    // ── Connectivity filter: keep only the largest connected surface component.
    // Isolated tetrahedra produce 4-triangle closed groups that confuse Gmsh's
    // ClassifySurfaces (it loops forever trying to partition them).
    {
        int N = (int)bndFaces.size();
        // edge → adjacent face indices
        std::map<std::pair<int,int>, std::vector<int>> edgeAdj;
        for (int i = 0; i < N; ++i) {
            for (int ei = 0; ei < 3; ++ei) {
                int a = bndFaces[i][ei], b = bndFaces[i][(ei+1)%3];
                edgeAdj[{std::min(a,b), std::max(a,b)}].push_back(i);
            }
        }
        // BFS per component
        std::vector<int> comp(N, -1);
        std::vector<int> compSize;
        for (int start = 0; start < N; ++start) {
            if (comp[start] >= 0) continue;
            int c = (int)compSize.size();
            compSize.push_back(0);
            std::queue<int> q;
            q.push(start); comp[start] = c;
            while (!q.empty()) {
                int fi = q.front(); q.pop();
                compSize[c]++;
                for (int ei = 0; ei < 3; ++ei) {
                    int a = bndFaces[fi][ei], b = bndFaces[fi][(ei+1)%3];
                    auto it = edgeAdj.find({std::min(a,b), std::max(a,b)});
                    if (it == edgeAdj.end()) continue;
                    for (int fj : it->second)
                        if (comp[fj] < 0) { comp[fj] = c; q.push(fj); }
                }
            }
        }
        int largest = (int)(std::max_element(compSize.begin(), compSize.end()) - compSize.begin());
        std::vector<std::array<int,3>> filtered;
        filtered.reserve(compSize[largest]);
        for (int i = 0; i < N; ++i)
            if (comp[i] == largest) filtered.push_back(bndFaces[i]);
        bndFaces = std::move(filtered);
    }

    // ── Ghost face removal for HEX→TET conversion artifacts.
    // Stage 1: non-manifold edge filter (fast, O(n log n)).
    //   For edges shared by > 2 faces, keep the 2 most outward-facing ones.
    // Stage 2: if open edges remain, apply ray-casting parity filter (O(n²))
    //   to identify true outer surface faces from first-principles.
    {
        // Helper: compute per-face score (normal · (face_centroid - mesh_centroid))
        struct FData {
            double cx,cy,cz;   // face centroid
            double nx,ny,nz;   // face normal (unnormalised)
            double v0x,v0y,v0z, e1x,e1y,e1z, e2x,e2y,e2z; // for ray test
            bool valid;
        };

        auto buildFData = [&](const std::vector<std::array<int,3>>& faces,
                               double mcx, double mcy, double mcz) {
            std::vector<FData> fd(faces.size());
            for (int i = 0; i < (int)faces.size(); ++i) {
                const auto& fv = faces[i];
                const Node* n0=mesh.getNode(fv[0]),*n1=mesh.getNode(fv[1]),*n2=mesh.getNode(fv[2]);
                fd[i].valid = n0&&n1&&n2;
                if (!fd[i].valid) continue;
                fd[i].v0x=n0->position.x; fd[i].v0y=n0->position.y; fd[i].v0z=n0->position.z;
                fd[i].e1x=n1->position.x-fd[i].v0x; fd[i].e1y=n1->position.y-fd[i].v0y; fd[i].e1z=n1->position.z-fd[i].v0z;
                fd[i].e2x=n2->position.x-fd[i].v0x; fd[i].e2y=n2->position.y-fd[i].v0y; fd[i].e2z=n2->position.z-fd[i].v0z;
                fd[i].cx=(n0->position.x+n1->position.x+n2->position.x)/3.0;
                fd[i].cy=(n0->position.y+n1->position.y+n2->position.y)/3.0;
                fd[i].cz=(n0->position.z+n1->position.z+n2->position.z)/3.0;
                double ax=fd[i].e1x,ay=fd[i].e1y,az=fd[i].e1z;
                double bx=fd[i].e2x,by=fd[i].e2y,bz=fd[i].e2z;
                fd[i].nx=ay*bz-az*by; fd[i].ny=az*bx-ax*bz; fd[i].nz=ax*by-ay*bx;
                (void)mcx; (void)mcy; (void)mcz;
            }
            return fd;
        };

        // Möller–Trumbore ray-triangle test; returns t if hit, -1 otherwise
        auto rayT = [](double ox,double oy,double oz,
                        double dx,double dy,double dz,
                        const FData& f, double tMax) -> double {
            const double eps=1e-8;
            double hx=dy*f.e2z-dz*f.e2y, hy=dz*f.e2x-dx*f.e2z, hz=dx*f.e2y-dy*f.e2x;
            double a=f.e1x*hx+f.e1y*hy+f.e1z*hz;
            if (std::fabs(a)<eps) return -1.0;
            double inv=1.0/a;
            double sx=ox-f.v0x,sy=oy-f.v0y,sz=oz-f.v0z;
            double u=inv*(sx*hx+sy*hy+sz*hz);
            if (u<-eps||u>1+eps) return -1.0;
            double qx=sy*f.e1z-sz*f.e1y,qy=sz*f.e1x-sx*f.e1z,qz=sx*f.e1y-sy*f.e1x;
            double v=inv*(dx*qx+dy*qy+dz*qz);
            if (v<-eps||u+v>1+eps) return -1.0;
            double t=inv*(f.e2x*qx+f.e2y*qy+f.e2z*qz);
            return (t>eps && t<tMax-eps) ? t : -1.0;
        };
        // Wrapper for Stage 1 (only needs bool)
        auto rayHit = [&rayT](double ox,double oy,double oz,
                               double dx,double dy,double dz,
                               const FData& f, double tMax) -> bool {
            return rayT(ox,oy,oz,dx,dy,dz,f,tMax) > 0;
        };

        // Count open edges using coordinate-based keys (matches what Gmsh/STL see).
        // Node-ID keys can disagree with coordinate keys when ghost faces share
        // coordinates through different node ID paths.
        auto countOpenEdges = [&mesh](const std::vector<std::array<int,3>>& faces) -> int {
            std::map<std::pair<std::string,std::string>,int> ec;
            auto posKey = [&](int nid) -> std::string {
                const Node* nd = mesh.getNode(nid); if(!nd) return "";
                char buf[72];
                std::snprintf(buf, sizeof(buf), "%.6e,%.6e,%.6e",
                    nd->position.x, nd->position.y, nd->position.z);
                return buf;
            };
            for (auto& fv : faces)
                for (int e=0;e<3;++e) {
                    auto ka=posKey(fv[e]), kb=posKey(fv[(e+1)%3]);
                    if(ka.empty()||kb.empty()) continue;
                    if(ka>kb) std::swap(ka,kb);
                    ec[{ka,kb}]++;
                }
            int open=0;
            for (auto& [k,v] : ec) if (v==1) ++open;
            return open;
        };

        // Keep a copy of the original full boundary set for Stage 2 ray-casting.
        // Stage 1 can leave holes (removes faces that bridge non-manifold edges),
        // and a holey surface gives wrong parity counts. The original set has no
        // holes (just non-manifold edges) and is a better ray-casting reference.
        std::vector<std::array<int,3>> origFaces = bndFaces;

        // Compute mesh centroid
        double mcx=0,mcy=0,mcz=0; int vcnt=0;
        std::set<int> seen;
        for (auto& fv : bndFaces)
            for (int ni : fv) if (seen.insert(ni).second)
                if (auto* nd=mesh.getNode(ni)) { mcx+=nd->position.x; mcy+=nd->position.y; mcz+=nd->position.z; vcnt++; }
        if (vcnt>0) { mcx/=vcnt; mcy/=vcnt; mcz/=vcnt; }

        // ── Stage 1: non-manifold edge filter ──────────────────────────────
        {
            int N=(int)bndFaces.size();
            auto fd=buildFData(bndFaces,mcx,mcy,mcz);
            std::vector<double> score(N,0.0);
            for (int i=0;i<N;++i) {
                if(!fd[i].valid) continue;
                score[i]= fd[i].nx*(fd[i].cx-mcx) + fd[i].ny*(fd[i].cy-mcy) + fd[i].nz*(fd[i].cz-mcz);
            }
            std::map<std::pair<int,int>,std::vector<int>> edgeF;
            for (int i=0;i<N;++i)
                for (int e=0;e<3;++e) {
                    int a=bndFaces[i][e],b=bndFaces[i][(e+1)%3];
                    edgeF[{std::min(a,b),std::max(a,b)}].push_back(i);
                }
            std::vector<bool> remove(N,false);
            for (auto& [key,faces]:edgeF) {
                if (faces.size()<=2) continue;
                std::vector<std::pair<double,int>> sv;
                for (int fi:faces) sv.push_back({score[fi],fi});
                std::sort(sv.begin(),sv.end(),[](auto&a,auto&b){return a.first>b.first;});
                for (int i=2;i<(int)sv.size();++i) remove[sv[i].second]=true;
            }
            std::vector<std::array<int,3>> f1;
            f1.reserve(N);
            for (int i=0;i<N;++i) if(!remove[i]) f1.push_back(bndFaces[i]);
            bndFaces=std::move(f1);
        }

        // ── Stage 2: ray-casting parity filter if surface is not closed ─────
        if (countOpenEdges(bndFaces) > 0) {
            // Bounding-box surface-node filter.
            // In HEX→TET meshes, interior "ghost" faces always contain at least
            // one interior node (a node strictly inside the bounding box in all
            // 3 dimensions). True outer-surface faces have ALL nodes on the
            // bounding box (coordinate equals bmin or bmax within tolerance for
            // at least one dimension). This is O(n) and reliable for any mesh
            // whose outer surface aligns with its bounding box (rectangular solids,
            // the most common HEX mesh geometry).
            double bMin[3]={1e30,1e30,1e30}, bMax[3]={-1e30,-1e30,-1e30};
            for (auto& fv:origFaces)
                for (int ni:fv) if(auto* nd=mesh.getNode(ni)){
                    bMin[0]=std::min(bMin[0],nd->position.x); bMax[0]=std::max(bMax[0],nd->position.x);
                    bMin[1]=std::min(bMin[1],nd->position.y); bMax[1]=std::max(bMax[1],nd->position.y);
                    bMin[2]=std::min(bMin[2],nd->position.z); bMax[2]=std::max(bMax[2],nd->position.z);
                }
            double tol = std::max({bMax[0]-bMin[0], bMax[1]-bMin[1], bMax[2]-bMin[2]}) * 1e-5;

            auto onBBSurface = [&](int nid) -> bool {
                const Node* nd=mesh.getNode(nid); if(!nd) return false;
                return std::fabs(nd->position.x-bMin[0])<tol || std::fabs(nd->position.x-bMax[0])<tol ||
                       std::fabs(nd->position.y-bMin[1])<tol || std::fabs(nd->position.y-bMax[1])<tol ||
                       std::fabs(nd->position.z-bMin[2])<tol || std::fabs(nd->position.z-bMax[2])<tol;
            };

            std::vector<std::array<int,3>> f2;
            for (auto& fv : origFaces)
                if (onBBSurface(fv[0]) && onBBSurface(fv[1]) && onBBSurface(fv[2]))
                    f2.push_back(fv);
            bndFaces = std::move(f2);
        }
    }

    // Final manifold check — warn but do not abort; let Gmsh try
    {
        std::map<std::pair<int,int>,int> ec;
        for (auto& fv : bndFaces)
            for (int e=0;e<3;++e) {
                int a=fv[e], b=fv[(e+1)%3];
                ec[{std::min(a,b),std::max(a,b)}]++;
            }
        int openEdges=0;
        for (auto& [k,v]:ec) if(v==1) ++openEdges;
        if (openEdges > 0) {
            // Surface still not fully closed after all filters; Gmsh may fail.
            // This can happen with HEX→TET conversion meshes.
            // We still write the STL and let Gmsh try.
        }
    }

    if (facesOut) *facesOut = (int)bndFaces.size();
    std::ofstream f(stlPath);
    if (!f.is_open()) { err = "Cannot write STL: " + stlPath; return false; }

    f << std::scientific;
    f << "solid part_" << pid << "\n";
    for (auto& face : bndFaces) {
        const Node* n[3];
        bool ok=true;
        for (int i=0;i<3;++i) { n[i]=mesh.getNode(face[i]); if(!n[i]){ok=false;break;} }
        if (!ok) continue;
        double ax=n[1]->position.x-n[0]->position.x, ay=n[1]->position.y-n[0]->position.y, az=n[1]->position.z-n[0]->position.z;
        double bx=n[2]->position.x-n[0]->position.x, by=n[2]->position.y-n[0]->position.y, bz=n[2]->position.z-n[0]->position.z;
        double nx=ay*bz-az*by, ny=az*bx-ax*bz, nz=ax*by-ay*bx;
        double nl=std::sqrt(nx*nx+ny*ny+nz*nz);
        if (nl>1e-15){nx/=nl;ny/=nl;nz/=nl;}
        f << "  facet normal " << nx << " " << ny << " " << nz << "\n";
        f << "    outer loop\n";
        for (int i=0;i<3;++i)
            f << "      vertex " << n[i]->position.x << " " << n[i]->position.y << " " << n[i]->position.z << "\n";
        f << "    endloop\n";
        f << "  endfacet\n";
    }
    f << "endsolid part_" << pid << "\n";
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gmsh .geo script
// ─────────────────────────────────────────────────────────────────────────────

static int algoCode(const std::string& a) {
    if (a=="del3d")     return 1;
    if (a=="frontal3d") return 4;
    return 10; // hxt
}

// Forward-slashify path for geo string literals (Gmsh uses / even on Windows)
static std::string fwdSlash(std::string p) {
    for (auto& c : p) if (c=='\\') c='/';
    return p;
}
// Backslashify path for Windows cmd.exe / batch files
static std::string backSlash(std::string p) {
    for (auto& c : p) if (c=='/') c='\\';
    return p;
}

static bool writeGeoScript(const std::string& geoPath,
                            const std::string& stlPath,
                            const std::string& mshPath,
                            const AnalysisResult& ar,
                            const Cfg& cfg, std::string& err) {
    std::ofstream f(geoPath);
    if (!f.is_open()) { err = "Cannot write geo: " + geoPath; return false; }

    f << "// KooRemapper meshfix\n";
    f << "Merge \"" << fwdSlash(stlPath) << "\";\n";
    // Classify STL surface triangles into topological surfaces/curves/points,
    // then create parametric geometry so a volume can be defined.
    // Angle threshold 40° works for most engineering geometry.
    f << "ClassifySurfaces{40 * Pi / 180, 1, 1, Pi / 2};\n";
    f << "CreateGeometry;\n";
    f << "s() = Surface{:};\n";
    f << "sl = newsl; Surface Loop(sl) = {s()};\n";
    f << "v  = newv;  Volume(v) = {sl};\n\n";

    if (cfg.adaptive && !ar.attractors.empty()) {
        f << std::scientific;
        for (int i=0;i<(int)ar.attractors.size();++i)
            f << "Point(" << (i+1) << ") = {"
              << ar.attractors[i].x << ","
              << ar.attractors[i].y << ","
              << ar.attractors[i].z << "};\n";
        f << "\n";

        f << "Field[1] = Distance;\nField[1].PointsList = {";
        for (int i=0;i<(int)ar.attractors.size();++i) { if(i) f<<","; f<<(i+1); }
        f << "};\n\n";

        double distMin = ar.lcMinEff * 2.0;
        double distMax = ar.lcMinEff * cfg.decayFactor;
        f << "Field[2] = Threshold;\n"
          << "Field[2].InField = 1;\n"
          << "Field[2].SizeMin = " << ar.lcMinEff << ";\n"
          << "Field[2].SizeMax = " << ar.lcMaxEff << ";\n"
          << "Field[2].DistMin = " << distMin << ";\n"
          << "Field[2].DistMax = " << distMax << ";\n\n";

        f << "Field[3] = MathEval;\n"
          << "Field[3].F = \"" << cfg.lcTarget << "\";\n\n";

        f << "Field[4] = Min;\nField[4].FieldsList = {2,3};\n"
          << "Background Field = 4;\n\n";
    }

    f << "Mesh.CharacteristicLengthMin = " << ar.lcMinEff << ";\n"
      << "Mesh.CharacteristicLengthMax = " << ar.lcMaxEff << ";\n"
      << "Mesh.CharacteristicLengthExtendFromBoundary = 1;\n"
      << "Mesh.Algorithm3D = " << algoCode(cfg.algorithm) << ";\n"
      << "Mesh.Optimize = 1;\n"
      << "Mesh.OptimizeNetgen = " << (cfg.optimizeNetgen?1:0) << ";\n"
      << "Mesh.MshFileVersion = 2.2;\n\n"
      << "Mesh 3;\n"
      << "Save \"" << fwdSlash(mshPath) << "\";\n";
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gmsh subprocess
// ─────────────────────────────────────────────────────────────────────────────

static bool runGmsh(const std::string& gmshExe,
                    const std::string& geoPath,
                    const std::string& mshPath,   // check for output as success criterion
                    const std::string& logPath, std::string& err) {
#ifdef _WIN32
    // All paths normalized to backslash for cmd.exe; geo path stays forward-slash for Gmsh
    std::string gmshNative = backSlash(gmshExe);
    std::string geoNative  = backSlash(geoPath);
    std::string logNative  = backSlash(logPath);
    // Use a .bat file: avoids system() double-quote nesting on Windows
    std::string batPath = backSlash(logPath) + ".bat";
    {
        std::ofstream bat(batPath);
        bat << "@echo off\r\n";
        bat << "\"" << gmshNative << "\" \"" << geoNative << "\" -v 3 -parse_and_exit"
            << " > \"" << logNative << "\" 2>&1\r\n";
    }
    // cmd /c "batpath" — single quote level, no nesting
    std::string cmd = "cmd /c \"" + batPath + "\"";
    int ret = std::system(cmd.c_str());
    { std::error_code ec; fs::remove(batPath, ec); }
#else
    std::string cmd = "\"" + gmshExe + "\" \"" + geoPath + "\" -v 3 -parse_and_exit"
                    + " > \"" + logPath + "\" 2>&1";
    int ret = std::system(cmd.c_str());
#endif
    // Gmsh may return exit code 1 for warnings (e.g. ClassifySurfaces recursion)
    // even when the mesh was successfully written. Trust the output file.
    if (fs::exists(mshPath)) return true;
    err = "Gmsh failed (exit " + std::to_string(ret) + "). See log: " + logPath;
    return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// MSH2 parser
// ─────────────────────────────────────────────────────────────────────────────

struct MshNode { int id; double x,y,z; };
struct MshElem { int id; std::array<int,4> nodes; }; // TET4 only

static bool parseMsh2(const std::string& path,
                       std::vector<MshNode>& nodes,
                       std::vector<MshElem>& elems,
                       std::string& err) {
    std::ifstream f(path);
    if (!f.is_open()) { err = "Cannot open Gmsh output: " + path; return false; }

    std::string line;
    enum { NONE, NODE_S, ELEM_S } sec = NONE;
    bool countRead = false;

    while (std::getline(f, line)) {
        while (!line.empty() && (line.back()=='\r'||line.back()=='\n')) line.pop_back();
        if (line=="$MeshFormat"||line=="$EndMeshFormat") continue;
        if (line=="$Nodes")        { sec=NODE_S; countRead=false; continue; }
        if (line=="$EndNodes")     { sec=NONE; continue; }
        if (line=="$Elements")     { sec=ELEM_S; countRead=false; continue; }
        if (line=="$EndElements")  { sec=NONE; continue; }
        if (!line.empty()&&line[0]=='$') { sec=NONE; continue; }

        std::istringstream iss(line);
        if (sec==NODE_S) {
            if (!countRead) { countRead=true; continue; } // skip count line
            MshNode n;
            if (iss >> n.id >> n.x >> n.y >> n.z) nodes.push_back(n);
        } else if (sec==ELEM_S) {
            if (!countRead) { countRead=true; continue; }
            int id,type,ntags;
            if (!(iss>>id>>type>>ntags)) continue;
            for (int i=0;i<ntags;++i) { int tmp; iss>>tmp; }
            if (type==4) { // TET4
                MshElem e; e.id=id;
                if (iss>>e.nodes[0]>>e.nodes[1]>>e.nodes[2]>>e.nodes[3])
                    elems.push_back(e);
            }
            // type 2 = TRI3 surface elements → ignore
        }
    }
    if (nodes.empty()) { err="No nodes in Gmsh output (MSH2 expected)"; return false; }
    if (elems.empty()) { err="No TET4 elements in Gmsh output";          return false; }
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Build final node/element lists with resolved model IDs
// ─────────────────────────────────────────────────────────────────────────────

struct FinalNode { int id; double x,y,z; };
struct FinalElem { int id; std::array<int,4> nodes; };

// For fixed mode: match Gmsh surface nodes to original model nodes by coordinate
static std::map<int,int> matchBoundaryNodes(const Mesh& mesh, int pid,
                                             const std::vector<MshNode>& gmshNodes,
                                             double tol) {
    // Build set of boundary node IDs (nodes in boundary faces of PID)
    using FaceKey = std::array<int,3>;
    std::map<FaceKey,int> fc;
    for (auto& [eid,e] : mesh.elements) {
        if (e.partId!=pid||!isTet4(e)) continue;
        int t[4]; getTet(e,t);
        for (int fi=0;fi<4;++fi) {
            FaceKey key={t[TF[fi][0]],t[TF[fi][1]],t[TF[fi][2]]};
            std::sort(key.begin(),key.end());
            fc[key]++;
        }
    }
    std::set<int> bndIds;
    for (auto& [key,cnt] : fc)
        if (cnt==1) for (int n : key) bndIds.insert(n);

    double tol2=tol*tol;
    std::map<int,int> result; // gmsh_id → orig_model_id
    for (auto& gn : gmshNodes) {
        for (int oid : bndIds) {
            const Node* on=mesh.getNode(oid); if(!on) continue;
            double dx=gn.x-on->position.x, dy=gn.y-on->position.y, dz=gn.z-on->position.z;
            if (dx*dx+dy*dy+dz*dz<=tol2) { result[gn.id]=oid; break; }
        }
    }
    return result;
}

static void buildFinalMesh(const Mesh& mesh, int pid,
                            const Cfg& cfg,
                            const std::vector<MshNode>& gmshNodes,
                            const std::vector<MshElem>& gmshElems,
                            std::vector<FinalNode>& finalNodes,
                            std::vector<FinalElem>& finalElems,
                            int& nodesAdded, int& elemsAdded,
                            ConsoleOutput& console) {
    int maxNid = mesh.getMaxNodeId();
    int maxEid = mesh.getMaxElementId();

    std::map<int,int> gmshToFinal; // gmsh_id → final model node ID

    if (cfg.boundaryNodes == "fixed") {
        // Match Gmsh surface nodes to original model boundary nodes
        auto bndMap = matchBoundaryNodes(mesh, pid, gmshNodes, cfg.snapTolerance);
        console.keyValue("Boundary nodes matched", std::to_string(bndMap.size()));

        // Assign final IDs: boundary → orig, interior → new sequential
        int counter = 0;
        for (auto& gn : gmshNodes) {
            auto it = bndMap.find(gn.id);
            if (it != bndMap.end()) {
                gmshToFinal[gn.id] = it->second; // keep original ID
            } else {
                int newId = maxNid + 1 + counter++;
                gmshToFinal[gn.id] = newId;
                finalNodes.push_back({newId, gn.x, gn.y, gn.z});
            }
        }
    } else {
        // free / snap: all gmsh nodes → new IDs
        int counter = 0;
        for (auto& gn : gmshNodes) {
            int newId = maxNid + 1 + counter++;
            gmshToFinal[gn.id] = newId;
            finalNodes.push_back({newId, gn.x, gn.y, gn.z});
        }

        if (cfg.boundaryNodes == "snap") {
            // Snap new boundary nodes to nearest neighbor-part nodes within tolerance
            // Build set of all non-PID nodes
            std::vector<const Node*> neighborNodes;
            for (auto& [nid,nd] : mesh.nodes) {
                // Only keep nodes used by other parts
                bool usedByOther = false;
                for (auto& [eid,e] : mesh.elements) {
                    if (e.partId==pid) continue;
                    for (int i=0;i<Element::NUM_NODES;++i)
                        if (e.nodeIds[i]==nid) { usedByOther=true; break; }
                    if (usedByOther) break;
                }
                if (usedByOther) neighborNodes.push_back(&nd);
            }
            double tol2 = cfg.snapTolerance * cfg.snapTolerance;
            int snapped = 0;
            for (auto& fn : finalNodes) {
                for (auto* nn : neighborNodes) {
                    double dx=fn.x-nn->position.x, dy=fn.y-nn->position.y, dz=fn.z-nn->position.z;
                    if (dx*dx+dy*dy+dz*dz <= tol2) {
                        // remap: fn.id → nn->id
                        for (auto& [gid,fid] : gmshToFinal)
                            if (fid==fn.id) gmshToFinal[gid]=nn->id;
                        fn.id = -1; // mark for removal (duplicated with neighbor)
                        ++snapped;
                        break;
                    }
                }
            }
            // Remove snapped-away nodes
            finalNodes.erase(
                std::remove_if(finalNodes.begin(), finalNodes.end(),
                               [](const FinalNode& fn){ return fn.id<0; }),
                finalNodes.end());
            if (snapped > 0)
                console.keyValue("Snap: nodes merged to neighbor", std::to_string(snapped));
        }
    }

    // Build final elements
    int eCounter = 0;
    for (auto& ge : gmshElems) {
        FinalElem fe;
        fe.id = maxEid + 1 + eCounter++;
        bool ok = true;
        for (int i=0;i<4;++i) {
            auto it = gmshToFinal.find(ge.nodes[i]);
            if (it==gmshToFinal.end()) { ok=false; break; }
            fe.nodes[i] = it->second;
        }
        if (ok) finalElems.push_back(fe);
    }

    nodesAdded = (int)finalNodes.size();
    elemsAdded = (int)finalElems.size();
}

// ─────────────────────────────────────────────────────────────────────────────
// Quality check on Gmsh output
// ─────────────────────────────────────────────────────────────────────────────

static void reportQuality(const std::vector<MshNode>& nodes,
                           const std::vector<MshElem>& elems,
                           double warnThr, ConsoleOutput& console) {
    std::map<int,std::array<double,3>> nmap;
    for (auto& n : nodes) nmap[n.id]={n.x,n.y,n.z};

    double minJ=1e30, maxJ=-1e30, sumJ=0; int bad=0;
    for (auto& e : elems) {
        auto& p0=nmap[e.nodes[0]]; auto& p1=nmap[e.nodes[1]];
        auto& p2=nmap[e.nodes[2]]; auto& p3=nmap[e.nodes[3]];
        double v1x=p1[0]-p0[0],v1y=p1[1]-p0[1],v1z=p1[2]-p0[2];
        double v2x=p2[0]-p0[0],v2y=p2[1]-p0[1],v2z=p2[2]-p0[2];
        double v3x=p3[0]-p0[0],v3y=p3[1]-p0[1],v3z=p3[2]-p0[2];
        double vol=(v1x*(v2y*v3z-v2z*v3y)-v1y*(v2x*v3z-v2z*v3x)+v1z*(v2x*v3y-v2y*v3x))/6.0;
        double maxE=0;
        int ns[4]={e.nodes[0],e.nodes[1],e.nodes[2],e.nodes[3]};
        const int eIdx[6][2]={{0,1},{0,2},{0,3},{1,2},{1,3},{2,3}};
        for (auto& ed:eIdx) {
            auto& a=nmap[ns[ed[0]]]; auto& b=nmap[ns[ed[1]]];
            double dx=a[0]-b[0],dy=a[1]-b[1],dz=a[2]-b[2];
            maxE=std::max(maxE,std::sqrt(dx*dx+dy*dy+dz*dz));
        }
        double jac=(maxE>1e-15)?6.0*vol/(maxE*maxE*maxE)*std::sqrt(2.0):0.0;
        minJ=std::min(minJ,jac); maxJ=std::max(maxJ,jac); sumJ+=jac;
        if (jac<warnThr) ++bad;
    }
    double avgJ = elems.empty()?0.0:sumJ/elems.size();
    auto fmt=[](double v){ std::ostringstream s; s<<v; return s.str(); };
    console.keyValue("Min scaled Jacobian", fmt(minJ));
    console.keyValue("Avg scaled Jacobian", fmt(avgJ));
    console.keyValue("Max scaled Jacobian", fmt(maxJ));
    if (bad>0) console.warning(std::to_string(bad)+" elements below warn_min_jac="+fmt(warnThr));
    else        console.success("All elements above quality threshold");
}

// ─────────────────────────────────────────────────────────────────────────────
// Raw line splice: remove old PID nodes/elements, insert new ones
// ─────────────────────────────────────────────────────────────────────────────

static int parseFirstInt(const std::string& s) {
    std::istringstream iss(s); int v=-1; iss>>v; return v;
}

static std::string fmtNode(const FinalNode& n) {
    char buf[128];
    std::snprintf(buf,sizeof(buf),"%8d%16.8f%16.8f%16.8f", n.id, n.x, n.y, n.z);
    return buf;
}
static std::string fmtElem(const FinalElem& e, int pid) {
    // TET4 as degenerate HEX8: n0 n1 n2 n3 n3 n3 n3 n3
    char buf[128];
    std::snprintf(buf,sizeof(buf),"%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d",
        e.id, pid,
        e.nodes[0],e.nodes[1],e.nodes[2],e.nodes[3],
        e.nodes[3],e.nodes[3],e.nodes[3],e.nodes[3]);
    return buf;
}

static bool spliceMesh(const std::string& modelPath,
                        const std::string& outputPath,
                        int pid,
                        const std::set<int>& removeNodes,
                        const std::set<int>& removeElems,
                        const std::vector<FinalNode>& newNodes,
                        const std::vector<FinalElem>& newElems,
                        std::string& err) {
    // Buffer all input lines first (handles model==output case safely)
    std::vector<std::string> rawLines;
    {
        std::ifstream f(modelPath);
        if (!f.is_open()) { err="Cannot open model: "+modelPath; return false; }
        std::string line;
        while (std::getline(f, line)) {
            while (!line.empty()&&line.back()=='\r') line.pop_back();
            rawLines.push_back(line);
        }
    }

    std::ofstream out(outputPath);
    if (!out.is_open()) { err="Cannot write output: "+outputPath; return false; }

    enum { NONE, IN_NODE, IN_ELEM } sec = NONE;
    bool insertedNew = false;

    auto flushNew = [&]() {
        if (insertedNew) return;
        insertedNew = true;
        out << "*NODE\n";
        for (auto& n : newNodes) out << fmtNode(n) << "\n";
        out << "*ELEMENT_SOLID\n";
        for (auto& e : newElems) out << fmtElem(e, pid) << "\n";
    };

    for (auto& line : rawLines) {
        // Keyword detection
        std::string trimmed = line;
        size_t p = trimmed.find_first_not_of(" \t");
        std::string up;
        if (p!=std::string::npos && trimmed[p]=='*') {
            up = trimmed.substr(p);
            for (auto& c : up) c=(char)std::toupper((unsigned char)c);
        }

        if (!up.empty()) {
            if (up=="*END") {
                flushNew(); // ensure new data precedes *END
                sec=NONE;
                out << line << "\n";
                continue;
            }
            // *NODE but not *NODE_RIGID_BODY / *NODE_SET / etc.
            bool isNode = up.rfind("*NODE",0)==0
                       && up.find("RIGID")==std::string::npos
                       && up.find("SET")  ==std::string::npos
                       && up.find("TO_SURFACE")==std::string::npos;
            bool isElem = up.rfind("*ELEMENT_SOLID",0)==0;
            sec = isNode ? IN_NODE : isElem ? IN_ELEM : NONE;
            out << line << "\n";
            continue;
        }

        // Comment
        if (!line.empty() && line[0]=='$') { out << line << "\n"; continue; }

        // Data
        if (sec==IN_NODE) {
            int nid = parseFirstInt(line);
            if (nid>0 && removeNodes.count(nid)) continue; // skip removed
        } else if (sec==IN_ELEM) {
            int eid = parseFirstInt(line);
            if (eid>0 && removeElems.count(eid)) continue; // skip removed
        }
        out << line << "\n";
    }

    // File had no *END
    if (!insertedNew) {
        flushNew();
        out << "*END\n";
    }
    return true;
}

} // anonymous namespace

// ─────────────────────────────────────────────────────────────────────────────
// Public entry point
// ─────────────────────────────────────────────────────────────────────────────

int runMeshFix(const char* configPath, ConsoleOutput& console) {
    Timer timer; timer.start();

    // 1. Config
    Cfg cfg;
    std::string err;
    if (!readConfig(configPath, cfg, err)) { console.error("Config: "+err); return 1; }

    // 2. Gmsh
    std::string gmshExe = findGmshExe();
    if (gmshExe.empty()) {
        console.error("Gmsh not found — place gmsh.exe in dist/gmsh/ or dist/gmsh-<ver>/ next to KooRemapper.exe");
        return 1;
    }
    console.keyValue("Gmsh", gmshExe);

    // 3. Load model
    console.info("Loading: " + cfg.model);
    KFileReader reader;
    Mesh mesh = reader.readFile(cfg.model);
    if (mesh.getNodeCount() == 0) {
        console.error("Load failed or empty mesh: " + cfg.model); return 1;
    }
    {
        int cnt=0;
        for (auto& [eid,e] : mesh.elements) if (e.partId==cfg.pid&&isTet4(e)) ++cnt;
        if (cnt==0) {
            console.error("No TET4 elements for PID "+std::to_string(cfg.pid)); return 1;
        }
        console.keyValue("PID "+std::to_string(cfg.pid)+" TET4", std::to_string(cnt));
    }

    // 4. Analyze
    console.header("Mesh Analysis");
    AnalysisResult ar = analyzePart(mesh, cfg.pid, cfg);
    {
        std::ostringstream s;
        s << ar.nodeCount << " nodes / " << ar.elemCount << " elements";
        console.println("  " + s.str());
    }
    {
        std::ostringstream s;
        s << "edge min/avg/max: " << ar.edgeMin << " / " << ar.edgeAvg << " / " << ar.edgeMax;
        console.println("  " + s.str());
    }
    {
        std::ostringstream s; s << "lc_min=" << ar.lcMinEff << "  lc_max=" << ar.lcMaxEff;
        console.println("  " + s.str());
    }
    if (ar.thinDim > 0) {
        std::ostringstream s; s << ar.thinDim << " (thin solid → " << cfg.minLayersThin << " layers)";
        console.warning("Thin dimension: " + s.str());
    }
    if (cfg.adaptive)
        console.keyValue("Attractors", std::to_string(ar.attractors.size()));
    if (ar.badElemCount > 0)
        console.warning("Bad Jacobian elements: " + std::to_string(ar.badElemCount));

    // Temp paths alongside output — use fs::path for native separator consistency
    fs::path outDir = fs::path(cfg.output).parent_path();
    if (outDir.empty()) outDir = fs::path(".");
    std::string stem = fs::path(cfg.output).stem().string();
    auto tempPath = [&](const std::string& ext) {
        return (outDir / (stem + "__mf" + ext)).string();
    };
    std::string stlPath = tempPath(".stl");
    std::string geoPath = tempPath(".geo");
    std::string mshPath = tempPath(".msh");
    std::string logPath = tempPath(".log");

    // 5. STL
    console.info("Extracting boundary surface...");
    int stlFaces = 0;
    if (!extractSTL(mesh, cfg.pid, stlPath, err, &stlFaces)) { console.error(err); return 1; }
    console.keyValue("STL faces (after filter)", std::to_string(stlFaces));

    // 6. Geo script
    if (!writeGeoScript(geoPath, stlPath, mshPath, ar, cfg, err)) { console.error(err); return 1; }

    // 7. Gmsh
    console.info("Running Gmsh (" + cfg.algorithm + ")...");
    console.println("  geo: " + geoPath);
    console.println("  stl: " + stlPath);
    if (!runGmsh(gmshExe, geoPath, mshPath, logPath, err)) {
        console.error(err);
        // Print log (kept for diagnosis)
        std::ifstream logF(logPath); std::string ln;
        int logLines = 0;
        while (std::getline(logF,ln)) { console.println("  "+ln); ++logLines; }
        if (logLines==0) console.println("  (log empty — bat/redirect may have failed)");
        // Do NOT delete temp files on failure so user can inspect
        console.println("  Temp files kept for inspection:");
        console.println("    " + stlPath);
        console.println("    " + geoPath);
        console.println("    " + logPath);
        return 1;
    }
    console.success("Gmsh done");

    // 8. Parse MSH2
    std::vector<MshNode> gmshNodes;
    std::vector<MshElem> gmshElems;
    if (!parseMsh2(mshPath, gmshNodes, gmshElems, err)) {
        console.error(err);
        // Keep temp files so user can inspect the STL/geo/msh
        console.println("  Temp files kept for inspection:");
        console.println("    " + stlPath);
        console.println("    " + geoPath);
        console.println("    " + mshPath);
        return 1;
    }
    console.keyValue("Gmsh nodes",    std::to_string(gmshNodes.size()));
    console.keyValue("Gmsh TET4",     std::to_string(gmshElems.size()));

    // 9. Quality of Gmsh output
    if (cfg.qualityCheck) {
        console.header("Output Quality");
        reportQuality(gmshNodes, gmshElems, cfg.warnMinJac, console);
    }

    // 10. Build final IDs
    std::vector<FinalNode> finalNodes;
    std::vector<FinalElem> finalElems;
    int nodesAdded=0, elemsAdded=0;
    buildFinalMesh(mesh, cfg.pid, cfg,
                   gmshNodes, gmshElems,
                   finalNodes, finalElems,
                   nodesAdded, elemsAdded, console);
    console.keyValue("Nodes added to model",    std::to_string(nodesAdded));
    console.keyValue("Elements added to model", std::to_string(elemsAdded));

    // 11. Collect IDs to remove from model
    std::set<int> removeNodes, removeElems;
    for (auto& [eid,e] : mesh.elements) {
        if (e.partId!=cfg.pid||!isTet4(e)) continue;
        removeElems.insert(eid);
        int t[4]; getTet(e,t);
        for (int i=0;i<4;++i) removeNodes.insert(t[i]);
    }
    // Keep nodes shared with other parts
    for (auto& [eid,e] : mesh.elements) {
        if (e.partId==cfg.pid) continue;
        for (int i=0;i<Element::NUM_NODES;++i)
            removeNodes.erase(e.nodeIds[i]);
    }
    // In fixed mode, keep original boundary nodes (they stay in model untouched)
    if (cfg.boundaryNodes=="fixed") {
        auto bndMap = matchBoundaryNodes(mesh, cfg.pid, gmshNodes, cfg.snapTolerance);
        for (auto& [gid,oid] : bndMap) removeNodes.erase(oid);
    }

    // 12. Splice
    console.info("Writing output: " + cfg.output);
    if (!spliceMesh(cfg.model, cfg.output, cfg.pid,
                    removeNodes, removeElems, finalNodes, finalElems, err)) {
        console.error(err);
        for (auto& p : {stlPath,geoPath,mshPath,logPath}) { std::error_code ec; fs::remove(p,ec); }
        return 1;
    }
    console.success("Output written");

    // 13. Cleanup temp files
    for (auto& p : {stlPath, geoPath, mshPath, logPath}) {
        std::error_code ec; fs::remove(p, ec);
    }

    timer.stop();
    console.info("Total time: " + timer.elapsedString());
    return 0;
}
