#include "BatteryMeshWound.h"
#include "BatteryWriter.h"
#include "BatteryIds.h"
#include "BatterySwelling.h"
#include <ostream>
#include <vector>
#include <array>
#include <unordered_map>
#include <map>
#include <cmath>
#include <cstdio>
#include <algorithm>
#include <numeric>

namespace bat {

// ─────────────────────────────────────────────────────────────
// Internal mesh builder class
// ─────────────────────────────────────────────────────────────
class WoundMeshGen {
public:
    explicit WoundMeshGen(const BatteryConfig& cfg, std::ostream& out)
        : cfg_(cfg), out_(out) {}

    MeshStats build();

private:
    const BatteryConfig& cfg_;
    std::ostream&        out_;

    int nextNid_ = 1;
    int nextEid_ = 1;

    int nNodes_   = 0;
    int nShells_  = 0;
    int nTShells_ = 0;
    int nSolids_  = 0;

    // Accumulated node/element data streamed into out_
    // (We stream directly; wound cells are large)

    // Node sets
    std::vector<int> fixBotNids_;   // SID_NODE_FIX_BOT=1: bottom perimeter nodes
    std::vector<int> indenterNids_; // SID_NODE_INDENTER=2: impactor nodes
    std::vector<int> groundNids_;   // SID_NODE_GROUND=3: ground plate nodes

    // Part ID tracking (for SET_PART_LIST)
    std::vector<int> cellPids_;        // all jellyroll + pouch
    std::vector<int> cathPids_;
    std::vector<int> anodePids_;
    std::vector<int> alCCPids_;
    std::vector<int> cuCCPids_;
    std::vector<int> sepPids_;

    // Airbag segment tracking (airbagFill=true only)
    bool trackPos_  = false;  // set to true before buildPouch()
    struct XYZ { double x, y, z; };
    std::unordered_map<int, XYZ>      trackedPos_;   // nid → position
    std::vector<std::array<int,4>>    pouchSegs_;     // (n1,n2,n3,n4) quads

    // Swelling element tracking (phase==2 && swelling.enabled)
    std::vector<SwellElement>  swellElems_;

    // EM Randles node sets (emRandles=true)
    std::vector<int> emAlNids_;   // SID 201: Al CC inner face outer ring
    std::vector<int> emCuNids_;   // SID 202: Cu CC outer face inner ring

    // Tabs (noPcm=false)
    std::vector<int> alTabTopNids_;   // innermost Al CC top edge (y=cellHeight)
    std::vector<int> cuTabTopNids_;   // outermost Cu CC top edge
    int tabPosNy_ = 0;   // last tab top row nid start
    int tabNegNy_ = 0;

    // Cached geometry for tabs/PCM
    double tabAlZ_  = 0.0;   // z of inner Al CC surface (for tab placement)
    double tabCuZ_  = 0.0;   // z of outer Cu CC surface
    double jHalfL_  = 0.0;   // half_L of jellyroll

    // ── helpers ──
    int  addNode(double x, double y, double z);
    void writeAirbag();
    void buildElectrolyte(double h_inner, double h_outer, double cx, double half_L,
                          double flat_ratio, int n_str, int n_arc, int ny, double dy);
    void buildTabs(int ny, double dy, double meshSize);
    void buildPcm(double meshSize);
    void writeSwellingWound();
    void writeEmRandles();
    int addShell(int pid, int n1, int n2, int n3, int n4);
    int addTShell(int pid, int n1, int n2, int n3, int n4,
                              int n5, int n6, int n7, int n8);
    int addSolid(int pid, int n1, int n2, int n3, int n4,
                             int n5, int n6, int n7, int n8);

    // ── racetrack geometry ──
    // flat_ratio: arc x-half-radius = h * flat_ratio  (1.0=semicircle)
    static int nArcSegs(double h, double flat_ratio, double mesh_s);

    // Build a flat racetrack loop grid: (ny+1) rows × (n_total+1) cols
    // Upper straight (n_str) → Right arc (n_arc) → Lower straight (n_str) → Left arc (n_arc)
    // Last column = first column (closed, same nid)
    // Returns grid[jy*(n_total+1) + js]
    std::vector<int> flatLoopNodes(double h, double cx, double half_L,
                                   double flat_ratio, int n_str, int n_arc,
                                   int ny, double dy,
                                   std::vector<int>* botPerim = nullptr,
                                   double y0 = 0.0);

    // Build separator grid with axial overhang: take a base grid (ny rows)
    // and prepend/append one row at y=-oh and y=cellHeight+oh.
    // Returns new grid with (ny+2) rows and same n_total columns.
    std::vector<int> addAxialOverhang(
        const std::vector<int>& baseGrid, int n_total, int ny,
        double oh, double cellHeight,
        double h, double cx, double half_L, double flat_ratio,
        int n_str, int n_arc);

    // Elements from two adjacent grid columns (SHELL)
    // segs: if non-null, append (n1,n2,n3,n4) quads for airbag tracking
    void shellFromGrid(int pid, const std::vector<int>& grid,
                       int n_total, int ny,
                       std::vector<std::array<int,4>>* segs = nullptr);
    // Elements from inner/outer grids (TSHELL 8-node)
    void tshellFromGrids(int pid, const std::vector<int>& inner,
                         const std::vector<int>& outer,
                         int n_total, int ny);
    // Elements from inner/outer grids (SOLID 8-node)
    void solidFromGrids(int pid, const std::vector<int>& inner,
                        const std::vector<int>& outer,
                        int n_total, int ny);

    // ── wound cell builders ──
    void buildFlatCell();
    void buildSpiralCell();   // conformal Archimedean spiral

    // ── fixtures ──
    double jRacX_ = 0.0;   // jellyroll outer X half-span (arc tip)
    double jRacZ_ = 0.0;   // jellyroll outer Z half-span
    double jBufZ_ = 0.0;   // outer surface Z  = jRacZ_ + buffer + pouch

    void buildPouch(double h_jelly, double cx, double half_L,
                    double flat_ratio, int n_str_out, int n_arc_out,
                    int ny, double dy);
    void buildSideImpactor();
    void buildNailImpactor();
    void buildDentImpactor();
    void buildGroundPlate();

    // ── flush (sets + parts) ──
    void flushSets();
    void flushParts();
    void flushContacts();
};

// ─────────────────────────────────────────────────────────────
// Node / element add helpers
// ─────────────────────────────────────────────────────────────
int WoundMeshGen::addNode(double x, double y, double z) {
    char buf[96];
    snprintf(buf, sizeof(buf), "%8d%16.6f%16.6f%16.6f       0       0\n",
             nextNid_, x, y, z);
    out_ << buf;
    if (trackPos_) trackedPos_[nextNid_] = {x, y, z};
    ++nNodes_;
    return nextNid_++;
}

int WoundMeshGen::addShell(int pid, int n1, int n2, int n3, int n4) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d\n",
             nextEid_, pid, n1, n2, n3, n4);
    out_ << buf;
    ++nShells_;
    return nextEid_++;
}

int WoundMeshGen::addTShell(int pid, int n1, int n2, int n3, int n4,
                                         int n5, int n6, int n7, int n8) {
    char buf[96];
    snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
             nextEid_, pid, n1, n2, n3, n4, n5, n6, n7, n8);
    out_ << buf;
    ++nTShells_;
    return nextEid_++;
}

int WoundMeshGen::addSolid(int pid, int n1, int n2, int n3, int n4,
                                        int n5, int n6, int n7, int n8) {
    char buf[96];
    snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
             nextEid_, pid, n1, n2, n3, n4, n5, n6, n7, n8);
    out_ << buf;
    ++nSolids_;
    return nextEid_++;
}

// ─────────────────────────────────────────────────────────────
// Racetrack geometry
// ─────────────────────────────────────────────────────────────
int WoundMeshGen::nArcSegs(double h, double flat_ratio, double mesh_s) {
    if (h < 0.1) return 0;
    // Ellipse half-perimeter approximation: π * sqrt((a² + b²) / 2)
    // a = h * flat_ratio  (x-radius),  b = h  (z-radius)
    double a = h * flat_ratio;
    double half_perim = M_PI * std::sqrt((a * a + h * h) / 2.0);
    int n = std::max(12, (int)std::round(half_perim / mesh_s));
    // Cap: min arc segment ≈ 0.05mm
    if (a > 1e-6) {
        int n_max = std::max(3, (int)std::floor(a * M_PI / 0.05));
        n = std::min(n, n_max);
    }
    return n;
}

