// =============================================================
// BatteryMeshStacked.cpp — Stacked battery cell mesh generation
// =============================================================
// Equivalent to references/Battery_source_4/generate_mesh_stacked.py
//
// Z-stack (dome_cap=false):
//   z += t_pouch                 : skip bottom pouch face
//   z += t_buf  [solid elec]     : bottom electrolyte buffer
//   per UC:
//     Al CC  SHELL @ z           (NO z advance — SHELL has no geometry thickness)
//     Cathode SOLID z..z+t_cat   (z += t_cat)
//     Sep    SHELL @ z           (NO z advance)
//     Anode  SOLID z..z+t_ano   (z += t_ano)
//     Cu CC  SHELL @ z           (NO z advance, grid reused by next UC Al CC)
//   z += t_buf  [solid elec]     : top electrolyte buffer
//   z += t_pouch                 : skip top pouch face
//   TotalZ = 2*t_pouch + 2*t_buf + n_uc*(t_cat+t_ano)
//          = 2*0.153 + 2*0.200 + 11*(0.065+0.070) = 2.191mm  ✓
//
// Node sharing (matches Python MeshGenerator):
//   UC-internal : Al CC bot ≡ Cathode bot; Cathode top ≡ Sep ≡ Anode bot;
//                 Anode top ≡ Cu CC
//   UC-boundary : Cu CC(k) top reused as Al CC(k+1) bot
//   Electrolyte : independent nodes (TIED contact to jellyroll)
// =============================================================

#include "BatteryMeshStacked.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"

#include <ostream>
#include <sstream>
#include <vector>
#include <set>
#include <unordered_set>
#include <algorithm>
#include <cmath>
#include <cstdio>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace bat {

// ─────────────────────────────────────────────────────────────
// Grid: (ny+1)*(nx+1) node IDs, row-major [iy*(nx+1)+ix]
// ─────────────────────────────────────────────────────────────
using Grid = std::vector<int>;

static inline int gAt(const Grid& g, int ix, int iy, int stride) {
    return g[iy * stride + ix];
}

// ─────────────────────────────────────────────────────────────
// BatMeshGen — streaming mesh generator
// Mirrors Python MeshGenerator class structure exactly.
// ─────────────────────────────────────────────────────────────
class BatMeshGen {
public:
    const BatteryConfig& cfg;
    int    nx, ny;       // element counts (node counts = nx+1, ny+1)
    double dx, dy;       // element sizes
    double meshSize;

    std::ostringstream nodeBuf, shellBuf, solidBuf, rigidBuf;
    int nextNid = 1, nextEid = 1;
    int nNodes = 0, nShells = 0, nSolids = 0, nRigids = 0;

    // Node position store (for airbag signed-volume check)
    struct Vec3 { double x,y,z; };
    std::vector<Vec3> nodePos;  // index = nid-1

    std::vector<int> partIds;

    struct TipRow { double z; std::vector<int> nids; };
    std::vector<TipRow> posTipRows, negTipRows;
    std::vector<std::pair<double,double>> tabXRanges;

    std::vector<int> nsetFixBottomEdge;
    std::vector<int> nsetStackTop;
    std::vector<int> nsetImpactorAll;
    std::vector<int> nsetGroundPlateAll;

    std::vector<int> psetPouch, psetAllCell;
    std::vector<int> psetAllCathode, psetAllAnode, psetSep;
    std::vector<int> psetAlCC, psetCuCC, psetElectrolyte;
    std::vector<int> psetImpactor, psetGroundPlate;

    // airbag_fill: pouch shell segments for AIRBAG_LINEAR_FLUID
    struct SegQuad { int pid,n1,n2,n3,n4; };
    std::vector<SegQuad> pouchSegments;

    // INITIAL_STRESS_SHELL: pouch element IDs
    std::vector<int> pouchEids;

    // EM RANDLES: Al_CC outer bottom grid (UC0), Cu_CC outer top grid (last UC)
    std::vector<int> emAlCCOuterNids;  // SID 201
    std::vector<int> emCuCCOuterNids;  // SID 202

    // per-UC tshell pid tracking for solidBuf routing
    std::set<int> tshellPids;

    MeshStats stats;

    // ── jellyroll fillet parameters (computed in constructor) ──
    int    jNF  = 0;     // adaptive fillet segments per corner
    int    jIFl = 0, jIFr = 0, jJFf = 0, jJFb = 0;
    double jRi  = 0.0;   // inner fillet radius = R - ht
    std::vector<double> jellyXs, jellyYs;

    // ── constructor ──────────────────────────────────────────
    explicit BatMeshGen(const BatteryConfig& c) : cfg(c) {
        meshSize = batteryMeshSize(c.tier);
        nx = (int)std::round(c.geo.cellWidth  / meshSize);
        ny = (int)std::round(c.geo.cellHeight / meshSize);
        if (nx < 1) nx = 1;
        if (ny < 1) ny = 1;
        dx = c.geo.cellWidth  / nx;
        dy = c.geo.cellHeight / ny;
        buildJellyCoords();
    }

    // ── buildJellyCoords ─────────────────────────────────────
    // Jellyroll uses a PLAIN UNIFORM RECTANGULAR GRID — no corner fillet.
    //
    // Rationale: arc-projection in a structured grid always creates at least
    // one element with angle > 135° at the outermost corner node (the 45°
    // arc point is flanked by two adjacent arc nodes, making the inner angle
    // approach 169° for nF=3 or 135° for nF=1). For all tiers the fillet
    // radius (Ri ≈ 1.9 mm) is small relative to the cell (66 × 90 mm), so
    // a rectangular jellyroll is structurally equivalent. The pouch outer
    // shell retains its arc via createPouchBox.
    void buildJellyCoords() {
        double W = cfg.geo.cellWidth;
        double H = cfg.geo.cellHeight;
        jNF = 0; jRi = 0.0;
        jIFl = 0; jIFr = nx; jJFf = 0; jJFb = ny;
        jellyXs.resize(nx + 1);
        jellyYs.resize(ny + 1);
        for (int i = 0; i <= nx; ++i) jellyXs[i] = i * (W / nx);
        for (int i = 0; i <= ny; ++i) jellyYs[i] = i * (H / ny);
    }

    // ── add_node ──────────────────────────────────────────────
    int addNode(double x, double y, double z) {
        char buf[128];
        std::snprintf(buf, sizeof(buf),
            "%8d%16.6f%16.6f%16.6f\n", nextNid, x, y, z);
        nodeBuf << buf;
        nodePos.push_back({x, y, z});
        ++nNodes;
        return nextNid++;
    }

    // ── add_shell ────────────────────────────────────────────
    static bool isPouchPid(int pid) {
        return (pid == PID_POUCH_TOP || pid == PID_POUCH_BOTTOM ||
                pid == PID_POUCH_SIDE);
    }

    int addShell(int pid, int n1, int n2, int n3, int n4) {
        int u[4] = {n1,n2,n3,n4};
        std::sort(u, u+4);
        if ((int)(std::unique(u,u+4)-u) < 3) return -1;
        // track pouch element IDs for INITIAL_STRESS_SHELL + airbag
        if (isPouchPid(pid)) {
            pouchEids.push_back(nextEid);
            if (cfg.airbagFill || cfg.mode == "bare")
                pouchSegments.push_back({pid, n1, n2, n3, n4});
        }
        char buf[128];
        std::snprintf(buf, sizeof(buf),
            "%8d%8d%8d%8d%8d%8d\n", nextEid, pid, n1,n2,n3,n4);
        shellBuf << buf;
        ++nShells;
        trackPart(pid);
        return nextEid++;
    }

    // ── add_solid ────────────────────────────────────────────
    // Rigid PIDs → ELEMENT_SOLID (rigidBuf)
    // solidElectrode → ELEMENT_SOLID (rigidBuf shares output)
    // allShell → no TSHELL; electrodes go to rigidBuf as SOLID
    // Deformable (electrodes/electrolyte) → ELEMENT_TSHELL (solidBuf)
    static bool isRigidPid(int pid) {
        return (pid == PID_INDENTER || pid == PID_GROUND ||
                pid == PID_PCM_POS || pid == PID_PCM_NEG);
    }

    static bool isElectrodePid(int pid) {
        if (pid < 1000) return false;
        int lt = pid % 10;
        return (lt == LT_CAT || lt == LT_ANO);
    }