std::vector<int> WoundMeshGen::flatLoopNodes(
        double h, double cx, double half_L,
        double flat_ratio, int n_str, int n_arc,
        int ny, double dy,
        std::vector<int>* botPerim,
        double y0) {

    // n_total = 2*n_str + 2*n_arc  (closed loop)
    int n_total = (n_arc > 0) ? (2 * n_str + 2 * n_arc)
                               : (2 * (n_str + 1));

    std::vector<int> grid((ny + 1) * (n_total + 1), 0);
    auto G = [&](int jy, int js) -> int& {
        return grid[jy * (n_total + 1) + js];
    };

    double x_left  = cx - half_L;
    double x_right = cx + half_L;
    double x_r = h * flat_ratio;   // arc x-radius

    int idx = 0;

    auto addCol = [&](double x, double z) {
        for (int jy = 0; jy <= ny; ++jy) {
            int nid = addNode(x, y0 + jy * dy, z);
            G(jy, idx) = nid;
            if (jy == 0 && botPerim) botPerim->push_back(nid);
        }
        ++idx;
    };

    if (n_arc == 0) {
        // No arc: upper strip left→right, lower strip right→left (loop continuity)
        for (int i = 0; i <= n_str; ++i) {
            double x = x_left + i * (2.0 * half_L) / n_str;
            addCol(x, +h);
        }
        for (int i = 0; i <= n_str; ++i) {
            double x = x_right - i * (2.0 * half_L) / n_str;
            addCol(x, -h);
        }
        // Closed: last col = first col (alias)
        for (int jy = 0; jy <= ny; ++jy)
            G(jy, n_total) = G(jy, 0);
    } else {
        // 1. Upper straight: z=+h, left→right (n_str pts, not including right end)
        for (int i = 0; i < n_str; ++i) {
            double x = x_left + i * (2.0 * half_L) / n_str;
            addCol(x, +h);
        }
        // 2. Right arc: theta from π/2 → -π/2
        for (int i = 0; i < n_arc; ++i) {
            double theta = M_PI_2 - i * M_PI / n_arc;
            double x = x_right + x_r * std::cos(theta);
            double z = h * std::sin(theta);
            addCol(x, z);
        }
        // 3. Lower straight: z=-h, right→left (n_str pts)
        for (int i = 0; i < n_str; ++i) {
            double x = x_right - i * (2.0 * half_L) / n_str;
            addCol(x, -h);
        }
        // 4. Left arc: theta from -π/2 → π/2
        for (int i = 0; i < n_arc; ++i) {
            double theta = -M_PI_2 - i * M_PI / n_arc;
            double x = x_left + x_r * std::cos(theta);
            double z = h * std::sin(theta);
            addCol(x, z);
        }
        // Close loop: last col = first col
        for (int jy = 0; jy <= ny; ++jy)
            G(jy, n_total) = G(jy, 0);
    }

    return grid;
}

// ─────────────────────────────────────────────────────────────
// Separator axial overhang: prepend row at y=-oh, append row at y=cellHeight+oh
// ─────────────────────────────────────────────────────────────
std::vector<int> WoundMeshGen::addAxialOverhang(
        const std::vector<int>& baseGrid, int n_total, int ny,
        double oh, double cellHeight,
        double h, double cx, double half_L, double flat_ratio,
        int n_str, int n_arc) {
    // Generate two single-row grids at overhang y positions
    auto botRow = flatLoopNodes(h, cx, half_L, flat_ratio, n_str, n_arc,
                                0, 1.0, nullptr, -oh);       // 1 row at y=-oh
    auto topRow = flatLoopNodes(h, cx, half_L, flat_ratio, n_str, n_arc,
                                0, 1.0, nullptr, cellHeight + oh); // 1 row at y=cH+oh

    int stride = n_total + 1;
    int ny_new = ny + 2;
    std::vector<int> newGrid((ny_new + 1) * stride);

    auto G = [&](int jy, int js) -> int& {
        return newGrid[jy * stride + js];
    };
    auto Gb = [&](int jy, int js) {
        return baseGrid[jy * stride + js];
    };

    // Row 0: bottom overhang
    for (int js = 0; js <= n_total; ++js)
        G(0, js) = botRow[js];  // botRow has (0+1)*stride entries
    // Rows 1..ny+1: original base grid
    for (int jy = 0; jy <= ny; ++jy)
        for (int js = 0; js <= n_total; ++js)
            G(jy + 1, js) = Gb(jy, js);
    // Row ny+2: top overhang
    for (int js = 0; js <= n_total; ++js)
        G(ny + 2, js) = topRow[js];

    return newGrid;
}

// ─────────────────────────────────────────────────────────────
// Element creation helpers
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::shellFromGrid(int pid, const std::vector<int>& grid,
                                  int n_total, int ny,
                                  std::vector<std::array<int,4>>* segs) {
    auto G = [&](int jy, int js) {
        return grid[jy * (n_total + 1) + js];
    };
    for (int js = 0; js < n_total; ++js) {
        for (int jy = 0; jy < ny; ++jy) {
            int n1 = G(jy,js), n2 = G(jy,js+1),
                n3 = G(jy+1,js+1), n4 = G(jy+1,js);
            addShell(pid, n1, n2, n3, n4);
            if (segs) segs->push_back({n1, n2, n3, n4});
        }
    }
}

void WoundMeshGen::tshellFromGrids(int pid,
        const std::vector<int>& inner, const std::vector<int>& outer,
        int n_total, int ny) {
    auto I = [&](int jy, int js) { return inner[jy*(n_total+1)+js]; };
    auto O = [&](int jy, int js) { return outer[jy*(n_total+1)+js]; };
    for (int js = 0; js < n_total; ++js) {
        for (int jy = 0; jy < ny; ++jy) {
            addTShell(pid,
                I(jy,js),   I(jy,js+1),   I(jy+1,js+1), I(jy+1,js),
                O(jy,js),   O(jy,js+1),   O(jy+1,js+1), O(jy+1,js));
        }
    }
}

void WoundMeshGen::solidFromGrids(int pid,
        const std::vector<int>& inner, const std::vector<int>& outer,
        int n_total, int ny) {
    auto I = [&](int jy, int js) { return inner[jy*(n_total+1)+js]; };
    auto O = [&](int jy, int js) { return outer[jy*(n_total+1)+js]; };
    for (int js = 0; js < n_total; ++js) {
        for (int jy = 0; jy < ny; ++jy) {
            addSolid(pid,
                I(jy,js),   I(jy,js+1),   I(jy+1,js+1), I(jy+1,js),
                O(jy,js),   O(jy,js+1),   O(jy+1,js+1), O(jy+1,js));
        }
    }
}