    // Fix degenerate wedge face: duplicate pair must be at positions [2],[3]
    // (LS-DYNA requirement to avoid Error 20222)
    static void fixWedgeFace(int* f) {
        if (f[0]==f[1]||f[1]==f[2]||f[2]==f[3]||f[3]==f[0]) {
            // find the duplicate adjacent pair, rotate so it's at [2],[3]
            for (int i = 0; i < 4; ++i) {
                if (f[i] == f[(i+1)%4]) {
                    int s = (i+2)%4;
                    int tmp[4] = {f[s], f[(s+1)%4], f[(s+2)%4], f[(s+3)%4]};
                    for (int k=0;k<4;++k) f[k]=tmp[k];
                    return;
                }
            }
        }
    }

    int addSolid(int pid,
                 int n1, int n2, int n3, int n4,
                 int n5, int n6, int n7, int n8) {
        // Skip completely degenerate (< 4 unique nodes)
        int allN[8]={n1,n2,n3,n4,n5,n6,n7,n8};
        std::sort(allN,allN+8);
        if ((int)(std::unique(allN,allN+8)-allN) < 4) return -1;

        // Wedge face fix
        int bot[4]={n1,n2,n3,n4}, top[4]={n5,n6,n7,n8};
        int bu[4]={n1,n2,n3,n4}; std::sort(bu,bu+4);
        if ((int)(std::unique(bu,bu+4)-bu) == 3) fixWedgeFace(bot);
        int tu[4]={n5,n6,n7,n8}; std::sort(tu,tu+4);
        if ((int)(std::unique(tu,tu+4)-tu) == 3) fixWedgeFace(top);
        n1=bot[0];n2=bot[1];n3=bot[2];n4=bot[3];
        n5=top[0];n6=top[1];n7=top[2];n8=top[3];

        char buf[160];
        std::snprintf(buf, sizeof(buf),
            "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
            nextEid, pid, n1,n2,n3,n4, n5,n6,n7,n8);

        bool asRigid = isRigidPid(pid) || cfg.solidElectrode;
        bool asTshell = !asRigid && !cfg.allShell &&
                        (isElectrodePid(pid) || pid == PID_ELECTROLYTE ||
                         tshellPids.count(pid));

        if (asRigid) {
            rigidBuf << buf; ++nRigids;
        } else if (asTshell) {
            solidBuf << buf; ++nSolids;
            tshellPids.insert(pid);
        } else {
            // allShell mode: solid electrodes go to rigidBuf as ELEMENT_SOLID
            rigidBuf << buf; ++nRigids;
        }
        trackPart(pid);
        return nextEid++;
    }

    void trackPart(int pid) {
        for (int p : partIds) if (p==pid) return;
        partIds.push_back(pid);
    }

    // ── _clip_to_inner_fillet ────────────────────────────────
    // Python-equivalent: projects jellyroll corner nodes that fall outside
    // the pouch inner fillet arc onto the arc.
    // Only nodes geometrically inside a corner zone (x<Ri && y<Ri etc.)
    // are considered; all other nodes stay at their uniform-grid positions.
    // Matches Python generate_mesh_stacked.py _clip_to_inner_fillet() exactly.
    void clipToInnerFillet(double& x, double& y) const {
        double R = cfg.pouch.rFillet;
        if (R <= 0.0) return;
        double ht  = cfg.thick.pouch / 2.0;
        double Ri  = R - ht;
        if (Ri <= 0.0) return;
        double W   = cfg.geo.cellWidth;
        double H   = cfg.geo.cellHeight;
        double Ref = Ri - 0.005;  // 0.005 mm clearance

        double cxArr[4] = {Ri,   W-Ri, W-Ri,  Ri  };
        double cyArr[4] = {Ri,   Ri,   H-Ri,  H-Ri};

        for (int ci = 0; ci < 4; ++ci) {
            bool in = false;
            switch (ci) {
                case 0: in = (x <  Ri    && y <  Ri   ); break;
                case 1: in = (x > W-Ri   && y <  Ri   ); break;
                case 2: in = (x > W-Ri   && y > H-Ri  ); break;
                case 3: in = (x <  Ri    && y > H-Ri  ); break;
            }
            if (!in) continue;
            double ddx = x - cxArr[ci], ddy = y - cyArr[ci];
            double dist = std::sqrt(ddx*ddx + ddy*ddy);
            if (dist > Ref && dist > 1e-12) {
                x = cxArr[ci] + Ref * ddx / dist;
                y = cyArr[ci] + Ref * ddy / dist;
            }
            break;
        }
    }

    // ── create_plane_nodes ───────────────────────────────────
    // Uniform rectangular (nx+1)×(ny+1) grid at z.
    // Corner fillet is intentionally omitted here; the outer pouch shell
    // carries the arc via createPouchBox/faceXY. Rectangular jellyroll gives
    // all-90° elements, eliminating the obtuse corner angles that arise when
    // arc-projecting nodes in a structured grid.
    Grid createPlaneNodes(double z) {
        Grid g((ny+1)*(nx+1));
        for (int iy = 0; iy <= ny; ++iy)
            for (int ix = 0; ix <= nx; ++ix)
                g[iy*(nx+1)+ix] = addNode(jellyXs[ix], jellyYs[iy], z);
        return g;
    }

    // ── create_shell_layer_from_grid ─────────────────────────
    void createShellFromGrid(int pid, const Grid& g) {
        int s = nx+1;
        for (int iy = 0; iy < ny; ++iy)
            for (int ix = 0; ix < nx; ++ix)
                addShell(pid,
                    gAt(g,ix,  iy,  s), gAt(g,ix+1,iy,  s),
                    gAt(g,ix+1,iy+1,s), gAt(g,ix,  iy+1,s));
    }

    // ── create_solid_layer_between ───────────────────────────
    void createSolidBetween(int pid, const Grid& bot, const Grid& top) {
        int s = nx+1;
        for (int iy = 0; iy < ny; ++iy)
            for (int ix = 0; ix < nx; ++ix)
                addSolid(pid,
                    gAt(bot,ix,  iy,  s), gAt(bot,ix+1,iy,  s),
                    gAt(bot,ix+1,iy+1,s), gAt(bot,ix,  iy+1,s),
                    gAt(top,ix,  iy,  s), gAt(top,ix+1,iy,  s),
                    gAt(top,ix+1,iy+1,s), gAt(top,ix,  iy+1,s));
    }

    // ── create_solid_coating ─────────────────────────────────
    // botGrid empty → create new plane at zBot (like Python bot_grid=None)
    // Returns {firstBotGrid, lastTopGrid}
    std::pair<Grid,Grid> createSolidCoating(int pid,
                                             double zBot, double zTop,
                                             int nThick,
                                             Grid botGrid = Grid{}) {
        if (botGrid.empty()) botGrid = createPlaneNodes(zBot);
        double dz = (zTop - zBot) / nThick;
        Grid curBot = botGrid;
        Grid lastTop;
        for (int k = 0; k < nThick; ++k) {
            Grid top = createPlaneNodes(zBot + (k+1)*dz);
            createSolidBetween(pid, curBot, top);
            curBot = top;
            lastTop = top;
        }
        return {botGrid, lastTop};
    }

    // ── _create_tab_strip ────────────────────────────────────
    // SHELL strip protruding from +Y edge at given z
    void createTabStrip(int pid, double z, const Grid& nidGrid, bool isPositive) {
        if (cfg.noPcm) return;
        const auto& tabs = cfg.tabs;
        double xCenter = isPositive ? tabs.posXCenter : tabs.negXCenter;
        double xLo = xCenter - tabs.width/2.0;
        double xHi = xCenter + tabs.width/2.0;

        // register for pouch hole generation
        bool found = false;
        for (auto& r : tabXRanges)
            if (std::fabs(r.first-xLo)<0.01 && std::fabs(r.second-xHi)<0.01)
                { found=true; break; }
        if (!found) tabXRanges.push_back({xLo, xHi});

        int ixStart = (int)std::round(xLo/dx);
        int ixEnd   = (int)std::round(xHi/dx);
        ixStart = std::max(0, std::min(ixStart, nx));
        ixEnd   = std::max(ixStart+1, std::min(ixEnd, nx));
        int nCols = ixEnd - ixStart;

        int nRows = std::max(2, (int)std::round(tabs.height/meshSize));
        double dyTab = tabs.height / nRows;

        // grab Y-max edge row from jellyroll grid
        int s = nx+1;
        std::vector<int> prevRow(nCols+1);
        for (int ii = 0; ii <= nCols; ++ii)
            prevRow[ii] = gAt(nidGrid, ixStart+ii, ny, s);

        double yStart = cfg.geo.cellHeight;
        for (int row = 0; row < nRows; ++row) {
            double y = yStart + (row+1)*dyTab;
            std::vector<int> newNids(nCols+1);
            for (int ii = 0; ii <= nCols; ++ii)
                newNids[ii] = addNode((ixStart+ii)*dx, y, z);
            for (int ii = 0; ii < nCols; ++ii)
                addShell(pid, prevRow[ii], prevRow[ii+1], newNids[ii+1], newNids[ii]);
            prevRow = newNids;
        }
        TipRow tr; tr.z = z; tr.nids = prevRow;
        if (isPositive) posTipRows.push_back(tr);
        else            negTipRows.push_back(tr);
    }

    // ── _create_pcm ──────────────────────────────────────────
    // Solid HEX block bridging both tabs at top of cell
    void createPcm(double cellTopZ) {
        if (cfg.noPcm) return;
        if (posTipRows.empty() && negTipRows.empty()) return;

        const auto& tabs = cfg.tabs;
        const auto& pcm  = cfg.pcm;
        double xLeft  = std::min(tabs.posXCenter, tabs.negXCenter) - tabs.width/2.0;
        double xRight = std::max(tabs.posXCenter, tabs.negXCenter) + tabs.width/2.0;
        double pcmW   = xRight - xLeft;
        double yTip   = cfg.geo.cellHeight + tabs.height;
        double zMid   = cellTopZ / 2.0;
        double zBot   = zMid - pcm.thickness/2.0;
        double zTop   = zMid + pcm.thickness/2.0;

        int nxP = std::max(2, (int)std::round(pcmW          / meshSize));
        int nzP = std::max(1, (int)std::round(pcm.thickness / meshSize));
        int nyP = std::max(1, (int)std::round(pcm.height    / meshSize));

        double dxP = pcmW / nxP;
        double dzP = (zTop-zBot) / nzP;
        double dyP = pcm.height  / nyP;

        // nids[jy][jz][jx]
        std::vector<std::vector<std::vector<int>>> nids(
            nyP+1, std::vector<std::vector<int>>(
                nzP+1, std::vector<int>(nxP+1)));

        for (int jy = 0; jy <= nyP; ++jy)
            for (int jz = 0; jz <= nzP; ++jz)
                for (int jx = 0; jx <= nxP; ++jx)
                    nids[jy][jz][jx] = addNode(
                        xLeft + jx*dxP, yTip + jy*dyP, zBot + jz*dzP);

        double xMid = (tabs.posXCenter + tabs.negXCenter) / 2.0;
        int ixMid = 0;
        for (int jx = 0; jx <= nxP; ++jx)
            if (xLeft + jx*dxP >= xMid) { ixMid=jx; break; }

        for (int jy = 0; jy < nyP; ++jy)
            for (int jz = 0; jz < nzP; ++jz)
                for (int jx = 0; jx < nxP; ++jx) {
                    int pid = (jx < ixMid) ? PID_PCM_POS : PID_PCM_NEG;
                    // Hex ordering: (n2-n1)×(n4-n1)·(n5-n1) > 0
                    addSolid(pid,
                        nids[jy  ][jz  ][jx  ], nids[jy  ][jz+1][jx  ],
                        nids[jy  ][jz+1][jx+1], nids[jy  ][jz  ][jx+1],
                        nids[jy+1][jz  ][jx  ], nids[jy+1][jz+1][jx  ],
                        nids[jy+1][jz+1][jx+1], nids[jy+1][jz  ][jx+1]);
                }
    }

    // ── _create_pouch_box ─────────────────────────────────────
    // Full 3-D pouch: top face + bottom face + 4 side walls + fillet corners
    // Tab holes cut into Y-max side wall
    void createPouchBox(double cellTopZ) {
        const auto& pp  = cfg.pouch;
        double ht   = cfg.thick.pouch / 2.0;
        double R    = pp.rFillet;
        int    nF   = pp.nFilletSegs;
        double bufX = pp.bufX;
        double bufY = pp.bufY;
        double W    = cfg.geo.cellWidth;
        double H    = cfg.geo.cellHeight;

        double tBuf  = cfg.thick.buffer;
        bool   dome  = cfg.pouch.domeCap && (tBuf > 0.0);
        double Rcap  = rCapZ();

        // side-wall z extents:
        //   dome_cap=false: ht … cellTopZ-ht
        //   dome_cap=true : ht+tBuf … cellTopZ-ht-tBuf
        //   (perimeter dome height ≈ 0, so face perimeter z ≈ ht+tBuf)
        double zBot = dome ? ht + tBuf      : ht;
        double zTop = dome ? cellTopZ - ht - tBuf : cellTopZ - ht;

        // XY extents of pouch mid-surface
        double x0=-(bufX+ht), x1=W+bufX+ht;
        double y0=-(bufY+ht), y1=H+bufY+ht;
        double xf0=x0+R, xf1=x1-R;
        double yf0=y0+R, yf1=y1-R;

        int nStrX = std::max(1,(int)std::round((xf1-xf0)/meshSize));
        int nStrY = std::max(1,(int)std::round((yf1-yf0)/meshSize));

        // Build coordinate arrays: [lo..fl] + [fl..fr skip1] + [fr..hi skip1]
        auto buildAxis = [](double lo, double fl, double fr, double hi,
                             int nFil, int nStr) -> std::vector<double> {
            std::vector<double> v;
            for (int i=0; i<=nFil; ++i) v.push_back(lo+(fl-lo)*i/nFil);
            for (int i=1; i<=nStr; ++i) v.push_back(fl+(fr-fl)*i/nStr);
            for (int i=1; i<=nFil; ++i) v.push_back(fr+(hi-fr)*i/nFil);
            return v;
        };

        std::vector<double> xs = buildAxis(x0,xf0,xf1,x1, nF,nStrX);
        std::vector<double> ys = buildAxis(y0,yf0,yf1,y1, nF,nStrY);
        int ni=(int)xs.size(), nj=(int)ys.size();

        int iFl=nF, iFr=nF+nStrX;
        int jFf=nF, jFb=nF+nStrY;

        double cxArr[4]={xf0,xf1,xf1,xf0};
        double cyArr[4]={yf0,yf0,yf1,yf1};

        // project corner-region nodes onto fillet arc
        auto faceXY = [&](int i, int j, double& ox, double& oy) {
            ox=xs[i]; oy=ys[j];
            if (R <= 0.0) return;
            bool inL=(i<=iFl), inR=(i>=iFr), inF=(j<=jFf), inB=(j>=jFb);
            int ci=-1;
            if      (inL&&inF) ci=0;
            else if (inR&&inF) ci=1;
            else if (inR&&inB) ci=2;
            else if (inL&&inB) ci=3;
            if (ci<0) return;
            double ddx=ox-cxArr[ci], ddy=oy-cyArr[ci];
            double dist=std::sqrt(ddx*ddx+ddy*ddy);
            if (dist>R && dist>1e-12) {
                ox=cxArr[ci]+R*ddx/dist;
                oy=cyArr[ci]+R*ddy/dist;
            }
        };

        // side-wall Z levels
        int nz=std::max(2,(int)std::round((zTop-zBot)/meshSize));
        std::vector<double> zs(nz+1);
        for (int k=0; k<=nz; ++k) zs[k]=zBot+(zTop-zBot)*k/nz;

        // bottom face grid
        // dome_cap: z = ht + tBuf - dome_h(ox,oy)  → bowl shape (center low, edge high)
        // flat:     z = ht (constant)
        std::vector<std::vector<int>> bot(nj, std::vector<int>(ni));
        for (int j=0; j<nj; ++j)
            for (int i=0; i<ni; ++i) {
                double ox,oy; faceXY(i,j,ox,oy);
                double zf = dome ? ht + tBuf - domeHeight(ox, oy, Rcap) : ht;
                bot[j][i]=addNode(ox,oy,zf);
            }

        // top face grid
        // dome_cap: z = (cellTopZ-ht-tBuf) + dome_h(ox,oy)
        // flat:     z = cellTopZ-ht (constant)
        std::vector<std::vector<int>> top(nj, std::vector<int>(ni));
        for (int j=0; j<nj; ++j)
            for (int i=0; i<ni; ++i) {
                double ox,oy; faceXY(i,j,ox,oy);
                double zf = dome ? (cellTopZ - ht - tBuf) + domeHeight(ox, oy, Rcap) : cellTopZ - ht;
                top[j][i]=addNode(ox,oy,zf);
            }

        // save for NSET_STACK_TOP
        nsetStackTop.clear();
        for (int j=0; j<nj; ++j)
            for (int i=0; i<ni; ++i)
                nsetStackTop.push_back(top[j][i]);

        // perimeter path (CCW)
        struct IP{int i,j;};
        std::vector<IP> perim;
        for (int i=0;   i<ni-1; ++i) perim.push_back({i,    0   });
        for (int j=0;   j<nj-1; ++j) perim.push_back({ni-1, j   });
        for (int i=ni-1;i>0;    --i) perim.push_back({i,    nj-1});
        for (int j=nj-1;j>0;    --j) perim.push_back({0,    j   });
        int nP=(int)perim.size();

        // rings: ring[0]=bottom perim, ring[nz]=top perim, middle=new nodes
        std::vector<std::vector<int>> rings(nz+1, std::vector<int>(nP));
        for (int p=0;p<nP;++p) rings[0][p]=bot[perim[p].j][perim[p].i];
        for (int kz=1;kz<nz;++kz)
            for (int p=0;p<nP;++p) {
                double ox,oy; faceXY(perim[p].i,perim[p].j,ox,oy);
                rings[kz][p]=addNode(ox,oy,zs[kz]);
            }
        for (int p=0;p<nP;++p) rings[nz][p]=top[perim[p].j][perim[p].i];

        // bottom face shells
        for (int j=0;j<nj-1;++j)
            for (int i=0;i<ni-1;++i)
                addShell(PID_POUCH_BOTTOM,
                    bot[j][i], bot[j][i+1], bot[j+1][i+1], bot[j+1][i]);

        // top face shells
        for (int j=0;j<nj-1;++j)
            for (int i=0;i<ni-1;++i)
                addShell(PID_POUCH_TOP,
                    top[j][i], top[j][i+1], top[j+1][i+1], top[j+1][i]);

        // side wall shells (tab holes in Y-max edge)
        for (int kz=0;kz<nz;++kz) {
            const auto& rb=rings[kz];
            const auto& rt=rings[kz+1];
            for (int p=0;p<nP;++p) {
                int pn=(p+1)%nP;
                // check tab hole at Y-max edge
                if (perim[p].j==nj-1 && perim[pn].j==nj-1 && !tabXRanges.empty()) {
                    double xp,yp_; faceXY(perim[p].i, perim[p].j, xp, yp_);
                    double xn,yn_; faceXY(perim[pn].i,perim[pn].j,xn, yn_);
                    double xlo=std::min(xp,xn), xhi=std::max(xp,xn);
                    bool hole=false;
                    for (auto& r:tabXRanges)
                        if (xlo<r.second && xhi>r.first) {hole=true;break;}
                    if (hole) continue;
                }
                addShell(PID_POUCH_SIDE, rb[p],rb[pn],rt[pn],rt[p]);
            }
        }
    }