// ─────────────────────────────────────────────────────────────
// buildFlatCell — flat non-conformal winding
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildFlatCell() {
    const auto& t   = cfg_.thick;
    const auto& geo = cfg_.geo;

    double cellWidth  = geo.cellWidth;
    double cellHeight = geo.cellHeight;
    int    nWinds     = cfg_.woundNWinds;
    double flatRatio  = cfg_.woundFlatRatio;

    // Wound: single-sided coatings
    double tAl  = t.alCC;
    double tCat = t.cathode;   // single side
    double tSep = t.separator;
    double tAno = t.anode;     // single side
    double tCu  = t.cuCC;
    double unitCell = tAl + tCat + tSep + tAno + tCu;

    // core_void: winding starts at mandrel radius instead of h=0
    // Minimum coreH: nArcSegs needs h >= 0.1mm to create arc segments.
    // With flat_ratio, arc x-radius = coreH * flat_ratio, so need coreH >= 0.1/flat_ratio.
    double coreH = cfg_.coreVoid ? cfg_.woundMandrel : 0.0;
    double minCore = 0.12 / std::max(flatRatio, 0.1);  // ensure arc generation at inner core
    if (cfg_.coreFill) minCore = std::max(minCore, unitCell * 0.6);  // extra space for fill layer
    if (coreH < minCore) coreH = minCore;

    // layer_gap_frac: inter-winding gap (debugging contact detection)
    double windingGap = unitCell * cfg_.layerGapFrac;  // gap between consecutive windings

    double hMax       = coreH + unitCell * nWinds + windingGap * (nWinds - 1);
    double cx         = cellWidth / 2.0;
    double half_L     = (cellWidth - 2.0 * hMax * flatRatio) / 2.0;
    if (half_L < 0.0) half_L = 0.0;

    double meshSize  = batteryMeshSize(cfg_.tier);
    double meshSizeP = (cfg_.woundMeshSizePath > 0.0) ? cfg_.woundMeshSizePath
                                                       : meshSize * 0.8;

    int ny = (int)std::round(cellHeight / meshSize);
    if (ny < 1) ny = 1;
    double dy = cellHeight / ny;
    int n_str = std::max(2, (int)std::round((2.0 * half_L) / meshSizeP));

    // Layer relative mid-offsets from winding base
    // (measured from inner edge of Al CC)
    struct LayerDef {
        int    pid;
        double midOff;  // from base_h
        bool   isTShell;
        bool   isShell;
        double innerOff; // solid inner edge (for TSHELL)
        double outerOff; // solid outer edge (for TSHELL)
    };
    std::vector<LayerDef> layers = {
        // SHELL at Al CC inner face (shared with cathode inner)
        {PID_W_AL,  0.0,       false, true,  0.0, 0.0},
        // TSHELL: cathode (inner=Al face, outer=Al+cat)
        {PID_W_CAT, tAl,       true,  false, 0.0, tCat},  // offsets relative to base_h start
        // SHELL at cathode outer face (= sep inner face)
        {PID_W_SEP, tAl+tCat,  false, true,  0.0, 0.0},
        // TSHELL: anode
        {PID_W_ANO, tAl+tCat+tSep, true, false, 0.0, tAno},
        // SHELL at anode outer face (= Cu CC inner face)
        {PID_W_CU,  unitCell - tCu, false, true, 0.0, 0.0},
    };

    // Track first/last layer PIDs for cell part set
    for (auto& ld : layers) {
        int pid = ld.pid;
        if (std::find(cellPids_.begin(), cellPids_.end(), pid) == cellPids_.end())
            cellPids_.push_back(pid);
    }
    alCCPids_ = {PID_W_AL};
    cathPids_ = {PID_W_CAT};
    sepPids_  = {PID_W_SEP};
    anodePids_= {PID_W_ANO};
    cuCCPids_ = {PID_W_CU};

    // Cache half_L for tabs
    jHalfL_ = half_L;
    bool doSwelling = ((cfg_.phase == 2 || cfg_.mode == "swell") && cfg_.swelling.enabled && cfg_.solidElectrode && !cfg_.useDynain);

    // ── Core fill: electrolyte solid in the inner core void ───
    // Fill h=0..coreH with electrolyte. Split into layers to avoid
    // degenerate elements at h=0 (minCore ensures h >= ~0.1mm).
    {
        // Core fill: simple hex block filling the inner core void
        // Shape: flat box from (-half_L, 0, -coreH) to (+half_L, cellH, +coreH)
        if (cfg_.coreFill && coreH > 0.01) {
            writeComment(out_, "Core Fill (Electrolyte)");
            double x_left  = cx - half_L;
            double x_right = cx + half_L;
            int nx_core = std::max(2, n_str);
            int nz_core = std::max(1, (int)std::round(2.0 * coreH / meshSizeP));
            double dxc = (x_right - x_left) / nx_core;
            double dzc = (2.0 * coreH) / nz_core;

            out_ << "*NODE\n";
            // Node grid: (nx_core+1) × (ny+1) × (nz_core+1)
            std::vector<std::vector<std::vector<int>>> coreNids(
                nz_core + 1, std::vector<std::vector<int>>(
                    ny + 1, std::vector<int>(nx_core + 1, 0)));
            for (int kz = 0; kz <= nz_core; ++kz)
                for (int jy = 0; jy <= ny; ++jy)
                    for (int ix = 0; ix <= nx_core; ++ix)
                        coreNids[kz][jy][ix] = addNode(
                            x_left + ix * dxc,
                            jy * dy,
                            -coreH + kz * dzc);

            out_ << "*ELEMENT_SOLID\n";
            char buf[128];
            for (int kz = 0; kz < nz_core; ++kz)
                for (int jy = 0; jy < ny; ++jy)
                    for (int ix = 0; ix < nx_core; ++ix) {
                        int n1 = coreNids[kz][jy][ix],     n2 = coreNids[kz][jy][ix+1],
                            n3 = coreNids[kz][jy+1][ix+1], n4 = coreNids[kz][jy+1][ix],
                            n5 = coreNids[kz+1][jy][ix],   n6 = coreNids[kz+1][jy][ix+1],
                            n7 = coreNids[kz+1][jy+1][ix+1],n8 = coreNids[kz+1][jy+1][ix];
                        std::snprintf(buf, sizeof(buf),
                            "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
                            nextEid_, PID_W_ELYTE, n1,n2,n3,n4, n5,n6,n7,n8);
                        out_ << buf;
                        ++nextEid_; ++nSolids_;
                    }
            if (std::find(cellPids_.begin(), cellPids_.end(), PID_W_ELYTE) == cellPids_.end())
                cellPids_.push_back(PID_W_ELYTE);
        }
    }

    out_ << "$\n$ --- Wound Layers ---\n$\n";

    for (int w = 0; w < nWinds; ++w) {
        double base_h = coreH + w * (unitCell + windingGap);

        // Al CC — SHELL at base_h (inner edge)
        // Each winding opens its own *NODE section so Al CC nodes for w>0
        // are not written into an *ELEMENT_SHELL context (pre-existing bug fix).
        {
            double h = base_h;
            int n_arc = nArcSegs(h, flatRatio, meshSizeP);
            std::vector<int>* botPerim = (w == 0) ? &fixBotNids_ : nullptr;
            out_ << "*NODE\n";
            auto grid = flatLoopNodes(h, cx, half_L, flatRatio, n_str, n_arc, ny, dy, botPerim);
            int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));
            out_ << "*ELEMENT_SHELL\n";
            shellFromGrid(PID_W_AL, grid, n_total, ny);
            if (w == 0) {
                for (int js = 0; js < n_total; ++js)
                    alTabTopNids_.push_back(grid[ny*(n_total+1)+js]);
                tabAlZ_ = h;
                if (cfg_.emRandles) emAlNids_ = alTabTopNids_;
            }
        }

        // Cathode — SOLID / TSHELL / SHELL(all_shell)
        {
            double h_inner = base_h;
            double h_outer = base_h + tCat;
            int n_arc = nArcSegs(h_outer, flatRatio, meshSizeP);
            out_ << "*NODE\n";
            if (cfg_.allShell) {
                double h_mid = (h_inner + h_outer) * 0.5;
                int na = nArcSegs(h_mid, flatRatio, meshSizeP);
                auto midGrid = flatLoopNodes(h_mid, cx, half_L, flatRatio, n_str, na, ny, dy);
                int nt = (na>0)?(2*n_str+2*na):(2*(n_str+1));
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_CAT, midGrid, nt, ny);
            } else {
                auto innerGrid = flatLoopNodes(h_inner, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
                auto outerGrid = flatLoopNodes(h_outer, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
                int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));
                if (cfg_.solidElectrode) {
                    out_ << "*ELEMENT_SOLID\n";
                    int eidBefore = nextEid_;
                    solidFromGrids(PID_W_CAT, innerGrid, outerGrid, n_total, ny);
                    if (doSwelling)
                        for (int e = eidBefore; e < nextEid_; ++e)
                            swellElems_.push_back({e, cfg_.swelling.nmcCte});
                } else {
                    out_ << "*ELEMENT_TSHELL\n";
                    tshellFromGrids(PID_W_CAT, innerGrid, outerGrid, n_total, ny);
                }
            }
        }

        // Separator — SHELL at base_h + tAl + tCat
        // Axial (Y) overhang: separator extends beyond electrode edges
        {
            double h = base_h + tAl + tCat;
            double sepOH = t.sepOverhang;
            int n_arc_sep = nArcSegs(h, flatRatio, meshSizeP);
            int n_total_sep = (n_arc_sep > 0) ? (2*n_str + 2*n_arc_sep) : (2*(n_str+1));
            out_ << "*NODE\n";
            auto baseGrid = flatLoopNodes(h, cx, half_L, flatRatio, n_str, n_arc_sep, ny, dy);
            if (sepOH > 0.0) {
                auto grid = addAxialOverhang(baseGrid, n_total_sep, ny, sepOH,
                                             cellHeight, h, cx, half_L, flatRatio, n_str, n_arc_sep);
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_SEP, grid, n_total_sep, ny + 2);
            } else {
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_SEP, baseGrid, n_total_sep, ny);
            }
        }

        // Anode — SOLID / TSHELL / SHELL(all_shell)
        {
            double h_inner = base_h + tAl + tCat + tSep;
            double h_outer = base_h + tAl + tCat + tSep + tAno;
            int n_arc = nArcSegs(h_outer, flatRatio, meshSizeP);
            out_ << "*NODE\n";
            if (cfg_.allShell) {
                double h_mid = (h_inner + h_outer) * 0.5;
                int na = nArcSegs(h_mid, flatRatio, meshSizeP);
                auto midGrid = flatLoopNodes(h_mid, cx, half_L, flatRatio, n_str, na, ny, dy);
                int nt = (na>0)?(2*n_str+2*na):(2*(n_str+1));
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_ANO, midGrid, nt, ny);
            } else {
                auto innerGrid = flatLoopNodes(h_inner, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
                auto outerGrid = flatLoopNodes(h_outer, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
                int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));
                if (cfg_.solidElectrode) {
                    out_ << "*ELEMENT_SOLID\n";
                    int eidBefore = nextEid_;
                    solidFromGrids(PID_W_ANO, innerGrid, outerGrid, n_total, ny);
                    if (doSwelling)
                        for (int e = eidBefore; e < nextEid_; ++e)
                            swellElems_.push_back({e, cfg_.swelling.graphiteCte});
                } else {
                    out_ << "*ELEMENT_TSHELL\n";
                    tshellFromGrids(PID_W_ANO, innerGrid, outerGrid, n_total, ny);
                }
            }
        }

        // Cu CC — SHELL at base_h + unitCell
        {
            double h = base_h + unitCell;
            int n_arc = nArcSegs(h, flatRatio, meshSizeP);
            out_ << "*NODE\n";
            auto grid = flatLoopNodes(h, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));
            out_ << "*ELEMENT_SHELL\n";
            shellFromGrid(PID_W_CU, grid, n_total, ny);
            if (w == nWinds - 1) {
                for (int js = 0; js < n_total; ++js)
                    cuTabTopNids_.push_back(grid[ny*(n_total+1)+js]);
                tabCuZ_ = h;
                if (cfg_.emRandles) emCuNids_ = cuTabTopNids_;
            }
        }
    }

    // Note: Electrolyte ring omitted for box-shaped pouch — the flatLoop arc shape
    // of the ring overlaps with the rectangular box corners at the arc ends.
    // The inner pouch space is treated as implicit electrolyte (bare: void, airbag: fluid).

    // Cache outer jellyroll geometry for pouch/impactor placement
    // Cache outer jellyroll geometry for pouch/impactor placement
    jRacZ_ = hMax;
    jRacX_ = hMax * flatRatio;  // arc x-tip extent from straight edge
    jBufZ_ = hMax + t.buffer + t.pouch / 2.0;

    // Pouch wrap + end caps
    double h_outer = hMax + t.buffer;
    int n_arc_out = nArcSegs(h_outer, flatRatio, meshSizeP);
    int n_str_out = std::max(2, (int)std::round((2.0 * half_L) / meshSizeP));
    if (cfg_.airbagFill || cfg_.mode == "bare") trackPos_ = true;
    buildPouch(h_outer, cx, half_L, flatRatio, n_str_out, n_arc_out, ny, dy);
    trackPos_ = false;

    // Fixture
    if (!cfg_.noImpactor) {
        if (cfg_.mode == "dent")
            buildDentImpactor();
        else
            buildSideImpactor();
        buildGroundPlate();
    }

    // Tabs + PCM
    if (!cfg_.noPcm) {
        double meshSize = batteryMeshSize(cfg_.tier);
        buildTabs(ny, dy, meshSize);
        buildPcm(meshSize);
    }
}