    // ── _create_dent_cylinder ────────────────────────────────
    // Disk punch from above; inner ring avoids degenerate wedge
    void createDentCylinder(double cellTopZ) {
        const auto& ind=cfg.indenter;
        double R    = ind.radius;
        double H    = ind.height;
        int nCirc   = ind.nCirc;
        int nRad    = ind.nRadial;
        double cx   = (ind.cx>0) ? ind.cx : cfg.geo.cellWidth/2.0;
        double cy_  = (ind.cy>0) ? ind.cy : cfg.geo.cellHeight/2.0;
        double zBot = cellTopZ + ind.offset;
        double zTop = zBot + H;

        // inner ring: r_inner = R/n_radial*0.3 (avoids degenerate wedge)
        double rInn = R/nRad*0.3;
        double dr   = (R-rInn)/nRad;

        // ring[iz][k][ic]  iz=0:bottom, iz=1:top  k=0..nRad
        std::vector<std::vector<std::vector<int>>> ring(2);
        for (int iz=0;iz<2;++iz) {
            double z=(iz==0)?zBot:zTop;
            ring[iz].resize(nRad+1, std::vector<int>(nCirc));
            for (int k=0;k<=nRad;++k) {
                double r=rInn+k*dr;
                for (int ic=0;ic<nCirc;++ic) {
                    double theta=2.0*M_PI*ic/nCirc;
                    int id=addNode(cx+r*std::cos(theta), cy_+r*std::sin(theta), z);
                    ring[iz][k][ic]=id;
                    nsetImpactorAll.push_back(id);
                }
            }
        }

        for (int k=0;k<nRad;++k)
            for (int ic=0;ic<nCirc;++ic) {
                int icn=(ic+1)%nCirc;
                addSolid(PID_INDENTER,
                    ring[0][k][ic],   ring[0][k+1][ic],
                    ring[0][k+1][icn],ring[0][k  ][icn],
                    ring[1][k][ic],   ring[1][k+1][ic],
                    ring[1][k+1][icn],ring[1][k  ][icn]);
            }
    }

    // ── _create_ground_plate ────────────────────────────────
    // Rigid HEX slab below cell at z=-(gap+t)..-gap
    void createGroundPlate() {
        const auto& pl=cfg.plate;
        double t=pl.thickness, gap=pl.gap, margin=pl.margin;
        int nxP=pl.nX, nyP=pl.nY;
        double W=cfg.geo.cellWidth, H=cfg.geo.cellHeight;

        double x0=-margin, x1=W+margin;
        double y0=-margin, y1=H+margin;
        double z0=-(gap+t), z1=-gap;
        double dxP=(x1-x0)/nxP, dyP=(y1-y0)/nyP;

        std::vector<std::vector<std::vector<int>>> nids(2,
            std::vector<std::vector<int>>(nyP+1, std::vector<int>(nxP+1)));

        for (int iz=0;iz<2;++iz) {
            double z=(iz==0)?z0:z1;
            for (int iy=0;iy<=nyP;++iy)
                for (int ix=0;ix<=nxP;++ix) {
                    int id=addNode(x0+ix*dxP, y0+iy*dyP, z);
                    nids[iz][iy][ix]=id;
                    nsetGroundPlateAll.push_back(id);
                }
        }

        for (int iy=0;iy<nyP;++iy)
            for (int ix=0;ix<nxP;++ix)
                addSolid(PID_GROUND,
                    nids[0][iy  ][ix  ], nids[0][iy  ][ix+1],
                    nids[0][iy+1][ix+1], nids[0][iy+1][ix  ],
                    nids[1][iy  ][ix  ], nids[1][iy  ][ix+1],
                    nids[1][iy+1][ix+1], nids[1][iy+1][ix  ]);
    }

    // ── _create_side_buffer ──────────────────────────────────
    // 4 rectangular solid columns surrounding the jellyroll
    // (left X-, right X+, front Y-, back Y+)
    // Matches Python MeshGenerator._create_side_buffer()
    void createSideBuffer(double zJBot, double zJTop) {
        double bufX = cfg.pouch.bufX;
        double bufY = cfg.pouch.bufY;
        if (bufX <= 0.0 && bufY <= 0.0) return;

        double W = cfg.geo.cellWidth;
        double H = cfg.geo.cellHeight;

        int nzSide = std::max(2, (int)std::round((zJTop-zJBot)/meshSize));
        std::vector<double> zLevs(nzSide+1);
        for (int k=0; k<=nzSide; ++k)
            zLevs[k] = zJBot + (zJTop-zJBot)*k/nzSide;

        // Helper: build one rectangular column of hex solids
        auto makeRectCol = [&](double x0,double x1,double y0,double y1,
                               int nxE,int nyE) {
            double dxE=(x1-x0)/nxE, dyE=(y1-y0)/nyE;
            // first Z-level nodes
            std::vector<std::vector<int>> prev(nyE+1, std::vector<int>(nxE+1));
            for (int jj=0;jj<=nyE;++jj)
                for (int ii=0;ii<=nxE;++ii)
                    prev[jj][ii]=addNode(x0+ii*dxE, y0+jj*dyE, zLevs[0]);

            for (int kz=0;kz<nzSide;++kz) {
                std::vector<std::vector<int>> cur(nyE+1, std::vector<int>(nxE+1));
                for (int jj=0;jj<=nyE;++jj)
                    for (int ii=0;ii<=nxE;++ii)
                        cur[jj][ii]=addNode(x0+ii*dxE, y0+jj*dyE, zLevs[kz+1]);
                for (int jj=0;jj<nyE;++jj)
                    for (int ii=0;ii<nxE;++ii)
                        addSolid(PID_ELECTROLYTE,
                            prev[jj][ii],    prev[jj][ii+1],
                            prev[jj+1][ii+1],prev[jj+1][ii],
                            cur[jj][ii],     cur[jj][ii+1],
                            cur[jj+1][ii+1], cur[jj+1][ii]);
                prev = cur;
            }
        };

        if (bufX > 0.0) {
            makeRectCol(-bufX, 0.0, 0.0, H, 1, ny);     // Left X-
            makeRectCol(W, W+bufX, 0.0, H, 1, ny);       // Right X+
        }
        if (bufY > 0.0) {
            int nxFace = nx + (bufX > 0.0 ? 2 : 0);
            makeRectCol(-bufX, W+bufX, -bufY, 0.0, nxFace, 1);  // Front Y-
            makeRectCol(-bufX, W+bufX, H, H+bufY, nxFace, 1);   // Back Y+
        }

        // Add PID to electrolyte set if not already present
        bool already=false;
        for (int p:psetElectrolyte) if(p==PID_ELECTROLYTE){already=true;break;}
        if (!already) psetElectrolyte.push_back(PID_ELECTROLYTE);
    }