// ─────────────────────────────────────────────────────────────
// buildPouch — Python-equivalent 3-D rounded box
// Matches generate_mesh_wound.py _create_pouch_flat_with_caps()
// All 6 faces are quad grids projected via 3-D clip+offset.
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildPouch(double h_outer, double cx, double half_L,
                               double flat_ratio, int /*n_str_out*/, int /*n_arc_out*/,
                               int /*ny*/, double /*dy*/) {
    double R   = cfg_.pouch.rFillet;          // default 0.5 mm for wound
    double buf = R;                            // Python: buf = r_pouch_fillet
    double ht  = cfg_.thick.pouch / 2.0;
    double Rp  = R + ht;
    double H   = cfg_.geo.cellHeight;
    double ds  = batteryMeshSize(cfg_.tier);

    // Jellyroll X span (straight + arc tips)
    double a_jelly = h_outer * flat_ratio;
    double jx0 = cx - half_L - a_jelly;
    double jx1 = cx + half_L + a_jelly;

    // Content boundary (electrolyte envelope)
    // Z: tight to jellyroll outer surface (no extra buf in Z)
    // X/Y: +buf offset. Y expands for separator overhang.
    double oh = cfg_.thick.sepOverhang;
    double bufY = std::max(buf, oh + buf);   // sep overhang + fillet clearance
    double ctx0 = jx0 - buf,    ctx1 = jx1 + buf;
    double cty0 = -bufY,        cty1 = H + bufY;
    double ctz0 = -h_outer,     ctz1 = h_outer;

    // Fillet centers
    double fx0 = ctx0 + R,  fx1 = ctx1 - R;
    double fy0 = cty0 + R,  fy1 = cty1 - R;
    double fz0 = ctz0 + R,  fz1 = ctz1 - R;

    // Box extents (pouch mid-surface)
    double bx0 = ctx0 - ht,  bx1 = ctx1 + ht;
    double by0 = cty0 - ht,  by1 = cty1 + ht;
    double bz0 = ctz0 - ht,  bz1 = ctz1 + ht;

    // Update outer Z extent for impactor placement
    jBufZ_ = bz1;

    // 3-D clip+offset: project (x,y,z) onto pouch mid-surface
    auto pouchMid = [&](double x, double y, double z,
                        double& rx, double& ry, double& rz) {
        double ccx = std::max(fx0, std::min(fx1, x));
        double ccy = std::max(fy0, std::min(fy1, y));
        double ccz = std::max(fz0, std::min(fz1, z));
        double dx = x - ccx, dy = y - ccy, dz = z - ccz;
        double dist = std::sqrt(dx*dx + dy*dy + dz*dz);
        if (dist < 1e-12) { rx = x; ry = y; rz = z; return; }
        rx = ccx + Rp * dx / dist;
        ry = ccy + Rp * dy / dist;
        rz = ccz + Rp * dz / dist;
    };

    // Uniform grid coordinate arrays
    auto makeCoords = [&](double lo, double hi) {
        int n = std::max(4, (int)std::round((hi - lo) / ds));
        std::vector<double> v(n + 1);
        for (int i = 0; i <= n; ++i) v[i] = lo + (hi - lo) * i / n;
        return v;
    };
    auto bxs = makeCoords(bx0, bx1);
    auto bys = makeCoords(by0, by1);
    auto bzs = makeCoords(bz0, bz1);
    int nBX = (int)bxs.size();
    int nBY = (int)bys.size();
    int nBZ = (int)bzs.size();

    // Node cache: deduplicate shared boundary nodes
    using Key3 = std::tuple<int64_t, int64_t, int64_t>;
    std::map<Key3, int> nodeCache;

    out_ << "*NODE\n";

    auto getNode = [&](double bx, double by, double bz) -> int {
        double rx, ry, rz;
        pouchMid(bx, by, bz, rx, ry, rz);
        Key3 key{ (int64_t)std::llround(rx * 1e4),
                  (int64_t)std::llround(ry * 1e4),
                  (int64_t)std::llround(rz * 1e4) };
        auto it = nodeCache.find(key);
        if (it != nodeCache.end()) return it->second;
        int nid = addNode(rx, ry, rz);
        nodeCache[key] = nid;
        return nid;
    };

    // Build 6 face node grids (nodes streamed to *NODE section)
    using Grid2D = std::vector<std::vector<int>>;

    auto buildFaceZ = [&](double zv) {
        Grid2D g(nBY, std::vector<int>(nBX));
        for (int jy = 0; jy < nBY; ++jy)
            for (int ix = 0; ix < nBX; ++ix)
                g[jy][ix] = getNode(bxs[ix], bys[jy], zv);
        return g;
    };
    auto buildFaceX = [&](double xv) {
        Grid2D g(nBZ, std::vector<int>(nBY));
        for (int jz = 0; jz < nBZ; ++jz)
            for (int iy = 0; iy < nBY; ++iy)
                g[jz][iy] = getNode(xv, bys[iy], bzs[jz]);
        return g;
    };
    auto buildFaceY = [&](double yv) {
        Grid2D g(nBZ, std::vector<int>(nBX));
        for (int jz = 0; jz < nBZ; ++jz)
            for (int ix = 0; ix < nBX; ++ix)
                g[jz][ix] = getNode(bxs[ix], yv, bzs[jz]);
        return g;
    };

    auto gZbot = buildFaceZ(bz0);   // -Z face (flat side)
    auto gZtop = buildFaceZ(bz1);   // +Z face (flat side)
    auto gXbot = buildFaceX(bx0);   // -X face (edge side)
    auto gXtop = buildFaceX(bx1);   // +X face (edge side)
    auto gYbot = buildFaceY(by0);   // -Y end cap (y=0)
    auto gYtop = buildFaceY(by1);   // +Y end cap (y=H)

    bool track = (cfg_.airbagFill || cfg_.mode == "bare");

    out_ << "*ELEMENT_SHELL\n";

    auto emitFaceShells = [&](const Grid2D& g, int pid, bool flip) {
        int nv = (int)g.size(), nu = (int)g[0].size();
        for (int jv = 0; jv < nv - 1; ++jv)
            for (int iu = 0; iu < nu - 1; ++iu) {
                int a = g[jv][iu],      b = g[jv][iu+1];
                int c = g[jv+1][iu+1],  d = g[jv+1][iu];
                if (flip) { addShell(pid, a, d, c, b);
                            if (track) pouchSegs_.push_back({a, d, c, b}); }
                else      { addShell(pid, a, b, c, d);
                            if (track) pouchSegs_.push_back({a, b, c, d}); }
            }
    };

    // All 6 faces use one PID — airbag standard, no need to distinguish caps vs sides
    emitFaceShells(gZbot, PID_W_POUCH_SIDE, true);   // -Z
    emitFaceShells(gZtop, PID_W_POUCH_SIDE, false);  // +Z
    emitFaceShells(gXbot, PID_W_POUCH_SIDE, true);   // -X
    emitFaceShells(gXtop, PID_W_POUCH_SIDE, false);  // +X
    emitFaceShells(gYbot, PID_W_POUCH_SIDE, true);   // -Y cap
    emitFaceShells(gYtop, PID_W_POUCH_SIDE, false);  // +Y cap

    // Bottom cap perimeter → Fix_Bottom_Edge boundary set
    for (int ix = 0;        ix < nBX;      ++ix) fixBotNids_.push_back(gYbot[0][ix]);
    for (int jz = 1;        jz < nBZ;      ++jz) fixBotNids_.push_back(gYbot[jz][nBX-1]);
    for (int ix = nBX - 2;  ix >= 0;       --ix) fixBotNids_.push_back(gYbot[nBZ-1][ix]);
    for (int jz = nBZ - 2;  jz >= 1;       --jz) fixBotNids_.push_back(gYbot[jz][0]);

    cellPids_.push_back(PID_W_POUCH_SIDE);
}