    // ── _dome_height ─────────────────────────────────────────
    // Variable fill height: t_buf interior, quarter-circle fillet to 0 at edge
    double domeHeight(double x, double y, double R_cap) const {
        double tBuf = cfg.thick.buffer;
        if (tBuf <= 0.0) return 0.0;
        double bufX = cfg.pouch.bufX, bufY = cfg.pouch.bufY;
        double W = cfg.geo.cellWidth, H = cfg.geo.cellHeight;
        double xlo = -bufX, xhi = W + bufX;
        double ylo = -bufY, yhi = H + bufY;
        double ddx = std::min(x - xlo, xhi - x);
        double ddy = std::min(y - ylo, yhi - y);
        double dEdge = std::max(std::min(ddx, ddy), 0.0);
        if (dEdge >= R_cap) return tBuf;
        if (dEdge <= 0.0)   return 0.0;
        double curve = std::sqrt(2.0*R_cap*dEdge - dEdge*dEdge);
        return tBuf * curve / R_cap;
    }

    // ── _create_dome_fill ────────────────────────────────────
    // direction: +1=top (above jelly), -1=bottom (below jelly)
    void createDomeFill(double zJelly, double R_cap, int direction) {
        Grid flatGrid = createPlaneNodes(zJelly);
        int s = nx+1;
        // dome surface nodes (variable Z) — reuse XY from flatGrid so fillet
        // clipping is consistent (no element shear at corner zones)
        Grid domeGrid((ny+1)*(nx+1));
        for (int iy=0; iy<=ny; ++iy)
            for (int ix=0; ix<=nx; ++ix) {
                int   nid = flatGrid[iy*s+ix];
                const Vec3& p = nodePos[nid-1];
                double h = domeHeight(p.x, p.y, R_cap);
                domeGrid[iy*s+ix] = addNode(p.x, p.y, zJelly + direction*h);
            }
        if (direction > 0)
            createSolidBetween(PID_ELECTROLYTE, flatGrid, domeGrid);
        else
            createSolidBetween(PID_ELECTROLYTE, domeGrid, flatGrid);

        bool already=false;
        for (int p:psetElectrolyte) if(p==PID_ELECTROLYTE){already=true;break;}
        if (!already) psetElectrolyte.push_back(PID_ELECTROLYTE);
    }

    // ── r_cap_z helper ───────────────────────────────────────
    double rCapZ() const {
        // match Python: r_cap_z = max(buf_x, buf_y, 0.3) * 3.0 if no explicit r_cap
        return std::max({cfg.pouch.bufX, cfg.pouch.bufY, 0.3}) * 3.0;
    }

    // ── _create_side_impactor ────────────────────────────────
    // Solid Y-axis cylinder at +X face; wedge core + hex rings
    void createSideImpactor(double cellTopZ) {
        const auto& ind = cfg.indenter;
        double R   = ind.radius;    // shaft radius
        double L   = ind.length;    // axial length (Y-dir)
        int nCirc  = ind.nCirc;
        int nRad   = ind.nRadial;
        double cx  = cfg.geo.cellWidth + ind.offset + R;
        double cy  = cfg.geo.cellHeight / 2.0;
        double cz  = cellTopZ / 2.0;

        int nAx = std::max(4, (int)std::round(L / meshSize));
        double dr = R / nRad;
        double dy_ax = L / nAx;
        double dtheta = 2.0*M_PI / nCirc;

        // center line + rings: [j][k][i]
        std::vector<int> centerNids(nAx+1);
        std::vector<std::vector<std::vector<int>>> ringNids(
            nAx+1, std::vector<std::vector<int>>(nRad, std::vector<int>(nCirc)));

        for (int j=0; j<=nAx; ++j) {
            double y = cy - L/2.0 + j*dy_ax;
            int cid = addNode(cx, y, cz);
            centerNids[j] = cid;
            nsetImpactorAll.push_back(cid);
            for (int k=0; k<nRad; ++k) {
                double r = (k+1)*dr;
                for (int i=0; i<nCirc; ++i) {
                    double theta = i*dtheta;
                    int nid = addNode(cx - r*std::cos(theta), y, cz + r*std::sin(theta));
                    ringNids[j][k][i] = nid;
                    nsetImpactorAll.push_back(nid);
                }
            }
        }

        for (int j=0; j<nAx; ++j) {
            // inner wedge (degenerate hex: center repeated)
            for (int i=0; i<nCirc; ++i) {
                int in = (i+1)%nCirc;
                addSolid(PID_INDENTER,
                    centerNids[j],      ringNids[j][0][i],   ringNids[j][0][in],  centerNids[j],
                    centerNids[j+1],    ringNids[j+1][0][i], ringNids[j+1][0][in],centerNids[j+1]);
            }
            // outer hex rings
            for (int k=1; k<nRad; ++k)
                for (int i=0; i<nCirc; ++i) {
                    int in = (i+1)%nCirc;
                    addSolid(PID_INDENTER,
                        ringNids[j][k-1][i],   ringNids[j][k][i],   ringNids[j][k][in],   ringNids[j][k-1][in],
                        ringNids[j+1][k-1][i], ringNids[j+1][k][i], ringNids[j+1][k][in], ringNids[j+1][k-1][in]);
                }
        }
    }

    // ── _create_nail_impactor ────────────────────────────────
    // Cone tip (tip_radius → shaft_radius) + cylinder shaft, X-axis penetration
    void createNailImpactor(double cellTopZ) {
        const auto& ind = cfg.indenter;
        double R_shaft = ind.nailShaftRadius;
        double R_tip   = ind.nailTipRadius;
        double tipLen  = ind.nailTipLength;
        double totalLen = ind.radius * 2.0;   // total length (reuses radius field)
        double shaftLen = totalLen - tipLen;
        int nCirc = ind.nCirc;
        int nRad  = std::max(2, ind.nRadial / 2);

        // tip starts at +X side of cell
        double cxStart = cfg.geo.cellWidth + ind.offset;
        double cy  = cfg.geo.cellHeight / 2.0;
        double cz  = cellTopZ / 2.0;

        int nTip   = std::max(3, (int)std::round(tipLen   / (meshSize*0.5)));
        int nShaft = std::max(4, (int)std::round(shaftLen / meshSize));
        double dtheta = 2.0*M_PI / nCirc;

        // build slice arrays
        std::vector<double> sliceX, sliceR;
        for (int j=0; j<=nTip; ++j) {
            double frac = (double)j/nTip;
            sliceX.push_back(cxStart + frac*tipLen);
            sliceR.push_back(R_tip + frac*(R_shaft - R_tip));
        }
        for (int j=1; j<=nShaft; ++j) {
            double frac = (double)j/nShaft;
            sliceX.push_back(cxStart + tipLen + frac*shaftLen);
            sliceR.push_back(R_shaft);
        }
        int nSlices = (int)sliceX.size();

        // nodes: center + rings per slice
        std::vector<int> centerNids(nSlices);
        std::vector<std::vector<std::vector<int>>> ringNids(
            nSlices, std::vector<std::vector<int>>(nRad, std::vector<int>(nCirc)));

        for (int j=0; j<nSlices; ++j) {
            double x = sliceX[j];
            double Rloc = sliceR[j];
            double dr = Rloc / nRad;
            int cid = addNode(x, cy, cz);
            centerNids[j] = cid;
            nsetImpactorAll.push_back(cid);
            for (int k=0; k<nRad; ++k) {
                double r = (k+1)*dr;
                for (int i=0; i<nCirc; ++i) {
                    double theta = i*dtheta;
                    int nid = addNode(x, cy + r*std::cos(theta), cz + r*std::sin(theta));
                    ringNids[j][k][i] = nid;
                    nsetImpactorAll.push_back(nid);
                }
            }
        }

        for (int j=0; j<nSlices-1; ++j) {
            // inner wedge
            for (int i=0; i<nCirc; ++i) {
                int in = (i+1)%nCirc;
                addSolid(PID_INDENTER,
                    centerNids[j],     ringNids[j][0][i],   ringNids[j][0][in],   centerNids[j],
                    centerNids[j+1],   ringNids[j+1][0][i], ringNids[j+1][0][in], centerNids[j+1]);
            }
            // outer hex rings
            for (int k=1; k<nRad; ++k)
                for (int i=0; i<nCirc; ++i) {
                    int in = (i+1)%nCirc;
                    addSolid(PID_INDENTER,
                        ringNids[j][k-1][i],   ringNids[j][k][i],   ringNids[j][k][in],   ringNids[j][k-1][in],
                        ringNids[j+1][k-1][i], ringNids[j+1][k][i], ringNids[j+1][k][in], ringNids[j+1][k-1][in]);
                }
        }
    }