// ─────────────────────────────────────────────────────────────
// buildSideImpactor — cylinder along Y axis (side impact)
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildSideImpactor() {
    if (cfg_.indenter.type == "nail") { buildNailImpactor(); return; }
    const auto& ind = cfg_.indenter;
    double R      = ind.radius;
    double length = ind.length;
    double offset = ind.offset;
    int    nCirc  = ind.nCirc;
    int    nRadial= ind.nRadial;
    double cellH  = cfg_.geo.cellHeight;

    // Impactor center: at z = -(jBufZ_ + offset + R)  (hitting from +X side adjusted here for side)
    // Python: side impactor placed at X = -(outer_radius + offset + R) from center
    // Actually for wound, the impactor hits the side (Z direction)
    double impZ = -(jBufZ_ + offset + R);   // impactor axis
    double impX = (ind.cx > 0) ? ind.cx : cfg_.geo.cellWidth / 2.0; // centered in X

    // Y extent: centered on cell, clamped by cell height
    double yStart = std::max(0.0, (cellH - length) / 2.0);
    double yEnd   = std::min(cellH, yStart + length);
    int nY = std::max(1, (int)std::round((yEnd - yStart) / batteryMeshSize(cfg_.tier)));

    out_ << "*NODE\n";
    // Build cylinder: nRadial shells + nCirc circumferential
    std::vector<std::vector<int>> rings(nRadial + 1, std::vector<int>(nCirc));
    for (int ir = 0; ir <= nRadial; ++ir) {
        double r = R * (double)(ir + 1) / (nRadial + 1);
        if (ir == nRadial) r = R;
        for (int ic = 0; ic < nCirc; ++ic) {
            double theta = 2.0 * M_PI * ic / nCirc;
            // Cylinder axis along Y, so X and Z are cross-section plane
            double x = impX + r * std::cos(theta);
            double z = impZ + r * std::sin(theta);
            // Store first Y-ring nodes; build along Y
            (void)x; (void)z;
        }
    }

    // Simpler: solid cylinder via concentric rings
    // Use nY+1 Y planes × nCirc nodes per plane × nRadial radii
    std::vector<std::vector<std::vector<int>>> grid(
        nY + 1, std::vector<std::vector<int>>(nRadial + 1, std::vector<int>(nCirc)));

    for (int jy = 0; jy <= nY; ++jy) {
        double y = yStart + jy * (yEnd - yStart) / nY;
        for (int ir = 0; ir <= nRadial; ++ir) {
            double r = R * (double)(ir + 1) / (nRadial + 1);
            if (ir == nRadial) r = R;
            for (int ic = 0; ic < nCirc; ++ic) {
                double theta = 2.0 * M_PI * ic / nCirc;
                double x = impX + r * std::cos(theta);
                double z = impZ + r * std::sin(theta);
                int nid = addNode(x, y, z);
                grid[jy][ir][ic] = nid;
                indenterNids_.push_back(nid);
            }
        }
    }

    out_ << "*ELEMENT_SOLID\n";
    for (int jy = 0; jy < nY; ++jy) {
        for (int ir = 0; ir < nRadial; ++ir) {
            for (int ic = 0; ic < nCirc; ++ic) {
                int ic1 = (ic + 1) % nCirc;
                int n1 = grid[jy  ][ir  ][ic ];
                int n2 = grid[jy  ][ir  ][ic1];
                int n3 = grid[jy  ][ir+1][ic1];
                int n4 = grid[jy  ][ir+1][ic ];
                int n5 = grid[jy+1][ir  ][ic ];
                int n6 = grid[jy+1][ir  ][ic1];
                int n7 = grid[jy+1][ir+1][ic1];
                int n8 = grid[jy+1][ir+1][ic ];
                addSolid(PID_INDENTER, n1, n2, n3, n4, n5, n6, n7, n8);
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────
// buildNailImpactor — cone-tip + shaft nail penetrating +X face along X-axis
// Axis: X (tip at xStart = cellWidth + offset, points toward -X into cell)
// Cross-section plane: Y-Z (same as side cylinder)
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildNailImpactor() {
    const auto& ind = cfg_.indenter;
    double R_shaft  = ind.nailShaftRadius;
    double R_tip    = ind.nailTipRadius;
    double tipLen   = ind.nailTipLength;
    double totalLen = ind.radius * 2.0;   // total nail length (reuses radius field)
    double shaftLen = totalLen - tipLen;
    int nCirc = ind.nCirc;
    int nRad  = std::max(2, ind.nRadial / 2);

    double cellH = cfg_.geo.cellHeight;
    double cy    = (ind.cy > 0) ? ind.cy : cellH / 2.0;
    double cz    = 0.0;  // wound cell Z-center is at 0 (jellyroll centered on Z=0)

    // tip starts at +X face
    double xStart = cfg_.geo.cellWidth + ind.offset;

    int nTip   = std::max(3, (int)std::round(tipLen   / (batteryMeshSize(cfg_.tier) * 0.5)));
    int nShaft = std::max(4, (int)std::round(shaftLen / batteryMeshSize(cfg_.tier)));
    double dtheta = 2.0 * M_PI / nCirc;

    // Build slices: tip (tapered) then shaft (uniform R_shaft)
    std::vector<double> sliceX, sliceR;
    for (int j = 0; j <= nTip; ++j) {
        double frac = (double)j / nTip;
        sliceX.push_back(xStart + frac * tipLen);
        sliceR.push_back(R_tip + frac * (R_shaft - R_tip));
    }
    for (int j = 1; j <= nShaft; ++j) {
        double frac = (double)j / nShaft;
        sliceX.push_back(xStart + tipLen + frac * shaftLen);
        sliceR.push_back(R_shaft);
    }
    int nSlices = (int)sliceX.size();

    std::vector<int> centerNids(nSlices);
    std::vector<std::vector<std::vector<int>>> ringNids(
        nSlices, std::vector<std::vector<int>>(nRad, std::vector<int>(nCirc)));

    out_ << "*NODE\n";
    for (int j = 0; j < nSlices; ++j) {
        double x    = sliceX[j];
        double Rloc = sliceR[j];
        double dr   = Rloc / nRad;
        int cid = addNode(x, cy, cz);
        centerNids[j] = cid;
        indenterNids_.push_back(cid);
        for (int k = 0; k < nRad; ++k) {
            double r = (k + 1) * dr;
            for (int i = 0; i < nCirc; ++i) {
                double theta = i * dtheta;
                // Y-Z cross-section
                int nid = addNode(x, cy + r * std::cos(theta), cz + r * std::sin(theta));
                ringNids[j][k][i] = nid;
                indenterNids_.push_back(nid);
            }
        }
    }

    out_ << "*ELEMENT_SOLID\n";
    for (int j = 0; j < nSlices - 1; ++j) {
        // inner wedge (degenerate hex: center repeated as 4 nodes)
        for (int i = 0; i < nCirc; ++i) {
            int in = (i + 1) % nCirc;
            addSolid(PID_INDENTER,
                centerNids[j],     ringNids[j][0][i],    ringNids[j][0][in],    centerNids[j],
                centerNids[j+1],   ringNids[j+1][0][i],  ringNids[j+1][0][in],  centerNids[j+1]);
        }
        // outer hex rings
        for (int k = 1; k < nRad; ++k) {
            for (int i = 0; i < nCirc; ++i) {
                int in = (i + 1) % nCirc;
                addSolid(PID_INDENTER,
                    ringNids[j][k-1][i],    ringNids[j][k][i],    ringNids[j][k][in],    ringNids[j][k-1][in],
                    ringNids[j+1][k-1][i],  ringNids[j+1][k][i],  ringNids[j+1][k][in],  ringNids[j+1][k-1][in]);
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────
// buildDentImpactor — cylindrical punch from +Z (dent mode)
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildDentImpactor() {
    const auto& ind = cfg_.indenter;
    double R      = ind.radius;
    double thick  = 3.0;   // punch thickness in Z
    int    nCirc  = ind.nCirc;
    int    nRadial= ind.nRadial;
    double offset = ind.offset;
    double cx     = (ind.cx > 0) ? ind.cx : cfg_.geo.cellWidth  / 2.0;
    double cy     = (ind.cy > 0) ? ind.cy : cfg_.geo.cellHeight / 2.0;
    double zTop   = jBufZ_ + offset + thick;
    double zBot   = jBufZ_ + offset;

    int nZ = std::max(1, (int)std::round(thick / batteryMeshSize(cfg_.tier)));

    out_ << "*NODE\n";
    std::vector<std::vector<std::vector<int>>> grid(
        nZ + 1, std::vector<std::vector<int>>(nRadial + 1, std::vector<int>(nCirc)));

    for (int jz = 0; jz <= nZ; ++jz) {
        double z = zTop - jz * thick / nZ;
        for (int ir = 0; ir <= nRadial; ++ir) {
            double r = R * (double)(ir + 1) / (nRadial + 1);
            if (ir == nRadial) r = R;
            for (int ic = 0; ic < nCirc; ++ic) {
                double theta = 2.0 * M_PI * ic / nCirc;
                double x = cx + r * std::cos(theta);
                double y = cy + r * std::sin(theta);
                int nid = addNode(x, y, z);
                grid[jz][ir][ic] = nid;
                indenterNids_.push_back(nid);
            }
        }
    }

    out_ << "*ELEMENT_SOLID\n";
    for (int jz = 0; jz < nZ; ++jz) {
        for (int ir = 0; ir < nRadial; ++ir) {
            for (int ic = 0; ic < nCirc; ++ic) {
                int ic1 = (ic + 1) % nCirc;
                int n1 = grid[jz  ][ir  ][ic ];
                int n2 = grid[jz  ][ir  ][ic1];
                int n3 = grid[jz  ][ir+1][ic1];
                int n4 = grid[jz  ][ir+1][ic ];
                int n5 = grid[jz+1][ir  ][ic ];
                int n6 = grid[jz+1][ir  ][ic1];
                int n7 = grid[jz+1][ir+1][ic1];
                int n8 = grid[jz+1][ir+1][ic ];
                addSolid(PID_INDENTER, n1, n2, n3, n4, n5, n6, n7, n8);
            }
        }
    }
    (void)zBot;
}

// ─────────────────────────────────────────────────────────────
// buildGroundPlate — flat rigid plate at Z = -(jBufZ_ + plate_gap + plate_thick)
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildGroundPlate() {
    const auto& p  = cfg_.plate;
    double xMin = -p.margin;
    double xMax = cfg_.geo.cellWidth + p.margin;
    double yMin = -p.margin;
    double yMax = cfg_.geo.cellHeight + p.margin;
    double zTop = -(jBufZ_ + p.gap);
    double zBot = zTop - p.thickness;
    int nx = std::max(1, p.nX);
    int ny2= std::max(1, p.nY);

    double dx = (xMax - xMin) / nx;
    double dy = (yMax - yMin) / ny2;
    double dz = p.thickness;

    out_ << "*NODE\n";
    std::vector<std::vector<std::vector<int>>> grid(
        2, std::vector<std::vector<int>>(ny2+1, std::vector<int>(nx+1)));
    for (int jz = 0; jz < 2; ++jz) {
        double z = (jz == 0) ? zTop : zBot;
        for (int jy = 0; jy <= ny2; ++jy) {
            double y = yMin + jy * dy;
            for (int jx = 0; jx <= nx; ++jx) {
                double x = xMin + jx * dx;
                int nid = addNode(x, y, z);
                grid[jz][jy][jx] = nid;
                groundNids_.push_back(nid);
            }
        }
    }
    (void)dz;

    out_ << "*ELEMENT_SOLID\n";
    for (int jy = 0; jy < ny2; ++jy) {
        for (int jx = 0; jx < nx; ++jx) {
            addSolid(PID_GROUND,
                grid[0][jy  ][jx  ], grid[0][jy  ][jx+1],
                grid[0][jy+1][jx+1], grid[0][jy+1][jx  ],
                grid[1][jy  ][jx  ], grid[1][jy  ][jx+1],
                grid[1][jy+1][jx+1], grid[1][jy+1][jx  ]);
        }
    }
}

// ─────────────────────────────────────────────────────────────
// buildElectrolyte — solid ring between jellyroll and pouch
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildElectrolyte(double h_inner, double h_outer,
        double cx, double half_L, double flat_ratio,
        int n_str, int n_arc, int ny, double dy) {
    auto innerGrid = flatLoopNodes(h_inner, cx, half_L, flat_ratio, n_str, n_arc, ny, dy);
    auto outerGrid = flatLoopNodes(h_outer, cx, half_L, flat_ratio, n_str, n_arc, ny, dy);
    int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));
    out_ << "*ELEMENT_SOLID\n";
    solidFromGrids(PID_W_ELYTE, innerGrid, outerGrid, n_total, ny);
    if (std::find(cellPids_.begin(), cellPids_.end(), PID_W_ELYTE) == cellPids_.end())
        cellPids_.push_back(PID_W_ELYTE);
}

// ─────────────────────────────────────────────────────────────
// buildTabs — SHELL strips protruding in +Y from top edge
// Positive tab: inner Al CC top edge
// Negative tab: outer Cu CC top edge
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildTabs(int ny, double dy, double meshSize) {
    if (cfg_.noPcm) return;
    const auto& tabs = cfg_.tabs;
    double cellH = cfg_.geo.cellHeight;
    double cx    = cfg_.geo.cellWidth / 2.0;

    // Width filter: only nodes within tab X-range (take straight section nodes)
    double xLo_pos = tabs.posXCenter - tabs.width / 2.0;
    double xHi_pos = tabs.posXCenter + tabs.width / 2.0;
    double xLo_neg = tabs.negXCenter - tabs.width / 2.0;
    double xHi_neg = tabs.negXCenter + tabs.width / 2.0;

    // For wound model, tabs protrude in +Y from the top perimeter nodes.
    // We use x-range filter on the stored top-edge node positions.
    // Since we don't have per-node positions for all top-edge nodes (only tracked for airbag),
    // we build the tab by creating a new rectangular strip using the cell width and tab width.

    int nRows = std::max(2, (int)std::round(tabs.height / meshSize));
    double dyTab = tabs.height / nRows;
    int nColsPos = std::max(1, (int)std::round(tabs.width / meshSize));
    int nColsNeg = nColsPos;

    // Positive (Al) tab — at Z = tabAlZ_ (inner Al CC radius ≈ 0)
    {
        out_ << "*NODE\n";
        // Build rectangular tab: x ∈ [xLo_pos, xHi_pos], y from cellH upward, z = tabAlZ_
        // Bottom row uses existing top-edge nodes — approximated with new nodes at same positions
        std::vector<std::vector<int>> grid(nRows + 1, std::vector<int>(nColsPos + 1));
        for (int jy = 0; jy <= nRows; ++jy) {
            double y = cellH + jy * dyTab;
            for (int jx = 0; jx <= nColsPos; ++jx) {
                double x = xLo_pos + jx * tabs.width / nColsPos;
                grid[jy][jx] = addNode(x, y, tabAlZ_);
            }
        }
        out_ << "*ELEMENT_SHELL\n";
        for (int jy = 0; jy < nRows; ++jy)
            for (int jx = 0; jx < nColsPos; ++jx)
                addShell(PID_W_TAB_POS,
                    grid[jy][jx], grid[jy][jx+1],
                    grid[jy+1][jx+1], grid[jy+1][jx]);
        // Save top row for PCM
        for (int jx = 0; jx <= nColsPos; ++jx)
            tabPosNy_ = grid[nRows][0];  // just save first top-row nid as reference
        (void)cx; (void)xHi_pos;
    }

    // Negative (Cu) tab — at Z = tabCuZ_ (outer Cu CC radius)
    {
        out_ << "*NODE\n";
        std::vector<std::vector<int>> grid(nRows + 1, std::vector<int>(nColsNeg + 1));
        for (int jy = 0; jy <= nRows; ++jy) {
            double y = cellH + jy * dyTab;
            for (int jx = 0; jx <= nColsNeg; ++jx) {
                double x = xLo_neg + jx * tabs.width / nColsNeg;
                grid[jy][jx] = addNode(x, y, tabCuZ_);
            }
        }
        out_ << "*ELEMENT_SHELL\n";
        for (int jy = 0; jy < nRows; ++jy)
            for (int jx = 0; jx < nColsNeg; ++jx)
                addShell(PID_W_TAB_NEG,
                    grid[jy][jx], grid[jy][jx+1],
                    grid[jy+1][jx+1], grid[jy+1][jx]);
        tabNegNy_ = grid[nRows][0];
        (void)xHi_neg;
    }
    (void)ny; (void)dy;
}

// ─────────────────────────────────────────────────────────────
// buildPcm — solid HEX block bridging both tabs at top of cell
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildPcm(double meshSize) {
    if (cfg_.noPcm) return;
    const auto& tabs = cfg_.tabs;
    const auto& pcm  = cfg_.pcm;

    double xLeft  = std::min(tabs.posXCenter, tabs.negXCenter) - tabs.width / 2.0;
    double xRight = std::max(tabs.posXCenter, tabs.negXCenter) + tabs.width / 2.0;
    double zBot_c = tabAlZ_;
    double zTop_c = tabCuZ_;
    double zMid   = (zBot_c + zTop_c) * 0.5;
    double zBotP  = zMid - pcm.thickness / 2.0;
    double zTopP  = zMid + pcm.thickness / 2.0;

    double yBot = cfg_.geo.cellHeight + tabs.height;
    double yTop = yBot + pcm.height;

    int nxP = std::max(2, (int)std::round((xRight - xLeft) / meshSize));
    int nzP = std::max(1, (int)std::round(pcm.thickness / meshSize));
    int nyP = std::max(1, (int)std::round(pcm.height    / meshSize));

    out_ << "*NODE\n";
    std::vector<std::vector<std::vector<int>>> nids(
        nyP+1, std::vector<std::vector<int>>(
            nzP+1, std::vector<int>(nxP+1)));
    for (int jy = 0; jy <= nyP; ++jy) {
        double y = yBot + jy * (yTop - yBot) / nyP;
        for (int jz = 0; jz <= nzP; ++jz) {
            double z = zBotP + jz * (zTopP - zBotP) / nzP;
            for (int jx = 0; jx <= nxP; ++jx) {
                double x = xLeft + jx * (xRight - xLeft) / nxP;
                nids[jy][jz][jx] = addNode(x, y, z);
            }
        }
    }
    out_ << "*ELEMENT_SOLID\n";
    for (int jy = 0; jy < nyP; ++jy)
        for (int jz = 0; jz < nzP; ++jz)
            for (int jx = 0; jx < nxP; ++jx)
                addSolid(PID_W_PCM_POS,
                    nids[jy  ][jz  ][jx  ], nids[jy  ][jz  ][jx+1],
                    nids[jy  ][jz+1][jx+1], nids[jy  ][jz+1][jx  ],
                    nids[jy+1][jz  ][jx  ], nids[jy+1][jz  ][jx+1],
                    nids[jy+1][jz+1][jx+1], nids[jy+1][jz+1][jx  ]);
}

// ─────────────────────────────────────────────────────────────
// buildSpiralCell — conformal Archimedean spiral winding
// Adjacent windings share nodes at the Cu/Al CC interface.
// Uses fixed n_arc computed from final outer radius (uniform grid columns).
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::buildSpiralCell() {
    const auto& t   = cfg_.thick;
    const auto& geo = cfg_.geo;

    double cellWidth  = geo.cellWidth;
    double cellHeight = geo.cellHeight;
    int    nWinds     = cfg_.woundNWinds;
    double flatRatio  = cfg_.woundFlatRatio;

    double tAl  = t.alCC;
    double tCat = t.cathode;
    double tSep = t.separator;
    double tAno = t.anode;
    double tCu  = t.cuCC;
    double unitCell = tAl + tCat + tSep + tAno + tCu;

    // core_void: winding starts at mandrel radius instead of h=0
    double coreH = cfg_.coreVoid ? cfg_.woundMandrel : 0.0;
    double minCore = 0.12 / std::max(flatRatio, 0.1);
    if (coreH < minCore) coreH = minCore;

    double hMax    = coreH + unitCell * nWinds;
    double cx      = cellWidth / 2.0;
    double half_L  = (cellWidth - 2.0 * hMax * flatRatio) / 2.0;
    if (half_L < 0.0) half_L = 0.0;

    double meshSize  = batteryMeshSize(cfg_.tier);
    double meshSizeP = (cfg_.woundMeshSizePath > 0.0) ? cfg_.woundMeshSizePath : meshSize * 0.8;

    int ny = (int)std::round(cellHeight / meshSize);
    if (ny < 1) ny = 1;
    double dy = cellHeight / ny;
    int n_str = std::max(2, (int)std::round((2.0 * half_L) / meshSizeP));

    // Fixed n_arc based on outer radius (uniform column count for all windings)
    int n_arc = nArcSegs(hMax, flatRatio, meshSizeP);
    int n_total = (n_arc > 0) ? (2*n_str + 2*n_arc) : (2*(n_str+1));

    alCCPids_ = {PID_W_AL};
    cathPids_ = {PID_W_CAT};
    sepPids_  = {PID_W_SEP};
    anodePids_= {PID_W_ANO};
    cuCCPids_ = {PID_W_CU};
    jHalfL_   = half_L;

    bool doSwelling = ((cfg_.phase == 2 || cfg_.mode == "swell") && cfg_.swelling.enabled && cfg_.solidElectrode && !cfg_.useDynain);

    cellPids_ = {PID_W_AL, PID_W_CAT, PID_W_SEP, PID_W_ANO, PID_W_CU};

    out_ << "$\n$ --- Wound Layers (Spiral/Conformal) ---\n$\n";

    std::vector<int> prevCuGrid;   // outer Cu CC of previous winding → inner Al CC of next

    for (int w = 0; w < nWinds; ++w) {
        double base_h = coreH + w * unitCell;

        // Al CC grid (shared with prev winding's Cu CC, except w=0)
        std::vector<int> alGrid;
        if (w == 0) {
            out_ << "*NODE\n";
            alGrid = flatLoopNodes(base_h, cx, half_L, flatRatio, n_str, n_arc, ny, dy, &fixBotNids_);
            tabAlZ_ = base_h;
            for (int js = 0; js < n_total; ++js)
                alTabTopNids_.push_back(alGrid[ny*(n_total+1)+js]);
            if (cfg_.emRandles) emAlNids_ = alTabTopNids_;
        } else {
            alGrid = prevCuGrid;  // shared nodes — conformal interface
        }
        out_ << "*ELEMENT_SHELL\n";
        shellFromGrid(PID_W_AL, alGrid, n_total, ny);

        // Cathode
        {
            double h_outer = base_h + tCat;
            out_ << "*NODE\n";
            auto outerGrid = flatLoopNodes(h_outer, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            if (cfg_.allShell) {
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_CAT, outerGrid, n_total, ny);  // approx midplane
            } else if (cfg_.solidElectrode) {
                out_ << "*ELEMENT_SOLID\n";
                int eidBefore = nextEid_;
                solidFromGrids(PID_W_CAT, alGrid, outerGrid, n_total, ny);
                if (doSwelling)
                    for (int e = eidBefore; e < nextEid_; ++e)
                        swellElems_.push_back({e, cfg_.swelling.nmcCte});
            } else {
                out_ << "*ELEMENT_TSHELL\n";
                tshellFromGrids(PID_W_CAT, alGrid, outerGrid, n_total, ny);
            }
        }

        // Separator (axial overhang)
        {
            double h_sep = base_h + tAl + tCat;
            double sepOH = t.sepOverhang;
            out_ << "*NODE\n";
            auto baseGrid = flatLoopNodes(h_sep, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            if (sepOH > 0.0) {
                auto grid = addAxialOverhang(baseGrid, n_total, ny, sepOH,
                                             cellHeight, h_sep, cx, half_L, flatRatio, n_str, n_arc);
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_SEP, grid, n_total, ny + 2);
            } else {
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_SEP, baseGrid, n_total, ny);
            }
        }

        // Anode
        {
            double h_anoIn  = base_h + tAl + tCat + tSep;
            double h_anoOut = base_h + tAl + tCat + tSep + tAno;
            out_ << "*NODE\n";
            auto anoInGrid  = flatLoopNodes(h_anoIn,  cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            auto anoOutGrid = flatLoopNodes(h_anoOut, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            if (cfg_.allShell) {
                out_ << "*ELEMENT_SHELL\n";
                shellFromGrid(PID_W_ANO, anoInGrid, n_total, ny);
            } else if (cfg_.solidElectrode) {
                out_ << "*ELEMENT_SOLID\n";
                int eidBefore = nextEid_;
                solidFromGrids(PID_W_ANO, anoInGrid, anoOutGrid, n_total, ny);
                if (doSwelling)
                    for (int e = eidBefore; e < nextEid_; ++e)
                        swellElems_.push_back({e, cfg_.swelling.graphiteCte});
            } else {
                out_ << "*ELEMENT_TSHELL\n";
                tshellFromGrids(PID_W_ANO, anoInGrid, anoOutGrid, n_total, ny);
            }
        }

        // Cu CC — at base_h + unitCell (will be shared with next winding)
        {
            double h_cu = base_h + unitCell;
            out_ << "*NODE\n";
            auto cuGrid = flatLoopNodes(h_cu, cx, half_L, flatRatio, n_str, n_arc, ny, dy);
            out_ << "*ELEMENT_SHELL\n";
            shellFromGrid(PID_W_CU, cuGrid, n_total, ny);
            if (w == nWinds - 1) {
                for (int js = 0; js < n_total; ++js)
                    cuTabTopNids_.push_back(cuGrid[ny*(n_total+1)+js]);
                tabCuZ_ = h_cu;
                if (cfg_.emRandles) emCuNids_ = cuTabTopNids_;
            }
            prevCuGrid = cuGrid;
        }
    }

    // Electrolyte fill (when not airbag mode)
    if (!cfg_.airbagFill && t.buffer > 0.0) {
        double h_outer_e = hMax + t.buffer;
        int n_arc_e = nArcSegs(h_outer_e, flatRatio, meshSizeP);
        out_ << "*NODE\n";
        buildElectrolyte(hMax, h_outer_e, cx, half_L, flatRatio, n_str, n_arc_e, ny, dy);
    }

    // Cache outer jellyroll geometry
    jRacZ_ = hMax;
    jRacX_ = hMax * flatRatio;
    jBufZ_ = hMax + t.buffer + t.pouch / 2.0;

    double h_pouch = hMax + t.buffer;
    int n_arc_out = nArcSegs(h_pouch + t.pouch / 2.0, flatRatio, meshSizeP);
    int n_str_out = std::max(2, (int)std::round((2.0 * half_L) / meshSizeP));
    if (cfg_.airbagFill || cfg_.mode == "bare") trackPos_ = true;
    buildPouch(h_pouch, cx, half_L, flatRatio, n_str_out, n_arc_out, ny, dy);
    trackPos_ = false;

    if (!cfg_.noImpactor) {
        if (cfg_.mode == "dent") buildDentImpactor();
        else                     buildSideImpactor();
        buildGroundPlate();
    }

    if (!cfg_.noPcm) {
        buildTabs(ny, dy, meshSize);
        buildPcm(meshSize);
    }
}

// ─────────────────────────────────────────────────────────────
// writeSwellingWound — INITIAL_STRAIN_SOLID for electrode elements
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::writeSwellingWound() {
    if (swellElems_.empty()) return;
    writeSwellingStrains(out_, swellElems_, cfg_.swelling.soc);
}

// ─────────────────────────────────────────────────────────────
// writeEmRandles — SET_NODE_LIST SID=201 (Al), SID=202 (Cu)
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::writeEmRandles() {
    if (!cfg_.emRandles) return;
    writeComment(out_, "EM Randles Isopotential Node Sets");
    auto writeNSet = [&](const std::string& title, int sid, const std::vector<int>& nids) {
        if (nids.empty()) return;
        out_ << "*SET_NODE_LIST_TITLE\n" << title << "\n";
        out_ << iField(sid) << "\n";
        int cnt = 0;
        for (int nid : nids) {
            out_ << iField(nid);
            if (++cnt % 8 == 0) out_ << "\n";
        }
        if (cnt % 8 != 0) out_ << "\n";
    };
    writeNSet("EM_Al_CC_Outer",   201, emAlNids_);
    writeNSet("EM_Cu_CC_Outer",   202, emCuNids_);
}

// ─────────────────────────────────────────────────────────────
// writeAirbag — SET_SEGMENT_TITLE + AIRBAG_LINEAR_FLUID
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::writeAirbag() {
    if (pouchSegs_.empty()) return;

    // Compute signed volume via divergence theorem:
    //   V_signed = (1/3) * sum( centroid · normal * area )
    //   For a quad split into 2 triangles.
    double vSigned = 0.0;
    auto pos = [&](int nid) -> XYZ {
        auto it = trackedPos_.find(nid);
        if (it != trackedPos_.end()) return it->second;
        return {0.0, 0.0, 0.0};
    };

    for (auto& q : pouchSegs_) {
        // Split quad into 2 triangles: (n1,n2,n3) and (n1,n3,n4)
        auto p1 = pos(q[0]), p2 = pos(q[1]),
             p3 = pos(q[2]), p4 = pos(q[3]);

        auto triVol = [](const XYZ& a, const XYZ& b, const XYZ& c) -> double {
            // (1/6) * a · (b × c)
            double bxc_x = b.y*c.z - b.z*c.y;
            double bxc_y = b.z*c.x - b.x*c.z;
            double bxc_z = b.x*c.y - b.y*c.x;
            return (a.x*bxc_x + a.y*bxc_y + a.z*bxc_z) / 6.0;
        };
        vSigned += triVol(p1, p2, p3);
        vSigned += triVol(p1, p3, p4);
    }

    // If normals point inward (vSigned < 0), flip quad order
    bool flip = (vSigned < 0.0);

    writeComment(out_, "Airbag Segment Set + Linear Fluid");
    out_ << "*SET_SEGMENT_TITLE\nPouch_Airbag\n";
    out_ << iField(SID_SEG_AIRBAG) << "\n";
    for (auto& q : pouchSegs_) {
        int n1 = q[0], n2 = q[1], n3 = q[2], n4 = q[3];
        if (flip) { std::swap(n1, n2); std::swap(n3, n4); }
        char buf[80];
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d\n", n1, n2, n3, n4);
        out_ << buf;
    }

    // AIRBAG_LINEAR_FLUID  (Vol_I Card 1 + Card 3 format)
    // Electrolyte properties (t/mm/s unit system):
    //   density  ~ 1.2e-9 t/mm³  bulk mod ~ 800 MPa
    double bulk = cfg_.matElyte.bulkWound;
    double rho  = cfg_.matElyte.rho;
    out_ << "*AIRBAG_LINEAR_FLUID\n"
         << "$#     sid    sidtyp      rbid      vsca      psca      vini       mwd      spsf\n";
    char buf[160];
    snprintf(buf, sizeof(buf), "%10d%10d%10d\n", SID_SEG_AIRBAG, 0, 0);
    out_ << buf;
    out_ << "$#    bulk        ro     lcint    lcoutt    lcoutp     lcfit    lcbulk      lcid\n";
    snprintf(buf, sizeof(buf),
             "%10.1f%10.3E%10d%10d%10d%10d%10d%10d\n",
             bulk, rho, 0, 0, 0, 0, 0, 0);
    out_ << buf;
}

// ─────────────────────────────────────────────────────────────
// flushSets — SET_NODE_LIST + SET_PART_LIST
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::flushSets() {
    writeComment(out_, "Node and Part Sets");

    // SID 1: Fix bottom edge
    if (!fixBotNids_.empty()) {
        out_ << "*SET_NODE_LIST_TITLE\nFix_Bottom_Edge\n";
        out_ << iField(SID_NODE_FIX_BOT) << "\n";
        int cnt = 0;
        for (int nid : fixBotNids_) {
            out_ << iField(nid);
            if (++cnt % 8 == 0) out_ << "\n";
        }
        if (cnt % 8 != 0) out_ << "\n";
    }

    // SID 2: Impactor
    if (!indenterNids_.empty()) {
        out_ << "*SET_NODE_LIST_TITLE\nImpactor_All\n";
        out_ << iField(SID_NODE_INDENTER) << "\n";
        int cnt = 0;
        for (int nid : indenterNids_) {
            out_ << iField(nid);
            if (++cnt % 8 == 0) out_ << "\n";
        }
        if (cnt % 8 != 0) out_ << "\n";
    }

    // SID 3: Ground plate
    if (!groundNids_.empty()) {
        out_ << "*SET_NODE_LIST_TITLE\nGround_Plate\n";
        out_ << iField(SID_NODE_GROUND) << "\n";
        int cnt = 0;
        for (int nid : groundNids_) {
            out_ << iField(nid);
            if (++cnt % 8 == 0) out_ << "\n";
        }
        if (cnt % 8 != 0) out_ << "\n";
    }

    // SET_PART_LIST for contacts
    auto writePartSet = [&](const std::string& title, int sid,
                             const std::vector<int>& pids) {
        if (pids.empty()) return;
        out_ << "*SET_PART_LIST_TITLE\n" << title << "\n";
        out_ << iField(sid) << "\n";
        int cnt = 0;
        for (int pid : pids) {
            out_ << iField(pid);
            if (++cnt % 8 == 0) out_ << "\n";
        }
        if (cnt % 8 != 0) out_ << "\n";
    };

    writePartSet("Cell_All",      SID_PART_CELL,      cellPids_);
    writePartSet("Al_CC",         103,                 alCCPids_);
    writePartSet("Cathode",       104,                 cathPids_);
    writePartSet("Separator",     105,                 sepPids_);
    writePartSet("Anode",         106,                 anodePids_);
    writePartSet("Cu_CC",         107,                 cuCCPids_);
    if (!indenterNids_.empty())
        writePartSet("Impactor",  108,                 {PID_INDENTER});
    if (!groundNids_.empty())
        writePartSet("Ground",    109,                 {PID_GROUND});

    // Bare mode: SET_SEGMENT_TITLE for external pressure load (SID_SEG_POUCH_LOAD=503)
    if (cfg_.mode == "bare" && !pouchSegs_.empty()) {
        writeComment(out_, "Pouch Segment Set (bare mode external pressure)");
        out_ << "*SET_SEGMENT_TITLE\nPouch_Outer_Load\n";
        out_ << iField(SID_SEG_POUCH_LOAD) << "\n";
        for (auto& q : pouchSegs_) {
            char buf[80];
            snprintf(buf, sizeof(buf), "%10d%10d%10d%10d\n", q[0], q[1], q[2], q[3]);
            out_ << buf;
        }
    }
}

// ─────────────────────────────────────────────────────────────
// flushParts — *PART cards
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::flushParts() {
    writeComment(out_, "Parts");

    auto wp = [&](const std::string& name, int pid, int sid, int mid, int hgid) {
        writePart(out_, name, pid, sid, mid, hgid, 0);
    };

    bool solidElec = cfg_.solidElectrode;
    int  secCat    = solidElec ? SID_W_SOLID_ELEC : SID_W_TSHELL_CAT;
    int  secAno    = solidElec ? SID_W_SOLID_ELEC : SID_W_TSHELL_ANO;
    int  hgElec    = solidElec ? 0                : HGID_SOLID;

    wp("Wound_Al_CC",   PID_W_AL,  SID_W_SHELL_AL, MID_AL,  HGID_SHELL);
    wp("Wound_Cathode", PID_W_CAT, secCat,          MID_CAT, hgElec);
    wp("Wound_Sep",     PID_W_SEP, SID_W_SHELL_SEP, MID_SEP, 0);
    wp("Wound_Anode",   PID_W_ANO, secAno,           MID_ANO, hgElec);
    wp("Wound_Cu_CC",   PID_W_CU,  SID_W_SHELL_CU,  MID_CU,  HGID_SHELL);

    wp("Wound_Pouch", PID_W_POUCH_SIDE, SID_SHELL_POUCH, MID_POUCH, HGID_SHELL);

    // Core fill electrolyte (inner core void filled with electrolyte solid)
    if (std::find(cellPids_.begin(), cellPids_.end(), PID_W_ELYTE) != cellPids_.end())
        wp("Wound_Electrolyte", PID_W_ELYTE, SID_W_SOLID_ELEC, MID_ELYTE_SOLID, HGID_SOLID);

    if (!cfg_.noPcm) {
        wp("Wound_Tab_Pos", PID_W_TAB_POS, SID_SHELL_AL, MID_AL, HGID_SHELL);
        wp("Wound_Tab_Neg", PID_W_TAB_NEG, SID_SHELL_CU, MID_CU, HGID_SHELL);
        wp("Wound_PCM_Pos", PID_W_PCM_POS, SID_SOLID_RIGID, MID_RIGID, 0);
    }

    if (!indenterNids_.empty())
        wp("Impactor",      PID_INDENTER, SID_SOLID_RIGID, MID_RIGID, 0);
    if (!groundNids_.empty())
        wp("Ground_Plate",  PID_GROUND,   SID_SOLID_RIGID, MID_RIGID, 0);
}

// ─────────────────────────────────────────────────────────────
// flushContacts — wound model contacts
// ─────────────────────────────────────────────────────────────
void WoundMeshGen::flushContacts() {
    writeComment(out_, "Contacts");

    double meshSize = batteryMeshSize(cfg_.tier);
    double sofscl   = batterySofscl(meshSize,
                                    cfg_.contact.sofscl_base,
                                    5.0,
                                    cfg_.contact.sofscl_pow);
    double sst = cfg_.contact.sst_ext;
    char buf[256];

    // STS: impactor-to-cell
    if (!indenterNids_.empty()) {
        out_ << "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n"
             << "$#   cid                                                             title\n"
             << "         1  Impactor_to_Cell\n"
             << "$#  ssid    msid   sstyp   mstyp  sboxid  mboxid     spr     mpr\n";
        snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d%8d%8d\n",
                 108, SID_PART_CELL, 2, 2, 0, 0, 0, 0);
        out_ << buf;
        out_ << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n"
             << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0)
             << iField(0) << fldG(0.0) << fldG(1.0e20) << "\n";
        out_ << "$#      sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n";
        snprintf(buf, sizeof(buf), "%10.3f%10.3f%10.4f%10.4f%10.3f%10.3f%10.3f%10.3f\n",
                 1.0, 1.0, sst, sst, 1.0, 1.0, 1.0, 1.0);
        out_ << buf;
        out_ << "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n";
        snprintf(buf, sizeof(buf), "%10d%10.4f%10d%10.4f%10.3f%10d%10d%10d\n",
                 1, sofscl, 0, 1.375, 3.0, 5, 0, 1);
        out_ << buf;
    }

    // ASS: cell self-contact
    out_ << "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n"
         << "$#   cid                                                             title\n"
         << "         2  Cell_Self_Contact\n"
         << "$#  ssid    msid   sstyp   mstyp  sboxid  mboxid     spr     mpr\n";
    snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d%8d%8d\n",
             SID_PART_CELL, 0, 2, 0, 0, 0, 0, 0);
    out_ << buf;
    // Card 2: VDC=20 suppresses contact oscillations during DR
    out_ << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n"
         << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(0.0) << fldG(20.0)
         << iField(0) << fldG(0.0) << fldG(1.0e20) << "\n";
    out_ << "$#      sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n";
    snprintf(buf, sizeof(buf), "%10.3f%10.3f%10.4f%10.4f%10.3f%10.3f%10.3f%10.3f\n",
             1.0, 1.0, cfg_.contact.sst_self, cfg_.contact.sst_self, 1.0, 1.0, 1.0, 1.0);
    out_ << buf;
    // Card A: SOFT=2 (segment-based, stable for thin elements)
    out_ << "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n";
    snprintf(buf, sizeof(buf), "%10d%10.4f%10d%10.4f%10.3f%10d%10d%10d\n",
             2, sofscl, 0, 1.375, 3.0, 5, 0, 1);
    out_ << buf;
    // Card C: IGNORE=1
    out_ << "$#  ignore      bckt    lcbckt   ns2trk    initrk   partefx    cparm8\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d\n",
             1, 0, 0, 0, 0, 0, 0);
    out_ << buf;
}

// ─────────────────────────────────────────────────────────────
// build — main entry point
// ─────────────────────────────────────────────────────────────
MeshStats WoundMeshGen::build() {
    if (cfg_.woundFlat) {
        buildFlatCell();
    } else {
        buildSpiralCell();
    }

    // Parts + Sets + Contacts (appended after mesh data)
    flushParts();
    flushSets();
    if (cfg_.airbagFill) writeAirbag();
    if (cfg_.emRandles)  writeEmRandles();
    if (!swellElems_.empty()) writeSwellingWound();
    flushContacts();

    MeshStats st;
    st.nNodes  = nNodes_;
    st.nShells = nShells_ + nTShells_;
    st.nSolids = nSolids_;
    st.totalZ  = 2.0 * (cfg_.thick.cathode + cfg_.thick.anode +
                        cfg_.thick.alCC + cfg_.thick.cuCC +
                        cfg_.thick.separator) * cfg_.woundNWinds;
    return st;
}

// ─────────────────────────────────────────────────────────────
// writeMeshWound — public API
// ─────────────────────────────────────────────────────────────
MeshStats writeMeshWound(std::ostream& out, const BatteryConfig& cfg) {
    WoundMeshGen gen(cfg, out);
    return gen.build();
}

} // namespace bat