    // ── _create_boundary_node_sets ───────────────────────────
    void createBoundaryNodeSets() {
        // first (nx+1)*(ny+1) nodes = first plane, take edge nodes
        nsetFixBottomEdge.clear();
        for (int iy=0;iy<=ny;++iy)
            for (int ix=0;ix<=nx;++ix)
                if (ix==0||ix==nx||iy==0||iy==ny)
                    nsetFixBottomEdge.push_back(1 + iy*(nx+1) + ix);
    }

    // ── main build ────────────────────────────────────────────
    void build() {
        const auto& geo  = cfg.geo;
        const auto& thk  = cfg.thick;
        int nUC = geo.nUnitCells;

        double z = 0.0;

        // skip pouch bottom face (pouch box creates it separately)
        z += thk.pouch;

        // ---- Bottom electrolyte buffer ----
        // Independent nodes (no sharing with jellyroll)
        if (thk.buffer > 0.0) {
            if (!cfg.airbagFill) {
                if (cfg.allShell) {
                    Grid elecMid = createPlaneNodes(z + thk.buffer * 0.5);
                    createShellFromGrid(PID_ELECTROLYTE, elecMid);
                    psetElectrolyte.push_back(PID_ELECTROLYTE);
                } else if (cfg.pouch.domeCap) {
                    createDomeFill(z + thk.buffer, rCapZ(), -1);
                } else {
                    createSolidCoating(PID_ELECTROLYTE, z, z+thk.buffer, 1);
                    psetElectrolyte.push_back(PID_ELECTROLYTE);
                }
            }
            z += thk.buffer;
        }

        double zJellyBot = z;  // jellyroll bottom Z

        // ---- Unit cell loop ----
        std::vector<int> alCCPids, cathPids, sepPids, anodePids, cuCCPids;
        std::vector<int> cualCCPids;  // merge_cc composite pids
        Grid prevCuGrid;  // Cu CC top of previous UC (reused as next Al CC bot)
        Grid cualBotGrid; // merge_cc: anode top of previous UC (= CuAl SOLID bottom)

        for (int uc = 0; uc < nUC; ++uc) {
            int base = 1000 + uc*10;

            bool isMergeBoundary = cfg.mergeCc && (uc > 0);
            bool isLastUC        = (uc == nUC-1);

            // -- Al CC (or CuAl composite at boundary) --
            int pidAl = base + LT_AL;
            Grid alBot;
            if (isMergeBoundary) {
                // Replace Cu(prev)+Al(this) with single CuAl SOLID
                double tCuAl = thk.cuCC + thk.alCC;
                Grid cualTop = createPlaneNodes(z + tCuAl);
                int pidCuAl  = (1000 + (uc-1)*10) + LT_CUAL;
                createSolidBetween(pidCuAl, cualBotGrid, cualTop);
                createTabStrip(PID_TAB_NEG, z,       cualBotGrid, false);
                createTabStrip(PID_TAB_POS, z+tCuAl, cualTop,     true);
                cualCCPids.push_back(pidCuAl);
                z += tCuAl;
                alBot = cualTop;
            } else {
                alBot = (uc>0 && !prevCuGrid.empty())
                           ? prevCuGrid : createPlaneNodes(z);
                createShellFromGrid(pidAl, alBot);
                createTabStrip(PID_TAB_POS, z, alBot, true);
                alCCPids.push_back(pidAl);
            }
            if (uc == 0 && cfg.emRandles)
                emAlCCOuterNids.assign(alBot.begin(), alBot.end());
            {
            Grid ucPrev = alBot;
            // z unchanged (SHELL)

            // Cathode: SOLID (or SHELL if all_shell), z += t_cathode
            int pidCat = base + LT_CAT;
            if (cfg.allShell) {
                // all_shell: electrode as mid-plane SHELL (no z-advance for geometry,
                // but z still advances to keep stack height correct)
                Grid catMid = createPlaneNodes(z + thk.cathode * 0.5);
                createShellFromGrid(pidCat, catMid);
                ucPrev = catMid;
            } else {
                auto r = createSolidCoating(pidCat, z, z+thk.cathode, 1, ucPrev);
                ucPrev = r.second;
            }
            z += thk.cathode;
            cathPids.push_back(pidCat);

            // Separator: SHELL on Cathode top, NO z-advance
            int pidSep = base + LT_SEP;
            if (!cfg.allShell) {
                createShellFromGrid(pidSep, ucPrev);
            } else {
                Grid sepMid = createPlaneNodes(z);
                createShellFromGrid(pidSep, sepMid);
                ucPrev = sepMid;
            }
            sepPids.push_back(pidSep);
            // z unchanged (SHELL)

            // Anode: SOLID (or SHELL if all_shell), z += t_anode
            int pidAno = base + LT_ANO;
            if (cfg.allShell) {
                Grid anoMid = createPlaneNodes(z + thk.anode * 0.5);
                createShellFromGrid(pidAno, anoMid);
                ucPrev = anoMid;
            } else {
                auto r = createSolidCoating(pidAno, z, z+thk.anode, 1, ucPrev);
                ucPrev = r.second;
            }
            z += thk.anode;
            anodePids.push_back(pidAno);

            // Cu CC: SHELL (or defer to next UC's CuAl in merge_cc mode)
            int pidCu = base + LT_CU;
            bool skipCuShell = cfg.mergeCc && !isLastUC; // will be merged into next CuAl
            if (!skipCuShell) {
                createShellFromGrid(pidCu, ucPrev);
                createTabStrip(PID_TAB_NEG, z, ucPrev, false);
                cuCCPids.push_back(pidCu);
            }
            prevCuGrid = ucPrev;  // save for next UC's Al CC (standard mode)
            // merge_cc: save anode top as CuAl bottom for next UC boundary
            if (cfg.mergeCc && !isLastUC)
                cualBotGrid = ucPrev;
            // EM RANDLES: outer top face of last UC Cu CC
            if (uc == nUC-1 && cfg.emRandles)
                emCuCCOuterNids.assign(ucPrev.begin(), ucPrev.end());
            // z unchanged (SHELL)
            } // end ucPrev scope
        }
        // z = z_jelly_bot + n_uc*(t_cat + t_ano)
        double zJellyTop = z;  // jellyroll top Z

        // merge_cc pass: replace UC boundary Cu(k)+Al(k+1) with CuAl SOLID
        // (done after main loop so we have all grids; here we use prevCuGrid
        //  which is the last Cu CC top — represents UC boundary grids)
        // Full merge_cc requires tracking intermediate grids; we do it inline above.

        // ---- Top electrolyte buffer (independent bottom nodes) ----
        if (thk.buffer > 0.0) {
            if (!cfg.airbagFill) {
                if (cfg.allShell) {
                    Grid elecMidTop = createPlaneNodes(z + thk.buffer * 0.5);
                    createShellFromGrid(PID_ELECTROLYTE, elecMidTop);
                } else if (cfg.pouch.domeCap) {
                    createDomeFill(z, rCapZ(), +1);
                } else {
                    createSolidCoating(PID_ELECTROLYTE, z, z+thk.buffer, 1);
                }
            }
            z += thk.buffer;
        }

        // ---- Side electrolyte buffer (4 columns around jellyroll) ----
        if (!cfg.airbagFill)
            createSideBuffer(zJellyBot, zJellyTop);

        // skip pouch top face
        z += thk.pouch;
        double cellTopZ = z;
        stats.totalZ = cellTopZ;

        // ---- Part sets ----
        psetPouch    = {PID_POUCH_TOP, PID_POUCH_BOTTOM, PID_POUCH_SIDE};
        psetAllCell  = {PID_POUCH_TOP, PID_POUCH_BOTTOM, PID_POUCH_SIDE,
                        PID_TAB_POS, PID_TAB_NEG};
        if (!cfg.noPcm) {
            psetAllCell.push_back(PID_PCM_POS);
            psetAllCell.push_back(PID_PCM_NEG);
        }
        if (!cfg.airbagFill) psetAllCell.push_back(PID_ELECTROLYTE);
        for (int p: alCCPids)   psetAllCell.push_back(p);
        for (int p: cuCCPids)   psetAllCell.push_back(p);
        for (int p: cualCCPids) psetAllCell.push_back(p);
        for (int p: cathPids)  psetAllCell.push_back(p);
        for (int p: anodePids) psetAllCell.push_back(p);
        for (int p: sepPids)   psetAllCell.push_back(p);
        psetAllCathode = cathPids;
        psetAllAnode   = anodePids;
        psetSep        = sepPids;
        psetAlCC       = alCCPids;
        psetCuCC       = cuCCPids;

        // ---- Pouch box ----
        createPouchBox(cellTopZ);

        // ---- PCM board ----
        if (!cfg.noPcm) createPcm(cellTopZ);

        // ---- Impactor / ground plate ----
        if (!cfg.noImpactor) {
            if (cfg.mode == "dent") {
                createDentCylinder(cellTopZ);
                createGroundPlate();
                psetImpactor    = {PID_INDENTER};
                psetGroundPlate = {PID_GROUND};
            } else if (cfg.mode == "side") {
                if (cfg.indenter.type == "nail")
                    createNailImpactor(cellTopZ);
                else
                    createSideImpactor(cellTopZ);
                psetImpactor = {PID_INDENTER};
            }
        }

        // ---- Boundary node sets ----
        createBoundaryNodeSets();

        stats.nNodes  = nNodes;
        stats.nShells = nShells;
        stats.nSolids = nSolids + nRigids;
    }

    // ── flush buffers to output ───────────────────────────────
    void flush(std::ostream& out) {
        int nUC = cfg.geo.nUnitCells;

        // Parts
        bool ph2 = (cfg.phase == 2) && !cfg.noThermal;
        writeComment(out, "Parts — Pouch / Electrolyte / Tab / PCM / Impactor");
        writePart(out,"Pouch_Bottom",PID_POUCH_BOTTOM,SID_SHELL_POUCH,MID_POUCH,HGID_SHELL, ph2?TMID_POUCH:0);
        writePart(out,"Pouch_Top",   PID_POUCH_TOP,   SID_SHELL_POUCH,MID_POUCH,HGID_SHELL, ph2?TMID_POUCH:0);
        writePart(out,"Pouch_Side",  PID_POUCH_SIDE,  SID_SHELL_POUCH,MID_POUCH,HGID_SHELL, ph2?TMID_POUCH:0);
        if (!cfg.airbagFill)
            // solidElectrode=true → ELEMENT_SOLID → must use SECTION_SOLID
            // solidElectrode=false → ELEMENT_TSHELL → use SECTION_TSHELL (SID_SOLID_ELEC)
            writePart(out,"Electrolyte", PID_ELECTROLYTE,
                cfg.solidElectrode ? SID_SOLID_ELEC_STACK : SID_SOLID_ELEC,
                MID_ELYTE, HGID_SOLID);
        writePart(out,"Tab_Pos",     PID_TAB_POS,     SID_SHELL_AL,   MID_AL,   HGID_SHELL, ph2?TMID_AL:0);
        writePart(out,"Tab_Neg",     PID_TAB_NEG,     SID_SHELL_CU,   MID_CU,   HGID_SHELL, ph2?TMID_CU:0);
        if (!cfg.noPcm) {
            writePart(out,"PCM_Pos",     PID_PCM_POS,     SID_SOLID_RIGID,MID_RIGID,0);
            writePart(out,"PCM_Neg",     PID_PCM_NEG,     SID_SOLID_RIGID,MID_RIGID,0);
        }
        if (cfg.mode != "bare" && cfg.mode != "swell") {
            writePart(out,"Impactor",    PID_INDENTER,    SID_SOLID_RIGID,MID_RIGID,0);
            writePart(out,"Ground_Plate",PID_GROUND,      SID_SOLID_RIGID,MID_RIGID,0);
        }

        writeComment(out, "Parts — Jellyroll (per UC)");
        for (int uc = 0; uc < nUC; ++uc) {
            char t[64];
            bool isMerge = cfg.mergeCc && (uc > 0);
            bool isLast  = (uc == nUC-1);
            if (!isMerge) {
                std::snprintf(t,sizeof(t),"Al_CC_UC%d",  uc);
                writePart(out,t,bat_pid_stacked(uc,LT_AL), SID_SHELL_AL,  MID_AL, HGID_SHELL, ph2?TMID_AL:0);
            }
            std::snprintf(t,sizeof(t),"Cathode_UC%d",uc);
            // solidElectrode=true → ELEMENT_SOLID → SECTION_SOLID (SID_SOLID_ELEC_STACK, configurable ELFORM)
            // solidElectrode=false → ELEMENT_TSHELL → SECTION_TSHELL (SID_SOLID_ELEC)
            int catSid = cfg.solidElectrode ? SID_SOLID_ELEC_STACK : SID_SOLID_ELEC;
            int anoSid = cfg.solidElectrode ? SID_SOLID_ELEC_STACK : SID_SOLID_ELEC;
            writePart(out,t,bat_pid_stacked(uc,LT_CAT),catSid,MID_CAT,HGID_SOLID, ph2?TMID_CAT:0);
            std::snprintf(t,sizeof(t),"Sep_UC%d",    uc);
            writePart(out,t,bat_pid_stacked(uc,LT_SEP),SID_SHELL_SEP, MID_SEP, 0, ph2?TMID_SEP:0);  // HGID=0: fully integrated
            std::snprintf(t,sizeof(t),"Anode_UC%d",  uc);
            writePart(out,t,bat_pid_stacked(uc,LT_ANO),anoSid,MID_ANO,HGID_SOLID, ph2?TMID_ANO:0);
            if (!cfg.mergeCc || isLast) {
                std::snprintf(t,sizeof(t),"Cu_CC_UC%d",  uc);
                writePart(out,t,bat_pid_stacked(uc,LT_CU), SID_SHELL_CU,  MID_CU, HGID_SHELL, ph2?TMID_CU:0);
            }
            if (cfg.mergeCc && !isLast) {
                std::snprintf(t,sizeof(t),"CuAl_CC_UC%d", uc);
                writePart(out,t,bat_pid_stacked(uc,LT_CUAL), SID_SOLID_CC, MID_CUAL, HGID_SOLID);
            }
        }

        // Nodes
        writeComment(out, "Nodes");
        out << "*NODE\n$#   nid               x               y               z\n";
        out << nodeBuf.str();

        // Shell elements
        writeComment(out, "Shell Elements");
        out << "*ELEMENT_SHELL\n$#   eid     pid      n1      n2      n3      n4\n";
        out << shellBuf.str();

        // Deformable elements (electrodes, electrolyte) → ELEMENT_TSHELL
        if (nSolids > 0) {
            writeComment(out, "Electrode / Electrolyte Elements (TSHELL)");
            out << "*ELEMENT_TSHELL\n"
                   "$#   eid     pid      n1      n2      n3      n4"
                   "      n5      n6      n7      n8\n";
            out << solidBuf.str();
        }
        // Rigid elements (impactor, PCM, ground plate) → ELEMENT_SOLID
        if (nRigids > 0) {
            writeComment(out, "Rigid Elements (Impactor / PCM / Ground Plate)");
            out << "*ELEMENT_SOLID\n"
                   "$#   eid     pid      n1      n2      n3      n4"
                   "      n5      n6      n7      n8\n";
            out << rigidBuf.str();
        }

        // Node sets
        writeComment(out, "Node Sets");
        if (!nsetFixBottomEdge.empty())
            writeSetNodeList(out, SID_NODE_FIX_BOT, "Fix_Bottom_Edge", nsetFixBottomEdge);
        if (!nsetStackTop.empty())
            writeSetNodeList(out, SID_NODE_TOPSTACK,  "Stack_Top_Nodes",   nsetStackTop);
        if (!nsetImpactorAll.empty())
            writeSetNodeList(out, SID_NODE_INDENTER, "Impactor_All_Nodes", nsetImpactorAll);
        if (!nsetGroundPlateAll.empty())
            writeSetNodeList(out, SID_NODE_GROUND, "Ground_Plate_Nodes", nsetGroundPlateAll);

        // Part sets
        writeComment(out, "Part Sets");
        writeSetPartList(out, SID_PART_CELL, "All_Cell_Parts",     psetAllCell);
        writeSetPartList(out, 110, "PSET_POUCH",            psetPouch);
        writeSetPartList(out, 111, "PSET_ALL_CATHODE",      psetAllCathode);
        writeSetPartList(out, 112, "PSET_ALL_ANODE",        psetAllAnode);
        writeSetPartList(out, 113, "PSET_ALL_SEPARATOR",    psetSep);
        writeSetPartList(out, 114, "PSET_ALL_AL_CC",        psetAlCC);
        writeSetPartList(out, 115, "PSET_ALL_CU_CC",        psetCuCC);
        if (!psetElectrolyte.empty())
            writeSetPartList(out, 116, "PSET_ELECTROLYTE",  psetElectrolyte);
        if (!psetImpactor.empty())
            writeSetPartList(out, 100, "PSET_IMPACTOR",     psetImpactor);
        if (!psetGroundPlate.empty())
            writeSetPartList(out, 101, "PSET_GROUND_PLATE", psetGroundPlate);

        // EM RANDLES isopotential node sets (SID 201/202)
        if (cfg.emRandles) {
            if (!emAlCCOuterNids.empty())
                writeSetNodeList(out, 201, "EM_Al_CC_Outer_Bot", emAlCCOuterNids);
            if (!emCuCCOuterNids.empty())
                writeSetNodeList(out, 202, "EM_Cu_CC_Outer_Top", emCuCCOuterNids);
        }

        // INITIAL_STRESS_SHELL (pouch pre-tension)
        if (cfg.pouchExpandRatio > 0.0 && !pouchEids.empty()) {
            double sigma = 70000.0 * cfg.pouchExpandRatio;  // E_pouch * ratio
            int NPLANE = 1, NTHICK = 5;
            writeComment(out, "INITIAL_STRESS_SHELL — Pouch pre-tension");
            char buf[128];
            std::snprintf(buf, sizeof(buf),
                "$ pouch biaxial tension: ratio=%.4f, sigma=%.1f MPa, %d elements\n",
                cfg.pouchExpandRatio, sigma, (int)pouchEids.size());
            out << buf;
            std::snprintf(buf, sizeof(buf),
                "%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f\n",
                sigma, sigma, 0.0, 0.0, 0.0, 0.0, 0.0);
            std::string stressLine(buf);
            for (int eid : pouchEids) {
                out << "*INITIAL_STRESS_SHELL\n";
                std::snprintf(buf, sizeof(buf),
                    "%10d%10d%10d%10d%10d%10d\n",
                    eid, NPLANE, NTHICK, 0, 0, 0);
                out << buf;
                for (int ip = 0; ip < NPLANE*NTHICK; ++ip)
                    out << stressLine;
            }
        }

        // AIRBAG_LINEAR_FLUID (airbag_fill mode)
        if (cfg.airbagFill && !pouchSegments.empty()) {
            int SID_AIRBAG = SID_SEG_AIRBAG;  // 504
            double bulk = cfg.matElyte.bulkStacked;
            double rho  = cfg.matElyte.rho;

            // Per-segment inward-normal fix for airbag:
            // LS-DYNA AIRBAG segments must have normals pointing INTO the gas cavity.
            // The top panel and bottom panel have the same node winding → same +z normal
            // direction, but only one side can be "inward". Fix each segment individually
            // by checking if its normal points toward the cavity centroid.
            auto& np = nodePos;

            // Compute centroid of all pouch boundary nodes
            double cxSum=0, cySum=0, czSum=0;
            int nPts=0;
            {
                std::unordered_set<int> seen;
                for (const auto& s : pouchSegments) {
                    for (int nid : {s.n1, s.n2, s.n3, s.n4}) {
                        if (seen.insert(nid).second) {
                            cxSum += np[nid-1].x;
                            cySum += np[nid-1].y;
                            czSum += np[nid-1].z;
                            ++nPts;
                        }
                    }
                }
            }
            Vec3 cav = {cxSum/nPts, cySum/nPts, czSum/nPts};

            writeComment(out, "AIRBAG_LINEAR_FLUID (Electrolyte Cavity)");
            out << "*SET_SEGMENT_TITLE\n"
                << "Electrolyte_Cavity_AIRBAG\n";
            char buf[128];
            std::snprintf(buf, sizeof(buf),
                "%10d%10.1f%10.1f%10.1f%10.1f\n",
                SID_AIRBAG, 0.0, 0.0, 0.0, 0.0);
            out << buf;
            for (const auto& s : pouchSegments) {
                // Segment quad normal via diagonal cross product
                const Vec3& p1=np[s.n1-1]; const Vec3& p2=np[s.n2-1];
                const Vec3& p3=np[s.n3-1]; const Vec3& p4=np[s.n4-1];
                double d1x=p3.x-p1.x, d1y=p3.y-p1.y, d1z=p3.z-p1.z;
                double d2x=p4.x-p2.x, d2y=p4.y-p2.y, d2z=p4.z-p2.z;
                double snx=d1y*d2z-d1z*d2y, sny=d1z*d2x-d1x*d2z, snz=d1x*d2y-d1y*d2x;
                // Vector from segment centroid toward cavity centroid (inward direction)
                double scx=(p1.x+p2.x+p3.x+p4.x)*0.25;
                double scy=(p1.y+p2.y+p3.y+p4.y)*0.25;
                double scz=(p1.z+p2.z+p3.z+p4.z)*0.25;
                double dot = snx*(cav.x-scx) + sny*(cav.y-scy) + snz*(cav.z-scz);
                // If normal points outward (dot < 0), reverse node order
                if (dot < 0)
                    std::snprintf(buf, sizeof(buf),
                        "%10d%10d%10d%10d\n", s.n1, s.n4, s.n3, s.n2);
                else
                    std::snprintf(buf, sizeof(buf),
                        "%10d%10d%10d%10d\n", s.n1, s.n2, s.n3, s.n4);
                out << buf;
            }

            out << "*AIRBAG_LINEAR_FLUID\n"
                << "$#     sid    sidtyp      rbid      vsca      psca"
                   "      vini       mwd      spsf\n";
            std::snprintf(buf, sizeof(buf),
                "%10d%10d%10d\n", SID_AIRBAG, 0, 0);
            out << buf;
            out << "$#    bulk        ro     lcint    lcoutt    lcoutp"
                   "     lcfit    lcbulk      lcid\n";
            std::snprintf(buf, sizeof(buf),
                "%10.1f%10.3E%10d%10d%10d%10d%10d%10d\n",
                bulk, rho, 0, 0, 0, 0, 0, 0);
            out << buf;
        }

        // Bare mode: SET_SEGMENT_TITLE for external pressure (SID_SEG_POUCH_LOAD=503)
        if (cfg.mode == "bare" && !pouchSegments.empty()) {
            writeComment(out, "Pouch Segment Set (bare mode external pressure)");
            char buf[128];

            // Compute signed volume for normal direction check
            double signedVol = 0.0;
            for (const auto& s : pouchSegments) {
                auto tri = [&](int a, int b, int c) {
                    const Vec3& p1=nodePos[a-1]; const Vec3& p2=nodePos[b-1]; const Vec3& p3=nodePos[c-1];
                    double cx_=(p2.y-p1.y)*(p3.z-p1.z)-(p2.z-p1.z)*(p3.y-p1.y);
                    double cy_=(p2.z-p1.z)*(p3.x-p1.x)-(p2.x-p1.x)*(p3.z-p1.z);
                    double cz_=(p2.x-p1.x)*(p3.y-p1.y)-(p2.y-p1.y)*(p3.x-p1.x);
                    return p1.x*cx_ + p1.y*cy_ + p1.z*cz_;
                };
                signedVol += tri(s.n1,s.n2,s.n3) + tri(s.n1,s.n3,s.n4);
            }
            bool flip = (signedVol < 0.0);

            out << "*SET_SEGMENT_TITLE\nPouch_Outer_Load\n";
            out << iField(SID_SEG_POUCH_LOAD) << "\n";
            for (const auto& s : pouchSegments) {
                int a=s.n1, b=s.n2, c=s.n3, d=s.n4;
                if (flip) { std::swap(a,b); std::swap(c,d); }
                std::snprintf(buf,sizeof(buf),"%10d%10d%10d%10d\n",a,b,c,d);
                out << buf;
            }
        }
    }
};

// ─────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────
MeshStats writeMeshStacked(std::ostream& out, const BatteryConfig& cfg) {
    BatMeshGen gen(cfg);
    gen.build();
    gen.flush(out);
    return gen.stats;
}

} // namespace bat
